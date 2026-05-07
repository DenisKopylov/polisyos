from __future__ import annotations

import tomllib
from pathlib import Path

from tools.quality.validation import check_docs_freshness_baseline, check_docs_lifecycle
from tools.quality.validation.check_docs_gate import build_gate_plan

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase6_4_docs_lifecycle_gate_passes_current_contract() -> None:
    assert check_docs_lifecycle.run_checks(REPO_ROOT) == []


def test_phase7_active_plan_with_accepted_closeout_is_rejected(tmp_path: Path) -> None:
    active_root = tmp_path / "docs" / "plans" / "active"
    active_root.mkdir(parents=True)
    plan = active_root / "CLOSED_PLAN.md"
    plan.write_text(
        "\n".join(
            (
                "---",
                "title: Closed Plan",
                "status: active",
                "owner: team-docs",
                "---",
                "",
                "- Status: accepted final closeout on 2026-05-07.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_docs_lifecycle.check_active_plans(tmp_path)

    assert findings == [
        check_docs_lifecycle.LifecycleFinding(
            "active_plan_metadata",
            "docs/plans/active/CLOSED_PLAN.md",
            "active plan contains accepted final closeout evidence; move it to docs/plans/archive.",
        )
    ]


def test_phase6_4_docs_freshness_baseline_is_docs_only_and_stable() -> None:
    assert check_docs_freshness_baseline.check_baseline(REPO_ROOT) == []


def test_phase6_4_adr_index_covers_every_adr_by_status_and_topic() -> None:
    with (REPO_ROOT / "docs/adr/index.toml").open("rb") as stream:
        index = tomllib.load(stream)

    rows = index["adr"]
    indexed_paths = {row["path"] for row in rows}
    expected_paths = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "docs/adr").glob("*.md")
        if path.name not in check_docs_lifecycle.generate_adr_index.SKIP_FILENAMES
    }

    assert indexed_paths == expected_paths
    assert all(row["status"] for row in rows)
    assert all(row["topic"] for row in rows)


def test_phase6_4_docs_gate_dispatches_lifecycle_nav_and_example_smokes() -> None:
    plan = build_gate_plan(
        (
            "docs/adr/0001-remove-legacy-foundry-engine.md",
            "architecture/tooling/mkdocs/nav/70-adrs.yml",
            "examples/extensions/fabric_connector/pyproject.toml",
        )
    )

    command_keys = {command.key for command in plan.commands}
    assert "docs_lifecycle" in command_keys
    docs_command = next(command for command in plan.commands if command.key == "docs_accuracy")
    assert "check-docs-freshness-baseline" in docs_command.argv
    assert "repository-sota-closeout" not in docs_command.argv
    assert "extension_examples" in command_keys
    assert "tool_configs" in command_keys
