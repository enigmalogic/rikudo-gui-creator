# guis/hex_renderer_json.py
#!/usr/bin/env python3
"""
Hexagonal Grid Renderer for JSON Format Puzzles
Renders Rikudo puzzles from the new graph-based JSON format.

Key features:
- Works with arbitrary vertex topologies
- Uses explicit adjacency lists instead of computed neighbors
- Handles missing coordinates gracefully
- Supports all standard Rikudo visual elements
"""

import math
import numpy as np
import matplotlib.patches as patches
from typing import Dict, List, Tuple, Optional, Any


class RikudoHexRenderer:
    """
    Render a Rikudo puzzle from JSON graph format using matplotlib.
    Supports arbitrary topologies defined by vertex adjacency lists.
    """

    def __init__(self, radius: float = 40.0, padding: float = 1.0, text_weight: str = 'bold'):
        """
        Initialize the renderer.
        
        Args:
            radius: Radius of hexagonal cells in pixels
            padding: Padding around the puzzle in units of radius
            text_weight: Font weight for numbers ('normal' or 'bold')
        """
        self.R = float(radius)
        self.pad = float(padding)
        self.tw = text_weight

    def _get_raw_centers(self, layout: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
        """
        Calculate raw (x,y) centers for vertices based on their grid coordinates.
        Uses hexagonal grid geometry with even-r offset pattern.
        
        Args:
            layout: Layout information from JSON puzzle
            
        Returns:
            Dictionary mapping vertex_id to (x, y) coordinates
        """
        w = math.sqrt(3) * self.R  # hexagon width
        h = 1.5 * self.R           # vertical step between rows

        raw_centers = {}
        
        # Use coordinates from layout if available
        if "coordinates" in layout:
            coordinates = layout["coordinates"]
            for vertex_id, coord in coordinates.items():
                r, c = coord
                
                # Even-r offset: shift even rows right by half-width
                offset = 0.5 * ((r + 1) & 1)
                
                x = w * (c + offset)
                y = h * r
                
                raw_centers[vertex_id] = (x, y)
        
        return raw_centers

    def _normalize_centers(
        self, raw_centers: Dict[str, Tuple[float, float]]
    ) -> Tuple[Dict[str, Tuple[float, float]], float, float, float, float]:
        """
        Normalize coordinates to center the puzzle and calculate bounds.

        Returns:
            (normalized_centers, half_width, half_height, cx_shift, cy_shift)
        """
        if not raw_centers:
            return {}, 0, 0, 0.0, 0.0

        xs, ys = zip(*raw_centers.values())
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Center of bounding box → origin
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0

        normalized = {vid: (x - cx, y - cy) for vid, (x, y) in raw_centers.items()}
        half_w = (max_x - min_x) / 2.0
        half_h = (max_y - min_y) / 2.0
        return normalized, half_w, half_h, cx, cy

    def _draw_hex(self, ax, cx: float, cy: float, facecolor: str, edgecolor: str = 'black', linewidth: float = 1):
        """
        Draw a single hexagon at the specified center.
        
        Args:
            ax: Matplotlib axis
            cx, cy: Center coordinates
            facecolor: Fill color
            edgecolor: Border color  
            linewidth: Border width
        """
        # Pointy-top hexagon vertices
        angles = np.deg2rad([30, 90, 150, 210, 270, 330, 30])
        pts = [
            (cx + self.R * math.cos(a), cy + self.R * math.sin(a))
            for a in angles
        ]
        
        poly = patches.Polygon(
            pts, closed=True,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth
        )
        ax.add_patch(poly)

    def _draw_inner_ring(self, ax, cx: float, cy: float, ring_ratio: float = 0.75):
        """
        Draw inner ring for start (1) and end (max_value) cells.
        
        Args:
            ax: Matplotlib axis
            cx, cy: Center coordinates
            ring_ratio: Size ratio of inner ring to outer hex
        """
        inner_radius = self.R * ring_ratio
        angles = np.deg2rad([30, 90, 150, 210, 270, 330, 30])
        pts = [
            (cx + inner_radius * math.cos(a), cy + inner_radius * math.sin(a))
            for a in angles
        ]
        
        ax.add_patch(patches.Polygon(
            pts, closed=True,
            facecolor='none',
            edgecolor='black',
            linewidth=1
        ))

    def _draw_center_badge(self, ax, cx: float, cy: float):
        """Draw a bold badge (purple inner on red outer) + two white arcs."""
        # Outer and inner hexes (reuse _draw_hex via polygons for consistency)
        angles = np.deg2rad([30, 90, 150, 210, 270, 330, 30])
        pts_out = [(cx + self.R * math.cos(a), cy + self.R * math.sin(a)) for a in angles]
        pts_inr = [(cx + 0.9*self.R * math.cos(a), cy + 0.9*self.R * math.sin(a)) for a in angles]

        ax.add_patch(patches.Polygon(pts_out, closed=True, facecolor="#f55", edgecolor='none', zorder=10))
        ax.add_patch(patches.Polygon(pts_inr, closed=True, facecolor="#7d3aa6", edgecolor='none', zorder=12))

        # Two clipped arcs in white
        arc_r = 0.675 * self.R
        arc_off = 0.5 * self.R
        lw = max(0.5, 0.04375 * self.R)

        up = patches.Circle((cx, cy + arc_off), arc_r, fill=False, linewidth=lw, edgecolor='white', zorder=14)
        lo = patches.Circle((cx, cy - arc_off), arc_r, fill=False, linewidth=lw, edgecolor='white', zorder=14)

        # Clip arcs to the inner hex
        inner_poly = patches.Polygon(pts_inr, closed=True, facecolor='none', edgecolor='none')
        ax.add_patch(inner_poly)
        up.set_clip_path(inner_poly)
        lo.set_clip_path(inner_poly)
        ax.add_patch(up)
        ax.add_patch(lo)

    def render_puzzle(self, graph_data: Dict[str, Any], ax=None, *, show_centroid_ring: bool = False) -> Optional[object]:
        """
        Render a complete puzzle from JSON graph data.
        
        Args:
            graph_data: Puzzle data in JSON graph format
            ax: Optional matplotlib axis (creates new figure if None)
            
        Returns:
            Matplotlib axis object
        """
        if ax is None:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 8))

        # Extract data
        layout = graph_data.get("layout", {})
        vertices = graph_data.get("vertices", {})
        dots = graph_data.get("constraints", {}).get("dots", [])
        max_num = graph_data.get("max_value", 0)

        # Calculate positions
        raw_centers = self._get_raw_centers(layout)
        centers, half_w, half_h, cx_shift, cy_shift = self._normalize_centers(raw_centers)


        # If no layout coordinates, fall back to simple grid
        if not centers and vertices:
            print("Warning: No layout coordinates found, using fallback positioning")
            centers = self._generate_fallback_layout(vertices)
            half_w = half_h = self.R * 3  # Conservative bounds

        # Draw vertices
        for vertex_id, vertex_info in vertices.items():
            if vertex_id not in centers:
                continue  # Skip vertices without coordinates
                
            cx, cy = centers[vertex_id]
            value = vertex_info.get("value")
            
            # Determine colors
            if value is not None:
                facecolor = "#FFA500"  # Orange for pre-filled
            else:
                facecolor = "#FFFFFF"  # White for empty
            
            # Draw the hexagon
            self._draw_hex(ax, cx, cy, facecolor)
            
            # Draw the number if present
            if value is not None:
                font_size = max(8, min(24, self.R / 2.5))
                ax.text(cx, cy, str(value),
                       ha='center', va='center',
                       fontsize=font_size,
                       fontweight=self.tw,
                       color='black')
                
                # Draw inner ring for start/end values
                if value in (1, max_num):
                    self._draw_inner_ring(ax, cx, cy)

        # Draw dot constraints
        for v1_id, v2_id in dots:
            if v1_id in centers and v2_id in centers:
                x1, y1 = centers[v1_id]
                x2, y2 = centers[v2_id]
                
                # Draw orange dot at midpoint
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                dot_radius = self.R / 8
                
                circle = patches.Circle(
                    (mx, my), radius=dot_radius,
                    facecolor='#FFA500',
                    edgecolor='black',
                    linewidth=1
                )
                ax.add_patch(circle)

        # --- Center handling (JSON) ---
        center_rc = layout.get("center_rc", None)
        if isinstance(center_rc, (list, tuple)) and len(center_rc) == 2:
            cr, cc = int(center_rc[0]), int(center_rc[1])

            # Compute the raw center position for this (r,c), then normalize using cx_shift, cy_shift
            w = math.sqrt(3) * self.R
            h = 1.5 * self.R
            offset = 0.5 * ((cr + 1) & 1)  # even-r offset pattern
            raw_x = w * (cc + offset)
            raw_y = h * cr
            cx, cy = raw_x - cx_shift, raw_y - cy_shift

            # Draw blocked hex at center + badge
            self._draw_hex(ax, cx, cy, facecolor="#909090")
            self._draw_center_badge(ax, cx, cy)

        elif show_centroid_ring and centers:
            # Optional subtle ring at the geometric centroid (when no explicit center_rc)
            mean_x = sum(x for x, _ in centers.values()) / len(centers)
            mean_y = sum(y for _, y in centers.values()) / len(centers)
            ax.add_patch(patches.Circle((mean_x, mean_y), radius=self.R*0.66, fill=False, linewidth=1.2, alpha=0.8))

        # Set up the axis
        pad_x = half_w + self.pad * self.R
        pad_y = half_h + self.pad * self.R

        ax.set_aspect('equal')
        ax.set_xlim(-pad_x, +pad_x)
        ax.set_ylim(+pad_y, -pad_y)  # Invert Y to match grid convention
        ax.axis('off')

        return ax

    def _generate_fallback_layout(self, vertices: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
        """
        Generate a simple fallback layout when no coordinates are provided.
        
        Args:
            vertices: Dictionary of vertices
            
        Returns:
            Dictionary mapping vertex_id to (x, y) positions
        """
        # Simple spiral layout as fallback
        centers = {}
        angle_step = 2 * math.pi / max(6, len(vertices))
        
        for i, vertex_id in enumerate(vertices.keys()):
            if i == 0:
                # Center the first vertex
                centers[vertex_id] = (0, 0)
            else:
                # Arrange others in a spiral
                radius = self.R * 2 * ((i - 1) // 6 + 1)
                angle = angle_step * i
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                centers[vertex_id] = (x, y)
        
        return centers


# Standalone testing
if __name__ == "__main__":
    # Create a simple test puzzle
    test_puzzle = {
        "id": "test_puzzle",
        "max_value": 7,
        "vertices": {
            "0,0": {"value": 1},
            "0,1": {"value": None},
            "1,0": {"value": None},
            "1,1": {"value": 7},
        },
        "adjacency": {
            "0,0": ["0,1", "1,0"],
            "0,1": ["0,0", "1,1"],
            "1,0": ["0,0", "1,1"],
            "1,1": ["0,1", "1,0"],
        },
        "constraints": {
            "dots": [["0,0", "0,1"]]
        },
        "layout": {
            "rows": 2,
            "cols": 2,
            "coordinates": {
                "0,0": [0, 0],
                "0,1": [0, 1],
                "1,0": [1, 0],
                "1,1": [1, 1],
            }
        }
    }
    
    # Test the renderer
    import matplotlib.pyplot as plt
    
    renderer = RikudoHexRenderer(radius=40)
    fig, ax = plt.subplots(figsize=(8, 6))
    
    renderer.render_puzzle(test_puzzle, ax)
    ax.set_title("Test JSON Puzzle Rendering", fontsize=14, pad=20)
    
    plt.tight_layout()
    plt.show()