"""Run with python backend/server.py. The browser owns the webcam stream."""
import asyncio
import base64
import json
import sqlite3

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import time

from game import Game
from hand_gesture import HandDetector
from leaderboard import fastest, save_score
from model_loader import ensure_model


app = FastAPI(title="SnapSlide")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
SIZES = {"3x3": 3, "4x4": 4, "5x5": 5}


@app.get("/api/leaderboard")
def leaderboard(difficulty: str = "3x3"):
    if difficulty not in SIZES:
        raise HTTPException(400, "Choose a supported grid size.")
    return fastest(SIZES[difficulty])


def open_detector():
    ensure_model()
    return HandDetector()


def process_frame(payload, detector, game):
    raw = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
    if raw is None:
        raise ValueError("Could not read the webcam frame.")
    stamp = time.monotonic()
    hands = detector.detect(raw)
    frame = game.render(raw, stamp, hands)
    ok, image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
    if not ok:
        raise ValueError("Could not display the webcam frame.")
    return image.tobytes()


def command(game, message):
    if message.get("round_id") != game.round_id:
        raise ValueError("This round has ended.")
    action = message.get("action")
    if action == "solution":
        ok, image = cv2.imencode(".jpg", game.solution())
        if not ok:
            raise ValueError("Could not display the solution.")
        return {"solution": "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")}
    if action == "score":
        player = message.get("player")
        if not isinstance(player, str):
            raise ValueError("Enter your name.")
        save_score(game, player)
        return {"score_saved": True}
    if action == "hide_solution":
        game.previewing = False
        return {"solution_hidden": True}
    raise ValueError("Unknown game action.")


@app.websocket("/ws/game")
async def play(ws: WebSocket, difficulty: str = "3x3"):
    await ws.accept()
    if difficulty not in SIZES:
        await ws.close(code=1008, reason="Choose a supported grid size.")
        return
    game = Game(SIZES[difficulty])
    detector = None
    try:
        detector = await run_in_threadpool(open_detector)
        status = game.status()
        await ws.send_json(status)
        while True:
            # Also release the model if a tab or a network connection disappears.
            msg = await asyncio.wait_for(ws.receive(), timeout=60)
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                jpg = await run_in_threadpool(process_frame, msg["bytes"], detector, game)
                if game.status() != status:
                    status = game.status()
                    await ws.send_json(status)
                await ws.send_bytes(jpg)
            else:
                try:
                    update = await run_in_threadpool(command, game, json.loads(msg["text"]))
                    status = game.status()
                    await ws.send_json({**status, **update})
                except (ValueError, sqlite3.Error) as exc:
                    await ws.send_json({**game.status(), "action_error": str(exc)})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"error": str(exc) or "The camera session timed out."})
            await ws.close(code=1011)
        except (RuntimeError, OSError):
            pass
    finally:
        if detector is not None:
            await run_in_threadpool(detector.stop)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ws_per_message_deflate=False)
