# ChessCheat

**ChessCheat** is a local Windows chess assistant and position analyzer. Mirror a game by entering the moves on the board; when the opponent has moved, ChessCheat shows the strongest reply, an evaluation, and the engine's main continuation.

> The desktop app is written in Python with Tkinter. Chess rules are handled by `python-chess`; persistence uses Python's built-in SQLite driver; analysis uses a local Stockfish process over UCI.

## Why Python

The Flutter/Visual Studio build chain has been replaced with a small Python build. There is no Flutter SDK, Android SDK, Visual Studio, C++ compiler, or Chocolatey requirement. The GUI, SQLite, threading and process management come with Python. The only runtime Python package is `chess` (python-chess); PyInstaller is installed only when building the executable.

## Features

- Chess.com-inspired dark theme (`#312E2B` / `#262421`) and green/cream board
- Startup wizard: White, Black (auto-flipped board) or Analysis Mode; search time and ELO/Stockfish skill controls
- Three-column workspace: animated evaluation bar, interactive board, engine / move-history sidebar
- Click-to-move and drag-and-drop, legal-move dots, capture rings, coordinates, last-move highlight and check highlight
- Custom white and black PNG piece artwork on the board, board editor and promotion picker
- Solid green best-move arrow and dashed orange opponent-threat arrow
- MultiPV recommendations, evaluation in centipawns or mate, SAN continuation and opening/ECO label
- Optional **CPU Play** checkbox beside the header buttons: Stockfish plays the opposite side automatically while suggestions remain available on your turn. Opponent-threat previews are hidden in this mode; Analysis Mode stays manual. Unchecked by default.
- One-click **Play Suggested Move**
- FIDE move validation, castling, en passant, promotion picker, checkmate, stalemate, insufficient material, 50-move / threefold draw claims and automatic 75-move / fivefold draws
- SAN move history, undo/redo, board flip, FEN paste and manual board editor, PGN import/export
- Always-on-top pin, local saved games and position cache, plus a toolbar option to select a custom `stockfish.exe` path

## Build a Windows executable

1. Install standard **64-bit Python 3.10 or newer** with Tcl/Tk (the normal python.org installer includes it). If Python is missing, the script tries `winget` and then Chocolatey to install Python 3.12.
2. Run:

   ```bat
   build_windows.bat
   ```

The script creates a project-local virtual environment, installs the small `python-chess` package and PyInstaller, builds a single-file executable, downloads the official Windows x86-64 Stockfish release, and places the engine and any required `.nnue` files next to the app:

```
dist\ChessCheat.exe
dist\stockfish.exe
dist\*.nnue
```

Copy the **whole `dist` folder** to another Windows machine. No Python installation is needed on the target machine. The build does not install Visual Studio or other C++ toolchains. Expect roughly 150–250 MB for the build environment, executable, and engine; the script removes temporary PyInstaller files after a successful build.

If Python is already installed, you can run from source instead:

```bat
py -3 -m pip install -r requirements.txt
py -3 main.py
```

On other platforms, install Python 3 and Tk support, then use `python3 -m pip install -r requirements.txt` and `python3 main.py`.

## Project structure

```
ChessCheat/
├── main.py                         # Desktop entry point
├── models.py                       # Game, engine and database data models
├── theme.py                        # Chess.com-inspired color palette
├── requirements.txt                # Runtime dependency: chess/python-chess
├── build_windows.bat               # Lightweight PyInstaller + Stockfish build
├── assets/
│   └── pieces/                     # White and black chess-piece PNG artwork
├── services/
│   ├── database_service.py         # SQLite brain and opening-book seed
│   ├── opening_book_seed.py        # ECO opening lines
│   ├── stockfish_locator.py        # Stockfish binary discovery
│   └── uci_engine_service.py       # Threaded UCI process and MultiPV parser
├── state/
│   ├── analysis_controller.py      # Opening → cache → live-engine pipeline
│   └── game_controller.py          # Rules, mirrored workflow, undo/redo, PGN
└── ui/
    ├── analysis_sidebar.py         # Engine lines, history and tool buttons
    ├── board_geometry.py           # Board square/pixel mapping
    ├── chess_board_widget.py       # Tk Canvas chessboard and arrows
    ├── dialogs.py                  # FEN editor, PGN and promotion dialogs
    ├── eval_bar.py                 # Animated evaluation bar
    ├── home_screen.py              # Main three-column workspace
    ├── piece_images.py             # Bundled PNG pieces and Tk image cache
    └── wizard_dialog.py            # Startup setup wizard
```

## How it works

1. **Rules layer** — `python-chess` validates every move and handles FIDE chess rules.
2. **Local knowledge layer** — SQLite database `chesscheat_brain.db` stores 37 ECO-classified opening lines, saved PGNs, settings, and previously analyzed positions.
3. **Engine layer** — Stockfish runs as a background process speaking UCI. Its `info depth`, `score cp/mate`, and `pv` output streams to the evaluation bar and top recommendations. A short follow-up search displays the opponent's likely reply as a threat arrow.

The SQLite database is stored under `%LOCALAPPDATA%\ChessCheat\chesscheat_brain.db` on Windows, and under the user's XDG data directory on Linux.

## Stockfish

ChessCheat looks for `stockfish.exe` next to the application, in the PyInstaller bundle directory, in `stockfish/` or `assets/stockfish/`, in the user's Documents folder, or on `PATH`. You can also set `CHESSCHEAT_ENGINE` to a custom engine path.

The build script obtains Stockfish from the official [Stockfish GitHub releases](https://github.com/official-stockfish/Stockfish). Stockfish is GPL-licensed; keep the corresponding license and source notices when redistributing it. ChessCheat uses no network service for chess analysis.

## Fair-play notice

ChessCheat is intended for study, training and casual analysis. Using real-time engine assistance during rated online games violates the fair-play rules of virtually all chess platforms.
