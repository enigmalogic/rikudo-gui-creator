"""
HexGrid - Clean grid state manager for Rikudo puzzle creator.

This module provides the core grid representation using EVEN-R coordinate system.
Integrates with command pattern for undo/redo functionality.

Architecture:
    - State management only (no validation, no export here)
    - Delegates neighbor calculation to canonical EVEN-R helper
    - All mutations through command system
    - All attributes initialized in __init__ (no hasattr checks needed)
"""
from typing import Dict, Tuple, Optional, Set, List
from utils.evenr import coordinate_to_string, string_to_coordinate
import json
from utils.hex_parity import get_hex_neighbors_evenr
# Import shared types
from core.types import CellState, ValidationError
from core.commands import (
    # Command,
    CommandHistory,
    SetCellStateCommand,
    CycleCellStateCommand,
    SetCellValueCommand,
    AddDotConstraintCommand,
    RemoveDotConstraintCommand,
    ImportPuzzleCommand,
    BatchCommand
)


class HexGrid:
    """
    Grid state manager for Rikudo puzzles using EVEN-R coordinate system.
    
    Responsibilities:
        - Store cell states (empty, prefilled, blocked, holes, center)
        - Store dot constraints between cells
        - Provide neighbor calculations (delegates to canonical helper)
        - Integrate with command system for undo/redo
    
    Attributes:
        rows: Number of rows in grid
        cols: Number of columns in grid
        cell_states: Mapping of (row, col) to (CellState, optional_value)
        dot_constraints: Set of constraint pairs (normalized)
        center_location: Optional center cell coordinate
        command_history: Undo/redo command stack
    """
    
    def __init__(self, rows: int, cols: int):
        """
        Initialize a new hex grid.
        
        Args:
            rows: Number of rows (must be > 0)
            cols: Number of columns (must be > 0)
        """
        if rows <= 0 or cols <= 0:
            raise ValueError(f"Grid dimensions must be positive: {rows}x{cols}")
        
        # Grid dimensions
        self.rows: int = rows
        self.cols: int = cols
        
        # Cell states: (row, col) -> (CellState, Optional[int])
        self.cell_states: Dict[Tuple[int, int], Tuple[CellState, Optional[int]]] = {}
        
        # Dot constraints: Set of normalized (cell1, cell2) tuples
        self.dot_constraints: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
        
        # Special center cell (only one allowed)
        self.center_location: Optional[Tuple[int, int]] = None
        
        # Command history for undo/redo
        self.command_history: CommandHistory = CommandHistory(max_history=100)
        
        # Initialize all cells as EMPTY
        self._initialize_empty_grid()
    
    def _initialize_empty_grid(self) -> None:
        """Initialize all cells to EMPTY state (not recorded in history)."""
        for row in range(self.rows):
            for col in range(self.cols):
                self.cell_states[(row, col)] = (CellState.EMPTY, None)
    
    # =============================================================================
    # CELL STATE QUERIES
    # =============================================================================
    
    def cell_exists(self, row: int, col: int) -> bool:
        """
        Check if a cell exists in the grid (is not a hole and within bounds).
        
        Args:
            row: Row coordinate
            col: Column coordinate
        
        Returns:
            True if cell exists and is not a hole
        """
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return False
        
        state, _ = self.cell_states.get((row, col), (CellState.HOLE, None))
        return state != CellState.HOLE
    
    def get_cell_state(self, row: int, col: int) -> Tuple[CellState, Optional[int]]:
        """
        Get the state and value of a cell.
        
        Args:
            row: Row coordinate
            col: Column coordinate
        
        Returns:
            Tuple of (CellState, optional_value)
            Returns (HOLE, None) for out-of-bounds cells
        """
        return self.cell_states.get((row, col), (CellState.HOLE, None))
    
    def get_all_existing_cells(self) -> Set[Tuple[int, int]]:
        """
        Get coordinates of all cells that exist (are not holes).
        
        Returns:
            Set of (row, col) coordinates
        """
        existing = set()
        for (row, col), (state, _) in self.cell_states.items():
            if state != CellState.HOLE:
                existing.add((row, col))
        return existing
    
    def get_playable_cells(self) -> Dict[Tuple[int, int], Optional[int]]:
        """
        Get all playable cells (EMPTY or PREFILLED) with their values.
        
        Returns:
            Dict mapping (row, col) to optional value
        """
        playable = {}
        for (row, col), (state, value) in self.cell_states.items():
            if state in (CellState.EMPTY, CellState.PREFILLED):
                playable[(row, col)] = value
        return playable
    
    def get_max_possible_value(self) -> int:
        """
        Calculate maximum value based on number of playable cells.
        
        Returns:
            Count of playable cells (the max value for the puzzle)
        """
        return len(self.get_playable_cells())
    
    def has_duplicate_value(self, value: int, exclude_cell: Optional[Tuple[int, int]] = None) -> bool:
        """
        Check if a value already exists in the puzzle.
        
        Args:
            value: Value to check for
            exclude_cell: Optional cell to exclude from check
        
        Returns:
            True if value exists elsewhere in the puzzle
        """
        for (row, col), (state, cell_value) in self.cell_states.items():
            if exclude_cell and (row, col) == exclude_cell:
                continue
            if state == CellState.PREFILLED and cell_value == value:
                return True
        return False
    
    # =============================================================================
    # NEIGHBOR CALCULATION (EVEN-R)
    # =============================================================================
    
    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Get all valid neighbors using canonical EVEN-R helper.
        
        This delegates to utils.hex_parity.get_hex_neighbors_evenr() to ensure
        consistency between GUI, export, and all adjacency calculations.
        
        Args:
            row: Row coordinate
            col: Column coordinate
        
        Returns:
            List of neighboring (row, col) coordinates that exist
        """
        if not self.cell_exists(row, col):
            return []
        
        # Build row_lengths for rectangular grid
        # TODO: For ragged grids, compute actual row lengths
        row_lengths = [self.cols] * self.rows
        
        # Get neighbors from canonical EVEN-R helper
        candidates = get_hex_neighbors_evenr(row_lengths, row, col)
        
        # Filter to only existing cells (not holes)
        neighbors = []
        for nr, nc in candidates:
            if self.cell_exists(nr, nc):
                neighbors.append((nr, nc))
        
        return neighbors
    
    # =============================================================================
    # DIRECT CELL STATE MUTATIONS (used by commands)
    # =============================================================================
    
    def set_cell_state(self, row: int, col: int, state: CellState, value: Optional[int] = None) -> None:
        """
        Set the state of a cell (direct method, use cmd_* for undo/redo).
        
        Args:
            row: Row coordinate
            col: Column coordinate
            state: New cell state
            value: Optional value for PREFILLED cells
        """
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return
        
        # Handle CENTER cell logic (only one center allowed)
        if state == CellState.CENTER:
            # Clear previous center if exists
            if self.center_location is not None:
                old_row, old_col = self.center_location
                self.cell_states[(old_row, old_col)] = (CellState.EMPTY, None)
            self.center_location = (row, col)
            value = None  # Center cells don't have values
        elif self.center_location == (row, col) and state != CellState.CENTER:
            # This cell was center, now it's not
            self.center_location = None
        
        self.cell_states[(row, col)] = (state, value)
    
    def cycle_cell_state(self, row: int, col: int) -> None:
        """
        Cycle through cell states (direct method, use cmd_* for undo/redo).
        
        Cycle order:
            EMPTY → NONPLAYABLE → HOLE → EMPTY
            PREFILLED → NONPLAYABLE → HOLE → EMPTY
            CENTER → EMPTY
        
        Args:
            row: Row coordinate
            col: Column coordinate
        """
        current_state, _ = self.get_cell_state(row, col)
        
        if current_state == CellState.EMPTY:
            self.set_cell_state(row, col, CellState.NONPLAYABLE)
        elif current_state == CellState.NONPLAYABLE:
            self.set_cell_state(row, col, CellState.HOLE)
        elif current_state == CellState.HOLE:
            self.set_cell_state(row, col, CellState.EMPTY)
        elif current_state == CellState.PREFILLED:
            self.set_cell_state(row, col, CellState.NONPLAYABLE)
        elif current_state == CellState.CENTER:
            self.set_cell_state(row, col, CellState.EMPTY)
    
    def set_cell_value(self, row: int, col: int, value: int) -> bool:
        """
        Set a numeric value in a cell (direct method, use cmd_* for undo/redo).
        
        Args:
            row: Row coordinate
            col: Column coordinate
            value: Value to set (1 to max_value)
        
        Returns:
            True if successful, False if invalid
        """
        if not self.cell_exists(row, col):
            return False
        
        max_val = self.get_max_possible_value()
        if not (1 <= value <= max_val):
            return False
        
        if self.has_duplicate_value(value, exclude_cell=(row, col)):
            return False
        
        self.set_cell_state(row, col, CellState.PREFILLED, value)
        return True
    
    def clear_cell_value(self, row: int, col: int) -> None:
        """Clear value from a cell (converts to EMPTY)."""
        if self.cell_exists(row, col):
            self.set_cell_state(row, col, CellState.EMPTY)
    
    # =============================================================================
    # CONSTRAINT MANAGEMENT
    # =============================================================================
    
    def _normalize_constraint(self, cell1: Tuple[int, int], cell2: Tuple[int, int]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Normalize constraint pair (smaller cell first)."""
        return tuple(sorted([cell1, cell2]))
    
    def add_dot_constraint(self, cell1: Tuple[int, int], cell2: Tuple[int, int]) -> bool:
        """
        Add a dot constraint between two adjacent cells (direct method).
        
        Args:
            cell1: First cell coordinate
            cell2: Second cell coordinate
        
        Returns:
            True if constraint was added, False if invalid
        """
        r1, c1 = cell1
        r2, c2 = cell2
        
        # Check both cells exist
        if not (self.cell_exists(r1, c1) and self.cell_exists(r2, c2)):
            return False
        
        # Check cells are adjacent
        if cell2 not in self.get_neighbors(r1, c1):
            return False
        
        # Check both cells are playable
        state1, _ = self.get_cell_state(r1, c1)
        state2, _ = self.get_cell_state(r2, c2)
        
        if state1 not in (CellState.EMPTY, CellState.PREFILLED) or \
           state2 not in (CellState.EMPTY, CellState.PREFILLED):
            return False
        
        # Add normalized constraint
        constraint = self._normalize_constraint(cell1, cell2)
        self.dot_constraints.add(constraint)
        return True
    
    def remove_dot_constraint(self, cell1: Tuple[int, int], cell2: Tuple[int, int]) -> bool:
        """
        Remove a dot constraint between two cells (direct method).
        
        Args:
            cell1: First cell coordinate
            cell2: Second cell coordinate
        
        Returns:
            True if constraint was removed, False if didn't exist
        """
        constraint = self._normalize_constraint(cell1, cell2)
        if constraint in self.dot_constraints:
            self.dot_constraints.remove(constraint)
            return True
        return False
    
    def has_dot_constraint(self, cell1: Tuple[int, int], cell2: Tuple[int, int]) -> bool:
        """
        Check if there's a dot constraint between two cells.
        
        Args:
            cell1: First cell coordinate
            cell2: Second cell coordinate
        
        Returns:
            True if constraint exists
        """
        constraint = self._normalize_constraint(cell1, cell2)
        return constraint in self.dot_constraints
    
    # =============================================================================
    # COMMAND-BASED MUTATIONS (use these for user operations with undo/redo)
    # =============================================================================
    
    def cmd_set_cell_state(self, row: int, col: int, state: CellState, value: Optional[int] = None) -> bool:
        """Set cell state using command system (for undo/redo)."""
        command = SetCellStateCommand(row, col, state, value)
        return self.command_history.execute_command(command, self)
    
    def cmd_cycle_cell_state(self, row: int, col: int) -> bool:
        """Cycle cell state using command system (for undo/redo)."""
        command = CycleCellStateCommand(row, col)
        return self.command_history.execute_command(command, self)
    
    def cmd_set_cell_value(self, row: int, col: int, value: int) -> bool:
        """Set cell value using command system (for undo/redo)."""
        command = SetCellValueCommand(row, col, value)
        return self.command_history.execute_command(command, self)
    
    def cmd_add_dot_constraint(self, cell1: Tuple[int, int], cell2: Tuple[int, int]) -> bool:
        """Add dot constraint using command system (for undo/redo)."""
        command = AddDotConstraintCommand(cell1, cell2)
        return self.command_history.execute_command(command, self)
    
    def cmd_remove_dot_constraint(self, cell1: Tuple[int, int], cell2: Tuple[int, int]) -> bool:
        """Remove dot constraint using command system (for undo/redo)."""
        command = RemoveDotConstraintCommand(cell1, cell2)
        return self.command_history.execute_command(command, self)
    
    def cmd_import_puzzle(self, json_data: Dict) -> bool:
        """Import puzzle using command system (for undo/redo)."""
        command = ImportPuzzleCommand(json_data)
        return self.command_history.execute_command(command, self)
    
    def cmd_clear_grid(self) -> bool:
        """Clear entire grid using batch command."""
        commands = []
        
        # Create commands to clear all cells
        for (row, col), (state, value) in self.cell_states.items():
            if state != CellState.EMPTY or value is not None:
                commands.append(SetCellStateCommand(row, col, CellState.EMPTY, None))
        
        # Create commands to remove all constraints
        for constraint in list(self.dot_constraints):
            commands.append(RemoveDotConstraintCommand(constraint[0], constraint[1]))
        
        if commands:
            batch_command = BatchCommand(commands, "Clear grid")
            return self.command_history.execute_command(batch_command, self)
        
        return True
    
    # =============================================================================
    # UNDO/REDO OPERATIONS
    # =============================================================================
    
    def undo(self) -> bool:
        """Undo the last operation."""
        return self.command_history.undo(self)
    
    def redo(self) -> bool:
        """Redo the next operation."""
        return self.command_history.redo(self)
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.command_history.can_undo()
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.command_history.can_redo()
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of operation that would be undone."""
        return self.command_history.get_undo_description()
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of operation that would be redone."""
        return self.command_history.get_redo_description()
    
    def clear_history(self) -> None:
        """Clear undo/redo history."""
        self.command_history.clear_history()
    
    def get_history_info(self) -> Dict:
        """Get detailed history information."""
        return self.command_history.get_history_info()
    
    # =============================================================================
    # VALIDATION
    # =============================================================================
    
    def validate_connectivity(self) -> Tuple[bool, str]:
        """
        Validate that all playable cells form a connected graph.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        playable_cells = list(self.get_playable_cells().keys())
        
        if not playable_cells:
            return False, "No playable cells found"
        
        if len(playable_cells) == 1:
            return True, ""
        
        # BFS to check connectivity
        visited = set()
        queue = [playable_cells[0]]
        visited.add(playable_cells[0])
        
        while queue:
            current_row, current_col = queue.pop(0)
            neighbors = self.get_neighbors(current_row, current_col)
            
            for (nr, nc) in neighbors:
                if (nr, nc) in playable_cells and (nr, nc) not in visited:
                    visited.add((nr, nc))
                    queue.append((nr, nc))
        
        if len(visited) == len(playable_cells):
            return True, ""
        else:
            disconnected_count = len(playable_cells) - len(visited)
            return False, f"{disconnected_count} playable cells are disconnected"
    
    def validate_puzzle(self) -> List[ValidationError]:
        """
        Comprehensive puzzle validation.
        
        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors = []
        
        # Check connectivity
        is_connected, conn_msg = self.validate_connectivity()
        if not is_connected:
            errors.append(ValidationError("error", conn_msg))
        
        # Check for duplicate values
        value_locations = {}
        for (row, col), (state, value) in self.cell_states.items():
            if state == CellState.PREFILLED and value is not None:
                if value in value_locations:
                    errors.append(ValidationError(
                        "error",
                        f"Duplicate value {value}",
                        location=(row, col)
                    ))
                else:
                    value_locations[value] = (row, col)
        
        # Check value ranges
        max_val = self.get_max_possible_value()
        for (row, col), (state, value) in self.cell_states.items():
            if state == CellState.PREFILLED and value is not None:
                if value < 1 or value > max_val:
                    errors.append(ValidationError(
                        "error",
                        f"Value {value} out of range (1-{max_val})",
                        location=(row, col)
                    ))
        
        # Check constraint validity
        for (cell1, cell2) in self.dot_constraints:
            if not self.cell_exists(*cell1) or not self.cell_exists(*cell2):
                errors.append(ValidationError(
                    "error",
                    f"Constraint references non-existent cells",
                    location=cell1
                ))
            elif cell2 not in self.get_neighbors(*cell1):
                errors.append(ValidationError(
                    "error",
                    f"Invalid constraint between non-adjacent cells",
                    location=cell1
                ))
        
        return errors
    
    def get_statistics(self) -> Dict:
        """
        Get comprehensive grid statistics.
        
        Returns:
            Dict with various statistics about the grid
        """
        stats = {
            "empty_cells": 0,
            "prefilled_cells": 0,
            "blocked_cells": 0,
            "center_cells": 0,
            "hole_cells": 0,
            "total_playable": 0,
            "total_existing": 0,
            "dot_constraints": len(self.dot_constraints)
        }
        
        for (state, _) in self.cell_states.values():
            if state == CellState.EMPTY:
                stats["empty_cells"] += 1
                stats["total_playable"] += 1
                stats["total_existing"] += 1
            elif state == CellState.PREFILLED:
                stats["prefilled_cells"] += 1
                stats["total_playable"] += 1
                stats["total_existing"] += 1
            elif state == CellState.NONPLAYABLE:
                stats["blocked_cells"] += 1
                stats["total_existing"] += 1
            elif state == CellState.CENTER:
                stats["center_cells"] += 1
                stats["total_existing"] += 1
            elif state == CellState.HOLE:
                stats["hole_cells"] += 1
        
        validation_errors = self.validate_puzzle()
        stats["errors"] = len([e for e in validation_errors if e.severity == "error"])
        stats["warnings"] = len([e for e in validation_errors if e.severity == "warning"])
        
        is_connected, _ = self.validate_connectivity()
        stats["is_connected"] = is_connected
        
        # Add undo/redo info
        history_info = self.get_history_info()
        stats.update({
            "can_undo": history_info["can_undo"],
            "can_redo": history_info["can_redo"],
            "total_commands": history_info["total_commands"]
        })
        
        return stats
    
    # =============================================================================
    # JSON IMPORT/EXPORT
    # =============================================================================
    
    @classmethod
    def from_json(cls, json_data: Dict) -> 'HexGrid':
        """
        Create a HexGrid from JSON puzzle data.
        
        Args:
            json_data: Puzzle data in JSON format
        
        Returns:
            New HexGrid instance
        """
        layout = json_data.get("layout", {})
        rows = layout.get("rows", 7)
        cols = layout.get("cols", 7)
        coordinates = layout.get("coordinates", {})
        center_rc = layout.get("center_rc")
        
        grid = cls(rows, cols)
        
        # Initialize all cells as holes
        for row in range(rows):
            for col in range(cols):
                grid.cell_states[(row, col)] = (CellState.HOLE, None)
        
        # Set vertices from JSON
        vertices = json_data.get("vertices", {})
        for vertex_id, vertex_data in vertices.items():
            # Get coordinates
            if vertex_id in coordinates:
                row, col = coordinates[vertex_id]
            else:
                try:
                    row, col = string_to_coordinate(vertex_id)
                except:
                    continue
            
            if not (0 <= row < rows and 0 <= col < cols):
                continue
            
            # Set cell state
            value = vertex_data.get("value")
            if value is not None:
                grid.cell_states[(row, col)] = (CellState.PREFILLED, int(value))
            else:
                grid.cell_states[(row, col)] = (CellState.EMPTY, None)
        
        # Set center cell if specified
        if center_rc and isinstance(center_rc, list) and len(center_rc) == 2:
            center_row, center_col = int(center_rc[0]), int(center_rc[1])
            if 0 <= center_row < rows and 0 <= center_col < cols:
                grid.set_cell_state(center_row, center_col, CellState.CENTER)
        
        # Add constraints
        constraints = json_data.get("constraints", {})
        dots = constraints.get("dots", [])
        for dot_pair in dots:
            if len(dot_pair) == 2:
                v1_id, v2_id = dot_pair
                
                try:
                    if v1_id in coordinates and v2_id in coordinates:
                        r1, c1 = coordinates[v1_id]
                        r2, c2 = coordinates[v2_id]
                    else:
                        r1, c1 = string_to_coordinate(v1_id)
                        r2, c2 = string_to_coordinate(v2_id)
                    
                    grid.add_dot_constraint((r1, c1), (r2, c2))
                except:
                    # Skip malformed constraints
                    continue
        
        # Clear history after import (this is the initial state)
        grid.clear_history()
        
        return grid
    
    def to_json(self, puzzle_id: str = "created_puzzle") -> Dict:
        """
        Export grid to JSON format using canonical EVEN-R neighbors.
        
        Args:
            puzzle_id: Identifier for the puzzle
        
        Returns:
            Dict in JSON puzzle format
        """
        vertices = {}
        coordinates = {}
        playable_cells = self.get_playable_cells()
        
        # Build vertices and coordinates
        for (row, col), value in playable_cells.items():
            vertex_id = coordinate_to_string(row, col)
            vertices[vertex_id] = {"value": value}
            coordinates[vertex_id] = [row, col]
        
        # Build adjacency using canonical EVEN-R neighbors
        adjacency = {}
        for (row, col) in playable_cells.keys():
            vertex_id = coordinate_to_string(row, col)
            neighbors = self.get_neighbors(row, col)
            
            playable_neighbors = []
            for (nr, nc) in neighbors:
                if (nr, nc) in playable_cells:
                    playable_neighbors.append(coordinate_to_string(nr, nc))
            
            adjacency[vertex_id] = sorted(playable_neighbors)
        
        # Export constraints
        dots = []
        for (cell1, cell2) in self.dot_constraints:
            if cell1 in playable_cells and cell2 in playable_cells:
                v1_id = coordinate_to_string(cell1[0], cell1[1])
                v2_id = coordinate_to_string(cell2[0], cell2[1])
                dots.append([v1_id, v2_id])
        
        # Build layout section
        layout = {
            "rows": self.rows,
            "cols": self.cols,
            "coordinates": coordinates
        }
        
        if self.center_location is not None and self.cell_exists(*self.center_location):
            layout["center_rc"] = [self.center_location[0], self.center_location[1]]
        
        return {
            "id": puzzle_id,
            "max_value": self.get_max_possible_value(),
            "vertices": vertices,
            "adjacency": adjacency,
            "constraints": {"dots": dots},
            "layout": layout
        }
    
    @classmethod
    def load_from_file(cls, filename: str) -> 'HexGrid':
        """Load a HexGrid from a JSON file."""
        with open(filename, 'r') as f:
            json_data = json.load(f)
        return cls.from_json(json_data)
    
    def save_json(self, filename: str, puzzle_id: str = "created_puzzle") -> None:
        """Save grid to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.to_json(puzzle_id), f, indent=2)