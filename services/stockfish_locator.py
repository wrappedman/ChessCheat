"""Locates the local stockfish.exe binary on the machine."""

import os
import shutil
import sys
from typing import Optional


# Search order:
#   1. Path stored in the SQLite settings table (user provided).
#   2. CHESSCHEAT_ENGINE environment variable.
#   3. Directory of the running executable (release / PyInstaller layout,
#      including the PyInstaller one-file bundle extraction dir).
#   4. ./stockfish/stockfish.exe and ./assets/stockfish/stockfish.exe
#      (development layouts).
#   5. The user's Documents directory.
#   6. System PATH (via `where stockfish.exe`).


def locate(custom_path: Optional[str] = None) -> Optional[str]:
    """Returns the absolute path of the engine binary, or None
    when no executable can be found."""
    candidates = []

    if custom_path and custom_path.strip():
        candidates.append(custom_path.strip())

    env = os.environ.get("CHESSCHEAT_ENGINE")
    if env and env.strip():
        candidates.append(env.strip())

    # PyInstaller one-file apps extract Python files into _MEIPASS, but
    # Stockfish is shipped next to the actual ChessCheat.exe. Search both.
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "stockfish.exe"))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates.append(os.path.join(exe_dir, "stockfish.exe"))

    # Development layouts, relative to both the current directory and source.
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.extend([
        os.path.join("stockfish", "stockfish.exe"),
        os.path.join("assets", "stockfish", "stockfish.exe"),
        os.path.join(project_dir, "stockfish.exe"),
        os.path.join(project_dir, "stockfish", "stockfish.exe"),
        os.path.join(project_dir, "assets", "stockfish", "stockfish.exe"),
    ])

    # User documents directory.
    try:
        documents = os.path.join(os.path.expanduser("~"), "Documents")
        candidates.append(os.path.join(documents, "stockfish.exe"))
    except Exception:
        pass

    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)

    # PATH lookup.
    where = shutil.which("stockfish.exe") or shutil.which("stockfish")
    if where:
        return where

    return None
