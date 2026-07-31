import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { deleteJob, fetchJobs } from "../api";
import { statusLabels } from "../copy";
import { JobRecord } from "../types";

export function HistoryPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null);

  useEffect(() => {
    fetchJobs().then(setJobs).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : "加载历史记录失败");
    });
  }, []);

  async function handleDelete(job: JobRecord) {
    if (job.status === "running") {
      setError("分析中的任务不能删除，请先取消或等待完成。");
      return;
    }
    const confirmed = window.confirm(`确定删除「${job.name}」吗？\n\n会同时清理上传视频、标定文件和分析结果。`);
    if (!confirmed) {
      return;
    }
    setDeletingJobId(job.id);
    setError(null);
    try {
      await deleteJob(job.id);
      setJobs((current) => current.filter((item) => item.id !== job.id));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "删除历史记录失败");
    } finally {
      setDeletingJobId(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>任务历史</h2>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="history-list">
        {jobs.length === 0 ? (
          <div className="empty-state">还没有任务，先上传一场比赛开始吧。</div>
        ) : (
          jobs.map((job) => (
            <div key={job.id} className="history-item">
              <Link className="history-link" to={job.status === "draft" || job.status === "calibrating" ? `/jobs/${job.id}/calibrate` : `/jobs/${job.id}`}>
                <div>
                  <strong>{job.name}</strong>
                  <span>{job.created_at}</span>
                </div>
              </Link>
              <div className="history-actions">
                <span className={`status-pill ${job.status}`}>{statusLabels[job.status] ?? job.status}</span>
                <button
                  type="button"
                  className="delete-button"
                  disabled={job.status === "running" || deletingJobId === job.id}
                  onClick={() => handleDelete(job)}
                >
                  {deletingJobId === job.id ? "删除中" : "删除"}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
