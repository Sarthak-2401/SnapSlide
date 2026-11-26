"""Standalone desktop player. Run python backend/main.py."""
import tkinter as tk
from tkinter import messagebox, simpledialog
import sqlite3

import cv2
import numpy as np

from constants import WIN_NAME
from game import Game
from hand_gesture import HandDetector
from leaderboard import fastest, save_score
from model_loader import ensure_model


def main():
    root = tk.Tk()
    root.withdraw()
    grid = simpledialog.askinteger("SnapSlide", "Grid size (3, 4 or 5)", initialvalue=3,
                                   minvalue=3, maxvalue=5, parent=root)
    if grid is None or not messagebox.askyesno("SnapSlide", "Allow SnapSlide to use your webcam for this session?", parent=root):
        root.destroy()
        return

    cap = cv2.VideoCapture(0)
    detector = None
    try:
        if not cap.isOpened():
            messagebox.showerror("SnapSlide", "Could not open the webcam.", parent=root)
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ensure_model()
        detector = HandDetector()
        detector.start()
        game = Game(grid)
        cv2.namedWindow(WIN_NAME)
        actions = []
        buttons = []

        def click(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONUP and y < 42:
                actions.extend(label for start, end, label in buttons if start <= x < end)

        cv2.setMouseCallback(WIN_NAME, click)
        while cv2.getWindowProperty(WIN_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            ok, frame = cap.read()
            if not ok:
                break
            camera = cv2.flip(frame, 1)
            detector.submit(camera)
            view = game.render(camera, *detector.snapshot())
            if game.previewing:
                game.puzzle.restore(view)
            bar = np.full((42, view.shape[1], 3), 30, dtype=np.uint8)
            labels = ["Reset", "Leaderboard", "Quit"]
            if game.puzzle:
                labels.append("Hide solution" if game.previewing else "Show solution")
            if game.state == "SOLVED" and not (game.assisted or game.saved):
                labels.append("Save score")
            buttons.clear()
            x = 4
            for label in labels:
                width = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0] + 18
                buttons.append((x, x + width, label))
                cv2.putText(bar, label, (x + 8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 240, 220), 1)
                x += width
            cv2.imshow(WIN_NAME, np.vstack((bar, view)))
            key = cv2.waitKey(1) & 0xff
            if key in (27, ord("q")) or "Quit" in actions:
                break
            if key == ord("r") or "Reset" in actions:
                game.reset()
            if "Show solution" in actions and game.puzzle:
                game.solution()
            if "Hide solution" in actions:
                game.previewing = False
            if "Save score" in actions:
                player = simpledialog.askstring("Save score", "Leaderboard name (up to 32 characters)", parent=root)
                if player is not None:
                    try:
                        save_score(game, player)
                    except (ValueError, sqlite3.Error) as exc:
                        messagebox.showerror("Save score", str(exc), parent=root)
            if "Leaderboard" in actions:
                rows = fastest(grid)
                lines = [f"{i}. {r['player']}   {r['elapsed_ms'] / 1000:.2f}s" for i, r in enumerate(rows, 1)]
                messagebox.showinfo(f"{grid}×{grid} leaderboard", "\n".join(lines) or "No scores yet.", parent=root)
            actions.clear()
    finally:
        cap.release()
        if detector:
            detector.stop()
        cv2.destroyAllWindows()
        root.destroy()


if __name__ == "__main__":
    main()
