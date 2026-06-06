"""
FastAPI application entry point.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title       = "OffsideAI",
    description = "Football offside detection — YOLOv8m + ByteTrack + WebSocket",
    version     = "1.0.0",
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router)

# ── Serve frontend build ───────────────────────────────────────────────────────

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")
    logger.info("Serving frontend from %s", FRONTEND_DIST)
else:
    logger.info("No frontend/dist — running in API-only mode")


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup() -> None:
    """Pre-warm the YOLO model so the first request is instant."""
    try:
        from backend.services.detector import get_model
        get_model()
        logger.info("YOLOv8m model loaded on startup")
    except Exception as exc:
        logger.warning("Could not pre-load YOLO model on startup: %s", exc)