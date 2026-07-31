import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { fetchJob, saveCalibration, startJob } from "../api";
import { CalibrationCanvas } from "../components/CalibrationCanvas";
import { JobRecord } from "../types";

export function CalibrationPage() {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobRecord | null>(null);
  const [corners, setCorners] = useState<number[][]>([]);
  const [frameTimeSec, setFrameTimeSec] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJob(jobId)
      .then((nextJob) => {
        setJob(nextJob);
        setCorners(nextJob.calibration_points ?? []);
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "加载任务失败"));
  }, [jobId]);

  const imageUrl = useMemo(() => {
    if (!job) {
      return "";
    }
    const cacheBust = job.updated_at ?? Date.now();
    const templatePath = job.template_frame_path;
    if (!templatePath) {
      return "";
    }
    const marker = "/storage/";
    const markerIndex = templatePath.indexOf(marker);
    if (markerIndex >= 0) {
      return `${templatePath.slice(markerIndex)}?cacheBust=${cacheBust}`;
    }
    return `/storage/jobs/${job.id}/template_frame.jpg?cacheBust=${cacheBust}`;
  }, [job]);

  async function handleSaveAndStart() {
    if (corners.length !== 4) {
      setError("请先标出四个球场角点。");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await saveCalibration(jobId, frameTimeSec, corners);
      await startJob(jobId);
      navigate(`/jobs/${jobId}`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存标定失败");
    } finally {
      setSaving(false);
    }
  }

  if (!job) {
    return <div className="panel loading-panel">正在加载标定工作区...</div>;
  }

  return (
    <div className="page-grid two-column">
      <section className="panel form-panel">
        <div className="panel-header">
          <h2>标定球场区域</h2>
        </div>
        <p className="muted">
          选择参考帧时间，按顺序点击球场四个角点，在分析开始前固定球场几何区域。
        </p>
        <label className="field">
          <span>参考帧时间（秒）</span>
          <input type="number" min={0} step={0.1} value={frameTimeSec} onChange={(event) => setFrameTimeSec(Number(event.target.value))} />
        </label>
        <div className="corner-list">
          {["左上", "右上", "右下", "左下"].map((label, index) => (
            <div className="corner-item" key={label}>
              <strong>{label}</strong>
              <span>{corners[index] ? `${corners[index][0]}, ${corners[index][1]}` : "待标记"}</span>
            </div>
          ))}
        </div>
        <div className="button-row">
          <button type="button" className="ghost-button" onClick={() => setCorners([])}>
            重置角点
          </button>
          <button type="button" className="primary-button" disabled={saving} onClick={handleSaveAndStart}>
            {saving ? "保存中..." : "保存并开始分析"}
          </button>
        </div>
        {error && <div className="error-banner">{error}</div>}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>标定画面</h2>
        </div>
        {imageUrl ? (
          <CalibrationCanvas imageUrl={imageUrl} corners={corners} onChange={setCorners} />
        ) : (
          <div className="empty-state">模板帧会显示在这里。</div>
        )}
      </section>
    </div>
  );
}
