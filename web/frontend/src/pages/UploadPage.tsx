import { FormEvent, PointerEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createJob } from "../api";
import { JobConfig } from "../types";

const defaultConfig: JobConfig = {
  language: "zh",
  pose_family: "yolo-pose",
  pose_mode: "balanced",
  yolo_pose_model: "yolo11n-pose.pt",
  keep_audio: true,
  visualize_positions: true,
  ball_model_path: "weights/yolo11s-ball.pt",
  trim_enabled: false,
  trim_start_sec: "",
  trim_end_sec: "",
};

function parseTimeInput(value: string | number | null): number | null {
  if (value === null || value === "") {
    return null;
  }
  const text = String(value).trim();
  if (!text) {
    return null;
  }
  if (text.includes(":")) {
    const parts = text.split(":");
    if (parts.length > 3) {
      return Number.NaN;
    }
    return parts.reduce((total, part) => total * 60 + Number(part), 0);
  }
  return Number(text);
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) {
    return "00:00";
  }
  const safeSeconds = Math.max(0, seconds);
  const wholeSeconds = Math.floor(safeSeconds);
  const hours = Math.floor(wholeSeconds / 3600);
  const minutes = Math.floor((wholeSeconds % 3600) / 60);
  const secs = wholeSeconds % 60;
  const fraction = safeSeconds - wholeSeconds;
  const secText = fraction > 0 ? `${String(secs).padStart(2, "0")}.${Math.round(fraction * 10)}` : String(secs).padStart(2, "0");
  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${secText}`;
  }
  return `${String(minutes).padStart(2, "0")}:${secText}`;
}

export function UploadPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("晚场对打复盘");
  const [config, setConfig] = useState<JobConfig>(defaultConfig);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [videoDuration, setVideoDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [draggingHandle, setDraggingHandle] = useState<"start" | "end" | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rangeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      setVideoDuration(0);
      return undefined;
    }
    const nextUrl = URL.createObjectURL(file);
    setPreviewUrl(nextUrl);
    setVideoDuration(0);
    return () => URL.revokeObjectURL(nextUrl);
  }, [file]);

  const trimStart = Math.max(0, parseTimeInput(config.trim_start_sec) ?? 0);
  const trimEnd = Math.max(trimStart + 0.1, parseTimeInput(config.trim_end_sec) ?? videoDuration);
  const selectionEnd = videoDuration > 0 ? Math.min(trimEnd, videoDuration) : trimEnd;
  const selectionStart = videoDuration > 0 ? Math.min(trimStart, Math.max(0, selectionEnd - 0.1)) : trimStart;
  const selectionPercentStart = videoDuration > 0 ? (selectionStart / videoDuration) * 100 : 0;
  const selectionPercentEnd = videoDuration > 0 ? (selectionEnd / videoDuration) * 100 : 100;

  function updateTrim(nextFields: Partial<JobConfig>) {
    setConfig((current) => ({ ...current, trim_enabled: true, ...nextFields }));
  }

  function handleFileChange(nextFile: File | null) {
    setFile(nextFile);
    setConfig((current) => ({ ...current, trim_start_sec: "", trim_end_sec: "" }));
  }

  function handleLoadedMetadata() {
    const duration = videoRef.current?.duration;
    if (duration && Number.isFinite(duration)) {
      setVideoDuration(duration);
      setConfig((current) => {
        if (!current.trim_enabled || current.trim_end_sec !== "") {
          return current;
        }
        return { ...current, trim_end_sec: Number(duration.toFixed(1)) };
      });
    }
  }

  function previewSegment() {
    if (!videoRef.current || !previewUrl) {
      return;
    }
    const start = selectionStart;
    videoRef.current.currentTime = start;
    void videoRef.current.play();
  }

  function handlePreviewTimeUpdate() {
    if (!config.trim_enabled || !videoRef.current || selectionEnd <= selectionStart) {
      return;
    }
    if (videoRef.current.currentTime >= selectionEnd) {
      videoRef.current.pause();
      videoRef.current.currentTime = selectionStart;
    }
  }

  function timeFromPointer(event: PointerEvent<HTMLElement>): number {
    const rect = rangeRef.current?.getBoundingClientRect();
    if (!rect || videoDuration <= 0) {
      return 0;
    }
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    return Number((ratio * videoDuration).toFixed(1));
  }

  function updateHandleFromPointer(event: PointerEvent<HTMLElement>, handle: "start" | "end") {
    const nextTime = timeFromPointer(event);
    if (handle === "start") {
      const cappedStart = Math.min(nextTime, Math.max(0, selectionEnd - 0.1));
      updateTrim({ trim_start_sec: cappedStart });
      if (videoRef.current) {
        videoRef.current.currentTime = cappedStart;
      }
      return;
    }
    const cappedEnd = Math.max(nextTime, selectionStart + 0.1);
    updateTrim({ trim_end_sec: cappedEnd });
    if (videoRef.current) {
      videoRef.current.currentTime = cappedEnd;
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("请先选择比赛视频。");
      return;
    }
    if (config.trim_enabled) {
      const start = parseTimeInput(config.trim_start_sec);
      const end = parseTimeInput(config.trim_end_sec);
      if (start === null && end === null) {
        setError("开启片段截取后，请填写开始时间或结束时间。");
        return;
      }
      if ((start !== null && !Number.isFinite(start)) || (end !== null && !Number.isFinite(end))) {
        setError("片段时间格式不正确，请输入秒数、mm:ss 或 hh:mm:ss。");
        return;
      }
      if ((start ?? 0) < 0 || (end !== null && end < 0)) {
        setError("片段时间不能小于 0。");
        return;
      }
      if (start !== null && end !== null && end <= start) {
        setError("结束时间必须晚于开始时间。");
        return;
      }
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await createJob({ file, name, config });
      navigate(`/jobs/${result.job_id}/calibrate`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="upload-workbench">
      <section className="intro-panel">
        <div className="intro-copy">
          <span className="section-kicker">羽毛球视频分析</span>
          <h1>比赛视频复盘</h1>
          <p>导入比赛录像，完成球场四角标定，本地引擎会生成标注视频、热力图、散点图和检测数据。</p>
          <div className="intro-status-row" aria-label="当前流程">
            <span>本机处理</span>
            <span>手动标定</span>
            <span>结果可下载</span>
          </div>
        </div>
        <div className="flow-strip" aria-label="分析流程">
          {["上传视频", "标定球场", "串行分析", "查看结果"].map((step) => (
            <span key={step}>{step}</span>
          ))}
        </div>
        <div className="court-preview" aria-hidden="true">
          <div className="court-preview-lines" />
          <div className="court-preview-net" />
          <div className="court-preview-path path-one" />
          <div className="court-preview-path path-two" />
          <div className="court-preview-player player-one" />
          <div className="court-preview-player player-two" />
        </div>
        <div className="signal-grid">
          <div>
            <span>运行方式</span>
            <strong>单机本地</strong>
          </div>
          <div>
            <span>任务模式</span>
            <strong>串行队列</strong>
          </div>
          <div>
            <span>默认模型</span>
            <strong>YOLO Pose</strong>
          </div>
        </div>
      </section>

      <form className="panel form-panel upload-form" onSubmit={handleSubmit}>
        <div className="panel-header">
          <div>
            <h2>创建分析任务</h2>
            <p className="muted form-intro">上传成功后会自动进入标定页。</p>
          </div>
        </div>
        <label className="field">
          <span>任务名称</span>
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>

        <label className="field file-field">
          <span>比赛视频</span>
          <input type="file" accept="video/*" onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)} required />
          <small>{file ? file.name : "支持 MP4、MOV、MKV、AVI、WEBM"}</small>
        </label>

        <div className="form-section-label">视频片段</div>
        <div className="clip-panel">
          <label className="clip-toggle">
            <input
              type="checkbox"
              checked={config.trim_enabled}
              onChange={(event) =>
                setConfig({
                  ...config,
                  trim_enabled: event.target.checked,
                  trim_start_sec: event.target.checked ? config.trim_start_sec || 0 : config.trim_start_sec,
                  trim_end_sec: event.target.checked ? config.trim_end_sec || (videoDuration ? Number(videoDuration.toFixed(1)) : "") : config.trim_end_sec,
                })
              }
            />
            只分析镜头固定的片段
          </label>
          <p className="muted">选择视频后可预览并拖动时间轴两端，保留镜头固定的片段。</p>
          {previewUrl ? (
            <div className="clip-preview">
              <video
                ref={videoRef}
                src={previewUrl}
                controls
                preload="metadata"
                className="clip-video"
                onLoadedMetadata={handleLoadedMetadata}
                onTimeUpdate={handlePreviewTimeUpdate}
              />
              <div className={`clip-trimmer ${videoDuration ? "" : "disabled"}`}>
                <div className="clip-time-row">
                  <strong>
                    {formatTime(selectionStart)} - {formatTime(selectionEnd)}
                  </strong>
                  <span>总时长 {videoDuration ? formatTime(videoDuration) : "读取中"}</span>
                </div>
                <div className="clip-range-shell">
                  <div className="clip-range-track" />
                  <div
                    className="clip-range-selection"
                    style={{ left: `${selectionPercentStart}%`, width: `${Math.max(0, selectionPercentEnd - selectionPercentStart)}%` }}
                  />
                  <div
                    ref={rangeRef}
                    className="clip-drag-layer"
                    onPointerMove={(event) => {
                      if (draggingHandle) {
                        updateHandleFromPointer(event, draggingHandle);
                      }
                    }}
                    onPointerUp={(event) => {
                      event.currentTarget.releasePointerCapture(event.pointerId);
                      setDraggingHandle(null);
                    }}
                    onPointerCancel={(event) => {
                      event.currentTarget.releasePointerCapture(event.pointerId);
                      setDraggingHandle(null);
                    }}
                  >
                    <button
                      type="button"
                      className={`clip-handle ${draggingHandle === "start" ? "dragging" : ""}`}
                      aria-label="拖动片段开始时间"
                      style={{ left: `${selectionPercentStart}%` }}
                      disabled={!videoDuration}
                      onPointerDown={(event) => {
                        event.currentTarget.parentElement?.setPointerCapture(event.pointerId);
                        setDraggingHandle("start");
                        updateHandleFromPointer(event, "start");
                      }}
                    />
                    <button
                      type="button"
                      className={`clip-handle ${draggingHandle === "end" ? "dragging" : ""}`}
                      aria-label="拖动片段结束时间"
                      style={{ left: `${selectionPercentEnd}%` }}
                      disabled={!videoDuration}
                      onPointerDown={(event) => {
                        event.currentTarget.parentElement?.setPointerCapture(event.pointerId);
                        setDraggingHandle("end");
                        updateHandleFromPointer(event, "end");
                      }}
                    />
                  </div>
                </div>
                <div className="clip-actions">
                  <button type="button" className="ghost-button" disabled={!videoDuration} onClick={previewSegment}>
                    播放片段
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={!videoDuration}
                    onClick={() => {
                      setConfig((current) => ({
                        ...current,
                        trim_enabled: false,
                        trim_start_sec: 0,
                        trim_end_sec: Number(videoDuration.toFixed(1)),
                      }));
                      if (videoRef.current) {
                        videoRef.current.currentTime = 0;
                      }
                    }}
                  >
                    使用全段
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="clip-empty">选择视频后，这里会显示预览播放器和可拖动截取条。</div>
          )}
          <div className="form-grid">
            <label className="field">
              <span>开始时间</span>
              <input
                placeholder="拖动后自动填写"
                value={config.trim_start_sec ?? ""}
                disabled={!previewUrl}
                onChange={(event) => updateTrim({ trim_start_sec: event.target.value })}
              />
            </label>
            <label className="field">
              <span>结束时间</span>
              <input
                placeholder="拖动后自动填写"
                value={config.trim_end_sec ?? ""}
                disabled={!previewUrl}
                onChange={(event) => updateTrim({ trim_end_sec: event.target.value })}
              />
            </label>
          </div>
        </div>

        <div className="form-section-label">分析参数</div>
        <div className="form-grid">
          <label className="field">
            <span>界面语言</span>
            <select value={config.language} onChange={(event) => setConfig({ ...config, language: event.target.value as JobConfig["language"] })}>
              <option value="zh">中文</option>
              <option value="en">英文</option>
            </select>
          </label>
          <label className="field">
            <span>姿态模型</span>
            <select value={config.pose_family} onChange={(event) => setConfig({ ...config, pose_family: event.target.value as JobConfig["pose_family"] })}>
              <option value="rtmpose">RTMPose</option>
              <option value="rtmo">RTMO</option>
              <option value="yolo-pose">YOLO Pose</option>
            </select>
          </label>
          <label className="field">
            <span>模型档位</span>
            <select value={config.pose_mode} onChange={(event) => setConfig({ ...config, pose_mode: event.target.value as JobConfig["pose_mode"] })}>
              <option value="lightweight">轻量</option>
              <option value="balanced">均衡</option>
              <option value="performance">高精度</option>
            </select>
          </label>
          <label className="field">
            <span>球模型路径</span>
            <input value={config.ball_model_path} onChange={(event) => setConfig({ ...config, ball_model_path: event.target.value })} />
          </label>
        </div>

        <div className="form-section-label">附加输出</div>
        <div className="toggle-row">
          <label>
            <input
              type="checkbox"
              checked={config.keep_audio}
              onChange={(event) => setConfig({ ...config, keep_audio: event.target.checked })}
            />
            保留原视频音频
          </label>
          <label>
            <input
              type="checkbox"
              checked={config.visualize_positions}
              onChange={(event) => setConfig({ ...config, visualize_positions: event.target.checked })}
            />
            生成热力图和散点图
          </label>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button className="primary-button primary-button-wide" disabled={submitting}>
          {submitting ? "创建中..." : "上传并继续"}
        </button>
      </form>
    </div>
  );
}
