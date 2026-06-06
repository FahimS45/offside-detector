#!/usr/bin/env python3
"""
test_ws.py  —  Terminal test client for OffsideAI.

Flow
----
1. HTTP POST /upload  → get session_id          (no WebSocket size issues)
2. WebSocket /ws/analyse/{session_id}
   Server → colour_options
   Client → team_select
   Server → progress... complete

Usage
-----
    python test_ws.py --video path/to/clip.mp4 [options]

Options
-------
    --video      PATH        Path to the football clip (required)
    --direction  left|right  Attacking direction (default: right)
    --team       a|b         Pre-select attacking team, skip prompt (optional)
    --host       HOST        Default: localhost
    --port       PORT        Default: 7860
    --save       PATH        Where to save output video (default: output.mp4)
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import websockets
except ImportError:
    sys.exit("Run:  pip install websockets  then try again.")

try:
    import httpx
except ImportError:
    sys.exit("Run:  pip install httpx  then try again.")


# ── Terminal colours ──────────────────────────────────────────────────────────

def _bg(r, g, b, text):
    return f"\033[48;2;{r};{g};{b}m{text}\033[0m"

def _fg(r, g, b, text):
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

def swatch(hex_str: str, label: str) -> str:
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"  {_bg(r,g,b,'   ')}  #{h.upper()}   {label}"

def hdr(t):  print(f"\n\033[1;36m{'─'*56}\033[0m\n\033[1;36m  {t}\033[0m\n\033[1;36m{'─'*56}\033[0m")
def ok(m):   print(f"\033[32m  ✓  {m}\033[0m")
def info(m): print(f"\033[34m  ·  {m}\033[0m")
def warn(m): print(f"\033[33m  ⚠  {m}\033[0m")
def err(m):  print(f"\033[31m  ✗  {m}\033[0m", file=sys.stderr)


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(args):
    video  = Path(args.video)
    base   = f"http://{args.host}:{args.port}"
    ws_base = f"ws://{args.host}:{args.port}"

    if not video.exists():
        err(f"File not found: {video}"); sys.exit(1)

    size_mb = video.stat().st_size / 1_048_576
    hdr("OffsideAI — Terminal Test Client")
    info(f"Video     : {video}  ({size_mb:.1f} MB)")
    info(f"Direction : attacking → {args.direction}")
    info(f"Server    : {base}")

    # ── Step 0: HTTP upload ───────────────────────────────────────────────────
    hdr("Step 1 — Uploading video (HTTP POST)")
    info("Sending file…")

    with httpx.Client(timeout=120) as client:
        try:
            resp = client.post(
                f"{base}/upload",
                files={"file": (video.name, video.read_bytes(), "video/mp4")},
                data={"direction": args.direction},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            err(f"Upload failed ({e.response.status_code}): {e.response.text}")
            sys.exit(1)
        except httpx.RequestError as e:
            err(f"Could not reach server: {e}")
            err("Is the server running?  uvicorn backend.main:app --port 7860 --reload")
            sys.exit(1)

    payload    = resp.json()
    session_id = payload["session_id"]
    ok(f"Uploaded {payload['bytes']:,} bytes — session: {session_id}")

    # ── Step 1-4: WebSocket session ───────────────────────────────────────────
    ws_url = f"{ws_base}/ws/analyse/{session_id}"
    info(f"Connecting WebSocket: {ws_url}")

    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        ok("WebSocket connected")

        colour_info = None

        # Drain until colour_options arrives
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            t   = msg.get("type")

            if t == "status":
                info(f"Server: {msg['message']}")
            elif t == "colour_options":
                colour_info = msg
                break
            elif t == "error":
                err(f"Server error: {msg['message']}"); return

        # ── Show colour swatches ──────────────────────────────────────────────
        hdr("Step 2 — Jersey colour clusters")
        a_hex = colour_info.get("team_a_hex", "#ffffff")
        b_hex = colour_info.get("team_b_hex", "#000000")
        r_hex = colour_info.get("referee_hex")

        print(swatch(a_hex, "← Cluster A   (type 'a' to pick as attackers)"))
        print(swatch(b_hex, "← Cluster B   (type 'b' to pick as attackers)"))
        if r_hex:
            print(swatch(r_hex, "← Referee (auto-labelled by model)"))
        info(f"Players found in best frame: {colour_info.get('player_count', '?')}")

        # ── Team selection ────────────────────────────────────────────────────
        hdr("Step 3 — Pick the attacking team")

        if args.team:
            choice = args.team.lower()
            info(f"Auto-selected via --team flag: cluster {choice.upper()}")
        else:
            while True:
                try:
                    choice = input(
                        "\n  Which cluster colour is the ATTACKING team? [a / b] : "
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nAborted."); return
                if choice in ("a", "b"):
                    break
                warn("Please type  a  or  b")

        attacking_team = "team_a" if choice == "a" else "team_b"
        ok(f"Attacking team → {attacking_team}")

        await ws.send(json.dumps({
            "type":               "team_select",
            "attacking_team":     attacking_team,
            "attacking_direction": args.direction,
        }))

        # ── Stream progress ───────────────────────────────────────────────────
        hdr("Step 4 — Processing")
        last_pct    = -1
        complete    = None

        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            t   = msg.get("type")

            if t == "status":
                info(f"Server: {msg['message']}")

            elif t == "progress":
                frame = msg.get("frame", 0)
                total = msg.get("total", 1) or 1
                pct   = int(frame / total * 100)
                if pct >= last_pct + 5:
                    verdict = msg.get("verdict", "…")
                    conf    = msg.get("confidence", 0)
                    done    = int(pct / 5)
                    bar     = "█" * done + "░" * (20 - done)
                    colour  = "\033[31m" if verdict == "OFFSIDE" else "\033[32m"
                    print(
                        f"\r  [{bar}] {pct:3d}%  {colour}{verdict}\033[0m  {conf*100:.0f}% conf",
                        end="", flush=True,
                    )
                    last_pct = pct

            elif t == "complete":
                print()
                complete = msg
                break

            elif t == "error":
                print()
                err(f"Server error: {msg['message']}"); return

        # ── Result ────────────────────────────────────────────────────────────
        hdr("Result")
        verdict = complete["verdict"]
        conf    = complete["confidence"]
        o_f     = complete.get("offside_frames", "?")
        t_f     = complete.get("total_frames", "?")
        v_url   = complete.get("video_url", "")

        if verdict == "OFFSIDE":
            print(f"\n  \033[1;31m🚩  OFFSIDE\033[0m  —  {conf*100:.1f}% confidence")
        else:
            print(f"\n  \033[1;32m✅  ONSIDE\033[0m   —  {conf*100:.1f}% confidence")

        info(f"Offside frames: {o_f} / {t_f}")

        if v_url and args.save:
            info(f"Downloading annotated video → {args.save}")
            with httpx.Client(timeout=120) as client:
                r = client.get(f"{base}{v_url}")
                Path(args.save).write_bytes(r.content)
            size = Path(args.save).stat().st_size / 1_048_576
            ok(f"Saved {size:.1f} MB → {args.save}")
            ok("Open it in VLC / any video player to review.")
        elif v_url:
            info(f"Video ready at: {base}{v_url}")
            info("Run with --save output.mp4 to download it.")

        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="OffsideAI terminal test client")
    p.add_argument("--video",     required=True)
    p.add_argument("--direction", default="right", choices=["left", "right"])
    p.add_argument("--team",      default=None,    choices=["a", "b"],
                   help="Skip interactive prompt — pick cluster a or b")
    p.add_argument("--host",      default="localhost")
    p.add_argument("--port",      default=7860, type=int)
    p.add_argument("--save",      default="output.mp4")
    args = p.parse_args()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.")
