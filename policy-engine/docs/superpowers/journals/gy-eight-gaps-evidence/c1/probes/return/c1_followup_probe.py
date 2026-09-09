"""Unrun C1 route witness; execute only after the parent releases runtime work.

This changes only a request hint supported by the real DesignProblem projection.
The default playbook, actual registry, input owner and admission stay unmodified.
"""

# ruff: noqa: S101, S102, T201 -- disposable assertions and complete witness output

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def _canonical_factory(source: Path, design_problem: type) -> Callable[..., object]:
    tree = ast.parse(source.read_text())
    owners = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_live_proof_payloads"
    ]
    assert len(owners) == 1, "canonical_phase2_producer_identity_changed"
    factories = [
        node for node in owners[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "_design_problem"
    ]
    assert len(factories) == 1, "canonical_phase2_request_factory_identity_changed"
    namespace = {"DesignProblem": design_problem}
    exec(compile(ast.Module(body=factories, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["_design_problem"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("unchanged", "compatible"), required=True)
    arguments = parser.parse_args()

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.data_forge_binding import verify_recorded_panel_method_input
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.workspace import loop as loop_owner
    from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
        build_workflow_playbook_registry,
        select_playbook_for_intent,
    )
    from tools.quality.validation import check_layer3_gy_phase2_artifacts as proof_owner

    root = Path(__file__).resolve().parents[2]
    source = root / "tools/quality/validation/check_layer3_gy_phase2_artifacts.py"
    factory = _canonical_factory(source, DesignProblem)
    problem = factory(verification_required=True)
    # This is the existing recorded-panel owner's explicit case method, not a
    # new best-method/scientific-admissibility claim or a vocabulary filter.
    requested_method = "causal.inference.synthetic_control@1.0.0"
    if arguments.mode == "compatible":
        payload = problem.model_dump(mode="json")
        payload["runtime_hints"]["causal_method_fqn"] = requested_method
        problem = DesignProblem.model_validate(payload)
    assert "observational_data_ref" not in problem.runtime_hints

    vocabulary = proof_owner.recompute_foundry_binding_vocabulary()
    rows = vocabulary["methods"]
    assert not vocabulary["bootstrap_errors"]
    assert not vocabulary["discovery_errors"]
    assert not any(row["errors"] for row in rows), "method_vocabulary_unreadable"
    matching = [row for row in rows if row["method_fqn"] == requested_method]
    assert len(matching) == 1
    assert matching[0]["recorded_panel_compatible"] is True
    method_identities = sorted((row["method_fqn"], row["signature_digest"]) for row in rows)
    print(json.dumps({
        "measurement": "complete_current_registry_input_classification",
        "denominator": vocabulary["denominator"],
        "support_states": vocabulary["support_states"],
        "identity_set_sha256": hashlib.sha256(json.dumps(method_identities).encode()).hexdigest(),
        "requested_case_method": matching[0],
        "scientific_accuracy_or_causal_identification_claim": None,
    }, sort_keys=True), flush=True)

    scratch_parent = root / "_build/gy-gaps/c1-followup"
    scratch_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="route-cas-", dir=scratch_parent) as directory:
        store = FileSystemCAS(Path(directory))
        bindings = []
        selections = []
        original_binding = loop_owner.produce_recorded_panel_method_input
        original_selection = loop_owner._phase2_value_method_selection

        def observe_binding(**kwargs: object) -> object:
            binding = original_binding(**kwargs)
            bindings.append(binding)
            return binding

        def observe_selection(*args: object, **kwargs: object) -> dict[str, object]:
            selection = original_selection(*args, **kwargs)
            selections.append(selection)
            return selection

        loop_owner.produce_recorded_panel_method_input = observe_binding
        loop_owner._phase2_value_method_selection = observe_selection
        try:
            stable = loop_owner.WorkspaceLoop(artifact_store=store).run_intent(problem)
        except Exception as exc:
            print(json.dumps({
                "mode": arguments.mode,
                "request": problem.model_dump(mode="json"),
                "actual_owner_selection_receipts": selections,
                "actual_binding_receipts": [
                    binding.receipt.model_dump(mode="json") for binding in bindings
                ],
                "run_error": {"type": type(exc).__name__, "message": str(exc)},
                "terminal": {"presence": "not_returned"},
                "adapter_admissions": {"presence": "not_returned"},
            }, sort_keys=True), flush=True)
            raise
        finally:
            loop_owner.produce_recorded_panel_method_input = original_binding
            loop_owner._phase2_value_method_selection = original_selection

        print(json.dumps({
            "mode": arguments.mode,
            "request": problem.model_dump(mode="json"),
            "actual_owner_selection_receipts": selections,
            "actual_binding_receipts": [
                binding.receipt.model_dump(mode="json") for binding in bindings
            ],
            "terminal": stable.terminal_state.model_dump(mode="json"),
            "trace": stable.phase2_playbook_trace.model_dump(mode="json"),
            "adapter_admissions": [
                item.model_dump(mode="json") for item in stable.adapter_admissions
            ],
            "method_output_consumption_record": (
                stable.method_output_consumption_record.model_dump(mode="json")
                if stable.method_output_consumption_record is not None else None
            ),
            "authority_boundary": (
                stable.authority_boundary.model_dump(mode="json")
                if stable.authority_boundary is not None else None
            ),
        }, sort_keys=True), flush=True)
        # The unchanged request is the original red witness. A successful exit
        # here requires actual admission evidence, never merely a typed terminal.
        assert stable.adapter_admissions, "c1_default_trajectory_never_reached_admission"
        assert bindings, "c1_recorded_owner_binding_was_not_produced"
        for binding in bindings:
            resolved = verify_recorded_panel_method_input(
                store=store, binding_receipt_ref=binding.binding_receipt_ref,
            )
            assert resolved == binding, "c1_recorded_owner_binding_readback_drift"
        deviation = loop_owner.WorkspaceLoop(artifact_store=store).run_intent(
            factory(force_counterexample="missing_bounds"),
        )
        packet = proof_owner.build_playbook_admission_proof(
            root, stable=stable, deviation=deviation,
            selected=select_playbook_for_intent(problem.to_workspace_intent()),
            registry=build_workflow_playbook_registry(), store=store,
        )
        print(json.dumps({"current_c1_packet": packet}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
