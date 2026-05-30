from __future__ import annotations

# ruff: noqa: S101
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR_PATH = REPO_ROOT / "docs/adr/0170-contestability-and-recourse-boundaries.md"
PLAN_PATH = (
    REPO_ROOT
    / "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
)
INDEX_PATH = REPO_ROOT / "docs/adr/index.toml"


def test_w0c_contestability_recourse_adr_ratifies_boundary_and_negative_test() -> None:
    text = ADR_PATH.read_text(encoding="utf-8")

    required_sections = (
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
    )
    for section in required_sections:
        assert section in text

    required_terms = (
        "This ADR ratifies W0.C FT-ADR-03",
        "verified-reachable recourse pointer",
        "PolicyOS owns contested records",
        "deployment-owned recourse processes",
        "`recourse_pointer`",
        "recourse-outcome ingestion",
        "high-stakes contested production publication",
        "absent or unreachable",
        "public_export_recourse_pointer_unreachable",
        "C39b",
        "E4",
        "E5",
        "E15",
        "P03",
        "P05",
        "P10",
    )
    for term in required_terms:
        assert term in text


def test_w0c_contestability_recourse_is_indexed_and_linked_from_plan() -> None:
    rows = tomllib.loads(INDEX_PATH.read_text(encoding="utf-8"))["adr"]
    row = next(
        item
        for item in rows
        if item["path"] == "docs/adr/0170-contestability-and-recourse-boundaries.md"
    )

    assert row["id"] == "0170"
    assert row["status"] == "accepted"
    assert row["topic"] == "runtime-state"
    assert row["package"] == "repository"
    assert {"0150", "0162", "0163", "0166"} <= set(row["related"])

    plan = PLAN_PATH.read_text(encoding="utf-8")
    assert "[ADR-0170 Contestability And Recourse Boundaries]" in plan
