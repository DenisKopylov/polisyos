"""Default CLI resume from a genuine, content-unavailable workflow checkpoint."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import SimulationResult, StateSnapshotRef
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.checkpoint import (
    compute_workflow_fingerprint,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.workflows.builder import run_default_workflow
from polisyos.scientist.orchestration.workflows.default import default_workflow_spec

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


def _build_income_tax_inputs(
    store: FileSystemCAS,
) -> tuple[TrinityBundleRef, ArtifactRef, DataSnapshotRef]:
    """Persist authentic income-tax inputs and return their typed CAS references."""
    import jax.numpy as jnp

    registry = build_default_registry_bundle(store)
    base_state = GlobalState.empty(n_agents=3, n_firms=1)
    initial_state = base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.asarray([100.0, 200.0, 300.0], dtype=jnp.float32),
            reported_income=jnp.asarray([100.0, 200.0, 300.0], dtype=jnp.float32),
        )
    )
    state_snapshot_artifact = put_state_snapshot(store, state=initial_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=state_snapshot_artifact.artifact_id)
    data_snapshot_artifact = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    data_snapshot_ref = DataSnapshotRef(artifact_id=data_snapshot_artifact.artifact_id)
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="rep_01_cli_tax", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="rep_01_cli_income_tax",
            interventions=[
                InterventionSpec(
                    intervention_id="rep_01_cli_tax_all",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="rep_01_cli_tax_model",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    trinity_artifact = store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
        ),
    )
    return (
        TrinityBundleRef(artifact_id=trinity_artifact.artifact_id),
        registry.bundle_ref,
        data_snapshot_ref,
    )


def _initial_experiment_state(
    *,
    run_id: str,
    trinity_ref: TrinityBundleRef,
    registry_ref: ArtifactRef,
    data_snapshot_ref: DataSnapshotRef,
) -> ExperimentState:
    """Build caller state without bypassing the default workflow's binder."""
    return ExperimentState(
        run_id=run_id,
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
    )


def _simulation_output_cents(
    store: FileSystemCAS,
    state: ExperimentState,
) -> tuple[list[int], int]:
    """Read back the persisted simulation output and express it in integer cents."""
    result_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    assert result_ref is not None
    assert store.get_manifest(result_ref).kind == "foundry.simulation_result"
    result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(result_ref.artifact_id))
    )
    assert result.state_snapshot_ref is not None
    final_state = load_state_snapshot(store, snapshot_ref=result.state_snapshot_ref)
    income_cents = [
        round(float(value) * 100)
        for value in np.asarray(final_state.agents.income).tolist()
    ]
    treasury_cents = round(float(np.asarray(final_state.government_balance)) * 100)
    return income_cents, treasury_cents


def _cli_environment() -> dict[str, str]:
    """Keep both workflow phases on the local CPU path with bounded thread counts."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(SRC_ROOT), str(PROJECT_ROOT)))
    environment["POLISYOS_RUNNER_BACKEND"] = "local"
    environment["POLISYOS_RUNNER_MAX_PARALLELISM"] = "1"
    environment["OMP_NUM_THREADS"] = "1"
    environment["OPENBLAS_NUM_THREADS"] = "1"
    environment["MKL_NUM_THREADS"] = "1"
    environment["NUMEXPR_NUM_THREADS"] = "1"
    environment["JAX_PLATFORMS"] = "cpu"
    return environment


@pytest.mark.integration
def test_default_cli_resume_executes_residual_from_native_partial_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public CLI resume must execute residual nodes after a real CAS input recovers."""
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    monkeypatch.setenv("POLISYOS_RUNNER_MAX_PARALLELISM", "1")
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "1")
    monkeypatch.setenv("MKL_NUM_THREADS", "1")
    monkeypatch.setenv("NUMEXPR_NUM_THREADS", "1")
    source = FileSystemCAS(tmp_path / "source-cas")
    trinity_ref, registry_ref, data_snapshot_ref = _build_income_tax_inputs(source)
    source_ids = source.iter_artifact_ids()
    source_id_strings = {str(artifact_id) for artifact_id in source_ids}
    data_snapshot_id = str(data_snapshot_ref.artifact_id)
    assert data_snapshot_id in source_id_strings

    transferable_ids = [
        artifact_id for artifact_id in source_ids if str(artifact_id) != data_snapshot_id
    ]
    transferable_id_strings = {str(artifact_id) for artifact_id in transferable_ids}
    assert transferable_id_strings == source_id_strings - {data_snapshot_id}
    for artifact_id in transferable_ids:
        manifest = source.get_manifest(artifact_id)
        assert all(
            str(input_ref.artifact_id) in transferable_id_strings
            for input_ref in manifest.inputs
        ), f"partial source transfer would sever manifest lineage for {artifact_id}"

    target_root = tmp_path / "resume-cas"
    target = FileSystemCAS(target_root)
    partial_transfer = source.export_subgraph(
        transferable_ids,
        tmp_path / "source-without-data-snapshot",
        compress=False,
    )
    assert partial_transfer.missing_artifacts == []
    assert partial_transfer.missing_manifests == []
    partial_import = target.import_subgraph(
        partial_transfer.output_path,
        verify_integrity=True,
    )
    assert partial_import.verification_failed == []
    assert partial_import.imported_artifacts == len(transferable_ids)
    for artifact_id in transferable_ids:
        assert target.get_bytes(artifact_id) == source.get_bytes(artifact_id)
        assert target.get_manifest(artifact_id) == source.get_manifest(artifact_id)
    with pytest.raises(FileNotFoundError):
        target.get_bytes(data_snapshot_ref.artifact_id)

    run_id = "R_rep_01_default_cli_partial_resume"
    initial_state = _initial_experiment_state(
        run_id=run_id,
        trinity_ref=trinity_ref,
        registry_ref=registry_ref,
        data_snapshot_ref=data_snapshot_ref,
    )
    partial_result = run_default_workflow(initial_state, store=target)
    assert partial_result.report.status == "fail"
    partial_nodes = {record.alias: record for record in partial_result.report.nodes}
    assert partial_nodes["bind_foundry_inputs"].status == "fail"

    partial_checkpoint = resolve_latest_checkpoint(target, run_id)
    assert partial_checkpoint is not None
    _, partial_artifact = partial_checkpoint
    default_spec = default_workflow_spec()
    expected_aliases = {invocation.alias for invocation in default_spec.nodes}
    assert len(expected_aliases) == 23
    assert partial_artifact.metadata.workflow_id == "scientist_default"
    assert (
        partial_artifact.metadata.origin_workflow_fingerprint
        == compute_workflow_fingerprint(default_spec)
    )
    partial_completed = set(partial_artifact.metadata.completed_nodes)
    assert "start" in partial_completed
    assert "build_execution_plan" in partial_completed
    assert "bind_foundry_inputs" not in partial_completed
    assert partial_completed < expected_aliases

    recovery_transfer = source.export_subgraph(
        source_ids,
        tmp_path / "authentic-source-recovery",
        compress=False,
    )
    assert recovery_transfer.missing_artifacts == []
    assert recovery_transfer.missing_manifests == []
    recovered_import = target.import_subgraph(
        recovery_transfer.output_path,
        verify_integrity=True,
    )
    assert recovered_import.verification_failed == []
    assert recovered_import.imported_artifacts == len(source_ids)
    assert target.get_bytes(data_snapshot_ref.artifact_id) == source.get_bytes(
        data_snapshot_ref.artifact_id
    )
    assert target.get_manifest(data_snapshot_ref) == source.get_manifest(data_snapshot_ref)

    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.ops_runners.runtime_cli",
            "resume",
            run_id,
            "--cas-root",
            str(target_root),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=_cli_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    (tmp_path / "cli.stdout.log").write_text(cli.stdout, encoding="utf-8")
    (tmp_path / "cli.stderr.log").write_text(cli.stderr, encoding="utf-8")
    cli_payload: dict[str, Any] = json.loads(cli.stdout)
    assert cli_payload["checkpoint"]["completed_nodes_count"] == len(partial_completed)
    assert cli_payload["resume"]["status"] == "ok"

    resumed_checkpoint = resolve_latest_checkpoint(target, run_id)
    assert resumed_checkpoint is not None
    _, resumed_artifact = resumed_checkpoint
    resumed_completed = set(resumed_artifact.metadata.completed_nodes)
    assert {
        "bind_foundry_inputs",
        "run_data_plane_gate",
        "compile_foundry",
        "resolve_parameters",
        "run_simulation",
    } <= resumed_completed
    resumed_state = ExperimentState.model_validate(resumed_artifact.state)
    resumed_income_cents, resumed_treasury_cents = _simulation_output_cents(
        target,
        resumed_state,
    )

    oracle_store = FileSystemCAS(tmp_path / "fresh-oracle-cas")
    oracle_trinity_ref, oracle_registry_ref, oracle_snapshot_ref = _build_income_tax_inputs(
        oracle_store
    )
    assert oracle_trinity_ref.artifact_id == trinity_ref.artifact_id
    assert oracle_registry_ref.artifact_id == registry_ref.artifact_id
    assert oracle_snapshot_ref.artifact_id == data_snapshot_ref.artifact_id
    oracle_result = run_default_workflow(
        _initial_experiment_state(
            run_id="R_rep_01_default_cli_fresh_oracle",
            trinity_ref=oracle_trinity_ref,
            registry_ref=oracle_registry_ref,
            data_snapshot_ref=oracle_snapshot_ref,
        ),
        store=oracle_store,
    )
    oracle_successful_nodes = {
        record.alias for record in oracle_result.report.nodes if record.status == "ok"
    }
    assert oracle_successful_nodes <= resumed_completed
    assert cli_payload["resume"]["status"] == oracle_result.report.status
    assert cli.returncode == (0 if oracle_result.report.status == "ok" else 1), (
        f"stdout={cli.stdout}\nstderr={cli.stderr}"
    )
    oracle_income_cents, oracle_treasury_cents = _simulation_output_cents(
        oracle_store,
        oracle_result.state,
    )

    independent_income_cents = [9_000, 18_000, 27_000]
    independent_tax_revenue_cents = 6_000
    assert resumed_income_cents == independent_income_cents
    assert resumed_treasury_cents == independent_tax_revenue_cents
    assert (resumed_income_cents, resumed_treasury_cents) == (
        oracle_income_cents,
        oracle_treasury_cents,
    )
