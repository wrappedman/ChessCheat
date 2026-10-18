"""CPU play regression tests without Tk or an installed Stockfish binary."""
import tempfile
import unittest
from pathlib import Path

import chess

from models import EngineAnalysis, EngineLine, UserSide, WizardConfig
from services.database_service import DatabaseService
from state.analysis_controller import AnalysisController
from state.cpu_controller import CpuController
from state.game_controller import GameController


class FakeEngine:
    def __init__(self):
        self.jobs = []

    def new_game(self):
        pass

    def cancel(self):
        pass

    def set_settings(self, settings):
        pass

    def analyze(self, fen, **kwargs):
        self.jobs.append((fen, kwargs))

    def finish(self, move, index=-1):
        fen, job = self.jobs[index]
        job['callback'](EngineAnalysis(
            fen=fen, best_move_uci=move, is_complete=True,
            lines=[EngineLine(multipv=1, depth=10, score_cp=20, uci_pv=[move])],
        ))


class CpuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = DatabaseService(str(Path(self.temp.name) / 'test.db'))
        self.engine = FakeEngine()
        self.analysis = AnalysisController(self.db, self.engine)
        self.game = GameController(self.db, self.analysis)
        self.cpu = CpuController(self.game)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def start(self, side, enabled=True):
        self.game.cpu_play = enabled
        self.game.start_match(WizardConfig(side, 500, 2200))
        self.cpu.sync()

    def test_disabled_keeps_manual_opponent(self):
        self.start(UserSide.WHITE, False)
        self.game.request_move(chess.E2, chess.E4)
        count = len(self.engine.jobs)
        self.cpu.sync()
        self.assertEqual(len(self.engine.jobs), count)
        self.assertTrue(self.game.request_move(chess.E7, chess.E5))

    def test_cpu_reply_and_user_suggestions_without_threat_search(self):
        self.start(UserSide.WHITE)
        self.engine.finish('e2e4')
        self.assertEqual(self.analysis.state.suggested_san, 'e4')
        self.assertEqual(len(self.engine.jobs), 1)
        self.game.play_suggested()
        self.cpu.sync()
        self.assertIsNone(self.analysis.state.suggested_move)
        self.assertFalse(self.game.request_move(chess.E7, chess.E5))
        self.engine.finish('e7e5')
        self.assertEqual(self.game.state.san_history, ['e4'])
        self.cpu.poll()
        self.assertEqual(self.game.state.san_history, ['e4', 'e5'])
        self.engine.finish('g1f3')
        self.assertEqual(self.analysis.state.suggested_san, 'Nf3')
        self.assertEqual(len(self.engine.jobs), 3)

    def test_black_cpu_opens_and_partial_results_do_not_move(self):
        self.start(UserSide.BLACK)
        fen, job = self.engine.jobs[-1]
        job['callback'](EngineAnalysis(fen=fen, best_move_uci='e2e4'))
        self.cpu.poll()
        self.assertEqual(self.game.state.san_history, [])
        self.engine.finish('e2e4')
        self.cpu.poll()
        self.assertEqual(self.game.state.san_history, ['e4'])
        self.assertFalse(self.game.is_cpu_turn)

    def test_toggle_off_ignores_queued_result(self):
        self.start(UserSide.BLACK)
        self.engine.finish('e2e4')
        self.game.cpu_play = False
        self.cpu.sync()
        self.cpu.poll()
        self.assertEqual(self.game.state.san_history, [])
        self.assertTrue(self.game.request_move(chess.E2, chess.E4))

    def test_new_match_rejects_old_result_even_for_same_fen(self):
        self.start(UserSide.BLACK)
        old = len(self.engine.jobs) - 1
        self.start(UserSide.BLACK)
        self.engine.finish('e2e4', old)
        self.cpu.poll()
        self.assertEqual(self.game.state.san_history, [])
        self.engine.finish('d2d4')
        self.cpu.poll()
        self.assertEqual(self.game.state.san_history, ['d4'])

    def test_analysis_mode_stays_manual(self):
        self.start(UserSide.ANALYSIS)
        self.assertFalse(self.game.is_cpu_turn)
        self.assertTrue(self.game.request_move(chess.E2, chess.E4))
        self.cpu.sync()
        self.assertTrue(self.game.request_move(chess.E7, chess.E5))

    def test_cpu_promotion(self):
        self.start(UserSide.BLACK)
        self.game.set_fen('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        self.cpu.sync()
        self.engine.finish('a7a8q')
        self.cpu.poll()
        self.assertEqual(self.game.state.board.piece_at(chess.A8).piece_type, chess.QUEEN)

    def test_undo_invalidates_pending_reply(self):
        self.start(UserSide.WHITE)
        self.game.request_move(chess.E2, chess.E4)
        self.cpu.sync()
        old = len(self.engine.jobs) - 1
        self.game.undo()
        self.cpu.sync()
        self.engine.finish('e7e5', old)
        self.cpu.poll()
        self.assertEqual(self.game.state.board.fen(), chess.STARTING_FEN)

    def test_engine_error_does_not_move_or_retry_forever(self):
        self.start(UserSide.BLACK)
        self.engine.jobs[-1][1]['on_error']('Stockfish was not found')
        self.cpu.poll()
        self.cpu.sync()
        self.assertEqual(len(self.engine.jobs), 1)
        self.assertEqual(self.game.state.san_history, [])
        self.assertIn('Stockfish was not found', self.game.state.status_message)

    def test_terminal_position_does_not_start_cpu(self):
        self.start(UserSide.WHITE)
        self.game.set_fen('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1')
        count = len(self.engine.jobs)
        self.cpu.sync()
        self.assertFalse(self.game.is_cpu_turn)
        self.assertEqual(len(self.engine.jobs), count)
