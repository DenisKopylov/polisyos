"""Exercise full candidate-to-smoke signature binding through actual admission."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.runtime.quality.workspace.workflow_playbook_projection import admit_playbook_step
from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
    _ProducingNode,
    _node,
    _station,
)
from tests.unit.runtime.quality.test_workspace_workflow_playbook_projection import (
    _admission_candidate,
)


class ChangedSpecNode:
    def __init__(self):
        self.original = _node().spec
        self.changed = self.original.model_copy(
            update={"state_writes": [*self.original.state_writes, "params.after_discovery"]}
        )
        self.armed = False
        self.reads = 0

    @property
    def spec(self):
        if self.armed:
            self.reads += 1
        return self.changed if self.armed and self.reads >= 3 else self.original

    def execute(self, ctx, state):
        outcome = _ProducingNode(self.changed).execute(ctx, state)
        outcome.state.params["after_discovery"] = "changed signature executed"
        return outcome


def main():
    with TemporaryDirectory(prefix="spec-review-", dir="_build/gy-gaps/c1") as temp:
        node = ChangedSpecNode()
        candidate, registry = _admission_candidate(node)
        node.armed = True
        ctx, state = _station(Path(temp))
        admission = admit_playbook_step(
            candidate,
            node_registry=registry,
            ctx=ctx,
            state=state,
            workspace_id="ws-c1-spec-review",
            invocation_id="invoke-c1-spec-review",
            cycle_index=1,
        )
        result = {
            "candidate_spec_hash": candidate.node_spec_hash,
            "smoked_spec_hash": admission.conformance.node_spec_hash,
            "same_spec_hash": candidate.node_spec_hash == admission.conformance.node_spec_hash,
            "same_contract_hash": candidate.adapter_contract_hash == admission.conformance.contract_hash,
            "admitted": admission.step is not None,
            "passed": admission.conformance.passed,
            "failures": admission.conformance.failures,
            "smoke_calls": ctx.calls,
            "spec_reads_after_candidate": node.reads,
            "real_conformance_ref": str(admission.conformance_ref.artifact_id)
            if admission.conformance_ref is not None else None,
        }
        print(json.dumps(result, sort_keys=True))
        assert admission.step is None, "changed_full_signature_admitted"


if __name__ == "__main__":
    main()
