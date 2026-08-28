"""Behavioral tests for the DS17 conditional confidence-risk surface."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from fractions import Fraction
from importlib import import_module
from pathlib import Path

import pytest

from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSemanticReceiptProjection,
    load_confidence_ledger_registry,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "architecture/production_quality/confidence_ledger.toml"
_N11 = _ROOT / "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"
_ACTION = "protected-action://ds17/review-risk-spend"
_OVER_SPEND_ALLOWSET = frozenset(
    {
        "semantic_forged_spend_row",
        "semantic_total_spend_drift",
        "semantic_budget_status_drift",
        "semantic_deterministic_spend_nonzero",
        "deterministic_real_run_spend_nonzero",
    }
)


def _surface():
    return import_module("polisyos.runtime.quality.confidence_ledger_surface")


def _coverage():
    return import_module("polisyos.runtime.quality.obligation_coverage")


def _projection_module():
    return import_module(
        "polisyos.runtime.http.services.confidence_ledger_risk_spend_projection"
    )


def _inputs() -> tuple[ConfidenceLedgerRegistry, ConfidenceLedgerSemanticReceiptProjection]:
    registry = load_confidence_ledger_registry(_REGISTRY)
    semantic = ConfidenceLedgerSemanticReceiptProjection.model_validate(
        json.loads(_N11.read_text())["real_ledger_projection"]
    )
    return registry, semantic


def _envelope(registry, semantic):
    return _coverage().build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        semantic_source_ref=semantic.projection_hash,
        semantic_source_verifier_ref="test.verified.semantic-ledger-source",
        protected_action_id=_ACTION,
    )


def _project(registry=None, semantic=None, **kwargs: object):
    if registry is None or semantic is None:
        registry, semantic = _inputs()
    return _surface().project_confidence_ledger_risk_spend(
        registry=registry,
        semantic_ledger=semantic,
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
        **kwargs,
    )


def _mutate_check(semantic, index: int, **updates: object):
    payload = semantic.model_dump(mode="json")
    payload["checks"][index].update(updates)
    return type(semantic).model_validate(payload)


def _stale_over_spend_ledger(semantic_ledger):
    payload = semantic_ledger.model_dump(mode="json")
    payload["checks"][0]["spend"] = {"numerator": 2, "denominator": 100}
    payload["total_spend"] = {"numerator": 1, "denominator": 50}
    payload["total_spend_decimal"] = "0.02"
    payload["within_budget"] = True
    return type(semantic_ledger).model_validate(payload)


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
        key: value
        for key, value in payload.items()
        if key not in {"envelope_hash", "envelope_ref"}
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


def _rebind_projection_to_envelope(payload: object, envelope) -> None:
    if isinstance(payload, dict):
        if "amount_hash" in payload:
            payload["coverage_envelope_ref"] = envelope.envelope_ref
            payload["coverage_envelope_hash"] = envelope.envelope_hash
            amount_body = {
                key: value for key, value in payload.items() if key != "amount_hash"
            }
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


@dataclass(frozen=True)
class _CoherentOverSpendOwnerSourceAdapter:
    """C02-only owner adapter for a scratch artifact with rebuilt bindings."""

    frozen_semantic_ledger: object
    check_id: str
    spend_numerator: int
    spend_denominator: int
    keep_display_markers: bool = True


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


def test_ds17_over_spend_allowset_matches_every_owner_diagnostic() -> None:
    """C02 owns source-worker diagnostic reachability."""
    projection = _projection_module()
    derived = projection.derive_over_spend_allowset()
    assert set(derived) == _OVER_SPEND_ALLOWSET
    with pytest.raises((TypeError, ValueError), match=r"allowset|diagnostic|DS17"):
        projection.validate_over_spend_allowset(
            derived_codes=tuple(
                code
                for code in derived
                if code != "deterministic_real_run_spend_nonzero"
            )
        )


def test_over_spend_recomputes_blocker_when_display_markers_stay_constant() -> None:
    """C02 owns coherent source admission and the source-blocked reason."""
    projection = _projection_module()
    registry, semantic_ledger = _inputs()
    stale_ledger = _stale_over_spend_ledger(semantic_ledger)
    worker_receipt = projection.build_content_bound_worker_receipt(
        registry=registry,
        semantic_ledger=stale_ledger,
    )
    with pytest.raises((TypeError, ValueError), match=r"source|hash|binding|DS17"):
        projection.classify_content_bound_over_spend(
            registry=registry,
            semantic_ledger=stale_ledger,
            worker_receipt=worker_receipt,
        )
    source_adapter = _CoherentOverSpendOwnerSourceAdapter(
        frozen_semantic_ledger=semantic_ledger,
        check_id=semantic_ledger.checks[0].request_key,
        spend_numerator=2,
        spend_denominator=100,
    )
    blocked = projection.classify_content_bound_over_spend(
        registry=registry, owner_source_adapter=source_adapter
    ).model_dump(mode="json")
    assert blocked["status"] == "source_blocked"
    assert blocked["reason"] == "over_spend"
    assert blocked["recomputed_total_spend"] == {"numerator": 1, "denominator": 50}


def test_real_projection_has_complete_disjoint_denominators_and_exact_bindings() -> None:
    registry, semantic = _inputs()
    projection = _project(registry, semantic)
    assert len(projection.obligation_class_risk_spend) == len(registry.obligation_weights) == 15
    assert len(projection.instrument_definitions) == len(registry.instruments) == 13
    assert len(projection.certificate_routes) == len(registry.certificate_class_routes) == 6
    assert len({row.certificate_class for row in projection.certificate_routes}) == 6
    assert all(
        row.registry_content_hash == registry.content_hash
        for row in projection.certificate_routes
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
        projection_body = {
            key: value for key, value in payload.items() if key != "projection_hash"
        }
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
        projection_body = {
            key: value for key, value in payload.items() if key != "projection_hash"
        }
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
    remaining_body = {
        key: value for key, value in remaining.items() if key != "amount_hash"
    }
    remaining["amount_hash"] = fingerprint(
        remaining_body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    forged_body = {
        key: value for key, value in forged.items() if key != "projection_hash"
    }
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
        payload["obligation_class_risk_spend"] = payload[
            "obligation_class_risk_spend"
        ][:-1]
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
                    ref
                    for ref in row["instrument_refs"]
                    if ref != removed["instrument_id"]
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
            coverage_envelope=forged_envelope,
        )
    with pytest.raises((TypeError, ValueError), match=r"coverage|envelope|witness"):
        _coverage().evaluate_protected_action(
            envelope=forged_envelope,
            registry=registry,
            semantic_ledger=semantic,
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
                **{
                    name: getattr(envelope, name)
                    for name in type(envelope).model_fields
                },
                "assessment": coverage.CoverageAssessment.KNOWN_INCOMPLETE,
            }
        )
    else:
        payload = envelope.model_dump(mode="python")
        if mutation == "audience":
            payload["authorized_audiences"] = ("reviewer",)
        else:
            payload["may_not_use_for"] = tuple(
                value
                for value in payload["may_not_use_for"]
                if value != "world_completeness"
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
            coverage_envelope=candidate,
        )
    with pytest.raises((TypeError, ValueError), match=r"coverage|envelope|witness"):
        coverage.evaluate_protected_action(
            envelope=candidate,
            registry=registry,
            semantic_ledger=semantic,
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
