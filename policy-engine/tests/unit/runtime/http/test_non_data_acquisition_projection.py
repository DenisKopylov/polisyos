"""Exercise the operator/CAS/DS15 refusal chain with a bounded legacy carrier.

The existing N13a/N13b files are copied without deriving their unrelated owner
history. Only that legacy registration derivation and the outer subprocess
receipt are carried here. CLI planning, receipt persistence/admission, HTTP source
loading, and the worker's exact input/payload recomputation remain real.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from polisyos.fabric.evidence.non_data_acquisition import NonDataRequest
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services import (
    governed_projection_validation_worker as worker,
)
from polisyos.runtime.http.services import governed_projections as governed
from polisyos.runtime.quality import non_data_acquisition as bridge
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionGap,
    AcquisitionGapType,
    AuthorityLevel,
    MandatoryGateState,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
PDC = "architecture/policy_design_case"
CENSUS_PATH = f"{PDC}/layer3_gy_n13a_acquisition_census.json"
LIFECYCLE_PATH = f"{PDC}/layer3_gy_n13b_lifecycle_manifest.json"
BUNDLE_PATH = f"{PDC}/gy_aq1_non_data_projection/receipt-bundle.json"
N13A_PATHS = (
    CENSUS_PATH,
    f"{PDC}/layer3_gy_n13a_live_probe_journal.json",
    f"{PDC}/layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json",
)

LEGAL_DEMAND = {
    "act": {
        "jurisdiction": "UA",
        "office": "office:projection-test",
        "action": "act:projection-test",
        "delegation_chain": [None],
    }
}
MUTATION_DEMAND = {
    "mutation": {
        "system": "system:projection-test",
        "object": "object:projection-test",
        "field": "field:projection-test",
        "operation": "correct",
        "purpose": "purpose:projection-test",
    }
}


def _load_json(root: Path, relative_path: str) -> dict[str, Any]:
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def _write_json(root: Path, relative_path: str, value: dict[str, Any]) -> Path:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return target


@pytest.fixture
def governed_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Carry legacy registrations while running the real added source chain."""
    lifecycle = _load_json(REPO_ROOT, LIFECYCLE_PATH)
    paths = {
        *N13A_PATHS,
        LIFECYCLE_PATH,
        "architecture/generated_artifacts.toml",
        *(row["path"] for row in lifecycle["registrations"]),
    }
    for relative_path in paths:
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative_path, target)

    from tools.quality.validation import layer3_gy_n13b_acquisition_contract

    monkeypatch.setattr(
        layer3_gy_n13b_acquisition_contract,
        "derive_lifecycle_manifest",
        lambda _root: SimpleNamespace(
            registrations=tuple(SimpleNamespace(**row) for row in lifecycle["registrations"])
        ),
    )

    def validate_projection(
        *,
        repository_root: Path,
        definition: Any,
        loaded: Any,
        payload: BaseModel,
    ) -> Any:
        payload_data = payload.model_dump(mode="json")
        bindings = dict(loaded.component_bindings)
        issues = worker._validate_acquisition_growth_projection(
            repository_root, bindings=bindings, projection_payload=payload_data
        )
        dependency_bindings = {path: f"file:{identity}" for path, identity in bindings.items()}
        return governed.ProjectionSourceValidation(
            validator_id=definition.owner_validator_id,
            validator_version=definition.owner_validator_version,
            status="failed" if issues else "passed",
            bound_artifact_content_hash=loaded.content_hash,
            bound_dependency_aggregate_identity=governed.hash_export_projection(
                dependency_bindings
            ),
            bound_dependency_count=len(dependency_bindings),
            semantic_projection_hash=None if issues else gy_content_hash(payload_data),
            semantic_projection_hash_rule_version=(
                None if issues else "polisyos.pdc.gy_content_hash.v1"
            ),
            issue_codes=tuple(issues),
        )

    monkeypatch.setattr(governed, "_run_owner_validation", validate_projection)
    return tmp_path


def _publish(
    root: Path, demand: dict[str, Any], *, request_id: str = "projection-refusal"
) -> tuple[str, Any]:
    route = _load_json(root, CENSUS_PATH)["route_evidence"][0]["route"]
    request = NonDataRequest(
        request_id=request_id,
        claim_ref=route["candidate_ref"],
        gap_id=route["requirement_gap_id"],
        demand=copy.deepcopy(demand),
    )
    gap = AcquisitionGap(
        gap_id=request.gap_id,
        claim_ref=request.claim_ref,
        gap_type=AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY,
        authority_level=AuthorityLevel.GOVERNED,
        mandatory_gate_state=MandatoryGateState.NON_OVERRIDABLE,
    )
    request_path = _write_json(
        root, "operator-inputs/request.json", request.model_dump(mode="json")
    )
    gap_path = _write_json(root, "operator-inputs/gap.json", gap.model_dump(mode="json"))
    assert (
        bridge.main(
            [
                "--governed-root",
                str(root),
                "--request",
                str(request_path),
                "--gap",
                str(gap_path),
                "--route-id",
                route["route_id"],
                "--run-id",
                f"run:{request_id}",
                "--at",
                "2026-09-13T09:00:00+00:00",
            ]
        )
        == 0
    )
    source = bridge.load_non_data_projection_source(
        governed_root=root, census=_load_json(root, CENSUS_PATH)
    )
    return route["route_id"], source


def _get(service: Any) -> tuple[Any, dict[str, Any]]:
    packet = service.get(governed.ProjectionId.ACQUISITION_GROWTH)
    assert packet.availability == governed.ProjectionAvailability.AVAILABLE, packet
    return packet, json.loads(packet.model_dump_json())["payload"]


def _route(payload: dict[str, Any], route_id: str) -> dict[str, Any]:
    return next(row for row in payload["structural_routes"] if row["route_id"] == route_id)


@pytest.mark.parametrize(
    ("demand", "types", "state", "reasons"),
    [
        (LEGAL_DEMAND, {"legal_mandate"}, "admission_refused", ("non_data_object_missing",)),
        (
            {**LEGAL_DEMAND, **MUTATION_DEMAND},
            {"legal_mandate", "owner_writability"},
            "split_required",
            ("split_required",),
        ),
        ({"binding_gap": True}, set(), "shape_not_established", ("not_established",)),
    ],
    ids=("missing-object", "compound-demand", "unknown-shape"),
)
def test_cli_receipt_reaches_serialized_projection_without_authority(
    governed_root: Path,
    demand: dict[str, Any],
    types: set[str],
    state: str,
    reasons: tuple[str, ...],
) -> None:
    route_id, source = _publish(governed_root, demand)
    receipt = source.routes[0].receipt
    assert set(receipt.shape.acquisition_types) == types
    assert receipt.resolution_state == state
    assert receipt.reason_codes == reasons
    assert receipt.authority_granted is False
    assert receipt.institutional_signer is None

    service = governed.GovernedProjectionService(repository_root=governed_root)
    _, payload = _get(service)
    assert _route(payload, route_id) == {
        "route_id": route_id,
        "route_class": "candidate_non_data:"
        + (",".join(receipt.shape.acquisition_types) or "not_established"),
        "witness_kind": state,
        "missing_link": "; ".join(reasons),
        "gap_class": "not_established",
        "action_eligibility": "blocked",
    }


def test_bundle_arrival_replacement_and_row_growth_rebind_without_progress(
    governed_root: Path,
) -> None:
    service = governed.GovernedProjectionService(repository_root=governed_root)
    absent, historical_payload = _get(service)
    route_id, _ = _publish(governed_root, LEGAL_DEMAND)
    assert _route(historical_payload, route_id)["action_eligibility"] == "not_applicable"
    present, refusal_payload = _get(service)
    assert present.source.artifact_content_hash != absent.source.artifact_content_hash
    assert present.source_dependency_hash != absent.source_dependency_hash
    assert present.projection_hash != absent.projection_hash
    assert _route(refusal_payload, route_id)["action_eligibility"] == "blocked"

    _publish(governed_root, {"binding_gap": True}, request_id="replacement-unknown")
    replaced, unknown_payload = _get(service)
    assert replaced.source.artifact_content_hash != present.source.artifact_content_hash
    assert replaced.source_dependency_hash != present.source_dependency_hash
    assert replaced.projection_hash != present.projection_hash
    assert _route(unknown_payload, route_id)["witness_kind"] == "shape_not_established"

    census = _load_json(governed_root, CENSUS_PATH)
    census["route_evidence"][0]["declared_supply"]["local_observation_count"] += 1_000_000
    _write_json(governed_root, CENSUS_PATH, census)
    grown, grown_payload = _get(service)
    assert grown.source.artifact_content_hash != replaced.source.artifact_content_hash
    assert grown.source_dependency_hash != replaced.source_dependency_hash
    assert grown.projection_hash == replaced.projection_hash
    assert _route(grown_payload, route_id) == _route(unknown_payload, route_id)


@pytest.mark.parametrize("corruption", ["malformed-bundle", "different-route", "cas-bytes"])
def test_corrupt_or_rebound_receipts_fail_the_packet_closed(
    governed_root: Path, corruption: str
) -> None:
    _, source = _publish(governed_root, LEGAL_DEMAND)
    service = governed.GovernedProjectionService(repository_root=governed_root)
    before, _ = _get(service)
    if corruption == "malformed-bundle":
        (governed_root / BUNDLE_PATH).write_text("{broken", encoding="utf-8")
    elif corruption == "different-route":
        bundle = _load_json(governed_root, BUNDLE_PATH)
        other_route = _load_json(governed_root, CENSUS_PATH)["route_evidence"][1]["route"]
        bundle["entries"][0]["route_id"] = other_route["route_id"]
        _write_json(governed_root, BUNDLE_PATH, bundle)
    else:
        cas_dependency = next(path for path, _ in source.component_bindings if "/cas/" in path)
        (governed_root / cas_dependency).write_bytes(b'{"corrupted":true}')

    packet = service.get(governed.ProjectionId.ACQUISITION_GROWTH)
    assert packet.availability == governed.ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert packet.source.validation.status != "passed"
    assert packet.source.artifact_content_hash != before.source.artifact_content_hash


def test_real_worker_rejects_omitted_dependencies_and_changed_refusal(
    governed_root: Path,
) -> None:
    route_id, _ = _publish(governed_root, LEGAL_DEMAND)
    service = governed.GovernedProjectionService(repository_root=governed_root)
    _, payload = _get(service)
    loaded = service._load(governed._DEFINITION_BY_ID[governed.ProjectionId.ACQUISITION_GROWTH])
    bindings = dict(loaded.component_bindings)
    assert BUNDLE_PATH in bindings
    del bindings[BUNDLE_PATH]
    assert "acquisition_growth_component_denominator_mismatch" in (
        worker._validate_acquisition_growth_projection(
            governed_root, bindings=bindings, projection_payload=payload
        )
    )

    drifted = copy.deepcopy(payload)
    _route(drifted, route_id)["action_eligibility"] = "not_applicable"
    assert "acquisition_growth_projection_recompute_mismatch" in (
        worker._validate_acquisition_growth_projection(
            governed_root,
            bindings=dict(loaded.component_bindings),
            projection_payload=drifted,
        )
    )
