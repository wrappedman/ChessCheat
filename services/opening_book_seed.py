"""Curated opening book lines (ECO classified) used to seed
the openings_book table on first launch.

Each entry: ECO code, opening name and the main line in SAN.
The database service walks every line with python-chess and
stores the FEN before each ply together with the recommended
next book move, giving instant (0ms) answers for known
openings.
"""

# (eco, name, [san moves from the initial position])
OPENING_SEEDS = [
    # ------------------------------------------------------------ Ruy Lopez
    ("C84", "Ruy Lopez, Closed Defense", [
        "e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7",
        "Re1", "b5", "Bb3", "d6", "c3", "O-O",
    ]),
    ("C68", "Ruy Lopez, Exchange Variation", [
        "e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6", "dxc6", "O-O", "f6",
        "d4", "exd4", "Qxd4", "Qxd4", "Nxd4",
    ]),
    ("C70", "Ruy Lopez, Berlin Defense", [
        "e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "O-O", "Nxe4", "d4", "Nd6",
        "Bxc6", "dxc6", "dxe5", "Nf5",
    ]),
    # ------------------------------------------------------------ Italian
    ("C50", "Italian Game", [
        "e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d4", "exd4",
        "cxd4", "Bb4+", "Nc3", "Nxe4",
    ]),
    ("C57", "Italian Game, Two Knights Defense", [
        "e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Na5",
        "Bb5+", "c6", "dxc6", "bxc6",
    ]),
    ("C51", "Evans Gambit", [
        "e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4", "Bxb4", "c3", "Ba5",
        "d4", "exd4", "O-O", "d6",
    ]),
    # ------------------------------------------------------------ Sicilian
    ("B90", "Sicilian Defense, Najdorf Variation", [
        "e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6",
        "Bg5", "e6", "f4", "Be7", "Qf3", "Qc7",
    ]),
    ("B70", "Sicilian Defense, Dragon Variation", [
        "e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6",
        "Be3", "Bg7", "f3", "O-O", "Qd2", "Nc6",
    ]),
    ("B80", "Sicilian Defense, Scheveningen Variation", [
        "e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "e6",
        "Be2", "a6", "O-O", "Be7", "f4", "O-O",
    ]),
    ("B22", "Sicilian Defense, Alapin Variation", [
        "e4", "c5", "c3", "Nf6", "e5", "Nd5", "d4", "cxd4", "Nf3", "Nc6",
        "Bc4", "e6",
    ]),
    ("B23", "Sicilian Defense, Closed Variation", [
        "e4", "c5", "Nc3", "Nc6", "g3", "g6", "Bg2", "Bg7", "d3", "d6",
        "f4", "Nf6",
    ]),
    # ------------------------------------------------------------ French
    ("C00", "French Defense", [
        "e4", "e6", "d4", "d5", "Nc3", "Nf6", "e5", "Nfd7", "f4", "c5",
        "Nf3", "Nc6",
    ]),
    ("C02", "French Defense, Advance Variation", [
        "e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6",
        "Be2", "cxd4",
    ]),
    ("C03", "French Defense, Tarrasch Variation", [
        "e4", "e6", "d4", "d5", "Nd2", "Nf6", "e5", "Nfd7", "Ndf3", "c5",
        "c3", "Nc6",
    ]),
    # ------------------------------------------------------------ Caro-Kann
    ("B10", "Caro-Kann Defense", [
        "e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Ng3", "Bg6",
        "h4", "h6", "Nf3", "Nd7",
    ]),
    ("B12", "Caro-Kann, Advance Variation", [
        "e4", "c6", "d4", "d5", "e5", "Bf5", "Nf3", "e6", "Be2", "c5",
        "O-O", "Nc6",
    ]),
    # ------------------------------------------------------------ Scandinavian
    ("B01", "Scandinavian Defense", [
        "e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "c6",
        "Bc4", "Bf5",
    ]),
    # ------------------------------------------------------------ Pirc / Modern
    ("B07", "Pirc Defense", [
        "e4", "d6", "d4", "Nf6", "Nc3", "g6", "Nf3", "Bg7", "Be2", "O-O",
        "O-O", "Nc6",
    ]),
    ("B06", "Modern Defense", [
        "e4", "g6", "d4", "Bg7", "Nc3", "d6", "Nf3", "Nf6", "Be2", "O-O",
        "O-O", "Nc6",
    ]),
    # ------------------------------------------------------------ King's Gambit
    ("C30", "King's Gambit Accepted", [
        "e4", "e5", "f4", "exf4", "Nf3", "d6", "Bc4", "h6", "d4", "g5",
        "O-O", "Bg7",
    ]),
    ("C33", "King's Gambit Accepted, King's Knight Gambit", [
        "e4", "e5", "f4", "exf4", "Nf3", "d5", "exd5", "Nf6",
    ]),
    # ------------------------------------------------------------ Vienna
    ("C25", "Vienna Game", [
        "e4", "e5", "Nc3", "Nf6", "f4", "d5", "fxe5", "Nxe4", "Nf3", "Be7",
        "d4", "O-O",
    ]),
    # ------------------------------------------------------------ Scotch
    ("C45", "Scotch Game", [
        "e4", "e5", "Nf3", "Nc6", "d4", "exd4", "Nxd4", "Nf6", "Nc3", "Bb4",
        "Bc4", "O-O",
    ]),
    # ------------------------------------------------------------ Petrov
    ("C42", "Petrov's Defense", [
        "e4", "e5", "Nf3", "Nf6", "Nxe5", "d6", "Nf3", "Nxe4", "d4", "d5",
        "Bd3", "Bd6",
    ]),
    # ------------------------------------------------------------ Queen's Gambit
    ("D30", "Queen's Gambit Declined", [
        "d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O",
        "Nf3", "h6",
    ]),
    ("D20", "Queen's Gambit Accepted", [
        "d4", "d5", "c4", "dxc4", "Nf3", "Nf6", "e3", "e6", "Bxc4", "c5",
        "O-O", "Nc6",
    ]),
    ("D02", "London System", [
        "d4", "d5", "Bf4", "Nf6", "e3", "e6", "Nf3", "c5", "c3", "Nc6",
        "Nbd2", "Bd6",
    ]),
    # ------------------------------------------------------------ King's Indian
    ("E90", "King's Indian Defense", [
        "d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O",
        "Be2", "e5", "O-O", "Nc6",
    ]),
    # ------------------------------------------------------------ Nimzo-Indian
    ("E20", "Nimzo-Indian Defense", [
        "d4", "Nf6", "c4", "e6", "Nc3", "Bb4", "e3", "O-O", "Bd3", "d5",
        "Nf3", "c5",
    ]),
    # ------------------------------------------------------------ Catalan
    ("E00", "Catalan Opening", [
        "d4", "Nf6", "c4", "e6", "g3", "d5", "Bg2", "Be7", "Nf3", "O-O",
        "O-O", "Nc6",
    ]),
    # ------------------------------------------------------------ Dutch
    ("A80", "Dutch Defense", [
        "d4", "f5", "c4", "Nf6", "g3", "e6", "Bg2", "Be7", "Nf3", "O-O",
        "O-O", "d6",
    ]),
    # ------------------------------------------------------------ English
    ("A10", "English Opening", [
        "c4", "e5", "Nc3", "Nf6", "Nf3", "Nc6", "g3", "d5", "cxd5", "Nxd5",
        "Bg2", "Nb6",
    ]),
    # ------------------------------------------------------------ Reti
    ("A09", "Reti Opening", [
        "Nf3", "d5", "c4", "e6", "g3", "Nf6", "Bg2", "Be7", "O-O", "O-O",
        "d4", "Nc6",
    ]),
    # ------------------------------------------------------------ Bird's
    ("A02", "Bird's Opening", [
        "f4", "d5", "Nf3", "g6", "e3", "Bg7", "Be2", "Nf6", "O-O", "O-O",
        "d4", "Nc6",
    ]),
    # ------------------------------------------------------------ Benoni
    ("A43", "Benoni Defense", [
        "d4", "Nf6", "c4", "c5", "d5", "e6", "Nc3", "exd5", "cxd5", "d6",
        "Nf3", "g6",
    ]),
    # ------------------------------------------------------------ Grunfeld
    ("D80", "Grünfeld Defense", [
        "d4", "Nf6", "c4", "g6", "Nc3", "d5", "cxd5", "Nxd5", "e4", "Nxc3",
        "bxc3", "Bg7",
    ]),
    # ------------------------------------------------------------ Closed Spanish
    ("C92", "Ruy Lopez, Closed, Main Line", [
        "e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7",
        "Re1", "b5", "Bb3", "d6", "c3", "O-O", "h3", "Na5",
    ]),
]
