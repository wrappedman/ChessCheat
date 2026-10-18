"""Main ChessCheat desktop workspace and application composition root."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from models import StatusKind
from services.database_service import DatabaseService
from services.uci_engine_service import UciEngineService
from state.analysis_controller import AnalysisController
from state.game_controller import GameController
from state.cpu_controller import CpuController
from theme import AppColors
from ui.analysis_sidebar import AnalysisSidebar
from ui.chess_board_widget import ChessBoardCanvas
from ui.dialogs import show_fen_dialog, show_pgn_dialog, show_promotion_dialog
from ui.eval_bar import EvalBar
from ui.wizard_dialog import SetupWizardDialog


class ChessCheatApp(tk.Tk):
    """Tkinter app root: services, controllers, layout and user actions."""

    def __init__(self) -> None:
        super().__init__()
        self.title("ChessCheat")
        self.geometry("1440x940")
        self.minsize(1080, 720)
        self.configure(bg=AppColors.BACKGROUND)
        self._pinned = False
        self._render_queued = False
        self._last_promotion = None
        self._closed = False

        self._configure_styles()
        self.database = DatabaseService()
        self.engine = UciEngineService(
            status_callback=self._engine_status_changed,
            custom_path=self.database.get_setting("engine_path"),
        )
        self.analysis = AnalysisController(
            self.database, self.engine, on_change=self._analysis_changed
        )
        self.game = GameController(
            self.database, self.analysis, on_change=self._game_changed
        )
        self.cpu = CpuController(self.game)
        self._build_layout()
        self.after(50, self._poll_cpu)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(250, self._show_startup_wizard)
        self.after(100, self._render)

    def _configure_styles(self) -> None:
        try:
            ttk.Style(self).theme_use("clam")
        except tk.TclError:
            pass
        ttk_style = ttk.Style(self)
        ttk_style.configure(
            "Treeview", background=AppColors.BACKGROUND,
            fieldbackground=AppColors.BACKGROUND, foreground=AppColors.TEXT_PRIMARY,
            rowheight=25, borderwidth=0, font=("Segoe UI", 9),
        )
        ttk_style.configure(
            "Treeview.Heading", background=AppColors.PANEL_LIGHT,
            foreground=AppColors.TEXT_SECONDARY, relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        ttk_style.map(
            "Treeview", background=[("selected", AppColors.ACCENT_DARK)],
            foreground=[("selected", AppColors.TEXT_PRIMARY)],
        )
        ttk_style.configure("TNotebook", background=AppColors.PANEL, borderwidth=0)
        ttk_style.configure(
            "TNotebook.Tab", background=AppColors.PANEL_LIGHT,
            foreground=AppColors.TEXT_SECONDARY, padding=(12, 7),
        )
        ttk_style.map(
            "TNotebook.Tab", background=[("selected", AppColors.ACCENT_DARK)],
            foreground=[("selected", AppColors.TEXT_PRIMARY)],
        )

    def _build_layout(self) -> None:
        header = tk.Frame(self, bg=AppColors.PANEL, height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        title = tk.Frame(header, bg=AppColors.PANEL)
        title.pack(side="left", fill="y", padx=15)
        tk.Label(
            title, text="♞", bg=AppColors.PANEL, fg=AppColors.ACCENT,
            font=("Segoe UI Symbol", 22),
        ).pack(side="left", padx=(0, 8))
        tk.Label(
            title, text="ChessCheat", bg=AppColors.PANEL,
            fg=AppColors.TEXT_PRIMARY, font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        tk.Label(
            title, text="1.0.2", bg="#283521", fg=AppColors.ACCENT,
            font=("Segoe UI", 8, "bold"), padx=6, pady=2,
        ).pack(side="left", padx=8)

        self.header_status = tk.Label(
            header, text="Local chess analysis", bg=AppColors.PANEL,
            fg=AppColors.TEXT_SECONDARY, font=("Segoe UI", 9),
        )
        self.header_status.pack(side="left", padx=20)

        actions = tk.Frame(header, bg=AppColors.PANEL)
        actions.pack(side="right", padx=12)
        self._header_button(actions, "＋  New Match", self._show_wizard).pack(side="left", padx=4)
        self.pin_button = self._header_button(actions, "⌖  Always on Top", self._toggle_pin)
        self.pin_button.pack(side="left", padx=4)
        self.cpu_play_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions, text="CPU Play", variable=self.cpu_play_var,
            command=self._toggle_cpu_play, bg=AppColors.PANEL,
            fg=AppColors.TEXT_SECONDARY, selectcolor=AppColors.PANEL_LIGHT,
            activebackground=AppColors.PANEL, activeforeground=AppColors.TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=4)

        body = tk.Frame(self, bg=AppColors.BACKGROUND)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self.eval_bar = EvalBar(body)
        self.eval_bar.grid(row=0, column=0, sticky="ns", padx=(8, 0), pady=12)

        center = tk.Frame(body, bg=AppColors.BACKGROUND)
        center.grid(row=0, column=1, sticky="nsew")
        center.grid_rowconfigure(0, weight=1)
        center.grid_columnconfigure(0, weight=1)
        self.board_area = tk.Frame(center, bg=AppColors.BACKGROUND)
        self.board_area.grid(row=0, column=0, sticky="nsew")
        self.board_area.grid_rowconfigure(0, weight=1)
        self.board_area.grid_columnconfigure(0, weight=1)

        self.board_canvas = ChessBoardCanvas(self.board_area, self.game)
        self.board_canvas.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 4))

        self.idle_frame = tk.Frame(self.board_area, bg=AppColors.BACKGROUND)
        self._build_idle_screen()

        status = tk.Frame(center, bg=AppColors.PANEL, padx=10, pady=6)
        status.grid(row=1, column=0, sticky="ew", padx=12, pady=(3, 12))
        status.grid_columnconfigure(1, weight=1)
        self.status_icon = tk.Label(status, text="●", bg=AppColors.PANEL,
                                    fg=AppColors.INFO, font=("Segoe UI", 10, "bold"))
        self.status_icon.grid(row=0, column=0, sticky="w", padx=(0, 7))
        self.status_label = tk.Label(
            status, text="Welcome to ChessCheat.", bg=AppColors.PANEL,
            fg=AppColors.TEXT_PRIMARY, anchor="w", font=("Segoe UI", 9, "bold"),
        )
        self.status_label.grid(row=0, column=1, sticky="ew")
        self.depth_label = tk.Label(
            status, text="", bg=AppColors.PANEL,
            fg=AppColors.TEXT_MUTED, font=("Segoe UI", 8),
        )
        self.depth_label.grid(row=0, column=2, sticky="e", padx=(8, 4))
        self.fen_label = tk.Label(
            status, text="", bg=AppColors.PANEL,
            fg=AppColors.TEXT_MUTED, anchor="w", font=("Consolas", 8),
        )
        self.fen_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        tk.Button(
            status, text="Copy FEN", command=self._copy_fen,
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, relief="flat",
            font=("Segoe UI", 8, "bold"), padx=7, pady=3,
        ).grid(row=1, column=2, sticky="e", pady=(3, 0))

        self.sidebar = AnalysisSidebar(body, actions=self._sidebar_actions())
        self.sidebar.grid(row=0, column=2, sticky="ns", padx=(0, 0), pady=0)
        self.sidebar.configure(width=360)

    def _header_button(self, master, text: str, command) -> tk.Button:
        return tk.Button(
            master, text=text, command=command,
            bg=AppColors.PANEL_LIGHT, fg=AppColors.TEXT_SECONDARY,
            activebackground=AppColors.BORDER, activeforeground=AppColors.TEXT_PRIMARY,
            relief="flat", padx=10, pady=7, font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )

    def _sidebar_actions(self) -> dict:
        return {
            "undo": self.game.undo,
            "redo": self.game.redo,
            "flip": self.game.flip,
            "fen": self._open_fen_dialog,
            "engine_path": self._choose_engine,
            "pgn_import": lambda: self._open_pgn_dialog("import"),
            "pgn_export": lambda: self._open_pgn_dialog("export"),
            "pin": self._toggle_pin,
            "is_pinned": lambda: self._pinned,
            "threats": self.game.toggle_threats,
            "save": self._save_game,
            "new": self._show_wizard,
            "claim": self.game.claim_draw,
            "play": self.game.play_suggested,
        }

    def _build_idle_screen(self) -> None:
        inner = tk.Frame(self.idle_frame, bg=AppColors.BACKGROUND)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            inner, text="♞", bg=AppColors.BACKGROUND,
            fg=AppColors.ACCENT, font=("Segoe UI Symbol", 64),
        ).pack()
        tk.Label(
            inner, text="Welcome to ChessCheat", bg=AppColors.BACKGROUND,
            fg=AppColors.TEXT_PRIMARY, font=("Segoe UI", 22, "bold"),
        ).pack(pady=(6, 6))
        tk.Label(
            inner,
            text="Mirror a game, enter the opponent's move, and see the best\n"
                 "counter-move highlighted by a local Stockfish engine.",
            bg=AppColors.BACKGROUND, fg=AppColors.TEXT_SECONDARY,
            justify="center", font=("Segoe UI", 10),
        ).pack(pady=(0, 18))
        buttons = tk.Frame(inner, bg=AppColors.BACKGROUND)
        buttons.pack()
        self._idle_button(buttons, "Start Match", self._show_wizard, primary=True).grid(row=0, column=0, padx=4)
        self._idle_button(buttons, "Load FEN / Editor", self._open_fen_dialog).grid(row=0, column=1, padx=4)
        self._idle_button(buttons, "Import PGN", lambda: self._open_pgn_dialog("import")).grid(row=0, column=2, padx=4)

    @staticmethod
    def _idle_button(master, text: str, command, primary: bool = False) -> tk.Button:
        return tk.Button(
            master, text=text, command=command,
            bg=AppColors.ACCENT if primary else AppColors.PANEL_LIGHT,
            fg="#151912" if primary else AppColors.TEXT_SECONDARY,
            activebackground=AppColors.ACCENT_DARK if primary else AppColors.BORDER,
            relief="flat", padx=14, pady=9,
            font=("Segoe UI", 9, "bold"), cursor="hand2",
        )

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def _queue_render(self) -> None:
        if self._closed or self._render_queued:
            return
        self._render_queued = True
        try:
            self.after(0, self._render)
        except tk.TclError:
            self._render_queued = False

    def _game_changed(self, _state) -> None:
        self._queue_render()

    def _analysis_changed(self, _state) -> None:
        self._queue_render()

    def _engine_status_changed(self, message: str) -> None:
        # UCI worker callbacks run on a background thread; marshal to Tk.
        if self._closed:
            return
        try:
            self.after(0, lambda: self.header_status.configure(text=message))
        except tk.TclError:
            pass

    def _toggle_cpu_play(self) -> None:
        self.game.cpu_play = self.cpu_play_var.get()
        self.cpu.sync()
        if self.game.state.should_analyze:
            self.game._request_analysis()
        self._queue_render()

    def _poll_cpu(self) -> None:
        if self._closed:
            return
        self.cpu.sync()
        self.cpu.poll()
        self.after(50, self._poll_cpu)

    def _render(self) -> None:
        self._render_queued = False
        if self._closed:
            return
        game = self.game.state
        analysis = self.analysis.state
        if game.session_active:
            self.idle_frame.grid_remove()
            self.board_canvas.grid()
            self.board_canvas.set_state(game, analysis)
        else:
            self.board_canvas.grid_remove()
            self.idle_frame.grid(row=0, column=0, sticky="nsew")
        self.status_label.configure(text=game.status_message)
        color = {
            StatusKind.INFO: AppColors.INFO,
            StatusKind.SUCCESS: AppColors.ACCENT,
            StatusKind.WARNING: AppColors.WARNING,
            StatusKind.ERROR: AppColors.DANGER,
        }[game.status_kind]
        self.status_icon.configure(fg=color)
        self.fen_label.configure(text=game.board.fen())
        self.depth_label.configure(text=f"depth {analysis.depth}" if analysis.depth else "")
        self.header_status.configure(
            text=("Analysis mode" if game.is_analysis_mode else
                  f"Playing as {game.user_side.value}" if game.session_active else "Local chess analysis")
        )
        self.eval_bar.set_analysis(analysis, game.board.turn)
        self.sidebar.update_data(game, analysis)
        if game.pending_promotion and game.pending_promotion != self._last_promotion:
            self._last_promotion = game.pending_promotion
            self.after_idle(self._handle_promotion)
        elif game.pending_promotion is None:
            self._last_promotion = None

    # ------------------------------------------------------------------
    # Dialogs and actions
    # ------------------------------------------------------------------

    def _show_startup_wizard(self) -> None:
        if self._closed or self.game.state.session_active:
            return
        self._show_wizard()

    def _show_wizard(self) -> None:
        if self._closed:
            return
        dialog = SetupWizardDialog(self)
        self.wait_window(dialog)
        if dialog.result is not None:
            self.game.start_match(dialog.result)

    def _choose_engine(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Select Stockfish engine",
            filetypes=(("Windows executable", "*.exe"), ("All files", "*.*")),
        )
        if not path:
            return
        self.engine.set_engine_path(path)
        try:
            self.database.set_setting("engine_path", path)
            self.status_label.configure(
                text="Stockfish path saved. Restart the app to switch a running engine."
            )
        except Exception as exc:
            self.status_label.configure(text=f"Could not save engine path: {exc}")

    def _open_fen_dialog(self) -> None:
        show_fen_dialog(self, self.game.state.board, self.game.set_fen)

    def _open_pgn_dialog(self, mode: str) -> None:
        show_pgn_dialog(
            self,
            mode=mode,
            export_text=self.game.export_pgn(),
            on_import=self.game.import_pgn,
        )

    def _handle_promotion(self) -> None:
        pending = self.game.state.pending_promotion
        if pending is None or self._closed:
            return
        piece = self.game.state.board.piece_at(pending[0])
        color = piece.color if piece else self.game.state.board.turn
        choice = show_promotion_dialog(self, color)
        if choice is None:
            self.game.cancel_pending_promotion()
        else:
            self.game.complete_pending_promotion(choice)

    def _toggle_pin(self) -> None:
        self._pinned = not self._pinned
        try:
            self.attributes("-topmost", self._pinned)
        except tk.TclError:
            pass
        self.pin_button.configure(text="⌖  Pinned" if self._pinned else "⌖  Always on Top")
        self._queue_render()

    def _copy_fen(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.game.state.board.fen())
        self.status_label.configure(text="FEN copied to clipboard.")

    def _save_game(self) -> None:
        if self.game.save_current_game():
            self.status_label.configure(text="Game saved to the local database.")

    def _on_close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.engine.stop()
        except Exception:
            pass
        try:
            self.database.close()
        except Exception:
            pass
        self.destroy()
