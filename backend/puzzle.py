# -*- coding: utf-8 -*-
"""
puzzle.py
---------
All puzzle computation.
SQUARE TILES: the captured region is always cropped to a square
(shortest side wins) before slicing, so all 9 tiles are identical squares.

Public API
~~~~~~~~~~
    Puzzle(region, frame)
        .square_region          the actual square (x1,y1,x2,y2) used
        .draw(frame)
        .restore(frame)
        .tile_rect(gp)
        .gp_at(px, py)
        .start_drag(gp)
        .finish_drag(gp)
        .cancel_drag()
        .solved() -> bool
        .dragging
"""

import cv2
import random

from constants import GRID, C_CYAN, C_GREEN, C_WHITE, C_ORANGE, C_DARK_GRAY


def _make_square(region):
    """
    Shrink a rectangle to the largest centred square that fits inside it.
    Returns (x1, y1, x2, y2).
    """
    x1, y1, x2, y2 = region
    w = x2 - x1
    h = y2 - y1
    side = min(w, h)
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    half = side // 2
    return cx - half, cy - half, cx - half + side, cy - half + side


class Puzzle:

    def __init__(self, region, frame):
        # Force square
        self.square_region = _make_square(region)
        self.region        = self.square_region   # alias used by renderer
        self.dragging      = None

        self._tiles        = self._slice(frame)
        self.order         = list(range(GRID * GRID))
        self._shuffle_order()

    # ── Private ───────────────────────────────────────────────────────────────

    def _slice(self, frame):
        x1, y1, x2, y2 = self.square_region
        side = x2 - x1
        tile_px = side // GRID          # square tiles
        tiles = []
        for row in range(GRID):
            for col in range(GRID):
                tx = x1 + col * tile_px
                ty = y1 + row * tile_px
                tiles.append(frame[ty:ty + tile_px, tx:tx + tile_px].copy())
        return tiles

    def _shuffle_order(self):
        random.shuffle(self.order)
        while self.order == list(range(GRID * GRID)):
            random.shuffle(self.order)

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _tile_px(self):
        x1, _, x2, _ = self.square_region
        return (x2 - x1) // GRID

    def tile_rect(self, gp):
        x1, y1, _, _ = self.square_region
        tp = self._tile_px()
        col, row = gp % GRID, gp // GRID
        tx = x1 + col * tp
        ty = y1 + row * tp
        return tx, ty, tx + tp, ty + tp

    def gp_at(self, px, py):
        x1, y1, x2, y2 = self.square_region
        if not (x1 <= px < x2 and y1 <= py < y2):
            return None
        tp = self._tile_px()
        col = min(int((px - x1) / tp), GRID - 1)
        row = min(int((py - y1) / tp), GRID - 1)
        return row * GRID + col

    # ── Interaction ───────────────────────────────────────────────────────────

    def start_drag(self, gp):
        self.dragging = self.order[gp]

    def finish_drag(self, gp):
        if self.dragging is None:
            return
        from_pos = self.order.index(self.dragging)
        if from_pos != gp:
            self.order[from_pos], self.order[gp] = \
                self.order[gp], self.order[from_pos]
        self.dragging = None

    def cancel_drag(self):
        self.dragging = None

    # ── Rendering ─────────────────────────────────────────────────────────────

    def draw(self, frame):
        x1, y1, x2, y2 = self.square_region
        tp = self._tile_px()

        for gp, ti in enumerate(self.order):
            tx1, ty1, tx2, ty2 = self.tile_rect(gp)
            resized = cv2.resize(self._tiles[ti], (tp, tp))
            frame[ty1:ty1 + tp, tx1:tx1 + tp] = resized

            # Selected-tile highlight (cyan tint)
            if self.dragging == ti:
                ov = frame[ty1:ty1 + tp, tx1:tx1 + tp].copy()
                cv2.rectangle(ov, (0, 0), (tp - 1, tp - 1), C_CYAN, -1)
                cv2.addWeighted(ov, 0.25,
                                frame[ty1:ty1 + tp, tx1:tx1 + tp], 0.75, 0,
                                frame[ty1:ty1 + tp, tx1:tx1 + tp])

            # Thin white grid line
            cv2.rectangle(frame, (tx1, ty1), (tx2 - 1, ty2 - 1), C_WHITE, 1)

        # Outer border (lime)
        cv2.rectangle(frame, (x1, y1), (x2, y2), C_GREEN, 2)

    def draw_hover(self, frame, gp):
        hx1, hy1, hx2, hy2 = self.tile_rect(gp)
        cv2.rectangle(frame, (hx1, hy1), (hx2, hy2), C_ORANGE, 2)

    def restore(self, frame):
        x1, y1, _, _ = self.square_region
        tp = self._tile_px()
        for i, tile in enumerate(self._tiles):
            col, row = i % GRID, i // GRID
            tx = x1 + col * tp
            ty = y1 + row * tp
            frame[ty:ty + tp, tx:tx + tp] = cv2.resize(tile, (tp, tp))

    # ── Solved ────────────────────────────────────────────────────────────────

    def solved(self):
        return self.order == list(range(GRID * GRID))
