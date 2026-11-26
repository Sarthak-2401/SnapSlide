# -*- coding: utf-8 -*-
"""
constants.py
------------
All shared configuration: grid size, colours, landmark indices,
MediaPipe model details, and hand-connection topology.
"""

# ── Grid ──────────────────────────────────────────────────────────────────────
GRID = 3

# ── Window ───────────────────────────────────────────────────────────────────
WIN_NAME    = "LIVE PUZZLE"
CANVAS_W    = 1280
CANVAS_H    = 720

# ── Canvas chrome (dark surround matching reference UI) ───────────────────────
BG_COLOR        = (18,  18,  18)   # near-black background
PANEL_COLOR     = (28,  28,  28)   # slightly lighter panel
BORDER_COLOR    = (50,  50,  50)   # subtle border

# ── Puzzle frame padding (px from edges of camera feed area) ─────────────────
FEED_PAD_TOP    = 90    # space for title bar
FEED_PAD_BOTTOM = 30
FEED_PAD_LEFT   = 60
FEED_PAD_RIGHT  = 60

# ── MediaPipe model ───────────────────────────────────────────────────────────
from pathlib import Path

MODEL_FILE = str(Path(__file__).with_name("hand_landmarker.task"))
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# ── Gesture thresholds ────────────────────────────────────────────────────────
PINCH_THRESHOLD = 0.052

# ── Hand landmark indices ─────────────────────────────────────────────────────
THUMB_TIP  = 4
INDEX_TIP  = 8
INDEX_PIP  = 6

# ── Accent colours (BGR) ─────────────────────────────────────────────────────
C_LIME      = (57,  255,  20)   # bright lime  – matches reference title
C_WHITE     = (255, 255, 255)
C_BLACK     = (0,   0,   0)
C_GRAY      = (140, 140, 140)
C_DARK_GRAY = (60,  60,  60)
C_YELLOW    = (0,   220, 220)   # subtitle / hint text
C_CYAN      = (220, 220,   0)   # pinch cursor / selected tile tint
C_GREEN     = (57,  255,  20)   # solved overlay (same as lime)
C_RED       = (60,   60, 220)   # right-hand corner dot
C_ORANGE    = (0,   165, 255)   # hover / shuffle bar
C_BADGE_BG  = (30,  60,  10)    # dark green badge background

# ── Legacy aliases so other modules don't break ───────────────────────────────
C_GREEN  = C_LIME

# ── Hand skeleton ─────────────────────────────────────────────────────────────
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(0,17),(17,18),(18,19),(19,20),
]
