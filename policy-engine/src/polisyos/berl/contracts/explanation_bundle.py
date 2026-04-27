"""Versioned, auditable BERL ExplanationBundle contract."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

JsonObject = dict[str, object]
EXPLANATION_BUNDLE_SCHEMA_VERSION = "1.0.0"


class StrictModel(BaseModel):
    """Base model that keeps BERL bundles closed to undeclared fields."""

    model_config = ConfigDict(extra="forbid")


class ModelContext(StrictModel):
    """Model identity and provenance for one explanation claim."""

    model_id: str = Field(min_length=1)
    model_hash: str = Field(min_length=1)
    model_class: str = Field(min_length=1)
    training_data_hash: str | None = None
    calibration_ref: str | None = None


class PredictionContext(StrictModel):
    """Prediction being explained."""

    prediction_id: str = Field(min_length=1)
    row_id: str = Field(min_length=1)
    output_name: str = Field(min_length=1)
    output_scale: str = Field(min_length=1)
    raw_score: float
    display_score: float | None = None
    decision_threshold: float | None = None


class FeatureContext(StrictModel):
    """Feature value, schema, constraint, and missingness references."""

    feature_values_ref: str = Field(min_length=1)
    feature_schema_version: str = Field(min_length=1)
    constraints_ref: str | None = None
    missingness_policy: str = Field(default="model_native", min_length=1)


class PerturbationDistribution(StrictModel):
    """Declared local perturbation distribution."""

    name: str = Field(min_length=1)
    radius: float | None = Field(default=None, ge=0.0)
    categorical_policy: str | None = None
    continuous_policy: str | None = None
    support_constraints: str | None = None


class FeatureDependencePolicy(StrictModel):
    """Declared semantics for dependent and correlated features."""

    primary: str = Field(min_length=1)
    alternatives_tested: list[str] = Field(default_factory=list)
    causal_claim_made: bool = False


class BackgroundData(StrictModel):
    """Background data reference used by removal or perturbation explainers."""

    dataset_ref: str | None = None
    n: int | None = Field(default=None, ge=0)
    sampling_policy: str | None = None


class ExplanationAssumptions(StrictModel):
    """Assumption set that scopes every explanation claim in the bundle."""

    explanation_question: str = Field(default="local_prediction_drivers", min_length=1)
    perturbation_distribution: PerturbationDistribution
    feature_dependence_policy: FeatureDependencePolicy
    background_data: BackgroundData | None = None


class RedundancyEvidenceModel(StrictModel):
    """Evidence behind one redundancy cluster."""

    max_abs_corr: float | None = Field(default=None, ge=0.0, le=1.0)
    max_predictability_r2: float | None = Field(default=None, ge=0.0, le=1.0)
    domain_rule: str | None = None


class RedundancyClusterModel(StrictModel):
    """Redundancy cluster serialized inside an ExplanationBundle."""

    cluster_id: str = Field(min_length=1)
    features: list[str] = Field(min_length=2)
    evidence: RedundancyEvidenceModel = Field(default_factory=RedundancyEvidenceModel)
    reporting_policy: str = Field(default="group_first", min_length=1)


class RedundancyContext(StrictModel):
    """Redundancy clusters used by UI and validation gates."""

    clusters: list[RedundancyClusterModel] = Field(default_factory=list)


class FeatureAttribution(StrictModel):
    """One feature attribution and optional estimator uncertainty."""

    feature: str = Field(min_length=1)
    value: float
    standard_error: float | None = Field(default=None, ge=0.0)
    confidence_interval: tuple[float, float] | None = None


class GroupAttribution(StrictModel):
    """One redundancy-cluster attribution and optional interval."""

    cluster_id: str = Field(min_length=1)
    value: float
    confidence_interval: tuple[float, float] | None = None


class InfidelityReport(StrictModel):
    """Held-out local reconstruction infidelity claim."""

    loss: str = Field(default="squared_reconstruction_error", min_length=1)
    point_estimate: float = Field(ge=0.0)
    upper_bound: float = Field(ge=0.0)
    confidence: float = Field(gt=0.0, lt=1.0)
    n_eval_perturbations: int = Field(gt=0)
    residual_cap: float = Field(gt=0.0)
    bound_type: str = Field(min_length=1)
    evaluation_split: str = Field(default="heldout", min_length=1)


class StabilityReport(StrictModel):
    """Stability diagnostics for stochastic explainers."""

    bootstrap_runs: int | None = Field(default=None, ge=0)
    seed_policy: str | None = None
    max_rank_shift_top5: int | None = Field(default=None, ge=0)


class MethodExplanation(StrictModel):
    """One method-specific explanation inside the bundle."""

    method_id: str = Field(min_length=1)
    library: str | None = None
    library_version: str | None = None
    scope: Literal["local", "global", "local_bin", "diagnostic"] = "local"
    params: JsonObject = Field(default_factory=dict)
    assumptions: JsonObject = Field(default_factory=dict)
    attributions: list[FeatureAttribution] = Field(default_factory=list)
    group_attributions: list[GroupAttribution] = Field(default_factory=list)
    infidelity: InfidelityReport | None = None
    stability: StabilityReport | None = None


class DisagreementReport(StrictModel):
    """Cross-method disagreement summary."""

    methods_compared: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, gt=0)
    top_k_jaccard_median: float | None = Field(default=None, ge=0.0, le=1.0)
    kendall_tau_median: float | None = Field(default=None, ge=-1.0, le=1.0)
    magnitude_l1_median: float | None = Field(default=None, ge=0.0)
    sign_conflict_features: list[str] = Field(default_factory=list)
    redundancy_adjusted_conflicts: list[str] = Field(default_factory=list)
    uncertainty_summary: str | None = None
    flags: list[str] = Field(default_factory=list)


class SupportCheck(StrictModel):
    """Support and constraint checks for held-out perturbations."""

    ood_rate_eval_perturbations: float = Field(default=0.0, ge=0.0, le=1.0)
    constraint_violation_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class ValidityReport(StrictModel):
    """Use restrictions and support diagnostics."""

    support_check: SupportCheck = Field(default_factory=SupportCheck)
    use_restrictions: list[str] = Field(default_factory=list)


class AuditReport(StrictModel):
    """Reproducibility metadata and artifact references."""

    code_version: str = Field(min_length=1)
    random_seeds: list[int] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class ExplanationBundle(StrictModel):
    """Audited explanation artifact that prevents assumption-free bar charts."""

    schema_version: str = Field(
        default=EXPLANATION_BUNDLE_SCHEMA_VERSION,
        pattern=r"^\d+\.\d+\.\d+$",
    )
    bundle_id: str = Field(min_length=1)
    created_at: AwareDatetime
    faithfulness_claim: Literal["bounded", "unbounded"] = "bounded"
    display_policy: Literal["analyst_display", "limited", "diagnostic_only"] = "limited"
    analyst_warning: str | None = None
    model: ModelContext
    prediction: PredictionContext
    feature_context: FeatureContext
    assumptions: ExplanationAssumptions
    redundancy: RedundancyContext = Field(default_factory=RedundancyContext)
    methods: list[MethodExplanation] = Field(default_factory=list)
    disagreement: DisagreementReport | None = None
    validity: ValidityReport = Field(default_factory=ValidityReport)
    audit: AuditReport


def bundle_json_schema() -> dict[str, object]:
    """Return the JSON schema for the current ExplanationBundle contract."""

    return cast("dict[str, object]", ExplanationBundle.model_json_schema())
