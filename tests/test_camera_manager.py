"""test_camera_manager.py — unit tests for CameraManager with mocked OpenCV."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cloudcam.config import Config


class TestCameraManagerEnumerate:
    def test_enumerate_returns_open_indices(self):
        """enumerate_cameras() should return only indices where isOpened() is True."""
        mock_cap_open = MagicMock()
        mock_cap_open.isOpened.return_value = True
        mock_cap_closed = MagicMock()
        mock_cap_closed.isOpened.return_value = False

        def fake_videocapture(idx, *args, **kwargs):
            return mock_cap_open if idx in (0, 1) else mock_cap_closed

        with patch("cloudcam.camera_manager.cv2.VideoCapture", side_effect=fake_videocapture):
            from cloudcam.camera_manager import CameraManager
            result = CameraManager.enumerate_cameras(max_index=4)

        assert result == [0, 1]


class TestCameraManagerFrameAccess:
    def test_get_frame_returns_none_before_start(self):
        from cloudcam.camera_manager import CameraManager
        mgr = CameraManager(Config())
        assert mgr.get_frame("A") is None
        assert mgr.get_frame("B") is None

    def test_get_frame_returns_copy(self):
        from cloudcam.camera_manager import CameraManager
        fake_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        mgr = CameraManager(Config())
        mgr._frames["A"] = fake_frame  # type: ignore[index]
        result = mgr.get_frame("A")
        assert result is not None
        assert result is not fake_frame  # must be a copy
        np.testing.assert_array_equal(result, fake_frame)
