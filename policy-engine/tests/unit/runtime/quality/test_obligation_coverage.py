"""Red-first semantic boundary tests for DS17 obligation coverage.

These C00 witnesses invoke the public C01 coverage contract inside their test
bodies so collection stays independent of the unimplemented module. An empty
module cannot satisfy them: each test exercises a concrete semantic mutation.
"""

from __future__ import annotations

from importlib import import_module

import pytest

_SCOPE_ID = "confidence-risk-scope://ds17/red"
_ASSESSMENT_KEY = "assessment://ds17/red"


def _coverage_module():
    """Load the C01 owner only while executing a C00 red witness."""
    return import_module("polisyos.runtime.quality.obligation_coverage")


def _surface_module():
    """Load the C01 amount owner only while executing its red witness."""
    return import_module("polisyos.runtime.quality.confidence_ledger_surface")


def _canonical_registry():
    """Resolve the planned amount source from the canonical N11 registry only."""
    from pathlib import Path

    from polisyos.runtime.quality.confidence_ledger import ConfidenceLedgerRegistry
    from tools.quality.validation.check_layer3_gy_confidence_ledger import (
        FrozenConfidenceLedgerContract,
    )

    contract = FrozenConfidenceLedgerContract.model_validate_json(
        Path("architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json").read_text()
    )
    projection = contract.registry_projection
    return ConfidenceLedgerRegistry(
        schema_version=projection.registry_schema_version,
        policy=projection.policy,
        schedule_profiles=projection.schedule_profiles,
        obligation_pools=projection.obligation_pools,
        proof_profiles=projection.proof_profiles,
        instruments=projection.instruments,
        certificate_class_routes=projection.certificate_class_routes,
    )


def _dump(value: object) -> dict[str, object]:
    """Require a strict DTO result instead of accepting a shaped dictionary."""
    model_dump = value.model_dump  # type: ignore[attr-defined]
    return model_dump(mode="json")


def _open_world_envelope(coverage):
    """Construct the canonical v1 negative envelope through its planned producer."""
    return coverage.build_coverage_envelope(
        scope_id=_SCOPE_ID,
        assessment_key=_ASSESSMENT_KEY,
        unknown_remainder="unresolved obligation remainder",
        admitted_witnesses=(),
    )


def test_every_delta_amount_requires_the_coverage_envelope_ref_and_rider() -> None:
    """Reject a delta amount after removing its envelope reference or either rider."""
    coverage = _coverage_module()
    surface = _surface_module()
    envelope = _open_world_envelope(coverage)
    envelope_payload = _dump(envelope)
    registry = _canonical_registry()
    bound = surface.build_conditional_delta_amount(registry=registry, envelope=envelope)
    assert _dump(bound)["coverage_envelope_ref"] == envelope_payload["envelope_ref"]
    valid_amount = _dump(bound)
    for missing_key in (
        "coverage_envelope_ref",
        "declared_set_rider",
        "locality_rider",
    ):
        mutated = {key: value for key, value in valid_amount.items() if key != missing_key}
        with pytest.raises((TypeError, ValueError), match=r"coverage|rider|DS17"):
            surface.bind_conditional_delta_amount(
                amount=mutated,
                envelope=envelope,
                registry=registry,
            )


def test_coverage_assessment_moves_on_admitted_witness() -> None:
    """Move only on a resolved exact-scope witness; reject a shaped stand-in."""
    coverage = _coverage_module()
    baseline = _open_world_envelope(coverage)
    assert _dump(baseline)["assessment"] == "open_world_unresolved"

    witness = coverage.AdmittedCoverageWitness(
        receipt_ref="coverage-witness://ds17/concrete-omission",
        assessment_key=_ASSESSMENT_KEY,
        scope_id=_SCOPE_ID,
        content_hash="sha256:" + "1" * 64,
        verifier_id="test.ds17.coverage-witness.v1",
    )
    moved = coverage.build_coverage_envelope(
        scope_id=_SCOPE_ID,
        assessment_key=_ASSESSMENT_KEY,
        unknown_remainder="unresolved obligation remainder",
        admitted_witnesses=(witness,),
    )
    moved_payload = _dump(moved)
    assert moved_payload["assessment"] == "known_incomplete"
    assert moved_payload["witness_refs"] == ["coverage-witness://ds17/concrete-omission"]

    with pytest.raises((TypeError, ValueError), match=r"witness|admitted|DS17"):
        coverage.build_coverage_envelope(
            scope_id=_SCOPE_ID,
            assessment_key=_ASSESSMENT_KEY,
            unknown_remainder="unresolved obligation remainder",
            admitted_witnesses=({"receipt_ref": "coverage-witness://shaped"},),
        )


def test_negative_coverage_cannot_be_rescued_by_claim_narrowing() -> None:
    """Keep the same negative action blocked when only its displayed claim narrows."""
    coverage = _coverage_module()
    envelope = _open_world_envelope(coverage)

    original = coverage.evaluate_protected_action(
        envelope=envelope,
        action_id="action://ds17/original",
        presented_claim_scope="all declared obligations",
    )
    narrowed = coverage.evaluate_protected_action(
        envelope=envelope,
        action_id="action://ds17/original",
        presented_claim_scope="one displayed obligation class",
    )
    assert _dump(original)["status"] == "blocked"
    assert _dump(narrowed)["status"] == "blocked"
    assert _dump(narrowed)["action_id"] == "action://ds17/original"
