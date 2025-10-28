"""
Enhanced main application with Phase 3 undo/redo system.
Complete integration of command pattern for reversible operations.
"""

# In main.py, organize imports better:
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sys
import os
from typing import Optional, Any, Callable

# Add project root to path first
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Then import project modules
from core.hex_grid import HexGrid
from guis.hex_canvas import HexCanvas
from core.constraints import ConstraintEditor
from guis.status_bar import EnhancedStatusBar

class RikudoCreatorApp:
    """Enhanced Rikudo Puzzle Creator with Phase 3 undo/redo functionality."""
    
    def __init__(self):
        """Initialize the application."""
        self.root = tk.Tk()
        self.root.title("Rikudo Puzzle Creator")
        self.root.geometry("1400x900")

        # Phase 4 additions
        self.constraint_editor: Optional[ConstraintEditor] = None
        
        # Application state
        self.grid: HexGrid = None
        
        # UI Components
        self.canvas: HexCanvas = None
        self.status_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="cell")
        self.validation_var = tk.StringVar()
        self.history_var = tk.StringVar()  # New: for undo/redo status
        self.enhanced_status_bar = EnhancedStatusBar(self.root)
        
        # Undo/Redo button references
        self.undo_button = None
        self.redo_button = None
        
        self._create_ui()
        self._create_default_grid()
    
    def _create_ui(self):
        """Create the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel for controls
        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        # Right panel for canvas
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self._create_control_panel(left_panel)
        self._create_canvas_area(right_panel)
        self._create_status_bar()

    def _set_edit_mode_enabled(self, enabled: bool):
        """Enable or disable edit mode radio buttons."""
        state = "normal" if enabled else "disabled"
        
        # Disable/enable all radio buttons
        self.edit_cells_radio.config(state=state)
        self.place_constraints_radio.config(state=state)
        self.mark_center_radio.config(state=state)
        self.select_radio.config(state=state)

    def _is_batch_selection_active(self) -> bool:
        """Check if batch selection mode is currently active."""
        return (hasattr(self.canvas, 'constraint_editor') and 
                self.canvas.constraint_editor and 
                self.canvas.constraint_editor.selection_mode)

    def _create_control_panel(self, parent):
        """Create the enhanced left control panel with space-saving layout."""
        # File operations section
        file_frame = ttk.LabelFrame(parent, text="File Operations", padding=5)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_frame, text="New Grid", command=self._create_new_grid).pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="Import JSON", command=self._import_puzzle).pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="Export JSON", command=self._export_json).pack(fill=tk.X, pady=2)
        
        # Undo/Redo section - OPTIMIZED: Clear History button moved to same row
        history_frame = ttk.LabelFrame(parent, text="Undo/Redo", padding=5)
        history_frame.pack(fill=tk.X, pady=(0, 10))
        
        # All three buttons in one row
        button_frame = ttk.Frame(history_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.undo_button = ttk.Button(button_frame, text="↶ Undo", command=self._undo_action, width=10)
        self.undo_button.pack(side=tk.LEFT, padx=(0, 3))
        
        self.redo_button = ttk.Button(button_frame, text="↷ Redo", command=self._redo_action, width=10)
        self.redo_button.pack(side=tk.LEFT, padx=(0, 3))
        
        # Clear History button in same row (right side)
        ttk.Button(button_frame, text="Clear History", command=self._clear_history, width=12).pack(side=tk.RIGHT)
        
        # History status display (now takes full width since no button below)
        self.history_var.set("No operations")
        history_status = ttk.Label(history_frame, textvariable=self.history_var, 
                                relief=tk.SUNKEN, anchor=tk.W, padding=3, font=("Arial", 9))
        history_status.pack(fill=tk.X, pady=(5, 0))
        
        # OPTIMIZED: Grid Dimensions and Edit Mode side-by-side
        dimensions_and_mode_frame = ttk.Frame(parent)
        dimensions_and_mode_frame.pack(fill=tk.X, pady=(0, 10))

        # Grid dimensions section - LEFT COLUMN
        dims_frame = ttk.LabelFrame(dimensions_and_mode_frame, text="Grid Dimensions", padding=5)
        dims_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(dims_frame, text="Rows:").pack(anchor=tk.W)
        self.rows_var = tk.StringVar(value="7")
        ttk.Entry(dims_frame, textvariable=self.rows_var, width=8).pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(dims_frame, text="Columns:").pack(anchor=tk.W)
        self.cols_var = tk.StringVar(value="7")
        ttk.Entry(dims_frame, textvariable=self.cols_var, width=8).pack(anchor=tk.W, pady=(0, 5))

        # Edit mode section - RIGHT COLUMN (ONLY ONE SET - with references)
        mode_frame = ttk.LabelFrame(dimensions_and_mode_frame, text="Functions", padding=5)
        mode_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Store references to radio buttons for enable/disable control
        self.edit_cells_radio = ttk.Radiobutton(mode_frame, text="Edit Cells", variable=self.mode_var, 
                        value="cell", command=self._change_mode)
        self.edit_cells_radio.pack(anchor=tk.W)

        self.place_constraints_radio = ttk.Radiobutton(mode_frame, text="Place Constraints", variable=self.mode_var,
                        value="constraint", command=self._change_mode)
        self.place_constraints_radio.pack(anchor=tk.W)

        self.mark_center_radio = ttk.Radiobutton(mode_frame, text="Mark Center", variable=self.mode_var,
                        value="center", command=self._change_mode)
        self.mark_center_radio.pack(anchor=tk.W)

        self.select_radio = ttk.Radiobutton(mode_frame, text="Select / Inspect", variable=self.mode_var,
                    value="select", command=self._change_mode)
        self.select_radio.pack(anchor=tk.W)
        
        # Validation section
        validation_frame = ttk.LabelFrame(parent, text="Validation", padding=5)
        validation_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(validation_frame, text="Full Validation Report", 
                command=self._show_validation_report).pack(fill=tk.X, pady=2)
        
        # Validation status display
        self.validation_var.set("Ready")
        validation_status = ttk.Label(validation_frame, textvariable=self.validation_var, 
                                    relief=tk.SUNKEN, anchor=tk.W, padding=3)
        validation_status.pack(fill=tk.X, pady=(5, 0))
        
        # Advanced Constraints section
        constraint_frame = ttk.LabelFrame(parent, text="Advanced Constraints", padding=5)
        constraint_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(constraint_frame, text="Batch Selection", command=self._toggle_batch_selection).pack(fill=tk.X, pady=2)
        ttk.Button(constraint_frame, text="Batch Operations/Constraint Analysis", command=self._show_constraint_analysis).pack(fill=tk.X, pady=2)
        
        # Instructions section - Compact version
        help_frame = ttk.LabelFrame(parent, text="Instructions - Phase 4", padding=5)
        help_frame.pack(fill=tk.X, pady=(0, 10))
        
        instructions = """RIKUDO PUZZLE CREATOR - PHASE 4

ADVANCED CONSTRAINTS:
• Batch Selection: Multi-cell operations mode
• Constraint Analysis: Validation and batch operations
• Visual Guides: Red highlights show selections

EDITING MODES:
• Edit Cells: Left=cycle states, Right=enter numbers  
• Place Constraints: Click adjacent cells for dots
• Mark Center: Left click to mark/unmark center

BATCH OPERATIONS:
• Number by Selection Order: Click order numbering
• Number by Position: Spatial order numbering
• Set States: Empty/Blocked/Holes for regions
• Grow/Shrink Selection: Expand/contract selections

UNDO/REDO SYSTEM:
• All operations reversible with descriptions
• Clear History: Reset undo/redo state
• Command tracking: Shows operation counts

WORKFLOW:
• Import JSON: Load existing puzzles
• Export JSON: Save completed puzzles
• Full Validation: Check puzzle completeness"""
        
        # Compact text widget
        text_widget = tk.Text(help_frame, wrap=tk.WORD, height=8, width=38, font=("Arial", 8))
        text_widget.insert(tk.END, instructions)
        text_widget.config(state=tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(help_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.config(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


    # def _create_canvas_area(self, parent):
    #     """Create the canvas area."""
    #     canvas_frame = ttk.Frame(parent)
    #     canvas_frame.pack(fill=tk.BOTH, expand=True)
        
    #     self.canvas = HexCanvas(canvas_frame, width=1100, height=750)
    #     self.canvas.set_change_callback(self._on_grid_change)
    #     self.canvas.set_history_callback(self._on_history_change)
        
    #     # NEW: Connect position callback for enhanced status bar
    #     self.canvas.set_position_callback(self.enhanced_status_bar.update_position)


    def _create_canvas_area(self, parent):
        """Create the canvas area - CLEAN VERSION without temporary Phase 4 sections."""
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = HexCanvas(canvas_frame, width=1100, height=750)
        self.canvas.set_change_callback(self._on_grid_change)
        self.canvas.set_history_callback(self._on_history_change)
        
        # Connect position callback for enhanced status bar
        self.canvas.set_position_callback(self.enhanced_status_bar.update_position)

    def _create_status_bar(self):
        """Create the enhanced status bar."""
        # Enhanced status bar is created in __init__, just connect callbacks here
        pass
    
    def _create_default_grid(self):
        """Create the initial default grid."""
        self.grid = HexGrid(7, 7)
        self.canvas.set_grid(self.grid)
        self._update_status()
        self._update_history_status()
    
    def _create_new_grid(self):
        """Create a new grid with specified dimensions."""
        try:
            rows = int(self.rows_var.get())
            cols = int(self.cols_var.get())
            
            if rows < 3 or rows > 20 or cols < 3 or cols > 20:
                messagebox.showerror("Invalid Dimensions", 
                                "Grid dimensions must be between 3 and 20.")
                return
            
            # Confirm if current puzzle has content
            if self.grid and self._has_puzzle_content():
                result = messagebox.askyesno("New Grid", 
                                        "Current puzzle will be lost. Continue?")
                if not result:
                    return
            
            # Exit batch selection mode if active
            if hasattr(self.canvas, 'constraint_editor') and self.canvas.constraint_editor:
                if self.canvas.constraint_editor.selection_mode:
                    self.canvas.constraint_editor.exit_selection_mode()
                    self._set_edit_mode_enabled(True)
            
            # Create new grid
            self.grid = HexGrid(rows, cols)
            self.canvas.set_grid(self.grid)
            
            # Reset constraint editor
            if hasattr(self.canvas, 'constraint_editor'):
                self.canvas.constraint_editor = None
                self.canvas.enhanced_mode = False
            
            self._update_status()
            self._update_history_status()
            
        except ValueError:
            messagebox.showerror("Invalid Input", 
                            "Please enter valid integer dimensions.")
    
    def _has_puzzle_content(self) -> bool:
        """Check if current puzzle has any content."""
        if not self.grid:
            return False
        
        stats = self.grid.get_statistics()
        return (stats['prefilled_cells'] > 0 or 
                stats['blocked_cells'] > 0 or 
                stats['hole_cells'] > 0 or 
                stats['dot_constraints'] > 0)
    
    def _import_puzzle(self):
        """Import a puzzle from JSON file."""
        if self.grid and self._has_puzzle_content():
            result = messagebox.askyesno("Import Puzzle", 
                                       "Current puzzle will be lost. Continue?")
            if not result:
                return
        
        self.canvas.import_puzzle()
        
        # Update grid reference and dimensions
        if hasattr(self.canvas, 'grid') and self.canvas.grid:
            self.grid = self.canvas.grid
            self.rows_var.set(str(self.grid.rows))
            self.cols_var.set(str(self.grid.cols))
            self._update_status()
            self._update_history_status()
    
    def _export_json(self):
        """Export the current puzzle."""
        self.canvas.export_json()
    
    def _show_validation_report(self):
        """Show detailed validation report."""
        self.canvas.show_validation_report()
    
    # NEW: Undo/Redo methods
    
    def _undo_action(self):
        """Handle undo action."""
        if self.canvas and self.canvas.undo():
            self._update_status()
            self._update_history_status()
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")
    
    def _redo_action(self):
        """Handle redo action.""" 
        if self.canvas and self.canvas.redo():
            self._update_status()
            self._update_history_status()
        else:
            messagebox.showinfo("Redo", "Nothing to redo.")
    
    def _clear_history(self):
        """Clear undo/redo history."""
        if self.grid:
            result = messagebox.askyesno("Clear History", 
                                       "This will clear all undo/redo history. Continue?")
            if result:
                self.canvas.clear_history()
                self._update_history_status()
    
    def _change_mode(self):
        """Handle edit mode changes."""
        # Prevent mode changes if batch selection is active
        if self._is_batch_selection_active():
            return
        
        mode = self.mode_var.get()
        self.canvas.set_edit_mode(mode)

        # OPTIONAL: explicit clear (safe even if already cleared in set_edit_mode)
        if mode != "select" and hasattr(self.canvas, "clear_inspect_overlay"):
            self.canvas.clear_inspect_overlay()
        
        # Normal mode change handling
        if mode == "cell":
            mode_status = "Cell Edit Mode: Left=cycle states, Right=enter numbers"
        elif mode == "constraint":
            mode_status = "Constraint Mode: Click two adjacent cells to add/remove dots"
        elif mode == "center":
            mode_status = "Center Mode: Left click to mark/unmark center cell"
        elif mode == "select":
            mode_status = "Select / Inspect: Left=highlight neighbors, Esc=clear"
        else:
            mode_status = f"{mode} Mode"
        
        self.enhanced_status_bar.update_main_status(mode_status)
        self.status_var.set(mode_status)
    
    def _on_grid_change(self):
        """Handle grid state changes."""
        self._update_status()
        self._update_validation_status()
    
    def _on_history_change(self):
        """Handle undo/redo history changes."""
        self._update_history_status()

    def _update_status(self):
        """Update status bar with current grid statistics."""
        if self.grid is None:
            return
        
        # FIXED: Don't override status if batch selection is active
        if (hasattr(self.canvas, 'constraint_editor') and 
            self.canvas.constraint_editor and 
            self.canvas.constraint_editor.selection_mode):
            # Batch selection is active - only update the old status var for backward compatibility
            # but don't override the enhanced status bar main message
            stats = self.grid.get_statistics()
            mode_text = "Batch Selection"
            
            status_parts = [
                f"{mode_text} Mode",
                f"Selected: {len(self.canvas.constraint_editor.selected_cells)}",
                f"Playable: {stats['total_playable']}",
                f"Dots: {stats['dot_constraints']}"
            ]
            
            # Update only the old status var, leave enhanced status bar alone
            self.status_var.set(" | ".join(status_parts))
            return
        
        # Normal status update when NOT in batch selection mode
        stats = self.grid.get_statistics()
        mode_text = {
            "cell": "Cell Edit",
            "constraint": "Constraint", 
            "center": "Center"
        }.get(self.mode_var.get(), "Unknown")
        
        # Build status message for enhanced status bar
        status_parts = [
            f"{mode_text} Mode",
            f"Playable: {stats['total_playable']}",
            f"Empty: {stats['empty_cells']}",
            f"Filled: {stats['prefilled_cells']}",
            f"Blocked: {stats['blocked_cells']}",
        ]
        
        if stats['hole_cells'] > 0:
            status_parts.append(f"Holes: {stats['hole_cells']}")
        
        status_parts.append(f"Dots: {stats['dot_constraints']}")
        
        if stats['center_cells'] > 0:
            status_parts.append(f"Center: {stats['center_cells']}")
        
        if stats['is_connected']:
            status_parts.append("✓Connected")
        else:
            status_parts.append("⚠ Disconnected")
        
        # Update enhanced status bar
        self.enhanced_status_bar.update_main_status(" | ".join(status_parts))
        
        # Also update the old status var for backward compatibility
        self.status_var.set(" | ".join(status_parts))

    def _update_validation_status(self):
        """Update validation status display."""
        if self.grid is None:
            self.validation_var.set("No puzzle")
            return
        
        validation_errors = self.grid.validate_puzzle()
        errors = [e for e in validation_errors if e.severity == "error"]
        warnings = [e for e in validation_errors if e.severity == "warning"]
        
        # Update enhanced status bar
        self.enhanced_status_bar.update_validation_status(len(errors), len(warnings))
        
        # Update old status var for backward compatibility
        if errors:
            self.validation_var.set(f"❌ {len(errors)} errors")
        elif warnings:
            self.validation_var.set(f"⚠️ {len(warnings)} warnings")
        else:
            stats = self.grid.get_statistics()
            if stats['is_connected'] and stats['total_playable'] > 0:
                self.validation_var.set("✅ Valid puzzle")
            else:
                self.validation_var.set("⚠️ Incomplete")
    
    def _update_history_status(self):
        """Update undo/redo status display."""
        if self.grid is None:
            self.history_var.set("No grid")
            self.undo_button.config(state="disabled")
            self.redo_button.config(state="disabled")
            return
        
        # Update button states
        can_undo = self.grid.can_undo()
        can_redo = self.grid.can_redo()
        
        self.undo_button.config(state="normal" if can_undo else "disabled")
        self.redo_button.config(state="normal" if can_redo else "disabled")
        
        # Get operation descriptions
        history_info = self.grid.get_history_info()
        undo_desc = history_info["undo_description"]
        redo_desc = history_info["redo_description"]
        
        # Update old status var for backward compatibility
        parts = []
        if can_undo and undo_desc:
            short_desc = undo_desc[:22] + "..." if len(undo_desc) > 25 else undo_desc
            parts.append(f"Undo: {short_desc}")
        
        if can_redo and redo_desc:
            short_desc = redo_desc[:22] + "..." if len(redo_desc) > 25 else redo_desc
            parts.append(f"Redo: {short_desc}")
        
        if not parts:
            parts.append(f"Operations: {history_info['total_commands']}")
        
        self.history_var.set(" | ".join(parts) if parts else "No operations")
    
    def run(self):
        """Start the application."""
        self.root.mainloop()

    def _toggle_batch_selection(self):
        """Toggle batch constraint selection mode."""
        if not self.grid:
            messagebox.showwarning("No Grid", "No grid loaded for constraint editing.")
            return
        
        # Initialize enhanced mode and constraint editor if needed
        if not hasattr(self.canvas, 'enhanced_mode') or not self.canvas.enhanced_mode:
            self.canvas.set_enhanced_mode(True)
        
        if not hasattr(self.canvas, 'constraint_editor') or self.canvas.constraint_editor is None:
            self.canvas.constraint_editor = ConstraintEditor(self.canvas, self.grid)
        
        # Toggle selection mode
        if self.canvas.constraint_editor.selection_mode:
            # Exit batch selection mode
            self.canvas.constraint_editor.exit_selection_mode()
            
            # Re-enable edit mode controls
            self._set_edit_mode_enabled(True)
            
            # Restore normal status by triggering mode change
            self._change_mode()
        else:
            # Enter batch selection mode
            self.canvas.constraint_editor.enter_selection_mode()
            
            # Disable edit mode controls to show they're overridden
            self._set_edit_mode_enabled(False)
            
            # Set persistent batch selection status
            status_msg = "BATCH SELECTION ACTIVE - Click cells to select (overrides edit mode)"
            self.enhanced_status_bar.update_main_status(status_msg)
            
            # Show clear instructions
            messagebox.showinfo("Batch Selection Mode", 
                            """BATCH SELECTION MODE ENABLED

    This mode overrides all edit mode settings.

    • Edit mode radio buttons are disabled (greyed out)
    • Click any cell to add/remove from selection
    • Only playable cells (white/orange) can be selected
    • Selected cells show red highlights
    • Use 'Batch Operations' for batch operations
    • Click 'Batch Selection' again to exit and re-enable edit modes

    The edit mode controls will be restored when you exit batch selection.""")
        
        # Redraw to show changes and update status
        self.canvas.redraw_grid()
        self._update_status()

    def _show_batch_operations_menu(self):
        """Show batch operations menu for selected cells."""
        if not hasattr(self.canvas, 'constraint_editor') or not self.canvas.constraint_editor:
            return
            
        operations = self.canvas.constraint_editor.get_batch_operations_menu()
        selected_count = len(self.canvas.constraint_editor.selected_cells)
        
        if not operations:
            messagebox.showinfo("No Operations", "No batch operations available.")
            return
        
        # Create operations menu dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Batch Operations")
        dialog.geometry("350x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Title
        title_label = ttk.Label(dialog, text=f"Batch Operations", font=("Arial", 14, "bold"))
        title_label.pack(pady=10)
        
        subtitle_label = ttk.Label(dialog, text=f"{selected_count} cells selected", font=("Arial", 10))
        subtitle_label.pack(pady=(0, 10))
        
        # Scrollable frame for operations
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Operations buttons
        for op_name, op_func in operations.items():
            if op_name == "---":  # Separator
                ttk.Separator(scrollable_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
                continue
                
            btn = ttk.Button(scrollable_frame, text=op_name, 
                            command=lambda f=op_func: self._execute_batch_operation(f, dialog))
            btn.pack(fill=tk.X, pady=2, padx=10)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def _execute_batch_operation(self, operation_func: Callable, dialog: tk.Toplevel):
        """Execute a batch operation and update the UI."""
        try:
            success = operation_func()
            if success:
                self._update_status()
                self._update_validation_status()
                self._update_history_status()  # Update undo/redo status
                self.canvas.redraw_grid()
            # Don't close dialog automatically - let user perform multiple operations
        except Exception as e:
            messagebox.showerror("Operation Error", f"Failed to execute operation: {str(e)}")

    def _show_constraint_analysis(self):
        """Show constraint analysis dialog with batch operations menu."""
        if not self.grid:
            messagebox.showwarning("No Grid", "No grid loaded for analysis.")
            return
        
        # Ensure enhanced mode and constraint editor are initialized
        if not hasattr(self.canvas, 'enhanced_mode') or not self.canvas.enhanced_mode:
            self.canvas.set_enhanced_mode(True)
        
        if not hasattr(self.canvas, 'constraint_editor') or self.canvas.constraint_editor is None:
            self.canvas.constraint_editor = ConstraintEditor(self.canvas, self.grid)
        
        # If in batch selection mode, show operations menu
        if self.canvas.constraint_editor.selection_mode and self.canvas.constraint_editor.selected_cells:
            self._show_batch_operations_menu()
            return
        
        # Otherwise show regular constraint analysis
        analysis = self.canvas.constraint_editor.get_constraint_analysis()
        
        # Build analysis report
        report_parts = []
        report_parts.append(f"CONSTRAINT ANALYSIS REPORT\n{'='*35}")
        report_parts.append(f"Total Constraints: {analysis['total_constraints']}")
        report_parts.append(f"Constraint Density: {analysis['density']:.2%}")
        report_parts.append("")
        
        # Show conflicts
        conflicts = analysis['conflicts']
        if conflicts:
            error_conflicts = [c for c in conflicts if c.severity == "error"]
            warning_conflicts = [c for c in conflicts if c.severity == "warning"]
            
            if error_conflicts:
                report_parts.append(f"CONSTRAINT ERRORS ({len(error_conflicts)}):")
                for conflict in error_conflicts[:5]:
                    report_parts.append(f"  • {conflict.message}")
                if len(error_conflicts) > 5:
                    report_parts.append(f"  ... and {len(error_conflicts) - 5} more errors")
                report_parts.append("")
            
            if warning_conflicts:
                report_parts.append(f"CONSTRAINT WARNINGS ({len(warning_conflicts)}):")
                for conflict in warning_conflicts[:5]:
                    report_parts.append(f"  • {conflict.message}")
                if len(warning_conflicts) > 5:
                    report_parts.append(f"  ... and {len(warning_conflicts) - 5} more warnings")
                report_parts.append("")
        else:
            report_parts.append("✓ No constraint conflicts detected")
            report_parts.append("")
        
        # Show recommendations
        recommendations = analysis['recommendations']
        if recommendations:
            report_parts.append("RECOMMENDATIONS:")
            for rec in recommendations:
                report_parts.append(f"  • {rec}")
            report_parts.append("")
        
        # Batch operations info
        if hasattr(self.canvas, 'constraint_editor') and self.canvas.constraint_editor.selection_mode:
            selected_count = len(self.canvas.constraint_editor.selected_cells)
            possible_constraints = len(self.canvas.constraint_editor.get_possible_constraints(
                self.canvas.constraint_editor.selected_cells))
            
            report_parts.append("BATCH SELECTION:")
            report_parts.append(f"  • Selected Cells: {selected_count}")
            report_parts.append(f"  • Possible Constraints: {possible_constraints}")
            
            if possible_constraints > 0:
                report_parts.append("")
                if messagebox.askyesno("Batch Operations", 
                                    "\n".join(report_parts) + 
                                    "\n\nCreate all possible constraints from selection?"):
                    success = self.canvas.constraint_editor.create_batch_constraints()
                    if success:
                        self._update_status()
                        self._update_validation_status()
                        self.canvas.redraw_grid()
                    return
        
        # Show analysis report
        report_text = "\n".join(report_parts)
        messagebox.showinfo("Constraint Analysis", report_text)

    def _update_all_status(self):
        """Centralized status update method."""
        self._update_status()
        self._update_validation_status() 
        self._update_history_status()

def main():
    """Main entry point."""
    try:
        app = RikudoCreatorApp()
        app.run()
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()