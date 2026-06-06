"""
detector.py
YOLOv8 inference + ByteTrack for stable track_ids + direct per-frame
jersey-colour role assignment (KMeans distance).
"""
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from backend.config import YOLO_MODEL, COCO_PERSON, COCO_BALL, CONF_THRESH
from backend.utils.colours import lab_distance

logger = logging.getLogger(__name__)

_model: YOLO | None = None


# ── Model singleton ───────────────────────────────────────────────────────────

def get_model() -> YOLO:
    global _model
    if _model is None:
        model_path = Path(YOLO_MODEL)
        if model_path.exists():
            logger.info("Loading YOLO from %s", model_path)
            _model = YOLO(str(model_path))
        else:
            logger.warning("Model not found at %s — auto-downloading yolov8s.pt", model_path)
            _model = YOLO("yolov8m.pt")
    return _model


def reset_trackers() -> None:
    """
    Reset ByteTrack state between videos.
    Ultralytics keeps ByteTrack state inside the model object; re-loading
    a fresh YOLO instance is the cleanest reset.
    """
    global _model
    if _model is not None:
        # Reload from the same weights to flush ByteTrack's internal state
        source = _model.ckpt_path or "yolov8m.pt"
        _model = YOLO(source)
        logger.info("ByteTrack state reset — model reloaded from %s", source)


# ── Role assignment (per frame, no vote window) ───────────────────────────────

def _assign_role(
    frame:      np.ndarray,
    box:        tuple,
    team_a_lab: np.ndarray,
    team_b_lab: np.ndarray,
    ref_lab:    np.ndarray | None,
    frame_w:    int,
) -> tuple[str, np.ndarray]:
    """
    Assign a role to one detected person using jersey colour distance.

    Priority
    --------
    1. ref_lab available and colour clearly closer to ref → "referee"
    2. Box centre near left/right edge                    → "goalkeeper"
    3. KMeans distance to team_a_lab vs team_b_lab        → "team_a" | "team_b"

    Returns (role, jersey_lab_colour)
    """
    from backend.services.team_classifier import sample_jersey_colour

    colour = sample_jersey_colour(frame, box)
    if colour is None:
        colour = np.zeros(3, dtype=np.float32)

    cx = (box[0] + box[2]) / 2

    # 1. Referee colour check
    if ref_lab is not None:
        d_ref  = lab_distance(colour, ref_lab)
        d_team = min(lab_distance(colour, team_a_lab), lab_distance(colour, team_b_lab))
        edge   = 0.15 * frame_w
        if d_ref < d_team * 0.8 and edge < cx < (frame_w - edge):
            return "referee", colour

    # 2. Edge heuristic → goalkeeper
    if cx < 0.08 * frame_w or cx > 0.92 * frame_w:
        return "goalkeeper", colour

    # 3. KMeans colour distance → team
    role = "team_a" if lab_distance(colour, team_a_lab) <= lab_distance(colour, team_b_lab) \
           else "team_b"
    return role, colour


# ── Public API ────────────────────────────────────────────────────────────────

def detect_persons(frame: np.ndarray) -> list[dict]:
    """
    Plain detection, no tracking, no role.
    Used by analyse_best_frame() in team_classifier.py.
    Returns [{box, conf}].
    """
    model = get_model()
    res   = model(frame, classes=[COCO_PERSON], conf=CONF_THRESH, verbose=False)[0]
    return [
        {"box": tuple(map(int, box.xyxy[0].tolist())), "conf": float(box.conf[0])}
        for box in res.boxes
    ]


def detect_and_classify(
    frame:      np.ndarray,
    team_a_lab: np.ndarray,
    team_b_lab: np.ndarray,
    ref_lab:    np.ndarray | None,
    frame_w:    int,
    frame_h:    int,
) -> list[dict]:
    """
    ByteTrack person detection + direct colour-based role assignment.
    Returns [{box, conf, track_id, role, colour}].
    """
    model = get_model()
    res   = model.track(
        frame,
        persist      = True,
        tracker      = "bytetrack.yaml",
        classes      = [COCO_PERSON],
        conf         = CONF_THRESH,
        verbose      = False,
    )[0]

    results = []
    for box in res.boxes:
        if box.id is None:
            continue
        b    = tuple(map(int, box.xyxy[0].tolist()))
        tid  = int(box.id[0])
        role, colour = _assign_role(frame, b, team_a_lab, team_b_lab, ref_lab, frame_w)
        results.append({
            "box":      b,
            "conf":     float(box.conf[0]),
            "track_id": tid,
            "role":     role,
            "colour":   colour,
        })
    return results


def detect_ball(frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
    """Returns [(x1, y1, x2, y2, conf)]."""
    model = get_model()
    res   = model(frame, classes=[COCO_BALL], conf=CONF_THRESH, verbose=False)[0]
    return [
        (*map(int, box.xyxy[0].tolist()), float(box.conf[0]))
        for box in res.boxes
    ]
