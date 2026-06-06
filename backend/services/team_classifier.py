"""
Jersey-colour extraction and KMeans team classification.
"""
from __future__ import annotations

import logging
from collections import Counter

import cv2
import numpy as np
from sklearn.cluster import KMeans

from backend.config import KMEANS_K, KMEANS_INIT, MIN_YELLOW_SCORE, MIN_PLAYERS
from backend.utils.colours import lab_to_rgb, rgb_to_hex, lab_distance

logger = logging.getLogger(__name__)


# ── Jersey colour extraction ─────────────────────────────────────────────────

def sample_jersey_colour(frame: np.ndarray, box: tuple) -> np.ndarray | None:
    """
    Extract the dominant jersey colour (in Lab) from the torso region of *box*.
    Returns a (3,) float32 Lab array, or None if the crop is unusable.
    
    Uses median instead of mean for better robustness against outliers
    (e.g. small patches of skin, numbers, dirt, shadows).
    """
    x1, y1, x2, y2 = [int(v) for v in box[:4]]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return None

    # Top 20-55 % of the bounding box ≈ torso
    torso = roi[int(0.20 * roi.shape[0]): int(0.55 * roi.shape[0])]
    if torso.size == 0:
        return None

    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)

    # Mask grass (green) and near-white pixels
    grass_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
    white_mask = cv2.inRange(hsv, (0,  0, 200), (180, 40, 255))
    exclude    = cv2.bitwise_or(grass_mask, white_mask)
    keep       = cv2.bitwise_not(exclude)

    jersey_pixels = torso[keep > 0]
    if len(jersey_pixels) < 20:
        jersey_pixels = torso.reshape(-1, 3)   # fallback

    if len(jersey_pixels) == 0:
        return None

    pixels_bgr = jersey_pixels.reshape(-1, 1, 3).astype(np.uint8)
    pixels_lab = cv2.cvtColor(pixels_bgr, cv2.COLOR_BGR2Lab)
    lab_array = pixels_lab.reshape(-1, 3).astype(np.float32)
    
    # Use median for robustness
    return np.median(lab_array, axis=0)

# ── Referee cluster detection ────────────────────────────────────────────────

def find_referee_cluster(lab_means: dict[int, np.ndarray]) -> int:
    """
    Yellow kits score high on (b* − a*) in Lab.
    Returns cluster id, or -1 if no convincingly yellow cluster found.
    """
    best_cid, best_score = -1, -999.0
    for cid, mean in lab_means.items():
        L, a, b = float(mean[0]), float(mean[1]), float(mean[2])
        score   = b - a
        logger.debug("Cluster %d: L=%.1f a=%.1f b=%.1f  yellow_score=%.1f", cid, L, a, b, score)
        if score > best_score:
            best_score, best_cid = score, cid

    if best_score < MIN_YELLOW_SCORE:
        logger.debug("No referee cluster (best score %.1f < %d)", best_score, MIN_YELLOW_SCORE)
        return -1
    logger.debug("Referee cluster: %d (score=%.1f)", best_cid, best_score)
    return best_cid


# ── Pre-analysis: find best frame + cluster ──────────────────────────────────

def analyse_best_frame(
    video_path: str,
    detect_fn,           # callable(frame) → list[{box, conf}]
    progress_cb=None,    # optional async-friendly callback(msg: str)
) -> dict:
    """
    Scan the first SCAN_FRAMES*SCAN_INTERVAL frames.
    Pick the frame with the most player detections.
    Run KMeans on jersey colours.

    Returns
    -------
    {
        "team_a_rgb": (R,G,B),
        "team_b_rgb": (R,G,B),
        "team_a_hex": "#rrggbb",
        "team_b_hex": "#rrggbb",
        "team_a_lab": np.ndarray,
        "team_b_lab": np.ndarray,
        "referee_rgb": (R,G,B) | None,
        "best_frame_idx": int,
        "player_count": int,
    }
    """
    import cv2
    from backend.config import SCAN_FRAMES, SCAN_INTERVAL

    cap        = cv2.VideoCapture(video_path)
    best_frame = None
    best_count = 0
    best_idx   = 0

    total_to_scan = SCAN_FRAMES
    for i in range(total_to_scan):
        frame_idx = i * SCAN_INTERVAL
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, fr = cap.read()
        if not ret:
            break
        dets  = detect_fn(fr)
        count = len(dets)
        if progress_cb:
            progress_cb(f"Scanning frame {frame_idx}: {count} players detected")
        if count > best_count:
            best_count = count
            best_frame = fr.copy()
            best_idx   = frame_idx

    cap.release()

    if best_frame is None:
        raise RuntimeError(
            "Could not read any frames from the video — check the file is a valid "
            "MP4 and that the detector (Roboflow/YOLO) is reachable."
        )

    if best_count < MIN_PLAYERS:
        logger.warning("Not enough players found (%d) — clustering may be unreliable", best_count)

    # Re-detect on best frame for accurate boxes
    dets  = detect_fn(best_frame)
    boxes = [d["box"] for d in dets]

    colours, valid_boxes = [], []
    for box in boxes:
        c = sample_jersey_colour(best_frame, box)
        if c is not None:
            colours.append(c)
            valid_boxes.append(box)

    if len(colours) < 4:
        # Not enough samples — return placeholder colours
        return {
            "team_a_rgb": (255, 255, 255),
            "team_b_rgb": (0, 0, 0),
            "team_a_hex": "#ffffff",
            "team_b_hex": "#000000",
            "team_a_lab": np.zeros(3),
            "team_b_lab": np.zeros(3),
            "referee_rgb": None,
            "best_frame_idx": best_idx,
            "player_count": best_count,
        }

    features = np.array(colours, dtype=np.float32)
    k        = min(KMEANS_K, len(colours))
    km       = KMeans(n_clusters=k, random_state=42, n_init=KMEANS_INIT)
    labels   = km.fit_predict(features)

    cluster_counts = Counter(labels.tolist())

    # Lab means per cluster
    lab_means: dict[int, np.ndarray] = {}
    for cid in range(k):
        members = features[labels == cid]
        lab_means[cid] = members.mean(axis=0) if len(members) > 0 else np.zeros(3)

    ref_cluster = find_referee_cluster(lab_means)

    non_ref = sorted(
        [cid for cid in range(k) if cid != ref_cluster],
        key=lambda c: cluster_counts[c],
        reverse=True,
    )

    team_a_cid = non_ref[0]
    team_b_cid = non_ref[1] if len(non_ref) > 1 else non_ref[0]

    team_a_lab = lab_means[team_a_cid]
    team_b_lab = lab_means[team_b_cid]
    team_a_rgb = lab_to_rgb(team_a_lab)
    team_b_rgb = lab_to_rgb(team_b_lab)
    ref_rgb    = lab_to_rgb(lab_means[ref_cluster]) if ref_cluster != -1 else None

    return {
        "team_a_rgb":       team_a_rgb,
        "team_b_rgb":       team_b_rgb,
        "team_a_hex":       rgb_to_hex(team_a_rgb),
        "team_b_hex":       rgb_to_hex(team_b_rgb),
        "team_a_lab":       team_a_lab,
        "team_b_lab":       team_b_lab,
        "referee_rgb":      ref_rgb,
        "best_frame_idx":   best_idx,
        "player_count":     best_count,
    }


# ── Per-player colour → team assignment ─────────────────────────────────────

def assign_team_by_colour(
    jersey_lab: np.ndarray,
    team_a_lab: np.ndarray,
    team_b_lab: np.ndarray,
) -> str:
    """
    Nearest-neighbour assignment to team_a / team_b in Lab space.
    """
    da = lab_distance(jersey_lab, team_a_lab)
    db = lab_distance(jersey_lab, team_b_lab)
    return "team_a" if da <= db else "team_b"