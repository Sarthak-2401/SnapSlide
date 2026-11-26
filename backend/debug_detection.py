"""
debug_detection.py
------------------
Run this standalone to test if MediaPipe can detect your hands at all.
It opens your webcam, runs detection every frame, and prints results.

    python debug_detection.py

Watch the terminal. When you put your hand in front of the camera you should see:
  [HAND] Left  pinching=False tip=(640, 360)
  [HAND] Right pinching=False tip=(700, 400)

If you see nothing, the detection pipeline itself is broken.
If you see hands but the game doesn't work, the issue is in server.py.
"""

import os, sys, time
os.environ["GLOG_minloglevel"]      = "3"
os.environ["TF_CPP_MIN_LOG_LEVEL"]  = "3"
os.environ["MEDIAPIPE_DISABLE_GPU"] = "1"

import cv2
import numpy as np

# ── Locate model ──────────────────────────────────────────────────────────────
MODEL = "hand_landmarker.task"
if not os.path.exists(MODEL):
    print(f"[ERROR] {MODEL} not found in {os.getcwd()}")
    print("  Run this script from the backend folder (same folder as main.py)")
    sys.exit(1)

from mediapipe import Image as MpImage, ImageFormat
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

PINCH_THRESHOLD = 0.052
THUMB_TIP = 4
INDEX_TIP = 8

# ── Build landmarker ──────────────────────────────────────────────────────────
print("[INFO] Loading MediaPipe model...")
opts = mp_vision.HandLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path=MODEL),
    running_mode=mp_vision.RunningMode.IMAGE,
    num_hands=2,
    min_hand_detection_confidence=0.4,
    min_hand_presence_confidence=0.4,
    min_tracking_confidence=0.4,
)
lmk = mp_vision.HandLandmarker.create_from_options(opts)
print("[INFO] Model loaded OK")

# ── Open camera ───────────────────────────────────────────────────────────────
print("[INFO] Opening camera...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Cannot open camera")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
for _ in range(5): cap.read()   # warm up

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"[INFO] Camera opened: {actual_w}x{actual_h}")
print("[INFO] Show your hand to the camera. Press Ctrl+C to stop.\n")

frame_n = 0
t0 = time.time()

try:
    while True:
        ok, raw = cap.read()
        if not ok or raw is None:
            print("[WARN] Bad frame")
            continue

        frame_n += 1
        cam = cv2.flip(raw, 1)
        fh, fw = cam.shape[:2]

        # ── Center-crop to square then resize to 192x192 ──────────────────
        side  = min(fh, fw)
        x_off = (fw - side) // 2
        y_off = (fh - side) // 2
        crop  = cam[y_off:y_off+side, x_off:x_off+side]
        small = cv2.resize(crop, (192, 192), interpolation=cv2.INTER_LINEAR)
        rgb   = np.ascontiguousarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))

        # ── Detect ────────────────────────────────────────────────────────
        mp_img = MpImage(image_format=ImageFormat.SRGB, data=rgb)
        try:
            result = lmk.detect(mp_img)
        except AttributeError as e:
            if "GetMessageClass" in str(e):
                print("\n[ERROR] protobuf version incompatible with MediaPipe!")
                print("  Fix: python fix_deps.py")
                print("  Or:  pip install protobuf==3.20.3 --force-reinstall")
                sys.exit(1)
            raise

        # ── Print result every frame ──────────────────────────────────────
        if result.hand_landmarks:
            for lms, hedness in zip(result.hand_landmarks, result.handedness):
                label = hedness[0].category_name

                # Remap to full frame
                lm_list = []
                for lm in lms:
                    fx = (lm.x * side + x_off) / fw
                    fy = (lm.y * side + y_off) / fh
                    lm_list.append((fx, fy))

                t  = lm_list[THUMB_TIP]
                ix = lm_list[INDEX_TIP]
                dist     = ((t[0]-ix[0])**2 + (t[1]-ix[1])**2)**0.5
                pinching = dist < PINCH_THRESHOLD
                tip_px   = (int((t[0]+ix[0])/2 * fw),
                            int((t[1]+ix[1])/2 * fh))

                print(f"[HAND] {label:5s}  pinching={str(pinching):5s}  "
                      f"dist={dist:.4f}  tip={tip_px}  frame={frame_n}",
                      flush=True)
        else:
            # Print a dot every 30 frames so you know it's running
            if frame_n % 30 == 0:
                fps = frame_n / (time.time() - t0)
                print(f"[----] No hands  frame={frame_n}  fps={fps:.1f}",
                      flush=True)

except KeyboardInterrupt:
    pass
finally:
    lmk.close()
    cap.release()
    print("\n[INFO] Done")
