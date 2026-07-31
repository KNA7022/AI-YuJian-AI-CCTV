<div align="center">

# 🏸 AI-YuJian-AI · 羽见 AI

### AI 羽毛球鹰眼系统 —— 让每一拍都看得见

[![GitHub stars](https://img.shields.io/github/stars/lzylovec/AI-YuJian-AI?style=for-the-badge&logo=github&color=ffd33d)](https://github.com/lzylovec/AI-YuJian-AI/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/lzylovec/AI-YuJian-AI?style=for-the-badge&logo=github&color=58a6ff)](https://github.com/lzylovec/AI-YuJian-AI/network/members)
[![License](https://img.shields.io/github/license/lzylovec/AI-YuJian-AI?style=for-the-badge&color=blueviolet)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=for-the-badge)]()
[![Open Source](https://img.shields.io/badge/Open%20Source-Apache%202.0-success?style=for-the-badge)]()

**基于计算机视觉的羽毛球比赛视频分析工具 · 你的开源版鹰眼**

[English](README_EN.md) · [快速开始](#-快速开始) · [功能特性](#-功能特性) · [效果展示](#-效果展示) · [路线图](#-路线图)

</div>

---

## ✨ 这是什么

**AI-YuJian-AI**（羽见 AI）是一套面向业余和专业羽毛球比赛的开源视频分析系统。它把一段比赛录像，喂给几个 CV 模型，就能自动输出：

- 🎯 **球员姿态** —— RTMPose / RTMO / YOLO Pose 多模型支持
- 🪶 **羽毛球轨迹** —— YOLO 检测 + 跨帧追踪
- 🗺️ **球场坐标映射** —— 手动四点标注 → 标准球场坐标系
- 📊 **运动统计** —— 移动距离、瞬时速度、最大速度、回合数
- 🔥 **位置热力图** —— 上下半场球员热区 & 散点图
- 🎬 **可视化比赛视频** —— 骨架 / 轨迹 / 数据 / 回合编号叠加层
- 🌐 **中英双语** —— 一键切换 `--language zh/en`

> 名字来由：**羽见 = 看见每一羽**；AI-YuJian-AI 既是双关，也像强化学习的"AI 见 AI，愈见愈明"。

---

## 🎬 效果展示

<div align="center">

![AI-YuJian-AI 分析效果预览](assets/demo.gif)

*完整演示视频：[`assets/demo.mp4`](assets/demo.mp4)*

</div>

### 📍 位置可视化

| 🔥 热力图 | 🎯 散点图 |
| :---: | :---: |
| ![球员位置热力图](assets/match_heatmap.png) | ![球员位置散点图](assets/match_scatter.png) |

---

## 🆕 更新日志

- **2026-07-31** · 项目重命名为 **AI-YuJian-AI**（羽见 AI），重写 README。
- **2026-06-20** · 正式开源。
- **2026-06-17** · 整理项目介绍文档。
- **当前版本** · 球员姿态检测 · 羽毛球检测 · 球场坐标映射 · 轨迹统计 · 热力图/散点图 · 带标注视频输出。
- **实验功能** · 击球点分析、技术动作统计仍在迭代中，适合研究和二次开发。

---

## ✨ 功能特性

### 🧠 AI 视觉
- 🦴 **球员姿态检测** —— 支持 RTMPose、RTMO、Ultralytics YOLO Pose，识别人体关键点和骨架
- 🪶 **羽毛球检测** —— 基于 YOLO 模型检测羽毛球位置，并在输出视频中绘制轨迹
- 🗺️ **球场坐标映射** —— 手动标注四点球场关键点，把图像坐标映射到标准羽毛球场地坐标
- 🧍 **球员位置追踪** —— 区分上下半场球员，分别记录移动轨迹
- 🏸 **回合检测** —— 通过连续球场视图自动判定回合开始 / 结束，并在叠加层和数据中标注回合编号

### 📊 数据分析
- 📏 **运动统计** —— 移动距离、瞬时速度、最大速度、回合数
- 🔥 **位置图表** —— 自动生成球员位置热力图和散点图
- 📁 **结构化导出** —— `metadata.json` + `detections.jsonl` 方便二次开发

### 🎨 视觉与体验
- 🎬 **可视化输出** —— 带骨架 / 轨迹 / 统计 / 回合编号叠加层的 MP4
- 🌐 **中英双语** —— 通过 `--language zh/en` 切换可视化文字
- 🎛️ **可调叠加层** —— ROI、骨架、球员轨迹、球场轨迹、羽毛球轨迹、统计面板按需开关
- 🖥️ **本地运行** —— 视频、模型、结果全部留在本地，零云依赖

---

## 🏗️ 架构

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

## 🚀 快速开始

### 📋 系统要求

- **Python** 3.8+
- **FFmpeg** 已加入系统 `PATH`
- **OpenCV / PyTorch / Ultralytics / RTMLib / ONNX Runtime**
- 推荐 **NVIDIA GPU**；CPU 也能跑，但分析速度会明显变慢

### 📦 安装

```bash
# 克隆仓库
git clone https://github.com/lzylovec/AI-YuJian-AI.git
cd AI-YuJian-AI

# 创建虚拟环境
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 安装依赖（默认 CPU 版）
pip install -r requirements.txt
```

### 🎮 GPU 加速（Windows / NVIDIA，可选）

```powershell
.\.venv\Scripts\activate

pip uninstall -y torch torchvision onnxruntime onnxruntime-gpu
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install onnxruntime-gpu==1.20.1

# 验证
python -c "import torch; print('cuda:', torch.cuda.is_available())"
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# 期望看到: cuda: True 和 CUDAExecutionProvider
```

### 🧠 模型准备

从 [GitHub Releases](https://github.com/lzylovec/AI-YuJian-AI/releases) 下载羽毛球检测权重：

```text
weights/yolo11s-ball.pt
```

RTMPose / RTMO / YOLOX 可选 ONNX 模型：

```text
weights/yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx
weights/rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx
weights/rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx
```

> 本地 ONNX 不存在时，`rtmlib` 会尝试在线下载到用户缓存目录。

### ▶️ 运行

```bash
# 基础运行
python main.py --video-path videos/demo.mp4

# 选择姿态模型
python main.py --video-path videos/demo.mp4 --pose-family rtmpose --pose-mode balanced
python main.py --video-path videos/demo.mp4 --pose-family rtmo --pose-mode lightweight
python main.py --video-path videos/demo.mp4 --pose-family yolo-pose --yolo-pose-model yolo11n-pose.pt

# 切换中英文
python main.py --video-path videos/demo.mp4 --language en
```

#### 第一次运行

1. 准备输入视频和羽毛球权重
2. 跑基础命令，未传 `--template-path` 会弹出文件选择框，选一张球场清晰可见的模板帧
3. 弹出球场标注窗口 → 按顶部提示，**依次点击 4 个角点：左上 → 右上 → 右下 → 左下**

![球场标注示例](assets/label_court_example.png)

4. 完成后会显示绿色球场框 + 蓝色姿态 ROI 框
5. 标注结果缓存到 `results/<视频名>/court_annotations.txt`，下次自动复用

> 换了视角 / 裁切 / 模板图？删掉对应目录里的 `court_annotations.txt` 重新标注即可。

---

## ⚙️ 常用参数

| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `--video-path` | 输入视频路径（必填） | — |
| `--output-dir` | 输出目录 | `results/<视频文件名>` |
| `--ball-model` | 羽毛球检测模型 | `weights/yolo11s-ball.pt` |
| `--pose-family` | 姿态模型族：`rtmpose` / `rtmo` / `yolo-pose` | `rtmpose` |
| `--pose-mode` | 档位：`lightweight` / `balanced` / `performance` | `balanced` |
| `--yolo-pose-model` | YOLO pose 模型 | `yolo11n-pose.pt` |
| `--template-path` | 球场模板图 | 弹出选择框 |
| `--pose-roi` | 显示姿态 ROI 框 | `true` |
| `--display` | 显示 OpenCV 预览 | `true` |
| `--skeletons` | 显示人体骨架 | `true` |
| `--player-trajectories` | 显示球员轨迹 | `true` |
| `--court-trajectory` | 显示球场轨迹叠加层 | `true` |
| `--shuttlecock-trajectory` | 显示羽毛球轨迹 | `true` |
| `--player-stats` | 显示球员统计 | `true` |
| `--visualize-positions` | 生成热力图 & 散点图 | `true` |
| `--audio` | 保留原视频音频 | `true` |
| `--language` | `zh` / `en` | `zh` |
| `--save-images` | 保存逐帧图像 | `false` |
| `--performance-stats` | 打印性能耗时 | `false` |

---

## 📊 输出结果

默认输出到 `results/<视频文件名>/`：

```text
results/<video_name>/
├── metadata.json                  # 视频 / 模型 / 球场标注 / 输出元信息
├── detections.jsonl               # 逐帧检测记录（回合、球员、手部、坐标、速度、羽毛球）
├── detect_<video_name>.mp4        # 带骨架 / 轨迹 / 统计 / 回合编号的 MP4
├── court_annotations.txt          # 球场四点标注缓存
└── position_visualizations/
    ├── heatmaps/                   # 球员位置热力图
    └── scatter_plots/              # 球员位置散点图
```

---

## 🧩 项目结构

```text
AI-YuJian-AI/
├── main.py                       # CLI 入口与参数解析
├── badminton_analysis/
│   ├── system.py                 # 视频分析主流程
│   ├── service.py                # 上层服务封装
│   ├── court/                    # 球场标注 & 坐标映射
│   ├── data/                     # JSON / JSONL 持久化
│   ├── detection/                # 羽毛球检测 & 姿态检测
│   ├── media/                    # 视频 / 音频处理
│   ├── tracking/                 # 球员追踪
│   ├── visualization/            # 叠加层 & 统计图
│   └── analysis/                 # 回合 / 统计计算
├── assets/                       # 演示 GIF / 视频 / 示例图
├── videos/                       # 输入视频
├── templates/                    # 球场模板图
├── results/                      # 默认输出目录
├── specs/                        # 设计文档
└── weights/                      # 模型权重（运行时下载）
```

---

## 🔮 路线图

- [x] 羽毛球比赛视频逐帧分析
- [x] RTMPose / RTMO / YOLO Pose 多姿态模型
- [x] YOLO 羽毛球检测模型接入
- [x] 手动球场标注 & 球场坐标映射
- [x] 球员移动轨迹、速度、距离、回合统计
- [x] 中 / 英可视化文字
- [x] 热力图、散点图、检测数据导出
- [ ] 更稳定的击球点识别
- [ ] 更精准的羽毛球检测模型
- [ ] 更完整的技术动作统计
- [ ] 自动球场关键点检测
- [ ] 批量视频分析工作流

---

## 🛠️ 技术栈

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

## 🙏 致谢

- [TrackNetV2](https://github.com/wywyWang/TrackNetV2) 提供的羽毛球数据集
- [RTMPose](https://github.com/open-mmlab/mmpose) 的人体姿态检测算法
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) 的检测生态

---

## 📄 许可证

本项目代码和 `weights/yolo11s-ball.pt` 使用 **Apache License 2.0**。
随 Release 提供的 RTMPose / RTMO / YOLOX ONNX 权重来自 OpenMMLab / RTMPose 生态，
按其上游 Apache License 2.0 授权使用，并保留原始归属。

详见 [LICENSE](LICENSE)。

---

<div align="center">

如果这个项目对你有帮助，欢迎 ⭐ Star 支持一下！

**Made with ❤️ by [lzylovec](https://github.com/lzylovec)**

</div>
