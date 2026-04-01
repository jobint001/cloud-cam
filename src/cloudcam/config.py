"""config.py — load and persist user configuration from config.json."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.json"


@dataclass
class Config:
    camera_a: int = 0
    camera_b: int = 1
    yaw_threshold: float = 15.0   # degrees before switching cameras
    hysteresis: float = 3.0       # dead-band around threshold
    fps: int = 30
    width: int = 1280
    height: int = 720


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
        path.write_text(
            json.dumps(asdict(cfg), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Could not save config to %s: %s", path, exc)
