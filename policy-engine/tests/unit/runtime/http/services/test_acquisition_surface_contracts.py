from __future__ import annotations

import copy
import json
from pathlib import Path

from polisyos.runtime.http.services.acquisition_surface_contracts import GapClass
from polisyos.runtime.http.services.acquisition_surface_projection import (
    build_acquisition_growth_projection,
)

_POLICY_ENGINE = Path(__file__).resolve().parents[5]
_PDC = _POLICY_ENGINE / "architecture/policy_design_case"


def _source(filename: str) -> dict[str, object]:
    parsed = json.loads((_PDC / filename).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _sources() -> dict[str, dict[str, object]]:
    return {
        "census": _source("layer3_gy_n13a_acquisition_census.json"),
        "journal": _source("layer3_gy_n13a_live_probe_journal.json"),
        "carrier_liveness": _source(
            "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
        ),
        "executor_contract": _source("layer3_gy_n13b_acquisition_executor_contract.json"),
        "lifecycle_manifest": _source("layer3_gy_n13b_lifecycle_manifest.json"),
        "reentry_trace": _source("layer3_gy_n13b_reentry_trace.json"),
    }


def test_available_source_claim_does_not_promote_a_stale_binding_gap_to_data_gap() -> None:
    sources = _sources()
    contradictory = copy.deepcopy(sources)
    trace = contradictory["reentry_trace"]
    requirement = trace["requirement_gap"]
    availability = requirement["metadata"]["availability"]
    availability.update(
        {
            "status": "available",
            "dataset_count": 1,
            "metric_binding_count": 1,
            "observation_count": 1,
        }
    )

    projection = build_acquisition_growth_projection(**contradictory)
    backlog = {row.variable_id: row for row in projection.backlog}

    assert backlog["government.balance"].gap_class is GapClass.NOT_ESTABLISHED
    assert backlog["government.balance"].classification_basis == "not_established"
