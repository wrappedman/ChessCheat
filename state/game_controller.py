"""Rule-validated mirrored-game workflow and session controller."""

from __future__ import annotations

import io
import time
from dataclasses import replace
from typing import Callable, Optional

import chess
import chess.pgn

from models import (
    EngineSettings,
    GamePhase,
    GameState,
    SavedGame,
    StatusKind,
    UserSide,
    WizardConfig,
)

ChangeCallback = Callable[[GameState], None]


class GameController:
    """Owns the current board, move history and game workflow.

    The human mirrors both their played moves and the opponent's moves. In
    normal mode, the engine advises only when it is the user's turn; in
    analysis mode the engine analyzes after either side moves.
    """

    def __init__(self, database, analysis_controller, on_change: Optional[ChangeCallback] = None):
        self.cpu_play = False
        self.database = database
        self.analysis = analysis_controller
        self.on_change = on_change
        initial = chess.Board()
        self.state = GameState(
            board=initial,
            history=[initial.copy(stack=True)],
        )

    def _set(self, **changes) -> None:
        self.state = replace(self.state, **changes)
        self._notify()

    def _notify(self) -> None:
        if self.on_change:
            try:
                self.on_change(self.state)
            except Exception:
                pass

    @staticmethod
    def _phase_for(board: chess.Board, side: UserSide) -> GamePhase:
        if board.outcome(claim_draw=False) is not None:
            return GamePhase.GAME_OVER
        if side == UserSide.ANALYSIS or board.turn == (
            chess.BLACK if side == UserSide.BLACK else chess.WHITE
        ):
            return GamePhase.USER_TURN
        return GamePhase.AWAITING_OPPONENT

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_match(self, config: WizardConfig) -> None:
        self.analysis.reset()
        self.analysis.engine.new_game()
        board = chess.Board()
        phase = self._phase_for(board, config.side)
        message = {
            UserSide.WHITE: "Your move as White. The engine is analyzing the opening.",
            UserSide.BLACK: "Waiting for your opponent's first move as White.",
            UserSide.ANALYSIS: "Analysis mode. Enter moves for either side.",
        }[config.side]
        self.state = GameState(
            board=board,
            user_side=config.side,
            phase=phase,
            history=[board.copy(stack=True)],
            settings=EngineSettings(
                search_time_ms=config.search_time_ms,
                elo=config.elo,
            ),
            is_flipped=config.side == UserSide.BLACK,
            session_active=True,
            started_at=time.time(),
            status_message=message,
            status_kind=StatusKind.SUCCESS,
        )
        self._notify()
        if self.state.should_analyze:
            self._request_analysis()
        else:
            self.analysis.clear_for_new_position(board.fen())

    def new_game(self) -> None:
        self.analysis.reset()
        board = chess.Board()
        self.state = GameState(
            board=board,
            history=[board.copy(stack=True)],
        )
        self._notify()

    # ------------------------------------------------------------------
    # Move input: click-to-move, drag/drop and suggested move
    # ------------------------------------------------------------------

    @property
    def is_cpu_turn(self) -> bool:
        return (self.cpu_play and self.state.session_active
                and not self.state.is_analysis_mode
                and self.state.phase == GamePhase.AWAITING_OPPONENT)

    def on_square_tap(self, square: chess.Square) -> None:
        if self.is_cpu_turn:
            return
        state = self.state
        if not state.session_active or state.pending_promotion is not None:
            return
        selected = state.selected_square
        if selected is not None:
            if self.request_move(selected, square):
                return
            piece = state.board.piece_at(square)
            if piece is not None and piece.color == state.board.turn:
                self._set(selected_square=square)
            else:
                self._set(selected_square=None)
            return
        piece = state.board.piece_at(square)
        if piece is not None and piece.color == state.board.turn:
            self._set(selected_square=square)

    def request_move(
        self,
        from_square: chess.Square,
        to_square: chess.Square,
        promotion: Optional[int] = None,
    ) -> bool:
        state = self.state
        if self.is_cpu_turn:
            return False
        if not state.session_active:
            return False
        if state.phase == GamePhase.GAME_OVER:
            self._set(status_message="Game over. Start a new match to continue.", status_kind=StatusKind.WARNING)
            return False
        if state.pending_promotion is not None:
            return False

        board = state.board
        piece = board.piece_at(from_square)
        if piece is None or piece.color != board.turn:
            self._set(
                status_message=f"It is {'White' if board.turn else 'Black'} to move. Select the correct piece.",
                status_kind=StatusKind.WARNING,
            )
            return False
        if not any(move.from_square == from_square and move.to_square == to_square for move in board.legal_moves):
            self._set(
                status_message=f"Illegal move: {chess.square_name(from_square)}{chess.square_name(to_square)}",
                status_kind=StatusKind.WARNING,
            )
            return False

        reaches_back_rank = piece.piece_type == chess.PAWN and chess.square_rank(to_square) in (0, 7)
        if reaches_back_rank and promotion is None:
            self._set(
                pending_promotion=(from_square, to_square),
                selected_square=None,
            )
            return False

        move = chess.Move(from_square, to_square, promotion=promotion)
        return self._apply_move(move)

    def complete_pending_promotion(self, piece_type: int) -> bool:
        pending = self.state.pending_promotion
        if pending is None:
            return False
        move = chess.Move(pending[0], pending[1], promotion=piece_type)
        return self._apply_move(move)

    def cancel_pending_promotion(self) -> None:
        self._set(pending_promotion=None)

    def _apply_move(self, move: chess.Move) -> bool:
        old = self.state
        board = old.board.copy(stack=True)
        if move not in board.legal_moves:
            return False
        san = board.san(move)
        board.push(move)

        history = [*old.history, board.copy(stack=True)]
        moves = [*old.moves, move]
        sans = [*old.san_history, san]
        outcome = board.outcome(claim_draw=False)
        phase = GamePhase.GAME_OVER if outcome else self._phase_for(board, old.user_side)
        self.state = replace(
            old,
            board=board,
            history=history,
            moves=moves,
            san_history=sans,
            redo_moves=[],
            selected_square=None,
            last_move=move,
            pending_promotion=None,
            phase=phase,
        )

        if outcome is not None:
            message = self._outcome_message(board)
            self.state = replace(self.state, status_message=message, status_kind=StatusKind.SUCCESS)
            self._save_game(board.result(claim_draw=False))
        elif phase == GamePhase.USER_TURN:
            message = (
                "Position updated — analyzing both sides."
                if self.state.is_analysis_mode
                else f"Your move ({'White' if board.turn else 'Black'}). Engine suggestion updating…"
            )
            self.state = replace(self.state, status_message=message, status_kind=StatusKind.INFO)
        else:
            message = f"Waiting for opponent's {'White' if board.turn else 'Black'} move… enter it on the board."
            if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
                message += " A draw claim is available."
            self.state = replace(self.state, status_message=message, status_kind=StatusKind.INFO)

        self._notify()
        if outcome is not None:
            self.analysis.clear_for_new_position(board.fen())
        elif phase == GamePhase.USER_TURN:
            self._request_analysis()
        else:
            self.analysis.clear_for_new_position(board.fen())
        return True

    def _outcome_message(self, board: chess.Board) -> str:
        outcome = board.outcome(claim_draw=False)
        if outcome is None:
            return "Game ended."
        result = board.result(claim_draw=False)
        termination = outcome.termination.name.replace("_", " ").title()
        if outcome.winner is None:
            return f"Draw by {termination.lower()} ({result})."
        winner = "White" if outcome.winner == chess.WHITE else "Black"
        you_won = not self.state.is_analysis_mode and outcome.winner == self.state.user_color
        suffix = " Well played!" if you_won else ""
        return f"{termination} — {winner} wins ({result}).{suffix}"

    def _request_analysis(self) -> None:
        self.analysis.request_analysis(
            self.state.board.copy(stack=True),
            self.state.settings,
            show_threats=(self.state.show_threats
                          and not (self.cpu_play and not self.state.is_analysis_mode)),
        )

    def play_suggested(self) -> None:
        move = self.analysis.state.suggested_move
        if move is None:
            self._set(status_message="No engine suggestion available yet.", status_kind=StatusKind.WARNING)
            return
        self.request_move(move.from_square, move.to_square, promotion=move.promotion)

    # ------------------------------------------------------------------
    # Draw claims, history, orientation and options
    # ------------------------------------------------------------------

    def can_claim_draw(self) -> bool:
        return self.state.session_active and self.state.board.can_claim_draw()

    def claim_draw(self) -> bool:
        board = self.state.board
        if not self.can_claim_draw():
            self._set(status_message="No draw claim is available in this position.", status_kind=StatusKind.WARNING)
            return False
        result = board.result(claim_draw=True)
        self.state = replace(
            self.state,
            phase=GamePhase.GAME_OVER,
            status_message=f"Draw claimed ({result}).",
            status_kind=StatusKind.SUCCESS,
        )
        self._notify()
        self.analysis.clear_for_new_position(board.fen())
        self._save_game(result)
        return True

    def undo(self) -> None:
        state = self.state
        if len(state.history) <= 1 or not state.moves:
            self._set(status_message="Nothing to undo.", status_kind=StatusKind.WARNING)
            return
        move = state.moves[-1]
        san = state.san_history[-1]
        board = state.history[-2].copy(stack=True)
        self.state = replace(
            state,
            board=board,
            history=state.history[:-1],
            moves=state.moves[:-1],
            san_history=state.san_history[:-1],
            redo_moves=[(move, san), *state.redo_moves],
            selected_square=None,
            last_move=state.moves[-2] if len(state.moves) > 1 else None,
            pending_promotion=None,
            phase=self._phase_for(board, state.user_side),
            status_message="Move taken back.",
            status_kind=StatusKind.INFO,
        )
        self._notify()
        if self.state.should_analyze:
            self._request_analysis()
        else:
            self.analysis.clear_for_new_position(board.fen())

    def redo(self) -> None:
        state = self.state
        if not state.redo_moves:
            self._set(status_message="Nothing to redo.", status_kind=StatusKind.WARNING)
            return
        move, san = state.redo_moves[0]
        board = state.board.copy(stack=True)
        if move not in board.legal_moves:
            self._set(status_message="This move can no longer be redone.", status_kind=StatusKind.WARNING)
            return
        board.push(move)
        self.state = replace(
            state,
            board=board,
            history=[*state.history, board.copy(stack=True)],
            moves=[*state.moves, move],
            san_history=[*state.san_history, san],
            redo_moves=state.redo_moves[1:],
            selected_square=None,
            last_move=move,
            phase=self._phase_for(board, state.user_side),
            status_message="Move redone.",
            status_kind=StatusKind.INFO,
        )
        if board.outcome(claim_draw=False):
            self.state = replace(
                self.state,
                phase=GamePhase.GAME_OVER,
                status_message=self._outcome_message(board),
            )
            self._save_game(board.result(claim_draw=False))
        self._notify()
        if self.state.should_analyze:
            self._request_analysis()
        else:
            self.analysis.clear_for_new_position(board.fen())

    def flip(self) -> None:
        self._set(is_flipped=not self.state.is_flipped)

    def toggle_threats(self) -> None:
        enabled = not self.state.show_threats
        self._set(show_threats=enabled)
        if enabled and self.state.should_analyze:
            self._request_analysis()
        elif not enabled:
            self.analysis.clear_threat()

    # ------------------------------------------------------------------
    # FEN, board editor and PGN
    # ------------------------------------------------------------------

    def set_fen(self, fen: str) -> bool:
        try:
            board = chess.Board(fen.strip())
            if not board.is_valid():
                raise ValueError("The position is not legal (check kings and pawns).")
        except (ValueError, TypeError) as exc:
            self._set(status_message=f"Invalid FEN: {exc}", status_kind=StatusKind.ERROR)
            return False
        return self._load_position(board, "Position loaded from FEN.")

    def set_board_from_editor(self, board: chess.Board) -> bool:
        if not board.is_valid():
            self._set(
                status_message="Invalid position: include exactly one king per side and remove impossible checks.",
                status_kind=StatusKind.ERROR,
            )
            return False
        return self._load_position(board, "Position applied from the board editor.")

    def _load_position(self, board: chess.Board, message: str) -> bool:
        board = board.copy(stack=True)
        side = self.state.user_side if self.state.session_active else UserSide.ANALYSIS
        self.analysis.reset()
        self.state = GameState(
            board=board,
            user_side=side,
            phase=self._phase_for(board, side),
            history=[board.copy(stack=True)],
            is_flipped=(side == UserSide.BLACK),
            show_threats=self.state.show_threats,
            status_message=message,
            status_kind=StatusKind.SUCCESS,
            settings=self.state.settings,
            session_active=True,
            started_at=time.time(),
        )
        self._notify()
        if self.state.should_analyze:
            self._request_analysis()
        else:
            self.analysis.clear_for_new_position(board.fen())
        return True

    def import_pgn(self, pgn_text: str) -> bool:
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if game is None:
                raise ValueError("No PGN game was found in the text.")
            if game.errors:
                raise ValueError(str(game.errors[0]))
            root_board = game.board()
            if not root_board.is_valid():
                raise ValueError("The PGN starting position is invalid.")
            board = root_board.copy(stack=True)
            history = [board.copy(stack=True)]
            moves: list[chess.Move] = []
            sans: list[str] = []
            for move in game.mainline_moves():
                if move not in board.legal_moves:
                    raise ValueError("The PGN contains an illegal move.")
                sans.append(board.san(move))
                moves.append(move)
                board.push(move)
                history.append(board.copy(stack=True))
        except (ValueError, TypeError, AssertionError) as exc:
            self._set(status_message=f"PGN import failed: {exc}", status_kind=StatusKind.ERROR)
            return False

        self.analysis.reset()
        self.state = GameState(
            board=board,
            user_side=UserSide.ANALYSIS,
            phase=self._phase_for(board, UserSide.ANALYSIS),
            history=history,
            moves=moves,
            san_history=sans,
            last_move=moves[-1] if moves else None,
            settings=self.state.settings,
            show_threats=self.state.show_threats,
            session_active=True,
            started_at=time.time(),
            status_message=f"Imported {len(moves)} half-moves from PGN.",
            status_kind=StatusKind.SUCCESS,
        )
        self._notify()
        if self.state.should_analyze:
            self._request_analysis()
        else:
            self.analysis.clear_for_new_position(board.fen())
        return True

    def export_pgn(self, result_override: Optional[str] = None) -> str:
        state = self.state
        game = chess.pgn.Game()
        game.headers["Event"] = "ChessCheat Session"
        game.headers["Site"] = "ChessCheat Desktop"
        game.headers["Date"] = time.strftime("%Y.%m.%d")
        game.headers["Round"] = "-"
        game.headers["White"] = "You" if state.user_side == UserSide.WHITE else "Opponent"
        game.headers["Black"] = "You" if state.user_side == UserSide.BLACK else "Opponent"
        game.headers["Result"] = result_override or self._current_result()
        if state.user_side == UserSide.ANALYSIS:
            game.headers["Annotator"] = "ChessCheat Analysis"

        start_board = state.history[0] if state.history else chess.Board()
        if start_board.fen() != chess.STARTING_FEN:
            game.headers["SetUp"] = "1"
            game.headers["FEN"] = start_board.fen()

        node = game
        for move in state.moves:
            node = node.add_variation(move)
        exporter = chess.pgn.StringExporter(
            headers=True, variations=False, comments=False
        )
        return game.accept(exporter)

    def _current_result(self) -> str:
        if self.state.phase != GamePhase.GAME_OVER:
            return "*"
        return self.state.board.result(claim_draw=True)

    def save_current_game(self) -> bool:
        if not self.state.moves:
            self._set(status_message="Nothing to save yet — play some moves first.", status_kind=StatusKind.WARNING)
            return False
        self._save_game(self._current_result())
        self._set(status_message="Game saved to the local database.", status_kind=StatusKind.SUCCESS)
        return True

    def _save_game(self, result: str) -> None:
        try:
            best = self.analysis.state.best_line
            self.database.insert_saved_game(
                SavedGame(
                    pgn=self.export_pgn(result_override=result),
                    user_color=self.state.user_side.name,
                    result=result,
                    final_eval_cp=best.score_cp if best else None,
                    created_at=int(time.time() * 1000),
                )
            )
        except Exception as exc:
            self._set(
                status_message=f"Could not save game: {exc}",
                status_kind=StatusKind.ERROR,
            )
