"""Semantic tests for the DS11 trust-claim posture contract."""

from __future__ import annotations

import importlib
from datetime import date
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


def _strict_register(posture: Any) -> Any:
    coordinate = posture.SourceCoordinate(
        path="src/polisyos/example.py",
        symbol="ExampleClaim",
        line=4,
        column=4,
        field_name="authoritative_for",
        use_kind="declaration",
    )
    member = posture.AdmittedSourceMember(
        path=coordinate.path,
        content_digest="sha256:" + "1" * 64,
    )
    receipt_kwargs = {
        "scanned_python_count": 1,
        "raw_candidate_count": 1,
        "exact_field_file_count": 1,
        "declaring_file_count": 1,
        "consuming_file_count": 0,
        "role_counts": {
            "declares_only": 1,
            "carries_only": 0,
            "consumes_only": 0,
            "declares_and_consumes": 0,
            "substring_collision": 0,
            "ambiguous": 0,
        },
        "direct_literal_site_count": 1,
        "direct_literal_file_count": 1,
        "direct_literal_subject_count": 1,
        "direct_empty_site_count": 0,
        "wrapper_literal_site_count": 1,
        "wrapper_literal_file_count": 1,
        "wrapper_literal_subject_count": 1,
        "may_not_use_for_raw_file_count": 1,
        "may_not_use_for_literal_site_count": 1,
        "may_not_use_for_literal_file_count": 1,
        "may_not_use_for_literal_subject_count": 1,
        "row_digest": "sha256:" + "2" * 64,
    }
    ast_receipt = posture.SourceDerivationReceipt(method="ast", **receipt_kwargs)
    token_receipt = posture.SourceDerivationReceipt(method="tokenize", **receipt_kwargs)
    literal = posture.LiteralSite(
        coordinate=coordinate,
        declaration_form="assignment",
        wrapper_kind="direct",
        values=("example_claim",),
        resolution="resolved",
    )
    denied_coordinate = coordinate.model_copy(update={"field_name": "may_not_use_for", "line": 5})
    denied = posture.LiteralSite(
        coordinate=denied_coordinate,
        declaration_form="assignment",
        wrapper_kind="direct",
        values=("publication_authority",),
        resolution="resolved",
    )
    inventory = posture.SourceInventoryRow(
        path=coordinate.path,
        content_digest=member.content_digest,
        role="declares_only",
        resolution="resolved",
        declaration_coordinates=(coordinate,),
        carrier_coordinates=(),
        consumer_coordinates=(),
        authoritative_sites=(literal,),
        forbidden_sites=(denied,),
        runtime_bound=False,
        issue_codes=(),
    )
    owner = posture.OwnerBinding(
        owner="team-example",
        basis="package_contract",
        source_ref="architecture/packages/example.toml",
        establishment_class="institutionally_supplied",
    )
    evidence = posture.EvidenceBinding(
        ref="cas:example-claim-evidence",
        content_digest="sha256:" + "8" * 64,
        subject_binding="example_claim",
        verifier_ref="verifier:independent",
        verifier_provenance_ref="provenance:independent",
        establishment_class="independently_reconciled",
        source_as_of=date(2026, 8, 20),
        supersession_ref=None,
    )
    predicates = (
        _predicate(posture, "content_bound_source"),
        _predicate(posture, "purpose_permission"),
        posture.SupportPredicate(
            kind="accountable_owner",
            satisfied=True,
            establishment_class="institutionally_supplied",
            evidence_refs=(owner.source_ref,),
            issue_code="DS11-GATE-PREDICATE-NOT-ESTABLISHED",
        ),
        _predicate(posture, "applicable_jurisdiction", satisfied=False),
        _predicate(posture, "current_review", satisfied=False),
        _predicate(posture, "content_bound_evidence", satisfied=False),
        _predicate(posture, "identity_boundary"),
        _predicate(posture, "no_blocker"),
    )
    source_binding = posture.ClaimSourceBinding(
        coordinate=coordinate,
        content_digest=member.content_digest,
        resolution="resolved",
        source_state="supported",
        subject="example_claim",
        family="methodology",
        authoritative_for=("example_claim",),
        may_not_use_for=("publication_authority",),
        authority_purpose="example_claim",
        owner=owner,
        jurisdiction=None,
        jurisdiction_establishment="not_established",
        review_on=None,
        review_due=None,
        source_as_of=date(2026, 8, 26),
        evidence_refs=(evidence.ref,),
        evidence_bindings=(evidence,),
        limitation_refs=("limitation:missing-independent-metadata",),
        prerequisite_refs=(),
        identity_boundary_ref="docs/system-design-decisions/policyos-identity-and-custody-boundary.md",
        declared_scope_assumption=None,
        supersedes_ref=None,
        superseded_by_ref=None,
        predicates=predicates,
        closure_signal=None,
    )
    anti_role = posture.AntiRoleBinding(
        role="administrator",
        display_label="administrator",
        source_path="docs/system-design-decisions/policyos-identity-and-custody-boundary.md",
        source_digest="sha256:" + "3" * 64,
        line=88,
        column=1,
    )
    identity = posture.IdentityBoundaryBinding(
        path=anti_role.source_path,
        content_digest=anti_role.source_digest,
        frontmatter_digest="sha256:" + "4" * 64,
        paragraph_digest="sha256:" + "5" * 64,
        paragraph_start_line=88,
        paragraph_end_line=90,
        anti_roles=(anti_role,),
        derivation_receipt_digests=("sha256:" + "6" * 64, "sha256:" + "7" * 64),
        owner="team-architecture",
        last_reviewed=date(2026, 7, 20),
        decision_status="accepted",
        authoritative_for=("system_identity",),
        may_not_use_for=("jurisdiction_specific_legal_conclusion",),
        identity_statement_digest="sha256:" + "9" * 64,
        identity_statement_start_line=28,
        identity_statement_end_line=31,
    )
    identity_member = posture.AdmittedSourceMember(
        path=identity.path,
        content_digest=identity.content_digest,
    )
    return posture.build_posture_register(
        register_as_of=date(2026, 8, 26),
        admitted_sources=(member, identity_member),
        ast_derivation=ast_receipt,
        token_derivation=token_receipt,
        identity_boundary=identity,
        source_inventory=(inventory,),
        source_bindings=(source_binding,),
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
    base = register.claims[0].source_bindings[0]
    predicates = tuple(_predicate(posture, kind) for kind in posture.REQUIRED_SUPPORT_PREDICATES)
    owner = posture.OwnerBinding(
        owner="team-example",
        basis="package_contract",
        source_ref="architecture/packages/example.toml",
        establishment_class="recomputed",
    )
    verifier = register.admitted_verifiers[0]
    evidence = base.evidence_bindings[0].model_copy(
        update={
            "ref": verifier.content_ref,
            "content_digest": verifier.content_digest,
            "verifier_ref": verifier.ref,
            "verifier_provenance_ref": verifier.provenance_ref,
        }
    )
    supported = base.model_copy(
        update={
            "source_state": "supported",
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
            subject="example_claim",
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
            subject="example_claim",
            family="methodology",
            register_as_of=date(2026, 8, 26),
            identity_boundary=register.identity_boundary,
            admitted_sources=register.admitted_sources,
            admitted_verifiers=register.admitted_verifiers,
        )
        assert state == "blocked"
        assert blockers


def test_grounded_performance_requires_governed_evidence_and_prerequisite() -> None:
    """Catch admission of performance support without governed prerequisite evidence."""
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
    governed = posture.EvidenceBinding(
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
            governed_performance_prerequisite=governed,
            admitted_sources=register.admitted_sources,
            admitted_verifiers=register.admitted_verifiers,
            register_as_of=date(2026, 8, 26),
        )
        == "supported"
    )


def test_strict_register_recomputes_state_digest_and_rejects_extra_fields() -> None:
    """Catch sparse factories, authored status upgrades, and permissive artifacts."""
    posture = _posture()
    register = _strict_register(posture)
    assert register.schema_version == "policyos.trust.claim_posture_register.v1"
    assert register.claims[0].effective_state == "blocked"
    assert register.payload_digest.startswith("sha256:")
    strict_payload = register.model_dump(mode="json")
    posture.validate_posture_register(strict_payload)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        posture.validate_posture_register({**strict_payload, "unexpected": True})
    strict_payload["claims"][0]["effective_state"] = "supported"
    with pytest.raises((ValidationError, ValueError), match=r"effective|digest|supported"):
        posture.validate_posture_register(strict_payload)


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
