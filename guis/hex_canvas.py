"""
Enhanced HexCanvas with undo/redo support.
Phase 3: Updated to use command-based operations for reversible actions.
"""
import tkinter as tk
from tkinter import messagebox, filedialog
from typing import Optional, Callable, Tuple, Set
from core.hex_grid import HexGrid
from core.types import CellState, ValidationError
from render.hex_render import HexRenderer
from core.constraints import ConstraintEditor

class HexCanvas:
    """Enhanced interactive canvas for editing hexagonal Rikudo puzzles with undo/redo."""
    
    def __init__(self, parent: tk.Widget, width: int = 800, height: int = 600):
        """Initialize the hex canvas."""
        self.canvas = tk.Canvas(parent, width=width, height=height, bg="lightgray")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Grid and rendering
        self.grid: Optional[HexGrid] = None
        self.renderer = HexRenderer(hex_size=25.0)
        
        # Canvas state
        self.canvas_offset_x = 50
        self.canvas_offset_y = 50
        
        # Interaction mode
        self.edit_mode = "cell"  # "cell", "constraint", "center"
        
        # Constraint editing state
        self.constraint_start_cell: Optional[Tuple[int, int]] = None
        
        # Callbacks
        self.on_grid_change: Optional[Callable] = None
        self.on_history_change: Optional[Callable] = None  # New callback for undo/redo state
        
        # Event bindings
        self._setup_event_bindings()
        
        # Drawing state
        self.cell_items = {}
        self.text_items = {}
        self.constraint_items = {}
        self.validation_items = {}

        # Phase 4 additions
        self.constraint_editor: Optional[ConstraintEditor] = None
        self.enhanced_mode = False

        self.inspect_target: Optional[Tuple[int, int]] = None
        self.inspect_neighbors: Set[Tuple[int, int]] = set()
        self.position_callback: Optional[Callable] = None
    
    def set_enhanced_mode(self, enabled: bool):
        """Enable/disable enhanced constraint editing."""
        self.enhanced_mode = enabled
        if enabled and not self.constraint_editor:
            self.constraint_editor = ConstraintEditor(self, self.grid)
    
    def _setup_event_bindings(self):
        """Set up mouse event handlers."""
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_mouse_motion)
        self.canvas.bind("<Escape>", self._clear_inspect_overlay)
    
    def set_grid(self, grid: HexGrid):
        """Set the grid to display and interact with."""
        self.grid = grid
        self.redraw_grid()
        self._notify_history_change()
    
    def set_edit_mode(self, mode: str):
        """Set the interaction mode."""
        self.edit_mode = mode
        self.constraint_start_cell = None  # Reset constraint selection

        # Auto-clear inspect overlay when switching away from Select/Inspect
        if mode != "select":
            self.inspect_target = None
            self.inspect_neighbors.clear()

        self.redraw_grid()  # Refresh to remove any constraint preview
    
    def set_change_callback(self, callback: Callable):
        """Set callback function to be called when grid changes."""
        self.on_grid_change = callback
    
    def set_history_callback(self, callback: Callable):
        """Set callback function to be called when undo/redo state changes."""
        self.on_history_change = callback
    
    def _notify_grid_change(self):
        """Notify about grid changes."""
        if self.on_grid_change:
            self.on_grid_change()
        self._notify_history_change()
    
    def _notify_history_change(self):
        """Notify about undo/redo state changes."""
        if self.on_history_change:
            self.on_history_change()

    def _on_left_click(self, event):
        """Handle left mouse clicks."""
        if self.grid is None:
            return
        
        self.canvas.focus_set()
        
        row, col = self.renderer.pixel_to_evenr(
            event.x, event.y, 
            self.canvas_offset_x, self.canvas_offset_y
        )
        
        if not (0 <= row < self.grid.rows and 0 <= col < self.grid.cols):
            return
        
        # CRITICAL FIX: Check batch selection mode FIRST, regardless of edit mode
        if (hasattr(self, 'enhanced_mode') and self.enhanced_mode and 
            hasattr(self, 'constraint_editor') and self.constraint_editor and
            self.constraint_editor.selection_mode):
            
            # In batch selection mode - handle selection regardless of edit mode radio button
            handled = self.constraint_editor.toggle_cell_selection(row, col)
            if handled:
                self.redraw_grid()  # Show selection changes
                self._notify_grid_change()  # Update status
                return  # Exit early - batch selection overrides everything
        
        # Only use normal edit mode behavior if NOT in batch selection mode
        if self.edit_mode == "cell":
            self._handle_cell_edit(row, col)
        elif self.edit_mode == "center":
            self._handle_center_edit(row, col)
        elif self.edit_mode == "constraint":
            # Normal constraint editing (only when NOT in batch selection mode)
            self._handle_constraint_edit(row, col)
        elif self.edit_mode == "select":
            self._handle_inspect_click(row, col)
        
        self._notify_grid_change()
        self.redraw_grid()

    def is_batch_selection_active(self) -> bool:
        """Check if batch selection mode is currently active."""
        return (hasattr(self, 'enhanced_mode') and self.enhanced_mode and 
                hasattr(self, 'constraint_editor') and self.constraint_editor and
                self.constraint_editor.selection_mode)

    def _on_right_click(self, event):
        """Handle right mouse clicks (number input)."""
        if self.grid is None or self.edit_mode != "cell":
            return
        
        row, col = self.renderer.pixel_to_evenr(
            event.x, event.y,
            self.canvas_offset_x, self.canvas_offset_y
        )
        
        if not (0 <= row < self.grid.rows and 0 <= col < self.grid.cols):
            return
        
        # Don't allow number input on holes
        current_state, _ = self.grid.get_cell_state(row, col)
        if current_state == CellState.HOLE:
            return
        
        self._prompt_for_number(row, col)

    def set_position_callback(self, callback: Callable):
        """Set position update callback for status bar."""
        self.position_callback = callback
    
    def _on_mouse_motion(self, event):
        """Handle mouse motion for constraint preview and position tracking."""
        # Always update position regardless of mode
        if hasattr(self, 'position_callback') and self.position_callback:
            row, col = self.renderer.pixel_to_evenr(
                event.x, event.y,
                self.canvas_offset_x, self.canvas_offset_y
            )
            # Only update if coordinates are valid
            if 0 <= row < self.grid.rows and 0 <= col < self.grid.cols:
                self.position_callback(row, col)
            else:
                self.position_callback()  # Clear position display
        
        # Constraint preview logic (keep existing)
        if self.edit_mode != "constraint" or self.constraint_start_cell is None:
            return
        
        row, col = self.renderer.pixel_to_evenr(
            event.x, event.y,
            self.canvas_offset_x, self.canvas_offset_y
        )
        
        if not (0 <= row < self.grid.rows and 0 <= col < self.grid.cols):
            return
        
        # Check if this would be a valid constraint
        if self.grid.get_neighbors(*self.constraint_start_cell):
            neighbors = self.grid.get_neighbors(*self.constraint_start_cell)
            if (row, col) in neighbors:
                self.redraw_grid()
                self._draw_constraint_preview(self.constraint_start_cell, (row, col))
    
    def _handle_cell_edit(self, row: int, col: int):
        """Handle cell state cycling using command system."""
        # Use the command-based method for undo/redo support
        self.grid.cmd_cycle_cell_state(row, col)

    def _handle_inspect_click(self, row: int, col: int):
        """Left-click in Select/Inspect mode: highlight this cell and its neighbors."""
        if self.grid is None:
            return
        
        state, _ = self.grid.get_cell_state(row, col)
        if state in (CellState.HOLE, CellState.NONPLAYABLE, CellState.CENTER):
            return

        # Compute neighbors via grid API; this matches the app's adjacency model
        nbrs = list(self.grid.get_neighbors(row, col))

        # Keep only non-hole cells
        cleaned = []
        for nr, nc in nbrs:
            s, _ = self.grid.get_cell_state(nr, nc)
            if s not in (CellState.HOLE, CellState.NONPLAYABLE, CellState.CENTER):
                cleaned.append((nr, nc))

        self.inspect_target = (row, col)
        self.inspect_neighbors = set(cleaned)
        self.redraw_grid()  # overlay drawn at the end

    def _clear_inspect_overlay(self, event=None):
        self.inspect_target = None
        self.inspect_neighbors.clear()
        self.redraw_grid()

    def _draw_inspect_overlay(self):
        """Overlay: ring on target + soft fill on neighbors (drawn last)."""
        if self.inspect_target is None:
            return

        tr, tc = self.inspect_target
        tx, ty = self.renderer.evenr_to_pixel(
            tr, tc, self.canvas_offset_x, self.canvas_offset_y
        )
        # Ring around the target cell
        radius = self.renderer.hex_size + 3
        self.canvas.create_oval(
            tx - radius, ty - radius, tx + radius, ty + radius,
            outline="blue", width=3
        )

        # Fill neighbors with a stippled polygon (fake transparency)
        for nr, nc in self.inspect_neighbors:
            nx, ny = self.renderer.evenr_to_pixel(
                nr, nc, self.canvas_offset_x, self.canvas_offset_y
            )
            pts = self.renderer.get_hex_points(nx, ny)
            self.canvas.create_polygon(
                pts,
                fill="#90EE90",       # light green
                stipple="gray25",     # ~25% opacity effect in Tk
                outline="green",
                width=2
            )

    
    def _handle_center_edit(self, row: int, col: int):
        """Handle center cell marking using command system."""
        current_state, _ = self.grid.get_cell_state(row, col)
        
        # Can't mark holes as center
        if current_state == CellState.HOLE:
            return
        
        if current_state == CellState.CENTER:
            # Remove center (convert to empty)
            self.grid.cmd_set_cell_state(row, col, CellState.EMPTY)
        else:
            # Set as center
            self.grid.cmd_set_cell_state(row, col, CellState.CENTER)
    
    def _handle_constraint_edit(self, row: int, col: int):
        """Handle constraint dot placement using command system."""
        cell = (row, col)
        
        # Check if cell is playable
        state, _ = self.grid.get_cell_state(row, col)
        if state not in (CellState.EMPTY, CellState.PREFILLED):
            messagebox.showwarning("Invalid Cell", "Can only place constraints between playable cells.")
            return
        
        if self.constraint_start_cell is None:
            # Start a new constraint
            self.constraint_start_cell = cell
        else:
            # Complete the constraint
            if cell == self.constraint_start_cell:
                # Clicked same cell, cancel
                self.constraint_start_cell = None
            else:
                # Try to add/remove constraint using command system
                if self.grid.has_dot_constraint(self.constraint_start_cell, cell):
                    success = self.grid.cmd_remove_dot_constraint(self.constraint_start_cell, cell)
                else:
                    success = self.grid.cmd_add_dot_constraint(self.constraint_start_cell, cell)
                
                if not success:
                    messagebox.showwarning("Invalid Constraint", 
                                         "Constraints can only be placed between adjacent cells.")
                
                self.constraint_start_cell = None
    
    def _prompt_for_number(self, row: int, col: int):
        """Prompt user to enter a number for a cell using command system."""
        current_state, current_value = self.grid.get_cell_state(row, col)
        
        if current_state in (CellState.NONPLAYABLE, CellState.HOLE):
            messagebox.showwarning("Invalid Cell", "Cannot place numbers in blocked cells or holes.")
            return
        
        result = tk.simpledialog.askinteger(
            "Enter Number",
            f"Enter number for cell ({row}, {col}):",
            minvalue=1,
            maxvalue=self.grid.get_max_possible_value() or 99,
            initialvalue=current_value or 1
        )
        
        if result is not None:
            # Use command-based method for undo/redo support
            success = self.grid.cmd_set_cell_value(row, col, result)
            if not success:
                # Check specific reason for failure
                if self.grid.has_duplicate_value(result, exclude_cell=(row, col)):
                    messagebox.showerror("Duplicate Value", 
                                       f"Value {result} already exists in the puzzle.")
                elif not (1 <= result <= self.grid.get_max_possible_value()):
                    max_val = self.grid.get_max_possible_value()
                    messagebox.showerror("Invalid Range", 
                                       f"Value must be between 1 and {max_val}.")
                else:
                    messagebox.showerror("Invalid Value", "Could not set this value.")
                return
            
            self._notify_grid_change()
            self.redraw_grid()
    
    # Undo/Redo methods
    
    def undo(self) -> bool:
        """Undo the last operation."""
        if not self.grid:
            return False
        
        success = self.grid.undo()
        if success:
            self._notify_grid_change()
            self.redraw_grid()
        return success
    
    def redo(self) -> bool:
        """Redo the next operation."""
        if not self.grid:
            return False
        
        success = self.grid.redo()
        if success:
            self._notify_grid_change()
            self.redraw_grid()
        return success
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.grid.can_undo() if self.grid else False
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.grid.can_redo() if self.grid else False
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of operation that would be undone."""
        return self.grid.get_undo_description() if self.grid else None
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of operation that would be redone."""
        return self.grid.get_redo_description() if self.grid else None
    
    def clear_history(self):
        """Clear undo/redo history."""
        if self.grid:
            self.grid.clear_history()
            self._notify_history_change()
    
    # All other existing methods remain the same
    
    def redraw_grid(self):
        """Completely redraw the grid on the canvas."""
        if self.grid is None:
            return
        
        # Clear existing items
        self.canvas.delete("all")
        self.cell_items.clear()
        self.text_items.clear()
        self.constraint_items.clear()
        self.validation_items.clear()
        
        # Draw all cells (but skip holes)
        for row in range(self.grid.rows):
            for col in range(self.grid.cols):
                state, _ = self.grid.get_cell_state(row, col)
                if state != CellState.HOLE:  # Don't draw holes
                    self._draw_cell(row, col)
        
        # Draw constraint dots
        self._draw_constraints()
        
        # Draw validation indicators
        self._draw_validation_indicators()
        
        # Highlight constraint start cell if in constraint mode
        if self.edit_mode == "constraint" and self.constraint_start_cell is not None:
            self._highlight_cell(*self.constraint_start_cell, "yellow")
        
        # CRITICAL: Update batch selection visual guides
        if (hasattr(self, 'constraint_editor') and self.constraint_editor and
            hasattr(self.constraint_editor, 'selection_mode') and 
            self.constraint_editor.selection_mode):
            self.constraint_editor._update_visual_guides()

        self._draw_inspect_overlay()
    
    def _draw_cell(self, row: int, col: int):
        """Draw a single cell with appropriate styling."""
        state, value = self.grid.get_cell_state(row, col)
        
        # Skip holes - they render as empty space
        if state == CellState.HOLE:
            return
        
        # Choose colors based on state
        if state == CellState.EMPTY:
            fill_color = "white"
            outline_color = "black"
        elif state == CellState.PREFILLED:
            fill_color = "orange"
            outline_color = "black"
        elif state == CellState.NONPLAYABLE:
            fill_color = "gray"
            outline_color = "darkgray"
        elif state == CellState.CENTER:
            fill_color = "lightblue"
            outline_color = "blue"
        else:
            fill_color = "white"
            outline_color = "black"
        
        # Draw hexagon
        item_id = self.renderer.draw_hexagon(
            self.canvas, row, col,
            fill_color=fill_color,
            outline_color=outline_color,
            offset_x=self.canvas_offset_x,
            offset_y=self.canvas_offset_y
        )
        self.cell_items[(row, col)] = item_id
        
        # Draw number if present
        if value is not None:
            text_id = self.renderer.draw_text_in_hex(
                self.canvas, row, col, str(value),
                offset_x=self.canvas_offset_x,
                offset_y=self.canvas_offset_y
            )
            self.text_items[(row, col)] = text_id
    
    def _draw_constraints(self):
        """Draw dot constraints as green dots between cell centers."""
        for (cell1, cell2) in self.grid.dot_constraints:
            r1, c1 = cell1
            r2, c2 = cell2
            
            # Skip constraints involving holes
            state1, _ = self.grid.get_cell_state(r1, c1)
            state2, _ = self.grid.get_cell_state(r2, c2)
            if state1 == CellState.HOLE or state2 == CellState.HOLE:
                continue
            
            x1, y1 = self.renderer.evenr_to_pixel(r1, c1, self.canvas_offset_x, self.canvas_offset_y)
            x2, y2 = self.renderer.evenr_to_pixel(r2, c2, self.canvas_offset_x, self.canvas_offset_y)
            
            # Calculate midpoint
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            
            # Draw green dot
            dot_id = self.canvas.create_oval(
                mx - 4, my - 4, mx + 4, my + 4,
                fill="green",
                outline="darkgreen",
                width=2
            )
            self.constraint_items[(cell1, cell2)] = dot_id
    
    def _draw_validation_indicators(self):
        """Draw visual indicators for validation errors."""
        if self.grid is None:
            return
        
        validation_errors = self.grid.validate_puzzle()
        
        for error in validation_errors:
            if error.location is None:
                continue
            
            row, col = error.location
            state, _ = self.grid.get_cell_state(row, col)
            
            # Skip indicators for holes
            if state == CellState.HOLE:
                continue
            
            # Choose color based on severity
            if error.severity == "error":
                color = "red"
                width = 3
            elif error.severity == "warning":
                color = "yellow"
                width = 2
            else:
                continue
            
            # Draw warning/error border around the cell
            x, y = self.renderer.evenr_to_pixel(row, col, self.canvas_offset_x, self.canvas_offset_y)
            radius = self.renderer.hex_size + 2
            
            indicator_id = self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                outline=color,
                width=width,
                fill=""
            )
            self.validation_items[(row, col)] = indicator_id
    
    def _draw_constraint_preview(self, cell1: Tuple[int, int], cell2: Tuple[int, int]):
        """Draw a preview of a potential constraint."""
        r1, c1 = cell1
        r2, c2 = cell2
        
        x1, y1 = self.renderer.evenr_to_pixel(r1, c1, self.canvas_offset_x, self.canvas_offset_y)
        x2, y2 = self.renderer.evenr_to_pixel(r2, c2, self.canvas_offset_x, self.canvas_offset_y)
        
        # Draw preview line
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill="lightgreen",
            width=3,
            dash=(5, 5)
        )
    
    def _highlight_cell(self, row: int, col: int, color: str):
        """Highlight a cell with a colored border."""
        x, y = self.renderer.evenr_to_pixel(row, col, self.canvas_offset_x, self.canvas_offset_y)
        radius = self.renderer.hex_size + 3
        
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            outline=color,
            width=3,
            fill=""
        )
    
    def import_puzzle(self):
        """Import a puzzle from JSON file using command system."""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import Puzzle from JSON"
        )
        
        if filename:
            try:
                import json
                with open(filename, 'r') as f:
                    json_data = json.load(f)
                
                # Use command-based import for undo/redo support
                success = self.grid.cmd_import_puzzle(json_data)
                
                if success:
                    # Show import summary
                    stats = self.grid.get_statistics()
                    summary = f"""Puzzle imported successfully!
                    
Grid: {self.grid.rows} × {self.grid.cols}
Playable cells: {stats['total_playable']}
Prefilled cells: {stats['prefilled_cells']}
Constraints: {stats['dot_constraints']}
Holes: {stats['hole_cells']}

Validation: {stats['errors']} errors, {stats['warnings']} warnings"""
                    
                    messagebox.showinfo("Import Success", summary)
                    
                    self._notify_grid_change()
                    self.redraw_grid()
                else:
                    messagebox.showerror("Import Error", "Failed to import puzzle. Please check the file format.")
                    
            except FileNotFoundError:
                messagebox.showerror("Import Error", "File not found.")
            except json.JSONDecodeError as e:
                messagebox.showerror("Import Error", f"Invalid JSON format: {str(e)}")
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import puzzle: {str(e)}")
    
    def export_json(self):
        """Export the current grid as JSON."""
        if self.grid is None:
            messagebox.showerror("No Grid", "No grid to export.")
            return
        
        # Check validation status
        validation_errors = self.grid.validate_puzzle()
        errors = [e for e in validation_errors if e.severity == "error"]
        warnings = [e for e in validation_errors if e.severity == "warning"]
        
        # Show validation summary
        if errors:
            error_details = "\n".join([f"• {e.message}" for e in errors[:5]])
            if len(errors) > 5:
                error_details += f"\n... and {len(errors) - 5} more errors"
            
            result = messagebox.askyesno("Validation Errors", 
                                       f"Puzzle has {len(errors)} errors:\n\n{error_details}\n\nExport anyway?")
            if not result:
                return
        elif warnings:
            warning_details = "\n".join([f"• {e.message}" for e in warnings[:3]])
            if len(warnings) > 3:
                warning_details += f"\n... and {len(warnings) - 3} more warnings"
            
            result = messagebox.askyesno("Validation Warnings", 
                                       f"Puzzle has {len(warnings)} warnings:\n\n{warning_details}\n\nContinue export?")
            if not result:
                return
        
        # Get filename
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Puzzle as JSON"
        )
        
        if filename:
            try:
                puzzle_id = tk.simpledialog.askstring("Puzzle ID", "Enter puzzle ID:", initialvalue="custom_puzzle")
                if puzzle_id:
                    self.grid.save_json(filename, puzzle_id)
                    messagebox.showinfo("Export Success", f"Puzzle exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export puzzle: {str(e)}")
    
    def show_validation_report(self):
        """Show detailed validation report."""
        if self.grid is None:
            messagebox.showwarning("No Puzzle", "No puzzle to validate.")
            return
        
        validation_errors = self.grid.validate_puzzle()
        stats = self.grid.get_statistics()
        
        # Build validation report
        report_parts = []
        report_parts.append(f"PUZZLE VALIDATION REPORT\n{'='*40}")
        report_parts.append(f"Grid Size: {self.grid.rows} × {self.grid.cols}")
        report_parts.append(f"Total Playable: {stats['total_playable']}")
        report_parts.append(f"Prefilled: {stats['prefilled_cells']}")
        report_parts.append(f"Empty: {stats['empty_cells']}")
        report_parts.append(f"Holes: {stats['hole_cells']}")
        report_parts.append(f"Constraints: {stats['dot_constraints']}")
        report_parts.append("")
        
        # Group errors by severity
        errors = [e for e in validation_errors if e.severity == "error"]
        warnings = [e for e in validation_errors if e.severity == "warning"]
        
        if errors:
            report_parts.append(f"ERRORS ({len(errors)}):")
            for error in errors[:10]:  # Limit to first 10
                report_parts.append(f"  • {error}")
            if len(errors) > 10:
                report_parts.append(f"  ... and {len(errors) - 10} more errors")
            report_parts.append("")
        
        if warnings:
            report_parts.append(f"WARNINGS ({len(warnings)}):")
            for warning in warnings[:10]:  # Limit to first 10
                report_parts.append(f"  • {warning}")
            if len(warnings) > 10:
                report_parts.append(f"  ... and {len(warnings) - 10} more warnings")
            report_parts.append("")
        
        if not errors and not warnings:
            report_parts.append("✓ No validation issues found!")
        
        # Export readiness
        export_ready = len(errors) == 0 and stats['is_connected']
        status = "READY for export" if export_ready else "NOT READY for export"
        report_parts.append(f"Export Status: {status}")
        
        # Show report in a dialog
        report_text = "\n".join(report_parts)
        messagebox.showinfo("Validation Report", report_text)