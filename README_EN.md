<div align="center">

# 🏸 AI-YuJian-AI · Feather-Eye

### AI Badminton Hawk-Eye System — See every shot.

[![GitHub stars](https://img.shields.io/github/stars/lzylovec/AI-YuJian-AI?style=for-the-badge&logo=github&color=ffd33d)](https://github.com/lzylovec/AI-YuJian-AI/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/lzylovec/AI-YuJian-AI?style=for-the-badge&logo=github&color=58a6ff)](https://github.com/lzylovec/AI-YuJian-AI/network/members)
[![License](https://img.shields.io/github/license/lzylovec/AI-YuJian-AI?style=for-the-badge&color=blueviolet)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=for-the-badge)]()
[![Open Source](https://img.shields.io/badge/Open%20Source-Apache%202.0-success?style=for-the-badge)]()

**An open-source computer-vision toolkit for badminton match video analysis — your own Hawk-Eye.**

[中文](README.md) · [Quick Start](#-quick-start) · [Features](#-features) · [Preview](#-preview) · [Roadmap](#-roadmap)

</div>

---

## ✨ What is this?

**AI-YuJian-AI** is an open-source match-analysis system built for amateur and competitive badminton.
Feed it a match video, and it will:

- 🎯 **Player pose** — RTMPose / RTMO / YOLO Pose
- 🪶 **Shuttlecock tracking** — YOLO detection + cross-frame tracking
- 🗺️ **Court coordinate mapping** — manual 4-point annotation → standard court coordinates
- 📊 **Motion stats** — distance, instant speed, max speed, rally count
- 🔥 **Position heatmaps** — per-half heatmap & scatter plots
- 🎬 **Annotated video** — skeleton / trajectory / stats / rally ID overlay
- 🌐 **Bilingual** — `--language zh/en`

> The name **YuJian (羽见)** literally means *"see the feather"* — a play on words for *"see every shuttle"*.

---

## 🎬 Preview

<div align="center">

![AI-YuJian-AI preview](assets/demo.gif)

*Full demo video: [`assets/demo.mp4`](assets/demo.mp4)*

</div>

### 📍 Position visualization

| 🔥 Heatmap | 🎯 Scatter |
| :---: | :---: |
| ![Player position heatmap](assets/match_heatmap.png) | ![Player position scatter](assets/match_scatter.png) |

---

## 🆕 Changelog

- **2026-07-31** · Renamed to **AI-YuJian-AI**, rewrote README.
- **2026-06-20** · Initial open-source release.
- **2026-06-17** · Documentation cleanup.
- **Current** · Pose detection, shuttlecock detection, court mapping, trajectory stats, heatmaps, scatter plots, annotated video output.
- **Experimental** · Hit-point analysis and stroke statistics are still under iteration — best for research & secondary development.

---

## ✨ Features

### 🧠 AI Vision
- 🦴 **Player pose detection** — RTMPose, RTMO, Ultralytics YOLO Pose
- 🪶 **Shuttlecock detection** — YOLO-based detector with trajectory overlay
- 🗺️ **Court coordinate mapping** — 4-point manual annotation → standard court coordinates
- 🧍 **Player tracking** — separate trajectories for upper-court and lower-court players
- 🏸 **Rally detection** — auto-detect rally start/end from continuous court-view matching

### 📊 Analytics
- 📏 **Motion stats** — distance, instant speed, max speed, rally count
- 🔥 **Position charts** — auto-generated heatmaps & scatter plots
- 📁 **Structured export** — `metadata.json` + `detections.jsonl`

### 🎨 UX
- 🎬 **Annotated video output** — MP4 with skeleton / trajectory / stats / rally ID overlay
- 🌐 **Bilingual UI** — `--language zh/en`
- 🎛️ **Toggleable overlays** — ROI, skeleton, player trajectory, court trajectory, shuttle trajectory, stats
- 🖥️ **Fully local** — no cloud, no upload

---

## 🏗️ Architecture

```text
                       ┌──────────────────────────┐
                       │  Input Video (MP4)       │
                       └────────────┬─────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │ Pose Detection   │  │ Shuttle Detect   │  │ Court Annotation │
    │ RTMPose/RTMO/YOLO│  │ YOLO (ball)      │  │ 4-point click    │
    └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
             │                     │                     │
             └─────────────────────┼─────────────────────┘
                                   ▼
                       ┌──────────────────────────┐
                       │  Court Coordinate Map   │
                       │  image → standard court  │
                       └────────────┬─────────────┘
                                    ▼
                       ┌──────────────────────────┐
                       │   Player Tracking &      │
                       │   Rally Detection        │
                       └────────────┬─────────────┘
                                    ▼
        ┌───────────────────┬───────┴────────┬────────────────────┐
        ▼                   ▼                ▼                    ▼
   ┌─────────┐       ┌──────────────┐  ┌────────────┐    ┌──────────────────┐
   │  Stats  │       │ Annotated    │  │ Heatmap /  │    │ detections.jsonl │
   │ panel   │       │ Video Output │  │ Scatter    │    │ metadata.json    │
   └─────────┘       └──────────────┘  └────────────┘    └──────────────────┘
```

---

## 🚀 Quick Start

### 📋 Requirements

- **Python** 3.8+
- **FFmpeg** in your `PATH`
- **OpenCV / PyTorch / Ultralytics / RTMLib / ONNX Runtime**
- Recommended: **NVIDIA GPU**. CPU works but is much slower.

### 📦 Install

```bash
git clone https://github.com/lzylovec/AI-YuJian-AI.git
cd AI-YuJian-AI

python -m venv .venv
# Windows
.\.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 🎮 GPU acceleration (Windows / NVIDIA, optional)

```powershell
.\.venv\Scripts\activate

pip uninstall -y torch torchvision onnxruntime onnxruntime-gpu
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install onnxruntime-gpu==1.20.1

# Verify
python -c "import torch; print('cuda:', torch.cuda.is_available())"
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# Expected: cuda: True and CUDAExecutionProvider
```

### 🧠 Model preparation

Download the shuttlecock weights from [GitHub Releases](https://github.com/lzylovec/AI-YuJian-AI/releases):

```text
weights/yolo11s-ball.pt
```

Optional RTMPose / RTMO / YOLOX ONNX models:

```text
weights/yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx
weights/rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx
weights/rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx
```

> If the local ONNX files are missing, `rtmlib` will try to download them to your user cache.

### ▶️ Run

```bash
# Basic
python main.py --video-path videos/demo.mp4

# Pose model selection
python main.py --video-path videos/demo.mp4 --pose-family rtmpose --pose-mode balanced
python main.py --video-path videos/demo.mp4 --pose-family rtmo --pose-mode lightweight
python main.py --video-path videos/demo.mp4 --pose-family yolo-pose --yolo-pose-model yolo11n-pose.pt

# Language
python main.py --video-path videos/demo.mp4 --language en
```

#### First-run flow

1. Prepare the input video and the shuttlecock weights.
2. Run the basic command. Without `--template-path`, a file picker appears — pick a clear court frame.
3. The court-annotation window pops up. Click **4 corners in order: top-left → top-right → bottom-right → bottom-left**.

![Court annotation example](assets/label_court_example.png)

4. After the 4 clicks, a green court frame + blue pose-ROI frame appear.
5. Annotations are cached at `results/<video_name>/court_annotations.txt` and reused on subsequent runs.

> Changed camera / crop / template? Delete that file and re-annotate.

---

## ⚙️ Common options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--video-path` | Input video (required) | — |
| `--output-dir` | Output directory | `results/<video_name>` |
| `--ball-model` | Shuttlecock YOLO model | `weights/yolo11s-ball.pt` |
| `--pose-family` | `rtmpose` / `rtmo` / `yolo-pose` | `rtmpose` |
| `--pose-mode` | `lightweight` / `balanced` / `performance` | `balanced` |
| `--yolo-pose-model` | YOLO pose model | `yolo11n-pose.pt` |
| `--template-path` | Court template image | file picker |
| `--pose-roi` | Show pose-ROI frame | `true` |
| `--display` | Show OpenCV preview | `true` |
| `--skeletons` | Show skeletons | `true` |
| `--player-trajectories` | Show player trajectories | `true` |
| `--court-trajectory` | Show court trajectory overlay | `true` |
| `--shuttlecock-trajectory` | Show shuttle trajectory | `true` |
| `--player-stats` | Show player stats panel | `true` |
| `--visualize-positions` | Generate heatmap & scatter | `true` |
| `--audio` | Keep original audio | `true` |
| `--language` | `zh` / `en` | `zh` |
| `--save-images` | Save per-frame images | `false` |
| `--performance-stats` | Print performance timing | `false` |

---

## 📊 Output

Default output to `results/<video_name>/`:

```text
results/<video_name>/
├── metadata.json                  # video / model / annotation / output meta
├── detections.jsonl               # per-frame records (rally, players, hands, coords, speed, shuttle)
├── detect_<video_name>.mp4        # MP4 with skeleton / trajectory / stats / rally ID overlay
├── court_annotations.txt          # 4-point annotation cache
└── position_visualizations/
    ├── heatmaps/                   # player position heatmaps
    └── scatter_plots/              # player position scatter plots
```

---

## 🧩 Project structure

```text
AI-YuJian-AI/
├── main.py                       # CLI entry & arg parser
├── badminton_analysis/
│   ├── system.py                 # main analysis pipeline
│   ├── service.py                # high-level service wrapper
│   ├── court/                    # court annotation & coordinate mapping
│   ├── data/                     # JSON / JSONL persistence
│   ├── detection/                # shuttle & pose detection
│   ├── media/                    # video / audio processing
│   ├── tracking/                 # player tracking
│   ├── visualization/            # overlays, charts, position plots
│   └── analysis/                 # rally & stats
├── assets/                       # demo GIF / video / sample images
├── videos/                       # input videos
├── templates/                    # court template images
├── results/                      # default output
├── specs/                        # design docs
└── weights/                      # model weights (downloaded at runtime)
```

---

## 🔮 Roadmap

- [x] Frame-by-frame badminton match video analysis
- [x] RTMPose / RTMO / YOLO Pose support
- [x] YOLO shuttlecock detection
- [x] Manual court annotation & coordinate mapping
- [x] Player trajectory / speed / distance / rally stats
- [x] Bilingual visualization (zh / en)
- [x] Heatmap, scatter plot, detection data export
- [ ] More stable hit-point recognition
- [ ] More accurate shuttlecock detection
- [ ] More complete stroke statistics
- [ ] Automatic court keypoint detection
- [ ] Batch video analysis workflow

---

## 🛠️ Tech stack

<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/Ultralytics%20YOLO-111F68?style=flat-square" />
  <img src="https://img.shields.io/badge/ONNX%20Runtime-005CED?style=flat-square" />
  <img src="https://img.shields.io/badge/RTMPose-OpenMMLab-3A3A3A?style=flat-square" />
  <img src="https://img.shields.io/badge/FFmpeg-007808?style=flat-square&logo=ffmpeg&logoColor=white" />
</p>

---

## 🙏 Acknowledgements

- [TrackNetV2](https://github.com/wywyWang/TrackNetV2) — shuttlecock dataset
- [RTMPose](https://github.com/open-mmlab/mmpose) — human pose estimation
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) — detection ecosystem

---

## 📄 License

Project code and `weights/yolo11s-ball.pt` are released under **Apache License 2.0**.
The RTMPose / RTMO / YOLOX ONNX weights shipped via Releases come from the OpenMMLab / RTMPose ecosystem
and are distributed under their upstream Apache License 2.0, with original attributions preserved.

See [LICENSE](LICENSE).

---

<div align="center">

If this project helps you, a ⭐ would mean a lot!

**Made with ❤️ by [lzylovec](https://github.com/lzylovec)**

</div>
