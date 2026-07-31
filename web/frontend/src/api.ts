import { JobConfig, JobEvent, JobRecord } from "./types";

export interface CreateJobPayload {
  file: File;
  name: string;
  config: JobConfig;
}

async function assertOk(response: Response): Promise<Response> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `Request failed with status ${response.status}`);
  }
  return response;
}

export async function createJob(payload: CreateJobPayload): Promise<{ job_id: string; status: string; video: unknown }> {
  const formData = new FormData();
  formData.set("file", payload.file);
  formData.set("name", payload.name);
  formData.set("language", payload.config.language);
  formData.set("pose_family", payload.config.pose_family);
  formData.set("pose_mode", payload.config.pose_mode);
  formData.set("yolo_pose_model", payload.config.yolo_pose_model);
  formData.set("keep_audio", String(payload.config.keep_audio));
  formData.set("visualize_positions", String(payload.config.visualize_positions));
  formData.set("ball_model_path", payload.config.ball_model_path);
  formData.set("trim_enabled", String(payload.config.trim_enabled));
  formData.set("trim_start_sec", String(payload.config.trim_start_sec ?? ""));
  formData.set("trim_end_sec", String(payload.config.trim_end_sec ?? ""));
  const response = await assertOk(await fetch("/api/jobs", { method: "POST", body: formData }));
  return response.json();
}

export async function fetchJobs(): Promise<JobRecord[]> {
  const response = await assertOk(await fetch("/api/jobs"));
  return response.json();
}

export async function fetchJob(jobId: string): Promise<JobRecord> {
  const response = await assertOk(await fetch(`/api/jobs/${jobId}`));
  return response.json();
}

export async function saveCalibration(jobId: string, frameTimeSec: number, corners: number[][]): Promise<void> {
  await assertOk(
    await fetch(`/api/jobs/${jobId}/calibration`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frame_time_sec: frameTimeSec, corners }),
    }),
  );
}

export async function startJob(jobId: string): Promise<void> {
  await assertOk(await fetch(`/api/jobs/${jobId}/start`, { method: "POST" }));
}

export async function cancelJob(jobId: string): Promise<void> {
  await assertOk(await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" }));
}

export async function deleteJob(jobId: string): Promise<void> {
  await assertOk(await fetch(`/api/jobs/${jobId}`, { method: "DELETE" }));
}

export function subscribeJob(jobId: string, onMessage: (event: JobEvent) => void): EventSource {
  const source = new EventSource(`/api/jobs/${jobId}/events`);
  source.onmessage = (event) => {
    if (!event.data) {
      return;
    }
    const payload = JSON.parse(event.data) as JobEvent;
    onMessage(payload);
  };
  return source;
}
