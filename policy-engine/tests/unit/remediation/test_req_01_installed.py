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
            "--no-build-isolation",
            "--python",
            sys.executable,
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
    record_property(
        "req01_wheel_build_command",
        "uv --offline build --no-build-isolation --python <current-test-interpreter> --wheel --out-dir <tmp>",
    )
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
    child_environment["REQ01_INSTALLED_SITE"] = str(installed_site)
    child_environment["REQ01_PRODUCT_ROOT"] = str(PRODUCT_ROOT.resolve())
    child_environment["REQ01_REPORT_DIR"] = str(outside_checkout / "compiler-reports")
    child_environment["REQ01_V1_REPORT_PATH"] = str(
        PRODUCT_ROOT
        / "docs/research/e02-cloud-test-plan/implementation-handoffs/A/compiler-full/compiler-readback.json"
    )
    child_environment["REQ01_V2_REPORT_PATH"] = str(
        PRODUCT_ROOT / "tests/_data/data_requirement/req01/pre-domain-source-replay-v2.json"
    )

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
    summary_lines = [
        line for line in result.stdout.splitlines() if line.startswith("REQ01_INSTALLED_PROBE=")
    ]
    assert len(summary_lines) == 1, result.stdout + "\n" + result.stderr
    record_property("req01_installed_wheel_probe_summary", summary_lines[0].partition("=")[2])


_INSTALLED_WHEEL_PROBE = r"""
import importlib
import hashlib
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
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver

site_packages = Path(os.environ["REQ01_INSTALLED_SITE"]).resolve()
product_root = Path(os.environ["REQ01_PRODUCT_ROOT"]).resolve()
package_root = (site_packages / "polisyos").resolve()
assert Path(importlib.import_module("polisyos").__file__).resolve().parent == package_root

runtime_module_names = (
    "polisyos.runtime.http.routes.acquisitions",
    "polisyos.runtime.http.routes.runs",
    "polisyos.runtime.http.services.acquisition_action_service",
    "polisyos.runtime.http.services.control.generation_cycle",
    "polisyos.runtime.http.services.control.run_lifecycle",
    "polisyos.runtime.http.services.control_plane_store",
    "polisyos.runtime.quality.acquisition_evaluation_dispatch",
    "polisyos.runtime.quality.acquisition_evaluation_history",
    "polisyos.runtime.quality.acquisition_route_loop",
    "polisyos.runtime.quality.candidate_source_basis",
    "polisyos.runtime.quality.generation_cycle",
    "polisyos.runtime.quality.recursive_generation_cycle",
)
runtime_modules = {
    module_name: importlib.import_module(module_name) for module_name in runtime_module_names
}
for module_name, module in runtime_modules.items():
    origin = getattr(getattr(module, "__spec__", None), "origin", None)
    assert origin is not None and Path(origin).resolve().is_relative_to(package_root), (
        module_name,
        origin,
        package_root,
    )

route_loop_module = runtime_modules["polisyos.runtime.quality.acquisition_route_loop"]
generation_cycle_module = runtime_modules["polisyos.runtime.quality.generation_cycle"]
assert (
    route_loop_module._n7_generic_fallback_source_record_matches
    is generation_cycle_module._n7_generic_fallback_source_record_matches
)

compiler_module_name = "polisyos.data_requirement.compiler"
compiler_module = importlib.import_module(compiler_module_name)
package_facade = importlib.import_module("polisyos.data_requirement")
model_module = importlib.import_module("polisyos.data_requirement._impl.models")
for export_name in (
    "DataRequirementCompiler",
    "ScenarioDomainInputError",
    "compile_data_requirements_for_scenario",
    "compiled_requirements_for_world_slot",
    "parse_data_requirement_compilation_report",
    "data_requirement_compilation_audit_surface",
    "write_data_requirement_compilation_report",
):
    assert getattr(package_facade, export_name) is getattr(compiler_module, export_name), (
        export_name,
        "public facade must preserve the canonical compiler/helper identity",
    )
for export_name in (
    "CapabilityBindingSnapshot",
    "CapabilityRequirementResolution",
    "DataRequirementBasisResolution",
    "DataRequirementCompilationReport",
    "DataRequirementCompilationReportV1",
    "DataRequirementSpec",
):
    assert getattr(package_facade, export_name) is getattr(model_module, export_name), (
        export_name,
        "public DTO facade must preserve the canonical model identity",
    )
assert FacadeCompiler is compiler_module.DataRequirementCompiler

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

assert type(report) is package_facade.DataRequirementCompilationReport
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
assert type(spec) is package_facade.DataRequirementSpec
assert spec.claim_id == "claim:req-01-employment"
assert spec.required_data_families == ("employment_panel",)
assert spec.metadata["construct_ref"] == "employment_status"
assert spec.metadata["capability_index_ref"] == "capability-index://req-01-installed-wheel"
assert spec.metadata["binding_status"] == "resolved"
persisted_path = write_data_requirement_compilation_report(
    report,
    Path(os.environ["REQ01_REPORT_DIR"]),
)
persisted_bytes = persisted_path.read_bytes()
persisted = json.loads(persisted_bytes)
assert persisted["schema_version"] == "policyos.data_requirement_compilation.v2"
assert persisted["specs"][0]["required_data_families"] == ["employment_panel"]
assert persisted["specs"][0]["metadata"]["construct_ref"] == "employment_status"
assert persisted["metadata"]["capability_index_refs"] == [
    "capability-index://req-01-installed-wheel"
]
parsed_report = package_facade.parse_data_requirement_compilation_report(persisted_bytes)
assert type(parsed_report) is package_facade.DataRequirementCompilationReport
assert parsed_report.model_dump(mode="json") == report.model_dump(mode="json")
audit_surface = package_facade.data_requirement_compilation_audit_surface(persisted_bytes)
assert audit_surface["surface"] == "data_requirement.audit_surface"
assert audit_surface["summary"]["requirement_count"] == 1
assert audit_surface["summary"]["required_data_families"] == ["employment_panel"]

# Read/write the tracked historical reports through the installed package. The V2
# artifact is a historical-source replay, not production provenance or authority.
v1_path = Path(os.environ["REQ01_V1_REPORT_PATH"])
v1_bytes = v1_path.read_bytes()
assert hashlib.sha256(v1_bytes).hexdigest() == (
    "d1d31eef31ddf6c0781d601be7325144e3f36292142abac20e5dd4413fb481d2"
)
v1_report = package_facade.parse_data_requirement_compilation_report(v1_bytes)
assert type(v1_report) is package_facade.DataRequirementCompilationReportV1
assert v1_report.original_bytes == v1_bytes
assert v1_report.requirement_basis.state == "not_established"
v1_surface = package_facade.data_requirement_compilation_audit_surface(v1_bytes)
assert v1_surface["schema_version"] == v1_report.schema_version
assert v1_surface["run_id"] == v1_report.run_id
assert v1_surface["metadata"] == v1_report.metadata
assert v1_surface["requirement_basis"]["state"] == "not_established"
v1_written = package_facade.write_data_requirement_compilation_report(
    v1_report, Path(os.environ["REQ01_REPORT_DIR"]) / "historical-v1"
)
assert v1_written.read_bytes() == v1_bytes

v2_path = Path(os.environ["REQ01_V2_REPORT_PATH"])
v2_bytes = v2_path.read_bytes()
v2_digest = hashlib.sha256(v2_bytes).hexdigest()
assert len(v2_bytes) == 3590
assert v2_digest == "1e816f7da651d4694aa29e7b52d0ec06d184fe8f788a01e3229aa215a232dd79"
v2_document = json.loads(v2_bytes)
v2_report = package_facade.parse_data_requirement_compilation_report(v2_bytes)
assert type(v2_report) is package_facade.DataRequirementCompilationReport
assert v2_report.original_bytes == v2_bytes
assert v2_report.scenario_id == "opaque:req01-pre-domain-v2-replay"
assert v2_report.input_content_hash == v2_document["input_content_hash"]
assert v2_report.rule_version_refs == ("policyos.data_requirement.compiler.v2",)
assert "scenario_domain_resolution" not in v2_report.metadata
assert v2_report.requirement_basis.state == "not_established"
assert v2_report.requirement_basis.basis_grade == "not_established"
assert v2_report.requirement_basis.reason_codes == ("legacy_report_basis_not_carried",)
assert not v2_report.specs
(v2_resolution,) = v2_report.capability_requirement_resolutions
assert v2_resolution.state == "not_established"
assert v2_resolution.scope_profile_id == "scope:req01-pre-domain-v2-replay:v1"
v2_surface = package_facade.data_requirement_compilation_audit_surface(v2_bytes)
assert v2_surface["schema_version"] == v2_report.schema_version
assert v2_surface["input_content_hash"] == v2_report.input_content_hash
assert v2_surface["rule_version_refs"] == list(v2_report.rule_version_refs)
assert v2_surface["metadata"] == v2_report.metadata
assert v2_surface["requirement_basis"]["state"] == "not_established"
v2_written = package_facade.write_data_requirement_compilation_report(
    v2_report, Path(os.environ["REQ01_REPORT_DIR"]) / "historical-v2"
)
assert v2_written.read_bytes() == v2_bytes
assert v2_written.name == f"sha256-{v2_digest}-data-requirements.json"
v2_written.write_bytes(b"tampered historical V2 report")
try:
    package_facade.write_data_requirement_compilation_report(
        v2_report, Path(os.environ["REQ01_REPORT_DIR"]) / "historical-v2"
    )
except ValueError as exc:
    assert "data_requirement_report_content_conflict" in str(exc)
else:
    raise AssertionError("installed writer accepted tampered historical V2 bytes")
assert v2_written.read_bytes() == b"tampered historical V2 report"
assert v2_path.read_bytes() == v2_bytes

# Run the installed public scenario helper with the exact declared domain
# spelling. The lexical text deliberately mentions fiscal policy so a topic
# guess cannot masquerade as honoring the declared domain.
education_report = package_facade.compile_data_requirements_for_scenario(
    {
        "scenario_id": "req-01-installed-education-alias",
        "request": "Evaluate a fiscal intervention for education policy.",
        "domain": "Education Policy",
    }
)
assert type(education_report) is package_facade.DataRequirementCompilationReport
education_domain = education_report.metadata["scenario_domain_resolution"]
assert education_domain["raw_inputs"] == {"domain": "Education Policy"}
assert education_domain["canonical_domain"] == "education"
assert education_domain["canonical_domain"] != "fiscal"
assert education_domain["status"] == "resolved"
assert education_domain["rule_version_ref"] in education_report.rule_version_refs
education_path = package_facade.write_data_requirement_compilation_report(
    education_report,
    Path(os.environ["REQ01_REPORT_DIR"]) / "education-alias",
)
education_bytes = education_path.read_bytes()
parsed_education = package_facade.parse_data_requirement_compilation_report(education_bytes)
assert type(parsed_education) is package_facade.DataRequirementCompilationReport
assert parsed_education.metadata["scenario_domain_resolution"] == education_domain
education_surface = package_facade.data_requirement_compilation_audit_surface(education_bytes)
assert education_surface["metadata"]["scenario_domain_resolution"] == education_domain

# Exercise the canonical world-slot helper on a real governed candidate
# discovery. Its source rows are a repository fixture; discovery stays
# candidate-only and does not claim source admission or empirical authority.
governed_resolver = RequirementToCapabilityResolver.governed_fixture(repo_root=product_root)
governed_rows_path = (
    product_root / "architecture/policy_design_case/layer2_s3_governed_capability_rows.json"
)
governed_rows = json.loads(governed_rows_path.read_text(encoding="utf-8"))
world_slot_report = FacadeCompiler(
    capability_resolver=governed_resolver,
    require_capability_index=True,
    scenario_family_construct_rows=governed_rows["scenario_family_construct_rows"],
).compile_for_scenario(
    {
        "scenario_id": "req-01-installed-world-slot",
        "text": "Evaluate annual nominal GDP for the national economy.",
        "domain": "fiscal",
        "scope_profile": {
            "profile_id": "scope:req-01-installed-gdp-usa-2024:v1",
            "jurisdiction": "USA",
            "population": "national_economy",
            "entity_scope": "country",
            "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
            "time_role": "observation_time",
            "granularity": "annual",
            "required_constructs": ["economic.gdp"],
        },
        "expected_evidence_contract": {"admissible_data_source_families": ["global.gdp"]},
    }
)
assert type(world_slot_report) is package_facade.DataRequirementCompilationReport
assert [item.required_data_families for item in world_slot_report.specs] == [
    ("wdi_nominal_gdp_annual",)
]
world_slot_matches = package_facade.compiled_requirements_for_world_slot(
    world_slot="global.gdp",
    specs=world_slot_report.specs,
    capability_resolutions=world_slot_report.capability_requirement_resolutions,
)
assert len(world_slot_matches) == 1
assert world_slot_matches[0] is world_slot_report.specs[0]
assert world_slot_matches[0].metadata["construct_ref"] == "construct:economic.gdp"
(world_slot_resolution,) = world_slot_report.capability_requirement_resolutions
assert type(world_slot_resolution) is package_facade.CapabilityRequirementResolution
assert world_slot_resolution.candidate_discovery is not None
assert world_slot_resolution.candidate_discovery.satisfies_claim_evidence is False
assert world_slot_resolution.candidate_discovery.requires_native_source_admission is True
assert governed_resolver.resolve(world_slot_resolution.query).satisfies_claim_evidence is False

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
        if origin and origin not in {"built-in", "frozen"}:
            assert Path(origin).resolve().is_relative_to(package_root), (module_name, origin)
for entry in sys.path:
    if not entry:
        continue
    resolved = Path(entry).resolve()
    assert not resolved.is_relative_to(product_root / "src"), entry
    assert not resolved.is_relative_to(product_root / "tests"), entry
    assert not resolved.is_relative_to(product_root / "architecture"), entry

print(
    "REQ01_INSTALLED_PROBE="
    + json.dumps(
        {
            "education_domain": education_domain["canonical_domain"],
            "education_rule_version": education_domain["rule_version_ref"],
            "helper_world_slot": "global.gdp",
            "helper_requirement_ids": [item.requirement_id for item in world_slot_matches],
            "candidate_discovery_satisfies_claim_evidence": (
                world_slot_resolution.candidate_discovery.satisfies_claim_evidence
            ),
            "historical_v1_sha256": hashlib.sha256(v1_bytes).hexdigest(),
            "historical_v2_basis": v2_report.requirement_basis.state,
            "historical_v2_sha256": v2_digest,
            "installed_compiler_module": str(Path(compiler_module.__file__).resolve()),
            "report_schema": parsed_report.schema_version,
            "report_sha256": hashlib.sha256(persisted_bytes).hexdigest(),
            "runtime_modules": sorted(runtime_modules),
            "wheel_package_root": str(package_root),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
)
"""
