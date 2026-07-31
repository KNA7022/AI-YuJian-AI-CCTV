import { JobRecord } from "../types";
import { artifactLabels } from "../copy";

interface ArtifactListProps {
  job: JobRecord;
}

export function ArtifactList({ job }: ArtifactListProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>产物下载</h2>
      </div>
      <div className="artifact-list">
        {job.artifacts && job.artifacts.length > 0 ? (
          job.artifacts.map((artifact) => (
            <a key={artifact.type} className="artifact-item" href={`/api/jobs/${job.id}/artifacts/${artifact.type}?download=true`} target="_blank" rel="noreferrer">
              <strong>{artifactLabels[artifact.type] ?? artifact.type}</strong>
              <span>{artifact.mime_type}</span>
            </a>
          ))
        ) : (
          <div className="empty-state">任务完成后，这里会出现可下载产物。</div>
        )}
      </div>
    </section>
  );
}
