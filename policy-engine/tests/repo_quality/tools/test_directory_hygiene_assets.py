from __future__ import annotations

import json
import os
import time
from pathlib import Path

from tools.devx.workspace import clean_local_reports
from tools.quality.validation import directory_hygiene_assets

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_directory_hygiene_asset_report_has_distinct_classes_and_clean_contract(
    tmp_path: Path,
) -> None:
    report = directory_hygiene_assets.build_report(REPO_ROOT)

    assert report["phase"] == "2.9"
    assert report["mode"] == "report_only"
    assert report["contract_error_count"] == 0

    classes = report["classes"]["counts"]
    for class_id in (
        "product_seed_assets",
        "test_fixtures",
        "golden_records",
        "examples_tutorial_assets",
        "local_reports",
        "generated_benchmark_reports",
        "source_adjacent_residue",
        "ambiguous_fixture_directories",
    ):
        assert class_id in classes

    budget = report["budgets"]["product_assets"]
    assert budget["file_count"] >= 1
    assert budget["total_bytes"] <= budget["max_total_bytes"]
    assert all(item["bytes"] <= budget["max_file_bytes"] for item in budget["files"])

    output = tmp_path / "directory-hygiene-assets.json"
    assert (
        directory_hygiene_assets.run_cli(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--fail-on-contract-errors",
                "--json-output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "reported"


def test_clean_local_reports_dry_run_and_apply_keep_audits_manual(tmp_path: Path) -> None:
    repo_root = tmp_path
    stale_time = time.time() - (45 * 24 * 60 * 60)

    old_report = repo_root / ".polisyos" / "reports" / "old" / "summary.json"
    old_report.parent.mkdir(parents=True)
    old_report.write_text("{}", encoding="utf-8")
    os.utime(old_report.parent, (stale_time, stale_time))

    fresh_report = repo_root / ".polisyos" / "reports" / "fresh" / "summary.json"
    fresh_report.parent.mkdir(parents=True)
    fresh_report.write_text("{}", encoding="utf-8")

    audit = repo_root / ".polisyos" / "audits" / "incident" / "audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text("{}", encoding="utf-8")
    os.utime(audit.parent, (stale_time, stale_time))

    pycache = repo_root / "src" / "polisyos" / "demo" / "__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "demo.pyc").write_bytes(b"cache")

    egg_info = repo_root / "src" / "policy_engine.egg-info"
    egg_info.mkdir(parents=True)
    (egg_info / "PKG-INFO").write_text("metadata", encoding="utf-8")

    ds_store = repo_root / "tests" / ".DS_Store"
    ds_store.parent.mkdir(parents=True, exist_ok=True)
    ds_store.write_bytes(b"finder")

    empty_fixture_raw = repo_root / "src" / "polisyos" / "demo" / "fixtures" / "raw"
    empty_fixture_raw.mkdir(parents=True)

    plan = clean_local_reports.build_cleanup_plan(
        repo_root,
        stale_days=30,
        include_residue=True,
    )
    candidates = {item["path"]: item for item in plan["candidates"]}
    assert ".polisyos/reports/old" in candidates
    assert "src/polisyos/demo/__pycache__" in candidates
    assert "src/policy_engine.egg-info" in candidates
    assert "tests/.DS_Store" in candidates
    assert "src/polisyos/demo/fixtures/raw" in candidates
    assert plan["manual_review"][0]["path"] == ".polisyos/audits/incident"

    payload = clean_local_reports.apply_cleanup(repo_root, plan)
    assert payload["deleted_count"] == len(plan["candidates"])
    assert not old_report.parent.exists()
    assert fresh_report.parent.exists()
    assert audit.parent.exists()
    assert not pycache.exists()
    assert not egg_info.exists()
    assert not ds_store.exists()
    assert not empty_fixture_raw.exists()
