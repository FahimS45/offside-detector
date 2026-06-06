---
title: Offside Detector
emoji: ⚽
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# OffsideAI

A football offside detection web application. Upload a short clip, pick the attacking team's jersey colour, and receive an annotated video with a frame-by-frame offside verdict delivered over a live WebSocket connection.

Detection runs locally using YOLOv8s. ByteTrack (bundled inside Ultralytics) assigns stable player IDs across frames. No external API calls are made during inference.

---

## Architecture overview

```
Browser
  │  HTTP POST /upload        (multipart video file)
  │  WebSocket /ws/analyse/{session_id}
  │
  ▼
FastAPI (Python 3.11)
  ├── /upload          → save file, return session_id
  ├── /ws/analyse/{id} → scan → colour_options → process → stream progress
  └── /video/{id}      → serve annotated MP4
  │
  ├── detector.py          YOLOv8s inference + ByteTrack + colour-based role assignment
  ├── team_classifier.py   KMeans jersey colour clustering (CIE Lab)
  ├── offside_logic.py     Geometric offside rule engine
  └── annotator.py         OpenCV frame annotation
```

### WebSocket message flow

| Step | Direction | Message type |
|------|-----------|-------------|
| 1 | S → C | `status` — "Scanning video…" |
| 2 | S → C | `colour_options` — two hex colours for team picker |
| 3 | C → S | `team_select` — `{attacking_team, attacking_direction}` |
| 4 | S → C | `progress` — per-frame `{frame, total, verdict, confidence}` |
| 5 | S → C | `complete` — `{verdict, confidence, video_url, offside_frames, total_frames}` |

---

## How it works — end to end

1. **Upload** — The user selects a short football clip (10–15 seconds) and chooses the attacking direction (left or right). The video is sent to the server via HTTP POST and a unique session ID is returned.

2. **Frame scanning** — The server samples frames from the clip and runs YOLOv8s detection to find the frame with the most visible players. KMeans clustering is applied in the CIE Lab colour space on the detected jersey regions to extract the two dominant team colours.

3. **Team selection** — The two colours are sent back to the browser over WebSocket. The user clicks the swatch that matches the attacking team's jersey.

4. **Processing** — The server processes every frame: YOLOv8s detects all persons and the ball, ByteTrack assigns stable IDs across frames, each player is classified as Team A, Team B, or referee based on jersey colour proximity in Lab space, and the offside geometry engine checks whether any attacker is behind the second-last defender at the moment the ball is played.

5. **Live progress** — Frame-by-frame progress events stream to the browser over the same WebSocket connection, updating a progress bar in real time.

6. **Result** — Once all frames are processed, the server re-encodes the annotated video with FFmpeg (H.264/yuv420p, faststart) for browser compatibility and sends a final verdict — OFFSIDE or ONSIDE — with a confidence score. The annotated video is displayed inline and available for download.

---

## Tech stack

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8s-Ultralytics-0075FF?logo=python&logoColor=white)
![KMeans](https://img.shields.io/badge/KMeans-CIE%20Lab%20Clustering-FF6B35?logo=scikitlearn&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.10-5C3EE8?logo=opencv&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-containerised-2496ED?logo=docker&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Spaces-FFD21E?logo=huggingface&logoColor=black)

---

## Local development

### Prerequisites

- Python 3.11+
- FFmpeg installed and on PATH — verify with `ffmpeg -version`
- ~500 MB disk space for the YOLOv8s weights (auto-downloaded on first run)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/FahimS45/offside-detector.git
cd offside-detector

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Pre-download YOLO weights so first startup is instant
python -c "from ultralytics import YOLO; YOLO('yolov8s.pt')"

# 5. Start the server
uvicorn backend.main:app --host 0.0.0.0 --port 7860 --reload
```

Open http://localhost:7860 in your browser. No API keys, no `.env` file needed.

### Run the terminal test client (no frontend needed)

```bash
python test_ws.py --video assets/sample_input/offside01-720.mp4 --direction right

# Skip the prompt and save output video directly
python test_ws.py --video assets/sample_input/offside01-720.mp4 --direction right  --save result.mp4
```

---

## Docker

### Build and run locally

```bash
# (Optional but recommended) Pre-download weights before building
# so they are baked into the image and the container starts instantly.
python -c "from ultralytics import YOLO; YOLO('yolov8s.pt')"
# This saves yolov8m.pt to the current directory.

# Build the image
docker build -t offside-ai .

# Run
docker run -p 7860:7860 offside-ai
```

Open http://localhost:7860.

### Build with the frontend included

```bash
# Build the frontend first
cd frontend && npm install && npm run build && cd ..

# Then build the Docker image — it copies frontend/dist automatically
docker build -t offside-ai .
```

---

## Configuration reference

All tuneable values are plain constants in `backend/config.py`. No environment variables, no `.env` file.

| Constant | Default | Description |
|----------|---------|-------------|
| `YOLO_MODEL` | `"yolov8s.pt"` | Path to weights. Swap to `yolov8l.pt` for higher accuracy. |
| `CONF_THRESH` | `0.35` | Minimum detection confidence to accept a bounding box. |
| `SCAN_FRAMES` | `30` | Number of frames sampled to find the best clustering frame. |
| `SCAN_INTERVAL` | `10` | Gap between sampled frames during the scan phase. |
| `MIN_PLAYERS` | `6` | Minimum detections needed for reliable KMeans clustering. |
| `KMEANS_K` | `4` | Number of KMeans clusters (team A, team B, referee, noise). |
| `KMEANS_INIT` | `10` | KMeans initialisations — higher is more stable. |
| `MIN_YELLOW_SCORE` | `40` | Lab b*−a* score to identify the referee kit cluster. |
| `OFFSIDE_VERDICT_THRESHOLD` | `0.30` | Fraction of frames showing OFFSIDE needed for a final OFFSIDE verdict. |
| `MAX_UPLOAD_MB` | `200` | Maximum accepted video file size. |

---

## Project structure

```
offside-detector/
├── backend/
│   ├── main.py                  FastAPI app, startup, static file serving
│   ├── config.py                All constants — single source of truth
│   ├── api/
│   │   └── routes.py            HTTP upload + WebSocket pipeline endpoints
│   ├── services/
│   │   ├── detector.py          YOLOv8m + ByteTrack + colour-based role assignment
│   │   ├── team_classifier.py   KMeans jersey colour clustering
│   │   ├── offside_logic.py     Geometric offside rule engine
│   │   ├── annotator.py         OpenCV frame annotation and rendering
│   │   └── video_processor.py   Session lifecycle, scan → classify → process pipeline
│   └── utils/
│       ├── colours.py           CIE Lab helpers, role→BGR colour map
│       ├── geometry.py          Bounding box helpers
│       └── video.py             FFmpeg re-encode, VideoWriter wrapper
├── frontend/                    
│   └── dist/                    Built output — served by FastAPI as static files
│   ├── src/
│   │   ├── api/                 Axios/Fetch HTTP or WebSocket client logic
│   │   ├── components/          Reusable UI elements (buttons, video players, etc.)
│   │   ├── pages/               Main view components (e.g., Dashboard, Analysis)
│   │   ├── App.tsx              Root component
│   │   ├── index.css            Global styles
│   │   └── main.tsx             App entry point
│   ├── index.html               HTML template entry point
│   ├── package-lock.json        NPM lockfile
│   ├── package.json             NPM dependencies and scripts
│   ├── tsconfig.json            TypeScript configuration
│   └── vite.config.ts           Vite configuration
├── assets/
│   └── sample_input/            Sample football clips for testing
├── test_ws.py                   Terminal WebSocket test client
├── Dockerfile                   Production image
├── requirements.txt             Python dependencies
└── .gitignore
```

---

## Known limitations

- The player detection pipeline is trained on general-purpose object detection data and may incorrectly classify spectators, coaching staff, substitutes, camera operators, advertising boards, or other off-pitch objects as active players. These false positives can propagate through the tracking and offside decision pipeline, leading to inaccurate offside calculations. Domain-specific fine-tuning on football broadcast footage would improve robustness.

- Team identification relies on colour-based clustering of jersey regions using KMeans in the CIE Lab colour space. Variations in lighting conditions, shadows, motion blur, camera exposure, kit designs, and visually similar team colours can reduce clustering accuracy. More robust colour feature extraction, temporal colour aggregation, and advanced clustering strategies should be explored.

- The current colour assignment process is based on a limited frame sampling strategy. Increasing the number of sampled frames and incorporating temporal consistency checks could improve team classification stability throughout a match sequence.

- The system currently uses heuristic-based player role assignment and geometric offside reasoning. Additional experimentation with alternative tracking algorithms, player re-identification methods, pitch calibration techniques, and perspective-aware spatial modelling may improve overall accuracy and reliability.

- The offside decision is derived from detected player positions without explicit pitch-line calibration or homography estimation. As a result, player distances and relative positions may not accurately reflect real-world field geometry, particularly in videos with significant camera tilt, zoom, or perspective distortion.

- Performance has been evaluated on a limited set of football clips. Broader validation across different leagues, stadium environments, camera angles, weather conditions, resolutions, and broadcast styles is required to assess generalisation performance and identify failure cases.

---

## License

MIT
