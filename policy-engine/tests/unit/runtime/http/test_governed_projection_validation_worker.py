from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKER_PATH = (
    REPO_ROOT / "src/polisyos/runtime/http/services/governed_projection_validation_worker.py"
)


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _write_bytes(root: Path, relative_path: str, raw: bytes) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _run_worker(
    *,
    projection_id: str,
    repository_root: Path,
    component_bindings: dict[str, str],
) -> dict[str, Any]:
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    pythonpath = str(REPO_ROOT / "src")
    if existing_pythonpath:
        pythonpath = f"{pythonpath}{os.pathsep}{existing_pythonpath}"
    environment["PYTHONPATH"] = pythonpath
    completed = subprocess.run(
        [sys.executable, str(WORKER_PATH)],
        cwd=REPO_ROOT,
        env=environment,
        input=json.dumps(
            {
                "projection_id": projection_id,
                "repository_root": str(repository_root),
                "component_bindings": component_bindings,
            }
        ),
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert len(lines) == 1, completed.stdout
    result = json.loads(lines[0])
    assert result["schema_version"] == ("policyos.runtime.governed_projection.owner_validation.v1")
    assert result["projection_id"] == projection_id
    assert result["bound_source_identities"] == dict(sorted(component_bindings.items()))
    assert result["bound_aggregate_identity"].startswith("sha256:")
    assert result["validator_id"]
    assert result["validator_version"]
    return result


def _canonical_proving_ground_bindings() -> dict[str, str]:
    manifest_relative = "tests/fixtures/universal-corpus/manifest.json"
    manifest_path = REPO_ROOT / manifest_relative
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bindings = {manifest_relative: _sha256(manifest_path)}
    for fixture in manifest["fixtures"]:
        relative_path = (Path(manifest_relative).parent / str(fixture["path"])).as_posix()
        bindings[relative_path] = _sha256(REPO_ROOT / relative_path)
    return bindings


def test_all_null_capability_report_fails_owner_validation(tmp_path: Path) -> None:
    relative_path = "architecture/policy_design_case/capability_reality_report.json"
    source = _write_bytes(
        tmp_path,
        relative_path,
        json.dumps(
            {
                "schema_version": None,
                "tool": None,
                "capability_claim_inputs": None,
                "summary": None,
                "debt_algebra": None,
                "ratchet_templates": None,
                "issues": None,
                "ratchet_integrity_status": None,
            },
            sort_keys=True,
        ).encode(),
    )

    result = _run_worker(
        projection_id="capability-reality",
        repository_root=tmp_path,
        component_bindings={relative_path: _sha256(source)},
    )

    assert result["status"] == "failed"
    assert "capability_ratchet_schema_version_invalid" in result["issue_codes"]


@pytest.mark.parametrize(
    ("projection_id", "component_bindings"),
    [
        (
            "engine-census",
            {
                "architecture/policy_design_case/layer3_gy_task0_audit/"
                "layer3_gy_engine_census.json": _sha256(
                    REPO_ROOT / "architecture/policy_design_case/layer3_gy_task0_audit/"
                    "layer3_gy_engine_census.json"
                )
            },
        ),
        (
            "n13a-acquisition-census",
            {
                "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json": _sha256(
                    REPO_ROOT / "architecture/policy_design_case/"
                    "layer3_gy_n13a_acquisition_census.json"
                ),
                "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json": _sha256(
                    REPO_ROOT / "architecture/policy_design_case/"
                    "layer3_gy_n13a_live_probe_journal.json"
                ),
            },
        ),
        ("legacy-proving-ground", _canonical_proving_ground_bindings()),
    ],
)
def test_canonical_owner_sources_validate(
    projection_id: str,
    component_bindings: dict[str, str],
) -> None:
    result = _run_worker(
        projection_id=projection_id,
        repository_root=REPO_ROOT,
        component_bindings=component_bindings,
    )

    assert result["status"] == "passed"
    assert result["issue_codes"] == []


def test_component_hash_mismatch_fails_before_owner_validator(tmp_path: Path) -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json"
    )
    _write_bytes(tmp_path, relative_path, b"not-json")

    result = _run_worker(
        projection_id="engine-census",
        repository_root=tmp_path,
        component_bindings={relative_path: f"sha256:{'0' * 64}"},
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == ["component_hash_mismatch"]


def test_n13a_census_fails_when_bound_journal_semantics_drift(
    tmp_path: Path,
) -> None:
    census_relative = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    journal_relative = "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"
    census = _write_bytes(
        tmp_path,
        census_relative,
        (REPO_ROOT / census_relative).read_bytes(),
    )
    journal_payload = json.loads((REPO_ROOT / journal_relative).read_text())
    journal_payload["selection_plan"]["candidates"][0]["binding_confidence"] = 0.91
    journal = _write_bytes(
        tmp_path,
        journal_relative,
        json.dumps(journal_payload, sort_keys=True).encode(),
    )

    result = _run_worker(
        projection_id="n13a-acquisition-census",
        repository_root=tmp_path,
        component_bindings={
            census_relative: _sha256(census),
            journal_relative: _sha256(journal),
        },
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == ["journal_semantic_content_hash_mismatch"]


def test_normal_projection_import_does_not_import_owner_validators() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO_ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, sys; "
                "import polisyos.runtime.http.services.governed_projections; "
                "print(json.dumps(sorted(sys.modules)))"
            ),
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    imported = set(json.loads(completed.stdout))
    forbidden = {
        "polisyos.corpus._impl.loaders",
        "polisyos.runtime.http.services.governed_projection_validation_worker",
        "polisyos.runtime.quality.proving_ground.pre_adapter_grounding_inventory",
        "tools.quality.validation.check_layer3_gy_acquisition_contract",
        "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
        "tools.quality.validation.check_layer3_gy_engine_census",
        "tools.quality.validation.check_layer3_gy_generation_cycle_disposition_ledger",
        "tools.quality.validation.check_layer3_gy_n10_cg1_l2_relation_census",
        "tools.quality.validation.check_layer3_gy_value_gate_contract",
        "tools.quality.validation.check_policy_design_case_capability_ratchet",
        "tools.quality.validation.check_policy_design_case_cluster_ownership_map",
        "tools.quality.validation.layer3_gy_n13a_acquisition_census",
    }

    assert imported.isdisjoint(forbidden)
