from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services import governed_projections

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_PATH = (
    REPO_ROOT / "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
)
ROUTE_REFERENCE_FIELDS = frozenset(
    {
        "owner_content_hash",
        "owner_schema",
        "planner_report_content_hash",
        "requirement_gap_id",
    }
)


def _source() -> dict[str, Any]:
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def _acquisition_route_references(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "acquisition_route" and isinstance(child, dict):
                yield child
            yield from _acquisition_route_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _acquisition_route_references(child)


def test_route_reference_contract_admits_every_committed_owner_instance() -> None:
    route_model = governed_projections.DepthNAcquisitionRouteReference
    references = tuple(_acquisition_route_references(_source()))

    assert len(references) == 8
    assert {frozenset(reference) for reference in references} == {ROUTE_REFERENCE_FIELDS}
    assert len([route_model.model_validate(reference) for reference in references]) == len(
        references
    )

    for field in ROUTE_REFERENCE_FIELDS:
        missing = dict(references[0])
        del missing[field]
        with pytest.raises(ValidationError):
            route_model.model_validate(missing)
    with pytest.raises(ValidationError):
        route_model.model_validate({**references[0], "owner": "invented"})


def test_depth_n_projection_separates_route_reference_from_resolved_economics() -> None:
    source = _source()
    projected = governed_projections._project_depth_n(source)
    projected_payload = governed_projections.DepthNCycleBoardPayload.model_validate(projected)

    for role, run in source["domain_runs"].items():
        projected_run = projected_payload.domain_runs[role]
        route_reference = run["evidence_witness"].get("acquisition_route")
        planner_report = run["terminal"]["costed_plan"]["canonical_planner_report"]
        planner_hash = run["stage_trace"]["acquisition"]["planner_report_content_hash"]
        acquisition_record = planner_report["acquisition_records"][0]
        strategy = next(
            item
            for item in acquisition_record["strategy_records"]
            if item["strategy"] == acquisition_record["recommended_strategy"]
        )
        expected_economics = governed_projections.DepthNAcquisitionEconomicsProjection(
            planner_report_content_hash=planner_hash,
            planner_status=planner_report["status"],
            missing_requirement_fields=tuple(acquisition_record["missing_requirement_fields"]),
            recommended_strategy=acquisition_record["recommended_strategy"],
            expected_cost=strategy["voi_expected_cost"],
            expected_voi=strategy["voi_expected_value"],
            voi_rank=strategy["voi_rank"],
            decision_owner_ref=acquisition_record["decision_owner_ref"],
            producer_expected=acquisition_record["producer_expected"],
            next_action=acquisition_record["next_actions"][0]["action"],
        )

        if route_reference is None:
            assert projected_run.acquisition_route is None
        else:
            assert projected_run.acquisition_route == (
                governed_projections.DepthNAcquisitionRouteReference.model_validate(route_reference)
            )
        assert projected_run.acquisition_economics == expected_economics
        assert gy_content_hash(planner_report) == planner_hash

    assert projected_payload.domain_runs["education"].acquisition_route is None


@pytest.mark.parametrize(
    "mutation",
    ["missing_report", "mismatched_hash", "mismatched_requirement_gap"],
)
def test_unresolved_planner_report_preserves_route_and_types_economics_absent(
    mutation: str,
) -> None:
    source = _source()
    run = source["domain_runs"]["first_vertical"]
    if mutation == "missing_report":
        del run["terminal"]["costed_plan"]["canonical_planner_report"]
    elif mutation == "mismatched_hash":
        run["stage_trace"]["acquisition"]["planner_report_content_hash"] = "sha256:" + "0" * 64
    else:
        run["evidence_witness"]["acquisition_route"]["requirement_gap_id"] = (
            "requirement-gap:different-owner-gap"
        )
    expected_route = deepcopy(run["evidence_witness"]["acquisition_route"])

    projected = governed_projections._project_depth_n(source)
    projected_run = projected["domain_runs"]["first_vertical"]

    assert projected_run["acquisition_route"] == expected_route
    assert projected_run["acquisition_economics"] is None
