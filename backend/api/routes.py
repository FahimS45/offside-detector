"""
API routes.

Upload flow
-----------
Step 0  POST /upload
        multipart/form-data: file=<video>, direction=left|right
        Validates file size and MIME type.
        Returns { session_id, direction, bytes }

Step 1  WebSocket /ws/analyse/{session_id}
        Server scans video and sends:
        → { type: "colour_options", team_a_hex, team_b_hex, referee_hex, ... }

Step 2  Client → { type: "team_select", attacking_team: "team_a"|"team_b",
                   attacking_direction: "left"|"right" }

Step 3  Server streams:
        → { type: "progress", frame, total, verdict, confidence }  (repeated)
        → { type: "complete", verdict, confidence, video_url, offside_frames, total_frames }

On any error:
        → { type: "error", message }

REST helpers
------------
GET /video/{session_id}   — stream annotated output video
GET /health               — liveness probe
"""

from __future__ import annotations

import os
import json
import logging
from pathlib import Path

from fastapi import (
    APIRouter, File, Form, HTTPException,
    UploadFile, WebSocket, WebSocketDisconnect, Request
)
from fastapi.responses import FileResponse, StreamingResponse

from backend.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB
from backend.services.video_processor import (
    create_session,
    get_session,
    save_upload,
    scan_best_frame,
    set_attacking_team,
    process_video,
)


logger = logging.getLogger(__name__)
router = APIRouter()

# Accepted video MIME types
_ALLOWED_MIME = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/mpeg", "video/webm", "video/x-matroska",
    "application/octet-stream",   # some clients send this for .mp4
}

# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness probe — returns 200 if the server is running."""
    return {"status": "ok"}

# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", tags=["pipeline"])
async def upload_video(
    file:      UploadFile = File(..., description="Football video clip (MP4 recommended)"),
    direction: str        = Form("left", description="Attacking direction: 'left' or 'right'"),
) -> dict:
    """
    Upload a video clip via HTTP multipart.
    Returns a session_id to be passed to the WebSocket endpoint.
    """
    # Validate direction
    if direction not in ("left", "right"):
        raise HTTPException(
            status_code=422,
            detail="direction must be 'left' or 'right'",
        )

    # Validate MIME type
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{content_type}'. "
                "Please upload an MP4 or other common video format."
            ),
        )

    # Read and validate size
    try:
        data = await file.read()
    except Exception as exc:
        logger.exception("Failed to read uploaded file")
        raise HTTPException(status_code=400, detail=f"Could not read upload: {exc}") from exc

    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large ({len(data) / 1_048_576:.1f} MB). "
                f"Maximum allowed size is {MAX_UPLOAD_MB} MB."
            ),
        )

    # Create session and persist file
    sid = create_session()
    try:
        save_upload(sid, data, file.filename or "clip.mp4")
    except OSError as exc:
        logger.exception("Failed to save upload for session %s", sid)
        raise HTTPException(
            status_code=500,
            detail="Server could not save the uploaded file. Please try again.",
        ) from exc

    get_session(sid)["attacking_direction"] = direction

    logger.info(
        "Upload OK — session %s | %.1f MB | direction=%s | type=%s",
        sid, len(data) / 1_048_576, direction, content_type or "unknown",
    )
    return {"session_id": sid, "direction": direction, "bytes": len(data)}


# ── Video download and stream on the frontend ─────────────────────────────────────

@router.get("/video/{session_id}", tags=["pipeline"])
async def get_video(session_id: str, request: Request):
    """Stream the annotated output video with range request support."""
    try:
        s = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")

    out = s.get("output_path")
    if not out:
        raise HTTPException(status_code=404, detail="Annotated video is not ready yet.")

    out_path = Path(out)
    if not out_path.exists():
        logger.error("Output file missing from disk: %s", out_path)
        raise HTTPException(status_code=500, detail="Output file not found on server.")

    file_size = os.path.getsize(out_path)
    range_header = request.headers.get("range")

    def iter_file(start: int, end: int):
        with open(out_path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(65536, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    if range_header:
        range_val = range_header.strip().replace("bytes=", "")
        start_str, end_str = range_val.split("-")
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
        return StreamingResponse(
            iter_file(start, end),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range":  f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(end - start + 1),
                "Accept-Ranges":  "bytes",
            },
        )

    return FileResponse(
        path       = str(out_path),
        media_type = "video/mp4",
        headers    = {
            "Accept-Ranges":  "bytes",
            "Cache-Control":  "no-store",
            "Content-Disposition": "inline",
        },
    )

# ── WebSocket pipeline ────────────────────────────────────────────────────────

@router.websocket("/ws/analyse/{session_id}")
async def websocket_analyse(ws: WebSocket, session_id: str) -> None:
    """
    Main analysis pipeline over WebSocket.
    Connect after a successful POST /upload.
    """
    await ws.accept()
    logger.info("WS connected — session %s", session_id)

    async def send(payload: dict) -> None:
        """Send a JSON message, ignoring errors if the socket is already closed."""
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as exc:
            logger.debug("Could not send WS message (socket likely closed): %s", exc)

    # ── Validate session ──────────────────────────────────────────────────────
    try:
        s = get_session(session_id)
    except KeyError:
        await send({"type": "error", "message": f"Unknown session: {session_id}"})
        await ws.close(code=1008)
        return

    direction = s.get("attacking_direction") or "right"

    try:
        # Phase 1: scan best frame, return colour options 
        await send({"type": "status", "message": "Scanning video for best frame…"})

        try:
            colour_info = await scan_best_frame(session_id, direction)
        except RuntimeError as exc:
            # Known failure (e.g. no frames decoded, Roboflow unreachable)
            logger.error("scan_best_frame failed for session %s: %s", session_id, exc)
            await send({"type": "error", "message": str(exc)})
            return
        except Exception as exc:
            logger.exception("Unexpected error in scan_best_frame — session %s", session_id)
            await send({
                "type":    "error",
                "message": "Frame scan failed due to an internal error. Check server logs.",
            })
            return

        await send({"type": "colour_options", **colour_info})

        # Phase 2: wait for team selection 
        try:
            raw = await ws.receive_text()
        except WebSocketDisconnect:
            logger.info("Client disconnected before team_select — session %s", session_id)
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await send({
                "type":    "error",
                "message": "Invalid JSON received. Expected a team_select message.",
            })
            return

        if msg.get("type") != "team_select":
            await send({
                "type":    "error",
                "message": (
                    f"Unexpected message type '{msg.get('type')}'. "
                    "Expected 'team_select'."
                ),
            })
            return

        attacking_team = msg.get("attacking_team", "team_a")

        # Allow direction override at this stage
        if msg.get("attacking_direction") in ("left", "right"):
            direction = msg["attacking_direction"]
            s["attacking_direction"] = direction

        try:
            set_attacking_team(session_id, attacking_team)
        except ValueError as exc:
            await send({"type": "error", "message": str(exc)})
            return

        # Phase 3: stream per-frame processing 
        await send({"type": "status", "message": "Processing video…"})

        try:
            async for event in process_video(session_id):
                await send(event)
                if event.get("type") in ("complete", "error"):
                    break
        except Exception as exc:
            logger.exception("process_video crashed — session %s", session_id)
            await send({
                "type":    "error",
                "message": "Video processing failed due to an internal error. Check server logs.",
            })

    except WebSocketDisconnect:
        logger.info("WS disconnected mid-session — session %s", session_id)

    except Exception as exc:
        logger.exception("Unhandled error in WS handler — session %s", session_id)
        await send({"type": "error", "message": f"Unexpected server error: {exc}"})

    finally:
        logger.info("WS session %s closed", session_id)