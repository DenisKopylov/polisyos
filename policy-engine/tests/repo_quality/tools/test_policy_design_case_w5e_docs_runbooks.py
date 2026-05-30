# ruff: noqa: S101

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

OPERATOR_GUIDE = "docs/reference/policy-design-case-operator-guide.md"
ROLLOUT_RUNBOOK = "docs/runbooks/policy-design-case-rollout-rollback.md"
EVIDENCE_PATHS_DOC = "docs/reference/policy-design-case-evidence-paths.md"
SOURCE_OWNERSHIP_DOC = "docs/reference/policy-design-case-source-ownership.md"
STRUCTURAL_ADR_REGISTRY_DOC = "docs/reference/policy-design-case-structural-adr-registry.md"
IMPLEMENTATION_PLAN = (
    "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
)
TRIAGE_RUNBOOK = "docs/runbooks/policy-design-case-operator-triage.md"
RUNBOOK_INDEX = "docs/runbooks/index.md"
SDD_INDEX = "docs/system-design-decisions/README.md"

DISCOVERABILITY_SURFACES = (
    "docs/reference/index.md",
    "docs/reference/documentation-inventory.md",
    "architecture/tooling/mkdocs/nav/30-reference.yml",
    "architecture/tooling/mkdocs/nav/60-runbooks.yml",
    "architecture/tooling/mkdocs/generated.yml",
    EVIDENCE_PATHS_DOC,
    SOURCE_OWNERSHIP_DOC,
    STRUCTURAL_ADR_REGISTRY_DOC,
    IMPLEMENTATION_PLAN,
    TRIAGE_RUNBOOK,
    RUNBOOK_INDEX,
    SDD_INDEX,
)

LOCAL_PATH_SCAN_SURFACES = (
    OPERATOR_GUIDE,
    ROLLOUT_RUNBOOK,
    EVIDENCE_PATHS_DOC,
    SOURCE_OWNERSHIP_DOC,
    STRUCTURAL_ADR_REGISTRY_DOC,
    IMPLEMENTATION_PLAN,
    TRIAGE_RUNBOOK,
    RUNBOOK_INDEX,
    "docs/reference/index.md",
    "docs/reference/documentation-inventory.md",
)

FORBIDDEN_LOCAL_PATHS = (
    (re.compile(r"(?<![A-Za-z0-9_./-])/Users/"), "absolute workstation path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])~/(Downloads|Desktop|Documents)\b"), "home path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])(?:Downloads|Desktop|Documents)/"), "local folder path"),
    (re.compile(r"file://"), "file URI"),
)


def test_w5e_operator_guide_declares_required_surfaces() -> None:
    text = _read(OPERATOR_GUIDE)

    required_sections = (
        "# Policy Design Case Operator Guide",
        "## Start Here",
        "## ADR And Decision Index",
        "## Public Evidence Path Discipline",
        "## Tuned Parameter Owner Ledger",
        "## Validation Ladder",
        "## Capability Evidence",
        "## Rollout And Rollback",
        "## Pattern Pass",
    )
    for section in required_sections:
        assert section in text

    required_paths = (
        "docs/reference/policy-design-case-structural-adr-registry.md",
        "docs/adr/index.md",
        "docs/adr/by-topic.md",
        "docs/adr/index.toml",
        "docs/system-design-decisions/README.md",
        "docs/system-design-decisions/policy-design-case-decision-log.md",
        "docs/reference/policy-design-case-evidence-paths.md",
        "architecture/policy_design_case/capability_reality_report.json",
        "docs/reference/policy-design-case-capability-ratchet.md",
        ROLLOUT_RUNBOOK,
        TRIAGE_RUNBOOK,
        IMPLEMENTATION_PLAN,
    )
    for path in required_paths:
        assert path in text, path


def test_w5e_tuned_parameter_owner_ledger_has_owners_validation_and_rollback() -> None:
    text = _read(OPERATOR_GUIDE)

    controls = (
        "Universal PDC projection",
        "Effective-independence graded weights",
        "Acquisition planner commit",
        "Review-effectiveness consequences",
        "Calibration blocking",
        "Complexity budget closeout effect",
        "Participation thresholds",
        "Rare-domain scarcity path",
        "Run-cost and degradation thresholds",
        "Legal fallback tables",
    )
    for control in controls:
        assert control in text

    required_owner_tokens = (
        "`team-runtime-quality`",
        "`team-science-quality`",
        "`team-domain-producers`",
        "`team-quality-closeout`",
        "`team-ddm`",
        "`@platform-owners`",
        "`@lex-owners`",
    )
    for token in required_owner_tokens:
        assert token in text

    assert "Promotion evidence" in text
    assert "Rollback or safe disable" in text
    assert "No tuned parameter may be represented as final" not in text
    assert "owner, version, default source, status" in text


def test_w5e_validation_ladder_and_runbook_are_operational() -> None:
    guide = _read(OPERATOR_GUIDE)
    runbook = _read(ROLLOUT_RUNBOOK)

    required_commands = (
        "uv run pytest tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py -q",
        "uv run polisyos-tools workspace tool-configs --check",
        "uv run --extra docs python -m mkdocs build --strict",
        "uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py -q",
        (
            "uv run python tools/quality/validation/"
            "check_policy_design_case_capability_ratchet.py --repo-root ."
        ),
        (
            "uv run --extra runtime --extra multi-tenant --extra ml python "
            "tools/quality/testing/local_prod_debug_probe.py"
        ),
        "uv run python tools/ops_runners/runtime/run_canary_matrix.py",
        "uv run python tools/quality/validation/inspect_evidence_bundles.py",
    )
    for command in required_commands:
        assert command in guide or command in runbook, command

    required_runbook_sections = (
        "# Policy Design Case Rollout And Rollback",
        "## Authority Rules",
        "## Preflight Inputs",
        "## First 15 Minutes Of A Failed Promotion",
        "## Rollout Ladder",
        "## Accept, Hold, Or Abort",
        "## Rollback Procedure",
        "## Tuned Config Rollback Map",
        "## Closeout Record Minimum",
    )
    for section in required_runbook_sections:
        assert section in runbook

    runbook_tokens = (
        "research-only",
        "governed pilot",
        "production-capable",
        "kill switch",
        "feature flags",
        "tuned configs",
        "quality_evidence/*.json",
        "_build/.tmp/policy-design-case/<phase-or-wave>/",
        "docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.md",
    )
    for token in runbook_tokens:
        assert token in runbook


def test_w5e_records_pattern_pass_and_capability_reality() -> None:
    text = _read(OPERATOR_GUIDE)

    required_refs = ("`W5.E`", "E23", "`P03`", "`P06`", "`P13`")
    for ref in required_refs:
        assert ref in text

    capability_terms = (
        "Typed artifact/contract",
        "Producer",
        "Persisted artifact/event",
        "Orchestration bridge",
        "Consumer",
        "Verification",
        "Surface",
        "Negative/e2e semantic test",
    )
    for term in capability_terms:
        assert term in text

    missing_labels = (
        "contract_only",
        "producer_missing",
        "artifact_missing",
        "bridge_missing",
        "consumer_missing",
        "verification_missing",
        "implemented_but_not_orchestrated",
        "surface_missing",
        "semantic_test_missing",
    )
    for label in missing_labels:
        assert label in text


def test_w5e_operator_surfaces_are_discoverable() -> None:
    assert (REPO_ROOT / OPERATOR_GUIDE).is_file()
    assert (REPO_ROOT / ROLLOUT_RUNBOOK).is_file()

    for surface in DISCOVERABILITY_SURFACES:
        text = _read(surface)
        if surface == "architecture/tooling/mkdocs/nav/30-reference.yml":
            assert "policy-design-case-operator-guide.md" in text, surface
            continue
        if surface == "architecture/tooling/mkdocs/nav/60-runbooks.yml":
            assert "policy-design-case-rollout-rollback.md" in text, surface
            continue
        assert "policy-design-case-operator-guide.md" in text, surface
        assert "policy-design-case-rollout-rollback.md" in text, surface


def test_w5e_rejects_local_or_ephemeral_operator_paths() -> None:
    for path in LOCAL_PATH_SCAN_SURFACES:
        text = _read(path)
        for pattern, label in FORBIDDEN_LOCAL_PATHS:
            assert pattern.search(text) is None, f"{path} contains {label}"


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
