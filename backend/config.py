"""
config.py — single source of truth for OffsideAI.
"""
from pathlib import Path

# ── Directories ───────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).resolve().parent   # backend/
UPLOAD_DIR = Path("/tmp/offside_uploads")
OUTPUT_DIR = Path("/tmp/offside_outputs")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── YOLO model ────────────────────────────────────────────────────────────────

YOLO_MODEL  = "yolov8s.pt"   # swap to yolov8l.pt / yolov8x.pt for more accuracy

# COCO class indices used for filtering detections
COCO_PERSON = 0
COCO_BALL   = 32   # "sports ball" in COCO

# Minimum detection confidence to accept a box
CONF_THRESH = 0.35

# ── Pre-analysis (best-frame scan) ────────────────────────────────────────────

# How many frames to sample when looking for the frame with the most players.
# Total frames scanned = SCAN_FRAMES × SCAN_INTERVAL
SCAN_FRAMES   = 30    # number of samples
SCAN_INTERVAL = 10    # gap between samples (in frames)
MIN_PLAYERS   = 6     # warn if fewer players found during scan

# ── Team classifier (KMeans) ──────────────────────────────────────────────────

KMEANS_K         = 4    # clusters: team_a, team_b, referee, (noise)
KMEANS_INIT      = 10   # number of KMeans initialisations (higher = more stable)
MIN_YELLOW_SCORE = 40   # Lab b*−a* threshold to flag a cluster as referee kit

# ── Offside verdict ───────────────────────────────────────────────────────────

# Fraction of processed frames that must show OFFSIDE to return a final
# verdict of OFFSIDE.  Lower = more sensitive, higher = more conservative.
OFFSIDE_VERDICT_THRESHOLD = 0.30

# ── Upload limits ─────────────────────────────────────────────────────────────

MAX_UPLOAD_MB    = 200
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024