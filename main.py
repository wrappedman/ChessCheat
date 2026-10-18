"""ChessCheat entry point.

Run with ``python main.py`` after installing requirements.txt, or build a
Windows executable with ``build_windows.bat``.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from ui.home_screen import ChessCheatApp


def main() -> int:
    try:
        app = ChessCheatApp()
    except Exception as exc:
        # Tkinter is included with standard python.org Windows builds.
        root = getattr(tk, "_default_root", None)
        if root is None:
            root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ChessCheat could not start",
            "The application could not initialize. Confirm that standard 64-bit "
            "Python has Tcl/Tk enabled, then try again.\n\n"
            f"Details: {exc}",
            parent=root,
        )
        root.destroy()
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
