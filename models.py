"""Immutable-ish data models shared by the services, controllers and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import chess


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UserSide(Enum):
    """The role the human player takes in a mirrored session."""

    WHITE = "White"
    BLACK = "Black"
    ANALYSIS = "Analysis Mode"

    @property
    def description(self) -> str:
        return {
            UserSide.WHITE: "You move first. The engine suggests your opening move.",
            UserSide.BLACK: "You move second. The board is flipped for you.",
            UserSide.ANALYSIS: "Play both sides, or import a FEN / PGN.",
        }[self]


class GamePhase(Enum):
    """High level phase of a mirrored session."""

    IDLE = "idle"
    USER_TURN = "userTurn"
    AWAITING_OPPONENT = "awaitingOpponent"
    GAME_OVER = "gameOver"


class StatusKind(Enum):
    """Severity of the status line shown under the board."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class AnalysisStatus(Enum):
    """Status of the analysis pipeline."""

    IDLE = "idle"
    THINKING = "thinking"
    READY = "ready"
    ERROR = "error"
    ENGINE_UNAVAILABLE = "engineUnavailable"


# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------


@dataclass
class EngineSettings:
    """Runtime configuration of the local Stockfish engine."""

    search_time_ms: int = 2000
    elo: int = 2600
    multi_pv: int = 3
    threads: int = 4
    hash_mb: int = 256

    @property
    def skill_level(self) -> int:
        """Maps the requested ELO range (1500..3500) onto the UCI
        'Skill Level' option (0..20) supported by Stockfish."""
        raw = round((self.elo - 1300) / 2000 * 20)
        return max(0, min(20, raw))

    @property
    def speed_label(self) -> str:
        if self.search_time_ms <= 800:
            return "Fast (~0.5s)"
        if self.search_time_ms <= 3000:
            return "Deep (~2s)"
        return "Grandmaster (~5s)"


@dataclass
class WizardConfig:
    """Result of the startup setup wizard."""

    side: UserSide
    search_time_ms: int
    elo: int


# ---------------------------------------------------------------------------
# Engine analysis
# ---------------------------------------------------------------------------


@dataclass
class EngineLine:
    """One principal variation line reported by the UCI engine."""

    multipv: int
    depth: int
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None
    uci_pv: List[str] = field(default_factory=list)
    nodes: int = 0
    nps: int = 0
    time_ms: int = 0


@dataclass
class EngineAnalysis:
    """A complete snapshot of an engine search (or a partial one
    while streaming)."""

    fen: str
    lines: List[EngineLine] = field(default_factory=list)
    depth: int = 0
    best_move_uci: Optional[str] = None
    ponder_uci: Optional[str] = None
    is_complete: bool = False


@dataclass
class EvalLine:
    """A UI friendly evaluation line: UCI moves resolved to SAN,
    plus the parsed first Move so the UI can draw arrows."""

    rank: int
    move: chess.Move
    san: str
    san_pv: List[str]
    depth: int
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None
    nodes: int = 0
    nps: int = 0
    time_ms: int = 0

    def white_score_cp(self, turn: chess.Color) -> float:
        """Score in centipawns from White's point of view."""
        if self.score_mate is not None:
            white_mate = self.score_mate if turn == chess.WHITE else -self.score_mate
            return float(100000 if white_mate > 0 else -100000)
        cp = self.score_cp or 0
        return float(cp if turn == chess.WHITE else -cp)

    def eval_label(self, turn: chess.Color) -> str:
        """Formatted evaluation from White's perspective,
        e.g. '+1.8', '-0.4', 'M3' or 'M-2'."""
        if self.score_mate is not None:
            white_mate = self.score_mate if turn == chess.WHITE else -self.score_mate
            return f"M{white_mate}"
        pawns = self.white_score_cp(turn) / 100
        return f"+{pawns:.1f}" if pawns > 0 else f"{pawns:.1f}"

    def favors_white_from(self, turn: chess.Color) -> bool:
        if self.score_mate is not None:
            white_mate = self.score_mate if turn == chess.WHITE else -self.score_mate
            return white_mate > 0
        return self.white_score_cp(turn) > 0


@dataclass
class BoardArrow:
    """An arrow rendered on top of the chessboard."""

    from_square: chess.Square
    to_square: chess.Square
    color: str = "#96FF64"  # engine green
    dashed: bool = False


# ---------------------------------------------------------------------------
# Database rows
# ---------------------------------------------------------------------------


@dataclass
class OpeningBookEntry:
    """One row of the openings_book table."""

    eco: Optional[str]
    name: str
    fen: str
    san: str
    ply: int
    line: str


@dataclass
class SavedGame:
    """One row of the saved_games table."""

    pgn: str
    user_color: str
    result: str
    final_eval_cp: Optional[int] = None
    created_at: int = 0
    id: Optional[int] = None


@dataclass
class PositionCacheEntry:
    """One row of the position_cache table: a deeply analyzed FEN
    and its best move, so previously seen scenarios answer in ~0ms."""

    fen: str
    best_move_san: str
    depth: int
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None
    pv_sans: List[str] = field(default_factory=list)
    updated_at: int = 0


# ---------------------------------------------------------------------------
# Analysis state
# ---------------------------------------------------------------------------


@dataclass
class AnalysisState:
    """Everything the UI needs to render the intelligence panel:
    multi-PV lines, suggested move, threat move and opening info."""

    status: AnalysisStatus = AnalysisStatus.IDLE
    fen: str = ""
    lines: List[EvalLine] = field(default_factory=list)
    opening_name: Optional[str] = None
    opening_eco: Optional[str] = None
    suggested_move: Optional[chess.Move] = None
    suggested_san: Optional[str] = None
    threat_move: Optional[chess.Move] = None
    threat_san: Optional[str] = None
    from_cache: bool = False
    message: Optional[str] = None

    @property
    def depth(self) -> int:
        return self.lines[0].depth if self.lines else 0

    @property
    def best_line(self) -> Optional[EvalLine]:
        return self.lines[0] if self.lines else None


@dataclass
class GameState:
    """Snapshot of the mirrored game and its UI-facing state."""

    board: chess.Board = field(default_factory=chess.Board)
    user_side: UserSide = UserSide.WHITE
    phase: GamePhase = GamePhase.IDLE
    history: List[chess.Board] = field(default_factory=list)
    moves: List[chess.Move] = field(default_factory=list)
    san_history: List[str] = field(default_factory=list)
    redo_moves: List[tuple[chess.Move, str]] = field(default_factory=list)
    selected_square: Optional[chess.Square] = None
    last_move: Optional[chess.Move] = None
    pending_promotion: Optional[tuple[chess.Square, chess.Square]] = None
    is_flipped: bool = False
    show_threats: bool = True
    status_message: str = "Welcome to ChessCheat. Start a match to begin."
    status_kind: StatusKind = StatusKind.INFO
    settings: EngineSettings = field(default_factory=EngineSettings)
    session_active: bool = False
    started_at: Optional[float] = None

    @property
    def user_color(self) -> chess.Color:
        return chess.BLACK if self.user_side == UserSide.BLACK else chess.WHITE

    @property
    def is_analysis_mode(self) -> bool:
        return self.user_side == UserSide.ANALYSIS

    @property
    def is_game_over(self) -> bool:
        return self.phase == GamePhase.GAME_OVER

    @property
    def should_analyze(self) -> bool:
        return self.session_active and self.phase == GamePhase.USER_TURN and not self.is_game_over
