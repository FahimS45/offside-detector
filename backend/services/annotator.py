"""
Annotates a single frame with:
"""
from __future__ import annotations

import cv2
import numpy as np

from backend.utils.colours import ROLE_COLOUR_BGR


def annotate_frame(
    frame: np.ndarray,
    persons: list[dict],
    balls_raw: list[tuple],
    logic: dict,
    frame_idx: int  = 0,
    total_frames: int = 1,
) -> np.ndarray:
    out            = frame.copy()
    fh, fw         = out.shape[:2]
    attacking_team = logic.get("attacking_team")
    offside_ids    = {id(p) for p in logic["offside_players"]}

    # Offside line 
    if logic.get("offside_line_x") is not None:
        lx   = logic["offside_line_x"]
        lcol = (0, 0, 220) if logic["verdict"] == "OFFSIDE" else (0, 200, 30)
        cv2.line(out, (lx, 0), (lx, fh), lcol, 2)
        cv2.putText(out, "OFFSIDE LINE", (lx + 4, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, lcol, 2)

    # Ball 
    for (x1, y1, x2, y2, _) in balls_raw:
        col = ROLE_COLOUR_BGR["ball"]
        cv2.rectangle(out, (x1, y1), (x2, y2), col, 2)
        cv2.putText(out, "BALL", (x1 + 3, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)

    # Players 
    for p in persons:
        x1, y1, x2, y2 = p["box"]
        role = p["role"]

        if role == "referee":
            label = "REF"
        elif role == "goalkeeper":
            label = "GK"
        elif role == attacking_team:
            label = "ATK"
        else:
            label = "DEF"
        label += f" #{p['track_id']}"

        col   = ROLE_COLOUR_BGR.get(role, (180, 180, 180))
        thick = 3 if id(p) in offside_ids else 2

        cv2.rectangle(out, (x1, y1), (x2, y2), col, thick)

        # Red flash on offside attacker (every other 5 frames)
        if id(p) in offside_ids and frame_idx % 10 < 5:
            overlay = out.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.22, out, 0.78, 0, out)

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        cv2.rectangle(out, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), col, -1)
        cv2.putText(out, label, (x1 + 4, y1 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)

    # Verdict banner
    bh   = 48
    bcol = (0, 0, 190) if logic["verdict"] == "OFFSIDE" else (0, 155, 0)
    cv2.rectangle(out, (0, fh - bh), (fw, fh), bcol, -1)
    cv2.putText(
        out,
        f"{logic['verdict']}  |  Confidence: {logic['confidence'] * 100:.0f}%",
        (12, fh - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2,
    )

    # Progress bar
    if total_frames > 1:
        bar_w = int(fw * frame_idx / total_frames)
        cv2.rectangle(out, (0, fh - bh - 4), (bar_w, fh - bh), (255, 255, 255), -1)

    return out
