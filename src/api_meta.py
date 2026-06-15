"""Response metadata helpers."""

from __future__ import annotations

from typing import Any, Dict


def with_simulated(payload: Dict[str, Any], *, basis: str = "mock_data") -> Dict[str, Any]:
    """Mark demo/simulated analytics responses."""
    return {**payload, "simulated": True, "data_basis": basis}


def with_data_meta(
    payload: Dict[str, Any],
    *,
    simulated: bool,
    basis: str,
    basis_label: str = "",
) -> Dict[str, Any]:
    return {
        **payload,
        "simulated": simulated,
        "data_basis": basis,
        "data_basis_label": basis_label or basis,
    }
