from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.runtime.http.services.acquisition_surface_contracts import (
    EpochQualificationDisclosure,
    GapClass,
)
from polisyos.runtime.http.services.acquisition_surface_projection import (
    build_acquisition_growth_projection,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
PDC_ROOT = REPO_ROOT / "architecture/policy_design_case"


def _json(name: str) -> dict[str, object]:
    value = json.loads((PDC_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sources() -> dict[str, dict[str, object]]:
    return {
        "census": _json("layer3_gy_n13a_acquisition_census.json"),
        "journal": _json("layer3_gy_n13a_live_probe_journal.json"),
        "carrier_liveness": _json(
            "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
        ),
        "executor_contract": _json("layer3_gy_n13b_acquisition_executor_contract.json"),
        "lifecycle_manifest": _json("layer3_gy_n13b_lifecycle_manifest.json"),
        "reentry_trace": _json("layer3_gy_n13b_reentry_trace.json"),
    }


def test_acquisition_growth_preserves_structural_and_data_denominators() -> None:
    """DS15-STRUCTURAL-NOT-DATA and DS15-BINDING-NOT-DATA."""

    sources = _sources()
    structural = sources["census"]["route_evidence"]
    assert isinstance(structural, list)
    structural[0]["row_addressable_supply"] = {
        "catalog_rows": 99,
        "fetchable": True,
        "cost": 1.0,
        "gap_class": "data_gap",
    }
    payload = build_acquisition_growth_projection(**sources)

    assert len(payload.structural_routes) == 3
    assert all(route.gap_class is GapClass.STRUCTURAL_GAP for route in payload.structural_routes)
    assert all(route.action_eligibility == "not_applicable" for route in payload.structural_routes)
    assert len(payload.backlog) == 15
    by_variable = {row.variable_id: row for row in payload.backlog}
    assert by_variable["government.balance"].gap_class is GapClass.DATA_GAP
    assert by_variable["government.balance"].classification_basis == ("independently_reconciled")
    assert by_variable["avg_hh_income_uah"].gap_class is GapClass.NOT_ESTABLISHED

    without_owner_evidence = copy.deepcopy(sources)
    without_owner_evidence["reentry_trace"].pop("requirement_gap")
    changed = build_acquisition_growth_projection(**without_owner_evidence)
    changed_by_variable = {row.variable_id: row for row in changed.backlog}
    assert changed_by_variable["government.balance"].gap_class is GapClass.NOT_ESTABLISHED


def test_acquisition_growth_discloses_zero_ranking_basis_and_voi_owner() -> None:
    """DS15-RANKING-NOT-VOI and DS15-ZERO-SCORE-DISCLOSURE."""

    payload = build_acquisition_growth_projection(**_sources())

    assert payload.summary.family_scorecard_count == 12
    assert payload.summary.actual_network_call_count == 18
    assert payload.summary.selected_record_count == 144
    assert payload.summary.metric_resolution_count == 124
    assert payload.summary.backlog_count == 15
    assert payload.summary.structural_route_count == 3
    assert all(row.binding_confidence == 0.0 for row in payload.backlog)
    assert all(row.ranking_score == 0.0 for row in payload.backlog)
    assert sum(row.route_demand == 2.0 for row in payload.backlog) == 3
    assert sum(row.route_demand == 1.0 for row in payload.backlog) == 12
    assert {row.ranking_method for row in payload.backlog} == {
        "interim_binding_confidence_x_route_demand"
    }
    assert {row.authority_boundary for row in payload.backlog} == {"ranking_only_not_voi"}
    assert {row.voi_owner_fit for row in payload.backlog} == {
        "metric_residual_granularity_not_supported"
    }
    assert {row.voi_owner_integration for row in payload.backlog} == {"routed_to_gy_n13b"}
    assert {row.voi_owner_ref for row in payload.backlog} == {
        "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition"
    }


def test_acquisition_growth_keeps_qualification_and_n13b_history_negative() -> None:
    """DS15-QUALIFICATION-DISCLOSURE and DS15-N13B-NEGATIVE-HONESTY."""

    payload = build_acquisition_growth_projection(**_sources())
    history = payload.n13b_history
    qualification = history.epoch_qualification

    assert history.attempt_count == 5
    assert history.raw_response_count == 2
    assert history.response_admitted_count == 0
    assert history.overlay_epoch_count == 0
    assert history.execution_phase == "terminal"
    assert history.admission == "not_reached"
    assert history.world_growth == "no_growth"
    assert history.reentry == "deeper_terminal"
    assert qualification.epoch_state == "pending_epoch_activation"
    assert qualification.status == "not_established"
    assert qualification.code == "policy_admission_missing"
    assert qualification.authority_owner_ref is None
    assert qualification.appointment_state == "unappointed"

    upgraded = qualification.model_dump(mode="json")
    upgraded.update({"epoch_state": "active", "status": "qualified"})
    with pytest.raises(ValidationError):
        EpochQualificationDisclosure.model_validate(upgraded)
