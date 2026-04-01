"""gaze_engine.py — decide which camera is active based on head yaw."""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

CamId = Literal["A", "B"]


class GazeEngine:
    """Converts a yaw angle into a camera selection with hysteresis.

    When the head turns right (positive yaw) past ``yaw_threshold``,
    Camera B (right monitor cam) becomes active.  When the head turns left
    (negative yaw) past ``-yaw_threshold``, Camera A (left monitor cam)
    becomes active.  The ``hysteresis`` dead-band prevents rapid toggling
    near the boundary: once a camera is selected it remains selected until
    the yaw crosses ``threshold ± hysteresis`` in the opposite direction.

    Args:
        yaw_threshold: Absolute yaw angle (degrees) at which a switch is made.
        hysteresis: Half-width of the dead-band around the threshold.
    """

    def __init__(self, yaw_threshold: float = 20.0, hysteresis: float = 5.0) -> None:
        if hysteresis < 0:
            raise ValueError("hysteresis must be >= 0")
        self.yaw_threshold = yaw_threshold
        self.hysteresis = hysteresis
        self._active: CamId = "A"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def active_camera(self) -> CamId:
        """The currently selected camera (``"A"`` or ``"B"``)."""
        return self._active

    def update(self, yaw: float) -> CamId:
        """Feed a new yaw reading and return the (possibly updated) active camera.

        Args:
            yaw: Head yaw in degrees.  Positive = looking right.
        """
        if self._active == "A":
            # Switch to B only when yaw exceeds threshold + hysteresis.
            if yaw > self.yaw_threshold + self.hysteresis:
                self._active = "B"
                logger.debug("Switched to Camera B (yaw=%.1f°)", yaw)
        else:
            # Switch back to A only when yaw drops below -(threshold + hysteresis).
            if yaw < -(self.yaw_threshold + self.hysteresis):
                self._active = "A"
                logger.debug("Switched to Camera A (yaw=%.1f°)", yaw)
        return self._active

    def reset(self) -> None:
        """Force-reset to Camera A."""
        self._active = "A"
