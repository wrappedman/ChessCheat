"""Central color palette, inspired by the Chess.com desktop interface."""


class AppColors:
    # --- Surfaces --------------------------------------------------------
    # Main application background.
    BACKGROUND = "#312E2B"
    # Side panels / cards.
    PANEL = "#262421"
    # Slightly lighter panel used for nested cards.
    PANEL_LIGHT = "#32302E"
    # Subtle borders and dividers.
    BORDER = "#4A4743"

    # --- Typography ------------------------------------------------------
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#989795"
    TEXT_MUTED = "#757472"

    # --- Accent ----------------------------------------------------------
    # Chess.com style green accent (buttons, highlights).
    ACCENT = "#81B64C"
    ACCENT_DARK = "#5A8D3A"

    # Danger / opponent threat.
    DANGER = "#E5534B"
    WARNING = "#FF9D2E"
    INFO = "#64B5F6"

    # --- Chessboard ------------------------------------------------------
    # Classic green & cream board.
    BOARD_LIGHT = "#EEEED2"
    BOARD_DARK = "#769656"
    # Last move highlight, rgba(255, 255, 51, 0.5) over the square color.
    LAST_MOVE = "#80FFFF33"
    # Selected square (blue, Chess.com style).
    SELECTED = "#73245CDF"
    # Legal move dot / capture ring.
    MOVE_DOT = "#4D000000"
    # Engine suggestion arrow (bold green).
    ARROW_GREEN = "#96FF64"
    # Opponent threat arrow (orange, dashed).
    ARROW_ORANGE = "#FF8A3D"

    # --- Evaluation bar --------------------------------------------------
    EVAL_WHITE = "#EDEDEF"
    EVAL_BLACK = "#3B3B3B"
    EVAL_TRACK = "#1E1D1B"


# Tkinter-compatible (8-digit #RRGGBBAA is NOT supported by Tk),
# so the last-move highlight is pre-blended over both square colors.
LAST_MOVE_ON_LIGHT = "#F2F2A8"  # cream square + 50% yellow
LAST_MOVE_ON_DARK = "#B8B846"  # green square + 50% yellow
