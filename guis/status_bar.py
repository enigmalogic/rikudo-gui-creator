import tkinter as tk
from tkinter import ttk
from typing import Optional

class EnhancedStatusBar:
    """Advanced status bar with multiple information zones."""
    
    def __init__(self, parent: tk.Widget):
        self.frame = ttk.Frame(parent)
        self.frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create status zones
        self._create_status_zones()
        
        # Status data
        self.mode_info = ""
        self.grid_stats = ""
        self.validation_status = ""
        self.operation_status = ""
        self.position_info = ""

    def _create_status_zones(self):
        """Create different zones of the status bar."""
        # Main status (left side)
        self.main_status = tk.StringVar(value="Ready")
        main_label = ttk.Label(self.frame, textvariable=self.main_status, 
                              relief=tk.SUNKEN, anchor=tk.W, padding=3)
        main_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=2)
        
        # Validation status
        self.validation_var = tk.StringVar(value="No errors")
        validation_label = ttk.Label(self.frame, textvariable=self.validation_var,
                                   relief=tk.SUNKEN, anchor=tk.CENTER, padding=3, width=15)
        validation_label.pack(side=tk.LEFT)
        
        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=2)
        
        # Position info (right side) - MOVED UP, NO MORE OPERATIONS SECTION
        self.position_var = tk.StringVar(value="")
        position_label = ttk.Label(self.frame, textvariable=self.position_var,
                                 relief=tk.SUNKEN, anchor=tk.E, padding=3, width=12)
        position_label.pack(side=tk.RIGHT)
    
    def update_main_status(self, status: str):
        """Update main status message."""
        self.main_status.set(status)
    
    def update_validation_status(self, errors: int, warnings: int):
        """Update validation status zone."""
        if errors > 0:
            self.validation_var.set(f"❌ {errors} errors")
        elif warnings > 0:
            self.validation_var.set(f"⚠️ {warnings} warnings")
        else:
            self.validation_var.set("✅ Valid")
    
    def update_position(self, row: Optional[int] = None, col: Optional[int] = None):
        """Update mouse position info."""
        if row is not None and col is not None:
            self.position_var.set(f"({row},{col})")
        else:
            self.position_var.set("")