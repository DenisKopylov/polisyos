#!/usr/bin/env python3
"""Reconcile the generated debt ledger with published source denominators."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, namedtuple
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTER_PATH = Path("docs/plans/active/DEBT-REGISTER.md")
GY_PATH = Path("docs/plans/active/layer3-slices/GY-engine-subordination.md")
ATLAS_PATH = Path("docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md")
DISPOSITION_PATH = Path("architecture/atlas_surfaces/frontend-disposition-register.json")
LEDGER_PATH = Path("docs/plans/active/LEDGER.md")
PLAN_ROOTS = (Path("docs/plans/active/atlas-slices"), Path("docs/superpowers/plans"))
PUBLISHED_DENOMINATORS = {
    "register": 79,
    "gy": 38,
    "atlas": 22,
    "frontend_disposition_entries": 261,
    "frontend_ds8_assignments": 217,
}
INFORMATIONAL_FINDING_CODES = frozenset(
    {
        "register_supplies_missing_standing",
        "register_withholds_source_standing",
    }
)
REGISTER_STATUSES = frozenset(
    {"open", "open_unmerged", "blocked", "folded", "closed", "ambiguous", "foreign"}
)
GY_STATUSES = frozenset({"blocked_on_product_decision", "prose_only"})
CAPABILITY_STATES = (
    "absent/unallocated",
    "contract_only",
    "producer_missing",
    "artifact_missing",
    "bridge_missing",
    "consumer_missing",
    "verification_missing",
    "implemented_but_not_orchestrated",
    "surface_missing",
    "surface_out_of_scope",
    "semantic_test_missing",
)
CAPABILITY_PATTERN = "|".join(map(re.escape, CAPABILITY_STATES))
CANONICAL_GY_RE = re.compile(r"GY-(?:DEF\d+|DEFC-\d+|GAP\d+)$")
ANY_GY_HEADING_RE = re.compile(r"^- \*\*(GY-(?:DEF\d+|DEFC-\d+|GAP\d+|DI\d+|PA\d+))\s+—")
FILE_LINE_RE = re.compile(r"(?<![\w/])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*):(\d+)\b")
UNBLOCKED_PLANLESS = frozenset({"DS9", "DS10", "DS12", "DS14", "DS15", "DS17"})

Finding = namedtuple("Finding", "code detail")
_DebtRow = namedtuple("_DebtRow", "debt_id status owner section heading raw branch")
_StandingBlock = namedtuple("_StandingBlock", "debt_id status line hit_count heading raw")
_AtlasDebt = namedtuple("_AtlasDebt", "debt_id status owner line heading raw")
_WorkRow = namedtuple("_WorkRow", "slice_id stage basis heading branch")
_Snapshot = namedtuple(
    "_Snapshot",
    "debts gy atlas_debts work plan_ids explicit_nonclosures frontend_entries frontend_entry_statuses frontend_ds8_assignments frontend_ds8_statuses ds5_rows ds5_planless irregular_branches carried_closed branch_states",
)
AuditReport = namedtuple(
    "AuditReport",
    "findings blocking_findings informational_findings metrics ledger_text",
)


def _cells(line: str) -> list[str]:
    if not line.startswith("|"):
        return []
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return [] if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells) else cells


def _inline_id(cell: str) -> str | None:
    return match.group(1).strip() if (match := re.search(r"`([^`]+)`", cell)) else None


def _plain(value: str) -> str:
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    return value.replace("`", "").replace("**", "").replace("~~", "").strip()


def _anchor(heading: str) -> str:
    return re.sub(r"[^a-z0-9 _-]", "", heading.lower()).replace(" ", "-")


def _status_token(text: str) -> str | None:
    statuses = REGISTER_STATUSES | GY_STATUSES
    return next(
        (token for token in re.findall(r"`([^`]+)`", text) if token in statuses), None
    ) or next((status for status in statuses if re.search(rf"\b{re.escape(status)}\b", text)), None)


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
        owner = (
            _plain(cells[owner_index])
            if owner_index is not None and len(cells) > owner_index
            else "—"
        )
        branches = re.findall(r"`(codex/[^`]+)`", line)
        branch = (
            branches[-1]
            if branches
            else rows[-1].branch
            if section == "C" and "same branch" in line.lower()
            else None
        )
        rows.append(_DebtRow(debt_id, status, owner, section, heading, line, branch))
    return rows, irregular


def _bold_span(lines: list[str], start: int) -> str:
    parts = [lines[start].strip()]
    while sum(part.count("**") for part in parts) % 2 and start + len(parts) < len(lines):
        parts.append(lines[start + len(parts)].strip())
    return " ".join(parts)


def _standing_status(span: str) -> str:
    plain = _plain(span).lower()
    defect = re.search(r"defect_standing\s*=\s*([a-z_]+)", plain)
    tail = plain.split("):", 1)[-1].strip()
    token = (
        defect.group(1)
        if defect
        else (match.group(1) if (match := re.match(r"([a-z_]+)", tail)) else "")
    )
    if token in {"closed", "executed"}:
        return "closed"
    if token in REGISTER_STATUSES | GY_STATUSES:
        return token
    if tail.startswith("the substring proxy"):
        return "prose_only"
    return "ambiguous"


def _standing_hits(lines: list[str], offset: int) -> tuple[list[tuple[int, str, bool, str]], int]:
    candidates: list[tuple[int, str, bool, str]] = []
    recognized = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        span = _bold_span(lines, index)
        if stripped.startswith(("**STANDING RECORDED (", "**STANDING EXECUTED (")):
            status = _standing_status(span)
        elif stripped.startswith(("**EXECUTED", "**SUPERSEDED", "**Final superseding closure")):
            status = "closed"
        elif (
            stripped.startswith("**Execution standing (")
            and re.search(r"`defect_standing\s*=\s*[a-z_]+`", span)
        ) or re.fullmatch(r"`defect_standing`\s*=\s*`[a-z_]+`", stripped):
            status = _standing_status(span)
        elif stripped.startswith("**`defect_standing`:"):
            status = "ambiguous"
        elif stripped.startswith("**CLOSED at "):
            status = "closed"
        elif stripped.startswith("**Standing after execution ("):
            status = "ambiguous" if "did not" in span.lower() else "closed"
        elif re.match(
            r"^\*\*(?:STANDING|Standing|Execution standing|GY-DEFC-9 .* standing)", stripped
        ):
            candidates.append((offset + index, "ambiguous", False, span))
            continue
        else:
            continue
        recognized += 1
        candidates.append((offset + index, status, True, span))
    return candidates, recognized


def _parse_gy(text: str) -> list[_StandingBlock]:
    lines = text.splitlines()
    headings: list[tuple[int, str, str]] = []
    heading = "GY engine subordination"
    for index, line in enumerate(lines):
        if match := re.match(r"^#{1,6}\s+(.+)$", line):
            heading = _plain(match.group(1))
        match = ANY_GY_HEADING_RE.match(line)
        if match:
            headings.append((index, match.group(1), heading))
    blocks: list[_StandingBlock] = []
    for position, (start, debt_id, source_heading) in enumerate(headings):
        if not CANONICAL_GY_RE.fullmatch(debt_id):
            continue
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        candidates, recognized = _standing_hits(lines[start:end], start + 1)
        if candidates:
            line, status, _known, raw = candidates[-1]
        else:
            line, status, raw = start + 1, "ambiguous", ""
        blocks.append(_StandingBlock(debt_id, status, line, recognized, source_heading, raw))
    return blocks


def _parse_atlas_debts(text: str) -> list[_AtlasDebt]:
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("| Debt | Measured | Owner |")), -1
    )
    heading = next(
        (
            _plain(re.sub(r"^#+\s+", "", line))
            for line in reversed(lines[:start])
            if re.match(r"^#{1,6}\s+", line)
        ),
        "Atlas plan",
    )
    rows: list[_AtlasDebt] = []
    for index in range(start + 2, len(lines)) if start >= 0 else ():
        cells = _cells(lines[index])
        if not cells:
            break
        status = "closed" if "~~" in cells[0] else "open"
        leading = re.match(r"^(?:~~)?(?:\*\*)?`([^`]+)`", cells[0])
        title = re.match(r"^(?:~~)?\*\*([^*`]+)", cells[0])
        seed = leading.group(1) if leading else title.group(1) if title else _plain(cells[0])
        debt_id = (
            seed
            if leading
            else re.sub(r"[^a-z0-9]+", "-", seed.lower().replace("&", " and ")).strip("-")
        )
        owner = _plain(cells[2]) if len(cells) > 2 else "—"
        rows.append(_AtlasDebt(debt_id, status, owner, index + 1, heading, lines[index]))
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
            status = re.search(r"(?m)^status:\s*(.+)$", head)
            for slice_id in found:
                if branch and (not status or "closed" not in status.group(1).lower()):
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


def _slice_state(cells: list[str]) -> str:
    fields = [_plain(cell).lower() for cell in cells[1:3]]
    closed = fields[1].startswith("closed") or any(
        re.search(r"\bclosed\s*(?:&|and)\s*merged\b", field) for field in fields
    )
    merged = closed or any(re.match(r"(?:whole[- ]slice\s+)?merged\b", field) for field in fields)
    return "closed" if closed else "merged" if merged else "open"


_GY_TASK_ROW = re.compile(
    r"^\| `(GY-[A-Za-z0-9-]+)` \| (\S+) \| \*{0,2}`?([a-z_]+)`?\*{0,2} \| (.+?) \| (.+?) \|$"
)


def _parse_gy_tasks(text: str) -> list[_WorkRow]:
    """Read the GY plan's authoritative task-standing table.

    Task status is recorded there and nowhere else: the revision log is history,
    not state. A row whose status is `executed`, `not_executable` or `not_started`
    is terminal or not yet begun and stays out of the open-work table; only
    `in_flight` and anything unrecognised surface as open work.
    """
    rows: list[_WorkRow] = []
    for line in text.splitlines():
        match = _GY_TASK_ROW.match(line)
        if not match:
            continue
        task_id, phase, status, evidence, gates = match.groups()
        if status in {"executed", "not_executable", "not_started"}:
            continue
        rows.append(
            _WorkRow(
                slice_id=task_id,
                stage=status,
                basis=f"phase {phase}; {_plain(evidence)}",
                heading=f"{task_id} — {_plain(gates)}",
                branch=None,
            )
        )
    return rows


def _parse_work(text: str, plan_ids: set[str], branches: dict[str, str]) -> list[_WorkRow]:
    lines = text.splitlines()
    headings: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^#### (DS\d+)\s+—\s+(.+)$", line)
        if match:
            headings[match.group(1)] = f"{match.group(1)} — {match.group(2)}"
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("| Slice | Theme | Gate / prereqs |")
        ),
        -1,
    )
    rows: list[_WorkRow] = []
    for index in range(start + 2, len(lines)) if start >= 0 else ():
        cells = _cells(lines[index])
        if not cells:
            break
        slice_id = _plain(cells[0])
        slice_state = _slice_state(cells)
        if not re.fullmatch(r"DS\d+", slice_id) or slice_state == "closed":
            continue
        if slice_id == "DS16":
            stage = "unblocked"
            basis = (
                '"a surface exists that renders values rather than refusals" — measured 2026-08-21'
            )
        elif slice_id in branches:
            stage, basis = "in-flight", "attached branch declared by slice plan"
        elif slice_id in plan_ids:
            stage, basis = "planned", "plan file present"
        elif slice_id in UNBLOCKED_PLANLESS:
            stage = "unblocked"
            basis = "unblocking property `not_established` — measured 2026-08-22; no plan file in either plan root"
        elif "HANDED BACK" in cells[2].upper():
            stage, basis = "handed-back", "hand-back recorded in master plan"
        elif slice_state == "merged":
            stage, basis = "merged", "whole-slice merge recorded; `CLOSED` marker absent"
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
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("| Direct-`Badge` debt group |")), -1
    )
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


def _branch_state(repo_root: Path, branch: str) -> str:
    for ref, state in (
        (f"refs/remotes/origin/{branch}", "published"),
        (f"refs/heads/{branch}", "local-only"),
    ):
        result = subprocess.run(("git", "show-ref", "--verify", "--quiet", ref), cwd=repo_root)
        if result.returncode == 0:
            return state
    return "declared-ref-missing"


def _snapshot(repo_root: Path) -> _Snapshot:
    register_text = (repo_root / REGISTER_PATH).read_text(encoding="utf-8")
    gy_text = (repo_root / GY_PATH).read_text(encoding="utf-8")
    atlas_text = (repo_root / ATLAS_PATH).read_text(encoding="utf-8")
    debts, irregular = _parse_register(register_text)
    plan_ids, branches, paths = _plan_inventory(repo_root)
    disposition = json.loads((repo_root / DISPOSITION_PATH).read_text(encoding="utf-8"))
    entries = disposition.get("entries", [])
    assignments = disposition.get("ds8_strangle_coverage", {}).get("assignments", [])
    entry_statuses = Counter(str(row.get("disposition", "untyped")) for row in entries)
    ds8_statuses = Counter(str(row.get("disposition", "untyped")) for row in assignments)
    ds5_rows, ds5_planless = _ds5_metrics(repo_root, plan_ids)
    marker = "### G.3 Carried closed set"
    carried_text = register_text.split(marker, 1)[1] if marker in register_text else ""
    carried_closed = {
        f"GY-{item}" for item in re.findall(r"(?<![A-Z-])(DEF\d+|DEFC-\d+|GAP\d+)\b", carried_text)
    }
    gy_rows = tuple(_parse_gy(gy_text))
    atlas_rows = tuple(_parse_atlas_debts(atlas_text))
    work = tuple(_parse_work(atlas_text, plan_ids, branches)) + tuple(_parse_gy_tasks(gy_text))
    branch_names = {row.branch for row in debts} | {row.branch for row in work}
    branch_states = tuple(
        sorted((name, _branch_state(repo_root, name)) for name in branch_names if name)
    )
    return _Snapshot(
        debts=tuple(debts),
        gy=gy_rows,
        atlas_debts=atlas_rows,
        work=work,
        plan_ids=frozenset(plan_ids),
        explicit_nonclosures=tuple(_explicit_nonclosures(repo_root, paths)),
        frontend_entries=len(entries),
        frontend_entry_statuses=tuple(sorted(entry_statuses.items())),
        frontend_ds8_assignments=len(assignments),
        frontend_ds8_statuses=tuple(sorted(ds8_statuses.items())),
        ds5_rows=ds5_rows,
        ds5_planless=ds5_planless,
        irregular_branches=tuple(irregular),
        carried_closed=frozenset(carried_closed),
        branch_states=branch_states,
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


def _branch_link(branch: str | None, states: dict[str, str]) -> str:
    if not branch:
        return "—"
    state = states.get(branch, "declared-ref-missing")
    if state == "published":
        return f"[`{branch}`](https://github.com/DenisKopylov/polisyos/tree/{branch})"
    return f"`{branch}` ({state})"


def _owner_cells(row: _DebtRow, plan_ids: frozenset[str]) -> tuple[str, str]:
    raw = re.sub(r"(?i)(?:explicitly\s+)?(?:\*\*)?not(?:\*\*)?\s+`[^`]+`", "", row.raw)
    cells = _cells(raw)
    subject = cells[1] if len(cells) > 1 else ""
    label = re.search(rf"(?i)reality-bar label:\s*(?:\*\*)?`?({CAPABILITY_PATTERN})", subject)
    stated = re.search(r"(?i)\bstates:\s*([^.;]+)", subject)
    scopes = (
        [label.group(1)]
        if label
        else [stated.group(1)]
        if stated
        else [row.owner, subject if row.section != "Atlas" else ""]
    )
    sibling = rf"`([^`]+)`\s+(?:is|returns|—\s*re-typed)\s+`?({CAPABILITY_PATTERN})`?"
    for member, state in re.findall(sibling, subject, flags=re.IGNORECASE):
        if _key(member) == _key(row.debt_id):
            scopes.append(state)
    scopes = [re.sub(sibling, "", scope, flags=re.IGNORECASE) for scope in scopes]
    states = [
        state
        for state in CAPABILITY_STATES
        if any(re.search(rf"(?<![\w/]){re.escape(state)}(?![\w/])", scope) for scope in scopes)
    ]
    raw_states = [
        state
        for state in CAPABILITY_STATES
        if re.search(rf"(?<![\w/]){re.escape(state)}(?![\w/])", raw)
    ]
    slices = {f"DS{item}" for item in re.findall(r"\bDS(\d+)\b", row.owner)}
    if "candidate" in row.owner.lower() or slices - plan_ids:
        states.append("candidate")
    state = ", ".join(dict.fromkeys(states)) or ("not_established" if raw_states else "—")
    owner = "—" if "absent/unallocated" in states or "candidate" in states else row.owner
    return state, owner


def _projected_debts(snapshot: _Snapshot) -> list[_DebtRow]:
    rows = [row for row in snapshot.debts if row.status != "closed"]
    authority = {_key(row.debt_id) for row in snapshot.debts}
    for row in snapshot.gy:
        if (
            _key(row.debt_id) not in authority
            and row.debt_id not in snapshot.carried_closed
            and row.status != "closed"
        ):
            rows.append(_DebtRow(row.debt_id, row.status, "—", "GY", row.heading, row.raw, None))
    for row in snapshot.atlas_debts:
        if _key(row.debt_id) not in authority and row.status != "closed":
            rows.append(
                _DebtRow(row.debt_id, row.status, row.owner, "Atlas", row.heading, row.raw, None)
            )
    return rows


def _source_link(row: _DebtRow) -> tuple[str, str]:
    anchor = _anchor(row.heading)
    if row.section == "GY":
        path, label = "layer3-slices/GY-engine-subordination.md", "GY plan"
    elif row.section == "Atlas":
        path, label = "POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md", "Atlas plan"
    else:
        path, label = "DEBT-REGISTER.md", f"register §{row.section}"
    return f"{path}#{anchor}", label


def render_ledger(snapshot: _Snapshot) -> str:
    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    def summary(values: Sequence[str]) -> str:
        return ", ".join(f"{key}={value}" for key, value in sorted(Counter(values).items()))

    branch_states = dict(snapshot.branch_states)
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
        source = (
            "[GY plan §8.5](layer3-slices/GY-engine-subordination.md#85-task-standing-authoritative)"
            if row.slice_id.startswith("GY-")
            else f"[master plan](POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md#{_anchor(row.heading)})"
        )
        lines.append(
            f"| `{row.slice_id}` | `{row.stage}` | {cell(row.basis)} | {source} | {_branch_link(row.branch, branch_states)} |"
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
    open_debts = _projected_debts(snapshot)
    for row in sorted(open_debts, key=lambda item: (item.status, item.debt_id.lower())):
        target, label = _source_link(row)
        source = f"[{label}]({target})"
        state, owner = _owner_cells(row, snapshot.plan_ids)
        lines.append(
            f"| [`{cell(row.debt_id)}`]({target}) | `{row.status}` | `{state}` | {cell(owner)} | {source} | {_branch_link(row.branch, branch_states)} |"
        )
    register_ids = {row.debt_id for row in snapshot.debts}
    open_ids = {row.debt_id for row in open_debts}
    open_keys = {_key(item) for item in open_ids}
    gy_ids = {row.debt_id for row in snapshot.gy}
    atlas_keys = {_key(row.debt_id) for row in snapshot.atlas_debts}
    receipts = ", ".join(f"`{row.debt_id}`={row.hit_count}@{row.line}" for row in snapshot.gy)
    lines.extend(
        [
            "",
            "## Denominators",
            "",
            "| source | published | observed | indexed here | status distribution |",
            "| --- | ---: | ---: | ---: | --- |",
            f"| `DEBT-REGISTER.md` | {PUBLISHED_DENOMINATORS['register']} | {len(register_ids)} | {sum(_key(item) in open_keys for item in register_ids)} | {summary([row.status for row in snapshot.debts])} |",
            f"| `GY-engine-subordination.md` | {PUBLISHED_DENOMINATORS['gy']} | {len(gy_ids)} | {sum(_key(item) in open_keys for item in gy_ids)} | {summary([row.status for row in snapshot.gy])} |",
            f"| Atlas master debt table | {PUBLISHED_DENOMINATORS['atlas']} | {len(snapshot.atlas_debts)} | {sum(_key(item) in open_keys for item in atlas_keys)} | {summary([row.status for row in snapshot.atlas_debts])} |",
            f"| `frontend-disposition-register.json` entries | {PUBLISHED_DENOMINATORS['frontend_disposition_entries']} | {snapshot.frontend_entries} | 0 | {summary([key for key, count in snapshot.frontend_entry_statuses for _ in range(count)]) or 'none'} |",
            f"| `frontend-disposition-register.json` `ds8_strangle_coverage.assignments` | {PUBLISHED_DENOMINATORS['frontend_ds8_assignments']} | {snapshot.frontend_ds8_assignments} | 0 | {summary([key for key, count in snapshot.frontend_ds8_statuses for _ in range(count)]) or 'none'} |",
            "",
            f"GY standing receipts (recognized hits/final line): {receipts or 'none'}.",
            "",
            "## Task-census coverage",
            "",
            "| ladder | task ids | indexed here | why |",
            "| --- | ---: | ---: | --- |",
            f"| Atlas slice sequence | 21 | {len(snapshot.work)} | open slices only; closed ones stay in the master plan |",
            f"| `GY-engine-subordination.md` | 37 | {sum(1 for row in snapshot.work if row.slice_id.startswith('GY-'))} | indexed from the authoritative task-standing table (§8.5), censused 2026-08-23: 24 `executed`, 1 `in_flight`, 1 `not_executable`, 11 `not_started`, 0 `ambiguous`. Only non-terminal rows are listed above. |",
            "| 16 further plans (Foundry, Fabric, Scientist, UPDC, Layer2/3, …) | 213 | 0 | dormant lanes; out of the declared scope, counted so the remainder is visible |",
            "",
            "Measured 2026-08-23 across `docs/plans/active/**`: **271 task ids in 18 plans**. This ledger",
            "indexes the Atlas ladder only. The census is complete against that declared scope and the",
            "remainder is enumerated rather than unknown.",
            f"Section-E irregular branch rows retained as branch records, not debt ids: {', '.join(f'`{item}`' for item in snapshot.irregular_branches) or 'none'}.",
        ]
    )
    return "\n".join(lines) + "\n"


_TERMINAL = {"closed", "folded"}
_UNSTATED = {"ambiguous", "prose_only", "none"}
# String inequality is a proxy for contradiction and misclassifies at its own
# boundary (P38): `foreign` and `open` are both true of one row, and `blocked`
# is `open` with a named blocker. Only a terminal/non-terminal split conflicts.
_RELATION_FINDING = {
    "conflict": "source_status_conflict",
    "register_supplies_standing": "register_supplies_missing_standing",
    "source_supplies_standing": "register_withholds_source_standing",
}


def _status_relation(register: str, source: str) -> str:
    if register == source:
        return "agree"
    if source in _UNSTATED:
        return "register_supplies_standing"
    if register in _UNSTATED:
        # Informational, not a lag: the register may deliberately withhold a
        # verdict asserted by a secondary source while its own evidence remains
        # undecidable. The authoritative register row states that reason.
        return "source_supplies_standing"
    return "conflict" if (register in _TERMINAL) != (source in _TERMINAL) else "compatible"


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
    repo_root = repo_root.resolve()
    snapshot = _snapshot(repo_root)
    findings: list[Finding] = []
    observed = {
        "register": len({row.debt_id for row in snapshot.debts}),
        "gy": len(snapshot.gy),
        "atlas": len(snapshot.atlas_debts),
        "frontend_disposition_entries": snapshot.frontend_entries,
        "frontend_ds8_assignments": snapshot.frontend_ds8_assignments,
    }
    for source, expected in PUBLISHED_DENOMINATORS.items():
        if observed[source] != expected:
            findings.append(
                Finding(
                    f"{source}_denominator_mismatch",
                    f"published={expected}, observed={observed[source]}",
                )
            )
    by_id: dict[str, list[_DebtRow]] = {}
    for row in snapshot.debts:
        by_id.setdefault(row.debt_id, []).append(row)
    for debt_id, rows in by_id.items():
        if any(row.section == "G" for row in rows) and any(
            row.section != "G" and row.status != "closed" for row in rows
        ):
            findings.append(Finding("closed_open_conflict", debt_id))
    closed_sources = [
        ("register", row.debt_id, row.raw) for row in snapshot.debts if row.status == "closed"
    ]
    closed_sources += [
        ("GY", row.debt_id, row.raw) for row in snapshot.gy if row.status == "closed"
    ]
    closed_sources += [
        ("Atlas", row.debt_id, row.raw) for row in snapshot.atlas_debts if row.status == "closed"
    ]
    for source, debt_id, raw in closed_sources:
        lead = r"closed(?:_by)?(?:\s+\d{4}-\d{2}-\d{2})?|merged?|landed|executed" + (
            "|at" if source == "GY" else ""
        )
        citation = rf"(?i)\b(?:{lead})(?:\s+(?:by|at|head|merge))*[\s(:;,]*`?([0-9a-f]{{7,40}})"
        for commit in dict.fromkeys(re.findall(citation, raw)):
            ancestor = _git_commit_is_ancestor(repo_root, commit)
            if ancestor is not True:
                findings.append(
                    Finding("closure_commit_not_on_main", f"{source}:{debt_id}: {commit}")
                )
    for row in snapshot.debts:
        slices = {f"DS{item}" for item in re.findall(r"\bDS(\d+)\b", row.owner)}
        if (
            slices - snapshot.plan_ids
            and "candidate" not in row.owner.lower()
            and row.status != "closed"
        ):
            findings.append(
                Finding(
                    "planless_slice_named_owner",
                    f"{row.debt_id}: {sorted(slices - snapshot.plan_ids)}",
                )
            )
    atlas_text = (repo_root / ATLAS_PATH).read_text(encoding="utf-8")
    for line_no, line in enumerate(atlas_text.splitlines(), 1):
        cells = _cells(line)
        if len(cells) == 4 and re.fullmatch(r"DS\d+", _plain(cells[0])):
            if _slice_state(cells) == "merged":
                findings.append(Finding("merged_slice_not_closed", f"{_plain(cells[0])}:{line_no}"))
    ledger_path = repo_root / LEDGER_PATH
    ledger_text = ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    ledger_debts = _parse_ledger_table(ledger_text, "## Table B — open debts")
    expected_debts = {row.debt_id: row for row in _projected_debts(snapshot)}
    for debt_id in sorted(expected_debts.keys() - ledger_debts.keys()):
        findings.append(Finding("ledger_missing_id", debt_id))
    for debt_id in sorted(ledger_debts.keys() - expected_debts.keys()):
        findings.append(Finding("ledger_extra_id", debt_id))
    for debt_id in sorted(expected_debts.keys() & ledger_debts.keys()):
        actual = _status_token(ledger_debts[debt_id][1]) if len(ledger_debts[debt_id]) > 1 else None
        if actual != expected_debts[debt_id].status:
            findings.append(
                Finding(
                    "ledger_status_mismatch",
                    f"{debt_id}: source={expected_debts[debt_id].status}, ledger={actual}",
                )
            )
    ledger_keys = {_key(debt_id): debt_id for debt_id in ledger_debts}
    authority = {_key(row.debt_id): row for row in snapshot.debts}
    secondary = [(row.debt_id, row.status, "GY") for row in snapshot.gy] + [
        (row.debt_id, row.status, "Atlas") for row in snapshot.atlas_debts
    ]
    for debt_id, status, source in secondary:
        key = _key(debt_id)
        authority_status = (
            authority[key].status
            if key in authority
            else "closed"
            if source == "GY" and debt_id in snapshot.carried_closed
            else None
        )
        name = (
            _RELATION_FINDING.get(_status_relation(authority_status, status))
            if authority_status is not None
            else None
        )
        if name:
            findings.append(
                Finding(name, f"{source}:{debt_id}: register={authority_status}, source={status}")
            )
        source_is_open = status != "closed" and authority_status != "closed"
        if source_is_open and key not in ledger_keys:
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
        "frontend_disposition_entries": observed["frontend_disposition_entries"],
        "frontend_ds8_assignment_rows": observed["frontend_ds8_assignments"],
        "gy_history_blocks": sum(row.hit_count > 1 for row in snapshot.gy),
        "gy_absent_from_register": len(absent),
        "gy_absent_from_register_closed": sum(
            row.debt_id in snapshot.carried_closed for row in absent
        ),
        "ds5_nonclosure_rows": snapshot.ds5_rows,
        "ds5_planless_routes": snapshot.ds5_planless,
        "irregular_section_e_branch_rows": len(snapshot.irregular_branches),
    }
    ordered_findings = tuple(sorted(findings, key=lambda item: (item.code, item.detail)))
    informational = tuple(
        finding for finding in ordered_findings if finding.code in INFORMATIONAL_FINDING_CODES
    )
    blocking = tuple(
        finding for finding in ordered_findings if finding.code not in INFORMATIONAL_FINDING_CODES
    )
    return AuditReport(ordered_findings, blocking, informational, metrics, expected_text)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="reconcile the committed ledger")
    mode.add_argument("--write", action="store_true", help="regenerate the committed ledger")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--report-only", action="store_true", help="print findings without a red exit"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = audit_repository(args.repo_root)
    if args.write:
        atomic_write_text(args.repo_root / LEDGER_PATH, report.ledger_text)
        report = audit_repository(args.repo_root)
    for key, value in report.metrics.items():
        print(f"{key}={value}")
    if report.blocking_findings:
        print("Blocking findings:")
    for finding in report.blocking_findings:
        print(f"{finding.code}: {finding.detail}")
    if report.informational_findings:
        print("Informational findings (do not block):")
    for finding in report.informational_findings:
        print(f"{finding.code}: {finding.detail}")
    return int(bool(report.blocking_findings and not args.report_only))


if __name__ == "__main__":
    raise SystemExit(main())
