"""CausalEngine — Pearl-Bareinboim causal inference orchestrator.

Wires together identification (id_engine), compilation (estimand_compiler),
estimation (foundry methods), and audit trail (EvidenceBundle).

Usage::

    engine = CausalEngine(registry=MethodRegistry.get_instance(), knowledge_base=kb)
    report, bundle, cert = engine.run(
        treatment="X", outcome="Y", graph=graph, data_dict=data,
        s_nodes=s_nodes, n_obs=500,
    )
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

logger = logging.getLogger(__name__)

from polisyos.foundry.methods.catalog._phase1_artifacts import (
    is_government_dataset,
    resolve_dataset_context,
)
from polisyos.foundry.methods.catalog.causal._causal_engine_contracts import (
    DataReadinessBlockedError,
)
from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    do_operator,
    has_directed_cycle,
    induced_subgraph,
)
from polisyos.foundry.methods.catalog.causal.cyclic_id import (
    cyclic_id_algorithm,
    well_posedness_check,
)
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    CyclicExecutionBlock,
    ExecutorGraph,
    ExecutorNode,
    compile_estimand,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    conditional_intervention_id,
    dynamic_intervention_id,
    id_star_algorithm,
    id_with_oracle_fallback,
    idc_algorithm,
    idc_star_algorithm,
    multi_outcome_id,
    mz_id_algorithm,
    # Phase-5 additions
    sid_algorithm,
    tr_algorithm,
    z_id_algorithm,
)
from polisyos.foundry.methods.catalog.causal.local_independence_id import (
    build_temporal_identification_certificate,
    li_id_algorithm,
)
from polisyos.foundry.methods.catalog.causal.proof_trace_composability import (
    build_witness_index_from_proof_steps,
    check_proof_trace_composability,
)
from polisyos.foundry.methods.catalog.causal.proximal_identify import (
    proximal_identify_v1,
    proximal_spatial_identify_v1,
)
from polisyos.foundry.methods.catalog.causal.schema_resolver import (
    SchemaResolutionReport,
    SchemaResolver,
)
from polisyos.ir.analytics.causal import (
    DataReadinessReport,
    EstimationStatus,
    ProofBundle,
    build_data_readiness_report,
    build_dynamic_proof_bundle,
    persist_data_readiness_report,
    persist_proof_bundle,
    proof_bundle_from_identification_result,
    proof_bundle_from_negative_certificate,
    proof_bundle_from_proximal_certificate,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.dual_certificate import hydrate_bounds_bundle_with_dual_certificate
from polisyos.ir.analytics.dynamic_causal_semantics import (
    DynamicReductionStatus,
    DynamicScopeStatement,
    DynamicSemanticsAttachment,
    DynamicSemanticsFamily,
    GraphicalMarkovCertificate,
    GraphicalOracleKind,
    InterventionKind,
    InterventionScope,
    LocalIndependenceAttachment,
    SeparationClaim,
    WellPosednessStatus,
    WellPosednessWitness,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    EffectTrajectoryBundle,
    InterventionInterpolationPolicy,
    StrategicAdaptationMode,
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionTrajectory,
    TemporalQueryMode,
    TemporalSamplingScheme,
    load_temporal_intervention_trajectory,
    persist_continuous_time_query,
    persist_dynamic_treatment_regime,
    persist_effect_trajectory_bundle,
    persist_temporal_identification_certificate,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.analytics.estimand import (
    DistributionLawQuery,
    DistributionRef,
    EdgeInterventionAssignment,
    EdgeInterventionNode,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
    PathSpecificNode,
    StochasticInterventionNode,
    StochasticPolicy,
    make_distribution_law_estimand,
)
from polisyos.ir.analytics.evidence_bundle import (
    CompilationStep,
    DataProvenance,
    EstimationStep,
    EvidenceBundle,
    _fingerprint,
    persist_causal_evidence_bundle,
)
from polisyos.ir.analytics.evidence_bundle import (
    ProofStep as IRProofStep,
)
from polisyos.ir.analytics.frontier import (
    FrontierSketch,
    persist_frontier_sketch,
)
from polisyos.ir.analytics.interventions import (
    CompositeIntervention,
    ConditionalIntervention,
    ConditionalPolicy,
    EdgeIntervention,
    InterferenceIntervention,
    InterventionCertificate,
    InterventionFallback,
    InterventionFallbackMode,
    InterventionIdentificationStatus,
    InterventionQuery,
    ModifiedTreatmentPolicySpec,
    MTPIntervention,
    NodeIntervention,
    PathIntervention,
    QueryTarget,
    QueryTargetKind,
    StochasticIntervention,
    StochasticPolicySpec,
    TransportIntervention,
    VariableAssignment,
    build_intervention_certificate,
    certificate_for_typecheck_failure,
    check_intervention_composition,
    persist_intervention_certificate,
    persist_intervention_query,
    render_intervention_query,
)
from polisyos.ir.analytics.local_independence import (
    CensoringInterventionSpec,
    EliminabilityCheck,
    EliminabilityStep,
    IndependentCensoringCheck,
    IntensityModelRequirement,
    LocalIndependenceEdge,
    LocalIndependenceGraphicalChecks,
    LocalIndependenceGraphSpec,
    LocalIndependenceIdentificationSpec,
    LocalIndependenceRuntimeRequirements,
    LocalIndependenceTarget,
    LocalIndependenceWeightingCertificate,
    TreatmentIntensityInterventionSpec,
    persist_local_independence_weighting_certificate,
)
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    EpistemicTier,
    FallbackResult,
    NegativeCertificate,
    ParametricRescueResult,
    persist_negative_certificate,
    recovery_plan_from_negative_certificate,
)
from polisyos.ir.analytics.partial_identification import (
    BoundsBundle,
    bounds_bundle_from_partial_identification_result,
    persist_bounds_bundle,
)
from polisyos.ir.analytics.proof_composability import (
    attach_proof_composability_to_proof_bundle,
    persist_proof_composability_certificate,
    persist_proof_witness_index,
)
from polisyos.ir.analytics.proximal import (
    BridgePlausibilityReport,
    ProximalIdentificationCertificate,
    ProxyAnnotation,
    persist_bridge_plausibility_report,
    persist_proximal_identification_certificate,
)
from polisyos.ir.analytics.recoverability import (
    JointDecisionCertificate,
    RecoverabilityCertificate,
    persist_joint_decision_certificate,
    persist_recoverability_certificate,
)
from polisyos.ir.analytics.survey_quality import load_survey_quality_certificate
from polisyos.ir.artifacts import ArtifactStore, InputRef, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.governance.phase1 import (
    build_phase1_gate_summary,
    load_phase1_flagship_dataset_ids,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    DynamicTreatmentRegimeRef,
    SurveyQualityCertificateRef,
    TemporalIdentificationCertificateRef,
    TemporalInterventionTrajectoryRef,
)

if TYPE_CHECKING:
    from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
    from polisyos.ir.analytics.dynamic_regime import GComputationResult
    from polisyos.ir.analytics.mgraph import MGraphMetadata
    from polisyos.ir.analytics.proximal import ProximalMediationCertificate
    from polisyos.ir.analytics.recoverability import JointDecisionCertificate



def _infer_sample_size(
    data_dict: dict[str, Any] | None,
    *,
    explicit_n_obs: int | None = None,
) -> int | None:
    """Infer sample size from explicit metadata or the first array-like value."""
    if explicit_n_obs is not None:
        return int(explicit_n_obs)
    if not data_dict:
        return None
    for value in data_dict.values():
        try:
            size = len(value)  # type: ignore[arg-type]
        except Exception:
            continue
        if size >= 0:
            return size
    return None


def _has_fallback_arrays(
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> bool:
    """Return True when treatment and outcome arrays appear to be available."""
    if not data_dict:
        return False
    treatment_name = _singleton_query_name(treatment, "treatment")
    outcome_name = _singleton_query_name(outcome, "outcome")
    if treatment_name is None or outcome_name is None:
        return False
    treatment_candidates = (
        data_dict.get(treatment_name),
        data_dict.get("treatment"),
        data_dict.get("protected"),
    )
    outcome_candidates = (
        data_dict.get(outcome_name),
        data_dict.get("outcome"),
    )
    return any(candidate is not None for candidate in treatment_candidates) and any(
        candidate is not None for candidate in outcome_candidates
    )


def _coerce_aligned_vector(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        return None
    return arr


def _coerce_aligned_covariates(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    elif arr.ndim > 2:
        try:
            arr = arr.reshape(arr.shape[0], -1)
        except Exception:
            return None
    if arr.ndim != 2 or arr.shape[0] != n_obs:
        return None
    return arr


def _coerce_aligned_proxy_matrix(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2 or arr.shape[0] != n_obs:
        return None
    return arr


def _coerce_aligned_square_matrix(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim != 2 or arr.shape != (n_obs, n_obs):
        return None
    return arr


def _collect_proxy_matrix(
    *,
    data_dict: dict[str, Any] | None,
    direct_keys: tuple[str, ...],
    proxy_variables: tuple[str, ...],
    n_obs: int,
) -> np.ndarray | None:
    if not data_dict:
        return None
    for key in direct_keys:
        matrix = _coerce_aligned_proxy_matrix(data_dict.get(key), n_obs=n_obs)
        if matrix is not None:
            return matrix
    proxy_columns: list[np.ndarray] = []
    for name in proxy_variables:
        column = _coerce_aligned_vector(data_dict.get(name))
        if column is None or column.shape[0] != n_obs:
            return None
        proxy_columns.append(column)
    if not proxy_columns:
        return None
    return np.column_stack(proxy_columns)


def _first_valid_square_matrix(
    data_dict: dict[str, Any] | None,
    candidate_keys: tuple[str, ...],
    *,
    n_obs: int,
) -> np.ndarray | None:
    if not data_dict:
        return None
    for key in candidate_keys:
        matrix = _coerce_aligned_square_matrix(data_dict.get(key), n_obs=n_obs)
        if matrix is not None:
            return matrix
    return None


def _derive_proximal_bridge_state(
    *,
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
    certificate: ProximalIdentificationCertificate,
) -> dict[str, np.ndarray] | None:
    """Build the B-layer proximal estimator state from graph variable names."""

    if not data_dict:
        return None

    treatment_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, _treatment_candidate_keys(treatment))
    )
    outcome_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, _outcome_candidate_keys(outcome))
    )
    if treatment_vector is None or outcome_vector is None:
        return None
    n_obs = int(outcome_vector.shape[0])
    z_proxy = _collect_proxy_matrix(
        data_dict=data_dict,
        direct_keys=("treatment_proxy",),
        proxy_variables=certificate.proxies.treatment_inducing,
        n_obs=n_obs,
    )
    w_proxy = _collect_proxy_matrix(
        data_dict=data_dict,
        direct_keys=("outcome_proxy",),
        proxy_variables=certificate.proxies.outcome_inducing,
        n_obs=n_obs,
    )
    if treatment_vector is None or outcome_vector is None or z_proxy is None or w_proxy is None:
        return None
    if any(item.shape[0] != n_obs for item in (treatment_vector, z_proxy, w_proxy)):
        return None

    covariates = _coerce_aligned_covariates(data_dict.get("covariates"), n_obs=n_obs)
    if covariates is None:
        covariate_names = tuple(certificate.query.covariates or certificate.proxies.covariates)
        covariate_columns: list[np.ndarray] = []
        for name in covariate_names:
            column = _coerce_aligned_vector(data_dict.get(name))
            if column is None or column.shape[0] != n_obs:
                return None
            covariate_columns.append(column)
        covariates = (
            np.column_stack(covariate_columns)
            if covariate_columns
            else np.empty((n_obs, 0), dtype=float)
        )

    finite_mask = (
        np.isfinite(outcome_vector)
        & np.isfinite(treatment_vector)
        & np.isfinite(z_proxy).all(axis=1)
        & np.isfinite(w_proxy).all(axis=1)
        & np.isfinite(covariates).all(axis=1)
    )
    binary_mask = np.isclose(treatment_vector, 0.0) | np.isclose(treatment_vector, 1.0)
    mask = finite_mask & binary_mask
    if int(np.sum(mask)) < 60:
        return None
    return {
        "outcome": outcome_vector[mask].astype(float),
        "treatment": treatment_vector[mask].astype(float),
        "covariates": covariates[mask].astype(float),
        "treatment_proxy": z_proxy[mask].astype(float),
        "outcome_proxy": w_proxy[mask].astype(float),
    }


def _derive_spatial_proximal_bridge_state(
    *,
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
    certificate: ProximalIdentificationCertificate,
) -> dict[str, Any] | None:
    if not data_dict:
        return None

    treatment_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, _treatment_candidate_keys(treatment))
    )
    outcome_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, _outcome_candidate_keys(outcome))
    )
    if treatment_vector is None or outcome_vector is None:
        return None
    n_obs = int(outcome_vector.shape[0])
    if treatment_vector.shape[0] != n_obs:
        return None

    z_proxy = _collect_proxy_matrix(
        data_dict=data_dict,
        direct_keys=("treatment_proxy",),
        proxy_variables=certificate.proxies.treatment_inducing,
        n_obs=n_obs,
    )
    w_proxy = _collect_proxy_matrix(
        data_dict=data_dict,
        direct_keys=("outcome_proxy",),
        proxy_variables=certificate.proxies.outcome_inducing,
        n_obs=n_obs,
    )
    if z_proxy is None or w_proxy is None:
        return None

    covariates = _coerce_aligned_covariates(data_dict.get("covariates"), n_obs=n_obs)
    if covariates is None:
        covariate_names = tuple(certificate.query.covariates or certificate.proxies.covariates)
        covariate_columns: list[np.ndarray] = []
        for name in covariate_names:
            column = _coerce_aligned_vector(data_dict.get(name))
            if column is None or column.shape[0] != n_obs:
                return None
            covariate_columns.append(column)
        covariates = (
            np.column_stack(covariate_columns)
            if covariate_columns
            else np.empty((n_obs, 0), dtype=float)
        )

    weight_matrix = _first_valid_square_matrix(
        data_dict,
        (
            "weight_matrix",
            "weights_matrix",
            "spatial_weights",
            "W",
            "adjacency_matrix",
            "adjacency",
        ),
        n_obs=n_obs,
    )
    if weight_matrix is None:
        return None
    weight_matrix_error = _first_valid_square_matrix(
        data_dict,
        (
            "weight_matrix_error",
            "weights_matrix_error",
            "spatial_weights_error",
            "M",
            "adjacency_matrix_error",
        ),
        n_obs=n_obs,
    )
    spatial_lag_covariates = _coerce_aligned_covariates(
        data_dict.get("spatial_lag_covariates"), n_obs=n_obs
    )
    spatial_lag_treatment = _coerce_aligned_vector(data_dict.get("spatial_lag_treatment"))
    if spatial_lag_treatment is not None and spatial_lag_treatment.shape[0] != n_obs:
        return None

    finite_mask = (
        np.isfinite(outcome_vector)
        & np.isfinite(treatment_vector)
        & np.isfinite(covariates).all(axis=1)
        & np.isfinite(z_proxy).all(axis=1)
        & np.isfinite(w_proxy).all(axis=1)
        & np.isfinite(weight_matrix).all(axis=1)
        & np.isfinite(weight_matrix).all(axis=0)
    )
    if spatial_lag_covariates is not None:
        finite_mask = finite_mask & np.isfinite(spatial_lag_covariates).all(axis=1)
    if spatial_lag_treatment is not None:
        finite_mask = finite_mask & np.isfinite(spatial_lag_treatment)
    if weight_matrix_error is not None:
        finite_mask = (
            finite_mask
            & np.isfinite(weight_matrix_error).all(axis=1)
            & np.isfinite(weight_matrix_error).all(axis=0)
        )
    binary_mask = np.isclose(treatment_vector, 0.0) | np.isclose(treatment_vector, 1.0)
    mask = finite_mask & binary_mask
    if int(np.sum(mask)) < 80:
        return None

    model_family = str(
        data_dict.get("model_family") or certificate.metadata.get("spatial_model_family") or "sdm"
    ).lower()
    return {
        "outcome": outcome_vector[mask].astype(float),
        "treatment": treatment_vector[mask].astype(float),
        "covariates": covariates[mask].astype(float),
        "treatment_proxy": z_proxy[mask].astype(float),
        "outcome_proxy": w_proxy[mask].astype(float),
        "weight_matrix": weight_matrix[np.ix_(mask, mask)].astype(float),
        "weight_matrix_error": (
            None
            if weight_matrix_error is None
            else weight_matrix_error[np.ix_(mask, mask)].astype(float)
        ),
        "spatial_lag_covariates": (
            None if spatial_lag_covariates is None else spatial_lag_covariates[mask].astype(float)
        ),
        "spatial_lag_treatment": (
            None if spatial_lag_treatment is None else spatial_lag_treatment[mask].astype(float)
        ),
        "spatial_proxy_specs": tuple(certificate.proxies.spatial_proxy_specs),
        "model_family": model_family,
        "metadata": {
            "weight_matrix_refs": list(certificate.metadata.get("weight_matrix_refs", [])),
            "spatial_proxy_spec": list(certificate.metadata.get("spatial_proxy_spec", [])),
        },
    }


def _derive_proximal_mediation_state(
    *,
    data_dict: dict[str, Any] | None,
    certificate: ProximalMediationCertificate,
) -> dict[str, np.ndarray] | None:
    """Build the proximal mediation estimator state from certificate variable roles."""

    if not data_dict:
        return None

    treatment_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, ("treatment", certificate.query.treatment))
    )
    outcome_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, ("outcome", certificate.query.outcome))
    )
    mediator_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, ("mediator", certificate.query.mediator))
    )
    z_proxy = _coerce_aligned_vector(
        _first_non_null(
            data_dict,
            ("treatment_proxy", *certificate.variable_roles.get("Z", ())),
        )
    )
    w_proxy = _coerce_aligned_vector(
        _first_non_null(
            data_dict,
            ("outcome_proxy", *certificate.variable_roles.get("W", ())),
        )
    )
    if (
        treatment_vector is None
        or outcome_vector is None
        or mediator_vector is None
        or z_proxy is None
        or w_proxy is None
    ):
        return None
    n_obs = int(outcome_vector.shape[0])
    if any(
        vector.shape[0] != n_obs for vector in (treatment_vector, mediator_vector, z_proxy, w_proxy)
    ):
        return None

    covariates = _coerce_aligned_covariates(data_dict.get("covariates"), n_obs=n_obs)
    if covariates is None:
        covariate_names = tuple(certificate.variable_roles.get("X", ()))
        covariate_columns: list[np.ndarray] = []
        for name in covariate_names:
            column = _coerce_aligned_vector(data_dict.get(name))
            if column is None or column.shape[0] != n_obs:
                return None
            covariate_columns.append(column)
        covariates = (
            np.column_stack(covariate_columns)
            if covariate_columns
            else np.empty((n_obs, 0), dtype=float)
        )

    finite_mask = (
        np.isfinite(outcome_vector)
        & np.isfinite(treatment_vector)
        & np.isfinite(mediator_vector)
        & np.isfinite(z_proxy)
        & np.isfinite(w_proxy)
        & np.isfinite(covariates).all(axis=1)
    )
    binary_mask = np.isclose(treatment_vector, 0.0) | np.isclose(treatment_vector, 1.0)
    mask = finite_mask & binary_mask
    if int(np.sum(mask)) < 60:
        return None
    return {
        "outcome": outcome_vector[mask].astype(float),
        "treatment": treatment_vector[mask].astype(float),
        "mediator": mediator_vector[mask].astype(float),
        "covariates": covariates[mask].astype(float),
        "treatment_proxy": z_proxy[mask].astype(float),
        "outcome_proxy": w_proxy[mask].astype(float),
    }


def _resolve_graph_outcome_support(
    graph: CausalGraphModel,
    *,
    outcome: str,
) -> tuple[float, float] | None:
    metadata = dict(graph.metadata or {})
    raw = metadata.get("outcome_support")
    candidate: Any = None
    if isinstance(raw, dict):
        candidate = raw.get(outcome)
    elif raw is not None:
        candidate = raw
    if not isinstance(candidate, (tuple, list)) or len(candidate) != 2:
        return None
    try:
        lower = float(candidate[0])
        upper = float(candidate[1])
    except (TypeError, ValueError):
        return None
    if not np.isfinite(lower) or not np.isfinite(upper) or lower >= upper:
        return None
    return (lower, upper)


def _infer_proximal_path_target(
    *,
    treatment: str,
    mediator: str,
    outcome: str,
    intervention: PathIntervention,
) -> str:
    """Classify the requested path policy as NDE, NIE, or generic psi."""

    direct_path = (treatment, outcome)

    def _uses_mediator(path: tuple[str, ...]) -> bool:
        return mediator in path[1:-1]

    active_uses_mediator = any(_uses_mediator(path) for path in intervention.active_paths)
    frozen_uses_mediator = any(_uses_mediator(path) for path in intervention.frozen_paths)
    active_has_direct = direct_path in intervention.active_paths
    frozen_has_direct = direct_path in intervention.frozen_paths

    if active_uses_mediator and frozen_has_direct:
        return "nie"
    if active_has_direct and frozen_uses_mediator:
        return "nde"
    return "psi"


def _float_metrics_from_mapping(values: dict[str, Any] | None) -> dict[str, float]:
    """Best-effort float extraction for readiness metrics."""
    metrics: dict[str, float] = {}
    for key, value in (values or {}).items():
        try:
            metrics[key] = float(value)
        except (TypeError, ValueError):
            continue
    return metrics


def _unknown_data_readiness_report(
    *,
    sample_size: int | None,
    fallback_data_available: bool,
    reason: str,
    metrics: dict[str, float] | None = None,
) -> DataReadinessReport:
    """Construct a fail-closed readiness artifact when verification cannot complete."""
    resolved_metrics = dict(metrics or {})
    if sample_size is not None:
        resolved_metrics.setdefault("sample_size", float(sample_size))
    return DataReadinessReport(
        decision="unknown",
        can_compile_estimation=False,
        can_run_estimation=False,
        sample_size=sample_size,
        measurement_quality="unknown",
        fallback_data_available=fallback_data_available,
        blocking_reasons=[reason],
        warnings=["measurement_quality_unknown"],
        metrics=resolved_metrics,
    )


def _ensure_readiness_registry(registry: Any) -> Any | None:
    """Resolve a registry instance and lazily register the causal catalog when needed."""
    if registry is not None:
        return registry
    try:
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            register_causal_methods,
        )
        from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
        from polisyos.foundry.methods.selection.registry import MethodRegistry
    except Exception:
        return None

    resolved_registry = MethodRegistry.get_instance()
    try:
        for method_class in register_causal_methods():
            try:
                resolved_registry.register(method_class)
            except MethodAlreadyRegisteredError:
                continue
    except Exception:
        return None
    return resolved_registry


def _coerce_numeric_matrix(value: Any) -> np.ndarray | None:
    """Convert arrays/lists into a finite 2D float matrix when possible."""
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.size == 0:
        return None
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    elif arr.ndim > 2:
        try:
            arr = arr.reshape(arr.shape[0], -1)
        except Exception:
            return None
    finite_mask = np.isfinite(arr).all(axis=1)
    if not finite_mask.any():
        return None
    arr = arr[finite_mask]
    return arr if arr.size > 0 else None


def _coerce_binary_vector(value: Any) -> np.ndarray | None:
    """Convert treatment-like inputs into a finite binary vector when possible."""
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float).reshape(-1)
    except Exception:
        return None
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    unique = np.unique(finite)
    if unique.size == 1:
        if np.isclose(unique[0], 0.0) or np.isclose(unique[0], 1.0):
            return finite.astype(float)
        return None
    if unique.size > 2 or not np.all(np.isclose(unique, 0.0) | np.isclose(unique, 1.0)):
        return None
    return finite.astype(float)


def _align_numeric_rows(
    matrix: np.ndarray | None,
    vector: np.ndarray | None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Align a covariate matrix and treatment vector on shared finite observations."""
    if matrix is None or vector is None:
        return None, None
    if matrix.shape[0] != vector.shape[0]:
        return None, None
    finite_mask = np.isfinite(vector) & np.isfinite(matrix).all(axis=1)
    if not finite_mask.any():
        return None, None
    aligned_matrix = matrix[finite_mask]
    aligned_vector = vector[finite_mask]
    if aligned_matrix.shape[0] == 0 or aligned_vector.size == 0:
        return None, None
    return aligned_matrix, aligned_vector


def _treatment_candidate_keys(
    treatment: str | frozenset[str],
) -> tuple[str, ...]:
    """Return likely treatment keys for direct-wrapper payloads."""
    treatment_name = _singleton_query_name(treatment, "treatment")
    candidates = [
        treatment_name,
        "treatment",
        "protected",
    ]
    return tuple(str(candidate) for candidate in candidates if candidate)


def _outcome_candidate_keys(
    outcome: str | frozenset[str],
) -> tuple[str, ...]:
    """Return likely outcome keys for direct-wrapper payloads."""
    outcome_name = _singleton_query_name(outcome, "outcome")
    candidates = [outcome_name, "outcome"]
    return tuple(str(candidate) for candidate in candidates if candidate)


def _first_non_null(
    data_dict: dict[str, Any] | None,
    candidate_keys: tuple[str, ...],
) -> Any | None:
    """Return the first non-null payload entry among candidate keys."""
    if not data_dict:
        return None
    for key in candidate_keys:
        value = data_dict.get(key)
        if value is not None:
            return value
    return None


def _derive_direct_positivity_state(
    *,
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> dict[str, np.ndarray] | None:
    """Build the positivity diagnostic state for direct estimator wrappers."""
    if not data_dict:
        return None

    treatment_vector = _coerce_binary_vector(
        _first_non_null(data_dict, _treatment_candidate_keys(treatment))
    )
    if treatment_vector is None:
        treatment_sequence = data_dict.get("treatment_sequence")
        if treatment_sequence is not None:
            try:
                treatment_vector = _coerce_binary_vector(
                    np.asarray(treatment_sequence, dtype=float).reshape(-1)
                )
            except Exception:
                treatment_vector = None
    if treatment_vector is None:
        return None

    candidate_matrices = [
        _coerce_numeric_matrix(data_dict.get("covariates")),
        _coerce_numeric_matrix(data_dict.get("confounders")),
        _coerce_numeric_matrix(data_dict.get("covariate_sequence")),
    ]

    outcome_matrix = _coerce_numeric_matrix(
        _first_non_null(data_dict, _outcome_candidate_keys(outcome))
    )
    if outcome_matrix is not None:
        time_treatment = data_dict.get("time_treatment")
        if outcome_matrix.ndim == 2 and outcome_matrix.shape[1] > 1:
            try:
                boundary = (
                    int(time_treatment)
                    if time_treatment is not None
                    else outcome_matrix.shape[1] - 1
                )
            except Exception:
                boundary = outcome_matrix.shape[1] - 1
            boundary = max(1, min(boundary, outcome_matrix.shape[1]))
            candidate_matrices.append(outcome_matrix[:, :boundary])

    for matrix in candidate_matrices:
        aligned_matrix, aligned_vector = _align_numeric_rows(matrix, treatment_vector)
        if aligned_matrix is not None and aligned_vector is not None:
            return {
                "X": aligned_matrix,
                "treatment": aligned_vector,
            }

    intercept = np.zeros((treatment_vector.shape[0], 1), dtype=float)
    aligned_matrix, aligned_vector = _align_numeric_rows(intercept, treatment_vector)
    if aligned_matrix is None or aligned_vector is None:
        return None
    return {
        "X": aligned_matrix,
        "treatment": aligned_vector,
    }


def _derive_direct_support_state(
    data_dict: dict[str, Any] | None,
) -> dict[str, np.ndarray] | None:
    """Build source/target covariate views when a direct wrapper carries them explicitly."""
    if not data_dict:
        return None
    source = _coerce_numeric_matrix(
        _first_non_null(
            data_dict,
            ("X_source", "source_covariates", "covariates_source"),
        )
    )
    target = _coerce_numeric_matrix(
        _first_non_null(
            data_dict,
            ("X_target", "target_covariates", "covariates_target"),
        )
    )
    if source is None or target is None:
        return None
    if source.shape[1] != target.shape[1]:
        return None
    return {
        "X_source": source,
        "X_target": target,
    }


def _execute_readiness_diagnostic(
    *,
    registry: Any,
    fqn_full: str,
    state: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve and execute a diagnostic method, returning its raw output."""
    method_cls = _resolve_method_class(registry, fqn_full)
    output = method_cls.pure_step(state, params or {})
    return output if isinstance(output, dict) else None


def _run_direct_readiness_diagnostics(
    *,
    registry: Any,
    data: Any,
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run concrete diagnostics for direct wrappers and report verification status."""
    del data
    diagnostic_outputs: dict[str, Any] = {}
    status: dict[str, Any] = {
        "positivity": "positivity_inputs_unavailable",
        "support": "not_requested",
        "support_required": False,
    }

    positivity_state = _derive_direct_positivity_state(
        data_dict=data_dict,
        treatment=treatment,
        outcome=outcome,
    )
    if positivity_state is not None:
        try:
            positivity_result = _execute_readiness_diagnostic(
                registry=registry,
                fqn_full="causal.diagnostics.positivity_check@1.0.0",
                state=positivity_state,
            )
        except Exception:
            positivity_result = None
            status["positivity"] = "positivity_diagnostic_failed"
        if positivity_result is not None:
            diagnostic_outputs["direct:positivity"] = positivity_result
            positivity_payload = positivity_result.get("result")
            if isinstance(positivity_payload, dict) and "passes_positivity" in positivity_payload:
                status["positivity"] = "verified"
            else:
                status["positivity"] = "positivity_diagnostic_invalid"

    support_state = _derive_direct_support_state(data_dict)
    if support_state is not None:
        status["support_required"] = True
        try:
            support_result = _execute_readiness_diagnostic(
                registry=registry,
                fqn_full="causal.diagnostics.support_mismatch@1.0.0",
                state=support_state,
            )
        except Exception:
            support_result = None
            status["support"] = "support_diagnostic_failed"
        if support_result is not None:
            diagnostic_outputs["direct:support"] = support_result
            support_payload = support_result.get("result")
            if isinstance(support_payload, dict) and "passes_support_check" in support_payload:
                status["support"] = "verified"
            else:
                status["support"] = "support_diagnostic_invalid"

    return diagnostic_outputs, status


def _extract_readiness_diagnostics(
    node_outputs: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Extract positivity/support diagnostics from executor node outputs."""
    positivity: dict[str, Any] | None = None
    support: dict[str, Any] | None = None
    for output in (node_outputs or {}).values():
        if not isinstance(output, dict):
            continue
        result_dict = output.get("result")
        if isinstance(result_dict, dict):
            if positivity is None and "passes_positivity" in result_dict:
                positivity = result_dict
            if support is None and (
                "passes_support_check" in result_dict or "support_mismatch_fraction" in result_dict
            ):
                support = result_dict
        if positivity is not None and support is not None:
            break
    return positivity, support


def _resolve_survey_quality_inputs(
    data_dict: dict[str, Any] | None,
    *,
    artifact_store: Any | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(data_dict, dict):
        return None, None

    search_spaces: list[dict[str, Any]] = [data_dict]
    for nested_key in ("metadata", "dataset_metadata", "source_metadata", "data_quality_report"):
        nested = data_dict.get(nested_key)
        if isinstance(nested, dict):
            search_spaces.append(nested)
            nested_meta = nested.get("metadata")
            if isinstance(nested_meta, dict):
                search_spaces.append(nested_meta)

    for payload_space in search_spaces:
        payload = payload_space.get("survey_quality_certificate")
        if isinstance(payload, dict):
            for ref_space in (payload_space, *search_spaces):
                ref_payload = ref_space.get("survey_quality_certificate_ref")
                if isinstance(ref_payload, dict):
                    return payload, ref_payload
            return payload, None

    ref_payload = None
    for payload_space in search_spaces:
        candidate = payload_space.get("survey_quality_certificate_ref")
        if isinstance(candidate, dict):
            ref_payload = candidate
            break
    if isinstance(ref_payload, dict) and artifact_store is not None:
        try:
            ref = SurveyQualityCertificateRef.model_validate(ref_payload)
            certificate = load_survey_quality_certificate(
                artifact_store,
                ref,
            )
            return certificate.model_dump(mode="json"), ref.model_dump(mode="json")
        except Exception:
            return None, ref_payload
    return None, ref_payload if isinstance(ref_payload, dict) else None


def _apply_government_phase1_requirements(
    report: DataReadinessReport,
    *,
    government_dataset: bool,
    survey_quality_certificate_present: bool,
    phase1_gate_summary: Any | None,
) -> DataReadinessReport:
    if not government_dataset:
        return report

    blocking_reasons = list(report.blocking_reasons)
    if not survey_quality_certificate_present:
        blocking_reasons.append("survey_quality_certificate_missing_for_government_dataset")
    if phase1_gate_summary is not None:
        blocking_reasons.extend(
            item
            for item in getattr(phase1_gate_summary, "blocking_reasons", ())
            if item not in blocking_reasons
        )
    normalized_blocking_reasons: list[str] = []
    seen: set[str] = set()
    for item in blocking_reasons:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            normalized_blocking_reasons.append(text)
    if not normalized_blocking_reasons:
        return report
    return report.model_copy(
        update={
            "decision": "block",
            "can_compile_estimation": False,
            "can_run_estimation": False,
            "blocking_reasons": normalized_blocking_reasons,
        }
    )


def _build_postrun_readiness_report(
    *,
    node_outputs: dict[str, Any] | None,
    sample_size: int | None,
    fallback_data_available: bool,
    recoverability_certificate: dict[str, Any] | None = None,
    missingness_assessment: Any | None = None,
    survey_quality_certificate: Any | None = None,
    survey_quality_certificate_ref: Any | None = None,
    phase1_gate_summary: Any | None = None,
    government_dataset: bool = False,
) -> DataReadinessReport | None:
    """Build a richer readiness report from executor diagnostics when available."""
    positivity, support = _extract_readiness_diagnostics(node_outputs)
    if (
        positivity is None
        and support is None
        and sample_size is None
        and missingness_assessment is None
    ):
        return None
    report = build_data_readiness_report(
        positivity=positivity,
        support_mismatch=support,
        sample_size=sample_size,
        measurement_quality="unknown",
        fallback_data_available=fallback_data_available,
        recoverability_certificate=recoverability_certificate,
        missingness_assessment=missingness_assessment,
        survey_quality_certificate=survey_quality_certificate,
        survey_quality_certificate_ref=survey_quality_certificate_ref,
        phase1_gate_summary=phase1_gate_summary,
    )
    return _apply_government_phase1_requirements(
        report,
        government_dataset=government_dataset,
        survey_quality_certificate_present=survey_quality_certificate is not None,
        phase1_gate_summary=phase1_gate_summary,
    )


def _resolve_missingness_assessment(
    *,
    graph: Any | None,
    data_dict: dict[str, Any] | None,
    mgraph_meta: Any | None = None,
    query_variables: frozenset[str] | None = None,
    treatment: Any | None = None,
    outcome: Any | None = None,
) -> Any | None:
    """Best-effort administrative missingness assessment for M-graphs."""
    if graph is None:
        return None
    try:
        from polisyos.foundry.methods.catalog.causal.missing_data import (
            assess_administrative_missingness,
        )
        from polisyos.ir.analytics.causal_graph import GraphType
    except Exception:
        return None

    if getattr(graph, "graph_type", None) is not GraphType.MGRAPH:
        return None

    try:
        return assess_administrative_missingness(
            graph=graph,
            data=data_dict,
            mgraph_meta=mgraph_meta,
            query_variables=query_variables,
            treatment=treatment,
            outcome=outcome,
        )
    except Exception as exc:
        logger.warning("Failed to build missingness assessment for readiness: %s", exc)
        return None


def _extract_recoverability_summary(payload: Any) -> dict[str, Any] | None:
    """Extract a compact recoverability summary from results or proof artifacts."""

    def _compact(candidate: dict[str, Any]) -> dict[str, Any]:
        if "recoverability" in candidate and isinstance(candidate["recoverability"], dict):
            return _compact(dict(candidate["recoverability"]))
        if "status" not in candidate:
            return candidate
        blocking = candidate.get("blocking_r_nodes")
        repairs = candidate.get("minimal_repair_sets")
        warnings = candidate.get("warnings")
        return {
            "schema_version": candidate.get("schema_version", "1.0"),
            "target_query": candidate.get("target_query"),
            "mgraph_fingerprint": candidate.get("mgraph_fingerprint"),
            "status": candidate.get("status"),
            "recovery_scope": candidate.get("recovery_scope"),
            "blocking_r_nodes": list(blocking or []),
            "blocking_r_nodes_count": len(blocking or []),
            "minimal_repair_sets": list(repairs or []),
            "minimal_repair_set_count": len(repairs or []),
            "recommended_estimator_family": candidate.get("recommended_estimator_family"),
            "computable_functionals": list(candidate.get("computable_functionals") or []),
            "warnings": list(warnings or []),
            "completeness_regime": candidate.get("completeness_regime"),
            "theorem_family": candidate.get("theorem_family"),
        }

    candidates: list[Any] = [payload]
    if isinstance(payload, dict):
        metadata = payload.get("metadata")
        if metadata is not None:
            candidates.append(metadata)
        diagnostics = payload.get("quantitative_diagnostics")
        if diagnostics is not None:
            candidates.append(diagnostics)
    else:
        metadata = getattr(payload, "metadata", None)
        if metadata is not None:
            candidates.append(metadata)
        diagnostics = getattr(payload, "quantitative_diagnostics", None)
        if diagnostics is not None:
            candidates.append(diagnostics)

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if isinstance(candidate.get("recoverability_certificate"), dict):
            return _compact(dict(candidate["recoverability_certificate"]))
        if isinstance(candidate.get("recoverability"), dict):
            return _compact(dict(candidate["recoverability"]))
        if isinstance(candidate.get("joint_decision"), dict):
            return _compact(dict(candidate["joint_decision"]))
    return None


def _query_str_from_io(
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> str:
    treatment_name = _singleton_query_name(treatment, "treatment") or "treatment"
    outcome_name = _singleton_query_name(outcome, "outcome") or "outcome"
    return f"P({outcome_name}|do({treatment_name}))"


def _coerce_mapping_like_data(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        return dict(data)
    model_dump = getattr(data, "model_dump", None)
    if callable(model_dump):
        try:
            payload = model_dump(mode="json")
            if isinstance(payload, dict):
                return payload
        except Exception:
            try:
                payload = model_dump()
                if isinstance(payload, dict):
                    return payload
            except Exception:
                return None
    raw_dict = getattr(data, "__dict__", None)
    if isinstance(raw_dict, dict):
        return dict(raw_dict)
    return None


def _make_dummy_identification_result(
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> IdentificationResult:
    """Build a minimal IdentificationResult for audit when identification failed."""
    tx = frozenset({treatment} if isinstance(treatment, str) else treatment)
    oy = frozenset({outcome} if isinstance(outcome, str) else outcome)
    tx_terms = ",".join(sorted(tx))
    oy_terms = ",".join(sorted(oy))
    return IdentificationResult(
        status=IdentificationStatus.HEDGE_FOUND,
        estimand_ast=None,
        hedge_certificate=None,
        trace=[],
        required_distributions=[],
        query_str=f"P({oy_terms}|do({tx_terms}))",
    )


def _identification_query_str(identification_result: IdentificationResult) -> str:
    """Recover a readable query string for audit and diagnostics."""
    if identification_result.query_str:
        return identification_result.query_str
    estimand = identification_result.estimand_ast
    if estimand is not None and getattr(estimand, "query_str", ""):
        return str(estimand.query_str)
    return ""


def _attach_proof_composability_certificate(
    *,
    store: ArtifactStore,
    proof_payload: ProofBundle,
    witness_index: Any,
    graph: CausalGraphModel,
    query_str: str,
    graph_fingerprint: str,
) -> ProofBundle:
    """Persist and attach the Stage 2.2 replay certificate for an audited proof."""

    metadata = dict(proof_payload.metadata or {})
    source_fragment_id = _proof_composability_source_fragment_id(
        proof_payload,
        graph_fingerprint=graph_fingerprint,
    )
    composed_graph_ref = proof_payload.graph_ref or graph_fingerprint or None
    interface_vars = _proof_composability_interface_vars(metadata)
    proof_trace_hash = _proof_composability_trace_hash(proof_payload)
    certificate = check_proof_trace_composability(
        witness_index=witness_index,
        composed_graph=graph,
        source_fragment_id=source_fragment_id,
        checked_query=query_str or str(proof_payload.query_ref or ""),
        composed_graph_ref=composed_graph_ref,
        proof_trace_ref=proof_payload.proof_trace_ref,
        witness_index_ref=proof_payload.witness_index_ref,
        interface_vars=interface_vars,
        invalidated_by_graph_hashes=tuple(proof_payload.invalidated_by_graph_hashes),
        metadata={
            "theorem_family": proof_payload.theorem_family,
            "proof_trace_hash": proof_trace_hash,
            "source": "CausalEngine.audit",
        },
    )
    inputs = [
        InputRef(artifact_id=ref.artifact_id, role=role)
        for ref, role in (
            (proof_payload.proof_trace_ref, "proof_trace"),
            (proof_payload.witness_index_ref, "proof_witness_index"),
        )
        if ref is not None
    ]
    certificate_ref = persist_proof_composability_certificate(
        store,
        certificate,
        inputs=inputs or None,
    )
    return attach_proof_composability_to_proof_bundle(
        proof_payload,
        certificate_ref,
        certificate,
    )


def _proof_composability_source_fragment_id(
    proof_payload: ProofBundle,
    *,
    graph_fingerprint: str,
) -> str:
    metadata = dict(proof_payload.metadata or {})
    for candidate in (
        proof_payload.graph_ref,
        metadata.get("source_fragment_id"),
        metadata.get("fragment_id"),
        graph_fingerprint,
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    return "unknown_source_fragment"


def _proof_composability_interface_vars(metadata: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[Any] = [
        metadata.get("interface_vars"),
        metadata.get("interface_variables"),
    ]
    for key in ("composition_certificate", "composition", "graph_composition"):
        payload = metadata.get(key)
        if isinstance(payload, dict):
            candidates.extend(
                [
                    payload.get("interface_vars"),
                    payload.get("interface_variables"),
                    payload.get("preserved_interface_vars"),
                ]
            )
    output: set[str] = set()
    for value in candidates:
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple, set, frozenset)):
            items = list(value)
        else:
            continue
        for item in items:
            text = str(item).strip()
            if text:
                output.add(text)
    return tuple(sorted(output))


def _proof_composability_trace_hash(proof_payload: ProofBundle) -> str:
    if proof_payload.proof_trace_ref is not None:
        return str(proof_payload.proof_trace_ref.artifact_id)
    if proof_payload.proof_trace:
        return _fingerprint(list(proof_payload.proof_trace))
    metadata_trace = proof_payload.metadata.get("proof_trace")
    if isinstance(metadata_trace, (list, tuple)):
        return _fingerprint(list(metadata_trace))
    return ""


def _prepare_executor_state(node: ExecutorNode, state: dict[str, Any]) -> Any:
    """Adapt raw engine state to method-specific payload contracts when needed."""
    if node.method_fqn == "causal.structural.hybrid_scm_fit":
        return _build_scm_fit_payload(state, node.params)
    if node.method_fqn == "causal.structural.twin_network_query":
        return _build_twin_network_payload(state, node.params)
    if node.method_fqn == "causal.diagnostics.positivity_check":
        return _build_positivity_diagnostic_payload(state)
    if node.method_fqn == "causal.diagnostics.support_mismatch":
        return _build_support_mismatch_payload(state)
    return state


def _build_positivity_diagnostic_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Provide the slot names expected by positivity diagnostics."""
    payload = dict(state)
    if "X" not in payload:
        if "covariates" in state:
            payload["X"] = state["covariates"]
        elif "X_source" in state:
            payload["X"] = state["X_source"]
    if "treatment" not in payload:
        for candidate in ("T", "treatment_value"):
            if candidate in state:
                payload["treatment"] = state[candidate]
                break
    return payload


def _build_support_mismatch_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Provide source/target covariate matrices expected by support diagnostics."""
    payload = dict(state)
    if "X_source" not in payload:
        if "source_covariates" in state:
            payload["X_source"] = state["source_covariates"]
        elif "covariates" in state:
            payload["X_source"] = state["covariates"]
    if "X_target" not in payload:
        if "target_covariates" in state:
            payload["X_target"] = state["target_covariates"]
        elif "covariates" in state:
            payload["X_target"] = state["covariates"]
    return payload


def _build_scm_fit_payload(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Construct SCMFitData-compatible payload from columnar arrays."""
    graph = state.get("graph") or params.get("graph")
    if graph is None:
        raise ValueError("SCM fitting requires a graph in state or node params.")

    if "data" in state and "column_names" in state:
        payload = dict(state)
        payload.setdefault("graph", graph)
        return payload

    try:
        graph_model = (
            graph if isinstance(graph, CausalGraphModel) else CausalGraphModel.model_validate(graph)
        )
        graph_nodes = set(graph_model.nodes)
    except Exception:
        graph_nodes = set()

    column_names: list[str] = []
    columns: list[np.ndarray] = []
    expected_len: int | None = None
    for key, raw in state.items():
        if key.startswith("__") or key in {
            "graph",
            "scm_spec",
            "factual_condition",
            "treatment_variable",
            "outcome_variable",
            "factual_treatment_value",
            "counterfactual_treatment_value",
            "n_samples",
            "metadata",
        }:
            continue
        if graph_nodes and key not in graph_nodes:
            continue
        try:
            arr = np.asarray(raw, dtype=float).reshape(-1)
        except Exception:
            continue
        if arr.size < 2 or not np.isfinite(arr).all():
            continue
        if expected_len is None:
            expected_len = int(arr.size)
        if int(arr.size) != expected_len:
            continue
        column_names.append(str(key))
        columns.append(arr)

    if not columns:
        raise ValueError("Could not build SCM fitting payload from the provided data_dict.")

    payload: dict[str, Any] = {
        "data": np.column_stack(columns),
        "column_names": column_names,
        "graph": graph,
        "metadata": dict(state.get("metadata", {})),
    }
    for key in ("graph_ref", "literature_priors", "skg_snapshot_ref"):
        if key in state:
            payload[key] = state[key]
    return payload


def _build_twin_network_payload(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Construct TwinNetworkQueryData-compatible payload from engine state."""
    payload = dict(state)
    if "scm_spec" not in payload:
        from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit

        scm_payload = _build_scm_fit_payload(state, params)
        payload.update(HybridSCMFit.pure_step(scm_payload, {}))

    scm_spec = payload["scm_spec"]
    treatment_variable = str(
        payload.get("treatment_variable") or params.get("treatment_variable") or ""
    )
    outcome_variable = str(payload.get("outcome_variable") or params.get("outcome_variable") or "")
    if not treatment_variable or not outcome_variable:
        raise ValueError("Twin-network execution requires treatment and outcome variables.")

    factual_condition = payload.get("factual_condition")
    if not isinstance(factual_condition, dict) or not factual_condition:
        factual_condition = _first_observed_condition(payload, scm_spec)

    factual_treatment_value = payload.get(
        "factual_treatment_value", params.get("factual_treatment_value")
    )
    if factual_treatment_value is None:
        factual_treatment_value = factual_condition.get(
            treatment_variable,
            _coerce_first_scalar(payload.get(treatment_variable), default=0.0),
        )

    counterfactual_treatment_value = payload.get(
        "counterfactual_treatment_value",
        params.get("counterfactual_treatment_value"),
    )
    if counterfactual_treatment_value is None:
        counterfactual_treatment_value = 1.0 if float(factual_treatment_value) != 1.0 else 0.0

    n_samples = int(payload.get("n_samples") or params.get("n_samples") or 2000)
    return {
        "scm_spec": scm_spec,
        "factual_condition": factual_condition,
        "treatment_variable": treatment_variable,
        "factual_treatment_value": float(factual_treatment_value),
        "counterfactual_treatment_value": float(counterfactual_treatment_value),
        "outcome_variable": outcome_variable,
        "n_samples": n_samples,
        "metadata": {
            "query_type": params.get("query_type", "counterfactual"),
        },
    }


def _first_observed_condition(state: dict[str, Any], scm_spec: Any) -> dict[str, float]:
    """Use the first observed row as the factual world when none is supplied."""
    try:
        nodes = set(scm_spec.graph.nodes)
    except Exception:
        nodes = set()

    condition: dict[str, float] = {}
    for key, raw in state.items():
        if nodes and key not in nodes:
            continue
        value = _coerce_first_scalar(raw)
        if value is not None:
            condition[str(key)] = value
    return condition


def _coerce_first_scalar(value: Any, default: float | None = None) -> float | None:
    """Best-effort conversion of scalars or vectors to a representative float."""
    if value is None:
        return default
    try:
        if np.isscalar(value):
            casted = float(value)
            return casted if np.isfinite(casted) else default
        arr = np.asarray(value, dtype=float).reshape(-1)
    except Exception:
        return default
    if arr.size == 0 or not np.isfinite(arr[0]):
        return default
    return float(arr[0])


def _is_binary_treatment_vector(values: np.ndarray) -> bool:
    """Return True when values look like a binary treatment assignment."""
    if values.size == 0:
        return False
    unique = np.unique(values[np.isfinite(values)])
    if unique.size != 2:
        return False
    return bool(np.all(np.isclose(unique, 0.0) | np.isclose(unique, 1.0)))


def _looks_discrete_vector(values: np.ndarray, *, max_levels: int) -> bool:
    """Heuristic support-size check used to keep interactive bounds tractable."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return False
    return int(np.unique(finite).size) <= int(max_levels)


def _singleton_query_name(
    value: str | frozenset[str],
    fallback_name: str,
) -> str | None:
    """Return the single variable name from a scalar-or-set query argument."""
    if isinstance(value, str):
        return value
    if len(value) != 1:
        return None
    return next(iter(value), fallback_name)


def _candidate_linear_instruments(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> tuple[str, ...]:
    """Find observed IV candidates that satisfy simple graph-based exclusion checks."""
    directed_edges = {
        (edge.src, edge.dst)
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
    }
    directed_children: dict[str, set[str]] = {}
    for src, dst in directed_edges:
        directed_children.setdefault(src, set()).add(dst)

    bidirected_pairs = {
        frozenset((edge.src, edge.dst))
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
    }
    parents_of_treatment = sorted(
        src for src, dst in directed_edges if dst == treatment and src not in {treatment, outcome}
    )

    candidates: list[str] = []
    for instrument in parents_of_treatment:
        if frozenset((instrument, treatment)) in bidirected_pairs:
            continue
        if frozenset((instrument, outcome)) in bidirected_pairs:
            continue
        if (instrument, outcome) in directed_edges:
            continue
        if _has_directed_path_avoiding(
            directed_children=directed_children,
            src=instrument,
            dst=outcome,
            forbidden={treatment},
        ):
            continue
        candidates.append(instrument)
    return tuple(candidates)


def _has_directed_path_avoiding(
    *,
    directed_children: dict[str, set[str]],
    src: str,
    dst: str,
    forbidden: set[str],
) -> bool:
    """Return True if a directed path exists from src to dst without visiting forbidden nodes."""
    frontier = [src]
    seen = {src}
    while frontier:
        current = frontier.pop()
        for child in directed_children.get(current, ()):
            if child in forbidden or child in seen:
                continue
            if child == dst:
                return True
            seen.add(child)
            frontier.append(child)
    return False


def _extract_aligned_numeric_columns(
    *,
    data_dict: dict[str, Any],
    variable_names: tuple[str, ...],
) -> dict[str, np.ndarray] | None:
    """Extract numeric columns and align them on a common finite mask."""
    arrays: dict[str, np.ndarray] = {}
    expected_len: int | None = None

    for index, name in enumerate(variable_names):
        candidates = [data_dict.get(name)]
        if index == 0:
            candidates.append(data_dict.get("outcome"))
        elif index == 1:
            candidates.extend((data_dict.get("treatment"), data_dict.get("protected")))
        elif len(variable_names) == 3:
            candidates.append(data_dict.get("instrument"))

        raw = next((candidate for candidate in candidates if candidate is not None), None)
        if raw is None:
            return None
        try:
            arr = np.asarray(raw, dtype=float).reshape(-1)
        except Exception:
            return None
        if expected_len is None:
            expected_len = int(arr.size)
        if int(arr.size) != expected_len or arr.size == 0:
            return None
        arrays[name] = arr

    finite_mask = np.ones(expected_len or 0, dtype=bool)
    for arr in arrays.values():
        finite_mask &= np.isfinite(arr)
    if not finite_mask.any():
        return None
    return {name: arr[finite_mask] for name, arr in arrays.items()}


def _linear_iv_effect(
    *,
    y: np.ndarray,
    t: np.ndarray,
    instruments: np.ndarray,
) -> tuple[float | None, float | None, dict[str, Any]]:
    """Estimate a linear-IV rescue via Wald/2SLS using observed instruments."""
    n_obs = int(y.size)
    if n_obs != int(t.size) or n_obs != int(instruments.shape[0]) or n_obs < 5:
        return None, None, {"failure_reason": "insufficient or misaligned observations"}

    z = np.column_stack([np.ones(n_obs), instruments])
    x = np.column_stack([np.ones(n_obs), t])
    if np.linalg.matrix_rank(z) < z.shape[1]:
        return None, None, {"failure_reason": "instrument matrix is rank-deficient"}

    ztz_inv = np.linalg.pinv(z.T @ z)
    pz = z @ ztz_inv @ z.T
    xt_pz_x = x.T @ pz @ x
    if np.linalg.matrix_rank(xt_pz_x) < x.shape[1]:
        return None, None, {"failure_reason": "projected treatment design is rank-deficient"}

    beta = np.linalg.pinv(xt_pz_x) @ (x.T @ pz @ y)
    estimate = float(beta[1])
    if not np.isfinite(estimate):
        return None, None, {"failure_reason": "non-finite IV estimate"}

    residual = y - x @ beta
    sigma2 = float(np.dot(residual, residual) / max(n_obs - x.shape[1], 1))
    cov_beta = sigma2 * np.linalg.pinv(xt_pz_x)
    standard_error = float(np.sqrt(max(float(cov_beta[1, 1]), 0.0)))
    if not np.isfinite(standard_error):
        standard_error = None

    t_mean = float(np.mean(t))
    rss_reduced = float(np.dot(t - t_mean, t - t_mean))
    beta_fs = ztz_inv @ z.T @ t
    fs_residual = t - z @ beta_fs
    rss_full = float(np.dot(fs_residual, fs_residual))
    q = max(z.shape[1] - 1, 1)
    denom_df = max(n_obs - z.shape[1], 1)
    if rss_full <= 1e-12:
        first_stage_f = float("inf")
    else:
        explained = max(rss_reduced - rss_full, 0.0)
        first_stage_f = float((explained / q) / (rss_full / denom_df))

    return (
        estimate,
        standard_error,
        {
            "first_stage_f": first_stage_f,
            "n_obs": n_obs,
            "n_instruments": int(instruments.shape[1]),
        },
    )


def _linear_iv_rescue_result(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    data_dict: dict[str, Any],
) -> tuple[ParametricRescueResult | None, list[str]]:
    """Fast linear rescue when a graph-valid observed IV exists."""
    instruments = _candidate_linear_instruments(
        graph=graph,
        treatment=treatment,
        outcome=outcome,
    )
    if not instruments:
        return None, [
            "Linearity rescue: no graph-valid observed instrument was found for the direct IV/2SLS path."
        ]

    aligned = _extract_aligned_numeric_columns(
        data_dict=data_dict,
        variable_names=(outcome, treatment, *instruments),
    )
    if aligned is None:
        return None, [
            "Linearity rescue: treatment/outcome/instrument columns were missing, non-numeric, or misaligned for the IV/2SLS path."
        ]

    y = aligned[outcome]
    t = aligned[treatment]
    z = np.column_stack([aligned[instrument] for instrument in instruments])
    estimate, standard_error, diagnostics = _linear_iv_effect(y=y, t=t, instruments=z)
    if estimate is None:
        message = diagnostics.get(
            "failure_reason", "linear-IV solver could not produce a stable estimate"
        )
        return None, [f"Linearity rescue: IV/2SLS path failed: {message}."]

    method = "wald_iv" if len(instruments) == 1 else "linear_2sls"
    if len(instruments) == 1:
        estimand_formula = f"Cov({instruments[0]}, {outcome}) / Cov({instruments[0]}, {treatment})"
    else:
        joined = ", ".join(instruments)
        estimand_formula = f"2SLS({outcome} ~ {treatment} | {joined})"

    warnings = [
        "Assumption-dependent result: valid only under linear structural equations, instrument exogeneity, and exclusion restriction."
    ]
    first_stage_f = diagnostics.get("first_stage_f")
    if isinstance(first_stage_f, float) and first_stage_f < 10.0:
        warnings.append(
            "Weak-instrument warning: first-stage F-statistic is below the conventional threshold of 10."
        )

    rescue = ParametricRescueResult(
        assumption="linearity",
        method=method,
        description="Point-identifying rescue under a linear SEM using a graph-validated observed instrument.",
        point_estimate=estimate,
        standard_error=standard_error,
        estimand_formula=estimand_formula,
        supporting_variables=tuple(instruments),
        diagnostics=diagnostics,
        warnings=tuple(warnings),
    )
    return rescue, [
        f"Added linearity rescue via {method} using instrument(s): {', '.join(instruments)}."
    ]


def _wright_path_tracing_rescue_result(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    data_dict: dict[str, Any],
) -> tuple[ParametricRescueResult | None, list[str]]:
    """General linear rescue via Wright/path-tracing covariance equations on an ancestor subgraph."""
    node_order, directed_edges, bidirected_edges, notes = _wright_subgraph_spec(
        graph=graph,
        treatment=treatment,
        outcome=outcome,
    )
    if node_order is None:
        return None, notes

    aligned = _extract_aligned_numeric_columns(
        data_dict=data_dict,
        variable_names=node_order,
    )
    if aligned is None:
        return None, [
            *notes,
            "Linearity rescue: ancestor-subgraph variables were missing, non-numeric, or misaligned for Wright/path tracing.",
        ]

    matrix = np.column_stack([aligned[name] for name in node_order])
    sample_cov = np.cov(matrix, rowvar=False, bias=True)
    solve = _solve_linear_path_system(
        node_order=node_order,
        directed_edges=directed_edges,
        bidirected_edges=bidirected_edges,
        sample_cov=sample_cov,
        treatment=treatment,
        outcome=outcome,
    )
    if solve is None:
        return None, [
            *notes,
            "Linearity rescue: Wright/path-tracing covariance equations were not stably identified on the ancestor subgraph.",
        ]

    effect, standard_error, diagnostics, formula = solve
    rescue = ParametricRescueResult(
        assumption="linearity",
        method="wright_path_tracing",
        description=(
            "Point-identifying rescue under a linear SEM using Wright/path-tracing covariance equations on the ancestor subgraph."
        ),
        point_estimate=effect,
        standard_error=standard_error,
        estimand_formula=formula,
        supporting_variables=node_order,
        diagnostics=diagnostics,
        warnings=(
            "Assumption-dependent result: valid only under linear structural equations and the specified mixed-graph error structure.",
            "Numerical Wright/path-tracing solve was accepted only after a stable multi-start covariance-equation fit; this is evidence of identification, not a symbolic proof.",
        ),
    )
    return rescue, [
        *notes,
        f"Added linearity rescue via wright_path_tracing on ancestor subgraph: {', '.join(node_order)}.",
    ]


def _wright_subgraph_spec(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> tuple[
    tuple[str, ...] | None, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...], list[str]
]:
    """Build the ancestor subgraph specification used by the general Wright solver."""
    directed_edges_all = tuple(
        (edge.src, edge.dst)
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
    )
    parent_map: dict[str, set[str]] = {}
    for src, dst in directed_edges_all:
        parent_map.setdefault(dst, set()).add(src)

    needed = {treatment, outcome}
    frontier = [treatment, outcome]
    while frontier:
        current = frontier.pop()
        for parent in parent_map.get(current, ()):
            if parent not in needed:
                needed.add(parent)
                frontier.append(parent)

    directed_edges = tuple(
        (src, dst) for src, dst in directed_edges_all if src in needed and dst in needed
    )
    bidirected_edges = tuple(
        tuple(sorted((edge.src, edge.dst)))
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW
        and edge.mark_dst is EdgeMark.ARROW
        and edge.src in needed
        and edge.dst in needed
    )
    bidirected_edges = tuple(dict.fromkeys(bidirected_edges))

    node_order = _topological_order_from_edges(tuple(sorted(needed)), directed_edges)
    if node_order is None:
        return (
            None,
            (),
            (),
            [
                "Linearity rescue: Wright/path tracing skipped because the ancestor subgraph is cyclic."
            ],
        )
    if len(node_order) > 6:
        return (
            None,
            (),
            (),
            [
                "Linearity rescue: Wright/path tracing skipped because the ancestor subgraph is larger than 6 observed nodes."
            ],
        )

    children = _children_from_directed_edges(directed_edges)
    paths = list(_enumerate_directed_paths(children, treatment, outcome))
    if not paths:
        return (
            None,
            (),
            (),
            [
                "Linearity rescue: Wright/path tracing skipped because there is no directed treatment-to-outcome path."
            ],
        )

    return node_order, directed_edges, bidirected_edges, []


def _topological_order_from_edges(
    nodes: tuple[str, ...],
    directed_edges: tuple[tuple[str, str], ...],
) -> tuple[str, ...] | None:
    """Topological order for a directed acyclic edge list."""
    incoming: dict[str, set[str]] = {node: set() for node in nodes}
    children: dict[str, set[str]] = {node: set() for node in nodes}
    for src, dst in directed_edges:
        incoming.setdefault(dst, set()).add(src)
        children.setdefault(src, set()).add(dst)

    ready = sorted(node for node in nodes if not incoming.get(node))
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(children.get(node, ())):
            parents = incoming.get(child)
            if parents is None:
                continue
            parents.discard(node)
            if not parents:
                ready.append(child)
        ready.sort()

    if len(order) != len(nodes):
        return None
    return tuple(order)


def _children_from_directed_edges(
    directed_edges: tuple[tuple[str, str], ...],
) -> dict[str, tuple[str, ...]]:
    """Materialize adjacency from a directed edge list."""
    children: dict[str, list[str]] = {}
    for src, dst in directed_edges:
        children.setdefault(src, []).append(dst)
    return {src: tuple(sorted(dsts)) for src, dsts in children.items()}


def _enumerate_directed_paths(
    children: dict[str, tuple[str, ...]],
    src: str,
    dst: str,
    prefix: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], ...]:
    """Enumerate simple directed paths in a DAG."""
    path = (*prefix, src)
    if src == dst:
        return (path,)
    paths: list[tuple[str, ...]] = []
    for child in children.get(src, ()):
        if child in path:
            continue
        paths.extend(_enumerate_directed_paths(children, child, dst, path))
    return tuple(paths)


def _solve_linear_path_system(
    *,
    node_order: tuple[str, ...],
    directed_edges: tuple[tuple[str, str], ...],
    bidirected_edges: tuple[tuple[str, str], ...],
    sample_cov: np.ndarray,
    treatment: str,
    outcome: str,
) -> tuple[float, float | None, dict[str, Any], str] | None:
    """Solve linear mixed-graph covariance equations and recover the total effect."""
    from scipy.optimize import least_squares

    n_nodes = len(node_order)
    index = {node: idx for idx, node in enumerate(node_order)}
    directed_names = tuple(f"b_{src}_{dst}" for src, dst in directed_edges)
    bidirected_names = tuple(f"w_{src}_{dst}" for src, dst in bidirected_edges)
    variance_names = tuple(f"psi_{node}" for node in node_order)
    n_unknown = len(directed_names) + len(bidirected_names) + len(variance_names)
    n_equations = n_nodes * (n_nodes + 1) // 2
    if n_unknown > n_equations or n_unknown > 18:
        return None

    tri_upper = np.triu_indices(n_nodes)
    observed = sample_cov[tri_upper]
    directed_offset = 0
    bidirected_offset = len(directed_edges)
    variance_offset = bidirected_offset + len(bidirected_edges)

    def unpack(theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        b = np.zeros((n_nodes, n_nodes), dtype=float)
        omega = np.zeros((n_nodes, n_nodes), dtype=float)
        for offset, (src, dst) in enumerate(directed_edges):
            b[index[src], index[dst]] = float(theta[directed_offset + offset])
        for offset, (src, dst) in enumerate(bidirected_edges):
            value = float(theta[bidirected_offset + offset])
            i, j = index[src], index[dst]
            omega[i, j] = value
            omega[j, i] = value
        for offset, node in enumerate(node_order):
            omega[index[node], index[node]] = float(theta[variance_offset + offset] ** 2 + 1e-6)
        return b, omega

    def residual(theta: np.ndarray) -> np.ndarray:
        b, omega = unpack(theta)
        try:
            transform = np.linalg.inv(np.eye(n_nodes) - b.T)
        except np.linalg.LinAlgError:
            return np.full(observed.shape, 1e6, dtype=float)
        sigma = transform @ omega @ transform.T
        if not np.all(np.isfinite(sigma)):
            return np.full(observed.shape, 1e6, dtype=float)
        return sigma[tri_upper] - observed

    starts = [np.zeros(n_unknown, dtype=float)]
    rng = np.random.default_rng(0)
    for scale in (0.05, 0.15, 0.3, 0.6):
        starts.append(rng.standard_normal(n_unknown) * scale)

    candidates: list[tuple[float, float, float | None, np.ndarray]] = []
    for start in starts:
        result = least_squares(residual, start, method="trf", max_nfev=4000)
        resid = residual(result.x)
        rel_resid = float(np.linalg.norm(resid) / max(np.linalg.norm(observed), 1e-8))
        if not np.isfinite(rel_resid) or rel_resid > 0.12:
            continue
        b, _ = unpack(result.x)
        total_effect = _linear_total_effect(b, node_order, treatment, outcome)
        if total_effect is None or not np.isfinite(total_effect):
            continue
        jacobian = result.jac
        effect_se = _linear_effect_standard_error(
            jacobian=jacobian,
            residuals=resid,
            parameter_vector=result.x,
            unpack=unpack,
            node_order=node_order,
            treatment=treatment,
            outcome=outcome,
        )
        candidates.append((rel_resid, float(total_effect), effect_se, result.x))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    best_rel_resid = candidates[0][0]
    stable = [item for item in candidates if item[0] <= max(best_rel_resid * 2.0, 0.02)]
    effect_values = np.asarray([item[1] for item in stable], dtype=float)
    if effect_values.size == 0 or float(np.std(effect_values)) > 0.05:
        return None

    best_effect = float(np.mean(effect_values))
    best_se = stable[0][2]
    best_theta = stable[0][3]
    best_b, _ = unpack(best_theta)
    diagnostics = {
        "relative_residual": best_rel_resid,
        "n_unknown_params": n_unknown,
        "n_equations": n_equations,
        "n_multistart_successes": len(stable),
        "path_formula_terms": len(
            _enumerate_directed_paths(
                _children_from_directed_edges(directed_edges), treatment, outcome
            )
        ),
        "edge_coefficients": {
            f"{src}->{dst}": float(best_b[index[src], index[dst]]) for src, dst in directed_edges
        },
    }
    formula = _wright_formula_string(
        directed_edges=directed_edges,
        treatment=treatment,
        outcome=outcome,
    )
    return best_effect, best_se, diagnostics, formula


def _linear_total_effect(
    b: np.ndarray,
    node_order: tuple[str, ...],
    treatment: str,
    outcome: str,
) -> float | None:
    """Compute total causal effect under a linear SEM from direct coefficients."""
    index = {node: idx for idx, node in enumerate(node_order)}
    if treatment not in index or outcome not in index:
        return None
    try:
        total = np.linalg.inv(np.eye(len(node_order)) - b.T) - np.eye(len(node_order))
    except np.linalg.LinAlgError:
        return None
    return float(total[index[outcome], index[treatment]])


def _linear_effect_standard_error(
    *,
    jacobian: np.ndarray,
    residuals: np.ndarray,
    parameter_vector: np.ndarray,
    unpack: Any,
    node_order: tuple[str, ...],
    treatment: str,
    outcome: str,
) -> float | None:
    """Approximate SE for the recovered total effect via numerical delta method."""
    dof = max(jacobian.shape[0] - jacobian.shape[1], 1)
    try:
        sigma2 = float(np.dot(residuals, residuals) / dof)
        cov_theta = sigma2 * np.linalg.pinv(jacobian.T @ jacobian)
    except np.linalg.LinAlgError:
        return None

    step = 1e-5
    grad = np.zeros(parameter_vector.shape[0], dtype=float)
    base_b, _ = unpack(parameter_vector)
    base_effect = _linear_total_effect(base_b, node_order, treatment, outcome)
    if base_effect is None:
        return None

    for idx in range(parameter_vector.shape[0]):
        bumped = parameter_vector.copy()
        bumped[idx] += step
        bumped_b, _ = unpack(bumped)
        bumped_effect = _linear_total_effect(bumped_b, node_order, treatment, outcome)
        if bumped_effect is None:
            return None
        grad[idx] = (bumped_effect - base_effect) / step

    variance = float(grad @ cov_theta @ grad)
    if variance < 0.0 or not np.isfinite(variance):
        return None
    return float(np.sqrt(variance))


def _wright_formula_string(
    *,
    directed_edges: tuple[tuple[str, str], ...],
    treatment: str,
    outcome: str,
) -> str:
    """Path-sum formula for the total effect in terms of structural coefficients."""
    children = _children_from_directed_edges(directed_edges)
    paths = _enumerate_directed_paths(children, treatment, outcome)
    terms: list[str] = []
    for path in paths:
        edges = tuple(zip(path, path[1:], strict=False))
        if not edges:
            continue
        terms.append("*".join(f"b_{src}_{dst}" for src, dst in edges))
    return " + ".join(terms)


def _resolve_method_class(registry: Any, fqn_full: str) -> Any:
    """Resolve a Foundry method via registry with direct-import fallbacks."""
    try:
        return registry.get(fqn_full)
    except Exception:
        bare_fqn = fqn_full.split("@", 1)[0]
        if bare_fqn == "causal.structural.twin_network_query":
            from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery

            return TwinNetworkQuery
        if bare_fqn == "causal.structural.hybrid_scm_fit":
            from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit

            return HybridSCMFit
        if bare_fqn == "causal.sensitivity.sensitivity_metrics":
            from polisyos.foundry.methods.catalog.causal.sensitivity_metrics import (
                SensitivityMetrics,
            )

            return SensitivityMetrics
        if bare_fqn == "causal.diagnostics.positivity_check":
            from polisyos.foundry.methods.catalog.causal.diagnostics import (
                PositivityDiagnostic,
            )

            return PositivityDiagnostic
        if bare_fqn == "causal.diagnostics.support_mismatch":
            from polisyos.foundry.methods.catalog.causal.diagnostics import (
                SupportMismatchDiagnostic,
            )

            return SupportMismatchDiagnostic
        raise


class CausalEngineArtifactsMixin:
    def _materialize_identification_artifacts(
        self,
        identification_outcome: (
            IdentificationResult | NegativeCertificate | ProximalIdentificationCertificate
        ),
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> tuple[
        IdentificationResult | None,
        ProofBundle,
        NegativeCertificate | None,
        BoundsBundle | None,
        dict[str, Any] | None,
        Any | None,
        ProximalIdentificationCertificate | None,
    ]:
        """Normalize positive and negative ID outcomes into canonical public artifacts."""
        if isinstance(identification_outcome, ProximalIdentificationCertificate):
            proof_bundle = proof_bundle_from_proximal_certificate(
                identification_outcome,
                graph_ref=self._graph_artifact_ref(graph),
                query_ref=_query_str_from_io(treatment, outcome),
            )
            return None, proof_bundle, None, None, None, None, identification_outcome

        if isinstance(identification_outcome, NegativeCertificate):
            completed, dual_certificate_payload = self._complete_negative_certificate(
                identification_outcome,
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                data_dict=data_dict,
            )
            proof_bundle = proof_bundle_from_negative_certificate(
                completed,
                query_ref=(
                    str(completed.quantitative_diagnostics.get("intervention_query_string") or "")
                    or _query_str_from_io(treatment, outcome)
                ),
                theorem_family=str(
                    completed.quantitative_diagnostics.get("algorithm_version") or ""
                )
                or None,
                status_raw=str(
                    completed.quantitative_diagnostics.get("identification_status") or ""
                )
                or None,
            )
            return (
                None,
                proof_bundle,
                completed,
                completed.bounds_bundle,
                dual_certificate_payload,
                None,
                None,
            )

        proof_bundle = proof_bundle_from_identification_result(identification_outcome)
        from polisyos.ir.analytics.dp_robustness import (
            attach_dp_robustness_to_proof_bundle,
            bounds_bundle_from_dp_robustness_certificate,
            coerce_dp_robustness_certificate,
        )

        dp_certificate = coerce_dp_robustness_certificate(
            getattr(identification_outcome, "metadata", None)
        )
        dp_bounds_bundle = None
        if dp_certificate is not None:
            proof_bundle = attach_dp_robustness_to_proof_bundle(
                proof_bundle,
                None,
                dp_certificate,
            )
            if dp_certificate.effective_validity.status.value == "bounded":
                dp_bounds_bundle = bounds_bundle_from_dp_robustness_certificate(
                    dp_certificate,
                    estimand_type="causal_effect",
                )
        proximal_mediation_bounds = None
        metadata = dict(getattr(identification_outcome, "metadata", {}) or {})
        cert_payload = metadata.get("proximal_mediation_certificate")
        if (
            cert_payload is not None
            and getattr(identification_outcome, "status", None)
            is IdentificationStatus.ORACLE_NEEDED
        ):
            try:
                from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
                    proximal_mediation_bounds_bundle,
                )
                from polisyos.ir.analytics.proximal import ProximalMediationCertificate

                certificate = ProximalMediationCertificate.model_validate(cert_payload)
                outcome_vector = None
                if data_dict:
                    outcome_vector = _coerce_aligned_vector(
                        _first_non_null(
                            data_dict,
                            ("outcome", certificate.query.outcome),
                        )
                    )
                proximal_mediation_bounds = proximal_mediation_bounds_bundle(
                    outcome=outcome_vector,
                    target_effect=certificate.query.target_effect,
                    outcome_support=_resolve_graph_outcome_support(
                        graph,
                        outcome=certificate.query.outcome,
                    ),
                    assumption_tag="proximal_mediation_oracle_not_accepted",
                    metadata={
                        "path_specific_proximal": True,
                        "query_target_effect": certificate.query.target_effect,
                    },
                    warnings=[
                        "Proof kernel certified the proximal mediation template, but oracle assumptions were not accepted; returned bounds instead of a point estimate.",
                    ],
                )
            except Exception:
                proximal_mediation_bounds = None

        return (
            identification_outcome,
            proof_bundle,
            None,
            proximal_mediation_bounds or dp_bounds_bundle,
            None,
            dp_certificate,
            None,
        )


    def _complete_negative_certificate(
        self,
        negative_cert: NegativeCertificate,
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> tuple[NegativeCertificate, dict[str, Any] | None]:
        """Attach recovery/bounds artifacts for any supported non-identification path."""
        if negative_cert.blocking_type is BlockingType.HEDGE_STRUCTURE:
            return self._hedge_fallback_chain(
                negative_cert,
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                data_dict=data_dict,
            )

        diagnostics = dict(negative_cert.quantitative_diagnostics)
        y, t, extraction_notes = self._extract_hedge_fallback_arrays(
            data_dict=data_dict,
            treatment=treatment,
            outcome=outcome,
        )
        notes = list(extraction_notes)
        bounds_bundle: BoundsBundle | None = negative_cert.bounds_bundle
        dual_certificate_payload: dict[str, Any] | None = None
        if bounds_bundle is None and diagnostics.get("path_specific_proximal"):
            try:
                from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
                    proximal_mediation_bounds_bundle,
                )

                bounds_bundle = proximal_mediation_bounds_bundle(
                    outcome=y,
                    target_effect=str(diagnostics.get("target_effect") or "psi"),
                    outcome_support=_resolve_graph_outcome_support(
                        graph,
                        outcome=(
                            outcome
                            if isinstance(outcome, str)
                            else next(iter(sorted(outcome)), "outcome")
                        ),
                    ),
                    assumption_tag="proximal_mediation_structure_failed",
                    metadata={
                        "path_specific_proximal": True,
                        "failed_check": diagnostics.get("failed_check"),
                    },
                    warnings=[
                        "Structural proximal mediation checks failed; returned theorem-specific outer bounds when support information was available.",
                    ],
                )
                notes.append("Computed proximal mediation support-implied bounds bundle.")
            except Exception as exc:
                notes.append(f"Proximal mediation bounds completion failed: {exc}")
        if bounds_bundle is None and y is not None and t is not None:
            bounds_bundle, bounds_notes, dual_certificate_payload = (
                self._compute_generic_bounds_bundle(
                    y=y,
                    t=t,
                )
            )
            notes.extend(bounds_notes)
        elif bounds_bundle is None:
            notes.append(
                "Observed treatment/outcome vectors unavailable; bounds completion skipped."
            )

        diagnostics.update(
            {
                "bounds_completion_attempted": True,
                "bounds_completion_available": bounds_bundle is not None,
            }
        )
        if notes:
            diagnostics["bounds_completion_notes"] = list(notes)

        updated = negative_cert.model_copy(
            update={
                "bounds_bundle": bounds_bundle,
                "quantitative_diagnostics": diagnostics,
            }
        )
        updated = updated.model_copy(
            update={"recovery_plan": recovery_plan_from_negative_certificate(updated)}
        )
        return updated, dual_certificate_payload


    def audit(
        self,
        identification_result: IdentificationResult | NegativeCertificate | None,
        estimation_result: Any | None,
        *,
        run_id: str,
        graph: CausalGraphModel | None = None,
        executor_graph: ExecutorGraph | None = None,
        schema_report: SchemaResolutionReport | None = None,
        node_outputs: dict[str, Any] | None = None,
        negative_certificate: NegativeCertificate | None = None,
        fallback_result: FallbackResult | None = None,
        proof_bundle: Any | None = None,
        bounds_bundle: Any | None = None,
        dual_certificate_payload: dict[str, Any] | None = None,
        data_readiness_report: DataReadinessReport | Any | None = None,
        dp_robustness_certificate: Any | None = None,
    ) -> EvidenceBundle:
        """Build an EvidenceBundle from identification and estimation results.

        Parameters
        ----------
        graph:
            The CausalGraphModel used for identification (for fingerprinting).
        executor_graph:
            Compiled ExecutorGraph (for CompilationStep records).
        """
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir

        query_str = (
            _identification_query_str(identification_result)
            if isinstance(identification_result, IdentificationResult)
            else ""
        )
        if not query_str and negative_certificate is not None:
            query_str = str(
                negative_certificate.quantitative_diagnostics.get("intervention_query_string") or ""
            )
        if proof_bundle is not None:
            proof_payload = proof_bundle
        elif isinstance(identification_result, IdentificationResult):
            proof_payload = proof_bundle_from_identification_result(identification_result)
        elif negative_certificate is not None:
            proof_payload = proof_bundle_from_negative_certificate(
                negative_certificate,
                query_ref=query_str or None,
            )
        else:
            raise ValueError("audit() requires either an identification result or a proof bundle.")
        if not isinstance(proof_payload, ProofBundle):
            proof_payload = ProofBundle.model_validate(proof_payload)
        if self._artifact_store is not None:
            metadata_update = dict(proof_payload.metadata)
            if "bridge_plausibility_report" not in metadata_update:
                for outputs in (node_outputs or {}).values():
                    if isinstance(outputs, dict) and isinstance(
                        outputs.get("bridge_plausibility_report"), dict
                    ):
                        metadata_update["bridge_plausibility_report"] = outputs[
                            "bridge_plausibility_report"
                        ]
                        break
            resolved_query_ref = proof_payload.query_ref
            resolved_frontier_sketch_ref = proof_payload.frontier_sketch_ref
            resolved_bridge_plausibility_report_ref = proof_payload.bridge_plausibility_report_ref
            resolved_proximal_certificate_ref = proof_payload.proximal_certificate_ref
            resolved_recoverability_certificate_ref = proof_payload.recoverability_certificate_ref
            resolved_joint_decision_ref = proof_payload.joint_decision_ref
            intervention_query_payload = metadata_update.get("intervention_query")
            intervention_certificate_payload = metadata_update.get("intervention_certificate")
            frontier_sketch_payload = metadata_update.get("frontier_sketch")
            bridge_plausibility_payload = metadata_update.get("bridge_plausibility_report")
            proximal_certificate_payload = metadata_update.get("proximal_certificate")
            recoverability_certificate_payload = metadata_update.get("recoverability_certificate")
            joint_decision_payload = metadata_update.get("joint_decision")
            intervention_query_ref = None
            if isinstance(intervention_query_payload, dict):
                intervention_query_model = InterventionQuery.model_validate(
                    intervention_query_payload
                )
                intervention_query_ref = persist_intervention_query(
                    self._artifact_store,
                    intervention_query_model,
                )
                metadata_update["intervention_query_ref"] = intervention_query_ref.model_dump(
                    mode="json"
                )
                resolved_query_ref = str(intervention_query_ref.artifact_id)
            if isinstance(intervention_certificate_payload, dict):
                intervention_certificate_model = InterventionCertificate.model_validate(
                    intervention_certificate_payload
                )
                if intervention_query_ref is None:
                    intervention_query_ref = persist_intervention_query(
                        self._artifact_store,
                        intervention_certificate_model.query,
                    )
                    metadata_update["intervention_query_ref"] = intervention_query_ref.model_dump(
                        mode="json"
                    )
                    resolved_query_ref = str(intervention_query_ref.artifact_id)
                intervention_certificate_ref = persist_intervention_certificate(
                    self._artifact_store,
                    intervention_certificate_model,
                    inputs=[
                        InputRef(
                            artifact_id=intervention_query_ref.artifact_id,
                            role="intervention_query",
                        )
                    ],
                )
                metadata_update["intervention_certificate_ref"] = (
                    intervention_certificate_ref.model_dump(mode="json")
                )
            if isinstance(frontier_sketch_payload, dict):
                frontier_sketch_model = FrontierSketch.model_validate(frontier_sketch_payload)
                resolved_frontier_sketch_ref = persist_frontier_sketch(
                    self._artifact_store,
                    frontier_sketch_model,
                )
                metadata_update["frontier_sketch_ref"] = resolved_frontier_sketch_ref.model_dump(
                    mode="json"
                )
            if isinstance(bridge_plausibility_payload, dict):
                bridge_plausibility_model = BridgePlausibilityReport.model_validate(
                    bridge_plausibility_payload
                )
                resolved_bridge_plausibility_report_ref = persist_bridge_plausibility_report(
                    self._artifact_store,
                    bridge_plausibility_model,
                )
                metadata_update["bridge_plausibility_report_ref"] = (
                    resolved_bridge_plausibility_report_ref.model_dump(mode="json")
                )
            if isinstance(proximal_certificate_payload, dict):
                proximal_certificate_model = ProximalIdentificationCertificate.model_validate(
                    proximal_certificate_payload
                )
                resolved_proximal_certificate_ref = persist_proximal_identification_certificate(
                    self._artifact_store,
                    proximal_certificate_model,
                )
                metadata_update["proximal_certificate_ref"] = (
                    resolved_proximal_certificate_ref.model_dump(mode="json")
                )
            if isinstance(recoverability_certificate_payload, dict):
                recoverability_certificate_model = RecoverabilityCertificate.model_validate(
                    recoverability_certificate_payload
                )
                resolved_recoverability_certificate_ref = persist_recoverability_certificate(
                    self._artifact_store,
                    recoverability_certificate_model,
                )
                metadata_update["recoverability_certificate_ref"] = (
                    resolved_recoverability_certificate_ref.model_dump(mode="json")
                )
            if isinstance(joint_decision_payload, dict):
                joint_decision_model = JointDecisionCertificate.model_validate(
                    joint_decision_payload
                )
                if resolved_recoverability_certificate_ref is None:
                    resolved_recoverability_certificate_ref = persist_recoverability_certificate(
                        self._artifact_store,
                        joint_decision_model.recoverability,
                    )
                    metadata_update["recoverability_certificate_ref"] = (
                        resolved_recoverability_certificate_ref.model_dump(mode="json")
                    )
                joint_inputs = (
                    [
                        InputRef(
                            artifact_id=resolved_recoverability_certificate_ref.artifact_id,
                            role="recoverability_certificate",
                        )
                    ]
                    if resolved_recoverability_certificate_ref is not None
                    else None
                )
                resolved_joint_decision_ref = persist_joint_decision_certificate(
                    self._artifact_store,
                    joint_decision_model,
                    inputs=joint_inputs,
                )
                metadata_update["joint_decision_ref"] = resolved_joint_decision_ref.model_dump(
                    mode="json"
                )
            if (
                metadata_update != proof_payload.metadata
                or resolved_query_ref != proof_payload.query_ref
            ):
                proof_payload = proof_payload.model_copy(
                    update={
                        "metadata": metadata_update,
                        "query_ref": resolved_query_ref,
                        "frontier_sketch_ref": resolved_frontier_sketch_ref,
                        "bridge_plausibility_report_ref": resolved_bridge_plausibility_report_ref,
                        "proximal_certificate_ref": resolved_proximal_certificate_ref,
                        "recoverability_certificate_ref": resolved_recoverability_certificate_ref,
                        "joint_decision_ref": resolved_joint_decision_ref,
                    }
                )
        from polisyos.ir.analytics.dp_robustness import (
            attach_dp_robustness_to_proof_bundle,
            coerce_dp_robustness_certificate,
            persist_dp_robustness_certificate,
        )

        resolved_dp_certificate = coerce_dp_robustness_certificate(dp_robustness_certificate)
        if resolved_dp_certificate is None and isinstance(
            getattr(identification_result, "metadata", None),
            dict,
        ):
            resolved_dp_certificate = coerce_dp_robustness_certificate(
                identification_result.metadata
            )
        if resolved_dp_certificate is not None:
            proof_payload = attach_dp_robustness_to_proof_bundle(
                proof_payload,
                getattr(proof_payload, "dp_robustness_ref", None),
                resolved_dp_certificate,
            )
        if not query_str:
            query_str = str(proof_payload.query_ref or "")
        fallback_payload = fallback_result or (
            negative_certificate.fallback_result if negative_certificate is not None else None
        )
        bounds_payload = bounds_bundle or (
            negative_certificate.bounds_bundle if negative_certificate is not None else None
        )
        if (
            bounds_payload is None
            and fallback_result is not None
            and fallback_result.bounds is not None
        ):
            bounds_payload = bounds_bundle_from_partial_identification_result(
                fallback_result.bounds,
                metadata={
                    "epistemic_tier": (
                        fallback_result.bounds_tier.value
                        if fallback_result.bounds_tier is not None
                        else None
                    ),
                    "fallback_level": fallback_result.fallback_level,
                },
            )
        if bounds_payload is not None and not isinstance(bounds_payload, BoundsBundle):
            bounds_payload = BoundsBundle.model_validate(bounds_payload)
        if (
            bounds_payload is None
            and fallback_payload is not None
            and fallback_payload.bounds is not None
        ):
            bounds_payload = bounds_bundle_from_partial_identification_result(
                fallback_payload.bounds,
                metadata={
                    "epistemic_tier": (
                        fallback_payload.bounds_tier.value
                        if fallback_payload.bounds_tier is not None
                        else None
                    ),
                    "fallback_level": fallback_payload.fallback_level,
                },
            )

        # -- Proof steps -------------------------------------------------
        ir_steps: list[IRProofStep] = (
            [
                _internal_proof_step_to_ir(s)
                for s in getattr(identification_result, "proof_steps", [])
            ]
            if isinstance(identification_result, IdentificationResult)
            else []
        )

        # -- DataProvenance ----------------------------------------------
        provenance: list[DataProvenance] = []
        for dr in (
            getattr(identification_result, "required_distributions", [])
            if isinstance(identification_result, IdentificationResult)
            else []
        ):
            ref = getattr(dr, "dataset_ref", None) or ""
            quality = 1.0
            n_obs = None
            avail = "available"
            if self._kb is not None and ref:
                try:
                    av, _ = self._kb.can_identify_distribution(dr)
                    avail = av.value if hasattr(av, "value") else str(av)
                    for entry in self._kb.datasets:
                        if entry.dataset_ref == ref:
                            quality = entry.quality_score
                            n_obs = entry.n_obs
                            break
                except Exception:
                    pass
            provenance.append(
                DataProvenance(
                    dataset_ref=ref or "unknown",
                    n_obs=n_obs,
                    quality_score=quality,
                    domain=getattr(dr, "domain", "source").value
                    if hasattr(getattr(dr, "domain", ""), "value")
                    else str(getattr(dr, "domain", "source")),
                    availability_status=avail,
                )
            )

        # -- Diagnostic scores (legacy flat dict) ------------------------
        diag: dict[str, float] = {}
        if schema_report is not None:
            diag["schema_warnings_count"] = float(len(schema_report.support_warnings))
            diag["schema_feasible"] = 1.0 if schema_report.is_feasible else 0.0

        if estimation_result is not None:
            pt = getattr(estimation_result, "point_estimate", None)
            if pt is not None and isinstance(pt, float) and pt == pt:  # not NaN
                diag["point_estimate"] = pt

        for outputs in (node_outputs or {}).values():
            if not isinstance(outputs, dict):
                continue
            sr = outputs.get("sensitivity_result")
            if sr is not None:
                e_val = (
                    getattr(sr, "e_value", None) if not isinstance(sr, dict) else sr.get("e_value")
                )
                if e_val is not None:
                    try:
                        diag["e_value"] = float(e_val)
                    except (TypeError, ValueError):
                        pass
                rb = (
                    getattr(sr, "rosenbaum_gamma", None)
                    if not isinstance(sr, dict)
                    else sr.get("rosenbaum_gamma")
                )
                if rb is not None:
                    try:
                        diag["rosenbaum_gamma"] = float(rb)
                    except (TypeError, ValueError):
                        pass
            # Also extract from nested "result" dict (PositivityDiagnostic, SupportMismatch)
            result_dict = outputs.get("result", {})
            if isinstance(result_dict, dict):
                for key in ("ess_fraction", "overlap_score"):
                    val = result_dict.get(key)
                    if val is not None and key not in diag:
                        try:
                            diag[key] = float(val)
                        except (TypeError, ValueError):
                            pass
            for key in ("ess_fraction", "overlap_score", "support_mismatch_score"):
                val = outputs.get(key)
                if val is not None and key not in diag:
                    try:
                        diag[key] = float(val)
                    except (TypeError, ValueError):
                        pass
            bridge_report = outputs.get("bridge_plausibility_report")
            if isinstance(bridge_report, dict):
                bridge_metric_keys = {
                    "residual_r": "bridge_residual_r",
                    "effective_rank": "bridge_effective_rank",
                    "sigma_min": "bridge_sigma_min",
                    "ill_posedness_index": "bridge_ill_posedness_index",
                    "proxy_association_score": "bridge_proxy_association",
                    "moran_i_bridge_residual": "bridge_moran_i",
                    "ring_sensitivity_instability": "bridge_ring_instability",
                }
                for source_key, target_key in bridge_metric_keys.items():
                    val = bridge_report.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass
                if (
                    "buffer_exclusion_falsification" in bridge_report
                    and "buffer_exclusion_falsification" not in diag
                ):
                    diag["buffer_exclusion_falsification"] = (
                        1.0 if bool(bridge_report["buffer_exclusion_falsification"]) else 0.0
                    )
            kernel_report = outputs.get("kernel_report")
            if isinstance(kernel_report, dict):
                for source_key, target_key in {
                    "effect_norm": "kernel_effect_norm",
                    "condition_number": "kernel_condition_number",
                }.items():
                    val = kernel_report.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass
                if "characteristic" in kernel_report:
                    diag["kernel_characteristic"] = (
                        1.0 if bool(kernel_report["characteristic"]) else 0.0
                    )
                if "weak_metrizing" in kernel_report:
                    diag["kernel_weak_metrizing"] = (
                        1.0 if bool(kernel_report["weak_metrizing"]) else 0.0
                    )
            kernel_semantics = outputs.get("kernel_semantics")
            if isinstance(kernel_semantics, dict):
                if "passed" in kernel_semantics:
                    diag["kernel_semantics_passed"] = (
                        1.0 if bool(kernel_semantics["passed"]) else 0.0
                    )
                if "characteristic" in kernel_semantics and "kernel_characteristic" not in diag:
                    diag["kernel_characteristic"] = (
                        1.0 if bool(kernel_semantics["characteristic"]) else 0.0
                    )
                if "weak_metrizing" in kernel_semantics and "kernel_weak_metrizing" not in diag:
                    diag["kernel_weak_metrizing"] = (
                        1.0 if bool(kernel_semantics["weak_metrizing"]) else 0.0
                    )
            kernel_regularization = outputs.get("kernel_regularization")
            if isinstance(kernel_regularization, dict):
                for source_key, target_key in {
                    "condition_number": "kernel_condition_number",
                    "instability": "kernel_regularization_instability",
                }.items():
                    val = kernel_regularization.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass
            kernel_effect_test = outputs.get("kernel_effect_test")
            if isinstance(kernel_effect_test, dict):
                p_val = kernel_effect_test.get("p_value")
                if p_val is not None:
                    try:
                        diag["kernel_effect_test_p_value"] = float(p_val)
                    except (TypeError, ValueError):
                        pass
                if "effect_norm" in kernel_effect_test and "kernel_effect_norm" not in diag:
                    try:
                        diag["kernel_effect_norm"] = float(kernel_effect_test["effect_norm"])
                    except (TypeError, ValueError):
                        pass
            if isinstance(result_dict, dict):
                for source_key, target_key in {
                    "operator_injectivity_score": "operator_injectivity_score",
                    "proxy_association_score": "proxy_association_score",
                }.items():
                    val = result_dict.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass

        # -- Estimand AST -----------------------------------------------
        estimand_dict: dict[str, Any] = {}
        ast = (
            identification_result.estimand_ast
            if isinstance(identification_result, IdentificationResult)
            else None
        )
        if ast is not None:
            try:
                estimand_dict = ast.model_dump(mode="json")
            except Exception:
                estimand_dict = {}

        method_config: dict[str, Any] = {}
        kernel_spec_payload: dict[str, Any] | None = None
        resolved_kernel_spec = None
        if executor_graph is not None:
            primary_nodes = [
                node
                for node in executor_graph.nodes
                if not getattr(node, "is_nuisance", False)
                and node.method_fqn != "causal.sensitivity.sensitivity_metrics"
            ]
            if primary_nodes:
                primary_node = primary_nodes[-1]
                method_config["primary_method_fqn"] = (
                    f"{primary_node.method_fqn}@{primary_node.method_version}"
                )
            method_config["executor_node_count"] = len(executor_graph.nodes)
            nuisance_fqns = [
                f"{node.method_fqn}@{node.method_version}"
                for node in executor_graph.nodes
                if getattr(node, "is_nuisance", False)
            ]
            if nuisance_fqns:
                method_config["nuisance_method_fqns"] = nuisance_fqns
            for node in executor_graph.nodes:
                payload = node.params.get("kernel_spec")
                if isinstance(payload, dict):
                    kernel_spec_payload = payload
                    break
        if kernel_spec_payload is not None:
            try:
                from polisyos.ir.analytics.kernel_causal import KernelEstimatorSpec

                resolved_kernel_spec = KernelEstimatorSpec.model_validate(kernel_spec_payload)
                method_config.update(
                    {
                        "kernel_template": resolved_kernel_spec.template.value,
                        "kernel_target_representation": (
                            resolved_kernel_spec.target_representation.value
                        ),
                        "kernel_consistency_claim": (resolved_kernel_spec.consistency_claim.value),
                        "kernel_lowering_disposition": (
                            resolved_kernel_spec.lowering_disposition.value
                        ),
                        "kernel_output_kernel": resolved_kernel_spec.output_kernel.model_dump(
                            mode="json"
                        ),
                    }
                )
            except Exception:
                resolved_kernel_spec = None

        # -- 5.1: fingerprints ------------------------------------------
        graph_fp = ""
        if graph is not None:
            try:
                graph_fp = _fingerprint(graph.model_dump(mode="json"))
            except Exception:
                pass

        estimand_fp = _fingerprint(estimand_dict) if estimand_dict else ""

        # -- 5.1: CompilationStep from executor_graph --------------------
        compilation_steps: list[CompilationStep] = []
        if executor_graph is not None:
            try:
                from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
                    classify_estimand,
                    recommend_estimator,
                )

                shape_val = ""
                strategy_val = ""
                if ast is not None:
                    try:
                        rec = recommend_estimator(ast, n_obs=None, covariate_dim=None)
                        shape_val = rec.shape.value
                        strategy_val = rec.strategy.value
                    except Exception:
                        try:
                            shape_val = classify_estimand(ast).value
                        except Exception:
                            pass
                nuisance_fqns = tuple(
                    n.method_fqn for n in executor_graph.nodes if getattr(n, "is_nuisance", False)
                )
                compilation_steps.append(
                    CompilationStep(
                        estimand_shape=shape_val,
                        estimation_strategy=strategy_val,
                        n_executor_nodes=len(executor_graph.nodes),
                        nuisance_components=nuisance_fqns,
                        compiler_warnings=tuple(
                            str(w) for w in getattr(executor_graph, "warnings", ())
                        ),
                    )
                )
            except Exception:
                pass

        # -- 5.1: EstimationStep per executor node -----------------------
        estimation_steps: list[EstimationStep] = []
        if executor_graph is not None and node_outputs:
            import hashlib
            import json as _json

            for node in executor_graph.nodes:
                nid = node.node_id
                out = (node_outputs or {}).get(nid, {})
                params_hash = ""
                try:
                    params_hash = hashlib.sha256(
                        _json.dumps(node.params, sort_keys=True, default=str).encode()
                    ).hexdigest()[:16]
                except Exception:
                    pass
                node_warnings: list[str] = []
                if isinstance(out, dict):
                    node_warnings = [str(w) for w in out.get("warnings", [])]
                estimation_steps.append(
                    EstimationStep(
                        node_id=nid,
                        method_fqn=node.method_fqn,
                        method_version=node.method_version,
                        backend="",
                        params_hash=params_hash,
                        wall_time_ms=None,
                        determinism_tier="",
                        warnings=tuple(node_warnings),
                        is_nuisance=getattr(node, "is_nuisance", False),
                    )
                )

        # -- 5.2: DiagnosticDashboardData --------------------------------
        dashboard_dict: dict[str, Any] | None = None
        try:
            from polisyos.ir.analytics.diagnostic_dashboard import DiagnosticDashboardData

            dashboard = DiagnosticDashboardData.from_node_outputs(
                run_id=run_id,
                query_str=query_str,
                node_outputs=node_outputs or {},
                created_at=datetime.now(UTC).isoformat(),
            )
            dashboard_dict = dashboard.model_dump(mode="json")
        except Exception:
            pass

        # -- 5.4: CausalQualityReport ------------------------------------
        quality_dict: dict[str, Any] | None = None
        try:
            from polisyos.foundry.methods.catalog.causal.quality_aggregator import (
                QualityScoreAggregator,
            )

            quality_report = QualityScoreAggregator().score(
                run_id=run_id,
                query_str=query_str,
                data_provenance=tuple(provenance),
                estimation_steps=tuple(estimation_steps),
                node_outputs=node_outputs,
            )
            quality_dict = quality_report.model_dump(mode="json")
        except Exception:
            pass

        witness_index = None
        if graph is not None and ir_steps:
            try:
                witness_index = build_witness_index_from_proof_steps(
                    ir_steps,
                    graph=graph,
                    theorem_family=proof_payload.theorem_family,
                )
            except Exception:
                witness_index = None

        proof_trace_ref = proof_payload.proof_trace_ref
        witness_index_ref = proof_payload.witness_index_ref
        if self._artifact_store is not None and proof_trace_ref is None and ir_steps:
            trace_bundle_payload = EvidenceBundle(
                run_id=run_id,
                query_str=query_str,
                estimand_ast=estimand_dict,
                proof_steps=tuple(ir_steps),
                data_provenance=tuple(provenance),
                diagnostic_scores=diag,
                method_config=method_config,
                identification_status=(
                    identification_result.status.value
                    if isinstance(identification_result, IdentificationResult)
                    else str(proof_payload.metadata.get("status") or proof_payload.proof_status)
                ),
                algorithm_version=(
                    getattr(identification_result, "algorithm_version", "id_v1")
                    if isinstance(identification_result, IdentificationResult)
                    else str(
                        negative_certificate.quantitative_diagnostics.get("algorithm_version")
                        if negative_certificate is not None
                        else proof_payload.theorem_family
                    )
                ),
                created_at=datetime.now(UTC).isoformat(),
                graph_fingerprint=graph_fp,
                estimand_fingerprint=estimand_fp,
                compilation_steps=tuple(compilation_steps),
                estimation_steps=tuple(estimation_steps),
                diagnostic_dashboard=dashboard_dict,
                quality_report=quality_dict,
            )
            proof_trace_ref = persist_causal_evidence_bundle(
                self._artifact_store,
                trace_bundle_payload,
            )
        if (
            self._artifact_store is not None
            and witness_index_ref is None
            and witness_index is not None
        ):
            witness_inputs = (
                [
                    InputRef(
                        artifact_id=proof_trace_ref.artifact_id,
                        role="proof_trace",
                    )
                ]
                if proof_trace_ref is not None
                else None
            )
            witness_index_ref = persist_proof_witness_index(
                self._artifact_store,
                witness_index,
                inputs=witness_inputs,
            )
        if (
            proof_trace_ref is not None
            or witness_index_ref is not None
            or witness_index is not None
        ):
            metadata_update = dict(proof_payload.metadata)
            if proof_trace_ref is not None:
                metadata_update["proof_trace_ref"] = proof_trace_ref.model_dump(mode="json")
            if witness_index_ref is not None:
                metadata_update["witness_index_ref"] = witness_index_ref.model_dump(mode="json")
            proof_support_projection_hash = proof_payload.proof_support_projection_hash or (
                witness_index.proof_support_projection_hash if witness_index is not None else None
            )
            metadata_update["proof_support_projection_hash"] = proof_support_projection_hash
            metadata_update.setdefault(
                "composability_status",
                proof_payload.composability_status,
            )
            proof_payload = proof_payload.model_copy(
                update={
                    "proof_trace_ref": proof_trace_ref,
                    "witness_index_ref": witness_index_ref,
                    "proof_support_projection_hash": proof_support_projection_hash,
                    "metadata": metadata_update,
                }
            )
        if (
            self._artifact_store is not None
            and graph is not None
            and witness_index is not None
            and witness_index.witnesses
        ):
            proof_payload = _attach_proof_composability_certificate(
                store=self._artifact_store,
                proof_payload=proof_payload,
                witness_index=witness_index,
                graph=graph,
                query_str=query_str,
                graph_fingerprint=graph_fp,
            )

        proof_bundle_ref = None
        bounds_bundle_ref = None
        negative_certificate_ref = None
        data_readiness_report_ref = None
        kernel_estimator_spec_ref = None
        if self._artifact_store is not None:
            if resolved_dp_certificate is not None:
                dp_robustness_ref = persist_dp_robustness_certificate(
                    self._artifact_store,
                    resolved_dp_certificate,
                )
                proof_payload = attach_dp_robustness_to_proof_bundle(
                    proof_payload,
                    dp_robustness_ref,
                    resolved_dp_certificate,
                )
            proof_bundle_inputs = [
                InputRef(artifact_id=trace_ref.artifact_id, role="proof_trace")
                for trace_ref in (proof_payload.proof_trace_ref,)
                if trace_ref is not None
            ]
            proof_bundle_inputs.extend(
                InputRef(
                    artifact_id=witness_ref.artifact_id,
                    role="proof_witness_index",
                )
                for witness_ref in (proof_payload.witness_index_ref,)
                if witness_ref is not None
            )
            proof_bundle_inputs.extend(
                InputRef(
                    artifact_id=composability_ref.artifact_id,
                    role="proof_composability_certificate",
                )
                for composability_ref in (proof_payload.composability_certificate_ref,)
                if composability_ref is not None
            )
            proof_bundle_ref = persist_proof_bundle(
                self._artifact_store,
                proof_payload,
                inputs=proof_bundle_inputs or None,
            )
            if bounds_payload is not None:
                bounds_payload, bounds_inputs = hydrate_bounds_bundle_with_dual_certificate(
                    self._artifact_store,
                    bounds_payload,
                    dual_certificate_payload,
                )
                bounds_bundle_ref = persist_bounds_bundle(
                    self._artifact_store,
                    bounds_payload,
                    inputs=bounds_inputs,
                )
            if data_readiness_report is not None:
                readiness_payload = (
                    data_readiness_report
                    if isinstance(data_readiness_report, DataReadinessReport)
                    else DataReadinessReport.model_validate(data_readiness_report)
                )
                readiness_update: dict[str, Any] = {}
                if (
                    proof_payload.recoverability_certificate_ref is not None
                    and readiness_payload.recoverability_certificate_ref is None
                ):
                    readiness_update["recoverability_certificate_ref"] = (
                        proof_payload.recoverability_certificate_ref
                    )
                if (
                    proof_payload.joint_decision_ref is not None
                    and readiness_payload.joint_decision_ref is None
                ):
                    readiness_update["joint_decision_ref"] = proof_payload.joint_decision_ref
                if readiness_update:
                    readiness_payload = readiness_payload.model_copy(update=readiness_update)
                if resolved_dp_certificate is not None and readiness_payload.dp_distortion is None:
                    from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

                    readiness_payload = apply_dp_readiness_gate(
                        readiness_payload,
                        resolved_dp_certificate,
                    )
                data_readiness_report_ref = persist_data_readiness_report(
                    self._artifact_store,
                    readiness_payload,
                )
            if negative_certificate is not None:
                negative_inputs = (
                    [
                        InputRef(
                            artifact_id=bounds_bundle_ref.artifact_id,
                            role="bounds_bundle",
                        )
                    ]
                    if bounds_bundle_ref is not None
                    else None
                )
                negative_certificate_ref = persist_negative_certificate(
                    self._artifact_store,
                    negative_certificate,
                    inputs=negative_inputs,
                )
            if resolved_kernel_spec is not None:
                from polisyos.ir.analytics.kernel_causal import persist_kernel_estimator_spec

                if proof_bundle_ref is not None and resolved_kernel_spec.proof_bundle_ref is None:
                    resolved_kernel_spec = resolved_kernel_spec.model_copy(
                        update={"proof_bundle_ref": proof_bundle_ref}
                    )
                kernel_inputs = (
                    [
                        InputRef(
                            artifact_id=proof_bundle_ref.artifact_id,
                            role="proof_bundle",
                        )
                    ]
                    if proof_bundle_ref is not None
                    else None
                )
                kernel_estimator_spec_ref = persist_kernel_estimator_spec(
                    self._artifact_store,
                    resolved_kernel_spec,
                    inputs=kernel_inputs,
                )
                method_config["kernel_estimator_spec_ref"] = kernel_estimator_spec_ref.model_dump(
                    mode="json"
                )

        return EvidenceBundle(
            run_id=run_id,
            query_str=query_str,
            estimand_ast=estimand_dict,
            proof_steps=tuple(ir_steps),
            data_provenance=tuple(provenance),
            diagnostic_scores=diag,
            method_config=method_config,
            identification_status=(
                identification_result.status.value
                if isinstance(identification_result, IdentificationResult)
                else str(proof_payload.metadata.get("status") or proof_payload.proof_status)
            ),
            algorithm_version=(
                getattr(identification_result, "algorithm_version", "id_v1")
                if isinstance(identification_result, IdentificationResult)
                else str(
                    negative_certificate.quantitative_diagnostics.get("algorithm_version")
                    if negative_certificate is not None
                    else proof_payload.theorem_family
                )
            ),
            created_at=datetime.now(UTC).isoformat(),
            graph_fingerprint=graph_fp,
            estimand_fingerprint=estimand_fp,
            compilation_steps=tuple(compilation_steps),
            estimation_steps=tuple(estimation_steps),
            diagnostic_dashboard=dashboard_dict,
            quality_report=quality_dict,
            proof_bundle_ref=proof_bundle_ref,
            bounds_bundle_ref=bounds_bundle_ref,
            negative_certificate_ref=negative_certificate_ref,
            data_readiness_report_ref=data_readiness_report_ref,
            kernel_estimator_spec_ref=kernel_estimator_spec_ref,
        )


    def run(
        self,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        graph: CausalGraphModel,
        data_dict: dict[str, Any] | None = None,
        *,
        df_columns: list[str] | None = None,
        df_dtypes: dict[str, str] | None = None,
        source_domains: list[Any] | None = None,
        s_nodes: list[Any] | None = None,
        z_interventions: frozenset[str] | None = None,
        conditions: frozenset[str] | None = None,
        n_obs: int | None = None,
        covariate_dim: int | None = None,
        run_id: str | None = None,
        oracle: str = "none",
        use_cross_fitting: bool = True,
        dataset_ref: str | None = None,
        mgraph_meta: Any | None = None,
        counterfactual_query: CtfQuery | None = None,
        intervention_query: InterventionQuery | None = None,
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None = None,
    ) -> tuple[Any, EvidenceBundle, NegativeCertificate | None]:
        """Run the full Pearl-Bareinboim pipeline: identify → compile → estimate → audit.

        Returns
        -------
        (CausalEffectReport | None, EvidenceBundle, NegativeCertificate | None)
        """
        run_id = run_id or uuid.uuid4().hex

        schema_report: SchemaResolutionReport | None = None

        # 1. Identify
        id_result = self.identify(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            source_domains=source_domains,
            s_nodes=s_nodes,
            z_interventions=z_interventions,
            conditions=conditions,
            oracle=oracle,
            dataset_ref=dataset_ref,
            mgraph_meta=mgraph_meta,
            counterfactual_query=counterfactual_query,
            intervention_query=intervention_query,
            proximal_annotation=proximal_annotation,
        )

        sample_size = _infer_sample_size(data_dict, explicit_n_obs=n_obs)
        fallback_data_available = _has_fallback_arrays(data_dict, treatment, outcome)
        (
            resolved_id_result,
            proof_bundle,
            negative_cert,
            resolved_bounds_bundle,
            dual_certificate_payload,
            dp_robustness_certificate,
            proximal_certificate,
        ) = self._materialize_identification_artifacts(
            id_result,
            graph=graph,
            treatment=treatment,
            outcome=outcome,
            data_dict=data_dict,
        )
        recoverability_summary = _extract_recoverability_summary(
            resolved_id_result if negative_cert is None else negative_cert
        ) or _extract_recoverability_summary(proof_bundle)
        missingness_assessment = _resolve_missingness_assessment(
            graph=graph,
            data_dict=data_dict,
            mgraph_meta=mgraph_meta,
            treatment=treatment,
            outcome=outcome,
        )

        # If identification failed, return canonical impossibility artifacts.
        if negative_cert is not None:
            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="unknown",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
                extra_metrics=_float_metrics_from_mapping(negative_cert.quantitative_diagnostics),
            )
            bundle = self.audit(
                None,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                negative_certificate=negative_cert,
                fallback_result=negative_cert.fallback_result,
                proof_bundle=proof_bundle,
                bounds_bundle=resolved_bounds_bundle,
                dual_certificate_payload=dual_certificate_payload,
                data_readiness_report=readiness_report,
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, negative_cert

        if proximal_certificate is not None:
            is_spatial_proximal = bool(
                getattr(proximal_certificate.proxies, "spatial_proxy_specs", ())
            )
            if is_spatial_proximal:
                proximal_state = _derive_spatial_proximal_bridge_state(
                    data_dict=data_dict,
                    treatment=treatment,
                    outcome=outcome,
                    certificate=proximal_certificate,
                )
            else:
                proximal_state = _derive_proximal_bridge_state(
                    data_dict=data_dict,
                    treatment=treatment,
                    outcome=outcome,
                    certificate=proximal_certificate,
                )
            proximal_output: dict[str, Any] | None = None
            proximal_metrics: dict[str, Any] = {
                "bridge_functions_count": proof_bundle.metadata.get("bridge_functions_count"),
                "graph_checks_count": proof_bundle.metadata.get("graph_checks_count"),
            }
            if proximal_state is not None:
                from polisyos.foundry.methods.catalog.causal.frontier import (
                    ProximalBridgeEstimator,
                    SpatialProximalBridgeEstimator,
                )

                method_seed = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16)
                if is_spatial_proximal:
                    proximal_output = SpatialProximalBridgeEstimator.pure_step(
                        proximal_state,
                        {
                            "model_family": proximal_state.get("model_family", "sdm"),
                            "sieve_degree": 3,
                            "n_folds": 4,
                            "block_cv_scheme": "spatial_blocks",
                            "n_bootstrap": 80,
                            "confidence_level": 0.95,
                            "ridge": 1.0e-4,
                            "bridge_residual_splits": 12,
                            "epsilon_grid": (0.01, 0.025, 0.05),
                            "stability_constraint_margin": 0.025,
                            "__seed__": method_seed,
                        },
                    )
                    weight_matrix = np.asarray(proximal_state["weight_matrix"], dtype=float)
                    weight_matrix_hash = hashlib.sha256(weight_matrix.tobytes()).hexdigest()
                    updated_metadata = dict(proof_bundle.metadata)
                    updated_metadata.update(
                        {
                            "weight_matrix_hash": weight_matrix_hash,
                            "spatial_model_family": str(proximal_state.get("model_family", "sdm")),
                        }
                    )
                    proof_bundle = proof_bundle.model_copy(update={"metadata": updated_metadata})
                else:
                    proximal_output = ProximalBridgeEstimator.pure_step(
                        proximal_state,
                        {
                            "n_bootstrap": 200,
                            "confidence_level": 0.95,
                            "ridge": 1.0e-4,
                            "__seed__": method_seed,
                        },
                    )
                bridge_report_payload = proximal_output.get("bridge_plausibility_report")
                if isinstance(bridge_report_payload, dict):
                    proximal_metrics.update(
                        {
                            "bridge_residual_r": bridge_report_payload.get("residual_r"),
                            "bridge_effective_rank": bridge_report_payload.get("effective_rank"),
                            "bridge_sigma_min": bridge_report_payload.get("sigma_min"),
                            "bridge_proxy_association": bridge_report_payload.get(
                                "proxy_association_score"
                            ),
                            "bridge_moran_i": bridge_report_payload.get("moran_i_bridge_residual"),
                            "bridge_ring_instability": bridge_report_payload.get(
                                "ring_sensitivity_instability"
                            ),
                            "buffer_exclusion_falsification": (
                                1.0
                                if bridge_report_payload.get("buffer_exclusion_falsification")
                                else 0.0
                            )
                            if bridge_report_payload.get("buffer_exclusion_falsification")
                            is not None
                            else None,
                        }
                    )

            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="proxy_only",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
                extra_metrics=_float_metrics_from_mapping(proximal_metrics),
            )
            if proximal_output is not None:
                proximal_report = proximal_output.get("report")
                node_outputs = {
                    "spatial_proximal_bridge"
                    if is_spatial_proximal
                    else "proximal_bridge": proximal_output
                }
                negative_payload = proximal_output.get("negative_certificate")
                bounds_payload = proximal_output.get("bounds_bundle")
                proximal_negative_cert = (
                    NegativeCertificate.model_validate(negative_payload)
                    if isinstance(negative_payload, dict)
                    else None
                )
                proximal_bounds_bundle = None
                if proximal_negative_cert is not None:
                    proximal_bounds_bundle = proximal_negative_cert.bounds_bundle
                if proximal_bounds_bundle is None and isinstance(bounds_payload, dict):
                    proximal_bounds_bundle = BoundsBundle.model_validate(bounds_payload)
                if proximal_negative_cert is not None:
                    bundle = self.audit(
                        None,
                        proximal_report,
                        run_id=run_id,
                        graph=graph,
                        schema_report=schema_report,
                        node_outputs=node_outputs,
                        negative_certificate=proximal_negative_cert,
                        proof_bundle=proof_bundle,
                        bounds_bundle=proximal_bounds_bundle,
                        data_readiness_report=readiness_report,
                    )
                    return None, bundle, proximal_negative_cert
                if proximal_report is not None:
                    bundle = self.audit(
                        None,
                        proximal_report,
                        run_id=run_id,
                        graph=graph,
                        schema_report=schema_report,
                        node_outputs=node_outputs,
                        proof_bundle=proof_bundle,
                        data_readiness_report=readiness_report,
                    )
                    return proximal_report, bundle, None
            bundle = self.audit(
                None,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                proof_bundle=proof_bundle,
                data_readiness_report=readiness_report,
            )
            return None, bundle, None

        assert resolved_id_result is not None

        proximal_mediation_payload = dict(getattr(resolved_id_result, "metadata", {}) or {}).get(
            "proximal_mediation_certificate"
        )
        if proximal_mediation_payload is not None:
            from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
                PROXIMAL_MEDIATION_V1_THEOREM,
                ProximalMediationEstimator,
            )
            from polisyos.ir.analytics.proximal import ProximalMediationCertificate

            proximal_mediation_certificate = ProximalMediationCertificate.model_validate(
                proximal_mediation_payload
            )
            proximal_mediation_state = _derive_proximal_mediation_state(
                data_dict=data_dict,
                certificate=proximal_mediation_certificate,
            )
            bridge_metrics: dict[str, Any] = {
                "bridge_equations_count": len(proximal_mediation_certificate.bridge_equations),
                "graph_checks_count": len(proximal_mediation_certificate.graph_checks),
            }
            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="proxy_only",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
                extra_metrics=_float_metrics_from_mapping(bridge_metrics),
            )
            if proximal_mediation_state is None:
                bundle = self.audit(
                    resolved_id_result,
                    None,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    proof_bundle=proof_bundle,
                    bounds_bundle=resolved_bounds_bundle,
                    dual_certificate_payload=dual_certificate_payload,
                    data_readiness_report=readiness_report,
                    dp_robustness_certificate=dp_robustness_certificate,
                )
                return None, bundle, None

            proximal_mediation_output = ProximalMediationEstimator.pure_step(
                proximal_mediation_state,
                {
                    "theorem_family": PROXIMAL_MEDIATION_V1_THEOREM,
                    "oracle_gate": (
                        "accepted"
                        if bool(
                            dict(getattr(resolved_id_result, "metadata", {}) or {}).get(
                                "oracle_assumptions_accepted",
                                False,
                            )
                        )
                        else "required"
                    ),
                    "target_effect": proximal_mediation_certificate.query.target_effect,
                    "treatment_name": proximal_mediation_certificate.query.treatment,
                    "mediator_name": proximal_mediation_certificate.query.mediator,
                    "outcome_name": proximal_mediation_certificate.query.outcome,
                    "treatment_proxy_names": list(
                        proximal_mediation_certificate.variable_roles.get("Z", ())
                    ),
                    "outcome_proxy_names": list(
                        proximal_mediation_certificate.variable_roles.get("W", ())
                    ),
                    "covariate_names": list(
                        proximal_mediation_certificate.variable_roles.get("X", ())
                    ),
                    "n_bootstrap": 200,
                    "confidence_level": 0.95,
                    "ridge": 1.0e-4,
                    "y_lower": (
                        _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )[0]
                        if _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )
                        is not None
                        else None
                    ),
                    "y_upper": (
                        _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )[1]
                        if _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )
                        is not None
                        else None
                    ),
                    "__seed__": int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16),
                },
            )
            bridge_report_payload = proximal_mediation_output.get("bridge_plausibility_report")
            if isinstance(bridge_report_payload, dict):
                bridge_metrics.update(
                    {
                        "bridge_residual_r": bridge_report_payload.get("residual_r"),
                        "bridge_effective_rank": bridge_report_payload.get("effective_rank"),
                        "bridge_sigma_min": bridge_report_payload.get("sigma_min"),
                        "bridge_proxy_association": bridge_report_payload.get(
                            "proxy_association_score"
                        ),
                    }
                )
                readiness_report = build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="proxy_only",
                    fallback_data_available=fallback_data_available,
                    recoverability_certificate=recoverability_summary,
                    missingness_assessment=missingness_assessment,
                    extra_metrics=_float_metrics_from_mapping(bridge_metrics),
                )
            proximal_report = proximal_mediation_output.get("report")
            node_outputs = {"proximal_mediation": proximal_mediation_output}
            negative_payload = proximal_mediation_output.get("negative_certificate")
            bounds_payload = proximal_mediation_output.get("bounds_bundle")
            proximal_negative_cert = (
                NegativeCertificate.model_validate(negative_payload)
                if isinstance(negative_payload, dict)
                else None
            )
            proximal_bounds_bundle = None
            if proximal_negative_cert is not None:
                proximal_bounds_bundle = proximal_negative_cert.bounds_bundle
            if proximal_bounds_bundle is None and isinstance(bounds_payload, dict):
                proximal_bounds_bundle = BoundsBundle.model_validate(bounds_payload)
            if proximal_negative_cert is not None:
                bundle = self.audit(
                    resolved_id_result,
                    proximal_report,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    node_outputs=node_outputs,
                    negative_certificate=proximal_negative_cert,
                    proof_bundle=proof_bundle,
                    bounds_bundle=proximal_bounds_bundle,
                    data_readiness_report=readiness_report,
                )
                return None, bundle, proximal_negative_cert
            if (
                proximal_report is not None
                and getattr(proximal_report, "status", None) is EstimationStatus.SUCCESS
            ):
                bundle = self.audit(
                    resolved_id_result,
                    proximal_report,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    node_outputs=node_outputs,
                    proof_bundle=proof_bundle,
                    data_readiness_report=readiness_report,
                )
                return proximal_report, bundle, None
            bundle = self.audit(
                resolved_id_result,
                proximal_report,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                node_outputs=node_outputs,
                proof_bundle=proof_bundle,
                bounds_bundle=proximal_bounds_bundle or resolved_bounds_bundle,
                data_readiness_report=readiness_report,
            )
            return None, bundle, None

        if resolved_id_result.status is not IdentificationStatus.IDENTIFIED:
            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="unknown",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
            )
            bundle = self.audit(
                resolved_id_result,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                proof_bundle=proof_bundle,
                bounds_bundle=resolved_bounds_bundle,
                dual_certificate_payload=dual_certificate_payload,
                data_readiness_report=readiness_report,
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, None

        if dp_robustness_certificate is not None:
            from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

            dp_readiness = apply_dp_readiness_gate(
                build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="unknown",
                    fallback_data_available=fallback_data_available,
                    recoverability_certificate=recoverability_summary,
                    missingness_assessment=missingness_assessment,
                ),
                dp_robustness_certificate,
            )
            if not dp_readiness.can_run_estimation:
                bundle = self.audit(
                    resolved_id_result,
                    None,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    proof_bundle=proof_bundle,
                    bounds_bundle=resolved_bounds_bundle,
                    dual_certificate_payload=dual_certificate_payload,
                    data_readiness_report=dp_readiness,
                    dp_robustness_certificate=dp_robustness_certificate,
                )
                return None, bundle, None

        # G4: validate query structure and KB feasibility before compiling
        from polisyos.foundry.methods.catalog.causal.query_validator import CausalQueryValidator

        val_report = CausalQueryValidator().validate(
            graph, resolved_id_result.estimand_ast, self._kb
        )
        if val_report.has_errors():
            neg_cert = NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description="; ".join(e.message for e in val_report.errors),
                quantitative_diagnostics={
                    "identification_status": str(resolved_id_result.status.value),
                    "algorithm_version": str(
                        getattr(resolved_id_result, "algorithm_version", "") or ""
                    ),
                },
                constructive_message=(
                    "Fix graph structure or provide required data before proceeding."
                ),
            )
            bundle = self.audit(
                resolved_id_result,
                None,
                run_id=run_id,
                graph=graph,
                negative_certificate=neg_cert,
                proof_bundle=proof_bundle,
                data_readiness_report=build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="unknown",
                    fallback_data_available=fallback_data_available,
                    recoverability_certificate=recoverability_summary,
                    missingness_assessment=missingness_assessment,
                ),
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, neg_cert

        # 2. Optional schema resolution (now that we have the estimand)
        if (
            df_columns is not None
            and df_dtypes is not None
            and resolved_id_result.estimand_ast is not None
        ):
            resolver = SchemaResolver()
            schema_report = resolver.resolve(
                resolved_id_result.estimand_ast,
                df_columns=df_columns,
                df_dtypes=df_dtypes,
            )

        # 3. Compile
        try:
            executor_graph = self.compile(
                resolved_id_result,
                graph=graph,
                n_obs=n_obs,
                covariate_dim=covariate_dim,
                run_id=run_id,
                use_cross_fitting=use_cross_fitting,
            )
        except Exception as exc:
            neg_cert = NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description=f"Compilation failed: {exc}",
                quantitative_diagnostics={
                    "identification_status": str(resolved_id_result.status.value),
                    "algorithm_version": str(
                        getattr(resolved_id_result, "algorithm_version", "") or ""
                    ),
                },
                constructive_message="Check that the estimand AST is valid.",
            )
            bundle = self.audit(
                resolved_id_result,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                negative_certificate=neg_cert,
                proof_bundle=proof_bundle,
                bounds_bundle=resolved_bounds_bundle,
                data_readiness_report=build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="unknown",
                    fallback_data_available=fallback_data_available,
                    missingness_assessment=missingness_assessment,
                ),
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, neg_cert

        # G2: inject diagnostic nodes (PositivityDiagnostic always; SupportMismatch for transport)
        executor_graph = self._inject_diagnostic_nodes(
            executor_graph,
            resolved_id_result.estimand_ast,
        )

        preflight_readiness, preflight_outputs = self._run_readiness_preflight(
            executor_graph=executor_graph,
            data_dict=data_dict,
            sample_size=sample_size,
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_summary,
            missingness_assessment=missingness_assessment,
        )
        if dp_robustness_certificate is not None:
            from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

            preflight_readiness = apply_dp_readiness_gate(
                preflight_readiness,
                dp_robustness_certificate,
            )

        # 4. Estimate only after readiness preflight has allowed execution.
        effect_report: Any = None
        node_outputs: dict[str, Any] = dict(preflight_outputs)
        if (
            data_dict is not None
            and self._registry is not None
            and preflight_readiness.can_run_estimation
        ):
            try:
                effect_report, execution_outputs = self.estimate(executor_graph, data_dict)
                if (
                    effect_report is not None
                    and isinstance(getattr(resolved_id_result, "metadata", None), dict)
                    and resolved_id_result.metadata
                ):
                    effect_report = effect_report.model_copy(
                        update={
                            "metadata": {
                                **dict(effect_report.metadata),
                                **dict(resolved_id_result.metadata),
                            }
                        }
                    )
                node_outputs.update(execution_outputs)
            except Exception:
                pass  # estimate is best-effort; audit still proceeds
        postrun_readiness = _build_postrun_readiness_report(
            node_outputs=node_outputs,
            sample_size=sample_size,
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_summary,
            missingness_assessment=missingness_assessment,
        )
        if postrun_readiness is not None and dp_robustness_certificate is not None:
            from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

            postrun_readiness = apply_dp_readiness_gate(
                postrun_readiness,
                dp_robustness_certificate,
            )
        data_readiness = (
            preflight_readiness
            if not preflight_readiness.can_run_estimation
            else (postrun_readiness or preflight_readiness)
        )

        # 5. Audit
        bundle = self.audit(
            resolved_id_result,
            effect_report,
            run_id=run_id,
            graph=graph,
            executor_graph=executor_graph,
            schema_report=schema_report,
            node_outputs=node_outputs,
            proof_bundle=proof_bundle,
            bounds_bundle=resolved_bounds_bundle,
            data_readiness_report=data_readiness,
            dp_robustness_certificate=dp_robustness_certificate,
        )

        # 6. Build CausalRunSnapshot for reproducibility
        try:
            from polisyos.ir.analytics.causal_run_snapshot import CausalRunSnapshot

            estimand_dict: dict[str, Any] = {}
            if resolved_id_result.estimand_ast is not None:
                try:
                    estimand_dict = resolved_id_result.estimand_ast.model_dump(mode="json")
                except Exception:
                    pass

            snapshot = CausalRunSnapshot.build(
                run_id=run_id,
                graph=graph,
                estimand_ast_dict=estimand_dict,
                estimand_shape=bundle.compilation_steps[0].estimand_shape
                if bundle.compilation_steps
                else "",
                query_str=bundle.query_str,
                estimation_steps=bundle.estimation_steps,
                data_dict=data_dict,
                algorithm_version=bundle.algorithm_version,
                compilation_steps=bundle.compilation_steps,
            )
            # Attach snapshot to bundle metadata for downstream consumers
            bundle = (
                dataclasses.replace(bundle, snapshot=snapshot)
                if hasattr(bundle, "snapshot")
                else bundle
            )
            # Store on engine instance for programmatic access
            self._last_snapshot = snapshot
        except Exception:
            pass  # snapshot is best-effort; never blocks the pipeline

        return effect_report, bundle, None


    def _persist_temporal_payload(
        self,
        payload: dict[str, Any],
        *,
        kind: str,
        schema_name: str,
        schema_version: str = "1.0",
        inputs: list[Any] | None = None,
    ) -> ArtifactRefModel:
        if self._artifact_store is None:
            raise RuntimeError("Temporal payload persistence requires an ArtifactStore")
        ref = put_json_artifact(
            self._artifact_store,
            payload,
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return ArtifactRefModel.model_validate(ref)


    @staticmethod
    def _artifact_input_ref(ref: Any, *, role: str) -> dict[str, str]:
        artifact_id = getattr(ref, "artifact_id", ref)
        return {"artifact_id": str(artifact_id), "role": role}


    def _temporal_input_refs(self, *refs_and_roles: tuple[Any | None, str]) -> list[dict[str, str]]:
        inputs: list[dict[str, str]] = []
        for ref, role in refs_and_roles:
            if ref is None:
                continue
            inputs.append(self._artifact_input_ref(ref, role=role))
        return inputs


    @staticmethod
    def _serialize_ref(ref: Any | None) -> dict[str, Any] | None:
        if ref is None:
            return None
        if hasattr(ref, "model_dump"):
            return ref.model_dump(mode="python")
        if isinstance(ref, dict):
            return dict(ref)
        return None


    def _resolve_temporal_intervention(
        self,
        query: ContinuousTimeQuery,
        *,
        intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
    ) -> tuple[TemporalInterventionTrajectory, ArtifactRefModel | None, str]:
        from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
            TemporalCompileError,
        )

        if intervention is not None:
            resolved = (
                intervention
                if isinstance(intervention, TemporalInterventionTrajectory)
                else TemporalInterventionTrajectory.model_validate(intervention)
            )
            return resolved, None, "override"

        if self._artifact_store is None:
            raise TemporalCompileError(
                "missing_intervention_contract",
                "CausalEngine.temporal_causal_effect requires an intervention override or an ArtifactStore-backed intervention contract.",
            )

        if query.intervention_trajectory_ref is None:
            raise TemporalCompileError(
                "missing_intervention_contract",
                "ContinuousTimeQuery.intervention_trajectory_ref is required for fixed_intervention execution when no override is provided.",
            )

        if query.intervention_trajectory_ref.kind != "ir.temporal_intervention_trajectory":
            raise TemporalCompileError(
                "invalid_intervention_contract_ref",
                "ContinuousTimeQuery.intervention_trajectory_ref must point to an ir.temporal_intervention_trajectory artifact for engine-level execution.",
                details={"kind": query.intervention_trajectory_ref.kind},
            )

        intervention_ref = TemporalInterventionTrajectoryRef.model_validate(
            query.intervention_trajectory_ref.model_dump(mode="python")
        )
        return (
            load_temporal_intervention_trajectory(self._artifact_store, intervention_ref),
            intervention_ref,
            "artifact_store",
        )


    def dynamic_causal_effect(
        self,
        data: DynamicTreatmentData,
        regime: DynamicTreatmentRegime | None = None,
        method: str = "ice_g",
        run_id: str | None = None,
    ) -> GComputationResult:
        """Estimate the causal effect of a dynamic treatment regime.

        Bypasses the standard identify → compile → estimate → audit pipeline
        (which is designed for cross-sectional identification). Uses sequential
        ignorability: A_t ⊥ Y^{ā} | H_t for all t.

        Args:
            data:   DynamicTreatmentData with time-varying treatment and covariates.
            regime: Optional DynamicTreatmentRegime spec. If None, uses the regime
                    specified in params (default: always_treat).
            method: One of "parametric_g", "ice_g", "ltmle", "g_estimation".
            run_id: Optional run identifier for logging.

        Returns:
            GComputationResult (not EvidenceBundle — no graph-based ID step).
        """
        self._require_estimation_readiness(
            data=data,
            treatment="treatment",
            outcome="outcome",
        )
        from polisyos.foundry.methods.catalog.causal.g_computation import (
            ICEGFormula,
            LTMLEEstimator,
            ParametricGFormula,
        )
        from polisyos.foundry.methods.catalog.causal.g_estimation import (
            StructuralNestedMeanModel,
        )
        from polisyos.ir.analytics.dynamic_regime import GComputationResult

        _method_dispatch: dict[str, type] = {
            "parametric_g": ParametricGFormula,
            "ice_g": ICEGFormula,
            "ltmle": LTMLEEstimator,
            "g_estimation": StructuralNestedMeanModel,
        }

        method_cls = _method_dispatch.get(method)
        if method_cls is None:
            raise ValueError(
                f"Unknown dynamic method {method!r}. Choose from: {sorted(_method_dispatch)}"
            )

        params: dict[str, object] = {}
        if regime is not None:
            params["regime"] = regime.rule.value
            params["threshold_covariate_index"] = regime.threshold_covariate_index
            params["threshold_value"] = regime.threshold_value

        result = method_cls.pure_step(data, params)
        g_result = result.get("g_result")
        if g_result is None:
            # g_estimation returns snmm_result, not g_result — wrap into GComputationResult
            report = result.get("report")
            if report is not None and hasattr(report, "point_estimate"):
                from polisyos.ir.analytics.dynamic_regime import GComputationResult

                g_result = GComputationResult(
                    counterfactual_mean=float(report.point_estimate or 0.0),
                    confidence_interval=report.confidence_interval or (0.0, 0.0),
                    confidence_level=0.95,
                    standard_error=float(report.standard_error or 0.0),
                    regime=str(params.get("regime", "always_treat")),
                    n_units=report.sample_size,
                    n_periods=report.pre_periods,
                    method="ice_g",
                )
            else:
                raise RuntimeError(
                    f"Method {method!r} did not return a GComputationResult. "
                    "Check that the estimator succeeded."
                )
        return g_result


    def temporal_causal_effect(
        self,
        data: Any,
        query: ContinuousTimeQuery,
        *,
        regime: DynamicTreatmentRegime | None = None,
        intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
        method: str = "linear_sde",
        identification_certificate: TemporalIdentificationCertificate
        | dict[str, Any]
        | None = None,
    ) -> Any:
        """Estimate a temporal effect trajectory and optionally persist its bundle."""

        readiness_treatment = "treatment"
        readiness_outcome = "outcome"
        if str(method).strip().lower() == "event_process_weighting":
            readiness_treatment = "policy_weights"
            readiness_outcome = "outcome_events"
        if str(method).strip().lower() != "event_process_weighting":
            self._require_estimation_readiness(
                data=data,
                treatment=readiness_treatment,
                outcome=readiness_outcome,
            )
        from polisyos.foundry.methods.catalog.causal.dtr import estimate_dtr_trajectory
        from polisyos.foundry.methods.catalog.causal.event_process_weighting import (
            estimate_event_process_weighting_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.g_computation import (
            estimate_g_computation_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.protocols import (
            DynamicTreatmentData,
            EventProcessObservationalData,
            PanelObservationalData,
        )
        from polisyos.foundry.methods.catalog.causal.structural_time_series import (
            estimate_structural_time_series_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
            TemporalCompileError,
        )

        resolved_identification_certificate = self._normalize_temporal_identification_certificate(
            identification_certificate,
            query=query,
        )
        effective_query = query.model_copy(
            update={
                "metadata": {
                    **query.metadata,
                    "preferred_backend": method,
                    **(
                        {
                            "temporal_identification_certificate": (
                                resolved_identification_certificate.model_dump(mode="json")
                            )
                        }
                        if resolved_identification_certificate is not None
                        else {}
                    ),
                }
            }
        )
        if resolved_identification_certificate is not None:
            effective_query = effective_query.model_copy(
                update={
                    "metadata": {
                        **effective_query.metadata,
                        "identification_scope": self._temporal_identification_scope_snapshot(
                            effective_query,
                            resolved_identification_certificate,
                        ),
                    }
                }
            )

        panel_data: PanelObservationalData | None = None
        dynamic_data: DynamicTreatmentData | None = None
        event_process_data: EventProcessObservationalData | None = None
        if isinstance(data, EventProcessObservationalData):
            event_process_data = data
        elif isinstance(data, PanelObservationalData):
            panel_data = data
        elif isinstance(data, DynamicTreatmentData):
            dynamic_data = data
        else:
            preferred_backend = str(
                effective_query.metadata.get("preferred_backend", "linear_sde")
            ).strip()
            if preferred_backend == "event_process_weighting":
                event_process_data = EventProcessObservationalData.model_validate(data)
            else:
                try:
                    panel_data = PanelObservationalData.model_validate(data)
                except Exception:
                    try:
                        dynamic_data = DynamicTreatmentData.model_validate(data)
                    except Exception:
                        event_process_data = EventProcessObservationalData.model_validate(data)

        if effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY and (
            panel_data is not None or regime is not None
        ):
            raise TemporalCompileError(
                "query_mode_conflict",
                "optimal_policy_discovery is only supported for the DTR temporal route.",
            )
        if (
            effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
            and intervention is not None
        ):
            raise TemporalCompileError(
                "query_mode_conflict",
                "optimal_policy_discovery queries do not accept a fixed intervention override.",
            )

        resolved_intervention: TemporalInterventionTrajectory | None
        intervention_ref: ArtifactRefModel | None
        intervention_resolution_source: str
        if effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY:
            resolved_intervention = None
            intervention_ref = None
            intervention_resolution_source = "policy_discovery"
        else:
            resolved_intervention, intervention_ref, intervention_resolution_source = (
                self._resolve_temporal_intervention(
                    effective_query,
                    intervention=intervention,
                )
            )

        scalar_result: Any | None = None
        policy_ref: DynamicTreatmentRegimeRef | None = None
        derived_schedule_ref: ArtifactRefModel | None = None
        if event_process_data is not None:
            trajectory = estimate_event_process_weighting_trajectory(
                event_process_data,
                effective_query,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
            )
        elif panel_data is not None:
            trajectory = estimate_structural_time_series_trajectory(
                panel_data,
                effective_query,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
            )
        elif regime is not None:
            estimator_method = str(
                effective_query.metadata.get("temporal_estimator_method", "parametric_g")
            )
            scalar_result, trajectory = estimate_g_computation_trajectory(
                dynamic_data,
                effective_query,
                regime=regime,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
                method=estimator_method,
            )
        else:
            estimator_method = str(
                effective_query.metadata.get("temporal_estimator_method", "q_learning")
            )
            scalar_result, trajectory = estimate_dtr_trajectory(
                dynamic_data,
                effective_query,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
                intervention_contract_status=(
                    "derived_optimal_policy"
                    if effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
                    else None
                ),
                method=estimator_method,
            )
            if effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY:
                resolved_intervention = trajectory.plan.resolved_intervention

        if (
            intervention_ref is None
            and resolved_intervention is not None
            and self._artifact_store is not None
        ):
            intervention_ref = persist_temporal_intervention_trajectory(
                self._artifact_store,
                resolved_intervention,
            )
            if effective_query.query_mode is TemporalQueryMode.FIXED_INTERVENTION:
                effective_query = effective_query.model_copy(
                    update={"intervention_trajectory_ref": intervention_ref}
                )
            else:
                derived_schedule_ref = intervention_ref

        if self._artifact_store is not None:
            if (
                effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
                and scalar_result is not None
            ):
                policy_ref = persist_dynamic_treatment_regime(
                    self._artifact_store,
                    scalar_result.optimal_regime,
                )
                derived_schedule_ref = intervention_ref
            query_ref = persist_continuous_time_query(self._artifact_store, effective_query)
            proof_payload = self.identify_continuous_time_query(
                effective_query,
                identification_certificate=resolved_identification_certificate,
                query_ref=str(query_ref.artifact_id),
            )
            local_independence_certificate_ref = None
            temporal_identification_certificate_ref = None
            proof_temporal_certificate = resolved_identification_certificate
            identification_scope = None
            try:
                payload = proof_payload.metadata.get("local_independence_certificate_ref")
                if isinstance(payload, dict):
                    local_independence_certificate_ref = ArtifactRefModel.model_validate(payload)
            except Exception:
                local_independence_certificate_ref = None
            try:
                payload = proof_payload.metadata.get("temporal_identification_certificate_ref")
                if isinstance(payload, dict):
                    temporal_identification_certificate_ref = (
                        TemporalIdentificationCertificateRef.model_validate(payload)
                    )
            except Exception:
                temporal_identification_certificate_ref = None
            try:
                payload = proof_payload.metadata.get("temporal_identification_certificate")
                if payload is not None:
                    proof_temporal_certificate = (
                        self._normalize_temporal_identification_certificate(payload)
                    )
            except Exception:
                pass
            payload = proof_payload.metadata.get("identification_scope")
            if isinstance(payload, dict):
                identification_scope = dict(payload)
            elif proof_temporal_certificate is not None:
                identification_scope = self._temporal_identification_scope_snapshot(
                    effective_query,
                    proof_temporal_certificate,
                )
            if identification_scope is not None:
                trajectory.metadata["identification_scope"] = identification_scope
                trajectory.metadata["identification_support_status"] = str(
                    identification_scope.get("support_status")
                )
            proof_bundle_ref = persist_proof_bundle(
                self._artifact_store,
                proof_payload,
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (
                        temporal_identification_certificate_ref,
                        "temporal_identification_certificate",
                    ),
                    (
                        local_independence_certificate_ref,
                        "local_independence_certificate",
                    ),
                ),
            )
            trajectory_ref = self._persist_temporal_payload(
                trajectory.trajectory_payload(),
                kind="ir.temporal_trajectory",
                schema_name="ir.temporal_trajectory",
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                ),
            )
            confidence_band_ref = self._persist_temporal_payload(
                trajectory.confidence_band_payload(),
                kind="ir.temporal_confidence_band",
                schema_name="ir.temporal_confidence_band",
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (trajectory_ref, "trajectory"),
                ),
            )
            if proof_temporal_certificate is not None:
                trajectory.metadata["temporal_identification_certificate"] = (
                    proof_temporal_certificate.model_dump(mode="json")
                )
            solver_diagnostics_payload = trajectory.solver_diagnostics_payload()
            diagnostics_ref = self._persist_temporal_payload(
                solver_diagnostics_payload,
                kind="ir.temporal_solver_diagnostics",
                schema_name="ir.temporal_solver_diagnostics",
                schema_version=str(solver_diagnostics_payload.get("schema_version", "1.0")),
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (trajectory_ref, "trajectory"),
                ),
            )
            rough_path_metadata = {
                key: value
                for key, value in {
                    "path_semantics": trajectory.metadata.get("path_semantics"),
                    "rough_path_certificate": trajectory.metadata.get("rough_path_certificate"),
                    "rough_path_identification_status": trajectory.metadata.get(
                        "rough_path_identification_status"
                    ),
                    "rough_path_runtime_support": trajectory.metadata.get(
                        "rough_path_runtime_support"
                    ),
                }.items()
                if value is not None
            }
            bundle = EffectTrajectoryBundle(
                query_ref=query_ref,
                trajectory_ref=trajectory_ref,
                confidence_band_ref=confidence_band_ref,
                solver_diagnostics_ref=diagnostics_ref,
                identification_certificate_ref=temporal_identification_certificate_ref,
                discretization_error=trajectory.discretization_error,
                discretization_note=trajectory.discretization_note,
                path_representation=trajectory.path_representation,
                solver_family=trajectory.solver_family,
                time_scale=effective_query.time_scale,
                interpolation_policy=effective_query.interpolation_policy,
                strategic_adaptation_mode=StrategicAdaptationMode.ABSENT,
                continuous_time_degraded=trajectory.continuous_time_degraded,
                metadata={
                    "backend_target": trajectory.plan.backend_target.value,
                    "fallback_mode": trajectory.plan.fallback_mode.value,
                    "comparator_semantics": trajectory.plan.comparator_semantics.value,
                    "scalar_result_method": getattr(scalar_result, "method", None),
                    "execution_contract_kind": effective_query.query_mode.value,
                    "intervention_contract_status": trajectory.plan.intervention_contract_status,
                    "intervention_resolution_source": intervention_resolution_source,
                    "intervention_artifact_ref": self._serialize_ref(intervention_ref),
                    "policy_artifact_ref": self._serialize_ref(policy_ref),
                    "derived_schedule_ref": self._serialize_ref(derived_schedule_ref),
                    "temporal_identification_certificate_ref": self._serialize_ref(
                        temporal_identification_certificate_ref
                    ),
                    "local_independence_certificate_ref": self._serialize_ref(
                        local_independence_certificate_ref
                    ),
                    "proof_bundle_ref": self._serialize_ref(proof_bundle_ref),
                    "proof_bundle_artifact_id": str(proof_bundle_ref.artifact_id),
                    "proof_status": proof_payload.proof_status,
                    "identification_scope": identification_scope,
                    "identification_support_status": (
                        None
                        if identification_scope is None
                        else identification_scope.get("support_status")
                    ),
                    **rough_path_metadata,
                },
            )
            bundle_ref = persist_effect_trajectory_bundle(
                self._artifact_store,
                bundle,
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (
                        temporal_identification_certificate_ref,
                        "temporal_identification_certificate",
                    ),
                    (trajectory_ref, "trajectory"),
                    (confidence_band_ref, "confidence_band"),
                    (diagnostics_ref, "solver_diagnostics"),
                ),
            )
            trajectory.effect_bundle = bundle
            trajectory.metadata["effect_bundle_artifact_id"] = str(bundle_ref.artifact_id)
            trajectory.metadata["proof_bundle_artifact_id"] = str(proof_bundle_ref.artifact_id)
            trajectory.metadata["proof_status"] = proof_payload.proof_status
        elif (
            effective_query.query_mode is TemporalQueryMode.FIXED_INTERVENTION
            and intervention is None
        ):
            raise TemporalCompileError(
                "missing_intervention_contract",
                "Engine-level temporal execution without ArtifactStore requires an explicit intervention override.",
            )

        if scalar_result is not None:
            trajectory.metadata["scalar_result_method"] = getattr(scalar_result, "method", None)
        trajectory.metadata["intervention_resolution_source"] = intervention_resolution_source
        trajectory.metadata["execution_contract_kind"] = effective_query.query_mode.value
        if (
            "identification_scope" not in trajectory.metadata
            and resolved_identification_certificate is not None
        ):
            identification_scope = self._temporal_identification_scope_snapshot(
                effective_query,
                resolved_identification_certificate,
            )
            trajectory.metadata["identification_scope"] = identification_scope
            trajectory.metadata["identification_support_status"] = str(
                identification_scope.get("support_status")
            )
            trajectory.metadata["temporal_identification_certificate"] = (
                resolved_identification_certificate.model_dump(mode="json")
            )
        if policy_ref is not None:
            trajectory.metadata["policy_artifact_id"] = str(policy_ref.artifact_id)
        if derived_schedule_ref is not None:
            trajectory.metadata["derived_schedule_artifact_id"] = str(
                derived_schedule_ref.artifact_id
            )
        return trajectory


__all__ = [name for name in globals() if not name.startswith("__")]
