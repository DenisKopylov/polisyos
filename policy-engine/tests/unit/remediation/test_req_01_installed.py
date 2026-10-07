"""Exercise REQ-01 compiler compatibility from a freshly installed wheel."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
PRODUCT_ROOT = REPO_ROOT / "policy-engine"


def test_installed_wheel_keeps_active_compiler_and_retires_legacy_helpers(
    tmp_path: Path,
    record_property: Any,
) -> None:
    """Resolve a mapped construct through the installed active compiler only."""

    uv_executable = shutil.which("uv")
    assert uv_executable is not None, "uv is required to build and install the local wheel"

    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    build_environment = os.environ.copy()
    build_environment["UV_OFFLINE"] = "1"
    build_environment["UV_PYTHON_DOWNLOADS"] = "never"
    started = time.monotonic()
    build_result = subprocess.run(
        [
            uv_executable,
            "--offline",
            "build",
            "--wheel",
            "--out-dir",
            str(wheelhouse),
        ],
        cwd=PRODUCT_ROOT,
        env=build_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    record_property("req01_wheel_build_wall_seconds", round(time.monotonic() - started, 3))
    record_property("req01_wheel_build_command", "uv --offline build --wheel --out-dir <tmp>")
    assert build_result.returncode == 0, build_result.stdout + "\n" + build_result.stderr

    wheels = tuple(sorted(wheelhouse.glob("*.whl")))
    assert len(wheels) == 1, f"expected exactly one PolicyOS wheel, got {len(wheels)}"
    wheel_path = wheels[0]
    with wheel_path.open("rb") as wheel_file:
        wheel_sha256 = hashlib.file_digest(wheel_file, "sha256").hexdigest()
    record_property("req01_installed_wheel_sha256", wheel_sha256)

    virtual_environment = tmp_path / "venv"
    venv_result = subprocess.run(
        [
            uv_executable,
            "--offline",
            "venv",
            "--python",
            sys.executable,
            str(virtual_environment),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert venv_result.returncode == 0, venv_result.stdout + "\n" + venv_result.stderr
    venv_python = (
        virtual_environment / "Scripts/python.exe"
        if os.name == "nt"
        else virtual_environment / "bin/python"
    )

    install_result = subprocess.run(
        [
            uv_executable,
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--python",
            str(venv_python),
            str(wheel_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    record_property(
        "req01_wheel_install_command",
        "uv pip install --offline --no-deps --python <fresh-venv> <wheel>",
    )
    assert install_result.returncode == 0, install_result.stdout + "\n" + install_result.stderr

    site_result = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert site_result.returncode == 0, site_result.stdout + "\n" + site_result.stderr
    installed_site = Path(site_result.stdout.strip()).resolve()
    installed_package = installed_site / "polisyos"
    assert installed_package.is_dir(), f"wheel was not installed under {installed_site}"

    outside_checkout = tmp_path / "outside-checkout"
    outside_checkout.mkdir()
    dependency_paths = tuple(
        dict.fromkeys(
            sysconfig.get_paths()[key]
            for key in ("purelib", "platlib")
            if Path(sysconfig.get_paths()[key]).is_dir()
        )
    )
    child_environment = os.environ.copy()
    child_environment.pop("PYTHONPATH", None)
    child_environment.pop("PYTHONHOME", None)
    child_environment["PYTHONPATH"] = os.pathsep.join((str(installed_site), *dependency_paths))
    child_environment["PYTHONNOUSERSITE"] = "1"
    child_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    child_environment["POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED"] = "false"
    child_environment["REQ01_INSTALLED_SITE"] = str(installed_site)
    child_environment["REQ01_PRODUCT_ROOT"] = str(PRODUCT_ROOT.resolve())
    child_environment["REQ01_REPORT_DIR"] = str(outside_checkout / "compiler-reports")

    result = subprocess.run(
        [str(venv_python), "-S", "-c", _INSTALLED_WHEEL_PROBE],
        cwd=outside_checkout,
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    record_property("req01_installed_wheel_probe_cwd", str(outside_checkout))
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


_INSTALLED_WHEEL_PROBE = r"""
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from polisyos.data_requirement import (
    DataRequirementCompiler as FacadeCompiler,
    write_data_requirement_compilation_report,
)
from polisyos.core.contracts.capability_resolution import RequirementToCapabilityQuery

site_packages = Path(os.environ["REQ01_INSTALLED_SITE"]).resolve()
product_root = Path(os.environ["REQ01_PRODUCT_ROOT"]).resolve()
package_root = (site_packages / "polisyos").resolve()
assert Path(importlib.import_module("polisyos").__file__).resolve().parent == package_root

compiler_module_name = "polisyos.data_requirement.compiler"
compiler_module = importlib.import_module(compiler_module_name)
assert compiler_module.DataRequirementCompiler is FacadeCompiler

retired_names = (
    "_data_families_from_obligation_graph",
    "_data_family_token_from_frontier_item",
    "_nested",
    "_normalised_family",
    "_slug_family",
    "_ordered_data_families",
    "_DATA_FAMILY_ORDER",
    "_digest",
)
family_rows = ({
    "scenario_family": "employment_panel",
    "construct": "employment_status",
    "producer_ref": "producer://req-01/test-employment-panel",
},)
assert compiler_module.construct_for_legacy_family("Employment Panel", rows=family_rows) == (
    "employment_status"
)
package_facade = importlib.import_module("polisyos.data_requirement")
for retired_name in retired_names:
    assert retired_name not in compiler_module.__all__
    assert retired_name not in package_facade.__all__
    try:
        getattr(compiler_module, retired_name)
    except AttributeError:
        pass
    else:
        raise AssertionError(f"retired compiler attribute still resolves: {retired_name}")
    try:
        legacy_import = __import__(compiler_module_name, fromlist=[retired_name])
        getattr(legacy_import, retired_name)
    except (AttributeError, ImportError):
        pass
    else:
        raise AssertionError(f"dynamic legacy import still resolves: {retired_name}")
    try:
        getattr(package_facade, retired_name)
    except AttributeError:
        pass
    else:
        raise AssertionError(f"retired package export still resolves: {retired_name}")


class RecordingResolver:
    def __init__(self, capability_index_ref):
        self.capability_index_ref = capability_index_ref
        self.queries = []

    def resolve(self, query):
        normalized = RequirementToCapabilityQuery.model_validate(query)
        self.queries.append(normalized)
        return SimpleNamespace(
            schema_version="policyos.capability_binding.test.v1",
            rule_version_ref="policyos.capability_binding.test-rule.v1",
            requirement_id=normalized.requirement_id,
            status="resolved",
            selected_capability_ref="capability://req-01/active-construct",
            construct_ref=normalized.construct,
            capability_index_ref=self.capability_index_ref,
            authority_level=normalized.authority_level,
            authority_envelope_result="candidate",
            binding_reasons=("recording resolver returned this test binding",),
            blocked_reasons=(),
            limitations=("fixture resolver; not source admission",),
            acquisition_strategies=(),
            rejected_alternatives=(),
            conflict_markers=(),
        )


ledger = {
    "claims": [{
        "claim_id": "claim:req-01-employment",
        "claim_family": "implementation",
        "claim_type": "implementation",
        "claim_use": "decision_support",
        "text": "Evaluate employment program implementation.",
        "metadata": {},
    }]
}
obligation_graph = {
    "blocking_frontier": [{
        "metadata": {"legacy_evidence_family_alias": "Employment Panel"},
    }]
}
resolver = RecordingResolver("capability-index://req-01-installed-wheel")
compiler = FacadeCompiler(
    capability_resolver=resolver,
    require_capability_index=True,
    scenario_family_construct_rows=family_rows,
)
report = compiler.compile_for_claim_ledger(
    run_id="run:req-01-installed-wheel",
    scenario_id="opaque-case-alpha",
    claim_ledger=ledger,
    facet_snapshots=(),
    obligation_graph=obligation_graph,
    authority_profile_refs=("authority_profile:req-01-test",),
)

assert len(resolver.queries) == 1
query = resolver.queries[0]
assert query.construct == "employment_status"
assert query.source_family_alias == "employment_panel"
assert query.authority_level == "governed_pilot"
assert report.metadata["capability_index_refs"] == (
    "capability-index://req-01-installed-wheel",
)
assert len(report.specs) == 1
spec = report.specs[0]
assert spec.claim_id == "claim:req-01-employment"
assert spec.required_data_families == ("employment_panel",)
assert spec.metadata["construct_ref"] == "employment_status"
assert spec.metadata["capability_index_ref"] == "capability-index://req-01-installed-wheel"
assert spec.metadata["binding_status"] == "resolved"
persisted_path = write_data_requirement_compilation_report(
    report,
    Path(os.environ["REQ01_REPORT_DIR"]),
)
persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
assert persisted["schema_version"] == "policyos.data_requirement_compilation.v1"
assert persisted["specs"][0]["required_data_families"] == ["employment_panel"]
assert persisted["specs"][0]["metadata"]["construct_ref"] == "employment_status"
assert persisted["metadata"]["capability_index_refs"] == [
    "capability-index://req-01-installed-wheel"
]

unknown_resolver = RecordingResolver("capability-index://req-01-negative")
unknown_report = FacadeCompiler(
    capability_resolver=unknown_resolver,
    require_capability_index=True,
    scenario_family_construct_rows=family_rows,
).compile_for_claim_ledger(
    run_id="run:req-01-unmapped-family",
    scenario_id="opaque-case-beta",
    claim_ledger=ledger,
    facet_snapshots=(),
    obligation_graph={
        "blocking_frontier": [{
            "metadata": {"legacy_evidence_family_alias": "unmapped external category"},
        }]
    },
    authority_profile_refs=("authority_profile:req-01-test",),
)
assert unknown_resolver.queries == []
assert unknown_report.specs == ()

for module_name, module in tuple(sys.modules.items()):
    if module_name == "polisyos" or module_name.startswith("polisyos."):
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if origin and origin.endswith(".py"):
            assert Path(origin).resolve().is_relative_to(package_root), (module_name, origin)
for entry in sys.path:
    if not entry:
        continue
    resolved = Path(entry).resolve()
    assert not resolved.is_relative_to(product_root / "src"), entry
    assert not resolved.is_relative_to(product_root / "tests"), entry
    assert not resolved.is_relative_to(product_root / "architecture"), entry
"""
