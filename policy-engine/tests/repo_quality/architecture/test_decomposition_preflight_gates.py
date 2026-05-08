from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from tools.quality.validation.decomposition_preflight import (
    REPO_ROOT,
    validate_dynamic_imports,
    validate_import_cycles,
    validate_import_time_regression,
    validate_reexport_shim_shapes,
)


def test_dynamic_imports_gate_resolves_registered_targets() -> None:
    findings = validate_dynamic_imports()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_import_cycles_gate_allows_only_phase3a_lazy_cycles() -> None:
    findings = validate_import_cycles()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_reexport_shim_shape_gate_forbids_star_import_shims() -> None:
    findings = validate_reexport_shim_shapes()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_import_time_regression_gate_has_phase3a_baseline() -> None:
    baseline = (
        REPO_ROOT
        / "architecture"
        / "baselines"
        / "structure_remediation"
        / "import_time_pre_decomp.json"
    )

    assert baseline.exists()
    if os.environ.get("POLISYOS_RUN_IMPORT_TIME_GATE") == "1":
        findings = validate_import_time_regression(live=True)
        assert findings == [], "\n".join(finding.render() for finding in findings)


def test_phase5_scientist_root_facade_has_no_loose_python_modules() -> None:
    scientist_root = REPO_ROOT / "src" / "polisyos" / "scientist"
    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text())
    registered_root_shims = {
        Path(shim["source_path"]).name
        for shim in shims["shim"]
        if shim.get("type") == "python_reexport"
        and Path(shim.get("source_path", "")).parent == Path("src/polisyos/scientist")
    }
    root_py_files = sorted(path.name for path in scientist_root.glob("*.py"))
    non_shim_root_py_files = [
        name for name in root_py_files if name not in registered_root_shims
    ]
    top_level_entries = [path for path in scientist_root.iterdir() if path.name != "__pycache__"]
    gate_result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "loose_files",
            "--mode",
            "fail-closed",
            "--package",
            "scientist",
            "--scope",
            "root",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert non_shim_root_py_files == ["__init__.py", "api.py"]
    assert len(top_level_entries) <= 250
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr


def test_phase6_foundry_root_facade_stays_within_loose_python_budget() -> None:
    foundry_root = REPO_ROOT / "src" / "polisyos" / "foundry"
    root_py_files = sorted(path.name for path in foundry_root.glob("*.py"))
    top_level_entries = [path for path in foundry_root.iterdir() if path.name != "__pycache__"]
    gate_result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "loose_files",
            "--mode",
            "fail-closed",
            "--package",
            "foundry",
            "--scope",
            "root",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert "__init__.py" in root_py_files
    assert "api.py" in root_py_files
    assert len(root_py_files) <= 5
    assert len(top_level_entries) <= 250
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr


def test_import_graph_baseline_records_phase3a_collector_contract() -> None:
    baseline = json.loads(
        (
            REPO_ROOT
            / "architecture"
            / "baselines"
            / "structure_remediation"
            / "import_graph_pre_decomp.json"
        ).read_text(encoding="utf-8")
    )

    assert baseline["collector_mode"] == "internal_ast_import_graph"
    assert "pydeps_available" in baseline
    assert "import_linter_available" in baseline


def test_pickle_inventory_includes_canonical_checkpoint_fixtures() -> None:
    inventory = json.loads(
        (
            REPO_ROOT
            / "architecture"
            / "baselines"
            / "structure_remediation"
            / "pickle_checkpoint_inventory.json"
        ).read_text(encoding="utf-8")
    )
    artifacts = {artifact["path"] for artifact in inventory["live_artifacts"]}
    manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((REPO_ROOT / "tests" / "_data" / "checkpoint_compat").glob("*/*.json"))
    ]

    assert "tests/_data/checkpoint_compat/foundry/agent_sim_experiment_result.pkl" in artifacts
    assert "tests/_data/checkpoint_compat/scientist/engine_checkpoint_artifact.pkl" in artifacts
    assert {manifest["producer"] for manifest in manifests} == {
        "polisyos.foundry.agent_sim.experiment.ExperimentRun.log_artifact",
        "polisyos.scientist.orchestration.engine.checkpoint.create_checkpoint/load_checkpoint",
    }


def test_phase3a_gate_registry_lists_new_decomposition_gates() -> None:
    gates = tomllib.loads(
        (REPO_ROOT / "architecture" / "gates" / "structure_remediation.toml").read_text(
            encoding="utf-8"
        )
    )
    gate_ids = {gate["id"] for gate in gates["gate"]}

    assert {
        "dynamic_imports_gate",
        "pickle_compat_gate",
        "public_surface_snapshot_gate",
        "import_cycles_gate",
        "import_time_regression_gate",
        "reexport_shim_shape_gate",
    } <= gate_ids


def test_phase4_1_foundry_executor_lane_closes_legacy_private_siblings() -> None:
    foundry_root = REPO_ROOT / "src" / "polisyos" / "foundry"
    removed_private_siblings = {
        "_execution_posture",
        "_executor_graph",
        "_executor_models",
        "_executor_ops",
        "_executor_patching",
        "_executor_snapshots",
        "_numeric",
    }

    assert {
        path.name for path in foundry_root.iterdir() if path.name in removed_private_siblings
    } == set()

    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text(encoding="utf-8"))[
        "shim"
    ]
    shim_sources = {shim["source_path"] for shim in shims}
    dynamic_sources = {
        entry["source_file"]
        for entry in tomllib.loads(
            (REPO_ROOT / "architecture" / "imports" / "dynamic.toml").read_text(encoding="utf-8")
        )["pattern"]
    }
    removed_source_paths = {
        f"src/polisyos/foundry/{name}/__init__.py" for name in removed_private_siblings
    }
    executor_cycle_markers = (
        "polisyos.foundry.execute",
        "polisyos.foundry.executor",
        "polisyos.foundry.runtime.numeric",
    )

    assert shim_sources.isdisjoint(removed_source_paths)
    assert dynamic_sources.isdisjoint(removed_source_paths)
    assert [
        finding
        for finding in validate_dynamic_imports()
        if "src/polisyos/foundry/execute" in finding.detail
        or "src/polisyos/foundry/executor" in finding.detail
        or any(path in finding.detail for path in removed_source_paths)
    ] == []
    assert [
        finding
        for finding in validate_import_cycles()
        if any(marker in finding.detail for marker in executor_cycle_markers)
    ] == []


def test_move_module_codemod_dry_run_plans_synthetic_world_move() -> None:
    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(script),
            "--from",
            "polisyos.foundry.agent_sim.world.world",
            "--to",
            "polisyos.foundry.agent_sim.world.runtime.world",
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "polisyos.foundry.agent_sim.world.runtime.world" in result.stdout
    assert '"src/polisyos/foundry/agent_sim/world/runtime/__init__.py"' in result.stdout


def test_move_module_codemod_rewrites_parent_leaf_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "polisyos" / "example"
    source_dir.mkdir(parents=True)
    (repo / "architecture").mkdir()
    (repo / "src" / "polisyos" / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "old.py").write_text("class Public:\n    pass\n", encoding="utf-8")
    (source_dir / "consumer.py").write_text(
        "from polisyos.example import old\nfrom polisyos.example.old import Public\n",
        encoding="utf-8",
    )
    (repo / "architecture" / "shims.toml").write_text("", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)

    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo-root",
            str(repo),
            "--from",
            "polisyos.example.old",
            "--to",
            "polisyos.example.new.old",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (source_dir / "new" / "__init__.py").exists()
    assert (source_dir / "new" / "old.py").exists()
    assert "from polisyos.example.new import old" in (source_dir / "consumer.py").read_text(
        encoding="utf-8"
    )
    assert "from polisyos.example.new.old import Public" in (source_dir / "consumer.py").read_text(
        encoding="utf-8"
    )
    assert not (source_dir / "old.py").exists()
    shim = (source_dir / "old" / "__init__.py").read_text(encoding="utf-8")
    assert "import *" not in shim
