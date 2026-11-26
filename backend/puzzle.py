"""A square photo puzzle. Any two tiles can be swapped."""
import random

import cv2

from constants import GRID, C_CYAN, C_GREEN, C_ORANGE, C_WHITE


class Puzzle:
    def __init__(self, region, frame, grid=GRID):
        if grid not in (3, 4, 5):
            raise ValueError("Choose a 3, 4 or 5 tile grid.")
        self.grid = grid
        x1, y1, x2, y2 = region
        height, width = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        self.tile_size = min(x2 - x1, y2 - y1) // grid
        if self.tile_size < 1:
            raise ValueError("The frame is too small for this grid.")
        side = self.tile_size * grid
        x, y = (x1 + x2 - side) // 2, (y1 + y2 - side) // 2
        self.square_region = self.region = (x, y, x + side, y + side)
        self.original = frame[y:y + side, x:x + side].copy()
        self.board = self.original.copy()
        self.order = list(range(grid * grid))
        while self.solved():
            random.shuffle(self.order)
        self.dragging = None
        for pos in range(len(self.order)):
            self._paint_tile(pos)

    def _local_rect(self, pos):
        row, col = divmod(pos, self.grid)
        s = self.tile_size
        return col * s, row * s, (col + 1) * s, (row + 1) * s

    def _paint_tile(self, pos):
        x, y, right, bottom = self._local_rect(pos)
        sx, sy, sr, sb = self._local_rect(self.order[pos])
        self.board[y:bottom, x:right] = self.original[sy:sb, sx:sr]
        cv2.rectangle(self.board, (x, y), (right - 1, bottom - 1), C_WHITE, 1)

    def tile_rect(self, pos):
        x, y, right, bottom = self._local_rect(pos)
        ox, oy, _, _ = self.region
        return ox + x, oy + y, ox + right, oy + bottom

    def gp_at(self, px, py):
        x, y, right, bottom = self.region
        if x <= px < right and y <= py < bottom:
            return ((py - y) // self.tile_size) * self.grid + (px - x) // self.tile_size
        return None

    def start_drag(self, pos):
        self.dragging = self.order[pos]

    def finish_drag(self, pos):
        if self.dragging is None:
            return
        source = self.order.index(self.dragging)
        if source != pos:
            self.order[source], self.order[pos] = self.order[pos], self.order[source]
            self._paint_tile(source)
            self._paint_tile(pos)
        self.cancel_drag()

    def cancel_drag(self):
        self.dragging = None

    def draw(self, frame):
        x, y, right, bottom = self.region
        frame[y:bottom, x:right] = self.board
        cv2.rectangle(frame, (x, y), (right - 1, bottom - 1), C_GREEN, 2)
        if self.dragging is not None:
            self._outline(frame, self.order.index(self.dragging), C_CYAN)

    def _outline(self, frame, pos, color):
        x, y, right, bottom = self.tile_rect(pos)
        cv2.rectangle(frame, (x, y), (right - 1, bottom - 1), color, 3)

    def draw_hover(self, frame, pos):
        self._outline(frame, pos, C_ORANGE)

    def restore(self, frame):
        x, y, right, bottom = self.region
        frame[y:bottom, x:right] = self.original

    def solved(self):
        return all(pos == tile for pos, tile in enumerate(self.order))
