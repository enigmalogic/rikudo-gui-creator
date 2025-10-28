"""
EVEN-R coordinate system utilities integrated with robust hex_parity implementation.
"""
from typing import List, Tuple, Set
from utils.hex_parity import get_hex_neighbors_evenr

def evenr_neighbors(row: int, col: int, max_rows: int, max_cols: int) -> List[Tuple[int, int]]:
    """Get all valid neighbors using robust EVEN-R calculation."""
    row_lengths = [max_cols] * max_rows
    if not (0 <= row < max_rows and 0 <= col < max_cols):
        return []
    return get_hex_neighbors_evenr(row_lengths, row, col)

def evenr_neighbors_ragged(row: int, col: int, row_lengths: List[int]) -> List[Tuple[int, int]]:
    """Get neighbors for ragged grids where each row can have different lengths."""
    if not (0 <= row < len(row_lengths) and 0 <= col < row_lengths[row]):
        return []
    return get_hex_neighbors_evenr(row_lengths, row, col)

def coordinate_to_string(row: int, col: int) -> str:
    """Convert coordinate tuple to string format used in JSON."""
    return f"{row},{col}"

def string_to_coordinate(coord_str: str) -> Tuple[int, int]:
    """Convert string coordinate back to tuple."""
    row, col = coord_str.split(',')
    return int(row), int(col)