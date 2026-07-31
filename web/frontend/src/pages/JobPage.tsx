import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { cancelJob, fetchJob, subscribeJob } from "../api";
import { statusLabels } from "../copy";
import { ArtifactList } from "../components/ArtifactList";
import { StatCards } from "../components/StatCards";
import { StatusTimeline } from "../components/StatusTimeline";
import { JobEvent, JobRecord } from "../types";

export function JobPage() {
  const { jobId = "" } = useParams();
  const [job, setJob] = useState<JobRecord | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    let active = true;
    fetchJob(jobId)
      .then((nextJob) => {
        if (active) {
          setJob(nextJob);
        }
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "加载任务失败"));

    const source = subscribeJob(jobId, (event) => {
      setEvents((current) => [...current, event]);
      fetchJob(jobId).then((nextJob) => setJob(nextJob)).catch(() => undefined);
    });
    source.onerror = () => {
      source.close();
    };
    return () => {
      active = false;
      source.close();
    };
  }, [jobId]);

  async function handleCancel() {
    try {
      await cancelJob(jobId);
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "取消任务失败");
    }
  }

  const annotatedVideoUrl = useMemo(() => {
    if (!job?.artifacts) {
      return null;
    }
    const artifact = job.artifacts.find((item) => item.type === "annotated_video");
    const cacheKey = encodeURIComponent(job.updated_at ?? job.finished_at ?? job.id);
    return artifact ? `/api/jobs/${job.id}/artifacts/${artifact.type}?v=${cacheKey}` : null;
  }, [job]);

  const cacheKey = encodeURIComponent(job?.updated_at ?? job?.finished_at ?? job?.id ?? "");
  const heatmapUrl = job?.summary?.artifacts.match_heatmap
    ? `/api/jobs/${job.id}/artifacts/match_heatmap?v=${cacheKey}`
    : null;
  const scatterUrl = job?.summary?.artifacts.match_scatter
    ? `/api/jobs/${job.id}/artifacts/match_scatter?v=${cacheKey}`
    : null;

  useEffect(() => {
    setVideoError(null);
    if (!annotatedVideoUrl || !videoRef.current) {
      return;
    }
    videoRef.current.load();
  }, [annotatedVideoUrl]);

  if (!job) {
    return <div className="panel loading-panel">正在加载任务...</div>;
  }

  return (
    <div className="result-layout">
      <div className="result-main">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>{job.name}</h2>
              <p className="muted">{job.status === "failed" ? job.error_message : "分析进行中时，这里会自动刷新复盘结果。"}</p>
            </div>
            {(job.status === "queued" || job.status === "running") && (
              <button type="button" className="ghost-button" onClick={handleCancel}>
                取消任务
              </button>
            )}
          </div>
          <StatCards summary={job.summary} />
          {annotatedVideoUrl ? (
            <>
              <video
                ref={videoRef}
                className="video-panel"
                controls
                preload="auto"
                src={annotatedVideoUrl}
                onLoadedMetadata={(event) => {
                  const video = event.currentTarget;
                  if (Number.isFinite(video.duration) && video.duration > 1 && video.currentTime < 0.1) {
                    video.currentTime = Math.min(1, video.duration / 2);
                  }
                }}
                onCanPlay={() => setVideoError(null)}
                onError={() => setVideoError("标注视频暂时无法在浏览器内预览，可以先从右侧产物列表下载查看。")}
              />
              {videoError && <div className="error-banner media-error">{videoError}</div>}
            </>
          ) : (
            <div className="video-skeleton">分析完成后，标注视频会显示在这里。</div>
          )}
        </section>

        <div className="chart-grid">
          <section className="panel chart-panel">
            <div className="panel-header">
              <h2>热力图</h2>
            </div>
            {heatmapUrl ? <img src={heatmapUrl} alt="比赛热力图" className="chart-image" /> : <div className="video-skeleton">等待热力图生成...</div>}
          </section>
          <section className="panel chart-panel">
            <div className="panel-header">
              <h2>散点图</h2>
            </div>
            {scatterUrl ? <img src={scatterUrl} alt="比赛散点图" className="chart-image" /> : <div className="video-skeleton">等待散点图生成...</div>}
          </section>
        </div>
      </div>

      <div className="result-side">
        <StatusTimeline events={events} status={statusLabels[job.status] ?? job.status} statusKey={job.status} />
        <ArtifactList job={job} />
        {error && <div className="error-banner">{error}</div>}
      </div>
    </div>
  );
}
