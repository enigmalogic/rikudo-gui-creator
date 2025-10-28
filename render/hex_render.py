"""
Hexagonal rendering utilities for Tkinter Canvas.
Fixed to properly implement EVEN-R coordinate system for correct Rikudo layout.
"""
import math
from typing import Tuple, List
import tkinter as tk

class HexRenderer:
    """Handles hexagonal cell rendering calculations and drawing with correct EVEN-R layout."""
    
    def __init__(self, hex_size: float = 30.0):
        """
        Initialize hex renderer.
        
        Args:
            hex_size: Radius of hexagon (distance from center to vertex)
        """
        self.hex_size = hex_size
        self.hex_width = hex_size * 2
        self.hex_height = hex_size * math.sqrt(3)
        
        # Calculate proper spacing for hexagonal grid
        self.hex_spacing_x = hex_size * math.sqrt(3)  # Distance between hex centers horizontally
        self.hex_spacing_y = hex_size * 1.5  # Distance between hex centers vertically
        
    def evenr_to_pixel(self, row: int, col: int, offset_x: float = 50, offset_y: float = 50) -> Tuple[float, float]:
        """
        Convert EVEN-R coordinates to pixel coordinates for proper hexagonal layout.
        
        Args:
            row, col: EVEN-R grid coordinates
            offset_x, offset_y: Canvas offset for positioning
            
        Returns:
            (x, y) pixel coordinates for hexagon center
        """
        # Calculate base position
        x = offset_x + col * self.hex_spacing_x
        y = offset_y + row * self.hex_spacing_y
        
        # EVEN-R offset: even rows (0, 2, 4...) are shifted right by half hex width
        if row % 2 == 0:
            x += self.hex_spacing_x / 2
            
        return x, y
    
    def pixel_to_evenr(self, pixel_x: float, pixel_y: float, offset_x: float = 50, offset_y: float = 50) -> Tuple[int, int]:
        """
        Convert pixel coordinates back to EVEN-R coordinates (approximate).
        Used for mouse click detection.
        
        Args:
            pixel_x, pixel_y: Canvas pixel coordinates
            offset_x, offset_y: Canvas offset used in drawing
            
        Returns:
            (row, col) EVEN-R coordinates of nearest hex
        """
        # Remove offset
        x = pixel_x - offset_x
        y = pixel_y - offset_y
        
        # Calculate approximate row
        row = round(y / self.hex_spacing_y)
        row = max(0, row)
        
        # Account for even row offset when calculating column
        if row % 2 == 0:
            x -= self.hex_spacing_x / 2
            
        col = round(x / self.hex_spacing_x)
        col = max(0, col)
        
        return row, col
    
    def get_hex_points(self, center_x: float, center_y: float) -> List[float]:
        """
        Get the 6 vertices of a hexagon for Tkinter polygon drawing.
        Creates a pointy-top hexagon (which is standard for Rikudo).
        
        Args:
            center_x, center_y: Center point of hexagon
            
        Returns:
            List of coordinates [x1, y1, x2, y2, ...] for polygon
        """
        points = []
        # Start from top vertex and go clockwise (pointy-top hexagon)
        for i in range(6):
            angle = math.pi / 2 - (math.pi / 3 * i)  # Start from top, go clockwise
            x = center_x + self.hex_size * math.cos(angle)
            y = center_y - self.hex_size * math.sin(angle)  # Negative for screen coordinates
            points.extend([x, y])
        return points
    
    def draw_hexagon(self, canvas: tk.Canvas, row: int, col: int, 
                    fill_color: str = "white", outline_color: str = "black",
                    offset_x: float = 50, offset_y: float = 50) -> int:
        """
        Draw a single hexagon on the canvas.
        
        Args:
            canvas: Tkinter Canvas to draw on
            row, col: EVEN-R coordinates
            fill_color: Interior color
            outline_color: Border color
            offset_x, offset_y: Canvas positioning offset
            
        Returns:
            Canvas item ID for the drawn hexagon
        """
        center_x, center_y = self.evenr_to_pixel(row, col, offset_x, offset_y)
        points = self.get_hex_points(center_x, center_y)
        
        return canvas.create_polygon(
            points, 
            fill=fill_color, 
            outline=outline_color,
            width=2
        )
    
    def draw_text_in_hex(self, canvas: tk.Canvas, row: int, col: int, text: str,
                        offset_x: float = 50, offset_y: float = 50) -> int:
        """
        Draw text in the center of a hexagon.
        
        Args:
            canvas: Tkinter Canvas
            row, col: EVEN-R coordinates  
            text: Text to display
            offset_x, offset_y: Canvas positioning offset
            
        Returns:
            Canvas item ID for the text
        """
        center_x, center_y = self.evenr_to_pixel(row, col, offset_x, offset_y)
        
        return canvas.create_text(
            center_x, center_y,
            text=text,
            font=("Arial", 12, "bold"),
            fill="black"
        )