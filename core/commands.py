"""
Command pattern implementation for undo/redo functionality in Rikudo Puzzle Creator.
Phase 3: Add reversible operations for all grid modifications.
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Any, Dict
from enum import Enum
from core.types import CellState

class Command(ABC):
    """Abstract base class for all reversible commands."""
    
    @abstractmethod
    def execute(self, grid) -> bool:
        """Execute the command. Returns True if successful."""
        pass
    
    @abstractmethod
    def undo(self, grid) -> bool:
        """Undo the command. Returns True if successful."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description of the command."""
        pass

class SetCellStateCommand(Command):
    """Command to change cell state and value."""
    
    def __init__(self, row: int, col: int, new_state: CellState, new_value: Optional[int] = None):
        self.row = row
        self.col = col
        self.new_state = new_state
        self.new_value = new_value
        self.old_state: Optional[CellState] = None
        self.old_value: Optional[int] = None
        self.old_center_location: Optional[Tuple[int, int]] = None
    
    def execute(self, grid) -> bool:
        """Execute the cell state change."""
        # Store old state for undo
        self.old_state, self.old_value = grid.get_cell_state(self.row, self.col)
        self.old_center_location = grid.center_location
        
        # Execute the change
        grid.set_cell_state(self.row, self.col, self.new_state, self.new_value)
        return True
    
    def undo(self, grid) -> bool:
        """Undo the cell state change."""
        if self.old_state is None:
            return False
        
        # Restore old center location if it was changed
        if self.old_center_location != grid.center_location:
            grid.center_location = self.old_center_location
        
        # Restore old state
        grid.set_cell_state(self.row, self.col, self.old_state, self.old_value)
        return True
    
    def get_description(self) -> str:
        """Get description of the command."""
        return f"Set cell ({self.row}, {self.col}) to {self.new_state.value}"

class CycleCellStateCommand(Command):
    """Command to cycle through cell states."""
    
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col
        self.old_state: Optional[CellState] = None
        self.old_value: Optional[int] = None
        self.new_state: Optional[CellState] = None
        self.new_value: Optional[int] = None
        self.old_center_location: Optional[Tuple[int, int]] = None
    
    def execute(self, grid) -> bool:
        """Execute the cell state cycle."""
        # Store old state
        self.old_state, self.old_value = grid.get_cell_state(self.row, self.col)
        self.old_center_location = grid.center_location
        
        # Execute cycle
        grid.cycle_cell_state(self.row, self.col)
        
        # Store new state for description
        self.new_state, self.new_value = grid.get_cell_state(self.row, self.col)
        return True
    
    def undo(self, grid) -> bool:
        """Undo the cell state cycle."""
        if self.old_state is None:
            return False
        
        # Restore old center location if it was changed
        if self.old_center_location != grid.center_location:
            grid.center_location = self.old_center_location
        
        # Restore old state
        grid.set_cell_state(self.row, self.col, self.old_state, self.old_value)
        return True
    
    def get_description(self) -> str:
        """Get description of the command."""
        return f"Cycle cell ({self.row}, {self.col}) {self.old_state.value} → {self.new_state.value}"

class SetCellValueCommand(Command):
    """Command to set a numeric value in a cell."""
    
    def __init__(self, row: int, col: int, value: int):
        self.row = row
        self.col = col
        self.new_value = value
        self.old_state: Optional[CellState] = None
        self.old_value: Optional[int] = None
    
    def execute(self, grid) -> bool:
        """Execute the value setting."""
        # Store old state
        self.old_state, self.old_value = grid.get_cell_state(self.row, self.col)
        
        # Execute the change
        success = grid.set_cell_value(self.row, self.col, self.new_value)
        return success
    
    def undo(self, grid) -> bool:
        """Undo the value setting."""
        if self.old_state is None:
            return False
        
        # Restore old state
        grid.set_cell_state(self.row, self.col, self.old_state, self.old_value)
        return True
    
    def get_description(self) -> str:
        """Get description of the command."""
        return f"Set value {self.new_value} at ({self.row}, {self.col})"

class AddDotConstraintCommand(Command):
    """Command to add a dot constraint between two cells."""
    
    def __init__(self, cell1: Tuple[int, int], cell2: Tuple[int, int]):
        self.cell1 = cell1
        self.cell2 = cell2
        self.was_successful = False
    
    def execute(self, grid) -> bool:
        """Execute adding the constraint."""
        self.was_successful = grid.add_dot_constraint(self.cell1, self.cell2)
        return self.was_successful
    
    def undo(self, grid) -> bool:
        """Undo adding the constraint."""
        if not self.was_successful:
            return True  # Nothing to undo
        
        return grid.remove_dot_constraint(self.cell1, self.cell2)
    
    def get_description(self) -> str:
        """Get description of the command."""
        return f"Add constraint {self.cell1} ↔ {self.cell2}"

class RemoveDotConstraintCommand(Command):
    """Command to remove a dot constraint between two cells."""
    
    def __init__(self, cell1: Tuple[int, int], cell2: Tuple[int, int]):
        self.cell1 = cell1
        self.cell2 = cell2
        self.was_removed = False
    
    def execute(self, grid) -> bool:
        """Execute removing the constraint."""
        self.was_removed = grid.remove_dot_constraint(self.cell1, self.cell2)
        return self.was_removed
    
    def undo(self, grid) -> bool:
        """Undo removing the constraint."""
        if not self.was_removed:
            return True  # Nothing to undo
        
        return grid.add_dot_constraint(self.cell1, self.cell2)
    
    def get_description(self) -> str:
        """Get description of the command."""
        return f"Remove constraint {self.cell1} ↔ {self.cell2}"

class BatchCommand(Command):
    """Command that groups multiple commands into a single undo/redo unit."""
    
    def __init__(self, commands: List[Command], description: str):
        self.commands = commands
        self.description = description
        self.executed_commands: List[Command] = []
    
    def execute(self, grid) -> bool:
        """Execute all commands in sequence."""
        self.executed_commands.clear()
        
        for command in self.commands:
            if command.execute(grid):
                self.executed_commands.append(command)
            else:
                # If any command fails, undo all successful ones
                for executed_command in reversed(self.executed_commands):
                    executed_command.undo(grid)
                return False
        
        return True
    
    def undo(self, grid) -> bool:
        """Undo all commands in reverse order."""
        success = True
        for command in reversed(self.executed_commands):
            if not command.undo(grid):
                success = False
        
        return success
    
    def get_description(self) -> str:
        """Get description of the batch operation."""
        return self.description

class ImportPuzzleCommand(Command):
    """Command to import a complete puzzle (batch operation)."""
    
    def __init__(self, json_data: Dict):
        self.json_data = json_data
        self.old_grid_data: Optional[Dict] = None
    
    def execute(self, grid) -> bool:
        """Execute the puzzle import."""
        # Store old grid state
        self.old_grid_data = grid.to_json("backup")
        
        # Clear current grid and import new data
        try:
            # Import the new puzzle data
            new_grid = grid.__class__.from_json(self.json_data)
            
            # Copy all state from new grid to current grid
            grid.rows = new_grid.rows
            grid.cols = new_grid.cols
            grid.cell_states = new_grid.cell_states.copy()
            grid.dot_constraints = new_grid.dot_constraints.copy()
            grid.center_location = new_grid.center_location

            # Preserve loaded adjacency (Phase-1 fidelity)
            grid.loaded_adjacency = getattr(new_grid, 'loaded_adjacency', None)
            
            return True
        except Exception:
            return False
    
    def undo(self, grid) -> bool:
        """Undo the puzzle import."""
        if self.old_grid_data is None:
            return False
        
        try:
            # Restore old grid state
            old_grid = grid.__class__.from_json(self.old_grid_data)
            
            grid.rows = old_grid.rows
            grid.cols = old_grid.cols
            grid.cell_states = old_grid.cell_states.copy()
            grid.dot_constraints = old_grid.dot_constraints.copy()
            grid.center_location = old_grid.center_location

            # Restore loaded adjacency on undo
            grid.loaded_adjacency = getattr(old_grid, 'loaded_adjacency', None)
            
            return True
        except Exception:
            return False
    
    def get_description(self) -> str:
        """Get description of the import operation."""
        puzzle_id = self.json_data.get("id", "unknown")
        return f"Import puzzle '{puzzle_id}'"

class CommandHistory:
    """Manages command history for undo/redo operations."""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.history: List[Command] = []
        self.current_index = -1  # Points to last executed command
    
    def execute_command(self, command: Command, grid) -> bool:
        """Execute a command and add it to history."""
        success = command.execute(grid)
        
        if success:
            # Remove any commands after current index (if we're in middle of history)
            if self.current_index < len(self.history) - 1:
                self.history = self.history[:self.current_index + 1]
            
            # Add new command
            self.history.append(command)
            self.current_index += 1
            
            # Limit history size
            if len(self.history) > self.max_history:
                self.history.pop(0)
                self.current_index -= 1
        
        return success
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return self.current_index < len(self.history) - 1
    
    def undo(self, grid) -> bool:
        """Undo the last command."""
        if not self.can_undo():
            return False
        
        command = self.history[self.current_index]
        success = command.undo(grid)
        
        if success:
            self.current_index -= 1
        
        return success
    
    def redo(self, grid) -> bool:
        """Redo the next command."""
        if not self.can_redo():
            return False
        
        self.current_index += 1
        command = self.history[self.current_index]
        success = command.execute(grid)
        
        if not success:
            self.current_index -= 1
        
        return success
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of command that would be undone."""
        if not self.can_undo():
            return None
        return self.history[self.current_index].get_description()
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of command that would be redone."""
        if not self.can_redo():
            return None
        return self.history[self.current_index + 1].get_description()
    
    def clear_history(self):
        """Clear all command history."""
        self.history.clear()
        self.current_index = -1
    
    def get_history_info(self) -> Dict[str, Any]:
        """Get information about current history state."""
        return {
            "total_commands": len(self.history),
            "current_index": self.current_index,
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
            "undo_description": self.get_undo_description(),
            "redo_description": self.get_redo_description()
        }