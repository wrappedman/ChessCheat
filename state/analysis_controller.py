"""Opening-book, SQLite-cache and live Stockfish analysis pipeline."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Optional

import chess

from models import (
    AnalysisState,
    AnalysisStatus,
    EngineAnalysis,
    EngineSettings,
    EvalLine,
    OpeningBookEntry,
    PositionCacheEntry,
)

AnalysisChangeCallback = Callable[[AnalysisState], None]


class AnalysisController:
    """Converts UCI snapshots to UI lines and protects against stale results."""

    def __init__(self, database, engine, on_change: Optional[AnalysisChangeCallback] = None) -> None:
        self.database = database
        self.engine = engine
        self.on_change = on_change
        self.state = AnalysisState()
        self._lock = threading.RLock()
        self._generation = 0

    def _publish(self, state: AnalysisState) -> None:
        with self._lock:
            self.state = state
        self._notify_change(state)

    def _publish_if_current(self, generation: int, state: AnalysisState) -> bool:
        with self._lock:
            if generation != self._generation:
                return False
            self.state = state
        self._notify_change(state)
        return True

    def _notify_change(self, state: AnalysisState) -> None:
        if self.on_change:
            try:
                self.on_change(state)
            except Exception:
                pass

    def request_analysis(
        self,
        board: chess.Board,
        settings: EngineSettings,
        *,
        show_threats: bool = True,
    ) -> None:
        """Publish book/cache hints immediately, then stream Stockfish lines."""
        position = board.copy(stack=True)
        fen = position.fen()
        with self._lock:
            self._generation += 1
            generation = self._generation

        opening = self._safe_opening_lookup(fen)
        cached = self._safe_cache_lookup(fen)
        cached_lines: list[EvalLine] = []
        if cached and cached.depth >= 1:
            try:
                move = position.parse_san(cached.best_move_san)
                if move in position.legal_moves:
                    cached_lines.append(
                        EvalLine(
                            rank=1,
                            move=move,
                            san=cached.best_move_san,
                            san_pv=list(cached.pv_sans),
                            depth=cached.depth,
                            score_cp=cached.score_cp,
                            score_mate=cached.score_mate,
                        )
                    )
            except (ValueError, AssertionError):
                cached_lines = []

        # Cached and book information reaches the UI before the engine starts.
        if not self._publish_if_current(
            generation,
            AnalysisState(
                status=AnalysisStatus.THINKING,
                fen=fen,
                lines=cached_lines,
                opening_name=opening.name if opening else None,
                opening_eco=opening.eco if opening else None,
                suggested_move=cached_lines[0].move if cached_lines else None,
                suggested_san=cached_lines[0].san if cached_lines else None,
                from_cache=bool(cached_lines),
            ),
        ):
            return

        self.engine.set_settings(settings)
        self.engine.analyze(
            fen,
            multi_pv=settings.multi_pv,
            movetime_ms=settings.search_time_ms,
            callback=lambda snapshot: self._handle_main_snapshot(
                generation, position, opening, snapshot, settings, show_threats
            ),
            on_error=lambda message: self._handle_error(generation, fen, message),
        )

    def _handle_main_snapshot(
        self,
        generation: int,
        position: chess.Board,
        opening: Optional[OpeningBookEntry],
        snapshot: EngineAnalysis,
        settings: EngineSettings,
        show_threats: bool,
    ) -> None:
        with self._lock:
            if generation != self._generation:
                return
            current = self.state
        lines = self._convert_lines(snapshot, position)
        # Some UCI engines can return bestmove before a useful PV (e.g. mate
        # or a terminal position); retain the previous cache line if needed.
        if not lines and current.from_cache and current.fen == snapshot.fen:
            lines = current.lines

        best = lines[0] if lines else None
        published = self._publish_if_current(
            generation,
            AnalysisState(
                status=AnalysisStatus.READY if snapshot.is_complete else AnalysisStatus.THINKING,
                fen=snapshot.fen,
                lines=lines,
                opening_name=opening.name if opening else None,
                opening_eco=opening.eco if opening else None,
                suggested_move=best.move if best else None,
                suggested_san=best.san if best else None,
                threat_move=current.threat_move if current.fen == snapshot.fen else None,
                threat_san=current.threat_san if current.fen == snapshot.fen else None,
                from_cache=False,
            ),
        )
        if not published:
            return

        if not snapshot.is_complete or best is None:
            return

        self._save_cache(snapshot.fen, best)
        if show_threats:
            self._request_threat(generation, position, best.move, settings)

    def _request_threat(
        self,
        generation: int,
        position: chess.Board,
        best_move: chess.Move,
        settings: EngineSettings,
    ) -> None:
        if not self._is_current(generation) or best_move not in position.legal_moves:
            return
        after = position.copy(stack=True)
        after.push(best_move)
        if after.outcome(claim_draw=False) is not None:
            return
        duration = max(300, min(settings.search_time_ms // 3, settings.search_time_ms))
        self.engine.analyze(
            after.fen(),
            multi_pv=1,
            movetime_ms=duration,
            callback=lambda snapshot: self._handle_threat_snapshot(
                generation, after, snapshot
            ),
            on_error=lambda _message: None,
        )

    def _handle_threat_snapshot(
        self,
        generation: int,
        position: chess.Board,
        snapshot: EngineAnalysis,
    ) -> None:
        with self._lock:
            if generation != self._generation:
                return
            current = self.state
        lines = self._convert_lines(snapshot, position)
        if not lines:
            return
        self._publish_if_current(
            generation,
            replace(
                current,
                threat_move=lines[0].move,
                threat_san=lines[0].san,
            ),
        )

    def _convert_lines(self, analysis: EngineAnalysis, root: chess.Board) -> list[EvalLine]:
        converted: list[EvalLine] = []
        for raw in sorted(analysis.lines, key=lambda line: line.multipv):
            if not raw.uci_pv:
                continue
            board = root.copy(stack=True)
            san_pv: list[str] = []
            first_move: Optional[chess.Move] = None
            first_san: Optional[str] = None
            for uci in raw.uci_pv[:6]:
                try:
                    move = chess.Move.from_uci(uci)
                except ValueError:
                    break
                if move not in board.legal_moves:
                    break
                san = board.san(move)
                if first_move is None:
                    first_move, first_san = move, san
                san_pv.append(san)
                board.push(move)
            if first_move is None or first_san is None:
                continue
            converted.append(
                EvalLine(
                    rank=raw.multipv,
                    move=first_move,
                    san=first_san,
                    san_pv=san_pv,
                    depth=raw.depth,
                    score_cp=raw.score_cp,
                    score_mate=raw.score_mate,
                    nodes=raw.nodes,
                    nps=raw.nps,
                    time_ms=raw.time_ms,
                )
            )
        return converted[:5]

    def _save_cache(self, fen: str, best: EvalLine) -> None:
        try:
            self.database.put_cached_analysis(
                PositionCacheEntry(
                    fen=fen,
                    best_move_san=best.san,
                    depth=best.depth,
                    score_cp=best.score_cp,
                    score_mate=best.score_mate,
                    pv_sans=list(best.san_pv),
                    updated_at=int(time.time() * 1000),
                )
            )
        except Exception:
            # A cache write failure should never interrupt an active game.
            pass

    def _safe_opening_lookup(self, fen: str) -> Optional[OpeningBookEntry]:
        try:
            return self.database.find_opening_by_fen(fen)
        except Exception:
            return None

    def _safe_cache_lookup(self, fen: str) -> Optional[PositionCacheEntry]:
        try:
            return self.database.get_cached_analysis(fen)
        except Exception:
            return None

    def _handle_error(self, generation: int, fen: str, message: str) -> None:
        with self._lock:
            if generation != self._generation:
                return
            current = self.state
        unavailable = "not found" in message.lower() or "could not launch" in message.lower()
        self._publish_if_current(
            generation,
            replace(
                current,
                status=(
                    AnalysisStatus.ENGINE_UNAVAILABLE
                    if unavailable else AnalysisStatus.ERROR
                ),
                fen=fen,
                message=message,
            ),
        )

    def _is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation

    def clear_for_new_position(self, fen: str) -> None:
        with self._lock:
            self._generation += 1
        self.engine.cancel()
        self._publish(AnalysisState(fen=fen))

    def clear_threat(self) -> None:
        self._publish(replace(self.state, threat_move=None, threat_san=None))

    def reset(self) -> None:
        with self._lock:
            self._generation += 1
        self.engine.cancel()
        self._publish(AnalysisState())
