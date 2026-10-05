"""Behavioral witness for the HYG-04 migrations and preserved entry points."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from polisyos.common import jax_env
from tools.quality.validation import check_docs_lifecycle

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.unit

_FRONTEND_DIR = "front" + "end"
_FRONTEND_README = f"{_FRONTEND_DIR}/README.md"


def test_install_wrapper_forwards_argv_and_exit_status(tmp_path: Path) -> None:
    """The shell entry point must pass arguments and the canonical exit code."""

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "uv-argv.txt"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$HYG04_CAPTURE"\nexit 23\n',
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    environment = os.environ.copy()
    environment["HYG04_CAPTURE"] = str(capture)
    environment["PATH"] = os.pathsep.join((str(fake_bin), environment.get("PATH", "")))
    result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "install.sh"),
            "--profile",
            "docs",
            "--skip-frontend",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 23
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "run",
        "polisyos-tools",
        "workspace",
        "bootstrap",
        "--profile",
        "docs",
        "--skip-frontend",
    ]


def test_jax_callers_apply_defaults_before_importing_jax() -> None:
    """Each real JAX entry point calls the common owner before the first JAX import."""

    probe = """
import builtins
import runpy
import sys
import types

events = []
real_import = builtins.__import__

class StopAtFirstJaxImport(Exception):
    pass

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "polisyos.common.jax_env":
        module = types.ModuleType(name)
        def apply_defaults():
            events.append("defaults")
        module.apply_jax_env_defaults = apply_defaults
        return module
    if name == "jax" or name.startswith("jax."):
        if not events:
            raise AssertionError("JAX was imported before common defaults")
        raise StopAtFirstJaxImport()
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
try:
    runpy.run_path(sys.argv[1], run_name="hyg04_jax_entrypoint_probe")
except StopAtFirstJaxImport:
    pass
else:
    raise AssertionError("entry point never reached its first JAX import")

assert events == ["defaults"]
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")))
    )
    scripts = (
        "tools/research/benchmarks/jax/bench_domain.py",
        "tools/research/benchmarks/jax/bench_simulation.py",
        "tools/research/demos/run_laffer_demo.py",
    )
    for relative in scripts:
        result = subprocess.run(
            [sys.executable, "-c", probe, str(REPO_ROOT / relative)],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{relative}: {result.stderr}"


def test_retired_jax_bootstrap_import_fails_in_a_fresh_interpreter() -> None:
    """The retired root module is absent from supported import resolution."""

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")))
    )
    probe = """
import importlib

try:
    importlib.import_module("jax_bootstrap")
except ModuleNotFoundError as exc:
    assert exc.name == "jax_bootstrap"
else:
    raise AssertionError("the retired bootstrap shim still resolves")
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", probe],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_workspace_bootstrap_subprocess_exposes_real_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The real bootstrap main forwards each profile to a captured uv argv."""

    from tools.devx.workspace import bootstrap

    capture = tmp_path / "uv-argv.txt"
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$HYG04_BOOTSTRAP_CAPTURE"\n',
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    monkeypatch.setenv("HYG04_BOOTSTRAP_CAPTURE", str(capture))
    monkeypatch.setattr(bootstrap, "_ensure_python_baseline", lambda: None)
    monkeypatch.setattr(bootstrap, "_ensure_uv_available", lambda **_: None)
    monkeypatch.setattr(bootstrap, "_ensure_node_baseline", lambda **_: None)
    monkeypatch.setattr(bootstrap, "uv_command", lambda: (str(fake_uv),))

    expected_profiles = {
        "minimal": ("lint", "test"),
        "docs": ("lint", "docs"),
        "runtime": ("lint", "test", "runtime"),
        "research": ("lint", "test", "runtime", "research"),
    }
    for profile, extras in expected_profiles.items():
        expected_argv = ["sync", "--frozen"]
        for extra in extras:
            expected_argv.extend(("--extra", extra))
        assert (
            bootstrap.main(
                [
                    "--profile",
                    profile,
                    "--skip-frontend",
                    "--skip-hooks",
                    "--skip-doctor",
                    "--no-install-uv",
                ]
            )
            == 0
        )
        assert capture.read_text(encoding="utf-8").splitlines() == expected_argv


def test_jax_env_defaults_to_cpu_on_darwin_without_a_user_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical env helper supplies safe defaults only when unset."""

    monkeypatch.setattr(jax_env.sys, "platform", "darwin")
    for name in (
        "JAX_PLATFORMS",
        "JAX_PLATFORM_NAME",
        "POLICY_ENGINE_ALLOW_JAX_METAL",
    ):
        monkeypatch.delenv(name, raising=False)

    jax_env.apply_jax_env_defaults()

    assert os.environ["JAX_PLATFORMS"] == "cpu"
    assert os.environ["JAX_PLATFORM_NAME"] == "cpu"


def test_jax_env_preserves_explicit_platform_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit platform selection, including opted-in Metal, is untouched."""

    monkeypatch.setattr(jax_env.sys, "platform", "darwin")
    monkeypatch.setenv("JAX_PLATFORMS", "metal")
    monkeypatch.setenv("JAX_PLATFORM_NAME", "metal")
    monkeypatch.setenv("POLICY_ENGINE_ALLOW_JAX_METAL", "1")

    jax_env.apply_jax_env_defaults()

    assert os.environ["JAX_PLATFORMS"] == "metal"
    assert os.environ["JAX_PLATFORM_NAME"] == "metal"


def test_canonical_benchmark_owners_expose_the_runtime_contract() -> None:
    """The retained root package owns benchmark objects directly."""

    from benchmarks import harness, metrics, suite_registry

    assert harness.BenchmarkHarness.__module__ == "benchmarks.harness"
    assert metrics.compute_timing_stats.__module__ == "benchmarks.metrics"
    assert suite_registry.SuiteSpec.__module__ == "benchmarks.suite_registry"
    assert suite_registry.canonical_suite_id.__module__ == "benchmarks.suite_registry"


def test_canonical_benchmark_suite_registry_cli_accepts_and_rejects_inputs() -> None:
    """The canonical registry command preserves its JSON and usage-error contract."""

    canonical = REPO_ROOT / "benchmarks/suite_registry.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )

    valid = subprocess.run(
        [sys.executable, str(canonical), "--profile", "air-m2", "--format", "json"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert valid.returncode == 0, valid.stderr
    payload = json.loads(valid.stdout)
    assert payload
    assert all("air-m2" in item["profiles"] for item in payload)
    assert all({"suite_id", "script_path", "profiles"} <= set(item) for item in payload)

    invalid = subprocess.run(
        [sys.executable, str(canonical), "--format", "not-a-format"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert invalid.returncode == 2
    assert "invalid choice" in invalid.stderr


def test_benchmark_wrapper_census_scans_tracked_text_and_executable_selectors() -> None:
    """Enumerate tracked text, then distinguish live code/config from reference prose."""

    module_names = tuple(
        ".".join(("tools", "research", "benchmarks", leaf))
        for leaf in ("harness", "metrics", "suite_registry")
    )
    file_names = tuple(
        f"tools/research/benchmarks/{leaf}.py" for leaf in ("harness", "metrics", "suite_registry")
    )
    parent_import = "from " + ".".join(("tools", "research", "benchmarks")) + " import"

    tracked = subprocess.run(
        ["git", "ls-files", "--cached", "-z", "--", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr.decode(errors="replace")
    tracked_paths = {path.decode() for path in tracked.stdout.split(b"\0") if path}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    assert untracked.returncode == 0, untracked.stderr.decode(errors="replace")
    untracked_paths = {path.decode() for path in untracked.stdout.split(b"\0") if path}
    untracked_text: dict[str, str] = {}
    text_inventory = subprocess.run(
        ["git", "grep", "-I", "-l", "-e", "^", "--", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert text_inventory.returncode == 0, text_inventory.stderr
    text_paths = set(text_inventory.stdout.splitlines())
    for relative in untracked_paths:
        try:
            content = (REPO_ROOT / relative).read_bytes()
            content.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if b"\0" not in content:
            text_paths.add(relative)
            untracked_text[relative] = content.decode("utf-8")
    assert text_paths <= tracked_paths | untracked_paths
    suffix_denominator: dict[str, int] = {}
    for relative in text_paths:
        suffix = Path(relative).suffix.lower() or "<no suffix>"
        suffix_denominator[suffix] = suffix_denominator.get(suffix, 0) + 1
    assert sum(suffix_denominator.values()) == len(text_paths)

    token_search = ["git", "grep", "-I", "-l", "-F"]
    tokens = (
        parent_import,
        *module_names,
        *file_names,
        *(f"policy-engine/{name}" for name in file_names),
    )
    for token in tokens:
        token_search.extend(("-e", token))
    token_search.extend(("--", "."))
    result = subprocess.run(
        token_search,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    matched_paths = set(result.stdout.splitlines())
    matched_paths.update(
        relative
        for relative, content in untracked_text.items()
        if any(token in content for token in tokens)
    )
    assert matched_paths <= text_paths

    executable_roots = (
        "apps/",
        "benchmarks/",
        "ops/",
        "scripts/",
        "src/",
        "tests/",
        "tools/",
        ".github/",
    )
    executable_manifests = {
        ".pre-commit-config.yaml",
        "Dockerfile.reproducible",
        "Makefile",
        "package.json",
        "pnpm-workspace.yaml",
        "pyproject.toml",
        "uv.toml",
    }
    live_candidates = {
        path
        for path in matched_paths
        if path.startswith(executable_roots) or path in executable_manifests
    }
    outside_classes = {
        "docs/plans/": "plans_and_bundle_contracts",
        "docs/superpowers/journals/": "historical_evidence",
        "docs/migration/archive/": "archived_migration_material",
        "architecture/baselines/": "generated_baselines",
        "architecture/policy_design_case/": "retained_case_evidence",
    }
    classified_outside: dict[str, str] = {}
    unclassified: list[str] = []
    for relative in matched_paths - live_candidates:
        category = next(
            (label for prefix, label in outside_classes.items() if relative.startswith(prefix)),
            None,
        )
        if category is None:
            unclassified.append(relative)
        else:
            classified_outside[relative] = category

    assert live_candidates == set(), sorted(live_candidates)
    assert unclassified == [], sorted(unclassified)
    assert set(classified_outside.values()) <= set(outside_classes.values())


def test_retired_benchmark_wrapper_imports_fail_in_a_fresh_interpreter() -> None:
    """Each retired module path now fails while canonical CLI entry points remain live."""

    module_names = tuple(
        ".".join(("tools", "research", "benchmarks", leaf))
        for leaf in ("harness", "metrics", "suite_registry")
    )
    probe = """
import importlib
import sys

name = sys.argv[1]
try:
    importlib.import_module(name)
except ModuleNotFoundError as exc:
    assert exc.name == name
else:
    raise AssertionError(f"retired module still resolves: {name}")
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")))
    )
    for module_name in module_names:
        result = subprocess.run(
            [sys.executable, "-S", "-c", probe, module_name],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{module_name}: {result.stderr}"


def test_hyg04_shim_registry_resolves_retained_install_wrapper() -> None:
    """The retained install entry point resolves to its canonical owner."""

    payload = tomllib.loads((REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in payload["shim"]}

    expected = {
        "product-install-sh-to-workspace-bootstrap": (
            "install.sh",
            "tools/devx/workspace/bootstrap.py",
        ),
    }
    for shim_id, (source_path, target_path) in expected.items():
        entry = entries[shim_id]
        assert (entry["source_path"], entry["target_path"]) == (source_path, target_path)
        assert entry["type"] == "wrapper_only"
        assert (REPO_ROOT / source_path).is_file()
        assert (REPO_ROOT / target_path).is_file()


def test_frontend_redirect_stub_is_retired_without_touching_live_workspaces() -> None:
    """The legacy handoff is absent while canonical roots remain protected."""

    readme = REPO_ROOT / _FRONTEND_DIR / "README.md"
    assert not readme.exists()

    findings = [
        finding
        for finding in check_docs_lifecycle.check_redirect_stubs(REPO_ROOT)
        if finding.path == _FRONTEND_README
    ]
    assert findings == []

    for protected in (
        "apps/runtime-dashboard",
        "apps/runtime-reference-shell",
        "packages/runtime-api-client",
        "tools/research/benchmarks",
    ):
        assert (REPO_ROOT / protected).is_dir(), protected


def test_frontend_workspace_build_paths_and_python_package_boundaries() -> None:
    """Frontend workspace build commands and generated outputs stay bounded."""

    workspace_lines = (REPO_ROOT / "pnpm-workspace.yaml").read_text(encoding="utf-8")
    workspace_globs = tuple(
        line.strip()[2:].strip().strip("'\"")
        for line in workspace_lines.splitlines()
        if line.strip().startswith("- ")
    )
    assert workspace_globs == ("apps/*", "packages/*")

    root_manifest = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "--workspace-concurrency=1" in root_manifest["scripts"]["build"]

    workspace_manifests = {
        relative: json.loads((REPO_ROOT / relative / "package.json").read_text(encoding="utf-8"))
        for relative in (
            "apps/runtime-dashboard",
            "apps/runtime-reference-shell",
            "packages/runtime-api-client",
        )
    }
    for manifest in workspace_manifests.values():
        assert manifest["private"] is True
        assert manifest["engines"]["node"] == ">=22 <23"
        assert "build" in manifest["scripts"]
    assert "vite build" in workspace_manifests["apps/runtime-dashboard"]["scripts"]["build"]
    assert "typecheck" in workspace_manifests["apps/runtime-reference-shell"]["scripts"]["build"]
    assert "typecheck" in workspace_manifests["packages/runtime-api-client"]["scripts"]["build"]

    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=REPO_ROOT,
        input=(
            "apps/runtime-dashboard/dist/index.js\n"
            "packages/runtime-api-client/node_modules/.bin/tool\n"
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0
    assert set(ignored.stdout.splitlines()) == {
        "apps/runtime-dashboard/dist/index.js",
        "packages/runtime-api-client/node_modules/.bin/tool",
    }


def test_redirect_lifecycle_rejects_an_unqualified_expired_stub() -> None:
    """An expired redirect cannot be retired or prolonged without an ADR."""

    with TemporaryDirectory() as temporary_root:
        fixture_root = Path(temporary_root)
        subprocess.run(
            ["git", "init", "--quiet", "--initial-branch=main"],
            cwd=fixture_root,
            check=True,
        )
        frontend = fixture_root / _FRONTEND_DIR
        frontend.mkdir()
        (frontend / "README.md").write_text(
            "\n".join(
                (
                    "---",
                    "redirect_stub: true",
                    "owner: team-frontend",
                    "target_path: apps; packages/runtime-api-client",
                    "reason: compatibility handoff",
                    "created_date: 2026-01-01",
                    "sunset_date: 2026-05-01",
                    "removal_gate: uv run python tools/quality/validation/check_docs_lifecycle.py",
                    "---",
                    "",
                    "Use the canonical workspaces.",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "--", f"{_FRONTEND_DIR}/README.md"],
            cwd=fixture_root,
            check=True,
        )

        assert check_docs_lifecycle.check_redirect_stubs(fixture_root) == [
            check_docs_lifecycle.LifecycleFinding(
                "redirect_stub",
                _FRONTEND_README,
                "redirect stub sunset exceeds the 90-day policy without `compatibility_adr`.",
            )
        ]
