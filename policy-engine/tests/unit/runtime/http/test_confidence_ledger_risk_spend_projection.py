"""Owner-validation bridge tests for the DS17 confidence risk-spend packet."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.http.services import governed_projections as governed_sources
from polisyos.runtime.http.services.confidence_ledger_risk_spend_contracts import (
    ArtifactMissingConfidenceLedgerRiskSpendPacket,
    AvailableConfidenceLedgerRiskSpendPacket,
    InvalidConfidenceLedgerRiskSpendPacket,
    SourceBlockedConfidenceLedgerRiskSpendPacket,
    SourceBlockedReason,
)
from polisyos.runtime.http.services.confidence_ledger_risk_spend_projection import (
    ConfidenceLedgerRiskSpendProjectionService,
)
from polisyos.runtime.http.services.governed_projections import (
    GovernedProjectionService,
    GuardedProjectionId,
    GuardedProjectionSourceResolution,
    ProjectionAvailability,
    ProjectionId,
    ProjectionSourceIdentity,
    ProjectionSourceValidation,
)
from tools.quality.validation import check_layer3_gy_confidence_ledger as n11_owner

_ROOT = Path(__file__).resolve().parents[4]
_SOURCE = "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"


def _copy_source(root: Path) -> Path:
    destination = root / _SOURCE
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_ROOT / _SOURCE, destination)
    return destination


def _ledger_hash(value: object) -> str:
    return n11_owner._ledger_content_hash(value)  # noqa: SLF001


def _rebind_check(check: dict[str, Any], spend: Fraction) -> None:
    check["spend"] = {
        "numerator": spend.numerator,
        "denominator": spend.denominator,
    }
    check["spend_decimal"] = "0" if spend == 0 else "0.02"
    claim_values = {
        "scope_id": check["scope_id"],
        "request_fingerprint": check["request_fingerprint"],
        "claim_ref": check["claim_ref"],
        "null_ref": check["null_ref"],
        "claim_scope_ref": check["claim_scope_ref"],
        "data_window_ref": check["data_window_ref"],
        "filtration_projection_hash": check["filtration_projection_hash"],
        "certificate_role": check["certificate_role"],
        "claim_polarity": check["claim_polarity"],
        "execution_id": check["execution_id"],
        "execution_ordinal": check["execution_ordinal"],
        "schedule_query_index": check["schedule_query_index"],
        "reserved_alpha": check["spend"],
        "registry_content_hash": check["registry_content_hash"],
        "instrument_definition_hash": check["instrument_definition_hash"],
        "proof_profile_hash": check["proof_profile_hash"],
    }
    check["claim_execution_projection_hash"] = _ledger_hash(claim_values)
    check["check_projection_hash"] = _ledger_hash(
        {key: value for key, value in check.items() if key != "check_projection_hash"}
    )


def coherent_over_spend_artifact(
    target_ordinal: int,
    *,
    stale_total: bool = False,
) -> dict[str, Any]:
    artifact = json.loads((_ROOT / _SOURCE).read_text(encoding="utf-8"))
    real = artifact["real_ledger_projection"]
    exact_spend = Fraction(1, 50)
    head = real["root_projection_hash"]
    filtrations: dict[str, str] = {}
    current: dict[str, dict[str, Any]] = {}
    for event in real["events"]:
        event["parent_event_projection_hash"] = head
        check = event["check"]
        request_key = check["request_key"]
        if event["event_type"] == "prepared":
            filtrations[request_key] = head
        check["filtration_projection_hash"] = filtrations[request_key]
        check_spend = (
            exact_spend
            if check["execution_ordinal"] == target_ordinal
            else Fraction()
        )
        _rebind_check(check, check_spend)
        event["event_projection_hash"] = _ledger_hash(
            {
                key: value
                for key, value in event.items()
                if key != "event_projection_hash"
            }
        )
        head = event["event_projection_hash"]
        current[request_key] = copy.deepcopy(check)
    real["head_event_projection_hash"] = head
    real["checks"] = [current[key] for key in sorted(current)]
    exact_amount = {
        "numerator": exact_spend.numerator,
        "denominator": exact_spend.denominator,
    }
    real["total_spend"] = (
        {"numerator": 0, "denominator": 1} if stale_total else exact_amount
    )
    real["total_spend_decimal"] = "0.02"
    real["within_budget"] = stale_total
    real["projection_hash"] = _ledger_hash(
        {key: value for key, value in real.items() if key != "projection_hash"}
    )

    checks_by_certificate = {
        check["certificate_ref"]: check for check in real["checks"]
    }
    accounted = artifact["accounted_run"]
    for row in accounted["evidence_rows"]:
        check = checks_by_certificate[row["certificate_ref"]]
        row["check_projection_hash"] = check["check_projection_hash"]
        row["claim_execution_projection_hash"] = check[
            "claim_execution_projection_hash"
        ]
        row["spend_numerator"] = check["spend"]["numerator"]
        row["spend_denominator"] = check["spend"]["denominator"]
    accounted["total_spend_numerator"] = exact_spend.numerator
    accounted["total_spend_denominator"] = exact_spend.denominator
    accounted["total_spend_decimal"] = "0.02"
    accounted["projection_hash"] = _ledger_hash(
        {key: value for key, value in accounted.items() if key != "projection_hash"}
    )

    n9 = artifact["n9_promotion_projection"]
    n9["ledger_projection_hash"] = real["projection_hash"]
    n9["total_spend"] = real["total_spend"]
    n9["total_spend_decimal"] = "0.02"
    n9["within_budget"] = real["within_budget"]
    n9["projection_hash"] = _ledger_hash(
        {key: value for key, value in n9.items() if key != "projection_hash"}
    )
    n12 = artifact["n12_epoch_reference_projection"]
    n12["ledger_projection_hash"] = real["projection_hash"]
    n12["projection_hash"] = _ledger_hash(
        {key: value for key, value in n12.items() if key != "projection_hash"}
    )

    consumer_hashes = {
        real["projection_scope"]: real["projection_hash"],
        "n11_accounted_run": accounted["projection_hash"],
        "n9_promotion_certificate": n9["projection_hash"],
        "n12_epoch_reference": n12["projection_hash"],
    }
    for edge in artifact["projection_edges"]:
        if edge["producer_scope"] == real["projection_scope"]:
            edge["producer_projection_hash"] = real["projection_hash"]
        edge["consumer_projection_hash"] = consumer_hashes[edge["consumer_scope"]]
    n11_owner._set_confidence_contract_identities(artifact)  # noqa: SLF001
    return artifact


def owner_issue_codes(artifact: dict[str, Any]) -> set[str]:
    result = n11_owner.validate_payload(artifact)
    return {
        str(issue["code"])
        for issue in result["issues"]
        if isinstance(issue, dict) and "code" in issue
    }


def test_guarded_source_is_catalogued_without_widening_dynamic_projection_ids() -> None:
    service = GovernedProjectionService(_ROOT)
    catalog_ids = {entry.projection_id for entry in service.catalog()}

    assert len(ProjectionId) == 13
    assert set(ProjectionId).issubset(catalog_ids)
    assert catalog_ids - set(ProjectionId) == {
        GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND
    }
    with pytest.raises(ValueError):
        service.get(GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND.value)


def test_real_owner_artifact_reaches_available_domain_projection(
    tmp_path: Path,
) -> None:
    _copy_source(tmp_path)
    packet = ConfidenceLedgerRiskSpendProjectionService(tmp_path).get()

    assert isinstance(packet, AvailableConfidenceLedgerRiskSpendPacket)
    assert packet.availability == "available"
    assert packet.worker_validation_receipt_hash.startswith("sha256:")
    assert packet.payload.registry_content_hash == packet.registry_content_hash
    assert packet.payload.source_projection_hash == packet.frozen_semantic_projection_hash
    assert packet.payload.coverage_assessment == "open_world_unresolved"
    assert packet.payload.appointment_posture == "institutional_authority_unappointed"
    assert packet.payload.status == "not_promoted"
    assert len(packet.payload.instrument_definitions) == 13
    assert len(packet.payload.instrument_instances) == 3
    assert len(packet.payload.acquisition_instance_refs) == 2
    assert len(packet.payload.refusal_instance_refs) == 1


def test_coherent_owner_over_spend_reaches_detail_free_source_blocker(
    tmp_path: Path,
) -> None:
    artifacts = tuple(coherent_over_spend_artifact(index) for index in range(3))
    expected_codes = {
        "semantic_forged_spend_row",
        "semantic_deterministic_spend_nonzero",
        "deterministic_real_run_spend_nonzero",
    }
    assert all(owner_issue_codes(artifact) == expected_codes for artifact in artifacts)
    stale_total_artifact = coherent_over_spend_artifact(2, stale_total=True)
    assert owner_issue_codes(stale_total_artifact) == {
        *expected_codes,
        "semantic_total_spend_drift",
        "semantic_budget_status_drift",
    }

    source = tmp_path / _SOURCE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(stale_total_artifact, sort_keys=True), encoding="utf-8")
    packet = ConfidenceLedgerRiskSpendProjectionService(tmp_path).get()

    assert isinstance(packet, SourceBlockedConfidenceLedgerRiskSpendPacket)
    assert packet.source_blocked_reason is SourceBlockedReason.OVER_SPEND
    assert packet.worker_validation_receipt_hash.startswith("sha256:")
    assert packet.projection_hash.startswith("sha256:")
    assert packet.replay_address.startswith(packet.stable_address + "?")


def test_missing_malformed_and_forged_sources_fail_closed_distinctly(
    tmp_path: Path,
) -> None:
    service = ConfidenceLedgerRiskSpendProjectionService(tmp_path)
    missing = service.get()
    assert isinstance(missing, ArtifactMissingConfidenceLedgerRiskSpendPacket)

    source = tmp_path / _SOURCE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{", encoding="utf-8")
    malformed = ConfidenceLedgerRiskSpendProjectionService(tmp_path).get()
    assert isinstance(malformed, InvalidConfidenceLedgerRiskSpendPacket)
    assert malformed.source_artifact_content_hash is not None

    forged_artifact = json.loads((_ROOT / _SOURCE).read_text(encoding="utf-8"))
    forged_artifact["registry_projection"]["projection_hash"] = "sha256:" + "0" * 64
    source.write_text(json.dumps(forged_artifact, sort_keys=True), encoding="utf-8")
    forged = ConfidenceLedgerRiskSpendProjectionService(tmp_path).get()
    assert isinstance(forged, InvalidConfidenceLedgerRiskSpendPacket)
    assert forged.source_artifact_content_hash is not None
    assert forged.worker_validation_receipt_hash is not None


def test_requested_projection_must_equal_owner_artifact_projection(tmp_path: Path) -> None:
    source = _copy_source(tmp_path)
    artifact = json.loads(source.read_text(encoding="utf-8"))
    requested = artifact["conformance_ledger_projection"]

    result = GovernedProjectionService(tmp_path).resolve_guarded_source(
        GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND,
        projection_payload=requested,
    )

    assert result.validation.status == "failed"
    assert "source_projection_payload_mismatch" in result.validation.issue_codes
    assert result.source_payload_equal is False


class _FixedGuardedSourceService:
    """Attempt the forbidden hand-authored owner-resolution seam."""

    def __init__(self, resolution: GuardedProjectionSourceResolution) -> None:
        self._resolution = resolution

    def resolve_guarded_source(
        self,
        projection_id: GuardedProjectionId,
    ) -> GuardedProjectionSourceResolution:
        assert projection_id is GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND
        return self._resolution


def _coherent_hand_authored_over_spend_resolution(
    resolution: GuardedProjectionSourceResolution,
) -> GuardedProjectionSourceResolution:
    assert resolution.source is not None
    assert resolution.validation is not None
    source_payload = resolution.source.model_dump(mode="python")
    validation_payload = resolution.validation.model_dump(mode="python")
    validation_payload.update(
        {
            "status": "failed",
            "semantic_projection_hash": None,
            "issue_codes": ("semantic_total_spend_drift",),
            "recomputed_total_spend_numerator": 2,
            "recomputed_total_spend_denominator": 100,
            "registry_delta_numerator": 1,
            "registry_delta_denominator": 100,
        }
    )
    validation = ProjectionSourceValidation.model_validate(validation_payload)
    source_payload["validation"] = validation.model_dump(mode="python")
    source = ProjectionSourceIdentity.model_validate(source_payload)
    return replace(
        resolution,
        availability=ProjectionAvailability.INVALID_SOURCE,
        source=source,
        validation=validation,
    )


def test_hand_authored_typed_resolution_cannot_enter_supported_service_api() -> None:
    resolution = GovernedProjectionService(_ROOT).resolve_guarded_source(
        GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND
    )
    assert resolution.validation is not None
    assert resolution.validation.status == "passed"
    forged = _coherent_hand_authored_over_spend_resolution(resolution)
    assert forged.availability is ProjectionAvailability.INVALID_SOURCE
    assert forged.validation is not None
    assert forged.validation.issue_codes == ("semantic_total_spend_drift",)

    with pytest.raises(TypeError, match="source_service"):
        ConfidenceLedgerRiskSpendProjectionService(
            _ROOT,
            source_service=_FixedGuardedSourceService(forged),  # type: ignore[call-arg]
        )


def test_guarded_owner_validation_executes_per_request_and_cannot_be_seeded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never reuse or accept a candidate in place of a guarded owner execution."""

    _copy_source(tmp_path)
    monkeypatch.setattr(governed_sources, "_OWNER_VALIDATION_CACHE", {})
    real_run = governed_sources.subprocess.run
    owner_worker_runs = 0

    def count_real_owner_runs(
        *args: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal owner_worker_runs
        owner_worker_runs += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr(
        governed_sources.subprocess,
        "run",
        count_real_owner_runs,
    )
    service = ConfidenceLedgerRiskSpendProjectionService(tmp_path)

    first = service.get()
    unchanged = service.get()

    assert isinstance(first, AvailableConfidenceLedgerRiskSpendPacket)
    assert isinstance(unchanged, AvailableConfidenceLedgerRiskSpendPacket)
    assert unchanged.worker_validation_receipt_hash == first.worker_validation_receipt_hash
    assert owner_worker_runs == 2
    assert governed_sources._OWNER_VALIDATION_CACHE == {}  # noqa: SLF001
    with pytest.raises(TypeError, match="packet_candidate"):
        service.get(
            packet_candidate=unchanged,  # type: ignore[call-arg]
        )
    assert governed_sources._OWNER_VALIDATION_CACHE == {}  # noqa: SLF001
    assert owner_worker_runs == 2


def test_external_pythonpath_hook_change_reexecutes_guarded_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe changed execution code even when it is outside the artifact root."""

    artifact_root = tmp_path / "artifact-root"
    hook_root = tmp_path / "external-hook"
    _copy_source(artifact_root)
    hook_root.mkdir()
    hook = hook_root / "sitecustomize.py"
    hook.write_text("# initial no-op owner hook\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(hook_root))
    monkeypatch.setattr(governed_sources, "_OWNER_VALIDATION_CACHE", {})
    real_run = governed_sources.subprocess.run
    owner_worker_runs = 0

    def count_real_owner_runs(
        *args: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal owner_worker_runs
        owner_worker_runs += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr(
        governed_sources.subprocess,
        "run",
        count_real_owner_runs,
    )
    service = ConfidenceLedgerRiskSpendProjectionService(artifact_root)

    first = service.get()
    assert isinstance(first, AvailableConfidenceLedgerRiskSpendPacket)
    assert owner_worker_runs == 1

    hook.write_text(
        """from tools.quality.validation import check_layer3_gy_confidence_ledger as owner

original_validate_payload = owner.validate_payload


def reject_payload(payload):
    result = original_validate_payload(payload)
    result[\"issues\"] = [*result[\"issues\"], {\"code\": \"outside_diagnostic\"}]
    return result


owner.validate_payload = reject_payload
""",
        encoding="utf-8",
    )
    changed_hook = service.get()

    assert isinstance(changed_hook, InvalidConfidenceLedgerRiskSpendPacket)
    assert owner_worker_runs == 2
    assert governed_sources._OWNER_VALIDATION_CACHE == {}  # noqa: SLF001
