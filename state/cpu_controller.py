"""Optional opponent play; engine results are applied on the UI thread."""

import queue

import chess

from models import GamePhase, StatusKind


class CpuController:
    def __init__(self, game):
        self.game = game
        self._position = None
        self._generation = 0
        self._results = queue.SimpleQueue()

    def sync(self):
        """Called by the UI after normal game/analysis updates have finished."""
        state = self.game.state
        position = state.board if self.game.is_cpu_turn else None
        if position is self._position:
            return
        self._generation += 1
        generation = self._generation
        was_active = self._position is not None
        self._position = position
        if position is None:
            if was_active:
                self.game.analysis.engine.cancel()
                if state.phase == GamePhase.AWAITING_OPPONENT:
                    self.game._set(
                        status_message="Waiting for opponent’s move… enter it on the board.",
                        status_kind=StatusKind.INFO,
                    )
                if state.should_analyze:
                    self.game._request_analysis()
            return

        self.game.analysis.clear_for_new_position(position.fen())
        self.game._set(
            selected_square=None,
            pending_promotion=None,
            status_message="CPU is thinking…",
            status_kind=StatusKind.INFO,
        )
        engine = self.game.analysis.engine
        engine.set_settings(state.settings)
        engine.analyze(
            position.fen(), multi_pv=1,
            movetime_ms=state.settings.search_time_ms,
            callback=lambda result: self._results.put((generation, position, result, None))
            if result.is_complete else None,
            on_error=lambda error: self._results.put((generation, position, None, error)),
        )

    def poll(self):
        """Drain results on Tk's main thread, discarding obsolete searches."""
        while True:
            try:
                generation, position, result, error = self._results.get_nowait()
            except queue.Empty:
                return
            if (generation != self._generation or not self.game.is_cpu_turn
                    or self.game.state.board is not position):
                continue
            if error is None:
                try:
                    move = chess.Move.from_uci(result.best_move_uci or "")
                    if move not in position.legal_moves:
                        raise ValueError("CPU returned an illegal move.")
                except ValueError as exc:
                    error = str(exc) or "CPU did not return a valid move."
            if error is not None:
                self.game._set(status_message=f"CPU: {error}", status_kind=StatusKind.ERROR)
                continue
            # The search is finished: do not cancel the user's new analysis.
            self._position = None
            self._generation += 1
            self.game._apply_move(move)
