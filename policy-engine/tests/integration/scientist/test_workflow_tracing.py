"""Integration test for end-to-end workflow tracing."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.scientist import run_experiment

pytestmark = pytest.mark.integration

if os.getenv("POLISYOS_RUN_INTEGRATION") != "1":
    pytest.skip(
        "Set POLISYOS_RUN_INTEGRATION=1 to run integration tracing", allow_module_level=True
    )


def _put_data_snapshot(
    store: FileSystemCAS,
    state_snapshot_ref: StateSnapshotRef,
) -> DataSnapshotRef:
    snapshot = DataSnapshot(data_ref=state_snapshot_ref)
    ref = store.put_json(
        snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    return DataSnapshotRef(artifact_id=ref.artifact_id)


def test_full_workflow_trace_consistency(in_memory_exporter, monkeypatch, tmp_path):
    store = FileSystemCAS(tmp_path)
    monkeypatch.setattr("polisyos.scientist.orchestration.workflows.builder.DEFAULT_CAS_ROOT", tmp_path)

    registry_bundle = build_default_registry_bundle(store)
    base_state = GlobalState.empty(n_agents=5, n_firms=2)
    snapshot_ref_payload = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref_payload.artifact_id)
    data_snapshot_ref = _put_data_snapshot(store, state_snapshot_ref)

    trinity_bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_trace", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_trace",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_trace",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        ),
    )
    trinity_ref = store.put_json(
        trinity_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle",
                version=trinity_bundle.schema_version,
            ),
        ),
    )

    initial_state = {
        "run_id": "R_integration_test",
        "inputs": {
            "trinity_bundle_ref": trinity_ref.model_dump(mode="json"),
            "registry_bundle_ref": registry_bundle.bundle_ref.model_dump(mode="json"),
            "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
        },
        "params": {
            "user_request": "Create a policy to increase GDP by 5%",
        },
        "budgets": {
            "max_llm_calls": 10,
            "max_sim_runs": 1,
            "max_wall_time_s": 60,
        },
    }

    final_state = run_experiment(initial_state)

    spans = in_memory_exporter.get_finished_spans()
    workflow_spans = [
        span for span in spans if span.attributes.get("polisyos.run_id") == "R_integration_test"
    ]
    trace_ids = {span.context.trace_id for span in workflow_spans}
    assert len(trace_ids) == 1, "All spans must share same trace_id"

    phases = {
        s.attributes.get("polisyos.phase") for s in spans if s.attributes.get("polisyos.phase")
    }
    expected_phases = {"FRAME", "DRAFT", "VALIDATE", "EXECUTE", "DECIDE"}
    assert phases & expected_phases

    run_ids = {
        s.attributes.get("polisyos.run_id") for s in spans if s.attributes.get("polisyos.run_id")
    }
    assert run_ids == {"R_integration_test"}
