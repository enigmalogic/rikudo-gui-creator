"""
Connectivity validation respects loaded adjacency:
- Initially connected (for current puzzles)
- After isolating one vertex (remove both directions), validator flags disconnect
"""

import json
import pytest

from conftest import load_puzzle

def test_connectivity_respects_loaded_graph(load_puzzle):
    g = load_puzzle("puzzles_json/puzzle17.json")
    ok, msg = g.validate_connectivity()
    assert ok is True, f"Expected connected graph; got: {msg or ''}"

    # Build a fresh normalized JSON to get coordinates mapping
    norm = g.to_json("tmp")
    coords = {k: tuple(v) for k, v in norm["layout"]["coordinates"].items()}
    first_vid = next(iter(norm["adjacency"]))
    iso_rc = coords[first_vid]

    # Remove all neighbors of first_vid and the back-edges too
    assert g.loaded_adjacency is not None, "Expected loaded_adjacency to exist for this puzzle"
    to_remove = list(g.loaded_adjacency.get(iso_rc, []))
    g.loaded_adjacency[iso_rc] = set()
    for nbr in to_remove:
        g.loaded_adjacency[nbr].discard(iso_rc)

    ok2, msg2 = g.validate_connectivity()
    assert ok2 is False, "Graph should be disconnected after isolating a vertex"
    assert "disconnected" in (msg2 or "").lower()