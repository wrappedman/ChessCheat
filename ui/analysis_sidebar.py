"""Right-side engine recommendations, move history and tool buttons."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from collections.abc import Callable

from models import AnalysisState, AnalysisStatus, GamePhase, GameState
from theme import AppColors


class AnalysisSidebar(tk.Frame):
    """The compact intelligence panel used by the main workspace."""

    def __init__(self, master, actions: dict[str, Callable], **kwargs) -> None:
        super().__init__(master, background=AppColors.PANEL, width=360, **kwargs)
        self.actions = actions
        self.pack_propagate(False)

        self.status_var = tk.StringVar(value="Engine idle")
        self.opening_var = tk.StringVar(value="")
        self._pin_var = tk.StringVar(value="Pin Top")
        self._threat_var = tk.StringVar(value="Threats: On")

        self._build()

    def _build(self) -> None:
        pad = 12
        header = tk.Label(
            self, text="ENGINE ANALYSIS", anchor="w",
            bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
            font=("Segoe UI", 9, "bold"),
        )
        header.pack(fill="x", padx=pad, pady=(pad, 6))

        status_box = tk.Frame(
            self, bg=AppColors.PANEL_LIGHT,
            highlightbackground=AppColors.BORDER, highlightthickness=1,
        )
        status_box.pack(fill="x", padx=pad, pady=(0, 8))
        self.status_dot = tk.Label(
            status_box, text="●", bg=AppColors.PANEL_LIGHT,
            fg=AppColors.TEXT_MUTED, font=("Segoe UI", 10, "bold"),
        )
        self.status_dot.pack(side="left", padx=(10, 6), pady=8)
        tk.Label(
            status_box, textvariable=self.status_var, anchor="w",
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"), wraplength=285,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)

        self.opening_box = tk.Frame(
            self, bg="#283521",
            highlightbackground=AppColors.ACCENT_DARK, highlightthickness=1,
        )
        self.opening_box.pack(fill="x", padx=pad, pady=(0, 10))
        tk.Label(
            self.opening_box, text="BOOK", bg="#283521",
            fg=AppColors.ACCENT, font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(8, 6), pady=6)
        tk.Label(
            self.opening_box, textvariable=self.opening_var, anchor="w",
            bg="#283521", fg=AppColors.ACCENT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
        self.opening_box.pack_forget()

        tk.Label(
            self, text="TOP ENGINE RECOMMENDATIONS", anchor="w",
            bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", padx=pad, pady=(0, 6))

        self.lines_frame = tk.Frame(self, bg=AppColors.PANEL)
        self.lines_frame.pack(fill="x", padx=pad)
        self._empty_label = tk.Label(
            self.lines_frame,
            text="Start a match or load a position to see\nthe top engine moves.",
            justify="center", bg=AppColors.PANEL, fg=AppColors.TEXT_MUTED,
            font=("Segoe UI", 9), pady=18,
        )
        self._empty_label.pack(fill="x")

        self.play_button = self._button(
            self, "▶  Play Suggested Move", self._call("play"),
            bg=AppColors.ACCENT, fg="#151912", active=AppColors.ACCENT_DARK,
        )
        self.play_button.pack(fill="x", padx=pad, pady=(9, 12))

        tk.Label(
            self, text="MOVE HISTORY", anchor="w",
            bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", padx=pad, pady=(0, 5))

        table_frame = tk.Frame(self, bg=AppColors.PANEL)
        table_frame.pack(fill="both", expand=True, padx=pad)
        self.moves = ttk.Treeview(
            table_frame, columns=("number", "white", "black"),
            show="headings", height=9, selectmode="browse",
        )
        self.moves.heading("number", text="#")
        self.moves.heading("white", text="White")
        self.moves.heading("black", text="Black")
        self.moves.column("number", width=42, anchor="center", stretch=False)
        self.moves.column("white", width=90, anchor="w")
        self.moves.column("black", width=90, anchor="w")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.moves.yview)
        self.moves.configure(yscrollcommand=scroll.set)
        self.moves.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.moves.tag_configure("latest", background="#3A3732", foreground=AppColors.TEXT_PRIMARY)

        tk.Label(
            self, text="TOOLS", anchor="w",
            bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", padx=pad, pady=(11, 5))
        self.tools_frame = tk.Frame(self, bg=AppColors.PANEL)
        self.tools_frame.pack(fill="x", padx=pad, pady=(0, pad))
        self._tool_buttons: dict[str, tk.Button] = {}
        tools = [
            ("undo", "↶ Undo"), ("redo", "↷ Redo"), ("flip", "⇅ Flip"),
            ("fen", "FEN / Editor"), ("engine_path", "Engine Path"),
            ("pgn_import", "PGN Import"), ("pgn_export", "PGN Export"),
            ("pin", "Pin Top"),
            ("threats", "Threats: On"), ("save", "Save Game"),
            ("new", "New Match"), ("claim", "Claim Draw"),
        ]
        for index, (key, label) in enumerate(tools):
            row, column = divmod(index, 3)
            button = self._button(
                self.tools_frame, label, self._call(key),
                bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
                active=AppColors.BORDER,
            )
            button.grid(row=row, column=column, sticky="ew", padx=2, pady=2, ipady=4)
            self._tool_buttons[key] = button
        for column in range(3):
            self.tools_frame.grid_columnconfigure(column, weight=1)

    @staticmethod
    def _button(master, text: str, command, *, bg: str, fg: str, active: str) -> tk.Button:
        return tk.Button(
            master, text=text, command=command,
            bg=bg, fg=fg, activebackground=active, activeforeground=fg,
            relief="flat", borderwidth=0, cursor="hand2",
            font=("Segoe UI", 9, "bold"), padx=6, pady=7,
            disabledforeground=AppColors.TEXT_MUTED,
        )

    def _call(self, key: str):
        def invoke() -> None:
            callback = self.actions.get(key)
            if callback:
                callback()
        return invoke

    def update_data(self, game: GameState, analysis: AnalysisState) -> None:
        status_text, status_color = self._status_display(analysis)
        self.status_var.set(status_text)
        self.status_dot.configure(fg=status_color)

        if analysis.opening_name:
            text = analysis.opening_name
            if analysis.opening_eco:
                text += " · " + analysis.opening_eco
            self.opening_var.set(text)
            self.opening_box.pack(fill="x", padx=12, pady=(0, 10), before=self.lines_frame.master.winfo_children()[3])
        else:
            self.opening_box.pack_forget()

        self._render_lines(game, analysis)
        self._render_moves(game)

        self.play_button.configure(
            state=(tk.NORMAL if game.phase == GamePhase.USER_TURN and analysis.suggested_move else tk.DISABLED),
        )
        self._set_tool("pin", "Pinned" if self.actions.get("is_pinned", lambda: False)() else "Pin Top")
        self._set_tool("threats", "Threats: On" if game.show_threats else "Threats: Off")
        self._set_tool(
            "claim", "Claim Draw",
            enabled=game.session_active and game.board.can_claim_draw(),
        )
        self._set_tool("undo", "↶ Undo", enabled=len(game.moves) > 0)
        self._set_tool("redo", "↷ Redo", enabled=bool(game.redo_moves))
        self._set_tool("save", "Save Game", enabled=bool(game.moves))

    @staticmethod
    def _status_display(analysis: AnalysisState) -> tuple[str, str]:
        if analysis.status == AnalysisStatus.THINKING:
            return f"Stockfish thinking… depth {analysis.depth}", AppColors.WARNING
        if analysis.status == AnalysisStatus.READY:
            if analysis.from_cache:
                return "Instant answer · position cache", AppColors.ACCENT
            return f"Engine ready · depth {analysis.depth}", AppColors.ACCENT
        if analysis.status == AnalysisStatus.ENGINE_UNAVAILABLE:
            return analysis.message or "Stockfish engine not found", AppColors.DANGER
        if analysis.status == AnalysisStatus.ERROR:
            return analysis.message or "Engine error", AppColors.DANGER
        return "Engine idle", AppColors.TEXT_MUTED

    def _render_lines(self, game: GameState, analysis: AnalysisState) -> None:
        for child in self.lines_frame.winfo_children():
            child.destroy()
        if not analysis.lines:
            empty_text = analysis.message or (
                "Waiting for engine analysis…"
                if analysis.status == AnalysisStatus.THINKING
                else "Start a match or load a position to see\nthe top engine moves."
            )
            tk.Label(
                self.lines_frame,
                text=empty_text,
                justify="center", wraplength=320,
                bg=AppColors.PANEL, fg=AppColors.TEXT_MUTED,
                font=("Segoe UI", 9), pady=14,
            ).pack(fill="x")
            return

        for index, line in enumerate(analysis.lines[:3]):
            best = index == 0
            card = tk.Frame(
                self.lines_frame,
                bg="#30372B" if best else AppColors.PANEL_LIGHT,
                highlightbackground=AppColors.ACCENT if best else AppColors.BORDER,
                highlightthickness=1,
            )
            card.pack(fill="x", pady=3)
            badge = tk.Label(
                card, text=str(line.rank), width=2,
                bg=AppColors.ACCENT if best else AppColors.PANEL,
                fg="#151912" if best else AppColors.TEXT_SECONDARY,
                font=("Segoe UI", 9, "bold"),
            )
            badge.pack(side="left", padx=(7, 6), pady=6)
            tk.Label(
                card, text=line.san, bg=card["bg"],
                fg=AppColors.TEXT_PRIMARY,
                font=("Segoe UI", 14, "bold"),
            ).pack(side="left", padx=(0, 5), pady=4)
            favors_white = line.favors_white_from(game.board.turn)
            eval_bg = AppColors.EVAL_WHITE if favors_white else AppColors.EVAL_BLACK
            eval_fg = "#111111" if favors_white else "#FFFFFF"
            tk.Label(
                card, text=line.eval_label(game.board.turn),
                bg=eval_bg, fg=eval_fg,
                font=("Segoe UI", 9, "bold"), padx=5, pady=2,
            ).pack(side="right", padx=(5, 7), pady=6)
            tk.Label(
                card, text="d%d" % line.depth, bg=card["bg"],
                fg=AppColors.TEXT_MUTED, font=("Segoe UI", 8),
            ).pack(side="right", pady=6)
            continuation = " ".join(line.san_pv[1:6])
            if continuation:
                tk.Label(
                    card, text=continuation, anchor="w", bg=card["bg"],
                    fg=AppColors.TEXT_SECONDARY, font=("Segoe UI", 8),
                ).pack(fill="x", padx=39, pady=(0, 6))

    def _render_moves(self, game: GameState) -> None:
        for item in self.moves.get_children():
            self.moves.delete(item)
        for index in range(0, len(game.san_history), 2):
            number = index // 2 + 1
            white = game.san_history[index]
            black = game.san_history[index + 1] if index + 1 < len(game.san_history) else ""
            is_latest = index + 2 >= len(game.san_history)
            self.moves.insert(
                "", "end", values=(f"{number}.", white, black),
                tags=("latest",) if is_latest else (),
            )
        children = self.moves.get_children()
        if children:
            self.moves.see(children[-1])

    def _set_tool(self, key: str, label: str, enabled: bool = True) -> None:
        button = self._tool_buttons.get(key)
        if button is None:
            return
        button.configure(text=label, state=tk.NORMAL if enabled else tk.DISABLED)
