"""Supervisor-worker swarm runtime with bounded fan-out and synthesis modes."""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.core.components import ComponentId
from polisyos.scientist.agent.workers import (
    WorkerExecutionMode,
    WorkerTaskEnvelope,
    WorkerTaskResult,
    build_self_moa_worker_envelopes,
)
from polisyos.scientist.engine.errors import CycleDetectedError
from polisyos.scientist.engine.topo import topo_sort_tiers
from polisyos.scientist.engine.workflow_spec import NodeInvocation
from polisyos.scientist.provenance.run_dag import RunProvenanceDAG

if TYPE_CHECKING:
    from polisyos.scientist.agent.tools.registry import ToolRegistry

logger = get_logger(__name__)
_WORKER_DAG_NODE_ID = ComponentId.parse("scientist.worker@1.0.0")

__all__ = [
    "ScientistSupervisorAgent",
    "ScientistSupervisorConfig",
    "SupervisorRunResult",
    "SupervisorSynthesisMode",
]


class SupervisorSynthesisMode(StrEnum):
    """How the supervisor should aggregate successful worker outputs."""

    SECTIONING = "sectioning"
    VOTING = "voting"
    SELF_MOA = "self_moa"


class ScientistSupervisorConfig(BaseModel):
    """Execution limits and scaling rules for one swarm run."""

    model_config = ConfigDict(extra="forbid")

    max_total_workers: int = Field(default=16, ge=1, le=256)
    max_parallel_workers: int = Field(default=4, ge=1, le=64)
    max_total_budget_usd: Decimal = Field(default=Decimal("0.05"), ge=Decimal("0"))
    default_worker_budget_usd: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    semaphore_timeout_s: float | None = Field(default=5.0, ge=0.1, le=600.0)
    fail_fast: bool = False
    max_self_moa_replicas: int = Field(default=5, ge=1, le=32)


class SupervisorRunResult(BaseModel):
    """Final supervisor outcome with synthesized text and full worker trace."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    mode: SupervisorSynthesisMode
    status: str = "ok"
    objective: str = ""
    synthesized_text: str = ""
    synthesized_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    worker_results: list[WorkerTaskResult] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    winner_task_ids: list[str] = Field(default_factory=list)
    skipped_task_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_cost_usd: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    provenance: dict[str, Any] = Field(default_factory=dict)


class ScientistSupervisorAgent:
    """Supervisor that delegates worker envelopes through `ToolRegistry` tools."""

    def __init__(
        self,
        worker_registry: ToolRegistry,
        *,
        config: ScientistSupervisorConfig | None = None,
    ) -> None:
        self._worker_registry = worker_registry
        self._config = config or ScientistSupervisorConfig()

    async def run(
        self,
        envelopes: Sequence[WorkerTaskEnvelope],
        *,
        objective: str,
        mode: SupervisorSynthesisMode = SupervisorSynthesisMode.SECTIONING,
        run_id: str | None = None,
        provenance_dag: RunProvenanceDAG | None = None,
        self_moa_replicas: int | None = None,
    ) -> SupervisorRunResult:
        """Execute worker envelopes with bounded parallelism and synthesize results."""
        active_run_id = run_id or f"swarm_{uuid.uuid4().hex[:12]}"
        dag = provenance_dag or RunProvenanceDAG(run_id=active_run_id)
        dag.set_experiment_metadata(
            problem_statement=objective,
            supervisor_mode=mode.value,
        )

        planned, skipped, warnings = self._plan_envelopes(
            envelopes,
            mode=mode,
            self_moa_replicas=self_moa_replicas,
        )
        worker_results = await self._execute_envelopes(planned, dag)
        result = self._synthesize_results(
            run_id=active_run_id,
            mode=mode,
            objective=objective,
            worker_results=worker_results,
            skipped_task_ids=skipped,
            warnings=warnings,
        )
        try:
            dag.finalize()
            result.provenance = dag.to_prov_json()
        except Exception as exc:
            logger.debug("Supervisor provenance export failed: %s", exc)
            result.warnings.append("provenance_export_failed")
        return result

    async def delegate_worker(
        self,
        envelope: WorkerTaskEnvelope,
        *,
        provenance_dag: RunProvenanceDAG | None = None,
    ) -> WorkerTaskResult:
        """Invoke a single worker tool from one `WorkerTaskEnvelope`."""
        results = await self._execute_envelopes([envelope], provenance_dag)
        if results:
            return results[0]
        return WorkerTaskResult(
            task_id=envelope.task_id,
            worker_name=envelope.worker_name,
            success=False,
            error="worker skipped before execution",
            error_type="worker_skipped",
            section_id=envelope.section_id,
            vote_group_id=envelope.vote_group_id,
        )

    def _plan_envelopes(
        self,
        envelopes: Sequence[WorkerTaskEnvelope],
        *,
        mode: SupervisorSynthesisMode,
        self_moa_replicas: int | None,
    ) -> tuple[list[WorkerTaskEnvelope], list[str], list[str]]:
        """Apply scaling and budget caps before launching workers."""
        requested = list(envelopes)
        warnings: list[str] = []
        skipped: list[str] = []

        if mode == SupervisorSynthesisMode.SELF_MOA:
            replicas = min(
                self._config.max_self_moa_replicas,
                max(1, self_moa_replicas or self._config.max_self_moa_replicas),
            )
            if self_moa_replicas is not None and self_moa_replicas > replicas:
                warnings.append(
                    f"self_moa_replicas capped at {replicas}"
                )
            expanded: list[WorkerTaskEnvelope] = []
            for envelope in requested:
                expanded.extend(
                    build_self_moa_worker_envelopes(
                        envelope.model_copy(update={"mode": WorkerExecutionMode.SELF_MOA}),
                        replicas=replicas,
                    )
                )
            requested = expanded
        elif mode == SupervisorSynthesisMode.VOTING:
            requested = [
                envelope.model_copy(update={"mode": WorkerExecutionMode.VOTING})
                for envelope in requested
            ]
        else:
            requested = [
                envelope.model_copy(update={"mode": WorkerExecutionMode.SECTIONING})
                for envelope in requested
            ]

        unique_envelopes: list[WorkerTaskEnvelope] = []
        seen_task_ids: dict[str, int] = {}
        for envelope in requested:
            count = seen_task_ids.get(envelope.task_id, 0)
            seen_task_ids[envelope.task_id] = count + 1
            if count == 0:
                unique_envelopes.append(envelope)
            else:
                deduped_id = f"{envelope.task_id}__{count + 1}"
                warnings.append(
                    f"duplicate task_id '{envelope.task_id}' renamed to '{deduped_id}'"
                )
                unique_envelopes.append(envelope.model_copy(update={"task_id": deduped_id}))

        planned: list[WorkerTaskEnvelope] = []
        reserved_cost = Decimal("0")
        for envelope in unique_envelopes:
            if len(planned) >= self._config.max_total_workers:
                skipped.append(envelope.task_id)
                continue
            task_cost = (
                envelope.budget_hints.max_cost_usd
                if envelope.budget_hints.max_cost_usd is not None
                else self._config.default_worker_budget_usd
            )
            if (
                self._config.max_total_budget_usd > 0
                and task_cost is not None
                and reserved_cost + task_cost > self._config.max_total_budget_usd
            ):
                skipped.append(envelope.task_id)
                continue
            reserved_cost += task_cost or Decimal("0")
            planned.append(envelope)

        if skipped:
            warnings.append(
                f"skipped {len(skipped)} worker task(s) due to worker/budget caps"
            )
        return planned, skipped, warnings

    async def _execute_envelopes(
        self,
        envelopes: Sequence[WorkerTaskEnvelope],
        provenance_dag: RunProvenanceDAG | None,
    ) -> list[WorkerTaskResult]:
        semaphore = asyncio.Semaphore(self._config.max_parallel_workers)
        cancel_event = asyncio.Event()
        results: list[WorkerTaskResult | None] = [None] * len(envelopes)

        async def _run_one(index: int, envelope: WorkerTaskEnvelope) -> None:
            if cancel_event.is_set():
                return
            acquired = False
            started_at = datetime.now(UTC)
            if self._config.semaphore_timeout_s is None:
                await semaphore.acquire()
                acquired = True
            else:
                try:
                    await asyncio.wait_for(
                        semaphore.acquire(),
                        timeout=self._config.semaphore_timeout_s,
                    )
                    acquired = True
                except TimeoutError:
                    results[index] = WorkerTaskResult(
                        task_id=envelope.task_id,
                        worker_name=envelope.worker_name,
                        success=False,
                        section_id=envelope.section_id,
                        vote_group_id=envelope.vote_group_id,
                        error=(
                            "timeout waiting for worker semaphore "
                            f"after {self._config.semaphore_timeout_s}s"
                        ),
                        error_type="worker_semaphore_timeout",
                    )
                    _record_worker_failure(provenance_dag, envelope, results[index], started_at)
                    if self._config.fail_fast:
                        cancel_event.set()
                    return

            try:
                if cancel_event.is_set():
                    return
                if envelope.budget_hints.timeout_s is None:
                    tool_call = await self._worker_registry.aexecute(
                        envelope.worker_name,
                        {"envelope": envelope.model_dump(mode="json", exclude_none=True)},
                    )
                else:
                    tool_call = await asyncio.wait_for(
                        self._worker_registry.aexecute(
                            envelope.worker_name,
                            {"envelope": envelope.model_dump(mode="json", exclude_none=True)},
                        ),
                        timeout=envelope.budget_hints.timeout_s,
                    )
                if tool_call.error is not None:
                    result = WorkerTaskResult(
                        task_id=envelope.task_id,
                        worker_name=envelope.worker_name,
                        success=False,
                        section_id=envelope.section_id,
                        vote_group_id=envelope.vote_group_id,
                        duration_ms=tool_call.duration_ms,
                        error=tool_call.error,
                        error_type=tool_call.error_type or "tool_error",
                        metadata={
                            "tool_error_details": tool_call.error_details or {},
                            "mode": envelope.mode.value,
                        },
                    )
                    _record_worker_failure(provenance_dag, envelope, result, started_at)
                    if self._config.fail_fast:
                        cancel_event.set()
                else:
                    try:
                        result = WorkerTaskResult.model_validate(tool_call.result)
                    except Exception as exc:
                        result = WorkerTaskResult(
                            task_id=envelope.task_id,
                            worker_name=envelope.worker_name,
                            success=False,
                            section_id=envelope.section_id,
                            vote_group_id=envelope.vote_group_id,
                            duration_ms=tool_call.duration_ms,
                            error=f"invalid worker result payload: {exc}",
                            error_type="invalid_worker_result",
                        )
                        _record_worker_failure(provenance_dag, envelope, result, started_at)
                        if self._config.fail_fast:
                            cancel_event.set()
                    else:
                        if result.duration_ms <= 0:
                            result.duration_ms = tool_call.duration_ms
                        _record_worker_success(provenance_dag, envelope, result, started_at)
                        if not result.success and self._config.fail_fast:
                            cancel_event.set()
                results[index] = result
            except TimeoutError:
                result = WorkerTaskResult(
                    task_id=envelope.task_id,
                    worker_name=envelope.worker_name,
                    success=False,
                    section_id=envelope.section_id,
                    vote_group_id=envelope.vote_group_id,
                    error=f"worker timeout after {envelope.budget_hints.timeout_s}s",
                    error_type="worker_timeout",
                )
                results[index] = result
                _record_worker_failure(provenance_dag, envelope, result, started_at)
                if self._config.fail_fast:
                    cancel_event.set()
            except Exception as exc:
                result = WorkerTaskResult(
                    task_id=envelope.task_id,
                    worker_name=envelope.worker_name,
                    success=False,
                    section_id=envelope.section_id,
                    vote_group_id=envelope.vote_group_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                results[index] = result
                _record_worker_failure(provenance_dag, envelope, result, started_at)
                if self._config.fail_fast:
                    cancel_event.set()
            finally:
                if acquired:
                    semaphore.release()

        try:
            execution_tiers, missing_dependencies = _worker_execution_tiers(envelopes)
        except CycleDetectedError as exc:
            return [
                WorkerTaskResult(
                    task_id=envelope.task_id,
                    worker_name=envelope.worker_name,
                    success=False,
                    section_id=envelope.section_id,
                    vote_group_id=envelope.vote_group_id,
                    error=str(exc),
                    error_type="worker_dag_cycle",
                )
                for envelope in envelopes
            ]

        failed_or_blocked: set[str] = set()
        for tier in execution_tiers:
            if cancel_event.is_set():
                break
            runnable: list[tuple[int, WorkerTaskEnvelope]] = []
            for index in tier:
                envelope = envelopes[index]
                missing = missing_dependencies.get(index, [])
                failed_dependencies = [
                    task_id
                    for task_id in _worker_dependencies(envelope)
                    if task_id in failed_or_blocked
                ]
                if missing or failed_dependencies:
                    result = WorkerTaskResult(
                        task_id=envelope.task_id,
                        worker_name=envelope.worker_name,
                        success=False,
                        section_id=envelope.section_id,
                        vote_group_id=envelope.vote_group_id,
                        error=(
                            "worker dependency unavailable: "
                            f"missing={missing}, failed={failed_dependencies}"
                        ),
                        error_type=(
                            "worker_dependency_missing"
                            if missing
                            else "worker_dependency_failed"
                        ),
                    )
                    results[index] = result
                    failed_or_blocked.add(envelope.task_id)
                    _record_worker_failure(
                        provenance_dag,
                        envelope,
                        result,
                        datetime.now(UTC),
                    )
                    if self._config.fail_fast:
                        cancel_event.set()
                    continue
                runnable.append((index, envelope))

            async with asyncio.TaskGroup() as tg:
                for index, envelope in runnable:
                    tg.create_task(_run_one(index, envelope))

            for index in tier:
                result = results[index]
                if result is not None and not result.success:
                    failed_or_blocked.add(result.task_id)

        return [
            item for item in results
            if item is not None
        ]

    def _synthesize_results(
        self,
        *,
        run_id: str,
        mode: SupervisorSynthesisMode,
        objective: str,
        worker_results: Sequence[WorkerTaskResult],
        skipped_task_ids: Sequence[str],
        warnings: Sequence[str],
    ) -> SupervisorRunResult:
        """Aggregate worker outputs into a final cited answer."""
        successes = [result for result in worker_results if result.success]
        failures = [result for result in worker_results if not result.success]
        if mode == SupervisorSynthesisMode.SECTIONING:
            text, data, winners = _synthesize_sectioned(successes, failures)
        else:
            text, data, winners = _synthesize_votes(successes, failures)

        citations = _dedupe_citations(
            citation.model_dump(mode="json", exclude_none=True)
            for result in successes
            for citation in result.citations
            if mode == SupervisorSynthesisMode.SECTIONING or result.task_id in winners
        )
        avg_confidence = (
            sum(result.confidence for result in successes) / len(successes)
            if successes
            else 0.0
        )
        total_cost = sum((result.cost_usd for result in worker_results), Decimal("0"))
        merged_warnings = [*warnings]
        merged_warnings.extend(
            f"{result.task_id}: {result.error_type or 'worker_error'}: {result.error}"
            for result in failures
            if result.error
        )
        return SupervisorRunResult(
            run_id=run_id,
            mode=mode,
            status="ok" if successes and not failures else ("partial" if successes else "fail"),
            objective=objective,
            synthesized_text=text,
            synthesized_data=data,
            confidence=max(0.0, min(1.0, avg_confidence)),
            worker_results=list(worker_results),
            citations=citations,
            winner_task_ids=winners,
            skipped_task_ids=list(skipped_task_ids),
            warnings=merged_warnings,
            total_cost_usd=total_cost,
        )


def _synthesize_sectioned(
    successes: Sequence[WorkerTaskResult],
    failures: Sequence[WorkerTaskResult],
) -> tuple[str, dict[str, Any], list[str]]:
    """Compose section outputs while keeping section order stable."""
    sorted_results = sorted(
        successes,
        key=lambda result: (
            result.section_id or "",
            int(result.metadata.get("section_order", 0) or 0),
            result.task_id,
        ),
    )
    chunks: list[str] = []
    data_sections: list[dict[str, Any]] = []
    winners: list[str] = []
    for result in sorted_results:
        section_id = result.section_id or result.task_id
        text = result.output_text.strip()
        if text:
            chunks.append(f"## {section_id}\n{text}")
        data_sections.append(
            {
                "task_id": result.task_id,
                "section_id": result.section_id,
                "worker_name": result.worker_name,
                "output_data": result.output_data,
                "confidence": result.confidence,
            }
        )
        winners.append(result.task_id)

    if failures:
        data_sections.append(
            {
                "failed_tasks": [
                    {
                        "task_id": result.task_id,
                        "worker_name": result.worker_name,
                        "error_type": result.error_type,
                        "error": result.error,
                    }
                    for result in failures
                ]
            }
        )

    return "\n\n".join(chunks).strip(), {"sections": data_sections}, winners


def _synthesize_votes(
    successes: Sequence[WorkerTaskResult],
    failures: Sequence[WorkerTaskResult],
) -> tuple[str, dict[str, Any], list[str]]:
    """Majority-vote synthesis for voting/self-MoA modes."""
    grouped: dict[str, list[WorkerTaskResult]] = defaultdict(list)
    for result in successes:
        group_id = result.vote_group_id or "default_vote_group"
        grouped[group_id].append(result)

    winner_task_ids: list[str] = []
    group_payload: list[dict[str, Any]] = []
    text_chunks: list[str] = []
    for group_id in sorted(grouped):
        group_results = grouped[group_id]
        counter = Counter(result.normalized_vote_key for result in group_results)
        ranked_labels = sorted(
            counter,
            key=lambda label: (
                -counter[label],
                -_average_confidence(group_results, label),
                label,
            ),
        )
        winner_label = ranked_labels[0] if ranked_labels else ""
        winners = [
            result for result in group_results
            if result.normalized_vote_key == winner_label
        ]
        representative = max(
            winners,
            key=lambda result: (result.confidence, -result.duration_ms, result.task_id),
        )
        winner_task_ids.extend(result.task_id for result in winners)
        if representative.output_text.strip():
            text_chunks.append(f"## {group_id}\n{representative.output_text.strip()}")
        group_payload.append(
            {
                "vote_group_id": group_id,
                "winner_label": winner_label,
                "vote_counts": dict(counter),
                "winner_task_ids": [result.task_id for result in winners],
                "all_task_ids": [result.task_id for result in group_results],
                "output_data": representative.output_data,
                "confidence": representative.confidence,
            }
        )

    if failures:
        group_payload.append(
            {
                "failed_tasks": [
                    {
                        "task_id": result.task_id,
                        "worker_name": result.worker_name,
                        "error_type": result.error_type,
                        "error": result.error,
                    }
                    for result in failures
                ]
            }
        )
    return "\n\n".join(text_chunks).strip(), {"votes": group_payload}, winner_task_ids


def _average_confidence(results: Sequence[WorkerTaskResult], label: str) -> float:
    matching = [result.confidence for result in results if result.normalized_vote_key == label]
    if not matching:
        return 0.0
    return sum(matching) / len(matching)


def _dedupe_citations(citations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, int | None, int | None]] = set()
    merged: list[dict[str, Any]] = []
    for citation in citations:
        key = (
            str(citation.get("source_id") or ""),
            str(citation.get("url") or ""),
            str(citation.get("snippet") or ""),
            citation.get("start_char"),
            citation.get("end_char"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(citation))
    return merged


def _worker_execution_tiers(
    envelopes: Sequence[WorkerTaskEnvelope],
) -> tuple[list[list[int]], dict[int, list[str]]]:
    """Build worker execution tiers with the shared Scientist DAG topological sorter."""
    alias_by_task_id: dict[str, str] = {}
    alias_to_index: dict[str, int] = {}
    for index, envelope in enumerate(envelopes):
        alias = _worker_task_alias(envelope.task_id, index)
        alias_by_task_id[envelope.task_id] = alias
        alias_to_index[alias] = index

    missing_dependencies: dict[int, list[str]] = {}
    invocations: dict[str, NodeInvocation] = {}
    for index, envelope in enumerate(envelopes):
        dependencies = _worker_dependencies(envelope)
        missing = [task_id for task_id in dependencies if task_id not in alias_by_task_id]
        if missing:
            missing_dependencies[index] = missing
        invocations[alias_by_task_id[envelope.task_id]] = NodeInvocation(
            alias=alias_by_task_id[envelope.task_id],
            node_id=_WORKER_DAG_NODE_ID,
            depends_on=[
                alias_by_task_id[task_id]
                for task_id in dependencies
                if task_id in alias_by_task_id
            ],
        )

    return (
        [
            [alias_to_index[alias] for alias in tier]
            for tier in topo_sort_tiers(invocations)
        ],
        missing_dependencies,
    )


def _worker_dependencies(envelope: WorkerTaskEnvelope) -> list[str]:
    metadata_dependencies = (
        envelope.metadata.get("depends_on_task_ids")
        or envelope.metadata.get("depends_on")
        or []
    )
    raw_dependencies: list[str] = [*envelope.depends_on_task_ids]
    if isinstance(metadata_dependencies, str):
        raw_dependencies.append(metadata_dependencies)
    elif isinstance(metadata_dependencies, Sequence):
        raw_dependencies.extend(str(item) for item in metadata_dependencies)
    return [
        task_id
        for task_id in dict.fromkeys(item.strip() for item in raw_dependencies)
        if task_id and task_id != envelope.task_id
    ]


def _worker_task_alias(task_id: str, index: int) -> str:
    normalized = re.sub(r"[^a-z0-9_]", "_", task_id.lower()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"task_{normalized or 'worker'}"
    return f"{normalized}_{index}"


def _record_worker_success(
    provenance_dag: RunProvenanceDAG | None,
    envelope: WorkerTaskEnvelope,
    result: WorkerTaskResult,
    started_at: datetime,
) -> None:
    if provenance_dag is None:
        return
    try:
        provenance_dag.record_node_execution(
            alias=envelope.task_id,
            node_id=envelope.worker_name,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            input_refs=[
                f"worker_objective:{envelope.task_id}:{_hashish(envelope.objective)}"
            ],
            output_refs=[f"worker_result:{result.task_id}:{_hashish(result.output_text)}"],
            params={
                "mode": envelope.mode.value,
                "worker_name": envelope.worker_name,
                "section_id": envelope.section_id,
                "vote_group_id": envelope.vote_group_id,
                "budget_hints": envelope.budget_hints.model_dump(mode="json", exclude_none=True),
                "source_policy": envelope.source_policy.model_dump(mode="json", exclude_none=True),
                "success": result.success,
                "confidence": result.confidence,
                "cost_usd": str(result.cost_usd),
            },
        )
    except Exception as exc:
        logger.debug("Supervisor provenance success recording failed: %s", exc)


def _record_worker_failure(
    provenance_dag: RunProvenanceDAG | None,
    envelope: WorkerTaskEnvelope,
    result: WorkerTaskResult | None,
    started_at: datetime,
) -> None:
    if provenance_dag is None:
        return
    try:
        provenance_dag.record_node_failure(
            alias=envelope.task_id,
            node_id=envelope.worker_name,
            error=(result.error if result is not None and result.error else "worker failed"),
            started_at=started_at,
            ended_at=datetime.now(UTC),
        )
    except Exception as exc:
        logger.debug("Supervisor provenance failure recording failed: %s", exc)


def _hashish(value: str) -> str:
    """Stable short label suffix for provenance references."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
