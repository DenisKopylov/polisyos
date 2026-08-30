"""Behavioral tests for the DS17 conditional confidence-risk surface."""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from importlib import import_module
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.runtime.http.services.confidence_ledger_risk_spend_contracts import (
    SourceBlockedConfidenceLedgerRiskSpendPacket,
    SourceBlockedReason,
)
from polisyos.runtime.http.services.confidence_ledger_risk_spend_projection import (
    ConfidenceLedgerRiskSpendProjectionService,
    derive_over_spend_allowset,
    validate_over_spend_allowset,
)
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSemanticReceiptProjection,
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
    load_confidence_ledger_registry,
    project_confidence_ledger_semantic_receipt,
)
from tests.unit.runtime.http.test_confidence_ledger_risk_spend_projection import (
    coherent_over_spend_artifact,
    owner_issue_codes,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "architecture/production_quality/confidence_ledger.toml"
_N11 = _ROOT / "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"
_ACTION = "protected-action://ds17/review-risk-spend"


def _surface():
    return import_module("polisyos.runtime.quality.confidence_ledger_surface")


def _coverage():
    return import_module("polisyos.runtime.quality.obligation_coverage")


def _inputs() -> tuple[ConfidenceLedgerRegistry, ConfidenceLedgerSemanticReceiptProjection]:
    registry = load_confidence_ledger_registry(_REGISTRY)
    semantic = ConfidenceLedgerSemanticReceiptProjection.model_validate(
        json.loads(_N11.read_text())["real_ledger_projection"]
    )
    return registry, semantic


def _derivation_context():
    return _coverage().CoverageDerivationContext(
        protected_action_id=_ACTION,
        semantic_source_ref="semantic-ledger://ds17/owner-admitted",
        semantic_source_verifier_ref="test.verified.semantic-ledger-source",
    )


def _envelope(registry, semantic):
    return _coverage().build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
    )


def test_owner_derivation_context_is_strict_and_matching_open_world_traverses() -> None:
    coverage = _coverage()
    surface = _surface()
    registry, semantic = _inputs()
    context = _derivation_context()
    with pytest.raises((TypeError, ValueError), match=r"extra|forbid"):
        coverage.CoverageDerivationContext.model_validate(
            {**context.model_dump(mode="python"), "caller_selected": True}
        )

    envelope = coverage.build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=context,
    )
    projection = surface.project_confidence_ledger_risk_spend(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=context,
        coverage_envelope=envelope,
    )
    admission = surface.admit_confidence_ledger_risk_spend_projection(
        projection,
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=context,
    )
    evaluation = coverage.evaluate_protected_action(
        envelope=envelope,
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=context,
        action_id=_ACTION,
        presented_claim_scope="matching owner context",
    )
    assert projection.coverage_assessment.value == "open_world_unresolved"
    assert admission.status == "exact"
    assert evaluation.assessment.value == "open_world_unresolved"


def _project(registry=None, semantic=None, **kwargs: object):
    if registry is None or semantic is None:
        registry, semantic = _inputs()
    return _surface().project_confidence_ledger_risk_spend(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        coverage_envelope=_envelope(registry, semantic),
        **kwargs,
    )


def _admit(candidate: object, registry=None, semantic=None, **kwargs: object):
    if registry is None or semantic is None:
        registry, semantic = _inputs()
    return _surface().admit_confidence_ledger_risk_spend_projection(
        candidate,
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=kwargs.pop("derivation_context", _derivation_context()),
        **kwargs,
    )


def _mutate_check(semantic, index: int, **updates: object):
    payload = semantic.model_dump(mode="json")
    payload["checks"][index].update(updates)
    return type(semantic).model_validate(payload)


def _rehash_projection(payload: dict[str, object]) -> dict[str, object]:
    body = {key: value for key, value in payload.items() if key != "projection_hash"}
    payload["projection_hash"] = fingerprint(
        body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    return payload


def _replace_amount(amount: dict[str, object], value: Fraction) -> None:
    amount["amount"] = {
        "numerator": value.numerator,
        "denominator": value.denominator,
    }
    amount["rational_display"] = f"{value.numerator}/{value.denominator}"
    amount["canonical_decimal"] = _surface().format_canonical_decimal_v1(value)
    body = {key: item for key, item in amount.items() if key != "amount_hash"}
    amount["amount_hash"] = fingerprint(
        body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )


def _forge_known_incomplete_envelope(envelope):
    coverage = _coverage()
    payload = envelope.model_dump(mode="python")
    payload["assessment"] = "known_incomplete"
    payload["reason_codes"] = (
        "DS17-COVERAGE-KNOWN-INCOMPLETE",
        "DS17-COVERAGE-SEARCH-NOT-ESTABLISHED",
        "DS17-COVERAGE-EXCLUSIONS-NOT-ESTABLISHED",
        "DS17-COVERAGE-INDEPENDENCE-MISSING",
    )
    payload["witness_refs"] = ("sha256:" + "f" * 64,)
    payload["ttl_state"] = "not_issued_known_incomplete"
    body = {
        key: value for key, value in payload.items() if key not in {"envelope_hash", "envelope_ref"}
    }
    envelope_hash = fingerprint(
        body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    return coverage.ObligationCoverageEnvelope.model_validate(
        {
            **body,
            "envelope_hash": envelope_hash,
            "envelope_ref": f"coverage-envelope:{envelope_hash}",
        }
    )


def _forge_derivation_input(envelope, mutation: str):
    payload = envelope.model_dump(mode="json")
    if mutation == "action":
        payload["protected_action_id"] = "protected-action://ds17/attacker-selected"
    elif mutation == "source_ref":
        payload["source_identities"][1]["source_ref"] = "semantic-ledger://attacker/self-attested"
    else:
        payload["source_identities"][1]["verifier_ref"] = "attacker.self_attested.verifier"
    payload["assessment_key"] = fingerprint(
        {
            "rule_version": payload["rule_version"],
            "scope_id": payload["scope_id"],
            "owner_scope_key": payload["owner_scope_key"],
            "protected_action_id": payload["protected_action_id"],
            "sources": payload["source_identities"],
        },
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    body = {
        key: value for key, value in payload.items() if key not in {"envelope_hash", "envelope_ref"}
    }
    envelope_hash = fingerprint(
        body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    return _coverage().ObligationCoverageEnvelope.model_validate(
        {
            **body,
            "envelope_hash": envelope_hash,
            "envelope_ref": f"coverage-envelope:{envelope_hash}",
        }
    )


def _rebind_projection_to_envelope(payload: object, envelope) -> None:
    if isinstance(payload, dict):
        if "amount_hash" in payload:
            payload["coverage_envelope_ref"] = envelope.envelope_ref
            payload["coverage_envelope_hash"] = envelope.envelope_hash
            amount_body = {key: value for key, value in payload.items() if key != "amount_hash"}
            payload["amount_hash"] = fingerprint(
                amount_body,
                prefix=True,
                canon_spec=CanonSpec(exclude_none=False),
            )
        for value in payload.values():
            _rebind_projection_to_envelope(value, envelope)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            _rebind_projection_to_envelope(value, envelope)


def test_ds17_reason_algebra_derives_typed_declarations_and_reachable_emitters() -> None:
    surface = _surface()
    registry, _ = _inputs()
    algebra = surface.derive_ds17_reason_algebra(registry=registry)
    expected_count = sum(
        len(enum_type)
        for enum_type in (
            _coverage().CoverageAssessment,
            surface.InstrumentBlocker,
            surface.AppointmentPosture,
        )
    )
    assert len(algebra.rows) == expected_count
    assert algebra.declared_rows == algebra.reachable_rows

    payload = registry.model_dump(mode="json")
    profile = next(
        row for row in payload["proof_profiles"] if row["profile_id"] == "fixed_time_ineligible"
    )
    profile["refusal_code"] = "coverage_argument_missing"
    mutated = ConfidenceLedgerRegistry.model_validate(payload)
    with pytest.raises((TypeError, ValueError), match=r"reason|reachable|algebra"):
        surface.derive_ds17_reason_algebra(registry=mutated)


def test_ds17_over_spend_allowset_matches_every_owner_diagnostic(
    tmp_path: Path,
) -> None:
    """Derive the C02 denominator from real owner-validator emissions."""
    artifacts = [coherent_over_spend_artifact(index) for index in range(3)]
    artifacts.append(coherent_over_spend_artifact(2, stale_total=True))
    emitted_codes = set().union(*(owner_issue_codes(value) for value in artifacts))
    derived = derive_over_spend_allowset()

    source = tmp_path / _N11.relative_to(_ROOT)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(artifacts[0], sort_keys=True), encoding="utf-8")
    packet = ConfidenceLedgerRiskSpendProjectionService(tmp_path).get()

    assert set(derived) == emitted_codes
    assert isinstance(packet, SourceBlockedConfidenceLedgerRiskSpendPacket)
    assert packet.source_blocked_reason is SourceBlockedReason.OVER_SPEND
    validate_over_spend_allowset(derived_codes=tuple(sorted(emitted_codes)))
    with pytest.raises((TypeError, ValueError), match=r"allowset|diagnostic|DS17"):
        validate_over_spend_allowset(
            derived_codes=tuple(
                code for code in derived if code != "deterministic_real_run_spend_nonzero"
            )
        )


def test_over_spend_recomputes_blocker_when_display_markers_stay_constant(
    tmp_path: Path,
) -> None:
    """Drive stale display markers through the real worker and packet service."""
    artifact = coherent_over_spend_artifact(2, stale_total=True)
    source = tmp_path / _N11.relative_to(_ROOT)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
    real_projection = artifact["real_ledger_projection"]
    recomputed_total = sum(
        (
            Fraction(
                check["spend"]["numerator"],
                check["spend"]["denominator"],
            )
            for check in real_projection["checks"]
        ),
        start=Fraction(),
    )
    packet = ConfidenceLedgerRiskSpendProjectionService(tmp_path).get()

    assert real_projection["within_budget"] is True
    assert real_projection["total_spend"] == {"numerator": 0, "denominator": 1}
    assert recomputed_total > Fraction(1, 100)
    assert isinstance(packet, SourceBlockedConfidenceLedgerRiskSpendPacket)
    assert packet.source_blocked_reason is SourceBlockedReason.OVER_SPEND


def test_real_projection_has_complete_disjoint_denominators_and_exact_bindings() -> None:
    registry, semantic = _inputs()
    projection = _project(registry, semantic)
    assert len(projection.obligation_class_risk_spend) == len(registry.obligation_weights) == 15
    assert len(projection.instrument_definitions) == len(registry.instruments) == 13
    assert len(projection.certificate_routes) == len(registry.certificate_class_routes) == 6
    assert len({row.certificate_class for row in projection.certificate_routes}) == 6
    assert all(
        row.registry_content_hash == registry.content_hash for row in projection.certificate_routes
    )
    assert len(projection.instrument_instances) == len(semantic.checks) == 3
    assert all(row.proof_kernel_id for row in projection.instrument_definitions)
    assert all(row.proof_profile_id for row in projection.instrument_instances)
    assert all(row.certificate_route_ref for row in projection.instrument_instances)
    assert all(row.eligible_for_promotion is False for row in projection.instrument_instances)
    assert len(projection.positive_register.entries) == 0
    assert len(projection.refusal_instance_refs) == 1
    assert len(projection.acquisition_instance_refs) == 2
    assert set(projection.refusal_instance_refs).isdisjoint(projection.acquisition_instance_refs)
    assert projection.coverage_assessment.value == "open_world_unresolved"
    assert projection.status == "not_promoted"
    assert projection.positive_register.population_state == "valid_zero"
    assert projection.positive_register.population_count == 0
    assert len(projection.positive_register.would_populate_when) == 7
    assert projection.positive_register.verified_appointment_refs == ()
    assert projection.positive_register.authority_posture.value.endswith("unappointed")
    assert projection.good_event_posture.independence_claim is False
    assert projection.good_event_posture.executed_probabilistic_good_event_refs == ()
    assert projection.source_provenance == projection.coverage_envelope.source_identities
    assert projection.fixed_scope_disclosure == projection.total_spend.locality_rider
    assert projection.scope_total_risk_spend.allocation.amount.fraction == Fraction(1, 100)
    assert projection.scope_total_risk_spend.spent.amount.fraction == 0
    assert projection.scope_total_risk_spend.remaining.amount.fraction == Fraction(1, 100)
    assert projection.scope_total_risk_spend.overspend_amount.amount.fraction == 0
    dumped = projection.model_dump(mode="json")
    assert not ({"parent_total", "family_total", "sequence_total"} & dumped.keys())
    with pytest.raises(TypeError, match=r"appointment"):
        _project(registry, semantic, caller_appointment_authority=True)
    amounts = [projection.total_spend]
    for row in projection.obligation_class_risk_spend:
        assert row.remaining.amount.fraction == max(
            row.allocation.amount.fraction - row.spent.amount.fraction,
            Fraction(),
        )
        assert row.overspend_amount.amount.fraction == max(
            row.spent.amount.fraction - row.allocation.amount.fraction,
            Fraction(),
        )
        assert row.allocation.obligation_class is row.obligation_class
        amounts.extend((row.allocation, row.spent, row.remaining, row.overspend_amount))
    for amount in amounts:
        assert amount.scope_id == semantic.scope_id
        assert amount.owner_scope_key == semantic.risk_scope.owner_scope_key
        assert amount.coverage_envelope_ref == projection.coverage_envelope_ref
        assert amount.canonical_decimal


def test_registry_evolution_projects_source_derived_denominators(
    tmp_path: Path,
) -> None:
    registry = load_confidence_ledger_registry(_REGISTRY)
    source = copy.deepcopy(registry.source_payload())
    original_class_order = tuple(
        obligation for pool in registry.obligation_pools for obligation in pool.obligation_classes
    )

    multi_class_pool = next(
        pool for pool in source["obligation_pools"] if len(pool["obligation_classes"]) > 1
    )
    pool_classes = tuple(multi_class_pool["obligation_classes"])
    multi_class_pool["obligation_classes"] = (*pool_classes[1:], pool_classes[0])

    routes = tuple(source["certificate_class_routes"])
    retired_route = next(
        route
        for route in routes
        if sum(candidate["instrument_id"] == route["instrument_id"] for candidate in routes) > 1
    )
    retained_routes = tuple(route for route in routes if route != retired_route)
    source["certificate_class_routes"] = retained_routes
    routed_instrument_ids = {route["instrument_id"] for route in retained_routes}
    instruments = tuple(source["instruments"])
    retired_instrument = next(
        instrument
        for instrument in instruments
        if instrument["instrument_id"] not in routed_instrument_ids
        and "promotion_conformance" not in instrument["certificate_roles"]
    )
    source["instruments"] = tuple(
        instrument for instrument in instruments if instrument != retired_instrument
    )
    evolved = load_confidence_ledger_registry(source)

    risk_scope = ConfidenceRiskBudgetScope(
        scope_owner_ref=(
            "tests.unit.runtime.quality.test_confidence_ledger_surface."
            "test_registry_evolution_projects_source_derived_denominators"
        ),
        authority_purpose="n11_real_n10_n13b_accounting",
        owner_scope_key="ds17:test:dynamic-registry",
        owner_projection_hash=evolved.content_hash,
        epoch_ref=None,
        model_ref=None,
        rule_ref="policyos.policy_design_case.layer3_gy.n11_confidence_ledger.v1",
        schema_ref="policyos.policy_design_case.layer3_gy.n11_confidence_ledger.v1",
    )
    session = ConfidenceLedgerSession._for_verification(
        _ROOT,
        risk_scope=risk_scope,
        artifact_store=FileSystemCAS(tmp_path / "cas"),
        state_root=tmp_path / "state",
        registry_source=evolved.source_payload(),
    )
    semantic = project_confidence_ledger_semantic_receipt(
        session.receipt(),
        session=session,
        projection_scope="n11_real_accounting_append_lineage",
    )
    context = _derivation_context()
    envelope = _coverage().build_coverage_envelope(
        registry=evolved,
        semantic_ledger=semantic,
        derivation_context=context,
    )
    projection = _surface().project_confidence_ledger_risk_spend(
        registry=evolved,
        semantic_ledger=semantic,
        derivation_context=context,
        coverage_envelope=envelope,
    )
    admission = _surface().admit_confidence_ledger_risk_spend_projection(
        projection,
        registry=evolved,
        semantic_ledger=semantic,
        derivation_context=context,
    )

    evolved_class_order = tuple(
        obligation for pool in evolved.obligation_pools for obligation in pool.obligation_classes
    )
    assert evolved_class_order != original_class_order
    assert (
        tuple(row.obligation_class for row in projection.obligation_class_risk_spend)
        == evolved_class_order
    )
    assert len(projection.obligation_class_risk_spend) == len(original_class_order)
    assert len(projection.instrument_definitions) == len(registry.instruments) - 1
    assert len(projection.certificate_routes) == len(registry.certificate_class_routes) - 1
    assert tuple(row.instrument_id for row in projection.instrument_definitions) == tuple(
        instrument.instrument_id for instrument in evolved.instruments
    )
    assert tuple(row.certificate_class for row in projection.certificate_routes) == tuple(
        route.certificate_class for route in evolved.certificate_class_routes
    )
    assert semantic.checks == ()
    assert projection.instrument_instances == ()
    assert projection.coverage_assessment.value == "open_world_unresolved"
    assert projection.registry_content_hash == evolved.content_hash
    assert semantic.registry_content_hash == evolved.content_hash
    assert registry.content_hash != evolved.content_hash
    assert admission.status == "exact"
    assert admission.projection == projection


@pytest.mark.parametrize(
    ("instrument_id", "expected"),
    [
        ("bayesian_credible_interval", "coverage_argument_missing"),
        ("fixed_time_confidence_interval", "non_anytime_valid"),
    ],
)
def test_registry_profile_blocks_caller_eligibility_marker(
    instrument_id: str, expected: str
) -> None:
    registry, semantic = _inputs()
    definition = registry.resolve_instrument(instrument_id)
    profile = registry.resolve_proof_profile(definition.proof_profile_id)
    mutated = _mutate_check(
        semantic,
        0,
        instrument_id=definition.instrument_id,
        instrument_family=definition.instrument_family,
        proof_profile_id=profile.profile_id,
        certificate_class=None,
        certificate_route_hash=None,
        certificate_role="promotion",
        claim_polarity="false_accept",
        anytime_valid=profile.anytime_valid,
        eligible_for_promotion=True,
        refusal_code=profile.refusal_code,
    )
    projection = _project(
        registry,
        mutated,
        caller_eligibility_by_instrument={instrument_id: True},
    )
    assert expected in {reason.value for reason in projection.instrument_blockers}
    assert projection.positive_register.entries == ()


def test_surface_recomputes_exact_over_spend_while_input_marker_stays_true() -> None:
    registry, semantic = _inputs()
    payload = semantic.model_dump(mode="json")
    payload["checks"][0]["spend"] = {"numerator": 2, "denominator": 100}
    payload["checks"][0]["spend_decimal"] = "0.02"
    payload["total_spend"] = {"numerator": 1, "denominator": 50}
    payload["total_spend_decimal"] = "0.02"
    payload["within_budget"] = True
    mutated = type(semantic).model_validate(payload)
    projection = _project(registry, mutated)
    assert projection.total_spend.amount.fraction == Fraction(1, 50)
    assert projection.scope_total_risk_spend.allocation.amount.fraction == Fraction(1, 100)
    assert projection.scope_total_risk_spend.spent.amount.fraction == Fraction(1, 50)
    assert projection.scope_total_risk_spend.remaining.amount.fraction == 0
    assert projection.scope_total_risk_spend.overspend_amount.amount.fraction == Fraction(1, 100)
    assert projection.budget_posture == "over_spend"
    assert projection.status == "not_promoted"


def test_canonical_decimal_and_projection_nested_envelope_binding() -> None:
    surface = _surface()
    assert surface.format_canonical_decimal_v1(Fraction(1, 1000)) == "0.001"
    assert surface.format_canonical_decimal_v1(Fraction(1, 3)) == "0.(3)"
    assert surface.format_canonical_decimal_v1(Fraction(1, 6)) == "0.1(6)"
    projection = _project()
    base = projection.model_dump(mode="python")
    for field_name, forged_value in (
        ("maintained_assumptions", ("validator_soundness",)),
        ("declared_obligation_classes_hash", "sha256:" + "7" * 64),
    ):
        payload = copy.deepcopy(base)
        amount = payload["obligation_class_risk_spend"][0]["allocation"]
        amount[field_name] = forged_value
        amount_body = {key: value for key, value in amount.items() if key != "amount_hash"}
        amount["amount_hash"] = fingerprint(
            amount_body,
            prefix=True,
            canon_spec=CanonSpec(exclude_none=False),
        )
        projection_body = {key: value for key, value in payload.items() if key != "projection_hash"}
        payload["projection_hash"] = fingerprint(
            projection_body,
            prefix=True,
            canon_spec=CanonSpec(exclude_none=False),
        )
        with pytest.raises(ValueError, match=r"nested_amount_binding"):
            surface.ConfidenceLedgerRiskSpendProjection.model_validate(payload)


def test_complete_certificate_route_denominator_rejects_missing_duplicate_and_swap() -> None:
    surface = _surface()
    projection = _project()
    base = projection.model_dump(mode="python")
    mutations: list[dict[str, object]] = []

    missing = copy.deepcopy(base)
    missing["certificate_routes"] = missing["certificate_routes"][:-1]
    mutations.append(missing)

    duplicate = copy.deepcopy(base)
    duplicate["certificate_routes"] = (
        *duplicate["certificate_routes"],
        duplicate["certificate_routes"][0],
    )
    mutations.append(duplicate)

    swapped = copy.deepcopy(base)
    routes = list(swapped["certificate_routes"])
    routes[0]["instrument_id"], routes[1]["instrument_id"] = (
        routes[1]["instrument_id"],
        routes[0]["instrument_id"],
    )
    swapped["certificate_routes"] = tuple(routes)
    mutations.append(swapped)

    for payload in mutations:
        projection_body = {key: value for key, value in payload.items() if key != "projection_hash"}
        payload["projection_hash"] = fingerprint(
            projection_body,
            prefix=True,
            canon_spec=CanonSpec(exclude_none=False),
        )
        with pytest.raises(ValueError, match=r"route.*(?:binding|denominator)"):
            surface.ConfidenceLedgerRiskSpendProjection.model_validate(payload)


def test_unknown_owner_refusal_maps_to_catchall_without_coverage_semantics() -> None:
    registry, semantic = _inputs()
    mutated = _mutate_check(semantic, 0, refusal_code="owner_grounded_new_refusal")
    projection = _project(registry, mutated)
    assert projection.instrument_blockers == (_surface().InstrumentBlocker.OTHER_RUNTIME_REFUSAL,)
    assert projection.coverage_assessment.value == "open_world_unresolved"
    for invalid in ("", "contains spaces", "UPPER"):
        with pytest.raises((TypeError, ValueError), match=r"refusal|source"):
            _project(registry, _mutate_check(semantic, 0, refusal_code=invalid))


def test_domain_projection_admission_revalidates_real_semantics_and_hash_identity() -> None:
    surface = _surface()
    projection = _project()
    exact = _admit(projection)
    assert exact.status == "exact"
    assert exact.projection == projection
    assert "reason" not in exact.model_dump(mode="json")
    assert len(surface.SharedSafetyBlockedReason) == 7

    missing = projection.model_dump(mode="python")
    missing.pop("scope_total_risk_spend")
    blocked = _admit(missing)
    assert blocked.status == "blocked"
    assert blocked.reason.value == "missing_input_or_incomplete_history"

    for update in (
        {"unexpected_surface_arm": "still_exact"},
        {"schema_version": "policyos.runtime.confidence_ledger_surface.v999"},
        {"rule_version": "policyos.runtime.confidence_ledger_surface.unknown"},
    ):
        unsupported = {**projection.model_dump(mode="python"), **update}
        blocked = _admit(unsupported)
        assert blocked.status == "blocked"
        assert blocked.reason.value == "unsupported_or_out_of_model"

    malformed = projection.model_dump(mode="python")
    malformed["projection_hash"] = "sha256:" + "0" * 64
    blocked = _admit(malformed)
    assert blocked.status == "blocked"
    assert blocked.reason.value == "parser_or_schema_failure"

    forged = projection.model_dump(mode="python")
    remaining = forged["obligation_class_risk_spend"][0]["remaining"]
    remaining["amount"] = {"numerator": 1, "denominator": 1}
    remaining["rational_display"] = "1/1"
    remaining["canonical_decimal"] = "1"
    remaining_body = {key: value for key, value in remaining.items() if key != "amount_hash"}
    remaining["amount_hash"] = fingerprint(
        remaining_body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    forged_body = {key: value for key, value in forged.items() if key != "projection_hash"}
    forged["projection_hash"] = fingerprint(
        forged_body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    blocked = _admit(forged)
    assert blocked.status == "blocked"
    assert blocked.reason.value == "parser_or_schema_failure"

    assert projection.status == "not_promoted"
    assert projection.budget_posture == "within_budget"
    assert "safe" not in blocked.model_dump(mode="json")


@pytest.mark.parametrize(
    "mutation",
    [
        "class_denominator",
        "definition_denominator",
        "route_denominator",
        "instance_role_denominator",
        "reason_slot",
        "cross_row_allocation",
    ],
)
def test_domain_projection_admission_blocks_coherent_recursive_narrowing(
    mutation: str,
) -> None:
    surface = _surface()
    projection = _project()
    payload = projection.model_dump(mode="python")

    if mutation == "class_denominator":
        payload["obligation_class_risk_spend"] = payload["obligation_class_risk_spend"][:-1]
    elif mutation == "definition_denominator":
        payload["instrument_definitions"] = payload["instrument_definitions"][:-1]
    elif mutation == "route_denominator":
        routes = payload["certificate_routes"][:-1]
        payload["certificate_routes"] = routes
        payload["certificate_route_denominator_count"] = len(routes)
        payload["certificate_route_denominator_hash"] = fingerprint(
            [row["route_binding_hash"] for row in routes],
            prefix=True,
            canon_spec=CanonSpec(exclude_none=False),
        )
    elif mutation == "instance_role_denominator":
        removed = payload["instrument_instances"][-1]
        payload["instrument_instances"] = payload["instrument_instances"][:-1]
        for field_name in (
            "refusal_instance_refs",
            "acquisition_instance_refs",
            "conformance_instance_refs",
        ):
            payload[field_name] = tuple(
                ref for ref in payload[field_name] if ref != removed["instance_ref"]
            )
        payload["grouped_spend"] = tuple(
            row
            for row in payload["grouped_spend"]
            if not (
                row["obligation_class"] == removed["obligation_class"]
                and row["instrument_id"] == removed["instrument_id"]
            )
        )
        for row in payload["obligation_class_risk_spend"]:
            if removed["instance_ref"] in row["check_refs"]:
                row["check_refs"] = tuple(
                    ref for ref in row["check_refs"] if ref != removed["instance_ref"]
                )
                row["instrument_refs"] = tuple(
                    ref for ref in row["instrument_refs"] if ref != removed["instrument_id"]
                )
    elif mutation == "reason_slot":
        payload["positive_register"]["blockers"][0]["slot"] = "appointment_posture"
    else:
        row = payload["obligation_class_risk_spend"][0]
        _replace_amount(row["allocation"], Fraction())
        _replace_amount(row["remaining"], Fraction())

    blocked = _admit(_rehash_projection(payload))
    assert blocked.status == "blocked"
    assert blocked.reason.value == "parser_or_schema_failure"


def test_forged_known_incomplete_envelope_cannot_cross_projection_or_admission() -> None:
    surface = _surface()
    registry, semantic = _inputs()
    open_envelope = _envelope(registry, semantic)
    forged_envelope = _forge_known_incomplete_envelope(open_envelope)

    with pytest.raises((TypeError, ValueError), match=r"witness|signature|authentic"):
        surface.project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            coverage_envelope=forged_envelope,
        )
    with pytest.raises((TypeError, ValueError), match=r"coverage|envelope|witness"):
        _coverage().evaluate_protected_action(
            envelope=forged_envelope,
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            action_id=_ACTION,
            presented_claim_scope="forged known-incomplete arm",
        )

    candidate = _project(registry, semantic).model_dump(mode="python")
    candidate["coverage_envelope"] = forged_envelope.model_dump(mode="python")
    candidate["coverage_envelope_ref"] = forged_envelope.envelope_ref
    candidate["coverage_assessment"] = _coverage().CoverageAssessment.KNOWN_INCOMPLETE
    candidate["positive_register"]["blockers"][0]["value"] = "known_incomplete"
    _rebind_projection_to_envelope(candidate, forged_envelope)
    _rehash_projection(candidate)
    parsed = surface.ConfidenceLedgerRiskSpendProjection.model_validate(candidate)
    assert parsed.coverage_assessment.value == "known_incomplete"
    blocked = _admit(
        candidate,
        registry=registry,
        semantic=semantic,
    )
    assert blocked.status == "blocked"
    assert blocked.reason.value == "parser_or_schema_failure"


@pytest.mark.parametrize("mutation", ["action", "source_ref", "source_verifier"])
def test_zero_witness_candidate_cannot_select_owner_derivation_inputs(
    mutation: str,
) -> None:
    coverage = _coverage()
    surface = _surface()
    registry, semantic = _inputs()
    context = _derivation_context()
    envelope = _envelope(registry, semantic)
    forged = _forge_derivation_input(envelope, mutation)

    with pytest.raises((TypeError, ValueError), match=r"coverage|derivation|envelope"):
        surface.project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=context,
            coverage_envelope=forged,
        )
    with pytest.raises((TypeError, ValueError), match=r"coverage|derivation|envelope"):
        coverage.evaluate_protected_action(
            envelope=forged,
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=context,
            action_id=forged.protected_action_id,
            presented_claim_scope="attacker-selected derivation input",
        )

    payload = _project(registry, semantic).model_dump(mode="python")
    payload["coverage_envelope"] = forged.model_dump(mode="python")
    payload["coverage_envelope_ref"] = forged.envelope_ref
    _rebind_projection_to_envelope(payload, forged)
    _rehash_projection(payload)
    blocked = _admit(
        payload,
        registry=registry,
        semantic=semantic,
        derivation_context=context,
    )
    assert blocked.status == "blocked"
    assert blocked.reason.value == "parser_or_schema_failure"

    context_update = {
        "action": {"protected_action_id": "protected-action://ds17/wrong-owner-context"},
        "source_ref": {"semantic_source_ref": "semantic-ledger://wrong-owner-context"},
        "source_verifier": {"semantic_source_verifier_ref": "wrong.owner.context.verifier"},
    }[mutation]
    wrong_context = context.model_copy(update=context_update)
    with pytest.raises((TypeError, ValueError), match=r"coverage|derivation|envelope"):
        surface.project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=wrong_context,
            coverage_envelope=envelope,
        )
    with pytest.raises((TypeError, ValueError), match=r"coverage|derivation|envelope"):
        coverage.evaluate_protected_action(
            envelope=envelope,
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=wrong_context,
            action_id=_ACTION,
            presented_claim_scope="wrong owner derivation context",
        )
    wrong_admission = _admit(
        _project(registry, semantic),
        registry=registry,
        semantic=semantic,
        derivation_context=wrong_context,
    )
    assert wrong_admission.status == "blocked"
    assert wrong_admission.reason.value == "parser_or_schema_failure"


@pytest.mark.parametrize("mutation", ["model_copy", "model_construct", "audience", "may_not_use"])
def test_every_arm_reader_rederives_the_complete_envelope(mutation: str) -> None:
    coverage = _coverage()
    surface = _surface()
    registry, semantic = _inputs()
    envelope = _envelope(registry, semantic)
    if mutation == "model_copy":
        candidate = envelope.model_copy(
            update={"assessment": coverage.CoverageAssessment.KNOWN_INCOMPLETE}
        )
    elif mutation == "model_construct":
        candidate = coverage.ObligationCoverageEnvelope.model_construct(
            **{
                **{name: getattr(envelope, name) for name in type(envelope).model_fields},
                "assessment": coverage.CoverageAssessment.KNOWN_INCOMPLETE,
            }
        )
    else:
        payload = envelope.model_dump(mode="python")
        if mutation == "audience":
            payload["authorized_audiences"] = ("reviewer",)
        else:
            payload["may_not_use_for"] = tuple(
                value for value in payload["may_not_use_for"] if value != "world_completeness"
            )
        body = {
            key: value
            for key, value in payload.items()
            if key not in {"envelope_hash", "envelope_ref"}
        }
        envelope_hash = fingerprint(
            body,
            prefix=True,
            canon_spec=CanonSpec(exclude_none=False),
        )
        candidate = coverage.ObligationCoverageEnvelope.model_validate(
            {
                **body,
                "envelope_hash": envelope_hash,
                "envelope_ref": f"coverage-envelope:{envelope_hash}",
            }
        )

    with pytest.raises((TypeError, ValueError), match=r"coverage|envelope|witness"):
        surface.project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            coverage_envelope=candidate,
        )
    with pytest.raises((TypeError, ValueError), match=r"coverage|envelope|witness"):
        coverage.evaluate_protected_action(
            envelope=candidate,
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            action_id=_ACTION,
            presented_claim_scope="candidate mutation",
        )
    forged_projection = _project(registry, semantic).model_copy(
        update={
            "coverage_envelope": candidate,
            "coverage_envelope_ref": candidate.envelope_ref,
            "coverage_assessment": candidate.assessment,
        }
    )
    blocked = _admit(
        forged_projection,
        registry=registry,
        semantic=semantic,
    )
    assert blocked.status == "blocked"
    assert blocked.reason.value == "parser_or_schema_failure"
