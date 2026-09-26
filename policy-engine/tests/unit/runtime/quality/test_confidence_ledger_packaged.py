from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_PACKAGE = REPO_ROOT / "src" / "polisyos"
CONFIDENCE_LEDGER = SOURCE_PACKAGE / "runtime" / "quality" / "confidence_ledger.py"

OWNER_IMPORT = """
import importlib
import json
import os
import sys
import types
from pathlib import Path

sys.path.append(os.environ["DEPENDENCY_SITE_PACKAGES"])
import polisyos
base_package = Path(os.environ["BASE_PACKAGE_ROOT"])
if str(base_package) not in polisyos.__path__:
    polisyos.__path__.append(str(base_package))
import polisyos.runtime
base_runtime = base_package / "runtime"
if str(base_runtime) not in polisyos.runtime.__path__:
    polisyos.runtime.__path__.append(str(base_runtime))
quality = types.ModuleType("polisyos.runtime.quality")
quality.__path__ = [
    os.environ["OWNER_QUALITY_DIR"],
    str(base_runtime / "quality"),
]
quality.__package__ = "polisyos.runtime.quality"
sys.modules[quality.__name__] = quality
ledger = importlib.import_module("polisyos.runtime.quality.confidence_ledger")

def package_origins():
    origins = {}
    for name, module in sorted(sys.modules.items()):
        if name == "polisyos" or name.startswith("polisyos."):
            spec = getattr(module, "__spec__", None)
            origin = getattr(spec, "origin", None)
            origins[name] = origin or "<explicit test seam>"
    return origins
"""


def _installed_leaf_overlay(tmp_path: Path) -> tuple[Path, Path]:
    """Install only the confidence-ledger leaf; use source for dependencies."""
    site_packages = tmp_path / "site-packages"
    package_root = site_packages / "polisyos"
    quality_root = package_root / "runtime" / "quality"
    quality_root.mkdir(parents=True)
    for relative in (Path("__init__.py"), Path("runtime") / "__init__.py"):
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE_PACKAGE / relative, target)
    shutil.copyfile(CONFIDENCE_LEDGER, quality_root / "confidence_ledger.py")
    return site_packages, quality_root


def _run_owner(
    tmp_path: Path,
    *,
    import_root: Path,
    owner_quality_root: Path,
    body: str,
) -> subprocess.CompletedProcess[str]:
    """Run the explicitly bounded leaf overlay with Python site startup off."""
    cwd = tmp_path / "outside"
    cwd.mkdir(exist_ok=True)
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(import_root),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "DEPENDENCY_SITE_PACKAGES": sysconfig.get_paths()["purelib"],
        "BASE_PACKAGE_ROOT": str(SOURCE_PACKAGE),
        "OWNER_QUALITY_DIR": str(owner_quality_root),
    }
    return subprocess.run(
        [sys.executable, "-S", "-c", OWNER_IMPORT + body],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )


def _assert_bounded_installed_origins(origins: dict[str, str], *, site_packages: Path) -> None:
    """Prove only the leaf is installed and disclose every repo module origin."""
    overlay_package = (site_packages / "polisyos").resolve()
    owner_name = "polisyos.runtime.quality.confidence_ledger"
    assert owner_name in origins
    for name, origin in origins.items():
        if name == "polisyos.runtime.quality":
            assert origin == "<explicit test seam>"
            continue
        path = Path(origin).resolve()
        if name in {"polisyos", "polisyos.runtime", owner_name}:
            assert path.is_relative_to(overlay_package), (name, origin)
        else:
            assert path.is_relative_to(SOURCE_PACKAGE.resolve()), (name, origin)


def test_installed_leaf_overlay_without_build_identity_is_typed_unrun(
    tmp_path: Path,
) -> None:
    site_packages, quality_root = _installed_leaf_overlay(tmp_path)
    result = _run_owner(
        tmp_path,
        import_root=site_packages,
        owner_quality_root=quality_root,
        body="""
root = ledger._loaded_policy_engine_root()
assert root == Path(os.environ["PYTHONPATH"])
assert not (root / "pyproject.toml").exists()
assert not (root / "uv.lock").exists()
print(json.dumps({
    "identity": ledger.capture_loaded_deployment_identity().model_dump(mode="json"),
    "readiness": ledger.inspect_packaged_deployment_identity().model_dump(mode="json"),
    "origins": package_origins(),
}))
""",
    )
    assert result.returncode == 0, result.stderr
    observation = json.loads(result.stdout)
    _assert_bounded_installed_origins(observation["origins"], site_packages=site_packages)
    assert observation["identity"]["status"] == "not_established"
    assert (
        observation["identity"]["reason_code"] == "packaged_deployment_identity_issuer_unavailable"
    )
    readiness = observation["readiness"]
    assert readiness["verdict"] == "UNRUN"
    assert readiness["inputs"]["package_manifest_present"] is False
    assert readiness["inputs"]["lockfile_present_at_runtime"] is False
    assert readiness["inputs"]["n6_census_verdict"] == "UNRUN"
    assert readiness["unresolved_by_construction"] == [
        "packaged_build_identity_issuer_not_appointed",
        "n6_strangle_census_not_established",
        "deployment_authority_issuer_not_appointed",
    ]


def test_installed_leaf_overlay_refuses_loaded_runtime_authority(
    tmp_path: Path,
) -> None:
    site_packages, quality_root = _installed_leaf_overlay(tmp_path)
    result = _run_owner(
        tmp_path,
        import_root=site_packages,
        owner_quality_root=quality_root,
        body="""
root = ledger._loaded_policy_engine_root()
try:
    ledger._admit_loaded_runtime(root)
except ledger.ConfidenceLedgerError as exc:
    assert exc.code == "canonical_deployment_identity_invalid", str(exc)
    print(json.dumps({"authority_admission": "refused", "code": exc.code}))
else:
    raise AssertionError("source-free owner admitted deployment authority")
""",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "authority_admission": "refused",
        "code": "canonical_deployment_identity_invalid",
    }


def test_source_checkout_identity_remains_established_control(
    tmp_path: Path,
) -> None:
    source_root = REPO_ROOT / "src"
    quality_root = SOURCE_PACKAGE / "runtime" / "quality"
    result = _run_owner(
        tmp_path,
        import_root=source_root,
        owner_quality_root=quality_root,
        body="""
observation = ledger.capture_loaded_deployment_identity()
assert observation.status == "established", observation.model_dump(mode="json")
assert observation.reason_code is None
assert observation.deployment_identity.startswith("policy-engine-deployment:sha256:")
""",
    )
    assert result.returncode == 0, result.stderr


def test_self_attested_manifest_with_stale_lock_digest_remains_unrun(
    tmp_path: Path,
) -> None:
    site_packages, quality_root = _installed_leaf_overlay(tmp_path)
    (site_packages / "uv.lock").write_text(
        "# package-local lock without an appointed issuer\n", encoding="utf-8"
    )
    (quality_root / "_packaged_deployment_identity.json").write_text(
        json.dumps(
            {
                "schema_version": "candidate.self_attested.v1",
                "lock_sha256": "sha256:" + "0" * 64,
                "n6_census_verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )
    result = _run_owner(
        tmp_path,
        import_root=site_packages,
        owner_quality_root=quality_root,
        body="""
print(json.dumps({
    "identity": ledger.capture_loaded_deployment_identity().model_dump(mode="json"),
    "readiness": ledger.inspect_packaged_deployment_identity().model_dump(mode="json"),
}))
""",
    )
    assert result.returncode == 0, result.stderr
    observation = json.loads(result.stdout)
    assert observation["identity"]["status"] == "not_established"
    assert observation["readiness"]["verdict"] == "UNRUN"
    assert observation["readiness"]["inputs"]["lockfile_present_at_runtime"] is True
    assert observation["readiness"]["inputs"]["package_manifest_present"] is True
    assert observation["readiness"]["inputs"]["n6_census_verdict"] == "UNRUN"


def test_removing_currentness_guard_with_markers_retained_turns_red(
    tmp_path: Path,
) -> None:
    site_packages, quality_root = _installed_leaf_overlay(tmp_path)
    source = CONFIDENCE_LEDGER.read_text(encoding="utf-8")
    guard = "if not _IMPORT_TIME_LOADED_CODE_CONSISTENT:"
    assert source.count(guard) == 1
    mutant = source.replace(guard, "if False:", 1)
    for marker in (
        "LoadedDeploymentIdentityObservation",
        'status="established"',
        "packaged_deployment_identity_issuer_unavailable",
    ):
        assert marker in mutant
    (quality_root / "confidence_ledger.py").write_text(mutant, encoding="utf-8")
    result = _run_owner(
        tmp_path,
        import_root=site_packages,
        owner_quality_root=quality_root,
        body="""
observation = ledger.capture_loaded_deployment_identity()
assert observation.status == "not_established", observation.model_dump(mode="json")
""",
    )
    assert result.returncode != 0
    assert 'observation.status == "not_established"' in result.stderr
    assert "'status': 'established'" in result.stderr
