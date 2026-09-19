# 本地启动与网络摄像头验证记录

验证时间：2026-09-14
工作目录：`D:\ballcctv\AI-YuJian-AI-CCTV`
摄像头：`rtsp://<credentials>@192.168.0.15/live/chn=0`（凭据不写入本文件）

## 结论

| # | 验证项 | 结果 |
| :-- | :-- | :-- |
| 1 | 环境搭建（Python 3.11 venv + 依赖） | 通过 |
| 2 | 前端构建（`web/frontend/dist`） | 通过 |
| 3 | 后端启动（FastAPI + uvicorn，`127.0.0.1:8000`） | 通过 |
| 4 | SPA 页面与深层路由（`/`、`/live`、`/history`） | 通过 |
| 5 | **网络摄像头 RTSP 连通与解码** | **通过** |
| 6 | 应用内抓图（`POST /api/live/court/snapshot`） | 通过 |
| 7 | 直播分析进程（模型加载 → 取帧 → 统计 → 产物封存） | 通过 |
| 8 | 会话产物下载 / 图表读取 | 通过 |
| 9 | FFmpeg 可用性（`ffmpeg_available`） | 通过（补装 `imageio-ffmpeg` 后） |
| 10 | 真实球场画面四点标定 | **未执行（需现场人工完成）** |
| 11 | 球场识别准确率验收 | **未执行（需实拍与人工标注）** |

## 摄像头实测数据

```
isOpened: True (open took 1.44–2.15s)
backend: FFMPEG
reported_width_height: 2560x1440
reported_fps: 25.0
reported_fourcc: 'h264'
read_failures: 0
first_frame_after_sec: 1.5
```

- 主机 `192.168.0.15` TCP 80 与 554 均开放；端口 80 返回中文 Web 管理页面（非标准 ONVIF/Dahua CGI，`/cgi-bin/*` 与 `/snapshot.jpg` 均 404）。
- ICMP ping 无应答，属设备策略，不影响 RTSP。
- 采样帧统计：2560×1440×3，亮度均值 110–111、标准差 66.8–70.1、灰度级 256 级全覆盖 → 真实场景画面而非纯色/黑屏。

## 直播分析实测（CPU，`device=cpu`，`analysis_fps=10`）

应用内 HTTP 全链路会话（`POST /api/live/sessions` → 轮询 → `stop`）：

```
[  3.0s] status=preparing
[  9.1s] status=running  frames=18   inference_fps=3.60
[ 30.2s] status=running  frames=171  inference_fps=6.60  frame_age_sec=0.109
stop  -> status=stopped  frames=174  skipped=451  source_fps=25.0
```

产物：`annotated_*.mp4` 分片、`camera_*.mp4` 分片、`detections.jsonl`（174 行）、
`match_heatmap.jpg` / `match_scatter.jpg` / `rally_*.jpg`、`live_summary.json`、
`session_summary.json`、`metadata.json`。图表接口返回 `image/jpeg`（30 284 字节）正常。

说明：测试画面中无羽毛球比赛场景，检测到的人物位置为空属预期；本项验证的是
**取流—推理—统计—封存—读取**链路的可用性，不代表识别准确率或完整直播帧率。
`skipped_frames` 偏大是因为 `analysis_fps=10` 低于摄像头 25fps，属设计内跳帧。

## 启动过程中发现并修复的问题

1. **OpenCV 5.x 兼容性缺陷（代码修复）**
   `badminton_analysis/media/frame_source.py:47` 调用 `cv2.setLogLevel(0)`，该 API 在
   OpenCV 5.0 中已被移除。取流线程在建立连接**之前**即抛 `AttributeError` 退出，
   上层表现为「摄像头连接超时」（API 返回 502 / `摄像头连接超时`），极易被误判为
   网络或凭据问题。
   → 已改为按能力检测：优先 `cv2.setLogLevel`，否则回退
   `cv2.utils.logging.setLogLevel(LOG_LEVEL_SILENT)`。修复后同一摄像头 1.7s 内抓帧成功。
   注：项目 `requirements-live.txt` 锁定 `opencv-python==4.10.0.84`，按文档安装不会触发此问题。

2. **PyPI 镜像分片校验失败**
   `mirrors.aliyun.com` 下载的 `imageio-ffmpeg` 出现 SHA-256 不匹配导致整批安装回滚。
   → 改用官方 `pypi.org` 安装成功。安装大体积依赖时建议固定来源并校验哈希。

3. **并发 pip 安装互相覆盖**
   两个并行 pip 进程同时安装到同一 venv，先完成者被后完成者的安装记录覆盖，
   表现为「装完却 `pip list` 看不到」。
   → 依赖安装改为串行执行。

4. **npm / esbuild 受限说明（环境限制，非项目缺陷）**
   初次 `npm install` 与 `vite build` 在受限沙箱下因 `spawn EPERM` 失败；
   放开权限后正常。前端已成功产出 `dist/`（`tsc --noEmit` 通过，49 模块）。

5. **FFmpeg 缺失导致片段导出不可用（依赖补装）**
   `ffmpeg` 不在系统 `PATH`，且 venv 未安装 `imageio-ffmpeg`，`/api/system/health` 返回
   `ffmpeg_available=false`，录像裁剪/片段导出会直接报错。
   → `badminton_analysis/media/binaries.py` 会回退到 `imageio_ffmpeg`，因此补装
   `imageio-ffmpeg==0.6.0` 后无需改动系统 `PATH` 即恢复：现返回 `ffmpeg_available=true`，
   解析到 `.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe`。

## 当前状态与后续步骤

- 服务正在运行：<http://127.0.0.1:8000>（`/live` 为球场实时分析入口）。
- 摄像头配置已保存（地址、`admin` 账号、密码已加密存放于 `.runtime/live.sqlite3`，接口不回显密码）。
- **标定已清空**：`/api/live/health` 当前提示「请先抓取摄像头画面并完成四点标定」。
  测试期间为验证链路注入的合成标定已移除，避免污染现场配置。
- 下一步：打开 <http://127.0.0.1:8000/live> → 点击「连接并抓取画面」→ 在**真实球场画面**上
  按左上、右上、右下、左下点击四角保存标定 → 开始分析。
- 本机为 CPU 版 PyTorch（`2.5.1+cpu`，实测约 6.6 FPS@10fps 目标、含录像叠加）。
  现场需要更高帧率时按 `docs/live-deployment.md` 安装 `cu124` 版 PyTorch。

## 复现命令

```powershell
# 启动服务
$env:YUJIAN_HOST="127.0.0.1"; $env:YUJIAN_PORT="8000"
.\.venv\Scripts\python.exe -m web.api.run

# 摄像头连通性（不打印凭据）
.\.venv\Scripts\python.exe scripts\verify_rtsp.py --url "rtsp://<user>:<pass>@192.168.0.15/live/chn=0" --frames 5

# 直播链路（工作目录需在本仓库根目录）
$env:PYTHONPATH = $PWD.Path
.\.venv\Scripts\python.exe scripts\test_live_worker.py --seconds 45

# 应用内 HTTP 全链路
.\.venv\Scripts\python.exe scripts\test_live_session_api.py --seconds 30

# 清除测试标定（保留摄像头地址与凭据）
.\.venv\Scripts\python.exe scripts\clear_live_calibration.py
```

## 证据文件（`.runtime/verify/`）

| 文件 | 说明 |
| :-- | :-- |
| `app_snapshot.jpg` | 经应用 API 抓取的摄像头画面（2560×1440） |
| `result.json` | 直接 RTSP 探测结果（分辨率、帧率、后端、耗时） |
| `http_probe.json` | 摄像头 HTTP 端口探测结果 |
| `court_quad.jpg` / `court_overlay.jpg` | 球场亮区与长直线检测叠加图，供人工核对角点 |
| `corners.json` | 上述自动拟合出的候选角点（**仅供参考，未用于正式标定**） |
