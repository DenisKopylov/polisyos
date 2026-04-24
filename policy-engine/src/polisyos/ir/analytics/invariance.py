"""Multi-environment and invariance-learning contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_finite_numeric, ensure_unique_ids
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    CausalGraphModelRef,
    RegimeShiftIdentificationCertificateRef,
)


class EnvironmentShiftType(str, Enum):
    """Distribution shift classes observed across environments."""

    COVARIATE = "covariate"
    INTERVENTIONAL = "interventional"
    SELECTION = "selection"
    TEMPORAL = "temporal"


class InvarianceMethod(str, Enum):
    """Frontier multi-environment causal methods."""

    ICP = "icp"
    IRM = "irm"
    ANCHOR_REGRESSION = "anchor_regression"
    ENVIRONMENT_AWARE_DISCOVERY = "environment_aware_discovery"


class InvarianceVerdict(str, Enum):
    """Outcome of an invariance evaluation run."""

    ACCEPTED = "accepted"
    PARTIAL = "partial"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class EnvironmentSpec(BaseModel):
    """One observed environment or deployment regime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    environment_id: str = Field(min_length=1)
    shift_type: EnvironmentShiftType
    context_features: tuple[str, ...] = ()
    role: str = Field(default="source", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_environment(self) -> EnvironmentSpec:
        ensure_unique_ids(
            self.context_features,
            key_fn=lambda item: item,
            label="environment context_feature",
        )
        return self


class InvariantMechanismHypothesis(BaseModel):
    """One hypothesis about an invariant mechanism across environments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str = Field(min_length=1)
    target_variable: str = Field(min_length=1)
    invariant_parents: tuple[str, ...] = ()
    violating_environments: tuple[str, ...] = ()
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_hypothesis(self) -> InvariantMechanismHypothesis:
        ensure_unique_ids(
            self.invariant_parents,
            key_fn=lambda item: item,
            label="invariant parent",
        )
        ensure_unique_ids(
            self.violating_environments,
            key_fn=lambda item: item,
            label="violating environment",
        )
        if self.score is not None:
            ensure_finite_numeric(self.score, field_name=f"{self.hypothesis_id}.score")
        return self


class MultiEnvironmentCausalContract(BaseModel):
    """Contract surface for multi-environment causal identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    method: InvarianceMethod
    target_variable: str = Field(min_length=1)
    intervention_field: str | None = None
    environments: list[EnvironmentSpec] = Field(..., min_length=1)
    assumptions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_contract(self) -> MultiEnvironmentCausalContract:
        ensure_unique_ids(
            self.environments,
            key_fn=lambda item: item.environment_id,
            label="environment_id",
        )
        return self


class InvarianceResult(BaseModel):
    """Frozen result contract for multi-environment invariance analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    method: InvarianceMethod
    verdict: InvarianceVerdict
    hypotheses: list[InvariantMechanismHypothesis] = Field(default_factory=list)
    accepted_hypothesis_ids: tuple[str, ...] = ()
    rejected_hypothesis_ids: tuple[str, ...] = ()
    environment_risks: dict[str, float] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> InvarianceResult:
        ensure_unique_ids(
            self.hypotheses,
            key_fn=lambda item: item.hypothesis_id,
            label="hypothesis_id",
        )
        hypothesis_ids = {item.hypothesis_id for item in self.hypotheses}
        missing_accepted = set(self.accepted_hypothesis_ids) - hypothesis_ids
        missing_rejected = set(self.rejected_hypothesis_ids) - hypothesis_ids
        if missing_accepted:
            raise ValueError(
                f"accepted_hypothesis_ids reference unknown hypotheses {sorted(missing_accepted)}"
            )
        if missing_rejected:
            raise ValueError(
                f"rejected_hypothesis_ids reference unknown hypotheses {sorted(missing_rejected)}"
            )
        shared = set(self.accepted_hypothesis_ids) & set(self.rejected_hypothesis_ids)
        if shared:
            raise ValueError(
                f"accepted_hypothesis_ids and rejected_hypothesis_ids overlap {sorted(shared)}"
            )
        for environment_id, risk in self.environment_risks.items():
            if not environment_id.strip():
                raise ValueError("environment_risks keys must be non-empty")
            ensure_finite_numeric(risk, field_name=f"environment_risks.{environment_id}")
        return self


class RegimeShiftProducedBy(BaseModel):
    """Producer metadata for a regime-shift identification certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str = Field(default="causal.discovery.icp_regime_shifts", min_length=1)
    implementation: str = Field(default="icp_regime_shift_v1", min_length=1)
    code_version: str | None = Field(default=None, min_length=1)


class RegimeShiftDataSignature(BaseModel):
    """Dataset and variable fingerprint used by regime-shift discovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_ref: str | None = Field(default=None, min_length=1)
    variables: tuple[str, ...]
    time_grain: str | None = Field(default=None, min_length=1)
    sample_sizes_by_env: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_signature(self) -> RegimeShiftDataSignature:
        if not self.variables:
            raise ValueError("variables must be non-empty")
        ensure_unique_ids(self.variables, key_fn=lambda item: item, label="regime variable")
        for env_id, sample_size in self.sample_sizes_by_env.items():
            if not env_id.strip():
                raise ValueError("sample_sizes_by_env keys must be non-empty")
            if sample_size < 0:
                raise ValueError("sample_sizes_by_env values must be non-negative")
        return self


class RegimeShiftTimeWindow(BaseModel):
    """Optional time window used to construct one environment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: str | None = Field(default=None, min_length=1)
    end: str | None = Field(default=None, min_length=1)


class RegimeShiftEnvironmentConstruction(BaseModel):
    """How one environment/regime was carved from the source data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(default="manual", min_length=1)
    notes: tuple[str, ...] = ()
    boundary_excluded: bool = False


class RegimeShiftSummary(BaseModel):
    """Observed shift diagnostics for one environment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detected_covariate_shifts: tuple[str, ...] = ()
    detected_target_shift_flags: dict[str, bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_shift_summary(self) -> RegimeShiftSummary:
        ensure_unique_ids(
            self.detected_covariate_shifts,
            key_fn=lambda item: item,
            label="detected_covariate_shift",
        )
        if any(not target.strip() for target in self.detected_target_shift_flags):
            raise ValueError("detected_target_shift_flags keys must be non-empty")
        return self


class RegimeShiftEnvironmentRecord(BaseModel):
    """One environment used by an ICP-style discovery run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    env_id: str = Field(min_length=1)
    regime_id: str | None = Field(default=None, min_length=1)
    time_window: RegimeShiftTimeWindow | None = None
    construction: RegimeShiftEnvironmentConstruction = Field(
        default_factory=RegimeShiftEnvironmentConstruction
    )
    shift_summary: RegimeShiftSummary = Field(default_factory=RegimeShiftSummary)


class RegimeShiftInvarianceTesting(BaseModel):
    """Statistical test configuration recorded by the certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha: float = Field(default=0.05, ge=0.0, le=1.0)
    multiple_testing: str = Field(default="bh", min_length=1)
    test_family: str = Field(default="residual_distribution", min_length=1)
    model_class: str = Field(default="linear_ols", min_length=1)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_testing(self) -> RegimeShiftInvarianceTesting:
        ensure_finite_numeric(self.alpha, field_name="alpha")
        return self


class RegimeShiftCandidateSetPlan(BaseModel):
    """Candidate parent set search plan for one target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enumeration: str = Field(default="all_subsets_upto_k", min_length=1)
    max_set_size: int = Field(default=2, ge=0)
    screening: str | None = Field(default=None, min_length=1)


class RegimeShiftSetTestResult(BaseModel):
    """Invariance test result for one candidate parent set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    S: tuple[str, ...] = ()
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_set_result(self) -> RegimeShiftSetTestResult:
        ensure_unique_ids(self.S, key_fn=lambda item: item, label="candidate set variable")
        if self.p_value is not None:
            ensure_finite_numeric(self.p_value, field_name="p_value")
        return self


class RegimeShiftStabilityMetrics(BaseModel):
    """Population/finite-sample stability summary for one target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_set_count: int = Field(default=0, ge=0)
    intersection_size: int = Field(default=0, ge=0)
    stability_ratio: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_metrics(self) -> RegimeShiftStabilityMetrics:
        for variable, ratio in self.stability_ratio.items():
            if not variable.strip():
                raise ValueError("stability_ratio keys must be non-empty")
            ensure_finite_numeric(ratio, field_name=f"stability_ratio.{variable}")
            if not (0.0 <= ratio <= 1.0):
                raise ValueError(f"stability_ratio.{variable} must be in [0,1]")
        return self


class RegimeShiftInformativeness(BaseModel):
    """Environment informativeness and redundancy diagnostics for one target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    empty_set_stable: bool = False
    redundant_envs: tuple[str, ...] = ()
    leave_one_out_parent_changes: dict[str, bool] = Field(default_factory=dict)
    leave_one_out_minimal_set_changes: dict[str, bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_informativeness(self) -> RegimeShiftInformativeness:
        ensure_unique_ids(self.redundant_envs, key_fn=lambda item: item, label="redundant env")
        if any(not env_id.strip() for env_id in self.leave_one_out_parent_changes):
            raise ValueError("leave_one_out_parent_changes keys must be non-empty")
        if any(not env_id.strip() for env_id in self.leave_one_out_minimal_set_changes):
            raise ValueError("leave_one_out_minimal_set_changes keys must be non-empty")
        return self


class RegimeShiftIdentifiabilityWitness(BaseModel):
    """Typed theorem/certificate witness for a Stage 16.1 identification slice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    theorem_slice: str = Field(min_length=1)
    model_class: str = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    min_environments_required: int = Field(ge=2)
    min_informative_environments_required: int = Field(default=1, ge=1)
    environment_diversity_requirements: tuple[str, ...] = ()
    informative_envs: tuple[str, ...] = ()
    redundant_envs: tuple[str, ...] = ()
    diversity_satisfied: bool = False
    identification_scope: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_witness(self) -> RegimeShiftIdentifiabilityWitness:
        ensure_unique_ids(
            self.assumptions, key_fn=lambda item: item, label="identifiability assumption"
        )
        ensure_unique_ids(
            self.environment_diversity_requirements,
            key_fn=lambda item: item,
            label="environment_diversity_requirement",
        )
        ensure_unique_ids(self.informative_envs, key_fn=lambda item: item, label="informative env")
        ensure_unique_ids(self.redundant_envs, key_fn=lambda item: item, label="redundant env")
        overlap = set(self.informative_envs) & set(self.redundant_envs)
        if overlap:
            raise ValueError(
                f"identifiability witness informative_envs and redundant_envs overlap {sorted(overlap)}"
            )
        return self


class RegimeShiftTargetResult(BaseModel):
    """ICP-style parent identification result for one target variable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str = Field(min_length=1)
    envs_used: tuple[str, ...]
    candidate_sets_tested: RegimeShiftCandidateSetPlan = Field(
        default_factory=RegimeShiftCandidateSetPlan
    )
    accepted_sets: tuple[RegimeShiftSetTestResult, ...] = ()
    rejected_sets: tuple[RegimeShiftSetTestResult, ...] = ()
    estimated_parents: tuple[str, ...] = ()
    stability_metrics: RegimeShiftStabilityMetrics = Field(
        default_factory=RegimeShiftStabilityMetrics
    )
    informativeness: RegimeShiftInformativeness = Field(default_factory=RegimeShiftInformativeness)
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_target_result(self) -> RegimeShiftTargetResult:
        if not self.envs_used:
            raise ValueError("envs_used must be non-empty")
        ensure_unique_ids(self.envs_used, key_fn=lambda item: item, label="envs_used")
        ensure_unique_ids(
            self.estimated_parents,
            key_fn=lambda item: item,
            label="estimated parent",
        )
        seen_sets: set[tuple[str, ...]] = set()
        for result in (*self.accepted_sets, *self.rejected_sets):
            key = tuple(result.S)
            if key in seen_sets:
                raise ValueError(f"duplicate candidate set result for {self.target}: {key}")
            seen_sets.add(key)
        return self


class RegimeShiftMECContractionEdgeUpdates(BaseModel):
    """Orientation deltas induced by regime-shift evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    forced_orientations: tuple[tuple[str, str], ...] = ()
    forbidden_orientations: tuple[tuple[str, str], ...] = ()
    newly_oriented_by_closure: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_edge_updates(self) -> RegimeShiftMECContractionEdgeUpdates:
        for field_name in ("forced_orientations", "forbidden_orientations"):
            edges = getattr(self, field_name)
            ensure_unique_ids(edges, key_fn=lambda item: item, label=field_name)
            for edge in edges:
                if len(edge) != 2 or not edge[0].strip() or not edge[1].strip():
                    raise ValueError(f"{field_name} entries must be non-empty pairs")
                if edge[0] == edge[1]:
                    raise ValueError(f"{field_name} entries cannot be self-loops")
        return self


class RegimeShiftMECContractionSummary(BaseModel):
    """Compact before/after MEC contraction accounting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edges_oriented_total: int = Field(default=0, ge=0)
    edges_ambiguous_remaining: int = Field(default=0, ge=0)


class RegimeShiftMECContraction(BaseModel):
    """Graph-level contraction summary caused by ICP-style orientations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_graph_ref: CausalGraphModelRef | None = None
    input_graph_type: str | None = Field(default=None, min_length=1)
    output_graph_ref: CausalGraphModelRef | None = None
    edge_updates: RegimeShiftMECContractionEdgeUpdates = Field(
        default_factory=RegimeShiftMECContractionEdgeUpdates
    )
    summary: RegimeShiftMECContractionSummary = Field(
        default_factory=RegimeShiftMECContractionSummary
    )


class RegimeShiftTrack7Revalidation(BaseModel):
    """Closed-loop Track 7 audit summary after Stage 16.3 graph assembly."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    performed: bool = False
    severity: Literal["info", "warning", "blocker"] | None = None
    violated_by_family: dict[str, int] = Field(default_factory=dict)
    blocker_families: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    exact_certificate_valid: bool = True

    @model_validator(mode="after")
    def validate_revalidation(self) -> RegimeShiftTrack7Revalidation:
        if self.performed and self.severity is None:
            raise ValueError("performed Track 7 revalidation requires severity")
        if not self.performed and self.severity is not None:
            raise ValueError("Track 7 revalidation severity requires performed=True")
        ensure_unique_ids(
            self.blocker_families,
            key_fn=lambda item: item,
            label="track7.revalidation.blocker_families",
        )
        for family, count in self.violated_by_family.items():
            if not family.strip():
                raise ValueError("track7 revalidation family names must be non-empty")
            if count < 0:
                raise ValueError("track7 revalidation family counts must be non-negative")
        if self.blocker_families and self.exact_certificate_valid:
            raise ValueError(
                "Track 7 revalidation with blocker_families must invalidate the exact certificate"
            )
        return self


class RegimeShiftTrack7InteractionStats(BaseModel):
    """Typed summary of how Track 7 algebraic blocks pruned the ICP search space."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_suppression_applied: bool = False
    block_lifting_applied: bool = False
    suppressed_candidates_by_target: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    mutually_exclusive_candidate_groups_by_target: dict[str, tuple[tuple[str, ...], ...]] = Field(
        default_factory=dict
    )
    hard_forbidden_edges: tuple[tuple[str, str], ...] = ()
    prior_blocker_families: tuple[str, ...] = ()
    revalidation_required: bool = True
    revalidation: RegimeShiftTrack7Revalidation = Field(
        default_factory=RegimeShiftTrack7Revalidation
    )
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_track7_stats(self) -> RegimeShiftTrack7InteractionStats:
        for target, suppressed in self.suppressed_candidates_by_target.items():
            if not target.strip():
                raise ValueError("suppressed_candidates_by_target keys must be non-empty")
            ensure_unique_ids(
                suppressed,
                key_fn=lambda item: item,
                label=f"suppressed_candidates_by_target.{target}",
            )
        for target, groups in self.mutually_exclusive_candidate_groups_by_target.items():
            if not target.strip():
                raise ValueError(
                    "mutually_exclusive_candidate_groups_by_target keys must be non-empty"
                )
            ensure_unique_ids(
                groups,
                key_fn=lambda item: item,
                label=f"mutually_exclusive_candidate_groups_by_target.{target}",
            )
            for group in groups:
                ensure_unique_ids(
                    group,
                    key_fn=lambda item: item,
                    label=f"mutually_exclusive_candidate_groups_by_target.{target}.group",
                )
                if len(group) < 2:
                    raise ValueError(
                        "mutually exclusive groups must contain at least two variables"
                    )
        ensure_unique_ids(
            self.hard_forbidden_edges,
            key_fn=lambda item: item,
            label="track7.hard_forbidden_edges",
        )
        for src, dst in self.hard_forbidden_edges:
            if not src.strip() or not dst.strip():
                raise ValueError("track7 hard_forbidden_edges must contain non-empty variables")
            if src == dst:
                raise ValueError("track7 hard_forbidden_edges cannot contain self-loops")
        ensure_unique_ids(
            self.prior_blocker_families,
            key_fn=lambda item: item,
            label="track7.prior_blocker_families",
        )
        if any(not family.strip() for family in self.prior_blocker_families):
            raise ValueError("track7 prior_blocker_families must be non-empty")
        return self


class RegimeShiftComputationalFeasibility(BaseModel):
    """Certificate describing whether the Stage 16.3 search remained tractable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("0.1", pattern=r"^\d+\.\d+$")
    mode: Literal["exact", "partial"] = "partial"
    n_variables: int = Field(ge=1)
    n_targets: int = Field(ge=1)
    n_environments: int = Field(ge=2)
    n_environment_pairs: int = Field(ge=1)
    conditioning_cap_q: int = Field(default=0, ge=0)
    local_separator_cap_eta: int | None = Field(default=None, ge=0)
    candidate_parent_sizes: dict[str, int] = Field(default_factory=dict)
    max_candidate_parents: int = Field(default=0, ge=0)
    expected_test_count: int = Field(default=0, ge=0)
    component_sizes: tuple[int, ...] = ()
    treewidth_upper_bounds: tuple[int, ...] = ()
    hard_required_edges: tuple[tuple[str, str], ...] = ()
    hard_forbidden_edges: tuple[tuple[str, str], ...] = ()
    exact_mode_possible: bool = False
    exact_mode_applied: bool = False
    fallback_reason: str | None = Field(default=None, min_length=1)
    estimated_runtime_seconds: float | None = Field(default=None, ge=0.0)
    estimated_memory_mb: float | None = Field(default=None, ge=0.0)
    selected_parent_sets: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    track7: RegimeShiftTrack7InteractionStats = Field(
        default_factory=RegimeShiftTrack7InteractionStats
    )

    @model_validator(mode="after")
    def validate_feasibility(self) -> RegimeShiftComputationalFeasibility:
        if self.treewidth_upper_bounds and (
            len(self.treewidth_upper_bounds) != len(self.component_sizes)
        ):
            raise ValueError("treewidth_upper_bounds must align with component_sizes when provided")
        for target, size in self.candidate_parent_sizes.items():
            if not target.strip():
                raise ValueError("candidate_parent_sizes keys must be non-empty")
            if size < 0:
                raise ValueError("candidate_parent_sizes values must be non-negative")
        if self.candidate_parent_sizes:
            observed_max = max(self.candidate_parent_sizes.values())
            if self.max_candidate_parents < observed_max:
                raise ValueError(
                    "max_candidate_parents must be at least the maximum candidate_parent_sizes value"
                )
        ensure_unique_ids(
            self.hard_required_edges,
            key_fn=lambda item: item,
            label="hard_required_edges",
        )
        ensure_unique_ids(
            self.hard_forbidden_edges,
            key_fn=lambda item: item,
            label="hard_forbidden_edges",
        )
        for label, edges in (
            ("hard_required_edges", self.hard_required_edges),
            ("hard_forbidden_edges", self.hard_forbidden_edges),
        ):
            for src, dst in edges:
                if not src.strip() or not dst.strip():
                    raise ValueError(f"{label} must contain non-empty variables")
                if src == dst:
                    raise ValueError(f"{label} cannot contain self-loops")
        for target, parents in self.selected_parent_sets.items():
            if not target.strip():
                raise ValueError("selected_parent_sets keys must be non-empty")
            ensure_unique_ids(
                parents,
                key_fn=lambda item: item,
                label=f"selected_parent_sets.{target}",
            )
        if self.mode == "exact" and not self.exact_mode_applied:
            raise ValueError("mode='exact' requires exact_mode_applied=True")
        if self.mode == "partial" and self.exact_mode_applied:
            raise ValueError("mode='partial' cannot set exact_mode_applied=True")
        if self.exact_mode_applied and not self.exact_mode_possible:
            raise ValueError("exact_mode_applied requires exact_mode_possible=True")
        if self.estimated_runtime_seconds is not None:
            ensure_finite_numeric(
                self.estimated_runtime_seconds,
                field_name="estimated_runtime_seconds",
            )
        if self.estimated_memory_mb is not None:
            ensure_finite_numeric(
                self.estimated_memory_mb,
                field_name="estimated_memory_mb",
            )
        return self


class ShiftTypeOverallLabel(str, Enum):
    """Overall conservative classification of an observed regime shift."""

    STRUCTURAL_ONLY_CONSISTENT = "structural_only_consistent"
    SELECTION_ONLY_CONSISTENT = "selection_only_consistent"
    MIXED_OR_LATENT_SUSPECTED = "mixed_or_latent_suspected"
    AMBIGUOUS = "ambiguous"
    UNINFORMATIVE_SHIFT = "uninformative_shift"


class ShiftTypeCertificationLevel(str, Enum):
    """How strong the diagnostic certification is."""

    CERTIFIED = "certified"
    PROVISIONAL = "provisional"
    SCREEN_ONLY = "screen_only"


class ShiftTypeContextExogeneity(str, Enum):
    """Status of the JCI-style context exogeneity assumption."""

    DECLARED = "declared"
    DESIGN_BASED = "design_based"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


class ShiftTypeObservedSelectionSufficiency(str, Enum):
    """Status of the observed balancing-set sufficiency assumption."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNTESTED = "untested"


class ShiftTypeOverlapStatus(str, Enum):
    """Overlap quality for the selection-only witness path."""

    OK = "ok"
    WEAK = "weak"
    FAILED = "failed"


class ShiftTypeWitnessStatus(str, Enum):
    """Outcome of a simple witness model check."""

    NOT_REJECTED = "not_rejected"
    REJECTED = "rejected"
    UNTESTABLE = "untestable"


class ShiftTypeAlphaSplit(BaseModel):
    """Type-I error budget allocation across diagnostic blocks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shift: float = Field(default=0.05 / 3.0, ge=0.0, le=1.0)
    selection: float = Field(default=0.05 / 3.0, ge=0.0, le=1.0)
    structural: float = Field(default=0.05 / 3.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_split(self) -> ShiftTypeAlphaSplit:
        ensure_finite_numeric(self.shift, field_name="shift")
        ensure_finite_numeric(self.selection, field_name="selection")
        ensure_finite_numeric(self.structural, field_name="structural")
        total = self.shift + self.selection + self.structural
        if total > 1.0 + 1e-9:
            raise ValueError("alpha split must sum to at most 1.0")
        return self


class ShiftTypeAssumptions(BaseModel):
    """Assumption status tracked by the shift-type diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context_exogeneity: ShiftTypeContextExogeneity = ShiftTypeContextExogeneity.UNVERIFIED
    observed_selection_sufficiency: ShiftTypeObservedSelectionSufficiency = (
        ShiftTypeObservedSelectionSufficiency.UNTESTED
    )
    overlap: ShiftTypeOverlapStatus = ShiftTypeOverlapStatus.OK


class ShiftTypeGlobalShiftTest(BaseModel):
    """Global multi-environment shift screen."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str = Field(default="aggregated_ks_proxy", min_length=1)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    effect_size: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_global_shift(self) -> ShiftTypeGlobalShiftTest:
        if self.p_value is not None:
            ensure_finite_numeric(self.p_value, field_name="p_value")
        if self.effect_size is not None:
            ensure_finite_numeric(self.effect_size, field_name="effect_size")
        return self


class ShiftTypeSelectionOnlyWitness(BaseModel):
    """Observed-balancing-set witness for selection-only shifts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ShiftTypeWitnessStatus = ShiftTypeWitnessStatus.UNTESTABLE
    balancing_set: tuple[str, ...] = ()
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    per_variable_p_values: dict[str, float] = Field(default_factory=dict)
    max_weight: float | None = Field(default=None, ge=0.0)
    ess_min: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_witness(self) -> ShiftTypeSelectionOnlyWitness:
        ensure_unique_ids(self.balancing_set, key_fn=lambda item: item, label="balancing set")
        if self.p_value is not None:
            ensure_finite_numeric(self.p_value, field_name="selection_only_witness.p_value")
        for variable, value in self.per_variable_p_values.items():
            if not variable.strip():
                raise ValueError(
                    "selection_only_witness per_variable_p_values keys must be non-empty"
                )
            ensure_finite_numeric(
                value,
                field_name=f"selection_only_witness.per_variable_p_values.{variable}",
            )
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"selection_only_witness.per_variable_p_values.{variable} must be in [0,1]"
                )
        if self.max_weight is not None:
            ensure_finite_numeric(self.max_weight, field_name="selection_only_witness.max_weight")
        if self.ess_min is not None:
            ensure_finite_numeric(self.ess_min, field_name="selection_only_witness.ess_min")
        return self


class ShiftTypeStructuralOnlyWitness(BaseModel):
    """Invariant-parent witness for structural-only shifts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ShiftTypeWitnessStatus = ShiftTypeWitnessStatus.UNTESTABLE
    targets_tested: tuple[str, ...] = ()
    accepted_parent_sets: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    per_target_p_values: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_witness(self) -> ShiftTypeStructuralOnlyWitness:
        ensure_unique_ids(self.targets_tested, key_fn=lambda item: item, label="targets_tested")
        for target, parents in self.accepted_parent_sets.items():
            if not target.strip():
                raise ValueError("accepted_parent_sets keys must be non-empty")
            ensure_unique_ids(
                parents,
                key_fn=lambda item: item,
                label=f"accepted_parent_sets.{target}",
            )
        if self.p_value is not None:
            ensure_finite_numeric(self.p_value, field_name="structural_only_witness.p_value")
        for target, value in self.per_target_p_values.items():
            if not target.strip():
                raise ValueError("per_target_p_values keys must be non-empty")
            ensure_finite_numeric(
                value,
                field_name=f"structural_only_witness.per_target_p_values.{target}",
            )
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"structural_only_witness.per_target_p_values.{target} must be in [0,1]"
                )
        return self


class ShiftTypeLatentMixedSeverity(BaseModel):
    """Heuristic severity scores for the mixed/latent branch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["heuristic_only"] = "heuristic_only"
    anchor_stability_gap: float | None = None
    icp_cd_gap: float | None = None

    @model_validator(mode="after")
    def validate_scores(self) -> ShiftTypeLatentMixedSeverity:
        if self.anchor_stability_gap is not None:
            ensure_finite_numeric(
                self.anchor_stability_gap,
                field_name="latent_mixed_severity.anchor_stability_gap",
            )
        if self.icp_cd_gap is not None:
            ensure_finite_numeric(
                self.icp_cd_gap,
                field_name="latent_mixed_severity.icp_cd_gap",
            )
        return self


class ShiftTypeWitnessBundle(BaseModel):
    """All witnesses recorded by the Stage 16.2 pre-screen."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    global_shift_test: ShiftTypeGlobalShiftTest = Field(default_factory=ShiftTypeGlobalShiftTest)
    selection_only_witness: ShiftTypeSelectionOnlyWitness = Field(
        default_factory=ShiftTypeSelectionOnlyWitness
    )
    structural_only_witness: ShiftTypeStructuralOnlyWitness = Field(
        default_factory=ShiftTypeStructuralOnlyWitness
    )
    latent_mixed_severity: ShiftTypeLatentMixedSeverity = Field(
        default_factory=ShiftTypeLatentMixedSeverity
    )


class ShiftTypePipelineAction(BaseModel):
    """Routing decision emitted by the Stage 16.2 pre-screen."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allow_icp_graph_contraction: bool = False
    allow_selection_transport_path: bool = False
    route_to_latent_aware_discovery: bool = False
    block_reason: str | None = Field(default=None, min_length=1)


class RegimeShiftTypeAssessment(BaseModel):
    """Certificate-carrying Stage 16.2 shift-type assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("0.1", pattern=r"^\d+\.\d+$")
    overall_label: ShiftTypeOverallLabel
    certification_level: ShiftTypeCertificationLevel = ShiftTypeCertificationLevel.SCREEN_ONLY
    alpha_total: float = Field(default=0.05, ge=0.0, le=1.0)
    alpha_split: ShiftTypeAlphaSplit = Field(default_factory=ShiftTypeAlphaSplit)
    assumptions: ShiftTypeAssumptions = Field(default_factory=ShiftTypeAssumptions)
    witnesses: ShiftTypeWitnessBundle = Field(default_factory=ShiftTypeWitnessBundle)
    pipeline_action: ShiftTypePipelineAction = Field(default_factory=ShiftTypePipelineAction)
    narrative_summary: str = ""

    @model_validator(mode="after")
    def validate_assessment(self) -> RegimeShiftTypeAssessment:
        ensure_finite_numeric(self.alpha_total, field_name="alpha_total")
        split_total = (
            self.alpha_split.shift + self.alpha_split.selection + self.alpha_split.structural
        )
        if split_total - self.alpha_total > 1e-9:
            raise ValueError("alpha_split must not exceed alpha_total")
        return self


class RegimeShiftIdentificationCertificate(BaseModel):
    """Audit certificate for ICP-based MEC contraction from regime shifts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["ir.regime_shift_identification_certificate"] = (
        "ir.regime_shift_identification_certificate"
    )
    produced_by: RegimeShiftProducedBy = Field(default_factory=RegimeShiftProducedBy)
    data_signature: RegimeShiftDataSignature
    environments: tuple[RegimeShiftEnvironmentRecord, ...]
    invariance_testing: RegimeShiftInvarianceTesting = Field(
        default_factory=RegimeShiftInvarianceTesting
    )
    targets: tuple[RegimeShiftTargetResult, ...]
    identifiability_witness: RegimeShiftIdentifiabilityWitness | None = None
    computational_feasibility: RegimeShiftComputationalFeasibility | None = None
    shift_type_assessment: RegimeShiftTypeAssessment | None = None
    mec_contraction: RegimeShiftMECContraction = Field(default_factory=RegimeShiftMECContraction)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_certificate(self) -> RegimeShiftIdentificationCertificate:
        if not self.environments:
            raise ValueError("environments must be non-empty")
        if not self.targets:
            raise ValueError("targets must be non-empty")
        ensure_unique_ids(
            self.environments,
            key_fn=lambda item: item.env_id,
            label="env_id",
        )
        ensure_unique_ids(self.targets, key_fn=lambda item: item.target, label="target")
        env_ids = {env.env_id for env in self.environments}
        variables = set(self.data_signature.variables)
        target_ids = {target.target for target in self.targets}
        if self.identifiability_witness is not None:
            unknown_informative_envs = set(self.identifiability_witness.informative_envs) - env_ids
            if unknown_informative_envs:
                raise ValueError(
                    "identifiability_witness.informative_envs references unknown envs "
                    f"{sorted(unknown_informative_envs)}"
                )
            unknown_redundant_envs = set(self.identifiability_witness.redundant_envs) - env_ids
            if unknown_redundant_envs:
                raise ValueError(
                    "identifiability_witness.redundant_envs references unknown envs "
                    f"{sorted(unknown_redundant_envs)}"
                )
        for target_result in self.targets:
            if target_result.target not in variables:
                raise ValueError(f"target {target_result.target} is not declared in variables")
            unknown_envs = set(target_result.envs_used) - env_ids
            if unknown_envs:
                raise ValueError(
                    f"target {target_result.target} references unknown envs {sorted(unknown_envs)}"
                )
            unknown_redundant = set(target_result.informativeness.redundant_envs) - env_ids
            if unknown_redundant:
                raise ValueError(
                    f"target {target_result.target} has unknown redundant_envs "
                    f"{sorted(unknown_redundant)}"
                )
            referenced_variables = set(target_result.estimated_parents)
            for result in (*target_result.accepted_sets, *target_result.rejected_sets):
                referenced_variables.update(result.S)
            unknown_variables = referenced_variables - variables
            if unknown_variables:
                raise ValueError(
                    f"target {target_result.target} references unknown variables "
                    f"{sorted(unknown_variables)}"
                )
        if self.shift_type_assessment is not None:
            selection_unknown = (
                set(self.shift_type_assessment.witnesses.selection_only_witness.balancing_set)
                - variables
            )
            if selection_unknown:
                raise ValueError(
                    "shift_type_assessment.selection_only_witness references unknown variables "
                    f"{sorted(selection_unknown)}"
                )
            per_variable_unknown = (
                set(
                    self.shift_type_assessment.witnesses.selection_only_witness.per_variable_p_values
                )
                - variables
            )
            if per_variable_unknown:
                raise ValueError(
                    "shift_type_assessment.selection_only_witness.per_variable_p_values "
                    f"references unknown variables {sorted(per_variable_unknown)}"
                )
            structural_targets = set(
                self.shift_type_assessment.witnesses.structural_only_witness.targets_tested
            )
            unknown_structural_targets = structural_targets - target_ids
            if unknown_structural_targets:
                raise ValueError(
                    "shift_type_assessment.structural_only_witness references unknown targets "
                    f"{sorted(unknown_structural_targets)}"
                )
            accepted_parent_sets = (
                self.shift_type_assessment.witnesses.structural_only_witness.accepted_parent_sets
            )
            unknown_parent_targets = set(accepted_parent_sets) - target_ids
            if unknown_parent_targets:
                raise ValueError(
                    "shift_type_assessment.structural_only_witness.accepted_parent_sets "
                    f"references unknown targets {sorted(unknown_parent_targets)}"
                )
            accepted_parent_variables = {
                variable for parents in accepted_parent_sets.values() for variable in parents
            }
            unknown_parent_variables = accepted_parent_variables - variables
            if unknown_parent_variables:
                raise ValueError(
                    "shift_type_assessment.structural_only_witness.accepted_parent_sets "
                    f"references unknown variables {sorted(unknown_parent_variables)}"
                )
            unknown_per_target = (
                set(
                    self.shift_type_assessment.witnesses.structural_only_witness.per_target_p_values
                )
                - target_ids
            )
            if unknown_per_target:
                raise ValueError(
                    "shift_type_assessment.structural_only_witness.per_target_p_values "
                    f"references unknown targets {sorted(unknown_per_target)}"
                )
        if self.computational_feasibility is not None:
            unknown_candidate_targets = (
                set(self.computational_feasibility.candidate_parent_sizes) - target_ids
            )
            if unknown_candidate_targets:
                raise ValueError(
                    "computational_feasibility.candidate_parent_sizes references unknown targets "
                    f"{sorted(unknown_candidate_targets)}"
                )
            unknown_selected_targets = (
                set(self.computational_feasibility.selected_parent_sets) - target_ids
            )
            if unknown_selected_targets:
                raise ValueError(
                    "computational_feasibility.selected_parent_sets references unknown targets "
                    f"{sorted(unknown_selected_targets)}"
                )
            selected_parent_variables = {
                variable
                for parents in self.computational_feasibility.selected_parent_sets.values()
                for variable in parents
            }
            unknown_selected_parent_variables = selected_parent_variables - variables
            if unknown_selected_parent_variables:
                raise ValueError(
                    "computational_feasibility.selected_parent_sets references unknown variables "
                    f"{sorted(unknown_selected_parent_variables)}"
                )
            for edge_group_name, edges in (
                ("hard_required_edges", self.computational_feasibility.hard_required_edges),
                ("hard_forbidden_edges", self.computational_feasibility.hard_forbidden_edges),
                (
                    "track7.hard_forbidden_edges",
                    self.computational_feasibility.track7.hard_forbidden_edges,
                ),
            ):
                edge_variables = {item for edge in edges for item in edge}
                unknown_edge_variables = edge_variables - variables
                if unknown_edge_variables:
                    raise ValueError(
                        f"computational_feasibility.{edge_group_name} references unknown variables "
                        f"{sorted(unknown_edge_variables)}"
                    )
            unknown_suppression_targets = (
                set(self.computational_feasibility.track7.suppressed_candidates_by_target)
                - target_ids
            )
            if unknown_suppression_targets:
                raise ValueError(
                    "computational_feasibility.track7.suppressed_candidates_by_target "
                    f"references unknown targets {sorted(unknown_suppression_targets)}"
                )
            suppressed_variables = {
                variable
                for values in self.computational_feasibility.track7.suppressed_candidates_by_target.values()
                for variable in values
            }
            unknown_suppressed_variables = suppressed_variables - variables
            if unknown_suppressed_variables:
                raise ValueError(
                    "computational_feasibility.track7.suppressed_candidates_by_target "
                    f"references unknown variables {sorted(unknown_suppressed_variables)}"
                )
            unknown_group_targets = (
                set(
                    self.computational_feasibility.track7.mutually_exclusive_candidate_groups_by_target
                )
                - target_ids
            )
            if unknown_group_targets:
                raise ValueError(
                    "computational_feasibility.track7.mutually_exclusive_candidate_groups_by_target "
                    f"references unknown targets {sorted(unknown_group_targets)}"
                )
            grouped_variables = {
                variable
                for groups in (
                    self.computational_feasibility.track7.mutually_exclusive_candidate_groups_by_target.values()
                )
                for group in groups
                for variable in group
            }
            unknown_grouped_variables = grouped_variables - variables
            if unknown_grouped_variables:
                raise ValueError(
                    "computational_feasibility.track7.mutually_exclusive_candidate_groups_by_target "
                    f"references unknown variables {sorted(unknown_grouped_variables)}"
                )
        return self


def persist_regime_shift_identification_certificate(
    store: ArtifactStore,
    certificate: RegimeShiftIdentificationCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.regime_shift_identification_certificate",
    schema_version: str = "1.0",
) -> RegimeShiftIdentificationCertificateRef:
    """Persist a regime-shift identification certificate as a typed IR artifact."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.regime_shift_identification_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return RegimeShiftIdentificationCertificateRef.model_validate(ref)


def load_regime_shift_identification_certificate(
    store: ArtifactStore,
    ref: RegimeShiftIdentificationCertificateRef,
) -> RegimeShiftIdentificationCertificate:
    """Load a persisted regime-shift identification certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return RegimeShiftIdentificationCertificate.model_validate(payload)


__all__ = [
    "EnvironmentShiftType",
    "EnvironmentSpec",
    "InvarianceMethod",
    "InvarianceResult",
    "InvarianceVerdict",
    "InvariantMechanismHypothesis",
    "MultiEnvironmentCausalContract",
    "RegimeShiftCandidateSetPlan",
    "RegimeShiftComputationalFeasibility",
    "RegimeShiftDataSignature",
    "RegimeShiftEnvironmentConstruction",
    "RegimeShiftEnvironmentRecord",
    "RegimeShiftIdentifiabilityWitness",
    "RegimeShiftIdentificationCertificate",
    "RegimeShiftInformativeness",
    "RegimeShiftInvarianceTesting",
    "RegimeShiftMECContraction",
    "RegimeShiftMECContractionEdgeUpdates",
    "RegimeShiftMECContractionSummary",
    "RegimeShiftProducedBy",
    "RegimeShiftSetTestResult",
    "RegimeShiftStabilityMetrics",
    "RegimeShiftSummary",
    "RegimeShiftTargetResult",
    "RegimeShiftTimeWindow",
    "RegimeShiftTrack7InteractionStats",
    "RegimeShiftTrack7Revalidation",
    "RegimeShiftTypeAssessment",
    "ShiftTypeAlphaSplit",
    "ShiftTypeAssumptions",
    "ShiftTypeCertificationLevel",
    "ShiftTypeContextExogeneity",
    "ShiftTypeGlobalShiftTest",
    "ShiftTypeLatentMixedSeverity",
    "ShiftTypeObservedSelectionSufficiency",
    "ShiftTypeOverallLabel",
    "ShiftTypeOverlapStatus",
    "ShiftTypePipelineAction",
    "ShiftTypeSelectionOnlyWitness",
    "ShiftTypeStructuralOnlyWitness",
    "ShiftTypeWitnessBundle",
    "ShiftTypeWitnessStatus",
    "load_regime_shift_identification_certificate",
    "persist_regime_shift_identification_certificate",
]
