"""config.py — load and persist user configuration from config.json."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_config_path() -> Path:
    """Return the platform-appropriate config.json location.

    On Linux the install directory is often read-only, so config lives under
    the XDG config dir (``$XDG_CONFIG_HOME/cloud-cam/config.json``, falling
    back to ``~/.config/cloud-cam/config.json``).  Windows and macOS keep the
    historical repo-root location.
    """
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(base) / "cloud-cam" / "config.json"
    return Path(__file__).resolve().parents[3] / "config.json"


_CONFIG_PATH = _default_config_path()


@dataclass
class Config:
    camera_a: int = 0
    camera_b: int = 1
    yaw_threshold: float = 15.0   # degrees before switching cameras
    hysteresis: float = 3.0       # dead-band around threshold
    fps: int = 30
    width: int = 1280
    height: int = 720
    vcam_device: str = ""         # Linux: v4l2loopback device, e.g. /dev/video2


def load(path: Path = _CONFIG_PATH) -> Config:
    """Load config from *path*; return defaults if file is missing or malformed."""
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            # Only accept known keys so unknown keys are silently ignored.
            known = {f for f in Config.__dataclass_fields__}
            filtered = {k: v for k, v in raw.items() if k in known}
            return Config(**filtered)
        except Exception as exc:
            logger.warning("Could not parse %s (%s); using defaults.", path, exc)
    return Config()


def save(cfg: Config, path: Path = _CONFIG_PATH) -> None:
    """Persist *cfg* to *path* as pretty-printed JSON."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(cfg), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Could not save config to %s: %s", path, exc)
