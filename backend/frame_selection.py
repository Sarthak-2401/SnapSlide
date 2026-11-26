# -*- coding: utf-8 -*-
"""
frame_selection.py
------------------
Handles the SELECT phase:
  - Left pinch  -> top-left corner (lime dot)
  - Right pinch -> bottom-right corner (red dot)
  - Release     -> lock corner
  - Both locked -> returns validated square region

FIX: MIN_HOLD_FRAMES reduced to 3 and hold counter only resets after
MISS_TOLERANCE consecutive missed frames — necessary because the subprocess
detection pipeline delivers results every other frame, so a strict reset
on every missed frame made pinch-locking impossible.
"""

import cv2
from constants import C_GREEN, C_RED, C_CYAN, C_WHITE, C_GRAY, C_DARK_GRAY

MIN_REGION_SIZE = 120   # px — minimum side length after squaring
MIN_HOLD_FRAMES = 3     # pinch frames needed to lock (reduced from 6)
MISS_TOLERANCE  = 4     # missed frames tolerated before hold counter resets


def _dot(frame, pt, color, locked=False):
    r = 10 if locked else 12
    cv2.circle(frame, pt, r, color, -1)
    cv2.circle(frame, pt, r + 2, C_WHITE, 1)
    if locked:
        cv2.putText(frame, "LOCKED", (pt[0] + 14, pt[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)


class FrameSelector:

    def __init__(self):
        self.reset()

    def reset(self):
        self.lc       = None
        self.rc       = None
        self.lc_lock  = False
        self.rc_lock  = False
        self._hold    = {"Left": 0, "Right": 0}
        self._miss    = {"Left": 0, "Right": 0}  # consecutive missed frames

    def update(self, frame, hands, pinch_prev: dict, fresh=True, closed=()):
        """
        Returns (region, pinch_prev) where region is (x1,y1,x2,y2) or None.
        """
        for label, color, ca, la in [
            ("Left",  C_GREEN, "lc", "lc_lock"),
            ("Right", C_RED,   "rc", "rc_lock"),
        ]:
            was = pinch_prev.get(label, False)

            if label in hands:
                if fresh:
                    self._miss[label] = 0
                _, pinching, tip = hands[label]

                if not getattr(self, la):      # corner not yet locked
                    confirming = label in closed and self._hold[label] >= MIN_HOLD_FRAMES
                    if pinching and not confirming:
                        self._hold[label] += int(fresh)
                        setattr(self, ca, tip)
                        _dot(frame, tip, color, locked=False)

                        # Hold progress arc
                        hold_frac = min(self._hold[label] / MIN_HOLD_FRAMES, 1.0)
                        cv2.ellipse(frame, tip, (18, 18), -90,
                                    0, int(360 * hold_frac), color, 2)
                    else:
                        # Released — lock if held long enough
                        if (was
                                and self._hold[label] >= MIN_HOLD_FRAMES
                                and getattr(self, ca) is not None):
                            setattr(self, la, True)
                        self._hold[label] = 0
                else:
                    _dot(frame, getattr(self, ca), color, locked=True)

                pinch_prev[label] = pinching

            else:
                # Hand not visible — only reset hold after MISS_TOLERANCE frames
                self._miss[label] += int(fresh)
                if self._miss[label] >= MISS_TOLERANCE:
                    self._hold[label] = 0

        # Draw live selection rectangle
        if self.lc and self.rc:
            cv2.rectangle(frame, self.lc, self.rc, C_CYAN, 1)
            for pt, sgn_x, sgn_y in [
                (self.lc,  1,  1), (self.rc, -1, -1),
                ((self.rc[0], self.lc[1]), -1,  1),
                ((self.lc[0], self.rc[1]),  1, -1),
            ]:
                L = 12
                cv2.line(frame, pt, (pt[0] + sgn_x * L, pt[1]), C_WHITE, 2)
                cv2.line(frame, pt, (pt[0], pt[1] + sgn_y * L), C_WHITE, 2)

        # Both locked -> validate
        if self.lc_lock and self.rc_lock:
            lx, ly = self.lc;  rx, ry = self.rc
            x1, x2 = min(lx, rx), max(lx, rx)
            y1, y2 = min(ly, ry), max(ly, ry)
            if (x2 - x1) > MIN_REGION_SIZE and (y2 - y1) > MIN_REGION_SIZE:
                return (x1, y1, x2, y2), pinch_prev
            else:
                self.reset()

        return None, pinch_prev
