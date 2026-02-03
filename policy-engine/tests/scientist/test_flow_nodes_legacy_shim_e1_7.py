from __future__ import annotations

from decimal import Decimal
import warnings

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator
from polisyos.scientist.orchestrator.flow_nodes import compile_model_node, run_sim_node


def _put_data_snapshot(store: FileSystemCAS, state_snapshot_ref: StateSnapshotRef) -> DataSnapshotRef:
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


def test_flow_nodes_legacy_shim_e1_7(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store)

    base_state = GlobalState.empty(n_agents=4, n_firms=1)
    snapshot_ref_payload = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref_payload.artifact_id)
    data_snapshot_ref = _put_data_snapshot(store, state_snapshot_ref)

    problem_frame = ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL)
    policy_spec = PolicySpec(
        policy_id="policy_1",
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
                params={"rate": Decimal("0.05")},
            )
        ],
    )
    model_spec = ModelSpec(
        model_id="model_1",
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
        registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
    )
    trinity_bundle = TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )

    trinity_ref_payload = store.put_json(
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

    legacy_state = {
        "run_id": "R_legacy",
        "cas_root": str(tmp_path),
        "registry_bundle_ref": registry_bundle.bundle_ref.model_dump(),
        "trinity_bundle_ref": trinity_ref_payload.model_dump(),
        "data_snapshot_ref": data_snapshot_ref.model_dump(),
    }

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always", DeprecationWarning)
        compiled = compile_model_node(legacy_state)
        _ = compile_model_node(compiled)
        warns = [w for w in recorded if issubclass(w.category, DeprecationWarning)]
        assert len(warns) == 1

    assert compiled.get("exec_plan_ref") is not None

    simulated = run_sim_node(compiled)
    assert simulated.get("simulation_result_ref") is not None or simulated.get("simulation_results_ref") is not None
