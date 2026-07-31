<div align="center">

# 🏸 AI-YuJian-AI · Feather-Eye

### Turn badminton match video into court-aware replay data

[![GitHub](https://img.shields.io/badge/GitHub-lzylovec--AI--YuJian--AI-181717?style=flat-square&logo=github)](https://github.com/lzylovec/lzylovec-AI-YuJian-AI)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Web](https://img.shields.io/badge/Web-React%20%2B%20Vite-61DAFB?style=flat-square&logo=react&logoColor=111827)](web/frontend/)
[![API](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](web/api/)
[![License](https://img.shields.io/badge/License-Apache--2.0-2ea44f?style=flat-square)](LICENSE)

**A local-first computer-vision toolkit for player pose, shuttlecock tracking, court mapping, and match replay analytics.**

[中文](README.md) · [Quick Start](#-quick-start) · [Web Demo](#-web-demo) · [Preview](#-preview) · [Roadmap](#-roadmap)

</div>

---

## ✨ Overview

**AI-YuJian-AI** is designed for badminton training, match review, and computer-vision research. Feed it a match video, calibrate the four court corners once, and it produces annotated video, court trajectories, movement statistics, and structured detection data.

The project provides two entry points: a Python CLI for direct analysis and a local Web Demo for upload, clipping, browser-based calibration, queued analysis, and artifact downloads.

> **YuJian (羽见)** means “seeing every shuttle — and every movement.”

## 🎬 Preview

<div align="center">

![AI-YuJian-AI preview](assets/demo.gif)

*Full demo video: [assets/demo.mp4](assets/demo.mp4)*

</div>

| Player position heatmap | Player position scatter plot |
| :---: | :---: |
| ![Player position heatmap](assets/match_heatmap.png) | ![Player position scatter plot](assets/match_scatter.png) |

![Court calibration example](assets/label_court_example.png)

## 🧭 Two ways to use it

| Entry point | Best for | Start with |
| :--- | :--- | :--- |
| **Python CLI** | Single videos, parameter tuning, and scripts | `python main.py --video-path ...` |
| **Local Web Demo** | Uploading, clipping, calibration, job history, and downloads | FastAPI `8000` + Vite `5173` |

## 🚀 Quick Start

### Requirements

- Python 3.8+
- FFmpeg available in `PATH`
- NVIDIA GPU recommended; CPU is supported but considerably slower
- The default dependency file installs CPU builds of PyTorch and ONNX Runtime

### Install

```bash
git clone https://github.com/lzylovec/lzylovec-AI-YuJian-AI.git
cd lzylovec-AI-YuJian-AI

python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Prepare model weights

Shuttlecock weights are not committed to the repository. Download them from [GitHub Releases](https://github.com/lzylovec/lzylovec-AI-YuJian-AI/releases) and place them at:

```text
weights/yolo11s-ball.pt
```

For `rtmpose` or `rtmo`, `rtmlib` can use the corresponding ONNX models on demand. You can also place them under `weights/`:

```text
weights/yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx
weights/rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx
weights/rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx
```

> With `--pose-family yolo-pose`, the default model name is `yolo11n-pose.pt`. Ultralytics can resolve or download it by name, or you can pass a local path with `--yolo-pose-model`.

### Run the CLI

```bash
# Analyze the included sample video with default settings
python main.py --video-path videos/demo.mp4

# Select a pose model
python main.py --video-path videos/demo.mp4 --pose-family rtmpose --pose-mode balanced
python main.py --video-path videos/demo.mp4 --pose-family rtmo --pose-mode lightweight
python main.py --video-path videos/demo.mp4 --pose-family yolo-pose --yolo-pose-model yolo11n-pose.pt

# English visualization text
python main.py --video-path videos/demo.mp4 --language en
```

On the first run:

1. Without `--template-path`, a file picker opens. Choose a frame where the court is clearly visible.
2. In the calibration window, click **top-left → top-right → bottom-right → bottom-left**.
3. The annotation is cached at `results/<video_name>/court_annotations.txt` and reused later.

If the camera view, crop, or template changes, delete the corresponding cache file and calibrate again.

## 🖥️ Web Demo

The Web Demo is a local workbench. Uploaded videos are stored under local `storage/`, and analysis results are written to local `results/`; no cloud service is required.

### Start the backend

```bash
pip install -r requirements.txt -r web-requirements.txt
python -m web.api.run
```

Backend: <http://127.0.0.1:8000>

### Start the frontend

In another terminal, using the same virtual environment:

```bash
cd web/frontend
npm install
npm run dev
```

Frontend: <http://127.0.0.1:5173>

The Web Demo supports:

- Video upload and preview
- Start/end clipping before analysis
- Four-point court calibration in the browser
- Queued, running, completed, and failed job states
- Annotated video, heatmap, and scatter plot preview
- Artifact downloads, local history, and task deletion

## 🧠 Features

### Vision pipeline

- **Player pose detection** with RTMPose, RTMO, and Ultralytics YOLO Pose.
- **Shuttlecock detection** with YOLO and cross-frame trajectory overlays.
- **Court coordinate mapping** through four-point perspective transformation to standard court coordinates.
- **Player tracking** with separate upper- and lower-court trajectories.
- **Rally detection** based on continuous court-view segments, with rally IDs in overlays and records.

### Results and analytics

- **Motion statistics**: distance, instant speed, average speed, maximum speed, and rally count.
- **Position plots**: player heatmaps and scatter plots.
- **Configurable overlays**: pose ROI, skeletons, player trajectories, court trajectory, shuttle trajectory, and stats panel.
- **Structured export**: `metadata.json`, `session_summary.json`, and per-frame `detections.jsonl`.
- **Bilingual visualization** through `--language zh/en`.

## 🏗️ Processing pipeline

```text
Match video
    │
    ├── Player pose detection (RTMPose / RTMO / YOLO Pose)
    ├── Shuttlecock detection (YOLO)
    └── Four-point court calibration
           │
           ▼
    Perspective transform: image → standard court coordinates
           │
           ▼
    Player tracking, rally detection, speed and distance statistics
           │
           ├── Annotated MP4
           ├── Heatmap / scatter plot
           └── JSON / JSONL structured data
```

## ⚙️ Common options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--video-path` | Input video (required) | — |
| `--output-dir` | Output directory | `results/<video_name>` |
| `--ball-model` | Shuttlecock model path | `weights/yolo11s-ball.pt` |
| `--pose-family` | `rtmpose` / `rtmo` / `yolo-pose` | `rtmpose` |
| `--pose-mode` | `lightweight` / `balanced` / `performance` | `balanced` |
| `--yolo-pose-model` | YOLO Pose path or model name | `yolo11n-pose.pt` |
| `--template-path` | Court template image | file picker |
| `--display` | Show OpenCV preview | `true` |
| `--skeletons` | Draw player skeletons | `true` |
| `--player-trajectories` | Draw player trajectories | `true` |
| `--court-trajectory` | Draw court trajectory | `true` |
| `--shuttlecock-trajectory` | Draw shuttle trajectory | `true` |
| `--player-stats` | Show player stats panel | `true` |
| `--visualize-positions` | Generate heatmap and scatter plot | `true` |
| `--audio` | Keep original audio | `true` |
| `--language` | Visualization language: `zh` / `en` | `zh` |
| `--save-images` | Save per-frame images | `false` |
| `--performance-stats` | Print performance timing | `false` |

## 📦 Output

The CLI writes to `results/<video_name>/` by default:

```text
results/<video_name>/
├── metadata.json                  # video, model, calibration, and output metadata
├── detections.jsonl               # per-frame detection records
├── detect_<video_name>.mp4        # annotated video with overlays and stats
├── court_annotations.txt          # CLI four-point calibration cache
└── position_visualizations/
    ├── heatmaps/                  # player position heatmaps
    └── scatter_plots/              # player position scatter plots
```

Service mode additionally writes `session_summary.json` in the corresponding job directory with job status, summary statistics, and artifact indexes.

Web Demo runtime files live under `storage/` and `results/web/`. These directories are ignored by Git.

## 🧩 Project structure

```text
AI-YuJian-AI/
├── main.py                       # CLI entry point
├── badminton_analysis/           # core video-analysis pipeline
│   ├── court/                    # court calibration and mapping
│   ├── data/                     # JSON / JSONL persistence
│   ├── detection/                # pose and shuttlecock detection
│   ├── media/                    # video and audio processing
│   ├── tracking/                 # player tracking
│   └── visualization/            # overlays and charts
├── web/
│   ├── api/                     # FastAPI job service
│   └── frontend/                # React + Vite frontend
├── assets/                      # demo GIF, video, and sample images
├── templates/                   # court template images
├── videos/                      # sample input videos
├── specs/                       # design and requirements docs
├── requirements.txt             # analysis dependencies
└── web-requirements.txt         # Web backend dependencies
```

## 🔮 Roadmap

- [x] Frame-by-frame badminton match video analysis
- [x] RTMPose / RTMO / YOLO Pose support
- [x] YOLO shuttlecock detection
- [x] Manual court calibration and coordinate mapping
- [x] Player trajectory, speed, distance, and rally statistics
- [x] Heatmaps, scatter plots, and structured data export
- [x] Local Web Demo for upload, calibration, queued analysis, and downloads
- [ ] More stable hit-point recognition
- [ ] More accurate shuttlecock detection
- [ ] More complete stroke statistics
- [ ] Automatic court keypoint detection
- [ ] Batch video analysis workflow

## 🛠️ Tech stack

<p>
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch" />
  <img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white" alt="OpenCV" />
  <img src="https://img.shields.io/badge/Ultralytics%20YOLO-111F68?style=flat-square" alt="Ultralytics YOLO" />
  <img src="https://img.shields.io/badge/ONNX%20Runtime-005CED?style=flat-square" alt="ONNX Runtime" />
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/FFmpeg-007808?style=flat-square&logo=ffmpeg&logoColor=white" alt="FFmpeg" />
</p>

## 🙏 Acknowledgements

- [TrackNetV2](https://github.com/wywyWang/TrackNetV2): badminton dataset-related work
- [RTMPose](https://github.com/open-mmlab/mmpose): human pose estimation
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics): detection ecosystem

## 📄 License

Project code is released under the [Apache License 2.0](LICENSE). Model weights are not committed to this repository; follow the license and attribution requirements of each upstream project when downloading or redistributing them.

---

<div align="center">

If this project helps you, a ⭐ would be appreciated.

**Made with ❤️ by [lzylovec](https://github.com/lzylovec)**

</div>
