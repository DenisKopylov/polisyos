"""Behavioral controls for server-issued public verification records."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.runtime.http.services.public_decision_verification import (
    PublicDecisionVerificationError,
    PublicDecisionVerificationService,
    PublicDecisionVerificationTrustedKey,
)
from polisyos.runtime.http.services.public_decision_verification_contracts import (
    PublicDecisionVerificationRecord,
    PublicDecisionVerificationResponse,
)

ISSUED_AT = datetime(2026, 9, 7, 12, tzinfo=UTC)
PURPOSE = "public_decision_verification_record"


@pytest.fixture
def issued_service(tmp_path: Path):
    """Build real CAS and trusted keys, then issue one server record."""
    pair = artifacts.KeyPair.generate()
    signer = artifacts.Ed25519Signer(pair.private_key)
    trust = PublicDecisionVerificationTrustedKey(
        public_key_pem=pair.public_pem(),
        issuer_id="policyos-verifier",
        purposes=frozenset({PURPOSE}),
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    kwargs = {
        "store": store,
        "index_root": tmp_path / "issued",
        "issuer_id": "policyos-verifier",
        "signer": signer,
        "trusted_keys": (trust,),
    }
    service = PublicDecisionVerificationService(**kwargs)
    document = {"title": "Candidate projection", "score": 1.25, "limitation": None}
    record_id = service.issue(
        decision_id="decision-1", public_document=document, issued_at=ISSUED_AT
    )
    return service, kwargs, trust, record_id, document


def _entry(kwargs, record_id):
    return json.loads((kwargs["index_root"] / f"{record_id}.json").read_bytes())


def _record_artifact(kwargs, record_id):
    return artifacts.ArtifactID.model_validate(_entry(kwargs, record_id)["record_artifact_ref"])


def _replace_bytes(path: Path, data: bytes) -> None:
    path.chmod(0o644)
    path.write_bytes(data)


def test_issued_record_authenticates_exact_document_without_decision_authority(issued_service):
    service, kwargs, _, record_id, document = issued_service
    result = service.verify(record_id)
    assert result.report_authentication == "verified"
    assert result.cryptographic_signature == "valid"
    assert result.report_key_status == "trusted"
    assert result.public_document == document
    assert result.decision_id == "decision-1"
    assert result.issuer_id == "policyos-verifier"
    assert result.issued_at == ISSUED_AT
    assert result.promoted_record is None
    assert set(result.dimensions.model_dump().values()) == {"not_established"}
    assert result.reason_codes == ("promoted_public_record_not_established",)
    assert result.public_document_digest == _entry(kwargs, record_id)["public_document_digest"]
    assert "verified" not in result.model_dump()


def test_persisted_index_survives_new_service_and_reads_never_resign(issued_service):
    service, kwargs, _, record_id, _ = issued_service
    artifact_id = _record_artifact(kwargs, record_id)
    before = kwargs["store"].get_signature(artifact_id)
    first = service.verify(record_id)
    reloaded = PublicDecisionVerificationService(**kwargs)
    assert reloaded.verify(record_id) == first
    assert reloaded.verify(record_id) == first
    assert kwargs["store"].get_signature(artifact_id) == before


@pytest.mark.parametrize("tamper", ["record", "document", "manifest", "signature", "unsigned"])
def test_tampered_persisted_evidence_never_returns_document(issued_service, tamper):
    service, kwargs, _, record_id, _ = issued_service
    store = kwargs["store"]
    artifact_id = _record_artifact(kwargs, record_id)
    blob_path, manifest_path = store.get_paths(artifact_id)
    if tamper == "record":
        _replace_bytes(blob_path, store.get_bytes(artifact_id) + b" ")
    elif tamper == "document":
        doc_id = artifacts.ArtifactID.model_validate(
            _entry(kwargs, record_id)["public_document_digest"]
        )
        doc_path, _ = store.get_paths(doc_id)
        _replace_bytes(doc_path, b'{"title":"forged"}')
    elif tamper == "manifest":
        _replace_bytes(manifest_path, manifest_path.read_bytes() + b" ")
    elif tamper == "unsigned":
        blob_path.with_suffix(".sig").unlink()
    else:
        signature = store.get_signature(artifact_id)
        assert signature is not None
        store.put_signature(artifact_id, signature.model_copy(update={"signature_hex": "00" * 64}))
    result = service.verify(record_id)
    assert result.report_authentication != "verified"
    assert result.public_document is None
    assert "promoted_public_record_not_established" in result.reason_codes


@pytest.mark.parametrize("policy_change", ["untrusted", "wrong_issuer", "wrong_purpose"])
def test_missing_key_or_issuer_purpose_trust_never_authenticates(issued_service, policy_change):
    _, kwargs, trust, record_id, _ = issued_service
    changed = {
        "untrusted": (),
        "wrong_issuer": (replace(trust, issuer_id="other-issuer"),),
        "wrong_purpose": (replace(trust, purposes=frozenset({"human_decision_custody"})),),
    }[policy_change]
    result = PublicDecisionVerificationService(**{**kwargs, "trusted_keys": changed}).verify(
        record_id
    )
    assert result.report_authentication != "verified"
    assert result.public_document is None


@pytest.mark.parametrize("corrupt", [False, True])
def test_revocation_preserves_cryptographic_distinction_and_issued_bytes(issued_service, corrupt):
    service, kwargs, trust, record_id, _ = issued_service
    record_ref = _record_artifact(kwargs, record_id)
    assert service.verify(record_id).report_authentication == "verified"
    before = kwargs["store"].get_bytes(record_ref)
    if corrupt:
        signature = kwargs["store"].get_signature(record_ref)
        kwargs["store"].put_signature(
            record_ref, signature.model_copy(update={"signature_hex": "00" * 64})
        )
    revoked = PublicDecisionVerificationService(
        **{**kwargs, "trusted_keys": (replace(trust, revoked=True),)}
    )
    result = revoked.verify(record_id)
    assert result.cryptographic_signature == ("invalid" if corrupt else "valid")
    assert result.report_key_status == "revoked"
    assert result.report_authentication == ("invalid" if corrupt else "not_established")
    assert result.dimensions.current_authority == "not_established"
    assert result.public_document is None
    assert kwargs["store"].get_bytes(record_ref) == before


def test_unsigned_sidecar_hints_do_not_supply_identity_or_time(issued_service):
    service, kwargs, _, record_id, _ = issued_service
    artifact_id = _record_artifact(kwargs, record_id)
    signature = kwargs["store"].get_signature(artifact_id)
    kwargs["store"].put_signature(
        artifact_id,
        signature.model_copy(
            update={"signer_identity": "forged", "signed_at": datetime(1900, 1, 1, tzinfo=UTC)}
        ),
    )
    result = service.verify(record_id)
    assert result.report_authentication == "verified"
    assert result.issuer_id == "policyos-verifier"
    assert result.issued_at == ISSUED_AT


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("record_id", "pvr_" + "x" * 32),
        ("decision_id", "other-decision"),
        ("issuer_id", "other-issuer"),
        ("signing_key_id", "wrong-key"),
        ("purpose", "public_decision_issuance"),
        ("schema_version", "unknown.v9"),
        ("rule_version", "unknown.v9"),
        ("public_document_digest", "sha256:" + "1" * 64),
        ("publication_class", "public_decision"),
        ("promoted_record", {"status": "promoted"}),
    ],
)
def test_even_valid_signature_cannot_bypass_signed_record_bindings(issued_service, field, value):
    service, kwargs, _, record_id, _ = issued_service
    store = kwargs["store"]
    record_ref = _record_artifact(kwargs, record_id)
    payload = json.loads(store.get_bytes(record_ref))
    payload[field] = value
    replaced = store.put_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
        artifacts.ArtifactWriteOptions(
            kind="runtime.public_decision_verification_record",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.public_decision_verification_record", version="1"
            ),
        ),
    )
    store.sign_artifact(replaced.artifact_id, kwargs["signer"])
    entry = _entry(kwargs, record_id)
    entry["record_artifact_ref"] = str(replaced.artifact_id)
    (kwargs["index_root"] / f"{record_id}.json").write_text(json.dumps(entry))
    result = service.verify(record_id)
    assert result.report_authentication == "invalid"
    assert result.public_document is None


@pytest.mark.parametrize("field", tuple(PublicDecisionVerificationRecord.model_fields))
def test_missing_signed_field_cannot_be_supplied_by_a_model_default(issued_service, field):
    service, kwargs, _, record_id, _ = issued_service
    store = kwargs["store"]
    payload = json.loads(store.get_bytes(_record_artifact(kwargs, record_id)))
    del payload[field]
    replaced = store.put_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
        artifacts.ArtifactWriteOptions(
            kind="runtime.public_decision_verification_record",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.public_decision_verification_record", version="1"
            ),
        ),
    )
    store.sign_artifact(replaced.artifact_id, kwargs["signer"])
    entry = _entry(kwargs, record_id)
    entry["record_artifact_ref"] = str(replaced.artifact_id)
    (kwargs["index_root"] / f"{record_id}.json").write_text(json.dumps(entry))
    result = service.verify(record_id)
    assert result.report_authentication == "invalid"
    assert result.public_document is None


@pytest.mark.parametrize(
    ("record_id", "reason"),
    [
        ("pvr_" + "z" * 32, "record_not_issued"),
        ("eyJydW4iOiIxIn0.deadbeef", "client_token_not_server_issued"),
        ("../../private", "record_not_issued"),
    ],
)
def test_unknown_and_browser_forged_ids_are_specific_nonreceipts(issued_service, record_id, reason):
    service, _, _, _, _ = issued_service
    result = service.verify(record_id)
    assert result.report_authentication == (
        "invalid" if reason == "client_token_not_server_issued" else "not_established"
    )
    assert reason in result.reason_codes
    assert result.public_document is None


def test_arbitrary_cas_record_is_not_an_issued_public_url(issued_service):
    service, kwargs, _, record_id, _ = issued_service
    result = service.verify(str(_record_artifact(kwargs, record_id)))
    assert result.report_authentication == "not_established"
    assert "record_not_issued" in result.reason_codes


@pytest.mark.parametrize("missing", ["signer", "trust", "purpose", "revoked"])
def test_issue_fails_before_index_without_complete_issuer_trust(issued_service, missing):
    _, kwargs, trust, _, document = issued_service
    changes = {
        "signer": {"signer": None},
        "trust": {"trusted_keys": ()},
        "purpose": {"trusted_keys": (replace(trust, purposes=frozenset()),)},
        "revoked": {"trusted_keys": (replace(trust, revoked=True),)},
    }[missing]
    before = sorted(kwargs["index_root"].iterdir())
    service = PublicDecisionVerificationService(**{**kwargs, **changes})
    with pytest.raises(PublicDecisionVerificationError):
        service.issue(decision_id="decision-2", public_document=document, issued_at=ISSUED_AT)
    assert sorted(kwargs["index_root"].iterdir()) == before


def test_reissuing_same_document_creates_distinct_immutable_records(issued_service):
    service, kwargs, _, record_id, document = issued_service
    before = service.verify(record_id)
    second = service.issue(decision_id="decision-1", public_document=document, issued_at=ISSUED_AT)
    assert second != record_id
    assert service.verify(record_id) == before
    assert service.verify(second).report_authentication == "verified"
    assert _record_artifact(kwargs, second) != _record_artifact(kwargs, record_id)


def test_issued_index_enumeration_checks_each_actual_record(issued_service):
    service, kwargs, _, record_id, document = issued_service
    second = service.issue(decision_id="decision-2", public_document=document, issued_at=ISSUED_AT)
    assert service.issued_record_ids() == tuple(sorted((record_id, second)))
    bad = _entry(kwargs, record_id)
    bad["record_id"] = second
    (kwargs["index_root"] / f"{record_id}.json").write_text(json.dumps(bad))
    with pytest.raises(PublicDecisionVerificationError, match="issuance_index_invalid"):
        service.issued_record_ids()
    assert service.verify(record_id).report_authentication == "invalid"


def test_index_failure_never_returns_an_issued_identifier(issued_service):
    _, kwargs, _, _, document = issued_service
    bad_root = kwargs["index_root"] / "not-a-directory"
    bad_root.write_text("unavailable")
    service = PublicDecisionVerificationService(**{**kwargs, "index_root": bad_root})
    with pytest.raises(PublicDecisionVerificationError, match="issuance_index_write_failed"):
        service.issue(decision_id="decision-2", public_document=document, issued_at=ISSUED_AT)


@pytest.mark.parametrize("value", [float("nan"), {"not-json"}])
def test_issue_rejects_non_json_document_without_publishing(issued_service, value):
    service, _, _, _, _ = issued_service
    before = service.issued_record_ids()
    with pytest.raises(PublicDecisionVerificationError, match="public_document_invalid"):
        service.issue(
            decision_id="decision-2", public_document={"value": value}, issued_at=ISSUED_AT
        )
    assert service.issued_record_ids() == before


def test_response_uses_captured_document_bytes_even_if_store_changes_after_read(issued_service):
    service, kwargs, _, record_id, document = issued_service
    store = kwargs["store"]
    original_read = store.get_bytes
    doc_ref = _entry(kwargs, record_id)["public_document_digest"]

    def read_then_corrupt(artifact_id):
        captured = original_read(artifact_id)
        if str(artifact_id) == doc_ref:
            path, _ = store.get_paths(artifacts.ArtifactID.model_validate(doc_ref))
            _replace_bytes(path, b'{"title":"forged after read"}')
        return captured

    store.get_bytes = read_then_corrupt
    result = service.verify(record_id)
    assert result.report_authentication == "verified"
    assert result.public_document == document
    assert service.verify(record_id).public_document is None


@pytest.mark.parametrize(
    "invalid",
    [b"bytes", (1, 2), {1, 2}, Decimal("1.1"), ISSUED_AT, {1: "integer key"}],
    ids=["bytes", "tuple", "set", "decimal", "datetime", "integer-key"],
)
def test_response_rejects_non_json_values_at_nested_depth(issued_service, invalid):
    service, _, _, record_id, _ = issued_service
    response = service.verify(record_id).model_dump()
    response["public_document"] = {"nested": [{"value": invalid}]}
    with pytest.raises(ValidationError):
        PublicDecisionVerificationResponse.model_validate(response)


def test_recursive_json_values_preserve_types_through_issuance_and_response(issued_service):
    service, _, _, _, _ = issued_service
    values = [None, True, False, 0, -123, 1.25, "π", [], {}]
    document = {"nested": [{"value": value} for value in values]}
    record_id = service.issue(
        decision_id="recursive-json", public_document=document, issued_at=ISSUED_AT
    )
    response = service.verify(record_id)
    assert response.report_authentication == "verified"
    assert response.public_document == document
    assert [type(item["value"]) for item in response.public_document["nested"]] == [
        type(value) for value in values
    ]
