from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PUBLIC_DOC_ROOTS = (
    "docs/reference",
    "docs/how-to",
    "docs/runbooks",
    "docs/tutorials",
    "docs/brand",
)

DOCS_ROOT_ALLOWLIST = {
    "README.md",
    "index.md",
    "style-guide.md",
    "key-rotation.md",
}

EXCLUDED_PLAN_LINK = re.compile(
    r"\]\([^)]*(?:plans/active|archive/(?:plans|reports))/[^)]*\.md[^)]*\)"
)

STALE_CURRENT_TOPOLOGY_PHRASES = (
    "Product-root GitHub Actions workflows are not active platform files today",
    "legacy root-level `cloud_deploy/`",
    "`policy-engine/.github`",
    "`policy-engine/cloud_deploy`",
    "`policy-engine/deploy`",
    "`policy-engine/docker`",
    "`policy-engine/gcp`",
)


def test_published_docs_do_not_link_to_excluded_plan_evidence() -> None:
    offenders: list[str] = []
    for path in _public_markdown_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if EXCLUDED_PLAN_LINK.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}")

    assert offenders == []


def test_published_docs_do_not_describe_retired_topology_as_current() -> None:
    offenders: list[str] = []
    for path in _public_markdown_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for phrase in STALE_CURRENT_TOPOLOGY_PHRASES:
                if phrase in line:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}:{phrase}")

    assert offenders == []


def test_repository_sota_evidence_has_left_active_lifecycle() -> None:
    active_sota = sorted((REPO_ROOT / "docs/plans/active").glob("REPOSITORY_SOTA*.md"))

    assert active_sota == []
    for path in (
        "docs/plans/accepted/REPOSITORY_SOTA_PLAN.md",
        "docs/plans/accepted/REPOSITORY_SOTA_PHASE_0_CONTRACTS.md",
        "docs/plans/accepted/REPOSITORY_SOTA_PHASE_1_DATA_FORGE_FOUNDATION.md",
        "docs/plans/accepted/REPOSITORY_SOTA_PHASE_2_DOMAIN_MIGRATION.md",
        "docs/plans/accepted/REPOSITORY_SOTA_PHASE_3_TOPOLOGY_CLEANUP.md",
        "docs/plans/accepted/REPOSITORY_SOTA_PHASE_4_GENERATED_FRONTEND_DATA_OPS.md",
        "docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md",
        "docs/archive/reports/REPOSITORY_SOTA_PHASE_MINUS_1_INVENTORY.md",
        "docs/archive/reports/REPOSITORY_SOTA_PHASE_MINUS_1_5_CLASSIFICATION.md",
    ):
        assert (REPO_ROOT / path).exists(), path


def test_repository_topology_reference_is_public_and_linked() -> None:
    assert (REPO_ROOT / "docs/reference/repository-topology.md").exists()

    required_links = {
        "docs/index.md": "reference/repository-topology.md",
        "docs/reference/index.md": "repository-topology.md",
        "docs/reference/operations/index.md": "../repository-topology.md",
        "mkdocs.yml": "reference/repository-topology.md",
    }
    for path, needle in required_links.items():
        assert needle in (REPO_ROOT / path).read_text(encoding="utf-8"), path


def test_docs_root_remains_allowlisted() -> None:
    docs_root_files = {path.name for path in (REPO_ROOT / "docs").iterdir() if path.is_file()}

    assert docs_root_files <= DOCS_ROOT_ALLOWLIST


def _public_markdown_files() -> list[Path]:
    files: list[Path] = []
    for root in PUBLIC_DOC_ROOTS:
        files.extend(sorted((REPO_ROOT / root).rglob("*.md")))
    return files
