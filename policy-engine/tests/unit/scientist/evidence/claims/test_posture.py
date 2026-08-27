"""Semantic tests for the DS11 trust-claim posture contract."""

from __future__ import annotations

import importlib
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.runtime.quality.claim_registry import normalize_runtime_claim_registry

_POSTURE_MODULE = "polisyos.scientist.evidence.claims.posture"


def _posture() -> Any:
    """Load the required C01 owner or fail at the intended missing seam."""
    try:
        return importlib.import_module(_POSTURE_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == _POSTURE_MODULE or (
            exc.name is not None and _POSTURE_MODULE.startswith(f"{exc.name}.")
        ):
            pytest.fail("C01 strict posture contract owner is absent")
        raise


def _predicate(posture: Any, kind: str, *, satisfied: bool = True) -> Any:
    return posture.SupportPredicate(
        kind=kind,
        satisfied=satisfied,
        establishment_class="independently_reconciled",
        evidence_refs=(f"evidence:{kind}",),
        issue_code=None if satisfied else f"DS11-{kind.upper()}-FAILED",
    )


@cache
def _strict_register(posture: Any) -> Any:
    repo_root = Path(__file__).resolve().parents[5]
    artifact = repo_root / "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"
    return posture.validate_posture_register(artifact.read_bytes())


def _derived_source_binding(register: Any, posture: Any) -> Any:
    return next(
        row.source_bindings[0]
        for row in register.claims
        if row.subject is not None and row.subject not in posture.FIXED_SEMANTIC_BINDING_COUNTS
    )


def test_blocked_vetoes_planned_and_supported() -> None:
    """Catch a composer mutation that lets a blocked arm lose its veto."""
    posture = _posture()
    assert posture.compose_effective_state(("supported", "planned", "blocked")) == "blocked"


def test_candidate_or_planned_never_composes_to_supported() -> None:
    """Catch a composer mutation that treats candidate or planned as support."""
    posture = _posture()
    assert posture.compose_effective_state(("candidate", "supported")) == "blocked"
    assert (
        posture.compose_effective_state(
            ("planned", "supported"),
            planned_owner="team-runtime",
            closure_signal="uv run pytest tests/integration/test_custody.py -q",
        )
        == "planned"
    )
    assert posture.compose_effective_state(("planned", "supported")) == "blocked"


def test_planned_requires_only_the_content_bound_executable_commitment_basis() -> None:
    """Keep support-only jurisdiction, review, and evidence gates out of planning."""
    posture = _posture()
    register = _strict_register(posture)
    base = _derived_source_binding(register, posture)
    owner = posture.OwnerBinding(
        owner="team-example",
        basis="closure_commitment",
        source_ref=base.coordinate.path,
        establishment_class="recomputed",
    )
    planned_kinds = {
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "identity_boundary",
    }
    predicates = tuple(
        posture.SupportPredicate(
            kind=kind,
            satisfied=kind in planned_kinds,
            establishment_class=("recomputed" if kind in planned_kinds else "not_established"),
            evidence_refs=(),
            issue_code=None if kind in planned_kinds else f"DS11-{kind.upper()}-NOT-REQUIRED",
        )
        for kind in posture.REQUIRED_SUPPORT_PREDICATES
    )
    planned = base.model_copy(
        update={
            "source_state": "planned",
            "owner": owner,
            "jurisdiction": None,
            "jurisdiction_establishment": "not_established",
            "review_on": None,
            "review_due": None,
            "evidence_refs": (),
            "evidence_bindings": (),
            "predicates": predicates,
            "closure_signal": "uv run pytest tests/example/test_growth.py -q",
        }
    )
    state, blockers, _ = posture.evaluate_claim_posture(
        (planned,),
        subject=base.subject,
        family=base.family,
        register_as_of=date(2026, 8, 26),
        identity_boundary=register.identity_boundary,
        admitted_sources=register.admitted_sources,
        admitted_verifiers=register.admitted_verifiers,
    )
    assert state == "planned"
    assert blockers == ()

    second_arm = planned.model_copy(
        update={"owner": owner.model_copy(update={"owner": "team-second"})}
    )
    incomplete_arm = second_arm.model_copy(update={"closure_signal": None})
    state, blockers, _ = posture.evaluate_claim_posture(
        (planned, incomplete_arm),
        subject=base.subject,
        family=base.family,
        register_as_of=date(2026, 8, 26),
        identity_boundary=register.identity_boundary,
        admitted_sources=register.admitted_sources,
        admitted_verifiers=register.admitted_verifiers,
    )
    assert state == "blocked"
    assert "DS11-PLANNED-CLOSURE-SIGNAL-MISSING" in blockers
    with pytest.raises(ValueError, match=r"planned|closure"):
        posture.ClaimSourceBinding.model_validate(incomplete_arm.model_dump(mode="json"))


def test_admitted_verifier_scope_cannot_be_rebound_to_a_novel_subject() -> None:
    """Bind evidence authority to typed subject/purpose scope, not verifier names."""
    posture = _posture()
    register = _strict_register(posture)
    verifier = next(
        item
        for item in register.admitted_verifiers
        if item.verifier_kind == "identity_boundary_derivation"
    )
    assert verifier.subject_scope == ("system_identity",)
    assert "universal_custody_commitment" in verifier.prohibited_subjects

    base = next(row for row in register.claims if row.subject == "system_identity").source_bindings[
        0
    ]
    evidence = base.evidence_bindings[0].model_copy(
        update={
            "ref": verifier.content_ref,
            "content_digest": verifier.content_digest,
            "subject_binding": "novel_unrelated_subject",
            "verifier_ref": verifier.ref,
            "verifier_provenance_ref": verifier.provenance_ref,
        }
    )
    forged = base.model_copy(
        update={
            "subject": "novel_unrelated_subject",
            "authoritative_for": ("novel_unrelated_subject",),
            "authority_purpose": "novel_unrelated_subject",
            "evidence_refs": (evidence.ref,),
            "evidence_bindings": (evidence,),
        }
    )
    facts = posture._recomputed_binding_facts(
        forged,
        register_as_of=date(2026, 8, 26),
        identity_boundary=register.identity_boundary,
        admitted_sources=register.admitted_sources,
        admitted_verifiers=register.admitted_verifiers,
    )
    assert facts["content_bound_evidence"][0] is False


def test_support_requires_every_independently_established_predicate() -> None:
    """Catch a P37 mutation that lets supplied or missing predicates support."""
    posture = _posture()
    required = tuple(_predicate(posture, kind) for kind in posture.REQUIRED_SUPPORT_PREDICATES)
    assert (
        posture.compose_effective_state(("supported",), support_predicates=required) == "supported"
    )
    for establishment_class in (
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ):
        mutated = required[0].model_copy(update={"establishment_class": establishment_class})
        assert (
            posture.compose_effective_state(
                ("supported",), support_predicates=(mutated, *required[1:])
            )
            == "blocked"
        )


def test_empty_predicates_and_keep_marker_remove_property_probes_block() -> None:
    """Catch marker-only support when a required authority property is removed."""
    posture = _posture()
    assert posture.compose_effective_state(("supported",), support_predicates=()) == "blocked"
    register = _strict_register(posture)
    base = next(row for row in register.claims if row.subject == "system_identity").source_bindings[
        0
    ]
    predicates = tuple(_predicate(posture, kind) for kind in posture.REQUIRED_SUPPORT_PREDICATES)
    owner = posture.OwnerBinding(
        owner="team-example",
        basis="package_contract",
        source_ref="architecture/packages/example.toml",
        establishment_class="recomputed",
    )
    verifier = next(
        item
        for item in register.admitted_verifiers
        if item.verifier_kind == "identity_boundary_derivation"
    )
    evidence = base.evidence_bindings[0].model_copy(
        update={
            "ref": verifier.content_ref,
            "content_digest": verifier.content_digest,
            "subject_binding": "system_identity",
            "verifier_ref": verifier.ref,
            "verifier_provenance_ref": verifier.provenance_ref,
        }
    )
    supported = base.model_copy(
        update={
            "source_state": "supported",
            "subject": "system_identity",
            "authoritative_for": ("system_identity",),
            "authority_purpose": "system_identity",
            "owner": owner,
            "jurisdiction": "non_jurisdiction_specific",
            "jurisdiction_establishment": "recomputed",
            "review_on": date(2026, 8, 1),
            "review_due": date(2026, 9, 1),
            "evidence_refs": (evidence.ref,),
            "evidence_bindings": (evidence,),
            "limitation_refs": (),
            "predicates": predicates,
        }
    )
    assert (
        posture.evaluate_claim_posture(
            (supported,),
            subject="system_identity",
            family="methodology",
            register_as_of=date(2026, 8, 26),
            identity_boundary=register.identity_boundary,
            admitted_sources=register.admitted_sources,
            admitted_verifiers=register.admitted_verifiers,
        )[0]
        == "supported"
    )
    removals = (
        {"owner": owner.model_copy(update={"owner": None})},
        {"jurisdiction": None},
        {"review_due": date(2000, 1, 1)},
        {"evidence_bindings": (), "evidence_refs": ()},
        {"identity_boundary_ref": "docs/not-admitted.md"},
        {"resolution": "runtime_bound"},
    )
    for update in removals:
        state, blockers, _ = posture.evaluate_claim_posture(
            (supported.model_copy(update=update),),
            subject="system_identity",
            family="methodology",
            register_as_of=date(2026, 8, 26),
            identity_boundary=register.identity_boundary,
            admitted_sources=register.admitted_sources,
            admitted_verifiers=register.admitted_verifiers,
        )
        assert state == "blocked"
        assert blockers


def test_grounded_performance_requires_governed_evidence_and_prerequisite() -> None:
    """Catch substitution of admitted non-performance evidence for a missing basis."""
    posture = _posture()
    required = tuple(_predicate(posture, kind) for kind in posture.REQUIRED_SUPPORT_PREDICATES)
    assert (
        posture.compose_effective_state(
            ("supported",), support_predicates=required, family="grounded_performance"
        )
        == "blocked"
    )
    register = _strict_register(posture)
    verifier = register.admitted_verifiers[0]
    relabeled_nonperformance = posture.EvidenceBinding(
        ref=verifier.content_ref,
        content_digest=verifier.content_digest,
        subject_binding="grounded_performance",
        verifier_ref=verifier.ref,
        verifier_provenance_ref=verifier.provenance_ref,
        establishment_class="independently_reconciled",
        source_as_of=date(2026, 8, 26),
        supersession_ref=None,
    )
    assert (
        posture.compose_effective_state(
            ("supported",),
            support_predicates=required,
            family="grounded_performance",
            governed_performance_prerequisite=relabeled_nonperformance,
            admitted_sources=register.admitted_sources,
            admitted_verifiers=register.admitted_verifiers,
            register_as_of=date(2026, 8, 26),
        )
        == "blocked"
    )


def test_strict_register_recomputes_state_digest_and_rejects_extra_fields() -> None:
    """Catch sparse factories, authored status upgrades, and permissive artifacts."""
    posture = _posture()
    register = _strict_register(posture)
    assert register.schema_version == "policyos.trust.claim_posture_register.v1"
    source_index = next(
        index
        for index, row in enumerate(register.claims)
        if row.subject not in posture.FIXED_SEMANTIC_BINDING_COUNTS
    )
    assert register.claims[source_index].effective_state == "blocked"
    assert register.payload_digest.startswith("sha256:")
    strict_payload = register.model_dump(mode="json")
    posture.validate_posture_register(strict_payload)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        posture.validate_posture_register({**strict_payload, "unexpected": True})
    strict_payload["claims"][source_index]["effective_state"] = "supported"
    with pytest.raises(
        (ValidationError, ValueError),
        match=r"effective|digest|supported|authored claim rows|recomputation",
    ):
        posture.validate_posture_register(strict_payload)


def test_source_inventory_is_admitted_and_coordinate_bound() -> None:
    """Reject inventory rows or coordinates detached from admitted source bytes."""
    posture = _posture()
    register = _strict_register(posture)
    admitted = {member.path: member.content_digest for member in register.admitted_sources}
    row = next(item for item in register.source_inventory if item.declaration_coordinates)

    with pytest.raises(ValueError, match="admitted source membership"):
        posture._validate_source_inventory_basis(
            (row.model_copy(update={"path": "src/polisyos/fabricated.py"}),), admitted
        )

    first = row.declaration_coordinates[0]
    detached = row.model_copy(
        update={
            "declaration_coordinates": (
                first.model_copy(update={"path": "src/polisyos/fabricated.py"}),
                *row.declaration_coordinates[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="coordinate escapes"):
        posture._validate_source_inventory_basis((detached,), admitted)


def test_posture_artifact_cannot_enter_runtime_claim_registry() -> None:
    """Catch posture metadata discharging real claim-local runtime axes."""
    posture = _posture()
    payload = _strict_register(posture).model_dump(mode="json")
    payload["claims"][0]["claim_id"] = "final-runtime-claim"
    payload["claims"][0]["effective_state"] = "supported"
    registry = normalize_runtime_claim_registry(
        payload, claims=[{"claim_id": "final-runtime-claim", "major": True}]
    )
    assert registry["status"] == "fail"
    issue_codes = {issue["code"] for issue in registry["issues"]}
    assert {
        "runtime_claim_registry_scenario_requirement_refs_missing",
        "runtime_claim_registry_data_refs_missing",
        "runtime_claim_registry_selected_norm_refs_missing",
        "runtime_claim_registry_method_output_refs_missing",
        "runtime_claim_registry_portfolio_refs_missing",
        "runtime_claim_registry_argument_refs_missing",
        "runtime_claim_registry_warrant_refs_missing",
        "runtime_claim_registry_rebuttal_refs_missing",
        "runtime_claim_registry_counter_evidence_refs_missing",
        "runtime_claim_registry_accepted_deficit_refs_missing",
    } <= issue_codes
