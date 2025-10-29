"""
Advanced constraint management for Rikudo Puzzle Creator Phase 4.
Enhanced visual guides, validation, and batch operations for constraints.
"""
from typing import Set, Tuple, List, Dict, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox, simpledialog

from core.hex_grid import HexGrid
from core.types import CellState, ValidationError
from core.commands import Command, BatchCommand, AddDotConstraintCommand, RemoveDotConstraintCommand

from core.commands import (
    Command, BatchCommand, SetCellStateCommand, SetCellValueCommand,
    AddDotConstraintCommand, RemoveDotConstraintCommand, LiveBatchCommand
)

class ConstraintType(Enum):
    """Types of constraints supported."""
    DOT = "dot"                    # Current dot constraints
    SEQUENCE = "sequence"          # Future: enforce consecutive numbers
    DISTANCE = "distance"          # Future: minimum distance between numbers
    EXCLUSION = "exclusion"        # Future: cells that can't be adjacent

@dataclass(frozen=True)
class ConstraintConflict:
    """Represents a conflict between constraints."""
    type: str
    location: Tuple[Tuple[int, int], Tuple[int, int]]
    message: str
    severity: str  # "error", "warning", "info"

class ConstraintValidator:
    """Advanced constraint validation and conflict detection."""
    
    def __init__(self, grid: HexGrid):
        self.grid = grid
    
    def validate_constraint_placement(self, cell1: Tuple[int, int], cell2: Tuple[int, int]) -> List[ValidationError]:
        """Validate a single constraint placement with detailed analysis."""
        errors = []
        r1, c1 = cell1
        r2, c2 = cell2
        
        # Basic validation
        if not (self.grid.cell_exists(r1, c1) and self.grid.cell_exists(r2, c2)):
            errors.append(ValidationError("error", "One or both cells don't exist", location=cell1))
            return errors
        
        # Adjacency check
        neighbors = self.grid.get_neighbors(r1, c1)
        if (r2, c2) not in neighbors:
            errors.append(ValidationError("error", "Cells are not adjacent", location=cell1))
            return errors
        
        # Cell state validation
        state1, value1 = self.grid.get_cell_state(r1, c1)
        state2, value2 = self.grid.get_cell_state(r2, c2)
        
        if state1 not in (CellState.EMPTY, CellState.PREFILLED):
            errors.append(ValidationError("error", f"Cell {cell1} is not playable", location=cell1))
        
        if state2 not in (CellState.EMPTY, CellState.PREFILLED):
            errors.append(ValidationError("error", f"Cell {cell2} is not playable", location=cell2))
        
        # Advanced validation: Check for logical conflicts
        if value1 is not None and value2 is not None:
            if abs(value1 - value2) != 1:
                errors.append(ValidationError(
                    "warning", 
                    f"Constraint between non-consecutive numbers {value1} and {value2}",
                    location=cell1
                ))
        
        return errors
    
    def detect_constraint_conflicts(self) -> List[ConstraintConflict]:
        """Detect conflicts in the current constraint configuration."""
        conflicts = []
        
        # Check for overconstrained cells (cells with too many constraints)
        constraint_count = {}
        for (cell1, cell2) in self.grid.dot_constraints:
            constraint_count[cell1] = constraint_count.get(cell1, 0) + 1
            constraint_count[cell2] = constraint_count.get(cell2, 0) + 1
        
        # Cells with more than 2 constraints might be problematic
        for cell, count in constraint_count.items():
            if count > 2:
                conflicts.append(ConstraintConflict(
                    type="overconstrained",
                    location=(cell, cell),
                    message=f"Cell {cell} has {count} constraints (may be overconstrained)",
                    severity="warning"
                ))
        
        # Check for impossible constraint chains
        conflicts.extend(self._detect_impossible_chains())
        
        return conflicts
    
    def _detect_impossible_chains(self) -> List[ConstraintConflict]:
        """Detect constraint chains that create impossible sequences."""
        conflicts = []
        
        # Build constraint graph
        constraint_graph = {}
        for (cell1, cell2) in self.grid.dot_constraints:
            if cell1 not in constraint_graph:
                constraint_graph[cell1] = []
            if cell2 not in constraint_graph:
                constraint_graph[cell2] = []
            constraint_graph[cell1].append(cell2)
            constraint_graph[cell2].append(cell1)
        
        # Look for chains longer than the available sequence space
        visited = set()
        for start_cell in constraint_graph:
            if start_cell in visited:
                continue
            
            chain_length = self._get_constraint_chain_length(start_cell, constraint_graph, visited)
            playable_cells = len(self.grid.get_playable_cells())
            
            if chain_length > playable_cells:
                conflicts.append(ConstraintConflict(
                    type="impossible_chain",
                    location=(start_cell, start_cell),
                    message=f"Constraint chain of length {chain_length} exceeds grid size {playable_cells}",
                    severity="error"
                ))
        
        return conflicts
    
    def _get_constraint_chain_length(self, start_cell: Tuple[int, int], 
                                   constraint_graph: Dict, visited: Set) -> int:
        """Get the length of a constraint chain starting from a cell."""
        if start_cell in visited:
            return 0
        
        visited.add(start_cell)
        max_length = 1
        
        for neighbor in constraint_graph.get(start_cell, []):
            if neighbor not in visited:
                length = 1 + self._get_constraint_chain_length(neighbor, constraint_graph, visited)
                max_length = max(max_length, length)
        
        return max_length

class ConstraintEditor:
    """Enhanced constraint editing with visual guides and batch operations."""
    
    def __init__(self, canvas, grid: HexGrid):
        self.canvas = canvas
        self.grid = grid
        self.validator = ConstraintValidator(grid)
        
        # Visual state
        self.preview_items = []
        self.guide_items = []
        self.selection_mode = False
        self.selected_cells: Set[Tuple[int, int]] = set()
        
        # NEW: Track the order cells were selected for numbering
        self.selection_order: List[Tuple[int, int]] = []
        
        # Batch operation state
        self.batch_operations: List[Command] = []

        # Current-numbering highlight
        self.current_prompt_items: List[int] = []

    # ---------- dialog helpers to keep prompts always on top ----------
    def _dialog_parent(self):
        """Return the toplevel window to parent dialogs; None if unavailable."""
        try:
            return self.canvas.canvas.winfo_toplevel()
        except Exception:
            return None

    def _askinteger_topmost(self, title, prompt, **kwargs):
        """
        Ask for an integer with a dialog that reliably stays on top.
        Temporarily sets the parent to -topmost during the prompt and restores it after.
        """
        parent = self._dialog_parent()
        if parent is not None:
            try:
                parent.lift(); parent.attributes('-topmost', True); parent.update_idletasks()
                return simpledialog.askinteger(title, prompt, parent=parent, **kwargs)
            finally:
                try:
                    parent.attributes('-topmost', False)
                except Exception:
                    pass
        # Fallback without explicit parent
        return simpledialog.askinteger(title, prompt, **kwargs)

    def _askyesnocancel_topmost(self, title, prompt):
        """askyesnocancel that stays on top and is parented to the main window."""
        parent = self._dialog_parent()
        if parent is not None:
            try:
                parent.lift(); parent.attributes('-topmost', True); parent.update_idletasks()
                return messagebox.askyesnocancel(title, prompt, parent=parent)
            finally:
                try:
                    parent.attributes('-topmost', False)
                except Exception:
                    pass
        return messagebox.askyesnocancel(title, prompt)
    
    def enter_selection_mode(self):
        """Enter batch selection mode for constraint operations."""
        self.selection_mode = True
        self.selected_cells.clear()
        self.selection_order.clear()  # Clear order tracking
        self._update_visual_guides()
    
    def exit_selection_mode(self):
        """Exit batch selection mode."""
        self.selection_mode = False
        self.selected_cells.clear()
        self.selection_order.clear()  # Clear order tracking
        self._clear_visual_guides()
        self._clear_current_number_highlight()

    # ---------- visual helpers for current cell being edited ----------
    def _show_current_number_highlight(self, row: int, col: int, color: str = "#00BFFF"):
        self._clear_current_number_highlight()
        if not getattr(self.canvas, "renderer", None):
            return
        x, y = self.canvas.renderer.evenr_to_pixel(
            row, col, self.canvas.canvas_offset_x, self.canvas.canvas_offset_y
        )
        radius = self.canvas.renderer.hex_size + 4
        item_id = self.canvas.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            outline=color, width=3, fill="", tags="current_number_target"
        )
        self.current_prompt_items.append(item_id)

    def _clear_current_number_highlight(self):
        for iid in self.current_prompt_items:
            try:
                self.canvas.canvas.delete(iid)
            except Exception:
                pass
        self.current_prompt_items.clear()
    
    def toggle_cell_selection(self, row: int, col: int) -> bool:
        """Toggle cell selection in batch mode."""
        if not self.selection_mode:
            return False
        
        cell = (row, col)
        if cell in self.selected_cells:
            # Remove from selection
            self.selected_cells.remove(cell)
            if cell in self.selection_order:
                self.selection_order.remove(cell)
        else:
            # Add to selection
            # Only allow playable cells to be selected
            state, _ = self.grid.get_cell_state(row, col)
            if state in (CellState.EMPTY, CellState.PREFILLED, CellState.NONPLAYABLE):  # Allow blocked cells too
                self.selected_cells.add(cell)
                self.selection_order.append(cell)  # Track order
        
        self._update_visual_guides()
        return True
    
    def get_possible_constraints(self, selected_cells: Set[Tuple[int, int]]) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Get all possible constraint pairs from selected cells."""
        possible_constraints = []
        
        for cell1 in selected_cells:
            neighbors = self.grid.get_neighbors(*cell1)
            for neighbor in neighbors:
                if neighbor in selected_cells and cell1 < neighbor:  # Avoid duplicates
                    possible_constraints.append((cell1, neighbor))
        
        return possible_constraints
    
    def create_batch_constraints(self) -> bool:
        """Create constraints for all valid pairs in selection."""
        if not self.selection_mode or len(self.selected_cells) < 2:
            return False
        
        possible_constraints = self.get_possible_constraints(self.selected_cells)
        
        if not possible_constraints:
            messagebox.showwarning("No Constraints", "No valid constraint pairs found in selection.")
            return False
        
        # Validate all constraints first
        valid_constraints = []
        for cell1, cell2 in possible_constraints:
            errors = self.validator.validate_constraint_placement(cell1, cell2)
            if not any(e.severity == "error" for e in errors):
                valid_constraints.append((cell1, cell2))
        
        if not valid_constraints:
            messagebox.showwarning("Invalid Constraints", "No valid constraints can be created from selection.")
            return False
        
        # Create batch command
        commands = []
        for cell1, cell2 in valid_constraints:
            if not self.grid.has_dot_constraint(cell1, cell2):
                commands.append(AddDotConstraintCommand(cell1, cell2))
        
        if commands:
            batch_command = BatchCommand(commands, f"Add {len(commands)} constraints")
            success = self.grid.command_history.execute_command(batch_command, self.grid)
            
            if success:
                messagebox.showinfo("Constraints Added", f"Added {len(commands)} constraints successfully.")
                self.exit_selection_mode()
                return True
        
        return False
    
    def remove_batch_constraints(self) -> bool:
        """Remove constraints for all pairs in selection."""
        if not self.selection_mode or len(self.selected_cells) < 2:
            return False
        
        possible_constraints = self.get_possible_constraints(self.selected_cells)
        
        # Find existing constraints to remove
        commands = []
        for cell1, cell2 in possible_constraints:
            if self.grid.has_dot_constraint(cell1, cell2):
                commands.append(RemoveDotConstraintCommand(cell1, cell2))
        
        if not commands:
            messagebox.showinfo("No Constraints", "No constraints found to remove in selection.")
            return False
        
        batch_command = BatchCommand(commands, f"Remove {len(commands)} constraints")
        success = self.grid.command_history.execute_command(batch_command, self.grid)
        
        if success:
            messagebox.showinfo("Constraints Removed", f"Removed {len(commands)} constraints successfully.")
            self.exit_selection_mode()
            return True
        
        return False
    
    def show_constraint_preview(self, cell1: Tuple[int, int], cell2: Tuple[int, int]):
        """Show preview of potential constraint placement."""
        self._clear_preview()
        
        # Validate the constraint
        errors = self.validator.validate_constraint_placement(cell1, cell2)
        
        # Choose preview color based on validation
        if any(e.severity == "error" for e in errors):
            color = "red"
        elif any(e.severity == "warning" for e in errors):
            color = "yellow"
        else:
            color = "lightgreen"
        
        # Draw preview line
        x1, y1 = self.canvas.renderer.evenr_to_pixel(
            cell1[0], cell1[1], 
            self.canvas.canvas_offset_x, self.canvas.canvas_offset_y
        )
        x2, y2 = self.canvas.renderer.evenr_to_pixel(
            cell2[0], cell2[1], 
            self.canvas.canvas_offset_x, self.canvas.canvas_offset_y
        )
        
        preview_line = self.canvas.canvas.create_line(
            x1, y1, x2, y2,
            fill=color,
            width=3,
            dash=(5, 5),
            tags="constraint_preview"
        )
        self.preview_items.append(preview_line)
        
        # Draw preview dot
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        preview_dot = self.canvas.canvas.create_oval(
            mx - 6, my - 6, mx + 6, my + 6,
            fill=color,
            outline="darkgreen",
            width=2,
            tags="constraint_preview"
        )
        self.preview_items.append(preview_dot)
    
    def _clear_preview(self):
        """Clear constraint preview items."""
        for item_id in self.preview_items:
            self.canvas.canvas.delete(item_id)
        self.preview_items.clear()

    def _update_visual_guides(self):
        """Update visual guides for selection mode."""
        self._clear_visual_guides()
        
        if not self.selection_mode:
            return
        
        # Highlight selected cells with medium opacity red
        for row, col in self.selected_cells:
            if not self.canvas.renderer or not hasattr(self.canvas, 'canvas_offset_x'):
                continue
                
            x, y = self.canvas.renderer.evenr_to_pixel(
                row, col, 
                self.canvas.canvas_offset_x, self.canvas.canvas_offset_y
            )
            
            # Create red semi-transparent highlight
            hex_size = self.canvas.renderer.hex_size
            
            # Draw filled red hexagon with medium opacity
            highlight = self.canvas.canvas.create_polygon(
                self.canvas.renderer.get_hex_points(x, y),
                fill="#FF6B6B",  # Medium red color
                stipple="gray50",  # Creates 50% opacity effect
                outline="#CC0000",  # Darker red border
                width=2,
                tags="selection_guide"
            )
            self.guide_items.append(highlight)
        
        # Show possible constraint lines between selected cells
        possible_constraints = self.get_possible_constraints(self.selected_cells)
        for cell1, cell2 in possible_constraints:
            if not self.canvas.renderer:
                continue
                
            x1, y1 = self.canvas.renderer.evenr_to_pixel(
                cell1[0], cell1[1], 
                self.canvas.canvas_offset_x, self.canvas.canvas_offset_y
            )
            x2, y2 = self.canvas.renderer.evenr_to_pixel(
                cell2[0], cell2[1], 
                self.canvas.canvas_offset_x, self.canvas.canvas_offset_y
            )
            
            # Check if constraint already exists
            exists = self.grid.has_dot_constraint(cell1, cell2)
            color = "orange" if exists else "lightblue"
            
            guide_line = self.canvas.canvas.create_line(
                x1, y1, x2, y2,
                fill=color,
                width=2,
                dash=(3, 3),
                tags="selection_guide"
            )
            self.guide_items.append(guide_line)

    def _batch_number_by_selection_order(self):
        """Number cells in the order they were selected (clicked)."""
        if not self.selection_mode or not self.selection_order:
            return False
        
        # Only number playable cells, in selection order
        playable_cells = []
        for cell in self.selection_order:
            if cell in self.selected_cells:  # Still selected
                row, col = cell
                state, _ = self.grid.get_cell_state(row, col)
                if state in (CellState.EMPTY, CellState.PREFILLED):
                    playable_cells.append(cell)
        
        if not playable_cells:
            messagebox.showwarning("No Playable Cells", "No playable cells in selection order.")
            return False
        
        commands = []
        for i, (row, col) in enumerate(playable_cells, 1):
            commands.append(SetCellValueCommand(row, col, i))
        
        batch_command = BatchCommand(commands, f"Number {len(commands)} cells by selection order")
        success = self.grid.command_history.execute_command(batch_command, self.grid)
        
        if success:
            messagebox.showinfo("Selection Order Numbering", 
                            f"Numbered {len(commands)} cells in the order you selected them")
        return success
    
    def _batch_number_by_position(self):
        """Number cells by their position (top to bottom, left to right)."""
        if not self.selection_mode or not self.selected_cells:
            return False
        
        # Get playable cells and sort by position
        playable_cells = []
        for row, col in self.selected_cells:
            state, _ = self.grid.get_cell_state(row, col)
            if state in (CellState.EMPTY, CellState.PREFILLED):
                playable_cells.append((row, col))
        
        if not playable_cells:
            messagebox.showwarning("No Playable Cells", "No playable cells selected.")
            return False
        
        # Sort by position (row first, then column)
        sorted_cells = sorted(playable_cells)
        
        commands = []
        for i, (row, col) in enumerate(sorted_cells, 1):
            commands.append(SetCellValueCommand(row, col, i))
        
        batch_command = BatchCommand(commands, f"Number {len(commands)} cells by position")
        success = self.grid.command_history.execute_command(batch_command, self.grid)
        
        if success:
            messagebox.showinfo("Position Numbering", 
                            f"Numbered {len(commands)} cells by position (top-left to bottom-right)")
        return success

    def _batch_number_custom_start(self):
        """Number cells starting from a custom number."""
        """Number cells by selection order, starting from a custom number.
        Live applies each value (instant board update) and commits as a single undo step."""
        if not self.selection_mode or not self.selected_cells:
            return False

        # Resolve playable cells in explicit selection order
        playable_cells = []
        for cell in self.selection_order:
            if cell in self.selected_cells:
                r, c = cell
                state, _ = self.grid.get_cell_state(r, c)
                if state in (CellState.EMPTY, CellState.PREFILLED):
                    playable_cells.append((r, c))

        if not playable_cells:
            messagebox.showwarning("No Playable Cells", "No playable cells in selection.", parent=self._dialog_parent())
            return False

        max_val = getattr(self.grid, "get_max_possible_value", lambda: 999)()
        start_num = self._askinteger_topmost(
            "Custom Numbering",
            "Enter starting number:",
            minvalue=1, maxvalue=max_val, initialvalue=1
        )
        if start_num is None:
            return False

        # Prefer live updates with single undo step
        try:
            from core.commands import LiveBatchCommand
        except Exception:
            LiveBatchCommand = None

        if LiveBatchCommand is None:
            commands = [SetCellValueCommand(r, c, start_num + i)
                        for i, (r, c) in enumerate(playable_cells)]
            batch_command = BatchCommand(commands, f"Number {len(commands)} cells starting from {start_num}")
            success = self.grid.command_history.execute_command(batch_command, self.grid)
            if success:
                self.canvas.redraw_grid()
                end_num = start_num + len(commands) - 1
                messagebox.showinfo(
                    "Custom Numbering",
                    f"Numbered {len(commands)} cells from {start_num} to {end_num}",
                    parent=self._dialog_parent()
                )
            return success

        live = LiveBatchCommand(f"Number {len(playable_cells)} cells from {start_num}")
        for i, (row, col) in enumerate(playable_cells):
            self._show_current_number_highlight(row, col)
            cmd = SetCellValueCommand(row, col, start_num + i)
            if not live.add_and_execute(self.grid, cmd):
                self._clear_current_number_highlight()
                messagebox.showerror("Numbering Failed", "Could not set a value. Aborting.",
                                    parent=self._dialog_parent())
                live.undo(self.grid)
                if hasattr(self.canvas, "_notify_grid_change"):
                    self.canvas._notify_grid_change()
                self.canvas.redraw_grid()
                return False
            if hasattr(self.canvas, "_notify_grid_change"):
                self.canvas._notify_grid_change()
            self.canvas.redraw_grid()
        self._clear_current_number_highlight()

        success = self.grid.command_history.execute_command(live, self.grid)
        if success:
            end_num = start_num + len(playable_cells) - 1
            messagebox.showinfo(
                "Custom Numbering",
                f"Numbered {len(playable_cells)} cells from {start_num} to {end_num}",
                parent=self._dialog_parent()
            )
            if hasattr(self.canvas, "_notify_grid_change"):
                self.canvas._notify_grid_change()
            self.canvas.redraw_grid()
        return success

    def _batch_number_by_selection_ask_each(self):
        """Number cells by selection order, prompting for each value.
        - Cancel → triage (Abort / Skip / Retry)
        - Dialog stays on top
        - Highlights current cell
        - Live board updates after each accepted value
        - Single undo step overall"""
        if not self.selection_mode or not self.selected_cells:
            return False

        # Resolve playable cells in explicit selection order
        playable_cells = []
        for cell in self.selection_order:
            if cell in self.selected_cells:
                r, c = cell
                state, _ = self.grid.get_cell_state(r, c)
                if state in (CellState.EMPTY, CellState.PREFILLED):
                    playable_cells.append((r, c))

        if not playable_cells:
            messagebox.showwarning("No Playable Cells", "No playable cells in selection.", parent=self._dialog_parent())
            return False

        max_val = getattr(self.grid, "get_max_possible_value", lambda: 999)()
        try:
            from core.commands import LiveBatchCommand
        except Exception:
            LiveBatchCommand = None

        if LiveBatchCommand is None:
            # Fallback without live updates or triage
            commands = []
            last_val = None
            for (r, c) in playable_cells:
                initial = (last_val + 1) if last_val is not None else 1
                val = self._askinteger_topmost(
                    "Number cell",
                    f"Enter value for cell ({r},{c}):",
                    minvalue=1, maxvalue=max_val, initialvalue=initial
                )
                if val is None:
                    continue
                commands.append(SetCellValueCommand(r, c, val))
                last_val = val
            if not commands:
                return False
            batch = BatchCommand(commands, f"Number {len(commands)} cells (ask individually)")
            ok = self.grid.command_history.execute_command(batch, self.grid)
            if ok:
                self.canvas.redraw_grid()
            return ok

        live = LiveBatchCommand(f"Number {len(playable_cells)} cells (ask individually)")
        last_val = None

        for (r, c) in playable_cells:
            self._show_current_number_highlight(r, c)
            while True:
                initial = (last_val + 1) if last_val is not None else 1
                val = self._askinteger_topmost(
                    "Number cell",
                    f"Enter value for cell ({r},{c}):",
                    minvalue=1, maxvalue=max_val, initialvalue=initial
                )
                if val is None:
                    choice = self._askyesnocancel_topmost(
                        "Abort numbering?",
                        "Do you want to abort numbering?\n\n"
                        "Yes = Abort and discard all changes so far\n"
                        "No = Skip this cell and continue\n"
                        "Cancel = Try again for this cell"
                    )
                    if choice is True:
                        self._clear_current_number_highlight()
                        live.undo(self.grid)
                        if hasattr(self.canvas, "_notify_grid_change"):
                            self.canvas._notify_grid_change()
                        self.canvas.redraw_grid()
                        return False
                    elif choice is False:
                        self._clear_current_number_highlight()
                        break  # skip this cell
                    else:
                        continue  # retry same cell

                cmd = SetCellValueCommand(r, c, val)
                if not live.add_and_execute(self.grid, cmd):
                    self._clear_current_number_highlight()
                    messagebox.showerror("Numbering Failed", "Could not set this value. Aborting.",
                                        parent=self._dialog_parent())
                    live.undo(self.grid)
                    if hasattr(self.canvas, "_notify_grid_change"):
                        self.canvas._notify_grid_change()
                    self.canvas.redraw_grid()
                    return False
                last_val = val
                if hasattr(self.canvas, "_notify_grid_change"):
                    self.canvas._notify_grid_change()
                self.canvas.redraw_grid()
                self._clear_current_number_highlight()
                break  # next cell

        if not getattr(live, "commands", None):
            return False
        ok = self.grid.command_history.execute_command(live, self.grid)
        if ok:
            if hasattr(self.canvas, "_notify_grid_change"):
                self.canvas._notify_grid_change()
            self.canvas.redraw_grid()
        return ok

    def get_batch_operations_menu(self) -> Dict[str, Callable]:
        """Get available batch operations for selected cells."""
        if not self.selection_mode or not self.selected_cells:
            return {}
        
        # Analyze selected cells to show only relevant operations
        empty_cells = 0
        prefilled_cells = 0
        blocked_cells = 0
        
        for row, col in self.selected_cells:
            state, value = self.grid.get_cell_state(row, col)
            if state == CellState.EMPTY:
                empty_cells += 1
            elif state == CellState.PREFILLED:
                prefilled_cells += 1
            elif state == CellState.NONPLAYABLE:
                blocked_cells += 1
        
        operations = {}
        
        # Constraint operations
        operations["Create All Constraints"] = self.create_batch_constraints
        operations["Remove All Constraints"] = self.remove_batch_constraints
        
        # State operations
        if empty_cells > 0 or prefilled_cells > 0:
            operations["Set All to Blocked"] = lambda: self._batch_set_state(CellState.NONPLAYABLE)
            operations["Set All to Holes"] = lambda: self._batch_set_state(CellState.HOLE)
        
        if blocked_cells > 0:
            operations["Set All to Empty"] = lambda: self._batch_set_state(CellState.EMPTY)
        
        # IMPROVED: Multiple numbering options
        if empty_cells > 0 or prefilled_cells > 0:
            operations["Number by selection order, starting from..."] = self._batch_number_custom_start
            operations["Number by selection order (ask individually)"] = self._batch_number_by_selection_ask_each
            if prefilled_cells > 0:
                operations["Clear All Numbers"] = self._batch_clear_numbers
        
        # Selection operations
        operations["---"] = None  # Separator
        operations["Grow Selection"] = self._grow_selection
        operations["Select Neighbors Only"] = self._select_neighbors  # Renamed for clarity
        operations["Shrink Selection"] = self._shrink_selection
        operations["Invert Selection"] = self._invert_selection
        operations["Clear Selection"] = self._clear_selection
        
        return operations
    
    def _refresh_selection_after_state_change(self):
        """Refresh selection to only include selectable cells after state changes."""
        valid_selection = set()
        
        for row, col in self.selected_cells:
            # Check if cell still exists and is selectable
            if self.grid.cell_exists(row, col):
                state, _ = self.grid.get_cell_state(row, col)
                if state in (CellState.EMPTY, CellState.PREFILLED):
                    valid_selection.add((row, col))
        
        # Update selection to only valid cells
        self.selected_cells = valid_selection
        self._update_visual_guides()

    def _batch_set_state(self, target_state: CellState):
        """Set all selected cells to a specific state."""
        if not self.selection_mode or not self.selected_cells:
            return False
        
        commands = []
        changed_cells = 0
        
        for row, col in self.selected_cells:
            current_state, current_value = self.grid.get_cell_state(row, col)
            if current_state != target_state:
                commands.append(SetCellStateCommand(row, col, target_state, None))
                changed_cells += 1
        
        if commands:
            batch_command = BatchCommand(commands, f"Set {changed_cells} cells to {target_state.value}")
            success = self.grid.command_history.execute_command(batch_command, self.grid)
            
            if success:
                # Update selection to only include cells that still exist and are selectable
                self._refresh_selection_after_state_change()
                messagebox.showinfo("Batch Operation", f"Changed {changed_cells} cells to {target_state.value}")
            return success
        else:
            messagebox.showinfo("Batch Operation", f"All selected cells are already {target_state.value}")
            return True

    def _batch_number_consecutive(self):
        """Number selected cells consecutively starting from 1."""
        if not self.selection_mode or not self.selected_cells:
            return False
        
        # Only number playable cells
        playable_cells = []
        for row, col in self.selected_cells:
            state, _ = self.grid.get_cell_state(row, col)
            if state in (CellState.EMPTY, CellState.PREFILLED):
                playable_cells.append((row, col))
        
        if not playable_cells:
            messagebox.showwarning("No Playable Cells", "No playable cells selected for numbering.")
            return False
        
        # Sort cells by position for consistent numbering
        sorted_cells = sorted(playable_cells)
        
        commands = []
        for i, (row, col) in enumerate(sorted_cells, 1):
            commands.append(SetCellValueCommand(row, col, i))
        
        batch_command = BatchCommand(commands, f"Number {len(commands)} cells consecutively")
        success = self.grid.command_history.execute_command(batch_command, self.grid)
        
        if success:
            messagebox.showinfo("Batch Numbering", f"Numbered {len(commands)} cells from 1 to {len(commands)}")
        return success

    def _batch_clear_numbers(self):
        """Clear numbers from all selected prefilled cells."""
        if not self.selection_mode or not self.selected_cells:
            return False
        
        commands = []
        for row, col in self.selected_cells:
            current_state, current_value = self.grid.get_cell_state(row, col)
            if current_state == CellState.PREFILLED:
                commands.append(SetCellStateCommand(row, col, CellState.EMPTY, None))
        
        if commands:
            batch_command = BatchCommand(commands, f"Clear numbers from {len(commands)} cells")
            success = self.grid.command_history.execute_command(batch_command, self.grid)
            if success:
                messagebox.showinfo("Clear Numbers", f"Cleared numbers from {len(commands)} cells")
            return success
        else:
            messagebox.showinfo("Clear Numbers", "No numbered cells in selection to clear")
            return True

    def _grow_selection(self):
        """Expand selection by adding ALL neighbors of selected cells."""
        if not self.selection_mode:
            return
        
        if not self.selected_cells:
            messagebox.showinfo("Grow Selection", "No cells selected to grow from.")
            return
        
        new_cells = set(self.selected_cells)  # Start with current selection
        for row, col in list(self.selected_cells):
            neighbors = self.grid.get_neighbors(row, col)
            for nr, nc in neighbors:
                if (nr, nc) not in self.selected_cells:  # Don't add already selected cells
                    state, _ = self.grid.get_cell_state(nr, nc)
                    # Allow selection of any existing cell type
                    if self.grid.cell_exists(nr, nc):
                        new_cells.add((nr, nc))
                        self.selection_order.append((nr, nc))  # Track order of addition
        
        added_count = len(new_cells) - len(self.selected_cells)
        self.selected_cells = new_cells
        self._update_visual_guides()
        
        if added_count > 0:
            messagebox.showinfo("Grow Selection", f"Added {added_count} neighboring cells to selection")
        else:
            messagebox.showinfo("Grow Selection", "No additional neighbors to add")

    def _shrink_selection(self):
        """Remove cells from selection that have fewer than 2 selected neighbors."""
        if not self.selection_mode or len(self.selected_cells) <= 2:
            messagebox.showinfo("Shrink Selection", "Need at least 3 selected cells to shrink.")
            return
        
        cells_to_keep = set()
        for row, col in self.selected_cells:
            neighbors = self.grid.get_neighbors(row, col)
            selected_neighbor_count = sum(1 for n in neighbors if n in self.selected_cells)
            
            # Keep cells with 2 or more selected neighbors (well connected)
            if selected_neighbor_count >= 2:
                cells_to_keep.add((row, col))
        
        if len(cells_to_keep) < len(self.selected_cells):
            removed_count = len(self.selected_cells) - len(cells_to_keep)
            self.selected_cells = cells_to_keep
            
            # Update selection order to only include remaining cells
            self.selection_order = [cell for cell in self.selection_order if cell in cells_to_keep]
            
            self._update_visual_guides()
            messagebox.showinfo("Shrink Selection", f"Removed {removed_count} edge cells from selection")
        else:
            messagebox.showinfo("Shrink Selection", "All selected cells are well-connected - nothing to shrink")

    def _select_neighbors(self):
        """Replace selection with ONLY the neighbors of current selection."""
        if not self.selection_mode:
            return
        
        if not self.selected_cells:
            messagebox.showinfo("Select Neighbors", "No cells selected to find neighbors of.")
            return
        
        # Find all neighbors but DON'T include current selection
        neighbor_cells = set()
        for row, col in self.selected_cells:
            neighbors = self.grid.get_neighbors(row, col)
            for nr, nc in neighbors:
                if (nr, nc) not in self.selected_cells:  # Only neighbors, not current selection
                    if self.grid.cell_exists(nr, nc):
                        neighbor_cells.add((nr, nc))
        
        if neighbor_cells:
            old_count = len(self.selected_cells)
            self.selected_cells = neighbor_cells
            self.selection_order = list(neighbor_cells)  # New order
            self._update_visual_guides()
            messagebox.showinfo("Select Neighbors", 
                            f"Replaced {old_count} selected cells with {len(neighbor_cells)} neighbors")
        else:
            messagebox.showinfo("Select Neighbors", "No neighbors found")

    def _invert_selection(self):
        """Invert selection - select all unselected playable cells, deselect selected ones."""
        if not self.selection_mode:
            return
        
        all_playable = set()
        for row in range(self.grid.rows):
            for col in range(self.grid.cols):
                state, _ = self.grid.get_cell_state(row, col)
                if state in (CellState.EMPTY, CellState.PREFILLED):
                    all_playable.add((row, col))
        
        # Invert: selected becomes unselected, unselected becomes selected
        old_count = len(self.selected_cells)
        self.selected_cells = all_playable - self.selected_cells
        new_count = len(self.selected_cells)
        
        self._update_visual_guides()
        messagebox.showinfo("Invert Selection", f"Selection inverted: {old_count} → {new_count} cells")

    def _clear_selection(self):
        """Clear all selected cells."""
        if not self.selection_mode:
            return
        
        count = len(self.selected_cells)
        self.selected_cells.clear()
        self._update_visual_guides()
        messagebox.showinfo("Clear Selection", f"Cleared {count} selected cells")

    def _clear_visual_guides(self):
        """Clear visual guide items."""
        for item_id in self.guide_items:
            self.canvas.canvas.delete(item_id)
        self.guide_items.clear()
    
    def get_constraint_analysis(self) -> Dict[str, Any]:
        """Get comprehensive constraint analysis."""
        conflicts = self.validator.detect_constraint_conflicts()
        total_constraints = len(self.grid.dot_constraints)
        playable_cells = len(self.grid.get_playable_cells())
        
        # Calculate constraint density
        max_possible = playable_cells * 6 // 2  # Each cell has max 6 neighbors, avoid double counting
        density = total_constraints / max_possible if max_possible > 0 else 0
        
        return {
            "total_constraints": total_constraints,
            "conflicts": conflicts,
            "density": density,
            "recommendations": self._get_constraint_recommendations(conflicts, density)
        }
    
    def _get_constraint_recommendations(self, conflicts: List[ConstraintConflict], density: float) -> List[str]:
        """Generate constraint placement recommendations."""
        recommendations = []
        
        if density > 0.5:
            recommendations.append("High constraint density detected - puzzle may be over-constrained")
        elif density < 0.05:
            recommendations.append("Low constraint density - consider adding more constraints for uniqueness")
        
        error_conflicts = [c for c in conflicts if c.severity == "error"]
        if error_conflicts:
            recommendations.append(f"{len(error_conflicts)} constraint errors need resolution")
        
        warning_conflicts = [c for c in conflicts if c.severity == "warning"]
        if warning_conflicts:
            recommendations.append(f"{len(warning_conflicts)} constraint warnings should be reviewed")
        
        return recommendations