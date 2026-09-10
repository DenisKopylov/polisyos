"""Remove one output admission property in memory, retaining declaration markers."""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap


def main() -> None:
    import pytest

    mode = sys.argv[1]
    if mode == "cache-custody":
        from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache

        NodeResultCache._verify_output_aware_cache_artifact = lambda *args, **kwargs: None
        print({"mode": mode, "removed_property": "actual aware-cache emission-pair readback"})
        targets = [
            "tests/unit/scientist/orchestration/engine/test_idempotency.py::test_output_aware_cache_refuses_existing_base_epoch_manifest",
            "tests/unit/scientist/orchestration/engine/test_idempotency.py::test_output_aware_cache_refuses_loading_base_epoch_entry",
            "tests/unit/scientist/orchestration/engine/test_idempotency.py::test_output_aware_cache_refuses_old_entry_even_with_current_outcome",
            "tests/unit/scientist/orchestration/engine/test_idempotency.py::test_output_aware_cache_preserves_complete_outcome",
            "tests/unit/scientist/orchestration/engine/test_idempotency.py::test_ordinary_cache_keeps_existing_schema_epoch",
        ]
    elif mode == "wire-decoder":
        from polisyos.scientist.orchestration.engine import idempotency, protocol, retry

        def base_reader(value):
            return protocol.NodeOutcome.model_validate(value)

        for owner in (protocol, idempotency, retry):
            owner.decode_node_outcome = base_reader
        print({"mode": mode, "base_decoder_restored_in": [owner.__name__ for owner in (protocol, idempotency, retry)]})
        targets = [
            "tests/unit/scientist/orchestration/engine/runner/test_serialization.py::test_output_aware_public_deserializer_preserves_complete_outcome",
            "tests/unit/scientist/orchestration/engine/test_idempotency.py::test_output_aware_cache_preserves_complete_outcome",
            "tests/unit/scientist/orchestration/engine/test_retry.py::test_output_aware_fork_retry_preserves_complete_outcome",
            "tests/unit/scientist/orchestration/engine/test_idempotency.py::test_ordinary_cache_keeps_existing_schema_epoch",
            "tests/unit/scientist/orchestration/engine/runner/test_serialization.py::test_output_aware_decoder_preserves_ordinary_wire_and_live_identity",
        ]
    elif mode == "causal-premise":
        from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
            RunCausalEvaluationNode,
        )

        RunCausalEvaluationNode.verify_output_dispositions = lambda *args, **kwargs: None
        targets = [
            "tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_causal_output_refusal_readback_checks_substance",
            "tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_causal_output_contract_uses_complete_real_method_population",
        ]
    else:
        from polisyos.runtime.quality.workspace import scientist_node_adapters as owner

        tree = ast.parse(textwrap.dedent(inspect.getsource(owner._validated_current_output_payloads)))
        changed = []

        class RemoveProperty(ast.NodeTransformer):
            def visit_Expr(self, node):
                if (
                    mode == "consulted-premise"
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "verifier"
                ):
                    changed.append("actual_owner_verifier_call")
                    return ast.copy_location(ast.Pass(), node)
                return self.generic_visit(node)

            def visit_If(self, node):
                if mode == "current-emission" and any(
                    isinstance(row, ast.Call)
                    and isinstance(row.func, ast.Attribute)
                    and isinstance(row.func.value, ast.Name)
                    and row.func.value.id == "current"
                    and row.func.attr == "get"
                    for row in ast.walk(node.test)
                ):
                    changed.append(ast.unparse(node.test))
                    # Keep the complete failure body and all markers in place.
                    node.test = ast.copy_location(ast.Constant(value=False), node.test)
                return self.generic_visit(node)

        tree = ast.fix_missing_locations(RemoveProperty().visit(tree))
        if not changed:
            raise RuntimeError("removal_property_location_missing")
        exec(compile(tree, "<c3-output-contract-removal>", "exec"), owner.__dict__)
        print({"mode": mode, "removed_property_locations": changed})
        targets = {
            "current-emission": [
                "tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_playbook_admission_does_not_reuse_prior_output_as_current_production",
                "tests/unit/runtime/quality/test_workspace_scientist_node_adapters.py::test_conformance_returns_once_executed_payload_with_real_cas_custody",
            ],
            "consulted-premise": [
                "tests/unit/runtime/quality/test_workspace_scientist_node_adapters.py::test_conditional_output_adapter_consults_actual_source_premise",
                "tests/unit/runtime/quality/test_workspace_scientist_node_adapters.py::test_conditional_output_adapter_preserves_verified_refusal_as_separate_artifact",
            ],
        }[mode]
    print({"selected_native_targets": targets}, flush=True)
    raise SystemExit(pytest.main(["-q", "-rA", "--show-capture=no", "--tb=short", *targets]))


if __name__ == "__main__":
    main()
