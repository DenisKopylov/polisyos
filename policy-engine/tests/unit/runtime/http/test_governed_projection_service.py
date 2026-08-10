from __future__ import annotations

import json
import os
import shutil
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = REPO_ROOT / "src/polisyos/runtime/http/services/governed_projections.py"
MODULE_NAME = "polisyos.runtime.http.services.governed_projections"
MODULE_SPEC = spec_from_file_location(MODULE_NAME, MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = module_from_spec(MODULE_SPEC)
_previous_module = sys.modules.get(MODULE_NAME)
try:
    sys.modules[MODULE_NAME] = MODULE
    MODULE_SPEC.loader.exec_module(MODULE)
finally:
    if _previous_module is None:
        sys.modules.pop(MODULE_NAME, None)
    else:
        sys.modules[MODULE_NAME] = _previous_module

CHANNEL_REGISTRY = MODULE.CHANNEL_REGISTRY
AudienceClass = MODULE.AudienceClass
GovernedProjectionService = MODULE.GovernedProjectionService
ProjectionAvailability = MODULE.ProjectionAvailability
ProjectionId = MODULE.ProjectionId
ReplayPinMismatchError = MODULE.ReplayPinMismatchError
hash_export_projection = MODULE.hash_export_projection


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


def _payload(packet: Any) -> dict[str, Any]:
    payload = packet.payload
    assert payload is not None
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    assert isinstance(payload, dict)
    return payload


def _copy_governed_source(root: Path, relative_path: str) -> Path:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / relative_path, destination)
    return destination


def _copy_proving_ground(root: Path) -> None:
    source_root = REPO_ROOT / "tests/fixtures/universal-corpus"
    destination_root = root / "tests/fixtures/universal-corpus"
    destination_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_root / "manifest.json", destination_root / "manifest.json")
    shutil.copytree(source_root / "cases", destination_root / "cases")


@pytest.fixture
def owner_validator_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub an already-proven owner receipt for isolated projector semantics."""

    def pass_validation(
        *,
        repository_root: Path,
        definition: Any,
        loaded: Any,
        payload: BaseModel,
    ) -> Any:
        del repository_root
        payload_data = payload.model_dump(mode="json")
        if definition.projection_id in {
            ProjectionId.N13A_ACQUISITION_CENSUS,
            ProjectionId.N13A_LIVE_PROBE_JOURNAL,
        }:
            from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
                semantic_content_hash,
            )

            projection_hash = semantic_content_hash(payload_data)
            hash_rule = "policyos.layer3.gy.n13a.acquisition_census.v1"
        else:
            from polisyos.pdc import gy_content_hash

            projection_hash = gy_content_hash(payload_data)
            hash_rule = "polisyos.pdc.gy_content_hash.v1"
        dependency_bindings = {
            path: f"file:{content_hash}" for path, content_hash in loaded.component_bindings
        }
        return MODULE.ProjectionSourceValidation(
            validator_id=definition.owner_validator_id,
            validator_version=definition.owner_validator_version,
            status="passed",
            bound_artifact_content_hash=loaded.content_hash,
            bound_dependency_aggregate_identity=hash_export_projection(dependency_bindings),
            bound_dependency_count=len(dependency_bindings),
            semantic_projection_hash=projection_hash,
            semantic_projection_hash_rule_version=hash_rule,
        )

    monkeypatch.setattr(MODULE, "_run_owner_validation", pass_validation)


def test_runtime_http_import_does_not_read_governed_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("governed artifacts must be lazy")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    service = GovernedProjectionService(REPO_ROOT)

    assert ProjectionId.DEPTH_N_CYCLE_BOARD in {entry.projection_id for entry in service.catalog()}


def test_owner_validation_receipt_rejects_forged_aggregate_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json"
    )
    _copy_governed_source(tmp_path, relative_path)
    definition = MODULE._DEFINITION_BY_ID[ProjectionId.ENGINE_CENSUS]
    service = GovernedProjectionService(tmp_path)
    loaded = service._load(definition)
    payload = service._project(definition, loaded)
    dependency_bindings = {
        path: f"file:{content_hash}" for path, content_hash in loaded.component_bindings
    }

    def forged_worker(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "schema_version": ("policyos.runtime.governed_projection.owner_validation.v2"),
                    "projection_id": ProjectionId.ENGINE_CENSUS.value,
                    "validator_id": definition.owner_validator_id,
                    "validator_version": definition.owner_validator_version,
                    "status": "passed",
                    "bound_aggregate_identity": f"sha256:{'0' * 64}",
                    "bound_source_identities": dict(loaded.component_bindings),
                    "bound_projection_payload_hash": hash_export_projection(
                        payload.model_dump(mode="json")
                    ),
                    "semantic_projection_hash": hash_export_projection(
                        payload.model_dump(mode="json")
                    ),
                    "semantic_projection_hash_rule_version": (
                        "polisyos.pdc.gy_content_hash.v1"
                    ),
                    "dependency_aggregate_identity": hash_export_projection(
                        dependency_bindings
                    ),
                    "dependency_bindings": dependency_bindings,
                    "issue_codes": [],
                }
            ),
        )

    monkeypatch.setattr(MODULE.subprocess, "run", forged_worker)
    validation = MODULE._run_owner_validation(
        repository_root=tmp_path,
        definition=definition,
        loaded=loaded,
        payload=payload,
    )

    assert validation.status == "failed"
    assert validation.issue_codes == ("owner_validator_receipt_mismatch",)


def test_projection_packets_require_identity_as_of_and_freshness(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _write_minimal_capstone(tmp_path)

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert packet.availability is ProjectionAvailability.AVAILABLE
    assert packet.source is not None
    assert packet.source.artifact_content_hash.startswith("sha256:")
    assert packet.projection_hash is not None
    assert packet.projection_hash.startswith("sha256:")
    assert packet.export_replay_contract == "policyos.runtime.export_replay_binding.v1"
    assert packet.projection_rule_version == "policyos.runtime.governed_projection.v1"
    assert packet.as_of is not None
    assert packet.freshness.observed_at is not None
    assert packet.freshness.basis in {"source_timestamp", "filesystem_mtime"}
    assert packet.stable_address.endswith("/depth-n-cycle-board")
    assert "artifact_content_hash=" in (packet.replay_address or "")
    assert "projection_hash=" in (packet.replay_address or "")


def test_available_source_identity_is_content_bound_to_passed_owner_validation() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.ENGINE_CENSUS)

    assert packet.availability is ProjectionAvailability.AVAILABLE
    assert packet.source is not None
    validation = packet.source.validation
    assert validation.status == "passed"
    assert validation.bound_artifact_content_hash == packet.source.artifact_content_hash
    assert validation.validator_id == (
        "tools.quality.validation.check_layer3_gy_engine_census:validate"
    )
    assert validation.validator_version
    assert validation.bound_dependency_count > 0
    assert validation.bound_dependency_aggregate_identity.startswith("sha256:")
    assert validation.semantic_projection_hash == packet.projection_hash


def test_projection_packets_encode_distinct_available_missing_and_invalid_states(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)
    available = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    missing = service.get(ProjectionId.N13A_ACQUISITION_CENSUS)

    invalid_source = _minimal_capstone()
    del invalid_source["domain_runs"]["unseen"]["evidence_witness"]
    _write_minimal_capstone(tmp_path, invalid_source)
    invalid = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert len({type(available), type(missing), type(invalid)}) == 3
    assert available.source is not None and available.payload is not None
    assert missing.source is None and missing.payload is None
    assert invalid.source is not None and invalid.payload is None


def test_available_projection_payloads_are_source_specific_strict_models(
    owner_validator_pass: None,
) -> None:
    service = GovernedProjectionService(REPO_ROOT)
    available_ids = set(ProjectionId) - {ProjectionId.SURFACE_READINESS}

    packets = [service.get(projection_id) for projection_id in available_ids]

    assert all(packet.availability is ProjectionAvailability.AVAILABLE for packet in packets)
    assert all(isinstance(packet.payload, BaseModel) for packet in packets)
    assert len({type(packet.payload) for packet in packets}) == len(available_ids)
    assert all(packet.projection_rule_version for packet in packets)


def test_available_packet_rejects_payload_for_a_different_projection(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _write_minimal_capstone(tmp_path)
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    mismatched = packet.model_dump(mode="json")
    mismatched["projection_id"] = ProjectionId.VALUE_GATE.value

    with pytest.raises(ValidationError, match="requires ValueGatePayload"):
        TypeAdapter(MODULE.GovernedProjectionPacket).validate_python(mismatched)


def test_projection_cache_reuses_content_hash_key_until_source_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_validator_pass: None,
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


def test_replay_identity_binds_filesystem_fallback_as_of_for_identical_bytes(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    source = _write_minimal_capstone(tmp_path)
    first_mtime = 1_700_000_000_000_000_000
    second_mtime = first_mtime + 5_000_000_000
    os.utime(source, ns=(first_mtime, first_mtime))
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    assert before.freshness.basis == "filesystem_mtime"

    os.utime(source, ns=(second_mtime, second_mtime))
    after = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert before.source is not None and after.source is not None
    assert before.source.artifact_content_hash == after.source.artifact_content_hash
    assert before.projection_hash == after.projection_hash
    assert before.as_of != after.as_of
    assert before.replay_address != after.replay_address
    with pytest.raises(ReplayPinMismatchError, match="source_as_of"):
        service.get(
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            artifact_content_hash=before.source.artifact_content_hash,
            projection_hash=before.projection_hash,
            source_as_of=before.as_of,
        )


def test_path_cache_detects_same_size_rewrite_with_preserved_mtime(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    source = _write_minimal_capstone(tmp_path)
    original_stat = source.stat()
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    changed = _minimal_capstone()
    changed["producer"]["provenance_note"] = "other"
    replacement = json.dumps(changed, sort_keys=True)
    assert len(replacement.encode()) == original_stat.st_size
    source.write_text(replacement, encoding="utf-8")
    os.utime(
        source,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )

    after = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert before.source is not None and after.source is not None
    assert before.source.artifact_content_hash != after.source.artifact_content_hash
    assert before.projection_hash == after.projection_hash


def test_projection_cache_cannot_be_corrupted_through_returned_nested_payload() -> None:
    service = GovernedProjectionService(REPO_ROOT)
    first = service.get(ProjectionId.ENGINE_CENSUS)
    first_payload = first.payload
    assert isinstance(first_payload, BaseModel)
    vocabulary = first_payload.__dict__["execution_status_vocabulary"]
    assert isinstance(vocabulary, dict)
    vocabulary["cache_corruption_probe"] = "must_not_persist"

    second = service.get(ProjectionId.ENGINE_CENSUS)
    second_payload = _payload(second)

    assert "cache_corruption_probe" not in second_payload["execution_status_vocabulary"]
    assert second.projection_hash == first.projection_hash


def test_owner_validation_cache_revalidates_when_semantic_hasher_bytes_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_task0_audit/"
        "layer3_gy_engine_census.json"
    )
    _copy_governed_source(tmp_path, relative_path)
    dependency = _write_json(
        tmp_path,
        "src/polisyos/pdc/_impl/gy_waist.py",
        {"value": "first"},
    )
    calls = 0

    def worker(*_args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        request = json.loads(str(kwargs["input"]))
        payload = request["projection_payload"]
        dependency_bindings = {
            relative_path: f"file:{MODULE._sha256((tmp_path / relative_path).read_bytes())}",
            dependency.relative_to(tmp_path).as_posix(): (
                f"file:{MODULE._sha256(dependency.read_bytes())}"
            ),
        }
        definition = MODULE._DEFINITION_BY_ID[ProjectionId.ENGINE_CENSUS]
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "schema_version": (
                        "policyos.runtime.governed_projection.owner_validation.v2"
                    ),
                    "projection_id": ProjectionId.ENGINE_CENSUS.value,
                    "validator_id": definition.owner_validator_id,
                    "validator_version": definition.owner_validator_version,
                    "status": "passed",
                    "bound_aggregate_identity": hash_export_projection(
                        request["component_bindings"]
                    ),
                    "bound_source_identities": request["component_bindings"],
                    "bound_projection_payload_hash": hash_export_projection(payload),
                    "semantic_projection_hash": hash_export_projection(payload),
                    "semantic_projection_hash_rule_version": (
                        "polisyos.pdc.gy_content_hash.v1"
                    ),
                    "dependency_aggregate_identity": hash_export_projection(
                        dependency_bindings
                    ),
                    "dependency_bindings": dependency_bindings,
                    "issue_codes": [],
                }
            ),
        )

    monkeypatch.setattr(MODULE.subprocess, "run", worker)
    service = GovernedProjectionService(tmp_path)
    first = service.get(ProjectionId.ENGINE_CENSUS)
    second = service.get(ProjectionId.ENGINE_CENSUS)
    assert first.availability is ProjectionAvailability.AVAILABLE
    assert second.availability is ProjectionAvailability.AVAILABLE
    assert calls == 1

    stat = dependency.stat()
    dependency.write_text('{"value": "other"}', encoding="utf-8")
    assert dependency.stat().st_size == stat.st_size
    os.utime(dependency, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    third = service.get(ProjectionId.ENGINE_CENSUS)

    assert third.availability is ProjectionAvailability.AVAILABLE
    assert calls == 2
    assert first.source is not None and third.source is not None
    assert (
        first.source.validation.bound_dependency_aggregate_identity
        != third.source.validation.bound_dependency_aggregate_identity
    )


def test_owner_validation_cache_binds_exact_projected_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_task0_audit/"
        "layer3_gy_engine_census.json"
    )
    _copy_governed_source(tmp_path, relative_path)
    definition = MODULE._DEFINITION_BY_ID[ProjectionId.ENGINE_CENSUS]
    service = GovernedProjectionService(tmp_path)
    loaded = service._load(definition)
    first_payload = service._project(definition, loaded)
    second_payload = first_payload.model_copy(
        update={"row_count": first_payload.row_count + 1}
    )
    calls = 0

    def worker(*_args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        request = json.loads(str(kwargs["input"]))
        payload = request["projection_payload"]
        dependency_bindings = {
            path: f"file:{content_hash}"
            for path, content_hash in loaded.component_bindings
        }
        semantic_hash = hash_export_projection(payload)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "schema_version": (
                        "policyos.runtime.governed_projection.owner_validation.v2"
                    ),
                    "projection_id": ProjectionId.ENGINE_CENSUS.value,
                    "validator_id": definition.owner_validator_id,
                    "validator_version": definition.owner_validator_version,
                    "status": "passed",
                    "bound_aggregate_identity": hash_export_projection(
                        request["component_bindings"]
                    ),
                    "bound_source_identities": request["component_bindings"],
                    "bound_projection_payload_hash": semantic_hash,
                    "semantic_projection_hash": semantic_hash,
                    "semantic_projection_hash_rule_version": (
                        "polisyos.pdc.gy_content_hash.v1"
                    ),
                    "dependency_aggregate_identity": hash_export_projection(
                        dependency_bindings
                    ),
                    "dependency_bindings": dependency_bindings,
                    "issue_codes": [],
                }
            ),
        )

    monkeypatch.setattr(MODULE.subprocess, "run", worker)
    first = MODULE._run_owner_validation(
        repository_root=tmp_path,
        definition=definition,
        loaded=loaded,
        payload=first_payload,
    )
    second = MODULE._run_owner_validation(
        repository_root=tmp_path,
        definition=definition,
        loaded=loaded,
        payload=second_payload,
    )

    assert calls == 2
    assert first.semantic_projection_hash != second.semantic_projection_hash


def test_replay_identity_and_pin_bind_owner_validation_dependencies(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)
    packet = service.get(ProjectionId.DEPTH_N_CYCLE_BOARD)

    assert packet.source is not None
    dependency_hash = packet.source.validation.bound_dependency_aggregate_identity
    assert "source_dependency_hash=" in (packet.replay_address or "")
    with pytest.raises(ReplayPinMismatchError, match="source_dependency_hash"):
        service.get(
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            source_dependency_hash=f"sha256:{'0' * 64}",
        )


def test_replay_pin_rejects_artifact_hash_mismatch(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)

    with pytest.raises(ReplayPinMismatchError, match="artifact_content_hash"):
        service.get(
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            artifact_content_hash="sha256:not-this-artifact",
        )


def test_replay_pin_rejects_projection_hash_mismatch(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _write_minimal_capstone(tmp_path)
    service = GovernedProjectionService(tmp_path)

    with pytest.raises(ReplayPinMismatchError, match="projection_hash"):
        service.get(
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            projection_hash="sha256:not-this-projection",
        )


def test_depth_n_projection_preserves_recorded_validator_outputs_without_rederiving(
    tmp_path: Path,
    owner_validator_pass: None,
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
    run = _payload(packet)["domain_runs"]["unseen"]

    assert run["evidence_class"] == "deliberately_unseen_owner_evidence_class"
    assert run["weakest_links"] == ["deliberately_unseen_owner_weakest_link"]


def test_depth_n_projection_fails_closed_instead_of_deriving_missing_evidence(
    tmp_path: Path,
    owner_validator_pass: None,
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
    owner_validator_pass: None,
) -> None:
    _write_minimal_capstone(tmp_path, _minimal_capstone(terminal_label="contested_new_owner_label"))

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    payload = _payload(packet)
    run = payload["domain_runs"]["unseen"]

    assert run["terminal_distribution"] == {"contested_new_owner_label": 1}
    assert payload["terminal_distributions"] == {"unseen": {"contested_new_owner_label": 1}}


def test_depth_n_projection_hash_ignores_provenance_only_rebaseline(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
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


def test_value_gate_projection_contains_denominators_receipts_and_outer_set_slots(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _copy_governed_source(
        tmp_path,
        "architecture/policy_design_case/layer3_gy_value_gate_contract.json",
    )
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.VALUE_GATE)
    payload = _payload(packet)

    assert payload["denominators"]["registered_method_count"] > 0
    assert "method_selection_receipt" in payload["education_refusal"]
    assert "value_receipt" in payload["education_refusal"]
    assert payload["value_outer_set_contract"]


def test_disposition_projection_is_narrow_and_audience_declared(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _copy_governed_source(
        tmp_path,
        "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json",
    )
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.GENERATION_CYCLE_DISPOSITION)

    assert packet.intended_audience is AudienceClass.EXPERT
    payload = _payload(packet)
    assert "tasks" in payload
    assert "source_investigation" not in payload


def test_disposition_projection_rejects_missing_declared_dependencies(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path,
        "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json",
        {"schema_version": "disposition.v1"},
    )

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.GENERATION_CYCLE_DISPOSITION)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert "tasks" in (packet.absence_reason or "")


def test_disposition_projection_rejects_present_but_null_declared_dependency(
    tmp_path: Path,
) -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json"
    )
    source_path = _copy_governed_source(tmp_path, relative_path)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["tasks"] = None
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.GENERATION_CYCLE_DISPOSITION)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert packet.projection_hash is None


def test_engine_census_projection_omits_full_rows() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.ENGINE_CENSUS)

    payload = _payload(packet)
    assert payload["row_count"] > 0
    assert "rows" not in payload


def test_fork_b_projection_omits_relation_table_and_binds_counts() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.FORK_B_RELATION_CENSUS)

    payload = _payload(packet)
    assert payload["relation_counts"]
    assert "relation_table" not in payload


def test_acquisition_contract_projection_preserves_owner_receipts(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _copy_governed_source(
        tmp_path,
        "architecture/policy_design_case/layer3_gy_acquisition_contract.json",
    )
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)

    payload = _payload(packet)
    assert "positive_receipt" in payload
    assert "no_result_receipt" in payload
    assert "fail_closed_receipt" in payload


@pytest.mark.parametrize(
    "projection_id",
    [
        ProjectionId.DEPTH_N_CYCLE_BOARD,
        ProjectionId.VALUE_GATE,
        ProjectionId.GENERATION_CYCLE_DISPOSITION,
        ProjectionId.ACQUISITION_ROUTING_CONTRACT,
    ],
)
def test_missing_owner_validator_dependency_fails_closed(
    projection_id: Any,
) -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(projection_id)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert packet.source is not None
    assert packet.source.validation.status == "failed"
    assert any(
        code.startswith("owner_validator_dependency_missing_")
        for code in packet.source.validation.issue_codes
    )


def test_acquisition_projection_hash_ignores_receipt_provenance_rebaseline(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    relative_path = "architecture/policy_design_case/layer3_gy_acquisition_contract.json"
    source_path = _copy_governed_source(tmp_path, relative_path)
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["positive_receipt"]["generated_at"] = "2099-01-01T00:00:00Z"
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
    current = source_path.stat()
    os.utime(source_path, ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000))

    after = service.get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)

    assert before.source is not None and after.source is not None
    assert before.source.artifact_content_hash != after.source.artifact_content_hash
    assert before.projection_hash == after.projection_hash


@pytest.mark.parametrize(
    ("receipt_name", "artifact_index"),
    [("positive_receipt", 0), ("no_result_receipt", 0)],
)
def test_acquisition_projection_hash_ignores_recursive_capture_provenance_but_binds_owner_content(
    tmp_path: Path,
    owner_validator_pass: None,
    receipt_name: str,
    artifact_index: int,
) -> None:
    relative_path = "architecture/policy_design_case/layer3_gy_acquisition_contract.json"
    source_path = _copy_governed_source(tmp_path, relative_path)
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    owner_artifact = source[receipt_name]["owner_artifacts"][artifact_index]
    owner_artifact["capture_provenance"] = {
        "capture_mode": "replayed_provenance_probe",
        "captured_at": "2099-01-01T00:00:00Z",
        "owner_request_hash": "sha256:provenance-only-request",
        "owner_response_hash": "sha256:provenance-only-response",
    }
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")

    provenance_only = service.get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)

    assert before.source is not None and provenance_only.source is not None
    assert before.source.artifact_content_hash != provenance_only.source.artifact_content_hash
    assert before.projection_hash == provenance_only.projection_hash

    owner_artifact["content_hash"] = "sha256:changed-owner-content"
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
    owner_content_changed = service.get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)

    assert owner_content_changed.projection_hash != provenance_only.projection_hash


def test_acquisition_projection_hash_binds_semantic_producer_identity(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    relative_path = "architecture/policy_design_case/layer3_gy_acquisition_contract.json"
    source_path = _copy_governed_source(tmp_path, relative_path)
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["positive_receipt"]["compiled_requirement_specs"][0]["producer"] = (
        "polisyos.data_requirement.compiler.RebasedCompiler"
    )
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")

    after = service.get(ProjectionId.ACQUISITION_ROUTING_CONTRACT)

    assert before.projection_hash != after.projection_hash


def test_n13a_census_returns_typed_absence_when_source_is_missing(tmp_path: Path) -> None:
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.N13A_ACQUISITION_CENSUS)

    assert packet.availability is ProjectionAvailability.ARTIFACT_MISSING
    assert packet.payload is None


def test_n13a_census_fails_closed_when_recompute_catalog_is_absent() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.N13A_ACQUISITION_CENSUS)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.source is not None
    assert packet.payload is None
    assert packet.source.validation.status == "failed"
    assert packet.source.validation.issue_codes == (
        "owner_validator_dependency_missing_catalog",
    )
    assert packet.source.declared_content_hash is None


def test_n13a_valid_catalog_recomputes_through_service_within_bridge_budget(
    tmp_path: Path,
) -> None:
    catalog_value = os.environ.get("POLISYOS_N13A_PRODUCTION_CATALOG")
    if not catalog_value:
        pytest.skip("production catalog is an explicit read-only service witness")
    catalog = Path(catalog_value)
    if not catalog.is_file():
        pytest.skip("configured production catalog is absent")
    copied_paths = (
        "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json",
        "architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json",
        "architecture/policy_design_case/layer3_gy_value_gate_contract.json",
        "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json",
        "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json",
    )
    for relative_path in copied_paths:
        _copy_governed_source(tmp_path, relative_path)
    catalog_relative = (
        "production_data/datasets_full_phase3full_20260327_183054/"
        "dataset_catalog.duckdb"
    )
    catalog_destination = tmp_path / catalog_relative
    catalog_destination.parent.mkdir(parents=True, exist_ok=True)
    catalog_destination.symlink_to(catalog)

    packet = GovernedProjectionService(tmp_path).get(
        ProjectionId.N13A_ACQUISITION_CENSUS
    )

    assert packet.availability is ProjectionAvailability.AVAILABLE
    assert packet.source is not None
    assert packet.source.validation.status == "passed"
    assert packet.source.validation.bound_dependency_count > len(copied_paths)
    assert packet.projection_hash == packet.source.validation.semantic_projection_hash


def test_n13a_probe_journal_returns_typed_absence_when_source_is_missing(
    tmp_path: Path,
) -> None:
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.N13A_LIVE_PROBE_JOURNAL)

    assert packet.availability is ProjectionAvailability.ARTIFACT_MISSING
    assert packet.payload is None


def test_n13a_probe_journal_fails_closed_when_recompute_catalog_is_absent() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.N13A_LIVE_PROBE_JOURNAL)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert packet.source is not None
    assert packet.source.validation.issue_codes == (
        "owner_validator_dependency_missing_catalog",
    )


def test_n13a_owner_hash_ignores_run_economics_but_replay_binds_changed_bytes(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    relative_path = "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"
    source_path = _copy_governed_source(tmp_path, relative_path)
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.N13A_LIVE_PROBE_JOURNAL)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["records"][0]["attempt_wall_time_seconds"] += 0.1
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")

    after = service.get(ProjectionId.N13A_LIVE_PROBE_JOURNAL)

    assert before.source is not None and after.source is not None
    assert before.source.artifact_content_hash != after.source.artifact_content_hash
    assert before.projection_hash == after.projection_hash
    assert before.replay_address != after.replay_address
    assert (
        before.source.validation.bound_dependency_aggregate_identity
        != after.source.validation.bound_dependency_aggregate_identity
    )


def test_capability_reality_projection_uses_reported_readiness(
    tmp_path: Path,
    owner_validator_pass: None,
) -> None:
    _copy_governed_source(
        tmp_path,
        "architecture/policy_design_case/capability_reality_report.json",
    )
    packet = GovernedProjectionService(tmp_path).get(ProjectionId.CAPABILITY_REALITY)

    payload = _payload(packet)
    assert payload["readiness"]
    assert "summary" in payload


def test_capability_reality_fails_closed_on_current_owner_validator_drift() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.CAPABILITY_REALITY)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert packet.source is not None
    assert packet.source.validation.status == "failed"
    assert "capability_repo_ref_file_missing" in packet.source.validation.issue_codes


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        pytest.param("summary", None, id="null-summary"),
        pytest.param("readiness", "ready", id="scalar-readiness"),
        pytest.param(
            "capability_claims",
            {"all": "implemented"},
            id="mapping-instead-of-claim-list",
        ),
        pytest.param("debt_algebra", 42, id="scalar-debt-algebra"),
    ],
)
def test_capability_reality_rejects_present_but_semantically_invalid_fields(
    tmp_path: Path,
    field: str,
    invalid_value: object,
) -> None:
    relative_path = "architecture/policy_design_case/capability_reality_report.json"
    source_path = _copy_governed_source(tmp_path, relative_path)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    required_projection_fields = {
        "summary",
        "readiness",
        "capability_claims",
        "blockers",
        "issues",
        "chain_clusters",
        "ratchet_integrity_status",
        "debt_algebra",
    }
    assert required_projection_fields <= set(source)
    source[field] = invalid_value
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.CAPABILITY_REALITY)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert packet.projection_hash is None


@pytest.mark.parametrize("owner_field", ["schema_version", "contract_id", "tool"])
@pytest.mark.parametrize("mutation", ["missing", "unrecognized"])
def test_capability_reality_rejects_missing_or_unrecognized_owner_contract(
    tmp_path: Path,
    owner_field: str,
    mutation: str,
) -> None:
    relative_path = "architecture/policy_design_case/capability_reality_report.json"
    source_path = _copy_governed_source(tmp_path, relative_path)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    assert source.get("schema_version")
    assert source.get("contract_id")
    assert source.get("tool")
    if mutation == "missing":
        del source[owner_field]
    else:
        source[owner_field] = f"unrecognized.{owner_field}.v999"
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.CAPABILITY_REALITY)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert packet.projection_hash is None


def test_cluster_ownership_projection_parses_toml_without_reclassifying_cells() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.CLUSTER_OWNERSHIP)

    payload = _payload(packet)
    assert payload["required_clusters"]
    assert payload["clusters"]


def test_layer3_health_projection_preserves_freeze_values() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.LAYER3_HEALTH_METRICS)

    metrics = _payload(packet)["health_metric_ledgers"]
    assert metrics
    assert all("freeze_value" in metric for metric in metrics)


def test_proving_ground_never_promotes_fixture_expectations_to_runtime_outcomes() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.LEGACY_PROVING_GROUND)

    payload = _payload(packet)
    assert payload["fixture_authority"] == "fixture_only"
    assert payload["runtime_outcomes"]["availability"] == "artifact_missing"
    assert "readiness" in packet.may_not_use_for


def test_proving_ground_has_thirteen_fixture_identities() -> None:
    packet = GovernedProjectionService(REPO_ROOT).get(ProjectionId.LEGACY_PROVING_GROUND)

    assert len(_payload(packet)["fixture_identities"]) == 13


def test_proving_ground_projection_omits_producer_metadata_and_hash_ignores_it(
    tmp_path: Path,
) -> None:
    _copy_proving_ground(tmp_path)
    service = GovernedProjectionService(tmp_path)
    before = service.get(ProjectionId.LEGACY_PROVING_GROUND)
    before_payload = _payload(before)
    assert all("metadata" not in record for record in before_payload["fixture_records"])
    assert all("producer_pipeline" not in record for record in before_payload["fixture_records"])

    case_path = next((tmp_path / "tests/fixtures/universal-corpus/cases").glob("*.json"))
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["metadata"]["pattern_refs"] = list(reversed(case["metadata"]["pattern_refs"]))
    producer = dict(case["producer_pipeline"]["producers"][0])
    producer["requested_deadline_s"] = float(producer["requested_deadline_s"]) + 1.0
    case["producer_pipeline"]["producers"][0] = producer
    case_path.write_text(json.dumps(case, sort_keys=True), encoding="utf-8")
    current = case_path.stat()
    os.utime(case_path, ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000))

    after = service.get(ProjectionId.LEGACY_PROVING_GROUND)

    assert before.source is not None and after.source is not None
    assert before.source.artifact_content_hash != after.source.artifact_content_hash
    assert before.projection_hash == after.projection_hash


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


def test_surface_readiness_present_but_fake_is_invalid_source(tmp_path: Path) -> None:
    _write_json(
        tmp_path,
        "architecture/atlas_surfaces/surface-readiness-ledger.json",
        {},
    )

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.SURFACE_READINESS)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.payload is None
    assert "schema_version" in (packet.absence_reason or "")


def test_surface_readiness_rejects_revision_2_schema_at_live_path(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "architecture/atlas_surfaces/surface-readiness-ledger.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        REPO_ROOT / "architecture/atlas_surfaces/surface-readiness-ledger.example.json",
        destination,
    )

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.SURFACE_READINESS)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert "Revision-3-capable" in (packet.absence_reason or "")


@pytest.mark.parametrize(
    ("projection_id", "relative_path", "raw"),
    [
        (
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json",
            b"{not-json",
        ),
        (
            ProjectionId.CLUSTER_OWNERSHIP,
            "architecture/policy_design_case/cluster_ownership_map.toml",
            b"invalid = [toml",
        ),
    ],
)
def test_malformed_single_file_sources_return_typed_invalid_source(
    tmp_path: Path,
    projection_id: Any,
    relative_path: str,
    raw: bytes,
) -> None:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)

    packet = GovernedProjectionService(tmp_path).get(projection_id)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.source is not None
    assert packet.source.artifact_content_hash.startswith("sha256:")
    assert packet.source.validation.status == "not_run"
    assert packet.source.validation.validator_id == (
        "polisyos.runtime.http.services.governed_projections:source_projection"
    )
    assert packet.payload is None


def test_malformed_proving_ground_case_returns_typed_invalid_source(
    tmp_path: Path,
) -> None:
    manifest = {
        "schema_version": "fixture-manifest.v1",
        "fixtures": [
            {
                "case_id": "case-1",
                "domain": "test",
                "split": "test",
                "authority_levels": ["research"],
                "path": "cases/case-1.json",
            }
        ],
    }
    _write_json(tmp_path, "tests/fixtures/universal-corpus/manifest.json", manifest)
    case_path = tmp_path / "tests/fixtures/universal-corpus/cases/case-1.json"
    case_path.parent.mkdir(parents=True, exist_ok=True)
    case_path.write_text("{not-json", encoding="utf-8")

    packet = GovernedProjectionService(tmp_path).get(ProjectionId.LEGACY_PROVING_GROUND)

    assert packet.availability is ProjectionAvailability.INVALID_SOURCE
    assert packet.source is not None
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
