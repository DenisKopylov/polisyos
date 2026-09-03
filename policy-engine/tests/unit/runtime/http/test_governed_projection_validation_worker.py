from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.fabric.data_plane import content_sha256
from polisyos.runtime.http.services import (
    governed_projection_validation_worker as worker_module,
)
from polisyos.runtime.http.services import (
    governed_projections as governed_module,
)
from polisyos.runtime.http.services.acquisition_surface_projection import (
    build_acquisition_growth_projection,
)

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


def _acquisition_growth_request(
    root: Path = REPO_ROOT,
) -> tuple[dict[str, str], dict[str, Any]]:
    n13a_paths = (
        "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json",
        "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json",
        "architecture/policy_design_case/"
        "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json",
    )
    lifecycle_path = "architecture/policy_design_case/layer3_gy_n13b_lifecycle_manifest.json"
    lifecycle = json.loads((root / lifecycle_path).read_text(encoding="utf-8"))
    registered_paths = tuple(row["path"] for row in lifecycle["registrations"])
    paths = tuple(dict.fromkeys((*n13a_paths, *registered_paths)))
    bindings = {path: _sha256(root / path) for path in paths}

    def load(path: str) -> dict[str, Any]:
        value = json.loads((root / path).read_text(encoding="utf-8"))
        assert isinstance(value, dict)
        return value

    payload = build_acquisition_growth_projection(
        census=load(n13a_paths[0]),
        journal=load(n13a_paths[1]),
        carrier_liveness=load(n13a_paths[2]),
        executor_contract=load(
            "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
        ),
        lifecycle_manifest=lifecycle,
        reentry_trace=load("architecture/policy_design_case/layer3_gy_n13b_reentry_trace.json"),
    ).model_dump(mode="json")
    return bindings, payload


def _copy_acquisition_growth_inputs(destination: Path) -> None:
    bindings, _ = _acquisition_growth_request()
    for relative_path in bindings:
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative_path, target)
    generated = destination / "architecture/generated_artifacts.toml"
    generated.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / "architecture/generated_artifacts.toml", generated)


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


def test_value_gate_worker_projects_the_validated_foundry_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The isolated bridge receives one N8/Foundry binding, not a local resolver."""

    value_path = "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
    companion_path = (
        "architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json"
    )
    monkeypatch.setitem(worker_module._VALIDATORS, "value-gate", lambda _root: [])
    companion = json.loads((REPO_ROOT / companion_path).read_text(encoding="utf-8"))
    result = worker_module._validate_request(
        {
            "projection_id": "value-gate",
            "repository_root": str(REPO_ROOT),
            "component_bindings": {
                value_path: _sha256(REPO_ROOT / value_path),
                companion_path: _sha256(REPO_ROOT / companion_path),
            },
            "projection_payload": {"probe": "value-gate"},
        }
    )

    assert result["status"] == "passed"
    diagnostic = result["related_dependency_diagnostic"]
    assert diagnostic["decision_role"] == "ambient_non_decisive"
    assert diagnostic["predicate_class"] == "recomputed"
    assert diagnostic["receipt_state"] == "received"
    assert diagnostic["status"] in {"pass", "fail", "not_established"}
    assert diagnostic["profile"] == companion["profile_discriminant"]


def test_value_gate_worker_diagnostic_exception_cannot_change_governing_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken ambient probe becomes non-receipt, never owner-validation failure."""

    value_path = "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
    monkeypatch.setitem(worker_module._VALIDATORS, "value-gate", lambda _root: [])

    def broken_diagnostic(_root: Path) -> dict[str, Any]:
        raise RuntimeError("ambient probe failed")

    monkeypatch.setattr(worker_module, "_value_dependency_diagnostic", broken_diagnostic)
    result = worker_module._validate_request(
        {
            "projection_id": "value-gate",
            "repository_root": str(REPO_ROOT),
            "component_bindings": {value_path: _sha256(REPO_ROOT / value_path)},
            "projection_payload": {"probe": "value-gate"},
        }
    )

    assert result["status"] == "passed"
    assert result["issue_codes"] == []
    assert result["related_dependency_diagnostic"] == {
        "artifact_content_ref": None,
        "authority_boundary": None,
        "decision_role": "ambient_non_decisive",
        "first_case": None,
        "predicate_class": None,
        "profile": None,
        "receipt_state": "not_received",
        "status": "not_established",
    }


def test_value_gate_worker_maps_owner_diagnostic_nonreceipt_to_not_established(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

    companion_path = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json"
    )
    companion = n8.FoundryDependencyDiscriminantCompanion.model_validate_json(
        companion_path.read_bytes()
    )
    monkeypatch.setattr(
        n8,
        "validate_foundry_dependency_discriminant",
        lambda **_kwargs: SimpleNamespace(
            content_ref=companion.content_ref,
            profile_discriminant=companion.profile_discriminant,
            ambient_findings=(
                {
                    "code": "dependency_environment_diagnostic_not_received",
                    "decision_role": "ambient_non_decisive",
                },
            ),
        ),
    )

    diagnostic = worker_module._value_dependency_diagnostic(REPO_ROOT)

    assert diagnostic["receipt_state"] == "received"
    assert diagnostic["status"] == "not_established"
    assert diagnostic["first_case"] is None


def test_acquisition_growth_has_genuine_recomputing_owner_validator() -> None:
    bindings, payload = _acquisition_growth_request()

    result = _run_worker(
        projection_id="acquisition-growth",
        repository_root=REPO_ROOT,
        component_bindings=bindings,
        projection_payload=payload,
    )

    assert result["status"] == "passed"
    assert result["issue_codes"] == []


def test_acquisition_growth_publishes_the_registered_executed_validator() -> None:
    definition = governed_module._DEFINITION_BY_ID[governed_module.ProjectionId.ACQUISITION_GROWTH]
    module_name, separator, attribute = definition.owner_validator_id.partition(":")
    assert separator == ":"
    resolved = getattr(importlib.import_module(module_name), attribute, None)
    assert callable(resolved)

    assert worker_module._VALIDATOR_METADATA["acquisition-growth"][0] == (
        definition.owner_validator_id
    )
    assert worker_module._VALIDATORS["acquisition-growth"] is resolved

    bindings, payload = _acquisition_growth_request()
    result = _run_worker(
        projection_id="acquisition-growth",
        repository_root=REPO_ROOT,
        component_bindings=bindings,
        projection_payload=payload,
    )
    assert result["status"] == "passed"
    assert (
        "tools/quality/validation/layer3_gy_n13b_acquisition_contract.py"
        in result["dependency_bindings"]
    )


def test_acquisition_growth_rejects_payload_drift_with_markers_intact() -> None:
    bindings, payload = _acquisition_growth_request()
    mutated = copy.deepcopy(payload)
    mutated["summary"]["backlog_count"] += 1

    result = _run_worker(
        projection_id="acquisition-growth",
        repository_root=REPO_ROOT,
        component_bindings=bindings,
        projection_payload=mutated,
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == ["acquisition_growth_projection_recompute_mismatch"]


@pytest.mark.parametrize("mutation", ["lifecycle_hash", "source_schema"])
def test_acquisition_growth_rejects_owner_contract_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    canonical_bindings, payload = _acquisition_growth_request()
    _copy_acquisition_growth_inputs(tmp_path)
    if mutation == "lifecycle_hash":
        target = tmp_path / "architecture/policy_design_case/layer3_gy_n13b_lifecycle_manifest.json"
        source = json.loads(target.read_text(encoding="utf-8"))
        row = next(
            item
            for item in source["registrations"]
            if item["registration_status"] == "content_bound"
        )
        row["byte_sha256"] = "sha256:" + "0" * 64
        expected_issue = "acquisition_growth_lifecycle_content_binding_mismatch"
    else:
        target = tmp_path / "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
        source = json.loads(target.read_text(encoding="utf-8"))
        source["schema_version"] = "policyos.invalid-but-present.v1"
        expected_issue = "acquisition_growth_source_schema_mismatch"
    target.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
    bindings = {path: _sha256(tmp_path / path) for path in canonical_bindings}

    result = _run_worker(
        projection_id="acquisition-growth",
        repository_root=tmp_path,
        component_bindings=bindings,
        projection_payload=payload,
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == [expected_issue]


def test_acquisition_growth_rejects_replaced_owner_registration(
    tmp_path: Path,
) -> None:
    """A valid-shaped replacement cannot shrink the owner-derived family."""

    _copy_acquisition_growth_inputs(tmp_path)
    lifecycle_path = (
        tmp_path / "architecture/policy_design_case/layer3_gy_n13b_lifecycle_manifest.json"
    )
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    replacement_path = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    replaced = next(
        row for row in lifecycle["registrations"] if row["registration_status"] == "content_bound"
    )
    replacement_bytes = (tmp_path / replacement_path).read_bytes()
    replaced.update(
        {
            "path": replacement_path,
            "role": "receipt",
            "byte_sha256": f"sha256:{hashlib.sha256(replacement_bytes).hexdigest()}",
            "byte_size": len(replacement_bytes),
        }
    )
    lifecycle["registrations"] = sorted(
        lifecycle["registrations"],
        key=lambda row: row["path"],
    )
    identity = {key: value for key, value in lifecycle.items() if key != "manifest_sha256"}
    identity["registrations"] = [
        {
            "path": row["path"],
            "role": row["role"],
            "registration_status": row["registration_status"],
        }
        for row in lifecycle["registrations"]
    ]
    lifecycle["manifest_sha256"] = content_sha256(identity)
    lifecycle_path.write_text(json.dumps(lifecycle, sort_keys=True), encoding="utf-8")
    bindings, payload = _acquisition_growth_request(tmp_path)
    assert len(bindings) == 45

    result = _run_worker(
        projection_id="acquisition-growth",
        repository_root=tmp_path,
        component_bindings=bindings,
        projection_payload=payload,
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == ["acquisition_growth_owner_denominator_mismatch"]


def test_acquisition_growth_fails_when_validator_property_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Markers remain registered while the actual worker validator is removed."""

    bindings, payload = _acquisition_growth_request()
    monkeypatch.delitem(worker_module._VALIDATORS, "acquisition-growth")

    result = worker_module._validate_request(
        {
            "projection_id": "acquisition-growth",
            "repository_root": str(REPO_ROOT),
            "component_bindings": bindings,
            "projection_payload": payload,
        }
    )

    assert result["status"] == "failed"
    assert result["issue_codes"] == ["owner_validator_unregistered"]


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
