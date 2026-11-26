# SnapSlide

Turn a webcam snapshot into a picture puzzle. Frame the picture with your hands, close a fist to capture it, then pinch and swap tiles to put it back together. Play on a 3×3, 4×4, or 5×5 grid and see how your time compares with other solvers on the same difficulty.

---

## Prerequisites

- Python 3.11 (64-bit)
- Node.js 22.12 or later and npm for the browser version
- A webcam and a browser with camera access
- Tkinter and a graphical desktop for standalone mode

---

## How to Run

### 1. Open the project

If you already have SnapSlide, open a terminal in the folder that contains `backend` and `frontend`. To get a fresh copy, run the following commands.

```bash
git clone https://github.com/Sarthak-2401/SnapSlide.git
cd SnapSlide
```

### 2. Start the backend

Create and activate a Python environment from the project root. On Windows, use PowerShell.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux, use these commands instead.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

With the environment active, install the dependencies and start the game server.

```bash
python -m pip install "fastapi==0.111.0" "uvicorn[standard]==0.30.6" "websockets==12.0" "mediapipe==0.10.14" "numpy==1.26.4" "opencv-contrib-python==4.10.0.84" "jax==0.4.35" "jaxlib==0.4.35"
python backend/server.py
```

Keep this terminal open. To check that the backend is ready, open the [local 3×3 leaderboard](http://localhost:8000/api/leaderboard?difficulty=3x3). A fresh database returns `[]`.

### 3. Start the frontend

Open a **second terminal** in the project root.

```bash
cd frontend
npm ci
npm run dev
```

Open the **Local** address printed by Vite, usually [http://localhost:5173](http://localhost:5173). Keep both terminals running while you play. For hosting the game on Render with a Supabase leaderboard, follow the [deployment guide](DEPLOYMENT.md).

---

## Project Structure

```text
SnapSlide/
├── backend/
│   ├── server.py              # FastAPI and WebSocket entry point
│   ├── main.py                # Standalone desktop player
│   ├── game.py                # Round state, timer, and gesture controls
│   ├── frame_selection.py     # Corner selection and locking
│   ├── hand_gesture.py        # Hand tracking, pinches, and fists
│   ├── puzzle.py              # Tile layout, shuffling, and swaps
│   ├── renderer.py            # Camera overlays and timer display
│   ├── leaderboard.py         # Score storage and rankings
│   └── hand_landmarker.task   # Bundled MediaPipe model
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Difficulty selection and camera permission
│   │   ├── GameViewer.jsx     # Live game, solution preview, and score form
│   │   ├── Leaderboard.jsx    # Top Solvers table
│   │   └── gameApi.js         # Backend address and time formatting
│   ├── package.json
│   └── vite.config.js
├── DEPLOYMENT.md
└── README.md
```

---

## How It Works

1. **Choose a difficulty.** Select **Beginner (3×3)**, **Standard (4×4)**, or **Pro (5×5)**. Start the game and allow webcam access.
2. **Frame your picture.** Pinch with your thumb and index finger on each hand to mark opposite corners. Hold each pinch briefly, then release to lock that corner. Once both corners are locked, close either fist briefly to capture the picture.
3. **Swap tiles.** The timer starts after the shuffle. Pinch a tile, move your hand over any other tile, and release to swap the two. Restore the original picture to stop the timer.
4. **Preview the solution or save a score.** **Show solution** displays the original picture. Opening it before you finish makes the round a practice round. After an unassisted solve, enter your name and click **Save score**. **Top Solvers** lists the ten fastest saved times for each grid size.

The local leaderboard lives in `backend/leaderboard.sqlite3`. The browser and desktop players share this file, so restarting either one preserves saved scores.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI, Uvicorn |
| Hand tracking and rendering | MediaPipe, OpenCV, NumPy |
| Communication | HTTP for rankings and WebSocket for JPEG frames and JSON game messages |
| Local score storage | SQLite |

---

## API Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/leaderboard?difficulty=3x3` | GET | Returns up to ten scores, fastest first. Each entry has `player`, `grid`, and `elapsed_ms`. |
| `/ws/game?difficulty=3x3` | WebSocket | Starts a game session. The browser sends webcam frames and player actions. The server returns the rendered frames and round state. |

Both endpoints accept `3x3`, `4x4`, or `5x5` and default to `3x3`.

---

## Standalone Mode

To play in an OpenCV window, activate the same Python environment and run this command from the project root.

```bash
python backend/main.py
```

Choose a grid size and allow webcam access in the desktop dialog. Use the window toolbar to preview the solution, open the leaderboard, or save an eligible score. Press **R** to reset or **Q** or **Esc** to quit.

> In the browser version, use localhost or HTTPS so the browser can request camera access. During play, the browser sends webcam frames to the game server for hand tracking. **Stop game** releases the camera.
