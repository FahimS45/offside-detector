"""
Colour helpers shared across services.
"""
import cv2
import numpy as np

# ── Role → BGR drawing colour ────────────────────────────────────────────────

ROLE_COLOUR_BGR: dict[str, tuple[int, int, int]] = {
    "team_a":     (235, 180,  30),   # amber  – attackers
    "team_b":     ( 30, 160, 235),   # blue   – defenders
    "referee":    ( 50, 220, 255),   # yellow
    "goalkeeper": (200,  50, 200),   # purple
    "ball":       (255, 255, 255),   # white
}

# ── Conversion from LAB to RGB ────────────────────────────────────────────────

def lab_to_rgb(lab_arr: np.ndarray) -> tuple[int, int, int]:
    """Convert a single Lab pixel (OpenCV scale) → (R, G, B) int tuple."""
    px   = np.uint8([[[int(lab_arr[0]), int(lab_arr[1]), int(lab_arr[2])]]])
    bgr  = cv2.cvtColor(px, cv2.COLOR_Lab2BGR)
    b, g, r = int(bgr[0, 0, 0]), int(bgr[0, 0, 1]), int(bgr[0, 0, 2])
    return (r, g, b)

# ── Conversion from RGB to HEX ────────────────────────────────────────────────

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)

# ── LAB distance ────────────────────────────────────────────────

def lab_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a.astype(float) - b.astype(float)))
