# utils/hex_parity.py
"""
Parity-based neighbor calculation for EVEN-R hexagonal grids.

EVEN-R Convention:
- Even rows (0, 2, 4...) are shifted RIGHT by half a hexagon width
- Odd rows (1, 3, 5...) are at the base alignment

This means:
- EVEN row cells: diagonal neighbors lean RIGHT (column same or +1)
- ODD row cells: diagonal neighbors lean LEFT (column -1 or same)

Reference: Red Blob Games hexagonal grid guide
https://www.redblobgames.com/grids/hexagons/
"""

from __future__ import annotations
from typing import Iterable, List, Sequence, Tuple


# Deltas for EVEN rows (row % 2 == 0)
# Even rows are shifted RIGHT, so diagonals lean RIGHT
_EVEN_DELTAS: Tuple[Tuple[int, int], ...] = (
    (-1,  0),  # up-left (same column)
    (-1,  1),  # up-right (column +1)
    ( 0, -1),  # left
    ( 0,  1),  # right
    ( 1,  0),  # down-left (same column)
    ( 1,  1),  # down-right (column +1)
)

# Deltas for ODD rows (row % 2 == 1)
# Odd rows are at base alignment, so diagonals lean LEFT
_ODD_DELTAS: Tuple[Tuple[int, int], ...] = (
    (-1, -1),  # up-left (column -1)
    (-1,  0),  # up-right (same column)
    ( 0, -1),  # left
    ( 0,  1),  # right
    ( 1, -1),  # down-left (column -1)
    ( 1,  0),  # down-right (same column)
)

def get_hex_neighbors_evenr(
    row_lengths: Sequence[int],
    r: int,
    c: int,
) -> List[Tuple[int, int]]:
    """
    Return valid neighbor coordinates for (r, c) on a ragged hex grid
    using EVEN-R parity (even rows shifted right).

    Args:
        row_lengths: Length of each row; len(row_lengths) = row count
        r: Row index (0-based)
        c: Column index (0-based)

    Returns:
        List of (row, col) pairs for valid neighbors

    Raises:
        AssertionError: If coordinates are out of bounds
    """
    assert 0 <= r < len(row_lengths), f"row {r} out of range [0, {len(row_lengths)})"
    assert 0 <= c < row_lengths[r], f"col {c} out of range [0, {row_lengths[r]})"

    # Select delta pattern based on row parity
    deltas = _EVEN_DELTAS if (r % 2 == 0) else _ODD_DELTAS
    
    neighbors: List[Tuple[int, int]] = []
    for dr, dc in deltas:
        nr, nc = r + dr, c + dc
        
        # Validate neighbor is within grid bounds
        if 0 <= nr < len(row_lengths):
            if 0 <= nc < row_lengths[nr]:
                neighbors.append((nr, nc))
    
    return neighbors