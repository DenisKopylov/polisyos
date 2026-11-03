"""Adversarial readback controls for recursive budget-stop frontiers."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleNode,
    RecursiveGenerationCyclePartialRunV2,
    RecursiveGenerationCycleRun,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.integration.runtime_quality.test_e02_recursive_budget_frontier import (
    _run_recursive_fixture,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_budget_frontier_rejects_rehashed_later_sibling_execution() -> None:
    """A valid hash cannot claim depth-first work happened beyond a real stop."""

    completed, child_refs, _request, _completed_factory = await _run_recursive_fixture(
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    )
    assert type(completed) is RecursiveGenerationCycleRun
    completed_nodes = {node.node_ref: node for node in completed.nodes}
    later_sibling = completed_nodes[child_refs[1]]
    assert isinstance(later_sibling, RecursiveCycleNode)
    assert later_sibling.cycle_run is not None

    stopped, stopped_child_refs, _request, _stopped_factory = await _run_recursive_fixture(
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))})
    )
    assert isinstance(stopped, RecursiveGenerationCyclePartialRunV2)
    assert stopped_child_refs == child_refs
    assert stopped.budget_stop_node_ref == child_refs[0]
    assert stopped.frontier_node_refs == (child_refs[1],)

    # Replace the genuinely pending second child with a valid result from the
    # same deterministic graph and remove it from the frontier. Recompute the
    # outer hash so validation must inspect the DFS stop semantics itself.
    forged = stopped.model_dump(mode="json")
    forged["nodes"] = [
        (later_sibling.model_dump(mode="json") if node["node_ref"] == child_refs[1] else node)
        for node in forged["nodes"]
    ]
    forged["frontier_node_refs"] = []
    forged.pop("content_hash")
    forged["content_hash"] = gy_content_hash(forged)

    with pytest.raises(ValidationError, match="recursive_partial_later_sibling_not_pending"):
        RecursiveGenerationCyclePartialRunV2.model_validate(forged)
