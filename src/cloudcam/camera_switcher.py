"""camera_switcher.py — select the active frame and push it to an output queue."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

from cloudcam.config import Config
from cloudcam.gaze_engine import GazeEngine
from cloudcam.head_pose import HeadPoseTracker

if TYPE_CHECKING:
    from cloudcam.camera_manager import CameraManager

# Resize factor for inference — 0.5 × 1280×720 = 640×360 (good balance).
_INFER_SCALE = 0.5
# Run inference on every frame for minimum latency.
_INFER_EVERY = 1
# EMA weight — 0.55 tracks angle changes quickly while still smoothing noise.
_EMA_ALPHA = 0.55
# Frames without a detected face before we stop updating the gaze engine.
_NO_FACE_HOLD_FRAMES = 15
# Suppress gaze updates during extreme vertical poses (looking sharply up/down).
_PITCH_GATE_DEG = 45.0

logger = logging.getLogger(__name__)


class CameraSwitcher:
    """Ties together the tracker, gaze engine, and camera manager.

    Runs a loop that:
    1. Grabs the latest frame from the currently active camera.
    2. Runs head-pose estimation on it.
    3. Asks the gaze engine which camera should be active.
    4. Puts the selected frame into *output_queue* for the virtual cam writer.
    """

    def __init__(
        self,
        camera_manager: "CameraManager",
        gaze_engine: GazeEngine,
        tracker: HeadPoseTracker,
        output_queue: "queue.Queue[np.ndarray]",
        cfg: Config | None = None,
    ) -> None:
        self._mgr = camera_manager
        self._gaze = gaze_engine
        self._tracker = tracker
        self._queue = output_queue
        self._cfg = cfg
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop,
            name="switcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._tracker.close()

    # ------------------------------------------------------------------

    def _loop(self) -> None:
        fps = self._cfg.fps if self._cfg else 30
        frame_interval = 1.0 / fps
        frame_count = 0
        smoothed_yaw: float | None = None
        no_face_streak = 0  # consecutive inference frames with no face

        while not self._stop_event.is_set():
            t0 = time.monotonic()

            active = self._gaze.active_camera
            frame = self._mgr.get_frame(active)

            if frame is None:
                other_id = "B" if active == "A" else "A"
                frame = self._mgr.get_frame(other_id)  # type: ignore[arg-type]

            if frame is None:
                time.sleep(0.005)
                continue

            # --- Inference (downscaled, every N frames) ---
            frame_count += 1
            if frame_count % _INFER_EVERY == 0:
                h, w = frame.shape[:2]
                infer_w = max(1, int(w * _INFER_SCALE))
                infer_h = max(1, int(h * _INFER_SCALE))
                small = cv2.resize(frame, (infer_w, infer_h))
                pose = self._tracker.process(small)

                # If active camera has no face, try the other camera.
                if pose is None:
                    other_id = "B" if active == "A" else "A"
                    other_frame = self._mgr.get_frame(other_id)  # type: ignore[arg-type]
                    if other_frame is not None:
                        small_other = cv2.resize(other_frame, (infer_w, infer_h))
                        pose = self._tracker.process(small_other)

                if pose is not None and pose.confidence > 0.3:
                    # Pitch gate: ignore extreme up/down poses (noisy yaw).
                    if abs(pose.pitch) < _PITCH_GATE_DEG:
                        no_face_streak = 0
                        if smoothed_yaw is None:
                            smoothed_yaw = pose.yaw
                        else:
                            smoothed_yaw = (_EMA_ALPHA * pose.yaw
                                            + (1.0 - _EMA_ALPHA) * smoothed_yaw)
                        self._gaze.update(smoothed_yaw)
                else:
                    no_face_streak += 1
                    # After prolonged absence, clear EMA so next detection
                    # starts fresh rather than from a stale accumulated value.
                    if no_face_streak > _NO_FACE_HOLD_FRAMES * 3:
                        smoothed_yaw = None

            # --- Output ---
            if self._queue.qsize() < 4:
                self._queue.put_nowait(frame)

            # --- Rate limit to target FPS ---
            elapsed = time.monotonic() - t0
            sleep_t = frame_interval - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)
