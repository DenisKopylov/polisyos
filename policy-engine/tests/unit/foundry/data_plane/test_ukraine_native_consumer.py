"""Synthetic Ukraine seed reaches actual Scientist bindings and native execution.

D0 uses the maintained diagnostic payload producer; D1-D3 are explicit tiny
intake fixtures. No fixture here establishes empirical observations or authority.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path

import jax.numpy as jnp
import numpy as np
import pandas as pd
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlanRef,
    ExecuteRequest,
    FoundryExecutionInputBasis,
    FoundryInputBindingsRef,
    SimulationResult,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.data_forge.domains.ukraine.builders.bindings_validation import (
    _build_synthetic_multiscale_payload,
)
from polisyos.data_forge.domains.ukraine.builders.io import _cas_put_json
from polisyos.data_forge.domains.ukraine.manifests import (
    BuildRunManifest,
    RuntimeBundleManifest,
    load_manifest,
    write_manifest,
)
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.data_plane import load_input_bindings, prepare_input_bindings
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
from polisyos.scientist.nodes.builtins.data.bind_foundry_inputs import BindFoundryInputsNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)
from tests._helpers.ukraine_foundry_intake import _ukraine_intake_manifests
from tests.unit.foundry.data_plane.test_input_bindings_preparation import (
    _assert_complete_state,
    _without_writes,
)


def _seed(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    agents = pd.DataFrame(
        {
            "agent_id": ["synthetic::1", "synthetic::2"],
            "revenue": [1200.0, 1800.0],
            "employees": [1.0, 2.0],
        }
    )
    original = agents.copy(deep=True)
    payload = _build_synthetic_multiscale_payload(agents, pd.DataFrame(), pd.DataFrame())
    pd.testing.assert_frame_equal(agents, original)
    assert set(payload) == {"agents", "firms", "cells", "household_cells"}
    payload_ref = _cas_put_json(
        store, payload, kind="fabric.synthetic_multiscale_payload", return_selected_profile=True
    )
    snapshot = DataSnapshot(
        data_ref=payload_ref,
        notes=["ukraine_part_b_d0_p0_runtime_seed", "synthetic_diagnostic_fixture"],
    )
    snapshot_ref = DataSnapshotRef.model_validate(
        _cas_put_json(
            store,
            snapshot,
            kind=DataSnapshot.ARTIFACT_KIND,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version=DataSnapshot.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[input_ref_from_artifact_ref(payload_ref, role="data_ref")],
            return_selected_profile=True,
        ).model_dump(mode="python")
    )
    runtime = RuntimeBundleManifest(
        data_snapshot_artifact_id=str(snapshot_ref.artifact_id),
        data_snapshot_ref=snapshot_ref,
        input_bindings_artifact_id=None,
        validation=[],
        metrics={"foundry_input_bindings": "consumer_required"},
    )
    root = tmp_path / "ukraine"
    paths = _ukraine_intake_manifests(
        root, data_snapshot_ref=snapshot_ref, runtime_bundle_payload=runtime.model_dump(mode="json")
    )
    registry = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="synthetic_ukraine")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    state = ExperimentState(
        run_id="synthetic_ukraine",
        inputs={INPUT_DATA_SNAPSHOT_REF: snapshot_ref, INPUT_REGISTRY_BUNDLE_REF: registry},
        params={
            "ukraine_foundry_intake": {
                "allowed_root": str(root),
                "stage_manifests": {k: str(v) for k, v in paths.items()},
            }
        },
    )
    return store, snapshot_ref, registry, paths, ctx, state


def _assert_selected_edge(store, child, parent, role: str) -> None:
    assert parent.manifest_profile_sha256 is not None
    assert input_ref_from_artifact_ref(parent, role=role) in store.get_manifest(child).inputs


def test_synthetic_seed_reaches_actual_bind_node_and_public_tax_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, snapshot_ref, registry, paths, ctx, state = _seed(tmp_path)
    runtime_path = paths["d0_p0"].parent.parent / "stages/d0_p0/runtime_bundle_manifest.json"
    runtime_bytes = runtime_path.read_bytes()
    preparation = _without_writes(
        store,
        monkeypatch,
        lambda: prepare_input_bindings(
            store, data_snapshot_ref=snapshot_ref, registry_bundle_ref=registry
        ),
    )
    np.testing.assert_array_equal(preparation.materialized_state.agents.income, [1200.0, 1800.0])
    np.testing.assert_array_equal(
        preparation.materialized_state.agents.reported_income, [1104.0, 1656.0]
    )
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="synthetic_ukraine", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="synthetic_ukraine",
            interventions=[
                {
                    "intervention_id": "diagnostic_tax",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": "==",
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.25")},
                }
            ],
        ),
        model_spec=ModelSpec(
            model_id="synthetic_ukraine",
            data_snapshot_ref=str(snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        policy,
        candidate_id="synthetic_ukraine_tax_fixture",
        metadata={"evidence_grade": "candidate", "purpose": "synthetic diagnostic fixture"},
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        inputs=[
            input_ref_from_artifact_ref(snapshot_ref, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(registry, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    policy_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            policy,
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
        ).model_dump(mode="python")
    )
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = policy_ref
    before = state.model_dump(mode="python")
    outcome = BindFoundryInputsNode().execute(ctx, state)
    assert outcome.status == "ok", outcome.error
    assert state.model_dump(mode="python") == before
    assert state.observational_data_ref is None and outcome.state.observational_data_ref is None
    bound_ref = outcome.state.inputs[INPUT_INPUT_BINDINGS_REF]
    bindings = load_input_bindings(store, bound_ref)
    assert bindings.data_snapshot_ref.model_dump(mode="python") == snapshot_ref.model_dump(
        mode="python"
    )
    assert bindings.data_snapshot_ref.manifest_profile_sha256 is not None
    _assert_selected_edge(store, bound_ref, snapshot_ref, "input.data_snapshot_ref")
    _assert_selected_edge(
        store, bindings.bound_state_snapshot_ref, snapshot_ref, "input.data_snapshot_ref"
    )
    bound = load_state_snapshot(
        FileSystemCAS(tmp_path / "cas"), snapshot_ref=bindings.bound_state_snapshot_ref
    )
    _assert_complete_state(bound, preparation.materialized_state)
    receipt_ref = outcome.state.artifacts_index["ukraine_foundry_intake_receipt_ref"]
    receipt = from_canonical_bytes(store.get_bytes(receipt_ref))
    assert receipt["data_snapshot_ref"] == snapshot_ref.model_dump(mode="json")
    assert receipt["authority_purpose"] == "producer_artifact_content_binding"
    _assert_selected_edge(store, receipt_ref, snapshot_ref, "data_snapshot")
    assert runtime_path.read_bytes() == runtime_bytes
    assert json.loads(runtime_bytes)["validation"] == []
    assert json.loads(runtime_bytes)["metrics"]["foundry_input_bindings"] == "consumer_required"
    compiled = compile_foundry(
        store,
        CompileRequest(
            policy_ref=policy_ref, registry_bundle_ref=registry, return_selected_profile=True
        ),
    )
    assert compiled.ok, compiled.notes
    report = CompileReport.model_validate(
        from_canonical_bytes(store.get_bytes(compiled.compile_report_ref))
    )
    result = execute_foundry(
        FileSystemCAS(tmp_path / "cas"),
        ExecuteRequest(
            exec_plan_ref=ExecPlanRef.model_validate(
                report.exec_plan_ref.model_dump(mode="python")
            ),
            input_bindings_ref=FoundryInputBindingsRef.model_validate(
                bound_ref.model_dump(mode="python")
            ),
            registry_bundle_ref=registry,
            welfare_bound_mode="ex_ante",
            return_selected_profile=True,
        ),
    )
    assert result.ok, result.notes
    fresh = FileSystemCAS(tmp_path / "cas")
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(fresh.get_bytes(result.simulation_result_ref))
    )
    assert simulation.execution_source_status == "single_step_basis"
    assert simulation.execution_input_basis_ref is not None
    basis = FoundryExecutionInputBasis.model_validate(
        from_canonical_bytes(fresh.get_bytes(simulation.execution_input_basis_ref))
    )
    assert basis.authority_purpose == "execution_input_identity_only"
    assert basis.data_snapshot_ref.model_dump(mode="python") == snapshot_ref.model_dump(
        mode="python"
    )
    assert basis.input_bindings_ref.model_dump(mode="python") == bound_ref.model_dump(mode="python")
    _assert_selected_edge(
        fresh,
        simulation.execution_input_basis_ref,
        snapshot_ref,
        "basis.source.actual_data_snapshot",
    )
    _assert_selected_edge(
        fresh, simulation.execution_input_basis_ref, bound_ref, "basis.source.input_bindings"
    )
    _assert_selected_edge(
        fresh,
        result.simulation_result_ref,
        simulation.execution_input_basis_ref,
        "execution_input_basis",
    )
    consumed_snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(fresh.get_bytes(basis.data_snapshot_ref))
    )
    assert consumed_snapshot.data_ref.kind == "fabric.synthetic_multiscale_payload"
    assert "synthetic_diagnostic_fixture" in consumed_snapshot.notes
    _assert_selected_edge(fresh, basis.data_snapshot_ref, consumed_snapshot.data_ref, "data_ref")
    final = load_state_snapshot(fresh, snapshot_ref=simulation.state_snapshot_ref)
    # Independent fixed arithmetic: tax is 25% of reported, not gross, income.
    expected = bound.replace(
        agents=bound.agents.replace(
            income=jnp.asarray([924.0, 1386.0], dtype=bound.agents.income.dtype)
        ),
        government_balance=bound.government_balance + 690.0,
    )
    _assert_complete_state(final, expected)
    assert not np.array_equal(np.asarray(final.agents.income), np.asarray(bound.agents.income))


@pytest.mark.parametrize("defect", ["missing_required_contract", "wrong_snapshot_profile"])
def test_synthetic_intake_refuses_incomplete_or_wrong_profile_before_binding(
    tmp_path: Path, defect: str
) -> None:
    store, _snapshot, _registry, paths, ctx, state = _seed(tmp_path)
    if defect == "missing_required_contract":
        manifest = load_manifest(paths["d3"], BuildRunManifest)
        manifest.outputs = []
        write_manifest(paths["d3"], manifest)
    else:
        runtime = json.loads(
            (
                paths["d0_p0"].parent.parent / "stages/d0_p0/runtime_bundle_manifest.json"
            ).read_bytes()
        )
        runtime["data_snapshot_ref"]["manifest_profile_sha256"] = "sha256:" + "a" * 64
        from polisyos.data_forge.domains.ukraine.models import StageId
        from tests._helpers.ukraine_foundry_intake import _write_ukraine_stage

        _write_ukraine_stage(
            paths["d0_p0"].parent.parent,
            stage_id=StageId.D0_P0,
            outputs={"runtime_bundle_manifest.json": runtime},
        )
    before = state.model_dump(mode="python")
    outcome = BindFoundryInputsNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "Failed to load verified Ukraine Foundry intake" in outcome.error.message
    assert outcome.state.model_dump(mode="python") == before
    assert INPUT_INPUT_BINDINGS_REF not in outcome.state.inputs
    assert outcome.state.observational_data_ref is None
    assert not any(
        store.get_manifest(a).kind == "foundry.input_bindings" for a in store.iter_artifact_ids()
    )
