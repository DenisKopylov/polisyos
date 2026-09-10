"""Exercise the operational epoch custody caller and its persisted negatives."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core import artifacts, contracts, security


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _request(label: str = "publication") -> contracts.AnchorAcceptanceRequest:
    return contracts.AnchorAcceptanceRequest(
        bundle_ref=artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(_digest(f"bundle:{label}")),
            kind="candidate.chronology.bundle",
            media_type="application/octet-stream",
        ),
        expected_domain=contracts.ChronologyProofDomain(
            format="polisyos.chronology.full-prefix.v1",
            profile="full_prefix_canon_json_0_2_0_sha256_256_v1",
            proof_domain="semantic-epoch",
            family="epoch",
            scope_ref=_digest(f"scope:{label}"),
            authority_purpose=label,
        ),
        native_reconciliation_ref=artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(_digest(f"reconciliation:{label}")),
            kind="candidate.chronology.reconciliation",
            media_type="application/octet-stream",
        ),
        authority_purpose=label,
        requested_query_context_ref=_digest(f"query:{label}"),
        asserted_prior_acceptance_record_refs=(),
    )


def test_cli_persists_both_unappointed_roles(tmp_path: Path) -> None:
    """The real module run must persist its exact provider result and request."""
    request = _request()
    request_path = tmp_path / "request.json"
    request_path.write_text(request.model_dump_json(), encoding="utf-8")
    cas_root = tmp_path / "cas"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "polisyos.runtime.quality.epoch_custody_audit",
            "--request",
            str(request_path),
            "--cas-root",
            str(cas_root),
        ],
        cwd=Path(__file__).parents[4],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    from polisyos.runtime.quality.epoch_custody_audit import EpochCustodyAuditReceipt

    response = json.loads(run.stdout)
    receipt_ref = artifacts.ArtifactRef.model_validate(response["receipt_ref"])
    store = artifacts.FileSystemCAS(cas_root)
    receipt_bytes = store.get_bytes(receipt_ref.artifact_id)
    assert str(receipt_ref.artifact_id) == security.raw_content_hash(receipt_bytes)
    receipt = security.parse_canonical_statement(receipt_bytes, EpochCustodyAuditReceipt)
    stored_request = security.parse_canonical_statement(
        store.get_bytes(receipt.request_ref.artifact_id), contracts.AnchorAcceptanceRequest
    )
    assert stored_request == request
    assert receipt.authority_scope == "custody_provider_invocation_only"
    assert receipt.request_reference_verification == "not_established"
    assert receipt.observed_at.utcoffset().total_seconds() == 0
    assert receipt.result.status == response["status"] == "limited"
    assert receipt.result.acceptance.status == response["acceptance"] == "not_established"
    assert receipt.result.retention.status == response["retention"] == "not_established"
    acceptance = receipt.result.acceptance.non_receipts[0]
    retention = receipt.result.retention.non_receipts[0]
    assert acceptance.code == "anchor_acceptance_owner_not_established"
    assert retention.code == "anchor_holder_not_established"
    for outcome in (acceptance, retention):
        assert outcome.subject_artifact_ref == request.bundle_ref
        assert outcome.requested_query_context_ref == request.requested_query_context_ref
        assert outcome.predicate_class == "not_established"
        assert outcome.resolved_appointment_ref is None
    assert store.get_manifest(receipt_ref.artifact_id).inputs == [
        artifacts.InputRef(artifact_id=receipt.request_ref.artifact_id, role="audit_request")
    ]


def test_audits_bind_distinct_query_purposes(tmp_path: Path) -> None:
    """The negative for one query cannot be reused as another query's evidence."""
    from polisyos.runtime.quality.epoch_custody_audit import audit_epoch_custody

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    first_ref, first = audit_epoch_custody(request=_request("publication"), store=store)
    second_ref, second = audit_epoch_custody(request=_request("decision_validity"), store=store)
    assert first_ref != second_ref
    assert first.request_ref != second.request_ref
    first_retention = first.result.retention.non_receipts[0]
    second_retention = second.result.retention.non_receipts[0]
    assert first_retention.appointment_key_ref != second_retention.appointment_key_ref
    assert first_retention.requested_query_context_ref == _request().requested_query_context_ref
    assert (
        second_retention.requested_query_context_ref
        == _request("decision_validity").requested_query_context_ref
    )
    assert first_retention.code == second_retention.code == "anchor_holder_not_established"


@pytest.mark.parametrize("malformation", ["extra_field", "wrong_family", "conflicting_purpose"])
def test_cli_rejects_malformed_request_without_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], malformation: str
) -> None:
    """Request shape or routing ambiguity must not produce a completed audit."""
    from polisyos.runtime.quality.epoch_custody_audit import main

    payload = _request().model_dump(mode="json")
    if malformation == "extra_field":
        payload["holder_appointed"] = True
    elif malformation == "wrong_family":
        payload["expected_domain"]["family"] = "calibration"
    else:
        payload["expected_domain"]["authority_purpose"] = "different_purpose"
    request_path = tmp_path / "malformed.json"
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    cas_root = tmp_path / "cas"
    assert main(["--request", str(request_path), "--cas-root", str(cas_root)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "epoch_custody_audit_failed" in captured.err
    assert artifacts.FileSystemCAS(cas_root).iter_artifact_ids() == []


def test_missing_provider_result_cannot_complete_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing the live producer's output must leave no completed result artifact."""
    from polisyos.runtime.quality.chronology_custody import EpochAnchorCustodyService
    from polisyos.runtime.quality.epoch_custody_audit import audit_epoch_custody

    monkeypatch.setattr(
        EpochAnchorCustodyService, "evaluate_acceptance_and_custody", lambda self, **kwargs: None
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    with pytest.raises(TypeError, match="custody_provider_result_missing_or_invalid"):
        audit_epoch_custody(request=_request(), store=store)
    assert all(
        store.get_manifest(artifact_id).kind != "chronology.custody_audit"
        for artifact_id in store.iter_artifact_ids()
    )


def test_request_readback_failure_prevents_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful write return cannot stand in for exact persisted bytes."""
    from polisyos.runtime.quality.epoch_custody_audit import audit_epoch_custody

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    monkeypatch.setattr(store, "get_bytes", lambda artifact_id: b"corrupt")
    with pytest.raises(ValueError, match="epoch_custody_audit_readback_mismatch"):
        audit_epoch_custody(request=_request(), store=store)
    assert all(
        store.get_manifest(artifact_id).kind != "chronology.custody_audit"
        for artifact_id in store.iter_artifact_ids()
    )
