from __future__ import annotations

import hashlib
import json
import os
import shutil
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
    projection_payload: dict[str, Any] | None = None,
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
                "projection_payload": projection_payload or {"probe": projection_id},
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
    assert result["schema_version"] == ("policyos.runtime.governed_projection.owner_validation.v2")
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
    assert result["bound_projection_payload_hash"].startswith("sha256:")
    assert result["semantic_projection_hash"].startswith("sha256:")
    assert result["semantic_projection_hash_rule_version"]
    assert result["dependency_aggregate_identity"].startswith("sha256:")
    assert result["dependency_bindings"]


def test_canonical_confidence_ledger_binds_owner_payload_and_arithmetic() -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"
    )
    artifact = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))

    result = _run_worker(
        projection_id="confidence-ledger-risk-spend",
        repository_root=REPO_ROOT,
        component_bindings={relative_path: _sha256(REPO_ROOT / relative_path)},
        projection_payload=artifact["real_ledger_projection"],
    )

    assert result["status"] == "passed"
    assert result["issue_codes"] == []
    assert result["source_payload_equal"] is True
    assert result["registry_content_hash"] == artifact["registry_projection"][
        "registry_content_hash"
    ]
    assert result["registry_projection_hash"] == artifact["registry_projection"][
        "projection_hash"
    ]
    assert result["frozen_semantic_projection_hash"] == artifact[
        "real_ledger_projection"
    ]["projection_hash"]
    assert (result["recomputed_total_spend_numerator"], result["recomputed_total_spend_denominator"]) == (0, 1)
    assert (result["registry_delta_numerator"], result["registry_delta_denominator"]) == (1, 100)
    assert (
        "tools/quality/validation/check_layer3_gy_confidence_ledger.py"
        in result["dependency_bindings"]
    )


def test_owner_receipt_binds_canonical_semantic_hasher_source() -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_task0_audit/"
        "layer3_gy_engine_census.json"
    )

    result = _run_worker(
        projection_id="engine-census",
        repository_root=REPO_ROOT,
        component_bindings={relative_path: _sha256(REPO_ROOT / relative_path)},
    )

    assert result["status"] == "passed"
    assert "src/polisyos/pdc/_impl/gy_waist.py" in result["dependency_bindings"]


def test_n13a_fails_closed_without_canonical_recompute_catalog() -> None:
    census_relative = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    journal_relative = "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"

    result = _run_worker(
        projection_id="n13a-acquisition-census",
        repository_root=REPO_ROOT,
        component_bindings={
            census_relative: _sha256(REPO_ROOT / census_relative),
            journal_relative: _sha256(REPO_ROOT / journal_relative),
        },
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == ["owner_validator_dependency_missing_catalog"]


def test_n13a_canonical_recompute_rejects_corrupt_decisive_metric(
    tmp_path: Path,
) -> None:
    catalog_value = os.environ.get("POLISYOS_N13A_PRODUCTION_CATALOG")
    if not catalog_value:
        pytest.skip("production catalog is an explicit read-only recomputation witness")
    catalog = Path(catalog_value)
    if not catalog.is_file():
        pytest.skip("configured production catalog is absent")
    copied_paths = (
        "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json",
        "architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json",
        "architecture/policy_design_case/layer3_gy_value_gate_contract.json",
        "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json",
        "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json",
    )
    for relative_path in copied_paths:
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative_path, destination)
    catalog_relative = (
        "production_data/datasets_full_phase3full_20260327_183054/"
        "dataset_catalog.duckdb"
    )
    catalog_destination = tmp_path / catalog_relative
    catalog_destination.parent.mkdir(parents=True, exist_ok=True)
    catalog_destination.symlink_to(catalog)
    census_relative = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    journal_relative = "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"
    census_path = tmp_path / census_relative
    census = json.loads(census_path.read_text(encoding="utf-8"))
    census["metric_resolutions"][0]["binding_count"] += 1
    census_path.write_text(json.dumps(census, sort_keys=True), encoding="utf-8")

    result = _run_worker(
        projection_id="n13a-acquisition-census",
        repository_root=tmp_path,
        component_bindings={
            census_relative: _sha256(census_path),
            journal_relative: _sha256(tmp_path / journal_relative),
        },
        projection_payload={"metric_resolutions": census["metric_resolutions"]},
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == ["census_artifact_invalid"]


def test_owner_receipt_binds_cluster_validator_transitive_dependencies() -> None:
    relative_path = "architecture/policy_design_case/cluster_ownership_map.toml"

    result = _run_worker(
        projection_id="cluster-ownership",
        repository_root=REPO_ROOT,
        component_bindings={relative_path: _sha256(REPO_ROOT / relative_path)},
    )

    assert result["status"] == "passed"
    assert relative_path in result["dependency_bindings"]
    assert (
        "architecture/policy_design_case/capability_reality_report.json"
        in result["dependency_bindings"]
    )
    assert len(result["dependency_bindings"]) > 2


def test_projection_hash_is_computed_by_canonical_gy_hash_owner() -> None:
    relative_path = (
        "architecture/policy_design_case/layer3_gy_task0_audit/"
        "layer3_gy_engine_census.json"
    )
    bindings = {relative_path: _sha256(REPO_ROOT / relative_path)}
    first = _run_worker(
        projection_id="engine-census",
        repository_root=REPO_ROOT,
        component_bindings=bindings,
        projection_payload={"semantic": "bound", "reviewed_at": "2026-01-01T00:00:00Z"},
    )
    rebased = _run_worker(
        projection_id="engine-census",
        repository_root=REPO_ROOT,
        component_bindings=bindings,
        projection_payload={"semantic": "bound", "reviewed_at": "2099-01-01T00:00:00Z"},
    )

    assert first["bound_projection_payload_hash"] != rebased["bound_projection_payload_hash"]
    assert first["semantic_projection_hash"] == rebased["semantic_projection_hash"]


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


def test_n13a_journal_drift_cannot_bypass_missing_recompute_catalog(
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
    assert result["issue_codes"] == ["owner_validator_dependency_missing_catalog"]


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
        "tools.quality.validation.check_layer3_gy_confidence_ledger",
        "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
        "tools.quality.validation.check_layer3_gy_engine_census",
        "tools.quality.validation.check_layer3_gy_generation_cycle_disposition_ledger",
        "tools.quality.validation.check_layer3_gy_n10_cg1_l2_relation_census",
        "tools.quality.validation.check_layer3_gy_n13a_acquisition_census",
        "tools.quality.validation.check_layer3_gy_value_gate_contract",
        "tools.quality.validation.check_policy_design_case_capability_ratchet",
        "tools.quality.validation.check_policy_design_case_cluster_ownership_map",
        "tools.quality.validation.layer3_gy_n13a_acquisition_census",
    }

    assert imported.isdisjoint(forbidden)
