# 实时分析性能调优记录（GPU 启用）

日期：2026-09-14
目标：在不修改代码的前提下，让实时分析调用 GPU 并缩短取帧间隔。
结论：**帧间隔从 152 ms 降到 75 ms（吞吐 6.6 → 13.3 FPS），延迟指标 frame_age 从 156 ms 降到 47 ms。**

## 1. 硬件与依赖变更

| 项 | 变更前 | 变更后 |
| :-- | :-- | :-- |
| PyTorch | `2.5.1+cpu` | `2.5.1+cu124` |
| torchvision | `0.20.1+cpu` | `0.20.1+cu124` |
| `torch.cuda.is_available()` | `False` | `True` |
| 识别设备 | `NVIDIA GeForce RTX 4070 Laptop GPU` | 同左，实际可用 |
| 摄像头设置 `device` | `cpu` | `cuda:0` |
| `analysis_fps` | `10` | `25` |
| `record_video` | `True` | `False` |

驱动 566.07（支持 CUDA 12.7）与 cu124 运行时兼容。CUDA 版 wheel（2 394 MB）从 PyTorch 官方 CDN 分段断点续传获取，脚本见 `scripts/download_torch_cu124.ps1`。

### 注意：pip 不会自动把 `+cpu` 换成 `+cu124`

两种 wheel 的版本号都是 `2.5.1`，仅 local version 标签不同，普通 `pip install` 会直接
报 "Requirement already satisfied" 而静默跳过。必须使用
`--force-reinstall`（并配合 `--no-deps`，因为 cu124 索引不含 numpy 等依赖）。

## 2. 单帧各阶段耗时（2560×1440，实测）

隔离压测（GPU）：

| 路径 | 耗时 | 吞吐 |
| :-- | --: | --: |
| CPU 推理 `device=cpu` | 41.7 ms | 24.0 FPS |
| **GPU 推理 `device=0`** | **14.3 ms** | **69.8 FPS** |
| 整帧 2560×1440 → model | 16.7 ms | 60.0 FPS |
| 预缩放到 640×360 → model | 14.6 ms | 68.5 FPS |
| 纯 CNN 前向（640×640 张量已在 GPU） | 12.5 ms | 80.2 FPS |
| 纯 CPU 预处理（resize+RGB+归一化） | 4.7 ms | 214 FPS |

结论：**推理本身不是瓶颈**——即使不缩放整帧，GPU 也能跑到 60 FPS 以上。

整链路分阶段剖析（`scripts/profile_live_stages.py`）：

| 阶段 | 录制开启 | 录制关闭 |
| :-- | --: | --: |
| grab 取帧（含等待下一帧） | 9.7 ms | ~0 ms |
| pose 推理（GPU） | 39.8 ms | 25.2 ms |
| draw 叠加绘制（CPU） | 35.0 ms | 29.5 ms |
| write_raw 原始录像编码 | 47.9 ms | 0 |
| write_ann 标注录像编码 | 48.4 ms | 0 |
| jpeg 预览编码 | 11.0 ms | 12.6 ms |
| **合计 / 实测吞吐** | **≈192 ms → 5.5 FPS** | **≈70 ms → 14.3 FPS** |

GPU 利用率实测仅 13–37%、功耗 5–14 W —— **循环是 CPU 受限，不是 GPU 受限**。

## 3. 三次端到端会话对比（同一摄像头、同一台机器）

| 配置 | 处理帧 | 推理 FPS | frame_age | 标注录像 |
| :-- | --: | --: | --: | :-- |
| CPU + 录制开 + `analysis_fps=10` | 174 / 30 s | 6.60 | 156 ms | 有 |
| GPU + 录制开 + `analysis_fps=25` | 255 / 42 s | 6.76 | 148 ms | 有 |
| **GPU + 录制关 + `analysis_fps=25`** | **342 / 30 s** | **13.30** | **47 ms** | 无 |

关键结论：**只换 GPU 几乎没有提升（6.60 → 6.76 FPS）**，因为瓶颈是录像编码；
关闭录像后提升到 13.3 FPS。`skipped_frames` 也相应从 451 降到 266。

## 4. 取舍说明

`record_video=False` 的代价是**不再产出带骨架叠加的 `annotated_*.mp4`**。
`keep_audio=True` 仍然保留原始码流 HLS（`source.m3u8`），且检测数据
（`detections.jsonl`）、热力图/散点图、`session_summary.json` 全部照常产出。

需要复盘标注录像时，可在 `/live` 页面重新打开录像开关，代价是分析帧率回到约 6.8 FPS。

## 5. 未能消除的剩余瓶颈（需改代码）

关闭录像后剩余约 70 ms/帧，其中：

- `draw` 29.5 ms —— 骨架/轨迹/统计面板全部直接画在 2560×1440 全分辨率帧上
- `pose` 25.2 ms —— 整帧送入模型，含每帧 numpy→张量拷贝
- `jpeg` 12.6 ms —— 1280 宽预览编码

要在不改代码的前提下再提升，只能降低摄像头输出分辨率（在摄像头 Web 管理页调整），
把 2560×1440 降到 1280×720 可让上述三项大体按比例下降。

## 6. 当前生效配置

```
device          = cuda:0
analysis_fps    = 25
record_video    = False
record_fps      = 25
keep_audio      = True
pose_family     = yolo-pose      (weights/yolo11n-pose.pt)
ball_enabled    = False          (weights/yolo11s-ball.pt 缺失)
```

摄像头地址与凭据已保留；**标定已清空**，需在 `/live` 页面重新抓图并点选四角。
