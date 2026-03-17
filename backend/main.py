# -*- coding: utf-8 -*-
"""
main.py
-------
Entry point. Owns the game-loop and state-machine transitions only.
All logic is delegated to the other modules.

Run:
    python main.py

Controls:
    Left-hand pinch              set top-left corner of puzzle region
    Right-hand pinch             set bottom-right corner
    Release pinch                lock that corner
    Both corners locked          puzzle generated & shuffled
    Pinch a tile                 select it
    Move finger & release        swap with tile under finger
    Both fists (index curled)    reset the game
    Q / Esc                      quit
    R                            reset
"""

import sys
import time
import cv2

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from mediapipe import Image as MpImage, ImageFormat

from constants       import WIN_NAME, CANVAS_W, CANVAS_H
from model_loader    import ensure_model
from hand_gesture    import build_landmarker, parse_hands, is_fist, draw_skeleton
from frame_selection import FrameSelector
from puzzle          import Puzzle
from renderer        import (
    make_canvas,
    draw_top_bar,
    draw_phase_badge,
    draw_timer,
    draw_reset_icon,
    draw_bottom_hint,
    draw_shuffle_bar,
    draw_solved_overlay,
    draw_pinch_cursor,
)


# ── States ────────────────────────────────────────────────────────────────────
class St:
    SELECT  = "SELECT"
    SHUFFLE = "SHUFFLE"
    PLAY    = "PLAY"
    SOLVED  = "SOLVED"

SHUF_DUR = 1.2


# ═══════════════════════════════════════════════════════════════════════════════

def main():
    ensure_model()

    latest = [None]
    def on_result(result, _img, _ts):
        latest[0] = result

    lmk = build_landmarker(on_result)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam.")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CANVAS_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CANVAS_H)

    state      = St.SELECT
    selector   = FrameSelector()
    puzzle     = None
    pinch_prev = {}
    shuf_start = None
    solved_t   = None
    play_start = None       # for elapsed timer shown in PLAY / SOLVED
    boot_t     = time.time()

    while True:
        ok, raw = cap.read()
        if not ok:
            break

        cam_frame = cv2.flip(raw, 1)
        fh, fw    = cam_frame.shape[:2]
        ts_ms     = int((time.time() - boot_t) * 1000)

        # ── Hand tracking ──────────────────────────────────────────────────
        rgb = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
        lmk.detect_async(MpImage(image_format=ImageFormat.SRGB, data=rgb), ts_ms)

        hands = parse_hands(latest[0], fw, fh)

        # Compose dark-bg canvas from raw camera feed
        frame = make_canvas(cam_frame)

        # Draw skeletons on canvas
        for lms, _, _ in hands.values():
            draw_skeleton(frame, lms, fw, fh)

        # ══════════════════════════════════════════════════════════════════
        # SELECT
        # ══════════════════════════════════════════════════════════════════
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

        # ══════════════════════════════════════════════════════════════════
        # SHUFFLE
        # ══════════════════════════════════════════════════════════════════
        elif state == St.SHUFFLE:
            draw_top_bar(frame, subtitle="Frame it to Snap.  Pinch & Drag to Swap.")
            puzzle.draw(frame)
            elapsed = time.time() - shuf_start
            draw_shuffle_bar(frame, min(elapsed / SHUF_DUR, 1.0))
            if elapsed >= SHUF_DUR:
                state      = St.PLAY
                play_start = time.time()

        # ══════════════════════════════════════════════════════════════════
        # PLAY
        # ══════════════════════════════════════════════════════════════════
        elif state == St.PLAY:
            draw_top_bar(frame, subtitle="Frame it to Snap.  Pinch & Drag to Swap.")
            draw_phase_badge(frame, "PHASE 2: SOLVE", [
                "1. Pinch to Pick Up",
                "2. Drag & Drop to Swap",
                "Hold Fist to Reset",
            ])
            puzzle.draw(frame)

            play_elapsed = time.time() - play_start
            draw_timer(frame, play_elapsed)
            draw_reset_icon(frame)
            draw_bottom_hint(frame, "Use Space+Thumb Pinch")

            # Both-fist reset
            if (len(hands) == 2 and
                    all(is_fist(hands[l][0]) and not hands[l][1]
                        for l in hands)):
                state      = St.SELECT
                selector   = FrameSelector()
                puzzle     = None
                pinch_prev = {}
                play_start = None
                continue

            active = "Right" if "Right" in hands else \
                     ("Left"  if "Left"  in hands else None)

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

        # ══════════════════════════════════════════════════════════════════
        # SOLVED
        # ══════════════════════════════════════════════════════════════════
        elif state == St.SOLVED:
            draw_top_bar(frame, subtitle="Frame it to Snap.  Pinch & Drag to Swap.")
            puzzle.restore(frame)
            elapsed = time.time() - solved_t
            draw_solved_overlay(frame, puzzle.square_region, elapsed)
            play_elapsed = (solved_t - play_start) if play_start else 0
            draw_timer(frame, play_elapsed)

            if elapsed > 1.5 and len(hands) == 2:
                if all(is_fist(hands[l][0]) and not hands[l][1]
                       for l in hands):
                    state      = St.SELECT
                    selector   = FrameSelector()
                    puzzle     = None
                    pinch_prev = {}
                    play_start = None

        # ── Show ──────────────────────────────────────────────────────────
        cv2.imshow(WIN_NAME, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord('r'):
            state      = St.SELECT
            selector   = FrameSelector()
            puzzle     = None
            pinch_prev = {}
            play_start = None

    lmk.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
