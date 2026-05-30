# ruff: noqa: S101

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

EVIDENCE_PATHS_DOC = "docs/reference/policy-design-case-evidence-paths.md"
SOURCE_OWNERSHIP_DOC = "docs/reference/policy-design-case-source-ownership.md"
STRUCTURAL_ADR_REGISTRY_DOC = "docs/reference/policy-design-case-structural-adr-registry.md"
IMPLEMENTATION_PLAN = (
    "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
)
OPERATOR_TRIAGE_RUNBOOK = "docs/runbooks/policy-design-case-operator-triage.md"

REQUIRED_EXISTING_PATHS = (
    "docs/research/universal-policy-design/deep-research-reports-105-146-combined.md",
    "docs/backlog/universal-policy-design-case-research-results-consolidation.md",
    "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md",
    IMPLEMENTATION_PLAN,
    "docs/reference/policy-design-case-failure-patterns.md",
    SOURCE_OWNERSHIP_DOC,
    STRUCTURAL_ADR_REGISTRY_DOC,
    "docs/adr/index.md",
    "docs/adr/index.toml",
    OPERATOR_TRIAGE_RUNBOOK,
    "docs/reference/quality-gates.md",
    "docs/archive/reports/2026-05-19-policy-design-case-wave41-closeout.md",
)

DISCOVERABILITY_SURFACES = (
    "docs/reference/index.md",
    "docs/reference/documentation-inventory.md",
    "architecture/tooling/mkdocs/nav/30-reference.yml",
    "architecture/tooling/mkdocs/generated.yml",
    SOURCE_OWNERSHIP_DOC,
    STRUCTURAL_ADR_REGISTRY_DOC,
    IMPLEMENTATION_PLAN,
    OPERATOR_TRIAGE_RUNBOOK,
)

LOCAL_PATH_SCAN_SURFACES = (
    EVIDENCE_PATHS_DOC,
    SOURCE_OWNERSHIP_DOC,
    STRUCTURAL_ADR_REGISTRY_DOC,
    IMPLEMENTATION_PLAN,
    OPERATOR_TRIAGE_RUNBOOK,
    "docs/reference/index.md",
    "docs/reference/documentation-inventory.md",
    "docs/reference/quality-gates.md",
)

FORBIDDEN_LOCAL_PATHS = (
    (re.compile(r"(?<![A-Za-z0-9_./-])/Users/"), "absolute workstation path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])~/(Downloads|Desktop|Documents)\b"), "home path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])(?:Downloads|Desktop|Documents)/"), "local folder path"),
    (re.compile(r"file://"), "file URI"),
)


def test_w1e_evidence_path_contract_declares_required_path_families() -> None:
    text = _read(EVIDENCE_PATHS_DOC)

    required_families = (
        "Raw research source detail",
        "Normalized synthesis",
        "Research task contract",
        "Engineering wave plan",
        "ADR authority",
        "Operator triage runbook",
        "Validation command map",
        "Phase closeout notes",
        "Command Evidence Convention",
        "Closeout Note Minimum",
    )
    for family in required_families:
        assert family in text

    for path in REQUIRED_EXISTING_PATHS:
        if path.startswith("docs/archive/reports/2026-05-19"):
            continue
        assert path in text, path

    conventions = (
        "_build/.tmp/policy-design-case/<phase-or-wave>/",
        "quality_evidence/*.json",
        "docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.md",
        "docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.json",
        "uv run pytest",
        "uv run polisyos-tools workspace tool-configs --check",
        "uv run --extra docs python -m mkdocs build --strict",
    )
    for convention in conventions:
        assert convention in text


def test_w1e_evidence_paths_exist_and_are_discoverable() -> None:
    for path in REQUIRED_EXISTING_PATHS:
        assert (REPO_ROOT / path).is_file(), path

    for surface in DISCOVERABILITY_SURFACES:
        assert "policy-design-case-evidence-paths.md" in _read(surface), surface


def test_w1e_records_pattern_pass_and_capability_reality() -> None:
    text = _read(EVIDENCE_PATHS_DOC)

    required_refs = (
        "`W1.E`",
        "`P03`",
        "`P06`",
        "`P13`",
        "E23",
        "contract_only",
        "producer",
        "artifact",
        "bridge",
        "consumer",
        "surface",
        "verification",
        "semantic-test",
    )
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


def test_w1e_rejects_local_or_ephemeral_source_paths() -> None:
    for path in LOCAL_PATH_SCAN_SURFACES:
        text = _read(path)
        for pattern, label in FORBIDDEN_LOCAL_PATHS:
            assert pattern.search(text) is None, f"{path} contains {label}"


def test_w1e_forbidden_path_patterns_only_match_actual_paths() -> None:
    forbidden_examples = (
        "~/Downloads/pdc-closeout.md",
        "/Users/example/Downloads/pdc-closeout.md",
        "Desktop/pdc-validation.txt",
        "file:///tmp/pdc-evidence.md",
    )
    allowed_examples = (
        "docs/reference/policy-design-case-evidence-paths.md",
        "docs/archive/reports/YYYY-MM-DD-policy-design-case-wave1-closeout.md",
        "_build/.tmp/policy-design-case/W1.E/",
        "local files are not evidence",
    )

    for example in forbidden_examples:
        assert any(pattern.search(example) for pattern, _ in FORBIDDEN_LOCAL_PATHS)

    for example in allowed_examples:
        assert all(pattern.search(example) is None for pattern, _ in FORBIDDEN_LOCAL_PATHS)


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
