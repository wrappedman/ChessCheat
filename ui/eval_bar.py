"""Animated vertical evaluation bar."""

from __future__ import annotations

import math
import tkinter as tk

from models import AnalysisState
from theme import AppColors


class EvalBar(tk.Canvas):
    """Vertical centipawn bar with a smoothed transition and mate label."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master,
            width=42,
            background=AppColors.PANEL,
            highlightthickness=0,
            **kwargs,
        )
        self._fraction = 0.5
        self._target = 0.5
        self._label = "0.0"
        self._animation_pending = False
        self.bind("<Configure>", lambda _event: self._draw())
        self._draw()

    @staticmethod
    def _map_score(white_cp: float) -> float:
        try:
            value = 1.0 / (1.0 + math.exp(-white_cp / 320.0))
        except OverflowError:
            value = 0.02 if white_cp < 0 else 0.98
        return max(0.02, min(0.98, value))

    def set_analysis(self, analysis: AnalysisState, turn: bool) -> None:
        line = analysis.best_line
        if line is None:
            target = 0.5
            label = "0.0"
        else:
            target = self._map_score(line.white_score_cp(turn))
            label = line.eval_label(turn)
        changed = abs(target - self._target) >= 0.003 or label != self._label
        self._target = target
        self._label = label
        if changed and not self._animation_pending:
            self._animation_pending = True
            self._animate_step()
        else:
            self._draw()

    def _animate_step(self) -> None:
        delta = self._target - self._fraction
        if abs(delta) < 0.003:
            self._fraction = self._target
            self._animation_pending = False
            self._draw()
            return
        self._fraction += delta * 0.28
        self._draw()
        self.after(16, self._animate_step)

    def _draw(self) -> None:
        self.delete("all")
        width = max(24, self.winfo_width())
        height = max(80, self.winfo_height())
        self.create_rectangle(1, 1, width - 1, height - 1,
                              fill=AppColors.EVAL_BLACK,
                              outline=AppColors.BORDER)
        white_height = max(0, min(height - 2, (height - 2) * self._fraction))
        self.create_rectangle(1, height - white_height, width - 1, height - 1,
                              fill=AppColors.EVAL_WHITE, outline="")
        text_color = "#111111" if self._fraction > 0.55 else "#FFFFFF"
        self.create_text(width / 2, height / 2, text=self._label,
                         fill=text_color, font=("Segoe UI", 10, "bold"),
                         angle=90)
