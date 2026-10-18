"""Load and cache the bundled chess-piece PNG artwork for Tkinter widgets."""

from __future__ import annotations

import math
import sys
import tkinter as tk
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

import chess


PIECE_IMAGE_FILES: dict[tuple[chess.Color, int], str] = {
    (chess.WHITE, chess.KING): "wk.png",
    (chess.WHITE, chess.QUEEN): "wq.png",
    (chess.WHITE, chess.ROOK): "wr.png",
    (chess.WHITE, chess.BISHOP): "wb.png",
    (chess.WHITE, chess.KNIGHT): "wn.png",
    (chess.WHITE, chess.PAWN): "wp.png",
    (chess.BLACK, chess.KING): "bk.png",
    (chess.BLACK, chess.QUEEN): "bq.png",
    (chess.BLACK, chess.ROOK): "br.png",
    (chess.BLACK, chess.BISHOP): "bb.png",
    (chess.BLACK, chess.KNIGHT): "bn.png",
    (chess.BLACK, chess.PAWN): "bp.png",
}


def piece_assets_directory() -> Path:
    """Return the artwork directory in source and PyInstaller builds."""
    bundle_directory = getattr(sys, "_MEIPASS", None)
    if bundle_directory:
        return Path(bundle_directory) / "assets" / "pieces"
    return Path(__file__).resolve().parent.parent / "assets" / "pieces"


class PieceImageCache:
    """Own the Tk image references and cache a few commonly used sizes."""

    _SIZE_STEP = 4
    _MAX_CACHED_SIZES = 8

    def __init__(self, master: tk.Misc) -> None:
        self._sources: dict[tuple[chess.Color, int], tk.PhotoImage] = {}
        self._scaled: OrderedDict[
            int, dict[tuple[chess.Color, int], tk.PhotoImage]
        ] = OrderedDict()
        assets = piece_assets_directory()
        missing = [name for name in PIECE_IMAGE_FILES.values() if not (assets / name).is_file()]
        if missing:
            raise FileNotFoundError(
                f"Chess-piece images are missing from {assets}: {', '.join(missing)}"
            )

        for key, filename in PIECE_IMAGE_FILES.items():
            self._sources[key] = tk.PhotoImage(
                master=master,
                file=str(assets / filename),
            )

    def get(self, piece: chess.Piece, size: float) -> tk.PhotoImage:
        """Return a cached, approximately ``size``-pixel square image."""
        key = (piece.color, piece.piece_type)
        source = self._sources[key]
        requested_size = max(1, int(round(float(size))))
        requested_size = min(requested_size, source.width())
        cached_size = max(
            1,
            int(round(requested_size / self._SIZE_STEP)) * self._SIZE_STEP,
        )
        cached_size = min(cached_size, source.width())

        size_group = self._scaled.get(cached_size)
        if size_group is None:
            size_group = {}
            self._scaled[cached_size] = size_group
            if len(self._scaled) > self._MAX_CACHED_SIZES:
                self._scaled.popitem(last=False)
        else:
            self._scaled.move_to_end(cached_size)

        image = size_group.get(key)
        if image is None:
            image = self._scale(source, cached_size)
            size_group[key] = image
        return image

    @staticmethod
    def _scale(source: tk.PhotoImage, target_size: int) -> tk.PhotoImage:
        """Resize with Tk's native photo operations (no extra dependency)."""
        source_size = min(source.width(), source.height())
        target_size = min(max(1, target_size), source_size)
        if target_size == source_size:
            return source

        # For tiny icons, direct subsampling avoids an unnecessarily large
        # intermediate image. Board and dialog pieces normally use the
        # fractional path below for a closer fit.
        if target_size < source_size / 16:
            factor = max(1, math.ceil(source_size / target_size))
            return source.subsample(factor, factor)

        ratio = Fraction(target_size, source_size).limit_denominator(16)
        if ratio.numerator == 0:
            factor = max(1, math.ceil(source_size / target_size))
            return source.subsample(factor, factor)
        return source.zoom(ratio.numerator, ratio.numerator).subsample(
            ratio.denominator,
            ratio.denominator,
        )
