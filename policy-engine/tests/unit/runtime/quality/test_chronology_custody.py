"""Behavioral tests for the production epoch custody composition."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from polisyos.core.artifacts import ArtifactID, ArtifactRef, ArtifactWriteOptions
from polisyos.core.contracts.chronology import AnchorAcceptanceRequest, ChronologyProofDomain


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _ref(label: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(_digest(label)),
        kind="fixture",
        media_type="application/octet-stream",
    )


def test_production_provider_reports_both_unappointed_roles() -> None:
    """An absent institutional appointment must never become a local positive."""
    from polisyos.runtime.quality.chronology_custody import (
        build_production_epoch_anchor_custody_provider,
    )

    provider = build_production_epoch_anchor_custody_provider()
    result = provider.evaluate_acceptance_and_custody(
        request=AnchorAcceptanceRequest(
            bundle_ref=_ref("bundle"),
            expected_domain=ChronologyProofDomain(
                format="polisyos.chronology.full-prefix.v1",
                profile="full_prefix_canon_json_0_2_0_sha256_256_v1",
                proof_domain="epoch",
                family="epoch",
                scope_ref=_digest("scope"),
                authority_purpose="publication",
            ),
            native_reconciliation_ref=_ref("reconciliation"),
            authority_purpose="publication",
            requested_query_context_ref=_digest("query"),
            asserted_prior_acceptance_record_refs=(),
        )
    )
    assert result.status == "limited"
    assert result.acceptance.status == "not_established"
    assert result.retention.status == "not_established"


def test_production_composition_has_one_noninjectable_service_constructor() -> None:
    """A caller-supplied resolver must have no production route into the gate."""
    product_root = Path(__file__).parents[4] / "src" / "polisyos"
    calls: list[tuple[Path, int]] = []
    injectable: list[tuple[Path, int]] = []
    for source in product_root.rglob("*.py"):
        tree = ast.parse(source.read_text("utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function = node.func
                name = function.id if isinstance(function, ast.Name) else ""
                if name == "EpochAnchorCustodyService":
                    calls.append((source, node.lineno))
            if isinstance(node, ast.arg):
                annotation = ast.unparse(node.annotation) if node.annotation else ""
                if any(
                    marker in annotation
                    for marker in (
                        "EpochAnchorCustodyService",
                        "EpochAnchorAppointmentResolver",
                        "EpochAnchorAuthorityRegistry",
                    )
                ):
                    injectable.append((source, node.lineno))
    assert len(calls) == 1
    assert calls[0][0].name == "chronology_custody.py"
    assert injectable == []


def test_internal_service_is_not_reexported_from_core() -> None:
    """The public facade exposes outcomes, never an injectable service."""
    import polisyos.core as core

    assert hasattr(core, "AnchorCustodyVerification")
    assert not hasattr(core, "EpochAnchorCustodyService")


def test_appointed_service_verifies_both_roles_from_real_bytes(tmp_path: Path) -> None:
    """The generic consumer must do work when test-only owners are appointed."""
    from tests._helpers.chronology_qualification import (
        AppointedAnchorFixture,
        build_appointed_anchor_service,
    )

    fixture = AppointedAnchorFixture(tmp_path)
    result = build_appointed_anchor_service(fixture).evaluate_acceptance_and_custody(
        request=fixture.make_acceptance_request()
    )
    assert result.status == "verified"
    assert result.acceptance.status == "verified"
    assert result.retention.status == "verified"


def test_appointed_acceptance_rejects_ref_shaped_non_bundle_bytes(tmp_path: Path) -> None:
    """An appointed owner must run the real full-prefix verifier over loaded bytes."""
    from tests._helpers.chronology_qualification import (
        AppointedAnchorFixture,
        build_appointed_anchor_service,
    )

    fixture = AppointedAnchorFixture(tmp_path)
    request = fixture.make_acceptance_request()
    invalid_bundle_ref = fixture.store.put_bytes(
        b"not-a-full-prefix-bundle",
        ArtifactWriteOptions(
            kind="fixture.chronology.bundle",
            media_type="application/octet-stream",
        ),
    )
    result = build_appointed_anchor_service(fixture).evaluate_acceptance_and_custody(
        request=request.model_copy(update={"bundle_ref": invalid_bundle_ref})
    )

    assert result.status == "rejected"
    assert result.acceptance.status == "rejected"
    assert result.acceptance.rejections[0].code == "anchor_query_or_lineage_mismatch"


def test_appointed_acceptance_rejects_unreconciled_native_bytes(tmp_path: Path) -> None:
    """Authentic CAS bytes are not owner-qualified reconciliation evidence."""
    from tests._helpers.chronology_qualification import (
        AppointedAnchorFixture,
        build_appointed_anchor_service,
    )

    fixture = AppointedAnchorFixture(tmp_path)
    request = fixture.make_acceptance_request()
    forged_reconciliation_ref = fixture.store.put_bytes(
        b"caller-authored-reconciliation",
        ArtifactWriteOptions(
            kind="fixture.chronology.reconciliation",
            media_type="application/octet-stream",
        ),
    )
    result = build_appointed_anchor_service(fixture).evaluate_acceptance_and_custody(
        request=request.model_copy(update={"native_reconciliation_ref": forged_reconciliation_ref})
    )

    assert result.status == "rejected"
    assert result.acceptance.status == "rejected"
    assert result.acceptance.rejections[0].code == "anchor_query_or_lineage_mismatch"


def test_non_genesis_acceptance_runs_real_verifier_for_owner_derived_prefix(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    """A live lineage head must become an independently verified expected prefix."""
    from polisyos.core.security.full_prefix import FullPrefixVerifier
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    observed_prefixes: list[object] = []
    original = FullPrefixVerifier.verify_bundle

    def observe(self: object, bundle_bytes: bytes, **kwargs: object) -> object:
        observed_prefixes.append(kwargs.get("expected_prefix"))
        return original(self, bundle_bytes, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(FullPrefixVerifier, "verify_bundle", observe)  # type: ignore[attr-defined]
    fixture = AppointedAnchorFixture(tmp_path)
    fixture.build_acceptance(query_label="first")
    observed_prefixes.clear()
    fixture.build_acceptance(query_label="second")

    assert observed_prefixes
    assert any(prefix is not None for prefix in observed_prefixes)


def test_caller_prior_assertion_must_equal_owner_current_heads(tmp_path: Path) -> None:
    """A stale caller assertion cannot be silently replaced by owner lineage truth."""
    from tests._helpers.chronology_qualification import (
        AppointedAnchorFixture,
        build_appointed_anchor_service,
    )

    fixture = AppointedAnchorFixture(tmp_path)
    fixture.build_acceptance(query_label="first")
    stale_request = fixture.make_acceptance_request(query_label="second").model_copy(
        update={"asserted_prior_acceptance_record_refs": ()}
    )
    result = build_appointed_anchor_service(fixture).evaluate_acceptance_and_custody(
        request=stale_request
    )

    assert result.status == "rejected"
    assert result.acceptance.status == "rejected"
    assert result.acceptance.rejections[0].code == "anchor_query_or_lineage_mismatch"


def test_acceptance_only_preserves_verified_half_as_limited(tmp_path: Path) -> None:
    """An absent holder cannot erase independently verified acceptance evidence."""
    from tests._helpers.chronology_qualification import (
        AppointedAnchorFixture,
        build_appointed_anchor_service,
    )

    fixture = AppointedAnchorFixture(tmp_path)
    result = build_appointed_anchor_service(fixture, holder=False).evaluate_acceptance_and_custody(
        request=fixture.make_acceptance_request()
    )
    assert result.status == "limited"
    assert result.acceptance.status == "verified"
    assert result.retention.status == "not_established"


def test_holder_only_readback_preserves_verified_half_as_limited(tmp_path: Path) -> None:
    """A holder receipt remains evidence when no accepting consumer is appointed."""
    from tests._helpers.chronology_qualification import (
        AppointedAnchorFixture,
        build_appointed_anchor_service,
    )

    fixture = AppointedAnchorFixture(tmp_path)
    _, _, challenge, _ = fixture.build_retention()
    result = build_appointed_anchor_service(fixture, acceptance=False).evaluate_retained_challenge(
        challenge_record_ref=challenge.challenge_record_ref
    )
    assert result.status == "limited"
    assert result.acceptance.status == "not_established"
    assert result.retention.status == "verified"
