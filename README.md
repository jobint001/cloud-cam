# Cloud Cam

> A fun Python app built for a very specific edge case: you have **two monitors, one webcam per monitor**, and you're tired of manually switching cameras every time you look left or right.

Cloud Cam watches your head. The moment you turn toward the other screen it silently swaps the camera feed — so Zoom, Teams, Google Meet, or OBS always sees the camera you're actually facing, with zero clicks.

---

## The edge case

You're on a dual-monitor setup. Each monitor has its own webcam clipped to the top. During a call you glance at the other screen and your face is now a blurry side-profile on a camera two metres away. Cloud Cam solves exactly this problem and nothing else.

---

## How it works

```
Left cam  ──►  Head pose tracker (MediaPipe + solvePnP)
Right cam ──►       │
                    ▼ yaw angle
             Gaze direction engine  (threshold + hysteresis)
                    │ cam A / cam B
                    ▼
             Camera switcher
                    │ video frames
                    ▼
             Virtual camera driver  (OBS Virtual Camera)
                    │
         Zoom / Teams / Meet / OBS / any app
```

1. Both physical cameras are captured simultaneously on background threads.
2. MediaPipe FaceLandmarker estimates your **yaw angle** (left/right head rotation) every frame.
3. A **gaze engine** with configurable threshold + hysteresis decides which camera you're facing.
4. The selected frame is pushed to the **OBS Virtual Camera** driver — your calling app sees one seamless feed.
5. A **system tray icon** lets you tweak every setting live without restarting.

---

## Requirements

| | Windows | macOS |
|---|---|---|
| OS | Windows 10 / 11 (64-bit) | macOS 12 Monterey+ |
| Python | 3.10+ | 3.10+ |
| Virtual cam driver | [OBS Studio](https://obsproject.com/) | [OBS Studio](https://obsproject.com/) (v28+ has Virtual Camera built in) |

> **Linux** is not officially supported yet — `pyvirtualcam` can write to a V4L2 loopback device but that path is untested.

---

## Installation

### Windows

```powershell
git clone https://github.com/your-username/cloud-cam.git
cd cloud-cam
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

### macOS

```bash
git clone https://github.com/your-username/cloud-cam.git
cd cloud-cam
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> **Camera permissions:** macOS will prompt for camera access the first time. If denied, go to  
> System Settings → Privacy & Security → Camera and enable it for Terminal (or your Python executable).

> **OBS Virtual Camera on macOS:** Open OBS once, click **Start Virtual Camera**, then close OBS. The driver stays registered. In your calling app select **OBS Virtual Camera**.

Dependencies (`opencv-python`, `mediapipe`, `pyvirtualcam`, `pystray`, `Pillow`) are installed automatically.

> The MediaPipe face landmark model (~5 MB) is downloaded automatically on first run.

---

## Usage

**Windows (PowerShell):**
```powershell
python src/cloudcam/main.py
```

**macOS / Linux (Terminal):**
```bash
python3 src/cloudcam/main.py
```

Or, if installed via `pip install -e .`:

```bash
cloud-cam
```

A small camera icon appears in your **system tray**. Cloud Cam is now running — open Zoom/Teams/Meet and select **OBS Virtual Camera** as your webcam.

**To stop:** press `Ctrl+C` in the terminal, or right-click the tray icon → **Quit**.

---

## Configuration

Settings are saved to `config.json` in the project root and can be changed live from the **tray menu** (no restart needed).

| Key | Default | Description |
|---|---|---|
| `camera_a` | `0` | Device index for left monitor cam |
| `camera_b` | `1` | Device index for right monitor cam |
| `yaw_threshold` | `15.0` | Head yaw angle (°) that triggers a camera switch |
| `hysteresis` | `3.0` | Dead-band (°) around threshold — prevents rapid toggling |
| `fps` | `30` | Output frame rate |
| `width` | `1280` | Output frame width |
| `height` | `720` | Output frame height |

**Find your camera indices** (run once):

```bash
python3 -c "from cloudcam.camera_manager import CameraManager; print(CameraManager.enumerate_cameras())"
```

**Tuning tips:**

- Lower `yaw_threshold` (e.g. `12`) → switches earlier, on a slight glance
- Higher `yaw_threshold` (e.g. `20`) → switches only on a deliberate head turn
- Lower `hysteresis` → snappier switching; higher → more stable near the boundary

---

## Project layout

```
src/cloudcam/
├── main.py            # entry point, thread orchestration
├── camera_manager.py  # Camera A/B capture (per-cam background threads)
├── head_pose.py       # MediaPipe FaceLandmarker → yaw/pitch via solvePnP
├── gaze_engine.py     # threshold + hysteresis → cam A or B
├── camera_switcher.py # selects active frame, EMA smoothing, rate limiter
├── virtual_cam.py     # pyvirtualcam → OBS Virtual Camera output
├── tray_ui.py         # pystray system tray + live config menu
└── config.py          # load / save config.json
├── tray_ui.py         # pystray tray + config menu
└── config.py          # load/save config.json
```
