"""camera_manager.py — open and read frames from two physical cameras."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Literal

import cv2
import numpy as np

from cloudcam.config import Config

logger = logging.getLogger(__name__)

CamId = Literal["A", "B"]

# Pick the fastest native camera backend for the current OS.
# CAP_DSHOW  — Windows Direct Show  (avoids index-mapping issues on Windows)
# CAP_AVFOUNDATION — macOS AVFoundation (required; cv2.VideoCapture with 0 uses it anyway)
# CAP_ANY (0) — Linux and fallback
if sys.platform == "win32":
    _CAM_BACKEND = cv2.CAP_DSHOW
elif sys.platform == "darwin":
    _CAM_BACKEND = cv2.CAP_AVFOUNDATION
else:
    _CAM_BACKEND = cv2.CAP_ANY


class CameraManager:
    """Opens Camera A and Camera B and provides thread-safe frame access.

    Each camera is read in its own background thread so that a slow camera
    never blocks the other.
    """

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._caps: dict[CamId, cv2.VideoCapture] = {}
        self._frames: dict[CamId, np.ndarray | None] = {"A": None, "B": None}
        self._locks: dict[CamId, threading.Lock] = {
            "A": threading.Lock(),
            "B": threading.Lock(),
        }
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open both cameras and start capture threads."""
        self._open_camera("A", self._cfg.camera_a)
        self._open_camera("B", self._cfg.camera_b)
        for cam_id in ("A", "B"):
            t = threading.Thread(
                target=self._capture_loop,
                args=(cam_id,),
                name=f"capture-{cam_id}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        """Signal capture threads to stop and release camera handles."""
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=2.0)
        for cap in self._caps.values():
            cap.release()
        self._caps.clear()

    def get_frame(self, cam_id: CamId) -> np.ndarray | None:
        """Return the latest frame from *cam_id*, or ``None`` if unavailable."""
        with self._locks[cam_id]:
            frame = self._frames[cam_id]
            return frame.copy() if frame is not None else None

    @staticmethod
    def enumerate_cameras(max_index: int = 8) -> list[int]:
        """Return a list of device indices that successfully open."""
        available: list[int] = []
        for idx in range(max_index):
            cap = cv2.VideoCapture(idx, _CAM_BACKEND)
            if cap.isOpened():
                available.append(idx)
            cap.release()
        return available

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_camera(self, cam_id: CamId, index: int) -> None:
        cap = cv2.VideoCapture(index, _CAM_BACKEND)
        if not cap.isOpened():
            logger.error("Camera %s (index %d) could not be opened.", cam_id, index)
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._cfg.height)
        cap.set(cv2.CAP_PROP_FPS, self._cfg.fps)
        # Keep only the latest frame in the driver buffer — prevents stale frame accumulation.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._caps[cam_id] = cap
        logger.info("Camera %s opened (index %d).", cam_id, index)

    def _capture_loop(self, cam_id: CamId) -> None:
        cap = self._caps.get(cam_id)
        if cap is None:
            return
        while not self._stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                logger.warning("Camera %s read failed; retrying.", cam_id)
                continue
            with self._locks[cam_id]:
                self._frames[cam_id] = frame
