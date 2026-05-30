# ruff: noqa: S101

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

REGISTRY_DOC = "docs/reference/policy-design-case-structural-adr-registry.md"
SOURCE_OWNERSHIP_DOC = "docs/reference/policy-design-case-source-ownership.md"
IMPLEMENTATION_PLAN = (
    "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
)

EXPECTED_C_REFS = {
    *(f"C{number}" for number in range(0, 39)),
    "C39a",
    "C39b",
    "C40",
    "C41",
}
ALLOWED_REGISTRY_CLASSES = {
    "existing_adr",
    "fast_track_adr",
    "new_adr_required",
    "no_adr_required",
}
ALLOWED_NO_ADR_RATIONALES = {
    "implementation_local",
    "tuned_config_only",
    "deployment_owned",
    "research_blocked",
}
FAST_TRACK_ADRS = {
    "0166",
    "0167",
    "0168",
    "0169",
    "0170",
    "0171",
}
ADR_MINIMUM_SECTIONS = (
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
FORBIDDEN_LOCAL_PATHS = (
    (re.compile(r"(?<![A-Za-z0-9_./-])/Users/"), "absolute workstation path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])~/(Downloads|Desktop|Documents)\b"), "home path"),
    (re.compile(r"(?<![A-Za-z0-9_./-])(?:Downloads|Desktop|Documents)/"), "local folder path"),
    (re.compile(r"file://"), "file URI"),
)


def test_w0h_registry_covers_every_c_decision_with_a_blocking_source() -> None:
    rows = _markdown_table_rows(_read(REGISTRY_DOC), "## C0-C41 Decision Source Registry")

    assert set(rows) == EXPECTED_C_REFS

    for ref, row in rows.items():
        assert row["Registry class"] in ALLOWED_REGISTRY_CLASSES, ref
        assert row["Decision source"] not in {"", "-", "TBD", "TODO"}, ref
        assert row["Implementation gate"] not in {"", "-", "TBD", "TODO"}, ref
        assert row["Pattern pass"] not in {"", "-", "TBD", "TODO"}, ref
        assert row["E tasks"] not in {"", "-", "TBD", "TODO"}, ref

        if row["Registry class"] == "no_adr_required":
            assert row["Rationale label"] in ALLOWED_NO_ADR_RATIONALES, ref
            assert "no_adr_required" in row["Decision source"], ref
        else:
            assert row["Rationale label"] == "-", ref

        if row["Registry class"] == "new_adr_required":
            assert "ADR-TBD-" in row["Decision source"], ref
            assert "blocks_structural_implementation" in row["Implementation gate"], ref


def test_w0h_registry_adr_refs_exist_and_fast_track_adrs_are_template_complete() -> None:
    rows = _markdown_table_rows(_read(REGISTRY_DOC), "## C0-C41 Decision Source Registry")
    fast_track_seen: set[str] = set()

    for ref, row in rows.items():
        adr_refs = set(re.findall(r"ADR-([0-9]{4})", row["Decision source"]))
        if row["Registry class"] in {"existing_adr", "fast_track_adr"}:
            assert adr_refs, ref

        for adr_ref in adr_refs:
            adr_path = _adr_path(adr_ref)
            assert adr_path is not None, f"{ref}: ADR-{adr_ref}"

        if row["Registry class"] == "fast_track_adr":
            assert adr_refs <= FAST_TRACK_ADRS, ref
            fast_track_seen.update(adr_refs)

    assert fast_track_seen == FAST_TRACK_ADRS

    for adr_ref in FAST_TRACK_ADRS:
        adr_path = _adr_path(adr_ref)
        assert adr_path is not None, adr_ref
        adr_text = adr_path.read_text(encoding="utf-8")
        assert re.search(r"^## Status\n\nAccepted$", adr_text, flags=re.MULTILINE), adr_ref
        for section in ADR_MINIMUM_SECTIONS:
            assert section in adr_text, f"{adr_ref}: {section}"

        implementation_plan = _read(IMPLEMENTATION_PLAN)
        assert f"ADR-{adr_ref}" in implementation_plan, adr_ref
        assert adr_path.name in implementation_plan, adr_ref


def test_w0h_registry_is_indexed_from_canonical_w0_surfaces() -> None:
    expected_surfaces = (
        "docs/reference/index.md",
        "docs/reference/documentation-inventory.md",
        SOURCE_OWNERSHIP_DOC,
        IMPLEMENTATION_PLAN,
    )

    for path in expected_surfaces:
        assert REGISTRY_DOC in _read(path), path


def test_w0h_registry_records_pattern_pass_and_capability_reality() -> None:
    registry = _read(REGISTRY_DOC)

    required_refs = (
        "W0.H",
        "I0",
        "C0",
        "C41",
        "E23",
        "P01",
        "P03",
        "P05",
        "P06",
        "P13",
        "P15",
    )
    for ref in required_refs:
        assert f"`{ref}`" in registry

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
        assert term in registry


def test_w0h_registry_rejects_local_or_ephemeral_source_paths() -> None:
    for path in (REGISTRY_DOC, SOURCE_OWNERSHIP_DOC, IMPLEMENTATION_PLAN):
        text = _read(path)
        for pattern, label in FORBIDDEN_LOCAL_PATHS:
            assert pattern.search(text) is None, f"{path} contains {label}"


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _adr_path(adr_ref: str) -> Path | None:
    matches = sorted((REPO_ROOT / "docs" / "adr").glob(f"{adr_ref}-*.md"))
    return matches[0] if matches else None


def _markdown_table_rows(source: str, heading: str) -> dict[str, dict[str, str]]:
    lines = source.splitlines()
    try:
        start = lines.index(heading) + 1
    except ValueError as error:
        raise AssertionError(f"missing heading: {heading}") from error

    table_lines: list[str] = []
    for line in lines[start:]:
        if table_lines and not line.startswith("|"):
            break
        if line.startswith("|"):
            table_lines.append(line)
    if len(table_lines) < 3:
        raise AssertionError(f"missing table under heading: {heading}")

    header = [_clean_cell(cell) for cell in table_lines[0].strip("|").split("|")]
    rows: dict[str, dict[str, str]] = {}
    for line in table_lines[2:]:
        cells = [_clean_cell(cell) for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells, strict=True))
        rows[cells[0]] = row
    return rows


def _clean_cell(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.strip())
