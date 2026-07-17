from __future__ import annotations

import json
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = (
    REPO_ROOT / "src/polisyos/runtime/http/services/governed_projections.py"
)
MODULE_NAME = "polisyos.runtime.http.services.governed_projections"
MODULE_SPEC = spec_from_file_location(MODULE_NAME, MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = module_from_spec(MODULE_SPEC)
sys.modules[MODULE_NAME] = MODULE
MODULE_SPEC.loader.exec_module(MODULE)

CHANNEL_REGISTRY = MODULE.CHANNEL_REGISTRY
AudienceClass = MODULE.AudienceClass
GovernedProjectionService = MODULE.GovernedProjectionService
ProjectionAvailability = MODULE.ProjectionAvailability
ProjectionId = MODULE.ProjectionId
ReplayPinMismatchError = MODULE.ReplayPinMismatchError


def _write_json(root: Path, relative_path: str, payload: dict[str, Any]) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _minimal_capstone(*, terminal_label: str = "acquisition_required") -> dict[str, Any]:
    run = {
        "content_hash": "sha256:run",
        "design_problem_ref": "design://example",
        "domain_role": "unseen",
        "evidence_witness": {
            "kind": "owner_recorded_evidence_class",
            "schema_version": "evidence.v1",
        },
        "generation_cycle_run_id": "run-1",
        "stage_trace": {
            "acquisition": {
                "owner": "owner.planner",
                "planner_report_content_hash": "sha256:planner",
                "route_kind": "owner_route",
            }
        },
        "terminal": {
            "blocking_obligations": ["owner_recorded_weakest_link"],
            "costed_plan": {"canonical_planner_report": {"status": "pass"}},
            "kind": terminal_label,
        },
        "terminal_distribution": {terminal_label: 1},
    }
    return {
        "contract_content_hash": "sha256:declared",
        "depth_evidence": {"observed_max_depth": 3},
        "domain_runs": {"unseen": run},
        "producer": {"provenance_note": "first"},
        "rule_version": "rule.v1",
        "schema_version": "capstone.v1",
        "terminal_distributions": {"unseen": {terminal_label: 1}},
    }


def _write_minimal_capstone(root: Path, payload: dict[str, Any] | None = None) -> Path:
    return _write_json(
        root,
        "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json",
        payload or _minimal_capstone(),
    )


def test_runtime_http_import_does_not_read_governed_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("governed artifacts must be lazy")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    service = GovernedProjectionService(REPO_ROOT)

    assert ProjectionId.DEPTH_N_CYCLE_BOARD in {
        entry.projection_id for entry in service.catalog()
    }


def test_projection_packets_require_identity_as_of_and_freshness(tmp_path: Path) -> None:
    _write_minimal_capstone(tmp_path)

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert packet.availability is ProjectionAvailability.AVAILABLE
    assert packet.source is not None
    assert packet.source.artifact_content_hash.startswith("sha256:")
    assert packet.projection_hash is not None
    assert packet.projection_hash.startswith("sha256:")
    assert packet.export_replay_contract == "policyos.runtime.export_replay_binding.v1"
    assert packet.as_of is not None
    assert packet.freshness.observed_at is not None
    assert packet.freshness.basis in {"source_timestamp", "filesystem_mtime"}
    assert packet.stable_address.endswith("/depth-n-cycle-board")
    assert "artifact_content_hash=" in (packet.replay_address or "")
    assert "projection_hash=" in (packet.replay_address or "")


def test_projection_cache_reuses_content_hash_key_until_source_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)
    original = Path.read_bytes
    reads = 0

    def count_reads(path: Path) -> bytes:
        nonlocal reads
        reads += 1
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", count_reads)
    first = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    second = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    assert reads == 1
    assert first.source == second.source

    changed = _minimal_capstone(terminal_label="novel_owner_terminal")
    source.write_text(json.dumps(changed, sort_keys=True), encoding="utf-8")
    current = source.stat()
    os.utime(source, ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000))

    third = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    assert reads == 2
    assert third.source != first.source
    assert third.projection_hash != first.projection_hash


def test_replay_pin_rejects_artifact_hash_mismatch(tmp_path: Path) -> None:
    _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)

    with pytest.raises(ReplayPinMismatchError, match="artifact_content_hash"):
        service.get(
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            artifact_content_hash="sha256:not-this-artifact",
        )


def test_replay_pin_rejects_projection_hash_mismatch(tmp_path: Path) -> None:
    _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)

    with pytest.raises(ReplayPinMismatchError, match="projection_hash"):
        service.get(
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            projection_hash="sha256:not-this-projection",
        )


def test_depth_n_projection_preserves_recorded_validator_outputs_without_rederiving(
    tmp_path: Path,
) -> None:
    source = _minimal_capstone()
    source["domain_runs"]["unseen"]["evidence_witness"]["kind"] = (
        "deliberately_unseen_owner_evidence_class"
    )
    source["domain_runs"]["unseen"]["terminal"]["blocking_obligations"] = [
        "deliberately_unseen_owner_weakest_link"
    ]
    _write_minimal_capstone(tmp_path, source)

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    run = packet.payload["domain_runs"]["unseen"]

    assert run["evidence_class"] == "deliberately_unseen_owner_evidence_class"
    assert run["weakest_links"] == ["deliberately_unseen_owner_weakest_link"]


def test_depth_n_projection_fails_closed_instead_of_deriving_missing_evidence(
    tmp_path: Path,
) -> None:
    source = _minimal_capstone()
    del source["domain_runs"]["unseen"]["evidence_witness"]
    _write_minimal_capstone(tmp_path, source)

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert "evidence_witness" in (packet.absence_reason or "")


def test_depth_n_projection_accepts_unseen_terminal_labels_without_pinning(
    tmp_path: Path,
) -> None:
    _write_minimal_capstone(tmp_path, _minimal_capstone(terminal_label="contested_new_owner_label"))

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    run = packet.payload["domain_runs"]["unseen"]

    assert run["terminal_distribution"] == {"contested_new_owner_label": 1}
    assert packet.payload["terminal_distributions"] == {
        "unseen": {"contested_new_owner_label": 1}
    }


def test_depth_n_projection_hash_ignores_provenance_only_rebaseline(tmp_path: Path) -> None:
    source = _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    changed = _minimal_capstone()
    changed["producer"] = {"provenance_note": "rebaselined without semantic change"}
    source.write_text(json.dumps(changed, sort_keys=True), encoding="utf-8")
    current = source.stat()
    os.utime(source, ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000))
    after = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert before.source is not None
    assert after.source is not None
    assert before.source.artifact_content_hash != after.source.artifact_content_hash
    assert before.projection_hash == after.projection_hash


def test_value_gate_projection_contains_denominators_receipts_and_outer_set_slots() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.VALUE_GATE)

    assert packet.payload["denominators"]["registered_method_count"] > 0
    assert "method_selection_receipt" in packet.payload["education_refusal"]
    assert "value_receipt" in packet.payload["education_refusal"]
    assert packet.payload["value_outer_set_contract"]


def test_disposition_projection_is_narrow_and_audience_declared() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(
        ProjectionId.GENERATION_CYCLE_DISPOSITION
    )

    assert packet.intended_audience is AudienceClass.EXPERT
    assert "tasks" in packet.payload
    assert "source_investigation" not in packet.payload


def test_engine_census_projection_omits_full_rows() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.ENGINE_CENSUS)

    assert packet.payload["row_count"] > 0
    assert "rows" not in packet.payload


def test_fork_b_projection_omits_relation_table_and_binds_counts() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.FORK_B_RELATION_CENSUS)

    assert packet.payload["relation_counts"]
    assert "relation_table" not in packet.payload


def test_acquisition_contract_projection_preserves_owner_receipts() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(
        ProjectionId.ACQUISITION_ROUTING_CONTRACT
    )

    assert "positive_receipt" in packet.payload
    assert "no_result_receipt" in packet.payload
    assert "fail_closed_receipt" in packet.payload


def test_n13a_census_returns_typed_absence_when_source_is_missing(tmp_path: Path) -> None:
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.N13A_ACQUISITION_CENSUS)

    assert packet.availability is ProjectionAvailability.ARTIFACT_MISSING
    assert packet.payload is None


def test_n13a_census_projects_present_source() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.N13A_ACQUISITION_CENSUS)

    assert packet.availability is ProjectionAvailability.AVAILABLE
    assert packet.payload["family_scorecards"]


def test_n13a_probe_journal_returns_typed_absence_when_source_is_missing(
    tmp_path: Path,
) -> None:
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.N13A_LIVE_PROBE_JOURNAL)

    assert packet.availability is ProjectionAvailability.ARTIFACT_MISSING
    assert packet.payload is None


def test_n13a_probe_journal_projects_present_source() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.N13A_LIVE_PROBE_JOURNAL)

    assert packet.availability is ProjectionAvailability.AVAILABLE
    assert packet.payload["records"]


def test_capability_reality_projection_uses_reported_readiness() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.CAPABILITY_REALITY)

    assert packet.payload["readiness"]
    assert "summary" in packet.payload


def test_cluster_ownership_projection_parses_toml_without_reclassifying_cells() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.CLUSTER_OWNERSHIP)

    assert packet.payload["required_clusters"]
    assert packet.payload["clusters"]


def test_layer3_health_projection_preserves_freeze_values() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.LAYER3_HEALTH_METRICS)

    metrics = packet.payload["health_metric_ledgers"]
    assert metrics
    assert all("freeze_value" in metric for metric in metrics)


def test_proving_ground_never_promotes_fixture_expectations_to_runtime_outcomes() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.LEGACY_PROVING_GROUND)

    assert packet.payload["fixture_authority"] == "fixture_only"
    assert packet.payload["runtime_outcomes"]["availability"] == "artifact_missing"
    assert "readiness" in packet.may_not_use_for


def test_proving_ground_has_thirteen_fixture_identities() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.LEGACY_PROVING_GROUND)

    assert len(packet.payload["fixture_identities"]) == 13


def test_surface_readiness_rejects_example_as_live_authority(tmp_path: Path) -> None:
    _write_json(
        tmp_path,
        "architecture/atlas_surfaces/surface-readiness-ledger.example.json",
        {"entries": [{"slice_id": "DS0", "readiness": "implemented"}]},
    )

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.SURFACE_READINESS)

    assert packet.availability is ProjectionAvailability.ARTIFACT_MISSING
    assert packet.payload is None


def test_surface_readiness_returns_typed_absence_without_live_ledger() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.SURFACE_READINESS)

    assert packet.availability is ProjectionAvailability.ARTIFACT_MISSING
    assert packet.payload is None


def test_channel_registry_covers_declared_active_hidden_runtime_channels() -> None:
    by_path = {entry.path_template: entry for entry in CHANNEL_REGISTRY}

    assert by_path["/api/v1/runs/live"].transport == "sse"
    assert by_path["/api/v1/runs/{run_id}/live"].transport == "sse"
    review = by_path["/api/v1/review/live"]
    assert review.transport == "websocket"
    assert set(review.channels) == {"review.cursor", "review.lock", "review.presence"}
    assert all(entry.auth_class for entry in CHANNEL_REGISTRY)
    assert all(entry.consumers for entry in CHANNEL_REGISTRY)
