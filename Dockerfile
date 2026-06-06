# ── Stage 1: build frontend ───────────────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python backend + built frontend ──────────────────────────────────
# PyTorch runtime — includes torch/torchvision pre-installed.
# Ultralytics (YOLOv8) works on CPU for inference.
FROM pytorch/pytorch:2.2.2-cuda11.8-cudnn8-runtime

# System deps: FFmpeg for video re-encoding, libGL/libGLib for OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (layer-cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY backend/ ./backend/

# Frontend — copied from build stage (no need for frontend/dist in repo)
COPY --from=frontend-build /app/frontend/dist ./frontend/dist/

# YOLO weights — auto-downloaded at build time, baked into the image
RUN python -c "from ultralytics import YOLO; YOLO('yolov8s.pt')"

# Tmp directories for uploads / outputs (ephemeral, fine for HF Spaces demos)
RUN mkdir -p /tmp/offside_uploads /tmp/offside_outputs

EXPOSE 7860

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]