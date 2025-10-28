"""
HexGrid - Clean grid state manager for Rikudo puzzle creator.

This module provides the core grid representation using EVEN-R coordinate system.
Integrates with command pattern for undo/redo functionality.

Phase 1 changes:
- Schema extension: support layout.non_playable_cells (blocked cosmetics) while keeping layout.center_rc.
- Loader split: if JSON adjacency is present, store and prefer it as the ground-truth graph ("loaded graph");
  otherwise fall back to computed EVEN‑R neighbors.
- Exporter fidelity: when a loaded graph exists, export that exact topology (filtered to playable vertices);
  otherwise export canonical EVEN‑R topology. Ensure center_rc is also listed in non_playable_cells.

NOTE: No GUI changes here; this is a pure core change.
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
        - Provide neighbor calculations (delegates to canonical helper or uses loaded graph)
        - Integrate with command system for undo/redo
    
    Attributes:
        rows: Number of rows in grid
        cols: Number of columns in grid
        cell_states: Mapping of (row, col) to (CellState, optional_value)
        dot_constraints: Set of constraint pairs (normalized)
        center_location: Optional center cell coordinate
        command_history: Undo/redo command stack

        loaded_adjacency: Optional[(row,col) -> set[(row,col)]]  # present only when JSON provided adjacency
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

        # Optional loaded graph (adjacency) from JSON import
        self.loaded_adjacency: Optional[Dict[Tuple[int, int], Set[Tuple[int, int]]]] = None
        
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
    # NEIGHBOR CALCULATION (EVEN-R or LOADED GRAPH)
    # =============================================================================
    
    def _row_lengths_rect(self) -> List[int]:
        """Helper: row lengths for rectangular grid (ragged support is Phase 6)."""
        return [self.cols] * self.rows

    def has_loaded_graph(self) -> bool:
        """True if this grid was constructed/loaded with an explicit adjacency."""
        return self.loaded_adjacency is not None

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Get all valid neighbors.
        If a JSON adjacency was loaded, that is authoritative.
        Otherwise, delegate to canonical EVEN-R helper.
        """
        if not self.cell_exists(row, col):
            return []
        
        # Prefer loaded graph
        if self.loaded_adjacency is not None:
            return list(self.loaded_adjacency.get((row, col), set()))

        # Fallback: compute from parity
        row_lengths = self._row_lengths_rect()
        # Get neighbors from canonical EVEN-R helper
        candidates = get_hex_neighbors_evenr(row_lengths, row, col)
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
        
        # Check cells are adjacent (uses loaded graph if present)
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
        Return a list[ValidationError]. Empty list == VALID.
        Rules (hard errors):
        - Center invariants (center cannot appear as a graph vertex; must be CENTER state if set)
        - Adjacency symmetry (for loaded JSON graphs): undirected, no self-loops, endpoints exist
        - Dot constraints must reference valid edges
        - Graph connectivity must hold (single component)
        - Duplicate values are not allowed
        - Prefilled values must be in range [1..max_value]
        """
        errors: List[ValidationError] = []

        # ---------------------------
        # A) Connectivity (original)
        # ---------------------------
        is_connected, conn_msg = self.validate_connectivity()
        if not is_connected:
            errors.append(ValidationError("error", conn_msg))

        # ---------------------------------------
        # B) Duplicate values (original feature)
        # ---------------------------------------
        value_locations: Dict[int, Tuple[int, int]] = {}
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

        # -------------------------------------
        # C) Value ranges (original feature)
        # -------------------------------------
        max_val = self.get_max_possible_value()
        for (row, col), (state, value) in self.cell_states.items():
            if state == CellState.PREFILLED and value is not None:
                if value < 1 or value > max_val:
                    errors.append(ValidationError(
                        "error",
                        f"Value {value} out of range (1-{max_val})",
                        location=(row, col)
                    ))

        # -----------------------------------------------------------------
        # D) Constraint validity (original semantics + tiny safety add)
        #     - non-existent cells
        #     - non-adjacent endpoints (active graph semantics)
        #     - (extra safety) non-playable endpoints
        # -----------------------------------------------------------------
        for (cell1, cell2) in self.dot_constraints:
            if not self.cell_exists(*cell1) or not self.cell_exists(*cell2):
                errors.append(ValidationError(
                    "error",
                    "Constraint references non-existent cells",
                    location=cell1
                ))
                continue

            s1, _ = self.get_cell_state(*cell1)
            s2, _ = self.get_cell_state(*cell2)
            if s1 not in (CellState.EMPTY, CellState.PREFILLED) or \
            s2 not in (CellState.EMPTY, CellState.PREFILLED):
                errors.append(ValidationError(
                    "error",
                    "Constraint touches non-playable cell",
                    location=cell1
                ))
                continue

            if cell2 not in self.get_neighbors(*cell1):
                errors.append(ValidationError(
                    "error",
                    "Invalid constraint between non-adjacent cells",
                    location=cell1
                ))

        # -------------------------------------------------------
        # E) Center invariants (NEW, required for solver-safety)
        # -------------------------------------------------------
        center = self.center_location
        if center is not None:
            st, _ = self.get_cell_state(*center)
            if st != CellState.CENTER:
                errors.append(ValidationError("error", "Center cell is not marked CENTER", location=center))

            # Center must NOT be a graph vertex or neighbor if a loaded graph exists
            if self.loaded_adjacency is not None:
                if center in self.loaded_adjacency:
                    errors.append(ValidationError("error", "Center appears as a vertex in adjacency", location=center))
                else:
                    for u, nbrs in self.loaded_adjacency.items():
                        if center in nbrs:
                            errors.append(ValidationError("error", "Center appears as a neighbor in adjacency", location=center))
                            break

        # ------------------------------------------------------------------
        # F) Adjacency symmetry & well-formedness (NEW, only if graph loaded)
        # ------------------------------------------------------------------
        if self.loaded_adjacency is not None:
            for u, nbrs in self.loaded_adjacency.items():
                if not self.cell_exists(*u):
                    errors.append(ValidationError("error", "Adjacency references non-existent cell", location=u))
                for v in nbrs:
                    if v == u:
                        errors.append(ValidationError("error", "Self-loop in adjacency", location=u))
                        continue
                    if not self.cell_exists(*v):
                        errors.append(ValidationError("error", "Adjacency references non-existent neighbor", location=v))
                        continue
                    back = self.loaded_adjacency.get(v, set())
                    if u not in back:
                        errors.append(ValidationError(
                            "error",
                            f"Asymmetric adjacency: {u} → {v} but not {v} → {u}",
                            location=u
                        ))

        return errors
    
    # ============================================
    # VALIDATION: detailed rule implementations
    # ============================================
    def _validate_center_invariants(self):
        """
        Center cell may exist in the layout as a special marker, but:
        - It must NOT appear as a graph vertex (no adjacency entry, no membership in any neighbor set)
        - If present in the grid, its CellState must be CENTER (not playable)
        """
        v = []
        center = self.center_location  # Tuple[int,int] or None
        if center is None:
            return v  # Having no center is fine (some Rikudo variants)

        # Must be CENTER state
        st, _ = self.get_cell_state(*center)
        if st != CellState.CENTER:
            v.append(ValidationError("error", "Center cell is not marked CENTER", location=center))

        # Must not be a graph vertex (no key, no appearance in neighbor sets)
        if self.loaded_adjacency is not None:
            if center in self.loaded_adjacency:
                v.append(ValidationError("error", "Center appears as a vertex in adjacency", location=center))
            else:
                for u, nbrs in self.loaded_adjacency.items():
                    if center in nbrs:
                        v.append(ValidationError("error", "Center appears as a neighbor in adjacency", location=center))
                        break

        return v


    def _validate_adjacency_symmetry(self):
        """
        For loaded JSON graphs, enforce undirected symmetry and basic well-formedness:
        - For every (u -> v), a matching (v -> u) must exist
        - No self-loops
        - Endpoints must exist as non-hole cells in the grid
        """
        v = []

        # Build quick existence predicate from grid state
        def exists(cell):
            r, c = cell
            return self.cell_exists(r, c)

        for u, nbrs in self.loaded_adjacency.items():
            # Endpoint must exist
            if not exists(u):
                v.append(ValidationError("error", "Adjacency references non-existent cell", location=u))
                # Continue checking others; collect all errors
            for w in nbrs:
                # Self-loop?
                if w == u:
                    v.append(ValidationError("error", "Self-loop in adjacency", location=u))
                    continue
                # Endpoint must exist
                if not exists(w):
                    v.append(ValidationError("error", "Adjacency references non-existent neighbor", location=w))
                    continue
                # Symmetry check
                back = self.loaded_adjacency.get(w, set())
                if u not in back:
                    v.append(ValidationError(
                        "error",
                        f"Asymmetric adjacency: {u} → {w} but not {w} → {u}",
                        location=u
                    ))

        return v


    def _validate_constraints_reference_edges(self):
        """
        Dot constraints must reference valid edges of the ACTIVE graph:
        - If a loaded JSON graph exists → check edge ∈ loaded_adjacency
        - Else → check edge ∈ parity neighbors (get_neighbors)
        """
        v = []
        for (a, b) in self.dot_constraints:
            # Reject any constraint touching holes/center/non-playable
            st_a, _ = self.get_cell_state(*a)
            st_b, _ = self.get_cell_state(*b)
            if st_a not in (CellState.EMPTY, CellState.PREFILLED) or st_b not in (CellState.EMPTY, CellState.PREFILLED):
                v.append(ValidationError("error", "Constraint touches non-playable cell", location=a))
                continue

            # Active-graph edge check
            if self.loaded_adjacency is not None:
                nbrs = self.loaded_adjacency.get(a, set())
                if b not in nbrs:
                    v.append(ValidationError("error", "Constraint endpoints are not adjacent in graph", location=a))
            else:
                if b not in set(self.get_neighbors(*a)):
                    v.append(ValidationError("error", "Constraint endpoints are not adjacent (parity)", location=a))

        return v



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
        
        Loader split:
        - Initialize cells as HOLE
        - Mark NONPLAYABLE cells from layout.non_playable_cells (if present)
        - Mark vertices from "vertices" (EMPTY/PREFILLED)
        - Apply center_rc as CENTER
        - If "adjacency" exists, store it in loaded_adjacency (authoritative)
        - Add constraints AFTER loaded_adjacency so adjacency checks use the JSON graph
        """
        layout = json_data.get("layout", {})
        rows = layout.get("rows", 7)
        cols = layout.get("cols", 7)
        coordinates = layout.get("coordinates", {})
        center_rc = layout.get("center_rc")
        non_playable_list = layout.get("non_playable_cells", []) or []
        
        grid = cls(rows, cols)
        
        # Initialize all cells as holes
        for row in range(rows):
            for col in range(cols):
                grid.cell_states[(row, col)] = (CellState.HOLE, None)
        
        # Apply non-playable cosmetics (blocked tiles that aren't vertices)
        for coord in non_playable_list:
            try:
                if isinstance(coord, str):
                    r, c = string_to_coordinate(coord)
                else:
                    r, c = int(coord[0]), int(coord[1])
            except Exception:
                continue
            if 0 <= r < rows and 0 <= c < cols:
                grid.cell_states[(r, c)] = (CellState.NONPLAYABLE, None)
        
        # Set vertices from JSON
        vertices = json_data.get("vertices", {})
        for vertex_id, vertex_data in vertices.items():
            # Get coordinates
            if vertex_id in coordinates:
                row, col = coordinates[vertex_id]
            else:
                try:
                    row, col = string_to_coordinate(vertex_id)
                except Exception:
                    continue
            
            if not (0 <= row < rows and 0 <= col < cols):
                continue
            
            # Set cell state
            value = vertex_data.get("value")
            if value is not None:
                grid.cell_states[(row, col)] = (CellState.PREFILLED, int(value))
            else:
                grid.cell_states[(row, col)] = (CellState.EMPTY, None)
        
        # Set center cell if specified (center is non-playable by definition)
        if center_rc and isinstance(center_rc, list) and len(center_rc) == 2:
            center_row, center_col = int(center_rc[0]), int(center_rc[1])
            if 0 <= center_row < rows and 0 <= center_col < cols:
                grid.set_cell_state(center_row, center_col, CellState.CENTER)
        
        # Build loaded adjacency if provided
        loaded_adj_raw: Dict[str, List[str]] = json_data.get("adjacency", {})
        if loaded_adj_raw:
            loaded_map: Dict[Tuple[int, int], Set[Tuple[int, int]]] = {}
            # Prepare playable set for safety (adjacency usually lists only vertices)
            playable_set = set(grid.get_playable_cells().keys())
            for vid, neigh_ids in loaded_adj_raw.items():
                try:
                    if vid in coordinates:
                        r, c = coordinates[vid]
                    else:
                        r, c = string_to_coordinate(vid)
                except Exception:
                    continue
                key = (int(r), int(c))
                if key not in loaded_map:
                    loaded_map[key] = set()
                for nid in neigh_ids:
                    try:
                        if nid in coordinates:
                            nr, nc = coordinates[nid]
                        else:
                            nr, nc = string_to_coordinate(nid)
                        nbr = (int(nr), int(nc))
                        # Keep only neighbors that exist in grid bounds;
                        # do not force-playable here; constraint checks will enforce playability
                        if 0 <= nr < rows and 0 <= nc < cols:
                            loaded_map[key].add(nbr)
                    except Exception:
                        continue
            grid.loaded_adjacency = loaded_map
        
        # Add constraints (now get_neighbors will honor loaded_adjacency if present)
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
                    
                    grid.add_dot_constraint((int(r1), int(c1)), (int(r2), int(c2)))
                except Exception:
                    # Skip malformed constraints
                    continue
        
        # Clear history after import (this is the initial state)
        grid.clear_history()
        
        return grid
    
    def _build_adjacency_for_export(self) -> Dict[str, List[str]]:
        """
        Build adjacency for export based on current mode:
        - If a loaded graph exists: export that topology verbatim (filtered to playable set)
        - Else: export canonical EVEN-R adjacency among playable cells
        """
        playable = set(self.get_playable_cells().keys())
        adjacency: Dict[str, List[str]] = {}
        if self.loaded_adjacency is not None:
            for (r, c) in playable:
                vid = coordinate_to_string(r, c)
                nbrs = []
                for (nr, nc) in self.loaded_adjacency.get((r, c), set()):
                    if (nr, nc) in playable:
                        nbrs.append(coordinate_to_string(nr, nc))
                adjacency[vid] = sorted(nbrs)
            return adjacency
        
        # Fallback: compute from parity
        for (row, col) in playable:
            vertex_id = coordinate_to_string(row, col)
            neighbors = self.get_neighbors(row, col)  # will compute parity in this branch
            playable_neighbors = []
            for (nr, nc) in neighbors:
                if (nr, nc) in playable:
                    playable_neighbors.append(coordinate_to_string(nr, nc))
            adjacency[vertex_id] = sorted(playable_neighbors)
        return adjacency

    def _collect_non_playable_for_export(self) -> List[str]:
        """
        Build layout.non_playable_cells list.
        Includes all NONPLAYABLE cells and the center cell (if present).
        HOLE cells are *not* listed; they are rendered as empty space.
        """
        non_playable: Set[Tuple[int, int]] = set()
        for (row, col), (state, _) in self.cell_states.items():
            if state == CellState.NONPLAYABLE:
                non_playable.add((row, col))
        # Center SHOULD be listed as non-playable cosmetic too
        if self.center_location is not None:
            non_playable.add(self.center_location)
        return [coordinate_to_string(r, c) for (r, c) in sorted(non_playable)]
    
    def to_json(self, puzzle_id: str = "created_puzzle") -> Dict:
        """
        Export grid to JSON format with Phase 1 rules.
        
        - vertices/coordinates from current playable cells
        - adjacency: loaded graph if present, else canonical EVEN-R
        - layout: rows/cols/coordinates + center_rc (if any) + non_playable_cells (center included)
        - constraints: include only those whose endpoints are adjacent in the exported adjacency
        """
        vertices = {}
        coordinates = {}
        playable_cells = self.get_playable_cells()
        
        # Build vertices and coordinates
        for (row, col), value in playable_cells.items():
            vertex_id = coordinate_to_string(row, col)
            vertices[vertex_id] = {"value": value}
            coordinates[vertex_id] = [row, col]
        
        # Build adjacency per rules
        adjacency = self._build_adjacency_for_export()
        
        # Export constraints, filtered by adjacency
        dots = []
        # Build a quick lookup from adjacency
        adj_lookup: Dict[str, Set[str]] = {k: set(vs) for k, vs in adjacency.items()}
        for (cell1, cell2) in self.dot_constraints:
            if cell1 in playable_cells and cell2 in playable_cells:
                v1_id = coordinate_to_string(cell1[0], cell1[1])
                v2_id = coordinate_to_string(cell2[0], cell2[1])
                # keep only if adjacency contains the edge
                if v2_id in adj_lookup.get(v1_id, set()):
                    dots.append([v1_id, v2_id])
        
        # Build layout section
        layout = {
            "rows": self.rows,
            "cols": self.cols,
            "coordinates": coordinates
        }
        
        if self.center_location is not None and self.cell_exists(*self.center_location):
            layout["center_rc"] = [self.center_location[0], self.center_location[1]]
        
        # NEW: non_playable_cells (center included as cosmetic)
        layout["non_playable_cells"] = self._collect_non_playable_for_export()
        
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
