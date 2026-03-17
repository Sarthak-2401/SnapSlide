# -*- coding: utf-8 -*-
# Suppress noisy MediaPipe / TensorFlow C++ logs before any imports
import os
os.environ["GLOG_minloglevel"]    = "3"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["MEDIAPIPE_DISABLE_GPU"] = "1"   # avoid GPU init warnings on CPU machines

"""
server.py
---------
FastAPI server that:
  1. Runs the full gesture-puzzle game loop in a background thread.
  2. Streams processed OpenCV frames to the browser as MJPEG
     at  GET /video_feed
  3. Broadcasts game-state JSON to the browser via WebSocket
     at  WS  /ws/state
  4. Accepts difficulty selection via POST /api/start
  5. Stops the game via POST /api/stop

All original game modules (puzzle.py, renderer.py, hand_gesture.py, etc.)
are used completely unchanged.  Only cv2.imshow / waitKey are removed —
frames are pushed into a queue and served as MJPEG instead.

Run:
    pip install fastapi uvicorn
    python server.py
"""

import asyncio
import json
import queue
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── make sure game modules are importable ─────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from constants       import CANVAS_W, CANVAS_H
from model_loader    import ensure_model
from hand_gesture    import HandDetector, is_fist, draw_skeleton
from frame_selection import FrameSelector
from puzzle          import Puzzle
from renderer        import (
    make_canvas, draw_top_bar, draw_phase_badge,
    draw_timer, draw_reset_icon, draw_bottom_hint,
    draw_shuffle_bar, draw_solved_overlay, draw_pinch_cursor,
)

# ── tunables ──────────────────────────────────────────────────────────────────
DIFF_TO_GRID      = {"3x3": 3, "4x4": 4, "5x5": 5}
SHUF_DUR          = 1.2
JPEG_QUALITY      = 60    # 60 looks fine and is ~30% smaller than 72
STREAM_FPS        = 30
STREAM_W          = 960   # encode smaller for browser — game logic runs full res
STREAM_H          = 540
CAM_WARMUP_FRAMES = 8     # discard first N frames while cam auto-exposes

# ── thread-shared objects ─────────────────────────────────────────────────────
_state_q: queue.Queue = queue.Queue(maxsize=16)
_stop_evt  = threading.Event()
_game_thr: threading.Thread | None = None

# Latest encoded JPEG — shared via lock instead of a queue.
# Game thread writes here; MJPEG streamer reads here.
# Neither side ever blocks waiting for the other.
_latest_jpg: bytes   = b""
_latest_lock         = threading.Lock()
_frame_ready         = threading.Event()


# ── helpers ───────────────────────────────────────────────────────────────────

def _q_put(q: queue.Queue, item):
    """Drop-oldest non-blocking put for state queue."""
    if q.full():
        try:
            q.get_nowait()
        except queue.Empty:
            pass
    try:
        q.put_nowait(item)
    except queue.Full:
        pass


def _push_frame(jpg: bytes):
    """Write latest JPEG; non-blocking, always overwrites the previous frame."""
    global _latest_jpg
    with _latest_lock:
        _latest_jpg = jpg
    _frame_ready.set()   # wake the streamer immediately


def _patch_grid(grid: int):
    """Rewrite GRID = N in constants.py without touching anything else."""
    p = BASE_DIR / "constants.py"
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("GRID") and "=" in s and not s.startswith("#"):
            out.append(f"GRID = {grid}\n")
        else:
            out.append(ln)
    p.write_text("".join(out), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# Game loop  (daemon thread)
# ═══════════════════════════════════════════════════════════════════════════════

class St:
    SELECT  = "SELECT"
    SHUFFLE = "SHUFFLE"
    PLAY    = "PLAY"
    SOLVED  = "SOLVED"


def game_loop():
    ensure_model()

    # HandDetector runs MediaPipe in a background thread.
    # submit() is non-blocking; get_hands() always returns instantly.
    # The game loop renders at full camera FPS while detection runs async.
    detector = HandDetector()
    detector.start()

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        _q_put(_state_q, {"event": "error", "msg": "Cannot open webcam"})
        detector.stop()
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CANVAS_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CANVAS_H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    for _ in range(CAM_WARMUP_FRAMES):
        cap.read()

    state      = St.SELECT
    selector   = FrameSelector()
    puzzle     = None
    pinch_prev = {}
    shuf_start = None
    solved_t   = None
    play_start = None

    _q_put(_state_q, {"event": "started", "state": state})

    frame_dt      = 1.0 / STREAM_FPS
    last_frame    = 0.0
    read_failures = 0
    MAX_FAILURES  = 15

    try:
        while not _stop_evt.is_set():

            ok, raw = cap.read()
            if not ok or raw is None:
                read_failures += 1
                if read_failures >= MAX_FAILURES:
                    _q_put(_state_q, {"event": "error",
                                      "msg": "Webcam read failed"})
                    break
                time.sleep(0.03)
                continue
            read_failures = 0

            cam_frame = cv2.flip(raw, 1)
            fh, fw    = cam_frame.shape[:2]

            # Submit frame to background detector (non-blocking)
            detector.submit(cam_frame)

            # Get latest detection result (always instant)
            hands = detector.get_hands()

            # Draw
            frame = make_canvas(cam_frame)
            for lms, _, _ in hands.values():
                draw_skeleton(frame, lms, fw, fh)

            # ── SELECT ────────────────────────────────────────────────────
            if state == St.SELECT:
                draw_top_bar(frame,
                    subtitle="Frame it to Snap.  Pinch & Drag to Swap.")
                draw_phase_badge(frame, "PHASE 1: SELECT", [
                    "1. Left pinch = top-left",
                    "2. Right pinch = bottom-right",
                    "3. Release to lock",
                ])
                region, pinch_prev = selector.update(frame, hands, pinch_prev)
                if region:
                    puzzle     = Puzzle(region, frame)
                    state      = St.SHUFFLE
                    shuf_start = time.time()
                    _q_put(_state_q, {"event": "state_change", "state": state})

            # ── SHUFFLE ───────────────────────────────────────────────────
            elif state == St.SHUFFLE:
                draw_top_bar(frame,
                    subtitle="Frame it to Snap.  Pinch & Drag to Swap.")
                puzzle.draw(frame)
                elapsed = time.time() - shuf_start
                draw_shuffle_bar(frame, min(elapsed / SHUF_DUR, 1.0))
                if elapsed >= SHUF_DUR:
                    state      = St.PLAY
                    play_start = time.time()
                    _q_put(_state_q, {"event": "state_change", "state": state})

            # ── PLAY ──────────────────────────────────────────────────────
            elif state == St.PLAY:
                draw_top_bar(frame,
                    subtitle="Frame it to Snap.  Pinch & Drag to Swap.")
                draw_phase_badge(frame, "PHASE 2: SOLVE", [
                    "1. Pinch to Pick Up",
                    "2. Drag & Drop to Swap",
                    "Hold Fist to Reset",
                ])
                puzzle.draw(frame)
                draw_timer(frame, time.time() - play_start)
                draw_reset_icon(frame)
                draw_bottom_hint(frame, "Pinch & Drag to Swap")

                if (len(hands) == 2 and
                        all(is_fist(hands[l][0]) and not hands[l][1]
                            for l in hands)):
                    state      = St.SELECT
                    selector   = FrameSelector()
                    puzzle     = None
                    pinch_prev = {}
                    play_start = None
                    _q_put(_state_q, {"event": "state_change", "state": state})
                    continue

                active = ("Right" if "Right" in hands
                          else "Left" if "Left" in hands
                          else None)
                if active:
                    lms, pinching, tip = hands[active]
                    was = pinch_prev.get("play", False)
                    if pinching:
                        draw_pinch_cursor(frame, tip)
                        if not was:
                            gp = puzzle.gp_at(*tip)
                            if gp is not None:
                                puzzle.start_drag(gp)
                    else:
                        if was and puzzle.dragging is not None:
                            gp = puzzle.gp_at(*tip)
                            if gp is not None:
                                puzzle.finish_drag(gp)
                            else:
                                puzzle.cancel_drag()
                        else:
                            gp = puzzle.gp_at(*tip)
                            if gp is not None:
                                puzzle.draw_hover(frame, gp)
                    pinch_prev["play"] = pinching

                if puzzle.solved():
                    state    = St.SOLVED
                    solved_t = time.time()
                    _q_put(_state_q, {"event": "state_change", "state": state})

            # ── SOLVED ────────────────────────────────────────────────────
            elif state == St.SOLVED:
                draw_top_bar(frame,
                    subtitle="Frame it to Snap.  Pinch & Drag to Swap.")
                puzzle.restore(frame)
                elapsed = time.time() - solved_t
                draw_solved_overlay(frame, puzzle.square_region, elapsed)
                draw_timer(frame, (solved_t - play_start) if play_start else 0)

                if elapsed > 1.5 and len(hands) == 2:
                    if all(is_fist(hands[l][0]) and not hands[l][1]
                           for l in hands):
                        state      = St.SELECT
                        selector   = FrameSelector()
                        puzzle     = None
                        pinch_prev = {}
                        play_start = None
                        _q_put(_state_q,
                               {"event": "state_change", "state": state})

            # ── Encode & push JPEG ─────────────────────────────────────────
            now = time.time()
            if now - last_frame >= frame_dt:
                last_frame = now
                small = cv2.resize(frame, (STREAM_W, STREAM_H),
                                   interpolation=cv2.INTER_LINEAR)
                ret, buf = cv2.imencode(
                    ".jpg", small,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ret:
                    _push_frame(buf.tobytes())

    except Exception as exc:
        err_msg = f"Game loop error: {type(exc).__name__}: {exc}"
        print(f"[ERROR] {err_msg}", flush=True)
        _q_put(_state_q, {"event": "error", "msg": err_msg})

    finally:
        detector.stop()
        cap.release()
        _q_put(_state_q, {"event": "stopped"})


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="GesturePuzzle Stream Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRequest(BaseModel):
    difficulty: str = "3x3"


@app.post("/api/start")
async def api_start(req: StartRequest):
    global _game_thr

    grid = DIFF_TO_GRID.get(req.difficulty)
    if grid is None:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown difficulty '{req.difficulty}'")

    # Kill existing game
    if _game_thr and _game_thr.is_alive():
        _stop_evt.set()
        _game_thr.join(timeout=5)

    # Drain state queue and reset shared frame
    while not _state_q.empty():
        try: _state_q.get_nowait()
        except queue.Empty: break
    global _latest_jpg
    with _latest_lock:
        _latest_jpg = b""
    _frame_ready.clear()

    _patch_grid(grid)

    # Reload constants in this process so GRID is updated
    import importlib
    import constants as _const_mod
    importlib.reload(_const_mod)

    _stop_evt.clear()
    _game_thr = threading.Thread(target=game_loop, daemon=True, name="game")
    _game_thr.start()

    return {"status": "launched", "difficulty": req.difficulty, "grid": grid}


@app.post("/api/stop")
async def api_stop():
    global _game_thr
    _stop_evt.set()
    if _game_thr:
        _game_thr.join(timeout=5)
    return {"status": "stopped"}


@app.get("/api/status")
async def api_status():
    return {"running": bool(_game_thr and _game_thr.is_alive())}


# ── MJPEG stream ──────────────────────────────────────────────────────────────

def _make_blank_jpg() -> bytes:
    blank = np.zeros((STREAM_H, STREAM_W, 3), dtype=np.uint8)
    cv2.putText(blank, "Starting camera...",
                (STREAM_W // 2 - 160, STREAM_H // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (55, 55, 55), 2)
    _, buf = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 30])
    return buf.tobytes()


BLANK_JPG = _make_blank_jpg()


def _read_latest_frame() -> bytes:
    """
    Returns the most recently encoded frame.
    Blocks for at most 0.1 s waiting for a new frame signal, then returns
    whatever is available (could be the same frame as last time — that is
    intentional: the stream keeps flowing even when the game thread is busy).
    """
    _frame_ready.wait(timeout=0.1)
    _frame_ready.clear()
    with _latest_lock:
        return _latest_jpg if _latest_jpg else BLANK_JPG


async def _mjpeg_gen():
    loop = asyncio.get_event_loop()
    while True:
        # Run the blocking read in a thread — never blocks the event loop
        jpg = await loop.run_in_executor(None, _read_latest_frame)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            jpg +
            b"\r\n"
        )
        await asyncio.sleep(0)   # yield to event loop between frames


@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(
        _mjpeg_gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma":        "no-cache",
            "Expires":       "0",
            "Connection":    "keep-alive",
        },
    )


# ── WebSocket for state events ────────────────────────────────────────────────

@app.websocket("/ws/state")
async def ws_state(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            # Drain any pending state messages
            while not _state_q.empty():
                try:
                    msg = _state_q.get_nowait()
                    await ws.send_text(json.dumps(msg))
                except queue.Empty:
                    break
            # Yield control; catch disconnect via timeout
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=0.08)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 52)
    print("  GesturePuzzle Stream Server")
    print(f"  Dir    : {BASE_DIR}")
    print("  Stream : http://localhost:8000/video_feed")
    print("  API    : http://localhost:8000/api/start")
    print("=" * 52)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
