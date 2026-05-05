"""Unified promotion report for Scientist agent and tool runtime capabilities."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.agent.runtime_capabilities import (
    AgentCapabilityFamily,
    AgentCapabilityId,
    list_agent_capabilities,
)
from polisyos.scientist.agent.supervisor_eval import (
    SupervisorEvalMetrics,
    SupervisorPromotionEvaluation,
    evaluate_supervisor_promotion,
)
from polisyos.scientist.agent.tool_contracts import (
    ToolContractSummary,
    tool_contract_default_blockers,
)
from polisyos.scientist.engine.frontier_runtime import FrontierCapabilityStatus

if TYPE_CHECKING:
    from polisyos.scientist.agent.eval_harness import AgentPolicyComparisonReport
    from polisyos.scientist.agent.reasoning import ReasoningPolicyGate
    from polisyos.scientist.evals.authority import BenchmarkAuthorityVerdict
    from polisyos.scientist.search.strategies.advanced_policy import AdvancedSearchPolicyReport

__all__ = [
    "AgentCapabilityPromotionReport",
    "AgentCapabilityStatusRecord",
    "AgentPromotionCoverageDomain",
    "AgentPromotionCoverageRecord",
    "build_agent_capability_promotion_report",
    "project_agent_promotion_to_frontier_statuses",
]


class AgentPromotionCoverageDomain(StrEnum):
    """Cross-cutting domains covered by the unified agent promotion report."""

    TOOL_LOOP = "tool_loop"
    SUPERVISOR = "supervisor"
    SEARCH = "search"
    REFLEXION = "reflexion"
    CONTEXT_MEMORY = "context_memory"
    PROVIDER_BEHAVIOR = "provider_behavior"


class AgentCapabilityStatusRecord(BaseModel):
    """Promotion status for one agentic capability family."""

    model_config = ConfigDict(extra="forbid")

    capability_id: AgentCapabilityId
    display_name: str = Field(min_length=1)
    family: str = Field(min_length=1)
    status: FrontierCapabilityStatus
    default_rule: str = Field(min_length=1)
    default_enable_requested: bool = False
    default_enable_eligible: bool = False
    blockers: list[str] = Field(default_factory=list)
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    source_reports: list[str] = Field(default_factory=list)


class AgentPromotionCoverageRecord(BaseModel):
    """Cross-cutting promotion coverage beyond a single capability id."""

    model_config = ConfigDict(extra="forbid")

    domain: AgentPromotionCoverageDomain
    status: FrontierCapabilityStatus
    blockers: list[str] = Field(default_factory=list)
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    source_reports: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class AgentCapabilityPromotionReport(BaseModel):
    """One promotion surface for agentic Scientist capabilities."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    coverage_domains: list[AgentPromotionCoverageDomain] = Field(
        default_factory=lambda: list(AgentPromotionCoverageDomain)
    )
    coverage: list[AgentPromotionCoverageRecord] = Field(default_factory=list)
    capabilities: list[AgentCapabilityStatusRecord]
    offline_validation_ref: ArtifactRef | None = None
    benchmark_pack_ref: ArtifactRef | None = None
    default_enable_requested: bool = False
    default_enable_capability_ids: list[AgentCapabilityId] = Field(default_factory=list)
    default_enable_eligible: bool = False
    blockers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _capability_ids_are_complete(self) -> AgentCapabilityPromotionReport:
        expected = {item.value for item in AgentCapabilityId}
        observed = [item.capability_id.value for item in self.capabilities]
        duplicate_ids = sorted({item for item in observed if observed.count(item) > 1})
        missing = sorted(expected.difference(observed))
        extra = sorted(set(observed).difference(expected))
        if duplicate_ids or missing or extra:
            details = []
            if duplicate_ids:
                details.append(f"duplicate={duplicate_ids}")
            if missing:
                details.append(f"missing={missing}")
            if extra:
                details.append(f"extra={extra}")
            raise ValueError("agent capability promotion report mismatch: " + "; ".join(details))
        expected_domains = {item.value for item in AgentPromotionCoverageDomain}
        observed_domains = [item.domain.value for item in self.coverage]
        duplicate_domains = sorted(
            {item for item in observed_domains if observed_domains.count(item) > 1}
        )
        missing_domains = sorted(expected_domains.difference(observed_domains))
        extra_domains = sorted(set(observed_domains).difference(expected_domains))
        if duplicate_domains or missing_domains or extra_domains:
            details = []
            if duplicate_domains:
                details.append(f"duplicate_domains={duplicate_domains}")
            if missing_domains:
                details.append(f"missing_domains={missing_domains}")
            if extra_domains:
                details.append(f"extra_domains={extra_domains}")
            raise ValueError("agent promotion coverage mismatch: " + "; ".join(details))
        return self


def build_agent_capability_promotion_report(
    *,
    run_id: str | None = None,
    offline_validation_ref: ArtifactRef | None = None,
    benchmark_pack_ref: ArtifactRef | None = None,
    default_enable_requested: bool = False,
    default_enable_capability_ids: list[AgentCapabilityId | str] | None = None,
    tool_contract_summary: ToolContractSummary | None = None,
    supervisor_eval: SupervisorEvalMetrics | SupervisorPromotionEvaluation | None = None,
    agent_policy_report: AgentPolicyComparisonReport | None = None,
    advanced_search_report: AdvancedSearchPolicyReport | None = None,
    reasoning_gate: ReasoningPolicyGate | None = None,
    deep_research_eval_ref: ArtifactRef | None = None,
    citation_faithfulness_eval_ref: ArtifactRef | None = None,
    fanout_budget_eval_ref: ArtifactRef | None = None,
    fanout_consistency_eval_ref: ArtifactRef | None = None,
    context_memory_eval_ref: ArtifactRef | None = None,
    provider_behavior_eval_ref: ArtifactRef | None = None,
    benchmark_authority_verdict: BenchmarkAuthorityVerdict | None = None,
    require_benchmark_authority: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AgentCapabilityPromotionReport:
    """Build the Phase 1.4 unified promotion report.

    Existing reports are read as evidence inputs. The emitted report itself uses
    `ArtifactRef` objects for promotion evidence so free-form strings cannot
    silently unlock default enablement.
    """

    target_capability_ids = _resolve_default_enable_targets(
        default_enable_requested=default_enable_requested,
        capability_ids=default_enable_capability_ids,
    )
    global_blockers = _global_default_blockers(
        default_enable_requested=default_enable_requested,
        offline_validation_ref=offline_validation_ref,
        benchmark_pack_ref=benchmark_pack_ref,
        target_capability_ids=target_capability_ids,
        benchmark_authority_verdict=benchmark_authority_verdict,
        require_benchmark_authority=require_benchmark_authority,
    )
    supervisor_evaluation = _resolve_supervisor_evaluation(supervisor_eval)
    capabilities = [
        _status_record(
            family,
            default_enable_requested=family.capability_id in target_capability_ids,
            global_blockers=global_blockers,
            offline_validation_ref=offline_validation_ref,
            benchmark_pack_ref=benchmark_pack_ref,
            tool_contract_summary=tool_contract_summary,
            supervisor_evaluation=supervisor_evaluation,
            agent_policy_report=agent_policy_report,
            advanced_search_report=advanced_search_report,
            reasoning_gate=reasoning_gate,
            deep_research_eval_ref=deep_research_eval_ref,
            citation_faithfulness_eval_ref=citation_faithfulness_eval_ref,
            fanout_budget_eval_ref=fanout_budget_eval_ref,
            fanout_consistency_eval_ref=fanout_consistency_eval_ref,
        )
        for family in list_agent_capabilities()
    ]
    coverage = _build_coverage_records(
        offline_validation_ref=offline_validation_ref,
        benchmark_pack_ref=benchmark_pack_ref,
        tool_contract_summary=tool_contract_summary,
        supervisor_evaluation=supervisor_evaluation,
        agent_policy_report=agent_policy_report,
        advanced_search_report=advanced_search_report,
        deep_research_eval_ref=deep_research_eval_ref,
        citation_faithfulness_eval_ref=citation_faithfulness_eval_ref,
        context_memory_eval_ref=context_memory_eval_ref,
        provider_behavior_eval_ref=provider_behavior_eval_ref,
    )
    report_blockers = sorted(
        set(global_blockers).union(
            blocker
            for capability in capabilities
            for blocker in capability.blockers
            if capability.capability_id in target_capability_ids or blocker.startswith("invalid_")
        )
    )
    default_enable_eligible = bool(
        default_enable_requested
        and not report_blockers
        and target_capability_ids
        and all(
            item.default_enable_eligible
            for item in capabilities
            if item.capability_id in target_capability_ids
        )
    )
    return AgentCapabilityPromotionReport(
        run_id=run_id,
        coverage=coverage,
        capabilities=capabilities,
        offline_validation_ref=offline_validation_ref,
        benchmark_pack_ref=benchmark_pack_ref,
        default_enable_requested=default_enable_requested,
        default_enable_capability_ids=sorted(
            target_capability_ids,
            key=lambda item: item.value,
        ),
        default_enable_eligible=default_enable_eligible,
        blockers=report_blockers,
        metadata=_promotion_metadata(
            metadata or {},
            benchmark_authority_verdict=benchmark_authority_verdict,
        ),
    )


def project_agent_promotion_to_frontier_statuses(
    report: AgentCapabilityPromotionReport,
) -> dict[str, FrontierCapabilityStatus]:
    """Project agent capability statuses into the shared frontier vocabulary."""

    return {
        record.capability_id.value: record.status
        for record in sorted(report.capabilities, key=lambda item: item.capability_id.value)
    }


def _global_default_blockers(
    *,
    default_enable_requested: bool,
    offline_validation_ref: ArtifactRef | None,
    benchmark_pack_ref: ArtifactRef | None,
    target_capability_ids: set[AgentCapabilityId],
    benchmark_authority_verdict: BenchmarkAuthorityVerdict | None,
    require_benchmark_authority: bool,
) -> list[str]:
    if not default_enable_requested:
        return []
    blockers: list[str] = []
    if not target_capability_ids:
        blockers.append("missing_default_enable_capability_ids")
    if offline_validation_ref is None:
        blockers.append("missing_offline_validation_ref")
    if benchmark_pack_ref is None:
        blockers.append("missing_benchmark_pack_ref")
    blockers.extend(
        _benchmark_authority_blockers(
            benchmark_authority_verdict,
            require_benchmark_authority=require_benchmark_authority,
        )
    )
    return blockers


def _benchmark_authority_blockers(
    verdict: BenchmarkAuthorityVerdict | None,
    *,
    require_benchmark_authority: bool,
) -> list[str]:
    if verdict is None:
        return ["missing_benchmark_authority_verdict"] if require_benchmark_authority else []
    if verdict.default_enable_allowed:
        return []
    blockers = ["benchmark_authority_not_allowed"]
    blockers.extend(f"benchmark_authority_missing:{item}" for item in verdict.missing)
    blockers.extend(f"benchmark_authority_stale:{item}" for item in verdict.stale)
    return sorted(set(blockers))


def _promotion_metadata(
    metadata: dict[str, Any],
    *,
    benchmark_authority_verdict: BenchmarkAuthorityVerdict | None,
) -> dict[str, Any]:
    if benchmark_authority_verdict is None:
        return dict(metadata)
    return {
        **metadata,
        "benchmark_authority": {
            "default_enable_allowed": benchmark_authority_verdict.default_enable_allowed,
            "missing": list(benchmark_authority_verdict.missing),
            "stale": list(benchmark_authority_verdict.stale),
            "leakage_warnings": list(benchmark_authority_verdict.leakage_warnings),
            "family": benchmark_authority_verdict.request.family,
            "claim_mode": benchmark_authority_verdict.request.claim_mode,
        },
    }


def _resolve_default_enable_targets(
    *,
    default_enable_requested: bool,
    capability_ids: list[AgentCapabilityId | str] | None,
) -> set[AgentCapabilityId]:
    if not default_enable_requested:
        return set()
    return {AgentCapabilityId(item) for item in capability_ids or []}


def _resolve_supervisor_evaluation(
    supervisor_eval: SupervisorEvalMetrics | SupervisorPromotionEvaluation | None,
) -> SupervisorPromotionEvaluation | None:
    if supervisor_eval is None:
        return None
    if isinstance(supervisor_eval, SupervisorPromotionEvaluation):
        return supervisor_eval
    return evaluate_supervisor_promotion(supervisor_eval)


def _status_record(
    family: AgentCapabilityFamily,
    *,
    default_enable_requested: bool,
    global_blockers: list[str],
    offline_validation_ref: ArtifactRef | None,
    benchmark_pack_ref: ArtifactRef | None,
    tool_contract_summary: ToolContractSummary | None,
    supervisor_evaluation: SupervisorPromotionEvaluation | None,
    agent_policy_report: AgentPolicyComparisonReport | None,
    advanced_search_report: AdvancedSearchPolicyReport | None,
    reasoning_gate: ReasoningPolicyGate | None,
    deep_research_eval_ref: ArtifactRef | None,
    citation_faithfulness_eval_ref: ArtifactRef | None,
    fanout_budget_eval_ref: ArtifactRef | None,
    fanout_consistency_eval_ref: ArtifactRef | None,
) -> AgentCapabilityStatusRecord:
    if family.capability_id == AgentCapabilityId.TOOL_LOOP:
        blockers, evidence_refs, metrics, source_reports = _tool_loop_evidence(
            tool_contract_summary
        )
    elif family.capability_id == AgentCapabilityId.SUPERVISOR_WORKER:
        blockers, evidence_refs, metrics, source_reports = _supervisor_evidence(
            supervisor_evaluation
        )
    elif family.capability_id == AgentCapabilityId.DEEP_RESEARCH_SUBGRAPH:
        blockers, evidence_refs, metrics, source_reports = _deep_research_evidence(
            deep_research_eval_ref=deep_research_eval_ref,
            citation_faithfulness_eval_ref=citation_faithfulness_eval_ref,
        )
    elif family.capability_id in {AgentCapabilityId.TREE_OF_THOUGHT, AgentCapabilityId.LATS_MCTS}:
        mode = family.capability_id.value
        blockers, evidence_refs, metrics, source_reports = _reasoning_evidence(
            mode=mode,
            reasoning_gate=reasoning_gate,
            agent_policy_report=agent_policy_report,
        )
    elif family.capability_id in {AgentCapabilityId.LEARNED_ROUTING, AgentCapabilityId.LEARNED_VOI}:
        blockers, evidence_refs, metrics, source_reports = _learned_search_evidence(
            capability_id=family.capability_id,
            advanced_search_report=advanced_search_report,
        )
    elif family.capability_id == AgentCapabilityId.SAME_MODEL_FANOUT:
        blockers, evidence_refs, metrics, source_reports = _fanout_evidence(
            agent_policy_report=agent_policy_report,
            fanout_budget_eval_ref=fanout_budget_eval_ref,
            fanout_consistency_eval_ref=fanout_consistency_eval_ref,
        )
    else:  # pragma: no cover - registry completeness keeps this unreachable.
        blockers, evidence_refs, metrics, source_reports = (["unknown_capability"], [], {}, [])

    status = _frontier_status(
        family=family,
        blockers=blockers,
        evidence_refs=evidence_refs,
        offline_validation_ref=offline_validation_ref,
        benchmark_pack_ref=benchmark_pack_ref,
    )
    default_enable_eligible = bool(
        default_enable_requested
        and not global_blockers
        and not blockers
        and offline_validation_ref is not None
        and benchmark_pack_ref is not None
        and status == FrontierCapabilityStatus.AVAILABLE_OFFLINE
    )
    return AgentCapabilityStatusRecord(
        capability_id=family.capability_id,
        display_name=family.display_name,
        family=family.family,
        status=status,
        default_rule=family.default_rule,
        default_enable_requested=default_enable_requested,
        default_enable_eligible=default_enable_eligible,
        blockers=sorted(set(blockers)),
        evidence_refs=evidence_refs,
        metrics=metrics,
        source_reports=source_reports,
    )


def _build_coverage_records(
    *,
    offline_validation_ref: ArtifactRef | None,
    benchmark_pack_ref: ArtifactRef | None,
    tool_contract_summary: ToolContractSummary | None,
    supervisor_evaluation: SupervisorPromotionEvaluation | None,
    agent_policy_report: AgentPolicyComparisonReport | None,
    advanced_search_report: AdvancedSearchPolicyReport | None,
    deep_research_eval_ref: ArtifactRef | None,
    citation_faithfulness_eval_ref: ArtifactRef | None,
    context_memory_eval_ref: ArtifactRef | None,
    provider_behavior_eval_ref: ArtifactRef | None,
) -> list[AgentPromotionCoverageRecord]:
    tool_blockers, tool_refs, tool_metrics, tool_sources = _tool_loop_evidence(
        tool_contract_summary
    )
    supervisor_blockers, supervisor_refs, supervisor_metrics, supervisor_sources = (
        _supervisor_evidence(supervisor_evaluation)
    )
    search_blockers, search_refs, search_metrics, search_sources = _search_coverage_evidence(
        advanced_search_report=advanced_search_report,
        deep_research_eval_ref=deep_research_eval_ref,
        citation_faithfulness_eval_ref=citation_faithfulness_eval_ref,
    )
    reflexion_blockers, reflexion_refs, reflexion_metrics, reflexion_sources = (
        _reflexion_coverage_evidence(agent_policy_report)
    )
    context_blockers, context_refs, context_metrics, context_sources = _artifact_ref_coverage(
        context_memory_eval_ref,
        missing_blocker="missing_context_memory_eval_ref",
        source_report="ContextMemoryPromotionEvidence",
    )
    provider_blockers, provider_refs, provider_metrics, provider_sources = _artifact_ref_coverage(
        provider_behavior_eval_ref,
        missing_blocker="missing_provider_behavior_eval_ref",
        source_report="ProviderBehaviorPromotionEvidence",
    )
    evidence_by_domain = {
        AgentPromotionCoverageDomain.TOOL_LOOP: (
            tool_blockers,
            tool_refs,
            tool_metrics,
            tool_sources,
        ),
        AgentPromotionCoverageDomain.SUPERVISOR: (
            supervisor_blockers,
            supervisor_refs,
            supervisor_metrics,
            supervisor_sources,
        ),
        AgentPromotionCoverageDomain.SEARCH: (
            search_blockers,
            search_refs,
            search_metrics,
            search_sources,
        ),
        AgentPromotionCoverageDomain.REFLEXION: (
            reflexion_blockers,
            reflexion_refs,
            reflexion_metrics,
            reflexion_sources,
        ),
        AgentPromotionCoverageDomain.CONTEXT_MEMORY: (
            context_blockers,
            context_refs,
            context_metrics,
            context_sources,
        ),
        AgentPromotionCoverageDomain.PROVIDER_BEHAVIOR: (
            provider_blockers,
            provider_refs,
            provider_metrics,
            provider_sources,
        ),
    }
    records: list[AgentPromotionCoverageRecord] = []
    for domain in AgentPromotionCoverageDomain:
        blockers, evidence_refs, metrics, source_reports = evidence_by_domain[domain]
        records.append(
            AgentPromotionCoverageRecord(
                domain=domain,
                status=_coverage_status(
                    blockers=blockers,
                    offline_validation_ref=offline_validation_ref,
                    benchmark_pack_ref=benchmark_pack_ref,
                ),
                blockers=sorted(set(blockers)),
                evidence_refs=evidence_refs,
                metrics=metrics,
                source_reports=source_reports,
            )
        )
    return records


def _tool_loop_evidence(
    summary: ToolContractSummary | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    blockers = tool_contract_default_blockers(summary)
    metrics: dict[str, Any] = {}
    if summary is not None:
        metrics = {
            "tool_count": summary.tool_count,
            "invalid_tool_count": summary.invalid_tool_count,
            "schema_ready": summary.schema_ready,
            "runtime_caps_ready": summary.runtime_caps_ready,
            "structured_error_taxonomy_ready": summary.structured_error_taxonomy_ready,
            "issue_codes": [issue.issue_code for issue in summary.issues],
        }
    return blockers, [], metrics, ["ToolContractSummary"]


def _supervisor_evidence(
    evaluation: SupervisorPromotionEvaluation | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    if evaluation is None:
        return ["supervisor_eval_missing"], [], {}, ["SupervisorPromotionEvaluation"]
    metrics = evaluation.metrics.model_dump(mode="json", exclude={"handoff_eval_ref"})
    evidence_refs = (
        [evaluation.metrics.handoff_eval_ref]
        if evaluation.metrics.handoff_eval_ref is not None
        else []
    )
    return (
        list(evaluation.blockers),
        evidence_refs,
        metrics,
        ["SupervisorPromotionEvaluation"],
    )


def _deep_research_evidence(
    *,
    deep_research_eval_ref: ArtifactRef | None,
    citation_faithfulness_eval_ref: ArtifactRef | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    blockers: list[str] = []
    evidence_refs: list[ArtifactRef] = []
    if deep_research_eval_ref is None:
        blockers.append("missing_deep_research_eval_ref")
    else:
        evidence_refs.append(deep_research_eval_ref)
    if citation_faithfulness_eval_ref is None:
        blockers.append("missing_citation_faithfulness_eval_ref")
    else:
        evidence_refs.append(citation_faithfulness_eval_ref)
    return blockers, evidence_refs, {}, ["DeepResearchEvidence"]


def _reasoning_evidence(
    *,
    mode: str,
    reasoning_gate: ReasoningPolicyGate | None,
    agent_policy_report: AgentPolicyComparisonReport | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    blockers: list[str] = []
    metrics: dict[str, Any] = {"mode": mode}
    source_reports = ["ReasoningPolicyGate", "AgentPolicyComparisonReport"]
    if reasoning_gate is None:
        blockers.append(f"{mode}_reasoning_gate_missing")
    else:
        gate_status = reasoning_gate.status_for(mode)
        metrics["gate"] = gate_status
        if not gate_status.get("allowed"):
            blockers.append(f"{mode}_requires_offline_validation")
    if agent_policy_report is None:
        blockers.append("missing_comparative_agent_policy_report")
    else:
        metrics["agent_policy_rollout_status"] = str(agent_policy_report.rollout_status)
        metrics["agent_policy_default_enable_eligible"] = (
            agent_policy_report.default_enable_eligible
        )
        metrics["agent_policy_blockers"] = list(agent_policy_report.blockers)
        if not agent_policy_report.default_enable_eligible:
            blockers.append("comparative_agent_policy_not_default_eligible")
    return blockers, [], metrics, source_reports


def _learned_search_evidence(
    *,
    capability_id: AgentCapabilityId,
    advanced_search_report: AdvancedSearchPolicyReport | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    policy_name = capability_id.value
    blockers = [
        f"{policy_name}_shadow_only_until_calibration_tests_pass",
        f"{policy_name}_shadow_only_until_regret_tests_pass",
    ]
    metrics: dict[str, Any] = {"policy_name": policy_name}
    if advanced_search_report is None:
        blockers.append("missing_advanced_search_policy_report")
    else:
        metrics["requested_policies"] = list(advanced_search_report.requested_policies)
        metrics["offline_gate_passed"] = advanced_search_report.offline_gate_passed
        metrics["rollout_status"] = str(advanced_search_report.rollout_status)
        metrics["default_enable_eligible"] = advanced_search_report.default_enable_eligible
        if policy_name not in advanced_search_report.requested_policies:
            blockers.append(f"{policy_name}_not_requested_in_advanced_search_report")
    return blockers, [], metrics, ["AdvancedSearchPolicyReport"]


def _search_coverage_evidence(
    *,
    advanced_search_report: AdvancedSearchPolicyReport | None,
    deep_research_eval_ref: ArtifactRef | None,
    citation_faithfulness_eval_ref: ArtifactRef | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    blockers: list[str] = []
    evidence_refs: list[ArtifactRef] = []
    metrics: dict[str, Any] = {}
    source_reports = ["AdvancedSearchPolicyReport", "DeepResearchEvidence"]
    if advanced_search_report is None:
        blockers.append("missing_advanced_search_policy_report")
    else:
        metrics["advanced_search_requested_policies"] = list(
            advanced_search_report.requested_policies
        )
        metrics["advanced_search_rollout_status"] = str(advanced_search_report.rollout_status)
        metrics["advanced_search_default_enable_eligible"] = (
            advanced_search_report.default_enable_eligible
        )
    if deep_research_eval_ref is None:
        blockers.append("missing_deep_research_eval_ref")
    else:
        evidence_refs.append(deep_research_eval_ref)
    if citation_faithfulness_eval_ref is None:
        blockers.append("missing_citation_faithfulness_eval_ref")
    else:
        evidence_refs.append(citation_faithfulness_eval_ref)
    return blockers, evidence_refs, metrics, source_reports


def _reflexion_coverage_evidence(
    agent_policy_report: AgentPolicyComparisonReport | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    if agent_policy_report is None:
        return (
            ["missing_reflexion_baseline_comparison"],
            [],
            {},
            ["AgentPolicyComparisonReport"],
        )
    metrics = {
        "baseline_name": getattr(agent_policy_report, "baseline_name", "reflexion_only"),
        "candidate_name": getattr(agent_policy_report, "candidate_name", "candidate"),
        "rollout_status": str(agent_policy_report.rollout_status),
        "release_gate_passed": bool(agent_policy_report.release_gate_passed),
        "default_enable_eligible": bool(agent_policy_report.default_enable_eligible),
        "blockers": list(agent_policy_report.blockers),
    }
    blockers = (
        []
        if agent_policy_report.default_enable_eligible
        else ["reflexion_baseline_comparison_not_default_eligible"]
    )
    return blockers, [], metrics, ["AgentPolicyComparisonReport"]


def _artifact_ref_coverage(
    ref: ArtifactRef | None,
    *,
    missing_blocker: str,
    source_report: str,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    if ref is None:
        return [missing_blocker], [], {}, [source_report]
    return [], [ref], {}, [source_report]


def _fanout_evidence(
    *,
    agent_policy_report: AgentPolicyComparisonReport | None,
    fanout_budget_eval_ref: ArtifactRef | None,
    fanout_consistency_eval_ref: ArtifactRef | None,
) -> tuple[list[str], list[ArtifactRef], dict[str, Any], list[str]]:
    blockers: list[str] = []
    evidence_refs: list[ArtifactRef] = []
    metrics: dict[str, Any] = {}
    if agent_policy_report is None:
        blockers.append("missing_comparative_agent_policy_report")
    else:
        metrics["agent_policy_rollout_status"] = str(agent_policy_report.rollout_status)
        metrics["agent_policy_default_enable_eligible"] = (
            agent_policy_report.default_enable_eligible
        )
        if not agent_policy_report.default_enable_eligible:
            blockers.append("comparative_agent_policy_not_default_eligible")
    if fanout_budget_eval_ref is None:
        blockers.append("missing_fanout_budget_eval_ref")
    else:
        evidence_refs.append(fanout_budget_eval_ref)
    if fanout_consistency_eval_ref is None:
        blockers.append("missing_fanout_citation_consistency_eval_ref")
    else:
        evidence_refs.append(fanout_consistency_eval_ref)
    return blockers, evidence_refs, metrics, ["AgentPolicyComparisonReport", "FanoutEval"]


def _coverage_status(
    *,
    blockers: list[str],
    offline_validation_ref: ArtifactRef | None,
    benchmark_pack_ref: ArtifactRef | None,
) -> FrontierCapabilityStatus:
    if blockers or offline_validation_ref is None or benchmark_pack_ref is None:
        return FrontierCapabilityStatus.OFFLINE_GATED
    return FrontierCapabilityStatus.AVAILABLE_OFFLINE


def _frontier_status(
    *,
    family: AgentCapabilityFamily,
    blockers: list[str],
    evidence_refs: list[ArtifactRef],
    offline_validation_ref: ArtifactRef | None,
    benchmark_pack_ref: ArtifactRef | None,
) -> FrontierCapabilityStatus:
    if family.frontier_status == FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED:
        return FrontierCapabilityStatus.EXPERIMENTAL_NOT_WIRED
    if blockers or offline_validation_ref is None or benchmark_pack_ref is None:
        return FrontierCapabilityStatus.OFFLINE_GATED
    if family.capability_id in {
        AgentCapabilityId.TOOL_LOOP,
        AgentCapabilityId.SUPERVISOR_WORKER,
        AgentCapabilityId.TREE_OF_THOUGHT,
        AgentCapabilityId.LATS_MCTS,
    }:
        return FrontierCapabilityStatus.AVAILABLE_OFFLINE
    if (
        family.capability_id
        in {
            AgentCapabilityId.DEEP_RESEARCH_SUBGRAPH,
            AgentCapabilityId.SAME_MODEL_FANOUT,
        }
        and evidence_refs
    ):
        return FrontierCapabilityStatus.AVAILABLE_OFFLINE
    return FrontierCapabilityStatus.OFFLINE_GATED
