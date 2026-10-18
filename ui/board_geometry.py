"""Square-to-pixel mapping shared by the board and board editor."""

from __future__ import annotations

from typing import Optional

import chess


def square_origin(
    square: chess.Square,
    square_size: float,
    flipped: bool,
    left: float = 0,
    top: float = 0,
) -> tuple[float, float]:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    if flipped:
        column = 7 - file_index
        row = rank_index
    else:
        column = file_index
        row = 7 - rank_index
    return left + column * square_size, top + row * square_size


def square_center(
    square: chess.Square,
    square_size: float,
    flipped: bool,
    left: float = 0,
    top: float = 0,
) -> tuple[float, float]:
    x, y = square_origin(square, square_size, flipped, left, top)
    return x + square_size / 2, y + square_size / 2


def square_at(
    x: float,
    y: float,
    square_size: float,
    flipped: bool,
    left: float = 0,
    top: float = 0,
) -> Optional[chess.Square]:
    column = int((x - left) // square_size)
    row = int((y - top) // square_size)
    if not (0 <= column < 8 and 0 <= row < 8):
        return None
    if flipped:
        file_index = 7 - column
        rank_index = row
    else:
        file_index = column
        rank_index = 7 - row
    return chess.square(file_index, rank_index)


def blend_hex(base: str, overlay: str, alpha: float) -> str:
    """Blend #RRGGBB colors for Tk, which has no alpha color support."""
    base_rgb = tuple(int(base[i:i + 2], 16) for i in (1, 3, 5))
    over_rgb = tuple(int(overlay[i:i + 2], 16) for i in (1, 3, 5))
    rgb = tuple(round(a * (1 - alpha) + b * alpha) for a, b in zip(base_rgb, over_rgb))
    return "#%02X%02X%02X" % rgb
