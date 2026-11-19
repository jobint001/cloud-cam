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

| | Windows | macOS | Linux |
|---|---|---|---|
| OS | Windows 10 / 11 (64-bit) | macOS 12 Monterey+ | Any modern distro (X11/Wayland) |
| Python | 3.10+ | 3.10+ | 3.10+ |
| Virtual cam driver | [OBS Studio](https://obsproject.com/) | [OBS Studio](https://obsproject.com/) (v28+ has Virtual Camera built in) | `v4l2loopback` kernel module |
| Tray backend | built-in | built-in | Xlib, GTK or AppIndicator (optional) |

> **Linux** support uses the `v4l2loopback` kernel module for the virtual camera.
> The tray icon is optional — Cloud Cam runs headless (terminal only) if no tray
> backend is available.

---

## Installation

### Windows

```powershell
git clone https://github.com/jobint001/cloud-cam.git
cd cloud-cam
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

### macOS

```bash
git clone https://github.com/jobint001/cloud-cam.git
cd cloud-cam
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> **Camera permissions:** macOS will prompt for camera access the first time. If denied, go to  
> System Settings → Privacy & Security → Camera and enable it for Terminal (or your Python executable).

> **OBS Virtual Camera on macOS:** Open OBS once, click **Start Virtual Camera**, then close OBS. The driver stays registered. In your calling app select **OBS Virtual Camera**.

### Linux

Install the loopback driver and utilities:

```bash
# Debian / Ubuntu
sudo apt install v4l2loopback-dkms v4l2loopback-utils

# Fedora
sudo dnf install akmod-v4l2loopback v4l2loopback-utils
```

Load the module with **`exclusive_caps=1`** and a fixed device number:

```bash
sudo modprobe v4l2loopback exclusive_caps=1 video_nr=4 card_label="Cloud Cam"
```

> **Why `exclusive_caps=1`?** Most calling apps are Chromium-based (Chrome,
> Brave, Slack, Teams, …). Chromium ignores V4L2 devices that also advertise an
> *output* capability. With `exclusive_caps=1` the loopback reports
> **output-only while idle** and flips to **capture-only** as soon as Cloud Cam
> writes to it — which is what makes the app list it as a camera.

Then clone and install:

```bash
git clone https://github.com/jobint001/cloud-cam.git
cd cloud-cam
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Make the device persistent across reboots:**

```bash
echo 'options v4l2loopback exclusive_caps=1 video_nr=4 card_label="Cloud Cam"' \
  | sudo tee /etc/modprobe.d/v4l2loopback.conf
echo 'v4l2loopback' | sudo tee /etc/modules-load.d/v4l2loopback.conf
sudo update-initramfs -u
```

**Verify the loopback** (`/dev/video4` in this example):

```bash
v4l2-ctl -d /dev/video4 --info | grep -E 'Video Capture|Video Output'
# idle, Cloud Cam stopped       -> Video Output
# while Cloud Cam is running    -> Video Capture
```

> **Point `config.json` at the device:** find it with `v4l2-ctl --list-devices`
> (look for the *Cloud Cam* label) and set `vcam_device`, e.g.
> `"vcam_device": "/dev/video4"`. Camera indices map to device numbers
> (`/dev/video5` → index `5`), so set `camera_a`/`camera_b` accordingly.

> **Startup order matters:** start **Cloud Cam first**, then open the calling
> app. The virtual device only becomes visible once Cloud Cam is producing frames
> (it flips from output-only to capture-only). Stop Cloud Cam with **Ctrl+C** —
> force-killing it can leave the loopback stuck; reset with
> `sudo modprobe -r v4l2loopback && sudo modprobe v4l2loopback exclusive_caps=1
> video_nr=4 card_label="Cloud Cam"`.

> **Using your phone as a camera:** apps such as **DroidCam** or **Iriun**
> expose the phone as a `/dev/videoN` capture device (over Wi-Fi, USB tethering,
> or USB debugging). Point `camera_a`/`camera_b` at that index.

> **Tray backend:** `python-xlib` (installed automatically) gives an X11 tray
> icon but, in the supported pystray version, **no menu** — so the config items
> and **Quit** are unreachable from the icon. For a full tray menu install
> `PyGObject` / an AppIndicator library (e.g. `gir1.2-appindicator3-0.1` on
> Debian/Ubuntu). Without any backend, Cloud Cam logs a warning and runs
> headless.

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

A small camera icon appears in your **system tray**. Cloud Cam is now running — open Zoom/Teams/Meet and select your webcam:

- **Windows / macOS:** select **OBS Virtual Camera**.
- **Linux:** select **Cloud Cam** (the `v4l2loopback` device label), or whatever
  label you gave the loopback device.

**To stop:** press `Ctrl+C` in the terminal (or `kill`/`systemctl stop` to send
SIGTERM), or right-click the tray icon → **Quit**.

---

## Configuration

Settings are saved to `config.json` and can be changed live from the **tray menu** (no restart needed). On Linux the file lives in `$XDG_CONFIG_HOME/cloud-cam/config.json` (default `~/.config/cloud-cam/config.json`); on Windows and macOS it is in the project root.

| Key | Default | Description |
|---|---|---|
| `camera_a` | `0` | Device index for left monitor cam |
| `camera_b` | `1` | Device index for right monitor cam |
| `yaw_threshold` | `15.0` | Head yaw angle (°) that triggers a camera switch |
| `hysteresis` | `3.0` | Dead-band (°) around threshold — prevents rapid toggling |
| `fps` | `30` | Output frame rate |
| `width` | `1280` | Output frame width |
| `height` | `720` | Output frame height |
| `vcam_device` | `""` | Linux only: v4l2loopback device (e.g. `/dev/video2`); empty = auto |

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
