"""
fix_deps.py
-----------
Fixes MediaPipe hand detection on Windows.

MediaPipe 0.10.21 has a broken _build_landmarker_result on Windows.
The last known-good version is 0.10.14.

    python fix_deps.py
"""
import subprocess, sys

print("[1/4] Current versions:")
r = subprocess.run([sys.executable, "-m", "pip", "show", "mediapipe", "protobuf"],
                   capture_output=True, text=True)
print(r.stdout)

print("[2/4] Restoring compatible protobuf first...")
subprocess.run([sys.executable, "-m", "pip", "install",
                "protobuf>=4.25.3,<5", "--quiet"], check=False)

print("[3/4] Installing MediaPipe 0.10.14 (last stable Windows build)...")
result = subprocess.run([
    sys.executable, "-m", "pip", "install",
    "mediapipe==0.10.14",
    "--force-reinstall",
    "--quiet"
], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("[WARN] 0.10.14 failed, trying 0.10.11...")
    result2 = subprocess.run([
        sys.executable, "-m", "pip", "install",
        "mediapipe==0.10.11",
        "--force-reinstall",
        "--quiet"
    ], capture_output=True, text=True)
    print(result2.stdout)
    if result2.returncode != 0:
        print(result2.stderr)
        print("[ERROR] Could not install. Try manually:\n  pip install mediapipe==0.10.14")
        sys.exit(1)

print("[4/4] Verifying fix...")
test = subprocess.run([sys.executable, "-c", """
import os
os.environ['GLOG_minloglevel'] = '3'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import numpy as np
from mediapipe import Image as MpImage, ImageFormat
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
opts = mp_vision.HandLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path='hand_landmarker.task'),
    running_mode=mp_vision.RunningMode.IMAGE, num_hands=2)
lmk = mp_vision.HandLandmarker.create_from_options(opts)
blank = np.zeros((192,192,3), dtype=np.uint8)
result = lmk.detect(MpImage(image_format=ImageFormat.SRGB, data=blank))
lmk.close()
print('OK - MediaPipe working correctly')
"""], capture_output=True, text=True, cwd=r"C:\Users\sarth\OneDrive\Desktop\test2\backend")
print(test.stdout.strip() or test.stderr.strip())

import subprocess as sp
ver = sp.run([sys.executable,"-m","pip","show","mediapipe"],
             capture_output=True, text=True)
for line in ver.stdout.splitlines():
    if line.startswith("Version"):
        print(f"Installed: {line}")
        break

print("\nDone. Run: python debug_detection.py  to verify, then: python server.py")
