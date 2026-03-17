# -*- coding: utf-8 -*-
"""
hand_gesture.py
---------------
Hand detection runs in a dedicated background thread so the game loop
never blocks waiting for MediaPipe inference.

The game loop calls:
    detector = HandDetector()
    detector.start()
    ...
    hands = detector.get_hands()   # always returns instantly
    ...
    detector.stop()
"""

import os
import threading
import cv2
import numpy as np

os.environ["GLOG_minloglevel"]      = "3"
os.environ["TF_CPP_MIN_LOG_LEVEL"]  = "3"
os.environ["MEDIAPIPE_DISABLE_GPU"] = "1"

from mediapipe import Image as MpImage, ImageFormat
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from constants import (
    MODEL_FILE,
    PINCH_THRESHOLD,
    THUMB_TIP, INDEX_TIP, INDEX_PIP,
    HAND_CONNECTIONS,
)


class HandDetector:
    """
    Wraps MediaPipe in a background thread.

    Usage:
        det = HandDetector()
        det.start()
        while running:
            det.submit(bgr_frame)       # non-blocking, always returns immediately
            hands = det.get_hands()     # latest result, always returns immediately
        det.stop()
    """

    def __init__(self):
        opts = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_FILE),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.40,
            min_hand_presence_confidence=0.40,
            min_tracking_confidence=0.40,
        )
        self._lmk      = mp_vision.HandLandmarker.create_from_options(opts)
        self._lock     = threading.Lock()
        self._frame    = None          # latest BGR frame waiting to be processed
        self._hands    = {}            # latest detection result
        self._has_new  = threading.Event()
        self._stop     = threading.Event()
        self._thread   = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._has_new.set()            # unblock the thread if it's waiting
        self._thread.join(timeout=3)
        try:
            self._lmk.close()
        except Exception:
            pass

    def submit(self, bgr_frame):
        """Give the detector a new frame. Non-blocking — drops if busy."""
        with self._lock:
            self._frame = bgr_frame
        self._has_new.set()

    def get_hands(self):
        """Return the latest hands dict. Always returns immediately."""
        with self._lock:
            return dict(self._hands)

    # ── Background thread ──────────────────────────────────────────────────

    def _run(self):
        while not self._stop.is_set():
            self._has_new.wait()        # sleep until a new frame arrives
            self._has_new.clear()

            if self._stop.is_set():
                break

            with self._lock:
                frame = self._frame
                self._frame = None

            if frame is None:
                continue

            try:
                result = self._detect(frame)
            except Exception as e:
                print(f"[WARN] HandDetector: {e}", flush=True)
                result = {}

            with self._lock:
                self._hands = result

    def _detect(self, bgr_frame):
        fh, fw = bgr_frame.shape[:2]

        # Center-crop to square → avoids NORM_RECT projection warning
        side  = min(fh, fw)
        x_off = (fw - side) // 2
        y_off = (fh - side) // 2
        crop  = bgr_frame[y_off:y_off+side, x_off:x_off+side]

        # Resize to 192×192 (model's native palm-detector size)
        small = cv2.resize(crop, (192, 192), interpolation=cv2.INTER_LINEAR)
        rgb   = np.ascontiguousarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))

        mp_img = MpImage(image_format=ImageFormat.SRGB, data=rgb)
        result = self._lmk.detect(mp_img)

        hands = {}
        if not result or not result.hand_landmarks:
            return hands

        for lms, hedness in zip(result.hand_landmarks, result.handedness):
            label = hedness[0].category_name

            # Remap from crop-normalised → full-frame-normalised
            remapped = []
            for lm in lms:
                class _LM:
                    pass
                obj     = _LM()
                obj.x   = (lm.x * side + x_off) / fw
                obj.y   = (lm.y * side + y_off) / fh
                obj.z   = lm.z
                remapped.append(obj)

            pinching = _is_pinching(remapped)
            tip      = _tip_mid(remapped, fw, fh)
            hands[label] = (remapped, pinching, tip)

        return hands


# ── Gesture helpers ────────────────────────────────────────────────────────────

def _norm_dist(a, b):
    return ((a.x - b.x)**2 + (a.y - b.y)**2) ** 0.5

def _is_pinching(lms):
    return _norm_dist(lms[THUMB_TIP], lms[INDEX_TIP]) < PINCH_THRESHOLD

def _tip_mid(lms, w, h):
    t = lms[THUMB_TIP]; i = lms[INDEX_TIP]
    return int((t.x+i.x)/2*w), int((t.y+i.y)/2*h)

def is_fist(lms):
    return lms[INDEX_TIP].y > lms[INDEX_PIP].y

def draw_skeleton(frame, lms, w, h):
    def px(lm): return int(lm.x*w), int(lm.y*h)
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, px(lms[a]), px(lms[b]), (90, 90, 90), 1)
    for lm in lms:
        cv2.circle(frame, px(lm), 3, (160, 160, 160), -1)
