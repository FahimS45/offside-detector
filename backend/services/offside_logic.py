"""
Offside decision logic.

Rules implemented:
* Attacking direction is user-supplied (left | right).
* The attacking team is also user-supplied (team_a | team_b).
* Offside line = horizontal foot position of the last defender
  (second-last player including the goalkeeper, but we treat the
  deepest defender as the reference since keepers are separately labelled).
* An attacker is offside if:
    - their foot x is beyond the offside line, AND
    - their foot x is beyond the ball.
* Confidence grows with the pixel margin from the offside line.
"""
from __future__ import annotations

import numpy as np

from backend.utils.geometry import box_foot_x


# ── Core offside logic ────────────────────────────────────────────────────────────────────

def run_offside_logic(
    persons: list[dict],
    balls_raw: list[tuple],
    frame_w: int,
    attacking_team: str,        # "team_a" | "team_b"
    attacking_direction: str,   # "left"   | "right"
) -> dict:
    """
    Parameters
    ----------
    persons            : classified person list from tracker
    balls_raw          : [(x1,y1,x2,y2,conf), ...]
    frame_w            : frame pixel width
    attacking_team     : which team is attacking
    attacking_direction: direction they're attacking towards

    Returns
    -------
    {
        verdict, confidence, offside_line_x, ball_x,
        offside_players, attacking_team, attacking_right, reason
    }
    """
    attacking_right = (attacking_direction == "right")
    defending_team  = "team_b" if attacking_team == "team_a" else "team_a"

    attackers  = [p for p in persons if p["role"] == attacking_team]
    defenders  = [p for p in persons if p["role"] == defending_team]

    _base = dict(
        offside_line_x  = None,
        ball_x          = None,
        offside_players = [],
        attacking_team  = attacking_team,
        attacking_right = attacking_right,
    )

    if not attackers or not defenders:
        return {**_base, "verdict": "ONSIDE", "confidence": 0.50, "reason": "missing_team"}

    # Ball x
    ball_x = (
        (balls_raw[0][0] + balls_raw[0][2]) // 2
        if balls_raw else frame_w // 2
    )

    if len(defenders) < 2:
        return {**_base, "verdict": "ONSIDE", "confidence": 0.50,
                "ball_x": ball_x, "reason": "insufficient_defenders"}

    # Last defender (deepest = closest to own goal)
    sorted_defs   = sorted(defenders, key=box_foot_x, reverse=attacking_right)
    offside_line_x = box_foot_x(sorted_defs[0])   # deepest defender

    # Check each attacker
    offside_players: list[dict] = []
    margins: list[float]        = []

    for att in attackers:
        ax = box_foot_x(att)
        if attacking_right:
            beyond_line = ax > offside_line_x
            beyond_ball = ax > ball_x
        else:
            beyond_line = ax < offside_line_x
            beyond_ball = ax < ball_x

        if beyond_line and beyond_ball:
            offside_players.append(att)
            margins.append(abs(ax - offside_line_x))

    # Confidence
    if offside_players:
        confidence = float(np.clip(0.65 + np.mean(margins) / (frame_w * 0.5) * 0.31, 0.50, 0.97))
        verdict    = "OFFSIDE"
    else:
        closest    = min(abs(box_foot_x(a) - offside_line_x) for a in attackers)
        confidence = float(np.clip(0.65 + closest / (frame_w * 0.5) * 0.25, 0.50, 0.97))
        verdict    = "ONSIDE"

    return {
        "verdict":         verdict,
        "confidence":      round(confidence, 3),
        "ball_x":          ball_x,
        "offside_line_x":  offside_line_x,
        "offside_players": offside_players,
        "attacking_team":  attacking_team,
        "attacking_right": attacking_right,
        "reason":          "ok",
    }
