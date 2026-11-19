"""tray_ui.py — system-tray icon and configuration menu via pystray."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

try:
    import pystray

    _PYSTRAY_ERROR: Exception | None = None
except Exception as _exc:  # noqa: BLE001 - pystray raises ImportError when no
    pystray = None            # Linux tray backend (Xlib/GTK/AppIndicator) is present
    _PYSTRAY_ERROR = _exc

from PIL import Image, ImageDraw

from cloudcam import config as cfg_module
from cloudcam.config import Config

logger = logging.getLogger(__name__)

_ICON_PATH = Path(__file__).resolve().parents[3] / "assets" / "icon.png"


def _make_default_icon() -> Image.Image:
    """Generate a simple coloured circle as the tray icon fallback."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(52, 152, 219), outline=(255, 255, 255), width=3)
    return img


def _load_icon() -> Image.Image:
    if _ICON_PATH.exists():
        return Image.open(_ICON_PATH).convert("RGBA")
    return _make_default_icon()


class TrayUI:
    """Manages the system-tray icon and live configuration menu.

    Args:
        cfg: Mutable :class:`~cloudcam.config.Config` instance shared with all
            other components.
        on_config_change: Called (with the updated config) whenever the user
            changes a setting via the tray menu.
        on_quit: Called when the user selects Quit from the tray menu.
    """

    def __init__(
        self,
        cfg: Config,
        on_config_change: Callable[[Config], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._cfg = cfg
        self._on_change = on_config_change
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None

    def start(self) -> None:
        """Run the tray icon event loop in the calling thread (blocks).

        On Linux a tray backend (Xlib, GTK or AppIndicator) is required.  If
        none is available the method logs a warning and returns instead of
        crashing, so the app can still run headless.
        """
        if pystray is None:
            logger.warning(
                "System tray unavailable (%s); running without a tray icon.",
                _PYSTRAY_ERROR,
            )
            return
        try:
            self._icon = pystray.Icon(
                name="cloud-cam",
                icon=_load_icon(),
                title="Cloud Cam",
                menu=self._build_menu(),
            )
            self._icon.run()
        except Exception as exc:  # noqa: BLE001 - e.g. no X display on Linux
            logger.warning("System tray could not start: %s", exc)
            self._icon = None

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> pystray.Menu:
        def _set_cam_a(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
            idx = self._prompt_int("Camera A device index", self._cfg.camera_a)
            if idx is not None:
                self._cfg.camera_a = idx
                self._save_and_notify()

        def _set_cam_b(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
            idx = self._prompt_int("Camera B device index", self._cfg.camera_b)
            if idx is not None:
                self._cfg.camera_b = idx
                self._save_and_notify()

        def _set_threshold(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
            val = self._prompt_float("Yaw threshold (degrees)", self._cfg.yaw_threshold)
            if val is not None:
                self._cfg.yaw_threshold = val
                self._save_and_notify()

        def _set_hysteresis(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
            val = self._prompt_float("Hysteresis (degrees)", self._cfg.hysteresis)
            if val is not None:
                self._cfg.hysteresis = val
                self._save_and_notify()

        def _quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
            icon.stop()
            self._on_quit()

        return pystray.Menu(
            pystray.MenuItem("Set Camera A index", _set_cam_a),
            pystray.MenuItem("Set Camera B index", _set_cam_b),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Set yaw threshold", _set_threshold),
            pystray.MenuItem("Set hysteresis", _set_hysteresis),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _quit),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save_and_notify(self) -> None:
        cfg_module.save(self._cfg)
        self._on_change(self._cfg)

    @staticmethod
    def _prompt_int(label: str, current: int) -> int | None:
        """Show a simple console prompt (no GUI dependency required)."""
        try:
            raw = input(f"{label} [{current}]: ").strip()
            return int(raw) if raw else None
        except (ValueError, EOFError):
            return None

    @staticmethod
    def _prompt_float(label: str, current: float) -> float | None:
        try:
            raw = input(f"{label} [{current:.1f}]: ").strip()
            return float(raw) if raw else None
        except (ValueError, EOFError):
            return None
