"""
Shared types for Rikudo Puzzle Creator.
Separated to avoid circular imports between modules.
"""
from enum import Enum
from typing import Optional, Tuple

class CellState(Enum):
    """Possible states for grid cells."""
    EMPTY = "empty"           # Playable cell without value
    PREFILLED = "prefilled"   # Playable cell with number
    NONPLAYABLE = "blocked"   # Blocked/hole cells
    CENTER = "center"         # Special center cell
    HOLE = "hole"             # Cell doesn't exist (empty space)

class ValidationError:
    """Represents a validation error with severity and description."""
    def __init__(self, severity: str, message: str, location: Optional[Tuple[int, int]] = None):
        self.severity = severity  # "error", "warning", "info"
        self.message = message
        self.location = location
    
    def __str__(self):
        loc_str = f" at {self.location}" if self.location else ""
        return f"{self.severity.upper()}: {self.message}{loc_str}"