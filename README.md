# Rikudo Creator Coordinate System Specification

**Document Version:** 1.0  
**Date:** January 2025  
**Purpose:** Comprehensive specification of the GUI puzzle creator's coordinate system, neighbor calculation, and JSON export format

---

## 1. Overview

The Rikudo Puzzle Creator is a Tkinter-based GUI application that allows users to design hexagonal Rikudo puzzles and export them to JSON format. This document specifies exactly how the creator handles coordinates, calculates neighbors, and generates the JSON output that the solver will consume.

### 1.1 Key Design Principles

The creator is designed with several important principles:

**Sparse Grid Representation:** Unlike the legacy solver which uses dense rectangular grids with placeholder values, the creator only tracks cells that actually exist in the puzzle. This enables support for arbitrary puzzle shapes including holes and irregular boundaries.

**Standard EVEN-R Coordinates:** The creator uses the well-established EVEN-R (even-row-offset) hexagonal coordinate system throughout. In this system, even-numbered rows are shifted right by half a hexagon width, and all neighbor calculations are based on row parity.

**Explicit Topology:** Rather than computing neighbors on-demand from coordinates, the creator explicitly stores adjacency relationships in the exported JSON. This makes the puzzle format topology-agnostic and suitable for arbitrary graph shapes.

### 1.2 Coordinate System Choice

The creator uses standard EVEN-R coordinates because they provide a good balance of intuitiveness and mathematical simplicity. The coordinate system has these properties:

- Coordinates are integer pairs representing row and column positions
- Even rows (row index 0, 2, 4, etc.) are offset right by half a hexagon
- Odd rows (row index 1, 3, 5, etc.) are aligned to the left edge
- Neighbor relationships are determined by row parity using fixed delta patterns

---

## 2. EVEN-R Coordinate System

### 2.1 Basic Principles

In the EVEN-R (even-row-offset) coordinate system, hexagons are arranged in rows where each even row is shifted horizontally by half a hexagon width relative to odd rows. This creates the characteristic hexagonal tiling pattern.

A cell at position `(row, col)` represents a hexagon in the grid where:
- `row` is the vertical position (0-indexed from top)
- `col` is the horizontal position within that row (0-indexed from left)

The key distinguishing feature is that **even rows are offset to the right**. This affects how we calculate neighbor positions.

### 2.2 Visual Layout

Here is how coordinates map to hexagons in a small EVEN-R grid:

```
Row 0 (EVEN):       (0,0)   (0,1)   (0,2)   (0,3)
                    /  \    /  \    /  \    /  \
Row 1 (ODD):    (1,0)   (1,1)   (1,2)   (1,3)   (1,4)
                  /  \   /  \   /  \   /  \   /  \
Row 2 (EVEN):  (2,0) (2,1)  (2,2)  (2,3)  (2,4)
```

Notice how even rows (0, 2) appear shifted right compared to odd row (1). This offset is what makes the hexagonal tiling work correctly.

### 2.3 Parity-Based Neighbor Calculation

The neighbor calculation logic is based on row parity. Each hexagon has up to six neighbors arranged around it. The relative positions of these neighbors depend on whether the current cell is in an even or odd row.

**For EVEN rows** (row % 2 == 0), the six neighbor offsets are:
```
Up-Left:    (-1, -1)    Up-Right:   (-1,  0)
Left:       ( 0, -1)    Right:      ( 0,  1)
Down-Left:  ( 1, -1)    Down-Right: ( 1,  0)
```

**For ODD rows** (row % 2 == 1), the six neighbor offsets are:
```
Up-Left:    (-1,  0)    Up-Right:   (-1,  1)
Left:       ( 0, -1)    Right:      ( 0,  1)
Down-Left:  ( 1,  0)    Down-Right: ( 1,  1)
```

Notice that the left and right neighbors always use the same offsets regardless of parity, but the diagonal neighbors have different column offsets depending on whether the row is even or odd.

### 2.4 Implementation Details

The creator implements this neighbor calculation in `utils/hex_parity.py` through the `get_hex_neighbors_evenr()` function. This function takes three parameters:

- `row_lengths`: A sequence containing the length of each row (supporting ragged grids)
- `r`: The row coordinate of the cell
- `c`: The column coordinate of the cell

The function returns a list of valid neighbor coordinates by:

1. Determining row parity using `r % 2 == 0`
2. Selecting the appropriate delta pattern (even or odd)
3. Computing candidate neighbor positions by adding deltas
4. Filtering out invalid positions (negative indices, out of row bounds)
5. Returning only neighbors that actually exist in the grid

This approach naturally handles sparse grids and irregular shapes because it validates each neighbor against the actual grid structure rather than assuming a regular pattern.

---

## 3. Sparse Grid Architecture

### 3.1 What is a Sparse Grid?

A sparse grid representation only stores information about cells that actually exist in the puzzle, rather than maintaining a full rectangular array with placeholder values. This has several advantages:

**Memory Efficiency:** Only playable cells consume memory, not the surrounding empty space.

**Natural Hole Support:** Cells can be completely absent from the grid, creating holes in the puzzle without requiring special placeholder values.

**Flexible Shapes:** Puzzles can have any arbitrary shape defined by which cells exist, not constrained by rectangular boundaries.

**Explicit Topology:** By storing neighbors explicitly in the adjacency list, the topology is independent of coordinate calculations.

### 3.2 Grid Storage Structure

The creator's `HexGrid` class stores the puzzle state in several data structures:

**Cells Dictionary:** A nested dictionary `cells[row][col]` that maps coordinates to cell data. Only cells that exist in the puzzle have entries in this dictionary.

**Dot Constraints Set:** A set of tuples representing pairs of adjacent cells that must be consecutive in the solution path.

**Center Location:** An optional coordinate marking the special center cell (if present).

Each cell stores its state (empty, prefilled, blocked, etc.) and optional value (for prefilled numbers).

### 3.3 Coordinate-to-String Mapping

For JSON export and internal lookups, the creator uses string identifiers for cells. The conversion is straightforward:

**To String:** `f"{row},{col}"` produces strings like `"3,5"` or `"0,1"`

**From String:** Split on comma and convert to integers: `"3,5"` becomes `(3, 5)`

This string format is used as vertex IDs throughout the JSON structure, providing a readable and consistent identifier scheme.

---

## 4. Neighbor Calculation Algorithm

### 4.1 Core Algorithm

The neighbor calculation is the heart of the topology definition. Here is the complete algorithm implemented in `get_hex_neighbors_evenr()`:

**Step 1: Validate Input**
- Check that the row index is within bounds (0 to len(row_lengths))
- Check that the column index is within the specified row length
- Return empty list if coordinates are invalid

**Step 2: Determine Parity**
- Calculate `is_even = (r % 2 == 0)`
- Select delta pattern based on parity

**Step 3: Generate Candidates**
- For each of the six direction deltas:
  - Add delta to current position: `(r + dr, c + dc)`
  - Create candidate neighbor coordinate

**Step 4: Validate Candidates**
- Check neighbor row is non-negative
- Check neighbor row is within grid bounds
- Check neighbor column is non-negative
- Check neighbor column is within that row's length
- Only include neighbors that pass all checks

**Step 5: Return Valid Neighbors**
- Return list of validated neighbor coordinates

This algorithm is shape-agnostic because it checks actual row lengths rather than assuming a regular grid structure.

### 4.2 Example: Computing Neighbors

Let's walk through a concrete example. Consider a cell at position `(2, 3)` in a grid where row 2 has 5 cells.

**Given:** `r = 2`, `c = 3`, `row_lengths[2] = 5`

**Step 1:** Row 2 exists and column 3 is valid (< 5), so continue.

**Step 2:** `2 % 2 == 0`, so this is an EVEN row. Use EVEN deltas.

**Step 3:** Apply each delta:
- Up-Left: `(2-1, 3-1) = (1, 2)`
- Up-Right: `(2-1, 3+0) = (1, 3)`
- Left: `(2+0, 3-1) = (2, 2)`
- Right: `(2+0, 3+1) = (2, 4)`
- Down-Left: `(2+1, 3-1) = (3, 2)`
- Down-Right: `(2+1, 3+0) = (3, 3)`

**Step 4:** Validate each candidate against actual row lengths:
- `(1, 2)`: Valid if row 1 has at least 3 cells
- `(1, 3)`: Valid if row 1 has at least 4 cells
- `(2, 2)`: Valid (same row, column 2 < 5)
- `(2, 4)`: Valid (same row, column 4 < 5)
- `(3, 2)`: Valid if row 3 exists and has at least 3 cells
- `(3, 3)`: Valid if row 3 exists and has at least 4 cells

**Step 5:** Return only those candidates that passed validation.

This example shows how the algorithm naturally handles boundaries and ragged edges by checking actual row lengths.

---

## 5. JSON Export Format

### 5.1 Overall Structure

The creator exports puzzles to a JSON format with four main sections:

```json
{
  "id": "puzzle_name",
  "max_value": 36,
  "vertices": { ... },
  "adjacency": { ... },
  "constraints": { ... },
  "layout": { ... }
}
```

Each section serves a specific purpose in defining the puzzle completely.

### 5.2 Vertices Section

The vertices section defines all playable cells in the puzzle. Each vertex has:

- **Key:** String coordinate like `"3,5"`
- **Value:** Object with optional `value` field

**Example:**
```json
"vertices": {
  "0,2": { "value": 27 },      // Prefilled with 27
  "0,3": { "value": null },    // Empty cell
  "1,2": { "value": 23 },      // Prefilled with 23
  "1,3": { "value": null }     // Empty cell
}
```

Cells with `value: null` are empty and need to be filled by the solver. Cells with numeric values are prefilled and immutable.

### 5.3 Adjacency Section

The adjacency section explicitly lists all neighbor relationships. This is the critical topology definition.

**Format:** Each vertex ID maps to an array of its neighbor vertex IDs.

**Example:**
```json
"adjacency": {
  "0,2": ["0,3", "1,2", "1,3"],
  "0,3": ["0,2", "0,4", "1,3", "1,4"],
  "1,2": ["0,2", "1,3", "2,1", "2,2"],
  "1,3": ["0,2", "0,3", "1,2", "1,4", "2,2", "2,3"]
}
```

**Important Properties:**

**Symmetry:** If vertex A lists B as a neighbor, then B must list A as a neighbor. This is enforced during export.

**Consistency:** Every vertex listed in adjacency must exist in the vertices section.

**Completeness:** All valid neighbors (as computed by the algorithm) are included for each vertex.

By storing adjacency explicitly, the JSON format becomes independent of coordinate calculations. A solver can work with the graph purely through adjacency lists without knowing anything about hexagonal coordinates.

### 5.4 Constraints Section

The constraints section defines dot constraints (mandatory adjacencies). In standard Rikudo puzzles, a dot between two cells means those cells must contain consecutive numbers.

**Format:**
```json
"constraints": {
  "dots": [
    ["0,4", "1,5"],
    ["2,2", "3,3"],
    ["2,6", "2,7"]
  ]
}
```

Each dot constraint is an array of two vertex IDs. These IDs must:
- Exist in the vertices section
- Be adjacent according to the adjacency section
- Be playable cells (not holes or blocked cells)

### 5.5 Layout Section

The layout section provides information for rendering the puzzle. This is separate from the topology definition and used only for visualization.

**Format:**
```json
"layout": {
  "rows": 7,
  "cols": 7,
  "coordinates": {
    "0,1": [0, 1],
    "0,2": [0, 2],
    "1,1": [1, 1]
  },
  "center_rc": [3, 3]
}
```

**Fields:**

**rows/cols:** Bounding box dimensions (may be larger than actual puzzle).

**coordinates:** Mapping of vertex IDs to their `[row, col]` positions for rendering. This preserves the original coordinate assignments.

**center_rc:** Optional center cell location (if the puzzle has a designated center).

The layout section allows renderers to position hexagons correctly even when working with the abstract graph topology.

---

## 6. JSON Export Process

### 6.1 Export Workflow

The creator's JSON export process follows these steps:

**Step 1: Collect Vertex Data**
- Iterate through all cells in the grid
- For each cell that exists and is not a hole, create a vertex entry
- Set `value` to the cell's number if prefilled, or `null` if empty
- Build the vertices dictionary with string coordinate keys

**Step 2: Build Adjacency Lists**
- For each vertex, compute its neighbors using `get_hex_neighbors_evenr()`
- Filter neighbors to only include cells that exist as vertices
- Create adjacency list mapping each vertex ID to its neighbor IDs
- Ensure symmetry: if A→B then B→A

**Step 3: Export Constraints**
- Iterate through dot constraints stored in the grid
- Convert each constraint from coordinate tuples to vertex ID strings
- Validate that both endpoints are playable cells
- Add to constraints.dots array

**Step 4: Create Layout Information**
- Record grid dimensions (bounding box)
- Create coordinates mapping for all vertices
- Note center cell location if present
- Include in layout section

**Step 5: Assemble JSON**
- Combine all sections into final JSON object
- Add puzzle metadata (id, max_value)
- Serialize to formatted JSON string

### 6.2 Key Export Functions

The creator implements JSON export through several key functions:

**`export_to_json()` in HexGrid:**
- Main export function that orchestrates the process
- Calls helper functions to build each JSON section
- Returns complete JSON-serializable dictionary

**`get_neighbors()` in HexGrid:**
- Wrapper around `get_hex_neighbors_evenr()`
- Returns neighbors for a specific cell
- Used during adjacency list construction

**`coordinate_to_string()` in utils:**
- Converts `(row, col)` tuples to `"row,col"` strings
- Ensures consistent vertex ID format throughout JSON

---

## 7. Why This Works for Standard Puzzles

### 7.1 Comparison with Legacy System

The legacy solver uses a different coordinate convention. It determines neighbor deltas based on whether a row is "full" or "short" relative to the maximum column count, rather than using row parity. Specifically:

**Legacy Convention:** 
- If `len(row) == column_count`, use EVEN deltas
- If `len(row) < column_count`, use ODD deltas

**Creator Convention:**
- If `row % 2 == 0`, use EVEN deltas
- If `row % 2 == 1`, use ODD deltas

For standard Rikudo puzzles with regular hexagonal clustering, these two conventions produce identical neighbor relationships. This is why puzzle19 (and most existing puzzles) work correctly even though they use different internal logic.

### 7.2 When They Differ

The conventions diverge for irregular patterns. Consider puzzle17:

**Pattern:** EVEN rows have 6 cells, ODD rows have 7 cells

**Legacy interpretation:**
- Row 0: 6 cells, max=7, so 6 < 7 → SHORT → Use ODD deltas
- Row 1: 7 cells, max=7, so 7 == 7 → FULL → Use EVEN deltas

**Creator interpretation:**
- Row 0: 0 % 2 == 0 → EVEN → Use EVEN deltas
- Row 1: 1 % 2 == 1 → ODD → Use ODD deltas

The result is that the two systems compute different neighbor relationships for puzzle17. However, the creator's output is correct for standard EVEN-R hexagonal grids.

### 7.3 Resolution Strategy

The key insight is that the creator generates **explicit adjacency lists** in the JSON. This means the solver doesn't need to recompute neighbors from coordinates at all. The topology is fully specified by the adjacency section.

By working with the explicit graph structure, the solver becomes agnostic to coordinate conventions. Whether the JSON was generated using legacy conventions, creator conventions, or any other system, the solver only cares about the adjacency relationships provided in the JSON.

This is the fundamental advantage of the JSON format: it decouples the topology (the graph structure) from the coordinate system (the representation).

---

## 8. Implementation Reference

### 8.1 Core Neighbor Calculation Code

Here is the complete implementation of the EVEN-R neighbor calculation from `utils/hex_parity.py`:

```python
# Deltas for EVEN rows (row % 2 == 0)
_EVEN_DELTAS = (
    (-1, -1),  # up-left
    (-1,  0),  # up-right
    ( 0, -1),  # left
    ( 0,  1),  # right
    ( 1, -1),  # down-left
    ( 1,  0),  # down-right
)

# Deltas for ODD rows (row % 2 == 1)
_ODD_DELTAS = (
    (-1,  0),  # up-left
    (-1,  1),  # up-right
    ( 0, -1),  # left
    ( 0,  1),  # right
    ( 1,  0),  # down-left
    ( 1,  1),  # down-right
)

def get_hex_neighbors_evenr(
    row_lengths: Sequence[int],
    r: int,
    c: int,
) -> List[Tuple[int, int]]:
    """
    Return valid neighbor coordinates for (r, c) using EVEN-R parity.
    
    Args:
        row_lengths: Length of each row (supports ragged grids)
        r: Row index (0-based)
        c: Column index (0-based)
        
    Returns:
        List of valid neighbor coordinates
    """
    # Validate input coordinates
    if not (0 <= r < len(row_lengths) and 0 <= c < row_lengths[r]):
        return []
    
    # Select delta pattern based on row parity
    deltas = _EVEN_DELTAS if (r % 2 == 0) else _ODD_DELTAS
    
    # Generate and validate neighbors
    neighbors = []
    for dr, dc in deltas:
        nr, nc = r + dr, c + dc
        
        # Check if neighbor is within grid bounds
        if 0 <= nr < len(row_lengths) and 0 <= nc < row_lengths[nr]:
            neighbors.append((nr, nc))
    
    return neighbors
```

### 8.2 Usage Example

Here is how the neighbor calculation is used during JSON export:

```python
# In HexGrid.export_to_json()
def build_adjacency(self):
    """Build adjacency lists for all vertices."""
    adjacency = {}
    
    for vertex_id in self.get_all_vertices():
        # Parse vertex ID to get coordinates
        row, col = string_to_coordinate(vertex_id)
        
        # Get neighbors using EVEN-R calculation
        row_lengths = self.get_row_lengths()
        neighbor_coords = get_hex_neighbors_evenr(row_lengths, row, col)
        
        # Convert neighbor coordinates to vertex IDs
        neighbor_ids = []
        for nr, nc in neighbor_coords:
            neighbor_id = coordinate_to_string(nr, nc)
            # Only include if neighbor actually exists as a vertex
            if self.cell_exists(nr, nc):
                neighbor_ids.append(neighbor_id)
        
        adjacency[vertex_id] = neighbor_ids
    
    return adjacency
```

### 8.3 Coordinate Conversion Utilities

The creator provides simple utilities for coordinate format conversion:

```python
def coordinate_to_string(row: int, col: int) -> str:
    """Convert coordinate tuple to vertex ID string."""
    return f"{row},{col}"

def string_to_coordinate(coord_str: str) -> Tuple[int, int]:
    """Convert vertex ID string back to coordinates."""
    row, col = coord_str.split(',')
    return int(row), int(col)
```

These utilities are used throughout the codebase to maintain consistency in vertex ID format.

---

## 9. Key Takeaways

### 9.1 For Solver Developers

When building a solver to work with creator-generated JSON:

**Use Adjacency Lists Directly:** Don't recompute neighbors from coordinates. Trust the adjacency section as the definitive topology.

**Treat Coordinates as Labels:** The coordinate strings are just vertex identifiers. The actual spatial relationships are defined by adjacency.

**Validate JSON Structure:** Ensure symmetry in adjacency (if A→B then B→A), consistency between sections (all referenced vertices exist), and valid constraint endpoints.

**Ignore Coordinate System Details:** The solver should work with any valid graph structure regardless of how coordinates were originally assigned.

### 9.2 For Puzzle Creators

When using the creator GUI:

**Trust the Export:** The JSON export produces correct topology using standard EVEN-R conventions.

**Holes Work Naturally:** You can create holes by making cells non-playable. They'll be excluded from the vertex set automatically.

**Constraints are Validated:** The creator validates dot constraints to ensure they connect adjacent playable cells.

**Layout Preserves Intent:** The layout section stores your original coordinate assignments for rendering purposes.

### 9.3 For Future Development

This specification enables several future enhancements:

**Arbitrary Shapes:** The sparse grid and explicit adjacency support any puzzle shape, not just regular hexagons.

**Alternative Topologies:** The same JSON format could represent square grids, triangular grids, or irregular graphs by changing adjacency relationships.

**Coordinate-Free Solving:** A solver that works purely with the graph structure is more general and easier to test.

**Format Stability:** By documenting the format precisely, we ensure consistent behavior across tools and versions.

---

## 10. Conclusion

The Rikudo Puzzle Creator uses a well-designed architecture that separates topology (the graph structure) from coordinates (the representation). The key features are:

- **Standard EVEN-R coordinates** throughout, with row parity determining neighbor offsets
- **Sparse grid representation** allowing holes and arbitrary shapes
- **Explicit adjacency lists** in exported JSON, making topology independent of coordinates
- **Clean separation** between puzzle structure (vertices, adjacency, constraints) and rendering hints (layout)

This design provides a solid foundation for building a topology-agnostic solver. By working with the explicit graph representation in the JSON, the solver can handle any valid puzzle structure regardless of shape or coordinate system.

The next phase of development will focus on understanding the legacy solver pipeline and ensuring the new graph-based solver can replicate its 98% success rate while working with this JSON format.

---

## Appendix A: Quick Reference

**Coordinate Format:** `"row,col"` string, e.g. `"3,5"`

**EVEN Row Deltas:** `[(-1,-1), (-1,0), (0,-1), (0,1), (1,-1), (1,0)]`

**ODD Row Deltas:** `[(-1,0), (-1,1), (0,-1), (0,1), (1,0), (1,1)]`

**Parity Test:** `is_even = (row % 2 == 0)`

**JSON Sections:** id, max_value, vertices, adjacency, constraints, layout

**Validation Rules:**
- Adjacency must be symmetric
- All vertex IDs in adjacency must exist in vertices
- Dot constraint endpoints must be adjacent and playable
- Coordinates in layout must match vertex IDs

---

**End of Specification**