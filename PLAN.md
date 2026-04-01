# Cloud Cam — Project Plan

Auto-switching virtual webcam that tracks head pose and routes the active physical camera (left or right monitor cam) to a virtual camera device consumed by any app (Zoom, Teams, Meet, OBS, etc.).

---

## Architecture Overview

```
Camera A (left)  ──frame──►  Head Pose Tracker  ◄──frame──  Camera B (right)
                              (MediaPipe / dlib)
                                     │
                               yaw / pitch
                                     ▼
                          Gaze Direction Engine          ◄── Tray Config UI
                       (yaw angle + hysteresis threshold)
                                     │
                               cam A / cam B
                                     ▼
                           Camera Switcher
                        (selects active physical camera)
                                     │
                             video frames
                                     ▼
                        Virtual Camera Driver
                       (DirectShow / MediaFoundation)
                                     │
               ┌──────────┬──────────┼──────────┬──────────┐
            Google Meet  Zoom      Teams       OBS      Any app
```

---

## Milestones & Tasks

### M1 — Project Setup
- [ ] Create repo structure (see layout below)
- [ ] Set up Python virtual environment (`requirements.txt`)
- [ ] Pin dependencies: `opencv-python`, `mediapipe`, `numpy`, `pystray`, `Pillow`
- [ ] Add `.gitignore`, `README.md`

### M2 — Camera Capture
- [ ] Enumerate available webcams at startup
- [ ] Open two `cv2.VideoCapture` streams (Camera A and Camera B)
- [ ] Expose a `CameraManager` class with `get_frame(cam_id)` method
- [ ] Handle camera open failures gracefully (fallback / error log)

### M3 — Head Pose Tracker
- [ ] Integrate MediaPipe FaceMesh to extract 3D landmarks
- [ ] Compute yaw (left/right) and pitch (up/down) angles from landmarks
- [ ] Return a `PoseResult(yaw, pitch, confidence)` dataclass each frame
- [ ] Benchmark latency; target < 30 ms per frame on CPU
- [ ] Optional: fall back to dlib 68-point model if MediaPipe unavailable

### M4 — Gaze Direction Engine
- [ ] Define `GazeEngine` class with configurable `yaw_threshold` and `hysteresis`
- [ ] Implement hysteresis: only switch camera when angle crosses threshold ± dead-band
- [ ] Track last active camera to avoid rapid toggling
- [ ] Expose `active_camera: Literal["A", "B"]` property
- [ ] Unit-test logic with synthetic yaw sequences

### M5 — Camera Switcher
- [ ] `CameraSwitcher` reads `GazeEngine.active_camera` each frame
- [ ] Grabs the corresponding frame from `CameraManager`
- [ ] Pushes frame into a thread-safe queue consumed by the virtual driver
- [ ] Smooth transition option: blend N frames on switch (optional)

### M6 — Virtual Camera Driver (Windows)
- [ ] Research options:
  - **OBS Virtual Camera** (bundled plugin) — easiest path for end users
  - **pyvirtualcam** library — wraps OBS / UnityCapture virtual cam
  - **Custom DirectShow / MediaFoundation filter** — most compatible, hardest
- [ ] Implement using `pyvirtualcam` first (fastest prototype)
- [ ] Write frames from `CameraSwitcher` queue to virtual cam at target FPS (30)
- [ ] Document manual install step for virtual cam backend if required

### M7 — Tray Config UI
- [ ] Use `pystray` + `Pillow` for system tray icon
- [ ] Menu items:
  - Select Camera A device (dropdown / index)
  - Select Camera B device (dropdown / index)
  - Yaw threshold slider / input
  - Hysteresis value input
  - Show live preview window toggle
  - Quit
- [ ] Persist settings to `config.json` (AppData or repo root)
- [ ] Reload settings without restart where possible

### M8 — Main Entry Point & Thread Architecture
- [ ] Main process spawns threads:
  - Capture thread (reads frames from both cameras)
  - Tracker thread (runs head pose inference)
  - Switcher / output thread (writes to virtual cam)
  - Tray UI thread (event loop)
- [ ] Shared `threading.Event` for clean shutdown
- [ ] Logging via `logging` module (rotating file + stderr)

### M9 — Packaging & Distribution
- [ ] `pyproject.toml` / `setup.cfg` with entry point `cloud-cam`
- [ ] PyInstaller one-file EXE for Windows (no Python required)
- [ ] Bundle MediaPipe model files inside EXE
- [ ] Installer script or NSIS / Inno Setup (optional)
- [ ] Document prerequisites: Visual C++ redistributable, virtual cam backend

### M10 — Testing & QA
- [ ] Unit tests for `GazeEngine` hysteresis logic
- [ ] Unit tests for `CameraManager` mock capture
- [ ] Integration test: feed recorded video → assert correct camera selection
- [ ] Manual test matrix: Zoom, Teams, Google Meet, OBS

---

## Proposed Repository Layout

```
cloud-cam/
├── src/
│   └── cloudcam/
│       ├── __init__.py
│       ├── main.py              # entry point, thread orchestration
│       ├── camera_manager.py    # Camera A/B capture
│       ├── head_pose.py         # MediaPipe / dlib tracker
│       ├── gaze_engine.py       # yaw threshold + hysteresis
│       ├── camera_switcher.py   # selects active frame
│       ├── virtual_cam.py       # pyvirtualcam output
│       ├── tray_ui.py           # pystray tray + config menu
│       └── config.py            # load/save config.json
├── tests/
│   ├── test_gaze_engine.py
│   ├── test_camera_manager.py
│   └── fixtures/                # sample video clips for integration tests
├── assets/
│   └── icon.png                 # tray icon
├── config.json                  # default user config (gitignored for user overrides)
├── requirements.txt
├── pyproject.toml
├── PLAN.md                      # this file
└── README.md
```

---

## Key Technical Decisions

| Decision | Options | Chosen / Preferred |
|---|---|---|
| Face tracking | MediaPipe FaceMesh, dlib, OpenCV Haar | MediaPipe (fast, no models to ship) |
| Virtual cam output | pyvirtualcam, custom DirectShow filter | pyvirtualcam (prototype), custom filter (v2) |
| Config UI | pystray tray menu, Qt GUI, web UI | pystray (lightweight, no heavy GUI dep) |
| Packaging | PyInstaller, cx_Freeze, MSI | PyInstaller one-file EXE |
| Language | Python, C++ | Python (core), C++ only if DirectShow filter needed |

---

## Dependencies

```
opencv-python>=4.9
mediapipe>=0.10
numpy>=1.26
pyvirtualcam>=0.11
pystray>=0.19
Pillow>=10.0
```

---

## Progress Tracker

| Milestone | Status |
|---|---|
| M1 — Project Setup | ✅ Done |
| M2 — Camera Capture | ✅ Done |
| M3 — Head Pose Tracker | ✅ Done |
| M4 — Gaze Direction Engine | ✅ Done |
| M5 — Camera Switcher | ✅ Done |
| M6 — Virtual Camera Driver | ✅ Done |
| M7 — Tray Config UI | ✅ Done |
| M8 — Main Entry Point | ✅ Done |
| M9 — Packaging | 🔲 TODO |
| M10 — Testing & QA | 🔲 Unit tests written; manual testing pending |

---

## Open Questions

- [ ] Should Camera A and B always both be open, or lazy-open only the active one?
- [ ] Target minimum Windows version? (affects DirectShow vs MF choice)
- [ ] Should the virtual cam also mirror audio (e.g. switch microphone input)?
- [ ] Multi-monitor support: auto-assign camera by monitor position?
- [ ] macOS / Linux support needed? (pyvirtualcam supports macOS via OBS)
