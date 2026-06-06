"""
Video I/O helpers.
"""
import subprocess
from pathlib import Path
import cv2


def get_video_meta(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    meta = {
        "fps":    cap.get(cv2.CAP_PROP_FPS) or 25.0,
        "width":  int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    return meta

def reencode_h264(src: str, dst: str) -> bool:
    """
    Re-encode video with FFmpeg to H.264/AAC in a browser-friendly container.
    Returns True on success, False if FFmpeg is unavailable (caller falls back).
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", src,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p", 
                "-movflags", "+faststart",
                "-an",          # no audio
                dst,
            ],
            capture_output=True,
            timeout=300,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def raw_video_writer(path: str, fps: float, width: int, height: int):
    """Return an OpenCV VideoWriter writing mp4v to *path*."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(path, fourcc, fps, (width, height))
