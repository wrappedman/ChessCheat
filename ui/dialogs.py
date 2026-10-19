"""Dialogs for FEN input, the board editor, PGN transfer and promotion."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import chess

from theme import AppColors
from ui.board_geometry import square_at, square_origin
from ui.piece_images import PieceImageCache


def _dialog(parent, title: str, width: int, height: int) -> tk.Toplevel:
    window = tk.Toplevel(parent)
    window.title(title)
    window.configure(bg=AppColors.PANEL)
    window.resizable(False, False)
    window.transient(parent)
    window.grab_set()
    window.update_idletasks()
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    return window


def show_fen_dialog(parent, current_board: chess.Board, on_apply: Callable[[str], bool]) -> None:
    window = _dialog(parent, "FEN / Board Editor", 660, 570)
    top = tk.Frame(window, bg=AppColors.PANEL, padx=18, pady=14)
    top.pack(fill="x")
    tk.Label(top, text="Jump To Position", bg=AppColors.PANEL,
             fg=AppColors.TEXT_PRIMARY, font=("Segoe UI", 16, "bold")).pack(side="left")
    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    fen_tab = tk.Frame(notebook, bg=AppColors.PANEL, padx=16, pady=16)
    editor_tab = tk.Frame(notebook, bg=AppColors.PANEL, padx=8, pady=8)
    notebook.add(fen_tab, text="Paste FEN")
    notebook.add(editor_tab, text="Board Editor")

    tk.Label(
        fen_tab, text="Paste a full FEN position (six fields):",
        bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
        font=("Segoe UI", 10), anchor="w",
    ).pack(fill="x", pady=(4, 8))
    fen_var = tk.StringVar(value=current_board.fen())
    entry = tk.Entry(
        fen_tab, textvariable=fen_var, bg=AppColors.BACKGROUND,
        fg=AppColors.TEXT_PRIMARY, insertbackground=AppColors.TEXT_PRIMARY,
        relief="flat", font=("Consolas", 10),
    )
    entry.pack(fill="x", ipady=10)
    feedback = tk.Label(
        fen_tab, text="", bg=AppColors.PANEL,
        fg=AppColors.TEXT_SECONDARY, anchor="w", font=("Segoe UI", 9),
    )
    feedback.pack(fill="x", pady=(8, 0))

    def validate_fen(*_args) -> None:
        try:
            board = chess.Board(fen_var.get().strip())
            if board.is_valid():
                feedback.configure(text="Valid chess position.", fg=AppColors.ACCENT)
            else:
                feedback.configure(text="Position is not legal (check kings, pawns and checks).", fg=AppColors.DANGER)
        except (ValueError, TypeError):
            feedback.configure(text="Invalid FEN syntax.", fg=AppColors.DANGER)

    fen_var.trace_add("write", validate_fen)
    validate_fen()

    footer = tk.Frame(window, bg=AppColors.PANEL, padx=16, pady=12)
    footer.pack(fill="x")

    def apply_fen() -> None:
        if on_apply(fen_var.get()):
            window.destroy()
        else:
            notebook.select(fen_tab)

    tk.Button(
        fen_tab, text="Load Position", command=apply_fen,
        bg=AppColors.ACCENT, fg="#151912", activebackground=AppColors.ACCENT_DARK,
        relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=8,
        cursor="hand2",
    ).pack(side="bottom", anchor="e", pady=(15, 0))

    editor = _BoardEditor(editor_tab, current_board, on_apply)
    editor.pack(fill="both", expand=True)

    tk.Button(
        footer, text="Close", command=window.destroy,
        bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
        activebackground=AppColors.BORDER, relief="flat",
        font=("Segoe UI", 9, "bold"), padx=15, pady=7,
    ).pack(side="right")
    entry.focus_set()


class _BoardEditor(tk.Frame):
    """Compact manual editor: click a square after selecting a piece."""

    def __init__(self, master, source: chess.Board, on_apply: Callable[[str], bool]) -> None:
        super().__init__(master, bg=AppColors.PANEL)
        self.on_apply = on_apply
        self.piece_images = PieceImageCache(self)
        self.pieces = {square: piece for square, piece in source.piece_map().items()}
        self.palette: Optional[chess.Piece] = None
        self.turn_var = tk.StringVar(value="white" if source.turn else "black")
        self.ep_var = tk.StringVar(value=chess.square_name(source.ep_square) if source.ep_square is not None else "")
        self.halfmove_var = tk.StringVar(value=str(source.halfmove_clock))
        self.fullmove_var = tk.StringVar(value=str(source.fullmove_number))
        self.castle_vars = {
            "K": tk.BooleanVar(value=source.has_kingside_castling_rights(chess.WHITE)),
            "Q": tk.BooleanVar(value=source.has_queenside_castling_rights(chess.WHITE)),
            "k": tk.BooleanVar(value=source.has_kingside_castling_rights(chess.BLACK)),
            "q": tk.BooleanVar(value=source.has_queenside_castling_rights(chess.BLACK)),
        }
        self._build()
        self._draw_board()

    def _build(self) -> None:
        row = tk.Frame(self, bg=AppColors.PANEL)
        row.pack(fill="x", pady=(0, 5))
        self.canvas = tk.Canvas(
            row, width=320, height=320, bg=AppColors.BACKGROUND,
            highlightthickness=0, cursor="hand2",
        )
        self.canvas.pack(side="left", padx=(0, 10))
        self.canvas.bind("<Button-1>", self._on_square_click)

        palette_panel = tk.Frame(row, bg=AppColors.PANEL)
        palette_panel.pack(side="left", fill="y")
        tk.Label(palette_panel, text="Piece palette", bg=AppColors.PANEL,
                 fg=AppColors.TEXT_SECONDARY, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        for color in (chess.WHITE, chess.BLACK):
            piece_row = tk.Frame(palette_panel, bg=AppColors.PANEL)
            piece_row.pack(anchor="w", pady=2)
            for piece_type in (chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN):
                piece = chess.Piece(piece_type, color)
                tk.Button(
                    piece_row,
                    image=self.piece_images.get(piece, 36),
                    command=lambda p=piece: self._select_piece(p),
                    bg=AppColors.PANEL_LIGHT,
                    activebackground=AppColors.ACCENT_DARK,
                    relief="flat",
                    borderwidth=0,
                    padx=2,
                    pady=2,
                ).pack(side="left", padx=1)
        tk.Button(
            palette_panel, text="⌫ Erase square", command=lambda: self._select_piece(None),
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, relief="flat",
            font=("Segoe UI", 9), padx=7, pady=5,
        ).pack(anchor="w", pady=(7, 4))
        tk.Button(
            palette_panel, text="Clear board", command=self._clear,
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, relief="flat",
            font=("Segoe UI", 9), padx=7, pady=5,
        ).pack(anchor="w", pady=2)
        tk.Button(
            palette_panel, text="Reset standard", command=self._reset,
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, relief="flat",
            font=("Segoe UI", 9), padx=7, pady=5,
        ).pack(anchor="w", pady=2)

        settings = tk.Frame(self, bg=AppColors.PANEL)
        settings.pack(fill="x", pady=(2, 0))
        tk.Label(settings, text="To move:", bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(side="left")
        for label, value in (("White", "white"), ("Black", "black")):
            tk.Radiobutton(
                settings, text=label, variable=self.turn_var, value=value,
                bg=AppColors.PANEL, fg=AppColors.TEXT_PRIMARY,
                activebackground=AppColors.PANEL, selectcolor=AppColors.PANEL_LIGHT,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(2, 5))
        for label in ("K", "Q", "k", "q"):
            tk.Checkbutton(
                settings, text=label, variable=self.castle_vars[label],
                bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
                activebackground=AppColors.PANEL, selectcolor=AppColors.PANEL_LIGHT,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left", padx=1)
        tk.Label(settings, text="EP:", bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        tk.Entry(settings, textvariable=self.ep_var, width=4, bg=AppColors.BACKGROUND,
                 fg=AppColors.TEXT_PRIMARY, insertbackground=AppColors.TEXT_PRIMARY,
                 relief="flat", font=("Consolas", 9)).pack(side="left")
        tk.Label(settings, text="Half:", bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(side="left", padx=(7, 2))
        tk.Entry(settings, textvariable=self.halfmove_var, width=4, bg=AppColors.BACKGROUND,
                 fg=AppColors.TEXT_PRIMARY, insertbackground=AppColors.TEXT_PRIMARY,
                 relief="flat", font=("Consolas", 9)).pack(side="left")
        tk.Label(settings, text="Full:", bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(side="left", padx=(7, 2))
        tk.Entry(settings, textvariable=self.fullmove_var, width=4, bg=AppColors.BACKGROUND,
                 fg=AppColors.TEXT_PRIMARY, insertbackground=AppColors.TEXT_PRIMARY,
                 relief="flat", font=("Consolas", 9)).pack(side="left")

        action_row = tk.Frame(self, bg=AppColors.PANEL)
        action_row.pack(fill="x", pady=(6, 0))
        self.preview = tk.Label(
            action_row, text="", bg=AppColors.PANEL, fg=AppColors.TEXT_MUTED,
            font=("Consolas", 8), anchor="w", wraplength=425, justify="left",
        )
        self.preview.pack(side="left", fill="x", expand=True)
        tk.Button(
            action_row, text="Apply Position", command=self._apply,
            bg=AppColors.ACCENT, fg="#151912", activebackground=AppColors.ACCENT_DARK,
            relief="flat", font=("Segoe UI", 9, "bold"), padx=11, pady=7,
        ).pack(side="right", padx=(8, 0))

    def _select_piece(self, piece: Optional[chess.Piece]) -> None:
        self.palette = piece

    def _on_square_click(self, event) -> None:
        square_size = min(self.canvas.winfo_width(), self.canvas.winfo_height()) / 8
        square = square_at(event.x, event.y, square_size, False)
        if square is None:
            return
        if self.palette is None:
            self.pieces.pop(square, None)
        else:
            self.pieces[square] = self.palette
        self._draw_board()

    def _draw_board(self) -> None:
        self.canvas.delete("all")
        size = min(self.canvas.winfo_width(), self.canvas.winfo_height())
        if size < 100:
            size = 320
        square = size / 8
        for row in range(8):
            for column in range(8):
                # a8 is a dark square; light squares have odd screen parity.
                color = AppColors.BOARD_DARK if (row + column) % 2 == 1 else AppColors.BOARD_LIGHT
                x, y = column * square, row * square
                self.canvas.create_rectangle(x, y, x + square, y + square, fill=color, outline=color)
        for square_index, piece in self.pieces.items():
            x, y = square_origin(square_index, square, False)
            self.canvas.create_image(
                x + square / 2,
                y + square / 2,
                image=self.piece_images.get(piece, square * 0.92),
                anchor=tk.CENTER,
            )
        try:
            board = self._build_board()
            self.preview.configure(text=board.fen())
        except (ValueError, TypeError):
            self.preview.configure(text="Complete the position fields to preview FEN.")

    def _build_board(self) -> chess.Board:
        board = chess.Board(None)
        for square, piece in self.pieces.items():
            board.set_piece_at(square, piece)
        board.turn = self.turn_var.get() == "white"
        rights = 0
        for label, square in (("K", chess.H1), ("Q", chess.A1), ("k", chess.H8), ("q", chess.A8)):
            if self.castle_vars[label].get():
                rights |= chess.BB_SQUARES[square]
        board.castling_rights = rights
        ep = self.ep_var.get().strip().lower()
        board.ep_square = chess.parse_square(ep) if ep else None
        board.halfmove_clock = max(0, int(self.halfmove_var.get() or "0"))
        board.fullmove_number = max(1, int(self.fullmove_var.get() or "1"))
        board.clear_stack()
        return board

    def _clear(self) -> None:
        self.pieces.clear()
        for variable in self.castle_vars.values():
            variable.set(False)
        self.ep_var.set("")
        self._draw_board()

    def _reset(self) -> None:
        board = chess.Board()
        self.pieces = dict(board.piece_map())
        self.turn_var.set("white")
        self.castle_vars["K"].set(True)
        self.castle_vars["Q"].set(True)
        self.castle_vars["k"].set(True)
        self.castle_vars["q"].set(True)
        self.ep_var.set("")
        self.halfmove_var.set("0")
        self.fullmove_var.set("1")
        self._draw_board()

    def _apply(self) -> None:
        try:
            board = self._build_board()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid position", str(exc), parent=self)
            return
        if not board.is_valid():
            messagebox.showerror(
                "Invalid position",
                "Include exactly one king per side and remove impossible checks.",
                parent=self,
            )
            return
        if self.on_apply(board.fen()):
            self.winfo_toplevel().destroy()


def show_pgn_dialog(
    parent,
    *,
    mode: str,
    export_text: str,
    on_import: Callable[[str], bool],
) -> None:
    is_import = mode == "import"
    window = _dialog(parent, "Import PGN" if is_import else "Export PGN", 660, 500)
    header = tk.Frame(window, bg=AppColors.PANEL, padx=18, pady=12)
    header.pack(fill="x")
    tk.Label(
        header, text="Import PGN" if is_import else "Export PGN",
        bg=AppColors.PANEL, fg=AppColors.TEXT_PRIMARY,
        font=("Segoe UI", 16, "bold"),
    ).pack(side="left")
    text = tk.Text(
        window, wrap="word", bg=AppColors.BACKGROUND,
        fg=AppColors.TEXT_PRIMARY, insertbackground=AppColors.TEXT_PRIMARY,
        relief="flat", font=("Consolas", 10), padx=10, pady=10,
    )
    text.pack(fill="both", expand=True, padx=18, pady=(0, 9))
    text.insert("1.0", "" if is_import else export_text)
    if not is_import:
        text.configure(state="disabled")

    footer = tk.Frame(window, bg=AppColors.PANEL, padx=18, pady=12)
    footer.pack(fill="x")

    def import_text() -> None:
        if on_import(text.get("1.0", "end-1c")):
            window.destroy()

    def open_file() -> None:
        path = filedialog.askopenfilename(
            parent=window,
            title="Open PGN file",
            filetypes=(("PGN files", "*.pgn"), ("Text files", "*.txt"), ("All files", "*.*")),
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    text.configure(state="normal")
                    text.delete("1.0", "end")
                    text.insert("1.0", handle.read())
            except OSError as exc:
                messagebox.showerror("Could not open file", str(exc), parent=window)

    def save_file() -> None:
        path = filedialog.asksaveasfilename(
            parent=window,
            title="Save PGN file",
            defaultextension=".pgn",
            filetypes=(("PGN files", "*.pgn"), ("Text files", "*.txt")),
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(export_text)
                messagebox.showinfo("PGN saved", "PGN file saved successfully.", parent=window)
            except OSError as exc:
                messagebox.showerror("Could not save file", str(exc), parent=window)

    if is_import:
        tk.Button(
            footer, text="Open File…", command=open_file,
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, relief="flat", padx=10, pady=7,
        ).pack(side="left")
        tk.Button(
            footer, text="Import", command=import_text,
            bg=AppColors.ACCENT, fg="#151912", activebackground=AppColors.ACCENT_DARK,
            relief="flat", padx=14, pady=7, font=("Segoe UI", 9, "bold"),
        ).pack(side="right")
    else:
        tk.Button(
            footer, text="Copy to Clipboard", command=lambda: _copy_to_clipboard(window, export_text),
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, relief="flat", padx=10, pady=7,
        ).pack(side="left")
        tk.Button(
            footer, text="Save File…", command=save_file,
            bg=AppColors.ACCENT, fg="#151912", activebackground=AppColors.ACCENT_DARK,
            relief="flat", padx=14, pady=7, font=("Segoe UI", 9, "bold"),
        ).pack(side="right")
    tk.Button(
        footer, text="Close", command=window.destroy,
        bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
        activebackground=AppColors.BORDER, relief="flat", padx=12, pady=7,
    ).pack(side="right", padx=(0, 8))


def _copy_to_clipboard(window, text: str) -> None:
    window.clipboard_clear()
    window.clipboard_append(text)
    messagebox.showinfo("Copied", "PGN copied to clipboard.", parent=window)


def show_promotion_dialog(parent, color: bool) -> Optional[int]:
    window = _dialog(parent, "Promote Pawn", 340, 150)
    piece_images = PieceImageCache(window)
    tk.Label(
        window, text="Promote pawn to", bg=AppColors.PANEL,
        fg=AppColors.TEXT_PRIMARY, font=("Segoe UI", 13, "bold"),
    ).pack(pady=(16, 10))
    result: dict[str, Optional[int]] = {"piece": None}
    row = tk.Frame(window, bg=AppColors.PANEL)
    row.pack()
    for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
        piece = chess.Piece(piece_type, color)
        tk.Button(
            row,
            image=piece_images.get(piece, 48),
            command=lambda value=piece_type: (result.update(piece=value), window.destroy()),
            bg=AppColors.PANEL_LIGHT,
            activebackground=AppColors.ACCENT_DARK,
            relief="flat",
            borderwidth=0,
            padx=3,
            pady=3,
        ).pack(side="left", padx=4)
    window.wait_window()
    return result["piece"]
