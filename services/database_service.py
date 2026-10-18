"""SQLite persistence for openings, saved sessions and analysis cache."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

import chess

from models import OpeningBookEntry, PositionCacheEntry, SavedGame
from services.opening_book_seed import OPENING_SEEDS


class DatabaseService:
    """Local SQLite brain of ChessCheat.

    Tables:
      * ``openings_book``: ECO-coded positions and book moves.
      * ``saved_games``: complete PGN sessions.
      * ``position_cache``: analyzed FENs answered instantly.
      * ``settings``: small key/value store for user preferences.

    The connection is shared safely by the UI and engine callback threads.
    """

    DB_NAME = "chesscheat_brain.db"

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.path = Path(db_path) if db_path else self.default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            str(self.path),
            timeout=15,
            check_same_thread=False,
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._create_schema()
        self._seed_openings()

    @classmethod
    def default_path(cls) -> Path:
        """Choose a writable per-user data location on Windows and Linux."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ChessCheat"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "ChessCheat"
        return base / cls.DB_NAME

    def _create_schema(self) -> None:
        with self._lock, self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS openings_book (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eco TEXT NOT NULL,
                    name TEXT NOT NULL,
                    fen TEXT NOT NULL,
                    san TEXT NOT NULL,
                    ply INTEGER NOT NULL,
                    line TEXT NOT NULL,
                    UNIQUE(fen, eco, san)
                );
                CREATE INDEX IF NOT EXISTS idx_openings_fen
                    ON openings_book(fen);

                CREATE TABLE IF NOT EXISTS saved_games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pgn TEXT NOT NULL,
                    user_color TEXT NOT NULL,
                    result TEXT NOT NULL,
                    final_eval_cp INTEGER,
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS position_cache (
                    fen TEXT PRIMARY KEY,
                    best_move_san TEXT NOT NULL,
                    score_cp INTEGER,
                    score_mate INTEGER,
                    depth INTEGER NOT NULL,
                    pv TEXT NOT NULL DEFAULT '[]',
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def _seed_openings(self) -> None:
        """Walk the bundled SAN lines and seed every position once."""
        with self._lock:
            row = self._db.execute("SELECT COUNT(*) AS n FROM openings_book").fetchone()
            if row and row["n"] > 0:
                return

            rows = []
            for eco, name, san_moves in OPENING_SEEDS:
                board = chess.Board()
                played: list[str] = []
                for ply, san in enumerate(san_moves):
                    try:
                        move = board.parse_san(san)
                    except (ValueError, AssertionError):
                        # A bad book continuation must not prevent the rest
                        # of the application from starting.
                        break
                    before_fen = board.fen()
                    line = self._format_san_line(played + [move.uci()])
                    rows.append((eco, name, before_fen, san, ply, line))
                    played.append(move.uci())
                    board.push(move)

            with self._db:
                self._db.executemany(
                    """INSERT OR IGNORE INTO openings_book
                       (eco, name, fen, san, ply, line)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    rows,
                )

    @staticmethod
    def _format_san_line(uci_moves: list[str]) -> str:
        """Format a list of UCI moves as a human-friendly PGN line."""
        board = chess.Board()
        tokens = []
        for index, uci in enumerate(uci_moves):
            try:
                move = chess.Move.from_uci(uci)
                san = board.san(move)
            except (ValueError, AssertionError):
                break
            if board.turn == chess.WHITE:
                tokens.append(f"{board.fullmove_number}. {san}")
            else:
                tokens.append(san)
            board.push(move)
        return " ".join(tokens)

    def find_opening_by_fen(self, fen: str) -> Optional[OpeningBookEntry]:
        # The untouched starting position is not an opening name; several
        # unrelated first moves share that FEN, so labeling it would be random.
        if fen == chess.STARTING_FEN:
            return None
        with self._lock:
            rows = self._db.execute(
                """SELECT eco, name, fen, san, ply, line
                   FROM openings_book WHERE fen = ?
                   ORDER BY ply, eco""",
                (fen,),
            ).fetchall()
        if not rows:
            return None
        # Shared prefixes can belong to several named openings. Report only
        # the unambiguous family (e.g. "Sicilian Defense"), never label the
        # position with a variation whose defining moves have not happened.
        labels = {row["name"].split(",", 1)[0] for row in rows}
        families = {
            label.removesuffix(" Defense") for label in labels
        }
        if len(families) != 1:
            return None
        row = rows[0]
        ecos = {candidate["eco"] for candidate in rows}
        eco = next(iter(ecos)) if len(ecos) == 1 else None
        # Prefer the more descriptive spelling when a family contains both
        # e.g. "Caro-Kann" and "Caro-Kann Defense" seed labels.
        name = max(labels, key=len)
        return OpeningBookEntry(
            eco=eco, name=name, fen=row["fen"],
            san=row["san"], ply=row["ply"], line=row["line"],
        )

    def get_cached_analysis(self, fen: str) -> Optional[PositionCacheEntry]:
        with self._lock:
            row = self._db.execute(
                """SELECT fen, best_move_san, score_cp, score_mate,
                          depth, pv, updated_at
                   FROM position_cache WHERE fen = ?""",
                (fen,),
            ).fetchone()
        if row is None:
            return None
        try:
            pv_sans = json.loads(row["pv"] or "[]")
        except (TypeError, json.JSONDecodeError):
            pv_sans = []
        return PositionCacheEntry(
            fen=row["fen"],
            best_move_san=row["best_move_san"],
            score_cp=row["score_cp"],
            score_mate=row["score_mate"],
            depth=row["depth"],
            pv_sans=pv_sans if isinstance(pv_sans, list) else [],
            updated_at=row["updated_at"],
        )

    def put_cached_analysis(self, entry: PositionCacheEntry) -> None:
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO position_cache
                   (fen, best_move_san, score_cp, score_mate, depth, pv, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(fen) DO UPDATE SET
                     best_move_san=excluded.best_move_san,
                     score_cp=excluded.score_cp,
                     score_mate=excluded.score_mate,
                     depth=excluded.depth,
                     pv=excluded.pv,
                     updated_at=excluded.updated_at""",
                (
                    entry.fen, entry.best_move_san, entry.score_cp,
                    entry.score_mate, entry.depth,
                    json.dumps(entry.pv_sans, ensure_ascii=False),
                    entry.updated_at or int(time.time() * 1000),
                ),
            )

    def insert_saved_game(self, game: SavedGame) -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                """INSERT INTO saved_games
                   (pgn, user_color, result, final_eval_cp, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    game.pgn, game.user_color, game.result,
                    game.final_eval_cp,
                    game.created_at or int(time.time() * 1000),
                ),
            )
            return int(cursor.lastrowid)

    def load_saved_games(self, limit: int = 200) -> list[SavedGame]:
        with self._lock:
            rows = self._db.execute(
                """SELECT id, pgn, user_color, result, final_eval_cp, created_at
                   FROM saved_games ORDER BY created_at DESC LIMIT ?""",
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [
            SavedGame(
                id=row["id"], pgn=row["pgn"], user_color=row["user_color"],
                result=row["result"], final_eval_cp=row["final_eval_cp"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_setting(self, key: str) -> Optional[str]:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO settings(key, value) VALUES(?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, value),
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()
