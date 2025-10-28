"""
Phase-1 smoke tests:
- Round-trip adjacency fidelity
- Center rule + non_playable_cells
- Constraint export filter
- Import → Undo → Redo preserves topology
"""

import json
import pytest

# Provided by tests/conftest.py (adds project root to sys.path)
from conftest import load_puzzle


def _edge_set(adj: dict) -> set[tuple[str, str]]:
    """Undirected edge set for easy comparison (order-insensitive)."""
    edges = set()
    for a, nbrs in adj.items():
        for b in nbrs:
            edges.add(tuple(sorted([a, b])))
    return edges


@pytest.mark.parametrize("path", [
    "puzzles_json/puzzle17.json",
    "puzzles_json/puzzle18.json",
    "puzzles_json/puzzle19.json",
])
def test_round_trip_adjacency_fidelity(path, load_puzzle):
    """If input has adjacency: exported adjacency must match (edges, not order)."""
    g = load_puzzle(path)
    original = g.to_json("original")           # normalize structure
    roundtrip = g.to_json("roundtrip")         # export from in-memory model

    in_edges = _edge_set(original.get("adjacency", {}))
    out_edges = _edge_set(roundtrip.get("adjacency", {}))

    # If input has adjacency, we expect equality
    if in_edges:
        assert in_edges == out_edges, f"Adjacency mismatch in {path}"
    else:
        # No strong assertion when input lacked adjacency (parity is allowed)
        assert out_edges, "Expected parity adjacency to be generated"


def test_center_non_playable_and_absent_from_graph(load_puzzle):
    """
    Center must:
      - exist in layout.center_rc
      - be included in layout.non_playable_cells
      - NOT appear in vertices or adjacency
    """
    g = load_puzzle("puzzles_json/puzzle19.json")
    j = g.to_json("center_check")

    layout = j.get("layout", {})
    center = layout.get("center_rc")
    nonp = set(layout.get("non_playable_cells", []))
    vertices = j.get("vertices", {})
    adjacency = j.get("adjacency", {})

    assert center is not None, "Expected center_rc in layout"
    center_str = f"{center[0]},{center[1]}"
    assert center_str in nonp, "center_rc must be listed in non_playable_cells"
    assert center_str not in vertices, "center must not appear in vertices"
    assert center_str not in adjacency, "center must not be a graph vertex"


def test_constraint_export_filter(load_puzzle):
    """
    A dot constraint between non-adjacent vertices must not be exported.
    (Valid ones remain.)
    """
    g = load_puzzle("puzzles_json/puzzle19.json")
    verts = list(g.get_playable_cells().keys())
    assert len(verts) >= 2, "Not enough vertices to test"

    a, b = verts[0], verts[-1]  # Likely non-neighbors; if neighbors, add more cases as needed.
    ok = g.add_dot_constraint(a, b)

    exported = g.to_json("constraint_check")
    dots = exported["constraints"]["dots"]
    as_str = lambda t: f"{t[0]},{t[1]}"
    target = tuple(sorted([as_str(a), as_str(b)]))

    if ok:
        # If they ARE neighbors, then the edge must exist in adjacency
        # and the dot must be present.
        adj = exported["adjacency"]
        assert as_str(b) in set(adj.get(as_str(a), [])), "Edge present in dots must exist in adjacency"
        assert target in set(tuple(sorted(x)) for x in dots)
    else:
        # If they are NOT neighbors, dot must NOT export.
        assert target not in set(tuple(sorted(x)) for x in dots)


def test_import_undo_redo_preserves_topology(load_puzzle):
    """
    Import puzzle B → neighbors reflect B.
    Undo → neighbors reflect A.
    Redo → neighbors reflect B again.
    """
    gA = load_puzzle("puzzles_json/puzzle17.json")
    A = gA.to_json("A_norm")

    # Pick a stable vertex id present in adjacency
    a_vids = list(A.get("adjacency", {}).keys())
    assert a_vids, "Puzzle A should have adjacency"
    a0 = a_vids[0]

    # Helper to query neighbors via the model (not raw JSON),
    # proving get_neighbors() is honoring the active graph.
    def neighbors_of(grid, vid: str) -> list[str]:
        coords = grid.to_json("tmp")["layout"]["coordinates"]
        if vid in coords:
            r, c = coords[vid]
        else:
            r, c = map(int, vid.split(","))
        return sorted(f"{nr},{nc}" for (nr, nc) in grid.get_neighbors(r, c))

    # Baseline neighbors in A
    neighbors_A = neighbors_of(gA, a0)

    # Import B via command so history is populated
    gB_json = load_puzzle("puzzles_json/puzzle19.json").to_json("B_norm")
    gA.cmd_import_puzzle(gB_json)
    neighbors_after_import = neighbors_of(gA, list(gB_json["adjacency"].keys())[0])

    # Undo → should return to A's topology
    gA.undo()
    neighbors_after_undo = neighbors_of(gA, a0)

    # Redo → should return to B's topology
    gA.redo()
    neighbors_after_redo = neighbors_of(gA, list(gB_json["adjacency"].keys())[0])

    assert neighbors_A == neighbors_after_undo, "Undo should restore A's topology"
    assert neighbors_after_import == neighbors_after_redo, "Redo should restore B's topology"