"""Response metadata helpers."""

from __future__ import annotations

from typing import Any, Dict


def with_simulated(payload: Dict[str, Any], *, basis: str = "mock_data") -> Dict[str, Any]:
    """Mark demo/simulated analytics responses."""
    return {**payload, "simulated": True, "data_basis": basis}
