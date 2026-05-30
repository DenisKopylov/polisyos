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

from . import estimation as _estimation
from . import identification as _identification

globals().update({name: getattr(_identification, name) for name in dir(_identification) if not name.startswith("__")})
globals().update({name: getattr(_estimation, name) for name in dir(_estimation) if not name.startswith("__")})


# ──────────────────────────────────────────────────────────────────────────────
# Method 1: PartialInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "cluster", "spillover"},
)
class PartialInterferenceEstimator:
    """Clustered partial interference estimator (Hudgens & Halloran 2008).

    Decomposes average causal effects into a **direct effect** (own
    treatment, neighbours' allocation fixed) and a **spillover effect**
    (change in outcome from shifting cluster allocation from α_low to
    α_high, own treatment fixed at 0).

    Requires ``cluster_id`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="partial",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                    description="Observed outcome Y_i for each unit.",
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                    description="Binary treatment indicator A_i ∈ {0, 1}.",
                ),
                SlotSpec(
                    name="cluster_id",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("category", "id"),
                    shape=("n_units",),
                    description="Integer cluster membership c_i.",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                    description="Optional pre-treatment covariates X_i.",
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="alpha_high",
                default=0.5,
                description="High-coverage allocation arm α₁.",
            ),
            ParameterSpec(
                name="alpha_low",
                default=0.0,
                description="Low-coverage allocation arm α₂ (usually 0).",
            ),
            ParameterSpec(
                name="alpha_bandwidth",
                default=0.1,
                description="Tolerance window for α-stratum membership.",
            ),
            ParameterSpec(
                name="exposure_mapping",
                default="fractional",
                description="Exposure mapping type: 'fractional' or 'threshold'.",
            ),
            ParameterSpec(
                name="threshold",
                default=0.5,
                description="Threshold for binary exposure mapping.",
            ),
            ParameterSpec(
                name="confidence_level",
                default=0.95,
                description="Confidence level for interval estimates.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Clustered partial interference estimator. Decomposes ATE into "
            "direct effect DE(α) = E[Y(1,α)] − E[Y(0,α)] and spillover effect "
            "SE(α₁,α₂) = E[Y(0,α₁)] − E[Y(0,α₂)] using IPW with exposure "
            "mapping within clusters."
        ),
        tags=frozenset({"causal", "interference", "cluster", "spillover"}),
        citations=(
            "Hudgens, M.G. & Halloran, M.E. (2008). Toward causal inference with "
            "interference. JASA 103(482).",
            "Sobel, M.E. (2006). What do randomized studies of housing mobility "
            "demonstrate? JASA 101(476).",
            "Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal "
            "inference in the presence of interference. Stat. Methods Med. Res.",
        ),
        equations={
            "direct_effect": "DE(α) = E[Y(1,α)] - E[Y(0,α)]",
            "spillover_effect": "SE(α1,α2) = E[Y(0,α1)] - E[Y(0,α2)]",
            "total_effect": "TE(α1,α2) = E[Y(1,α1)] - E[Y(0,α2)]",
            "exposure_mapping_fractional": "f_i = Σ_{j≠i,c} A_j / (n_c - 1)",
        },
        assumptions={
            "partial_interference": "Units in different clusters do not interfere.",
            "stratified_interference": (
                "Within a cluster, a unit's potential outcome depends only on "
                "its own treatment and the aggregate cluster allocation."
            ),
            "positivity": ("P(A_i=a, f_i≈α | X_i) > 0 for all a ∈ {0,1} and α ∈ {α_low, α_high}."),
        },
        when_to_use=(
            "Cluster-randomised experiments or observational studies where "
            "interference is limited to within pre-defined groups (villages, "
            "schools, households, clinics)."
        ),
        when_not_to_use=(
            "Cross-cluster interference; continuous treatment; single-unit "
            "clusters (cluster_size=1)."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: effect of own treatment, holding neighbours' "
            "allocation fixed at α_high. "
            "spillover_effect: effect of shifting cluster allocation from "
            "α_low to α_high, own treatment fixed at 0."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_partial_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 2: NetworkAIPWEstimator
# ──────────────────────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "network", "aipw", "spillover"},
)
class NetworkAIPWEstimator:
    """General network AIPW estimator (Aronow & Samii 2017).

    Uses an arbitrary adjacency matrix to define the exposure mapping
    f(A, N_i) → exposure level, then applies doubly-robust AIPW
    estimation within exposure strata.

    Requires ``adjacency_matrix`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="network_aipw",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="adjacency_matrix",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("adjacency", "weight"),
                    shape=("n_units", "n_units"),
                    description="Network adjacency (weighted or binary).",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="exposure_mapping",
                default="fraction",
                description="'fraction' | 'count' | 'any'",
            ),
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(
                name="n_bootstrap",
                default=200,
                description="Bootstrap draws for variance estimation.",
            ),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Doubly-robust AIPW estimator under general network interference. "
            "Uses an exposure mapping f(A, N_i) derived from the adjacency "
            "matrix to define treatment×exposure strata, then applies AIPW "
            "within each stratum."
        ),
        tags=frozenset({"causal", "interference", "network", "aipw", "spillover"}),
        citations=(
            "Aronow, P.M. & Samii, C. (2017). Estimating average causal "
            "effects under general interference. Ann. Appl. Stat. 11(4).",
            "Liu, L., Hudgens, M.G. & Becker-Dreps, S. (2016). On sample "
            "randomization inference of causal effects in the presence of "
            "interference. JRSS-B.",
        ),
        equations={
            "exposure_fraction": "e_i = (Σ_j W_ij A_j) / (Σ_j W_ij)",
            "aipw_score": "ψ_i = I(stratum)/P(stratum|X) * Y - (I/P - 1) * μ̂(X)",
        },
        assumptions={
            "no_unmeasured_confounding": "Treatment ignorable given covariates.",
            "exposure_positivity": "P(e_i = e | X_i) > 0 for all exposure levels e.",
            "network_structure_known": "Adjacency matrix W is observed without error.",
        },
        when_to_use=(
            "Social network experiments or observational studies with an "
            "observed interaction graph where spillover is mediated by "
            "direct connections."
        ),
        when_not_to_use="Unobserved network structure; very sparse networks.",
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: E[Y(1,high)] - E[Y(0,high)] — effect of own "
            "treatment among units with high network exposure. "
            "spillover_effect: E[Y(0,high)] - E[Y(0,low)] — effect of "
            "having highly-treated neighbours."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_network_aipw(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 3: SpatialInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "spatial", "spillover"},
)
class SpatialInterferenceEstimator:
    """Gaussian kernel spatial spillover estimator.

    Constructs a kernel-weighted exposure mapping
    s_i = Σ_j K(d_ij; h) A_j / Σ_j K(d_ij; h)
    using geographic ``coordinates``, then estimates direct and spillover
    effects across high/low exposure strata.

    Requires ``coordinates`` (or falls back to ``adjacency_matrix``) in
    the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="spatial",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="coordinates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("space", "coordinate"),
                    shape=("n_units", "n_dims"),
                    description="Spatial coordinates [x, y] or [lon, lat].",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="bandwidth",
                default="auto",
                description="Kernel bandwidth h or 'auto' for Silverman ROT.",
            ),
            ParameterSpec(
                name="kernel",
                default="gaussian",
                description="Kernel function: 'gaussian'.",
            ),
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(
                name="compute_maup_certificate",
                default=False,
                description="When true, attach a MAUP invariance certificate using candidate_partitions.",
            ),
            ParameterSpec(
                name="compute_hodge_diagnostics",
                default=False,
                description=(
                    "When true, attach multiscale graph-Hodge diagnostics for declared and "
                    "candidate areal supports."
                ),
            ),
            ParameterSpec(
                name="candidate_partitions",
                default=(),
                description="Optional zoning schemes used for MAUP invariance checks.",
            ),
            ParameterSpec(name="scale_id", default="declared"),
            ParameterSpec(name="zoning_id", default="observed_support"),
            ParameterSpec(name="aggregation_rule", default="mean"),
            ParameterSpec(name="weight_spec", default=None),
            ParameterSpec(name="estimand", default="spillover"),
            ParameterSpec(name="effect_scale", default="mean_difference"),
            ParameterSpec(name="maup_alpha", default=0.05),
            ParameterSpec(name="maup_bandwidth", default=None),
            ParameterSpec(name="maup_probe_max_covariates", default=3),
            ParameterSpec(name="hodge_max_triangles", default=4096),
            ParameterSpec(name="treatment_threshold", default=0.5),
            ParameterSpec(name="lumpability_warn_threshold", default=0.01),
            ParameterSpec(name="lumpability_block_threshold", default=0.05),
            ParameterSpec(name="min_cell_ess_warn", default=50),
            ParameterSpec(name="min_cell_ess_block", default=20),
            ParameterSpec(name="min_cell_positivity_block", default=0.01),
            ParameterSpec(name="partitions_selected_post_outcome", default=False),
            ParameterSpec(name="interaction_complex_ref", default=None),
            ParameterSpec(name="interference_certificate_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Kernel-weighted geographic spillover estimator. Builds a "
            "Gaussian exposure mapping from spatial coordinates, then "
            "estimates direct effect DE and spillover SE via IPW across "
            "high/low kernel-exposure strata. Optional MAUP and multiscale "
            "Hodge diagnostics surface scale/zoning dependence on aggregated areas."
        ),
        tags=frozenset({"causal", "interference", "spatial", "spillover"}),
        citations=(
            "Verbitsky-Savitz, N. & Raudenbush, S.W. (2012). Causal "
            "inference under interference in spatial settings. Epidemiol. Methods.",
            "Aronow, P.M. & Samii, C. (2017). Estimating average causal "
            "effects under general interference. Ann. Appl. Stat. 11(4).",
        ),
        equations={
            "kernel_exposure": "s_i = Σ_j K(‖x_i - x_j‖; h) A_j / Σ_j K(‖x_i - x_j‖; h)",
            "gaussian_kernel": "K(d; h) = exp(-d² / (2h²))",
            "bandwidth_rot": "h* = σ_coords · n^(-1/5)",
        },
        assumptions={
            "spatial_spillover": "Interference decays smoothly with geographic distance.",
            "kernel_specification": "Gaussian kernel captures the decay structure adequately.",
            "positivity": "Positive probability of each spatial exposure level.",
        },
        when_to_use=(
            "Geographic policy evaluation (environmental regulations, "
            "infrastructure, epidemics) where spillover is plausibly distance-based."
        ),
        when_not_to_use="Non-geographic networks; sharp spillover cutoffs.",
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: effect of own treatment, controlling for "
            "spatial exposure. spillover_effect: effect of being in a "
            "high-treatment neighbourhood vs a low-treatment neighbourhood. "
            "When compute_maup_certificate=true, the result also reports whether "
            "the spatial effect is stable across declared alternative partitions. "
            "When compute_hodge_diagnostics=true, the result also reports gradient/curl/"
            "harmonic energy shares across declared spatial supports."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_spatial_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 4: BipartiteInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "bipartite", "spillover"},
)
class BipartiteInterferenceEstimator:
    """Bipartite causal inference with interference (Zigler & Papadogeorgou 2021).

    For settings where treatment units (e.g. power plants, hospitals) are
    distinct from outcome units (e.g. counties, patients).  Interference
    flows from treatment units to outcome units through a bipartite graph.

    Requires ``bipartite_edges`` and ``treatment_unit_ids`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bipartite",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                    description="Observed Y_i for all n units (tx + outcome units).",
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                    description="Binary treatment A_i; non-zero only for treatment units.",
                ),
                SlotSpec(
                    name="bipartite_edges",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("graph", "edge"),
                    shape=("n_edges", "2"),
                    description="[treatment_unit_idx, outcome_unit_idx] edges.",
                ),
                SlotSpec(
                    name="treatment_unit_ids",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("category", "id"),
                    shape=("n_treatment_units",),
                    description="Integer indices of treatment units within the n-unit array.",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(
                name="aggregate_fn",
                default="fraction",
                description="'fraction' | 'count' | 'max'",
            ),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Bipartite interference estimator for settings with separate "
            "treatment and outcome units linked by a bipartite graph. "
            "Aggregates upstream treatment into a per-outcome-unit exposure "
            "g_i and estimates effects across high/low exposure strata."
        ),
        tags=frozenset({"causal", "interference", "bipartite", "spillover"}),
        citations=(
            "Zigler, C.M. & Papadogeorgou, G. (2021). Bipartite causal "
            "inference with interference. Stat. Sci. 36(3).",
            "Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal "
            "inference in the presence of interference. Stat. Methods Med. Res.",
        ),
        equations={
            "aggregate_exposure_fraction": "g_i = (1/|N_i|) Σ_{j ∈ N_i} A_j",
            "aggregate_exposure_count": "g_i = Σ_{j ∈ N_i} A_j",
        },
        assumptions={
            "bipartite_structure": (
                "Outcome units are distinct from treatment units; "
                "interference acts only through the bipartite graph."
            ),
            "positivity": "P(g_i ≥ α_high | X_i) > 0 and P(g_i ≤ α_low | X_i) > 0.",
            "no_unmeasured_confounding": "Treatment unit assignments ignorable given covariates.",
        },
        when_to_use=(
            "Power-plant emission regulation studies (plants → counties), "
            "hospital interventions (hospitals → patients), "
            "supplier interventions (suppliers → retailers)."
        ),
        when_not_to_use="Treatment and outcome units are the same; treatment is continuous.",
        typical_min_obs=50,
        output_interpretation=(
            "direct_effect ≡ spillover_effect: contrast E[Y(high)] - E[Y(low)] "
            "for outcome units — effect of being downstream of more treated "
            "treatment units."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_bipartite_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


__all__ = [
    "BipartiteInterferenceEstimator",
    "InterferenceAugmentedGraph",
    "InterferenceIdentificationResult",
    "NetworkAIPWEstimator",
    "PartialInterferenceEstimator",
    "SpatialInterferenceEstimator",
    "build_block_stratified_network_causal_data",
    "build_interference_topology_contracts",
    "identify_interference_effect",
]
