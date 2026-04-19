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
    def validate_environment(self) -> "EnvironmentSpec":
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
    def validate_hypothesis(self) -> "InvariantMechanismHypothesis":
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
    def validate_contract(self) -> "MultiEnvironmentCausalContract":
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
    def validate_result(self) -> "InvarianceResult":
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
    def validate_signature(self) -> "RegimeShiftDataSignature":
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
    def validate_shift_summary(self) -> "RegimeShiftSummary":
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
    def validate_testing(self) -> "RegimeShiftInvarianceTesting":
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
    def validate_set_result(self) -> "RegimeShiftSetTestResult":
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
    def validate_metrics(self) -> "RegimeShiftStabilityMetrics":
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

    @model_validator(mode="after")
    def validate_informativeness(self) -> "RegimeShiftInformativeness":
        ensure_unique_ids(self.redundant_envs, key_fn=lambda item: item, label="redundant env")
        if any(not env_id.strip() for env_id in self.leave_one_out_parent_changes):
            raise ValueError("leave_one_out_parent_changes keys must be non-empty")
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
    informativeness: RegimeShiftInformativeness = Field(
        default_factory=RegimeShiftInformativeness
    )
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_target_result(self) -> "RegimeShiftTargetResult":
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
    def validate_edge_updates(self) -> "RegimeShiftMECContractionEdgeUpdates":
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
    mec_contraction: RegimeShiftMECContraction = Field(
        default_factory=RegimeShiftMECContraction
    )
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_certificate(self) -> "RegimeShiftIdentificationCertificate":
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
        for target_result in self.targets:
            if target_result.target not in variables:
                raise ValueError(f"target {target_result.target} is not declared in variables")
            unknown_envs = set(target_result.envs_used) - env_ids
            if unknown_envs:
                raise ValueError(
                    f"target {target_result.target} references unknown envs "
                    f"{sorted(unknown_envs)}"
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
    "RegimeShiftDataSignature",
    "RegimeShiftEnvironmentConstruction",
    "RegimeShiftEnvironmentRecord",
    "RegimeShiftIdentificationCertificate",
    "RegimeShiftInformativeness",
    "RegimeShiftInvarianceTesting",
    "RegimeShiftMECContraction",
    "RegimeShiftMECContractionEdgeUpdates",
    "RegimeShiftMECContractionSummary",
    "RegimeShiftProducedBy",
    "RegimeShiftSetTestResult",
    "RegimeShiftSummary",
    "RegimeShiftStabilityMetrics",
    "RegimeShiftTargetResult",
    "RegimeShiftTimeWindow",
    "load_regime_shift_identification_certificate",
    "persist_regime_shift_identification_certificate",
]
