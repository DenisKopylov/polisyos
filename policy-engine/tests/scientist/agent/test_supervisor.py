from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from polisyos.scientist.agent.supervisor import (
    ScientistSupervisorAgent,
    ScientistSupervisorConfig,
    SupervisorSynthesisMode,
)
from polisyos.scientist.agent.workers import (
    WorkerBudgetHints,
    WorkerCitation,
    WorkerSourcePolicy,
    WorkerTaskEnvelope,
    WorkerTaskResult,
    build_sectioned_worker_envelopes,
    build_worker_tool_registry,
)


@pytest.mark.asyncio
async def test_supervisor_sectioning_fanout_is_bounded_and_cited() -> None:
    active_workers = 0
    max_active_workers = 0
    lock = asyncio.Lock()

    async def research_worker(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        nonlocal active_workers, max_active_workers
        async with lock:
            active_workers += 1
            max_active_workers = max(max_active_workers, active_workers)
        await asyncio.sleep(0.03)
        async with lock:
            active_workers -= 1
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            output_text=f"{task.section_id}: {task.objective}",
            output_data={"section": task.section_id},
            citations=[
                WorkerCitation(
                    url=f"https://example.org/{task.section_id}",
                    snippet=f"Evidence for {task.section_id}",
                    source_id=f"src-{task.section_id}",
                )
            ],
            confidence=0.8,
            section_id=task.section_id,
        )

    registry = build_worker_tool_registry({"research_worker": research_worker})
    supervisor = ScientistSupervisorAgent(
        registry,
        config=ScientistSupervisorConfig(
            max_parallel_workers=2,
            max_total_workers=10,
            max_total_budget_usd=Decimal("0"),
        ),
    )
    envelopes = build_sectioned_worker_envelopes(
        worker_name="research_worker",
        objective="Parent research task",
        sections={
            "macro": "Analyze macroeconomic impacts",
            "legal": "Assess legal constraints",
            "equity": "Evaluate distributional effects",
            "ops": "Estimate implementation risks",
        },
        source_policy=WorkerSourcePolicy(require_citations=True, min_citations=1),
    )

    result = await supervisor.run(
        envelopes,
        objective="Parent research task",
        mode=SupervisorSynthesisMode.SECTIONING,
        run_id="run-sectioning",
    )

    assert result.status == "ok"
    assert max_active_workers <= 2
    assert len(result.worker_results) == 4
    assert len(result.citations) == 4
    assert result.skipped_task_ids == []
    assert set(result.winner_task_ids) == {item.task_id for item in envelopes}
    assert "## legal" in result.synthesized_text
    assert "Assess legal constraints" in result.synthesized_text
    assert result.provenance


@pytest.mark.asyncio
async def test_supervisor_self_moa_picks_majority_vote() -> None:
    async def voting_worker(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        replica = task.metadata.get("self_moa_replica_index", 0)
        decision = "approve policy" if replica in {0, 2} else "reject policy"
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            output_text=decision,
            output_data={"decision": decision},
            citations=[
                WorkerCitation(
                    url="https://example.org/vote",
                    snippet=f"Evidence for {decision}",
                    source_id=f"src-{replica}",
                )
            ],
            confidence=0.7 + replica * 0.05,
            vote_group_id=task.vote_group_id,
        )

    registry = build_worker_tool_registry({"voting_worker": voting_worker})
    supervisor = ScientistSupervisorAgent(
        registry,
        config=ScientistSupervisorConfig(
            max_parallel_workers=3,
            max_total_workers=10,
            max_total_budget_usd=Decimal("0"),
            max_self_moa_replicas=3,
        ),
    )

    result = await supervisor.run(
        [
            WorkerTaskEnvelope(
                task_id="vote-task",
                worker_name="voting_worker",
                objective="Decide whether the policy is acceptable",
                source_policy=WorkerSourcePolicy(require_citations=True, min_citations=1),
            )
        ],
        objective="Decide whether the policy is acceptable",
        mode=SupervisorSynthesisMode.SELF_MOA,
        self_moa_replicas=3,
        run_id="run-self-moa",
    )

    assert result.status == "ok"
    assert result.winner_task_ids == [
        "vote-task__replica_0",
        "vote-task__replica_2",
    ]
    assert "approve policy" in result.synthesized_text
    assert result.synthesized_data["votes"][0]["vote_counts"]["approve policy"] == 2
    assert result.synthesized_data["votes"][0]["vote_counts"]["reject policy"] == 1
    assert {item["source_id"] for item in result.citations} == {"src-0", "src-2"}


@pytest.mark.asyncio
async def test_supervisor_prunes_workers_by_budget_and_worker_cap() -> None:
    async def cheap_worker(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            output_text=task.objective,
            confidence=0.5,
        )

    registry = build_worker_tool_registry({"cheap_worker": cheap_worker})
    supervisor = ScientistSupervisorAgent(
        registry,
        config=ScientistSupervisorConfig(
            max_parallel_workers=2,
            max_total_workers=2,
            max_total_budget_usd=Decimal("0.03"),
            default_worker_budget_usd=Decimal("0.02"),
        ),
    )
    envelopes = [
        WorkerTaskEnvelope(
            task_id=f"task-{index}",
            worker_name="cheap_worker",
            objective=f"task {index}",
            budget_hints=WorkerBudgetHints(max_cost_usd=Decimal("0.02")),
        )
        for index in range(3)
    ]

    result = await supervisor.run(
        envelopes,
        objective="budget capped swarm",
        mode=SupervisorSynthesisMode.SECTIONING,
        run_id="run-budget",
    )

    assert [item.task_id for item in result.worker_results] == ["task-0"]
    assert result.skipped_task_ids == ["task-1", "task-2"]
    assert result.status == "ok"
    assert result.total_cost_usd == Decimal("0")
    assert any("skipped 2 worker task(s)" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_supervisor_fail_fast_cancels_pending_workers() -> None:
    async def flaky_worker(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        if task.objective == "fail first":
            await asyncio.sleep(0.02)
            return WorkerTaskResult(
                task_id=task.task_id,
                worker_name=task.worker_name,
                success=False,
                error="boom",
                error_type="worker_failed",
            )
        await asyncio.sleep(0.2)
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            output_text="late success",
            confidence=0.2,
        )

    registry = build_worker_tool_registry({"flaky_worker": flaky_worker})
    supervisor = ScientistSupervisorAgent(
        registry,
        config=ScientistSupervisorConfig(
            max_parallel_workers=1,
            max_total_workers=10,
            max_total_budget_usd=Decimal("0"),
            semaphore_timeout_s=0.1,
            fail_fast=True,
        ),
    )
    envelopes = [
        WorkerTaskEnvelope(
            task_id="task-fail",
            worker_name="flaky_worker",
            objective="fail first",
        ),
        WorkerTaskEnvelope(
            task_id="task-slow-1",
            worker_name="flaky_worker",
            objective="slow",
        ),
        WorkerTaskEnvelope(
            task_id="task-slow-2",
            worker_name="flaky_worker",
            objective="slow",
        ),
    ]

    result = await supervisor.run(
        envelopes,
        objective="fail fast swarm",
        mode=SupervisorSynthesisMode.SECTIONING,
        run_id="run-fail-fast",
    )

    assert result.status == "fail"
    assert [item.task_id for item in result.worker_results] == ["task-fail"]
    assert result.worker_results[0].success is False
    assert result.worker_results[0].error == "boom"
    assert any("task-fail" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_supervisor_executes_worker_dependency_dag_by_tiers() -> None:
    completed: set[str] = set()

    async def dag_worker(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        if task.task_id == "child" and completed != {"root-a", "root-b"}:
            return WorkerTaskResult(
                task_id=task.task_id,
                worker_name=task.worker_name,
                success=False,
                error="child started before dependency tier completed",
                error_type="dependency_order_violation",
            )
        await asyncio.sleep(0.01)
        completed.add(task.task_id)
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            output_text=task.objective,
            confidence=0.9,
        )

    registry = build_worker_tool_registry({"dag_worker": dag_worker})
    supervisor = ScientistSupervisorAgent(
        registry,
        config=ScientistSupervisorConfig(
            max_parallel_workers=2,
            max_total_workers=10,
            max_total_budget_usd=Decimal("0"),
        ),
    )

    result = await supervisor.run(
        [
            WorkerTaskEnvelope(
                task_id="root-a",
                worker_name="dag_worker",
                objective="root A",
            ),
            WorkerTaskEnvelope(
                task_id="root-b",
                worker_name="dag_worker",
                objective="root B",
            ),
            WorkerTaskEnvelope(
                task_id="child",
                worker_name="dag_worker",
                objective="child",
                depends_on_task_ids=["root-a", "root-b"],
            ),
        ],
        objective="dependency DAG",
        mode=SupervisorSynthesisMode.SECTIONING,
        run_id="run-worker-dag",
    )

    assert result.status == "ok"
    assert [item.task_id for item in result.worker_results] == ["root-a", "root-b", "child"]
    assert completed == {"root-a", "root-b", "child"}
