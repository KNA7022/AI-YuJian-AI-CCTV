"""Supervised RTSP A/V archive and bounded clip export, outside inference workers."""
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from badminton_analysis.media.binaries import ffmpeg_binary
from badminton_analysis.media.files import replace_when_ready

exports = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clip-export")


class LiveMedia:
    def __init__(self, url, directory, keep_audio=True, archive=True):
        self.url = url
        self.directory = Path(directory)
        self.keep_audio = keep_audio
        self.archive = archive
        self.process = None
        self.has_audio = False
        self.started = time.time()
        self.retries = 0

    def start(self):
        binary = ffmpeg_binary()
        if not binary:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        command = [binary, "-hide_banner", "-nostdin", "-y", "-rtsp_transport", "tcp", "-timeout", "5000000",
                   "-i", self.url, "-map", "0:v:0"]
        if self.keep_audio:
            command += ["-map", "0:a?", "-c:a", "aac", "-b:a", "96k"]
        command += ["-c:v", "copy", "-f", "hls", "-hls_time", "2", "-hls_list_size", "0" if self.archive else "6",
                    "-hls_flags", "append_list+program_date_time+temp_file+discont_start" + ("" if self.archive else "+delete_segments"),
                    "-hls_segment_filename", str(self.directory/"source_%06d.ts"), str(self.directory/"source.m3u8")]
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        threading.Thread(target=self._read_status, args=(self.process,), daemon=True).start()

    def _read_status(self, process):
        # Consume stderr so FFmpeg never blocks, but do not store private source URLs.
        for line in iter(process.stderr.readline, b""):
            if b"Audio:" in line:
                self.has_audio = self.keep_audio
        process.stderr.close()

    def poll(self):
        if self.process and self.process.poll() is not None and self.retries < 3:
            self.retries += 1
            self.start()
        manifest = self.directory/"source.m3u8"
        seconds = playlist_duration(manifest)
        return {"ready": manifest.exists() and seconds > 0, "has_audio": self.has_audio,
                "keep_audio": self.keep_audio, "duration_sec": seconds,
                "running": self.process is not None and self.process.poll() is None,
                "archive": self.archive, "annotated_ranges": annotated_ranges(self.directory)}

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(3)
        manifest = self.directory/"source.m3u8"
        if manifest.exists():
            text = manifest.read_text(encoding="utf-8")
            if "#EXT-X-ENDLIST" not in text:
                temp = manifest.with_suffix(".closed.tmp")
                temp.write_text(text+"\n#EXT-X-ENDLIST\n", encoding="utf-8")
                replace_when_ready(temp, manifest)


def playlist_duration(path):
    if not Path(path).exists():
        return 0.0
    try:
        return round(sum(float(line.split(":", 1)[1].split(",")[0])
                         for line in Path(path).read_text(encoding="utf-8").splitlines() if line.startswith("#EXTINF:")), 3)
    except (OSError, ValueError):
        return 0.0


def annotated_ranges(directory):
    try:
        return [{"start_sec": item["start_sec"], "end_sec": item["start_sec"]+item["frames"]/item["fps"],
                 "file": item["file"]} for item in json.loads((Path(directory)/"annotated_index.json").read_text(encoding="utf-8")) if item["closed"]]
    except (OSError, ValueError, KeyError):
        return []


def annotated_parts(directory, start, end):
    parts, cursor = [], start
    for item in annotated_ranges(directory):
        a, b = max(start, item["start_sec"]), min(end, item["end_sec"])
        if a >= b:
            continue
        # Frame rounding may leave one frame between adjacent segments.
        if a-cursor > 0.15:
            raise ValueError("所选时间包含未封存录像或断流空白，请选择连续的可用范围。")
        parts.append((item["file"], a-item["start_sec"], b-item["start_sec"]))
        cursor = b
    if not parts or end-cursor > 0.15:
        raise ValueError("标注录像尚未封存到所选时间，请稍后导出。")
    return parts


def export_clip(directory, clip_id, start, end, kind="original"):
    directory = Path(directory)
    state_path = directory/f"clip_{clip_id}.json"
    def save(status, message):
        payload = {"id": clip_id, "status": status, "message": message, "start_sec": start, "end_sec": end, "kind": kind}
        temp = state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        replace_when_ready(temp, state_path)
    save("running", "正在导出已接收的直播片段，实时分析继续运行。")
    target = directory/f"clip_{clip_id}.mp4"
    temporary = directory/f"clip_{clip_id}.pending.mp4"
    # Freeze the manifest. Later HLS appends must not change this export's bounds.
    manifest = directory/f"clip_{clip_id}.m3u8"
    try:
        source = directory/"source.m3u8"
        text = source.read_text(encoding="utf-8") if source.exists() else ""
        if kind == "original" and not text:
            raise ValueError("missing source archive")
        if "#EXT-X-ENDLIST" not in text:
            text += "\n#EXT-X-ENDLIST\n"
        manifest.write_text(text, encoding="utf-8")
        command = [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
                                 "-i", str(manifest), "-t", str(end-start), "-map", "0:v:0", "-map", "0:a?",
                                 "-c:v", "libx264", "-preset", "veryfast", "-threads", "2", "-c:a", "aac", "-movflags", "+faststart",
                                 str(temporary)]
        audio_added = False
        if kind == "annotated":
            parts = annotated_parts(directory, start, end)
            command = [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-y", "-filter_complex_threads", "1"]
            filters = []
            for index, (name, a, b) in enumerate(parts):
                command += ["-i", str(directory/name)]
                filters.append(f"[{index}:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{index}]")
            filters.append("".join(f"[v{i}]" for i in range(len(parts)))+f"concat=n={len(parts)}:v=1:a=0[out]")
            # The two capture paths use host time. This is approximate A/V alignment,
            # not a camera-PTS synchronization guarantee.
            from datetime import datetime
            metadata = json.loads((directory/"metadata.json").read_text(encoding="utf-8"))
            dates = [line.split(":", 1)[1] for line in text.splitlines() if line.startswith("#EXT-X-PROGRAM-DATE-TIME:")]
            if dates and metadata.get("audio"):
                offset = metadata["started_at_unix"]+start-datetime.fromisoformat(dates[0].replace("Z", "+00:00")).timestamp()
                if offset >= 0:
                    command += ["-ss", str(offset), "-i", str(manifest)]
                    audio_added = True
            command += ["-filter_complex", ";".join(filters), "-map", "[out]"]
            if audio_added:
                command += ["-map", f"{len(parts)}:a?"]
            command += ["-t", str(end-start), "-c:v", "libx264", "-preset", "veryfast", "-threads", "2", "-c:a", "aac", "-movflags", "+faststart", str(temporary)]
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode != 0 or not temporary.exists():
            raise RuntimeError("export failed")
        temporary.replace(target)
        save("completed", "原始音视频片段已导出。" if kind == "original" else "标注片段已导出" + ("，音轨按本机时间近似对齐。" if audio_added else "，该时间范围无可对齐音轨。"))
    except Exception:
        save("failed", "片段导出失败，请检查录像分片和磁盘空间。")
    finally:
        manifest.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
