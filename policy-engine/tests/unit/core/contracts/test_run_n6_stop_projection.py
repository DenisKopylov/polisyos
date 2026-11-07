"""Public history preserves stop, resource stop and abstention semantics."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from polisyos.core.contracts import runtime


def _history(**changes: object) -> dict[str, object]:
    return {
        "node_ref": "problem://candidate",
        "cycle_index": 2,
        "design_problem_ref": f"sha256:{'a' * 64}",
        "selected_candidate_ref": "candidate-same",
        "selected_candidate_content_hash": f"sha256:{'b' * 64}",
        "generation_cycle_run_terminal_status": "completed",
        "terminal_kind": "frontier_stable",
        "refinement_decision": "stop",
        "search_iteration_status": "stopped",
        "grounding_status": "grounded_shadow",
        "grounding_current_valid": False,
        "value_status": "value_conditional",
        "voi_next_action": "stop",
        **changes,
    }


@pytest.mark.parametrize(
    ("terminal", "decision", "status"),
    [
        ("frontier_stable", "stop", "stopped"),
        ("grounded_partial_admissible", "stop", "stopped"),
        ("budget_exhausted", "stop", "stopped"),
        ("grounded_abstention", "abstain", "abstained"),
    ],
)
def test_history_roundtrip_preserves_each_terminal_meaning(
    terminal: str, decision: str, status: str
) -> None:
    record = runtime.RunGenericCycleSimulationN6CycleHistoryEntry.model_validate(
        _history(
            terminal_kind=terminal,
            refinement_decision=decision,
            search_iteration_status=status,
        )
    )
    fresh = runtime.RunGenericCycleSimulationN6CycleHistoryEntry.model_validate_json(
        record.model_dump_json()
    )
    assert (fresh.terminal_kind, fresh.refinement_decision, fresh.search_iteration_status) == (
        terminal,
        decision,
        status,
    )
    assert fresh.grounding_current_valid is False


@pytest.mark.parametrize(
    "changes",
    [
        {"refinement_decision": "abstain"},
        {"search_iteration_status": "abstained"},
        {"terminal_kind": "grounded_abstention"},
        {"terminal_kind": "tool_failure"},
        {"voi_next_action": "advance"},
    ],
)
def test_public_history_refuses_corrupted_stop_siblings(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        runtime.RunGenericCycleSimulationN6CycleHistoryEntry.model_validate(_history(**changes))


def test_nonterminal_refinement_and_historical_limits_remain_readable() -> None:
    record = runtime.RunGenericCycleSimulationN6CycleHistoryEntry.model_validate(
        _history(
            terminal_kind="grounded_partial_admissible",
            voi_next_action="advance",
            refinement_decision="refine",
            search_iteration_status="refined_shadow",
        )
    )
    assert record.value_status == "value_conditional"
    assert record.grounding_current_valid is False


def test_shared_stop_projection_requires_the_complete_named_terminal_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert set(runtime.N6_TERMINAL_STOP_PROJECTIONS) == set(
        get_args(runtime.RunN6CycleSearchTerminalKind)
    )
    removed = dict(runtime.N6_TERMINAL_STOP_PROJECTIONS)
    removed.pop("grounded_abstention")
    monkeypatch.setattr(runtime, "N6_TERMINAL_STOP_PROJECTIONS", removed)
    with pytest.raises(ValueError, match="n6_stop_terminal_projection_denominator_mismatch"):
        runtime.n6_stop_projection_decision("frontier_stable")
