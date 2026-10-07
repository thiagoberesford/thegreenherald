"""Hand-verified mini-crosswords. Each puzzle MUST have consistent crossings.

Add more puzzles here; the edition rotates them by date. To verify a new grid:
every letter at a row/column crossing must match in both words.
"""

PUZZLES = [
    {
        # Verified: across GREEN / AMASS / NOTES, down GRAIN / EXACT / NEARS
        "size": 5,
        "blacks": {(2, 2), (2, 4), (4, 2), (4, 4)},   # 1-based (row, col)
        "solution": [
            ["G", "R", "E", "E", "N"],
            ["R", ".", "X", ".", "E"],
            ["A", "M", "A", "S", "S"],
            ["I", ".", "C", ".", "R"],
            ["N", "O", "T", "E", "S"],
        ],
        "numbers": {(1, 1): 1, (1, 3): 2, (1, 5): 3, (3, 1): 4, (5, 1): 5},
        "clues": {
            "across": [
                (1, "The colour of the sustainable economy - and what you recycle for (5)"),
                (4, "Accumulate, as carbon does in the atmosphere (5)"),
                (5, "What COP negotiators trade at the summit (5)"),
            ],
            "down": [
                (1, "Wheat, rice or maize - a staple crop (5)"),
                (2, "To ___ a price, as carbon markets do to emissions (5)"),
                (3, "Gets closer - what the planet is doing to the 1.5 C limit (5)"),
            ],
        },
    },
]


def puzzle_for_date(date):
    """Rotate the library by day-of-year."""
    return PUZZLES[date.timetuple().tm_yday % len(PUZZLES)]
