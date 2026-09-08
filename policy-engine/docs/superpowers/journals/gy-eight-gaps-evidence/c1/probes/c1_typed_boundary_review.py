"""C1 actual owner probe: deleting a ref discriminator must not erase its type."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
    _step_from_invocation,
    admit_playbook_step,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
    _FakeNode,
    _ProducingNode,
    _node,
    _station,
)


def main() -> int:
    results = []
    for side in ("input", "output"):
        for value_kind in ("identity_removed", "scalar"):
            with tempfile.TemporaryDirectory(prefix="c1-type-review-") as temporary:
                ctx, state = _station(Path(temporary))
                if value_kind == "identity_removed":
                    value = {"kind": "ir.causal_report", "media_type": "application/json"}
                else:
                    value = "causal_report_ref"

                class InvalidOutputNode(_FakeNode):
                    def execute(self, ctx, state):
                        ctx.calls.append("execute")
                        state.artifacts_index["causal_report_ref"] = value
                        return NodeOutcome(status="ok", state=state)

                node = (
                    InvalidOutputNode(_node().spec)
                    if side == "output"
                    else _ProducingNode(_node().spec)
                )
                if side == "input":
                    state.observational_data_ref = value
                registry = SimpleNamespace(get=lambda node_id: node)
                candidate = _step_from_invocation(
                    workflow_id="c1-typed-boundary-review",
                    invocation=SimpleNamespace(
                        alias="run_causal_evaluation", node_id=node.spec.metadata.component_id
                    ),
                    node_registry=registry,
                )
                admission = admit_playbook_step(
                    candidate,
                    node_registry=registry,
                    ctx=ctx,
                    state=state,
                    workspace_id="c1-type-review",
                    invocation_id=f"{side}-{value_kind}",
                    cycle_index=1,
                )
                results.append({
                    "side": side,
                    "variant": value_kind,
                    "passed": admission.conformance.passed,
                    "admitted": admission.step is not None,
                    "failures": admission.conformance.failures,
                    "node_calls": ctx.calls,
                    "input_bindings": [item.path for item in admission.conformance.input_bindings],
                    "source_output_bindings": [
                        item.path for item in admission.conformance.source_output_bindings
                    ],
                })
    print(json.dumps({"results": results}, indent=2))
    assert all(not item["admitted"] for item in results), "typed_ref_discriminator_removal_admitted"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
