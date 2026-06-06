"""
VideoProcessor — orchestrates the full pipeline for one session.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import AsyncGenerator

import cv2
import numpy as np

from backend.config import UPLOAD_DIR, OUTPUT_DIR, OFFSIDE_VERDICT_THRESHOLD
from backend.services.detector import (
    detect_persons,
    detect_and_classify,
    detect_ball,
    reset_trackers,
)
from backend.services.team_classifier import analyse_best_frame
from backend.services.offside_logic import run_offside_logic
from backend.services.annotator import annotate_frame
from backend.utils.video import get_video_meta, raw_video_writer, reencode_h264
from backend.utils.colours import rgb_to_hex

logger = logging.getLogger(__name__)

# ── In-process session store ──────────────────────────────────────────────────

_sessions: dict[str, dict] = {}


def create_session() -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "status":              "created",
        "video_path":          None,
        "output_path":         None,
        "cluster_info":        None,
        "attacking_team":      None,
        "attacking_direction": None,
        "final_verdict":       None,
        "final_confidence":    None,
    }
    return sid


def get_session(sid: str) -> dict:
    if sid not in _sessions:
        raise KeyError(f"Unknown session: {sid}")
    return _sessions[sid]


def save_upload(sid: str, file_bytes: bytes, filename: str) -> Path:
    ext  = Path(filename).suffix or ".mp4"
    dest = UPLOAD_DIR / f"{sid}{ext}"
    dest.write_bytes(file_bytes)
    s = get_session(sid)
    s["video_path"] = str(dest)
    s["status"]     = "uploaded"
    return dest


# ── Phase 1: scan best frame + KMeans ────────────────────────────────────────

async def scan_best_frame(sid: str, attacking_direction: str) -> dict:
    s = get_session(sid)
    if not s["video_path"]:
        raise RuntimeError("No video uploaded for session")

    s["attacking_direction"] = attacking_direction
    s["status"]              = "scanning"

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(
        None, lambda: analyse_best_frame(s["video_path"], detect_persons)
    )

    s["cluster_info"] = info
    s["status"]       = "awaiting_team_selection"

    return {
        "team_a_hex":     info["team_a_hex"],
        "team_b_hex":     info["team_b_hex"],
        "team_a_rgb":     info["team_a_rgb"],
        "team_b_rgb":     info["team_b_rgb"],
        "referee_hex":    rgb_to_hex(info["referee_rgb"]) if info["referee_rgb"] else None,
        "player_count":   info["player_count"],
        "best_frame_idx": info["best_frame_idx"],
    }


# ── Phase 2: record team choice ───────────────────────────────────────────────

def set_attacking_team(sid: str, attacking_team: str) -> None:
    if attacking_team not in ("team_a", "team_b"):
        raise ValueError("attacking_team must be 'team_a' or 'team_b'")
    s = get_session(sid)
    s["attacking_team"] = attacking_team
    s["status"]         = "ready"


# ── Phase 3: process video ────────────────────────────────────────────────────

async def process_video(sid: str) -> AsyncGenerator[dict, None]:
    """
    Yields:
        { type: progress,  frame, total, verdict, confidence }
        { type: complete,  verdict, confidence, video_url, offside_frames, total_frames }
        { type: error,     message }
    """
    s = get_session(sid)

    if s["status"] not in ("ready", "awaiting_team_selection"):
        yield {"type": "error", "message": f"Session not ready (status={s['status']})"}
        return
    if not s["attacking_team"]:
        yield {"type": "error", "message": "attacking_team not set"}
        return

    info                = s["cluster_info"]
    attacking_team      = s["attacking_team"]
    attacking_direction = s["attacking_direction"] or "right"
    team_a_lab          = info["team_a_lab"]
    team_b_lab          = info["team_b_lab"]

    # Convert referee RGB → Lab if available
    ref_lab = None
    if info.get("referee_rgb"):
        r, g, b = info["referee_rgb"]
        bgr_px  = np.uint8([[[b, g, r]]])
        ref_lab = cv2.cvtColor(bgr_px, cv2.COLOR_BGR2Lab)[0, 0].astype(np.float32)

    reset_trackers()

    meta      = get_video_meta(s["video_path"])
    fps       = meta["fps"]
    fw, fh    = meta["width"], meta["height"]
    total     = meta["total_frames"]

    raw_out   = str(OUTPUT_DIR / f"{sid}_raw.mp4")
    final_out = str(OUTPUT_DIR / f"{sid}_out.mp4")

    writer = raw_video_writer(raw_out, fps, fw, fh)
    cap    = cv2.VideoCapture(s["video_path"])

    all_results: list[dict] = []
    frame_idx = 0
    s["status"] = "processing"

    try:
        loop = asyncio.get_event_loop()

        while True:
            ret, fr = cap.read()
            if not ret:
                break

            def _process_frame(frame, _fidx=frame_idx):
                persons = detect_and_classify(
                    frame, team_a_lab, team_b_lab, ref_lab, fw, fh,
                )
                balls = detect_ball(frame)
                logic = run_offside_logic(
                    persons, balls, fw, attacking_team, attacking_direction,
                )
                ann = annotate_frame(frame, persons, balls, logic, _fidx, total)
                return ann, logic

            ann, logic = await loop.run_in_executor(None, _process_frame, fr)
            writer.write(ann)
            all_results.append(logic)

            if frame_idx % 10 == 0:
                yield {
                    "type":       "progress",
                    "frame":      frame_idx,
                    "total":      total,
                    "verdict":    logic["verdict"],
                    "confidence": logic["confidence"],
                }

            frame_idx += 1

    finally:
        cap.release()
        writer.release()

    if not all_results:
        yield {"type": "error", "message": "No frames processed"}
        return

    offside_count = sum(1 for r in all_results if r["verdict"] == "OFFSIDE")
    final_verdict = "OFFSIDE" if offside_count / len(all_results) >= OFFSIDE_VERDICT_THRESHOLD \
                    else "ONSIDE"
    conf_values   = [r["confidence"] for r in all_results if r["verdict"] == final_verdict]
    final_conf    = float(np.mean(conf_values)) if conf_values else 0.5

    encoded = await asyncio.get_event_loop().run_in_executor(
        None, lambda: reencode_h264(raw_out, final_out)
    )
    if not encoded:
        shutil.copy(raw_out, final_out)
    try:
        os.remove(raw_out)
    except OSError:
        pass

    s["status"]           = "done"
    s["output_path"]      = final_out
    s["final_verdict"]    = final_verdict
    s["final_confidence"] = final_conf

    yield {
        "type":           "complete",
        "verdict":        final_verdict,
        "confidence":     round(final_conf, 3),
        "video_url":      f"/video/{sid}",
        "offside_frames": offside_count,
        "total_frames":   len(all_results),
    }