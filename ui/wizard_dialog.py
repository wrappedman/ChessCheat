"""Three-step startup wizard for side and engine strength."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

import chess

from models import UserSide, WizardConfig
from theme import AppColors
from ui.piece_images import PieceImageCache


class SetupWizardDialog(tk.Toplevel):
    """Modal three-step setup: side, search strength, review/start."""

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("ChessCheat Setup")
        self.configure(bg=AppColors.PANEL)
        self.resizable(False, False)
        self.transient(master)
        self.result: Optional[WizardConfig] = None
        self.piece_images = PieceImageCache(self)
        self._step = 0
        self.side_var = tk.StringVar(value=UserSide.WHITE.name)
        self.time_var = tk.IntVar(value=2000)
        self.elo_var = tk.IntVar(value=2600)

        self._center(570, 590)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()
        self._build()
        self._render_step()
        self.focus_force()

    def _center(self, width: int, height: int) -> None:
        self.update_idletasks()
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build(self) -> None:
        outer = tk.Frame(self, bg=AppColors.PANEL, padx=24, pady=22)
        outer.pack(fill="both", expand=True)
        title = tk.Frame(outer, bg=AppColors.PANEL)
        title.pack(fill="x")
        tk.Label(
            title, text="♞  ChessCheat Setup", bg=AppColors.PANEL,
            fg=AppColors.TEXT_PRIMARY, font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        self.step_label = tk.Label(
            title, text="STEP 1 OF 3", bg=AppColors.PANEL,
            fg=AppColors.ACCENT, font=("Segoe UI", 9, "bold"),
        )
        self.step_label.pack(side="right", pady=8)

        self.progress = tk.Canvas(outer, height=7, bg=AppColors.PANEL, highlightthickness=0)
        self.progress.pack(fill="x", pady=(15, 20))
        self.progress.bind("<Configure>", lambda _event: self._draw_progress())

        self.content = tk.Frame(outer, bg=AppColors.PANEL)
        self.content.pack(fill="both", expand=True)

        footer = tk.Frame(outer, bg=AppColors.PANEL)
        footer.pack(fill="x", pady=(18, 0))
        self.back_button = tk.Button(
            footer, text="Back", command=self._back,
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, relief="flat", padx=18, pady=9,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        )
        self.back_button.pack(side="left")
        self.next_button = tk.Button(
            footer, text="Next", command=self._next,
            bg=AppColors.ACCENT, fg="#151912",
            activebackground=AppColors.ACCENT_DARK, relief="flat", padx=20, pady=9,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        )
        self.next_button.pack(side="right")

    def _draw_progress(self) -> None:
        self.progress.delete("all")
        width = max(1, self.progress.winfo_width())
        segment = width / 3
        for index in range(3):
            x1, x2 = index * segment + 2, (index + 1) * segment - 3
            color = AppColors.ACCENT if index <= self._step else AppColors.BORDER
            self.progress.create_rectangle(x1, 1, x2, 6, fill=color, outline=color)

    def _render_step(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        self.step_label.configure(text=f"STEP {self._step + 1} OF 3")
        self._draw_progress()
        if self._step == 0:
            self._render_side_step()
        elif self._step == 1:
            self._render_strength_step()
        else:
            self._render_review_step()
        self.back_button.configure(state=tk.NORMAL if self._step > 0 else tk.DISABLED)
        self.next_button.configure(text="Start Match" if self._step == 2 else "Next")

    def _section_title(self, text: str, subtitle: str = "") -> None:
        tk.Label(
            self.content, text=text, bg=AppColors.PANEL,
            fg=AppColors.TEXT_PRIMARY, anchor="w",
            font=("Segoe UI", 14, "bold"),
        ).pack(fill="x", pady=(0, 6))
        if subtitle:
            tk.Label(
                self.content, text=subtitle, bg=AppColors.PANEL,
                fg=AppColors.TEXT_SECONDARY, anchor="w",
                font=("Segoe UI", 9), wraplength=500, justify="left",
            ).pack(fill="x", pady=(0, 12))

    def _render_side_step(self) -> None:
        self._section_title("Select Player Color", "Choose your side, or open a free analysis board.")
        options = [
            (UserSide.WHITE, chess.WHITE, "White", "You move first. The engine suggests your opening move."),
            (UserSide.BLACK, chess.BLACK, "Black", "You move second. The board flips so your pieces sit at the bottom."),
            (UserSide.ANALYSIS, None, "Analysis Mode", "Play both sides, or import a FEN / PGN position."),
        ]
        for side, color, title, subtitle in options:
            selected = self.side_var.get() == side.name
            card = tk.Frame(
                self.content,
                bg="#2F3729" if selected else AppColors.PANEL_LIGHT,
                highlightbackground=AppColors.ACCENT if selected else AppColors.BORDER,
                highlightthickness=2 if selected else 1,
                padx=10, pady=9,
            )
            card.pack(fill="x", pady=5)
            radio = tk.Radiobutton(
                card, variable=self.side_var, value=side.name,
                command=self._render_step, bg=card["bg"],
                activebackground=card["bg"], selectcolor=AppColors.PANEL,
                fg=AppColors.ACCENT, highlightthickness=0,
            )
            radio.pack(side="left", padx=(0, 8))
            if color is None:
                tk.Label(
                    card, text="⚙", bg=card["bg"], fg=AppColors.TEXT_PRIMARY,
                    font=("Segoe UI Symbol", 28),
                ).pack(side="left", padx=(0, 12))
            else:
                image = self.piece_images.get(chess.Piece(chess.KING, color), 42)
                tk.Label(card, image=image, bg=card["bg"]).pack(
                    side="left", padx=(0, 12)
                )
            text_box = tk.Frame(card, bg=card["bg"])
            text_box.pack(side="left", fill="x", expand=True)
            tk.Label(
                text_box, text=title, bg=card["bg"], fg=AppColors.TEXT_PRIMARY,
                font=("Segoe UI", 11, "bold"), anchor="w",
            ).pack(fill="x")
            tk.Label(
                text_box, text=subtitle, bg=card["bg"], fg=AppColors.TEXT_SECONDARY,
                font=("Segoe UI", 9), anchor="w", wraplength=420, justify="left",
            ).pack(fill="x", pady=(2, 0))
            # Clicking anywhere on a card selects it.
            for widget in (card, text_box):
                widget.bind("<Button-1>", lambda _event, value=side.name: self._select_side(value))

    def _select_side(self, value: str) -> None:
        self.side_var.set(value)
        self._render_step()

    def _render_strength_step(self) -> None:
        self._section_title("Engine Strength & Search Depth", "More thinking time finds deeper lines; the ELO slider controls Stockfish's playing strength.")

        row = tk.Frame(self.content, bg=AppColors.PANEL)
        row.pack(fill="x", pady=(3, 0))
        tk.Label(
            row, text="Calculation time", bg=AppColors.PANEL,
            fg=AppColors.TEXT_PRIMARY, font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        self.time_value = tk.Label(
            row, text=self._time_label(), bg=AppColors.PANEL,
            fg=AppColors.ACCENT, font=("Segoe UI", 10, "bold"),
        )
        self.time_value.pack(side="right")
        tk.Scale(
            self.content, from_=500, to=5000, resolution=100,
            orient="horizontal", variable=self.time_var,
            showvalue=False, length=480, bg=AppColors.PANEL,
            troughcolor=AppColors.BORDER, activebackground=AppColors.ACCENT,
            highlightthickness=0, command=lambda _value: self._refresh_time_label(),
        ).pack(fill="x", pady=(7, 2))

        presets = tk.Frame(self.content, bg=AppColors.PANEL)
        presets.pack(fill="x", pady=(2, 16))
        for label, milliseconds in (("Fast · 0.5s", 500), ("Deep · 2s", 2000), ("Grandmaster · 5s", 5000)):
            tk.Button(
                presets, text=label,
                command=lambda value=milliseconds: self._set_time(value),
                bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
                activebackground=AppColors.BORDER, relief="flat",
                padx=9, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2",
            ).pack(side="left", padx=(0, 6))

        row2 = tk.Frame(self.content, bg=AppColors.PANEL)
        row2.pack(fill="x", pady=(5, 0))
        tk.Label(
            row2, text="Skill level (ELO)", bg=AppColors.PANEL,
            fg=AppColors.TEXT_PRIMARY, font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        self.elo_value = tk.Label(
            row2, text=f"{self.elo_var.get()} ELO", bg=AppColors.PANEL,
            fg=AppColors.ACCENT, font=("Segoe UI", 10, "bold"),
        )
        self.elo_value.pack(side="right")
        tk.Scale(
            self.content, from_=1500, to=3500, resolution=50,
            orient="horizontal", variable=self.elo_var,
            showvalue=False, length=480, bg=AppColors.PANEL,
            troughcolor=AppColors.BORDER, activebackground=AppColors.ACCENT,
            highlightthickness=0, command=lambda value: self.elo_value.configure(text=f"{int(float(value))} ELO"),
        ).pack(fill="x", pady=(7, 2))
        skill = self._skill_level()
        self.skill_label = tk.Label(
            self.content, text=f"UCI Skill Level {skill} of 20",
            bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
            font=("Segoe UI", 9), anchor="w",
        )
        self.skill_label.pack(fill="x")
        self.elo_var.trace_add("write", self._update_skill)

    def _update_skill(self, *_args) -> None:
        if hasattr(self, "skill_label"):
            self.skill_label.configure(text=f"UCI Skill Level {self._skill_level()} of 20")

    def _skill_level(self) -> int:
        return max(0, min(20, round((self.elo_var.get() - 1300) / 2000 * 20)))

    def _time_label(self) -> str:
        return f"{self.time_var.get() / 1000:.1f}s"

    def _refresh_time_label(self) -> None:
        if hasattr(self, "time_value"):
            self.time_value.configure(text=self._time_label())

    def _set_time(self, value: int) -> None:
        self.time_var.set(value)
        self._refresh_time_label()

    def _render_review_step(self) -> None:
        self._section_title("Review & Start", "Your choices are ready. You can change them by going back.")
        side = UserSide[self.side_var.get()]
        search = self.time_var.get()
        elo = self.elo_var.get()
        skill = self._skill_level()
        rows = [
            ("Playing as", side.value),
            ("Search time", f"{search / 1000:.1f}s"),
            ("Engine strength", f"{elo} ELO · UCI Skill Level {skill}/20"),
            ("Principal variations", "3 recommended moves"),
        ]
        for label, value in rows:
            row = tk.Frame(self.content, bg=AppColors.PANEL, pady=10)
            row.pack(fill="x")
            tk.Label(row, text=label, bg=AppColors.PANEL, fg=AppColors.TEXT_SECONDARY,
                     font=("Segoe UI", 10)).pack(side="left")
            tk.Label(row, text=value, bg=AppColors.PANEL, fg=AppColors.TEXT_PRIMARY,
                     font=("Segoe UI", 10, "bold")).pack(side="right")
            tk.Frame(self.content, bg=AppColors.BORDER, height=1).pack(fill="x")

        note = tk.Frame(self.content, bg=AppColors.PANEL_LIGHT, padx=10, pady=10)
        note.pack(fill="x", pady=(17, 0))
        tk.Label(
            note,
            text="A local Stockfish engine is needed for move analysis. "
                 "The build script downloads it automatically, or put stockfish.exe beside the app.",
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            font=("Segoe UI", 9), wraplength=475, justify="left",
        ).pack(anchor="w")

    def _back(self) -> None:
        if self._step > 0:
            self._step -= 1
            self._render_step()

    def _next(self) -> None:
        if self._step < 2:
            self._step += 1
            self._render_step()
            return
        self.result = WizardConfig(
            side=UserSide[self.side_var.get()],
            search_time_ms=self.time_var.get(),
            elo=self.elo_var.get(),
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
