"""Fast, headless regression tests for chess, persistence and UCI parsing."""

from __future__ import annotations

import os
import tempfile
import unittest

import chess

from models import (
    AnalysisState,
    EngineSettings,
    GamePhase,
    PositionCacheEntry,
    UserSide,
    WizardConfig,
)
from services.database_service import DatabaseService
from services.uci_engine_service import UciEngineService
from state.game_controller import GameController


class _FakeEngine:
    def new_game(self) -> None:
        pass

    def cancel(self) -> None:
        pass

    def set_settings(self, _settings: EngineSettings) -> None:
        pass


class _FakeAnalysis:
    def __init__(self) -> None:
        self.engine = _FakeEngine()
        self.state = AnalysisState()

    def reset(self) -> None:
        self.state = AnalysisState()

    def request_analysis(self, *_args, **_kwargs) -> None:
        pass

    def clear_for_new_position(self, *_args) -> None:
        pass

    def clear_threat(self) -> None:
        pass


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.unlink(self.db_path)
        self.database = DatabaseService(self.db_path)
        self.analysis = _FakeAnalysis()
        self.game = GameController(self.database, self.analysis)

    def tearDown(self) -> None:
        self.database.close()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except FileNotFoundError:
                pass

    def test_openings_are_seeded_and_start_position_has_no_name(self) -> None:
        count = self.database._db.execute(
            "SELECT COUNT(*) FROM openings_book"
        ).fetchone()[0]
        self.assertGreaterEqual(count, 400)
        self.assertIsNone(self.database.find_opening_by_fen(chess.STARTING_FEN))

    def test_mirrored_turn_workflow_san_and_pgn(self) -> None:
        self.game.start_match(WizardConfig(UserSide.WHITE, 500, 2200))
        self.assertEqual(self.game.state.phase, GamePhase.USER_TURN)

        self.assertTrue(self.game.request_move(chess.E2, chess.E4))
        self.assertEqual(self.game.state.san_history, ["e4"])
        self.assertEqual(self.game.state.phase, GamePhase.AWAITING_OPPONENT)

        self.assertTrue(self.game.request_move(chess.E7, chess.E5))
        self.assertEqual(self.game.state.san_history, ["e4", "e5"])
        self.assertEqual(self.game.state.phase, GamePhase.USER_TURN)

        pgn = self.game.export_pgn()
        self.assertIn("1. e4 e5", pgn)
        imported = GameController(self.database, self.analysis)
        self.assertTrue(imported.import_pgn(pgn))
        self.assertEqual(imported.state.san_history, ["e4", "e5"])

    def test_undo_and_redo_preserve_move_history(self) -> None:
        self.game.start_match(WizardConfig(UserSide.ANALYSIS, 500, 2200))
        self.game.request_move(chess.E2, chess.E4)
        self.game.request_move(chess.E7, chess.E5)
        self.game.undo()
        self.assertEqual(self.game.state.san_history, ["e4"])
        self.game.redo()
        self.assertEqual(self.game.state.san_history, ["e4", "e5"])

    def test_promotion_requires_choice_and_applies_queen(self) -> None:
        self.assertTrue(
            self.game.set_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        )
        self.assertFalse(self.game.request_move(chess.A7, chess.A8))
        self.assertEqual(
            self.game.state.pending_promotion, (chess.A7, chess.A8)
        )
        self.assertTrue(self.game.complete_pending_promotion(chess.QUEEN))
        piece = self.game.state.board.piece_at(chess.A8)
        self.assertIsNotNone(piece)
        self.assertEqual(piece.piece_type, chess.QUEEN)

    def test_black_starts_waiting_and_board_is_flipped(self) -> None:
        self.game.start_match(WizardConfig(UserSide.BLACK, 2000, 2600))
        self.assertEqual(self.game.state.phase, GamePhase.AWAITING_OPPONENT)
        self.assertTrue(self.game.state.is_flipped)

    def test_position_cache_round_trip(self) -> None:
        entry = PositionCacheEntry(
            fen=chess.STARTING_FEN,
            best_move_san="e4",
            depth=20,
            score_cp=35,
            pv_sans=["e4", "e5", "Nf3"],
            updated_at=1234,
        )
        self.database.put_cached_analysis(entry)
        cached = self.database.get_cached_analysis(chess.STARTING_FEN)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.best_move_san, "e4")
        self.assertEqual(cached.pv_sans, ["e4", "e5", "Nf3"])
        self.assertEqual(cached.depth, 20)

    def test_claimable_fifty_move_draw(self) -> None:
        self.assertTrue(
            self.game.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 100 51")
        )
        self.assertTrue(self.game.can_claim_draw())
        self.assertTrue(self.game.claim_draw())
        self.assertEqual(self.game.state.phase, GamePhase.GAME_OVER)
        self.assertEqual(self.game.state.board.result(claim_draw=True), "1/2-1/2")

    def test_uci_parser_extracts_multi_pv_and_score(self) -> None:
        parsed = UciEngineService._parse_info(
            "info depth 21 seldepth 30 multipv 2 score cp -42 "
            "nodes 12345 nps 100000 time 200 pv e2e4 e7e5",
            0,
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.depth, 21)
        self.assertEqual(parsed.multipv, 2)
        self.assertEqual(parsed.score_cp, -42)
        self.assertEqual(parsed.uci_pv, ["e2e4", "e7e5"])


if __name__ == "__main__":
    unittest.main()
