import { FormEvent, useEffect, useState } from "react";
import { CalibrationCanvas } from "../components/CalibrationCanvas";
import { LiveMediaPlayer } from "../components/LiveMediaPlayer";

interface Court {
  name: string;
  rtsp_url: string;
  username: string;
  has_password?: boolean;
  pose_model: string;
  ball_model: string;
  ball_enabled: boolean;
  device: string;
  analysis_fps: number;
  record_video: boolean;
  record_fps: number;
  max_duration_minutes: number;
  min_free_gb: number;
  language: "zh" | "en";
  pose_family: string;
  pose_mode: string;
  keep_audio: boolean;
  visualize_positions: boolean;
  auto_rallies: boolean;
  show_skeletons: boolean;
  show_player_trajectories: boolean;
  show_court_trajectory: boolean;
  show_shuttlecock_trajectory: boolean;
  show_player_stats: boolean;
  snapshot?: { id: string; width: number; height: number; fps: number } | null;
  calibration?: { version: string; corners: number[][] } | null;
}
interface Session {
  id: string;
  name: string;
  status: string;
  message: string;
  created_at: string;
  elapsed_sec?: number;
  inference_fps?: number;
  source_fps?: number;
  frame_age_sec?: number;
  skipped_frames?: number;
  processed_frames?: number;
  rallies?: { time_sec: number }[];
  stats: Record<string, { distance_m: number; speed_mps: number; max_speed_mps: number; avg_speed_mps: number;
    rally_distance?: number; rally_avg_speed?: number; rally_max_speed?: number }>;
  chart_revision?: number;
  visualize_positions?: boolean;
  rally?: { count: number; active: boolean; mode: string };
  media?: { ready: boolean; has_audio: boolean; keep_audio: boolean; duration_sec: number; archive: boolean; running: boolean; annotated_ranges?: { start_sec: number; end_sec: number }[] };
}
interface Health { errors: string[]; active_session_id: string | null; disk_free_gb: number }
interface Artifact { name: string; size: number; url: string }
const defaults: Court = {
  name: "羽毛球场 1", rtsp_url: "rtsp://192.168.0.15/live/chn=0", username: "admin",
  pose_model: "weights/yolo11n-pose.pt", ball_model: "weights/yolo11s-ball.pt", ball_enabled: false,
  device: "auto", analysis_fps: 10, record_video: true, record_fps: 25, max_duration_minutes: 120, min_free_gb: 2,
  language: "zh", pose_family: "yolo-pose", pose_mode: "balanced", keep_audio: true, visualize_positions: true,
  auto_rallies: true, show_skeletons: true, show_player_trajectories: true, show_court_trajectory: true,
  show_shuttlecock_trajectory: true, show_player_stats: true,
};
const activeStatuses = ["preparing", "running", "reconnecting", "stopping"];
const statusNames: Record<string, string> = {
  preparing: "正在准备", running: "正在识别", reconnecting: "断线重连", stopping: "正在封存",
  stopped: "已停止", failed: "失败", interrupted: "已中断",
};
async function api<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/live${path}`, {
    method, signal, headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "请求失败，请检查配置。");
  return data as T;
}

export function LivePage() {
  const [court, setCourt] = useState<Court>(defaults);
  const [password, setPassword] = useState("");
  const [corners, setCorners] = useState<number[][]>([]);
  const [loaded, setLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [files, setFiles] = useState<Artifact[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [notice, setNotice] = useState("");
  const [chartScope, setChartScope] = useState("match");
  const [clipStart, setClipStart] = useState(0);
  const [clipEnd, setClipEnd] = useState(10);
  const [clipKind, setClipKind] = useState("annotated");
  const active = sessions.find(item => activeStatuses.includes(item.status));
  const session = sessions.find(item => item.id === selected) ?? active ?? sessions[0];

  useEffect(() => {
    const controller = new AbortController();
    api<Court | null>("/court", "GET", undefined, controller.signal).then(value => {
      if (value) { setCourt(value); setCorners(value.calibration?.corners ?? []); }
      setLoaded(true);
    }).catch(err => { if (!controller.signal.aborted) setError(String(err.message)); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const [nextHealth, nextSessions] = await Promise.all([
          api<Health>("/health", "GET", undefined, controller.signal),
          api<Session[]>("/sessions", "GET", undefined, controller.signal),
        ]);
        setHealth(nextHealth); setSessions(nextSessions); setConnectionError("");
      } catch (err) {
        if (!controller.signal.aborted) setConnectionError(err instanceof Error ? err.message : "服务连接失败");
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 2000);
      }
    }
    void refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  const sessionId = session?.id;
  const sessionStatus = session?.status;
  useEffect(() => {
    const controller = new AbortController();
    setFiles([]);
    let timer: ReturnType<typeof setTimeout>;
    async function refreshFiles() {
      if (!sessionId) return;
      try { setFiles(await api<Artifact[]>(`/sessions/${sessionId}/artifacts`, "GET", undefined, controller.signal)); }
      catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "产物加载失败"); }
      finally { if (!controller.signal.aborted) timer = setTimeout(refreshFiles, 3000); }
    }
    void refreshFiles();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [sessionId, sessionStatus]);

  function edit<K extends keyof Court>(key: K, value: Court[K]) {
    setCourt(previous => ({ ...previous, [key]: value })); setDirty(true); setNotice("");
  }
  async function action(label: string, work: () => Promise<void>) {
    setBusy(label); setError(""); setNotice("");
    try { await work(); } catch (err) { setError(err instanceof Error ? err.message : "操作失败"); }
    finally { setBusy(""); }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    await action("保存", async () => {
      const value = await api<Court>("/court", "PUT", { ...court, password: password || undefined });
      setCourt(value); setPassword(""); setCorners(value.calibration?.corners ?? []); setDirty(false);
      setNotice("配置已保存。密码保存在本机，不会回传到页面。");
    });
  }
  const disabled = !loaded || Boolean(busy) || Boolean(active) || Boolean(connectionError);

  return <div className="live-page">
    <div className="live-heading">
      <div><span className="section-kicker">COURT · LIVE</span><h1>球场实时分析</h1>
        <p className="muted">固定机位 · 单打双人 · 本地处理与保存</p></div>
      <span className="live-status">{active ? statusNames[active.status] : "待机"}</span>
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {connectionError && <div className="error-banner" role="alert">连接服务失败：{connectionError}</div>}
    {notice && <div className="live-notice" role="status">{notice}</div>}
    <div className="live-columns">
      <section className="panel form-panel">
        <div className="panel-header"><h2>1. 摄像头与模型</h2></div>
        <form onSubmit={save}>
          <fieldset disabled={disabled} className="live-fieldset">
            <label className="field"><span>球场名称</span><input required maxLength={80} value={court.name} onChange={e => edit("name", e.target.value)} /></label>
            <label className="field"><span>RTSP 地址（不含账号密码）</span><input required value={court.rtsp_url} onChange={e => edit("rtsp_url", e.target.value)} /></label>
            <div className="live-input-pair">
              <label className="field"><span>账号</span><input autoComplete="username" value={court.username} onChange={e => edit("username", e.target.value)} /></label>
              <label className="field"><span>密码{court.has_password ? "（留空保留）" : ""}</span><input type="password" autoComplete="new-password" value={password} onChange={e => { setPassword(e.target.value); setDirty(true); }} /></label>
            </div>
            <details className="live-settings"><summary>识别与存储设置</summary>
              <label className="field"><span>统计与图表语言</span><select value={court.language} onChange={e => edit("language", e.target.value as "zh" | "en")}><option value="zh">中文</option><option value="en">English</option></select></label>
              <label className="field"><span>姿态模型</span><select value={court.pose_family} onChange={e => edit("pose_family", e.target.value)}><option value="yolo-pose">YOLO Pose</option><option value="rtmpose">RTMPose</option><option value="rtmo">RTMO</option></select></label>
              <label className="field"><span>模型档位（RTMPose / RTMO）</span><select value={court.pose_mode} disabled={court.pose_family === "yolo-pose"} onChange={e => edit("pose_mode", e.target.value)}><option value="lightweight">轻量</option><option value="balanced">均衡</option><option value="performance">高精度</option></select></label>
              <label className="field"><span>姿态模型路径</span><input value={court.pose_model} onChange={e => edit("pose_model", e.target.value)} /></label>
              <label className="field"><span>运算设备</span><select value={court.device} onChange={e => edit("device", e.target.value)}><option value="auto">自动选择 GPU / CPU</option><option value="cuda:0">NVIDIA GPU</option><option value="cpu">CPU</option></select></label>
              <label className="field"><span>分析帧率上限（FPS）</span><input type="number" min={1} max={30} required value={court.analysis_fps} onChange={e => edit("analysis_fps", Number(e.target.value))} /></label>
              <label className="live-check"><input type="checkbox" checked={court.ball_enabled} onChange={e => edit("ball_enabled", e.target.checked)} />启用羽毛球检测（需要专用权重）</label>
              <label className="field"><span>羽毛球模型路径</span><input value={court.ball_model} onChange={e => edit("ball_model", e.target.value)} /></label>
              <label className="live-check"><input type="checkbox" checked={court.record_video} onChange={e => edit("record_video", e.target.checked)} />保存原画面与标注录像</label>
              <label className="live-check"><input type="checkbox" checked={court.keep_audio} onChange={e => edit("keep_audio", e.target.checked)} />保留摄像头音频并允许直播回听</label>
              <label className="live-check"><input type="checkbox" checked={court.visualize_positions} onChange={e => edit("visualize_positions", e.target.checked)} />实时生成热力图和散点图</label>
              <label className="live-check"><input type="checkbox" checked={court.auto_rallies} onChange={e => edit("auto_rallies", e.target.checked)} />自动估计回合（需要羽毛球检测）</label>
              {([["show_skeletons", "人体骨架"], ["show_player_trajectories", "球员轨迹"], ["show_court_trajectory", "小球场坐标与轨迹"], ["show_shuttlecock_trajectory", "羽毛球轨迹"], ["show_player_stats", "实时统计面板"]] as const).map(([key, label]) =>
                <label className="live-check" key={key}><input type="checkbox" checked={court[key]} onChange={e => edit(key, e.target.checked)} />{label}</label>)}
              <label className="field"><span>原画面录像帧率</span><input type="number" min={1} max={60} required value={court.record_fps} onChange={e => edit("record_fps", Number(e.target.value))} /></label>
              <label className="field"><span>单场最长分钟数</span><input type="number" min={1} max={480} required value={court.max_duration_minutes} onChange={e => edit("max_duration_minutes", Number(e.target.value))} /></label>
              <label className="field"><span>磁盘保留空间（GB）</span><input type="number" min={0.5} max={100} step={0.5} required value={court.min_free_gb} onChange={e => edit("min_free_gb", Number(e.target.value))} /></label>
            </details>
            <button className="primary-button" type="submit">{busy === "保存" ? "保存中…" : "保存配置"}</button>
          </fieldset>
        </form>
        {dirty && <p className="muted">配置已修改，请先保存再抓图或开始分析。</p>}
        <p className="muted">可用磁盘：{health?.disk_free_gb ?? "—"} GB。多人同侧时暂停相关统计；双打尚未支持。</p>
      </section>

      <section className="panel form-panel">
        <div className="panel-header"><h2>2. 球场标定</h2><span className="muted">{court.calibration ? "已保存标定" : "待标定"}</span></div>
        <div className="button-row">
          <button className="ghost-button" disabled={disabled || dirty} onClick={() => void action("抓图", async () => {
            const value = await api<Court>("/court/snapshot", "POST"); setCourt(value); setCorners([]);
            setNotice("抓图成功，请在实际球场画面上标记四个角点。");
          })}>{busy === "抓图" ? "正在连接摄像头…" : "连接并抓取画面"}</button>
          <button className="ghost-button" disabled={disabled || !court.snapshot} onClick={() => setCorners([])}>重置角点</button>
        </div>
        {court.snapshot ? <>
          <p className="muted">{court.snapshot.width} × {court.snapshot.height} · 设备报告 {court.snapshot.fps.toFixed(1)} FPS</p>
          <div className={active ? "live-calibration-locked" : ""}>
            <CalibrationCanvas key={court.snapshot.id} imageUrl={`/api/live/court/snapshot.jpg?v=${court.snapshot.id}`} corners={corners} onChange={setCorners} />
          </div>
          <button className="primary-button" disabled={disabled || dirty || corners.length !== 4} onClick={() => void action("标定", async () => {
            const value = await api<Court>("/court/calibration", "PUT", { snapshot_id: court.snapshot!.id, corners });
            setCourt(value); setNotice("标定已保存，后续会话将自动复用。");
          })}>保存四点标定</button>
        </> : <div className="empty-state">保存摄像头配置后抓取参考画面。安装到球场、调整机位后需要重新标定。</div>}
      </section>
    </div>

    <section className="panel form-panel">
      <div className="panel-header"><h2>3. 分析会话</h2><div className="button-row">
        <button className="primary-button" disabled={disabled || dirty || !health || health.errors.length > 0} onClick={() => void action("启动", async () => {
          const value = await api<Session>("/sessions", "POST"); setSessions(previous => [value, ...previous]); setSelected(value.id);
        })}>开始分析</button>
        <button className="ghost-button" disabled={!active || Boolean(busy) || active.status === "stopping"} onClick={() => void action("停止", async () => {
          const value = await api<Session>(`/sessions/${active!.id}/stop`, "POST"); setSessions(previous => previous.map(item => item.id === value.id ? value : item));
        })}>{active?.status === "stopping" ? "正在封存…" : "停止并保存"}</button>
        <button className="ghost-button" disabled={!active || active.status !== "running" || Boolean(busy)} onClick={() => void action("回合", async () => {
          const value = await api<Session>(`/sessions/${active!.id}/rallies`, "POST"); setSessions(previous => previous.map(item => item.id === value.id ? value : item));
          setNotice("已标记一个回合边界。");
        })}>标记回合边界</button>
      </div></div>
      {!active && health && health.errors.length > 0 && <div className="live-notice">开始前需要：{health.errors.join("；")}</div>}
      <div className="live-columns">
        <div className="live-preview">
          {active?.status === "running" ? <img src={`/api/live/sessions/${active.id}/preview`} alt="实时识别画面" /> : <div className="empty-state">{active ? active.message : "分析开始后，这里显示实时识别画面。"}</div>}
        </div>
        <div>
          {session ? <>
            <h3>{session.name} · {statusNames[session.status] ?? session.status}</h3>
            <p role="status">{session.message}</p>
            <dl className="live-metrics">
              <div><dt>运行时长</dt><dd>{Math.floor((session.elapsed_sec ?? 0) / 60)} 分 {Math.floor((session.elapsed_sec ?? 0) % 60)} 秒</dd></div>
              <div><dt>实际分析速度</dt><dd>{session.inference_fps ?? "—"} FPS</dd></div>
              <div><dt>本机取帧至识别耗时</dt><dd>{session.frame_age_sec ?? "—"} 秒</dd></div>
              <div><dt>已分析 / 跳过帧</dt><dd>{session.processed_frames ?? 0} / {session.skipped_frames ?? 0}</dd></div>
              <div><dt>人工回合边界</dt><dd>{session.rallies?.length ?? 0}</dd></div>
              <div><dt>回合{session.rally?.mode === "automatic_estimate" ? "（自动估计）" : ""}</dt><dd>{session.rally?.count ?? 0} · {session.rally?.active ? "进行中" : "间歇"}</dd></div>
            </dl>
            <div className="live-stat-table"><table><thead><tr><th>球员</th><th>总距离</th><th>当前 / 平均 / 最高速度</th><th>当前回合距离 / 均速 / 最高速度</th></tr></thead><tbody>
              {Object.entries(session.stats ?? {}).map(([side, v]) => <tr key={side}><td>{side === "upper" ? "远场" : "近场"}</td><td>{v.distance_m.toFixed(1)} m</td><td>{v.speed_mps.toFixed(1)} / {(v.avg_speed_mps ?? 0).toFixed(1)} / {v.max_speed_mps.toFixed(1)} m/s</td><td>{(v.rally_distance ?? 0).toFixed(1)} m / {(v.rally_avg_speed ?? 0).toFixed(1)} / {(v.rally_max_speed ?? 0).toFixed(1)} m/s</td></tr>)}
            </tbody></table></div>
            <p className="muted">速度、距离和自动回合均为视觉估计；漏球或遮挡可能影响分段，可用“标记回合边界”纠正。</p>
          </> : <p className="muted">尚无分析会话。</p>}
        </div>
      </div>
    </section>

    {session && session.visualize_positions && <section className="panel form-panel">
      <div className="panel-header"><h2>实时热力图与散点图</h2><select aria-label="图表统计范围" value={chartScope} onChange={e => setChartScope(e.target.value)}><option value="match">整场</option><option value="rally">当前回合</option></select></div>
      <p className="muted">随检测约每 2 秒刷新，分布基于有效位置观测；完整逐帧位置同时保存。</p>
      {session.chart_revision || !activeStatuses.includes(session.status) ? <div className="live-chart-grid">
        {["heatmap", "scatter"].map(kind => <img key={`${session.id}-${chartScope}-${kind}`} src={`/api/live/sessions/${session.id}/images/${chartScope}_${kind}.jpg?v=${session.chart_revision ?? session.status}`} alt={kind === "heatmap" ? "实时球员热力图" : "实时球员散点图"} />)}
      </div> : <p>正在生成首批图表…</p>}
    </section>}

    {session?.media && <section className="panel form-panel">
      <div className="panel-header"><h2>原始音视频与直播片段</h2></div>
      <p className="muted">{session.media.has_audio ? "已检测到摄像头音频，可在播放器中开启声音。" : session.media.keep_audio ? "当前未检测到摄像头音轨；视频与实时分析继续运行。" : "已关闭音频保留。"} 原始音视频采用分片缓冲，与上方识别预览可能有延迟差。</p>
      {session.media.ready ? <LiveMediaPlayer sessionId={session.id} /> : <p>正在等待音视频分片…</p>}
      <label className="field"><span>导出内容</span><select value={clipKind} onChange={e => setClipKind(e.target.value)}><option value="annotated">识别标注视频（有音轨时近似对齐）</option><option value="original">原始音视频</option></select></label>
      <div className="live-input-pair">
        <label className="field"><span>片段开始（秒）</span><input type="number" min={0} step={.1} value={clipStart} onChange={e => setClipStart(Number(e.target.value))} /></label>
        <label className="field"><span>片段结束（秒）</span><input type="number" min={0} step={.1} value={clipEnd} onChange={e => setClipEnd(Number(e.target.value))} /></label>
      </div>
      <p className="muted">已接收 {session.media.duration_sec.toFixed(1)} 秒；单次导出最多 10 分钟，不中断正在运行的识别。</p>
      {clipKind === "annotated" && <p className="muted">标注视频使用会话时间，约每 10 秒封存。可用范围：{session.media.annotated_ranges?.map(range => `${range.start_sec.toFixed(1)}–${range.end_sec.toFixed(1)} 秒`).join("、") || "等待首个分片"}。原始视频使用播放器时间。</p>}
      <button className="ghost-button" disabled={Boolean(busy) || !session.media.archive || (clipKind === "original" ? !session.media.ready : !session.media.annotated_ranges?.length)} onClick={() => void action("片段", async () => {
        await api(`/sessions/${session.id}/clips`, "POST", { start_sec: clipStart, end_sec: clipEnd, kind: clipKind }); setNotice("片段已加入导出，完成后出现在下方结果列表。");
      })}>导出已接收片段</button>
    </section>}

    <section className="panel form-panel">
      <div className="panel-header"><h2>会话历史与结果</h2></div>
      <div className="live-input-pair">
        <label className="field"><span>选择会话</span><select value={session?.id ?? ""} onChange={e => setSelected(e.target.value)}>
          {!sessions.length && <option value="">暂无记录</option>}
          {sessions.map(item => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString()} · {statusNames[item.status]} · {item.name}</option>)}
        </select></label>
        <p className="muted">直播中可查看和下载已生成的图表与封存分片；停止后可下载完整 JSONL。原始音视频与片段导出保留摄像头提供的音轨。</p>
      </div>
      <div className="live-artifacts">{files.map(file => <a className="ghost-button" key={file.name} href={file.url} download>{file.name} · {(file.size / 1024).toFixed(0)} KB</a>)}</div>
      {session && <div className="button-row">
        {(session.processed_frames ?? 0) > 0 && <a className="ghost-button" href={`/api/live/sessions/${session.id}/detections`} download>下载当前检测数据快照</a>}
        <button className="ghost-button" disabled={Boolean(busy) || activeStatuses.includes(session.status)} onClick={() => {
          if (window.confirm("删除这次会话及本地录像、图表和检测数据？")) void action("删除", async () => {
            await api(`/sessions/${session.id}`, "DELETE"); setSessions(previous => previous.filter(item => item.id !== session.id)); setSelected(null);
          });
        }}>删除此会话</button>
      </div>}
      {session && files.length === 0 && <p className="muted">结果尚未生成或封存。</p>}
    </section>
  </div>;
}
