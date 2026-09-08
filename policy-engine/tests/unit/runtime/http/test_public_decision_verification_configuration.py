"""Exercise deployment trust loading through real report issuance and verification."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.runtime.http.services.public_decision_verification import (
    PublicDecisionVerificationError,
)
from polisyos.runtime.http.services.public_decision_verification_configuration import (
    build_public_decision_verification_service,
)

ISSUED_AT = datetime(2026, 9, 7, 12, tzinfo=UTC)
PURPOSE = "public_decision_verification_record"


@pytest.fixture
def deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Write a deployment-owned policy and real signing keys with private permissions."""
    pair = artifacts.KeyPair.generate()
    private_path = tmp_path / "private.pem"
    private_path.write_bytes(pair.private_pem())
    private_path.chmod(0o600)
    (tmp_path / "public.pem").write_bytes(pair.public_pem())
    config_path = tmp_path / "verification.json"
    config = {
        "issuer_id": "policyos-verification-reports",
        "private_key_path": "private.pem",
        "trusted_keys": [
            {
                "public_key_path": "public.pem",
                "issuer_id": "policyos-verification-reports",
                "purposes": [PURPOSE],
                "revoked": False,
            }
        ],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("POLISYOS_PUBLIC_VERIFICATION_CONFIG", str(config_path))
    return tmp_path, config_path, config


def test_configured_keys_issue_and_reverify_persisted_report(deployment):
    root, _, _ = deployment
    service = build_public_decision_verification_service(cas_root=root / "artifacts")
    document = {"title": "Candidate public projection", "limits": ["not promoted"]}
    record_id = service.issue(
        decision_id="decision-configuration",
        public_document=document,
        issued_at=ISSUED_AT,
    )

    reloaded = build_public_decision_verification_service(cas_root=root / "artifacts")
    result = reloaded.verify(record_id)
    assert reloaded.issued_record_ids() == (record_id,)
    assert result.report_authentication == "verified"
    assert result.cryptographic_signature == "valid"
    assert result.report_key_status == "trusted"
    assert result.issuer_id == "policyos-verification-reports"
    assert result.decision_id == "decision-configuration"
    assert result.public_document == document
    assert result.issued_at == ISSUED_AT
    assert result.promoted_record is None
    assert set(result.dimensions.model_dump().values()) == {"not_established"}
    assert result == service.verify(record_id)


def test_absent_configuration_cannot_issue_but_rejects_client_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("POLISYOS_PUBLIC_VERIFICATION_CONFIG", raising=False)
    service = build_public_decision_verification_service(cas_root=tmp_path)
    with pytest.raises(PublicDecisionVerificationError) as error:
        service.issue(
            decision_id="decision-unconfigured",
            public_document={"title": "Candidate"},
            issued_at=ISSUED_AT,
        )
    assert error.value.code == "verification_issuer_not_configured"
    assert service.issued_record_ids() == ()
    result = service.verify("browser_payload.browser_hash")
    assert result.report_authentication == "invalid"
    assert "client_token_not_server_issued" in result.reason_codes
    assert result.public_document is None


@pytest.mark.parametrize(
    ("scope", "field", "value"),
    [
        ("root", "promoted_record", {"verified": True}),
        ("key", "authority", "PUBLIC"),
        ("key", "revoked", "false"),
        ("key", "revoked", 0),
        ("root", "issuer_id", False),
        ("root", "trusted_keys", {}),
        ("key", "purposes", PURPOSE),
    ],
    ids=[
        "root-extra",
        "key-extra",
        "coerced-string-bool",
        "coerced-integer-bool",
        "issuer-type",
        "trust-list-type",
        "purposes-list-type",
    ],
)
def test_malformed_configuration_fails_before_issuing(deployment, scope, field, value):
    root, config_path, config = deployment
    target = config if scope == "root" else config["trusted_keys"][0]
    target[field] = value
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValidationError):
        build_public_decision_verification_service(cas_root=root / "artifacts")
    assert not (root / "artifacts" / "runtime" / "public-verification" / "issued").exists()


def test_readable_private_key_permissions_prevent_signer_loading(deployment):
    root, _, _ = deployment
    (root / "private.pem").chmod(0o644)
    with pytest.raises(ValueError, match="private key permissions invalid"):
        build_public_decision_verification_service(cas_root=root / "artifacts")
    assert not (root / "artifacts" / "runtime" / "public-verification" / "issued").exists()


@pytest.mark.parametrize("trust_change", ["absent", "issuer", "purpose", "key", "revoked"])
def test_configured_signer_requires_matching_issuer_key_and_purpose(deployment, trust_change):
    root, config_path, config = deployment
    key = config["trusted_keys"][0]
    if trust_change == "absent":
        config["trusted_keys"] = []
    elif trust_change == "issuer":
        key["issuer_id"] = "other-issuer"
    elif trust_change == "purpose":
        key["purposes"] = ["human_decision_custody"]
    elif trust_change == "key":
        (root / "public.pem").write_bytes(artifacts.KeyPair.generate().public_pem())
    else:
        key["revoked"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")
    service = build_public_decision_verification_service(cas_root=root / "artifacts")
    with pytest.raises(PublicDecisionVerificationError):
        service.issue(
            decision_id="decision-untrusted",
            public_document={"title": "Candidate"},
            issued_at=ISSUED_AT,
        )
    assert service.issued_record_ids() == ()
