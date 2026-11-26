"""Regression tests for the camera-to-score flow using synthetic hand samples."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

import leaderboard
import server
from game import Game
from hand_gesture import is_fist


def landmarks(curled, angle=0):
    points = [(0, 0)] * 21
    for finger, base in enumerate((5, 9, 13, 17)):
        x = (finger - 1.5) * 0.025
        offsets = [(0, -.10), (0, -.15), (.012, -.12), (.005, -.095)] if finger in curled else [
            (0, -.10), (0, -.15), (0, -.18), (0, -.205)]
        for i, (dx, y) in enumerate(offsets):
            points[base + i] = x + dx, y
    c, s = np.cos(angle), np.sin(angle)
    return [SimpleNamespace(x=.5 + x*c - y*s, y=.5 + x*s + y*c, z=0) for x, y in points]


class GameTests(unittest.TestCase):
    def test_rotation_and_one_bent_finger(self):
        for angle in (0, 1.4, 3.1):
            self.assertFalse(is_fist(landmarks({0}, angle)))
            self.assertFalse(is_fist(landmarks({1, 2, 3}, angle)))
            self.assertTrue(is_fist(landmarks({0, 1, 2}, angle)))

    def test_round_trip(self):
        image = np.random.default_rng(5).integers(0, 256, (360, 640, 3), dtype=np.uint8)
        payload = cv2.imencode(".jpg", image)[1].tobytes()
        open_hand, fist = landmarks(set()), landmarks({0, 1, 2, 3})
        client = TestClient(server.app)
        with tempfile.TemporaryDirectory() as directory, patch.object(
            leaderboard, "DB_PATH", Path(directory) / "scores.db"
        ):
            for size in (3, 4, 5):
                for peek in (False, True):
                    with self.subTest(size=size, peek=peek):
                        game = Game(size)
                        with patch.object(server, "Game", return_value=game), patch.object(
                            server, "open_detector"
                        ) as detector, client.websocket_connect(f"/ws/game?difficulty={size}x{size}") as ws:
                            status = ws.receive_json()
                            self.assertEqual(status["grid"], size)
                            clock = 10.

                            def frame(hands, seconds=.05, state=None):
                                nonlocal clock
                                clock += seconds
                                detector.return_value.detect.return_value = hands
                                with patch.object(server, "time", SimpleNamespace(monotonic=lambda: clock)), patch(
                                    "game.time", SimpleNamespace(monotonic=lambda: clock)
                                ):
                                    ws.send_bytes(payload)
                                    if state:
                                        self.assertEqual(ws.receive_json()["state"], state)
                                    self.assertTrue(ws.receive_bytes().startswith(b'\xff\xd8'))

                            def act(action, **args):
                                ws.send_json(dict(action=action, round_id=game.round_id, **args))
                                return ws.receive_json()

                            self.assertIn("action_error", act("score", player="Early"))
                            corners = {"Left": (open_hand, True, (110, 45)),
                                       "Right": (open_hand, True, (530, 302))}
                            for _ in range(4):
                                frame(corners)
                            frame({"Left": (fist, True, (130, 60)), "Right": (open_hand, False, (530, 302))}, state="CONFIRM")
                            # Curling keeps thumb and index together. A missed frame
                            # mid-hold must not discard the selected corners.
                            for hands in ({"Left": (fist, True, (130, 60))}, {}, {"Left": (fist, True, (132, 61))}):
                                frame(hands)
                            frame({"Left": (fist, True, (130, 60))}, seconds=.12, state="SHUFFLE")
                            puzzle = game.puzzle
                            self.assertEqual(len(puzzle.order), size * size)
                            self.assertNotEqual(puzzle.order, list(range(size * size)))
                            x, y, right, bottom = puzzle.region
                            raw = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
                            np.testing.assert_array_equal(puzzle.original, raw[y:bottom, x:right])
                            self.assertEqual(puzzle.gp_at(right-1, bottom-1), size*size-1)
                            self.assertIsNone(puzzle.gp_at(right, bottom-1))
                            if peek:
                                order = puzzle.order.copy()
                                preview = act("solution")
                                self.assertTrue(preview["solution"].startswith("data:image/jpeg;base64,"))
                                self.assertTrue(preview["assisted"])
                                self.assertEqual(puzzle.order, order)
                                self.assertTrue(act("hide_solution")["solution_hidden"])
                            frame({}, seconds=.8, state="PLAY")
                            for i in range(size * size):
                                if puzzle.order[i] == i:
                                    continue
                                src = puzzle.tile_rect(puzzle.order.index(i))
                                dst = puzzle.tile_rect(i)
                                frame({"Right": (open_hand, True, src[:2])})
                                will_finish = sum(k != v for k, v in enumerate(puzzle.order)) == 2
                                frame({"Right": (open_hand, False, dst[:2])}, state="SOLVED" if will_finish else None)
                            self.assertEqual(game.state, "SOLVED")
                            if peek:
                                self.assertIn("action_error", act("score", player="Practice"))
                            else:
                                self.assertIn("action_error", act("score", player="   "))
                                self.assertTrue(act("score", player=" Player ")["score_saved"])
                                self.assertTrue(act("score", player="Duplicate")["score_saved"])
                rows = client.get(f"/api/leaderboard?difficulty={size}x{size}").json()
                self.assertEqual([row["player"] for row in rows], ["Player"])
                self.assertGreater(rows[0]["elapsed_ms"], 0)


if __name__ == "__main__":
    unittest.main()
