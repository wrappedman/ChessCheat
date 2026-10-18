"""Interactive chessboard: click-to-move, drag/drop, legal dots and arrows."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

import chess

from models import AnalysisState, BoardArrow, GameState
from theme import AppColors
from ui.board_geometry import blend_hex, square_at, square_center, square_origin
from ui.piece_images import PieceImageCache


class ChessBoardCanvas(tk.Canvas):
    """Canvas-rendered board with native Tk mouse interactions."""

    def __init__(self, master, controller, **kwargs) -> None:
        super().__init__(
            master,
            background=AppColors.BACKGROUND,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.controller = controller
        self.piece_images = PieceImageCache(self)
        self.game_state: Optional[GameState] = None
        self.analysis_state = AnalysisState()
        self._board_box = (0.0, 0.0, 0.0)
        self._press_square: Optional[chess.Square] = None
        self._press_xy: Optional[tuple[float, float]] = None
        self._drag_xy: Optional[tuple[float, float]] = None
        self._dragging = False
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_state(self, game_state: GameState, analysis_state: AnalysisState) -> None:
        self.game_state = game_state
        self.analysis_state = analysis_state
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        state = self.game_state
        if state is None:
            return
        width = max(100, self.winfo_width())
        height = max(100, self.winfo_height())
        board_size = min(width, height)
        left = (width - board_size) / 2
        top = (height - board_size) / 2
        square_size = board_size / 8
        self._board_box = (left, top, square_size)

        selected = state.selected_square
        legal_targets: set[chess.Square] = set()
        if selected is not None:
            legal_targets = {
                move.to_square for move in state.board.legal_moves
                if move.from_square == selected
            }

        check_square = state.board.king(state.board.turn) if state.board.is_check() else None
        for row in range(8):
            for column in range(8):
                # a8 is a dark square; light squares have odd screen parity.
                base = AppColors.BOARD_LIGHT if (row + column) % 2 == 1 else AppColors.BOARD_DARK
                square = self._screen_square(column, row, state.is_flipped)
                color = base
                if state.last_move and square in (state.last_move.from_square, state.last_move.to_square):
                    color = blend_hex(base, "#FFFF33", 0.50)
                if square == selected:
                    color = blend_hex(color, "#245CDF", 0.45)
                if square == check_square:
                    color = blend_hex(color, AppColors.DANGER, 0.72)
                x1 = left + column * square_size
                y1 = top + row * square_size
                self.create_rectangle(
                    x1, y1, x1 + square_size, y1 + square_size,
                    fill=color, outline=color,
                )

        self._draw_coordinates(left, top, square_size, state.is_flipped)
        self._draw_move_hints(legal_targets, left, top, square_size, state)
        self._draw_pieces(left, top, square_size, state)
        self._draw_arrows(left, top, square_size, state.is_flipped)
        if self._dragging and self._press_square is not None and self._drag_xy is not None:
            piece = state.board.piece_at(self._press_square)
            if piece:
                self._draw_piece_at(piece, *self._drag_xy, square_size * 0.92)

    @staticmethod
    def _screen_square(column: int, row: int, flipped: bool) -> chess.Square:
        if flipped:
            return chess.square(7 - column, row)
        return chess.square(column, 7 - row)

    def _draw_coordinates(self, left: float, top: float, square: float, flipped: bool) -> None:
        font_size = max(8, int(square * 0.14))
        for column in range(8):
            file_index = 7 - column if flipped else column
            rank = 0 if not flipped else 7
            square_here = chess.square(file_index, rank)
            x, y = square_origin(square_here, square, flipped, left, top)
            base = AppColors.BOARD_LIGHT if (column + 7) % 2 == 1 else AppColors.BOARD_DARK
            color = AppColors.BOARD_DARK if base == AppColors.BOARD_LIGHT else AppColors.BOARD_LIGHT
            self.create_text(
                x + square - square * 0.13, y + square - square * 0.13,
                text=chess.FILE_NAMES[file_index], anchor="se",
                fill=color, font=("Segoe UI", font_size, "bold"),
            )

        for row in range(8):
            rank_index = row if flipped else 7 - row
            file_index = 7 if flipped else 0
            square_here = chess.square(file_index, rank_index)
            x, y = square_origin(square_here, square, flipped, left, top)
            base = AppColors.BOARD_LIGHT if row % 2 == 1 else AppColors.BOARD_DARK
            color = AppColors.BOARD_DARK if base == AppColors.BOARD_LIGHT else AppColors.BOARD_LIGHT
            self.create_text(
                x + square * 0.10, y + square * 0.08,
                text=str(rank_index + 1), anchor="nw",
                fill=color, font=("Segoe UI", font_size, "bold"),
            )

    def _draw_move_hints(
        self,
        targets: set[chess.Square],
        left: float,
        top: float,
        square: float,
        state: GameState,
    ) -> None:
        if not targets or state.selected_square is None:
            return
        for target in targets:
            cx, cy = square_center(target, square, state.is_flipped, left, top)
            x, y = square_origin(target, square, state.is_flipped, left, top)
            column = int((x - left) / square)
            row = int((y - top) / square)
            base = AppColors.BOARD_LIGHT if (row + column) % 2 == 1 else AppColors.BOARD_DARK
            hint_color = blend_hex(base, "#000000", 0.38)
            radius = square * 0.13
            occupied = state.board.piece_at(target) is not None or state.board.is_en_passant(
                chess.Move(state.selected_square, target)
            )
            if occupied:
                self.create_oval(
                    cx - square * 0.43, cy - square * 0.43,
                    cx + square * 0.43, cy + square * 0.43,
                    outline=hint_color, width=max(3, int(square * 0.07)),
                )
            else:
                self.create_oval(
                    cx - radius, cy - radius, cx + radius, cy + radius,
                    fill=hint_color, outline="",
                )

    def _draw_pieces(self, left: float, top: float, square: float, state: GameState) -> None:
        for square_index in chess.SQUARES:
            piece = state.board.piece_at(square_index)
            if piece is None:
                continue
            if self._dragging and square_index == self._press_square:
                continue
            cx, cy = square_center(square_index, square, state.is_flipped, left, top)
            self._draw_piece_at(piece, cx, cy, square * 0.92)

    def _draw_piece_at(self, piece: chess.Piece, x: float, y: float, size: float) -> None:
        self.create_image(
            x,
            y,
            image=self.piece_images.get(piece, size),
            anchor=tk.CENTER,
        )

    def _draw_arrows(self, left: float, top: float, square: float, flipped: bool) -> None:
        analysis = self.analysis_state
        arrows = []
        if analysis.suggested_move:
            arrows.append(BoardArrow(
                from_square=analysis.suggested_move.from_square,
                to_square=analysis.suggested_move.to_square,
                color=AppColors.ARROW_GREEN,
            ))
        if self.game_state and self.game_state.show_threats and analysis.threat_move:
            arrows.append(BoardArrow(
                from_square=analysis.threat_move.from_square,
                to_square=analysis.threat_move.to_square,
                color=AppColors.ARROW_ORANGE,
                dashed=True,
            ))

        for arrow in arrows:
            start = square_center(arrow.from_square, square, flipped, left, top)
            end = square_center(arrow.to_square, square, flipped, left, top)
            delta_x, delta_y = end[0] - start[0], end[1] - start[1]
            length = max(1.0, (delta_x * delta_x + delta_y * delta_y) ** 0.5)
            inset = square * 0.15
            start = (start[0] + delta_x / length * inset, start[1] + delta_y / length * inset)
            end = (end[0] - delta_x / length * inset, end[1] - delta_y / length * inset)
            self.create_line(
                start[0], start[1], end[0], end[1],
                fill=arrow.color,
                width=max(4, int(square * 0.13)),
                arrow=tk.LAST,
                arrowshape=(max(12, int(square * 0.38)), max(10, int(square * 0.30)), max(5, int(square * 0.13))),
                dash=(9, 6) if arrow.dashed else (),
                capstyle=tk.ROUND,
            )

    def _on_press(self, event) -> None:
        if self.game_state is None:
            return
        left, top, square = self._board_box
        source = square_at(event.x, event.y, square, self.game_state.is_flipped, left, top)
        self._press_square = source
        self._press_xy = (event.x, event.y)
        self._drag_xy = (event.x, event.y)
        self._dragging = False

    def _on_motion(self, event) -> None:
        if self._press_square is None or self._press_xy is None or self.game_state is None:
            return
        distance = ((event.x - self._press_xy[0]) ** 2 + (event.y - self._press_xy[1]) ** 2) ** 0.5
        if distance > 5 and self.game_state.board.piece_at(self._press_square) is not None:
            self._dragging = True
            self._drag_xy = (event.x, event.y)
            self.redraw()

    def _on_release(self, event) -> None:
        source = self._press_square
        dragging = self._dragging
        self._press_square = None
        self._press_xy = None
        self._drag_xy = None
        self._dragging = False
        if source is None or self.game_state is None:
            return
        left, top, square = self._board_box
        if dragging:
            target = square_at(event.x, event.y, square, self.game_state.is_flipped, left, top)
            if target is not None and target != source:
                self.controller.request_move(source, target)
            else:
                self.controller.on_square_tap(source)
        else:
            target = square_at(event.x, event.y, square, self.game_state.is_flipped, left, top)
            if target is not None:
                self.controller.on_square_tap(target)
        self.redraw()
