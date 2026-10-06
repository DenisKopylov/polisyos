"""Behavioral witnesses for bootstrap, benchmark, and workspace boundaries."""

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
from tools.lib import imports as tool_imports
from tools.quality.validation import check_docs_lifecycle

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.unit

_FRONTEND_DIR = "front" + "end"
_FRONTEND_README = f"{_FRONTEND_DIR}/README.md"


def _installed_workspace_module_path(tmp_path: Path, filename: str = "bootstrap.py") -> Path:
    site_packages = (
        tmp_path
        / "venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "tools"
        / "devx"
        / "workspace"
    )
    site_packages.mkdir(parents=True)
    return site_packages / filename


def test_workspace_bootstrap_subprocess_exposes_real_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The canonical bootstrap main maps each profile to its pinned extras."""

    from tools.devx.workspace import bootstrap

    capture = tmp_path / "uv-argv.txt"
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$@" > "$HYG04_BOOTSTRAP_CAPTURE"\n',
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
        assert bootstrap.main(
            [
                "--profile",
                profile,
                "--skip-frontend",
                "--skip-hooks",
                "--skip-doctor",
                "--no-install-uv",
            ]
        ) == 0
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


def test_canonical_workspace_bootstrap_is_the_public_setup_entrypoint() -> None:
    """The checked-out tool CLI exposes the real workspace bootstrap command."""

    result = subprocess.run(
        [sys.executable, "-m", "tools.cli", "workspace", "bootstrap", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (REPO_ROOT / "install.sh").exists()
    assert not (REPO_ROOT / "jax_bootstrap.py").exists()
    assert "--profile" in result.stdout
    assert "--skip-frontend" in result.stdout

    installed = Path(sys.executable).with_name("polisyos-tools")
    if installed.is_file():
        installed_result = subprocess.run(
            [str(installed), "workspace", "bootstrap", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert installed_result.returncode == 0, installed_result.stderr
        assert "--profile" in installed_result.stdout


def test_installed_workspace_module_can_resolve_the_checkout_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A site-packages module resolves a real workspace only through the opt-in CWD path."""

    installed_module = _installed_workspace_module_path(tmp_path)
    monkeypatch.chdir(REPO_ROOT)

    resolved = tool_imports.repo_root_from(installed_module, allow_cwd_fallback=True)
    assert resolved == REPO_ROOT


def test_import_root_bootstrap_uses_checkout_cwd_for_unanchored_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The workspace's pre-import root setup can find the checkout for installed tools."""

    installed_module = _installed_workspace_module_path(tmp_path, "doctor.py")
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(sys, "path", sys.path.copy())

    repo_root, src_root = tool_imports.ensure_repo_import_roots(
        installed_module,
        include_repo_root=True,
        include_src_root=False,
    )

    assert repo_root == REPO_ROOT
    assert src_root == REPO_ROOT / "src"


def test_repo_root_resolution_rejects_non_workspace_cwd_with_typed_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CWD fallback does not invent a checkout when the canonical layout is absent."""

    installed_module = _installed_workspace_module_path(tmp_path)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(tool_imports.RepositoryRootUnavailableError):
        tool_imports.repo_root_from(installed_module, allow_cwd_fallback=True)


def test_repo_root_resolution_preserves_source_anchor_and_default_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source-file ancestry still wins, while plain repo_root_from does not borrow CWD."""

    fake_checkout = tmp_path / "decoy"
    (fake_checkout / "tools").mkdir(parents=True)
    (fake_checkout / "src").mkdir()
    (fake_checkout / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.chdir(fake_checkout)

    anchored = tool_imports.repo_root_from(
        REPO_ROOT / "tools" / "lib" / "imports.py",
        allow_cwd_fallback=True,
    )
    assert anchored == REPO_ROOT

    installed_module = _installed_workspace_module_path(tmp_path)
    with pytest.raises(tool_imports.RepositoryRootUnavailableError):
        tool_imports.repo_root_from(installed_module)


def test_repo_root_resolution_verifies_explicit_checkout_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit workspace selection accepts a real root and rejects a nonexistent one."""

    installed_module = _installed_workspace_module_path(tmp_path)
    monkeypatch.chdir(tmp_path)

    resolved = tool_imports.repo_root_from(installed_module, workspace_root=REPO_ROOT)
    assert resolved == REPO_ROOT

    with pytest.raises(tool_imports.RepositoryRootUnavailableError):
        tool_imports.repo_root_from(installed_module, workspace_root=tmp_path / "missing")


def test_jax_entrypoints_apply_defaults_before_the_first_jax_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every retained checkout caller invokes the canonical JAX env policy early."""

    import builtins

    class JaxImportReachedError(Exception):
        pass

    real_import = builtins.__import__
    real_apply = jax_env.apply_jax_env_defaults
    defaults_calls: list[str] = []

    def record_defaults() -> None:
        real_apply()
        defaults_calls.append("applied")

    monkeypatch.setattr(jax_env, "apply_jax_env_defaults", record_defaults)

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "jax" or name.startswith("jax."):
            assert defaults_calls == ["applied"]
            assert os.environ.get("JAX_PLATFORMS") == "cpu"
            assert os.environ.get("JAX_PLATFORM_NAME") == "cpu"
            raise JaxImportReachedError
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(jax_env.sys, "platform", "darwin")
    monkeypatch.delenv("JAX_PLATFORMS", raising=False)
    monkeypatch.delenv("JAX_PLATFORM_NAME", raising=False)
    monkeypatch.delenv("POLICY_ENGINE_ALLOW_JAX_METAL", raising=False)

    callers = (
        "tools/research/benchmarks/jax/bench_domain.py",
        "tools/research/benchmarks/jax/bench_simulation.py",
        "tools/research/demos/run_laffer_demo.py",
    )
    for caller in callers:
        defaults_calls.clear()
        monkeypatch.delenv("JAX_PLATFORMS", raising=False)
        monkeypatch.delenv("JAX_PLATFORM_NAME", raising=False)
        try:
            import runpy

            runpy.run_path(str(REPO_ROOT / caller), run_name=f"hyg04_{Path(caller).stem}")
        except JaxImportReachedError:
            pass
        assert defaults_calls == ["applied"], caller


def test_canonical_benchmark_command_runs_a_real_registered_workload(tmp_path: Path) -> None:
    """The public checkout command runs the registered deterministic workload."""

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.cli",
            "benchmarks",
            "run-all",
            "--circuit",
            "reproducibility_deterministic",
            "--mode",
            "smoke",
            "--profile",
            "air-m2",
            "--json-dir",
            str(tmp_path),
            "--run-id",
            "hyg04-deterministic",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(
        (tmp_path / "reproducibility_deterministic.json").read_text(encoding="utf-8")
    )
    assert payload["suite_id"] == "reproducibility_deterministic"
    assert payload["mode"] == "smoke"
    assert payload["n_total"] > 0
    assert payload["n_passed"] == payload["n_total"]


def test_retired_compatibility_modules_are_not_importable() -> None:
    """Removed module paths fail as imports while their owning packages remain live."""

    retired_modules = (
        "polisyos.scientist.evidence._shim",
        "polisyos.scientist.governance.passes.base",
        "polisyos.scientist.governance.passes.legal_pass",
        "polisyos.scientist.governance.passes.safety_pass",
        "polisyos.lex.factlog",
        "tools.research.benchmarks.harness",
        "tools.research.benchmarks.metrics",
        "tools.research.benchmarks.suite_registry",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT / "src"), str(REPO_ROOT), environment.get("PYTHONPATH", "")),
        )
    )
    probe = "\n".join(
        (
            "import importlib",
            "modules = " + repr(retired_modules),
            "for name in modules:",
            "    try:",
            "        importlib.import_module(name)",
            "    except ModuleNotFoundError:",
            "        continue",
            "    raise AssertionError(f'retired module still imports: {name}')",
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


def test_bootstrap_shim_registry_does_not_advertise_retired_paths() -> None:
    """The active shim registry contains no records for removed bootstrap entrypoints."""

    payload = tomllib.loads(
        (REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8")
    )
    entries = payload["shim"]
    retired_sources = {"install.sh", "jax_bootstrap.py"}
    assert not retired_sources & {entry["source_path"] for entry in entries}
    assert not {
        "product-install-sh-to-workspace-bootstrap",
        "product-jax-bootstrap-to-workspace-vendor",
    } & {entry["id"] for entry in entries}


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
        "packages/atlas-ui",
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

    workspace_contract = tomllib.loads(
        (REPO_ROOT / "architecture/frontend_workspaces.toml").read_text(encoding="utf-8")
    )
    contract_roots = {workspace["path"] for workspace in workspace_contract["workspace"]}
    workspace_manifests = {
        manifest_path.parent.relative_to(REPO_ROOT).as_posix(): json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        for workspace_glob in workspace_globs
        for manifest_path in sorted(REPO_ROOT.glob(f"{workspace_glob}/package.json"))
    }
    assert set(workspace_manifests) == contract_roots
    for manifest in workspace_manifests.values():
        assert manifest["private"] is True
        if "engines" in manifest:
            assert manifest["engines"]["node"] == ">=22 <23"
    assert "vite build" in workspace_manifests["apps/runtime-dashboard"]["scripts"]["build"]
    assert "typecheck" in workspace_manifests["apps/runtime-reference-shell"]["scripts"]["build"]
    assert "typecheck" in workspace_manifests["packages/runtime-api-client"]["scripts"]["build"]

    atlas_manifest = workspace_manifests["packages/atlas-ui"]
    assert atlas_manifest["name"] == "@polisyos/atlas-ui"
    assert atlas_manifest["exports"]["."]["types"] == "./src/index.ts"
    assert "build" not in atlas_manifest["scripts"]
    assert (
        workspace_manifests["apps/runtime-dashboard"]["dependencies"]["@polisyos/atlas-ui"]
        == "workspace:*"
    )

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    hatch_config = tomllib.loads((REPO_ROOT / "hatch.toml").read_text(encoding="utf-8"))
    wheel_packages = hatch_config["build"]["targets"]["wheel"]["packages"]
    sdist_includes = set(hatch_config["build"]["targets"]["sdist"]["include"])
    assert "hatch" not in pyproject.get("tool", {})
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
            "packages/atlas-ui/node_modules/.bin/tool\n"
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0
    assert set(ignored.stdout.splitlines()) == {
        "apps/runtime-dashboard/dist/index.js",
        "packages/runtime-api-client/node_modules/.bin/tool",
        "packages/atlas-ui/node_modules/.bin/tool",
    }


def test_redirect_lifecycle_rejects_an_unqualified_expired_stub() -> None:
    """An expired redirect cannot be retired or prolonged without an ADR."""

    with TemporaryDirectory() as temporary_root:
        fixture_root = Path(temporary_root)
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

        assert check_docs_lifecycle.check_redirect_stubs(fixture_root) == [
            check_docs_lifecycle.LifecycleFinding(
                "redirect_stub",
                _FRONTEND_README,
                "redirect stub sunset exceeds the 90-day policy without `compatibility_adr`.",
            )
        ]
