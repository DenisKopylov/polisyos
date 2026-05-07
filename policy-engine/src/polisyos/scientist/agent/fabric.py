"""Production-facing Scientist v2 orchestration facade."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.ir.trinity import TrinityBundle
from polisyos.scholar.search.models import (
    SearchBudgetControls,
    SearchConstraints,
    WebEvidenceBundle,
)
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
from polisyos.scientist.agent.persistent_memory import PersistentMemoryStore
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame
from polisyos.scientist.agent.reflexion import ReflexionConfig, ReflexionOrchestrator
from polisyos.scientist.agent.reflexion_evaluator import (
    ReflexionScorecard,
    RubricReflexionEvaluator,
)
from polisyos.scientist.agent.supervisor import (
    ScientistSupervisorAgent,
    ScientistSupervisorConfig,
    SupervisorSynthesisMode,
)
from polisyos.scientist.agent.tools.scholar_search_tools import build_scholar_search_tool_registry
from polisyos.scientist.agent.tools.tool_loop import (
    ToolLoopCompactionConfig,
    ToolLoopResult,
    run_tool_loop,
)
from polisyos.scientist.agent.workers import (
    WorkerBudgetHints,
    WorkerSourcePolicy,
    build_critic_worker_handler,
    build_drafter_worker_handler,
    build_reflexion_evaluator_worker_handler,
    build_scholar_search_worker_handler,
    build_sectioned_worker_envelopes,
    build_worker_tool_registry,
    critique_from_payload,
    draft_from_payload,
)
from polisyos.scientist.orchestration.llm.provider_verification import is_provider_capability_verified

__all__ = [
    "ScientistAgentFabric",
    "ScientistAgentFabricConfig",
    "ScientistAgentFabricRequest",
    "ScientistAgentFabricResponse",
]


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ScientistAgentFabricConfig:
    """Feature flags and runtime knobs for Scientist v2 orchestration."""

    enabled: bool = False
    shadow_mode: bool = False
    web_search_enabled: bool = False
    swarm_enabled: bool = False
    reflexion_enabled: bool = False
    max_tool_loop_iterations: int = 4
    max_reflexion_iterations: int = 3
    max_swarm_workers: int = 8
    max_parallel_workers: int = 3
    max_swarm_budget_usd: Decimal = Decimal("0.03")
    drafter_self_moa_replicas: int = 3
    critic_vote_workers: int = 3
    tool_discovery_threshold: int = 24
    tool_discovery_max_tools: int = 12
    memory_index_path: Path = Path(".polisyos/scientist/reflexion_memory_index.txt")

    @classmethod
    def from_env(cls) -> ScientistAgentFabricConfig:
        return cls(
            enabled=_as_bool(os.getenv("POLISYOS_SCIENTIST_V2_ENABLED"), default=False),
            shadow_mode=_as_bool(os.getenv("POLISYOS_SCIENTIST_SHADOW_MODE"), default=False),
            web_search_enabled=_as_bool(
                os.getenv("POLISYOS_SCIENTIST_WEB_SEARCH_ENABLED"),
                default=False,
            ),
            swarm_enabled=_as_bool(
                os.getenv("POLISYOS_SCIENTIST_SWARM_ENABLED"),
                default=False,
            ),
            reflexion_enabled=_as_bool(
                os.getenv("POLISYOS_SCIENTIST_REFLEXION_ENABLED"),
                default=False,
            ),
            max_tool_loop_iterations=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_TOOL_LOOP_MAX_ITERS", "4")),
            ),
            max_reflexion_iterations=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_REFLEXION_MAX_ITERS", "3")),
            ),
            max_swarm_workers=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_SWARM_MAX_WORKERS", "8")),
            ),
            max_parallel_workers=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_SWARM_MAX_PARALLEL", "3")),
            ),
            max_swarm_budget_usd=Decimal(
                os.getenv("POLISYOS_SCIENTIST_SWARM_MAX_BUDGET_USD", "0.03")
            ),
            drafter_self_moa_replicas=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_DRAFTER_SELF_MOA_REPLICAS", "3")),
            ),
            critic_vote_workers=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_CRITIC_VOTE_WORKERS", "3")),
            ),
            tool_discovery_threshold=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_TOOL_DISCOVERY_THRESHOLD", "24")),
            ),
            tool_discovery_max_tools=max(
                1,
                int(os.getenv("POLISYOS_SCIENTIST_TOOL_DISCOVERY_MAX_TOOLS", "12")),
            ),
            memory_index_path=Path(
                os.getenv(
                    "POLISYOS_SCIENTIST_REFLEXION_MEMORY_INDEX_PATH",
                    ".polisyos/scientist/reflexion_memory_index.txt",
                )
            ),
        )


@dataclass(frozen=True)
class ScientistAgentFabricRequest:
    """One v2 orchestration request over already-resolved retrieval context."""

    run_id: str
    variant_id: str
    model_name: str | None
    llm_client: Any | None
    problem_frame: ProblemFrame
    data_context: dict[str, Any]
    drafter: Any
    formalizer: Any
    critic: Any
    artifact_store: ArtifactStore
    max_iterations: int
    search_service: ScholarDeepSearchService | None = None
    search_constraints: SearchConstraints | None = None
    search_budgets: SearchBudgetControls | None = None


@dataclass
class ScientistAgentFabricResponse:
    """Unified v2 result contract used by the HTTP control path."""

    draft: DraftResult
    trinity_bundle: TrinityBundle
    critique: Any
    result: dict[str, Any]
    traces: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    shadow: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class _FabricRunState:
    problem_frame: ProblemFrame
    data_context: dict[str, Any]
    memory_store: PersistentMemoryStore
    evaluator: RubricReflexionEvaluator
    reflexion: ReflexionOrchestrator
    traces: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    web_bundle: WebEvidenceBundle | None = None
    tool_loop_result: ToolLoopResult | None = None
    supervisor_payload: dict[str, Any] | None = None
    supervisor: ScientistSupervisorAgent | None = None


class ScientistAgentFabric:
    """Single entrypoint for web grounding, swarm, and Reflexion orchestration."""

    def __init__(
        self,
        *,
        config: ScientistAgentFabricConfig | None = None,
    ) -> None:
        self._config = config or ScientistAgentFabricConfig.from_env()

    @property
    def config(self) -> ScientistAgentFabricConfig:
        return self._config

    async def run(self, request: ScientistAgentFabricRequest) -> ScientistAgentFabricResponse:
        search_service = request.search_service or _default_search_service(request.artifact_store)
        state = self._initialize_run_state(request)
        supervisor_handlers = self._search_supervisor_handlers(search_service, state.evaluator)

        await self._apply_grounding(
            request=request,
            state=state,
            search_service=search_service,
        )

        if self._config.swarm_enabled and state.web_bundle is not None:
            state.supervisor = self._make_supervisor(supervisor_handlers)
            await self._run_search_swarm(
                request=request,
                state=state,
            )
        elif self._config.swarm_enabled:
            state.supervisor = self._make_supervisor(supervisor_handlers)

        hint_lines = self._collect_memory_hints(state)
        draft, trinity_bundle, critique, scorecard = await self._run_draft_cycle(
            request=request,
            state=state,
            hint_lines=hint_lines,
        )

        self._persist_reflexion_memory(
            request=request,
            state=state,
            critique=critique,
            scorecard=scorecard,
        )

        result = {
            "verdict": critique.verdict,
            "issue_count": len(critique.issues),
            "draft_confidence": draft.confidence,
            "web_evidence_bundle_id": (
                state.web_bundle.bundle_id if state.web_bundle is not None else None
            ),
            "tool_loop_used": state.tool_loop_result is not None,
            "swarm_used": state.supervisor is not None,
            "grounding": _grounding_contract(draft),
        }
        state.metrics["citation_coverage"] = _citation_coverage(draft)
        return ScientistAgentFabricResponse(
            draft=draft,
            trinity_bundle=trinity_bundle,
            critique=critique,
            result=result,
            traces=state.traces,
            metrics=state.metrics,
            notes=state.notes,
        )

    def _initialize_run_state(self, request: ScientistAgentFabricRequest) -> _FabricRunState:
        memory_store = self._build_memory_store(request.artifact_store)
        evaluator = RubricReflexionEvaluator()
        reflexion = ReflexionOrchestrator(
            config=ReflexionConfig(max_iterations=self._config.max_reflexion_iterations),
            persistent_memory=memory_store if self._config.reflexion_enabled else None,
            evaluator=evaluator,
        )
        return _FabricRunState(
            problem_frame=request.problem_frame,
            data_context=dict(request.data_context or {}),
            memory_store=memory_store,
            evaluator=evaluator,
            reflexion=reflexion,
        )

    def _search_supervisor_handlers(
        self,
        search_service: ScholarDeepSearchService,
        evaluator: RubricReflexionEvaluator,
    ) -> dict[str, Any]:
        return {
            "scholar_search_worker": build_scholar_search_worker_handler(search_service),
            "reflexion_evaluator_worker": build_reflexion_evaluator_worker_handler(evaluator),
        }

    async def _apply_grounding(
        self,
        *,
        request: ScientistAgentFabricRequest,
        state: _FabricRunState,
        search_service: ScholarDeepSearchService,
    ) -> None:
        if not self._config.web_search_enabled:
            return

        state.web_bundle = await search_service.deep_search(
            question=state.problem_frame.problem_statement,
            claim_texts=[
                state.problem_frame.problem_statement,
                *list(state.problem_frame.goals),
            ],
            constraints=request.search_constraints or SearchConstraints(locale="en-US"),
            budgets=request.search_budgets
            or SearchBudgetControls(
                max_search_queries=8,
                max_parallel_queries=3,
                max_fetch_pages=12,
                max_parallel_fetches=6,
                max_depth=2,
            ),
        )
        web_context = KnowledgeToolkit().format_web_evidence_context(state.web_bundle)
        state.problem_frame = _with_problem_context(
            state.problem_frame,
            web_evidence=state.web_bundle.model_dump(mode="json", exclude_none=True),
            web_evidence_context=web_context,
        )
        state.data_context["web_evidence_bundle_id"] = state.web_bundle.bundle_id
        state.data_context["web_evidence_partial"] = state.web_bundle.partial
        state.traces["web_evidence"] = {
            "bundle_id": state.web_bundle.bundle_id,
            "sources": len(state.web_bundle.sources),
            "snippets": len(state.web_bundle.snippets),
            "claim_supports": len(state.web_bundle.claim_supports),
            "partial": state.web_bundle.partial,
        }
        state.metrics["citation_count"] = len(state.web_bundle.snippets)

        if request.llm_client is None or not _tool_calling_allowed(request.model_name):
            return

        state.tool_loop_result = await run_tool_loop(
            client=request.llm_client,
            system=(
                "You are a research planner. Use the web search tools to collect "
                "fresh factual evidence and answer with a concise cited research memo."
            ),
            user=state.problem_frame.problem_statement,
            tool_registry=build_scholar_search_tool_registry(search_service),
            max_iterations=self._config.max_tool_loop_iterations,
            persistent_memory=state.memory_store if self._config.reflexion_enabled else None,
            reflexion_evaluator=state.evaluator if self._config.reflexion_enabled else None,
            compaction_config=ToolLoopCompactionConfig(),
            tool_discovery_threshold=self._config.tool_discovery_threshold,
            tool_discovery_max_tools=self._config.tool_discovery_max_tools,
        )
        state.traces["tool_loop"] = {
            "iterations": state.tool_loop_result.iterations,
            "tool_calls": len(state.tool_loop_result.tool_calls_made),
            "final_score": state.tool_loop_result.final_score,
            "convergence_reason": state.tool_loop_result.convergence_reason,
            "retrieved_memories": len(state.tool_loop_result.retrieved_memories),
        }
        if state.tool_loop_result.content.strip():
            state.data_context["tool_research_summary"] = state.tool_loop_result.content

    async def _run_search_swarm(
        self,
        *,
        request: ScientistAgentFabricRequest,
        state: _FabricRunState,
    ) -> None:
        if state.supervisor is None or state.web_bundle is None:
            return
        sections = _build_research_sections(state.problem_frame, state.web_bundle)
        envelopes = build_sectioned_worker_envelopes(
            worker_name="scholar_search_worker",
            objective=state.problem_frame.problem_statement,
            sections=sections,
            expected_output_schema={"type": "object"},
            source_policy=WorkerSourcePolicy(
                require_citations=True,
                require_snippets=True,
                min_citations=1,
                allowed_domains=[
                    source.domain for source in state.web_bundle.sources[:16] if source.domain
                ],
            ),
            budget_hints=WorkerBudgetHints(
                max_cost_usd=Decimal("0.003"),
                max_tokens=8192,
                timeout_s=45.0,
                model_id=request.model_name,
            ),
        )
        supervisor_result = await state.supervisor.run(
            envelopes,
            objective=state.problem_frame.problem_statement,
            mode=SupervisorSynthesisMode.SECTIONING,
            run_id=f"{request.run_id}.{request.variant_id}.swarm",
        )
        state.supervisor_payload = supervisor_result.model_dump(mode="json")
        state.traces["supervisor"] = {"search": state.supervisor_payload}
        state.data_context["swarm_research_summary"] = supervisor_result.synthesized_text
        state.metrics["swarm_worker_count"] = len(supervisor_result.worker_results)

    def _collect_memory_hints(self, state: _FabricRunState) -> list[str]:
        hint_lines: list[str] = []
        if not self._config.reflexion_enabled:
            return hint_lines
        recalled = state.memory_store.recall_reflexion_memories(
            problem_statement=state.problem_frame.problem_statement,
            max_results=3,
        )
        if recalled:
            state.traces["memory_recall"] = {
                "count": len(recalled),
                "preview": [entry.content[:160] for entry in recalled],
            }
            hint_lines.append(state.memory_store.format_for_prompt(recalled, max_chars=1200))
        return hint_lines

    async def _run_draft_cycle(
        self,
        *,
        request: ScientistAgentFabricRequest,
        state: _FabricRunState,
        hint_lines: list[str],
    ) -> tuple[DraftResult, TrinityBundle, Any, ReflexionScorecard | None]:
        prior_drafts: list[DraftResult] = []
        critique = None
        scorecard: ReflexionScorecard | None = None

        draft = await self._draft_policy(
            request=request,
            supervisor=state.supervisor,
            problem_frame=state.problem_frame,
            data_context=state.data_context,
            hint_lines=hint_lines,
            traces=state.traces,
        )
        trinity_bundle = await request.formalizer.formalize(draft)

        for iteration in range(
            max(1, min(self._config.max_reflexion_iterations, request.max_iterations))
        ):
            critique = await self._critique_policy(
                request=request,
                supervisor=state.supervisor,
                problem_frame=state.problem_frame,
                trinity_bundle=trinity_bundle,
                traces=state.traces,
                iteration=iteration,
            )
            scorecard = await self._evaluate_iteration(
                supervisor=state.supervisor,
                evaluator=state.evaluator,
                objective=state.problem_frame.problem_statement,
                draft=draft,
                critique=critique,
                traces=state.traces,
                iteration=iteration,
                reflexion=state.reflexion,
            )
            should_stop, stop_reason = state.reflexion.should_stop_optimization(scorecard)
            state.traces.setdefault("reflexion", []).append(
                {
                    "iteration": iteration + 1,
                    "scorecard": scorecard.model_dump(mode="json"),
                    "verdict": critique.verdict,
                    "stop_reason": stop_reason,
                }
            )
            if (
                critique.verdict == "APPROVE"
                or should_stop
                or iteration + 1 >= request.max_iterations
            ):
                state.metrics["final_score"] = scorecard.overall_score
                break

            prior_drafts.append(draft)
            refinement_hints = [critique.reflexion_hint] if critique.reflexion_hint else []
            if scorecard.retry_advice:
                refinement_hints.append(scorecard.retry_advice)
            draft = await self._draft_policy(
                request=request,
                supervisor=state.supervisor,
                problem_frame=state.problem_frame,
                data_context=state.data_context,
                hint_lines=refinement_hints,
                traces=state.traces,
                prior_drafts=prior_drafts,
                iteration=iteration + 1,
            )
            trinity_bundle = await request.formalizer.formalize(draft)

        if critique is None:
            critique = await self._critique_policy(
                request=request,
                supervisor=state.supervisor,
                problem_frame=state.problem_frame,
                trinity_bundle=trinity_bundle,
                traces=state.traces,
                iteration=0,
            )
        return draft, trinity_bundle, critique, scorecard

    def _persist_reflexion_memory(
        self,
        *,
        request: ScientistAgentFabricRequest,
        state: _FabricRunState,
        critique: Any,
        scorecard: ReflexionScorecard | None,
    ) -> None:
        if not self._config.reflexion_enabled or scorecard is None:
            return
        state.memory_store.store_reflexion_memory(
            problem_statement=state.problem_frame.problem_statement,
            reflection=scorecard.retry_advice or "fabric evaluation complete",
            trajectory_summary=(
                f"verdict={critique.verdict}; "
                f"issues={len(critique.issues)}; "
                f"score={scorecard.overall_score:.3f}"
            ),
            source_run_id=request.run_id,
            tool_error_patterns=scorecard.tool_error_patterns,
            confidence=max(0.1, min(1.0, scorecard.overall_score)),
        )
        memory_ref = state.memory_store.save_index()
        _write_memory_index_ref(
            self._config.memory_index_path,
            str(memory_ref.artifact_id),
        )
        state.traces["memory_index_ref"] = str(memory_ref.artifact_id)

    def _build_memory_store(self, artifact_store: ArtifactStore) -> PersistentMemoryStore:
        store = PersistentMemoryStore(artifact_store)
        ref_text = _read_memory_index_ref(self._config.memory_index_path)
        if ref_text:
            try:
                store.load_index(
                    ArtifactRef(
                        artifact_id=ArtifactID.model_validate(ref_text),
                        kind="scientist.memory_index",
                        media_type="application/json",
                    )
                )
            except Exception:
                pass
        return store

    def _make_supervisor(self, handlers: dict[str, Any]) -> ScientistSupervisorAgent:
        return ScientistSupervisorAgent(
            build_worker_tool_registry(handlers),
            config=self._supervisor_config(),
        )

    async def _draft_policy(
        self,
        *,
        request: ScientistAgentFabricRequest,
        supervisor: ScientistSupervisorAgent | None,
        problem_frame: ProblemFrame,
        data_context: dict[str, Any],
        hint_lines: list[str],
        traces: dict[str, Any],
        prior_drafts: list[DraftResult] | None = None,
        iteration: int = 0,
    ) -> DraftResult:
        if supervisor is None:
            return await request.drafter.draft_policy(
                problem_frame,
                data_context=data_context or None,
                hints=hint_lines or None,
                prior_drafts=prior_drafts or None,
            )

        local_supervisor = self._make_supervisor(
            {
                "drafter_worker": build_drafter_worker_handler(
                    request.drafter,
                    problem_frame=problem_frame,
                    data_context=data_context,
                    prior_drafts=prior_drafts or [],
                )
            }
        )
        envelope = build_sectioned_worker_envelopes(
            worker_name="drafter_worker",
            objective=problem_frame.problem_statement,
            sections={"draft": problem_frame.problem_statement},
            shared_constraints=hint_lines,
            expected_output_schema={"type": "object", "required": ["draft"]},
            source_policy=WorkerSourcePolicy(
                require_citations=bool(problem_frame.context.get("web_evidence")),
                require_snippets=False,
                min_citations=1 if problem_frame.context.get("web_evidence") else 0,
            ),
            budget_hints=WorkerBudgetHints(
                max_cost_usd=Decimal("0.003"),
                timeout_s=45.0,
                model_id=request.model_name,
            ),
            shared_input_payload={"hints": hint_lines},
        )[0]
        result = await local_supervisor.run(
            [envelope],
            objective=problem_frame.problem_statement,
            mode=SupervisorSynthesisMode.SELF_MOA,
            run_id=f"{request.run_id}.{request.variant_id}.draft.{iteration + 1}",
            self_moa_replicas=self._config.drafter_self_moa_replicas,
        )
        traces.setdefault("supervisor", {})["drafting"] = result.model_dump(mode="json")
        for worker_result in result.worker_results:
            payload = worker_result.output_data.get("draft")
            if worker_result.success and isinstance(payload, dict):
                return draft_from_payload(payload)
        return await request.drafter.draft_policy(
            problem_frame,
            data_context=data_context or None,
            hints=hint_lines or None,
            prior_drafts=prior_drafts or None,
        )

    async def _critique_policy(
        self,
        *,
        request: ScientistAgentFabricRequest,
        supervisor: ScientistSupervisorAgent | None,
        problem_frame: ProblemFrame,
        trinity_bundle: TrinityBundle,
        traces: dict[str, Any],
        iteration: int,
    ) -> Any:
        if supervisor is None:
            return await request.critic.critique(trinity_bundle, problem_frame)

        local_supervisor = self._make_supervisor(
            {
                "critic_worker": build_critic_worker_handler(
                    request.critic,
                    problem_frame=problem_frame,
                    trinity_bundle=trinity_bundle,
                )
            }
        )
        envelopes = [
            build_sectioned_worker_envelopes(
                worker_name="critic_worker",
                objective=problem_frame.problem_statement,
                sections={f"critique_{index + 1}": problem_frame.problem_statement},
                expected_output_schema={"type": "object", "required": ["critique", "verdict"]},
                source_policy=WorkerSourcePolicy(),
                budget_hints=WorkerBudgetHints(
                    max_cost_usd=Decimal("0.002"),
                    timeout_s=45.0,
                    model_id=request.model_name,
                ),
                shared_input_payload={"depth": "standard"},
            )[0].model_copy(
                update={
                    "task_id": f"critic_worker_vote_{index + 1}",
                    "vote_group_id": "critic_vote",
                }
            )
            for index in range(self._config.critic_vote_workers)
        ]
        result = await local_supervisor.run(
            envelopes,
            objective=problem_frame.problem_statement,
            mode=SupervisorSynthesisMode.VOTING,
            run_id=f"{request.run_id}.{request.variant_id}.critique.{iteration + 1}",
        )
        traces.setdefault("supervisor", {})["critique"] = result.model_dump(mode="json")
        winner_ids = set(result.winner_task_ids)
        ordered_results = [
            item
            for item in result.worker_results
            if item.success and (not winner_ids or item.task_id in winner_ids)
        ]
        for worker_result in ordered_results:
            payload = worker_result.output_data.get("critique")
            if isinstance(payload, dict):
                return critique_from_payload(payload)
        return await request.critic.critique(trinity_bundle, problem_frame)

    async def _evaluate_iteration(
        self,
        *,
        supervisor: ScientistSupervisorAgent | None,
        evaluator: RubricReflexionEvaluator,
        objective: str,
        draft: DraftResult,
        critique: Any,
        traces: dict[str, Any],
        iteration: int,
        reflexion: ReflexionOrchestrator,
    ) -> ReflexionScorecard:
        payload = {
            "objective": objective,
            "output_text": draft.narrative,
            "output_data": {
                "claim_supports": list(draft.claim_supports),
                "citations": list(draft.citations),
                "verdict": critique.verdict,
                "issues": [issue.message for issue in critique.issues],
            },
            "citations": list(draft.citations),
        }
        if supervisor is None:
            return reflexion.evaluate_candidate(
                objective=objective,
                output_text=draft.narrative,
                output_data=payload["output_data"],
                citations=list(draft.citations),
            )

        worker_result = await supervisor.delegate_worker(
            build_sectioned_worker_envelopes(
                worker_name="reflexion_evaluator_worker",
                objective=objective,
                sections={"evaluation": objective},
                expected_output_schema={"type": "object", "required": ["scorecard"]},
                source_policy=WorkerSourcePolicy(),
                budget_hints=WorkerBudgetHints(max_cost_usd=Decimal("0.001")),
                shared_input_payload=payload,
            )[0].model_copy(update={"task_id": f"reflexion_eval_{iteration + 1}"}),
        )
        traces.setdefault("supervisor", {})["evaluation"] = traces.setdefault("supervisor", {}).get(
            "evaluation",
            [],
        ) + [worker_result.model_dump(mode="json")]
        score_payload = worker_result.output_data.get("scorecard")
        if isinstance(score_payload, dict):
            return ReflexionScorecard.model_validate(score_payload)
        return evaluator.evaluate_candidate(
            objective=objective,
            output_text=draft.narrative,
            output_data=payload["output_data"],
            citations=list(draft.citations),
        )

    def _supervisor_config(self) -> ScientistSupervisorConfig:
        return ScientistSupervisorConfig(
            max_total_workers=self._config.max_swarm_workers,
            max_parallel_workers=self._config.max_parallel_workers,
            max_total_budget_usd=self._config.max_swarm_budget_usd,
            default_worker_budget_usd=Decimal("0.003"),
        )


def _default_search_service(artifact_store: ArtifactStore) -> ScholarDeepSearchService:
    if hasattr(artifact_store, "get_bytes") and hasattr(artifact_store, "put_json"):
        return ScholarDeepSearchService(cas=artifact_store)
    return ScholarDeepSearchService()


def _with_problem_context(problem_frame: ProblemFrame, **updates: Any) -> ProblemFrame:
    merged_context = dict(problem_frame.context)
    merged_context.update({key: value for key, value in updates.items() if value})
    return ProblemFrame(
        frame_id=problem_frame.frame_id,
        domain=problem_frame.domain,
        problem_statement=problem_frame.problem_statement,
        actors=problem_frame.actors,
        goals=problem_frame.goals,
        constraints=problem_frame.constraints,
        success_criteria=problem_frame.success_criteria,
        assumptions=problem_frame.assumptions,
        context=merged_context,
        created_at=problem_frame.created_at,
    )


def _build_research_sections(
    problem_frame: ProblemFrame,
    bundle: WebEvidenceBundle,
) -> dict[str, str]:
    perspectives = list(bundle.brief.perspectives or [])
    if not perspectives:
        perspectives = [
            "policy impact evidence",
            "implementation risks",
            "counterarguments and uncertainty",
        ]
    return {
        f"facet_{index + 1}": f"{problem_frame.problem_statement} :: {perspective}"
        for index, perspective in enumerate(perspectives[:4])
    }


def _grounding_contract(draft: DraftResult) -> dict[str, Any]:
    claim_links: list[dict[str, Any]] = []
    citations_by_source_id = {
        str(item.get("source_id") or ""): dict(item)
        for item in draft.citations
        if isinstance(item, dict)
    }
    for support in draft.claim_supports:
        if not isinstance(support, dict):
            continue
        source_ids = [
            str(source_id)
            for source_id in support.get("source_ids") or []
            if isinstance(source_id, str) and source_id.strip()
        ]
        support_score = float(support.get("support_score") or 0.0)
        conflict_score = float(support.get("conflict_score") or 0.0)
        support_state = "insufficient"
        if conflict_score >= 0.35:
            support_state = "conflict"
        elif support_score > 0:
            support_state = "supported"
        claim_links.append(
            {
                "claim_id": str(support.get("claim_id") or ""),
                "claim_text": str(support.get("claim_text") or ""),
                "source_ids": source_ids,
                "source_urls": [
                    str(citations_by_source_id.get(source_id, {}).get("url") or "")
                    for source_id in source_ids
                ],
                "snippet_span": {
                    "snippet_ids": list(support.get("snippet_ids") or []),
                },
                "support_state": support_state,
                "uncertainty_note": str(support.get("uncertainty_note") or ""),
            }
        )
    return {
        "citations": list(draft.citations),
        "claim_links": claim_links,
        "grounding_notes": list(draft.grounding_notes),
    }


def _citation_coverage(draft: DraftResult) -> float:
    supports = [item for item in draft.claim_supports if isinstance(item, dict)]
    if not supports:
        return 0.0
    covered = sum(1 for item in supports if item.get("source_ids") or item.get("snippet_ids"))
    return covered / len(supports)


def _tool_calling_allowed(model_name: str | None) -> bool:
    if not model_name:
        return False
    lowered = model_name.lower()
    if "qwen" in lowered:
        return (
            _as_bool(
                os.getenv("POLISYOS_QWEN_GONKA_TOOL_CALLING_EMERGENCY_OVERRIDE"),
                default=False,
            )
            or _as_bool(
                os.getenv("POLISYOS_QWEN_GONKA_TOOL_CALLING_VERIFIED"),
                default=False,
            )
            or is_provider_capability_verified(
                provider="gonka",
                model_id=model_name,
                capability="tool_calling",
            )
        )
    return True


def _read_memory_index_ref(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return value or None


def _write_memory_index_ref(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip(), encoding="utf-8")
