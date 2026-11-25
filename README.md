# SnapSlide

A webcam-based sliding puzzle game that uses computer vision and hand gestures to interact with puzzle tiles in real time. Built using React and Python, it integrates MediaPipe hand tracking, gesture recognition, and live video streaming.

---

## Prerequisites

- Python 3.10+
- Node.js
- npm
- Webcam

---

## How to Run

### 1. Clone the repository

```bash
git clone https://github.com/your-username/SnapSlide.git
cd SnapSlide
```

### 2. Set up the Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate

# Install backend dependencies
pip install fastapi uvicorn opencv-python numpy mediapipe

# Start the backend server
python server.py
```

Backend runs at: `http://localhost:8000`

### 3. Set up the Frontend

Open a new terminal:

```bash
cd frontend

# Install node dependencies
npm install

# Start the development server
npm run dev
```

Opens in browser at: **http://localhost:5173**

---

## Project Structure

```text
SnapSlide/
│
├── backend/
│   ├── server.py                 # FastAPI server and game endpoints
│   ├── main.py                  # Standalone game entry point
│   ├── constants.py              # Game configuration and constants
│   ├── hand_gesture.py           # Hand tracking and gesture recognition
│   ├── frame_selection.py         # Frame processing and selection
│   ├── model_loader.py            # Hand tracking model loader
│   ├── puzzle.py                  # Sliding puzzle logic
│   ├── renderer.py                # Game rendering
│   └── hand_landmarker.task       # MediaPipe hand tracking model
│
├── frontend/
│   ├── public/                   # Static assets
│   ├── src/
│   │   ├── App.jsx               # Root React component
│   │   ├── App.css               # Application styling
│   │   ├── main.jsx              # React entry point
│   │   └── index.css              # Global styles
│   ├── index.html                # HTML entry point
│   ├── package.json               # Frontend dependencies
│   └── vite.config.js              # Vite configuration
│
└── README.md
```

---

## How It Works

- **Hand Tracking** — MediaPipe detects and tracks hand landmarks through the webcam.
- **Gesture Recognition** — Hand gestures, including pinch interactions, are used to control puzzle tiles.
- **Puzzle Generation** — Generates sliding puzzles with multiple grid sizes and difficulty levels.
- **Interactive Gameplay** — Players interact with puzzle tiles using hand movements.
- **Live Video Streaming** — Streams webcam and processed frames to the frontend.
- **Real-Time Updates** — WebSocket communication synchronizes game states between the backend and frontend.
- **Puzzle Rendering** — OpenCV processes and renders the game visuals.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI, Uvicorn |
| Computer Vision | OpenCV, MediaPipe, NumPy |
| Communication | REST API, WebSockets, MJPEG Streaming |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Returns game and server status |
| `/api/start` | POST | Starts a puzzle |
| `/api/stop` | POST | Stops the game |
| `/video_feed` | GET | Streams webcam/game frames |
| `/ws/state` | WebSocket | Sends real-time game-state updates |

---

## Standalone Mode

The project also supports running the puzzle directly through OpenCV without the web interface.

```bash
cd backend

# Activate virtual environment
.venv\Scripts\activate

# Run standalone game
python main.py
```

---

> ⚠️ Webcam access is required for gesture-based gameplay. If the camera is unavailable, close other applications using it or run the backend directly on Windows instead of WSL.
