"""Cross-method consistency diagnostics for Foundry method outputs."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from itertools import combinations
from statistics import NormalDist
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

import numpy as np

MethodFamily = str

TargetKind = Literal[
    "parameter",
    "causal_effect",
    "predictive_mean",
    "predictive_observable",
    "policy_value",
    "counterfactual",
    "classification_probability",
]
EstimandScale = Literal["identity", "log", "logit", "probability", "standardized", "custom"]
TargetRole = Literal["estimate", "prediction", "causal", "decision", "ranking", "screening"]
ConsensusStatus = Literal[
    "not_run",
    "not_enough_methods",
    "not_comparable",
    "pass",
    "warn",
    "refuse",
    "hard_refuse",
]
MultiplicityAdjustment = Literal["holm", "bonferroni", "sidak", "none"]
DisagreementMetric = Literal[
    "mahalanobis_hausman",
    "z_score",
    "energy_distance",
    "mmd",
    "wasserstein",
    "js_divergence",
    "sym_kl",
    "decision_disagreement",
]
CovarianceSource = Literal[
    "joint_draws",
    "influence_function",
    "paired_bootstrap",
    "common_random_numbers",
    "conservative_bound",
    "independence_approximation",
    "unavailable",
]
Severity = Literal["none", "low", "warning", "refusal", "hard_refusal"]
MisspecificationStatus = Literal[
    "none",
    "likely_misspecified_family",
    "likely_misspecified_method",
    "estimand_mismatch",
    "uncertainty_underestimated",
    "ambiguous_two_clusters",
    "global_incompatibility",
    "insufficient_evidence",
]
Confidence = Literal["low", "medium", "high"]

_EPS = 1.0e-12
_DEFAULT_DISTRIBUTION_PERMUTATIONS = 199
_MAX_DISTRIBUTION_SAMPLES = 240


class NotComparableYet(ValueError):
    """Raised when a native result cannot yet expose a consensus target."""


@dataclass(frozen=True, slots=True)
class EstimandSpec:
    """Canonical identity of the estimand being compared across methods."""

    query_id: str
    estimand_id: str
    outcome: str
    treatment_or_exposure: str | None = None
    covariates_or_conditioning: tuple[str, ...] = ()
    adjustment_set: tuple[str, ...] | None = None
    population: str = "unspecified"
    sample_filter: str | None = None
    time_horizon: str | None = None
    prediction_origin: str | None = None
    unit: str = "unitless"
    scale: EstimandScale = "identity"
    transform: str | None = None
    target_role: TargetRole = "estimate"
    loss_or_utility_id: str | None = None


@dataclass(frozen=True, slots=True)
class IntervalSummary:
    """Interval summary on the canonical estimand scale."""

    level: float
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    interval_type: Literal["confidence", "credible", "prediction"] = "confidence"


@dataclass(frozen=True, slots=True)
class UncertaintyContract:
    """Declared meaning and reliability of uncertainty attached to a target."""

    uncertainty_type: Literal[
        "parameter",
        "predictive_mean",
        "future_observable",
        "policy_value",
        "unknown",
    ] = "unknown"
    covariance_type: str | None = None
    confidence_level: float | None = None
    reliability_score: float = 1.0
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodDiagnostics:
    """Small normalized diagnostic surface consumed by the consensus classifier."""

    failure_score: float = 0.0
    computational_failure_score: float = 0.0
    validation_disadvantage_score: float = 0.0
    issues: tuple[str, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Optional validation and calibration evidence for prediction-like targets."""

    calibration_failure_score: float = 0.0
    scoring_disadvantage_score: float = 0.0
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConsensusTarget:
    """Canonical method output used for cross-method comparisons."""

    result_id: str
    method_family: MethodFamily
    method_name: str
    estimand: EstimandSpec
    target_kind: TargetKind
    point: np.ndarray
    covariance: np.ndarray | None = None
    samples: np.ndarray | None = None
    intervals: tuple[IntervalSummary, ...] | None = None
    quantiles: Mapping[float, np.ndarray] | None = None
    uncertainty: UncertaintyContract = field(default_factory=UncertaintyContract)
    diagnostics: MethodDiagnostics = field(default_factory=MethodDiagnostics)
    validation: ValidationSummary | None = None
    influence_values: np.ndarray | None = None
    bootstrap_replicates: np.ndarray | None = None
    native_result_ref: str | None = None

    def __post_init__(self) -> None:
        point = _as_1d_vector(self.point, field_name="ConsensusTarget.point")
        object.__setattr__(self, "point", point)
        d = int(point.shape[0])
        if self.covariance is not None:
            cov = _as_square_matrix(self.covariance, d, field_name="ConsensusTarget.covariance")
            object.__setattr__(self, "covariance", cov)
        if self.samples is not None:
            object.__setattr__(self, "samples", _as_draw_matrix(self.samples, d))
        if self.influence_values is not None:
            object.__setattr__(
                self,
                "influence_values",
                _as_draw_matrix(self.influence_values, d),
            )
        if self.bootstrap_replicates is not None:
            object.__setattr__(
                self,
                "bootstrap_replicates",
                _as_draw_matrix(self.bootstrap_replicates, d),
            )


@runtime_checkable
class SupportsConsensusTarget(Protocol):
    """Protocol implemented by native method result contracts."""

    contract_id: ClassVar[str]

    def to_consensus_target(self, query: Any) -> ConsensusTarget:
        """Return a canonical target for a query."""
        ...


@dataclass(frozen=True, slots=True)
class PairwiseDisagreement:
    """One pairwise compatibility check between two canonical outputs."""

    method_i: str
    method_j: str
    comparable: bool
    noncomparable_reason: str | None
    estimand: EstimandSpec | None
    projection: str | None
    metric: DisagreementMetric
    statistic: float | None
    degrees_of_freedom: int | None
    raw_p_value: float | None
    adjusted_q_value: float | None
    cmd_score: float | None
    threshold: float
    point_i: tuple[float, ...] | None
    point_j: tuple[float, ...] | None
    covariance_source: CovarianceSource
    decision_relevant: bool
    decision_difference: str | None
    severity: Severity


@dataclass(frozen=True, slots=True)
class MisspecificationClassification:
    """Classifier output explaining which method family is suspect, if knowable."""

    status: MisspecificationStatus
    likely_family: MethodFamily | None
    likely_method_ids: tuple[str, ...] = ()
    confidence: Confidence = "low"
    suspicion_scores: Mapping[str, float] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    counterevidence: tuple[str, ...] = ()
    recommended_remediation: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CrossMethodConsensus:
    """Advisor-facing cross-method consensus report."""

    status: ConsensusStatus
    recommendation_allowed: bool
    query_id: str
    estimand_id: str | None
    alpha_warn: float
    alpha_refuse: float
    alpha_hard_refuse: float
    multiplicity_adjustment: MultiplicityAdjustment
    compared_method_ids: tuple[str, ...]
    noncomparable_method_ids: tuple[str, ...]
    consensus_set: tuple[str, ...]
    excluded_methods: tuple[str, ...]
    global_cmd_score: float
    refusal_threshold: float
    worst_pair: PairwiseDisagreement | None
    pairwise: tuple[PairwiseDisagreement, ...]
    likely_misspecification: MisspecificationClassification
    user_message: str
    developer_message: str
    remediation: tuple[str, ...]


def run_cross_method_consensus(
    query: Any,
    results: Sequence[SupportsConsensusTarget | ConsensusTarget | Mapping[str, Any]],
    *,
    alpha_warn: float = 0.05,
    alpha_refuse: float = 0.01,
    alpha_hard_refuse: float = 0.001,
    multiplicity_adjustment: MultiplicityAdjustment = "holm",
    distribution_permutations: int = _DEFAULT_DISTRIBUTION_PERMUTATIONS,
) -> CrossMethodConsensus:
    """Compare canonical method outputs and decide whether recommendation is allowed."""

    thresholds = _validate_thresholds(alpha_warn, alpha_refuse, alpha_hard_refuse)
    alpha_warn, alpha_refuse, alpha_hard_refuse = thresholds
    query_id = _query_value(query, "query_id", "method_advisor_query")
    targets: list[ConsensusTarget] = []
    failures: dict[str, str] = {}
    for index, result in enumerate(results):
        fallback_id = _result_identifier(result, index)
        try:
            targets.append(_coerce_consensus_target(result, query))
        except (NotComparableYet, TypeError, ValueError) as exc:
            failures[fallback_id] = str(exc)
    targets = _align_transformable_target_scales(targets, query)

    if len(targets) < 2:
        return CrossMethodConsensus(
            status="not_enough_methods",
            recommendation_allowed=True,
            query_id=query_id,
            estimand_id=targets[0].estimand.estimand_id if targets else None,
            alpha_warn=alpha_warn,
            alpha_refuse=alpha_refuse,
            alpha_hard_refuse=alpha_hard_refuse,
            multiplicity_adjustment=multiplicity_adjustment,
            compared_method_ids=tuple(target.result_id for target in targets),
            noncomparable_method_ids=tuple(sorted(failures)),
            consensus_set=tuple(target.result_id for target in targets),
            excluded_methods=tuple(sorted(failures)),
            global_cmd_score=0.0,
            refusal_threshold=1.0,
            worst_pair=None,
            pairwise=(),
            likely_misspecification=MisspecificationClassification(
                status="insufficient_evidence",
                likely_family=None,
                evidence=("Fewer than two consensus targets were available.",),
                recommended_remediation=("Run at least two comparable methods for this query.",),
            ),
            user_message=(
                "Only one comparable method was available; "
                "cross-method agreement was not checked."
            ),
            developer_message="not_enough_methods",
            remediation=("Run an independent alternative method for the same estimand.",),
        )

    groups = _group_by_comparable_identity(targets)
    primary_group = max(groups.values(), key=lambda group: (len(group), group[0].result_id))
    primary_ids = {target.result_id for target in primary_group}
    nonprimary_ids = tuple(target.result_id for target in targets if target.result_id not in primary_ids)

    pairwise_checks: list[PairwiseDisagreement] = []
    for target_i, target_j in combinations(primary_group, 2):
        pairwise_checks.extend(
            compute_pairwise_checks(
                target_i,
                target_j,
                query=query,
                alpha_warn=alpha_warn,
                alpha_refuse=alpha_refuse,
                alpha_hard_refuse=alpha_hard_refuse,
                distribution_permutations=distribution_permutations,
            )
        )
    for target_i, target_j in combinations(targets, 2):
        if target_i.result_id in primary_ids and target_j.result_id in primary_ids:
            continue
        if _comparable_identity(target_i) != _comparable_identity(target_j):
            pairwise_checks.append(_noncomparable_pair(target_i, target_j))

    adjusted = adjust_pairwise_p_values(
        pairwise_checks,
        alpha_warn=alpha_warn,
        alpha_refuse=alpha_refuse,
        alpha_hard_refuse=alpha_hard_refuse,
        method=multiplicity_adjustment,
    )
    comparable_checks = tuple(check for check in adjusted if check.comparable)
    if not comparable_checks:
        all_noncomparable = tuple(sorted({*(target.result_id for target in targets), *failures.keys()}))
        return CrossMethodConsensus(
            status="not_comparable",
            recommendation_allowed=True,
            query_id=query_id,
            estimand_id=None,
            alpha_warn=alpha_warn,
            alpha_refuse=alpha_refuse,
            alpha_hard_refuse=alpha_hard_refuse,
            multiplicity_adjustment=multiplicity_adjustment,
            compared_method_ids=(),
            noncomparable_method_ids=all_noncomparable,
            consensus_set=(),
            excluded_methods=all_noncomparable,
            global_cmd_score=0.0,
            refusal_threshold=1.0,
            worst_pair=None,
            pairwise=tuple(adjusted),
            likely_misspecification=MisspecificationClassification(
                status="estimand_mismatch",
                likely_family=None,
                evidence=("No pair of methods exposed the same canonical estimand.",),
                recommended_remediation=("Align target variable, horizon, scale, and loss before comparing.",),
            ),
            user_message="Methods were not comparable; no disagreement test was run.",
            developer_message="not_comparable: no shared EstimandSpec group with at least two methods",
            remediation=("Canonicalize methods to the same estimand, scale, horizon, and decision target.",),
        )

    consensus_set = largest_compatible_component(
        primary_group,
        comparable_checks,
        alpha_warn=alpha_warn,
    )
    classifier = classify_misspecification(
        primary_group,
        comparable_checks,
        consensus_set,
        alpha_warn=alpha_warn,
        alpha_refuse=alpha_refuse,
    )
    worst = max(comparable_checks, key=lambda check: check.cmd_score or 0.0)
    global_cmd_score = float(max((check.cmd_score or 0.0) for check in comparable_checks))
    status: ConsensusStatus
    allowed: bool
    message: str
    if any(
        (check.adjusted_q_value is not None and check.adjusted_q_value <= alpha_hard_refuse)
        and check.decision_relevant
        for check in comparable_checks
    ):
        status = "hard_refuse"
        allowed = False
        message = "Methods disagree, no recommendation."
    elif any(
        (check.adjusted_q_value is not None and check.adjusted_q_value <= alpha_refuse)
        and check.decision_relevant
        for check in comparable_checks
    ):
        status = "refuse"
        allowed = False
        message = "Methods disagree, no recommendation."
    elif any(check.raw_p_value is None for check in comparable_checks):
        status = "warn"
        allowed = True
        message = "Comparable methods lacked sufficient uncertainty for a reliable disagreement test."
    elif any(
        check.adjusted_q_value is not None and check.adjusted_q_value <= alpha_warn
        for check in comparable_checks
    ):
        status = "warn"
        allowed = True
        message = "Methods show material disagreement; recommendation should be treated cautiously."
    else:
        status = "pass"
        allowed = True
        message = "Comparable methods are mutually consistent within stated uncertainty."

    excluded = tuple(target.result_id for target in primary_group if target.result_id not in consensus_set)
    noncomparable_ids = tuple(sorted({*nonprimary_ids, *failures.keys()}))
    return CrossMethodConsensus(
        status=status,
        recommendation_allowed=allowed,
        query_id=query_id,
        estimand_id=primary_group[0].estimand.estimand_id,
        alpha_warn=alpha_warn,
        alpha_refuse=alpha_refuse,
        alpha_hard_refuse=alpha_hard_refuse,
        multiplicity_adjustment=multiplicity_adjustment,
        compared_method_ids=tuple(target.result_id for target in primary_group),
        noncomparable_method_ids=noncomparable_ids,
        consensus_set=consensus_set,
        excluded_methods=excluded,
        global_cmd_score=global_cmd_score,
        refusal_threshold=1.0,
        worst_pair=worst,
        pairwise=tuple(adjusted),
        likely_misspecification=classifier,
        user_message=message,
        developer_message=_developer_message(status, worst, classifier),
        remediation=_consensus_remediation(status, classifier, noncomparable_ids),
    )


def compute_hausman_like_check(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    *,
    query: Any = None,
    alpha_warn: float = 0.05,
    alpha_refuse: float = 0.01,
    alpha_hard_refuse: float = 0.001,
) -> PairwiseDisagreement:
    """Compute the generalized Hausman-style discrepancy for two targets."""

    if _comparable_identity(target_i) != _comparable_identity(target_j):
        return _noncomparable_pair(target_i, target_j)

    delta = target_i.point - target_j.point
    variance, covariance_source = _variance_of_difference(target_i, target_j)
    decision_relevant, decision_difference = _decision_relevance(target_i, target_j, query)
    metric: DisagreementMetric = "z_score" if delta.shape[0] == 1 else "mahalanobis_hausman"
    if variance is None:
        return PairwiseDisagreement(
            method_i=target_i.result_id,
            method_j=target_j.result_id,
            comparable=True,
            noncomparable_reason=None,
            estimand=target_i.estimand,
            projection=None,
            metric=metric,
            statistic=None,
            degrees_of_freedom=None,
            raw_p_value=None,
            adjusted_q_value=None,
            cmd_score=None,
            threshold=1.0,
            point_i=tuple(float(value) for value in target_i.point),
            point_j=tuple(float(value) for value in target_j.point),
            covariance_source=covariance_source,
            decision_relevant=decision_relevant,
            decision_difference=decision_difference,
            severity="low",
        )

    rank = int(np.linalg.matrix_rank(variance))
    if rank <= 0:
        statistic = 0.0 if float(np.linalg.norm(delta)) <= _EPS else math.inf
        p_value = 1.0 if math.isfinite(statistic) and statistic <= _EPS else 0.0
    else:
        statistic = float(delta.T @ np.linalg.pinv(variance) @ delta)
        p_value = _chi2_survival(statistic, rank)
    return PairwiseDisagreement(
        method_i=target_i.result_id,
        method_j=target_j.result_id,
        comparable=True,
        noncomparable_reason=None,
        estimand=target_i.estimand,
        projection=None,
        metric=metric,
        statistic=statistic,
        degrees_of_freedom=rank,
        raw_p_value=_clip_probability(p_value),
        adjusted_q_value=None,
        cmd_score=None,
        threshold=1.0,
        point_i=tuple(float(value) for value in target_i.point),
        point_j=tuple(float(value) for value in target_j.point),
        covariance_source=covariance_source,
        decision_relevant=decision_relevant,
        decision_difference=decision_difference,
        severity=_severity(None, alpha_warn, alpha_refuse, alpha_hard_refuse, decision_relevant),
    )


def compute_pairwise_checks(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    *,
    query: Any = None,
    alpha_warn: float = 0.05,
    alpha_refuse: float = 0.01,
    alpha_hard_refuse: float = 0.001,
    distribution_permutations: int = _DEFAULT_DISTRIBUTION_PERMUTATIONS,
) -> tuple[PairwiseDisagreement, ...]:
    """Compute moment, distributional, and decision-projection checks for a pair."""

    moment = compute_hausman_like_check(
        target_i,
        target_j,
        query=query,
        alpha_warn=alpha_warn,
        alpha_refuse=alpha_refuse,
        alpha_hard_refuse=alpha_hard_refuse,
    )
    if not moment.comparable:
        return (moment,)
    checks: list[PairwiseDisagreement] = [moment]
    distribution = compute_distributional_check(
        target_i,
        target_j,
        query=query,
        permutations=distribution_permutations,
    )
    if distribution is not None:
        checks.append(distribution)
    checks.extend(compute_projection_checks(target_i, target_j, query=query))
    return tuple(checks)


def compute_distributional_check(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    *,
    query: Any = None,
    permutations: int = _DEFAULT_DISTRIBUTION_PERMUTATIONS,
) -> PairwiseDisagreement | None:
    """Compare full target distributions when both methods expose samples."""

    if target_i.samples is None or target_j.samples is None:
        return None
    if _comparable_identity(target_i) != _comparable_identity(target_j):
        return None
    x = _downsample_draws(target_i.samples)
    y = _downsample_draws(target_j.samples)
    if x.shape[0] < 2 or y.shape[0] < 2 or x.shape[1] != y.shape[1]:
        return None
    metric = _distribution_metric_for(query, dimension=x.shape[1])
    statistic_fn = _distribution_statistic_fn(metric)
    statistic = float(statistic_fn(x, y))
    p_value = _permutation_p_value(
        x,
        y,
        statistic_fn=statistic_fn,
        observed=statistic,
        permutations=permutations,
    )
    decision_relevant, decision_difference = _distribution_decision_relevance(
        target_i,
        target_j,
        query,
    )
    return PairwiseDisagreement(
        method_i=target_i.result_id,
        method_j=target_j.result_id,
        comparable=True,
        noncomparable_reason=None,
        estimand=target_i.estimand,
        projection="distribution",
        metric=metric,
        statistic=statistic,
        degrees_of_freedom=None,
        raw_p_value=_clip_probability(p_value),
        adjusted_q_value=None,
        cmd_score=None,
        threshold=1.0,
        point_i=tuple(float(value) for value in target_i.point),
        point_j=tuple(float(value) for value in target_j.point),
        covariance_source="joint_draws",
        decision_relevant=decision_relevant,
        decision_difference=decision_difference,
        severity="low",
    )


def compute_projection_checks(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    *,
    query: Any = None,
) -> tuple[PairwiseDisagreement, ...]:
    """Run interpretable decision-projection checks for signs, thresholds, and rankings."""

    if _comparable_identity(target_i) != _comparable_identity(target_j):
        return ()
    variance, covariance_source = _variance_of_difference(target_i, target_j)
    checks: list[PairwiseDisagreement] = []
    sign_difference = _sign_difference(target_i.point, target_j.point)
    if sign_difference:
        checks.append(
            _projection_check(
                target_i,
                target_j,
                projection="effect_sign",
                decision_difference="effect signs differ",
                variance=variance,
                covariance_source=covariance_source,
            )
        )
    threshold = _decision_threshold(query)
    if threshold is not None and _threshold_crossings_differ(target_i, target_j, query):
        checks.append(
            _projection_check(
                target_i,
                target_j,
                projection="threshold_crossing",
                decision_difference=f"decision threshold {threshold:.6g} crossings differ",
                variance=variance,
                covariance_source=covariance_source,
            )
        )
    if target_i.point.shape[0] > 1 and int(np.argmax(target_i.point)) != int(np.argmax(target_j.point)):
        checks.append(
            _projection_check(
                target_i,
                target_j,
                projection="ranking",
                decision_difference="top-ranked alternative differs",
                variance=variance,
                covariance_source=covariance_source,
            )
        )
    return tuple(checks)


def _projection_check(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    *,
    projection: str,
    decision_difference: str,
    variance: np.ndarray | None,
    covariance_source: CovarianceSource,
) -> PairwiseDisagreement:
    delta = target_i.point - target_j.point
    metric: DisagreementMetric = "z_score" if delta.shape[0] == 1 else "decision_disagreement"
    statistic: float | None = None
    degrees_of_freedom: int | None = None
    p_value: float | None = None
    if variance is not None:
        degrees_of_freedom = int(np.linalg.matrix_rank(variance))
        if degrees_of_freedom <= 0:
            statistic = 0.0 if float(np.linalg.norm(delta)) <= _EPS else math.inf
            p_value = 1.0 if math.isfinite(statistic) and statistic <= _EPS else 0.0
        else:
            statistic = float(delta.T @ np.linalg.pinv(variance) @ delta)
            p_value = _chi2_survival(statistic, degrees_of_freedom)
    return PairwiseDisagreement(
        method_i=target_i.result_id,
        method_j=target_j.result_id,
        comparable=True,
        noncomparable_reason=None,
        estimand=target_i.estimand,
        projection=projection,
        metric=metric,
        statistic=statistic,
        degrees_of_freedom=degrees_of_freedom,
        raw_p_value=None if p_value is None else _clip_probability(p_value),
        adjusted_q_value=None,
        cmd_score=None,
        threshold=1.0,
        point_i=tuple(float(value) for value in target_i.point),
        point_j=tuple(float(value) for value in target_j.point),
        covariance_source=covariance_source,
        decision_relevant=True,
        decision_difference=decision_difference,
        severity="low",
    )


def _distribution_metric_for(query: Any, *, dimension: int) -> DisagreementMetric:
    requested = _query_value(query, "distribution_metric", None)
    if requested is not None:
        metric = str(requested)
        if metric in {
            "energy_distance",
            "mmd",
            "wasserstein",
            "js_divergence",
            "sym_kl",
        }:
            return metric  # type: ignore[return-value]
    if dimension == 1:
        return "energy_distance"
    if dimension <= 4:
        return "energy_distance"
    return "mmd"


def _distribution_statistic_fn(
    metric: DisagreementMetric,
) -> Callable[[np.ndarray, np.ndarray], float]:
    if metric == "wasserstein":
        return _wasserstein_statistic
    if metric == "mmd":
        return _mmd_statistic
    if metric == "js_divergence":
        return _js_divergence_statistic
    if metric == "sym_kl":
        return _sym_kl_statistic
    return _energy_distance_statistic


def _downsample_draws(draws: np.ndarray) -> np.ndarray:
    matrix = np.asarray(draws, dtype=float)
    if matrix.shape[0] <= _MAX_DISTRIBUTION_SAMPLES:
        return matrix
    indices = np.linspace(0, matrix.shape[0] - 1, _MAX_DISTRIBUTION_SAMPLES, dtype=int)
    return matrix[indices]


def _permutation_p_value(
    x: np.ndarray,
    y: np.ndarray,
    *,
    statistic_fn: Callable[[np.ndarray, np.ndarray], float],
    observed: float,
    permutations: int,
) -> float:
    permutations = max(0, int(permutations))
    if permutations == 0:
        return 1.0
    pooled = np.vstack([x, y])
    n_x = x.shape[0]
    rng = np.random.default_rng(17_091)
    exceedances = 0
    for _ in range(permutations):
        order = rng.permutation(pooled.shape[0])
        perm_x = pooled[order[:n_x]]
        perm_y = pooled[order[n_x:]]
        if statistic_fn(perm_x, perm_y) >= observed - _EPS:
            exceedances += 1
    return (1.0 + float(exceedances)) / (1.0 + float(permutations))


def _mean_pairwise_norm(x: np.ndarray, y: np.ndarray) -> float:
    distances = np.linalg.norm(x[:, None, :] - y[None, :, :], axis=2)
    return float(np.mean(distances))


def _energy_distance_statistic(x: np.ndarray, y: np.ndarray) -> float:
    statistic = (
        2.0 * _mean_pairwise_norm(x, y)
        - _mean_pairwise_norm(x, x)
        - _mean_pairwise_norm(y, y)
    )
    return max(float(statistic), 0.0)


def _wasserstein_statistic(x: np.ndarray, y: np.ndarray) -> float:
    values = []
    for dim in range(x.shape[1]):
        x_sorted = np.sort(x[:, dim])
        y_sorted = np.sort(y[:, dim])
        grid = min(x_sorted.shape[0], y_sorted.shape[0])
        if grid <= 0:
            continue
        x_q = np.quantile(x_sorted, np.linspace(0.0, 1.0, grid))
        y_q = np.quantile(y_sorted, np.linspace(0.0, 1.0, grid))
        values.append(float(np.mean(np.abs(x_q - y_q))))
    return float(np.mean(values)) if values else 0.0


def _mmd_statistic(x: np.ndarray, y: np.ndarray) -> float:
    pooled = np.vstack([x, y])
    distances = np.sum((pooled[:, None, :] - pooled[None, :, :]) ** 2, axis=2)
    positive = distances[distances > _EPS]
    bandwidth_sq = float(np.median(positive)) if positive.size else 1.0
    bandwidth_sq = max(bandwidth_sq, _EPS)

    def kernel(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        sq = np.sum((a[:, None, :] - b[None, :, :]) ** 2, axis=2)
        return np.exp(-sq / (2.0 * bandwidth_sq))

    k_xx = kernel(x, x)
    k_yy = kernel(y, y)
    k_xy = kernel(x, y)
    return max(float(np.mean(k_xx) + np.mean(k_yy) - 2.0 * np.mean(k_xy)), 0.0)


def _histogram_probabilities(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values_x = x.reshape(-1)
    values_y = y.reshape(-1)
    lo = float(min(np.min(values_x), np.min(values_y)))
    hi = float(max(np.max(values_x), np.max(values_y)))
    if hi <= lo:
        return np.asarray([1.0]), np.asarray([1.0])
    bins = np.linspace(lo, hi, min(40, max(8, int(math.sqrt(values_x.size + values_y.size)))) + 1)
    p, _ = np.histogram(values_x, bins=bins)
    q, _ = np.histogram(values_y, bins=bins)
    p = p.astype(float) + _EPS
    q = q.astype(float) + _EPS
    return p / np.sum(p), q / np.sum(q)


def _js_divergence_statistic(x: np.ndarray, y: np.ndarray) -> float:
    p, q = _histogram_probabilities(x, y)
    m = 0.5 * (p + q)
    return float(0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m)))


def _sym_kl_statistic(x: np.ndarray, y: np.ndarray) -> float:
    p, q = _histogram_probabilities(x, y)
    return float(0.5 * np.sum(p * np.log(p / q)) + 0.5 * np.sum(q * np.log(q / p)))


def adjust_pairwise_p_values(
    checks: Sequence[PairwiseDisagreement],
    *,
    alpha_warn: float = 0.05,
    alpha_refuse: float = 0.01,
    alpha_hard_refuse: float = 0.001,
    method: MultiplicityAdjustment = "holm",
) -> tuple[PairwiseDisagreement, ...]:
    """Apply multiplicity correction and attach CMD/severity to pairwise checks."""

    indices = [
        index
        for index, check in enumerate(checks)
        if check.comparable and check.raw_p_value is not None
    ]
    p_values = [float(checks[index].raw_p_value) for index in indices]
    q_values = _adjust_p_values(p_values, method=method)
    q_by_index = dict(zip(indices, q_values, strict=True))
    adjusted: list[PairwiseDisagreement] = []
    for index, check in enumerate(checks):
        q_value = q_by_index.get(index)
        cmd = _cmd_score(q_value, alpha_refuse) if q_value is not None else None
        adjusted.append(
            replace(
                check,
                adjusted_q_value=q_value,
                cmd_score=cmd,
                severity=_severity(
                    q_value,
                    alpha_warn,
                    alpha_refuse,
                    alpha_hard_refuse,
                    check.decision_relevant,
                ),
            )
        )
    return tuple(adjusted)


def largest_compatible_component(
    targets: Sequence[ConsensusTarget],
    checks: Sequence[PairwiseDisagreement],
    *,
    alpha_warn: float = 0.05,
) -> tuple[str, ...]:
    """Return the largest component joined by green pairwise edges."""

    ids = tuple(target.result_id for target in targets)
    if not ids:
        return ()
    adjacency: dict[str, set[str]] = {result_id: set() for result_id in ids}
    for check in checks:
        if (
            check.comparable
            and check.adjusted_q_value is not None
            and check.adjusted_q_value > alpha_warn
        ):
            adjacency.setdefault(check.method_i, set()).add(check.method_j)
            adjacency.setdefault(check.method_j, set()).add(check.method_i)

    seen: set[str] = set()
    components: list[tuple[str, ...]] = []
    for result_id in ids:
        if result_id in seen:
            continue
        queue: deque[str] = deque([result_id])
        seen.add(result_id)
        members: list[str] = []
        while queue:
            current = queue.popleft()
            members.append(current)
            for neighbor in sorted(adjacency.get(current, ())):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(tuple(sorted(members)))
    components.sort(key=lambda item: (-len(item), item))
    return components[0]


def classify_misspecification(
    targets: Sequence[ConsensusTarget],
    checks: Sequence[PairwiseDisagreement],
    consensus_set: Sequence[str],
    *,
    alpha_warn: float = 0.05,
    alpha_refuse: float = 0.01,
) -> MisspecificationClassification:
    """Classify likely misspecification from the disagreement graph."""

    if len(targets) < 2:
        return MisspecificationClassification(status="insufficient_evidence", likely_family=None)
    target_by_id = {target.result_id: target for target in targets}
    comparable_checks = [check for check in checks if check.comparable and check.adjusted_q_value is not None]
    if not comparable_checks:
        return MisspecificationClassification(
            status="estimand_mismatch",
            likely_family=None,
            evidence=("No comparable pairwise checks were available.",),
            recommended_remediation=("Canonicalize methods to the same estimand.",),
        )

    red_checks = [check for check in comparable_checks if (check.adjusted_q_value or 1.0) <= alpha_refuse]
    if not red_checks:
        return MisspecificationClassification(
            status="none",
            likely_family=None,
            confidence="medium",
            evidence=("All comparable methods are mutually consistent after adjustment.",),
        )

    family_counts = defaultdict(int)
    for target in targets:
        family_counts[target.method_family] += 1
    family_weight = {family: 1.0 / count for family, count in family_counts.items()}
    method_scores: dict[str, float] = {}
    for target in targets:
        denom = 0.0
        red_weight = 0.0
        for other in targets:
            if other.result_id == target.result_id:
                continue
            weight = family_weight[other.method_family]
            denom += weight
            if _is_red_edge(target.result_id, other.result_id, red_checks):
                red_weight += weight
        method_scores[target.result_id] = 0.0 if denom <= 0.0 else red_weight / denom

    family_scores: dict[str, float] = {}
    for family, members in _targets_by_family(targets).items():
        outlier = float(np.mean([method_scores[target.result_id] for target in members]))
        diagnostic = float(np.mean([target.diagnostics.failure_score for target in members]))
        validation = float(
            np.mean(
                [
                    (target.validation.scoring_disadvantage_score if target.validation else 0.0)
                    for target in members
                ]
            )
        )
        computational = float(
            np.mean([target.diagnostics.computational_failure_score for target in members])
        )
        pattern = _family_pattern_score(family, members, targets, red_checks, consensus_set)
        family_scores[family] = _clip_unit(
            0.40 * outlier
            + 0.25 * diagnostic
            + 0.20 * pattern
            + 0.10 * validation
            + 0.05 * computational
        )

    sorted_families = sorted(family_scores.items(), key=lambda item: (-item[1], item[0]))
    top_family, top_score = sorted_families[0]
    second_score = sorted_families[1][1] if len(sorted_families) > 1 else 0.0
    isolated_methods = tuple(
        sorted(result_id for result_id, score in method_scores.items() if score >= 0.75)
    )
    independent_against_top = {
        target_by_id[other_id].method_family
        for check in red_checks
        for other_id, maybe_top_id in (
            (check.method_i, check.method_j),
            (check.method_j, check.method_i),
        )
        if maybe_top_id in target_by_id
        and target_by_id[maybe_top_id].method_family == top_family
        and other_id in target_by_id
        and target_by_id[other_id].method_family != top_family
    }

    if _uncertainty_underestimated(targets, red_checks):
        return MisspecificationClassification(
            status="uncertainty_underestimated",
            likely_family=top_family,
            likely_method_ids=isolated_methods,
            confidence="medium",
            suspicion_scores=family_scores,
            evidence=("Point estimates are close relative to at least one very narrow covariance.",),
            recommended_remediation=("Recompute uncertainty with robust, bootstrap, or paired covariance.",),
        )

    if top_score >= 0.60 and (top_score - second_score) >= 0.15 and len(independent_against_top) >= 2:
        return MisspecificationClassification(
            status="likely_misspecified_family",
            likely_family=top_family,
            likely_method_ids=tuple(
                sorted(target.result_id for target in targets if target.method_family == top_family)
            ),
            confidence="high" if top_score >= 0.80 else "medium",
            suspicion_scores=family_scores,
            evidence=(
                f"Family {top_family!r} has red edges against multiple independent families.",
            ),
            recommended_remediation=(
                "Inspect family-specific identifying assumptions and diagnostics.",
                "Rerun with paired bootstrap or influence-function covariance where possible.",
            ),
        )

    if len(isolated_methods) == 1:
        method_id = isolated_methods[0]
        return MisspecificationClassification(
            status="likely_misspecified_method",
            likely_family=target_by_id[method_id].method_family,
            likely_method_ids=(method_id,),
            confidence="medium",
            suspicion_scores=family_scores,
            evidence=(f"Method {method_id!r} is incompatible with most comparable alternatives.",),
            recommended_remediation=("Review the isolated method's diagnostics and rerun it.",),
        )

    green_components = _green_components(targets, comparable_checks, alpha_warn=alpha_warn)
    if len(green_components) >= 2 and len(green_components[0]) >= 2 and len(green_components[1]) >= 2:
        return MisspecificationClassification(
            status="ambiguous_two_clusters",
            likely_family=None,
            confidence="medium",
            suspicion_scores=family_scores,
            evidence=("Comparable methods form at least two internally coherent incompatible clusters.",),
            recommended_remediation=("Collect stronger identification or validation evidence before choosing.",),
        )

    red_density = len(red_checks) / max(len(comparable_checks), 1)
    if red_density >= 0.75:
        return MisspecificationClassification(
            status="global_incompatibility",
            likely_family=None,
            confidence="medium",
            suspicion_scores=family_scores,
            evidence=("Most comparable method pairs disagree beyond the refusal threshold.",),
            recommended_remediation=("Treat the query as unresolved and audit estimand/data quality.",),
        )

    return MisspecificationClassification(
        status="insufficient_evidence",
        likely_family=top_family if top_score >= 0.50 else None,
        confidence="low",
        suspicion_scores=family_scores,
        evidence=("Methods disagree, but no unique culprit is statistically isolated.",),
        counterevidence=("Fewer than two independent families agree against one suspect family.",),
        recommended_remediation=("Run additional independent methods or stronger validation diagnostics.",),
    )


def consensus_target_from_mapping(payload: Mapping[str, Any], query: Any = None) -> ConsensusTarget:
    """Build a ``ConsensusTarget`` from a JSON-like payload."""

    estimand_payload = _mapping_value(payload, "estimand", default=None)
    if isinstance(estimand_payload, EstimandSpec):
        estimand = estimand_payload
    elif isinstance(estimand_payload, Mapping):
        estimand = estimand_from_mapping(estimand_payload, query=query)
    else:
        estimand = estimand_from_query(query, metadata=payload)
    return ConsensusTarget(
        result_id=str(_mapping_value(payload, "result_id", default=_mapping_value(payload, "method_name", default="result"))),
        method_family=str(_mapping_value(payload, "method_family", default=_mapping_value(payload, "family", default="unknown"))),
        method_name=str(_mapping_value(payload, "method_name", default="unknown")),
        estimand=estimand,
        target_kind=_target_kind(_mapping_value(payload, "target_kind", default="parameter")),
        point=np.asarray(_mapping_value(payload, "point", default=[]), dtype=float),
        covariance=_optional_array(_mapping_value(payload, "covariance", default=None)),
        samples=_optional_array(_mapping_value(payload, "samples", default=None)),
        intervals=_intervals_from_payload(_mapping_value(payload, "intervals", default=None)),
        uncertainty=_uncertainty_from_payload(_mapping_value(payload, "uncertainty", default=None)),
        diagnostics=_diagnostics_from_payload(_mapping_value(payload, "diagnostics", default=None)),
        validation=_validation_from_payload(_mapping_value(payload, "validation", default=None)),
        influence_values=_optional_array(_mapping_value(payload, "influence_values", default=None)),
        bootstrap_replicates=_optional_array(_mapping_value(payload, "bootstrap_replicates", default=None)),
        native_result_ref=_optional_str(_mapping_value(payload, "native_result_ref", default=None)),
    )


def estimand_from_mapping(payload: Mapping[str, Any], query: Any = None) -> EstimandSpec:
    """Build an ``EstimandSpec`` from a JSON-like payload."""

    return EstimandSpec(
        query_id=str(_mapping_value(payload, "query_id", default=_query_value(query, "query_id", "method_advisor_query"))),
        estimand_id=str(_mapping_value(payload, "estimand_id", default=_query_value(query, "estimand_id", "default"))),
        outcome=str(_mapping_value(payload, "outcome", default=_query_value(query, "outcome", "outcome"))),
        treatment_or_exposure=_optional_str(_mapping_value(payload, "treatment_or_exposure", default=None)),
        covariates_or_conditioning=_string_tuple(_mapping_value(payload, "covariates_or_conditioning", default=())),
        adjustment_set=_optional_string_tuple(_mapping_value(payload, "adjustment_set", default=None)),
        population=str(_mapping_value(payload, "population", default="unspecified")),
        sample_filter=_optional_str(_mapping_value(payload, "sample_filter", default=None)),
        time_horizon=_optional_str(_mapping_value(payload, "time_horizon", default=None)),
        prediction_origin=_optional_str(_mapping_value(payload, "prediction_origin", default=None)),
        unit=str(_mapping_value(payload, "unit", default="unitless")),
        scale=_estimand_scale(_mapping_value(payload, "scale", default="identity")),
        transform=_optional_str(_mapping_value(payload, "transform", default=None)),
        target_role=_target_role(_mapping_value(payload, "target_role", default="estimate")),
        loss_or_utility_id=_optional_str(_mapping_value(payload, "loss_or_utility_id", default=None)),
    )


def estimand_from_query(
    query: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
    default_estimand_id: str = "default",
    default_outcome: str = "outcome",
    default_role: TargetRole = "estimate",
) -> EstimandSpec:
    """Infer an estimand from query-like attributes plus optional result metadata."""

    meta = metadata or {}
    consensus = _nested_mapping(meta, "consensus")
    source = consensus or meta
    return EstimandSpec(
        query_id=str(_mapping_value(source, "query_id", default=_query_value(query, "query_id", "method_advisor_query"))),
        estimand_id=str(_mapping_value(source, "estimand_id", default=_query_value(query, "estimand_id", default_estimand_id))),
        outcome=str(_mapping_value(source, "outcome", default=_query_value(query, "outcome", default_outcome))),
        treatment_or_exposure=_optional_str(
            _mapping_value(source, "treatment_or_exposure", default=_query_value(query, "treatment_or_exposure", None))
        ),
        covariates_or_conditioning=_string_tuple(
            _mapping_value(source, "covariates_or_conditioning", default=_query_value(query, "covariates_or_conditioning", ()))
        ),
        adjustment_set=_optional_string_tuple(
            _mapping_value(source, "adjustment_set", default=_query_value(query, "adjustment_set", None))
        ),
        population=str(_mapping_value(source, "population", default=_query_value(query, "population", "unspecified"))),
        sample_filter=_optional_str(_mapping_value(source, "sample_filter", default=_query_value(query, "sample_filter", None))),
        time_horizon=_optional_str(_mapping_value(source, "time_horizon", default=_query_value(query, "time_horizon", None))),
        prediction_origin=_optional_str(
            _mapping_value(source, "prediction_origin", default=_query_value(query, "prediction_origin", None))
        ),
        unit=str(_mapping_value(source, "unit", default=_query_value(query, "unit", "unitless"))),
        scale=_estimand_scale(_mapping_value(source, "scale", default=_query_value(query, "scale", "identity"))),
        transform=_optional_str(_mapping_value(source, "transform", default=_query_value(query, "transform", None))),
        target_role=_target_role(_mapping_value(source, "target_role", default=_query_value(query, "target_role", default_role))),
        loss_or_utility_id=_optional_str(
            _mapping_value(source, "loss_or_utility_id", default=_query_value(query, "loss_or_utility_id", None))
        ),
    )


def target_from_econometric_result(result: Any, query: Any = None) -> ConsensusTarget:
    """Adapter for ``catalog.econometrics.protocols.EconometricResult``."""

    metadata = dict(getattr(result, "metadata", {}) or {})
    consensus = _nested_mapping(metadata, "consensus")
    param_names = _string_tuple(_mapping_value(consensus, "param_names", default=()))
    if not param_names:
        params = getattr(result, "params", {}) or {}
        non_const = [name for name in params if str(name).lower() != "const"]
        param_names = tuple(non_const[:1] or list(params)[:1])
    if not param_names:
        raise NotComparableYet("EconometricResult has no parameter to compare")
    params = getattr(result, "params", {}) or {}
    std_errors = getattr(result, "std_errors", {}) or {}
    point = np.asarray([float(params[name]) for name in param_names], dtype=float)
    covariance = _optional_array(_mapping_value(consensus, "covariance", default=None))
    if covariance is None:
        variances = [float(std_errors.get(name, math.nan)) ** 2 for name in param_names]
        covariance = None if any(not math.isfinite(value) for value in variances) else np.diag(variances)
    intervals = []
    for name in param_names:
        interval = (getattr(result, "confidence_intervals", {}) or {}).get(name)
        if interval is not None:
            intervals.append(
                IntervalSummary(
                    level=float(getattr(result, "confidence_level", 0.95)),
                    lower=(float(interval[0]),),
                    upper=(float(interval[1]),),
                    interval_type="confidence",
                )
            )
    family = str(_mapping_value(consensus, "method_family", default=metadata.get("method_family", "econometric")))
    estimand = estimand_from_query(
        query,
        metadata={
            **metadata,
            "estimand_id": _mapping_value(consensus, "estimand_id", default=param_names[0]),
            "outcome": _mapping_value(consensus, "outcome", default=param_names[0]),
            "target_role": _mapping_value(consensus, "target_role", default="causal"),
        },
        default_estimand_id=param_names[0],
        default_outcome=param_names[0],
        default_role="causal",
    )
    return ConsensusTarget(
        result_id=str(_mapping_value(consensus, "result_id", default=f"{getattr(result, 'method_name', 'econometric')}:{param_names[0]}")),
        method_family=family,
        method_name=str(getattr(result, "method_name", "econometric")),
        estimand=estimand,
        target_kind=_target_kind(_mapping_value(consensus, "target_kind", default="causal_effect")),
        point=point,
        covariance=covariance,
        intervals=tuple(intervals),
        uncertainty=UncertaintyContract(
            uncertainty_type="parameter",
            covariance_type=str(_mapping_value(consensus, "covariance_type", default="standard_error_diagonal")),
            confidence_level=float(getattr(result, "confidence_level", 0.95)),
        ),
        diagnostics=_econometric_diagnostics(result),
        bootstrap_replicates=_optional_array(_mapping_value(consensus, "bootstrap_replicates", default=None)),
        influence_values=_optional_array(_mapping_value(consensus, "influence_values", default=None)),
        native_result_ref=str(getattr(result, "contract_id", "foundry.econometrics.result")),
    )


def target_from_posterior_result(result: Any, query: Any = None) -> ConsensusTarget:
    """Adapter for ``catalog.bayesian.protocols.PosteriorResult``."""

    metadata = dict(getattr(result, "metadata", {}) or {})
    consensus = _nested_mapping(metadata, "consensus")
    param_names = _string_tuple(_mapping_value(consensus, "param_names", default=()))
    posterior_means = getattr(result, "posterior_means", {}) or {}
    if not param_names:
        param_names = tuple(
            name
            for name in sorted(posterior_means)
            if str(name).lower() not in {"sigma", "obs_noise", "noise_scale"}
        )
        param_names = param_names[:1] or tuple(sorted(posterior_means)[:1])
    if not param_names:
        raise NotComparableYet("PosteriorResult has no posterior mean to compare")
    posterior_stds = getattr(result, "posterior_stds", {}) or {}
    point = np.asarray([float(posterior_means[name]) for name in param_names], dtype=float)
    covariance = _optional_array(_mapping_value(consensus, "covariance", default=None))
    if covariance is None:
        variances = [float(posterior_stds.get(name, math.nan)) ** 2 for name in param_names]
        covariance = None if any(not math.isfinite(value) for value in variances) else np.diag(variances)
    intervals = []
    for name in param_names:
        interval = (getattr(result, "credible_intervals", {}) or {}).get(name)
        if interval is not None:
            intervals.append(
                IntervalSummary(
                    level=float(_mapping_value(consensus, "credible_level", default=0.95)),
                    lower=(float(interval[0]),),
                    upper=(float(interval[1]),),
                    interval_type="credible",
                )
            )
    estimand = estimand_from_query(
        query,
        metadata={
            **metadata,
            "estimand_id": _mapping_value(consensus, "estimand_id", default=param_names[0]),
            "outcome": _mapping_value(consensus, "outcome", default=param_names[0]),
            "target_role": _mapping_value(consensus, "target_role", default="estimate"),
        },
        default_estimand_id=param_names[0],
        default_outcome=param_names[0],
    )
    return ConsensusTarget(
        result_id=str(_mapping_value(consensus, "result_id", default=f"{getattr(result, 'method_name', 'posterior')}:{param_names[0]}")),
        method_family=str(_mapping_value(consensus, "method_family", default="bayesian")),
        method_name=str(getattr(result, "method_name", "posterior")),
        estimand=estimand,
        target_kind=_target_kind(_mapping_value(consensus, "target_kind", default="parameter")),
        point=point,
        covariance=covariance,
        samples=_optional_array(_mapping_value(consensus, "samples", default=None)),
        intervals=tuple(intervals),
        uncertainty=UncertaintyContract(
            uncertainty_type="parameter",
            covariance_type="posterior_covariance",
            confidence_level=float(_mapping_value(consensus, "credible_level", default=0.95)),
        ),
        diagnostics=_posterior_diagnostics(result),
        native_result_ref=str(getattr(result, "contract_id", "foundry.bayesian.posterior_result")),
    )


def target_from_prediction_result(result: Any, query: Any = None) -> ConsensusTarget:
    """Adapter for ``catalog.ml.protocols.PredictionResult``."""

    metadata = dict(getattr(result, "metadata", {}) or {})
    consensus = _nested_mapping(metadata, "consensus")
    predictions = _as_1d_vector(result.predictions, field_name="PredictionResult.predictions")
    aggregate = str(_mapping_value(consensus, "aggregate", default="vector"))
    point = np.asarray([float(np.mean(predictions))], dtype=float) if aggregate == "mean" else predictions
    covariance = _optional_array(_mapping_value(consensus, "covariance", default=None))
    if covariance is None and aggregate == "mean" and getattr(result, "target", None) is not None:
        target = _as_1d_vector(result.target, field_name="PredictionResult.target")
        residual = target - predictions
        variance = float(np.var(residual, ddof=1) / max(len(residual), 1)) if len(residual) > 1 else 0.0
        covariance = np.asarray([[max(variance, _EPS)]], dtype=float)
    estimand = estimand_from_query(
        query,
        metadata={
            **metadata,
            "estimand_id": _mapping_value(consensus, "estimand_id", default="prediction"),
            "outcome": _mapping_value(consensus, "outcome", default="prediction"),
            "target_role": _mapping_value(consensus, "target_role", default="prediction"),
        },
        default_estimand_id="prediction",
        default_outcome="prediction",
        default_role="prediction",
    )
    return ConsensusTarget(
        result_id=str(_mapping_value(consensus, "result_id", default=f"{getattr(result, 'method_name', 'prediction')}:prediction")),
        method_family=str(_mapping_value(consensus, "method_family", default="prediction")),
        method_name=str(getattr(result, "method_name", "prediction")),
        estimand=estimand,
        target_kind=_target_kind(_mapping_value(consensus, "target_kind", default="predictive_mean")),
        point=point,
        covariance=covariance,
        samples=_optional_array(_mapping_value(consensus, "samples", default=None)),
        uncertainty=UncertaintyContract(
            uncertainty_type="predictive_mean" if aggregate == "mean" else "unknown",
            covariance_type="validation_residual" if covariance is not None else None,
        ),
        diagnostics=MethodDiagnostics(raw=dict(getattr(result, "metrics", {}) or {})),
        validation=_prediction_validation(result),
        native_result_ref=str(getattr(result, "contract_id", "foundry.ml.prediction_result")),
    )


def _align_transformable_target_scales(
    targets: Sequence[ConsensusTarget],
    query: Any,
) -> list[ConsensusTarget]:
    grouped: dict[tuple[tuple[Any, ...], TargetKind, int], list[ConsensusTarget]] = defaultdict(list)
    for target in targets:
        grouped[
            (
                _estimand_identity_without_scale(target.estimand),
                target.target_kind,
                int(target.point.shape[0]),
            )
        ].append(target)

    aligned: list[ConsensusTarget] = []
    for group in grouped.values():
        destination = _preferred_common_scale(group, query)
        if destination is None:
            aligned.extend(group)
            continue
        for target in group:
            if target.estimand.scale == destination:
                aligned.append(target)
                continue
            try:
                aligned.append(_transform_target_scale(target, destination))
            except ValueError:
                aligned.append(target)
    return aligned


def _estimand_identity_without_scale(estimand: EstimandSpec) -> tuple[Any, ...]:
    return (
        estimand.query_id,
        estimand.estimand_id,
        estimand.outcome,
        estimand.treatment_or_exposure,
        estimand.covariates_or_conditioning,
        estimand.adjustment_set,
        estimand.population,
        estimand.sample_filter,
        estimand.time_horizon,
        estimand.prediction_origin,
        estimand.unit,
        estimand.target_role,
        estimand.loss_or_utility_id,
    )


def _preferred_common_scale(
    group: Sequence[ConsensusTarget],
    query: Any,
) -> EstimandScale | None:
    query_scale = _query_value(query, "scale", None)
    candidates: list[str] = []
    if query_scale is not None:
        candidates.append(str(query_scale))
    candidates.extend(["identity", "probability"])
    candidates.extend(target.estimand.scale for target in group)
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate not in {"identity", "log", "logit", "probability", "standardized", "custom"}:
            continue
        scale = _estimand_scale(candidate)
        if all(_can_transform_target_scale(target, scale) for target in group):
            return scale
    return None


def _can_transform_target_scale(target: ConsensusTarget, destination: EstimandScale) -> bool:
    if target.estimand.scale == destination:
        return True
    try:
        _scale_transform_values(target.point, target.estimand.scale, destination)
        _scale_transform_derivative(target.point, target.estimand.scale, destination)
    except ValueError:
        return False
    return True


def _transform_target_scale(
    target: ConsensusTarget,
    destination: EstimandScale,
) -> ConsensusTarget:
    source = target.estimand.scale
    transformed_point = _scale_transform_values(target.point, source, destination)
    derivative = _scale_transform_derivative(target.point, source, destination)
    transformed_covariance = None
    if target.covariance is not None:
        jacobian = np.diag(derivative)
        transformed_covariance = jacobian @ target.covariance @ jacobian
    transformed_samples = (
        None
        if target.samples is None
        else _scale_transform_values(target.samples, source, destination)
    )
    transformed_bootstrap = (
        None
        if target.bootstrap_replicates is None
        else _scale_transform_values(target.bootstrap_replicates, source, destination)
    )
    transformed_influence = (
        None
        if target.influence_values is None
        else target.influence_values * derivative.reshape(1, -1)
    )
    transformed_quantiles = None
    if target.quantiles is not None:
        transformed_quantiles = {
            level: _scale_transform_values(values, source, destination)
            for level, values in target.quantiles.items()
        }
    return replace(
        target,
        estimand=replace(target.estimand, scale=destination, transform=None),
        point=transformed_point,
        covariance=transformed_covariance,
        samples=transformed_samples,
        bootstrap_replicates=transformed_bootstrap,
        influence_values=transformed_influence,
        quantiles=transformed_quantiles,
    )


def _scale_transform_values(
    values: np.ndarray,
    source: EstimandScale,
    destination: EstimandScale,
) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if source == destination:
        return arr
    if source == "log" and destination == "identity":
        return np.exp(np.clip(arr, -700.0, 700.0))
    if source == "identity" and destination == "log":
        if np.any(arr <= 0.0):
            raise ValueError("identity-to-log transform requires positive values")
        return np.log(arr)
    if source == "logit" and destination == "probability":
        clipped = np.clip(arr, -700.0, 700.0)
        return 1.0 / (1.0 + np.exp(-clipped))
    if source == "probability" and destination == "logit":
        if np.any((arr <= 0.0) | (arr >= 1.0)):
            raise ValueError("probability-to-logit transform requires values in (0, 1)")
        return np.log(arr / (1.0 - arr))
    raise ValueError(f"unsupported scale transform: {source!r} -> {destination!r}")


def _scale_transform_derivative(
    point: np.ndarray,
    source: EstimandScale,
    destination: EstimandScale,
) -> np.ndarray:
    arr = np.asarray(point, dtype=float)
    if source == destination:
        return np.ones_like(arr, dtype=float)
    if source == "log" and destination == "identity":
        return np.exp(np.clip(arr, -700.0, 700.0))
    if source == "identity" and destination == "log":
        if np.any(arr <= 0.0):
            raise ValueError("identity-to-log transform requires positive values")
        return 1.0 / arr
    if source == "logit" and destination == "probability":
        prob = 1.0 / (1.0 + np.exp(-np.clip(arr, -700.0, 700.0)))
        return prob * (1.0 - prob)
    if source == "probability" and destination == "logit":
        if np.any((arr <= 0.0) | (arr >= 1.0)):
            raise ValueError("probability-to-logit transform requires values in (0, 1)")
        return 1.0 / (arr * (1.0 - arr))
    raise ValueError(f"unsupported scale transform: {source!r} -> {destination!r}")


def _coerce_consensus_target(
    result: SupportsConsensusTarget | ConsensusTarget | Mapping[str, Any],
    query: Any,
) -> ConsensusTarget:
    if isinstance(result, ConsensusTarget):
        return result
    if isinstance(result, Mapping):
        return consensus_target_from_mapping(result, query)
    adapter = getattr(result, "to_consensus_target", None)
    if adapter is None:
        raise TypeError(f"{type(result).__name__} does not implement to_consensus_target")
    target = adapter(query)
    if not isinstance(target, ConsensusTarget):
        raise TypeError("to_consensus_target must return ConsensusTarget")
    return target


def _variance_of_difference(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
) -> tuple[np.ndarray | None, CovarianceSource]:
    if (
        target_i.influence_values is not None
        and target_j.influence_values is not None
        and target_i.influence_values.shape == target_j.influence_values.shape
        and target_i.influence_values.shape[0] >= 2
    ):
        return _covariance_of_draws(target_i.influence_values - target_j.influence_values), "influence_function"
    if (
        target_i.bootstrap_replicates is not None
        and target_j.bootstrap_replicates is not None
        and target_i.bootstrap_replicates.shape == target_j.bootstrap_replicates.shape
        and target_i.bootstrap_replicates.shape[0] >= 2
    ):
        return _covariance_of_draws(target_i.bootstrap_replicates - target_j.bootstrap_replicates), "paired_bootstrap"
    if (
        target_i.samples is not None
        and target_j.samples is not None
        and target_i.samples.shape == target_j.samples.shape
        and target_i.samples.shape[0] >= 2
    ):
        return _covariance_of_draws(target_i.samples - target_j.samples), "joint_draws"
    cov_i = _target_covariance(target_i)
    cov_j = _target_covariance(target_j)
    if cov_i is None or cov_j is None:
        return None, "unavailable"
    return cov_i + cov_j, "independence_approximation"


def _target_covariance(target: ConsensusTarget) -> np.ndarray | None:
    if target.covariance is not None:
        return target.covariance
    if target.samples is not None and target.samples.shape[0] >= 2:
        return _covariance_of_draws(target.samples)
    if target.bootstrap_replicates is not None and target.bootstrap_replicates.shape[0] >= 2:
        return _covariance_of_draws(target.bootstrap_replicates)
    return None


def _covariance_of_draws(draws: np.ndarray) -> np.ndarray:
    matrix = np.asarray(draws, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("draws must be 2D")
    if matrix.shape[0] <= 1:
        return np.zeros((matrix.shape[1], matrix.shape[1]), dtype=float)
    covariance = np.cov(matrix, rowvar=False, ddof=1)
    return np.atleast_2d(np.asarray(covariance, dtype=float))


def _decision_relevance(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    query: Any,
) -> tuple[bool, str | None]:
    delta = target_i.point - target_j.point
    signs_differ = _sign_difference(target_i.point, target_j.point)
    practical_delta = _query_float(query, "practical_delta")
    if practical_delta is None:
        practical_delta = _query_float(query, "consensus_practical_delta")
    abs_gap = float(np.max(np.abs(delta))) if delta.size else 0.0
    threshold_crossings = _threshold_crossings_differ(target_i, target_j, query)
    rankings_differ = target_i.point.shape[0] > 1 and int(np.argmax(target_i.point)) != int(
        np.argmax(target_j.point)
    )
    if signs_differ:
        return True, "effect signs differ"
    if threshold_crossings:
        return True, "decision threshold crossings differ"
    if rankings_differ:
        return True, "top-ranked alternative differs"
    if practical_delta is not None and abs_gap > practical_delta:
        return True, f"absolute gap {abs_gap:.6g} exceeds practical delta {practical_delta:.6g}"
    if _strict_consensus_validation(query):
        return True, "strict consensus validation treats statistical disagreement as decision-relevant"
    return False, None


def _distribution_decision_relevance(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    query: Any,
) -> tuple[bool, str | None]:
    if target_i.samples is None or target_j.samples is None:
        return False, None
    threshold = _query_float(query, "tail_risk_threshold")
    if threshold is None:
        threshold = _query_float(query, "risk_threshold")
    risk_delta = _query_float(query, "tail_risk_delta")
    if risk_delta is None:
        risk_delta = _query_float(query, "risk_class_delta")
    if threshold is not None:
        prob_i = float(np.mean(np.any(target_i.samples >= threshold, axis=1)))
        prob_j = float(np.mean(np.any(target_j.samples >= threshold, axis=1)))
        if risk_delta is not None and abs(prob_i - prob_j) > risk_delta:
            return (
                True,
                f"tail risk differs by {abs(prob_i - prob_j):.6g} at threshold {threshold:.6g}",
            )
    quantile_level = _query_float(query, "decision_quantile")
    if quantile_level is None:
        quantile_level = _query_float(query, "tail_quantile")
    practical_delta = _query_float(query, "practical_delta")
    if practical_delta is None:
        practical_delta = _query_float(query, "consensus_practical_delta")
    if quantile_level is not None and practical_delta is not None:
        level = min(max(float(quantile_level), 0.0), 1.0)
        q_i = np.quantile(target_i.samples, level, axis=0)
        q_j = np.quantile(target_j.samples, level, axis=0)
        gap = float(np.max(np.abs(q_i - q_j)))
        if gap > practical_delta:
            return True, f"quantile {level:.3g} gap {gap:.6g} exceeds practical delta"
    if _strict_consensus_validation(query):
        return True, "strict consensus validation treats distributional disagreement as decision-relevant"
    return False, None


def _sign_difference(point_i: np.ndarray, point_j: np.ndarray) -> bool:
    return bool(
        np.any([_sign_class(left) != _sign_class(right) for left, right in zip(point_i, point_j, strict=True)])
    )


def _sign_class(value: float) -> int:
    parsed = float(value)
    if parsed > _EPS:
        return 1
    if parsed < -_EPS:
        return -1
    return 0


def _strict_consensus_validation(query: Any) -> bool:
    return bool(
        _query_value(query, "strict_consensus_validation", False)
        or _query_value(query, "strict_validation", False)
    )


def _decision_threshold(query: Any) -> float | None:
    threshold = _query_float(query, "decision_threshold")
    if threshold is None:
        threshold = _query_float(query, "threshold")
    return threshold


def _threshold_crossings_differ(
    target_i: ConsensusTarget,
    target_j: ConsensusTarget,
    query: Any,
) -> bool:
    threshold = _decision_threshold(query)
    if threshold is None:
        return False
    return bool(np.any((target_i.point >= threshold) != (target_j.point >= threshold)))


def _group_by_comparable_identity(
    targets: Sequence[ConsensusTarget],
) -> dict[tuple[EstimandSpec, TargetKind], list[ConsensusTarget]]:
    groups: dict[tuple[EstimandSpec, TargetKind], list[ConsensusTarget]] = defaultdict(list)
    for target in targets:
        groups[_comparable_identity(target)].append(target)
    return dict(groups)


def _comparable_identity(target: ConsensusTarget) -> tuple[EstimandSpec, TargetKind]:
    return target.estimand, target.target_kind


def _noncomparable_pair(target_i: ConsensusTarget, target_j: ConsensusTarget) -> PairwiseDisagreement:
    reason = _noncomparable_reason(target_i, target_j)
    return PairwiseDisagreement(
        method_i=target_i.result_id,
        method_j=target_j.result_id,
        comparable=False,
        noncomparable_reason=reason,
        estimand=None,
        projection=None,
        metric="decision_disagreement",
        statistic=None,
        degrees_of_freedom=None,
        raw_p_value=None,
        adjusted_q_value=None,
        cmd_score=None,
        threshold=1.0,
        point_i=tuple(float(value) for value in target_i.point),
        point_j=tuple(float(value) for value in target_j.point),
        covariance_source="unavailable",
        decision_relevant=False,
        decision_difference=None,
        severity="none",
    )


def _noncomparable_reason(target_i: ConsensusTarget, target_j: ConsensusTarget) -> str:
    if target_i.target_kind != target_j.target_kind:
        return f"target_kind differs: {target_i.target_kind!r} vs {target_j.target_kind!r}"
    fields = (
        "outcome",
        "treatment_or_exposure",
        "covariates_or_conditioning",
        "adjustment_set",
        "population",
        "sample_filter",
        "time_horizon",
        "prediction_origin",
        "unit",
        "scale",
        "target_role",
        "loss_or_utility_id",
    )
    for name in fields:
        left = getattr(target_i.estimand, name)
        right = getattr(target_j.estimand, name)
        if left != right:
            return f"estimand.{name} differs: {left!r} vs {right!r}"
    return "canonical estimands differ"


def _adjust_p_values(
    p_values: Sequence[float],
    *,
    method: MultiplicityAdjustment,
) -> tuple[float, ...]:
    if not p_values:
        return ()
    clipped = [_clip_probability(value) for value in p_values]
    n = len(clipped)
    if method == "none":
        return tuple(clipped)
    if method == "bonferroni":
        return tuple(min(value * n, 1.0) for value in clipped)
    if method == "sidak":
        return tuple(1.0 - (1.0 - value) ** n for value in clipped)
    if method != "holm":
        raise ValueError(f"unsupported multiplicity adjustment: {method!r}")
    order = sorted(range(n), key=lambda index: clipped[index])
    adjusted_sorted: list[float] = [1.0] * n
    running = 0.0
    for rank, original_index in enumerate(order):
        value = min((n - rank) * clipped[original_index], 1.0)
        running = max(running, value)
        adjusted_sorted[rank] = running
    result = [1.0] * n
    for rank, original_index in enumerate(order):
        result[original_index] = adjusted_sorted[rank]
    return tuple(result)


def _cmd_score(q_value: float | None, alpha_refuse: float) -> float | None:
    if q_value is None:
        return None
    q = max(_clip_probability(q_value), 1.0e-300)
    denom = -math.log10(alpha_refuse)
    if denom <= 0.0:
        return None
    return float(-math.log10(q) / denom)


def _severity(
    q_value: float | None,
    alpha_warn: float,
    alpha_refuse: float,
    alpha_hard_refuse: float,
    decision_relevant: bool,
) -> Severity:
    if q_value is None:
        return "low"
    if q_value <= alpha_hard_refuse and decision_relevant:
        return "hard_refusal"
    if q_value <= alpha_refuse and decision_relevant:
        return "refusal"
    if q_value <= alpha_warn:
        return "warning"
    return "none"


def _chi2_survival(statistic: float, degrees_of_freedom: int) -> float:
    if not math.isfinite(statistic):
        return 0.0
    if statistic <= 0.0:
        return 1.0
    try:
        from scipy.stats import chi2

        return float(chi2.sf(statistic, degrees_of_freedom))
    except Exception:  # pragma: no cover - exercised when scipy is unavailable
        pass
    if degrees_of_freedom == 1:
        return float(math.erfc(math.sqrt(statistic / 2.0)))
    if degrees_of_freedom == 2:
        return float(math.exp(-statistic / 2.0))
    z = (
        ((statistic / degrees_of_freedom) ** (1.0 / 3.0))
        - (1.0 - 2.0 / (9.0 * degrees_of_freedom))
    ) / math.sqrt(2.0 / (9.0 * degrees_of_freedom))
    return float(1.0 - NormalDist().cdf(z))


def _green_components(
    targets: Sequence[ConsensusTarget],
    checks: Sequence[PairwiseDisagreement],
    *,
    alpha_warn: float,
) -> list[tuple[str, ...]]:
    ids = tuple(target.result_id for target in targets)
    adjacency: dict[str, set[str]] = {result_id: set() for result_id in ids}
    for check in checks:
        if (
            check.comparable
            and check.adjusted_q_value is not None
            and check.adjusted_q_value > alpha_warn
        ):
            adjacency[check.method_i].add(check.method_j)
            adjacency[check.method_j].add(check.method_i)
    seen: set[str] = set()
    components: list[tuple[str, ...]] = []
    for result_id in ids:
        if result_id in seen:
            continue
        queue = deque([result_id])
        seen.add(result_id)
        component: list[str] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(tuple(sorted(component)))
    components.sort(key=lambda item: (-len(item), item))
    return components


def _is_red_edge(
    method_i: str,
    method_j: str,
    red_checks: Sequence[PairwiseDisagreement],
) -> bool:
    pair = frozenset((method_i, method_j))
    return any(frozenset((check.method_i, check.method_j)) == pair for check in red_checks)


def _targets_by_family(targets: Sequence[ConsensusTarget]) -> dict[str, tuple[ConsensusTarget, ...]]:
    grouped: dict[str, list[ConsensusTarget]] = defaultdict(list)
    for target in targets:
        grouped[target.method_family].append(target)
    return {family: tuple(members) for family, members in grouped.items()}


def _family_pattern_score(
    family: str,
    members: Sequence[ConsensusTarget],
    targets: Sequence[ConsensusTarget],
    red_checks: Sequence[PairwiseDisagreement],
    consensus_set: Sequence[str],
) -> float:
    member_ids = {target.result_id for target in members}
    consensus_ids = set(consensus_set)
    if member_ids and member_ids.isdisjoint(consensus_ids):
        red_to_consensus = 0
        total_to_consensus = 0
        for member_id in member_ids:
            for consensus_id in consensus_ids:
                total_to_consensus += 1
                if _is_red_edge(member_id, consensus_id, red_checks):
                    red_to_consensus += 1
        if total_to_consensus and red_to_consensus == total_to_consensus:
            return 1.0
    other_families = {
        target.method_family
        for target in targets
        if target.method_family != family
        and any(
            _is_red_edge(member.result_id, target.result_id, red_checks) for member in members
        )
    }
    return min(len(other_families) / 2.0, 1.0)


def _uncertainty_underestimated(
    targets: Sequence[ConsensusTarget],
    red_checks: Sequence[PairwiseDisagreement],
) -> bool:
    by_id = {target.result_id: target for target in targets}
    for check in red_checks:
        left = by_id.get(check.method_i)
        right = by_id.get(check.method_j)
        if left is None or right is None:
            continue
        gap = float(np.linalg.norm(left.point - right.point))
        if gap <= _EPS:
            continue
        for target in (left, right):
            cov = _target_covariance(target)
            if cov is None:
                continue
            trace = float(np.trace(cov))
            if trace > 0.0 and math.sqrt(trace) < 0.05 * gap:
                return True
    return False


def _developer_message(
    status: ConsensusStatus,
    worst: PairwiseDisagreement,
    classifier: MisspecificationClassification,
) -> str:
    q = "unavailable" if worst.adjusted_q_value is None else f"{worst.adjusted_q_value:.6g}"
    return (
        f"{status}: worst_pair={worst.method_i} vs {worst.method_j}; "
        f"metric={worst.metric}; adjusted_q={q}; "
        f"classifier={classifier.status}"
    )


def _consensus_remediation(
    status: ConsensusStatus,
    classifier: MisspecificationClassification,
    noncomparable_ids: Sequence[str],
) -> tuple[str, ...]:
    items: list[str] = []
    if status in {"refuse", "hard_refuse"}:
        items.append("Do not issue a method recommendation until the conflict is resolved.")
        items.extend(classifier.recommended_remediation)
    if noncomparable_ids:
        items.append("Canonicalize non-comparable outputs to the same estimand before interpreting disagreement.")
    if not items:
        items.append("Continue to monitor cross-method agreement as more outputs become available.")
    return tuple(dict.fromkeys(items))


def _validate_thresholds(
    alpha_warn: float,
    alpha_refuse: float,
    alpha_hard_refuse: float,
) -> tuple[float, float, float]:
    values = (float(alpha_warn), float(alpha_refuse), float(alpha_hard_refuse))
    if not all(0.0 < value < 1.0 for value in values):
        raise ValueError("alpha thresholds must be in (0, 1)")
    if not (values[2] <= values[1] <= values[0]):
        raise ValueError("thresholds must satisfy alpha_hard_refuse <= alpha_refuse <= alpha_warn")
    return values


def _as_1d_vector(value: Any, *, field_name: str = "value") -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    if arr.size == 0:
        raise ValueError(f"{field_name} must not be empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{field_name} must contain finite values")
    return arr.astype(float, copy=False)


def _as_square_matrix(value: Any, d: int, *, field_name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0 and d == 1:
        arr = arr.reshape(1, 1)
    if arr.ndim == 1 and d == 1 and arr.size == 1:
        arr = arr.reshape(1, 1)
    if arr.shape != (d, d):
        raise ValueError(f"{field_name} must have shape {(d, d)}, got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{field_name} must contain finite values")
    return arr


def _as_draw_matrix(value: Any, d: int) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1 and d == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2 or arr.shape[1] != d:
        raise ValueError(f"draw matrix must have shape [draws, {d}], got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("draw matrix must contain finite values")
    return arr


def _optional_array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    return np.asarray(value, dtype=float)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value)


def _optional_string_tuple(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    return _string_tuple(value)


def _mapping_value(mapping: Mapping[str, Any] | None, key: str, *, default: Any) -> Any:
    if mapping is None:
        return default
    return mapping.get(key, default)


def _nested_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _query_value(query: Any, key: str, default: Any) -> Any:
    if query is None:
        return default
    if isinstance(query, Mapping):
        return query.get(key, default)
    if hasattr(query, key):
        return getattr(query, key)
    criteria = getattr(query, "criteria", None)
    if criteria is not None and hasattr(criteria, key):
        return getattr(criteria, key)
    return default


def _query_float(query: Any, key: str) -> float | None:
    value = _query_value(query, key, None)
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _target_kind(value: Any) -> TargetKind:
    text = str(value)
    allowed = {
        "parameter",
        "causal_effect",
        "predictive_mean",
        "predictive_observable",
        "policy_value",
        "counterfactual",
        "classification_probability",
    }
    if text not in allowed:
        raise ValueError(f"unsupported target_kind: {text!r}")
    return text  # type: ignore[return-value]


def _estimand_scale(value: Any) -> EstimandScale:
    text = str(value)
    allowed = {"identity", "log", "logit", "probability", "standardized", "custom"}
    if text not in allowed:
        raise ValueError(f"unsupported estimand scale: {text!r}")
    return text  # type: ignore[return-value]


def _target_role(value: Any) -> TargetRole:
    text = str(value)
    allowed = {"estimate", "prediction", "causal", "decision", "ranking", "screening"}
    if text not in allowed:
        raise ValueError(f"unsupported target_role: {text!r}")
    return text  # type: ignore[return-value]


def _intervals_from_payload(value: Any) -> tuple[IntervalSummary, ...] | None:
    if value is None:
        return None
    intervals: list[IntervalSummary] = []
    for item in value:
        if isinstance(item, IntervalSummary):
            intervals.append(item)
        elif isinstance(item, Mapping):
            intervals.append(
                IntervalSummary(
                    level=float(item.get("level", 0.95)),
                    lower=tuple(float(v) for v in item.get("lower", ())),
                    upper=tuple(float(v) for v in item.get("upper", ())),
                    interval_type=str(item.get("interval_type", "confidence")),  # type: ignore[arg-type]
                )
            )
    return tuple(intervals)


def _uncertainty_from_payload(value: Any) -> UncertaintyContract:
    if isinstance(value, UncertaintyContract):
        return value
    if isinstance(value, Mapping):
        return UncertaintyContract(
            uncertainty_type=str(value.get("uncertainty_type", "unknown")),  # type: ignore[arg-type]
            covariance_type=_optional_str(value.get("covariance_type")),
            confidence_level=None if value.get("confidence_level") is None else float(value["confidence_level"]),
            reliability_score=_clip_unit(float(value.get("reliability_score", 1.0))),
            notes=_string_tuple(value.get("notes", ())),
        )
    return UncertaintyContract()


def _diagnostics_from_payload(value: Any) -> MethodDiagnostics:
    if isinstance(value, MethodDiagnostics):
        return value
    if isinstance(value, Mapping):
        return MethodDiagnostics(
            failure_score=_clip_unit(float(value.get("failure_score", 0.0))),
            computational_failure_score=_clip_unit(float(value.get("computational_failure_score", 0.0))),
            validation_disadvantage_score=_clip_unit(float(value.get("validation_disadvantage_score", 0.0))),
            issues=_string_tuple(value.get("issues", ())),
            raw=value,
        )
    return MethodDiagnostics()


def _validation_from_payload(value: Any) -> ValidationSummary | None:
    if value is None or isinstance(value, ValidationSummary):
        return value
    if isinstance(value, Mapping):
        return ValidationSummary(
            calibration_failure_score=_clip_unit(float(value.get("calibration_failure_score", 0.0))),
            scoring_disadvantage_score=_clip_unit(float(value.get("scoring_disadvantage_score", 0.0))),
            raw=value,
        )
    return None


def _econometric_diagnostics(result: Any) -> MethodDiagnostics:
    diagnostics = dict(getattr(result, "diagnostics", {}) or {})
    issues: list[str] = []
    score = 0.0
    weak_iv = _safe_float(diagnostics.get("weak_instrument_stat"))
    if weak_iv is not None and weak_iv < 10.0:
        issues.append("weak_instrument_stat_below_10")
        score = max(score, 0.8)
    overid = _safe_float(diagnostics.get("overidentification_pvalue"))
    if overid is not None and overid < 0.05:
        issues.append("overidentification_rejected")
        score = max(score, 0.7)
    pretrend = _safe_float(diagnostics.get("pretrend_pvalue"))
    if pretrend is not None and pretrend < 0.05:
        issues.append("pretrend_rejected")
        score = max(score, 0.6)
    return MethodDiagnostics(failure_score=score, issues=tuple(issues), raw=diagnostics)


def _posterior_diagnostics(result: Any) -> MethodDiagnostics:
    diagnostics = {
        **dict(getattr(result, "diagnostics", {}) or {}),
        **dict(getattr(result, "diagnostics_summary", {}) or {}),
    }
    issues: list[str] = []
    score = 0.0
    computational = 0.0
    rhat = _safe_float(diagnostics.get("rhat_max"))
    if rhat is not None and rhat > 1.05:
        issues.append("rhat_above_1.05")
        score = max(score, 0.7)
        computational = max(computational, 0.7)
    ess = _safe_float(diagnostics.get("ess_min") or diagnostics.get("ess_bulk_min"))
    if ess is not None and ess < 100.0:
        issues.append("ess_below_100")
        score = max(score, 0.5)
        computational = max(computational, 0.5)
    divergences = _safe_float(diagnostics.get("divergent_transitions") or diagnostics.get("divergences"))
    if divergences is not None and divergences > 0.0:
        issues.append("divergences_detected")
        score = max(score, 0.8)
        computational = max(computational, 0.8)
    return MethodDiagnostics(
        failure_score=score,
        computational_failure_score=computational,
        issues=tuple(issues),
        raw=diagnostics,
    )


def _prediction_validation(result: Any) -> ValidationSummary:
    metrics = dict(getattr(result, "metrics", {}) or {})
    calibration_score = 0.0
    if "coverage" in metrics:
        calibration_score = min(abs(float(metrics["coverage"]) - 0.95) / 0.25, 1.0)
    scoring = _clip_unit(float(metrics.get("brier_score", metrics.get("crps", 0.0)) or 0.0))
    return ValidationSummary(
        calibration_failure_score=calibration_score,
        scoring_disadvantage_score=scoring,
        raw=metrics,
    )


def _result_identifier(result: Any, index: int) -> str:
    if isinstance(result, ConsensusTarget):
        return result.result_id
    if isinstance(result, Mapping):
        return str(result.get("result_id", result.get("method_name", f"result_{index}")))
    return str(getattr(result, "method_name", f"result_{index}"))


def _clip_probability(value: float) -> float:
    if not math.isfinite(float(value)):
        return 0.0 if value < 0 else 1.0
    return min(max(float(value), 0.0), 1.0)


def _clip_unit(value: float) -> float:
    if not math.isfinite(float(value)):
        return 0.0
    return min(max(float(value), 0.0), 1.0)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


__all__ = [
    "ConsensusTarget",
    "CrossMethodConsensus",
    "EstimandSpec",
    "IntervalSummary",
    "MethodDiagnostics",
    "MethodFamily",
    "MisspecificationClassification",
    "NotComparableYet",
    "PairwiseDisagreement",
    "SupportsConsensusTarget",
    "UncertaintyContract",
    "ValidationSummary",
    "adjust_pairwise_p_values",
    "classify_misspecification",
    "compute_distributional_check",
    "compute_hausman_like_check",
    "compute_pairwise_checks",
    "compute_projection_checks",
    "consensus_target_from_mapping",
    "estimand_from_mapping",
    "estimand_from_query",
    "largest_compatible_component",
    "run_cross_method_consensus",
    "target_from_econometric_result",
    "target_from_posterior_result",
    "target_from_prediction_result",
]
