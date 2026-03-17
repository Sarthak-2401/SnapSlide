# -*- coding: utf-8 -*-
"""
model_loader.py
---------------
Downloads the MediaPipe hand-landmarker model file if it is not already
present on disk.

Public API
~~~~~~~~~~
    ensure_model()   -> None   (exits the process on failure)
"""

import os
import sys
import urllib.request

from constants import MODEL_FILE, MODEL_URL


def ensure_model():
    """Download MODEL_FILE from MODEL_URL if it does not already exist."""
    if os.path.exists(MODEL_FILE):
        return

    print(f"[INFO] Downloading hand landmarker model -> '{MODEL_FILE}' ...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)
        print("[INFO] Download complete.")
    except Exception as exc:
        print(f"[ERROR] Download failed: {exc}")
        print(f"  Please download manually from:\n  {MODEL_URL}")
        sys.exit(1)
