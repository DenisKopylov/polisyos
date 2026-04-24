"""Exact proof-carrying incentive-compatibility verification for typed mechanisms."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import product
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.ic_verification import (
    ICNegativeCertificate,
    ICNegativeCertificateRef,
    ICVerificationCertificateRef,
    ICVerificationReport,
    ICVerificationReportRef,
    ICVerificationRequest,
    ICVerificationResult,
    IncentiveCompatibilityCertificate,
)
from polisyos.foundry.mechanism_design import get_mechanism_family_spec
from polisyos.ir.analytics.mechanism_design import (
    IncentiveCertificateStatus as MechanismCertificateStatus,
)
from polisyos.ir.analytics.mechanism_design import (
    IncentiveCompatibilityCertificate as MechanismICCertificate,
)
from polisyos.ir.analytics.mechanism_design import (
    MechanismFamily,
    MechanismFamilySpec,
    MechanismWelfareLossBound,
    build_reserve_auction_welfare_loss_bound,
    certify_affine_tax,
    certify_license_scoring_auction,
    certify_piecewise_linear_tax,
    persist_mechanism_family_spec,
    persist_mechanism_welfare_loss_bound,
)
from polisyos.ir.analytics.mechanism_design import (
    persist_incentive_compatibility_certificate as persist_mechanism_ic_certificate,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.governance.game_design import (
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
)
from polisyos.ir.governance.mechanism_semantics import (
    CycMonGridSemanticsSpec,
    Envelope1DSemanticsSpec,
    MechanismPriorKind,
    MechanismSemanticFragment,
    MechanismSemanticsSpec,
    MechanismUtilityModelKind,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.trinity import TrinityBundle

_REPORT_SCHEMA_NAME = "polisyos.core.contracts.ic_verification.ICVerificationReport"
_CERTIFICATE_SCHEMA_NAME = (
    "polisyos.core.contracts.ic_verification.IncentiveCompatibilityCertificate"
)
_NEGATIVE_SCHEMA_NAME = "polisyos.core.contracts.ic_verification.ICNegativeCertificate"
_TAX_MECHANISM_IDS = frozenset({"bayes_tax_pl_v1", "bayes_tax_affine_v1"})
_LICENSE_MECHANISM_IDS = frozenset({"license_scoring_reserve_v1", "license_myerson_score_v1"})
_MECHANISM_FAMILY_IDS = _TAX_MECHANISM_IDS | _LICENSE_MECHANISM_IDS


@dataclass(frozen=True)
class _FiniteMechanism:
    design: MechanismDesignSpec
    semantics: MechanismSemanticsSpec
    property_name: str
    players: tuple[str, ...]
    players_checked: tuple[str, ...]
    type_spaces: dict[str, tuple[str, ...]]
    profiles: list[dict[str, str]]
    profile_keys: set[tuple[tuple[str, str], ...]]
    outcome_by_profile: dict[tuple[tuple[str, str], ...], str]
    payments_by_profile: dict[tuple[tuple[str, str], ...], dict[str, Fraction]]
    values: dict[tuple[str, str, str], Fraction]
    utilities: dict[tuple[str, str, tuple[tuple[str, str], ...]], Fraction]
    prior_kind: MechanismPriorKind | None
    independent_prior: dict[str, dict[str, Fraction]]
    joint_prior: list[tuple[dict[str, str], Fraction]]


@dataclass(frozen=True)
class _Envelope1DMechanism:
    property_name: str
    player_id: str
    type_labels: tuple[str, ...]
    type_values: dict[str, Fraction]
    allocation_by_label: dict[str, Fraction]
    payment_by_label: dict[str, Fraction] | None
    normalization_type_label: str
    normalization_utility: Fraction


@dataclass(frozen=True)
class _CycMonGridMechanism:
    property_name: str
    player_id: str
    type_labels: tuple[str, ...]
    coords_by_label: dict[str, tuple[Fraction, ...]]
    allocation_by_label: dict[str, tuple[Fraction, ...]]
    payment_by_label: dict[str, Fraction] | None
    normalization_type_label: str
    normalization_utility: Fraction


@dataclass(frozen=True)
class _MechanismFamilyCandidate:
    mechanism_id: str
    intervention_id: str
    params: dict[str, Any]


@dataclass(frozen=True)
class _MechanismFamilyEvaluation:
    report: ICVerificationReport
    certificate: IncentiveCompatibilityCertificate | ICNegativeCertificate | None
    family_spec: MechanismFamilySpec | None = None
    mechanism_certificate: MechanismICCertificate | None = None
    welfare_bound: MechanismWelfareLossBound | None = None
    component_evaluations: tuple[_MechanismFamilyEvaluation, ...] = ()


def _profile_key(profile: dict[str, str], players: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((player_id, profile[player_id]) for player_id in players)


def _fraction_to_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _fraction_tuple(values: tuple[str, ...]) -> tuple[Fraction, ...]:
    return tuple(Fraction(value) for value in values)


def _vector_to_text(values: tuple[Fraction, ...]) -> list[str]:
    return [_fraction_to_text(value) for value in values]


def _dot(lhs: tuple[Fraction, ...], rhs: tuple[Fraction, ...]) -> Fraction:
    return sum((left * right for left, right in zip(lhs, rhs, strict=True)), start=Fraction(0))


def _subtract(lhs: tuple[Fraction, ...], rhs: tuple[Fraction, ...]) -> tuple[Fraction, ...]:
    return tuple(left - right for left, right in zip(lhs, rhs, strict=True))


def _resolve_policy_input(
    store: ArtifactStore,
    request: ICVerificationRequest,
) -> tuple[PolicySpec, str]:
    payload = from_canonical_bytes(store.get_bytes(request.input_ref.artifact_id))
    if request.input_ref.kind == "ir.trinity_bundle":
        bundle = TrinityBundle.model_validate(payload)
        return bundle.policy_spec, str(request.input_ref.artifact_id)
    if request.input_ref.kind == "ir.policy_spec":
        policy = PolicySpec.model_validate(payload)
        return policy, str(request.input_ref.artifact_id)
    raise ValueError(
        f"Unsupported IC input_ref.kind '{request.input_ref.kind}'; "
        "expected 'ir.trinity_bundle' or 'ir.policy_spec'"
    )


def _resolve_semantics(
    store: ArtifactStore | None,
    request: ICVerificationRequest,
    design: MechanismDesignSpec,
) -> MechanismSemanticsSpec:
    if request.semantics_ref is not None:
        if store is None:
            raise ValueError("semantics_ref requires an ArtifactStore")
        payload = get_json_artifact(store, request.semantics_ref.artifact_id)
        return MechanismSemanticsSpec.model_validate(payload)
    if design.semantics is None:
        raise ValueError("mechanism_design.semantics is required for strict IC verification")
    return design.semantics


def _resolve_players_checked(
    design: MechanismDesignSpec,
    property_name: str,
) -> tuple[str, ...]:
    matching: list[MechanismDesignConstraint] = [
        constraint
        for constraint in design.constraints
        if constraint.constraint_type.value == property_name
    ]
    if not matching:
        return design.players
    declared = {player_id for constraint in matching for player_id in constraint.applies_to_players}
    if not declared:
        return design.players
    return tuple(player_id for player_id in design.players if player_id in declared)


def _normalize_finite_mechanism(
    design: MechanismDesignSpec,
    semantics: MechanismSemanticsSpec,
    property_name: str,
) -> _FiniteMechanism:
    if semantics.fragment is not MechanismSemanticFragment.FINITE_DIRECT:
        raise ValueError("finite_exact backend requires semantics.fragment='finite_direct'")
    if property_name not in {
        MechanismConstraintType.DOMINANT_STRATEGY_IC.value,
        MechanismConstraintType.BAYESIAN_IC.value,
        MechanismConstraintType.EX_POST_IR.value,
        MechanismConstraintType.EX_INTERIM_IR.value,
    }:
        raise ValueError(f"property '{property_name}' is not supported by finite_exact")

    players = design.players
    type_spaces = {item.player_id: item.type_space for item in design.bayesian_types}
    if set(type_spaces) != set(players):
        raise ValueError("finite IC verification requires bayesian_types for every player")
    semantics.validate_against_declared_structure(
        players=players,
        action_spaces=design.action_spaces,
        type_spaces=type_spaces,
    )

    all_profiles = [
        dict(zip(players, reports, strict=True))
        for reports in product(*(design.action_spaces[player_id] for player_id in players))
    ]
    profile_keys = {_profile_key(profile, players) for profile in all_profiles}

    outcome_by_profile: dict[tuple[tuple[str, str], ...], str] = {}
    payments_by_profile: dict[tuple[tuple[str, str], ...], dict[str, Fraction]] = {}
    for entry in semantics.allocation_rule:
        key = _profile_key(entry.report_profile, players)
        payment_map = {player_id: Fraction(0) for player_id in players}
        payment_map.update(
            {player_id: Fraction(value) for player_id, value in entry.payments_by_player.items()}
        )
        outcome_by_profile[key] = entry.outcome_id
        payments_by_profile[key] = payment_map
    if set(outcome_by_profile) != profile_keys:
        raise ValueError("finite allocation_rule must cover every report profile exactly once")

    values: dict[tuple[str, str, str], Fraction] = {}
    utilities: dict[tuple[str, str, tuple[tuple[str, str], ...]], Fraction] = {}
    outcome_ids = {outcome.outcome_id for outcome in semantics.finite_outcomes}

    if semantics.utility_model is None:
        raise ValueError("finite_exact requires utility_model")
    utility_model = semantics.utility_model
    if utility_model.kind is MechanismUtilityModelKind.QUASI_LINEAR_SCALAR:
        for player_id in players:
            for type_label in type_spaces[player_id]:
                for outcome_id in outcome_ids:
                    values[(player_id, type_label, outcome_id)] = Fraction(0)
        for entry in utility_model.value_table:
            for outcome_id, value in entry.outcome_values.items():
                values[(entry.player_id, entry.type_label, outcome_id)] = Fraction(value)
    else:
        for entry in utility_model.utility_table:
            key = (entry.player_id, entry.true_type, _profile_key(entry.report_profile, players))
            utilities[key] = Fraction(entry.utility)
        expected_size = sum(
            len(type_spaces[player_id]) * len(profile_keys) for player_id in players
        )
        if len(utilities) != expected_size:
            raise ValueError(
                "explicit_table utility_model must enumerate every player/true_type/report_profile"
            )

    independent_prior: dict[str, dict[str, Fraction]] = {}
    joint_prior: list[tuple[dict[str, str], Fraction]] = []
    prior_kind = None
    if property_name in {
        MechanismConstraintType.BAYESIAN_IC.value,
        MechanismConstraintType.EX_INTERIM_IR.value,
    }:
        if semantics.prior is None:
            raise ValueError(f"{property_name} verification requires exact prior semantics")
        prior_kind = semantics.prior.kind
        if prior_kind is MechanismPriorKind.INDEPENDENT_EXACT:
            independent_prior = {
                entry.player_id: {
                    type_label: Fraction(probability)
                    for type_label, probability in entry.probabilities.items()
                }
                for entry in semantics.prior.player_priors
            }
        else:
            joint_prior = [
                (dict(entry.type_profile), Fraction(entry.probability))
                for entry in semantics.prior.joint_support
            ]

    return _FiniteMechanism(
        design=design,
        semantics=semantics,
        property_name=property_name,
        players=players,
        players_checked=_resolve_players_checked(design, property_name),
        type_spaces=type_spaces,
        profiles=all_profiles,
        profile_keys=profile_keys,
        outcome_by_profile=outcome_by_profile,
        payments_by_profile=payments_by_profile,
        values=values,
        utilities=utilities,
        prior_kind=prior_kind,
        independent_prior=independent_prior,
        joint_prior=joint_prior,
    )


def _normalize_envelope_mechanism(
    design: MechanismDesignSpec,
    semantics: MechanismSemanticsSpec,
    property_name: str,
) -> _Envelope1DMechanism:
    if semantics.fragment is not MechanismSemanticFragment.ENVELOPE_1D:
        raise ValueError("envelope_1d backend requires semantics.fragment='envelope_1d'")
    type_spaces = {item.player_id: item.type_space for item in design.bayesian_types}
    semantics.validate_against_declared_structure(
        players=design.players,
        action_spaces=design.action_spaces,
        type_spaces=type_spaces,
    )
    if semantics.envelope_1d is None:
        raise ValueError("envelope_1d semantics are missing")
    fragment: Envelope1DSemanticsSpec = semantics.envelope_1d
    type_labels = tuple(point.type_label for point in fragment.points)
    explicit_payment_labels = {
        point.type_label for point in fragment.points if point.payment is not None
    }
    if explicit_payment_labels and explicit_payment_labels != set(type_labels):
        raise ValueError(
            "envelope_1d payments must be declared for every point or omitted entirely"
        )
    payments = (
        {
            point.type_label: Fraction(point.payment)
            for point in fragment.points
            if point.payment is not None
        }
        if explicit_payment_labels
        else None
    )
    return _Envelope1DMechanism(
        property_name=property_name,
        player_id=fragment.player_id,
        type_labels=type_labels,
        type_values={point.type_label: Fraction(point.type_value) for point in fragment.points},
        allocation_by_label={
            point.type_label: Fraction(point.allocation) for point in fragment.points
        },
        payment_by_label=payments,
        normalization_type_label=fragment.normalization_type_label or type_labels[0],
        normalization_utility=Fraction(fragment.normalization_utility),
    )


def _normalize_cycmon_mechanism(
    design: MechanismDesignSpec,
    semantics: MechanismSemanticsSpec,
    property_name: str,
) -> _CycMonGridMechanism:
    if semantics.fragment is not MechanismSemanticFragment.CYCMON_GRID:
        raise ValueError("cycmon_lp backend requires semantics.fragment='cycmon_grid'")
    type_spaces = {item.player_id: item.type_space for item in design.bayesian_types}
    semantics.validate_against_declared_structure(
        players=design.players,
        action_spaces=design.action_spaces,
        type_spaces=type_spaces,
    )
    if semantics.cycmon_grid is None:
        raise ValueError("cycmon_grid semantics are missing")
    fragment: CycMonGridSemanticsSpec = semantics.cycmon_grid
    type_labels = tuple(point.type_label for point in fragment.type_points)
    explicit_payment_labels = {
        point.type_label for point in fragment.allocation_points if point.payment is not None
    }
    if explicit_payment_labels and explicit_payment_labels != set(type_labels):
        raise ValueError(
            "cycmon_grid payments must be declared for every point or omitted entirely"
        )
    payments = (
        {
            point.type_label: Fraction(point.payment)
            for point in fragment.allocation_points
            if point.payment is not None
        }
        if explicit_payment_labels
        else None
    )
    return _CycMonGridMechanism(
        property_name=property_name,
        player_id=fragment.player_id,
        type_labels=type_labels,
        coords_by_label={
            point.type_label: _fraction_tuple(point.coords) for point in fragment.type_points
        },
        allocation_by_label={
            point.type_label: _fraction_tuple(point.allocation)
            for point in fragment.allocation_points
        },
        payment_by_label=payments,
        normalization_type_label=fragment.normalization_type_label or type_labels[0],
        normalization_utility=Fraction(fragment.normalization_utility),
    )


def _finite_utility(
    mechanism: _FiniteMechanism,
    *,
    player_id: str,
    true_type: str,
    report_profile: dict[str, str],
) -> Fraction:
    key = _profile_key(report_profile, mechanism.players)
    if mechanism.semantics.utility_model is not None and (
        mechanism.semantics.utility_model.kind is MechanismUtilityModelKind.EXPLICIT_TABLE
    ):
        return mechanism.utilities[(player_id, true_type, key)]

    outcome_id = mechanism.outcome_by_profile[key]
    value = mechanism.values[(player_id, true_type, outcome_id)]
    payment = mechanism.payments_by_profile[key][player_id]
    return value - payment


def _conditional_support(
    mechanism: _FiniteMechanism,
    *,
    player_id: str,
    true_type: str,
) -> list[tuple[dict[str, str], Fraction]]:
    others = [other for other in mechanism.players if other != player_id]
    if mechanism.prior_kind is MechanismPriorKind.INDEPENDENT_EXACT:
        support: list[tuple[dict[str, str], Fraction]] = []
        for types in product(*(mechanism.type_spaces[other] for other in others)):
            profile = dict(zip(others, types, strict=True))
            probability = Fraction(1)
            for other, other_type in profile.items():
                probability *= mechanism.independent_prior[other][other_type]
            support.append((profile, probability))
        return support

    matching = [
        (profile, probability)
        for profile, probability in mechanism.joint_prior
        if profile[player_id] == true_type
    ]
    total = sum(probability for _, probability in matching)
    if total == 0:
        raise ValueError(
            f"joint_exact_table prior assigns zero probability to type '{true_type}' "
            f"for player '{player_id}'"
        )
    normalized: list[tuple[dict[str, str], Fraction]] = []
    for profile, probability in matching:
        normalized.append(
            (
                {other: profile[other] for other in mechanism.players if other != player_id},
                probability / total,
            )
        )
    return normalized


def _find_finite_negative_witness(
    mechanism: _FiniteMechanism,
) -> tuple[dict[str, Any] | None, int]:
    checks = 0
    if mechanism.property_name == MechanismConstraintType.DOMINANT_STRATEGY_IC.value:
        for player_id in mechanism.players_checked:
            others = [other for other in mechanism.players if other != player_id]
            for true_type in mechanism.type_spaces[player_id]:
                truthful_report = true_type
                for deviating_report in mechanism.design.action_spaces[player_id]:
                    if deviating_report == truthful_report:
                        continue
                    for other_types in product(*(mechanism.type_spaces[other] for other in others)):
                        checks += 1
                        other_profile = dict(zip(others, other_types, strict=True))
                        truthful_profile = {player_id: truthful_report, **other_profile}
                        deviating_profile = {player_id: deviating_report, **other_profile}
                        utility_truthful = _finite_utility(
                            mechanism,
                            player_id=player_id,
                            true_type=true_type,
                            report_profile=truthful_profile,
                        )
                        utility_deviating = _finite_utility(
                            mechanism,
                            player_id=player_id,
                            true_type=true_type,
                            report_profile=deviating_profile,
                        )
                        gain = utility_deviating - utility_truthful
                        if gain > 0:
                            return (
                                {
                                    "kind": "profitable_deviation",
                                    "agent_id": player_id,
                                    "true_type": true_type,
                                    "truthful_report": truthful_report,
                                    "deviating_report": deviating_report,
                                    "others_report_profile": other_profile,
                                    "utility_truthful": _fraction_to_text(utility_truthful),
                                    "utility_deviating": _fraction_to_text(utility_deviating),
                                    "gain": _fraction_to_text(gain),
                                },
                                checks,
                            )
        return None, checks

    if mechanism.property_name == MechanismConstraintType.BAYESIAN_IC.value:
        for player_id in mechanism.players_checked:
            for true_type in mechanism.type_spaces[player_id]:
                truthful_report = true_type
                for deviating_report in mechanism.design.action_spaces[player_id]:
                    if deviating_report == truthful_report:
                        continue
                    expected_gain = Fraction(0)
                    expectation_terms: list[dict[str, Any]] = []
                    for other_profile, probability in _conditional_support(
                        mechanism,
                        player_id=player_id,
                        true_type=true_type,
                    ):
                        checks += 1
                        truthful_profile = {player_id: truthful_report, **other_profile}
                        deviating_profile = {player_id: deviating_report, **other_profile}
                        utility_truthful = _finite_utility(
                            mechanism,
                            player_id=player_id,
                            true_type=true_type,
                            report_profile=truthful_profile,
                        )
                        utility_deviating = _finite_utility(
                            mechanism,
                            player_id=player_id,
                            true_type=true_type,
                            report_profile=deviating_profile,
                        )
                        weighted_gain = probability * (utility_deviating - utility_truthful)
                        expected_gain += weighted_gain
                        expectation_terms.append(
                            {
                                "other_types": other_profile,
                                "probability": _fraction_to_text(probability),
                                "utility_truthful": _fraction_to_text(utility_truthful),
                                "utility_deviating": _fraction_to_text(utility_deviating),
                                "weighted_gain": _fraction_to_text(weighted_gain),
                            }
                        )
                    if expected_gain > 0:
                        return (
                            {
                                "kind": "profitable_deviation",
                                "agent_id": player_id,
                                "true_type": true_type,
                                "truthful_report": truthful_report,
                                "deviating_report": deviating_report,
                                "expectation_terms": expectation_terms,
                                "expected_gain": _fraction_to_text(expected_gain),
                            },
                            checks,
                        )
        return None, checks

    if mechanism.property_name == MechanismConstraintType.EX_POST_IR.value:
        for player_id in mechanism.players_checked:
            others = [other for other in mechanism.players if other != player_id]
            for true_type in mechanism.type_spaces[player_id]:
                truthful_report = true_type
                for other_types in product(*(mechanism.type_spaces[other] for other in others)):
                    checks += 1
                    other_profile = dict(zip(others, other_types, strict=True))
                    truthful_profile = {player_id: truthful_report, **other_profile}
                    utility_truthful = _finite_utility(
                        mechanism,
                        player_id=player_id,
                        true_type=true_type,
                        report_profile=truthful_profile,
                    )
                    if utility_truthful < 0:
                        return (
                            {
                                "kind": "ir_violation",
                                "agent_id": player_id,
                                "true_type": true_type,
                                "truthful_report": truthful_report,
                                "others_report_profile": other_profile,
                                "utility_truthful": _fraction_to_text(utility_truthful),
                            },
                            checks,
                        )
        return None, checks

    for player_id in mechanism.players_checked:
        for true_type in mechanism.type_spaces[player_id]:
            truthful_report = true_type
            expected_utility = Fraction(0)
            expectation_terms: list[dict[str, Any]] = []
            for other_profile, probability in _conditional_support(
                mechanism,
                player_id=player_id,
                true_type=true_type,
            ):
                checks += 1
                truthful_profile = {player_id: truthful_report, **other_profile}
                utility_truthful = _finite_utility(
                    mechanism,
                    player_id=player_id,
                    true_type=true_type,
                    report_profile=truthful_profile,
                )
                expected_utility += probability * utility_truthful
                expectation_terms.append(
                    {
                        "other_types": other_profile,
                        "probability": _fraction_to_text(probability),
                        "utility_truthful": _fraction_to_text(utility_truthful),
                    }
                )
            if expected_utility < 0:
                return (
                    {
                        "kind": "ir_violation",
                        "agent_id": player_id,
                        "true_type": true_type,
                        "truthful_report": truthful_report,
                        "expectation_terms": expectation_terms,
                        "expected_utility": _fraction_to_text(expected_utility),
                    },
                    checks,
                )
    return None, checks


def _finite_positive_witness(mechanism: _FiniteMechanism, checks: int) -> dict[str, Any]:
    if mechanism.property_name in {
        MechanismConstraintType.DOMINANT_STRATEGY_IC.value,
        MechanismConstraintType.BAYESIAN_IC.value,
    }:
        return {
            "kind": "zero_regret_exhaustive",
            "players_checked": list(mechanism.players_checked),
            "profiles_checked": len(mechanism.profile_keys),
            "deviations_checked": checks,
            "max_regret": "0",
        }
    return {
        "kind": "truthful_utility_nonnegative",
        "players_checked": list(mechanism.players_checked),
        "profiles_checked": len(mechanism.profile_keys),
        "comparisons_checked": checks,
        "min_truthful_utility": "0",
    }


def _envelope_monotonicity_violation(
    mechanism: _Envelope1DMechanism,
) -> dict[str, Any] | None:
    for idx in range(1, len(mechanism.type_labels)):
        left = mechanism.type_labels[idx - 1]
        right = mechanism.type_labels[idx]
        if mechanism.allocation_by_label[right] < mechanism.allocation_by_label[left]:
            return {
                "kind": "allocation_impossibility",
                "agent_id": mechanism.player_id,
                "reason": "non_monotone_allocation",
                "violating_pair": [
                    {
                        "type_label": left,
                        "type_value": _fraction_to_text(mechanism.type_values[left]),
                        "allocation": _fraction_to_text(mechanism.allocation_by_label[left]),
                    },
                    {
                        "type_label": right,
                        "type_value": _fraction_to_text(mechanism.type_values[right]),
                        "allocation": _fraction_to_text(mechanism.allocation_by_label[right]),
                    },
                ],
            }
    return None


def _envelope_deviation_witness(
    mechanism: _Envelope1DMechanism,
    *,
    payments: dict[str, Fraction],
) -> tuple[dict[str, Any] | None, int]:
    checks = 0
    for true_label in mechanism.type_labels:
        truthful_value = (
            mechanism.type_values[true_label] * mechanism.allocation_by_label[true_label]
            - payments[true_label]
        )
        for report_label in mechanism.type_labels:
            if report_label == true_label:
                continue
            checks += 1
            deviating_value = (
                mechanism.type_values[true_label] * mechanism.allocation_by_label[report_label]
                - payments[report_label]
            )
            gain = deviating_value - truthful_value
            if gain > 0:
                return (
                    {
                        "kind": "profitable_deviation",
                        "agent_id": mechanism.player_id,
                        "true_type": true_label,
                        "truthful_report": true_label,
                        "deviating_report": report_label,
                        "utility_truthful": _fraction_to_text(truthful_value),
                        "utility_deviating": _fraction_to_text(deviating_value),
                        "gain": _fraction_to_text(gain),
                    },
                    checks,
                )
    return None, checks


def _synthesize_envelope_utilities_and_payments(
    mechanism: _Envelope1DMechanism,
    *,
    normalization_label: str,
    normalization_utility: Fraction,
) -> tuple[dict[str, Fraction], dict[str, Fraction]]:
    cumulative: dict[str, Fraction] = {mechanism.type_labels[0]: Fraction(0)}
    for idx in range(1, len(mechanism.type_labels)):
        left = mechanism.type_labels[idx - 1]
        right = mechanism.type_labels[idx]
        cumulative[right] = cumulative[left] + mechanism.allocation_by_label[left] * (
            mechanism.type_values[right] - mechanism.type_values[left]
        )
    base_utility = normalization_utility - cumulative[normalization_label]
    utilities = {label: base_utility + cumulative[label] for label in mechanism.type_labels}
    payments = {
        label: (
            mechanism.type_values[label] * mechanism.allocation_by_label[label] - utilities[label]
        )
        for label in mechanism.type_labels
    }
    return utilities, payments


def _evaluate_envelope_1d(
    mechanism: _Envelope1DMechanism,
    request: ICVerificationRequest,
    *,
    input_digest: str,
) -> tuple[ICVerificationReport, IncentiveCompatibilityCertificate | ICNegativeCertificate | None]:
    semantic_property = mechanism.property_name
    if semantic_property in {
        MechanismConstraintType.BAYESIAN_IC.value,
        MechanismConstraintType.EX_INTERIM_IR.value,
    }:
        semantic_property = (
            MechanismConstraintType.DOMINANT_STRATEGY_IC.value
            if semantic_property == MechanismConstraintType.BAYESIAN_IC.value
            else MechanismConstraintType.EX_POST_IR.value
        )
    if semantic_property not in {
        MechanismConstraintType.DOMINANT_STRATEGY_IC.value,
        MechanismConstraintType.EX_POST_IR.value,
    }:
        return (
            ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="envelope_1d",
                verdict="unsupported_fragment",
                input_digest=input_digest,
                notes=("envelope_1d supports only DSIC/BIC and ex_post/ex_interim IR",),
            ),
            None,
        )

    explicit_payments = mechanism.payment_by_label
    violation = _envelope_monotonicity_violation(mechanism)
    if explicit_payments is None and violation is not None:
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend="envelope_1d",
            verdict="negative",
            input_digest=input_digest,
            players_checked=(mechanism.player_id,),
            notes=("allocation-only 1D fragment is not monotone; no truthful payment rule exists",),
        )
        certificate = ICNegativeCertificate(
            property=request.property,
            backend="envelope_1d",
            input_digest=input_digest,
            arithmetic=request.exact_number_format,
            witness=violation,
        )
        return report, certificate

    if explicit_payments is not None:
        truthful_utility = (
            mechanism.type_values[mechanism.normalization_type_label]
            * mechanism.allocation_by_label[mechanism.normalization_type_label]
            - explicit_payments[mechanism.normalization_type_label]
        )
        utilities, synthesized_payments = _synthesize_envelope_utilities_and_payments(
            mechanism,
            normalization_label=mechanism.normalization_type_label,
            normalization_utility=truthful_utility,
        )
        witness, checks = _envelope_deviation_witness(mechanism, payments=explicit_payments)
        if witness is not None:
            report = ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="envelope_1d",
                verdict="negative",
                input_digest=input_digest,
                players_checked=(mechanism.player_id,),
                deviations_checked=checks,
                notes=("explicit 1D payment rule admits a profitable deviation",),
            )
            certificate = ICNegativeCertificate(
                property=request.property,
                backend="envelope_1d",
                input_digest=input_digest,
                arithmetic=request.exact_number_format,
                witness=witness,
            )
            return report, certificate
        payment_source = "explicit"
        payments = explicit_payments
    else:
        if not request.allow_payment_synthesis:
            report = ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="envelope_1d",
                verdict="semantic_validation_failure",
                input_digest=input_digest,
                notes=("payment synthesis is required for allocation-only envelope_1d semantics",),
            )
            return report, None
        utilities, synthesized_payments = _synthesize_envelope_utilities_and_payments(
            mechanism,
            normalization_label=mechanism.normalization_type_label,
            normalization_utility=mechanism.normalization_utility,
        )
        payment_source = "synthesized"
        payments = synthesized_payments
        checks = len(mechanism.type_labels) * max(len(mechanism.type_labels) - 1, 0)

    if request.mode == "counterexample_search":
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend="envelope_1d",
            verdict="inconclusive",
            input_digest=input_digest,
            players_checked=(mechanism.player_id,),
            deviations_checked=checks,
            notes=("counterexample_search found no exact witness in the envelope_1d fragment",),
        )
        return report, None

    if semantic_property == MechanismConstraintType.EX_POST_IR.value:
        for label in mechanism.type_labels:
            truthful_utility = (
                mechanism.type_values[label] * mechanism.allocation_by_label[label]
                - payments[label]
            )
            if truthful_utility < 0:
                report = ICVerificationReport(
                    property=request.property,
                    mode=request.mode,
                    backend="envelope_1d",
                    verdict="negative",
                    input_digest=input_digest,
                    players_checked=(mechanism.player_id,),
                    deviations_checked=len(mechanism.type_labels),
                    notes=("truthful utility is negative for at least one 1D type",),
                )
                certificate = ICNegativeCertificate(
                    property=request.property,
                    backend="envelope_1d",
                    input_digest=input_digest,
                    arithmetic=request.exact_number_format,
                    witness={
                        "kind": "ir_violation",
                        "agent_id": mechanism.player_id,
                        "true_type": label,
                        "truthful_report": label,
                        "utility_truthful": _fraction_to_text(truthful_utility),
                    },
                )
                return report, certificate

    report = ICVerificationReport(
        property=request.property,
        mode=request.mode,
        backend="envelope_1d",
        verdict="positive",
        input_digest=input_digest,
        players_checked=(mechanism.player_id,),
        deviations_checked=checks,
        notes=("exact monotonicity and envelope replay passed",),
    )
    certificate = IncentiveCompatibilityCertificate(
        property=request.property,
        backend="envelope_1d",
        input_digest=input_digest,
        arithmetic=request.exact_number_format,
        witness={
            "kind": (
                "envelope_identity"
                if semantic_property == MechanismConstraintType.DOMINANT_STRATEGY_IC.value
                else "truthful_utility_nonnegative"
            ),
            "agent_id": mechanism.player_id,
            "type_grid": [
                {
                    "type_label": label,
                    "type_value": _fraction_to_text(mechanism.type_values[label]),
                }
                for label in mechanism.type_labels
            ],
            "allocation_schedule": [
                _fraction_to_text(mechanism.allocation_by_label[label])
                for label in mechanism.type_labels
            ],
            "payment_schedule": [
                _fraction_to_text(payments[label]) for label in mechanism.type_labels
            ],
            "utility_schedule": [
                _fraction_to_text(utilities[label]) for label in mechanism.type_labels
            ],
            "normalization": {
                "type_label": mechanism.normalization_type_label,
                "utility": _fraction_to_text(utilities[mechanism.normalization_type_label]),
            },
            "payment_source": payment_source,
        },
    )
    return report, certificate


def _cycmon_edge_weight(
    mechanism: _CycMonGridMechanism,
    source_label: str,
    target_label: str,
) -> Fraction:
    return _dot(
        _subtract(
            mechanism.coords_by_label[target_label],
            mechanism.coords_by_label[source_label],
        ),
        mechanism.allocation_by_label[source_label],
    )


def _find_negative_cycle(
    mechanism: _CycMonGridMechanism,
) -> tuple[list[str] | None, dict[str, Fraction]]:
    labels = list(mechanism.type_labels)
    dist = {label: Fraction(0) for label in labels}
    pred: dict[str, str | None] = dict.fromkeys(labels)
    last_updated: str | None = None
    for _ in range(len(labels)):
        last_updated = None
        for source in labels:
            for target in labels:
                weight = -_cycmon_edge_weight(mechanism, source, target)
                candidate = dist[source] + weight
                if candidate < dist[target]:
                    dist[target] = candidate
                    pred[target] = source
                    last_updated = target
    if last_updated is None:
        return None, dist
    cursor = last_updated
    for _ in range(len(labels)):
        predecessor = pred[cursor]
        if predecessor is None:
            break
        cursor = predecessor
    cycle: list[str] = [cursor]
    next_label = pred[cursor]
    while next_label is not None and next_label not in cycle:
        cycle.append(next_label)
        next_label = pred[next_label]
    if next_label is None:
        return None, dist
    cycle.append(next_label)
    cycle.reverse()
    return cycle, dist


def _payments_from_utilities(
    mechanism: _CycMonGridMechanism,
    utilities: dict[str, Fraction],
) -> dict[str, Fraction]:
    return {
        label: _dot(mechanism.coords_by_label[label], mechanism.allocation_by_label[label])
        - utilities[label]
        for label in mechanism.type_labels
    }


def _cycmon_deviation_witness(
    mechanism: _CycMonGridMechanism,
    *,
    payments: dict[str, Fraction],
) -> tuple[dict[str, Any] | None, int]:
    checks = 0
    for true_label in mechanism.type_labels:
        truthful_utility = (
            _dot(mechanism.coords_by_label[true_label], mechanism.allocation_by_label[true_label])
            - payments[true_label]
        )
        for report_label in mechanism.type_labels:
            if report_label == true_label:
                continue
            checks += 1
            deviating_utility = (
                _dot(
                    mechanism.coords_by_label[true_label],
                    mechanism.allocation_by_label[report_label],
                )
                - payments[report_label]
            )
            gain = deviating_utility - truthful_utility
            if gain > 0:
                return (
                    {
                        "kind": "profitable_deviation",
                        "agent_id": mechanism.player_id,
                        "true_type": true_label,
                        "truthful_report": true_label,
                        "deviating_report": report_label,
                        "utility_truthful": _fraction_to_text(truthful_utility),
                        "utility_deviating": _fraction_to_text(deviating_utility),
                        "gain": _fraction_to_text(gain),
                    },
                    checks,
                )
    return None, checks


def _evaluate_cycmon_grid(
    mechanism: _CycMonGridMechanism,
    request: ICVerificationRequest,
    *,
    input_digest: str,
) -> tuple[ICVerificationReport, IncentiveCompatibilityCertificate | ICNegativeCertificate | None]:
    semantic_property = mechanism.property_name
    if semantic_property in {
        MechanismConstraintType.BAYESIAN_IC.value,
        MechanismConstraintType.EX_INTERIM_IR.value,
    }:
        semantic_property = (
            MechanismConstraintType.DOMINANT_STRATEGY_IC.value
            if semantic_property == MechanismConstraintType.BAYESIAN_IC.value
            else MechanismConstraintType.EX_POST_IR.value
        )
    if semantic_property not in {
        MechanismConstraintType.DOMINANT_STRATEGY_IC.value,
        MechanismConstraintType.EX_POST_IR.value,
    }:
        return (
            ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="cycmon_lp",
                verdict="unsupported_fragment",
                input_digest=input_digest,
                notes=("cycmon_lp supports only DSIC/BIC and ex_post/ex_interim IR",),
            ),
            None,
        )

    explicit_payments = mechanism.payment_by_label
    cycle, dist = _find_negative_cycle(mechanism)
    if explicit_payments is None:
        if cycle is not None:
            cycle_sum = Fraction(0)
            for idx in range(len(cycle) - 1):
                cycle_sum += _cycmon_edge_weight(mechanism, cycle[idx], cycle[idx + 1])
            report = ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="cycmon_lp",
                verdict="negative",
                input_digest=input_digest,
                players_checked=(mechanism.player_id,),
                notes=("allocation-only multidimensional fragment violates cyclical monotonicity",),
            )
            certificate = ICNegativeCertificate(
                property=request.property,
                backend="cycmon_lp",
                input_digest=input_digest,
                arithmetic=request.exact_number_format,
                witness={
                    "kind": "negative_cycle_impossibility",
                    "agent_id": mechanism.player_id,
                    "cycle": [
                        {
                            "type_label": label,
                            "coords": _vector_to_text(mechanism.coords_by_label[label]),
                        }
                        for label in cycle
                    ],
                    "cycle_sum": _fraction_to_text(cycle_sum),
                },
            )
            return report, certificate
        utilities = {label: -dist[label] for label in mechanism.type_labels}
        shift = mechanism.normalization_utility - utilities[mechanism.normalization_type_label]
        utilities = {label: value + shift for label, value in utilities.items()}
        payments = _payments_from_utilities(mechanism, utilities)
        checks = len(mechanism.type_labels) * max(len(mechanism.type_labels) - 1, 0)
        payment_source = "synthesized"
    else:
        payments = explicit_payments
        utilities = {
            label: (
                _dot(mechanism.coords_by_label[label], mechanism.allocation_by_label[label])
                - payments[label]
            )
            for label in mechanism.type_labels
        }
        witness, checks = _cycmon_deviation_witness(mechanism, payments=payments)
        if witness is not None:
            report = ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="cycmon_lp",
                verdict="negative",
                input_digest=input_digest,
                players_checked=(mechanism.player_id,),
                deviations_checked=checks,
                notes=("explicit multidimensional payment rule admits a profitable deviation",),
            )
            certificate = ICNegativeCertificate(
                property=request.property,
                backend="cycmon_lp",
                input_digest=input_digest,
                arithmetic=request.exact_number_format,
                witness=witness,
            )
            return report, certificate
        payment_source = "explicit"

    if request.mode == "counterexample_search":
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend="cycmon_lp",
            verdict="inconclusive",
            input_digest=input_digest,
            players_checked=(mechanism.player_id,),
            deviations_checked=checks,
            notes=("counterexample_search found no exact witness in the cycmon_lp fragment",),
        )
        return report, None

    if semantic_property == MechanismConstraintType.EX_POST_IR.value:
        for label in mechanism.type_labels:
            truthful_utility = utilities[label]
            if truthful_utility < 0:
                report = ICVerificationReport(
                    property=request.property,
                    mode=request.mode,
                    backend="cycmon_lp",
                    verdict="negative",
                    input_digest=input_digest,
                    players_checked=(mechanism.player_id,),
                    deviations_checked=len(mechanism.type_labels),
                    notes=("truthful utility is negative for at least one multidimensional type",),
                )
                certificate = ICNegativeCertificate(
                    property=request.property,
                    backend="cycmon_lp",
                    input_digest=input_digest,
                    arithmetic=request.exact_number_format,
                    witness={
                        "kind": "ir_violation",
                        "agent_id": mechanism.player_id,
                        "true_type": label,
                        "truthful_report": label,
                        "utility_truthful": _fraction_to_text(truthful_utility),
                    },
                )
                return report, certificate

    report = ICVerificationReport(
        property=request.property,
        mode=request.mode,
        backend="cycmon_lp",
        verdict="positive",
        input_digest=input_digest,
        players_checked=(mechanism.player_id,),
        deviations_checked=checks,
        notes=("exact utility-potential replay passed",),
    )
    certificate = IncentiveCompatibilityCertificate(
        property=request.property,
        backend="cycmon_lp",
        input_digest=input_digest,
        arithmetic=request.exact_number_format,
        witness={
            "kind": (
                "utility_potential"
                if semantic_property == MechanismConstraintType.DOMINANT_STRATEGY_IC.value
                else "truthful_utility_nonnegative"
            ),
            "agent_id": mechanism.player_id,
            "type_points": [
                {
                    "type_label": label,
                    "coords": _vector_to_text(mechanism.coords_by_label[label]),
                }
                for label in mechanism.type_labels
            ],
            "allocation_vectors": [
                {
                    "type_label": label,
                    "allocation": _vector_to_text(mechanism.allocation_by_label[label]),
                }
                for label in mechanism.type_labels
            ],
            "utility_potential": {
                label: _fraction_to_text(utilities[label]) for label in mechanism.type_labels
            },
            "payment_schedule": {
                label: _fraction_to_text(payments[label]) for label in mechanism.type_labels
            },
            "normalization": {
                "type_label": mechanism.normalization_type_label,
                "utility": _fraction_to_text(utilities[mechanism.normalization_type_label]),
            },
            "payment_source": payment_source,
        },
    )
    return report, certificate


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Fraction):
        return _fraction_to_text(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _json_safe_mapping(value: Mapping[str, object]) -> dict[str, object]:
    safe = _json_safe(value)
    if not isinstance(safe, dict):
        raise TypeError("json-safe mapping conversion produced a non-mapping value")
    return safe


def _coerce_optional_float(params: Mapping[str, Any], key: str) -> float | None:
    value = params.get(key)
    if value is None:
        return None
    return float(value)


def _coerce_optional_int(params: Mapping[str, Any], key: str) -> int | None:
    value = params.get(key)
    if value is None:
        return None
    return int(value)


def _merge_family_params(
    binding_params: Mapping[str, Any],
    intervention_params: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(intervention_params)
    merged.update(binding_params)
    return merged


def _mechanism_family_candidates(policy: PolicySpec) -> list[_MechanismFamilyCandidate]:
    design = policy.mechanism_design
    if design is None:
        return []

    interventions_by_id = {
        intervention.intervention_id: intervention for intervention in policy.interventions
    }
    bindings_by_mechanism: dict[str, list[Any]] = {}
    for binding in policy.mechanism_bindings:
        bindings_by_mechanism.setdefault(binding.mechanism_id, []).append(binding)

    ordered_mechanism_ids = [
        mechanism_id
        for mechanism_id in design.mechanism_ids
        if mechanism_id in _MECHANISM_FAMILY_IDS
    ]
    if not ordered_mechanism_ids:
        ordered_mechanism_ids = [
            binding.mechanism_id
            for binding in policy.mechanism_bindings
            if binding.mechanism_id in _MECHANISM_FAMILY_IDS
        ]
    if not ordered_mechanism_ids:
        ordered_mechanism_ids = [
            intervention.kind
            for intervention in policy.interventions
            if intervention.kind in _MECHANISM_FAMILY_IDS
        ]

    candidates: list[_MechanismFamilyCandidate] = []
    seen: set[tuple[str, str]] = set()
    for mechanism_id in ordered_mechanism_ids:
        bindings = bindings_by_mechanism.get(mechanism_id, [])
        if not bindings:
            for intervention in policy.interventions:
                if intervention.kind != mechanism_id:
                    continue
                key = (mechanism_id, intervention.intervention_id)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    _MechanismFamilyCandidate(
                        mechanism_id=mechanism_id,
                        intervention_id=intervention.intervention_id,
                        params=dict(intervention.params),
                    )
                )
            continue

        for binding in bindings:
            for intervention_id in binding.intervention_ids:
                intervention = interventions_by_id.get(intervention_id)
                if intervention is None:
                    continue
                key = (mechanism_id, intervention_id)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    _MechanismFamilyCandidate(
                        mechanism_id=mechanism_id,
                        intervention_id=intervention_id,
                        params=_merge_family_params(
                            binding.config_overrides,
                            intervention.params,
                        ),
                    )
                )
    return candidates


def _family_constraint_supported(mechanism_id: str, property_name: str) -> bool:
    if mechanism_id in _TAX_MECHANISM_IDS:
        return property_name in {
            MechanismConstraintType.DOMINANT_STRATEGY_IC.value,
            MechanismConstraintType.BAYESIAN_IC.value,
            MechanismConstraintType.EX_POST_IR.value,
            MechanismConstraintType.EX_INTERIM_IR.value,
        }
    if mechanism_id in _LICENSE_MECHANISM_IDS:
        return property_name in {
            MechanismConstraintType.DOMINANT_STRATEGY_IC.value,
            MechanismConstraintType.BAYESIAN_IC.value,
            MechanismConstraintType.EX_POST_IR.value,
            MechanismConstraintType.EX_INTERIM_IR.value,
        }
    return False


def _mechanism_family_deviations_checked(certificate: MechanismICCertificate) -> int:
    class_count = 1
    classes = certificate.witness_summary.get("classes")
    if isinstance(classes, Mapping) and classes:
        class_count = len(classes)
    return class_count * len(certificate.grid) * max(len(certificate.grid) - 1, 0)


def _mechanism_family_positive_for_property(
    certificate: MechanismICCertificate,
    property_name: str,
) -> bool:
    if property_name in {
        MechanismConstraintType.EX_POST_IR.value,
        MechanismConstraintType.EX_INTERIM_IR.value,
    }:
        return certificate.interim_ir_passed is True
    return certificate.status == MechanismCertificateStatus.CERTIFIED


def _mechanism_family_negative_witness(
    *,
    mechanism_id: str,
    certificate: MechanismICCertificate,
    property_name: str,
    welfare_bound: MechanismWelfareLossBound | None,
) -> dict[str, Any]:
    if property_name in {
        MechanismConstraintType.EX_POST_IR.value,
        MechanismConstraintType.EX_INTERIM_IR.value,
    }:
        return {
            "kind": "mechanism_family_ir_violation",
            "mechanism_id": mechanism_id,
            "family": certificate.family.value,
            "interim_ir_passed": certificate.interim_ir_passed,
            "witness_summary": _json_safe(certificate.witness_summary),
        }

    if not certificate.monotonicity_passed:
        reason = "non_monotone_earnings_schedule"
        if certificate.family in {
            MechanismFamily.LICENSE_SCORING_RESERVE,
            MechanismFamily.LICENSE_MYERSON_SCORE,
        }:
            reason = "non_monotone_allocation_rule"
        violation_kind = "allocation_impossibility"
    elif (
        certificate.payment_residual_max is not None
        and certificate.payment_residual_max > certificate.tolerance
    ):
        reason = "payment_identity_residual_exceeds_tolerance"
        violation_kind = "payment_identity_violation"
    elif (
        certificate.profitable_deviation_max is not None
        and certificate.profitable_deviation_max > certificate.tolerance
    ):
        reason = "profitable_deviation_bound_exceeds_tolerance"
        violation_kind = "profitable_deviation"
    elif certificate.interim_ir_passed is False:
        reason = "interim_ir_violation"
        violation_kind = "ir_violation"
    else:
        reason = "mechanism_family_certificate_rejected"
        violation_kind = "mechanism_family_violation"

    witness: dict[str, Any] = {
        "kind": violation_kind,
        "reason": reason,
        "mechanism_id": mechanism_id,
        "family": certificate.family.value,
        "status": certificate.status.value,
        "monotonicity_passed": certificate.monotonicity_passed,
        "monotonicity_margin": certificate.monotonicity_margin,
        "envelope_residual_max": certificate.envelope_residual_max,
        "payment_residual_max": certificate.payment_residual_max,
        "profitable_deviation_max": certificate.profitable_deviation_max,
        "tolerance": certificate.tolerance,
        "witness_summary": _json_safe(certificate.witness_summary),
    }
    if welfare_bound is not None:
        witness["welfare_loss_upper_bound"] = welfare_bound.upper_bound
        witness["welfare_bound_type"] = welfare_bound.bound_type
    return _json_safe_mapping(witness)


def _mechanism_family_positive_witness(
    *,
    candidate: _MechanismFamilyCandidate,
    family_spec: MechanismFamilySpec,
    certificate: MechanismICCertificate,
    welfare_bound: MechanismWelfareLossBound | None,
) -> dict[str, Any]:
    witness: dict[str, Any] = {
        "kind": "mechanism_family_certificate",
        "mechanism_id": candidate.mechanism_id,
        "intervention_id": candidate.intervention_id,
        "family": family_spec.family.value,
        "verification_mode": family_spec.verification_mode.value,
        "certificate_type": certificate.certificate_type,
        "status": certificate.status.value,
        "grid_role": certificate.grid_role,
        "grid": list(certificate.grid),
        "monotonicity_passed": certificate.monotonicity_passed,
        "monotonicity_margin": certificate.monotonicity_margin,
        "envelope_residual_max": certificate.envelope_residual_max,
        "payment_residual_max": certificate.payment_residual_max,
        "profitable_deviation_max": certificate.profitable_deviation_max,
        "interim_ir_passed": certificate.interim_ir_passed,
        "budget_feasible": certificate.budget_feasible,
        "revenue_value": certificate.revenue_value,
        "revenue_floor": certificate.revenue_floor,
        "family_assumptions": list(family_spec.assumptions),
        "witness_summary": _json_safe(certificate.witness_summary),
    }
    if welfare_bound is not None:
        witness["welfare_loss_bound"] = welfare_bound.model_dump(mode="json")
    return _json_safe_mapping(witness)


def _certify_tax_family(
    candidate: _MechanismFamilyCandidate,
) -> tuple[MechanismICCertificate, MechanismWelfareLossBound]:
    params = candidate.params
    assumptions_hash = params.get("assumptions_hash")
    metadata = {
        "intervention_id": candidate.intervention_id,
        "source": "policy_spec.mechanism_binding",
    }
    if candidate.mechanism_id == "bayes_tax_affine_v1":
        gamma = params.get("gamma")
        if gamma is None:
            raise ValueError("bayes_tax_affine_v1 requires parameter 'gamma'")
        return certify_affine_tax(
            mechanism_id=candidate.mechanism_id,
            type_grid=params["type_grid"],
            gamma=float(gamma),
            u0=float(params.get("u0", 0.0)),
            prior_weights=params.get("prior_weights"),
            revenue_floor=_coerce_optional_float(params, "revenue_floor"),
            tolerance=float(params.get("tolerance", 1e-9)),
            assumptions_hash=str(assumptions_hash) if assumptions_hash is not None else None,
            metadata=metadata,
        )
    return certify_piecewise_linear_tax(
        mechanism_id=candidate.mechanism_id,
        type_grid=params["type_grid"],
        earnings_schedule=params["earnings_schedule"],
        u0=float(params.get("u0", 0.0)),
        prior_weights=params.get("prior_weights"),
        revenue_floor=_coerce_optional_float(params, "revenue_floor"),
        tolerance=float(params.get("tolerance", 1e-9)),
        assumptions_hash=str(assumptions_hash) if assumptions_hash is not None else None,
        metadata=metadata,
    )


def _certify_license_family(
    candidate: _MechanismFamilyCandidate,
    property_name: str,
) -> tuple[MechanismICCertificate, MechanismWelfareLossBound]:
    params = candidate.params
    assumptions_hash = params.get("assumptions_hash")
    metadata = {
        "intervention_id": candidate.intervention_id,
        "source": "policy_spec.mechanism_binding",
        "score_weight_alpha": _json_safe(params.get("alpha")),
        "public_score_weight_lambda": _json_safe(params.get("lambda")),
    }
    constraint_type = (
        MechanismConstraintType.BAYESIAN_IC
        if property_name == MechanismConstraintType.BAYESIAN_IC.value
        else MechanismConstraintType.DOMINANT_STRATEGY_IC
    )
    certificate = certify_license_scoring_auction(
        mechanism_id=candidate.mechanism_id,
        bid_grid=params["bid_grid"],
        allocation_rule=params["allocation_rule"],
        payments=params["payments"],
        reserve_price=params.get("reserve_price"),
        constraint_type=constraint_type,
        feasibility_family=str(params.get("feasibility_family", "top_k")),
        tolerance=float(params.get("tolerance", 1e-9)),
        assumptions_hash=str(assumptions_hash) if assumptions_hash is not None else None,
        metadata=metadata,
    )
    if candidate.mechanism_id == "license_myerson_score_v1":
        certificate = certificate.model_copy(
            update={"family": MechanismFamily.LICENSE_MYERSON_SCORE}
        )

    n_bidders = _coerce_optional_int(params, "n_bidders")
    k_units = _coerce_optional_int(params, "k_units")
    cdf_at_reserve = _coerce_optional_float(params, "cdf_at_reserve")
    reserve_price = params.get("reserve_price")
    if isinstance(reserve_price, Mapping) or reserve_price is None:
        reserve_for_bound = None
    else:
        reserve_for_bound = float(reserve_price)
    if n_bidders is None:
        raise ValueError(f"{candidate.mechanism_id} requires parameter 'n_bidders'")
    if k_units is None:
        raise ValueError(f"{candidate.mechanism_id} requires parameter 'k_units'")
    if cdf_at_reserve is None:
        raise ValueError(f"{candidate.mechanism_id} requires parameter 'cdf_at_reserve'")
    if reserve_for_bound is None:
        raise ValueError(
            f"{candidate.mechanism_id} requires a scalar 'reserve_price' to build the welfare-loss bound"
        )
    bound = build_reserve_auction_welfare_loss_bound(
        mechanism_id=candidate.mechanism_id,
        n_bidders=n_bidders,
        k_units=k_units,
        reserve_price=reserve_for_bound,
        cdf_at_reserve=cdf_at_reserve,
        assumptions_hash=str(assumptions_hash) if assumptions_hash is not None else None,
        metadata=metadata,
    )
    if candidate.mechanism_id == "license_myerson_score_v1":
        bound = bound.model_copy(update={"family": MechanismFamily.LICENSE_MYERSON_SCORE})
    return certificate, bound


def _evaluate_mechanism_family_candidate(
    candidate: _MechanismFamilyCandidate,
    request: ICVerificationRequest,
    *,
    input_digest: str,
) -> _MechanismFamilyEvaluation:
    family_spec = get_mechanism_family_spec(candidate.mechanism_id)
    if not _family_constraint_supported(candidate.mechanism_id, request.property):
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend="mechanism_family",
            verdict="unsupported_fragment",
            input_digest=input_digest,
            notes=(
                f"mechanism family '{candidate.mechanism_id}' does not support "
                f"property '{request.property}'",
            ),
        )
        return _MechanismFamilyEvaluation(report=report, certificate=None, family_spec=family_spec)

    if candidate.mechanism_id in _TAX_MECHANISM_IDS:
        mechanism_certificate, welfare_bound = _certify_tax_family(candidate)
    else:
        mechanism_certificate, welfare_bound = _certify_license_family(
            candidate,
            request.property,
        )

    deviations_checked = _mechanism_family_deviations_checked(mechanism_certificate)
    positive = _mechanism_family_positive_for_property(mechanism_certificate, request.property)
    if request.mode == "counterexample_search" and positive:
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend="mechanism_family",
            verdict="inconclusive",
            input_digest=input_digest,
            deviations_checked=deviations_checked,
            notes=("counterexample_search found no Phase 3 mechanism-family violation",),
        )
        return _MechanismFamilyEvaluation(
            report=report,
            certificate=None,
            family_spec=family_spec,
            mechanism_certificate=mechanism_certificate,
            welfare_bound=welfare_bound,
        )

    if positive:
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend="mechanism_family",
            verdict="positive",
            input_digest=input_digest,
            players_checked=(),
            deviations_checked=deviations_checked,
            notes=("Phase 3 mechanism-family constructive certificate passed",),
        )
        certificate = IncentiveCompatibilityCertificate(
            property=request.property,
            backend="mechanism_family",
            input_digest=input_digest,
            arithmetic="decimal_string",
            witness=_mechanism_family_positive_witness(
                candidate=candidate,
                family_spec=family_spec,
                certificate=mechanism_certificate,
                welfare_bound=welfare_bound,
            ),
        )
        return _MechanismFamilyEvaluation(
            report=report,
            certificate=certificate,
            family_spec=family_spec,
            mechanism_certificate=mechanism_certificate,
            welfare_bound=welfare_bound,
        )

    report = ICVerificationReport(
        property=request.property,
        mode=request.mode,
        backend="mechanism_family",
        verdict="negative",
        input_digest=input_digest,
        deviations_checked=deviations_checked,
        notes=("Phase 3 mechanism-family verifier found a constructive violation",),
    )
    certificate = ICNegativeCertificate(
        property=request.property,
        backend="mechanism_family",
        input_digest=input_digest,
        arithmetic="decimal_string",
        witness=_mechanism_family_negative_witness(
            mechanism_id=candidate.mechanism_id,
            certificate=mechanism_certificate,
            property_name=request.property,
            welfare_bound=welfare_bound,
        ),
    )
    return _MechanismFamilyEvaluation(
        report=report,
        certificate=certificate,
        family_spec=family_spec,
        mechanism_certificate=mechanism_certificate,
        welfare_bound=welfare_bound,
    )


def _combine_mechanism_family_evaluations(
    evaluations: list[_MechanismFamilyEvaluation],
    request: ICVerificationRequest,
    *,
    input_digest: str,
) -> _MechanismFamilyEvaluation | None:
    if not evaluations:
        return None
    if len(evaluations) == 1:
        return evaluations[0]

    failed = [
        evaluation
        for evaluation in evaluations
        if evaluation.report.verdict != "positive"
        or not isinstance(evaluation.certificate, IncentiveCompatibilityCertificate)
    ]
    if failed:
        first = failed[0]
        report = first.report.model_copy(
            update={
                "notes": (
                    *first.report.notes,
                    "Phase 3 mechanism-family package refused because at least one family did not certify.",
                )
            }
        )
        return first.__class__(
            report=report,
            certificate=first.certificate,
            family_spec=first.family_spec,
            mechanism_certificate=first.mechanism_certificate,
            welfare_bound=first.welfare_bound,
        )

    mechanism_ids: list[str] = []
    per_family: list[dict[str, Any]] = []
    proof_artifacts: list[ArtifactRef] = []
    deviations_checked = 0
    for evaluation in evaluations:
        certificate = evaluation.certificate
        if not isinstance(certificate, IncentiveCompatibilityCertificate):
            continue
        witness = _json_safe_mapping(certificate.witness)
        mechanism_id = str(
            witness.get("mechanism_id")
            or getattr(evaluation.mechanism_certificate, "mechanism_id", "")
        )
        if mechanism_id:
            mechanism_ids.append(mechanism_id)
        per_family.append(witness)
        proof_artifacts.extend(certificate.proof_artifacts)
        deviations_checked += evaluation.report.deviations_checked

    mechanism_ids = list(dict.fromkeys(mechanism_ids))
    report = ICVerificationReport(
        property=request.property,
        mode=request.mode,
        backend="mechanism_family",
        verdict="positive",
        input_digest=input_digest,
        deviations_checked=deviations_checked,
        notes=("Phase 3 mechanism-family certificate package passed",),
    )
    certificate = IncentiveCompatibilityCertificate(
        property=request.property,
        backend="mechanism_family",
        input_digest=input_digest,
        arithmetic="decimal_string",
        witness={
            "kind": "mechanism_family_certificate_package",
            "mechanism_ids": mechanism_ids,
            "covered_mechanism_ids": mechanism_ids,
            "per_family": per_family,
        },
        proof_artifacts=proof_artifacts,
    )
    return _MechanismFamilyEvaluation(
        report=report,
        certificate=certificate,
        component_evaluations=tuple(evaluations),
    )


def _try_evaluate_mechanism_family(
    policy: PolicySpec,
    request: ICVerificationRequest,
    *,
    input_digest: str,
) -> _MechanismFamilyEvaluation | None:
    if request.backend_hint not in {"auto", "envelope_1d"}:
        return None
    evaluations: list[_MechanismFamilyEvaluation] = []
    for candidate in _mechanism_family_candidates(policy):
        if (
            request.backend_hint == "envelope_1d"
            and candidate.mechanism_id not in _TAX_MECHANISM_IDS
        ):
            continue
        evaluations.append(
            _evaluate_mechanism_family_candidate(
                candidate,
                request,
                input_digest=input_digest,
            )
        )
    return _combine_mechanism_family_evaluations(
        evaluations,
        request,
        input_digest=input_digest,
    )


def _artifact_ref_from_ir_ref(ref: object) -> ArtifactRef:
    if hasattr(ref, "model_dump"):
        return ArtifactRef.model_validate(ref.model_dump(mode="json"))
    return ArtifactRef.model_validate(ref)


def _attach_mechanism_family_sidecars(
    store: ArtifactStore,
    request: ICVerificationRequest,
    evaluation: _MechanismFamilyEvaluation,
) -> IncentiveCompatibilityCertificate | ICNegativeCertificate | None:
    certificate = evaluation.certificate
    if (
        certificate is not None
        and evaluation.component_evaluations
        and isinstance(certificate, IncentiveCompatibilityCertificate)
    ):
        return _attach_mechanism_family_package_sidecars(
            store,
            request,
            certificate,
            evaluation.component_evaluations,
        )
    if (
        certificate is None
        or evaluation.family_spec is None
        or evaluation.mechanism_certificate is None
    ):
        return certificate

    inputs = _request_inputs(request)
    family_spec_ref = persist_mechanism_family_spec(
        store,
        evaluation.family_spec,
        inputs=inputs,
    )
    mechanism_certificate_ref = persist_mechanism_ic_certificate(
        store,
        evaluation.mechanism_certificate,
        inputs=inputs,
    )
    proof_artifacts = [
        _artifact_ref_from_ir_ref(family_spec_ref),
        _artifact_ref_from_ir_ref(mechanism_certificate_ref),
    ]

    witness = dict(certificate.witness)
    witness["mechanism_family_spec_ref"] = family_spec_ref.model_dump(mode="json")
    witness["mechanism_ic_certificate_ref"] = mechanism_certificate_ref.model_dump(mode="json")
    if evaluation.welfare_bound is not None:
        welfare_bound_ref = persist_mechanism_welfare_loss_bound(
            store,
            evaluation.welfare_bound,
            inputs=inputs,
        )
        proof_artifacts.append(_artifact_ref_from_ir_ref(welfare_bound_ref))
        witness["mechanism_welfare_loss_bound_ref"] = welfare_bound_ref.model_dump(mode="json")

    return certificate.model_copy(
        update={
            "witness": witness,
            "proof_artifacts": [*certificate.proof_artifacts, *proof_artifacts],
        }
    )


def _attach_mechanism_family_package_sidecars(
    store: ArtifactStore,
    request: ICVerificationRequest,
    certificate: IncentiveCompatibilityCertificate,
    component_evaluations: tuple[_MechanismFamilyEvaluation, ...],
) -> IncentiveCompatibilityCertificate:
    inputs = _request_inputs(request)
    proof_artifacts: list[ArtifactRef] = []
    family_spec_refs: dict[str, dict[str, Any]] = {}
    mechanism_certificate_refs: dict[str, dict[str, Any]] = {}
    welfare_bound_refs: dict[str, dict[str, Any]] = {}

    for component in component_evaluations:
        if component.family_spec is None or component.mechanism_certificate is None:
            continue
        mechanism_id = component.mechanism_certificate.mechanism_id
        family_spec_ref = persist_mechanism_family_spec(
            store,
            component.family_spec,
            inputs=inputs,
        )
        mechanism_certificate_ref = persist_mechanism_ic_certificate(
            store,
            component.mechanism_certificate,
            inputs=inputs,
        )
        family_spec_refs[mechanism_id] = family_spec_ref.model_dump(mode="json")
        mechanism_certificate_refs[mechanism_id] = mechanism_certificate_ref.model_dump(mode="json")
        proof_artifacts.extend(
            [
                _artifact_ref_from_ir_ref(family_spec_ref),
                _artifact_ref_from_ir_ref(mechanism_certificate_ref),
            ]
        )
        if component.welfare_bound is not None:
            welfare_bound_ref = persist_mechanism_welfare_loss_bound(
                store,
                component.welfare_bound,
                inputs=inputs,
            )
            welfare_bound_refs[mechanism_id] = welfare_bound_ref.model_dump(mode="json")
            proof_artifacts.append(_artifact_ref_from_ir_ref(welfare_bound_ref))

    witness = dict(certificate.witness)
    witness["mechanism_family_spec_refs"] = family_spec_refs
    witness["mechanism_ic_certificate_refs"] = mechanism_certificate_refs
    witness["mechanism_welfare_loss_bound_refs"] = welfare_bound_refs
    return certificate.model_copy(
        update={
            "witness": witness,
            "proof_artifacts": [*certificate.proof_artifacts, *proof_artifacts],
        }
    )


def _route_backend(
    semantics: MechanismSemanticsSpec,
    request: ICVerificationRequest,
) -> str:
    if request.backend_hint != "auto":
        return request.backend_hint
    if semantics.fragment is MechanismSemanticFragment.ENVELOPE_1D:
        return "envelope_1d"
    if semantics.fragment is MechanismSemanticFragment.CYCMON_GRID:
        return "cycmon_lp"
    return "finite_exact"


def evaluate_incentive_compatibility(
    policy: PolicySpec,
    request: ICVerificationRequest,
    *,
    input_digest: str | None = None,
    semantics: MechanismSemanticsSpec | None = None,
) -> tuple[
    ICVerificationReport,
    IncentiveCompatibilityCertificate | ICNegativeCertificate | None,
]:
    if policy.mechanism_design is None:
        raise ValueError("policy_spec.mechanism_design is required for IC verification")
    design = policy.mechanism_design
    effective_digest = input_digest or str(request.input_ref.artifact_id)
    family_evaluation = _try_evaluate_mechanism_family(
        policy,
        request,
        input_digest=effective_digest,
    )
    if family_evaluation is not None:
        return family_evaluation.report, family_evaluation.certificate

    effective_semantics = semantics or _resolve_semantics(
        store=None,
        request=request,
        design=design,
    )
    backend = _route_backend(effective_semantics, request)

    if backend == "finite_exact":
        mechanism = _normalize_finite_mechanism(design, effective_semantics, request.property)
        witness, checks = _find_finite_negative_witness(mechanism)
        if witness is not None:
            report = ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="finite_exact",
                verdict="negative",
                input_digest=effective_digest,
                players_checked=mechanism.players_checked,
                deviations_checked=checks,
                notes=("exact finite replay found a constructive negative witness",),
            )
            certificate = ICNegativeCertificate(
                property=request.property,
                backend="finite_exact",
                input_digest=effective_digest,
                arithmetic=request.exact_number_format,
                witness=witness,
            )
            return report, certificate
        if request.mode == "counterexample_search":
            report = ICVerificationReport(
                property=request.property,
                mode=request.mode,
                backend="finite_exact",
                verdict="inconclusive",
                input_digest=effective_digest,
                players_checked=mechanism.players_checked,
                deviations_checked=checks,
                notes=("counterexample_search found no negative witness in finite_exact",),
            )
            return report, None
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend="finite_exact",
            verdict="positive",
            input_digest=effective_digest,
            players_checked=mechanism.players_checked,
            deviations_checked=checks,
            notes=("exact finite replay passed",),
        )
        certificate = IncentiveCompatibilityCertificate(
            property=request.property,
            backend="finite_exact",
            input_digest=effective_digest,
            arithmetic=request.exact_number_format,
            witness=_finite_positive_witness(mechanism, checks),
        )
        return report, certificate

    if backend == "envelope_1d":
        mechanism = _normalize_envelope_mechanism(design, effective_semantics, request.property)
        return _evaluate_envelope_1d(mechanism, request, input_digest=effective_digest)

    if backend == "cycmon_lp":
        mechanism = _normalize_cycmon_mechanism(design, effective_semantics, request.property)
        return _evaluate_cycmon_grid(mechanism, request, input_digest=effective_digest)

    report = ICVerificationReport(
        property=request.property,
        mode=request.mode,
        backend=backend,
        verdict="unsupported_fragment",
        input_digest=effective_digest,
        notes=(f"backend '{backend}' is not implemented in this workspace",),
    )
    return report, None


def persist_ic_report(
    store: ArtifactStore,
    report: ICVerificationReport,
    *,
    inputs: list[Any] | None = None,
) -> ICVerificationReportRef:
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="scientist.ic_report",
        schema_name=_REPORT_SCHEMA_NAME,
        schema_version=report.schema_version,
        inputs=inputs,
    )
    return ICVerificationReportRef.model_validate(ref)


def load_ic_report(store: ArtifactStore, ref: ICVerificationReportRef) -> ICVerificationReport:
    payload = get_json_artifact(store, ref.artifact_id)
    return ICVerificationReport.model_validate(payload)


def persist_ic_certificate(
    store: ArtifactStore,
    certificate: IncentiveCompatibilityCertificate,
    *,
    inputs: list[Any] | None = None,
) -> ICVerificationCertificateRef:
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="scientist.ic_certificate",
        schema_name=_CERTIFICATE_SCHEMA_NAME,
        schema_version=certificate.schema_version,
        inputs=inputs,
    )
    return ICVerificationCertificateRef.model_validate(ref)


def load_ic_certificate(
    store: ArtifactStore,
    ref: ICVerificationCertificateRef,
) -> IncentiveCompatibilityCertificate:
    payload = get_json_artifact(store, ref.artifact_id)
    return IncentiveCompatibilityCertificate.model_validate(payload)


def persist_ic_negative_certificate(
    store: ArtifactStore,
    certificate: ICNegativeCertificate,
    *,
    inputs: list[Any] | None = None,
) -> ICNegativeCertificateRef:
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="scientist.ic_negative_certificate",
        schema_name=_NEGATIVE_SCHEMA_NAME,
        schema_version=certificate.schema_version,
        inputs=inputs,
    )
    return ICNegativeCertificateRef.model_validate(ref)


def load_ic_negative_certificate(
    store: ArtifactStore,
    ref: ICNegativeCertificateRef,
) -> ICNegativeCertificate:
    payload = get_json_artifact(store, ref.artifact_id)
    return ICNegativeCertificate.model_validate(payload)


def _request_inputs(request: ICVerificationRequest) -> list[InputRef]:
    inputs = [InputRef(artifact_id=request.input_ref.artifact_id, role="input")]
    if request.semantics_ref is not None:
        inputs.append(InputRef(artifact_id=request.semantics_ref.artifact_id, role="semantics"))
    return inputs


def verify_incentive_compatibility(
    store: ArtifactStore,
    request: ICVerificationRequest,
) -> ICVerificationResult:
    family_evaluation: _MechanismFamilyEvaluation | None = None
    try:
        policy, input_digest = _resolve_policy_input(store, request)
        family_evaluation = _try_evaluate_mechanism_family(
            policy,
            request,
            input_digest=input_digest,
        )
        if family_evaluation is not None:
            report = family_evaluation.report
            certificate = _attach_mechanism_family_sidecars(
                store,
                request,
                family_evaluation,
            )
        else:
            semantics = _resolve_semantics(
                store=store,
                request=request,
                design=policy.mechanism_design,
            )
            report, certificate = evaluate_incentive_compatibility(
                policy,
                request,
                input_digest=input_digest,
                semantics=semantics,
            )
    except (KeyError, OSError, RuntimeError, TypeError, ValidationError, ValueError) as exc:
        digest = str(request.input_ref.artifact_id)
        report = ICVerificationReport(
            property=request.property,
            mode=request.mode,
            backend=request.backend_hint if request.backend_hint != "auto" else "finite_exact",
            verdict="semantic_validation_failure",
            input_digest=digest,
            notes=(str(exc),),
        )
        report_ref = persist_ic_report(store, report, inputs=_request_inputs(request))
        return ICVerificationResult(
            ok=False,
            verdict=report.verdict,
            report_ref=report_ref,
            notes=[str(exc)],
        )

    inputs = _request_inputs(request)
    report_ref = persist_ic_report(store, report, inputs=inputs)
    if certificate is None:
        return ICVerificationResult(
            ok=False,
            verdict=report.verdict,
            report_ref=report_ref,
            notes=list(report.notes),
        )
    if isinstance(certificate, IncentiveCompatibilityCertificate):
        certificate_ref = persist_ic_certificate(store, certificate, inputs=inputs)
        return ICVerificationResult(
            ok=True,
            verdict=report.verdict,
            certificate_ref=certificate_ref,
            report_ref=report_ref,
            notes=list(report.notes),
        )
    certificate_ref = persist_ic_negative_certificate(store, certificate, inputs=inputs)
    return ICVerificationResult(
        ok=False,
        verdict=report.verdict,
        certificate_ref=certificate_ref,
        report_ref=report_ref,
        notes=list(report.notes),
    )


__all__ = [
    "evaluate_incentive_compatibility",
    "load_ic_certificate",
    "load_ic_negative_certificate",
    "load_ic_report",
    "persist_ic_certificate",
    "persist_ic_negative_certificate",
    "persist_ic_report",
    "verify_incentive_compatibility",
]
