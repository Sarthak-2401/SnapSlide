# -*- coding: utf-8 -*-
"""
renderer.py
-----------
All OpenCV drawing helpers — dark-theme UI matching the reference screenshot.

Layout (1280x720 canvas):
  ┌─────────────────────────────────────────────┐
  │  LIVE PUZZLE  (lime title, top-centre)       │  <- top bar
  │  subtitle hint text                          │
  ├─────────────────────────────────────────────┤
  │                                             ││
  │        live camera feed + puzzle            ││ <- phase badge (top-right)
  │                                             ││
  ├─────────────────────────────────────────────┤
  │  timer bubble (bottom-centre)    reset icon  │  <- bottom bar
  └─────────────────────────────────────────────┘
"""

import cv2
import numpy as np
import time

from constants import (
    C_LIME, C_WHITE, C_BLACK, C_GRAY, C_DARK_GRAY,
    C_YELLOW, C_CYAN, C_GREEN, C_ORANGE, C_RED,
    BG_COLOR, PANEL_COLOR, BORDER_COLOR, C_BADGE_BG,
    WIN_NAME, CANVAS_W, CANVAS_H,
)

FONT_TITLE  = cv2.FONT_HERSHEY_DUPLEX
FONT_BODY   = cv2.FONT_HERSHEY_SIMPLEX


# ── Internal helpers ──────────────────────────────────────────────────────────

def _text(frame, text, xy, font=FONT_BODY, scale=0.55,
          color=C_WHITE, thick=1, shadow=False):
    x, y = xy
    if shadow:
        cv2.putText(frame, text, (x+1, y+1), font, scale, C_BLACK, thick+1)
    cv2.putText(frame, text, (x, y), font, scale, color, thick)


def _text_centered(frame, text, y, font=FONT_BODY,
                   scale=0.55, color=C_WHITE, thick=1):
    (tw, _), _ = cv2.getTextSize(text, font, scale, thick)
    x = (frame.shape[1] - tw) // 2
    cv2.putText(frame, text, (x+1, y+1), font, scale, C_BLACK, thick+1)
    cv2.putText(frame, text, (x,   y),   font, scale, color,   thick)


def _filled_rect(frame, x1, y1, x2, y2, color, alpha=1.0):
    if alpha >= 1.0:
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
    else:
        roi = frame[max(0, y1):y2 + 1, max(0, x1):x2 + 1]
        if roi.size:
            cv2.addWeighted(roi, 1 - alpha, np.full_like(roi, color), alpha, 0, roi)


def _pill(frame, cx, cy, w, h, color, fill=True, thickness=1):
    """Draw a rounded-rectangle (pill) centred at (cx, cy)."""
    r  = h // 2
    x1, y1 = cx - w // 2, cy - h // 2
    x2, y2 = cx + w // 2, cy + h // 2
    if fill:
        cv2.rectangle(frame, (x1 + r, y1), (x2 - r, y2), color, -1)
        cv2.rectangle(frame, (x1, y1 + r), (x2, y2 - r), color, -1)
        for ccx, ccy in [(x1+r,y1+r),(x2-r,y1+r),(x1+r,y2-r),(x2-r,y2-r)]:
            cv2.circle(frame, (ccx, ccy), r, color, -1)
    else:
        cv2.rectangle(frame, (x1 + r, y1), (x2 - r, y2), color, thickness)
        cv2.rectangle(frame, (x1, y1 + r), (x2, y2 - r), color, thickness)
        for ccx, ccy in [(x1+r,y1+r),(x2-r,y1+r),(x1+r,y2-r),(x2-r,y2-r)]:
            cv2.circle(frame, (ccx, ccy), r, color, thickness)


# ═══════════════════════════════════════════════════════════════════════════════
# Canvas setup  (called once per frame before anything is drawn)
# ═══════════════════════════════════════════════════════════════════════════════

def make_canvas(camera_frame):
    """
    Composite the camera feed onto a dark background canvas.
    Returns the canvas (same size as camera_frame).
    """
    fh, fw = camera_frame.shape[:2]
    canvas = camera_frame.copy()

    # Slight vignette around camera area
    margin = 4
    cv2.rectangle(canvas, (0, 0), (fw - 1, fh - 1), BG_COLOR, margin * 2)

    # Thin border around the whole frame
    cv2.rectangle(canvas, (margin, margin),
                  (fw - margin, fh - margin), BORDER_COLOR, 1)
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
# Top bar  — title + subtitle
# ═══════════════════════════════════════════════════════════════════════════════

def draw_top_bar(frame, subtitle=""):
    fw = frame.shape[1]

    # Semi-transparent dark strip
    _filled_rect(frame, 0, 0, fw, 72, (10, 10, 10), alpha=0.75)
    cv2.line(frame, (0, 72), (fw, 72), BORDER_COLOR, 1)

    # Title  "LIVE PUZZLE"  spaced out, lime
    title = "LIVE PUZZLE"
    spaced = "  ".join(title)          # extra letter-spacing trick
    _text_centered(frame, spaced, 44,
                   font=FONT_TITLE, scale=1.0, color=C_LIME, thick=2)

    # Subtitle
    if subtitle:
        _text_centered(frame, subtitle, 66,
                       scale=0.48, color=C_GRAY, thick=1)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase badge  (top-right corner)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_phase_badge(frame, phase_label, instructions):
    """
    Dark green badge in top-right showing current phase + instruction list.
    phase_label  : e.g. "PHASE 1: SELECT" / "PHASE 2: SOLVE"
    instructions : list of short strings
    """
    fw = frame.shape[1]
    bw, bh = 190, 22 + 18 * len(instructions)
    bx = fw - bw - 10
    by = 82

    # Badge background
    _filled_rect(frame, bx, by, bx + bw, by + bh, C_BADGE_BG, alpha=0.85)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), C_LIME, 1)

    # Phase label
    _text(frame, phase_label, (bx + 6, by + 14),
          scale=0.42, color=C_LIME, thick=1)

    # Instructions
    for i, line in enumerate(instructions):
        _text(frame, line, (bx + 6, by + 28 + i * 18),
              scale=0.38, color=C_WHITE, thick=1)


# ═══════════════════════════════════════════════════════════════════════════════
# Timer bubble  (bottom-centre)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_timer(frame, elapsed_secs):
    fh, fw = frame.shape[:2]
    mins = int(elapsed_secs) // 60
    secs = int(elapsed_secs) % 60
    label = f"  {mins}:{secs:02d}"

    cx = fw // 2
    cy = fh - 22

    # Pill background
    _pill(frame, cx, cy, 80, 28, (30, 30, 30))
    _pill(frame, cx, cy, 80, 28, BORDER_COLOR, fill=False)

    # Clock icon dot
    cv2.circle(frame, (cx - 28, cy), 7, C_DARK_GRAY, -1)
    cv2.circle(frame, (cx - 28, cy), 7, C_GRAY, 1)
    cv2.line(frame, (cx - 28, cy), (cx - 28, cy - 4), C_WHITE, 1)
    cv2.line(frame, (cx - 28, cy), (cx - 25, cy), C_WHITE, 1)

    # Time text
    _text(frame, label, (cx - 22, cy + 5), scale=0.48, color=C_WHITE, thick=1)


# ═══════════════════════════════════════════════════════════════════════════════
# Reset icon  (bottom-left)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_reset_icon(frame):
    fh = frame.shape[0]
    cx, cy = 35, fh - 22
    cv2.circle(frame, (cx, cy), 14, (40, 40, 40), -1)
    cv2.circle(frame, (cx, cy), 14, C_DARK_GRAY, 1)
    # Simple circular arrow approximation
    cv2.ellipse(frame, (cx, cy), (7, 7), 0, 30, 300, C_GRAY, 1)
    # Arrow head
    ang = np.radians(30)
    ax = int(cx + 7 * np.cos(ang))
    ay = int(cy - 7 * np.sin(ang))
    cv2.circle(frame, (ax, ay), 2, C_GRAY, -1)


# ═══════════════════════════════════════════════════════════════════════════════
# Bottom hint  (bottom-right, very small)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_bottom_hint(frame, text):
    fh, fw = frame.shape[:2]
    (tw, _), _ = cv2.getTextSize(text, FONT_BODY, 0.35, 1)
    cv2.putText(frame, text, (fw - tw - 10, fh - 8),
                FONT_BODY, 0.35, C_DARK_GRAY, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Shuffle progress bar  (replaces old bottom bar)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_shuffle_bar(frame, progress):
    fh, fw = frame.shape[:2]
    bx = fw // 2 - 140
    by = fh - 48
    bw = int(280 * progress)
    # Track
    cv2.rectangle(frame, (bx, by), (bx + 280, by + 12), (40, 40, 40), -1)
    # Fill
    cv2.rectangle(frame, (bx, by), (bx + bw, by + 12), C_LIME, -1)
    _text_centered(frame, "Shuffling...", fh - 60, scale=0.55, color=C_GRAY)


# ═══════════════════════════════════════════════════════════════════════════════
# Solved overlay
# ═══════════════════════════════════════════════════════════════════════════════

def draw_solved_overlay(frame, region, elapsed):
    fh, fw = frame.shape[:2]
    x1, y1, x2, y2 = region

    alpha = 0.45 + 0.12 * abs(np.sin(elapsed * 3))
    _filled_rect(frame, x1, y1, x2, y2, C_LIME, 1 - alpha)
    cv2.rectangle(frame, (x1, y1), (x2, y2), C_LIME, 3)

    _text_centered(frame, "PUZZLE  SOLVED!", fh // 2 - 14,
                   font=FONT_TITLE, scale=1.4, color=C_LIME, thick=3)
    _text_centered(frame, "Hold both fists to play again",
                   fh // 2 + 38, scale=0.55, color=C_WHITE)


# ═══════════════════════════════════════════════════════════════════════════════
# Pinch cursor
# ═══════════════════════════════════════════════════════════════════════════════

def draw_pinch_cursor(frame, tip, color=C_CYAN):
    cv2.circle(frame, tip, 10, color,   -1)
    cv2.circle(frame, tip, 12, C_WHITE,  1)
