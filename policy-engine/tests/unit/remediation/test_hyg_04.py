"""Behavioral witness for the HYG-04 compatibility surfaces.

The tests keep the legacy entry points observable while the production move is
still pending.  They exercise forwarding, import ordering, canonical object
identity, lifecycle rejection, and the protected frontend/benchmark surfaces;
source-text markers alone are not sufficient evidence for any of these paths.
"""

from __future__ import annotations

import ast
import builtins
import json
import os
import re
import runpy
import subprocess
import sys
import tomllib
import types
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from polisyos.common import jax_env
from tools.lib.fs import iter_repository_files
from tools.quality.validation import check_docs_lifecycle

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.unit


def test_install_wrapper_forwards_argv_and_exit_status(tmp_path: Path) -> None:
    """The shell entry point must pass arguments and the canonical exit code."""

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "uv-argv.txt"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$@" > "$HYG04_CAPTURE"\n'
        "exit 23\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    environment = os.environ.copy()
    environment["HYG04_CAPTURE"] = str(capture)
    environment["PATH"] = os.pathsep.join(
        (str(fake_bin), environment.get("PATH", ""))
    )
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


def test_jax_bootstrap_inserts_src_before_any_jax_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bootstrap callback runs after path setup and before JAX is touched."""

    events: list[str] = []
    source_root = str(REPO_ROOT / "src")
    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "jax":
            raise AssertionError("jax was imported before bootstrap defaults")
        if name == "polisyos.common.jax_env":
            fake_module = types.ModuleType(name)

            def apply_defaults() -> None:
                assert source_root in sys.path
                events.append("defaults")

            fake_module.apply_jax_env_defaults = apply_defaults  # type: ignore[attr-defined]
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(sys, "path", list(sys.path))

    runpy.run_path(
        str(REPO_ROOT / "jax_bootstrap.py"),
        run_name="hyg04_jax_bootstrap",
    )

    assert events == ["defaults"]


def test_jax_bootstrap_subprocess_imports_environment_before_jax() -> None:
    """A fresh interpreter imports the bootstrap before any JAX module."""

    probe = """
import builtins
import sys

events = []
real_import = builtins.__import__


def guarded_import(name, *args, **kwargs):
    if name == "jax":
        raise AssertionError("jax was imported before bootstrap defaults")
    if name.startswith("polisyos.common.jax_env"):
        events.append(name)
    return real_import(name, *args, **kwargs)


builtins.__import__ = guarded_import
import jax_bootstrap  # noqa: F401

assert events
assert "jax" not in sys.modules
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_workspace_bootstrap_subprocess_exposes_real_profiles() -> None:
    """The real bootstrap parser exposes every supported dependency profile."""

    probe = """
from tools.devx.workspace._common import UV_SYNC_PROFILES
from tools.devx.workspace.bootstrap import _build_parser

expected = {
    "minimal": ("lint", "test"),
    "docs": ("lint", "docs"),
    "runtime": ("lint", "test", "runtime"),
    "research": ("lint", "test", "runtime", "research"),
}
assert UV_SYNC_PROFILES == expected

parser = _build_parser()
for profile in expected:
    parsed = parser.parse_args(
        [
            "--profile",
            profile,
            "--skip-frontend",
            "--skip-hooks",
            "--skip-doctor",
            "--no-install-uv",
        ]
    )
    assert parsed.profile == profile
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


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


def test_benchmark_shims_preserve_canonical_object_identity() -> None:
    """Legacy benchmark imports must expose the root implementation objects."""

    from benchmarks import harness as canonical_harness
    from benchmarks import metrics as canonical_metrics
    from benchmarks import suite_registry as canonical_registry
    from tools.research.benchmarks import harness as legacy_harness
    from tools.research.benchmarks import metrics as legacy_metrics
    from tools.research.benchmarks import suite_registry as legacy_registry

    assert legacy_harness.BenchmarkHarness is canonical_harness.BenchmarkHarness
    assert legacy_metrics.compute_timing_stats is canonical_metrics.compute_timing_stats
    assert legacy_registry.SuiteSpec is canonical_registry.SuiteSpec
    assert legacy_registry.canonical_suite_id is canonical_registry.canonical_suite_id


def test_benchmark_suite_registry_shim_forwards_cli_and_exit_code() -> None:
    """The legacy script path must preserve canonical CLI output and failures."""

    wrapper = REPO_ROOT / "tools/research/benchmarks/suite_registry.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )

    valid = subprocess.run(
        [sys.executable, str(wrapper), "--profile", "air-m2", "--format", "json"],
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
    assert all(
        {"suite_id", "script_path", "profiles"} <= set(item) for item in payload
    )

    invalid = subprocess.run(
        [sys.executable, str(wrapper), "--format", "not-a-format"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert invalid.returncode == 2
    assert "invalid choice" in invalid.stderr


def test_benchmark_wrapper_caller_census_is_complete_and_bounded() -> None:
    """All executable callers of the named benchmark wrappers are enumerated."""

    source_suffixes = {".py", ".pyi", ".sh"}
    legacy_modules = {
        "harness": "tools.research.benchmarks.harness",
        "metrics": "tools.research.benchmarks.metrics",
        "suite_registry": "tools.research.benchmarks.suite_registry",
    }
    callers: dict[str, set[str]] = {}
    parse_failures: list[str] = []

    for path in iter_repository_files(REPO_ROOT):
        if path.suffix not in source_suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        references: set[str] = set()
        if path.suffix in {".py", ".pyi"}:
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError:
                parse_failures.append(path.relative_to(REPO_ROOT).as_posix())
            else:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in legacy_modules.values():
                                references.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for name, full_name in legacy_modules.items():
                            if module == "tools.research.benchmarks" and any(
                                alias.name == name for alias in node.names
                            ):
                                references.add(full_name)

        for name, full_name in legacy_modules.items():
            if f"tools/research/benchmarks/{name}.py" in text:
                references.add(f"path:{full_name}")
        if references:
            callers[path.relative_to(REPO_ROOT).as_posix()] = references

    assert parse_failures == []
    assert set(callers) == {"tests/unit/remediation/test_hyg_04.py"}
    assert callers["tests/unit/remediation/test_hyg_04.py"] == {
        *legacy_modules.values(),
        "path:tools.research.benchmarks.suite_registry",
    }


def test_benchmark_wrapper_cli_matches_canonical_entrypoint() -> None:
    """The registry shim preserves canonical stdout, stderr, and exit status."""

    canonical = REPO_ROOT / "benchmarks/suite_registry.py"
    wrapper = REPO_ROOT / "tools/research/benchmarks/suite_registry.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )

    for arguments in (
        ("--profile", "air-m2", "--format", "json"),
        ("--format", "not-a-format"),
    ):
        canonical_result = subprocess.run(
            [sys.executable, str(canonical), *arguments],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        wrapper_result = subprocess.run(
            [sys.executable, str(wrapper), *arguments],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        assert (
            wrapper_result.returncode,
            wrapper_result.stdout,
            wrapper_result.stderr,
        ) == (
            canonical_result.returncode,
            canonical_result.stdout,
            canonical_result.stderr,
        )


def test_hyg04_shim_registry_resolves_live_source_and_target_paths() -> None:
    """The two executable shims resolve to existing canonical owners."""

    payload = tomllib.loads(
        (REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8")
    )
    entries = {entry["id"]: entry for entry in payload["shim"]}

    expected = {
        "product-install-sh-to-workspace-bootstrap": (
            "install.sh",
            "tools/devx/workspace/bootstrap.py",
        ),
        "product-jax-bootstrap-to-workspace-vendor": (
            "jax_bootstrap.py",
            "src/polisyos/common/jax_env.py",
        ),
    }
    for shim_id, (source_path, target_path) in expected.items():
        entry = entries[shim_id]
        assert (entry["source_path"], entry["target_path"]) == (source_path, target_path)
        assert entry["type"] == "wrapper_only"
        assert (REPO_ROOT / source_path).is_file()
        assert (REPO_ROOT / target_path).is_file()


def test_frontend_redirect_reaches_live_workspaces_and_protected_surfaces() -> None:
    """Redirect links resolve while real app/package and benchmark roots remain."""

    readme = REPO_ROOT / "frontend/README.md"
    links = re.findall(r"\]\(([^)]+)\)", readme.read_text(encoding="utf-8"))
    relative_links = [link for link in links if not re.match(r"^[a-z]+://", link)]

    assert relative_links
    for link in relative_links:
        assert (readme.parent / link).resolve().exists(), link

    findings = [
        finding
        for finding in check_docs_lifecycle.check_redirect_stubs(REPO_ROOT)
        if finding.path == "frontend/README.md"
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
    """Workspace build commands and Python package inclusion stay bounded."""

    workspace_lines = (REPO_ROOT / "pnpm-workspace.yaml").read_text(encoding="utf-8")
    workspace_globs = tuple(
        line.strip()[2:].strip().strip("'\"")
        for line in workspace_lines.splitlines()
        if line.strip().startswith("- ")
    )
    assert workspace_globs == ("apps/*", "packages/*")

    root_manifest = json.loads(
        (REPO_ROOT / "package.json").read_text(encoding="utf-8")
    )
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

    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    wheel_packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    sdist_includes = set(pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])
    assert wheel_packages == ["src/polisyos", "tools"]
    assert {"benchmarks", "docs", "ops", "schemas", "tools"} <= sdist_includes
    assert not any(
        item == prefix or item.startswith(f"{prefix}/")
        for item in sdist_includes
        for prefix in ("apps", "packages", "node_modules", "dist", "coverage")
    )

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
        frontend = fixture_root / "frontend"
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

        assert check_docs_lifecycle.check_redirect_stubs(fixture_root) == [
            check_docs_lifecycle.LifecycleFinding(
                "redirect_stub",
                "frontend/README.md",
                "redirect stub sunset exceeds the 90-day policy without `compatibility_adr`.",
            )
        ]
