"""Read-only C1 review probe through the real WorkspaceLoop consumer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
    _FakeNode,
    _node,
    _station,
)
from tests.unit.runtime.quality.test_workspace_workflow_playbook_projection import _design_problem


class NonproducingNode(_FakeNode):
    def execute(self, ctx, state):
        ctx.calls.append("execute")
        state.params["attempted_mutation"] = True
        return NodeOutcome(status="ok", state=state)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="c1-loop-review-") as temporary:
        ctx, state = _station(Path(temporary))
        state.params["data_causal_graph"] = {"nodes": ["x", "y"], "edges": [["x", "y"]]}
        original = state.model_dump(mode="json")
        node = NonproducingNode(_node().spec)
        registry = SimpleNamespace(get=lambda node_id: node)
        problem = _design_problem(causal_variables=["x", "y"])
        with (
            patch(
                "polisyos.runtime.quality.workspace.loop.build_registry_with_builtin_nodes",
                return_value=registry,
            ),
            patch.object(WorkspaceLoop, "_phase2_context", return_value=(ctx, None)),
            patch.object(WorkspaceLoop, "_phase2_state", return_value=state),
            patch(
                "polisyos.runtime.quality.workspace.workflow_playbook_projection._default_node_registry",
                return_value=registry,
            ),
            patch(
                "polisyos.runtime.quality.workspace.loop.FoundryMethodOutputConsumer.consume_from_state"
            ) as foundry,
        ):
            result = WorkspaceLoop(artifact_store=ctx.store).run_intent(problem)
        report = {
            "terminal": result.terminal_state.kind.value,
            "node_calls": ctx.calls,
            "admission_states": [
                item.step.admission_state if item.step is not None else "refused"
                for item in result.adapter_admissions
            ],
            "conformance_failures": [item.conformance.failures for item in result.adapter_admissions],
            "invocation_ids": [item.invocation_id for item in result.operation_invocations],
            "envelope_ids": [item.ref.artifact_id for item in result.artifact_envelopes],
            "ledger_ids": [item.event_id for item in result.search_ledger_events],
            "foundry_called": foundry.called,
            "caller_state_preserved": state.model_dump(mode="json") == original,
        }
        print(json.dumps(report, indent=2))
        assert ctx.calls == ["execute"]
        assert result.adapter_admissions[0].step is None
        assert "output_not_preserved:causal_report_ref" in result.adapter_admissions[0].conformance.failures
        assert not result.operation_invocations and not result.artifact_envelopes
        assert not result.search_ledger_events and not foundry.called
        assert state.model_dump(mode="json") == original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
