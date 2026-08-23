#!/usr/bin/env python3
"""Reconcile the generated debt ledger with published source denominators."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTER_PATH = Path("docs/plans/active/DEBT-REGISTER.md")
GY_PATH = Path("docs/plans/active/layer3-slices/GY-engine-subordination.md")
ATLAS_PATH = Path("docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md")
DISPOSITION_PATH = Path("architecture/atlas_surfaces/frontend-disposition-register.json")
LEDGER_PATH = Path("docs/plans/active/LEDGER.md")
PLAN_ROOTS = (Path("docs/plans/active/atlas-slices"), Path("docs/superpowers/plans"))
PUBLISHED_DENOMINATORS = {"register": 54, "gy": 36, "atlas": 13, "frontend": 217}
REGISTER_STATUSES = frozenset({"open", "open_unmerged", "blocked", "folded", "closed", "ambiguous", "foreign"})
CANONICAL_GY_RE = re.compile(r"GY-(?:DEF\d+|DEFC-\d+|GAP\d+)$")
ANY_GY_HEADING_RE = re.compile(r"^- \*\*(GY-(?:DEF\d+|DEFC-\d+|GAP\d+|DI\d+|PA\d+))\s+—")
FILE_LINE_RE = re.compile(r"(?<![\w/])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+):(\d+)\b")
UNBLOCKED_PLANLESS = frozenset({"DS9", "DS10", "DS12", "DS14", "DS15", "DS17"})


@dataclass(frozen=True)
class Finding:
    """One reproducible source or ledger disagreement."""
    code: str
    detail: str


class _DebtRow(NamedTuple):
    debt_id: str
    status: str
    owner: str
    section: str
    heading: str
    raw: str
    branch: str | None = None


class _StandingBlock(NamedTuple):
    debt_id: str
    status: str
    line: int
    hit_count: int


class _AtlasDebt(NamedTuple):
    debt_id: str
    status: str


class _WorkRow(NamedTuple):
    slice_id: str
    stage: str
    basis: str
    heading: str
    branch: str | None


class _Snapshot(NamedTuple):
    debts: tuple[_DebtRow, ...]
    gy: tuple[_StandingBlock, ...]
    atlas_debts: tuple[_AtlasDebt, ...]
    work: tuple[_WorkRow, ...]
    plan_ids: frozenset[str]
    explicit_nonclosures: tuple[tuple[str, str, int], ...]
    frontend_rows: int
    frontend_statuses: tuple[tuple[str, int], ...]
    ds5_rows: int
    ds5_planless: int
    irregular_branches: tuple[str, ...]
    carried_closed: frozenset[str]


@dataclass(frozen=True)
class AuditReport:
    """Complete result of one repository audit."""
    findings: tuple[Finding, ...]
    metrics: dict[str, Any]
    ledger_text: str


def _cells(line: str) -> list[str]:
    if not line.startswith("|"):
        return []
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return [] if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells) else cells


def _inline_id(cell: str) -> str | None:
    match = re.search(r"`([^`]+)`", cell)
    return match.group(1).strip() if match else None


def _plain(value: str) -> str:
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    return value.replace("`", "").replace("**", "").replace("~~", "").strip()


def _anchor(heading: str) -> str:
    clean = re.sub(r"[^a-z0-9 _-]", "", heading.lower())
    return clean.replace(" ", "-")


def _status_token(text: str) -> str | None:
    for token in re.findall(r"`([^`]+)`", text):
        if token in REGISTER_STATUSES:
            return token
    for status in REGISTER_STATUSES:
        if re.search(rf"\b{re.escape(status)}\b", text):
            return status
    return None


def _parse_register(text: str) -> tuple[list[_DebtRow], list[str]]:
    rows: list[_DebtRow] = []
    irregular: list[str] = []
    section = ""
    heading = ""
    for line_no, line in enumerate(text.splitlines(), 1):
        section_match = re.match(r"^## ([A-I])\.\s+(.+)$", line)
        if section_match:
            section = section_match.group(1)
            heading = f"{section}. {section_match.group(2)}"
            continue
        cells = _cells(line)
        if section not in set("ABCDEFG") or not cells or cells[0].lower() in {"id", "debt"}:
            continue
        debt_id = _inline_id(cells[0])
        if not debt_id:
            continue
        if section == "E" and debt_id.startswith("codex/"):
            irregular.append(debt_id)
            continue
        if section == "G" and len(cells) < 3:
            continue
        if "~~" in cells[0] or section == "G":
            status = "closed"
        elif section == "E":
            status = "folded"
        else:
            status = _status_token(line) or "ambiguous"
        owner_index = {"A": 2, "B": 2, "C": 2, "D": 1}.get(section)
        owner = _plain(cells[owner_index]) if owner_index is not None and len(cells) > owner_index else "—"
        branches = re.findall(r"`(codex/[^`]+)`", line)
        rows.append(
            _DebtRow(
                debt_id=debt_id,
                status=status,
                owner=owner,
                section=section,
                heading=heading,
                raw=line,
                branch=branches[-1] if branches else rows[-1].branch if section == "C" and "same branch" in line.lower() else None,
            )
        )
    return rows, irregular


def _bold_span(lines: list[str], start: int) -> str:
    parts = [lines[start].strip()]
    while parts[-1].count("**") < 2 and start + len(parts) < len(lines):
        parts.append(lines[start + len(parts)].strip())
    return " ".join(parts)


def _recorded_status(span: str) -> str:
    tail = span.split("):", 1)[-1].strip().lstrip("`").lower()
    if tail.startswith("closed") or tail.startswith("executed"):
        return "closed"
    if tail.startswith("open"):
        return "open"
    if tail.startswith("blocked_on_product_decision"):
        return "blocked_on_product_decision"
    if tail.startswith("stopped"):
        return "ambiguous"
    if tail.startswith("the substring proxy"):
        return "prose_only"
    return "ambiguous"


def _standing_hits(lines: list[str], offset: int) -> tuple[list[tuple[int, str, str]], int | None]:
    hits: list[tuple[int, str, str]] = []
    unknown_lines: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        span = _bold_span(lines, index)
        if stripped.startswith("**STANDING RECORDED ("):
            hits.append((offset + index, _recorded_status(span), "standing_recorded"))
        elif stripped.startswith("**STANDING EXECUTED ("):
            status = "closed" if "closed" in span.lower() else "ambiguous"
            hits.append((offset + index, status, "standing_executed"))
        elif stripped.startswith(("**EXECUTED", "**SUPERSEDED", "**Final superseding closure")):
            hits.append((offset + index, "closed", "executed_or_superseded"))
        elif re.search(r"`defect_standing`|`defect_standing\s*=\s*closed`", stripped):
            status = "closed" if "closed" in stripped.lower() else "ambiguous"
            hits.append((offset + index, status, "defect_standing"))
        elif stripped.startswith("**CLOSED at `"):
            hits.append((offset + index, "closed", "closed_at"))
        elif stripped.startswith("**Standing after execution ("):
            status = "ambiguous" if "did not" in span.lower() else "closed"
            hits.append((offset + index, status, "standing_after_execution"))
        elif re.match(r"^\*\*(?:Standing|Execution standing|GY-DEFC-9 .* standing)", stripped):
            unknown_lines.append(offset + index)
    return hits, unknown_lines[-1] if unknown_lines else None


def _parse_gy(text: str) -> list[_StandingBlock]:
    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = ANY_GY_HEADING_RE.match(line)
        if match:
            headings.append((index, match.group(1)))
    blocks: list[_StandingBlock] = []
    for position, (start, debt_id) in enumerate(headings):
        if not CANONICAL_GY_RE.fullmatch(debt_id):
            continue
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        hits, unknown_line = _standing_hits(lines[start:end], start + 1)
        if hits:
            line, status, _form = hits[-1]
        else:
            line, status = unknown_line or start + 1, "ambiguous"
        blocks.append(_StandingBlock(debt_id, status, line, len(hits)))
    return blocks


def _parse_atlas_debts(text: str) -> list[_AtlasDebt]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("| Debt | Measured | Owner |")), -1)
    rows: list[_AtlasDebt] = []
    for index in range(start + 2, len(lines)) if start >= 0 else ():
        cells = _cells(lines[index])
        if not cells:
            break
        status = "closed" if "~~" in cells[0] else "open"
        leading = re.match(r"^(?:~~)?(?:\*\*)?`([^`]+)`", cells[0])
        title = re.match(r"^(?:~~)?\*\*([^*`]+)", cells[0])
        seed = leading.group(1) if leading else title.group(1) if title else _plain(cells[0])
        debt_id = seed if leading else re.sub(r"[^a-z0-9]+", "-", seed.lower().replace("&", " and ")).strip("-")
        rows.append(_AtlasDebt(debt_id, status))
    return rows


def _plan_inventory(repo_root: Path) -> tuple[set[str], dict[str, str], list[Path]]:
    ids: set[str] = set()
    branches: dict[str, str] = {}
    paths: list[Path] = []
    for relative_root in PLAN_ROOTS:
        root = repo_root / relative_root
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            paths.append(path)
            found = {f"DS{item}" for item in re.findall(r"(?i)\bDS(\d+)\b", path.name)}
            ids.update(found)
            head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:30])
            branch = re.search(r"(?m)^branch:\s*(\S+)", head)
            for slice_id in found:
                if branch:
                    branches[slice_id] = branch.group(1)
    return ids, branches, paths


def _explicit_nonclosures(repo_root: Path, paths: list[Path]) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for path in paths:
        active = False
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line == "## Explicit non-closure":
                active = True
                continue
            if active and line.startswith("## "):
                active = False
            if active:
                match = re.match(r"^-\s+`([^`]+)`(?:\s|$)", line)
                if match:
                    rows.append((match.group(1), path.relative_to(repo_root).as_posix(), line_no))
    return rows


def _parse_work(text: str, plan_ids: set[str], branches: dict[str, str]) -> list[_WorkRow]:
    lines = text.splitlines()
    headings: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^#### (DS\d+)\s+—\s+(.+)$", line)
        if match:
            headings[match.group(1)] = f"{match.group(1)} — {match.group(2)}"
    start = next((i for i, line in enumerate(lines) if line.startswith("| Slice | Theme | Gate / prereqs |")), -1)
    rows: list[_WorkRow] = []
    for index in range(start + 2, len(lines)) if start >= 0 else ():
        cells = _cells(lines[index])
        if not cells:
            break
        slice_id = _plain(cells[0])
        if not re.fullmatch(r"DS\d+", slice_id) or "CLOSED" in lines[index]:
            continue
        if slice_id == "DS16":
            stage = "unblocked"
            basis = '"a surface exists that renders values rather than refusals" — measured 2026-08-21'
        elif slice_id in UNBLOCKED_PLANLESS:
            stage = "unblocked"
            basis = "unblocked; no plan file in either plan root — measured 2026-08-22"
        elif "HANDED BACK" in cells[2].upper():
            stage, basis = "handed-back", "hand-back recorded in master plan"
        elif slice_id in branches:
            stage, basis = "in-flight", "attached branch declared by slice plan"
        elif slice_id in plan_ids:
            stage, basis = "planned", "plan file present"
        else:
            stage, basis = "named", "named in the master-plan slice sequence"
        heading = headings.get(slice_id, f"{slice_id} — {_plain(cells[1])}")
        rows.append(_WorkRow(slice_id, stage, basis, heading, branches.get(slice_id)))
    return rows


def _ds5_metrics(repo_root: Path, plan_ids: set[str]) -> tuple[int, int]:
    path = repo_root / "docs/plans/active/atlas-slices/DS5-enforcement-waist.md"
    if not path.is_file():
        return 0, 0
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("| Direct-`Badge` debt group |")), -1)
    rows = 0
    planless = 0
    for index in range(start + 2, len(lines)) if start >= 0 else ():
        cells = _cells(lines[index])
        if not cells:
            break
        rows += 1
        owners = {f"DS{item}" for item in re.findall(r"\bDS(\d+)\b", cells[2])}
        if owners and not owners.issubset(plan_ids):
            planless += 1
    return rows, planless


def _snapshot(repo_root: Path) -> _Snapshot:
    register_text = (repo_root / REGISTER_PATH).read_text(encoding="utf-8")
    gy_text = (repo_root / GY_PATH).read_text(encoding="utf-8")
    atlas_text = (repo_root / ATLAS_PATH).read_text(encoding="utf-8")
    debts, irregular = _parse_register(register_text)
    plan_ids, branches, paths = _plan_inventory(repo_root)
    disposition = json.loads((repo_root / DISPOSITION_PATH).read_text(encoding="utf-8"))
    assignments = disposition.get("ds8_strangle_coverage", {}).get("assignments", [])
    frontend_statuses = Counter(str(row.get("disposition", "untyped")) for row in assignments)
    ds5_rows, ds5_planless = _ds5_metrics(repo_root, plan_ids)
    carried_text = register_text.split("### G.3 Carried closed set", 1)[-1]
    carried_closed = {
        f"GY-{item}" for item in re.findall(r"(?<![A-Z-])(DEF\d+|DEFC-\d+|GAP\d+)\b", carried_text)
    }
    return _Snapshot(
        debts=tuple(debts),
        gy=tuple(_parse_gy(gy_text)),
        atlas_debts=tuple(_parse_atlas_debts(atlas_text)),
        work=tuple(_parse_work(atlas_text, plan_ids, branches)),
        plan_ids=frozenset(plan_ids),
        explicit_nonclosures=tuple(_explicit_nonclosures(repo_root, paths)),
        frontend_rows=len(assignments),
        frontend_statuses=tuple(sorted(frontend_statuses.items())),
        ds5_rows=ds5_rows,
        ds5_planless=ds5_planless,
        irregular_branches=tuple(irregular),
        carried_closed=frozenset(carried_closed),
    )


def _parse_ledger_table(text: str, heading: str) -> dict[str, list[str]]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == heading), -1)
    rows: dict[str, list[str]] = {}
    for index in range(start + 1, len(lines)) if start >= 0 else ():
        if lines[index].startswith("## "):
            break
        cells = _cells(lines[index])
        if not cells or cells[0].lower() == "id":
            continue
        debt_id = _inline_id(cells[0])
        if debt_id:
            rows[debt_id] = cells
    return rows


def _branch_link(branch: str | None) -> str:
    return "—" if not branch else f"[`{branch}`](https://github.com/DenisKopylov/polisyos/tree/{branch})"


def _owner_cells(row: _DebtRow, plan_ids: frozenset[str]) -> tuple[str, str]:
    lowered = row.owner.lower()
    slices = {f"DS{item}" for item in re.findall(r"\bDS(\d+)\b", row.owner)}
    planless = slices - plan_ids
    if "absent/unallocated" in lowered:
        return "absent/unallocated", "—"
    if "candidate" in lowered or planless:
        return "candidate", "—"
    return "—", row.owner


def render_ledger(snapshot: _Snapshot) -> str:
    """Render the deterministic two-table ledger from one source snapshot."""
    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    def summary(values: Sequence[str]) -> str:
        return ", ".join(f"{key}={value}" for key, value in sorted(Counter(values).items()))
    lines = [
        "# PolicyOS Open Work and Debt Ledger",
        "",
        "Generated by `tools/quality/validation/check_debt_ledger.py --write`. Closed rows remain in their authoritative sources.",
        "",
        "## Table A — open work",
        "",
        "| id | stage | measured basis | authoritative source | branch |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in sorted(snapshot.work, key=lambda item: (item.stage, item.slice_id)):
        source = f"[master plan](POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md#{_anchor(row.heading)})"
        lines.append(
            f"| `{row.slice_id}` | `{row.stage}` | {cell(row.basis)} | {source} | {_branch_link(row.branch)} |"
        )
    lines.extend(
        [
            "",
            "## Table B — open debts",
            "",
            "| id | status | capability / ownership state | owner | authoritative source | branch |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    open_debts = [row for row in snapshot.debts if row.status != "closed"]
    for row in sorted(open_debts, key=lambda item: (item.status, item.debt_id.lower())):
        anchor = _anchor(row.heading)
        source = f"[register §{row.section}](DEBT-REGISTER.md#{anchor})"
        state, owner = _owner_cells(row, snapshot.plan_ids)
        lines.append(
            f"| [`{cell(row.debt_id)}`](DEBT-REGISTER.md#{anchor}) | `{row.status}` | `{state}` | {cell(owner)} | {source} | {_branch_link(row.branch)} |"
        )
    register_ids = {row.debt_id for row in snapshot.debts}
    open_ids = {row.debt_id for row in open_debts}
    gy_ids = {row.debt_id for row in snapshot.gy}
    atlas_keys = {_key(row.debt_id) for row in snapshot.atlas_debts}
    history = ", ".join(
        f"`{row.debt_id}` ({row.hit_count})" for row in snapshot.gy if row.hit_count > 1
    )
    lines.extend(
        [
            "",
            "## Denominators",
            "",
            "| source | published | observed | indexed here | status distribution |",
            "| --- | ---: | ---: | ---: | --- |",
            f"| `DEBT-REGISTER.md` | 54 | {len(register_ids)} | {len(open_ids)} | {summary([row.status for row in snapshot.debts])} |",
            f"| `GY-engine-subordination.md` | 36 | {len(gy_ids)} | {len(open_ids & gy_ids)} | {summary([row.status for row in snapshot.gy])} |",
            f"| Atlas master debt table | 13 | {len(snapshot.atlas_debts)} | {sum(_key(item) in atlas_keys for item in open_ids)} | {summary([row.status for row in snapshot.atlas_debts])} |",
            f"| `frontend-disposition-register.json` | 217 | {snapshot.frontend_rows} | 0 | {summary([key for key, count in snapshot.frontend_statuses for _ in range(count)]) or 'none'} |",
            "",
            f"GY standing histories (recognized hits per block): {history or 'none'}.",
            f"Section-E irregular branch rows retained as branch records, not debt ids: {', '.join(f'`{item}`' for item in snapshot.irregular_branches) or 'none'}.",
        ]
    )
    return "\n".join(lines) + "\n"


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _git_commit_is_ancestor(repo_root: Path, commit: str) -> bool | None:
    exists = subprocess.run(
        ("git", "cat-file", "-e", f"{commit}^{{commit}}"), cwd=repo_root, capture_output=True
    )
    if exists.returncode:
        return None
    result = subprocess.run(
        ("git", "merge-base", "--is-ancestor", commit, "main"), cwd=repo_root, capture_output=True
    )
    return result.returncode == 0


def audit_repository(repo_root: Path = REPO_ROOT) -> AuditReport:
    """Read every ledger source and return typed reconciliation findings."""
    repo_root = repo_root.resolve()
    snapshot = _snapshot(repo_root)
    findings: list[Finding] = []
    observed = {
        "register": len({row.debt_id for row in snapshot.debts}),
        "gy": len(snapshot.gy),
        "atlas": len(snapshot.atlas_debts),
        "frontend": snapshot.frontend_rows,
    }
    for source, expected in PUBLISHED_DENOMINATORS.items():
        if observed[source] != expected:
            findings.append(Finding(f"{source}_denominator_mismatch", f"published={expected}, observed={observed[source]}"))
    by_id: dict[str, list[_DebtRow]] = {}
    for row in snapshot.debts:
        by_id.setdefault(row.debt_id, []).append(row)
    for debt_id, rows in by_id.items():
        if any(row.section == "G" for row in rows) and any(row.section != "G" and row.status != "closed" for row in rows):
            findings.append(Finding("closed_open_conflict", debt_id))
    for row in snapshot.debts:
        if row.status == "closed":
            for commit in re.findall(r"`([0-9a-f]{7,40})`", row.raw):
                ancestor = _git_commit_is_ancestor(repo_root, commit)
                if ancestor is False or (ancestor is None and re.search(rf"(?i)(?:closed_by|closed at|closed by|merged|landed at)[^`]*`{commit}`", row.raw)):
                    findings.append(Finding("closure_commit_not_on_main", f"{row.debt_id}: {commit}"))
        slices = {f"DS{item}" for item in re.findall(r"\bDS(\d+)\b", row.owner)}
        if slices - snapshot.plan_ids and "candidate" not in row.owner.lower() and row.status != "closed":
            findings.append(Finding("planless_slice_named_owner", f"{row.debt_id}: {sorted(slices - snapshot.plan_ids)}"))
    atlas_text = (repo_root / ATLAS_PATH).read_text(encoding="utf-8")
    for line_no, line in enumerate(atlas_text.splitlines(), 1):
        cells = _cells(line)
        if len(cells) == 4 and re.fullmatch(r"DS\d+", _plain(cells[0])):
            gate = _plain(cells[2])
            if gate.lower().startswith("merged") and "CLOSED" not in cells[2]:
                findings.append(Finding("merged_slice_not_closed", f"{_plain(cells[0])}:{line_no}"))
    ledger_path = repo_root / LEDGER_PATH
    ledger_text = ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    ledger_debts = _parse_ledger_table(ledger_text, "## Table B — open debts")
    expected_debts = {row.debt_id: row for row in snapshot.debts if row.status != "closed"}
    for debt_id in sorted(expected_debts.keys() - ledger_debts.keys()):
        findings.append(Finding("ledger_missing_id", debt_id))
    for debt_id in sorted(ledger_debts.keys() - expected_debts.keys()):
        findings.append(Finding("ledger_extra_id", debt_id))
    for debt_id in sorted(expected_debts.keys() & ledger_debts.keys()):
        actual = _status_token(ledger_debts[debt_id][1]) if len(ledger_debts[debt_id]) > 1 else None
        if actual != expected_debts[debt_id].status:
            findings.append(Finding("ledger_status_mismatch", f"{debt_id}: source={expected_debts[debt_id].status}, ledger={actual}"))
    ledger_keys = {_key(debt_id): debt_id for debt_id in ledger_debts}
    authority = {_key(row.debt_id): row for row in snapshot.debts}
    secondary = [(row.debt_id, row.status, "GY") for row in snapshot.gy] + [(row.debt_id, row.status, "Atlas") for row in snapshot.atlas_debts]
    for debt_id, status, source in secondary:
        key = _key(debt_id)
        if key in authority and authority[key].status != status:
            findings.append(Finding("source_status_disagreement", f"{source}:{debt_id}: register={authority[key].status}, source={status}"))
        if status != "closed" and key not in ledger_keys:
            findings.append(Finding("ledger_missing_source_id", f"{source}:{debt_id}"))
    for debt_id, path, line in snapshot.explicit_nonclosures:
        if debt_id not in ledger_debts:
            findings.append(Finding("explicit_nonclosure_missing", f"{debt_id}: {path}:{line}"))
    for path, line in FILE_LINE_RE.findall(ledger_text):
        if not (repo_root / path).is_file():
            findings.append(Finding("ledger_file_reference_missing", f"{path}:{line}"))
    expected_text = render_ledger(snapshot)
    if ledger_text != expected_text:
        findings.append(Finding("ledger_render_drift", LEDGER_PATH.as_posix()))
    register_ids = {row.debt_id for row in snapshot.debts}
    absent = [row for row in snapshot.gy if row.debt_id not in register_ids]
    metrics: dict[str, Any] = {
        "register_ids": observed["register"],
        "gy_ids": observed["gy"],
        "atlas_debt_rows": observed["atlas"],
        "frontend_disposition_rows": observed["frontend"],
        "gy_history_blocks": sum(row.hit_count > 1 for row in snapshot.gy),
        "gy_absent_from_register": len(absent),
        "gy_absent_from_register_closed": sum(row.debt_id in snapshot.carried_closed for row in absent),
        "ds5_nonclosure_rows": snapshot.ds5_rows,
        "ds5_planless_routes": snapshot.ds5_planless,
        "irregular_section_e_branch_rows": len(snapshot.irregular_branches),
    }
    return AuditReport(tuple(sorted(findings, key=lambda item: (item.code, item.detail))), metrics, expected_text)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="reconcile the committed ledger")
    mode.add_argument("--write", action="store_true", help="regenerate the committed ledger")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--report-only", action="store_true", help="print findings without a red exit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run check or write mode and emit complete census receipts."""
    args = _build_parser().parse_args(argv)
    report = audit_repository(args.repo_root)
    if args.write:
        atomic_write_text(args.repo_root / LEDGER_PATH, report.ledger_text)
        report = audit_repository(args.repo_root)
    for key, value in report.metrics.items():
        print(f"{key}={value}")
    for finding in report.findings:
        print(f"{finding.code}: {finding.detail}")
    if report.findings and not args.report_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
