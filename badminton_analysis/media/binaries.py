"""Resolve FFmpeg without requiring machine-wide PATH changes."""
import shutil


def ffmpeg_binary():
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None
