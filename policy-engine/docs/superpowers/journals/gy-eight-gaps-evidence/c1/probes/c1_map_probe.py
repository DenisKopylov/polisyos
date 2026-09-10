"""Observe the existing canonical C1 run without changing tracked source."""

import ast
import json
import shutil
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
from polisyos.runtime.quality.workspace import scientist_node_adapters as adapters

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/quality/validation/check_layer3_gy_phase2_artifacts.py"
tree = ast.parse(SOURCE.read_text())
builder = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build_live_proof_payloads")
factory = next(node for node in builder.body if isinstance(node, ast.FunctionDef) and node.name == "_design_problem")
namespace = {"DesignProblem": DesignProblem, "Any": object}
exec(compile(ast.Module(body=[factory], type_ignores=[]), str(SOURCE), "exec"), namespace)
problem = namespace["_design_problem"](verification_required=True)
scratch = ROOT / "_build/gy-gaps/c1/canonical-probe-cas"
observed = []
original = adapters.ScientistNodeAdapter.execute_candidate


def observe(self, **kwargs):
    execution = original(self, **kwargs)
    declared = list(self.node.spec.produces)
    serialized_declared = self.node.spec.model_dump(mode="json")["produces"]
    if declared != serialized_declared or declared != self.produced_outputs:
        raise AssertionError("declared output denominator mismatch")
    outputs = {key: adapters._output_payload(execution.outcome, key) for key in declared}
    observed.append({
        "node_id": self.node_id,
        "legacy_alias": self.legacy_alias,
        "declared_output_identity_set": sorted(declared),
        "declared_identity_crosscheck": "NodeSpec.produces == NodeSpec.model_dump.produces == adapter.produced_outputs",
        "invocation_status": execution.invocation.status,
        "outcome_status": getattr(execution.outcome, "status", None),
        "blocker": execution.blocker.model_dump(mode="json") if execution.blocker else None,
        "output_presence": {
            key: {
                "state_value_is_null": value["state_value"] is None,
                "artifacts_index_value_is_null": value["artifacts_index_value"] is None,
            }
            for key, value in outputs.items()
        },
    })
    return execution


adapters.ScientistNodeAdapter.execute_candidate = observe
try:
    result = WorkspaceLoop(artifact_store=FileSystemCAS(scratch)).run_intent(problem)
    print(json.dumps({
        "canonical_request_owner": str(SOURCE.relative_to(ROOT)),
        "canonical_factory": "build_live_proof_payloads._design_problem(verification_required=True)",
        "terminal": result.terminal_state.kind.value,
        "trace": result.phase2_playbook_trace.model_dump(mode="json") if result.phase2_playbook_trace else None,
        "observed_adapter_executions": observed,
    }, indent=2, sort_keys=True))
finally:
    adapters.ScientistNodeAdapter.execute_candidate = original
    if scratch.exists():
        shutil.rmtree(scratch)
