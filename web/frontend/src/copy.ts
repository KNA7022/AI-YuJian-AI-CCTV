import { JobStatus } from "./types";

export const statusLabels: Record<JobStatus, string> = {
  draft: "待配置",
  calibrating: "待标定",
  queued: "排队中",
  running: "分析中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export const artifactLabels: Record<string, string> = {
  annotated_video: "标注视频",
  detections: "检测数据",
  metadata: "任务元数据",
  match_heatmap: "整场热力图",
  match_scatter: "整场散点图",
  summary: "结果摘要",
};

export function formatStageLabel(value?: string): string {
  if (!value) {
    return "状态更新";
  }
  const labels: Record<string, string> = {
    initializing: "初始化",
    loading_template: "加载模板帧",
    loading_calibration: "加载标定",
    processing: "视频分析中",
    summarizing: "整理结果",
    completed: "分析完成",
    connected: "已连接",
    status: "状态更新",
    progress: "进度更新",
  };
  return labels[value] ?? value;
}
