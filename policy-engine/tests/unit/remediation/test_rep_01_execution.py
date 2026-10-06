"""Behavioral witnesses for REP-01 replay routing and compatibility."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import venv
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.foundry import ExecPlanRef, ExecuteRequest, ExecuteResult

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"

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


def _build_income_tax_packet(
    cas_root: Path,
) -> tuple[FileSystemCAS, ArtifactID, ExecPlanRef, dict[str, Any]]:
    """Compile a real, bound income-tax program and persist a replay packet."""
    import jax.numpy as jnp

    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.contracts.foundry import (
        CompileRequest,
        FoundryInputBindings,
        StateSnapshotRef,
    )
    from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.execute.executor import put_state_snapshot
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import SelectorOperator
    from polisyos.ir.trinity import TrinityBundle

    store = FileSystemCAS(cas_root)
    registry = build_default_registry_bundle(store)
    load_registry_bundle_content(store, registry.bundle_ref)

    base_state = GlobalState.empty(n_agents=3, n_firms=1)
    initial_state = base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.asarray([100.0, 200.0, 300.0], dtype=jnp.float32),
            reported_income=jnp.asarray([100.0, 200.0, 300.0], dtype=jnp.float32),
        )
    )
    snapshot_ref = put_state_snapshot(store, state=initial_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    input_bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )

    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="rep_01_tax", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="rep_01_income_tax",
            interventions=[
                InterventionSpec(
                    intervention_id="rep_01_tax_all",
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
            model_id="rep_01_tax_model",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        policy,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=policy.schema_version),
        ),
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry.bundle_ref,
        ),
    )
    assert compile_result.ok, compile_result.notes
    assert compile_result.exec_plan_ref is not None
    lowered_ir = next(
        (item.ref for item in compile_result.derived_refs if item.role == "lowered_ir"),
        None,
    )
    assert lowered_ir is not None

    payload: dict[str, Any] = {
        "schema_version": "3.0",
        "run_id": "R_rep_01_foundry_execution",
        "seed": 731,
        "inputs": {
            "trinity_bundle_ref": str(policy_ref.artifact_id),
            "registry_bundle_ref": str(registry.bundle_ref.artifact_id),
            "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
            "state_snapshot_ref": str(state_snapshot_ref.artifact_id),
            "input_bindings_ref": str(input_bindings_ref.artifact_id),
        },
        "artifacts": {
            "exec_plan_ref": str(compile_result.exec_plan_ref.artifact_id),
            "lowered_ir_ref": str(lowered_ir.artifact_id),
        },
    }
    packet_ref = store.put_json(
        payload,
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
    )
    return store, packet_ref.artifact_id, compile_result.exec_plan_ref, payload


def _fresh_process_cas_readback(
    *,
    cas_root: Path,
    simulation_result_ref: str,
    exec_plan_ref: str,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    """Read a typed replay result and its snapshot in a clean interpreter."""
    code = r"""
import json
import sys

import numpy as np

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.foundry.execute.executor import load_state_snapshot

store = FileSystemCAS(sys.argv[1])
result_id = ArtifactID.model_validate(sys.argv[2])
expected_plan_id = ArtifactID.model_validate(sys.argv[3])
assert store.get_manifest(result_id).kind == "foundry.simulation_result"
payload = from_canonical_bytes(store.get_bytes(result_id))
result = SimulationResult.model_validate(payload)
assert result.exec_plan_ref.artifact_id == expected_plan_id
assert result.state_snapshot_ref is not None
state = load_state_snapshot(store, snapshot_ref=result.state_snapshot_ref)
print(json.dumps({
    "income": np.asarray(state.agents.income, dtype=float).tolist(),
    "government_balance": float(np.asarray(state.government_balance)),
}))
"""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONPATH"] = os.pathsep.join((str(SRC_ROOT), str(PROJECT_ROOT)))
    return subprocess.run(
        [sys.executable, "-c", code, str(cas_root), simulation_result_ref, exec_plan_ref],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
def test_replay_packet_executes_foundry_and_round_trips_real_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real replay must execute the compiled plan and persist independently checkable output."""
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.store import PutOptions

    backend = importlib.import_module("polisyos.scientist.replay.backend")
    store, packet_ref, exec_plan_ref, payload = _build_income_tax_packet(tmp_path / "cas")
    real_execute_foundry = backend.execute_foundry
    executed_requests: list[ExecuteRequest] = []
    assert "simulation_result_ref" not in payload["artifacts"]

    def observed_execute_foundry(
        store_arg: FileSystemCAS, request: ExecuteRequest
    ) -> ExecuteResult:
        executed_requests.append(request)
        return real_execute_foundry(store_arg, request)

    monkeypatch.setattr(backend, "execute_foundry", observed_execute_foundry)
    # The independent CAS readback below is the oracle; BIT_EXACT only compares result IDs.
    result = backend.replay_packet(store, packet_ref, verify=False)

    assert result.success, result.errors
    assert result.strategy.value == "foundry"
    assert result.completeness.level.value == "complete"
    assert len(executed_requests) == 1
    assert executed_requests[0].exec_plan_ref.artifact_id == exec_plan_ref.artifact_id
    assert result.replay_simulation_result_ref is not None

    outside_checkout = tmp_path / "outside-checkout"
    outside_checkout.mkdir()
    readback = _fresh_process_cas_readback(
        cas_root=store.root,
        simulation_result_ref=result.replay_simulation_result_ref,
        exec_plan_ref=str(exec_plan_ref.artifact_id),
        cwd=outside_checkout,
    )
    assert readback.returncode == 0, f"stdout={readback.stdout}\nstderr={readback.stderr}"
    observed = json.loads(readback.stdout.strip().splitlines()[-1])

    # The independent oracle is 10% of [100, 200, 300] collected as tax.
    assert observed["income"] == pytest.approx([90.0, 180.0, 270.0], abs=1e-5)
    assert observed["government_balance"] == pytest.approx(60.0, abs=1e-5)

    # A well-formed but absent plan ref and a content-corrupted real plan must
    # fail completeness before the Foundry executor can be called again.
    fake_plan_id = ArtifactID.from_sha256_hex("f" * 64)
    assert all(fake_plan_id != item for item in store.iter_artifact_ids())
    fake_payload = {**payload, "artifacts": dict(payload["artifacts"])}
    fake_payload["artifacts"]["exec_plan_ref"] = str(fake_plan_id)
    fake_packet_ref = store.put_json(
        fake_payload,
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
    )
    fake_result = backend.replay_packet(store, fake_packet_ref.artifact_id, verify=False)
    assert not fake_result.success
    assert fake_result.completeness.level.value == "incomplete"
    assert any(item.artifact_id == str(fake_plan_id) for item in fake_result.completeness.missing)
    assert len(executed_requests) == 1

    plan_blob, _ = store._paths(exec_plan_ref.artifact_id)
    original_plan_bytes = plan_blob.read_bytes()
    try:
        plan_blob.write_bytes(original_plan_bytes + b"rep-01-corruption-probe")
        corrupt_result = backend.replay_packet(store, packet_ref, verify=False)
    finally:
        plan_blob.write_bytes(original_plan_bytes)
    assert not corrupt_result.success
    assert corrupt_result.completeness.level.value == "incomplete"
    assert any(
        item.artifact_id == str(exec_plan_ref.artifact_id)
        for item in corrupt_result.completeness.corrupted
    )
    assert len(executed_requests) == 1

    # Removing the live execution path must not let a stored or fabricated
    # result turn replay green; this injected backend failure is the falsifier.
    def removed_executor(store_arg: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
        executed_requests.append(request)
        raise RuntimeError("rep_01_execution_removed_probe")

    monkeypatch.setattr(backend, "execute_foundry", removed_executor)
    removed_result = backend.replay_packet(store, packet_ref, verify=False)
    assert not removed_result.success
    assert removed_result.replay_simulation_result_ref is None
    assert any("rep_01_execution_removed_probe" in error for error in removed_result.errors)
    assert len(executed_requests) == 2


def test_direct_replay_consumers_work_with_legacy_shim_import_blocked(tmp_path: Path) -> None:
    """A sibling consumer still works when the transitional Runtime module cannot load."""
    code = r"""
import importlib
import contextlib
import importlib.abc
import json
import io
import sys

class LegacyReplayImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "polisyos.runtime.replay":
            raise AssertionError("retired Runtime replay shim imported")
        return None

runtime = importlib.import_module("polisyos.runtime")
assert "polisyos.scientist.replay.deterministic" not in sys.modules
assert "polisyos.runtime.replay" not in sys.modules
sys.meta_path.insert(0, LegacyReplayImportBlocker())
canonical = importlib.import_module("polisyos.scientist.replay.deterministic")
assert runtime.ReplayPlan is canonical.ReplayPlan

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import _cli_replay

store = FileSystemCAS(sys.argv[1])
packet = store.put_json(
    {"schema_version": "3.0", "run_id": "R_rep_01_blocker", "inputs": {}, "artifacts": {}},
    PutOptions(kind="scientist.decision_packet", media_type="application/json"),
)
args = type("Args", (), {
    "packet_ref": str(packet.artifact_id),
    "bundle": None,
    "cas_root": sys.argv[1],
    "check_only": True,
    "export": None,
    "json": True,
})()
output = io.StringIO()
with contextlib.redirect_stdout(output):
    assert _cli_replay._cmd_replay(args) == 1
cli_payload = json.loads(output.getvalue())
assert cli_payload["level"] == "incomplete"
assert "strategy_unresolved" in cli_payload["reason_codes"]

common = importlib.import_module("benchmarks.advanced.common")
assert common.runtime_replay is canonical
assert "polisyos.runtime.replay" not in sys.modules
"""
    cas_root = tmp_path / "cas"
    outside_checkout = tmp_path / "outside-checkout"
    outside_checkout.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONPATH"] = os.pathsep.join((str(SRC_ROOT), str(PROJECT_ROOT)))
    result = subprocess.run(
        [sys.executable, "-c", code, str(cas_root)],
        cwd=outside_checkout,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


@pytest.mark.integration
def test_built_wheel_replay_abi_imports_from_fresh_site_packages(tmp_path: Path) -> None:
    """An installed wheel must serve the lazy root and full compatibility ABI outside checkout."""
    uv = shutil.which("uv")
    assert uv is not None, "the contributor toolchain requires uv to build the package wheel"
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    build = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, f"stdout={build.stdout}\nstderr={build.stderr}"
    wheels = list(wheel_dir.glob("policy_engine-*.whl"))
    assert len(wheels) == 1, f"expected one policy-engine wheel, found {wheels}"

    environment_root = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment_root)
    python = environment_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            str(wheels[0]),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, f"stdout={install.stdout}\nstderr={install.stderr}"

    site_packages = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    outside_checkout = tmp_path / "wheel-consumer"
    outside_checkout.mkdir()
    code = f"""
import importlib
import inspect
import sys
from pathlib import Path

import polisyos

site_packages = Path({site_packages!r}).resolve()
assert Path(polisyos.__file__).resolve().is_relative_to(site_packages), polisyos.__file__
runtime = importlib.import_module("polisyos.runtime")
assert tuple(runtime.__all__) == {ROOT_EXPORTS!r}
assert "polisyos.scientist.replay.deterministic" not in sys.modules
assert "polisyos.runtime.replay" not in sys.modules
canonical = importlib.import_module("polisyos.scientist.replay.deterministic")
for name in {ROOT_EXPORTS!r}:
    runtime_export = getattr(runtime, name)
    canonical_export = getattr(canonical, name)
    assert runtime_export is canonical_export, name
    assert inspect.signature(runtime_export) == inspect.signature(canonical_export), name
compatibility = importlib.import_module("polisyos.runtime.replay")
expected = {COMPATIBILITY_EXPORTS!r}
assert tuple(compatibility.__all__) == expected
for name in expected:
    assert getattr(compatibility, name) is getattr(canonical, name), name
try:
    runtime.REP_01_UNKNOWN_REPLAY_SYMBOL
except AttributeError:
    pass
else:
    raise AssertionError("unknown Runtime replay name was accepted")
"""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    consumer = subprocess.run(
        [str(python), "-c", code],
        cwd=outside_checkout,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert consumer.returncode == 0, f"stdout={consumer.stdout}\nstderr={consumer.stderr}"
