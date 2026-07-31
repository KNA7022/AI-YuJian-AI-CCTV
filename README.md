<div align="center">

# 🏸 AI-YuJian-AI · 羽见 AI

### 把比赛录像变成可复盘的球场数据

[![GitHub](https://img.shields.io/badge/GitHub-lzylovec--AI--YuJian--AI-181717?style=flat-square&logo=github)](https://github.com/lzylovec/lzylovec-AI-YuJian-AI)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/Web-React%20%2B%20Vite-61DAFB?style=flat-square&logo=react&logoColor=111827)](web/frontend/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](web/api/)
[![License](https://img.shields.io/badge/License-Apache--2.0-2ea44f?style=flat-square)](LICENSE)

**一个本地优先的羽毛球比赛视频分析工具：检测球员姿态、追踪羽毛球、映射球场坐标，并生成可视化复盘结果。**

[English](README_EN.md) · [快速开始](#-快速开始) · [Web Demo](#-web-demo) · [效果展示](#-效果展示) · [路线图](#-路线图)

</div>

---

## ✨ 项目简介

**AI-YuJian-AI**（羽见 AI）面向羽毛球训练、比赛复盘和计算机视觉研究场景。输入一段比赛视频，完成一次球场四点标定后，系统会将画面中的检测结果转换为视频叠加层、球场轨迹、运动统计和结构化数据。

它既可以直接通过 Python CLI 运行，也提供一个本地 Web Demo，让上传、截取、标定、排队分析和结果下载都在浏览器中完成。

> **羽见**：看见每一羽，也看见每一次移动。

## 🎬 效果展示

<div align="center">

![AI-YuJian-AI 分析效果预览](assets/demo.gif)

*完整演示视频：[assets/demo.mp4](assets/demo.mp4)*

</div>

| 球员位置热力图 | 球员位置散点图 |
| :---: | :---: |
| ![球员位置热力图](assets/match_heatmap.png) | ![球员位置散点图](assets/match_scatter.png) |

![球场标定示例](assets/label_court_example.png)

## 🧭 两种使用方式

| 入口 | 适合场景 | 启动方式 |
| :--- | :--- | :--- |
| **Python CLI** | 快速跑单个视频、调试参数、批处理脚本 | `python main.py --video-path ...` |
| **本地 Web Demo** | 上传视频、裁剪片段、可视化标定、查看历史任务 | FastAPI `8000` + Vite `5173` |

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- FFmpeg，并加入系统 `PATH`
- 推荐 NVIDIA GPU；CPU 可以运行，但视频分析会明显变慢
- 默认依赖安装 CPU 版 PyTorch 和 ONNX Runtime

### 2. 安装分析依赖

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

### 3. 准备模型

羽毛球检测权重不会随仓库提交，请从 [GitHub Releases](https://github.com/lzylovec/lzylovec-AI-YuJian-AI/releases) 下载并放置到：

```text
weights/yolo11s-ball.pt
```

使用 `rtmpose` 或 `rtmo` 时，`rtmlib` 会按需使用对应的 ONNX 模型。也可以将模型放在 `weights/` 中：

```text
weights/yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx
weights/rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx
weights/rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx
```

> 使用 `--pose-family yolo-pose` 时，默认模型名是 `yolo11n-pose.pt`。Ultralytics 会按模型名查找或下载它，也可以通过 `--yolo-pose-model` 指定本地路径。

### 4. 运行 CLI

```bash
# 使用默认配置分析示例视频
python main.py --video-path videos/demo.mp4

# 选择姿态模型
python main.py --video-path videos/demo.mp4 --pose-family rtmpose --pose-mode balanced
python main.py --video-path videos/demo.mp4 --pose-family rtmo --pose-mode lightweight
python main.py --video-path videos/demo.mp4 --pose-family yolo-pose --yolo-pose-model yolo11n-pose.pt

# 生成英文可视化文字
python main.py --video-path videos/demo.mp4 --language en
```

首次运行时：

1. 如果没有传入 `--template-path`，程序会弹出文件选择框，请选择一张球场清晰可见的模板帧。
2. 在标定窗口依次点击四个球场角点：**左上 → 右上 → 右下 → 左下**。
3. 标定结果会缓存到 `results/<视频名>/court_annotations.txt`，后续运行会自动复用。

如果拍摄视角、裁切或模板发生变化，删除对应的 `court_annotations.txt` 后重新标定即可。

## 🖥️ Web Demo

Web Demo 是一个本地运行的可视化工作台：视频只写入本机的 `storage/`，分析结果写入本机的 `results/`，不依赖云端服务。

### 启动后端

```bash
pip install -r requirements.txt -r web-requirements.txt
python -m web.api.run
```

后端地址：<http://127.0.0.1:8000>

### 启动前端

另开一个终端，并激活同一个虚拟环境：

```bash
cd web/frontend
npm install
npm run dev
```

前端地址：<http://127.0.0.1:5173>

Web Demo 支持：

- 上传比赛视频并预览
- 按起止时间截取分析片段
- 在浏览器中点击四个球场角点完成标定
- 查看排队、运行、完成和失败状态
- 预览带标注视频、热力图和散点图
- 下载分析产物、查看历史任务并删除本地任务

## 🧠 功能特性

### 视觉分析

- **球员姿态检测**：支持 RTMPose、RTMO 和 Ultralytics YOLO Pose。
- **羽毛球检测**：使用 YOLO 模型定位羽毛球，并绘制跨帧轨迹。
- **球场坐标映射**：通过四点透视变换，将图像坐标映射到标准羽毛球场坐标。
- **球员追踪**：区分上下半场球员，记录球场位置和移动轨迹。
- **回合识别**：根据连续球场视图识别回合区间并标记回合编号。

### 结果与分析

- **运动统计**：移动距离、瞬时速度、平均速度、最大速度和回合数。
- **位置图表**：生成球员位置热力图和散点图。
- **视频叠加层**：可开关姿态 ROI、骨架、球员轨迹、球场轨迹、羽毛球轨迹和统计面板。
- **结构化导出**：输出 `metadata.json`、`session_summary.json` 和逐帧 `detections.jsonl`。
- **中英文可视化**：通过 `--language zh/en` 切换 CLI 输出图中的文字。

## 🏗️ 处理流程

```text
比赛视频
   │
   ├── 球员姿态检测（RTMPose / RTMO / YOLO Pose）
   ├── 羽毛球检测（YOLO）
   └── 球场四点标定
          │
          ▼
   透视变换：图像坐标 → 标准球场坐标
          │
          ▼
   球员追踪、回合识别、速度与距离统计
          │
          ├── 带标注 MP4
          ├── 热力图 / 散点图
          └── JSON / JSONL 结构化数据
```

## ⚙️ 常用参数

| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `--video-path` | 输入视频路径（必填） | — |
| `--output-dir` | 输出目录 | `results/<视频文件名>` |
| `--ball-model` | 羽毛球检测模型路径 | `weights/yolo11s-ball.pt` |
| `--pose-family` | `rtmpose` / `rtmo` / `yolo-pose` | `rtmpose` |
| `--pose-mode` | `lightweight` / `balanced` / `performance` | `balanced` |
| `--yolo-pose-model` | YOLO Pose 模型路径或模型名 | `yolo11n-pose.pt` |
| `--template-path` | 球场模板图像路径 | 文件选择框 |
| `--display` | 是否显示 OpenCV 预览窗口 | `true` |
| `--skeletons` | 是否绘制人体骨架 | `true` |
| `--player-trajectories` | 是否绘制球员轨迹 | `true` |
| `--court-trajectory` | 是否绘制球场轨迹 | `true` |
| `--shuttlecock-trajectory` | 是否绘制羽毛球轨迹 | `true` |
| `--player-stats` | 是否显示球员统计面板 | `true` |
| `--visualize-positions` | 是否生成热力图和散点图 | `true` |
| `--audio` | 是否保留原视频音频 | `true` |
| `--language` | 可视化语言：`zh` / `en` | `zh` |
| `--save-images` | 是否保存逐帧图像 | `false` |
| `--performance-stats` | 是否打印性能统计 | `false` |

## 📦 输出结果

CLI 默认输出到 `results/<视频文件名>/`：

```text
results/<video_name>/
├── metadata.json                  # 视频、模型、标定和输出元信息
├── detections.jsonl               # 逐帧检测记录
├── detect_<video_name>.mp4        # 带骨架、轨迹和统计面板的视频
├── court_annotations.txt          # CLI 四点标定缓存
└── position_visualizations/
    ├── heatmaps/                  # 球员位置热力图
    └── scatter_plots/              # 球员位置散点图
```

Web / 服务模式会在对应任务目录额外写入 `session_summary.json`，用于记录任务状态、统计摘要和产物索引。

Web Demo 的运行文件位于 `storage/` 和 `results/web/`，这些目录已加入 `.gitignore`，不会被提交。

## 🧩 项目结构

```text
AI-YuJian-AI/
├── main.py                       # CLI 入口
├── badminton_analysis/           # 核心视频分析管线
│   ├── court/                    # 球场标定与坐标映射
│   ├── data/                     # JSON / JSONL 持久化
│   ├── detection/                # 姿态与羽毛球检测
│   ├── media/                    # 视频与音频处理
│   ├── tracking/                 # 球员追踪
│   └── visualization/            # 视频叠加层与图表
├── web/
│   ├── api/                     # FastAPI 任务服务
│   └── frontend/                # React + Vite 前端
├── assets/                      # 演示 GIF、视频和示例图
├── templates/                   # 球场模板图
├── videos/                      # 示例输入视频
├── specs/                       # 设计与需求文档
├── requirements.txt             # 分析依赖
└── web-requirements.txt         # Web 后端依赖
```

## 🔮 路线图

- [x] 羽毛球比赛视频逐帧分析
- [x] RTMPose / RTMO / YOLO Pose 多姿态模型
- [x] YOLO 羽毛球检测模型接入
- [x] 手动球场标定与坐标映射
- [x] 球员移动轨迹、速度、距离和回合统计
- [x] 热力图、散点图和结构化数据导出
- [x] 本地 Web Demo：上传、标定、排队分析和结果下载
- [ ] 更稳定的击球点识别
- [ ] 更精准的羽毛球检测模型
- [ ] 更完整的技术动作统计
- [ ] 自动球场关键点检测
- [ ] 批量视频分析工作流

## 🛠️ 技术栈

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

## 🙏 致谢

- [TrackNetV2](https://github.com/wywyWang/TrackNetV2)：羽毛球数据集相关工作
- [RTMPose](https://github.com/open-mmlab/mmpose)：人体姿态估计
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)：目标检测生态

## 📄 许可证

项目代码采用 [Apache License 2.0](LICENSE)。模型权重不随仓库提交，请在下载和分发时遵循各自上游项目的许可证与归属要求。

---

<div align="center">

如果这个项目对你有帮助，欢迎 ⭐ Star 支持一下。

**Made with ❤️ by [lzylovec](https://github.com/lzylovec)**

</div>
