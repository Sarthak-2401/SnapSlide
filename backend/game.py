"""The same round and gesture rules drive the web and desktop players."""
import time
from uuid import uuid4

import cv2

from frame_selection import FrameSelector
from hand_gesture import GestureHold, draw_skeleton, is_fist
from puzzle import Puzzle
from renderer import (make_canvas, draw_phase_badge, draw_timer, draw_pinch_cursor,
                      draw_shuffle_bar, draw_solved_overlay)


class Game:
    def __init__(self, grid):
        self.grid = grid
        self.reset()

    def reset(self):
        self.state = "SELECT"
        self.round_id = uuid4().hex
        self.selector = FrameSelector()
        self.region = None
        self.puzzle = None
        self.pinch_prev = {}
        self.capture_hold = GestureHold(0.20, grace=0.32)
        self.reset_hold = GestureHold(0.75, grace=0.25)
        self.reset_armed = False
        self.last_stamp = None
        self.drag_hand = None
        self.drag_last_seen = 0
        self.started = self.finished = None
        self.assisted = self.saved = self.previewing = False

    def status(self):
        elapsed = None if self.finished is None else round((self.finished - self.started) * 1000)
        return dict(state=self.state, round_id=self.round_id, grid=self.grid,
                    assisted=self.assisted, saved=self.saved, previewing=self.previewing, elapsed_ms=elapsed)

    def solution(self):
        if self.puzzle is None:
            raise ValueError("Capture a puzzle first.")
        if self.state != "SOLVED":
            self.assisted = True
        self.previewing = True
        self.puzzle.cancel_drag()
        self.drag_hand = None
        return self.puzzle.original

    def _play(self, hands, frame, stamp):
        if self.drag_hand and self.drag_hand not in hands:
            if stamp - self.drag_last_seen > 0.25:
                self.puzzle.cancel_drag()
                self.drag_hand = None
            return
        label = self.drag_hand or ("Right" if "Right" in hands else "Left")
        if label not in hands:
            return
        _, pinch, tip = hands[label]
        pos = self.puzzle.gp_at(*tip)
        if pinch:
            draw_pinch_cursor(frame, tip)
            if not self.pinch_prev.get(label) and pos is not None:
                self.puzzle.start_drag(pos)
                self.drag_hand = label
            self.drag_last_seen = stamp
        elif self.drag_hand:
            if pos is None:
                self.puzzle.cancel_drag()
            else:
                self.puzzle.finish_drag(pos)
            self.drag_hand = None
        elif pos is not None:
            self.puzzle.draw_hover(frame, pos)
        self.pinch_prev[label] = pinch

    def render(self, camera, stamp, hands, now=None):
        now = time.monotonic() if now is None else now
        frame = make_canvas(camera)
        h, w = frame.shape[:2]
        fresh = stamp != self.last_stamp
        self.last_stamp = stamp
        if now - stamp > 0.4:
            hands = {}
        for landmarks, _, _ in hands.values():
            draw_skeleton(frame, landmarks, w, h)

        if self.state == "SELECT":
            # A fist can still look like a thumb-index pinch. Lock at the last
            # selected point when the fingers curl, before the fingertips shift.
            closed = {label for label, hand in hands.items()
                      if self.pinch_prev.get(label) and is_fist(hand[0], w / h)}
            self.region, self.pinch_prev = self.selector.update(frame, hands, self.pinch_prev, fresh, closed)
            if self.region:
                self.state = "CONFIRM"
            draw_phase_badge(frame, "SELECT FRAME", ["Pinch opposite corners", "Release each pinch to lock"])
        elif self.state == "CONFIRM":
            x1, y1, x2, y2 = self.region
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 200), 2)
            fists = any(is_fist(hand[0], w / h) for hand in hands.values())
            if fresh and self.capture_hold.update(fists, stamp):
                self.puzzle = Puzzle(self.region, camera, self.grid)
                self.state = "SHUFFLE"
                self.shuffled_at = now
                self.pinch_prev.clear()
            draw_phase_badge(frame, "CONFIRM FRAME", ["Close either fist briefly", "Keep the fist in view"])
        elif self.state == "SHUFFLE":
            self.puzzle.draw(frame)
            progress = (now - self.shuffled_at) / 0.7
            draw_shuffle_bar(frame, min(1, progress))
            if progress >= 1:
                self.state = "PLAY"
                self.started = now
        else:
            if self.state == "PLAY":
                self.puzzle.draw(frame)
                if fresh and not self.previewing:
                    self._play(hands, frame, stamp)
                    if self.puzzle.solved():
                        self.state = "SOLVED"
                        self.finished = now
                draw_timer(frame, now - self.started)
            else:
                self.puzzle.restore(frame)
                draw_solved_overlay(frame, self.puzzle.square_region, now - self.finished)
                draw_timer(frame, self.finished - self.started)
            if fresh and not self.previewing:
                fists = [is_fist(hand[0], w / h) for hand in hands.values()]
                if fists and not all(fists):
                    self.reset_armed = True
                if self.reset_armed and self.reset_hold.update(fists == [True, True], stamp):
                    self.reset()
        return frame
