import type HlsType from "hls.js";
import { useEffect, useRef, useState } from "react";

export function LiveMediaPlayer({ sessionId }: { sessionId: string }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const source = `/api/live/sessions/${sessionId}/media/source.m3u8`;
    setError("");
    let cancelled = false;
    let instance: HlsType | undefined;
    void import("hls.js").then(({default: Hls}) => {
      if (cancelled) return;
      if (Hls.isSupported()) {
      const hls = new Hls({ liveSyncDurationCount: 2, maxBufferLength: 15 });
      instance = hls;
      hls.loadSource(source);
      hls.attachMedia(element);
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) setError("原始音视频暂时不可播放，请检查摄像头编码或连接；实时识别画面仍可查看。");
      });
      return;
      }
    if (element.canPlayType("application/vnd.apple.mpegurl")) element.src = source;
    else setError("当前浏览器不支持原始音视频播放。");
    }).catch(() => { if (!cancelled) setError("音视频播放器加载失败，请刷新页面。"); });
    return () => { cancelled = true; instance?.destroy(); element.removeAttribute("src"); element.load(); };
  }, [sessionId]);
  return <div><video ref={video} controls playsInline preload="metadata" className="live-source-video" aria-label="原始音视频回看" />
    {error && <p role="alert" className="muted">{error}</p>}</div>;
}
