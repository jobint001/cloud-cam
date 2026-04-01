"""head_pose.py — estimate yaw and pitch from a face in a BGR frame."""

from __future__ import annotations

import logging
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
_MODEL_PATH = Path(__file__).resolve().parent / "face_landmarker.task"

# 15 well-distributed MediaPipe 478-landmark indices.
# Using more points spreads error and covers typical out-of-plane rotations.
_LANDMARK_IDS = [
    1,    # nose tip
    152,  # chin
    263,  # left eye outer corner
    33,   # right eye outer corner
    287,  # left mouth corner
    57,   # right mouth corner
    168,  # nose bridge
    10,   # forehead centre
    109,  # right temple
    338,  # left temple
    61,   # right lip corner
    291,  # left lip corner
    199,  # chin tip
    4,    # nose below bridge
    197,  # nose side right
]

# Corresponding 3-D positions in mm in a canonical frontal face model.
_MODEL_POINTS = np.array([
    [ 0.0,    0.0,    0.0  ],   # 1   nose tip
    [ 0.0,  -63.6,  -12.5 ],   # 152 chin
    [-43.3,  32.7,  -26.0 ],   # 263 left eye outer corner
    [ 43.3,  32.7,  -26.0 ],   # 33  right eye outer corner
    [-28.9, -28.9,  -24.1 ],   # 287 left mouth corner
    [ 28.9, -28.9,  -24.1 ],   # 57  right mouth corner
    [  0.0,  10.0,   -4.0 ],   # 168 nose bridge
    [  0.0,  68.0,  -14.0 ],   # 10  forehead centre
    [ 57.0,  32.0,  -41.0 ],   # 109 right temple
    [-57.0,  32.0,  -41.0 ],   # 338 left temple
    [ 30.0, -30.0,  -25.0 ],   # 61  right lip corner
    [-30.0, -30.0,  -25.0 ],   # 291 left lip corner
    [  0.0, -75.0,  -18.0 ],   # 199 chin tip
    [  0.0,   0.0,    8.0 ],   # 4   nose below bridge
    [  8.0,   0.0,   -7.0 ],   # 197 nose side right
], dtype=np.float64)


def _ensure_model() -> str:
    if not _MODEL_PATH.exists():
        logger.info("Downloading face_landmarker model to %s …", _MODEL_PATH)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        logger.info("Model download complete.")
    return str(_MODEL_PATH)


@dataclass(slots=True)
class PoseResult:
    yaw: float    # degrees; negative = looking left, positive = looking right
    pitch: float  # degrees; negative = looking down, positive = looking up
    confidence: float  # reprojection-based; 1.0 = solved cleanly


class HeadPoseTracker:
    """Estimates head yaw/pitch using MediaPipe FaceLandmarker + solvePnP.

    Uses SOLVEPNP_SQPNP (globally optimal) over 15 landmarks for
    accurate, stable pose estimation across a wide range of head angles.
    """

    def __init__(self) -> None:
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_ensure_model()),
            running_mode=RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.45,
            min_tracking_confidence=0.45,
        )
        self._detector = FaceLandmarker.create_from_options(options)
        self._start_ns = time.monotonic_ns()
        self._last_ts_ms: int = -1

    def process(self, frame_bgr: np.ndarray) -> PoseResult | None:
        """Return :class:`PoseResult` for the dominant face, or ``None`` if not found."""
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        ts = (time.monotonic_ns() - self._start_ns) // 1_000_000
        ts = max(ts, self._last_ts_ms + 1)
        self._last_ts_ms = ts
        result = self._detector.detect_for_video(mp_image, ts)

        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]
        img_pts = np.array(
            [[landmarks[i].x * w, landmarks[i].y * h] for i in _LANDMARK_IDS],
            dtype=np.float64,
        )

        focal = float(w)
        K = np.array([[focal, 0, w / 2],
                      [0, focal, h / 2],
                      [0, 0, 1]], dtype=np.float64)

        ok, rvec, _ = cv2.solvePnP(
            _MODEL_POINTS, img_pts, K, np.zeros((4, 1), dtype=np.float64),
            flags=cv2.SOLVEPNP_SQPNP,
        )
        if not ok:
            return None

        rmat, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
        yaw   = float(np.degrees(np.arctan2(rmat[1, 0], rmat[0, 0]))) if sy >= 1e-6 else 0.0
        pitch = float(np.degrees(np.arctan2(-rmat[2, 0], sy)))

        return PoseResult(yaw=yaw, pitch=pitch, confidence=1.0)

    def close(self) -> None:
        self._detector.close()


logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
_MODEL_PATH = Path(__file__).resolve().parent / "face_landmarker.task"


def _ensure_model() -> str:
    if not _MODEL_PATH.exists():
        logger.info("Downloading face_landmarker model to %s …", _MODEL_PATH)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        logger.info("Model download complete.")
    return str(_MODEL_PATH)


@dataclass(slots=True)
class PoseResult:
    yaw: float    # degrees; negative = left, positive = right (camera view)
    pitch: float  # degrees; negative = down, positive = up
    confidence: float  # 0–1: how directly the face is aimed at the camera


class HeadPoseTracker:
    """Estimates head yaw/pitch using MediaPipe FaceLandmarker.

    Uses the built-in facial_transformation_matrix (fit over all 478
    landmarks internally) instead of a custom solvePnP on 6 points —
    significantly more stable.

    Coordinate convention
    ---------------------
    MediaPipe canonical face: +Z points toward the viewer (nose forward).
    OpenCV camera space: +X right, +Y down, +Z into scene.

    At rest the face's +Z maps to camera -Z, so::

        face_z = R[:, 2]           # face-forward vector in camera space
        yaw   = atan2(face_z[0], -face_z[2])   # + = looking right
        pitch = atan2(-face_z[1], -face_z[2])  # + = looking up
        confidence = clamp(-face_z[2], 0, 1)    # 1 = facing straight
    """

    def __init__(self) -> None:
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_ensure_model()),
            running_mode=RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            output_facial_transformation_matrixes=True,
        )
        self._detector = FaceLandmarker.create_from_options(options)
        self._start_ns = time.monotonic_ns()
        self._last_ts_ms: int = -1

    def process(self, frame_bgr: np.ndarray) -> PoseResult | None:
        """Return :class:`PoseResult` for the dominant face, or ``None`` if not found."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        ts = (time.monotonic_ns() - self._start_ns) // 1_000_000
        ts = max(ts, self._last_ts_ms + 1)
        self._last_ts_ms = ts
        result = self._detector.detect_for_video(mp_image, ts)

        if not result.face_landmarks:
            return None

        # --- Primary: facial transformation matrix (most accurate) ---
        if result.facial_transformation_matrixes:
            mat = np.array(result.facial_transformation_matrixes[0]).reshape(4, 4)
            R = mat[:3, :3]
            face_z = R[:, 2]  # face-forward direction in camera space

            yaw = float(np.degrees(np.arctan2(face_z[0], -face_z[2])))
            pitch = float(np.degrees(np.arctan2(-face_z[1], -face_z[2])))
            # Confidence: 1.0 when face points directly at camera, 0 when edge-on.
            confidence = float(np.clip(-face_z[2], 0.0, 1.0))
            return PoseResult(yaw=yaw, pitch=pitch, confidence=confidence)

        # --- Fallback: solvePnP (if matrix unavailable) ---
        h, w = frame_bgr.shape[:2]
        landmarks = result.face_landmarks[0]
        _IDS = [1, 152, 263, 33, 287, 57]
        _PTS3D = np.array([[0.0,0,0],[0,-63.6,-12.5],[-43.3,32.7,-26],
                            [43.3,32.7,-26],[-28.9,-28.9,-24.1],[28.9,-28.9,-24.1]],
                           dtype=np.float64)
        pts2d = np.array([[landmarks[i].x * w, landmarks[i].y * h] for i in _IDS],
                         dtype=np.float64)
        focal = float(w)
        K = np.array([[focal,0,w/2],[0,focal,h/2],[0,0,1]], dtype=np.float64)
        ok, rvec, _ = cv2.solvePnP(_PTS3D, pts2d, K, np.zeros((4,1)),
                                    flags=cv2.SOLVEPNP_SQPNP)
        if not ok:
            return None
        rmat, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)
        yaw = float(np.degrees(np.arctan2(rmat[1,0], rmat[0,0])))
        pitch = float(np.degrees(np.arctan2(-rmat[2,0], sy)))
        return PoseResult(yaw=yaw, pitch=pitch, confidence=1.0)

    def close(self) -> None:
        self._detector.close()


logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
_MODEL_PATH = Path(__file__).resolve().parent / "face_landmarker.task"

# Landmark indices (same 478-point mesh as FaceMesh).
_LANDMARK_IDS = [
    1,    # nose tip
    152,  # chin
    263,  # left eye outer corner
    33,   # right eye outer corner
    287,  # left mouth corner
    57,   # right mouth corner
]

_MODEL_POINTS = np.array(
    [
        [0.0, 0.0, 0.0],
        [0.0, -63.6, -12.5],
        [-43.3, 32.7, -26.0],
        [43.3, 32.7, -26.0],
        [-28.9, -28.9, -24.1],
        [28.9, -28.9, -24.1],
    ],
    dtype=np.float64,
)


def _ensure_model() -> str:
    if not _MODEL_PATH.exists():
        logger.info("Downloading face_landmarker model to %s …", _MODEL_PATH)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        logger.info("Model download complete.")
    return str(_MODEL_PATH)


@dataclass(slots=True)
class PoseResult:
    yaw: float
    pitch: float
    confidence: float


class HeadPoseTracker:
    """Estimates head yaw/pitch using MediaPipe FaceLandmarker + solvePnP."""

    def __init__(self) -> None:
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_ensure_model()),
            running_mode=RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._detector = FaceLandmarker.create_from_options(options)
        self._start_ns = time.monotonic_ns()
        self._last_ts_ms: int = -1

    def process(self, frame_bgr: np.ndarray) -> PoseResult | None:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        ts = (time.monotonic_ns() - self._start_ns) // 1_000_000
        # MediaPipe requires strictly increasing timestamps.
        ts = max(ts, self._last_ts_ms + 1)
        self._last_ts_ms = ts
        result = self._detector.detect_for_video(mp_image, ts)

        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]

        image_points = np.array(
            [[landmarks[i].x * w, landmarks[i].y * h] for i in _LANDMARK_IDS],
            dtype=np.float64,
        )

        focal_length = w
        camera_matrix = np.array(
            [[focal_length, 0, w / 2],
             [0, focal_length, h / 2],
             [0, 0, 1]],
            dtype=np.float64,
        )
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        ok, rvec, _ = cv2.solvePnP(
            _MODEL_POINTS, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            return None

        rmat, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
        if sy >= 1e-6:
            pitch = np.degrees(np.arctan2(-rmat[2, 0], sy))
            yaw = np.degrees(np.arctan2(rmat[1, 0], rmat[0, 0]))
        else:
            pitch = np.degrees(np.arctan2(-rmat[2, 0], sy))
            yaw = 0.0

        return PoseResult(yaw=float(yaw), pitch=float(pitch), confidence=1.0)

    def close(self) -> None:
        self._detector.close()

