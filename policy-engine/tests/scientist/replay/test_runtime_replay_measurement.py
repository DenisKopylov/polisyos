from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.runtime.replay import measure_replayable_audit_bundle
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    persist_replayable_audit_bundle,
)


def test_measure_replayable_audit_bundle_reports_semantic_diff(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "cand-1"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
    evaluation_ref = store.put_json(
        {"score": 1, "decision": "promote"},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="evaluation", version="1.0"),
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        ),
    )
    runtime_input_ref = store.put_json(
        {"input": "snapshot"},
        PutOptions(
            kind="scientist.runtime_input",
            media_type="application/json",
            schema=SchemaInfo(name="runtime_input", version="1.0"),
        ),
    )
    replayed_evaluation_ref = store.put_json(
        {"score": 0, "decision": "hold"},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="evaluation", version="1.0"),
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        ),
    )

    replay_bundle_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-1",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            workflow_id="policy_design",
            execution_profile="full",
            runtime_input_refs={"decision_packet": runtime_input_ref},
            runtime_params_snapshot={"workflow_id": "policy_design"},
        ),
    )

    def _fake_run_selected_workflow(*, initial_state, store):
        replay_state = SimpleNamespace(
            params={"policy_evaluation_ref": replayed_evaluation_ref},
            artifacts_index={},
            reports_index={},
        )
        return SimpleNamespace(state=replay_state)

    fake_builder = ModuleType("polisyos.scientist.workflows.builder")
    fake_builder.run_selected_workflow = _fake_run_selected_workflow
    monkeypatch.setitem(sys.modules, "polisyos.scientist.workflows.builder", fake_builder)

    measurement = measure_replayable_audit_bundle(store, replay_bundle_ref)

    assert measurement.completeness.level.value == "complete"
    assert measurement.verification_mode == "semantic_diff"
    assert measurement.passed is False
    assert measurement.overall_similarity < 1.0
    assert "semantic_diff_exceeded_tolerance" in measurement.reason_codes
    assert measurement.details["semantic_diff_summary"]["structural_match"] is False
    assert measurement.details["replay_run_id"].startswith("replay_bundle_")
