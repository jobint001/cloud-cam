"""virtual_cam.py — write frames from a queue into a pyvirtualcam virtual device."""

from __future__ import annotations

import logging
import queue
import sys
import threading
import time

import cv2
import numpy as np
import pyvirtualcam

from cloudcam.config import Config

logger = logging.getLogger(__name__)


def _backend_hint() -> str:
    """Return a platform-specific install hint for the virtual camera backend."""
    if sys.platform.startswith("linux"):
        return (
            "Ensure the v4l2loopback kernel module is loaded:\n"
            "  sudo modprobe v4l2loopback exclusive_caps=1 "
            'card_label="Cloud Cam"\n'
            "Install with: sudo apt install v4l2loopback-dkms v4l2loopback-utils\n"
            "Then set 'vcam_device' in config.json to the loopback device "
            "(e.g. /dev/video2)."
        )
    return (
        "Ensure a virtual camera backend is installed "
        "(OBS Virtual Camera or UnityCapture)."
    )


class VirtualCamWriter:
    """Reads BGR frames from *input_queue* and pushes them to the virtual cam.

    Uses ``pyvirtualcam``, which supports the OBS Virtual Camera and
    UnityCapture backends on Windows, OBS on macOS, and v4l2loopback on Linux.
    """

    def __init__(
        self,
        cfg: Config,
        input_queue: "queue.Queue[np.ndarray]",
    ) -> None:
        self._cfg = cfg
        self._queue = input_queue
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop,
            name="vcam-writer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    # ------------------------------------------------------------------

    def _loop(self) -> None:
        target_w = self._cfg.width
        target_h = self._cfg.height
        fps = self._cfg.fps
        frame_interval = 1.0 / fps

        # On Linux the loopback device is chosen explicitly; on other
        # platforms pyvirtualcam auto-selects the backend.
        device = getattr(self._cfg, "vcam_device", "") or None
        kwargs: dict = {"device": device} if device else {}

        try:
            with pyvirtualcam.Camera(
                width=target_w,
                height=target_h,
                fps=fps,
                fmt=pyvirtualcam.PixelFormat.BGR,
                **kwargs,
            ) as cam:
                logger.info("Virtual camera opened: %s", cam.device)
                while not self._stop_event.is_set():
                    t0 = time.monotonic()
                    try:
                        frame = self._queue.get(timeout=frame_interval * 2)
                    except queue.Empty:
                        continue

                    # Resize if the source resolution differs from target.
                    h, w = frame.shape[:2]
                    if w != target_w or h != target_h:
                        frame = cv2.resize(frame, (target_w, target_h))

                    cam.send(frame)
                    elapsed = time.monotonic() - t0
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0:
                        cam.sleep_until_next_frame()
        except Exception as exc:
            logger.error("Virtual camera error: %s", exc)
            logger.error(_backend_hint())
