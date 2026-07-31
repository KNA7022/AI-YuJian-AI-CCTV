import { JobEvent } from "../types";
import { formatStageLabel } from "../copy";

interface StatusTimelineProps {
  events: JobEvent[];
  status: string;
  statusKey: string;
}

export function StatusTimeline({ events, status, statusKey }: StatusTimelineProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>实时进度</h2>
        <span className={`status-pill ${statusKey}`}>{status}</span>
      </div>
      <div className="timeline">
        {events.length === 0 ? (
          <div className="empty-state">等待任务状态更新...</div>
        ) : (
          events.map((event, index) => (
            <article key={`${event.timestamp ?? "event"}-${index}`} className="timeline-item">
              <span className="timeline-dot" />
              <div>
                <strong>{formatStageLabel(event.stage ?? event.status ?? event.type)}</strong>
                <p>{event.message ?? "暂无说明"}</p>
                {typeof event.progress === "number" && (
                  <div className="progress-row">
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${event.progress}%` }} />
                    </div>
                    <span>{event.progress}%</span>
                  </div>
                )}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
