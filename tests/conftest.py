import os
import sys
import pytest

# Add project root to sys.path (so tests can import core.*)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from core.hex_grid import HexGrid


@pytest.fixture
def load_puzzle():
    """Returns a function that loads and returns a HexGrid instance from JSON."""
    import json
    def _load(path):
        with open(path, "r") as f:
            data = json.load(f)
        return HexGrid.from_json(data)
    return _load
