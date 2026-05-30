from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_NAME = "tools.quality.validation.repository_last_mile_inventory"
EXPECTED_FINDING_IDS = {f"LM-{index:03d}" for index in range(1, 27)}
REQUIRED_FINDING_FIELDS = {
    "path",
    "paths",
    "count",
    "kind",
    "owner",
    "package",
    "finding_id",
    "suggested_target",
    "current_status",
}


def _module():
    assert importlib.util.find_spec(MODULE_NAME) is not None, (
        "Phase 0.1 last-mile inventory module is missing"
    )
    return importlib.import_module(MODULE_NAME)


@lru_cache(maxsize=1)
def _inventory() -> dict[str, object]:
    return _module().collect_inventory(REPO_ROOT)


def test_inventory_reports_all_last_mile_findings_with_gate_fields() -> None:
    last_mile = _module()
    payload = _inventory()

    assert last_mile.validate_inventory(payload) == []
    assert payload["schema_version"] == last_mile.SCHEMA_VERSION
    assert payload["phase"] == "0.1"

    findings = payload["findings"]
    assert {finding["finding_id"] for finding in findings} == EXPECTED_FINDING_IDS

    for finding in findings:
        assert set(finding) >= REQUIRED_FINDING_FIELDS, finding["finding_id"]
        assert isinstance(finding["paths"], list), finding["finding_id"]
        assert finding["count"] == len(finding["paths"]), finding["finding_id"]
        assert finding["kind"], finding["finding_id"]
        assert finding["owner"], finding["finding_id"]
        assert finding["current_status"] in {
            "observed",
            "not_observed",
            "needs_review",
        }


def test_inventory_captures_phase_0_1_last_mile_regressions() -> None:
    by_id = {
        finding["finding_id"]: finding
        for finding in _inventory()["findings"]
    }

    scientist_loose = by_id["LM-001"]
    assert scientist_loose["kind"] == "package_root_loose_python"
    assert scientist_loose["package"] == "scientist"
    assert scientist_loose["count"] <= 1
    assert scientist_loose["paths"] in ([], ["src/polisyos/scientist/api.py"])

    single_file_shells = by_id["LM-002"]
    assert single_file_shells["kind"] == "single_file_shell_package"
    assert 0 < single_file_shells["count"] <= 12
    assert any(path.startswith("src/polisyos/fabric/") for path in single_file_shells["paths"])
    assert any(path.startswith("src/polisyos/ir/") for path in single_file_shells["paths"])
    assert "src/polisyos/fabric/extensions" in single_file_shells["paths"]
    assert "src/polisyos/ir/schemas" in single_file_shells["paths"]

    assert by_id["LM-003"]["paths"] == []
    assert by_id["LM-003"]["current_status"] == "not_observed"
    assert by_id["LM-004"]["paths"] == [
        "src/polisyos/scientist/orchestration",
    ]

    semantic_pairs = {
        tuple(pair["paths"])
        for pair in by_id["LM-005"]["metadata"]["semantic_pairs"]
    }
    assert semantic_pairs == set()
    assert by_id["LM-005"]["current_status"] == "not_observed"

    assert by_id["LM-015"]["kind"] == "cross_cutting_concern_duplicate"
    assert by_id["LM-015"]["count"] > 0
    assert by_id["LM-016"]["kind"] == "scientist_parallel_family"
    assert by_id["LM-016"]["count"] == 0
    assert by_id["LM-016"]["current_status"] == "not_observed"
    assert by_id["LM-017"]["kind"] == "repeated_cross_package_name"
    assert by_id["LM-017"]["count"] > 0


def test_inventory_records_sunset_metadata_and_schema_residue() -> None:
    by_id = {
        finding["finding_id"]: finding
        for finding in _inventory()["findings"]
    }

    for finding_id in ("LM-006", "LM-010", "LM-012"):
        finding = by_id[finding_id]
        assert "sunset" in finding
        assert set(finding["sunset"]) >= {
            "metadata_present",
            "sunset_date",
            "source",
        }

    assert by_id["LM-006"]["count"] == 0
    assert by_id["LM-006"]["current_status"] == "not_observed"
    assert by_id["LM-006"]["sunset"]["sunset_date"] is None
    assert by_id["LM-010"]["sunset"]["source"] is None
    assert by_id["LM-012"]["sunset"]["source"] == "frontend/README.md"
    for finding_id in ("LM-010", "LM-012"):
        sunset = by_id[finding_id]["sunset"]
        assert sunset["metadata_present"] == (sunset["sunset_date"] is not None)

    schemas = by_id["LM-022"]
    assert schemas["kind"] == "top_level_schema_python_cache_residue"
    assert all(path.startswith("schemas/") for path in schemas["paths"])


def test_inventory_excludes_generated_and_ignored_paths_from_product_findings() -> None:
    generated_prefixes = (
        ".venv/",
        "_build/",
        "_cache/",
        "apps/runtime-dashboard/node_modules/",
        "apps/runtime-reference-shell/node_modules/",
        "node_modules/",
    )
    allowed_generated_kinds = {
        "local_ignored_residue",
        "top_level_schema_python_cache_residue",
    }

    for finding in _inventory()["findings"]:
        if finding["kind"] in allowed_generated_kinds:
            continue
        assert not any(
            path.startswith(generated_prefixes) for path in finding["paths"]
        ), finding["finding_id"]


def test_inventory_keeps_local_ignored_residue_out_of_committed_baseline(
    monkeypatch,
) -> None:
    last_mile = _module()
    monkeypatch.setattr(
        last_mile,
        "_collect_local_ignored_residue",
        lambda _repo_root: ["_build/phase7-local-junk-synthetic"],
    )

    default = last_mile.collect_inventory(REPO_ROOT)
    with_local = last_mile.collect_inventory(
        REPO_ROOT,
        include_local_ignored_residue=True,
    )

    default_lm009 = next(
        finding for finding in default["findings"] if finding["finding_id"] == "LM-009"
    )
    local_lm009 = next(
        finding for finding in with_local["findings"] if finding["finding_id"] == "LM-009"
    )
    assert default_lm009["paths"] == []
    assert local_lm009["paths"] == ["_build/phase7-local-junk-synthetic"]


def test_json_output_cli_and_committed_baseline_are_machine_readable(tmp_path: Path) -> None:
    output_path = tmp_path / "inventory.json"

    completed = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_last_mile_inventory.py",
            "--json-output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "last-mile inventory" in completed.stdout.lower()
    generated = json.loads(output_path.read_text(encoding="utf-8"))
    baseline = json.loads(
        (
            REPO_ROOT
            / "architecture/baselines/repository_best_in_class_last_mile/inventory.json"
        ).read_text(encoding="utf-8")
    )
    assert generated == baseline
