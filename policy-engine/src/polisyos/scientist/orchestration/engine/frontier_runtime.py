"""Offline-gated frontier runtime registry for Scientist Phase 4 capabilities."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "FrontierCapability",
    "FrontierCapabilityStatus",
    "FrontierRuntimeConfig",
    "FrontierRuntimeReport",
    "build_frontier_runtime_report",
    "summarize_agent_promotion_frontier_status",
]


class FrontierCapabilityStatus(StrEnum):
    """Lifecycle status for a frontier capability."""

    DISABLED = "disabled"
    OFFLINE_GATED = "offline_gated"
    AVAILABLE_OFFLINE = "available_offline"
    EXPERIMENTAL_NOT_WIRED = "experimental_not_wired"


class FrontierCapability(BaseModel):
    """One frontier capability tracked behind a runtime gate."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    feature_flag: str = Field(min_length=1)
    module_path: str = Field(min_length=1)
    method_fqns: list[str] = Field(default_factory=list)
    enabled: bool = False
    status: FrontierCapabilityStatus = FrontierCapabilityStatus.DISABLED
    offline_validation_ref: str | None = None
    benchmark_pack_ref: str | None = None
    default_enable_requested: bool = False
    default_enable_eligible: bool = False
    rationale: str = Field(min_length=1)


class FrontierRuntimeConfig(BaseModel):
    """Feature flags and rollout evidence for Phase 4 frontier capabilities."""

    model_config = ConfigDict(extra="forbid")

    enable_proximal_causal: bool = False
    enable_bayesian_causal_discovery: bool = False
    enable_neural_dag_learners: bool = False
    enable_causal_representation_learning: bool = False
    enable_adversarial_scenario_discovery: bool = False
    enable_continuous_governance_loop: bool = False
    offline_validation_ref: str | None = None
    benchmark_pack_ref: str | None = None
    default_enable_requested: bool = False
    allow_baseline_replacement: bool = False
    require_benchmark_authority: bool = False
    benchmark_authority_default_enable_allowed: bool | None = None
    benchmark_authority_ref: str | None = None
    rationale: str = (
        "Phase 4 frontier capabilities stay feature-flagged until offline validation "
        "and benchmark packs prove they beat or safely complement the baseline path."
    )

    @property
    def requested_capabilities(self) -> list[str]:
        requested: list[str] = []
        for field_name, capability_id in (
            ("enable_proximal_causal", "proximal_causal"),
            ("enable_bayesian_causal_discovery", "bayesian_causal_discovery"),
            ("enable_neural_dag_learners", "neural_dag_learners"),
            ("enable_causal_representation_learning", "causal_representation_learning"),
            ("enable_adversarial_scenario_discovery", "adversarial_scenario_discovery"),
            ("enable_continuous_governance_loop", "continuous_governance_loop"),
        ):
            if bool(getattr(self, field_name)):
                requested.append(capability_id)
        return requested


class FrontierRuntimeReport(BaseModel):
    """Machine-readable readiness report for Phase 4 rollout decisions."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    requested_capabilities: list[str] = Field(default_factory=list)
    offline_validation_ref: str | None = None
    benchmark_pack_ref: str | None = None
    default_enable_eligible: bool = False
    default_enable_blockers: list[str] = Field(default_factory=list)
    capabilities: list[FrontierCapability] = Field(default_factory=list)
    claim_projection: dict[str, str] = Field(
        default_factory=lambda: {
            "status": "available",
            "owner": "polisyos.scientist.claims.projections.project_frontier_runtime_claims",
        }
    )
    rationale: str = Field(min_length=1)


def build_frontier_runtime_report(
    config: FrontierRuntimeConfig | None = None,
) -> FrontierRuntimeReport:
    """Build an auditable frontier rollout report from feature flags and evidence refs."""

    resolved = config or FrontierRuntimeConfig()
    requested = resolved.requested_capabilities
    blockers: list[str] = []
    if requested and resolved.offline_validation_ref is None:
        blockers.append("missing_offline_validation_ref")
    if requested and resolved.benchmark_pack_ref is None:
        blockers.append("missing_benchmark_pack_ref")
    if resolved.default_enable_requested and not resolved.allow_baseline_replacement:
        blockers.append("baseline_replacement_not_approved")
    if (
        requested
        and resolved.default_enable_requested
        and resolved.require_benchmark_authority
        and resolved.benchmark_authority_default_enable_allowed is not True
    ):
        blockers.append("benchmark_authority_not_allowed")

    capabilities = [
        _capability(
            capability_id="proximal_causal",
            family="causal",
            feature_flag="enable_proximal_causal",
            module_path="polisyos.foundry.methods.catalog.causal.frontier:ProximalBridgeEstimator",
            method_fqns=["causal.proximal.proximal_bridge@1.0.0"],
            enabled=resolved.enable_proximal_causal,
            wired=True,
            config=resolved,
            rationale=(
                "Existing proximal bridge estimator is available for offline-gated "
                "causal validation when negative-control assumptions are credible."
            ),
        ),
        _capability(
            capability_id="bayesian_causal_discovery",
            family="causal",
            feature_flag="enable_bayesian_causal_discovery",
            module_path="polisyos.scientist.methods.causal.validity",
            method_fqns=["causal.discovery.bayesian.placeholder@0.1.0"],
            enabled=resolved.enable_bayesian_causal_discovery,
            wired=False,
            config=resolved,
            rationale=(
                "Bayesian causal discovery remains blocked until a dedicated eval pack "
                "and calibrated posterior diagnostics are wired into the runtime."
            ),
        ),
        _capability(
            capability_id="neural_dag_learners",
            family="causal",
            feature_flag="enable_neural_dag_learners",
            module_path="polisyos.scientist.methods.causal.validity",
            method_fqns=[
                "causal.discovery.neural.deci@0.1.0",
                "causal.discovery.neural.avici@0.1.0",
            ],
            enabled=resolved.enable_neural_dag_learners,
            wired=False,
            config=resolved,
            rationale=(
                "Neural DAG learners stay experimental until hidden-benchmark results "
                "demonstrate structural recovery and governance-safe uncertainty reporting."
            ),
        ),
        _capability(
            capability_id="causal_representation_learning",
            family="causal",
            feature_flag="enable_causal_representation_learning",
            module_path="polisyos.scientist.methods.causal.validity",
            method_fqns=["causal.representation.learning.placeholder@0.1.0"],
            enabled=resolved.enable_causal_representation_learning,
            wired=False,
            config=resolved,
            rationale=(
                "Causal representation learning requires separate latent-factor benchmarks "
                "before it can influence the default Scientist path."
            ),
        ),
        _capability(
            capability_id="adversarial_scenario_discovery",
            family="search",
            feature_flag="enable_adversarial_scenario_discovery",
            module_path="polisyos.scientist.search.adversarial:PlatformMetaEvaluator",
            method_fqns=["scientist.search.adversarial.platform_meta_eval@1.0.0"],
            enabled=resolved.enable_adversarial_scenario_discovery,
            wired=True,
            config=resolved,
            rationale=(
                "Adversarial scenario discovery is available, but only as an offline-gated "
                "stress layer until challenge bundles prove it improves governance outcomes."
            ),
        ),
        _capability(
            capability_id="continuous_governance_loop",
            family="governance",
            feature_flag="enable_continuous_governance_loop",
            module_path="polisyos.scientist.validation.decision_validity:DecisionValidityService",
            method_fqns=["scientist.governance.continuous_loop.placeholder@0.1.0"],
            enabled=resolved.enable_continuous_governance_loop,
            wired=True,
            config=resolved,
            rationale=(
                "Continuous governance monitoring exists, but retraining/reissue hooks "
                "remain offline-gated until benchmark packs validate drift, fairness, and calibration policies."
            ),
        ),
    ]

    default_enable_eligible = bool(
        requested
        and not blockers
        and all(cap.default_enable_eligible for cap in capabilities if cap.enabled)
        and (
            not resolved.require_benchmark_authority
            or resolved.benchmark_authority_default_enable_allowed is True
        )
    )
    return FrontierRuntimeReport(
        requested_capabilities=requested,
        offline_validation_ref=resolved.offline_validation_ref,
        benchmark_pack_ref=resolved.benchmark_pack_ref,
        default_enable_eligible=default_enable_eligible,
        default_enable_blockers=blockers,
        capabilities=capabilities,
        rationale=resolved.rationale,
    )


def summarize_agent_promotion_frontier_status(report: Any) -> FrontierCapabilityStatus:
    """Summarize a Phase 1.4 agent promotion report in frontier-runtime vocabulary."""

    if bool(getattr(report, "default_enable_eligible", False)):
        return FrontierCapabilityStatus.AVAILABLE_OFFLINE
    statuses: list[FrontierCapabilityStatus] = []
    for item in getattr(report, "capabilities", []):
        raw_status = getattr(item, "status", None)
        try:
            statuses.append(FrontierCapabilityStatus(str(raw_status)))
        except ValueError:
            return FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED
    if not statuses:
        return FrontierCapabilityStatus.DISABLED
    if any(status == FrontierCapabilityStatus.OFFLINE_GATED for status in statuses):
        return FrontierCapabilityStatus.OFFLINE_GATED
    if any(status == FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED for status in statuses):
        return FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED
    if all(status == FrontierCapabilityStatus.DISABLED for status in statuses):
        return FrontierCapabilityStatus.DISABLED
    return FrontierCapabilityStatus.AVAILABLE_OFFLINE


def _capability(
    *,
    capability_id: str,
    family: str,
    feature_flag: str,
    module_path: str,
    method_fqns: list[str],
    enabled: bool,
    wired: bool,
    config: FrontierRuntimeConfig,
    rationale: str,
) -> FrontierCapability:
    if not enabled:
        status = FrontierCapabilityStatus.DISABLED
    elif not wired:
        status = FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED
    elif config.offline_validation_ref is None or config.benchmark_pack_ref is None:
        status = FrontierCapabilityStatus.OFFLINE_GATED
    else:
        status = FrontierCapabilityStatus.AVAILABLE_OFFLINE

    default_enable_eligible = bool(
        enabled
        and wired
        and config.offline_validation_ref
        and config.benchmark_pack_ref
        and config.allow_baseline_replacement
    )
    return FrontierCapability(
        capability_id=capability_id,
        family=family,
        feature_flag=feature_flag,
        module_path=module_path,
        method_fqns=method_fqns,
        enabled=enabled,
        status=status,
        offline_validation_ref=config.offline_validation_ref,
        benchmark_pack_ref=config.benchmark_pack_ref,
        default_enable_requested=config.default_enable_requested,
        default_enable_eligible=bool(
            default_enable_eligible
            and (
                not config.require_benchmark_authority
                or config.benchmark_authority_default_enable_allowed is True
            )
        ),
        rationale=rationale,
    )
