"""Compatibility and execution witnesses for REP-01 replay ownership.

The direct-owner checks pin the Runtime root facade, delayed Core CLI import,
benchmark import, and dynamic import inventory to Scientist's deterministic
owner. The remaining tests protect the supported ABI and prove persisted CLI
replay and resume paths continue to execute through their canonical owners.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, FileSystemCAS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
DYNAMIC_IMPORTS = PROJECT_ROOT / "architecture" / "imports" / "dynamic.toml"

ROOT_EXPORTS = (
    "CompletenessLevel",
    "CompletenessReport",
    "ReplayPlan",
    "ReplayStrategy",
    "VerificationConfig",
    "VerificationMode",
    "VerificationResult",
    "build_replay_plan",
    "completeness_check",
    "verify_replay",
)

COMPATIBILITY_EXPORTS = (
    "CompletenessLevel",
    "CompletenessReport",
    "MissingArtifact",
    "ReplayBundleMeasurement",
    "ReplayPlan",
    "ReplayStrategy",
    "SeedResolution",
    "VerificationConfig",
    "VerificationMode",
    "VerificationResult",
    "build_replay_plan",
    "compare_current_environment",
    "completeness_check",
    "determine_replay_strategy",
    "measure_replayable_audit_bundle",
    "normalize_artifact_id",
    "resolve_effective_seed",
    "set_global_seeds",
    "try_parse_artifact_id",
    "verify_replay",
)


def _isolated_environment() -> dict[str, str]:
    """Return an import environment that resolves this checkout, not an editable sibling."""
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    paths = [str(SRC_ROOT), str(PROJECT_ROOT)]
    if existing:
        paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return environment


def _run_isolated(code: str) -> subprocess.CompletedProcess[str]:
    """Run one import-boundary probe in a fresh interpreter."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=_isolated_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_runtime_root_replay_exports_bind_directly_and_stay_lazy() -> None:
    """The ten-symbol Runtime facade must resolve Scientist without loading the shim."""
    result = _run_isolated(
        f"""
import importlib
import sys

runtime = importlib.import_module('polisyos.runtime')
assert not any(name == 'polisyos.scientist' or name.startswith('polisyos.scientist.')
               for name in sys.modules), sorted(sys.modules)
assert 'polisyos.runtime.replay' not in sys.modules
canonical = importlib.import_module('polisyos.scientist.replay.deterministic')
expected = {ROOT_EXPORTS!r}
assert tuple(runtime.__all__) == expected
assert 'polisyos.runtime.replay' not in sys.modules
for name in expected:
    assert getattr(runtime, name) is getattr(canonical, name), name
assert 'polisyos.runtime.replay' not in sys.modules
""",
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_runtime_replay_compatibility_window_keeps_all_twenty_symbols() -> None:
    """The transitional module keeps its twenty-symbol ABI while callers move away."""
    canonical = importlib.import_module("polisyos.scientist.replay.deterministic")
    compatibility = importlib.import_module("polisyos.runtime.replay")

    assert tuple(compatibility.__all__) == COMPATIBILITY_EXPORTS
    for name in COMPATIBILITY_EXPORTS:
        assert getattr(compatibility, name) is getattr(canonical, name), name


def test_runtime_unknown_replay_symbol_fails_closed() -> None:
    """An unknown root name must not be made importable by the relocation."""
    runtime = importlib.import_module("polisyos.runtime")

    with pytest.raises(AttributeError, match="no attribute"):
        assert runtime.REP_01_UNKNOWN_REPLAY_SYMBOL


def test_core_replay_cli_keeps_delayed_import_on_direct_scientist_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Core CLI keeps lazy loading but changes only its replay owner string."""
    from polisyos.core.components import _cli_replay

    imported: list[str] = []
    real_import_module = _cli_replay.importlib.import_module

    def _recording_import(module_name: str, package: str | None = None):
        imported.append(module_name)
        return real_import_module(module_name, package)

    monkeypatch.setattr(_cli_replay.importlib, "import_module", _recording_import)
    args = SimpleNamespace(
        packet_ref="sha256:" + "a" * 64,
        bundle=None,
        cas_root=tmp_path / "cas",
        check_only=True,
        export=None,
        json=True,
    )

    exit_code = _cli_replay._cmd_replay(args)

    assert exit_code == 1
    assert imported[0] == "polisyos.scientist.replay.deterministic"
    payload = json.loads(capsys.readouterr().out)
    assert payload["level"] == "incomplete"
    assert "packet_unreadable" in payload["reason_codes"]


def test_advanced_benchmark_replay_import_binds_direct_scientist_owner() -> None:
    """The benchmark helper must not keep a hidden dependency on Runtime replay."""
    result = _run_isolated(
        """
import importlib

common = importlib.import_module('benchmarks.advanced.common')
canonical = importlib.import_module('polisyos.scientist.replay.deterministic')
assert common.runtime_replay is canonical
"""
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_dynamic_inventory_declares_core_replay_owner_at_scientist_path() -> None:
    """The fail-closed dynamic inventory must describe the delayed direct owner."""
    document = tomllib.loads(DYNAMIC_IMPORTS.read_text(encoding="utf-8"))
    replay_entries = [
        entry
        for entry in document["pattern"]
        if entry.get("source_file") == "src/polisyos/core/components/_cli_replay.py"
        and entry.get("call") == "importlib.import_module"
        and entry.get("pattern")
        in {
            "polisyos.runtime.replay",
            "polisyos.scientist.replay.deterministic",
        }
    ]

    assert len(replay_entries) == 1
    entry = replay_entries[0]
    assert entry["pattern"] == "polisyos.scientist.replay.deterministic"
    assert entry["target"] == "polisyos.scientist.replay.deterministic"
    assert entry["allowed_targets"] == ["polisyos.scientist.replay.deterministic"]


def test_replay_cli_check_only_reads_a_persisted_packet_without_running_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Check-only reports a persisted packet's completeness and never starts replay."""
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.components import _cli_replay

    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    packet_ref = store.put_json(
        {
            "schema_version": "3.0",
            "run_id": "R_rep_01_check_only",
            "seed": 7,
            "inputs": {},
            "artifacts": {},
        },
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
    )
    args = SimpleNamespace(
        packet_ref=str(packet_ref.artifact_id),
        bundle=None,
        cas_root=cas_root,
        check_only=True,
        export=None,
        json=True,
    )

    exit_code = _cli_replay._cmd_replay(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["level"] == "incomplete"
    assert payload["strategy"] == "none"
    assert payload["present_artifacts"] == 1
    assert "strategy_unresolved" in payload["reason_codes"]


def test_resume_dry_run_reads_persisted_checkpoint_head(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Resume dry-run preserves the old persisted checkpoint/run-directory contract."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import _cli_replay
    from polisyos.scientist.orchestration.engine.checkpoint import (
        create_checkpoint,
        update_checkpoint_head,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    cas_root = tmp_path / "cas"
    run_id = "R_rep_01_resume"
    store = FileSystemCAS(cas_root)
    created = create_checkpoint(
        store,
        run_id=run_id,
        state=ExperimentState(run_id=run_id, params={"phase": "PLAN"}).model_dump(
            mode="python", by_alias=True, exclude_none=False
        ),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_noop@1.0.0",
        completed_nodes=["start"],
        workflow_id="wf_rep_01",
        workflow_fingerprint="1" * 64,
        fsm_phase="PLAN",
        cache_entry_refs=[],
    )
    update_checkpoint_head(
        cas_root / "runs" / run_id,
        run_id=run_id,
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=os.getpid(),
        writer_hostname="rep-01-test",
    )
    args = SimpleNamespace(
        cas_root=cas_root,
        run_id=run_id,
        checkpoint_policy="strict",
        json=True,
        dry_run=True,
        force=False,
    )

    exit_code = _cli_replay._cmd_resume(args)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == run_id
    assert payload["sequence_number"] == 0
    assert payload["node_alias"] == "start"
    assert payload["workflow_id"] == "wf_rep_01"


def test_resume_cli_executes_remaining_native_workflow_and_persists_fresh_head(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain the original default-workflow compatibility probe, not fresh CLI proof."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.orchestration.engine.checkpoint import (
        COMPLETED_NODE_STATUS_CONTRACT,
        compute_workflow_fingerprint,
        create_checkpoint,
        resolve_latest_checkpoint,
        update_checkpoint_head,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import (
        NodeInvocation,
        WorkflowSpec,
    )
    from tools.ops_runners.runtime_cli import main as runtime_cli_main

    cas_root = tmp_path / "cas"
    run_id = "R_rep_01_native_resume"
    workflow = WorkflowSpec(
        workflow_id="rep_01_resume",
        nodes=[
            NodeInvocation(alias="start", node_id="scientist.node_noop@1.0.0"),
            NodeInvocation(
                alias="finish",
                node_id="scientist.node_noop@1.0.0",
                depends_on=["start"],
            ),
        ],
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.workflows.default.default_workflow_spec",
        lambda: workflow,
    )

    store = FileSystemCAS(cas_root)
    state = ExperimentState(run_id=run_id, params={"phase": "PLAN"})
    created = create_checkpoint(
        store,
        run_id=run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_noop@1.0.0",
        completed_nodes=["start"],
        completed_node_status_contract=COMPLETED_NODE_STATUS_CONTRACT,
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        fsm_phase="PLAN",
        cache_entry_refs=[],
    )
    update_checkpoint_head(
        cas_root / "runs" / run_id,
        run_id=run_id,
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=os.getpid(),
        writer_hostname="rep-01-test",
    )

    exit_code = runtime_cli_main(
        [
            "resume",
            run_id,
            "--cas-root",
            str(cas_root),
            "--checkpoint-policy",
            "strict",
            "--json",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert output.err == ""
    payload = json.loads(output.out)
    assert payload["resume"]["status"] == "ok"
    assert payload["checkpoint"]["sequence_number"] == 0

    resolved = resolve_latest_checkpoint(FileSystemCAS(cas_root), run_id)
    assert resolved is not None
    head, checkpoint = resolved
    assert head.sequence_number == 1
    assert head.node_alias == "finish"
    assert checkpoint.metadata.completed_nodes == ["start", "finish"]
    assert checkpoint.metadata.completed_node_status_contract == COMPLETED_NODE_STATUS_CONTRACT


def test_fresh_cli_resumes_selected_original_workflow_without_default_override(
    tmp_path: Path,
) -> None:
    """Actual builtin production, explicit selected input and fresh CLI resume compose."""
    cas_root = tmp_path / "cas"
    run_id = "R_rep_01_fresh_cli"
    produced = _run_isolated(
        f"""
import json
import logging
from pathlib import Path
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.builtins import builtin_nodes
from polisyos.scientist.orchestration.engine.checkpoint import CASCheckpointHook, resolve_latest_checkpoint
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

class StoppedAfterPublication(RuntimeError):
    pass

class StopAfterFirst(CASCheckpointHook):
    def on_node_complete(self, **kwargs):
        result = super().on_node_complete(**kwargs)
        if kwargs["alias"] == "start":
            raise StoppedAfterPublication("stop after the real durable first head")
        return result

store = FileSystemCAS(Path({str(cas_root)!r}))
bundle = build_default_registry_bundle(store, return_selected_profile=True)
run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id={run_id!r})
ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("rep01.native"))
registry = NodeRegistry()
for node in builtin_nodes():
    registry.register(node)
workflow = WorkflowSpec(workflow_id="rep01_selected_original", nodes=[
    NodeInvocation(alias="start", node_id="scientist.node_set_state@1.0.0",
                   params={{"key": "first_value", "value": 1}}),
    NodeInvocation(alias="finish", node_id="scientist.node_emit_artifact@1.0.0",
                   depends_on=["start"],
                   params={{"key": "finish_result", "payload": {{"seed": 7, "value": 2}}}}),
])
state = ExperimentState(run_id={run_id!r}, inputs={{"registry_bundle_ref": bundle.bundle_ref}},
                        params={{"random_seed": 7}})
hook = StopAfterFirst(store=store, run_dir=store.root / "runs" / {run_id!r},
                      checkpoint_policy="strict")
try:
    WorkflowExecutor(ctx, registry, checkpoint_hook=hook).execute(workflow, state)
except StoppedAfterPublication:
    pass
else:
    raise AssertionError("publication stop was never reached")
selected = [ref for ref in run.run_manifest.inputs if ref.kind == "scientist.workflow_spec"]
assert len(selected) == 1
assert selected[0].manifest_profile_sha256
resolved = resolve_latest_checkpoint(store, {run_id!r})
assert resolved is not None
assert resolved[1].metadata.completed_nodes == ["start"]
assert resolved[1].state["params"]["first_value"] == 1
run.suspend_for_resume()
print(json.dumps(selected[0].model_dump(mode="json"), sort_keys=True))
""",
    )
    assert produced.returncode == 0, f"stdout={produced.stdout}\nstderr={produced.stderr}"
    selected = json.loads(produced.stdout.splitlines()[-1])
    trace_path = cas_root / "runs" / run_id / "trace.jsonl"

    def started_aliases() -> list[str]:
        records = [json.loads(line) for line in trace_path.read_text().splitlines() if line]
        return [
            record["phase"].removeprefix("scientist.node.")
            for record in records
            if record["event"] == "NODE_STARTED"
        ]

    assert started_aliases() == ["start"]
    command = [
        sys.executable,
        "-B",
        "-m",
        "tools.ops_runners.runtime_cli",
        "resume",
        run_id,
        "--cas-root",
        str(cas_root),
        "--workflow-ref",
        selected["artifact_id"],
        "--workflow-profile",
        selected["manifest_profile_sha256"],
        "--checkpoint-policy",
        "strict",
        "--json",
    ]
    environment = _isolated_environment()
    environment["POLISYOS_RUNNER_BACKEND"] = "local"
    for _attempt in range(2):
        resumed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert resumed.returncode == 0, f"stdout={resumed.stdout}\nstderr={resumed.stderr}"
        assert json.loads(resumed.stdout)["resume"]["status"] == "ok"
        assert started_aliases() == ["start", "finish"]

    from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.checkpoint import resolve_latest_checkpoint

    fresh = FileSystemCAS(cas_root)
    resolved = resolve_latest_checkpoint(fresh, run_id)
    assert resolved is not None
    head, checkpoint = resolved
    assert head.node_alias == "finish"
    assert checkpoint.metadata.completed_nodes == ["start", "finish"]
    assert checkpoint.state["params"]["first_value"] == 1
    output_ref = checkpoint.state["artifacts_index"]["finish_result"]
    assert from_canonical_bytes(fresh.get_bytes(ArtifactRef.model_validate(output_ref))) == {
        "seed": 7,
        "value": 2,
    }


@pytest.mark.parametrize(
    ("workflow_ref", "workflow_profile"),
    [
        ("sha256:" + "a" * 64, None),
        (None, "sha256:" + "b" * 64),
        ("not-an-id", "sha256:" + "b" * 64),
        ("sha256:" + "a" * 64, "bad-profile"),
    ],
)
def test_resume_cli_refuses_unselected_workflow_before_store_creation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    workflow_ref: str | None,
    workflow_profile: str | None,
) -> None:
    """The explicit original-workflow input is all-or-nothing and fully selected."""
    from polisyos.core.components import _cli_replay

    cas_root = tmp_path / "absent-cas"
    result = _cli_replay._cmd_resume(
        SimpleNamespace(
            cas_root=cas_root,
            run_id="R_invalid_workflow_selection",
            workflow_ref=workflow_ref,
            workflow_profile=workflow_profile,
            checkpoint_policy="strict",
            dry_run=False,
            force=False,
            json=True,
        )
    )
    assert result == 2
    assert "workflow" in capsys.readouterr().err
    assert not cas_root.exists()


def test_run_manifest_and_quality_replay_contracts_remain_available(tmp_path: Path) -> None:
    """REP-01 must not retire the independent historical RunManifest or quality replay path."""
    from polisyos.runtime.api import log_artifact, start_run
    from polisyos.runtime.manifest import RunManifest

    runs_root = tmp_path / "runs"
    manifest = start_run(run_id="R_rep_01_manifest", base_dir=runs_root)
    log_artifact(
        run_id=manifest.run_id,
        artifact_type="rep_01_probe",
        payload={"stable": True},
        base_dir=runs_root,
    )

    persisted = RunManifest.model_validate_json(
        (runs_root / manifest.run_id / "manifest.json").read_text(encoding="utf-8")
    )
    assert persisted.run_id == manifest.run_id
    assert any(item.artifact_type == "rep_01_probe" for item in persisted.artifacts)

    quality_replay = importlib.import_module("polisyos.runtime.quality.replay")
    assert callable(quality_replay.build_replay_manifest)


def test_skip_verification_never_claims_a_pass(tmp_path: Path) -> None:
    """An explicitly skipped comparison grants no verification evidence."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.scientist.replay.deterministic import (
        VerificationConfig,
        VerificationMode,
        verify_replay,
    )

    result = verify_replay(
        FileSystemCAS(tmp_path / "cas"),
        original_payload={},
        replay_simulation_ref=None,
        config=VerificationConfig(mode=VerificationMode.SKIP),
    )

    assert result.passed is False
    assert result.skipped is True
    assert result.mode is VerificationMode.SKIP
    assert result.details == {"reason": "verification_skipped"}


@pytest.mark.parametrize("same_ref", [True, False])
def test_bit_exact_reports_reference_identity_without_scientific_promotion(
    tmp_path: Path, same_ref: bool
) -> None:
    """Bit-exact compares persisted result identity, without a scientific claim."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.scientist.replay.deterministic import (
        VerificationConfig,
        VerificationMode,
        verify_replay,
    )

    store = FileSystemCAS(tmp_path / "cas")
    original = store.put_json(
        {"numerical_result": 1},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    other = store.put_json(
        {"numerical_result": 2},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    replay_ref = original if same_ref else other
    result = verify_replay(
        store,
        original_payload={"artifacts": {"simulation_result_ref": str(original.artifact_id)}},
        replay_simulation_ref=replay_ref.artifact_id,
        config=VerificationConfig(mode=VerificationMode.BIT_EXACT),
    )

    assert result.passed is same_ref
    assert result.skipped is False
    assert result.details == {"match": same_ref}
    assert result.original_ref == str(original.artifact_id)
    assert result.replay_ref == str(replay_ref.artifact_id)


def _persist_metric_result(store: FileSystemCAS, value: int) -> ArtifactRef:
    """Persist real typed metrics and their result for comparator boundary tests."""
    from polisyos.core.artifacts import ArtifactID
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.contracts.foundry import (
        ExecPlanRef,
        Metrics,
        MetricsRef,
        SimulationResult,
    )

    metrics = store.put_json(
        Metrics(values={"controlled_value": value}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        return_selected_profile=True,
    )
    return store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=ArtifactID.model_validate("sha256:" + "e" * 64)),
            metrics_ref=MetricsRef.model_validate(metrics.model_dump(mode="python")),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
        return_selected_profile=True,
    )


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), float("-inf"), -0.1])
def test_ci_bounded_rejects_invalid_tolerance_before_comparing_real_metrics(
    tmp_path: Path, tolerance: float
) -> None:
    """An unbounded/undefined numeric tolerance cannot turn real drift into a pass."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.scientist.replay.deterministic import (
        VerificationConfig,
        VerificationMode,
        verify_replay,
    )

    store = FileSystemCAS(tmp_path / "cas")
    original = _persist_metric_result(store, 1)
    changed = _persist_metric_result(store, 10)
    with pytest.raises(ValueError, match=r"relative_tolerance.*finite.*nonnegative"):
        verify_replay(
            store,
            original_payload={"artifacts": {"simulation_result_ref": str(original.artifact_id)}},
            replay_simulation_ref=changed,
            config=VerificationConfig(
                mode=VerificationMode.CI_BOUNDED, relative_tolerance=tolerance
            ),
        )


@pytest.mark.parametrize("inlet", ["verification", "seed", "environment"])
def test_replay_public_selected_binding_cannot_replace_the_payload_id(
    tmp_path: Path, inlet: str
) -> None:
    """A selected view names the payload artifact, rather than an alternative ID."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.scientist.replay.deterministic import (
        VerificationConfig,
        VerificationMode,
        compare_current_environment,
        resolve_effective_seed,
        verify_replay,
    )

    store = FileSystemCAS(tmp_path / "cas")
    if inlet == "verification":
        original = _persist_metric_result(store, 1)
        changed = _persist_metric_result(store, 10)
        with pytest.raises(ValueError, match="replay_input_binding_mismatch"):
            # B must not be loaded while the report attributes that comparison to A.
            verify_replay(
                store,
                original_payload={
                    "artifacts": {"simulation_result_ref": str(original.artifact_id)}
                },
                replay_simulation_ref=changed,
                config=VerificationConfig(mode=VerificationMode.CI_BOUNDED),
                original_reference_bindings={"artifact.simulation_result_ref": changed},
            )
        return

    kind = "foundry.exec_plan" if inlet == "seed" else "foundry.environment_manifest"
    original = store.put_json(
        {"controlled_input": "A"},
        PutOptions(kind=kind, media_type="application/json"),
        return_selected_profile=True,
    )
    changed = store.put_json(
        {"controlled_input": "B"},
        PutOptions(kind=kind, media_type="application/json"),
        return_selected_profile=True,
    )
    if inlet == "seed":
        with pytest.raises(ValueError, match="replay_input_binding_mismatch"):
            resolve_effective_seed(
                {"artifacts": {"exec_plan_ref": str(original.artifact_id)}},
                store=store,
                reference_bindings={"artifact.exec_plan_ref": changed},
            )
    else:
        with pytest.raises(ValueError, match="replay_input_binding_mismatch"):
            compare_current_environment(
                store,
                {"inputs": {"environment_manifest_ref": str(original.artifact_id)}},
                reference_bindings={"input.environment_manifest_ref": changed},
            )


@pytest.mark.parametrize(
    ("original_value", "replay_value", "tolerance", "expected_pass"),
    [(100, 101, 0.01, True), (100, 102, 0.01, False), (1, 1, 0.0, True), (1, 10, 0.0, False)],
)
def test_ci_bounded_has_a_finite_numeric_oracle_and_no_scientific_promotion(
    tmp_path: Path,
    original_value: int,
    replay_value: int,
    tolerance: float,
    expected_pass: bool,
) -> None:
    """Relative metric agreement is measured separately from scientific qualification."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.scientist.replay.deterministic import (
        VerificationConfig,
        VerificationMode,
        verify_replay,
    )

    store = FileSystemCAS(tmp_path / "cas")
    original = _persist_metric_result(store, original_value)
    replayed = _persist_metric_result(store, replay_value)
    result = verify_replay(
        store,
        original_payload={"artifacts": {"simulation_result_ref": str(original.artifact_id)}},
        replay_simulation_ref=replayed,
        config=VerificationConfig(mode=VerificationMode.CI_BOUNDED, relative_tolerance=tolerance),
        original_reference_bindings={"artifact.simulation_result_ref": original},
    )
    assert result.passed is expected_pass
    assert result.skipped is False
    assert result.details["scientific_qualification"] == "UNQUALIFIED"
    if not expected_pass:
        assert result.details["mismatches"]["controlled_value"]["relative_diff"] > tolerance


@pytest.mark.parametrize(
    "confidence", [float("nan"), float("inf"), float("-inf"), -0.1, 0.0, 1.0, 1.1]
)
def test_ci_bounded_refuses_nonfinite_or_out_of_range_confidence_metadata(
    tmp_path: Path, confidence: float
) -> None:
    """Agreement of real metrics cannot validate undefined probability metadata."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.scientist.replay.deterministic import (
        VerificationConfig,
        VerificationMode,
        verify_replay,
    )

    store = FileSystemCAS(tmp_path / "cas")
    original = _persist_metric_result(store, 1)
    with pytest.raises(ValueError, match=r"confidence_level.*finite.*between 0 and 1"):
        verify_replay(
            store,
            original_payload={"artifacts": {"simulation_result_ref": str(original.artifact_id)}},
            replay_simulation_ref=original,
            config=VerificationConfig(
                mode=VerificationMode.CI_BOUNDED, confidence_level=confidence
            ),
        )
