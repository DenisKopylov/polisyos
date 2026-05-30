from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

SOURCE_OWNERSHIP_DOC = "docs/reference/policy-design-case-source-ownership.md"

SOURCE_CHAIN_PATHS = (
    "docs/research/universal-policy-design/deep-research-reports-105-146-combined.md",
    "docs/backlog/universal-policy-design-case-research-results-consolidation.md",
    "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md",
    "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md",
    "docs/reference/policy-design-case-failure-patterns.md",
    "docs/adr/index.md",
    "docs/adr/index.toml",
    "docs/adr/0166-evidence-acquisition-decision-boundaries.md",
    "docs/adr/0167-participation-legitimacy-matrix.md",
    "docs/adr/0168-legal-hierarchy-and-competence.md",
    "docs/adr/0169-bounded-liveness-and-runtime-escalation.md",
    "docs/adr/0170-contestability-and-recourse-boundaries.md",
    "docs/adr/0171-review-effectiveness-telemetry-advisory-first.md",
    "docs/reference/index.md",
    "docs/reference/documentation-inventory.md",
    SOURCE_OWNERSHIP_DOC,
)

OWNERSHIP_INDEXED_PATHS = SOURCE_CHAIN_PATHS[:13]

FORBIDDEN_LOCAL_PATHS = (
    (re.compile(r"(?<![A-Za-z0-9_./-])/Users/"), "absolute workstation path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])~/(Downloads|Desktop|Documents)\b"), "home path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])(?:Downloads|Desktop|Documents)/"), "local folder path"),
    (re.compile(r"file://"), "file URI"),
)


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_w0g_source_chain_paths_exist_and_are_indexed() -> None:
    ownership = _read(SOURCE_OWNERSHIP_DOC)

    for path in SOURCE_CHAIN_PATHS:
        assert (REPO_ROOT / path).is_file(), path

    for path in OWNERSHIP_INDEXED_PATHS:
        assert path in ownership

    reference_index = _read("docs/reference/index.md")
    documentation_inventory = _read("docs/reference/documentation-inventory.md")
    assert "policy-design-case-source-ownership.md" in reference_index
    assert SOURCE_OWNERSHIP_DOC in documentation_inventory


def test_w0g_source_chain_rejects_local_or_ephemeral_source_paths() -> None:
    for path in SOURCE_CHAIN_PATHS:
        text = _read(path)
        for pattern, label in FORBIDDEN_LOCAL_PATHS:
            assert pattern.search(text) is None, f"{path} contains {label}"


def test_w0g_traceability_covers_concepts_tasks_patterns_and_gates() -> None:
    ownership = _read(SOURCE_OWNERSHIP_DOC)

    required_refs = (
        "C0",
        "C27",
        "E23",
        "E24",
        "P03",
        "P06",
        "P13",
        "P15",
        "I0",
        "W0.G",
        "W1.E",
        "W5.E",
    )
    for ref in required_refs:
        assert f"`{ref}`" in ownership

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
        assert term in ownership


def test_w0g_canonical_documents_crosslink_source_ownership() -> None:
    source_docs = (
        "docs/research/universal-policy-design/deep-research-reports-105-146-combined.md",
        "docs/backlog/universal-policy-design-case-research-results-consolidation.md",
        "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md",
        "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md",
        "docs/adr/0166-evidence-acquisition-decision-boundaries.md",
        "docs/adr/0167-participation-legitimacy-matrix.md",
        "docs/adr/0168-legal-hierarchy-and-competence.md",
        "docs/adr/0169-bounded-liveness-and-runtime-escalation.md",
        "docs/adr/0170-contestability-and-recourse-boundaries.md",
        "docs/adr/0171-review-effectiveness-telemetry-advisory-first.md",
    )

    for path in source_docs:
        assert "docs/reference/policy-design-case-source-ownership.md" in _read(path)


def test_forbidden_source_path_patterns_only_match_actual_paths() -> None:
    forbidden_examples = (
        "~/Downloads/research.md",
        "/Users/example/Downloads/research.md",
        "Downloads/research.md",
        "file:///tmp/research.md",
    )
    allowed_examples = (
        "local Downloads folder",
        "docs/research/universal-policy-design/deep-research-reports-105-146-combined.md",
    )

    for example in forbidden_examples:
        assert any(pattern.search(example) for pattern, _ in FORBIDDEN_LOCAL_PATHS)

    for example in allowed_examples:
        assert all(pattern.search(example) is None for pattern, _ in FORBIDDEN_LOCAL_PATHS)
