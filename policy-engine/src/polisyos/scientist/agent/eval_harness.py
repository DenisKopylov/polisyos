"""Starter eval harness for Scientist v2 rollout and provider smoke gates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.scholar.search.models import (
    ClaimSupportLink,
    QueryGraph,
    QueryNode,
    ResearchBrief,
    SearchQueryTrace,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
)
from polisyos.scientist.agent.critic import MockCriticAgent
from polisyos.scientist.agent.drafter_clients import MockDrafterAgent
from polisyos.scientist.agent.fabric import (
    ScientistAgentFabric,
    ScientistAgentFabricConfig,
    ScientistAgentFabricRequest,
)
from polisyos.scientist.agent.formalizer import MockFormalizerAgent
from polisyos.scientist.agent.pi import MockPIAgent
from polisyos.scientist.agent.reflexion_evaluator import (
    ReflexionReplayCase,
    ReflexionTrajectoryStep,
    evaluate_reflexion_replay_cases,
)
from polisyos.scientist.agent.tools.registry import ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition
from polisyos.scientist.llm.provider_verification import run_gonka_provider_smoke

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore

__all__ = [
    "AgentEvalCaseResult",
    "AgentEvalReport",
    "AgentPolicyComparisonReport",
    "AgentPolicyRolloutStatus",
    "AgentReleaseGateConfig",
    "ReleaseGateEvaluation",
    "compare_agent_eval_reports",
    "run_starter_eval_harness",
]


class AgentEvalCaseResult(BaseModel):
    """One starter-harness case result."""

    model_config = ConfigDict(extra="forbid")

    suite: str
    case_id: str
    passed: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    error: str | None = None


class AgentEvalReport(BaseModel):
    """Machine-readable starter eval report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cases: list[AgentEvalCaseResult] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class AgentReleaseGateConfig(BaseModel):
    """Thresholds for staged rollout and default-on promotion."""

    model_config = ConfigDict(extra="forbid")

    min_citation_coverage: float = Field(default=0.85, ge=0.0, le=1.0)
    min_search_precision_proxy: float = Field(default=0.60, ge=0.0, le=1.0)
    max_invalid_tool_call_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    min_task_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    min_reflexion_recovery_rate: float = Field(default=0.50, ge=0.0, le=1.0)
    min_candidate_lift: float = Field(default=0.0, ge=-1.0, le=1.0)


class ReleaseGateEvaluation(BaseModel):
    """Computed gate decision over starter-harness metrics."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    checks: dict[str, Any] = Field(default_factory=dict)
    failed_checks: list[str] = Field(default_factory=list)


class AgentPolicyComparisonReport(BaseModel):
    """Compare a candidate search/reasoning policy against Reflexion-only baseline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    baseline_name: str = "reflexion_only"
    candidate_name: str = "candidate"
    baseline_summary: dict[str, Any] = Field(default_factory=dict)
    candidate_summary: dict[str, Any] = Field(default_factory=dict)
    deltas: dict[str, float] = Field(default_factory=dict)
    offline_validation_ref: str | None = None
    release_gate_passed: bool = False
    rollout_status: "AgentPolicyRolloutStatus"
    passed: bool = False
    default_enable_eligible: bool = False
    blockers: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AgentPolicyRolloutStatus(StrEnum):
    """Explicit rollout posture for a candidate WS-3C policy."""

    OFFLINE_GATED = "offline_gated"
    RELEASE_GATED = "release_gated"
    DEFAULT_ENABLE_ELIGIBLE = "default_enable_eligible"


@dataclass
class _ProxySearchService:
    async def deep_search(
        self,
        *,
        question: str | None = None,
        claim_texts: list[str] | tuple[str, ...] | None = None,
        **kwargs: object,
    ) -> WebEvidenceBundle:
        del kwargs
        brief = ResearchBrief(
            question=question or "policy research",
            perspectives=[
                "impact evidence",
                "implementation",
                "uncertainty",
            ],
        )
        graph = QueryGraph(
            brief=brief,
            nodes=[
                QueryNode(
                    node_id="q1",
                    query=question or "policy research",
                    perspective="impact evidence",
                    status="searched",
                    hit_count=1,
                )
            ],
            root_node_ids=["q1"],
        )
        source = SourceMetadata(
            source_id="src.1",
            url="https://agency.gov/policy",
            title="Agency policy evidence",
            domain="agency.gov",
            source_type="government",
            provider="proxy",
            search_query=question or "policy research",
            search_rank=1,
            fetch_status="ok",
            content_type="text/html",
            quality_score=0.9,
        )
        snippet = SourceSnippet(
            snippet_id="snip.1",
            source_id="src.1",
            url="https://agency.gov/policy",
            query_node_id="q1",
            perspective="impact evidence",
            text="Targeted support increased earnings and reduced hardship.",
            start_char=0,
            end_char=63,
            relevance_score=0.9,
        )
        claim_text = (claim_texts or [question or "policy research"])[0]
        return WebEvidenceBundle(
            bundle_id="webkb.proxy",
            brief=brief,
            query_graph=graph,
            query_traces=[
                SearchQueryTrace(
                    query_node_id="q1",
                    query=question or "policy research",
                    perspective="impact evidence",
                    provider="proxy",
                    hit_count=1,
                )
            ],
            sources=[source],
            snippets=[snippet],
            claim_supports=[
                ClaimSupportLink(
                    claim_id="claim.1",
                    claim_text=claim_text,
                    snippet_ids=["snip.1"],
                    source_ids=["src.1"],
                    support_score=0.9,
                    conflict_score=0.0,
                )
            ],
        )


async def run_starter_eval_harness(
    *,
    cas_root: str | Path,
    include_live_provider: bool = False,
    model_id: str = "qwen/qwen3-235b-a22b-instruct-2507-fp8",
    base_url: str = "https://api.gonkagate.com/v1",
    verification_dir: str | Path = ".polisyos/provider_verification",
    release_gate_config: AgentReleaseGateConfig | None = None,
    artifact_store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> AgentEvalReport:
    cases: list[AgentEvalCaseResult] = []
    cases.append(
        await _run_tool_calling_regression_case()
    )
    cases.append(
        await _run_local_search_grounding_case(
            cas_root=Path(cas_root),
            artifact_store_factory=artifact_store_factory,
        )
    )
    cases.append(
        await _run_local_swarm_reflexion_case(
            cas_root=Path(cas_root),
            artifact_store_factory=artifact_store_factory,
        )
    )
    cases.append(_run_reflexion_replay_case())
    if include_live_provider:
        cases.append(
            await _run_live_provider_case(
                model_id=model_id,
                base_url=base_url,
                verification_dir=verification_dir,
            )
        )

    passed = sum(1 for case in cases if case.passed)
    metrics = _aggregate_case_metrics(cases)
    gate = _evaluate_release_gates(
        metrics,
        release_gate_config or AgentReleaseGateConfig(),
    )
    report = AgentEvalReport(
        cases=cases,
        summary={
            "total_cases": len(cases),
            "passed_cases": passed,
            "failed_cases": len(cases) - passed,
            "pass_rate": passed / max(len(cases), 1),
            "metrics": metrics,
            "release_gates": gate.model_dump(mode="json"),
        },
    )
    return report


async def _run_local_search_grounding_case(
    *,
    cas_root: Path,
    artifact_store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> AgentEvalCaseResult:
    case_id = "search_grounding_proxy"
    try:
        cas = (artifact_store_factory or _build_eval_artifact_store)(
            cas_root / "cas_search"
        )
        problem_frame = await MockPIAgent().create_problem_frame(
            "Reduce poverty with targeted transfers",
            domain_hint="economic",
        )
        fabric = ScientistAgentFabric(
            config=ScientistAgentFabricConfig(
                enabled=True,
                web_search_enabled=True,
                swarm_enabled=False,
                reflexion_enabled=False,
                memory_index_path=cas_root / "memory_index_search.txt",
            )
        )
        result = await fabric.run(
            ScientistAgentFabricRequest(
                run_id="eval_search",
                variant_id="variant_search",
                model_name=None,
                llm_client=None,
                problem_frame=problem_frame,
                data_context={"metrics": []},
                drafter=MockDrafterAgent(),
                formalizer=MockFormalizerAgent(),
                critic=MockCriticAgent(default_verdict="APPROVE"),
                artifact_store=cas,
                max_iterations=1,
                search_service=_ProxySearchService(),
            )
        )
        citation_coverage = float(result.metrics.get("citation_coverage") or 0.0)
        total_snippets = int(result.metrics.get("citation_count") or 0)
        search_precision_proxy = len(result.draft.citations) / max(total_snippets, 1)
        passed = citation_coverage > 0 and search_precision_proxy > 0
        return AgentEvalCaseResult(
            suite="search",
            case_id=case_id,
            passed=passed,
            metrics={
                "citation_count": len(result.draft.citations),
                "citation_coverage": citation_coverage,
                "search_precision_proxy": search_precision_proxy,
            },
        )
    except Exception as exc:
        return AgentEvalCaseResult(
            suite="search",
            case_id=case_id,
            passed=False,
            error=str(exc),
        )


async def _run_local_swarm_reflexion_case(
    *,
    cas_root: Path,
    artifact_store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> AgentEvalCaseResult:
    case_id = "fabric_proxy_grounding"
    try:
        cas = (artifact_store_factory or _build_eval_artifact_store)(
            cas_root / "cas_swarm"
        )
        problem_frame = await MockPIAgent().create_problem_frame(
            "Reduce poverty with targeted transfers",
            domain_hint="economic",
        )
        fabric = ScientistAgentFabric(
            config=ScientistAgentFabricConfig(
                enabled=True,
                web_search_enabled=True,
                swarm_enabled=True,
                reflexion_enabled=True,
                max_reflexion_iterations=2,
                max_swarm_budget_usd=Decimal("0.01"),
                memory_index_path=cas_root / "memory_index.txt",
            )
        )
        result = await fabric.run(
            ScientistAgentFabricRequest(
                run_id="eval_swarm",
                variant_id="variant_swarm",
                model_name=None,
                llm_client=None,
                problem_frame=problem_frame,
                data_context={"metrics": []},
                drafter=MockDrafterAgent(),
                formalizer=MockFormalizerAgent(),
                critic=MockCriticAgent(default_verdict="APPROVE"),
                artifact_store=cas,
                max_iterations=2,
                search_service=_ProxySearchService(),
            )
        )
        citation_count = len(result.draft.citations)
        supervisor_trace = dict(result.traces.get("supervisor") or {})
        passed = citation_count > 0 and all(
            key in supervisor_trace for key in ("search", "drafting", "critique", "evaluation")
        )
        return AgentEvalCaseResult(
            suite="swarm",
            case_id=case_id,
            passed=passed,
            metrics={
                "verdict": result.result["verdict"],
                "citation_count": citation_count,
                "issue_count": result.result["issue_count"],
                "has_memory_index_ref": "memory_index_ref" in result.traces,
                "has_supervisor_trace": "supervisor" in result.traces,
                "citation_coverage": float(result.metrics.get("citation_coverage") or 0.0),
                "search_precision_proxy": citation_count / max(
                    int(result.metrics.get("citation_count") or 0),
                    1,
                ),
                "reflexion_recovery_rate": 1.0 if "memory_index_ref" in result.traces else 0.0,
            },
        )
    except Exception as exc:
        return AgentEvalCaseResult(
            suite="swarm",
            case_id=case_id,
            passed=False,
            error=str(exc),
        )


async def _run_tool_calling_regression_case() -> AgentEvalCaseResult:
    case_id = "tool_registry_validation"
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="probe_tool",
            description="Validates structured tool arguments.",
            parameters={
                "type": "object",
                "required": ["query"],
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                },
            },
        ),
        lambda query: {"ok": query},
    )
    result = await registry.aexecute("probe_tool", {"unexpected": True})
    details = dict(result.error_details or {})
    passed = (
        result.error_type == "invalid_arguments"
        and bool(details)
        and (
            "message" in details
            or bool(details.get("schema_errors"))
            or bool(details.get("issues"))
        )
    )
    return AgentEvalCaseResult(
        suite="tool_calling",
        case_id=case_id,
        passed=passed,
        metrics={
            "invalid_tool_call_rate": 0.0 if passed else 1.0,
            "error_type": result.error_type,
        },
        notes=[result.error] if result.error else [],
    )


def _run_reflexion_replay_case() -> AgentEvalCaseResult:
    case_id = "reflexion_replay_proxy"
    replay = evaluate_reflexion_replay_cases(
        [
            ReflexionReplayCase(
                case_id="case-improves",
                objective="Explain policy with citations",
                steps=[
                    ReflexionTrajectoryStep(
                        iteration=1,
                        output_text="done",
                        tool_results=[
                            {
                                "tool_name": "scholar_web_search",
                                "arguments": {},
                                "error": "invalid args",
                                "error_type": "invalid_arguments",
                            }
                        ],
                    ),
                    ReflexionTrajectoryStep(
                        iteration=2,
                        output_text="Policy answer with cited evidence https://example.org/report",
                        citations=[
                            {
                                "url": "https://example.org/report",
                                "snippet": "Evidence snippet",
                                "source_id": "src-1",
                            }
                        ],
                    ),
                ],
            ),
            ReflexionReplayCase(
                case_id="case-repeats-error",
                objective="Explain policy",
                steps=[
                    ReflexionTrajectoryStep(
                        iteration=1,
                        output_text="done",
                        tool_results=[
                            {
                                "tool_name": "scholar_fetch_open",
                                "arguments": {},
                                "error": "timeout",
                                "error_type": "timeout",
                            }
                        ],
                    ),
                    ReflexionTrajectoryStep(
                        iteration=2,
                        output_text="done",
                        tool_results=[
                            {
                                "tool_name": "scholar_fetch_open",
                                "arguments": {},
                                "error": "timeout",
                                "error_type": "timeout",
                            }
                        ],
                    ),
                ],
                expected_success=False,
            ),
        ]
    )
    passed = replay.improvement_rate >= 0.5 and replay.repeated_error_rate <= 0.5
    return AgentEvalCaseResult(
        suite="reflexion",
        case_id=case_id,
        passed=passed,
        metrics=replay.model_dump(mode="json"),
    )


async def _run_live_provider_case(
    *,
    model_id: str,
    base_url: str,
    verification_dir: str | Path,
) -> AgentEvalCaseResult:
    case_id = "provider_contract_live"
    try:
        report = await run_gonka_provider_smoke(
            model_id=model_id,
            base_url=base_url,
            verification_dir=verification_dir,
            include_web_search_smoke=True,
        )
        passed = all(check.passed for check in report.checks)
        return AgentEvalCaseResult(
            suite="provider_contract",
            case_id=case_id,
            passed=passed,
            metrics={
                "checks": [check.model_dump(mode="json") for check in report.checks],
                "request_ids": list(report.verification.request_ids),
            },
        )
    except Exception as exc:
        return AgentEvalCaseResult(
            suite="provider_contract",
            case_id=case_id,
            passed=False,
            error=str(exc),
        )


def _build_eval_artifact_store(root: Path) -> ArtifactStore:
    return build_artifact_store(
        ArtifactStoreConfig(backend="filesystem", root=str(root)),
    )


def _aggregate_case_metrics(cases: list[AgentEvalCaseResult]) -> dict[str, Any]:
    active_cases = [case for case in cases if case.suite != "provider_contract"]
    task_success_rate = sum(1 for case in active_cases if case.passed) / max(len(active_cases), 1)
    citation_coverages = [
        float(case.metrics.get("citation_coverage") or 0.0)
        for case in cases
        if "citation_coverage" in case.metrics
    ]
    search_precisions = [
        float(case.metrics.get("search_precision_proxy") or 0.0)
        for case in cases
        if "search_precision_proxy" in case.metrics
    ]
    invalid_tool_rates = [
        float(case.metrics.get("invalid_tool_call_rate") or 0.0)
        for case in cases
        if "invalid_tool_call_rate" in case.metrics
    ]
    reflexion_rates = [
        float(
            case.metrics.get("improvement_rate")
            or case.metrics.get("reflexion_recovery_rate")
            or 0.0
        )
        for case in cases
        if case.suite in {"reflexion", "swarm"}
    ]
    provider_cases = [case for case in cases if case.suite == "provider_contract"]
    return {
        "task_success_rate": task_success_rate,
        "citation_coverage": sum(citation_coverages) / max(len(citation_coverages), 1),
        "search_precision_proxy": sum(search_precisions) / max(len(search_precisions), 1),
        "invalid_tool_call_rate": sum(invalid_tool_rates) / max(len(invalid_tool_rates), 1),
        "reflexion_recovery_rate": sum(reflexion_rates) / max(len(reflexion_rates), 1),
        "provider_contract_pass_rate": (
            sum(1 for case in provider_cases if case.passed) / len(provider_cases)
            if provider_cases
            else None
        ),
        "suite_pass_rates": {
            suite: (
                sum(1 for case in cases if case.suite == suite and case.passed)
                / max(sum(1 for case in cases if case.suite == suite), 1)
            )
            for suite in sorted({case.suite for case in cases})
        },
    }


def _evaluate_release_gates(
    metrics: dict[str, Any],
    config: AgentReleaseGateConfig,
) -> ReleaseGateEvaluation:
    checks = {
        "task_success_rate": {
            "actual": float(metrics.get("task_success_rate") or 0.0),
            "threshold": config.min_task_success_rate,
        },
        "citation_coverage": {
            "actual": float(metrics.get("citation_coverage") or 0.0),
            "threshold": config.min_citation_coverage,
        },
        "search_precision_proxy": {
            "actual": float(metrics.get("search_precision_proxy") or 0.0),
            "threshold": config.min_search_precision_proxy,
        },
        "invalid_tool_call_rate": {
            "actual": float(metrics.get("invalid_tool_call_rate") or 0.0),
            "threshold": config.max_invalid_tool_call_rate,
        },
        "reflexion_recovery_rate": {
            "actual": float(metrics.get("reflexion_recovery_rate") or 0.0),
            "threshold": config.min_reflexion_recovery_rate,
        },
    }
    failed_checks = [
        name
        for name, payload in checks.items()
        if (
            payload["actual"] < payload["threshold"]
            if name != "invalid_tool_call_rate"
            else payload["actual"] > payload["threshold"]
        )
    ]
    return ReleaseGateEvaluation(
        passed=not failed_checks,
        checks=checks,
        failed_checks=failed_checks,
    )


def compare_agent_eval_reports(
    baseline: AgentEvalReport,
    candidate: AgentEvalReport,
    *,
    config: AgentReleaseGateConfig | None = None,
    baseline_name: str = "reflexion_only",
    candidate_name: str = "candidate",
    offline_validation_ref: str | None = None,
) -> AgentPolicyComparisonReport:
    """Build the comparative WS-3C report required before default enablement."""

    active_config = config or AgentReleaseGateConfig()
    baseline_metrics = dict(baseline.summary.get("metrics") or {})
    candidate_metrics = dict(candidate.summary.get("metrics") or {})
    metric_names = sorted(set(baseline_metrics).intersection(candidate_metrics))
    deltas: dict[str, float] = {}
    for metric in metric_names:
        baseline_value = baseline_metrics.get(metric)
        candidate_value = candidate_metrics.get(metric)
        if isinstance(baseline_value, (int, float)) and isinstance(candidate_value, (int, float)):
            deltas[metric] = float(candidate_value) - float(baseline_value)

    gate = _evaluate_release_gates(candidate_metrics, active_config)
    blockers = list(gate.failed_checks)
    release_gate_passed = gate.passed
    if deltas.get("task_success_rate", 0.0) < active_config.min_candidate_lift:
        blockers.append("candidate_lift_below_threshold")
        release_gate_passed = False
    if offline_validation_ref is None:
        blockers.append("missing_offline_validation_ref")
    if offline_validation_ref is None:
        rollout_status = AgentPolicyRolloutStatus.OFFLINE_GATED
    elif release_gate_passed:
        rollout_status = AgentPolicyRolloutStatus.DEFAULT_ENABLE_ELIGIBLE
    else:
        rollout_status = AgentPolicyRolloutStatus.RELEASE_GATED

    passed = rollout_status is AgentPolicyRolloutStatus.DEFAULT_ENABLE_ELIGIBLE
    return AgentPolicyComparisonReport(
        baseline_name=baseline_name,
        candidate_name=candidate_name,
        baseline_summary=dict(baseline.summary),
        candidate_summary=dict(candidate.summary),
        deltas=deltas,
        offline_validation_ref=offline_validation_ref,
        release_gate_passed=release_gate_passed,
        rollout_status=rollout_status,
        passed=passed,
        default_enable_eligible=passed and offline_validation_ref is not None,
        blockers=sorted(set(blockers)),
        notes=[
            "Candidate policies remain offline-gated until this comparison report "
            "is persisted and referenced by runtime config.",
        ],
    )
