"""Separate live repository references from recorded documentary evidence.

These roles apply to references, not to the truth or authority of the evidence.
Archive member names and recorded observations do not designate live repo paths.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_JOURNAL_ROOT = ("docs", "superpowers", "journals")
_ARCHIVE_REFERENCE = re.compile(r"(?P<archive>[^\s`\"<>]+\.zip)::[^\s`\"<>]+")
_SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")
_COMMIT = re.compile(r"[a-fA-F0-9]{40}\Z")
_ARCHIVE_COLUMNS = frozenset(
    {"item / archive evidence", "archive report path(s)", "archive member path"}
)


def _front_matter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return {}


def _is_historical_audit(relative: Path, text: str) -> bool:
    if relative.parts[:2] != ("docs", "research") or "audits" not in relative.parts[2:-1]:
        return False
    fields = _front_matter(text)
    return (
        fields.get("kind") == "research-audit"
        and fields.get("research_only") == "true"
        and _COMMIT.fullmatch(fields.get("historical_repository_commit", "")) is not None
        and _COMMIT.fullmatch(fields.get("current_repository_commit", "")) is not None
    )


def _archive_table_text(text: str) -> str:
    output: list[str] = []
    archive_columns: set[int] = set()
    for line in text.splitlines(keepends=True):
        if not line.lstrip().startswith("|"):
            archive_columns = set()
            output.append(line)
            continue
        cells = line.split("|")
        headings = {
            index
            for index, cell in enumerate(cells)
            if cell.strip().lower() in _ARCHIVE_COLUMNS
        }
        if headings:
            archive_columns = headings
        elif archive_columns:
            for index in archive_columns:
                if index < len(cells) - 1:
                    cells[index] = " "
            line = "|".join(cells)
        output.append(line)
    return "".join(output)


def _archive_map_text(text: str) -> str:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        return text
    members = payload.get("members")
    if not (
        _SHA256.fullmatch(str(payload.get("archive_sha256", "")))
        and isinstance(members, list)
        and isinstance(payload.get("archive_non_directory_members"), int)
        and payload["archive_non_directory_members"] == len(members)
    ):
        return text
    for member in members:
        if not isinstance(member, dict):
            return text
        if not (
            isinstance(member.get("path"), str)
            and isinstance(member.get("size"), int)
            and _SHA256.fullmatch(str(member.get("sha256", "")))
            and isinstance(member.get("ledger_entry_id"), str)
            and isinstance(member.get("normalization_rule"), str)
        ):
            return text
    for member in members:
        del member["path"]
    return json.dumps(payload, ensure_ascii=False)


def reference_scan_text(relative: Path, text: str) -> str:
    """Return only text whose references can designate live repository paths.

    Args:
        relative: Document path relative to the product root.
        text: Complete decoded document contents.

    Returns:
        Text with established historical and archive-member roles removed. Unknown
        roles remain live; malformed JSON raises rather than becoming empty evidence.
    """
    suffix = relative.suffix.lower()
    if relative.parts[:3] == _JOURNAL_ROOT and suffix in {".md", ".json"}:
        if suffix == ".json":
            json.loads(text)
        return ""
    if suffix == ".md":
        if _is_historical_audit(relative, text):
            return ""
        text = _archive_table_text(text)
    elif suffix == ".json":
        text = _archive_map_text(text)
    return _ARCHIVE_REFERENCE.sub(r"\g<archive>", text) if ".zip::" in text else text
