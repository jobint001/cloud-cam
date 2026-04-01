"""test_gaze_engine.py — unit tests for GazeEngine hysteresis logic."""

import pytest

from cloudcam.gaze_engine import GazeEngine


class TestGazeEngineDefaults:
    def test_initial_camera_is_A(self):
        engine = GazeEngine()
        assert engine.active_camera == "A"

    def test_no_switch_below_threshold(self):
        engine = GazeEngine(yaw_threshold=20.0, hysteresis=5.0)
        engine.update(15.0)   # below 20+5 = 25
        assert engine.active_camera == "A"

    def test_switch_to_B_above_threshold_plus_hysteresis(self):
        engine = GazeEngine(yaw_threshold=20.0, hysteresis=5.0)
        engine.update(26.0)   # 26 > 20+5 = 25
        assert engine.active_camera == "B"

    def test_no_switch_back_inside_dead_band(self):
        engine = GazeEngine(yaw_threshold=20.0, hysteresis=5.0)
        engine.update(30.0)   # switch to B
        engine.update(-20.0)  # -20 is NOT below -(20+5) = -25
        assert engine.active_camera == "B"

    def test_switch_back_to_A_past_negative_threshold(self):
        engine = GazeEngine(yaw_threshold=20.0, hysteresis=5.0)
        engine.update(30.0)   # switch to B
        engine.update(-26.0)  # switch back to A
        assert engine.active_camera == "A"

    def test_rapid_yaw_sequence(self):
        engine = GazeEngine(yaw_threshold=20.0, hysteresis=5.0)
        yaw_sequence = [0, 10, 24, 25, 26, 20, 10, 0, -10, -25, -26, -30, 0]
        results = [engine.update(y) for y in yaw_sequence]
        # Should switch to B at yaw=26 and back to A at yaw=-26.
        assert results[6] == "B"   # yaw=20, still B (inside dead-band coming back)
        assert results[11] == "A"  # yaw=-30, back to A

    def test_reset_forces_camera_A(self):
        engine = GazeEngine(yaw_threshold=20.0, hysteresis=5.0)
        engine.update(30.0)
        assert engine.active_camera == "B"
        engine.reset()
        assert engine.active_camera == "A"

    def test_invalid_hysteresis_raises(self):
        with pytest.raises(ValueError):
            GazeEngine(hysteresis=-1.0)
