"""Interference and network causal inference methods.

Implements four estimators that relax SUTVA (Stable Unit Treatment Value
Assumption) by allowing spillover effects across units connected via a
cluster, network, spatial, or bipartite structure.

References
----------
Hudgens, M.G. & Halloran, M.E. (2008). Toward causal inference with
    interference. JASA 103(482).
Aronow, P.M. & Samii, C. (2017). Estimating average causal effects under
    general interference. Ann. Appl. Stat.
Liu, L., Hudgens, M.G. & Becker-Dreps, S. (2016). On sample randomization
    inference of causal effects in the presence of interference. JRSS-B.
Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal inference in
    the presence of interference. Stat. Methods Med. Res.
Zigler, C.M. & Papadogeorgou, G. (2021). Bipartite causal inference with
    interference. Stat. Sci.
Verbitsky-Savitz, N. & Raudenbush, S.W. (2012). Causal inference under
    interference in spatial settings. Epidemiol. Methods.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import ValidationError

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._interference_contracts import (
    InterferenceAugmentedGraph,
    InterferenceIdentificationResult,
    _ReductionErrorBoundPlan,
    _SimplicialSupportGate,
    _TopologyCertificatePlan,
)
from polisyos.foundry.methods.catalog.causal.protocols import NetworkCausalData
from polisyos.foundry.methods.catalog.network.generative_protocols import SBMStratificationResult
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InteractionComplex,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    MAUPInvarianceCertificate,
    MAUPPartitionCheck,
    NetworkInterferenceReport,
    SpatialHodgeDiagnostics,
    SpatialHodgeScaleProfile,
    SpatialResult,
)
from polisyos.ir.analytics.network_generative import BlockSupportReport, CausalBlockBridge
from polisyos.ir.registry.refs import ArtifactRefModel

_PAIRWISE_QUERY_FAMILY = "pairwise_projection_queries"
_CLUSTER_QUERY_FAMILY = "cluster_projection_queries"
_SIMPLICIAL_STAR_LOCAL_QUERY_FAMILY = "simplicial_star_local_queries"
_UNSUPPORTED_COMPLEX_QUERY_FAMILY = "unsupported_complex_queries"
_SUPPORTED_MAUP_ESTIMANDS = {"direct", "spillover", "total"}
_MAUP_POSITIVITY_BLOCK_THRESHOLD = 0.01

# ──────────────────────────────────────────────────────────────────────────────
# Shared output slots
# ──────────────────────────────────────────────────────────────────────────────

from . import identification as _identification

globals().update({name: getattr(_identification, name) for name in dir(_identification) if not name.startswith("__")})


def _fractional_exposure(treatment: np.ndarray, cluster_id: np.ndarray) -> np.ndarray:
    """Per-unit fraction of *other* cluster members who are treated.

    Hudgens & Halloran (2008) Eq. (1).
    Returns shape ``(n_units,)`` float in [0, 1].
    """
    clusters = np.unique(cluster_id)
    exposure = np.zeros(len(treatment), dtype=float)
    for c in clusters:
        mask = cluster_id == c
        indices = np.where(mask)[0]
        n_c = int(mask.sum())
        if n_c < 2:
            continue
        for pos, idx in enumerate(indices):
            total_others = float(treatment[mask].sum()) - float(treatment[idx])
            exposure[idx] = total_others / (n_c - 1)
    return exposure


def _threshold_exposure(
    treatment: np.ndarray,
    cluster_id: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Binary indicator: 1 if fractional exposure exceeds *threshold*."""
    return (_fractional_exposure(treatment, cluster_id) > threshold).astype(float)


def _network_exposure(
    treatment: np.ndarray,
    adjacency: np.ndarray,
    mapping_type: str = "fraction",
) -> np.ndarray:
    """Aronow & Samii (2017) exposure mapping via adjacency matrix.

    Parameters
    ----------
    mapping_type:
        ``"fraction"`` — mean neighbour treatment;
        ``"count"`` — number of treated neighbours;
        ``"any"`` — 1 if any neighbour is treated.
    """
    neighbor_sum = adjacency @ treatment.astype(float)
    degree = adjacency.sum(axis=1)
    if mapping_type == "fraction":
        with np.errstate(invalid="ignore", divide="ignore"):
            exp = np.where(degree > 0, neighbor_sum / degree, 0.0)
    elif mapping_type == "count":
        exp = neighbor_sum
    else:  # "any"
        exp = (neighbor_sum > 0).astype(float)
    return exp.astype(float)


def _kernel_weights(coordinates: np.ndarray, bandwidth: float) -> np.ndarray:
    """Gaussian kernel weight matrix; diagonal set to zero (no self-influence).

    W_ij = exp(−‖x_i − x_j‖² / (2h²)).
    """
    diff = coordinates[:, np.newaxis, :] - coordinates[np.newaxis, :, :]  # (n, n, d)
    sq_dist = (diff**2).sum(axis=-1)  # (n, n)
    W = np.exp(-sq_dist / (2.0 * bandwidth**2))
    np.fill_diagonal(W, 0.0)
    return W


def _auto_bandwidth(coordinates: np.ndarray) -> float:
    """Silverman rule-of-thumb bandwidth for spatial kernel."""
    n = len(coordinates)
    # Mean pairwise distance variance proxy
    sigma = float(np.std(coordinates))
    return max(sigma * (n ** (-0.2)), 1e-6)


def _logistic_propensity(
    treatment: np.ndarray,
    features: np.ndarray,
    C: float = 1.0,
) -> np.ndarray:
    """Fit logistic regression and return P(A=1|features) for each unit."""
    from sklearn.linear_model import LogisticRegression  # lazy import

    lr = LogisticRegression(max_iter=2000, solver="lbfgs", C=C)
    lr.fit(features, treatment.astype(int))
    return lr.predict_proba(features)[:, 1].astype(float)


def _sandwich_var(scores: np.ndarray) -> float:
    """Robust sandwich variance of the sample mean: Var(ȳ) = E[ψ²]/n."""
    n = len(scores)
    if n < 2:
        return float("nan")
    return float(np.mean(scores**2) - np.mean(scores) ** 2) / n


def _normal_ci(estimate: float, se: float, level: float = 0.95) -> tuple[float, float]:
    """Gaussian confidence interval."""
    z = _normal_quantile(1.0 - (1.0 - level) / 2.0)
    return float(estimate - z * se), float(estimate + z * se)


def _normal_quantile(p: float) -> float:
    """Rational approximation to the normal quantile (Beasley & Springer 1977)."""
    import math as _math

    if p <= 0.0 or p >= 1.0:
        return float("nan")
    if abs(p - 0.5) < 1e-9:
        return 0.0
    sign = 1.0 if p > 0.5 else -1.0
    q = min(p, 1.0 - p)
    r = _math.sqrt(-2.0 * _math.log(q))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    numer = c0 + c1 * r + c2 * r * r
    denom = 1.0 + d1 * r + d2 * r * r + d3 * r * r * r
    return sign * (r - numer / denom)


def _ipw_potential_outcome(
    outcome: np.ndarray,
    indicator: np.ndarray,
    propensity: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Horvitz-Thompson IPW mean of E[Y(a)] under indicator/propensity.

    Returns ``(estimate, influence_scores)`` where influence scores can be
    used for sandwich variance estimation.
    """
    ps_clipped = np.clip(propensity, 1e-6, 1.0 - 1e-6)
    scores = outcome * indicator / ps_clipped
    estimate = float(np.mean(scores))
    return estimate, scores


@dataclass(frozen=True)
class _ContrastEstimate:
    theta: float | None
    se: float | None
    ess_min: float | None
    min_positivity: float | None
    cell_counts: Mapping[str, int]
    blocker_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _dedupe_preserve_order(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _coerce_optional_artifact_ref(
    value: Any,
    *,
    field_name: str,
) -> tuple[ArtifactRefModel | None, tuple[str, ...]]:
    if value is None:
        return None, ()
    try:
        ref = (
            value if isinstance(value, ArtifactRefModel) else ArtifactRefModel.model_validate(value)
        )
    except ValidationError:
        return None, (f"{field_name}_invalid",)
    return ref, ()


def _resolve_maup_partitions(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    raw = params.get("candidate_partitions")
    if raw is None:
        raw = data.metadata.get("candidate_partitions")
    if raw is None:
        raw = data.metadata.get("partitions")
    if raw in (None, ()):
        return ()
    if not isinstance(raw, (list, tuple)):
        raise TypeError("candidate_partitions must be a list or tuple")
    partitions: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            partition = dict(item)
        else:
            partition = {"block_of_unit": item}
        partition.setdefault("partition_id", f"partition_{index}")
        partitions.append(partition)
    return tuple(partitions)


def _normalize_partition_labels(
    block_of_unit: Any,
    *,
    n_units: int,
) -> tuple[np.ndarray, tuple[str, ...]]:
    labels_raw = np.asarray(block_of_unit, dtype=object)
    if labels_raw.ndim != 1 or labels_raw.shape[0] != n_units:
        raise ValueError("block_of_unit must be a 1D array aligned with n_units")
    labels: list[str] = []
    for raw_label in labels_raw.tolist():
        if raw_label is None:
            raise ValueError("block_of_unit must not contain null labels")
        if isinstance(raw_label, (float, np.floating)) and not math.isfinite(float(raw_label)):
            raise ValueError("block_of_unit must not contain non-finite labels")
        label = str(raw_label).strip()
        if not label:
            raise ValueError("block_of_unit labels must be non-empty")
        labels.append(label)
    unique_labels, inverse = np.unique(np.asarray(labels, dtype=object), return_inverse=True)
    if unique_labels.size < 2:
        raise ValueError("candidate partition must contain at least two blocks")
    return inverse.astype(int), tuple(str(label) for label in unique_labels.tolist())


def _partition_operators(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n_units = int(labels.shape[0])
    n_blocks = int(labels.max()) + 1
    incidence = np.zeros((n_blocks, n_units), dtype=float)
    incidence[labels, np.arange(n_units)] = 1.0
    block_sizes = np.sum(incidence, axis=1, keepdims=True)
    averaging = incidence / np.clip(block_sizes, 1.0, None)
    return averaging, incidence


def _contrast_compute_lumpability_residual(
    exposure_operator: np.ndarray,
    block_of_unit: Any,
) -> tuple[float, bool, np.ndarray]:
    labels = np.asarray(block_of_unit, dtype=int)
    averaging, incidence = _partition_operators(labels)
    aggregate_operator = averaging @ exposure_operator @ incidence.T
    lhs = averaging @ exposure_operator
    rhs = aggregate_operator @ averaging
    denominator = float(np.linalg.norm(lhs, ord="fro"))
    if denominator <= 1e-12:
        return 0.0, True, aggregate_operator
    residual = float(np.linalg.norm(lhs - rhs, ord="fro") / denominator)
    return residual, residual <= 1e-12, aggregate_operator


def _cell_mean_and_var(
    values: np.ndarray, mask: np.ndarray
) -> tuple[float | None, float | None, int]:
    count = int(mask.sum())
    if count == 0:
        return None, None, 0
    sample = values[mask]
    mean = float(np.mean(sample))
    if count < 2:
        return mean, None, count
    return mean, float(np.var(sample, ddof=1)), count


def _difference_of_means(
    outcome: np.ndarray,
    *,
    left_mask: np.ndarray,
    right_mask: np.ndarray,
    left_label: str,
    right_label: str,
) -> _ContrastEstimate:
    left_mean, left_var, left_count = _cell_mean_and_var(outcome, left_mask)
    right_mean, right_var, right_count = _cell_mean_and_var(outcome, right_mask)
    cell_counts = {left_label: left_count, right_label: right_count}
    support = float(len(outcome))
    min_positivity = min(left_count, right_count) / support if support > 0 else None
    ess_min = float(min(left_count, right_count))
    warnings: list[str] = []
    blocker_codes: list[str] = []
    if left_count == 0 or right_count == 0 or left_mean is None or right_mean is None:
        blocker_codes.append("MAUP_E_POSITIVITY")
        warnings.append(f"Missing support for {left_label} or {right_label}.")
        return _ContrastEstimate(
            theta=None,
            se=None,
            ess_min=ess_min,
            min_positivity=min_positivity,
            cell_counts=cell_counts,
            blocker_codes=_dedupe_preserve_order(blocker_codes),
            warnings=_dedupe_preserve_order(warnings),
        )
    theta = left_mean - right_mean
    if left_var is None or right_var is None:
        blocker_codes.append("MAUP_E_LOW_ESS")
        warnings.append(
            f"Too few observations for a stable variance estimate in {left_label}/{right_label}."
        )
        return _ContrastEstimate(
            theta=theta,
            se=None,
            ess_min=ess_min,
            min_positivity=min_positivity,
            cell_counts=cell_counts,
            blocker_codes=_dedupe_preserve_order(blocker_codes),
            warnings=_dedupe_preserve_order(warnings),
        )
    se = math.sqrt(max(left_var / left_count + right_var / right_count, 0.0))
    return _ContrastEstimate(
        theta=theta,
        se=se,
        ess_min=ess_min,
        min_positivity=min_positivity,
        cell_counts=cell_counts,
    )


def _estimate_maup_contrast(
    outcome: np.ndarray,
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    estimand: Literal["direct", "spillover", "total"],
    alpha_high: float,
    alpha_low: float,
    treatment_threshold: float = 0.5,
) -> _ContrastEstimate:
    treated = treatment >= treatment_threshold
    control = treatment < treatment_threshold
    exposure_high = exposure >= alpha_high
    exposure_low = exposure <= alpha_low
    if estimand == "direct":
        return _difference_of_means(
            outcome,
            left_mask=treated & exposure_high,
            right_mask=control & exposure_high,
            left_label="treated_high",
            right_label="control_high",
        )
    if estimand == "spillover":
        return _difference_of_means(
            outcome,
            left_mask=control & exposure_high,
            right_mask=control & exposure_low,
            left_label="control_high",
            right_label="control_low",
        )
    return _difference_of_means(
        outcome,
        left_mask=treated & exposure_high,
        right_mask=control & exposure_low,
        left_label="treated_high",
        right_label="control_low",
    )


def _contrast_hausman_compare_partition_effects(
    theta_partition: float | None,
    se_partition: float | None,
    theta_micro: float | None,
    se_micro: float | None,
) -> tuple[float | None, float | None, str | None]:
    if theta_partition is None or theta_micro is None or se_partition is None or se_micro is None:
        return None, None, "MAUP_E_SINGULAR_COV"
    if not (
        math.isfinite(theta_partition)
        and math.isfinite(theta_micro)
        and math.isfinite(se_partition)
        and math.isfinite(se_micro)
    ):
        return None, None, "MAUP_E_SINGULAR_COV"
    variance = se_partition**2 + se_micro**2
    if variance <= 1e-12:
        return None, None, "MAUP_E_SINGULAR_COV"
    delta = theta_partition - theta_micro
    stat = (delta**2) / variance
    p_value = math.erfc(abs(delta) / math.sqrt(2.0 * variance))
    return stat, p_value, None


def _holm_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    total = len(p_values)
    for rank, (index, p_value) in enumerate(indexed, start=1):
        candidate = min((total - rank + 1) * p_value, 1.0)
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted


def _recommended_maup_mode(
    status: str,
) -> Literal[
    "micro_only",
    "micro_plus_safe_aggregate",
    "block_aggregate",
]:
    if status == "pass":
        return "micro_plus_safe_aggregate"
    if status in {"block", "not_identified"}:
        return "block_aggregate"
    return "micro_only"


def _attach_maup_certificate(
    report: NetworkInterferenceReport,
    certificate: MAUPInvarianceCertificate | None,
) -> SpatialResult:
    payload = report.model_dump()
    payload["maup_invariance_certificate"] = certificate
    return SpatialResult.model_validate(payload)


def _contrast_compute_maup_invariance_certificate(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
    *,
    exposure_operator: np.ndarray,
    exposure_vector: np.ndarray,
) -> MAUPInvarianceCertificate:
    estimand = str(params.get("estimand", "spillover")).strip().lower()
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    lump_warn = float(params.get("lumpability_warn_threshold", 0.01))
    lump_block = float(params.get("lumpability_block_threshold", 0.05))
    ess_warn = float(params.get("min_cell_ess_warn", 50))
    ess_block = float(params.get("min_cell_ess_block", 20))
    positivity_block = float(
        params.get("min_cell_positivity_block", _MAUP_POSITIVITY_BLOCK_THRESHOLD)
    )
    alpha = float(params.get("maup_alpha", 0.05))
    treatment_threshold = float(params.get("partition_treatment_threshold", 0.5))

    certificate_warnings: list[str] = list(spatial_result.warnings)
    certificate_blockers: list[str] = []
    metadata: dict[str, Any] = {
        "alpha_high": alpha_high,
        "alpha_low": alpha_low,
        "lumpability_warn_threshold": lump_warn,
        "lumpability_block_threshold": lump_block,
        "min_cell_ess_warn": ess_warn,
        "min_cell_ess_block": ess_block,
        "min_cell_positivity_block": positivity_block,
        "partition_treatment_threshold": treatment_threshold,
        "effect_source": "difference_in_means_contrast",
        "report_status": spatial_result.status,
    }

    interaction_complex_ref, ref_warnings = _coerce_optional_artifact_ref(
        params.get("interaction_complex_ref", data.metadata.get("interaction_complex_ref")),
        field_name="interaction_complex_ref",
    )
    certificate_warnings.extend(ref_warnings)
    interference_certificate_ref, cert_ref_warnings = _coerce_optional_artifact_ref(
        params.get(
            "interference_certificate_ref", data.metadata.get("interference_certificate_ref")
        ),
        field_name="interference_certificate_ref",
    )
    certificate_warnings.extend(cert_ref_warnings)

    if estimand not in _SUPPORTED_MAUP_ESTIMANDS:
        certificate_blockers.append("MAUP_E_UNSUPPORTED_EXPOSURE")
        certificate_warnings.append(f"Unsupported MAUP estimand '{estimand}'.")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand="spillover",
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if alpha_low > alpha_high:
        certificate_blockers.append("MAUP_E_UNSUPPORTED_EXPOSURE")
        certificate_warnings.append(
            "alpha_low must be less than or equal to alpha_high for MAUP certification."
        )
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if bool(
        params.get(
            "partitions_selected_post_outcome",
            data.metadata.get("partitions_selected_post_outcome", False),
        )
    ):
        certificate_blockers.append("MAUP_E_OUTCOME_LEAKAGE")
        certificate_warnings.append("Candidate partitions were flagged as post-outcome selections.")
        return MAUPInvarianceCertificate(
            status="block",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("block"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    try:
        partitions = _resolve_maup_partitions(data, params)
    except (TypeError, ValueError) as exc:
        certificate_blockers.append("MAUP_E_BAD_PARTITION")
        certificate_warnings.append(str(exc))
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if not partitions:
        certificate_warnings.append(
            "No candidate partitions were provided; MAUP certificate not tested."
        )
        return MAUPInvarianceCertificate(
            status="not_tested",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_tested"),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    micro_estimate = _estimate_maup_contrast(
        data.outcome.astype(float),
        data.treatment.astype(float),
        exposure_vector.astype(float),
        estimand=estimand,  # type: ignore[arg-type]
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        treatment_threshold=0.5,
    )
    metadata["micro_cell_counts"] = dict(micro_estimate.cell_counts)

    if micro_estimate.theta is None or micro_estimate.se is None:
        certificate_blockers.extend(micro_estimate.blocker_codes)
        certificate_blockers.append("MAUP_E_UNIDENTIFIED")
        certificate_warnings.extend(micro_estimate.warnings)
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            micro_effect=micro_estimate.theta,
            micro_se=micro_estimate.se,
            partitions_tested=0,
            min_positivity=micro_estimate.min_positivity,
            min_ess=micro_estimate.ess_min,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    checks: list[MAUPPartitionCheck] = []
    invalid_partitions: list[str] = []
    min_ess_candidates: list[float] = [
        micro_estimate.ess_min if micro_estimate.ess_min is not None else float("inf")
    ]
    min_pos_candidates: list[float] = [
        micro_estimate.min_positivity if micro_estimate.min_positivity is not None else 1.0
    ]

    for index, partition in enumerate(partitions):
        partition_id = (
            str(partition.get("partition_id", f"partition_{index}")).strip() or f"partition_{index}"
        )
        try:
            labels, unique_labels = _normalize_partition_labels(
                partition.get("block_of_unit"),
                n_units=data.n_units,
            )
        except ValueError:
            invalid_partitions.append(partition_id)
            certificate_blockers.append("MAUP_E_BAD_PARTITION")
            continue

        residual, exact_lumpable, aggregate_operator = _contrast_compute_lumpability_residual(
            exposure_operator,
            labels,
        )
        averaging, _ = _partition_operators(labels)
        outcome_partition = averaging @ data.outcome.astype(float)
        treatment_partition = averaging @ data.treatment.astype(float)
        exposure_partition = aggregate_operator @ treatment_partition
        partition_estimate = _estimate_maup_contrast(
            outcome_partition,
            treatment_partition,
            exposure_partition,
            estimand=estimand,  # type: ignore[arg-type]
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            treatment_threshold=treatment_threshold,
        )
        hausman_stat, p_value, hausman_code = _contrast_hausman_compare_partition_effects(
            partition_estimate.theta,
            partition_estimate.se,
            micro_estimate.theta,
            micro_estimate.se,
        )

        partition_blockers = list(partition_estimate.blocker_codes)
        partition_warnings = list(partition_estimate.warnings)
        if residual >= lump_block:
            partition_blockers.append("MAUP_E_STRUCTURAL_NONINVARIANCE")
        elif residual >= lump_warn:
            partition_warnings.append("lumpability_residual_warn")
        if partition_estimate.ess_min is not None:
            min_ess_candidates.append(partition_estimate.ess_min)
            if partition_estimate.ess_min < ess_block:
                partition_blockers.append("MAUP_E_LOW_ESS")
            elif partition_estimate.ess_min < ess_warn:
                partition_warnings.append("partition_low_ess_warn")
        if partition_estimate.min_positivity is not None:
            min_pos_candidates.append(partition_estimate.min_positivity)
            if partition_estimate.min_positivity < positivity_block:
                partition_blockers.append("MAUP_E_POSITIVITY")
        if hausman_code is not None:
            partition_blockers.append(hausman_code)

        checks.append(
            MAUPPartitionCheck(
                partition_id=partition_id,
                n_blocks=len(unique_labels),
                scale_label=partition.get("scale_label"),
                zoning_label=partition.get("zoning_label"),
                lumpability_residual=residual,
                exact_lumpable=exact_lumpable,
                theta_partition=partition_estimate.theta,
                se_partition=partition_estimate.se,
                hausman_stat=hausman_stat,
                p_value=p_value,
                ess_min=partition_estimate.ess_min,
                blocker_codes=_dedupe_preserve_order(partition_blockers),
                warnings=_dedupe_preserve_order(partition_warnings),
            )
        )

    if invalid_partitions:
        certificate_warnings.append(f"Skipped invalid partitions: {', '.join(invalid_partitions)}.")
        metadata["invalid_partitions"] = tuple(invalid_partitions)

    if not checks:
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,  # type: ignore[arg-type]
            effect_scale="mean_difference",
            micro_effect=micro_estimate.theta,
            micro_se=micro_estimate.se,
            partitions_tested=0,
            min_positivity=min(min_pos_candidates),
            min_ess=min(min_ess_candidates),
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers or ["MAUP_E_BAD_PARTITION"]),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    indexed_p_values = [idx for idx, check in enumerate(checks) if check.p_value is not None]
    adjusted_p_values = _holm_adjust([float(checks[idx].p_value) for idx in indexed_p_values])
    for idx, adjusted_p in zip(indexed_p_values, adjusted_p_values, strict=True):
        check = checks[idx]
        updated_blockers = list(check.blocker_codes)
        if adjusted_p < alpha:
            updated_blockers.append("MAUP_E_STATISTICAL_NONINVARIANCE")
        checks[idx] = check.model_copy(
            update={
                "adjusted_p_value": adjusted_p,
                "blocker_codes": _dedupe_preserve_order(updated_blockers),
            }
        )

    all_check_blockers = [code for check in checks for code in check.blocker_codes]
    all_check_warnings = [warning for check in checks for warning in check.warnings]
    certificate_blockers.extend(all_check_blockers)
    certificate_warnings.extend(all_check_warnings)

    max_residual = max(
        check.lumpability_residual for check in checks if check.lumpability_residual is not None
    )
    adjusted_p_candidates = [
        check.adjusted_p_value for check in checks if check.adjusted_p_value is not None
    ]
    min_adjusted_p = min(adjusted_p_candidates) if adjusted_p_candidates else None

    hard_block_codes = {
        "MAUP_E_OUTCOME_LEAKAGE",
        "MAUP_E_STRUCTURAL_NONINVARIANCE",
        "MAUP_E_STATISTICAL_NONINVARIANCE",
        "MAUP_E_POSITIVITY",
        "MAUP_E_LOW_ESS",
        "MAUP_E_UNIDENTIFIED",
        "MAUP_E_SINGULAR_COV",
        "MAUP_E_BAD_PARTITION",
    }
    has_hard_block = any(code in hard_block_codes for code in certificate_blockers)
    if has_hard_block:
        status = "block"
    elif certificate_warnings:
        status = "warn"
    else:
        status = "pass"

    exact_invariance = (
        status == "pass"
        and all(check.exact_lumpable is True for check in checks)
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
    )
    near_invariance = (
        status in {"pass", "warn"}
        and max_residual < lump_block
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
    )

    return MAUPInvarianceCertificate(
        status=status,  # type: ignore[arg-type]
        estimand=estimand,  # type: ignore[arg-type]
        effect_scale="mean_difference",
        micro_effect=micro_estimate.theta,
        micro_se=micro_estimate.se,
        partitions_tested=len(checks),
        max_lumpability_residual=max_residual,
        min_adjusted_p_value=min_adjusted_p,
        min_positivity=min(min_pos_candidates),
        min_ess=min(min_ess_candidates),
        exact_invariance=exact_invariance,
        near_invariance=near_invariance,
        recommended_mode=_recommended_maup_mode(status),
        partition_checks=tuple(checks),
        blocker_codes=_dedupe_preserve_order(certificate_blockers),
        warnings=_dedupe_preserve_order(certificate_warnings),
        interaction_complex_ref=interaction_complex_ref,
        interference_certificate_ref=interference_certificate_ref,
        metadata=metadata,
    )


def _build_report_failure(
    method: InterferenceMethod,
    exposure_mapping: ExposureMappingType,
    n_units: int,
    n_treated: int,
    reason: str,
    status: str = "input_invalid",
) -> NetworkInterferenceReport:
    return NetworkInterferenceReport(
        method=method,
        status=status,  # type: ignore[arg-type]
        status_reason=reason,
        exposure_mapping=exposure_mapping,
        n_units=n_units,
        n_treated=n_treated,
        warnings=[reason],
    )


def _build_report_success(
    method: InterferenceMethod,
    exposure_mapping: ExposureMappingType,
    de: float,
    se_val: float,
    te: float,
    se_de: float,
    se_se: float,
    se_te: float,
    n_units: int,
    n_treated: int,
    confidence_level: float,
    n_clusters: int | None = None,
    avg_cluster_size: float | None = None,
    alpha_high: float = 0.5,
    alpha_low: float = 0.0,
    exposure_params: dict[str, Any] | None = None,
    assumptions: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> NetworkInterferenceReport:
    ci_de = _normal_ci(de, se_de, confidence_level) if math.isfinite(se_de) and se_de > 0 else None
    ci_se = (
        _normal_ci(se_val, se_se, confidence_level) if math.isfinite(se_se) and se_se > 0 else None
    )
    ci_te = _normal_ci(te, se_te, confidence_level) if math.isfinite(se_te) and se_te > 0 else None

    # Interference detected: spillover SE different from 0 at 5%
    interference_detected = False
    if ci_se is not None and not (ci_se[0] <= 0.0 <= ci_se[1]):
        interference_detected = True
    elif math.isfinite(se_se) and se_se > 0:
        z = abs(se_val) / se_se
        interference_detected = z > 1.96

    effects = InterferenceEffectDecomposition(
        direct_effect=de,
        spillover_effect=se_val,
        total_effect=te,
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        se_direct=se_de if math.isfinite(se_de) else None,
        se_spillover=se_se if math.isfinite(se_se) else None,
        se_total=se_te if math.isfinite(se_te) else None,
        ci_direct=ci_de,
        ci_spillover=ci_se,
        ci_total=ci_te,
        n_units=n_units,
        n_treated=n_treated,
        confidence_level=confidence_level,
        interference_detected=interference_detected,
    )
    return NetworkInterferenceReport(
        method=method,
        status="success",
        effects=effects,
        exposure_mapping=exposure_mapping,
        exposure_mapping_params=exposure_params or {},
        n_units=n_units,
        n_treated=n_treated,
        n_clusters=n_clusters,
        average_cluster_size=avg_cluster_size,
        assumptions=assumptions or {},
        warnings=warnings or [],
    )


# ──────────────────────────────────────────────────────────────────────────────
# MAUP invariance helpers
# ──────────────────────────────────────────────────────────────────────────────


def _row_standardize_matrix(weights: np.ndarray) -> np.ndarray:
    matrix = np.asarray(weights, dtype=float).copy()
    if matrix.ndim != 2:
        raise ValueError("weights must be a 2D matrix")
    np.fill_diagonal(matrix, 0.0)
    row_sums = np.sum(matrix, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return matrix / row_sums


def _resolve_maup_estimand(
    params: Mapping[str, Any],
) -> Literal[
    "direct",
    "spillover",
    "total",
    "dose_response",
    "policy_effect",
]:
    candidate = str(params.get("estimand", "spillover")).strip().lower()
    if candidate in {"direct", "spillover", "total", "dose_response", "policy_effect"}:
        return candidate  # type: ignore[return-value]
    return "spillover"


def _resolve_maup_effect_scale(
    params: Mapping[str, Any],
) -> Literal[
    "risk_difference",
    "mean_difference",
    "log_rr",
    "custom",
]:
    candidate = str(params.get("effect_scale", "mean_difference")).strip().lower()
    if candidate in {"risk_difference", "mean_difference", "log_rr", "custom"}:
        return candidate  # type: ignore[return-value]
    return "custom"


def _resolve_spatial_weights_for_maup(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
) -> tuple[np.ndarray | None, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if data.adjacency_matrix is not None:
        metadata["weight_source"] = "adjacency_matrix"
        return _row_standardize_matrix(np.asarray(data.adjacency_matrix, dtype=float)), metadata

    if data.coordinates is None:
        return None, metadata

    coords = np.asarray(data.coordinates[:, :2], dtype=float)
    bandwidth_param = params.get(
        "maup_bandwidth",
        spatial_result.exposure_mapping_params.get("bandwidth", params.get("bandwidth", "auto")),
    )
    if bandwidth_param == "auto":
        bandwidth = _auto_bandwidth(coords)
    else:
        try:
            bandwidth = float(bandwidth_param)
        except (TypeError, ValueError):
            bandwidth = _auto_bandwidth(coords)
    if not math.isfinite(bandwidth) or bandwidth <= 0.0:
        return None, metadata
    metadata["weight_source"] = "coordinates_kernel"
    metadata["bandwidth"] = bandwidth
    return _row_standardize_matrix(_kernel_weights(coords, bandwidth)), metadata


def _resolve_probe_covariates(
    covariates: np.ndarray | None,
    *,
    max_features: int,
) -> tuple[np.ndarray | None, tuple[str, ...]]:
    if covariates is None:
        return None, ()
    array = np.asarray(covariates, dtype=float)
    if array.ndim != 2 or array.shape[0] == 0:
        return None, ("maup_probe_covariates_invalid",)
    if max_features <= 0:
        return None, ()
    if array.shape[1] <= max_features:
        return array, ()
    return array[:, :max_features], ("maup_probe_covariates_truncated",)


def _linear_effect_probe(
    outcome: np.ndarray,
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    estimand: Literal["direct", "spillover", "total", "dose_response", "policy_effect"],
    covariates: np.ndarray | None = None,
    weights: np.ndarray | None = None,
) -> tuple[float | None, float | None]:
    y = np.asarray(outcome, dtype=float)
    a = np.asarray(treatment, dtype=float)
    e = np.asarray(exposure, dtype=float)
    X = np.column_stack([np.ones(y.shape[0], dtype=float), a, e])
    if covariates is not None:
        X = np.column_stack([X, np.asarray(covariates, dtype=float)])

    w = np.ones(y.shape[0], dtype=float) if weights is None else np.asarray(weights, dtype=float)
    finite_mask = np.isfinite(y) & np.isfinite(a) & np.isfinite(e) & np.isfinite(w) & (w > 0.0)
    if covariates is not None:
        finite_mask &= np.isfinite(np.asarray(covariates, dtype=float)).all(axis=1)
    if finite_mask.sum() <= X.shape[1]:
        return None, None

    y = y[finite_mask]
    X = X[finite_mask]
    w = w[finite_mask]
    if np.linalg.matrix_rank(X) < 3:
        return None, None

    sqrt_w = np.sqrt(w)
    Xw = X * sqrt_w[:, None]
    yw = y * sqrt_w
    xtx = Xw.T @ Xw
    xtx_inv = np.linalg.pinv(xtx)
    beta = xtx_inv @ (Xw.T @ yw)
    resid = y - X @ beta
    rw = resid * sqrt_w
    meat = Xw.T @ ((rw[:, None] ** 2) * Xw)
    scale = y.shape[0] / max(y.shape[0] - X.shape[1], 1)
    cov = xtx_inv @ meat @ xtx_inv * scale

    if estimand == "direct":
        effect = float(beta[1])
        variance = float(cov[1, 1])
    elif estimand in {"spillover", "dose_response"}:
        effect = float(beta[2])
        variance = float(cov[2, 2])
    else:
        effect = float(beta[1] + beta[2])
        variance = float(cov[1, 1] + cov[2, 2] + 2.0 * cov[1, 2])
    variance = max(variance, 0.0)
    return effect, math.sqrt(variance)


def _support_metrics(
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    estimand: Literal["direct", "spillover", "total", "dose_response", "policy_effect"],
    alpha_high: float,
    alpha_low: float,
    treatment_threshold: float,
) -> tuple[float | None, float | None]:
    n_obs = len(treatment)
    if n_obs == 0:
        return None, None
    high = np.asarray(exposure, dtype=float) >= alpha_high
    low = np.asarray(exposure, dtype=float) <= alpha_low
    treated = np.asarray(treatment, dtype=float) >= treatment_threshold
    control = np.asarray(treatment, dtype=float) <= (1.0 - treatment_threshold)
    if estimand == "direct":
        fractions = [float(np.mean(treated & high)), float(np.mean(control & high))]
    elif estimand in {"total", "policy_effect"}:
        fractions = [float(np.mean(treated & high)), float(np.mean(control & low))]
    else:
        fractions = [float(np.mean(high)), float(np.mean(low))]
    positivity = min(fractions) if fractions else None
    ess = None if positivity is None else float(n_obs * positivity)
    return positivity, ess


def _coerce_candidate_partition(
    raw_partition: Any,
    *,
    index: int,
    n_units: int,
) -> tuple[str, str | None, str | None, np.ndarray]:
    if isinstance(raw_partition, Mapping):
        partition_id = str(
            raw_partition.get("partition_id") or raw_partition.get("id") or f"partition_{index}"
        ).strip()
        scale_label = (
            None
            if raw_partition.get("scale_label") is None
            else str(raw_partition.get("scale_label")).strip()
        )
        zoning_label = (
            None
            if raw_partition.get("zoning_label") is None
            else str(raw_partition.get("zoning_label")).strip()
        )
        labels_raw = raw_partition.get("block_of_unit")
    else:
        partition_id = f"partition_{index}"
        scale_label = None
        zoning_label = None
        labels_raw = raw_partition
    if not partition_id:
        raise ValueError("partition_id must be non-empty")
    labels = np.asarray(labels_raw, dtype=int)
    if labels.ndim != 1 or labels.shape[0] != n_units:
        raise ValueError("block_of_unit must be a 1D array aligned to n_units")
    if np.unique(labels).size < 2:
        raise ValueError("partition must contain at least two non-empty blocks")
    return partition_id, scale_label, zoning_label, labels


def _make_averaging_operator(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    unique_labels, inverse = np.unique(labels, return_inverse=True)
    counts = np.bincount(inverse).astype(float)
    n_blocks = int(unique_labels.size)
    n_units = int(labels.shape[0])
    M = np.zeros((n_blocks, n_units), dtype=float)
    C = np.zeros((n_units, n_blocks), dtype=float)
    for unit_idx, block_idx in enumerate(inverse):
        M[block_idx, unit_idx] = 1.0 / counts[block_idx]
        C[unit_idx, block_idx] = 1.0
    return M, C, counts


def _aggregate_weight_matrix(M: np.ndarray, W: np.ndarray, C: np.ndarray) -> np.ndarray:
    return _row_standardize_matrix(M @ W @ C)


def compute_lumpability_residual(M: np.ndarray, W: np.ndarray, Wq: np.ndarray) -> float:
    left = M @ W
    denom = float(np.linalg.norm(left))
    if denom <= 1.0e-12:
        return 0.0
    return float(np.linalg.norm(left - (Wq @ M)) / denom)


def hausman_compare_partition_effects(
    theta_micro: float | None,
    se_micro: float | None,
    theta_partition: float | None,
    se_partition: float | None,
) -> tuple[float | None, float | None]:
    if theta_micro is None or se_micro is None or theta_partition is None or se_partition is None:
        return None, None
    if not all(
        math.isfinite(value) for value in (theta_micro, se_micro, theta_partition, se_partition)
    ):
        return None, None
    variance = se_micro**2 + se_partition**2
    if variance <= 0.0:
        return None, None
    statistic = (theta_partition - theta_micro) ** 2 / variance
    p_value = math.erfc(math.sqrt(statistic / 2.0))
    return float(statistic), float(p_value)


def _holm_adjust(p_values: list[float | None]) -> list[float | None]:
    adjusted: list[float | None] = [None] * len(p_values)
    ranked = sorted(
        (float(p_value), index)
        for index, p_value in enumerate(p_values)
        if p_value is not None and math.isfinite(p_value)
    )
    m = len(ranked)
    running_max = 0.0
    for rank, (p_value, index) in enumerate(ranked, start=1):
        candidate = min(1.0, (m - rank + 1) * p_value)
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return adjusted


def _flatten_unique_codes(
    sequences: list[tuple[str, ...]] | tuple[tuple[str, ...], ...],
) -> tuple[str, ...]:
    flattened: list[str] = []
    seen: set[str] = set()
    for sequence in sequences:
        for code in sequence:
            if code in seen:
                continue
            seen.add(code)
            flattened.append(code)
    return tuple(flattened)


def compute_maup_invariance_certificate(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
) -> MAUPInvarianceCertificate:
    estimand = _resolve_maup_estimand(params)
    effect_scale = _resolve_maup_effect_scale(params)
    alpha = float(params.get("maup_alpha", 0.05))
    lumpability_warn = float(params.get("lumpability_warn_threshold", 0.01))
    lumpability_block = float(params.get("lumpability_block_threshold", 0.05))
    ess_warn = float(params.get("min_cell_ess_warn", 50.0))
    ess_block = float(params.get("min_cell_ess_block", 20.0))
    positivity_block = float(
        params.get("min_cell_positivity_block", _MAUP_POSITIVITY_BLOCK_THRESHOLD)
    )

    certificate_warnings: list[str] = list(spatial_result.warnings)
    certificate_blockers: list[str] = []
    metadata: dict[str, Any] = {
        "report_status": spatial_result.status,
        "effect_scale": effect_scale,
        "effect_source": "weighted_linear_probe",
        "lumpability_warn_threshold": lumpability_warn,
        "lumpability_block_threshold": lumpability_block,
        "min_cell_ess_warn": ess_warn,
        "min_cell_ess_block": ess_block,
        "min_cell_positivity_block": positivity_block,
    }

    interaction_complex_ref, ref_warnings = _coerce_optional_artifact_ref(
        params.get("interaction_complex_ref", data.metadata.get("interaction_complex_ref")),
        field_name="interaction_complex_ref",
    )
    certificate_warnings.extend(ref_warnings)
    interference_certificate_ref, cert_ref_warnings = _coerce_optional_artifact_ref(
        params.get(
            "interference_certificate_ref",
            data.metadata.get("interference_certificate_ref"),
        ),
        field_name="interference_certificate_ref",
    )
    certificate_warnings.extend(cert_ref_warnings)

    if estimand not in _SUPPORTED_MAUP_ESTIMANDS:
        certificate_blockers.append("MAUP_E_UNSUPPORTED_EXPOSURE")
        certificate_warnings.append(f"Unsupported MAUP estimand '{estimand}'.")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if bool(
        params.get(
            "partitions_selected_post_outcome",
            data.metadata.get("partitions_selected_post_outcome", False),
        )
    ):
        certificate_blockers.append("MAUP_E_OUTCOME_LEAKAGE")
        certificate_warnings.append("Candidate partitions were flagged as post-outcome selections.")
        return MAUPInvarianceCertificate(
            status="block",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("block"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    try:
        candidate_partitions = _resolve_maup_partitions(data, params)
    except (TypeError, ValueError) as exc:
        certificate_blockers.append("MAUP_E_BAD_PARTITION")
        certificate_warnings.append(str(exc))
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    if not candidate_partitions:
        certificate_warnings.append("candidate_partitions_missing")
        return MAUPInvarianceCertificate(
            status="not_tested",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_tested"),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    W, weight_metadata = _resolve_spatial_weights_for_maup(data, spatial_result, params)
    metadata["weight_metadata"] = weight_metadata
    if W is None:
        certificate_blockers.append("MAUP_E_NO_MICRODATA")
        certificate_warnings.append("spatial_weights_unavailable")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            partitions_tested=0,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    max_covariates = max(0, int(params.get("maup_probe_max_covariates", 3)))
    probe_covariates, probe_warnings = _resolve_probe_covariates(
        data.covariates,
        max_features=max_covariates,
    )
    certificate_warnings.extend(probe_warnings)
    Y = np.asarray(data.outcome, dtype=float)
    A = np.asarray(data.treatment, dtype=float)
    exposure = W @ A
    metadata["max_probe_covariates"] = max_covariates
    micro_effect, micro_se = _linear_effect_probe(
        Y,
        A,
        exposure,
        estimand=estimand,
        covariates=probe_covariates,
    )
    alpha_high = float(
        spatial_result.effects.alpha_high
        if spatial_result.effects is not None
        else params.get("alpha_high", 0.5)
    )
    alpha_low = float(
        spatial_result.effects.alpha_low
        if spatial_result.effects is not None
        else params.get("alpha_low", 0.0)
    )
    treatment_threshold = float(params.get("treatment_threshold", 0.5))
    micro_positivity, micro_ess = _support_metrics(
        A,
        exposure,
        estimand=estimand,
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        treatment_threshold=treatment_threshold,
    )
    metadata["micro_positivity"] = micro_positivity
    metadata["micro_ess"] = micro_ess

    if micro_positivity is not None and micro_positivity < positivity_block:
        certificate_blockers.append("MAUP_E_POSITIVITY")
    if micro_ess is not None and micro_ess < ess_block:
        certificate_blockers.append("MAUP_E_LOW_ESS")
    elif micro_ess is not None and micro_ess < ess_warn:
        certificate_warnings.append("micro_ess_warn")

    if micro_effect is None or micro_se is None:
        certificate_blockers.append("MAUP_E_UNIDENTIFIED")
        return MAUPInvarianceCertificate(
            status="not_identified",
            estimand=estimand,
            effect_scale=effect_scale,
            micro_effect=micro_effect,
            micro_se=micro_se,
            partitions_tested=0,
            min_positivity=micro_positivity,
            min_ess=micro_ess,
            recommended_mode=_recommended_maup_mode("not_identified"),
            blocker_codes=_dedupe_preserve_order(certificate_blockers),
            warnings=_dedupe_preserve_order(certificate_warnings),
            interaction_complex_ref=interaction_complex_ref,
            interference_certificate_ref=interference_certificate_ref,
            metadata=metadata,
        )

    raw_checks: list[MAUPPartitionCheck] = []
    partition_positivities: list[float] = []
    p_values: list[float | None] = []
    for index, raw_partition in enumerate(candidate_partitions):
        try:
            partition = (
                dict(raw_partition)
                if isinstance(raw_partition, Mapping)
                else {"block_of_unit": raw_partition}
            )
            partition_id = (
                str(partition.get("partition_id", f"partition_{index}")).strip()
                or f"partition_{index}"
            )
            scale_label = (
                None if partition.get("scale_label") is None else str(partition.get("scale_label"))
            )
            zoning_label = (
                None
                if partition.get("zoning_label") is None
                else str(partition.get("zoning_label"))
            )
            labels, unique_labels = _normalize_partition_labels(
                partition.get("block_of_unit"),
                n_units=data.n_units,
            )
        except ValueError as exc:
            raw_checks.append(
                MAUPPartitionCheck(
                    partition_id=f"partition_{index}",
                    n_blocks=0,
                    lumpability_residual=None,
                    exact_lumpable=None,
                    blocker_codes=("MAUP_E_BAD_PARTITION",),
                    warnings=(str(exc),),
                )
            )
            p_values.append(None)
            continue

        M, incidence = _partition_operators(labels)
        counts = np.sum(incidence, axis=1).astype(float)
        Wq = _aggregate_weight_matrix(M, W, incidence.T)
        residual = compute_lumpability_residual(M, W, Wq)
        Y_block = M @ Y
        A_block = M @ A
        exposure_block = Wq @ A_block
        cov_block = None if probe_covariates is None else M @ probe_covariates
        theta_partition, se_partition = _linear_effect_probe(
            Y_block,
            A_block,
            exposure_block,
            estimand=estimand,
            covariates=cov_block,
            weights=counts,
        )
        hausman_stat, p_value = hausman_compare_partition_effects(
            micro_effect,
            micro_se,
            theta_partition,
            se_partition,
        )
        positivity, ess = _support_metrics(
            A_block,
            exposure_block,
            estimand=estimand,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            treatment_threshold=treatment_threshold,
        )
        partition_blockers: list[str] = []
        partition_warnings: list[str] = []
        if residual >= lumpability_block:
            partition_blockers.append("MAUP_E_STRUCTURAL_NONINVARIANCE")
        elif residual >= lumpability_warn:
            partition_warnings.append("lumpability_residual_warn")
        if theta_partition is None or se_partition is None:
            partition_blockers.append("MAUP_E_UNIDENTIFIED")
        if p_value is None and theta_partition is not None:
            partition_blockers.append("MAUP_E_SINGULAR_COV")
        if positivity is not None and positivity < positivity_block:
            partition_blockers.append("MAUP_E_POSITIVITY")
        if ess is not None and ess < ess_block:
            partition_blockers.append("MAUP_E_LOW_ESS")
        elif ess is not None and ess < ess_warn:
            partition_warnings.append("ess_warn")
        if positivity is not None:
            partition_positivities.append(float(positivity))

        raw_checks.append(
            MAUPPartitionCheck(
                partition_id=partition_id,
                n_blocks=len(unique_labels),
                scale_label=scale_label,
                zoning_label=zoning_label,
                lumpability_residual=residual,
                exact_lumpable=residual <= 1.0e-12,
                theta_partition=theta_partition,
                se_partition=se_partition,
                hausman_stat=hausman_stat,
                p_value=p_value,
                ess_min=ess,
                blocker_codes=tuple(partition_blockers),
                warnings=tuple(partition_warnings),
            )
        )
        p_values.append(p_value)

    adjusted_p_values = _holm_adjust(p_values)
    checks: list[MAUPPartitionCheck] = []
    for check, adjusted_p_value in zip(raw_checks, adjusted_p_values, strict=True):
        blocker_codes = list(check.blocker_codes)
        warnings = list(check.warnings)
        if adjusted_p_value is not None and adjusted_p_value < alpha:
            blocker_codes.append("MAUP_E_STATISTICAL_NONINVARIANCE")
        checks.append(
            check.model_copy(
                update={
                    "adjusted_p_value": adjusted_p_value,
                    "blocker_codes": _flatten_unique_codes((tuple(blocker_codes),)),
                    "warnings": _flatten_unique_codes((tuple(warnings),)),
                }
            )
        )

    max_residual = max(
        (check.lumpability_residual for check in checks if check.lumpability_residual is not None),
        default=None,
    )
    min_adjusted_p = min(
        (check.adjusted_p_value for check in checks if check.adjusted_p_value is not None),
        default=None,
    )
    min_ess = min((check.ess_min for check in checks if check.ess_min is not None), default=None)

    report_effect_reference = None
    if spatial_result.effects is not None:
        if estimand == "direct":
            report_effect_reference = spatial_result.effects.direct_effect
        elif estimand in {"spillover", "dose_response"}:
            report_effect_reference = spatial_result.effects.spillover_effect
        else:
            report_effect_reference = spatial_result.effects.total_effect

    metadata["report_effect_reference"] = report_effect_reference

    positivity_values: list[float] = []
    if micro_positivity is not None:
        positivity_values.append(float(micro_positivity))
    positivity_values.extend(partition_positivities)
    min_positivity = min(positivity_values) if positivity_values else None
    if micro_ess is not None:
        min_ess = micro_ess if min_ess is None else min(min_ess, micro_ess)

    blocker_codes = _flatten_unique_codes(
        (tuple(certificate_blockers),) + tuple(check.blocker_codes for check in checks)
    )
    warnings = _flatten_unique_codes(
        (tuple(certificate_warnings),) + tuple(check.warnings for check in checks)
    )

    hard_block_codes = {
        "MAUP_E_OUTCOME_LEAKAGE",
        "MAUP_E_STRUCTURAL_NONINVARIANCE",
        "MAUP_E_STATISTICAL_NONINVARIANCE",
        "MAUP_E_POSITIVITY",
        "MAUP_E_LOW_ESS",
        "MAUP_E_SINGULAR_COV",
        "MAUP_E_BAD_PARTITION",
    }
    status: Literal["pass", "warn", "block", "not_tested", "not_identified"]
    if any(code in hard_block_codes for code in blocker_codes):
        status = "block"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    exact_invariance = (
        status == "pass"
        and len(checks) > 0
        and all(check.exact_lumpable is True for check in checks)
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
    )
    near_invariance = (
        status in {"pass", "warn"}
        and len(checks) > 0
        and (max_residual is None or max_residual < lumpability_block)
        and (min_adjusted_p is None or min_adjusted_p >= alpha)
        and (min_ess is None or min_ess >= ess_block)
        and (min_positivity is None or min_positivity >= positivity_block)
    )

    return MAUPInvarianceCertificate(
        status=status,
        estimand=estimand,
        effect_scale=effect_scale,
        micro_effect=micro_effect,
        micro_se=micro_se,
        partitions_tested=len(checks),
        max_lumpability_residual=max_residual,
        min_adjusted_p_value=min_adjusted_p,
        min_positivity=min_positivity,
        min_ess=min_ess,
        exact_invariance=exact_invariance,
        near_invariance=near_invariance or exact_invariance,
        recommended_mode=_recommended_maup_mode(status),
        partition_checks=tuple(checks),
        blocker_codes=blocker_codes,
        warnings=warnings,
        interaction_complex_ref=interaction_complex_ref,
        interference_certificate_ref=interference_certificate_ref,
        metadata=metadata,
    )


_SUPPORTED_HODGE_AGGREGATION_RULES = {
    "mean",
    "sum",
    "rate",
    "population_weighted_mean",
}


def _normalize_hodge_aggregation_rule(rule: Any) -> str:
    candidate = str(rule or "mean").strip().lower()
    aliases = {
        "avg": "mean",
        "average": "mean",
        "weighted_mean": "population_weighted_mean",
        "population-weighted-mean": "population_weighted_mean",
        "population weighted mean": "population_weighted_mean",
    }
    normalized = aliases.get(candidate, candidate)
    if normalized not in _SUPPORTED_HODGE_AGGREGATION_RULES:
        return "mean"
    return normalized


def _stable_payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.blake2b(encoded, digest_size=16).hexdigest()


def _hash_float_array(values: np.ndarray) -> str:
    array = np.asarray(values)
    if array.dtype.kind in {"f", "c"}:
        array = np.round(array.astype(float), 8)
    return hashlib.blake2b(array.tobytes(), digest_size=16).hexdigest()


def _resolve_weight_spec_label(
    spatial_result: NetworkInterferenceReport,
    weight_metadata: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    suffix: str | None = None,
) -> str:
    candidate = (
        str(params.get("weight_spec", "")).strip()
        or str(weight_metadata.get("weight_spec", "")).strip()
        or str(weight_metadata.get("weight_source", "")).strip()
        or spatial_result.exposure_mapping.value
    )
    if suffix:
        return f"{candidate}:{suffix}"
    return candidate


def _aggregate_partition_array(
    values: np.ndarray | None,
    labels: np.ndarray,
    *,
    rule: str,
    unit_weights: np.ndarray | None = None,
) -> np.ndarray | None:
    if values is None:
        return None
    array = np.asarray(values, dtype=float)
    inverse = np.asarray(labels, dtype=int)
    if array.ndim not in {1, 2}:
        raise ValueError("values must be a 1D or 2D array for partition aggregation")
    n_blocks = int(np.max(inverse)) + 1
    if unit_weights is None:
        weights = np.ones(inverse.shape[0], dtype=float)
    else:
        weights = np.asarray(unit_weights, dtype=float)
        if weights.shape != inverse.shape:
            raise ValueError("unit_weights must align with labels")
        if not np.isfinite(weights).all():
            raise ValueError("unit_weights must be finite")
    normalized_rule = _normalize_hodge_aggregation_rule(rule)

    if array.ndim == 1:
        weighted_values = (
            array * weights if normalized_rule == "population_weighted_mean" else array
        )
        totals = np.bincount(inverse, weights=weighted_values, minlength=n_blocks).astype(float)
        if normalized_rule == "sum":
            return totals
        block_weights = np.bincount(inverse, weights=weights, minlength=n_blocks).astype(float)
        if normalized_rule in {"mean", "rate"}:
            block_weights = np.bincount(inverse, minlength=n_blocks).astype(float)
        block_weights = np.clip(block_weights, 1.0, None)
        return totals / block_weights

    totals = np.zeros((n_blocks, array.shape[1]), dtype=float)
    for feature_idx in range(array.shape[1]):
        column = (
            array[:, feature_idx] * weights
            if normalized_rule == "population_weighted_mean"
            else array[:, feature_idx]
        )
        totals[:, feature_idx] = np.bincount(
            inverse,
            weights=column,
            minlength=n_blocks,
        ).astype(float)
    if normalized_rule == "sum":
        return totals
    block_weights = np.bincount(inverse, weights=weights, minlength=n_blocks).astype(float)
    if normalized_rule in {"mean", "rate"}:
        block_weights = np.bincount(inverse, minlength=n_blocks).astype(float)
    block_weights = np.clip(block_weights, 1.0, None)
    return totals / block_weights[:, None]


def _dominant_hodge_component(
    eta_grad: float,
    eta_curl: float,
    eta_harm: float,
) -> Literal["grad", "curl", "harm", "mixed"]:
    components = {
        "grad": float(eta_grad),
        "curl": float(eta_curl),
        "harm": float(eta_harm),
    }
    winner, value = max(components.items(), key=lambda item: item[1])
    if value <= 0.5:
        return "mixed"
    return winner  # type: ignore[return-value]


def _build_edge_incidence(
    weights: np.ndarray,
    *,
    edge_tol: float = 1.0e-10,
) -> tuple[tuple[tuple[int, int], ...], dict[tuple[int, int], int], np.ndarray, np.ndarray]:
    W = np.asarray(weights, dtype=float)
    support = (np.abs(W) > edge_tol) | (np.abs(W.T) > edge_tol)
    np.fill_diagonal(support, False)
    n_nodes = int(W.shape[0])
    edges: list[tuple[int, int]] = []
    edge_lookup: dict[tuple[int, int], int] = {}
    for src in range(n_nodes - 1):
        for dst in range(src + 1, n_nodes):
            if support[src, dst]:
                edge_lookup[(src, dst)] = len(edges)
                edges.append((src, dst))
    incidence = np.zeros((n_nodes, len(edges)), dtype=float)
    for edge_idx, (src, dst) in enumerate(edges):
        incidence[src, edge_idx] = -1.0
        incidence[dst, edge_idx] = 1.0
    return tuple(edges), edge_lookup, incidence, support


def _enumerate_triangles(
    support: np.ndarray,
    *,
    max_triangles: int,
) -> tuple[tuple[tuple[int, int, int], ...], tuple[str, ...]]:
    n_nodes = int(support.shape[0])
    neighbor_sets = [set(np.flatnonzero(support[node]).tolist()) for node in range(n_nodes)]
    triangles: list[tuple[int, int, int]] = []
    warnings: list[str] = []
    for i in range(n_nodes - 2):
        for j in sorted(neighbor for neighbor in neighbor_sets[i] if neighbor > i):
            common = sorted(node for node in (neighbor_sets[i] & neighbor_sets[j]) if node > j)
            for k in common:
                triangles.append((i, j, k))
                if len(triangles) >= max_triangles:
                    warnings.append("hodge_triangle_limit_applied")
                    return tuple(triangles), tuple(warnings)
    return tuple(triangles), tuple(warnings)


def _build_triangle_incidence(
    edge_lookup: Mapping[tuple[int, int], int],
    triangles: tuple[tuple[int, int, int], ...],
    *,
    n_edges: int,
) -> np.ndarray:
    if not triangles:
        return np.zeros((n_edges, 0), dtype=float)
    incidence = np.zeros((n_edges, len(triangles)), dtype=float)
    for triangle_idx, (i, j, k) in enumerate(triangles):
        incidence[edge_lookup[(i, j)], triangle_idx] = 1.0
        incidence[edge_lookup[(j, k)], triangle_idx] = 1.0
        incidence[edge_lookup[(i, k)], triangle_idx] = -1.0
    return incidence


def _edge_flow_from_scores(
    weights: np.ndarray,
    scores: np.ndarray,
    edges: tuple[tuple[int, int], ...],
) -> np.ndarray:
    W = np.asarray(weights, dtype=float)
    theta = np.asarray(scores, dtype=float)
    flow = np.zeros(len(edges), dtype=float)
    for edge_idx, (src, dst) in enumerate(edges):
        flow[edge_idx] = W[src, dst] * theta[src] - W[dst, src] * theta[dst]
    return flow


def _project_gradient_component(B1: np.ndarray, flow: np.ndarray) -> np.ndarray:
    if B1.size == 0 or flow.size == 0:
        return np.zeros_like(flow)
    laplacian_0 = B1 @ B1.T
    alpha = np.linalg.pinv(laplacian_0) @ (B1 @ flow)
    return B1.T @ alpha


def _project_curl_component(B2: np.ndarray, flow: np.ndarray) -> np.ndarray:
    if B2.size == 0 or flow.size == 0:
        return np.zeros_like(flow)
    laplacian_2 = B2.T @ B2
    beta = np.linalg.pinv(laplacian_2) @ (B2.T @ flow)
    return B2 @ beta


def _compute_zone_spillover_score(
    outcome: np.ndarray,
    treatment: np.ndarray,
    exposure: np.ndarray,
    *,
    covariates: np.ndarray | None,
) -> tuple[np.ndarray, dict[str, float | None], tuple[str, ...]]:
    warnings: list[str] = []
    spillover_effect, spillover_se = _linear_effect_probe(
        outcome,
        treatment,
        exposure,
        estimand="spillover",
        covariates=covariates,
    )
    direct_effect, direct_se = _linear_effect_probe(
        outcome,
        treatment,
        exposure,
        estimand="direct",
        covariates=covariates,
    )
    centered_exposure = np.asarray(exposure, dtype=float) - float(np.mean(exposure))
    centered_treatment = np.asarray(treatment, dtype=float) - float(np.mean(treatment))

    theta = centered_exposure.copy()
    if spillover_effect is None or not math.isfinite(spillover_effect):
        warnings.append("spillover_probe_unidentified")
    else:
        theta = spillover_effect * centered_exposure

    if float(np.linalg.norm(theta)) <= 1.0e-12:
        if direct_effect is not None and math.isfinite(direct_effect):
            theta = direct_effect * centered_treatment
            warnings.append("spillover_probe_flat_fallback_to_direct")
        else:
            theta = centered_exposure
            warnings.append("spillover_probe_flat_unscaled")

    return (
        theta,
        {
            "spillover_effect": spillover_effect,
            "spillover_se": spillover_se,
            "direct_effect": direct_effect,
            "direct_se": direct_se,
        },
        tuple(warnings),
    )


def _build_spatial_hodge_profile(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    weights: np.ndarray,
    covariates: np.ndarray | None,
    labels: np.ndarray,
    scale_id: str,
    zoning_id: str,
    aggregation_rule: str,
    weight_spec: str,
    support_level: str,
    max_triangles: int,
) -> SpatialHodgeScaleProfile:
    exposure = np.asarray(weights, dtype=float) @ np.asarray(treatment, dtype=float)
    theta, probe_metadata, probe_warnings = _compute_zone_spillover_score(
        np.asarray(outcome, dtype=float),
        np.asarray(treatment, dtype=float),
        exposure,
        covariates=None if covariates is None else np.asarray(covariates, dtype=float),
    )

    edges, edge_lookup, B1, support = _build_edge_incidence(weights)
    flow = _edge_flow_from_scores(weights, theta, edges)
    gradient = _project_gradient_component(B1, flow)
    triangles, triangle_warnings = _enumerate_triangles(support, max_triangles=max_triangles)
    B2 = _build_triangle_incidence(edge_lookup, triangles, n_edges=len(edges))
    curl = _project_curl_component(B2, flow)
    harmonic = flow - gradient - curl

    total_energy = float(np.dot(flow, flow))
    gradient_energy = float(np.dot(gradient, gradient))
    curl_energy = float(np.dot(curl, curl))
    harmonic_energy = float(np.dot(harmonic, harmonic))
    warnings: list[str] = list(probe_warnings) + list(triangle_warnings)
    if total_energy <= 1.0e-12:
        warnings.append("degenerate_edge_flow")
        eta_grad = 0.0
        eta_curl = 0.0
        eta_harm = 0.0
    else:
        eta_grad = gradient_energy / total_energy
        eta_curl = curl_energy / total_energy
        eta_harm = harmonic_energy / total_energy

    return SpatialHodgeScaleProfile(
        scale_id=scale_id,
        zoning_id=zoning_id,
        aggregation_rule=aggregation_rule,
        weight_spec=weight_spec,
        zoning_hash=_hash_float_array(np.asarray(labels, dtype=float)),
        weight_hash=_hash_float_array(np.asarray(weights, dtype=float)),
        aggregation_hash=_stable_payload_hash({"aggregation_rule": aggregation_rule}),
        n_zones=int(np.asarray(treatment, dtype=float).shape[0]),
        n_edges=len(edges),
        n_triangles=len(triangles),
        total_energy=total_energy,
        gradient_energy=gradient_energy,
        curl_energy=curl_energy,
        harmonic_energy=harmonic_energy,
        eta_grad=eta_grad,
        eta_curl=eta_curl,
        eta_harm=eta_harm,
        dominant_component=_dominant_hodge_component(eta_grad, eta_curl, eta_harm),
        warnings=_flatten_unique_codes((tuple(warnings),)),
        metadata={
            "support_level": support_level,
            "mean_exposure": float(np.mean(exposure)),
            "std_exposure": float(np.std(exposure)),
            "max_abs_flow": float(np.max(np.abs(flow))) if flow.size else 0.0,
            **probe_metadata,
        },
    )


def _profile_l1_gap(
    left: SpatialHodgeScaleProfile,
    right: SpatialHodgeScaleProfile,
) -> float:
    return float(
        abs(left.eta_grad - right.eta_grad)
        + abs(left.eta_curl - right.eta_curl)
        + abs(left.eta_harm - right.eta_harm)
    )


def _summarize_spatial_hodge_diagnostics(
    diagnostics: SpatialHodgeDiagnostics,
) -> dict[str, Any]:
    return {
        "declared_scale_id": diagnostics.declared_scale_id,
        "declared_zoning_id": diagnostics.declared_zoning_id,
        "aggregation_rule": diagnostics.aggregation_rule,
        "weight_spec": diagnostics.weight_spec,
        "zoning_hash": diagnostics.zoning_hash,
        "weight_hash": diagnostics.weight_hash,
        "aggregation_hash": diagnostics.aggregation_hash,
        "eta_grad": diagnostics.eta_grad,
        "eta_curl": diagnostics.eta_curl,
        "eta_harm": diagnostics.eta_harm,
        "dominant_component": diagnostics.dominant_component,
        "max_profile_l1_gap": diagnostics.max_profile_l1_gap,
        "scale_instability": diagnostics.scale_instability,
        "zoning_instability": diagnostics.zoning_instability,
        "topology_sensitivity": diagnostics.topology_sensitivity,
        "candidate_partition_ids": list(diagnostics.candidate_partition_ids),
        "warnings": list(diagnostics.warnings),
        "blocker_codes": list(diagnostics.blocker_codes),
    }


def compute_spatial_hodge_diagnostics(
    data: NetworkCausalData,
    spatial_result: NetworkInterferenceReport,
    params: Mapping[str, Any],
) -> SpatialHodgeDiagnostics | None:
    W, weight_metadata = _resolve_spatial_weights_for_maup(data, spatial_result, params)
    if W is None:
        return None

    raw_aggregation_rule = params.get("aggregation_rule", data.metadata.get("aggregation_rule"))
    aggregation_rule = _normalize_hodge_aggregation_rule(raw_aggregation_rule)
    declared_scale_id = (
        str(params.get("scale_id", data.metadata.get("scale_id", "declared"))).strip() or "declared"
    )
    declared_zoning_id = (
        str(params.get("zoning_id", data.metadata.get("zoning_id", "observed_support"))).strip()
        or "observed_support"
    )
    max_triangles = max(1, int(params.get("hodge_max_triangles", 4096)))
    weight_spec = _resolve_weight_spec_label(spatial_result, weight_metadata, params)

    warnings: list[str] = []
    raw_aggregation_label = None if raw_aggregation_rule is None else str(raw_aggregation_rule)
    if (
        raw_aggregation_label is not None
        and aggregation_rule != raw_aggregation_label.strip().lower()
    ):
        warnings.append("aggregation_rule_normalized_to_mean")

    micro_labels = np.arange(data.n_units, dtype=int)
    profiles: list[SpatialHodgeScaleProfile] = [
        _build_spatial_hodge_profile(
            outcome=np.asarray(data.outcome, dtype=float),
            treatment=np.asarray(data.treatment, dtype=float),
            weights=np.asarray(W, dtype=float),
            covariates=None
            if data.covariates is None
            else np.asarray(data.covariates, dtype=float),
            labels=micro_labels,
            scale_id=declared_scale_id,
            zoning_id=declared_zoning_id,
            aggregation_rule=aggregation_rule,
            weight_spec=weight_spec,
            support_level="declared",
            max_triangles=max_triangles,
        )
    ]

    unit_weights_raw = params.get("aggregation_weights", data.metadata.get("aggregation_weights"))
    unit_weights = None if unit_weights_raw is None else np.asarray(unit_weights_raw, dtype=float)
    candidate_partition_ids: list[str] = []
    try:
        candidate_partitions = _resolve_maup_partitions(data, params)
    except (TypeError, ValueError) as exc:
        candidate_partitions = ()
        warnings.append(f"candidate_partitions_invalid:{exc}")

    for index, raw_partition in enumerate(candidate_partitions):
        try:
            partition_id, scale_label, zoning_label, labels = _coerce_candidate_partition(
                raw_partition,
                index=index,
                n_units=data.n_units,
            )
        except ValueError as exc:
            warnings.append(f"invalid_partition_skipped:{index}:{exc}")
            continue
        candidate_partition_ids.append(partition_id)
        partition_rule = _normalize_hodge_aggregation_rule(
            raw_partition.get("aggregation_rule", aggregation_rule)
            if isinstance(raw_partition, Mapping)
            else aggregation_rule
        )
        M, C, _ = _make_averaging_operator(labels)
        Wq = _aggregate_weight_matrix(M, W, C)
        aggregated_outcome = _aggregate_partition_array(
            np.asarray(data.outcome, dtype=float),
            labels,
            rule=partition_rule,
            unit_weights=unit_weights,
        )
        aggregated_treatment = _aggregate_partition_array(
            np.asarray(data.treatment, dtype=float),
            labels,
            rule=partition_rule,
            unit_weights=unit_weights,
        )
        aggregated_covariates = (
            None
            if data.covariates is None
            else _aggregate_partition_array(
                np.asarray(data.covariates, dtype=float),
                labels,
                rule=partition_rule,
                unit_weights=unit_weights,
            )
        )
        profiles.append(
            _build_spatial_hodge_profile(
                outcome=np.asarray(aggregated_outcome, dtype=float),
                treatment=np.asarray(aggregated_treatment, dtype=float),
                weights=Wq,
                covariates=(
                    None
                    if aggregated_covariates is None
                    else np.asarray(aggregated_covariates, dtype=float)
                ),
                labels=np.asarray(labels, dtype=int),
                scale_id=scale_label or f"{declared_scale_id}:{partition_id}",
                zoning_id=zoning_label or partition_id,
                aggregation_rule=partition_rule,
                weight_spec=_resolve_weight_spec_label(
                    spatial_result,
                    weight_metadata,
                    params,
                    suffix=f"aggregate:{partition_id}",
                ),
                support_level="aggregate",
                max_triangles=max_triangles,
            )
        )

    pairwise_gaps: list[tuple[float, SpatialHodgeScaleProfile, SpatialHodgeScaleProfile]] = []
    for left_idx in range(len(profiles) - 1):
        for right_idx in range(left_idx + 1, len(profiles)):
            gap = _profile_l1_gap(profiles[left_idx], profiles[right_idx])
            pairwise_gaps.append((gap, profiles[left_idx], profiles[right_idx]))

    max_profile_l1_gap = max((gap for gap, _, _ in pairwise_gaps), default=0.0)
    scale_instability = max(
        (gap for gap, left, right in pairwise_gaps if left.scale_id != right.scale_id),
        default=0.0,
    )
    zoning_instability = max(
        (
            gap
            for gap, left, right in pairwise_gaps
            if left.zoning_id != right.zoning_id and left.scale_id == right.scale_id
        ),
        default=0.0,
    )

    symmetric_weights = _row_standardize_matrix(0.5 * (W + W.T))
    topology_probe = _build_spatial_hodge_profile(
        outcome=np.asarray(data.outcome, dtype=float),
        treatment=np.asarray(data.treatment, dtype=float),
        weights=symmetric_weights,
        covariates=None if data.covariates is None else np.asarray(data.covariates, dtype=float),
        labels=micro_labels,
        scale_id=declared_scale_id,
        zoning_id=declared_zoning_id,
        aggregation_rule=aggregation_rule,
        weight_spec=_resolve_weight_spec_label(
            spatial_result,
            weight_metadata,
            params,
            suffix="symmetric_probe",
        ),
        support_level="topology_probe",
        max_triangles=max_triangles,
    )
    topology_sensitivity = _profile_l1_gap(profiles[0], topology_probe)

    blocker_codes: list[str] = []
    if max_profile_l1_gap >= 1.0:
        blocker_codes.append("HODGE_E_STRONG_MAUP_INSTABILITY")
    if topology_sensitivity >= 1.0:
        blocker_codes.append("HODGE_E_TOPOLOGY_SENSITIVE")

    warnings.extend(warning for profile in profiles for warning in profile.warnings)
    warnings.extend(topology_probe.warnings)

    declared_profile = profiles[0]
    return SpatialHodgeDiagnostics(
        declared_scale_id=declared_scale_id,
        declared_zoning_id=declared_zoning_id,
        aggregation_rule=aggregation_rule,
        weight_spec=weight_spec,
        exposure_mapping=spatial_result.exposure_mapping.value,
        zoning_hash=declared_profile.zoning_hash,
        weight_hash=declared_profile.weight_hash,
        aggregation_hash=declared_profile.aggregation_hash,
        eta_grad=declared_profile.eta_grad,
        eta_curl=declared_profile.eta_curl,
        eta_harm=declared_profile.eta_harm,
        dominant_component=declared_profile.dominant_component,
        max_profile_l1_gap=max_profile_l1_gap,
        scale_instability=scale_instability,
        zoning_instability=zoning_instability,
        topology_sensitivity=topology_sensitivity,
        candidate_partition_ids=tuple(candidate_partition_ids),
        profiles=tuple(profiles),
        blocker_codes=_flatten_unique_codes((tuple(blocker_codes),)),
        warnings=_flatten_unique_codes((tuple(warnings),)),
        metadata={
            "weight_metadata": dict(weight_metadata),
            "topology_probe": {
                "weight_spec": topology_probe.weight_spec,
                "eta_grad": topology_probe.eta_grad,
                "eta_curl": topology_probe.eta_curl,
                "eta_harm": topology_probe.eta_harm,
                "dominant_component": topology_probe.dominant_component,
            },
            "profile_count": len(profiles),
            "candidate_partition_count": len(candidate_partition_ids),
            "areal_support": str(
                params.get("areal_support", data.metadata.get("areal_support", "observed_units"))
            ),
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Core algorithm implementations
# ──────────────────────────────────────────────────────────────────────────────


def _run_partial_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Hudgens & Halloran (2008) partial interference IPW."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    alpha_bw = float(params.get("alpha_bandwidth", 0.1))
    exposure_map = str(params.get("exposure_mapping", "fractional"))
    threshold = float(params.get("threshold", 0.5))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.cluster_id is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                ExposureMappingType.FRACTIONAL,
                n,
                n_treated,
                "cluster_id is required for PartialInterferenceEstimator",
            )
        }

    C = data.cluster_id
    clusters = np.unique(C)
    n_clusters = len(clusters)
    avg_cluster_size = float(n / n_clusters)

    # Compute exposure
    if exposure_map == "threshold":
        f = _threshold_exposure(A, C, threshold)
        exp_type = ExposureMappingType.THRESHOLD
    else:
        f = _fractional_exposure(A, C)
        exp_type = ExposureMappingType.FRACTIONAL

    # Build propensity features
    if data.covariates is not None:
        ps_features = np.column_stack([data.covariates, f])
    else:
        ps_features = f.reshape(-1, 1)

    try:
        ps = _logistic_propensity(A, ps_features)
    except Exception as exc:
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                exp_type,
                n,
                n_treated,
                f"propensity model failed: {exc}",
                status="numerical_failure",
            )
        }

    # Stratum masks: (treatment==a) & exposure near alpha
    def _potential_outcome_stratum(a_val: float, alpha: float) -> tuple[float, np.ndarray]:
        in_stratum = (a_val == A) & (np.abs(f - alpha) <= alpha_bw)
        if in_stratum.sum() < 2:
            return float("nan"), np.full(n, float("nan"))
        ps_a = ps if a_val == 1.0 else (1.0 - ps)
        # P(A=a, |f - alpha| <= alpha_bw) ≈ P(A=a) * P(|f-alpha|<=bw | A=a)
        # Use unit-level IPW within stratum
        est, scores = _ipw_potential_outcome(Y, in_stratum.astype(float), ps_a)
        # Normalise so it's an estimate of E[Y(a, alpha)], not a sum
        return est, scores

    mu11, sc11 = _potential_outcome_stratum(1.0, alpha_high)
    mu10, sc10 = _potential_outcome_stratum(0.0, alpha_high)
    mu01, sc01 = _potential_outcome_stratum(0.0, alpha_low)

    warnings: list[str] = []
    if any(math.isnan(x) for x in (mu11, mu10, mu01)):
        warnings.append(
            "Some alpha-strata have fewer than 2 observations; estimates may be unreliable."
        )

    # Fallback: simple cluster-level means when strata are sparse
    def _fallback_mean(a_val: float) -> float:
        mask = a_val == A
        return float(Y[mask].mean()) if mask.sum() > 0 else float("nan")

    if math.isnan(mu11):
        mu11 = _fallback_mean(1.0)
    if math.isnan(mu10):
        mu10 = _fallback_mean(0.0)
    if math.isnan(mu01):
        mu01 = _fallback_mean(0.0)

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    # Cluster-level sandwich variance
    def _cluster_var(scores: np.ndarray) -> float:
        """Mean cluster-level variance."""
        if np.any(np.isnan(scores)):
            return float("nan")
        cluster_means = np.array([scores[c == C].mean() for c in clusters], dtype=float)
        return float(np.var(cluster_means, ddof=1) / n_clusters)

    var_de = _cluster_var(sc11 - sc10) if not np.any(np.isnan(sc11 + sc10)) else float("nan")
    var_se = _cluster_var(sc10 - sc01) if not np.any(np.isnan(sc10 + sc01)) else float("nan")
    var_te = _cluster_var(sc11 - sc01) if not np.any(np.isnan(sc11 + sc01)) else float("nan")

    se_de = math.sqrt(max(var_de, 0.0)) if math.isfinite(var_de) else float("nan")
    se_se = math.sqrt(max(var_se, 0.0)) if math.isfinite(var_se) else float("nan")
    se_te = math.sqrt(max(var_te, 0.0)) if math.isfinite(var_te) else float("nan")

    if any(not math.isfinite(x) for x in (de, se_val, te)):
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                exp_type,
                n,
                n_treated,
                "Could not estimate one or more potential outcomes; "
                "check treatment variation and alpha bandwidth.",
                status="numerical_failure",
            )
        }

    assumptions = {
        "partial_interference": "Units in different clusters do not interfere.",
        "stratified_interference": "Within a cluster, potential outcome depends on own "
        "treatment and aggregate cluster allocation only.",
        "positivity": "Each unit has positive probability of treatment and each "
        "exposure level under both treatment arms.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.PARTIAL_IPW,
            exposure_mapping=exp_type,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            n_clusters=n_clusters,
            avg_cluster_size=avg_cluster_size,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "exposure_mapping": exposure_map,
                "alpha_bandwidth": alpha_bw,
                "threshold": threshold,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_network_aipw(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Aronow & Samii (2017) network AIPW with general exposure mapping."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    n_bootstrap = int(params.get("n_bootstrap", 200))
    mapping_type = str(params.get("exposure_mapping", "fraction"))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.adjacency_matrix is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.NETWORK_AIPW,
                ExposureMappingType.FRACTIONAL,
                n,
                n_treated,
                "adjacency_matrix is required for NetworkAIPWEstimator",
            )
        }

    W = data.adjacency_matrix.astype(float)
    e = _network_exposure(A, W, mapping_type)

    # Binary indicator: high exposure (e > alpha_high) vs low
    e_high = (e >= alpha_high).astype(float)
    e_low = (e <= alpha_low).astype(float)

    # Build features: [A, e, X] for propensity models
    base_features = np.column_stack([A, e])
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _aipw_for_stratum(
        a_val: float,
        e_indicator: np.ndarray,
    ) -> tuple[float, float]:
        """AIPW estimator for E[Y(a, e_type)] where e_type is high/low."""
        stratum = (a_val == A) & (e_indicator > 0)
        if stratum.sum() < 3:
            return float("nan"), float("nan")

        # Outcome model E[Y | X, A=a, e_type]
        try:
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X_s = scaler.fit_transform(base_features[stratum])
            y_s = Y[stratum]
            ridge = Ridge(alpha=1.0)
            ridge.fit(X_s, y_s)
            mu_hat = ridge.predict(scaler.transform(base_features))
        except Exception:
            mu_hat = np.full(n, float(Y[stratum].mean()))

        # Propensity P(in stratum | X)
        try:
            ps = _logistic_propensity(stratum.astype(int), base_features)
        except Exception:
            ps = np.full(n, float(stratum.mean()) + 1e-6)

        ps_clipped = np.clip(ps, 1e-4, 1 - 1e-4)
        # AIPW scores: IPW + augmentation
        aipw_scores = (
            stratum.astype(float) * Y / ps_clipped
            - (stratum.astype(float) / ps_clipped - 1.0) * mu_hat
        )
        est = float(np.mean(aipw_scores))
        se = math.sqrt(max(_sandwich_var(aipw_scores - est), 0.0))
        return est, se

    mu11, se11 = _aipw_for_stratum(1.0, e_high)
    mu10, se10 = _aipw_for_stratum(0.0, e_high)
    mu01, se01 = _aipw_for_stratum(0.0, e_low)

    warnings: list[str] = []
    if any(math.isnan(x) for x in (mu11, mu10, mu01)):
        warnings.append(
            "Some exposure strata have too few observations. "
            "Consider adjusting alpha_high / alpha_low."
        )
        # Fallback
        if math.isnan(mu11):
            mu11 = float(Y[A == 1.0].mean()) if (A == 1.0).sum() > 0 else 0.0
        if math.isnan(mu10):
            mu10 = float(Y[A == 0.0].mean()) if (A == 0.0).sum() > 0 else 0.0
        if math.isnan(mu01):
            mu01 = mu10

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    # Combined SEs (independent strata approximation)
    def _combined_se(s1: float, s2: float) -> float:
        if math.isnan(s1) or math.isnan(s2):
            return float("nan")
        return math.sqrt(s1**2 + s2**2)

    se_de = _combined_se(se11, se10)
    se_se = _combined_se(se10, se01)
    se_te = _combined_se(se11, se01)

    assumptions = {
        "no_unmeasured_confounding": "Treatment assignment is ignorable given observed covariates.",
        "positivity_exposure": "Each unit has positive probability of each exposure level.",
        "stratified_interference": "Potential outcome depends on own treatment and exposure "
        "level (aggregated from adjacency) only.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.NETWORK_AIPW,
            exposure_mapping=ExposureMappingType.FRACTIONAL,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "mapping_type": mapping_type,
                "n_bootstrap": n_bootstrap,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_spatial_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Kernel-weighted spatial spillover estimator."""
    bandwidth_param = params.get("bandwidth", "auto")
    kernel = str(params.get("kernel", "gaussian"))
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    conf = float(params.get("confidence_level", 0.95))
    compute_maup = bool(params.get("compute_maup_certificate", False))
    compute_hodge = bool(params.get("compute_hodge_diagnostics", compute_maup))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    # Resolve spatial structure
    if data.coordinates is not None:
        coords = data.coordinates[:, :2].astype(float)  # keep only x, y
    elif data.adjacency_matrix is not None:
        # Fallback: use adjacency as weight matrix directly
        W = data.adjacency_matrix.astype(float)
        degree = W.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(degree > 0, (W @ A) / degree, 0.0)
        coords = None
    else:
        base_report = _build_report_failure(
            InterferenceMethod.SPATIAL_KERNEL,
            ExposureMappingType.KERNEL,
            n,
            n_treated,
            "coordinates or adjacency_matrix required for SpatialInterferenceEstimator",
        )
        certificate = (
            compute_maup_invariance_certificate(data, base_report, params) if compute_maup else None
        )
        diagnostics = (
            compute_spatial_hodge_diagnostics(data, base_report, params) if compute_hodge else None
        )
        return {
            "result": SpatialResult(
                **base_report.model_dump(mode="python"),
                maup_invariance_certificate=certificate,
                spatial_hodge_diagnostics=diagnostics,
            )
        }

    used_bandwidth: float | None = None
    if coords is not None:
        if bandwidth_param == "auto":
            bw = _auto_bandwidth(coords)
        else:
            try:
                bw = float(bandwidth_param)
            except (TypeError, ValueError):
                bw = _auto_bandwidth(coords)
        if bw <= 0:
            base_report = _build_report_failure(
                InterferenceMethod.SPATIAL_KERNEL,
                ExposureMappingType.KERNEL,
                n,
                n_treated,
                f"bandwidth must be positive, got {bw}",
            )
            certificate = (
                compute_maup_invariance_certificate(data, base_report, params)
                if compute_maup
                else None
            )
            diagnostics = (
                compute_spatial_hodge_diagnostics(data, base_report, params)
                if compute_hodge
                else None
            )
            return {
                "result": SpatialResult(
                    **base_report.model_dump(mode="python"),
                    maup_invariance_certificate=certificate,
                    spatial_hodge_diagnostics=diagnostics,
                )
            }
        used_bandwidth = bw
        W = _kernel_weights(coords, bw)
        degree = W.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(degree > 0, (W @ A) / degree, 0.0)

    # Exposure strata
    e_high = (s >= alpha_high).astype(float)
    e_low = (s <= alpha_low).astype(float)

    base_features = np.column_stack([A, s])
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _ipw_mean(a_val: float, e_ind: np.ndarray) -> tuple[float, float]:
        stratum = (a_val == A) & (e_ind > 0)
        if stratum.sum() < 2:
            return float("nan"), float("nan")
        try:
            ps = _logistic_propensity(stratum.astype(int), base_features)
        except Exception:
            ps = np.full(n, float(stratum.mean()) + 1e-6)
        est, scores = _ipw_potential_outcome(Y, stratum.astype(float), ps)
        se = math.sqrt(max(_sandwich_var(scores - est), 0.0))
        return est, se

    mu11, se11 = _ipw_mean(1.0, e_high)
    mu10, se10 = _ipw_mean(0.0, e_high)
    mu01, se01 = _ipw_mean(0.0, e_low)

    warnings: list[str] = []
    for mu, name in ((mu11, "E[Y(1,high)]"), (mu10, "E[Y(0,high)]"), (mu01, "E[Y(0,low)]")):
        if math.isnan(mu):
            warnings.append(f"Stratum for {name} has too few units; using marginal mean.")

    if math.isnan(mu11):
        mu11 = float(Y[A == 1.0].mean()) if (A == 1.0).sum() > 0 else 0.0
    if math.isnan(mu10):
        mu10 = float(Y[A == 0.0].mean()) if (A == 0.0).sum() > 0 else 0.0
    if math.isnan(mu01):
        mu01 = mu10

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    def _cse(s1: float, s2: float) -> float:
        if math.isnan(s1) or math.isnan(s2):
            return float("nan")
        return math.sqrt(s1**2 + s2**2)

    se_de = _cse(se11, se10)
    se_se = _cse(se10, se01)
    se_te = _cse(se11, se01)

    exposure_params: dict[str, Any] = {
        "kernel": kernel,
        "alpha_high": alpha_high,
        "alpha_low": alpha_low,
    }
    if used_bandwidth is not None:
        exposure_params["bandwidth"] = used_bandwidth

    assumptions = {
        "geographic_spillover": "Spillover effects decay with geographic distance as modelled by the kernel.",
        "positivity": "Positive probability of each exposure level in each spatial location.",
        "no_unmeasured_confounding": "Treatment assignment ignorable given covariates.",
    }

    base_report = _build_report_success(
        method=InterferenceMethod.SPATIAL_KERNEL,
        exposure_mapping=ExposureMappingType.KERNEL,
        de=de,
        se_val=se_val,
        te=te,
        se_de=se_de,
        se_se=se_se,
        se_te=se_te,
        n_units=n,
        n_treated=n_treated,
        confidence_level=conf,
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        exposure_params=exposure_params,
        assumptions=assumptions,
        warnings=warnings,
    )
    diagnostics = (
        compute_spatial_hodge_diagnostics(data, base_report, params) if compute_hodge else None
    )
    certificate = (
        compute_maup_invariance_certificate(data, base_report, params) if compute_maup else None
    )
    if diagnostics is not None:
        summary = _summarize_spatial_hodge_diagnostics(diagnostics)
        updated_metadata = dict(base_report.metadata)
        updated_metadata["spatial_hodge_summary"] = summary
        updated_metadata["spatial_hodge_diagnostics"] = diagnostics.model_dump(mode="python")
        base_report = base_report.model_copy(update={"metadata": updated_metadata})
    if certificate is not None and diagnostics is not None:
        certificate_metadata = dict(certificate.metadata)
        certificate_metadata.setdefault("zoning_hash", diagnostics.zoning_hash)
        certificate_metadata.setdefault("weight_hash", diagnostics.weight_hash)
        certificate_metadata.setdefault("aggregation_hash", diagnostics.aggregation_hash)
        certificate_metadata.setdefault("max_profile_l1_gap", diagnostics.max_profile_l1_gap)
        certificate_metadata.setdefault("scale_instability", diagnostics.scale_instability)
        certificate_metadata.setdefault("zoning_instability", diagnostics.zoning_instability)
        certificate_metadata.setdefault("topology_sensitivity", diagnostics.topology_sensitivity)
        certificate = certificate.model_copy(update={"metadata": certificate_metadata})
    return {
        "result": SpatialResult(
            **base_report.model_dump(mode="python"),
            maup_invariance_certificate=certificate,
            spatial_hodge_diagnostics=diagnostics,
        )
    }


def _run_bipartite_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Zigler & Papadogeorgou (2021) bipartite interference."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    aggregate_fn = str(params.get("aggregate_fn", "fraction"))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.bipartite_edges is None or data.treatment_unit_ids is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.BIPARTITE,
                ExposureMappingType.BIPARTITE,
                n,
                n_treated,
                "bipartite_edges and treatment_unit_ids are required for "
                "BipartiteInterferenceEstimator",
            )
        }

    edges = data.bipartite_edges  # (n_edges, 2): [tx_unit_idx, outcome_unit_idx]
    tx_ids = data.treatment_unit_ids  # (n_tx,) int
    n_tx = len(tx_ids)

    # Treatment of treatment units
    A_tx = A[tx_ids]

    # Aggregate exposure for each outcome unit (all n units, non-outcome units get 0)
    g = np.zeros(n, dtype=float)
    for out_idx in range(n):
        upstream = edges[edges[:, 1] == out_idx, 0]
        if len(upstream) == 0:
            continue
        if aggregate_fn == "fraction":
            g[out_idx] = float(A_tx[upstream].mean())
        elif aggregate_fn == "count":
            g[out_idx] = float(A_tx[upstream].sum())
        else:  # "max"
            g[out_idx] = float(A_tx[upstream].max())

    # For outcome units: high/low exposure indicators
    e_high = (g >= alpha_high).astype(float)
    e_low = (g <= alpha_low).astype(float)

    # Mark outcome units (not treatment units)
    outcome_mask = np.ones(n, dtype=bool)
    outcome_mask[tx_ids] = False
    n_outcome = int(outcome_mask.sum())

    base_features = g.reshape(-1, 1)
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _mean_potential(e_ind: np.ndarray, out_mask: np.ndarray) -> tuple[float, float]:
        stratum = e_ind.astype(bool) & out_mask
        if stratum.sum() < 2:
            return float("nan"), float("nan")
        try:
            ps = _logistic_propensity(stratum[out_mask].astype(int), base_features[out_mask])
        except Exception:
            ps = np.full(int(out_mask.sum()), float(stratum[out_mask].mean()) + 1e-6)
        ps_full = np.zeros(n)
        ps_full[out_mask] = ps
        est, scores = _ipw_potential_outcome(
            Y * out_mask.astype(float),
            stratum.astype(float),
            np.clip(ps_full, 1e-6, 1 - 1e-6),
        )
        se = math.sqrt(max(_sandwich_var(scores - est), 0.0))
        return est, se

    mu_high, se_high = _mean_potential(e_high, outcome_mask)
    mu_low, se_low = _mean_potential(e_low, outcome_mask)

    warnings: list[str] = []
    if math.isnan(mu_high) or math.isnan(mu_low):
        warnings.append(
            "One or more exposure strata have too few outcome units. "
            "Falling back to marginal mean differences."
        )
        mu_high_val = (
            float(Y[outcome_mask & e_high.astype(bool)].mean())
            if (outcome_mask & e_high.astype(bool)).sum() > 0
            else 0.0
        )
        mu_low_val = (
            float(Y[outcome_mask & e_low.astype(bool)].mean())
            if (outcome_mask & e_low.astype(bool)).sum() > 0
            else 0.0
        )
        if math.isnan(mu_high):
            mu_high, se_high = mu_high_val, 0.0
        if math.isnan(mu_low):
            mu_low, se_low = mu_low_val, 0.0

    # In bipartite setting: direct effect = contrast in aggregate exposure
    # (no "own treatment" for outcome units)
    de = mu_high - mu_low
    se_val = mu_high - mu_low  # spillover ≡ aggregate exposure contrast
    te = de

    se_de = (
        math.sqrt(se_high**2 + se_low**2)
        if math.isfinite(se_high) and math.isfinite(se_low)
        else float("nan")
    )
    se_se = se_de
    se_te = se_de

    assumptions = {
        "bipartite_structure": "Outcome units are distinct from treatment units; "
        "interference acts only through upstream treatment.",
        "positivity": "Positive probability of each aggregate exposure level.",
        "no_unmeasured_confounding": "Assignment of treatment units is ignorable given observed covariates.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.BIPARTITE,
            exposure_mapping=ExposureMappingType.BIPARTITE,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "aggregate_fn": aggregate_fn,
                "n_treatment_units": n_tx,
                "n_outcome_units": n_outcome,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


__all__ = [name for name in globals() if not name.startswith("__")]
