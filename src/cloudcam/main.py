"""main.py — entry point; orchestrates all threads and components."""

from __future__ import annotations

import logging
import logging.handlers
import queue
import signal
import sys
import threading
from pathlib import Path

# Allow `python3 src/cloudcam/main.py` to work without pip install.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cloudcam import config as cfg_module
from cloudcam.camera_manager import CameraManager
from cloudcam.camera_switcher import CameraSwitcher
from cloudcam.config import Config
from cloudcam.gaze_engine import GazeEngine
from cloudcam.head_pose import HeadPoseTracker
from cloudcam.tray_ui import TrayUI
from cloudcam.virtual_cam import VirtualCamWriter

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "cloudcam.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class Application:
    def __init__(self) -> None:
        self._cfg = cfg_module.load()
        self._shutdown = threading.Event()
        self._signal_received = False      # set lock-free from signal handler
        self._cleanup_lock = threading.Lock()
        self._cleaned_up = False
        self._cleanup_done = threading.Event()
        self._frame_queue: queue.Queue = queue.Queue(maxsize=8)

        # Core components
        self._cam_mgr = CameraManager(self._cfg)
        self._tracker = HeadPoseTracker()
        self._gaze = GazeEngine(
            yaw_threshold=self._cfg.yaw_threshold,
            hysteresis=self._cfg.hysteresis,
        )
        self._switcher = CameraSwitcher(
            camera_manager=self._cam_mgr,
            gaze_engine=self._gaze,
            tracker=self._tracker,
            output_queue=self._frame_queue,
            cfg=self._cfg,
        )
        self._vcam = VirtualCamWriter(
            cfg=self._cfg,
            input_queue=self._frame_queue,
        )
        self._tray = TrayUI(
            cfg=self._cfg,
            on_config_change=self._on_config_change,
            on_quit=self._on_quit,
        )

    def run(self) -> None:
        logger.info("Cloud Cam starting up.")
        self._cam_mgr.start()
        self._switcher.start()
        self._vcam.start()

        # Run pystray on a background thread so the main thread stays free
        # to receive SIGINT — pystray's Win32 message loop blocks all Python
        # signal delivery when it owns the main thread.
        tray_thread = threading.Thread(
            target=self._tray.start,
            name="tray",
            daemon=True,
        )
        tray_thread.start()

        try:
            # SIGTERM (e.g. `systemctl stop`, `kill`) — common on Linux.
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, self._on_signal)
            # Main thread just waits; Ctrl+C raises KeyboardInterrupt here.
            while not self._shutdown.is_set() and not self._signal_received:
                self._shutdown.wait(timeout=0.5)
            if self._signal_received:
                logger.info("SIGTERM received — shutting down.")
        except KeyboardInterrupt:
            logger.info("Ctrl+C received — shutting down.")
        finally:
            self._shutdown_all()
            tray_thread.join(timeout=3.0)

    # ------------------------------------------------------------------

    def _on_signal(self, signum: int, _frame: object) -> None:
        # Signal handlers run in the main thread and may interrupt the
        # Event's internal lock; only flip a plain flag here and let the
        # main loop do the logging and synchronised shutdown work.
        self._signal_received = True

    # ------------------------------------------------------------------

    def _on_config_change(self, new_cfg: Config) -> None:
        """Apply live-reloadable settings without full restart."""
        self._gaze.yaw_threshold = new_cfg.yaw_threshold
        self._gaze.hysteresis = new_cfg.hysteresis
        logger.info(
            "Config updated: threshold=%.1f°  hysteresis=%.1f°",
            new_cfg.yaw_threshold,
            new_cfg.hysteresis,
        )

    def _on_quit(self) -> None:
        logger.info("Quit requested from tray.")
        self._shutdown.set()
        self._shutdown_all()

    def _shutdown_all(self) -> None:
        # Guard cleanup with its own flag: a shutdown *request* (which sets
        # ``_shutdown``) must not be mistaken for cleanup already performed.
        with self._cleanup_lock:
            owner = not self._cleaned_up
            if owner:
                self._cleaned_up = True
        if not owner:
            # Another caller is already stopping the components; wait for it
            # to finish so callers never return while stop() calls are still
            # running (e.g. so ``run()`` cannot exit mid-teardown).
            self._cleanup_done.wait()
            return
        self._shutdown.set()
        logger.info("Shutting down.")
        try:
            self._tray.stop()
            self._switcher.stop()
            self._vcam.stop()
            self._cam_mgr.stop()
        finally:
            self._cleanup_done.set()


def main() -> None:
    Application().run()


if __name__ == "__main__":
    main()
