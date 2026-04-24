"""Public scientist publisher module API."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any


def publish_decision(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build a canonical decision packet payload from engine state."""
    run_id = str(state.get("run_id") or "unknown")
    return {
        "schema_version": "2.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "run_record": {
            "schema_version": "2.0",
            "run_id": run_id,
            "seed": int(state.get("params", {}).get("random_seed", 0) or 0),
            "engine": "scientist.engine",
        },
        "simulation_results": state.get("simulation_results"),
        "governance": state.get("feedback"),
        "notes": [],
    }
