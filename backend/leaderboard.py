from contextlib import closing
from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).with_name("leaderboard.sqlite3")


def _connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS scores (
        round_id TEXT PRIMARY KEY, player TEXT NOT NULL,
        grid INTEGER NOT NULL, elapsed_ms INTEGER NOT NULL
    )""")
    return db


def save_score(game, player):
    player = player.strip()
    if not 1 <= len(player) <= 32:
        raise ValueError("Enter a name between 1 and 32 characters.")
    if game.state != "SOLVED" or game.assisted:
        raise ValueError("Only puzzles solved without viewing the solution can be ranked.")
    with closing(_connect()) as db, db:
        db.execute("INSERT INTO scores VALUES (?, ?, ?, ?) ON CONFLICT(round_id) DO NOTHING",
                   (game.round_id, player, game.grid, game.status()["elapsed_ms"]))
    game.saved = True


def fastest(grid):
    with closing(_connect()) as db:
        rows = db.execute("""SELECT player, grid, elapsed_ms FROM scores
                             WHERE grid = ? ORDER BY elapsed_ms, rowid LIMIT 10""", (grid,))
        return [dict(row) for row in rows]
