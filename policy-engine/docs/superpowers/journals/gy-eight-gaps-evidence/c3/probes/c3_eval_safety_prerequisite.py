"""Demonstrate the actual node's missing-context refusal without issuing authority."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def main():
    with TemporaryDirectory(prefix="c3-safety-", dir="_build/gy-gaps/c3") as directory:
        store = FileSystemCAS(Path(directory))
        panel = store.put_json(
            {"outcome": [[1, 2], [2, 3]], "treatment": [1, 0], "time_treatment": 1,
             "metadata": {"probe_material": True, "not_measurement_authority": True}},
            PutOptions(kind="ir.observational_data", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        refs = {
            name: store.put_json(
                {"probe_material": True, "port": name, "not_an_authority_attestation": True},
                PutOptions(kind="gy.probe_document", media_type="application/json"),
            )
            for name in (
                "ukraine_foundry_method_input_bundle_ref",
                "ukraine_selected_foundry_method_contract_ref",
                "ukraine_foundry_intake_receipt_ref",
            )
        }
        state = ExperimentState(
            run_id="c3-safety-prerequisite",
            observational_data_ref=panel,
            causal_method_fqn="causal.inference.synthetic_control@1.0.0",
            causal_method_params={},
            inputs={key: ref for key, ref in refs.items() if key != "ukraine_foundry_intake_receipt_ref"},
            artifacts_index={"ukraine_foundry_intake_receipt_ref": refs["ukraine_foundry_intake_receipt_ref"]},
            params={"random_seed": 1, "causal_method_fqn": "causal.inference.synthetic_control@1.0.0",
                    "causal_method_params": {}, "enable_causal_refutation": False,
                    "causal_refutation_params": {}, "enable_causal_sensitivity": False,
                    "causal_sensitivity_params": {}, "causal_validity": {}},
        )
        # RunContext is unused: the real owner refuses before attempting a method.
        ctx = ExecutionContext(store=store, run=None, logger=logging.getLogger(__name__))
        calls = []
        original = owner.run_job
        def unreachable(*args, **kwargs):
            calls.append("run_job")
            raise AssertionError("method_started_without_admission")
        owner.run_job = unreachable
        try:
            outcome = owner.RunCausalEvaluationNode().execute(ctx, state)
        finally:
            owner.run_job = original
        actual_refs = [panel, *refs.values()]
        bindings = []
        for ref in actual_refs:
            raw = store.get_bytes(ref.artifact_id)
            manifest = store.get_manifest(ref.artifact_id)
            assert str(ref.artifact_id) == "sha256:" + hashlib.sha256(raw).hexdigest()
            assert manifest.artifact_id == ref.artifact_id and manifest.kind == ref.kind
            bindings.append({"ref": ref.model_dump(mode="json"), "byte_count": len(raw)})
        print(json.dumps({
            "purpose": "pre-method missing-context refusal; probe docs are not valid institutional intake",
            "cas_bindings": bindings,
            "context": ctx.eval_safety_execution_context,
            "verifier": ctx.eval_safety_verifier,
            "outcome_status": outcome.status,
            "error": outcome.error.model_dump(mode="json") if outcome.error else None,
            "method_calls": calls,
            "produced_artifacts": [ref.model_dump(mode="json") for ref in outcome.artifacts],
            "state_identity_preserved": outcome.state is state,
        }, sort_keys=True))
        assert outcome.status == "fail"
        assert outcome.error.details["blocker_codes"] == ["polisyos.eval_safety.execution_context_missing@1.0.0"]
        assert calls == [] and outcome.artifacts == []


if __name__ == "__main__":
    main()
