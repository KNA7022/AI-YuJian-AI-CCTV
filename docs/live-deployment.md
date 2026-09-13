# 球场实时分析：运行与部署

当前实现为单摄像头、固定机位、单打双人的本地实时分析。现有上传录像入口保留，`/live` 支持同类识别、统计、图表和结果导出。双打独立身份、击球分类、精确落点和长期场馆验收尚未完成；自动回合使用运动启停估计，不等同于经过标注验收的比赛回合判定。

## 安装

使用 Python 3.10～3.12，推荐在项目目录建立独立虚拟环境。以下为 Windows PowerShell 命令。

```powershell
python -m venv .venv
# NVIDIA GPU（保持与当前项目模型版本兼容的 PyTorch 2.5.1）
.venv/Scripts/python.exe -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
# CPU 主机使用上方命令的 https://download.pytorch.org/whl/cpu 源
.venv/Scripts/python.exe -m pip install -r requirements-live.txt
```

不要随后安装原来的 `requirements.txt` 覆盖 GPU 包，因为它锁定了 CPU PyTorch。直播和上传都可以选择 YOLO Pose、RTMPose、RTMO。后两者另外安装以下依赖；CPU 机器把 `onnxruntime-gpu` 改为 `onnxruntime`，不要同时安装两种 Runtime。

```powershell
.venv/Scripts/python.exe -m pip install rtmlib==0.0.13 --no-deps
.venv/Scripts/python.exe -m pip install onnxruntime-gpu==1.20.2
.venv/Scripts/python.exe scripts/download_live_models.py
.venv/Scripts/python.exe scripts/download_pose_modes.py
```

`--no-deps` 避免 rtmlib 自动再安装 CPU Runtime；其 numpy、OpenCV、tqdm 依赖由上述通用运行环境提供。两份脚本分别获取基础权重与 RTMPose/RTMO 的其余档位，使用本地模型后直播启动无需临时下载。

GPU 安装命令依据 [PyTorch 官方历史版本说明](https://pytorch.org/get-started/previous-versions/)。不同硬件应验证驱动兼容性，不以显卡存在代替 CUDA 可用性检测：

```powershell
.venv/Scripts/python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

将官方 YOLO11n Pose 权重放在 `weights/yolo11n-pose.pt`。专用羽毛球权重从原始项目 [Good-Badminton v0.1.0](https://github.com/yo-WASSUP/Good-Badminton/releases/tag/v0.1.0) 下载，放在 `weights/yolo11s-ball.pt`。当前 fork 及重命名后的源仓库没有同步 Release 资产；不要只根据它们的 Releases 页面判断权重缺失。缺少权重时可关闭羽毛球检测。

也可以运行 `.venv/Scripts/python.exe scripts/download_live_models.py`，下载两份 YOLO 和基础 ONNX 模型并验证 Release 公布的 SHA-256；不会覆盖同名的不同自训练模型。

`imageio-ffmpeg` 提供应用可直接使用的 FFmpeg；不必修改系统 PATH。直播单独保存原始视频码流及 AAC 音轨为 HLS，浏览器可播放、回听、回看；摄像头必须实际提供音频。标注画面按本机接收时间重采样，导出标注片段时可附加原始音轨，依据本机时间近似对齐，不保证摄像头 PTS 级同步。HLS 播放通常比 JPEG 识别预览多出分片缓冲延迟，编码兼容性取决于浏览器。

## 上传功能在直播中的对应方式

| 上传功能 | 直播操作与更新时间 |
| --- | --- |
| 文件输入、名称、选取时间区间 | 摄像头源、球场名称、开始/停止会话；已接收区间可边分析边裁剪导出 |
| 参考帧四点标定 | 开始前抓取当前帧并标定，固定机位后复用 |
| YOLO Pose / RTMPose / RTMO、档位、语言 | 在识别设置中选择；配置对下一次会话生效 |
| 骨架、球员轨迹、羽毛球检测与轨迹、小球场映射 | 每个实际分析帧计算并叠加到预览 |
| 当前速度、平均/最高速度、距离、整场/回合统计 | 逐帧累计，页面约每 2 秒读取最新统计 |
| 回合计数 | 连续羽毛球运动估计开始、静止/失踪估计结束，可人工标记边界纠正 |
| 热力图、散点图 | 整场/当前回合两种范围，运行中约每 2 秒生成 |
| 保留声音、结果录像 | 原始 HLS 音视频回看；标注录像约 10 秒封存，可导出带标注片段 |
| JSON/JSONL、结果下载、任务历史/删除 | 运行中下载数据快照及封存结果，停止后完整数据可下载，会话可删除 |

片段导出最多 10 分钟，由独立后台线程调用 FFmpeg，不占用分析的 GPU 槽；CPU 与磁盘负载仍会影响实际吞吐。原始片段使用播放器时间，标注片段使用会话时间（含模型初始化），界面显示可用范围；断流空白不能作为连续标注片段导出。

## 启动

```powershell
Set-Location web/frontend
npm install
npm run build
Set-Location ../..
./start-live.ps1
```

打开 <http://127.0.0.1:8000/live>。也可以在项目目录运行 `.venv/Scripts/python.exe -m web.api.run`。前端深层路由支持刷新。Linux 使用 `.venv/bin/python -m web.api.run`。

需要球场局域网访问时，先在进程环境设置 `YUJIAN_PASSWORD`，再执行 `./start-live.ps1 -BindAddress 0.0.0.0`。浏览器登录账号为 `operator`，密码为设置值。不要把密码写进脚本、文档或命令历史；可通过 PowerShell 的安全输入或部署平台环境配置设置。绑定非回环地址但未配置密码时，启动脚本入口会拒绝启动。直接使用其他 uvicorn 启动方式时，也必须自行配置该密码。Basic 登录应在受信内网使用，跨网络部署需配置 HTTPS。

服务只启动一个 API 实例/worker；当前 GPU 排他锁属于进程内协调，多 API 实例不属于本版支持范围。开机启动可以用 Windows 任务计划程序启动此脚本，工作目录设为仓库根目录，使用拥有 `.runtime` 和 `results` 读写权限的服务账号。此版本未自动修改系统开机任务。

## 首次操作

1. 保存 RTSP 地址、账号、密码。地址输入框不要嵌入凭据，密码留空表示保留已经保存的密码。示例路径为 `rtsp://192.168.0.15/live/chn=0`。
2. 点击“连接并抓取画面”，检查视角和分辨率。调整摄像头，使四个场角及运动员脚部清楚可见，保留高球区域。
3. 在真实球场画面中按左上、右上、右下、左下点击四角，保存标定。不要在桌面预览上做正式标定。
4. 准备本地模型后点击“开始分析”。观察实际 FPS、跳过帧和本机取帧至识别耗时。该耗时不包含未知的摄像头编码/网络缓存延迟，不等同于完整端到端延迟。
5. 自动估计回合需要开启羽毛球检测。需要时点击“标记回合边界”，开启新回合并重置当前回合统计；整场统计继续累计。
6. 点击“停止并保存”，等待进程封存输出。在会话历史中下载 JSONL、摘要、热力图和录像分片。

更换 RTSP 地址或账号密码会清除关联的快照/标定。修改摄像头位置、缩放或裁切后，即使分辨率相同，也必须人工重新标定；本版不能自动检测所有同分辨率机位变化。分辨率不一致会阻止直播继续分析。

人物按地面坐标分为远场、近场。某半场检测到多人时，该半场位置记为不确定，不累计移动；这只是单打保护，不等同于双打跟踪或可靠的身份重识别。位置统计过滤长间隔和异常跳点，读取统计不会再次累计距离。热力图展示有效观测次数的分布，不代表按真实停留时间归一化的占位率。

## 数据与恢复

- `.runtime/live.sqlite3`：摄像头配置（含凭据）、标定、会话状态。此目录不被 Web 静态服务发布，也被 Git 忽略。保留系统文件访问限制，备份时按敏感配置处理。
- `.runtime/snapshot_*.jpg`：抓取的参考画面；通过明确的 API 读取当前画面。
- `results/live/<会话 ID>/metadata.json`：不含 RTSP 凭据的配置与标定快照。
- `detections.jsonl`：源序号、连接代次、本机接收时间、人物地面位置、球的检测状态。
- `camera_*.mp4` / `annotated_*.mp4`：原画面/叠加画面的无音频复盘分片；分别约 60 秒/10 秒一段，断流或分辨率改变会另起分片。
- `source.m3u8` / `source_*.ts`：原始视频及可选音频。开启录像时保留全场，关闭录像但保留声音时仅保留滚动窗口，不能导出历史片段。
- `clip_*.json` / `clip_*.mp4`：后台裁剪任务状态和导出结果；导出进行中会阻止删除该会话。
- `match_heatmap.jpg` / `match_scatter.jpg` / `rally_heatmap.jpg` / `rally_scatter.jpg`：运行中更新的整场和当前回合图表；`live_summary.json` 为对应统计快照。
- `*_index.json`：已经关闭的可用分片及其会话时间范围。浏览器只提供已封存分片，强杀时最后一个未封存 MP4 可能无法播放。
- `rallies.json`：人工回合边界；`session_summary.json`：结束状态与统计；`heatmap_*.jpg`：两侧球员位置热力图。

每次会话保存标定版本，旧结果不受后续重新标定影响。输入只保留最新待分析帧，允许跳帧并报告数量。录制在取流线程内编码，主机性能不足时仍可能影响摄像头读取速度，应以现场长时间基准判断，不宣称所有硬件都能连续无损录制。

断流会退避重连，超过约 60 秒未恢复则失败。工作进程心跳超过 120 秒无响应会被终止；主动停止 20 秒仍未结束会强制终止。服务重启将未完成会话标记中断，保留已封存文件。默认单场最长 120 分钟、磁盘至少保留 2GB，可在设置中调整；不会自动删除历史录像，需人工管理存储。本版尚未提供完整按日期自动清理策略。

直播和原有离线分析共享一个计算槽；正在离线分析时直播启动会被拒绝，直播期间离线任务继续排队。停止离线任务仍沿用原有任务接口。

## 验证

```powershell
.venv/Scripts/python.exe -m pip install pytest httpx
.venv/Scripts/python.exe -m pytest tests -q
Set-Location web/frontend
npm run build
```

自动测试覆盖密码脱敏、源地址限制、标定几何/版本、时间戳运动统计、单槽取帧、录像时间线、进程启停、GPU 排他、崩溃/重启状态和产物访问。真正的球场安装仍需按实施计划完成实拍质量、实际帧率、断网恢复及至少两小时稳定性验收。本次抓图连接成功不能替代现场识别准确率验收。

## 当前开发机验证记录（2026-09-13）

- RTX 3050 Laptop 4GB，PyTorch `2.5.1+cu124`，CUDA 可用。两份模型已按原始 Release SHA-256 校验。
- 实际 RTSP 抓图：2560×1440，设备报告 25 FPS。25 秒桌面场景双模型基准处理 360 帧，约 14.39 FPS；不含录像/叠加开销，不代表球场准确率或完整直播帧率。
- 仓库示例视频按实时节奏输入双模型管线，正常结束，产生递增时间戳、两侧球员观测、球检测记录、热力图和可播放录像分片。羽毛球接受帧数属于程序输出，未经人工标注，不能当作准确率。
- 后端测试增加运行中图表、回合重置、检测快照、跨断流导出拒绝、导出/删除互斥，以及带音轨标注片段的画面与时长验证。前端 TypeScript/Vite 构建通过。
- 实际 RTSP 音视频录制 20 秒以上，检测到摄像头音轨，3 秒带声音片段导出成功。该验证使用桌面摄像头画面，不代表球场识别验收。
- 本轮共 26 项后端测试通过；RTMPose 和 RTMO 各三个档位均在实际 GPU 上加载、推理成功。
- 隔离的示例视频直播联调通过：真实检测模型、图表版本更新、人工回合重置、HLS 播放、运行中标注片段导出、检测快照与停止保存。导出期间继续分析 35 帧；1440×1000 和 390×844 无页面横向溢出或脚本错误。测试使用独立配置与数据目录，没有把示例球场角点写入摄像头配置。
- 原有录像上传流程使用示例视频裁剪 3 秒，完成四点标定、GPU 分析并成功下载标注视频，回归通过。
- 尚未执行球场现场精度验收、物理断网测试、两小时连续运行和自动开机启动安装。
