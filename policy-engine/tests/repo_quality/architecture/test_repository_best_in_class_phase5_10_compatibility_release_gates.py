from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

from tools.ops_runners.release import check_compatibility_release_gates as gates

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase5_10_compatibility_release_gate_contract_is_report_only() -> None:
    contract = _read_toml("architecture/compatibility_release_gates.toml")
    header = contract["compatibility_release_gates"]
    checks = {item["id"]: item for item in contract["promotion_check"]}

    assert header["status"] == "report_only"
    assert header["mode"] == "report_only"
    assert header["gate_command"] == (
        "uv run polisyos-tools release check-compatibility-release-gates --fail-on-contract-errors"
    )
    assert {
        "breaking-compatibility-fragment",
        "migration-runbook-docs",
        "public-surface-inventory-review",
        "generated-client-compatibility",
    } == set(checks)
    for check in checks.values():
        assert check["mode"] == "report_only", check["id"]
        assert check["owner"].startswith("team-"), check["id"]
        for source in check["source_contracts"]:
            assert _path_or_glob_exists(source), (check["id"], source)


def test_phase5_10_compatibility_promises_have_owner_and_window() -> None:
    report = gates.build_report(repo_root=REPO_ROOT)

    assert report["contract_error_count"] == 0, report["contract_errors"]
    assert report["structured_compatibility_change_count"] >= 1


def test_phase5_10_release_tool_is_registered() -> None:
    from tools.registry import TOOL_SPECS_BY_KEY

    spec = TOOL_SPECS_BY_KEY[("release", "check-compatibility-release-gates")]

    assert spec.module == "tools.ops_runners.release.check_compatibility_release_gates"
    assert spec.callable_name == "main"
    assert spec.status.value == "active"


def test_phase5_10_checker_reports_breaking_class_without_fragment(tmp_path: Path) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()

    report = gates.build_report(
        repo_root=REPO_ROOT,
        fragments_dir=fragments,
        breaking_classes=("schema-openapi-abi",),
    )

    messages = {
        item["message"]
        for item in report["contract_errors"]
        if item["check"] == "breaking-fragment"
    }
    assert "breaking compatibility class has no structured release fragment" in messages


def test_phase5_10_checker_accepts_breaking_fragment_with_docs(tmp_path: Path) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "breaking.toml").write_text(
        """
id = "test-breaking-runtime-state"
title = "Runtime state migration"
type = "changed"
component = "runtime"
owner = "team-ops"
summary = "Runtime-state reader compatibility changed."
compatibility = "Runtime-state readers need the migration guide."
change_class = "runtime-state-format"
surface_classification = "public_stable: polisyos.runtime"
migration = "Follow the migration guide."
api = "No runtime HTTP API change."
limitations = "Operators must retain exported state until rollout finishes."
generated_client_compatibility = "not_applicable"
public_surface_inventory_reviewed = false
migration_docs = ["docs/runbooks/migration-release-promotion.md"]
runbook_docs = ["docs/runbooks/migration-release-promotion.md"]

[[compatibility_change]]
id = "runtime-state-reader-v2"
change_class = "runtime-state-format"
impact = "breaking"
surface = "public_stable: polisyos.runtime"
owner = "team-ops"
version_owner = "team-ops"
deprecation_window = "1 major release"
release_note = "Runtime-state readers require the documented migration path."
generated_client_compatibility = "not_applicable"
migration_docs = ["docs/runbooks/migration-release-promotion.md"]
runbook_docs = ["docs/runbooks/migration-release-promotion.md"]
""",
        encoding="utf-8",
    )

    report = gates.build_report(
        repo_root=REPO_ROOT,
        fragments_dir=fragments,
        breaking_classes=("runtime-state-format",),
    )

    assert report["contract_error_count"] == 0, report["contract_errors"]


def test_phase5_10_cli_contract_check_passes() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "polisyos-tools",
            "release",
            "check-compatibility-release-gates",
            "--fail-on-contract-errors",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "repository-best-in-class-phase-5.10" in result.stdout


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_or_glob_exists(path: str) -> bool:
    if any(char in path for char in "*?["):
        return bool(list(REPO_ROOT.glob(path)))
    return (REPO_ROOT / path).exists()
