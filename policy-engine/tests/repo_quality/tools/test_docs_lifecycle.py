from __future__ import annotations

import datetime as dt
import re
import tomllib
from pathlib import Path

from tools.quality.validation import check_docs_freshness_baseline, check_docs_lifecycle
from tools.quality.validation.check_docs_gate import build_gate_plan

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_ARCHITECTURE_ROOT = "tests" + "/architecture"
CANONICAL_ARCHITECTURE_ROOT = "tests/repo_quality" + "/architecture"
OLD_FRONTEND_DASHBOARD = "frontend" + "/runtime-dashboard"
OLD_FRONTEND_CLIENT = "frontend" + "/runtime-api-client"


def test_phase6_4_docs_lifecycle_gate_passes_current_contract() -> None:
    assert check_docs_lifecycle.run_checks(REPO_ROOT) == []


def test_decision_log_has_no_due_unresolved_hds_entries() -> None:
    decision_log = (
        REPO_ROOT
        / "docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md"
    )
    text = decision_log.read_text(encoding="utf-8")
    closure_targets = set(
        re.findall(r"^- \*\*Closes\*\*: (DL-HDS-\d{4})$", text, flags=re.MULTILINE)
    )
    due_unresolved: list[str] = []

    for block in re.split(r"(?m)^### ", text):
        match = re.match(r"(DL-HDS-\d{4})\b", block)
        if match is None:
            continue
        entry_id = match.group(1)
        if entry_id in closure_targets:
            continue
        status = _decision_log_field(block, "Promotion status")
        revisit_wave = _decision_log_field(block, "Revisit wave")
        wave_match = re.search(r"Wave\s+(\d+)", revisit_wave or "")
        wave = int(wave_match.group(1)) if wave_match else None
        if (
            status in {"log_only_pending_revisit", "operational_closeout_required"}
            and wave is not None
            and wave <= 6
        ):
            due_unresolved.append(entry_id)

    assert due_unresolved == []


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


def test_phase0_2_redirect_stub_without_sunset_date_is_rejected(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "README.md").write_text(
        "\n".join(
            (
                "# Frontend Handoff",
                "",
                "`frontend/` is a legacy handoff path. Active JavaScript workspaces moved.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_docs_lifecycle.check_redirect_stubs(tmp_path)

    assert findings == [
        check_docs_lifecycle.LifecycleFinding(
            "redirect_stub",
            "frontend/README.md",
            "redirect stub missing `sunset_date` metadata.",
        )
    ]


def test_phase6_2_removed_tests_architecture_redirect_directory_is_rejected(
    tmp_path: Path,
) -> None:
    legacy = tmp_path / LEGACY_ARCHITECTURE_ROOT
    legacy.mkdir(parents=True)
    (legacy / "README.md").write_text(
        "\n".join(
            (
                "---",
                "redirect_stub: true",
                "owner: team-quality",
                f"target_path: {CANONICAL_ARCHITECTURE_ROOT}",
                "reason: collectable tests moved to repo-quality",
                "sunset_date: 2026-08-05",
                f"removal_gate: uv run pytest {CANONICAL_ARCHITECTURE_ROOT} -q",
                "---",
                "",
                "# Redirect: Repository-Quality Architecture Tests",
                "",
                f"Collectable tests moved to `{CANONICAL_ARCHITECTURE_ROOT}`.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_docs_lifecycle.check_removed_stub_references(tmp_path)

    assert findings == [
        check_docs_lifecycle.LifecycleFinding(
            "removed_stub_path",
            LEGACY_ARCHITECTURE_ROOT,
            f"removed redirect stub directory still exists; use `{CANONICAL_ARCHITECTURE_ROOT}`.",
        ),
        check_docs_lifecycle.LifecycleFinding(
            "removed_stub_reference",
            f"{LEGACY_ARCHITECTURE_ROOT}/README.md",
            f"stale direct reference `{LEGACY_ARCHITECTURE_ROOT}`; use `{CANONICAL_ARCHITECTURE_ROOT}`.",
        ),
    ]


def test_phase6_2_stale_removed_stub_references_are_rejected(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "live.md").write_text(
        "\n".join(
            (
                f"Use {LEGACY_ARCHITECTURE_ROOT} for architecture tests.",
                f"Do not edit {OLD_FRONTEND_DASHBOARD}.",
                f"Do not edit {OLD_FRONTEND_CLIENT}.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_docs_lifecycle.check_removed_stub_references(tmp_path)

    assert findings == [
        check_docs_lifecycle.LifecycleFinding(
            "removed_stub_reference",
            "docs/live.md",
            f"stale direct reference `{LEGACY_ARCHITECTURE_ROOT}`; use `{CANONICAL_ARCHITECTURE_ROOT}`.",
        ),
        check_docs_lifecycle.LifecycleFinding(
            "removed_stub_reference",
            "docs/live.md",
            f"stale direct reference `{OLD_FRONTEND_DASHBOARD}`; use `apps/runtime-dashboard`.",
        ),
        check_docs_lifecycle.LifecycleFinding(
            "removed_stub_reference",
            "docs/live.md",
            f"stale direct reference `{OLD_FRONTEND_CLIENT}`; use `packages/runtime-api-client`.",
        ),
    ]


def test_phase6_2_reference_scan_skips_runtime_data_roots(tmp_path: Path) -> None:
    for root_name in ("production_data", ".polisyos", "runs"):
        root = tmp_path / root_name
        root.mkdir()
        (root / "large.duckdb").write_text(
            f"stale direct reference {OLD_FRONTEND_DASHBOARD}",
            encoding="utf-8",
        )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "live.md").write_text("Live docs are scanned.\n", encoding="utf-8")

    scanned = {
        path.relative_to(tmp_path).as_posix()
        for path in check_docs_lifecycle._iter_reference_scan_files(tmp_path)
    }

    assert scanned == {"docs/live.md"}


def test_phase1_4_redirect_stub_without_created_date_is_rejected(
    tmp_path: Path,
) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "README.md").write_text(
        "\n".join(
            (
                "---",
                "redirect_stub: true",
                "owner: team-frontend",
                "target_path: apps",
                "reason: legacy frontend handoff path retained while references are swept",
                "sunset_date: 2026-08-05",
                "removal_gate: uv run rg \"frontend/\" .",
                "---",
                "",
                "# Frontend Handoff",
                "",
                "`frontend/` is a legacy handoff path. Active JavaScript workspaces moved.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_docs_lifecycle.check_redirect_stubs(tmp_path)

    assert findings == [
        check_docs_lifecycle.LifecycleFinding(
            "redirect_stub",
            "frontend/README.md",
            "redirect stub missing `created_date` metadata.",
        )
    ]


def test_phase1_4_redirect_stub_over_90_days_without_adr_is_rejected(
    tmp_path: Path,
) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "README.md").write_text(
        "\n".join(
            (
                "---",
                "redirect_stub: true",
                "owner: team-frontend",
                "target_path: apps",
                "reason: legacy frontend handoff path retained while references are swept",
                "created_date: 2026-05-07",
                "sunset_date: 2026-08-06",
                "removal_gate: uv run rg \"frontend/\" .",
                "---",
                "",
                "# Frontend Handoff",
                "",
                "`frontend/` is a legacy handoff path. Active JavaScript workspaces moved.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_docs_lifecycle.check_redirect_stubs(tmp_path)

    assert findings == [
        check_docs_lifecycle.LifecycleFinding(
            "redirect_stub",
            "frontend/README.md",
            "redirect stub sunset exceeds the 90-day policy without `compatibility_adr`.",
        )
    ]


def test_phase1_4_redirect_stub_over_90_days_requires_adr_to_declare_stub(
    tmp_path: Path,
) -> None:
    adr_root = tmp_path / "docs" / "adr"
    adr_root.mkdir(parents=True)
    (adr_root / "0001-long-window.md").write_text(
        "# Longer Compatibility Window\n\nThis ADR covers another redirect stub.\n",
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "README.md").write_text(
        "\n".join(
            (
                "---",
                "redirect_stub: true",
                "owner: team-frontend",
                "target_path: apps",
                "reason: legacy frontend handoff path retained while references are swept",
                "created_date: 2026-05-07",
                "sunset_date: 2026-08-06",
                "compatibility_adr: docs/adr/0001-long-window.md",
                "removal_gate: uv run rg \"frontend/\" .",
                "---",
                "",
                "# Frontend Handoff",
                "",
                "`frontend/` is a legacy handoff path. Active JavaScript workspaces moved.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_docs_lifecycle.check_redirect_stubs(tmp_path)

    assert findings == [
        check_docs_lifecycle.LifecycleFinding(
            "redirect_stub",
            "frontend/README.md",
            "redirect stub `compatibility_adr` must declare `frontend/`.",
        )
    ]


def test_phase1_4_redirect_stub_over_90_days_with_declaring_adr_is_allowed(
    tmp_path: Path,
) -> None:
    adr_root = tmp_path / "docs" / "adr"
    adr_root.mkdir(parents=True)
    (adr_root / "0001-long-window.md").write_text(
        "# Longer Compatibility Window\n\n"
        "The `frontend/` redirect stub remains compatible through 2026-08-06.\n",
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "README.md").write_text(
        "\n".join(
            (
                "---",
                "redirect_stub: true",
                "owner: team-frontend",
                "target_path: apps",
                "reason: legacy frontend handoff path retained while references are swept",
                "created_date: 2026-05-07",
                "sunset_date: 2026-08-06",
                "compatibility_adr: docs/adr/0001-long-window.md",
                "removal_gate: uv run rg \"frontend/\" .",
                "---",
                "",
                "# Frontend Handoff",
                "",
                "`frontend/` is a legacy handoff path. Active JavaScript workspaces moved.",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    assert check_docs_lifecycle.check_redirect_stubs(tmp_path) == []


def test_phase1_4_directory_contract_declares_redirect_stub_sunset_policy() -> None:
    with (REPO_ROOT / "architecture/policies/directory_contracts.toml").open("rb") as stream:
        payload = tomllib.load(stream)

    policy = payload["redirect_stub_sunset_policy"]

    assert policy["max_lifetime_days"] == 90
    assert policy["longer_compatibility_window_requires"] == "compatibility_adr"
    assert set(policy["known_redirect_stub_paths"]) == {"frontend"}
    assert {
        "owner",
        "target_path",
        "reason",
        "created_date",
        "sunset_date",
        "removal_gate",
    } <= set(policy["required_readme_front_matter"])


def test_phase1_4_wave6_frontend_redirect_stub_has_90_day_window() -> None:
    metadata = check_docs_lifecycle._front_matter(REPO_ROOT / "frontend/README.md")
    created = dt.date.fromisoformat(metadata["created_date"])
    sunset = dt.date.fromisoformat(metadata["sunset_date"])

    assert (sunset - created).days == 90
    assert metadata["sunset_date"] == "2026-08-05"


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


def test_wave26_second_governance_adr_pack_is_lifecycle_checked() -> None:
    assert check_docs_lifecycle.check_policy_design_case_second_governance_pack(REPO_ROOT) == []


def test_w0b_participation_fast_track_adr_is_accepted_and_lifecycle_checked() -> None:
    adr_path = REPO_ROOT / "docs/adr/0167-participation-legitimacy-matrix.md"
    text = adr_path.read_text(encoding="utf-8")

    required_sections = (
        "## Status",
        "## Context",
        "## Decision",
        "## Structural Commitment",
        "## Tuned Parameter",
        "## Authority Boundary",
        "## Negative Laundering Test",
        "## Feature Flag / Advisory Posture",
        "## Revision Path",
        "## Affected E Tasks",
        "## Validation",
        "## Capability Reality And Pattern Pass",
    )
    assert all(section in text for section in required_sections)

    required_tokens = (
        "Accepted",
        "claim_use x authority_level x population_scope",
        "fail-safe downgrade",
        "prevalence",
        "existence",
        "qualitative",
        "role-feasibility",
        "dissent",
        "context-only",
        "representativeness thresholds",
        "governed configuration",
        "thin consultation",
        "affected-population prevalence",
        "producer_missing",
        "bridge_missing",
        "consumer_missing",
        "surface_missing",
        "semantic_test_missing",
        "P05",
        "P10",
        "P15",
        "E4",
        "E5",
        "E11",
        "E22",
    )
    assert all(token in text for token in required_tokens)

    with (REPO_ROOT / "docs/adr/index.toml").open("rb") as stream:
        index = tomllib.load(stream)

    indexed_rows = {
        row["id"]: row
        for row in index["adr"]
        if row["path"] == "docs/adr/0167-participation-legitimacy-matrix.md"
    }
    assert indexed_rows == {
        "0167": {
            "id": "0167",
            "title": "Participation Legitimacy Matrix",
            "status": "accepted",
            "topic": "product-domain",
            "package": "repository",
            "path": "docs/adr/0167-participation-legitimacy-matrix.md",
            "supersedes": [],
            "superseded_by": [],
            "related": ["0147", "0150", "0152", "0156", "0157", "0159", "0160", "0162", "0166"],
        }
    }

    implementation_plan = (
        REPO_ROOT
        / "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
    ).read_text(encoding="utf-8")
    assert "[ADR-0167 Participation Legitimacy Matrix]" in implementation_plan


def test_w0d_legal_competence_fast_track_adr_is_accepted_and_lifecycle_checked() -> None:
    adr_path = REPO_ROOT / "docs/adr/0168-legal-hierarchy-and-competence.md"
    text = adr_path.read_text(encoding="utf-8")

    required_sections = (
        "## Status",
        "## Context",
        "## Decision",
        "## Structural Commitment",
        "## Tuned Parameter",
        "## Authority Boundary",
        "## Negative Laundering Test",
        "## Feature Flag / Advisory Posture",
        "## Revision Path",
        "## Affected E Tasks",
        "## Validation",
        "## Capability Reality And Pattern Pass",
    )
    assert all(section in text for section in required_sections)

    required_tokens = (
        "Accepted",
        "generic legal context",
        "serious legal authority",
        "per-jurisdiction namespace configuration",
        "context_only",
        "candidate_norm",
        "selected_authority",
        "limited_authority",
        "contested_authority",
        "blocked_no_authority",
        "implementing",
        "delegating",
        "enabling",
        "funding",
        "oversight",
        "appeals_or_contestability",
        "Competence changes split claims by legal window",
        "legal_as_of",
        "legal_effective",
        "implementation_period",
        "fiscal_period",
        "generic Ukrainian jurisdiction/topic match",
        "universal jurisdiction fallback rule",
        "producer_missing",
        "semantic_test_missing",
        "P05",
        "P08",
        "P15",
        "E9",
    )
    assert all(token in text for token in required_tokens)

    with (REPO_ROOT / "docs/adr/index.toml").open("rb") as stream:
        index = tomllib.load(stream)

    indexed_rows = {
        row["id"]: row
        for row in index["adr"]
        if row["path"] == "docs/adr/0168-legal-hierarchy-and-competence.md"
    }
    assert indexed_rows == {
        "0168": {
            "id": "0168",
            "title": "Legal Hierarchy And Competence Boundaries",
            "status": "accepted",
            "topic": "product-domain",
            "package": "polisyos.lex",
            "path": "docs/adr/0168-legal-hierarchy-and-competence.md",
            "supersedes": [],
            "superseded_by": [],
            "related": ["0051", "0057", "0147", "0150", "0152", "0157", "0158", "0159", "0166"],
        }
    }


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


def _decision_log_field(block: str, field: str) -> str | None:
    match = re.search(rf"^- \*\*{re.escape(field)}\*\*: (.+)$", block, flags=re.MULTILINE)
    return match.group(1).strip() if match else None
