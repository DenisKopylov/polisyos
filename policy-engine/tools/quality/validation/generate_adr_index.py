#!/usr/bin/env python3
"""Generate ADR TOML and Markdown indexes from ``docs/adr``."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from tools.lib.fs import (
    FileReadMeasurement,
    iter_repository_files,
    measure_file_reads,
    measured_is_file,
    measured_read_text,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR_DIR = REPO_ROOT / "docs" / "adr"
DEFAULT_TOML = ADR_DIR / "index.toml"
DEFAULT_INDEX = ADR_DIR / "index.md"
DEFAULT_BY_TOPIC = ADR_DIR / "by-topic.md"
DEFAULT_STALE_REPORT = REPO_ROOT / "docs" / "archive" / "reports" / "ADR_STALE_LINK_REPORT.md"

SKIP_FILENAMES = {
    "AUTHORING.md",
    "README.md",
    "_template.md",
    "template.md",
    "index.md",
    "by-topic.md",
}

ADR_HEADING_RE = re.compile(r"^#\s+ADR-(?P<raw_id>RSR-\d{4}|\d{3,4})\s*:\s*(?P<title>.+)$")
STATUS_HEADING_RE = re.compile(r"^ {0,3}##\s+Status\s*$", flags=re.IGNORECASE)
STATUS_FIELD_RE = re.compile(
    r"^ {0,3}(?:[-*]\s+)?(?:\*\*)?(?:status|статус)(?:\*\*)?\s*:\s*"
    r"(?:\*\*\s*)?(?P<value>.+?)\s*(?:\*\*)?$",
    flags=re.IGNORECASE,
)
STATUS_TOKEN_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?(?P<status>[A-Za-z_-]+)", flags=re.I)
KNOWN_STATUSES = {"accepted", "approved", "completed", "deprecated", "proposed", "superseded"}
RELATION_FIELD_RE = re.compile(
    r"^ {0,3}(?:[-*]\s+)?(?:\*\*)?(?P<label>supersedes|superseded\s+by|"
    r"extends|extended\s+by|related)(?:\*\*)?\s*:\s*(?P<value>.*)$",
    flags=re.IGNORECASE,
)
RELATION_LABEL_FIELD_RE = re.compile(
    r"^ {0,3}(?:[-*]\s+)?(?:\*\*)?(?P<label>supersedes|superseded\s+by|extends|"
    r"extended\s+by|related\s+to)(?:\*\*)?\s+(?P<value>\[?ADR-(?:RSR-)?\d{3,4}\b.*)$",
    flags=re.IGNORECASE,
)
INLINE_RELATED_FIELD_RE = re.compile(r"\bRelated\s*:\s*(?P<value>.*)$", flags=re.IGNORECASE)
RELATED_DECISIONS_HEADING_RE = re.compile(
    r"^ {0,3}#{1,6}\s+Related\s+Decisions\s*#*\s*$", flags=re.IGNORECASE
)
RELATION_TOKEN_RE = re.compile(r"\b(?:ADR-(?:RSR-)?\d{3,4}|RSR-\d{4})\b")
FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((?P<target>[^)]+)\)")
GENERATED_ON_RE = re.compile(r'^generated_on\s*=\s*"(?P<date>[^"]+)"$', flags=re.MULTILINE)
STALE_REPORT_DATE_RE = re.compile(
    r"^Generated on (?P<date>\d{4}-\d{2}-\d{2}) from ", flags=re.MULTILINE
)
DEFAULT_GENERATED_ON = "source-controlled"

TOPIC_DEFINITIONS: tuple[tuple[str, str], ...] = (
    (
        "repository-structure",
        "Repository topology, package layout, import boundaries, docs governance, "
        "and workspace hygiene.",
    ),
    (
        "observation",
        "Observability, causal evidence, scientist workflows, measurement, "
        "confidence, and validity.",
    ),
    ("security", "Tenant isolation, signing, secrets, trust stores, and other security controls."),
    (
        "runtime-state",
        "Runtime state, replay, idempotency, CAS, snapshots, persistence, and lifecycle behavior.",
    ),
    ("schemas", "IR, API, schema, serialization, registry, metadata, and compatibility contracts."),
    ("testing", "Test topology, fixtures, golden data, drift checks, and reproducibility gates."),
    (
        "release",
        "Release trains, SemVer, versioning, deprecation, migration, and retraction policy.",
    ),
    ("frontend", "Frontend workspace, dashboard, UI language, themes, and authored text surfaces."),
    (
        "product-domain",
        "Domain-level Foundry, Fabric, Lex, Data Forge, synthetic-world, and product concepts.",
    ),
)
STABLE_TOPICS = tuple(topic for topic, _ in TOPIC_DEFINITIONS)
TOPIC_DESCRIPTIONS = dict(TOPIC_DEFINITIONS)

TOPIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "security",
        ("security", "secret", "tenant", "signing", "key-rotation", "trust-store", "fedramp"),
    ),
    (
        "frontend",
        (
            "frontend",
            "dashboard",
            "design",
            "atlas",
            "janus",
            "glyph",
            "theme",
            "ui",
            "authored-text",
        ),
    ),
    (
        "testing",
        (
            "test",
            "testing",
            "fixture",
            "golden",
            "differential",
            "drift",
            "reproducibility",
            "hermetic",
        ),
    ),
    ("release", ("release", "semver", "versioning", "deprecation", "migration", "retraction")),
    (
        "runtime-state",
        (
            "runtime",
            "rate-limiting",
            "idempotency",
            "audit-trail",
            "cas",
            "checkpoint",
            "resume",
            "replay",
            "lifecycle",
            "snapshot",
        ),
    ),
    (
        "schemas",
        (
            "schema",
            "schemas",
            "ir",
            "trinity",
            "policy-surface",
            "json",
            "abi",
            "registry",
            "metadata",
            "api",
            "serialization",
            "contract",
        ),
    ),
    (
        "repository-structure",
        (
            "repository-structure",
            "workspace",
            "root",
            "package",
            "topology",
            "codemod",
            "cycle",
            "decomposition",
            "architecture",
            "boundary",
            "import",
            "layered",
            "docs",
            "documentation",
            "diataxis",
            "archive",
            "plan",
            "hygiene",
        ),
    ),
    (
        "observation",
        (
            "observation",
            "observability",
            "otel",
            "scientist",
            "claim",
            "research-dag",
            "voi",
            "node",
            "decision-packet",
            "readiness",
            "causal",
            "estimate",
            "estimator",
            "transportability",
            "sutva",
            "backdoor",
            "collider",
            "pag",
            "dag",
            "graph",
            "identification",
            "confidence",
            "uncertainty",
            "refutation",
            "e-value",
            "proxy",
            "survey",
            "literature",
        ),
    ),
    (
        "product-domain",
        (
            "foundry",
            "fabric",
            "connector",
            "world",
            "synthetic-world",
            "agent-sim",
            "wvs",
            "wgi",
            "wdi",
            "streaming",
            "lex",
            "legal",
            "law",
            "norm",
            "normpack",
            "data-forge",
            "data",
            "dataset",
            "lakehouse",
            "artifact",
            "knowledge",
            "skg",
            "method",
            "simulation",
            "portfolio",
            "calibration",
        ),
    ),
)

LEGACY_TOPIC_ALIASES = {
    "causal": "observation",
    "data": "product-domain",
    "docs": "repository-structure",
    "fabric": "product-domain",
    "foundry": "product-domain",
    "frontend-design": "frontend",
    "ir": "schemas",
    "lex": "product-domain",
    "runtime": "runtime-state",
    "scientist": "observation",
}

PACKAGE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "polisyos.scientist",
        ("scientist", "claim", "research-dag", "voi", "node", "decision-packet"),
    ),
    ("polisyos.foundry", ("foundry", "method", "simulation", "estimator")),
    ("polisyos.fabric", ("fabric", "connector", "world", "wvs", "wgi", "wdi")),
    ("polisyos.lex", ("lex", "legal", "law", "norm", "normpack")),
    ("polisyos.ir", ("ir", "trinity", "policy-surface", "schema", "transport", "analytics")),
    ("polisyos.runtime", ("runtime", "rate-limiting", "idempotency", "audit-trail")),
    ("polisyos.data_forge", ("data-forge", "dataset", "lakehouse", "snapshot", "knowledge", "skg")),
    ("frontend", ("frontend", "dashboard", "atlas", "janus", "glyph", "theme", "design")),
    ("repository", ("repository", "workspace", "root", "topology", "docs", "release", "package")),
)


@dataclass(frozen=True)
class AdrEntry:
    id: str
    title: str
    status: str
    topic: str
    package: str
    path: str
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    related: tuple[str, ...]


@dataclass(frozen=True)
class StaleReference:
    source: str
    token: str
    reason: str


def _markdown_files(
    *,
    measurement: FileReadMeasurement | None = None,
    selection_receipt: dict[str, object] | None = None,
) -> list[Path]:
    selector = (
        "paths enumerated by tools.lib.fs.iter_repository_files(REPO_ROOT), then direct children "
        "of ADR_DIR whose suffix is .md, excluding SKIP_FILENAMES"
    )
    try:
        enumerated = list(iter_repository_files(REPO_ROOT))
    except (OSError, RuntimeError) as error:
        if measurement is not None:
            measurement.record(
                REPO_ROOT,
                "enumerate_repository_paths",
                status="unavailable",
                selector=selector,
                error=type(error).__name__,
            )
        if selection_receipt is not None:
            selection_receipt.update(
                {
                    "selector": selector,
                    "status": "unavailable",
                    "enumerated_denominator": None,
                    "candidate_count": None,
                    "excluded_names": sorted(SKIP_FILENAMES),
                    "excluded_paths": [],
                    "selected_paths": [],
                    "untracked_worktree_paths": "not_established",
                }
            )
        raise

    enumerated_names = sorted(_display_path(path) for path in enumerated)
    candidates = [path for path in enumerated if path.parent == ADR_DIR and path.suffix == ".md"]
    excluded = [path for path in candidates if path.name in SKIP_FILENAMES]
    selected = [path for path in candidates if path.name not in SKIP_FILENAMES]
    enumeration_digest = hashlib.sha256("\n".join(enumerated_names).encode("utf-8")).hexdigest()
    if measurement is not None:
        measurement.record(
            REPO_ROOT,
            "enumerate_repository_paths",
            status="enumerated",
            source="tools.lib.fs.iter_repository_files",
            enumerated_denominator=len(enumerated),
            path_set_sha256=enumeration_digest,
            selector=selector,
        )
        measurement.record(
            ADR_DIR,
            "select_adr_markdown",
            status="selected",
            selector=selector,
            enumerated_denominator=len(enumerated),
            candidate_count=len(candidates),
            excluded_names=sorted(SKIP_FILENAMES),
            excluded_paths=sorted(_display_path(path) for path in excluded),
            selected_paths=sorted(_display_path(path) for path in selected),
        )
    if selection_receipt is not None:
        selection_receipt.update(
            {
                "selector": selector,
                "enumerator": "tools.lib.fs.iter_repository_files(REPO_ROOT)",
                "enumerated_denominator": len(enumerated),
                "enumerated_paths_sha256": enumeration_digest,
                "candidate_count": len(candidates),
                "excluded_names": sorted(SKIP_FILENAMES),
                "excluded_paths": sorted(_display_path(path) for path in excluded),
                "selected_paths": sorted(_display_path(path) for path in selected),
                "untracked_worktree_paths": "not_established",
            }
        )
    return selected


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _lines_outside_fences(text: str) -> list[str | None]:
    """Return source lines, using ``None`` for fenced code content and delimiters."""
    lines: list[str | None] = []
    fence_char = ""
    fence_length = 0
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if fence_char:
            if match is not None and match.group("fence")[0] == fence_char:
                closing = re.match(
                    rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_length},}}\s*$", line
                )
                if closing is not None:
                    fence_char = ""
                    fence_length = 0
            lines.append(None)
            continue
        if match is not None:
            fence = match.group("fence")
            fence_char = fence[0]
            fence_length = len(fence)
            lines.append(None)
            continue
        lines.append(line)
    return lines


def _status_value(text: str) -> str | None:
    """Read a declared status from the document's opening status field or section."""
    lines = _lines_outside_fences(text)
    for index, line in enumerate(lines):
        if line is None:
            continue
        if STATUS_HEADING_RE.fullmatch(line):
            for following in lines[index + 1 :]:
                if following is None or not following.strip():
                    continue
                if re.match(r"^ {0,3}#{1,6}\s", following):
                    return None
                return following.strip()
            return None

        match = STATUS_FIELD_RE.fullmatch(line)
        if match is not None:
            return match.group("value").strip()

        if re.match(r"^ {0,3}##\s+", line):
            break
    return None


def _status(text: str) -> str:
    value = _status_value(text)
    if value is None:
        return "unknown"
    match = STATUS_TOKEN_RE.match(value)
    if match is None:
        return "unknown"
    status = match.group("status").strip().lower().replace("_", "-")
    return status if status in KNOWN_STATUSES else "unknown"


def _id_and_title(path: Path, text: str) -> tuple[str, str]:
    first_heading = next((line.strip() for line in text.splitlines() if line.startswith("# ")), "")
    match = ADR_HEADING_RE.match(first_heading)
    if match is not None:
        raw_id = match.group("raw_id")
        title = match.group("title").strip()
        if raw_id.startswith("RSR-"):
            return raw_id, title
        if path.name.startswith("ADR-") and len(raw_id) == 3:
            return f"ADR-{raw_id}", title
        return raw_id, title

    stem_match = re.match(
        r"(?P<id>\d{4}|ADR-\d{3}|repository-structure-\d{4})-(?P<slug>.+)", path.stem
    )
    if stem_match is not None:
        raw_id = stem_match.group("id")
        if raw_id.startswith("repository-structure-"):
            raw_id = f"RSR-{raw_id.rsplit('-', 1)[1]}"
        title = stem_match.group("slug").replace("-", " ").title()
        return raw_id, title

    raise ValueError(f"Cannot determine ADR id/title from {path}")


def _classify_topic(path: Path, title: str) -> str:
    haystack = f"{path.stem} {title}".lower()
    for topic, keywords in TOPIC_KEYWORDS:
        if _has_keyword(haystack, keywords):
            return topic
    return "product-domain"


def _classify_package(path: Path, title: str) -> str:
    haystack = f"{path.stem} {title}".lower()
    for package, keywords in PACKAGE_KEYWORDS:
        if _has_keyword(haystack, keywords):
            return package
    return "repository"


def _has_keyword(haystack: str, keywords: tuple[str, ...]) -> bool:
    normalized = " " + re.sub(r"[^a-z0-9]+", " ", haystack.lower()) + " "
    for keyword in keywords:
        needle = " " + re.sub(r"[^a-z0-9]+", " ", keyword.lower()).strip() + " "
        if needle in normalized:
            return True
    return False


def _topic_error_prefix(path: str, row_number: int) -> str:
    location = path if path else f"[[adr]] #{row_number}"
    return f"{location}:"


def _required_string(row: dict[str, object], field: str, row_number: int) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        path = str(row.get("path", ""))
        raise ValueError(f"{_topic_error_prefix(path, row_number)} ADR row missing `{field}`.")
    return value.strip()


def _string_array(row: dict[str, object], field: str, row_number: int) -> tuple[str, ...]:
    value = row.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        path = str(row.get("path", ""))
        raise ValueError(
            f"{_topic_error_prefix(path, row_number)} ADR row `{field}` must be a string array."
        )
    return tuple(value)


def _normalize_topic(
    topic: str,
    *,
    path: str,
    title: str,
    row_number: int,
    allow_legacy_topics: bool,
) -> str:
    if not topic.strip():
        raise ValueError(f"{_topic_error_prefix(path, row_number)} ADR row missing `topic`.")

    normalized = topic.strip()
    if normalized in STABLE_TOPICS:
        return normalized

    if allow_legacy_topics:
        if normalized == "architecture":
            return _classify_topic(Path(path), title)
        if normalized in LEGACY_TOPIC_ALIASES:
            return LEGACY_TOPIC_ALIASES[normalized]

    expected = ", ".join(STABLE_TOPICS)
    raise ValueError(
        f"{_topic_error_prefix(path, row_number)} unknown ADR topic `{normalized}`; "
        f"expected one of: {expected}."
    )


def load_index_entries(
    path: Path = DEFAULT_TOML, *, allow_legacy_topics: bool = False
) -> list[AdrEntry]:
    data = tomllib.loads(measured_read_text(path, encoding="utf-8"))

    rows = data.get("adr", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path}: adr rows missing.")

    entries: list[AdrEntry] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"[[adr]] #{row_number}: ADR row must be a table.")

        adr_id = _required_string(row, "id", row_number)
        title = _required_string(row, "title", row_number)
        status = _required_string(row, "status", row_number)
        raw_topic = str(row.get("topic", ""))
        package = _required_string(row, "package", row_number)
        adr_path = _required_string(row, "path", row_number)

        if adr_id in seen_ids:
            raise ValueError(f"{adr_path}: duplicate ADR id `{adr_id}`.")
        if adr_path in seen_paths:
            raise ValueError(f"{adr_path}: duplicate ADR path.")
        seen_ids.add(adr_id)
        seen_paths.add(adr_path)

        entries.append(
            AdrEntry(
                id=adr_id,
                title=title,
                status=status,
                topic=_normalize_topic(
                    raw_topic,
                    path=adr_path,
                    title=title,
                    row_number=row_number,
                    allow_legacy_topics=allow_legacy_topics,
                ),
                package=package,
                path=adr_path,
                supersedes=_string_array(row, "supersedes", row_number),
                superseded_by=_string_array(row, "superseded_by", row_number),
                related=_string_array(row, "related", row_number),
            )
        )

    return sorted(entries, key=lambda entry: entry.id)


def _index_entries_by_path(index_path: Path) -> dict[str, AdrEntry]:
    if not measured_is_file(index_path):
        raise ValueError(
            f"{_display_path(index_path)} is missing; add ADR rows with stable topics."
        )
    return {entry.path: entry for entry in load_index_entries(index_path, allow_legacy_topics=True)}


def _normalize_token(token: str, known_ids: set[str]) -> str | None:
    if token.startswith("ADR-RSR-"):
        candidate = token.removeprefix("ADR-")
        return candidate if candidate in known_ids else None
    if token.startswith("RSR-"):
        return token if token in known_ids else None
    if not token.startswith("ADR-"):
        return token if token in known_ids else None

    raw = token.removeprefix("ADR-")
    exact_legacy = f"ADR-{raw}"
    if exact_legacy in known_ids:
        return exact_legacy
    if raw in known_ids:
        return raw
    padded = raw.zfill(4)
    if padded in known_ids:
        return padded
    return None


def _declared_relation_tokens(text: str) -> dict[str, set[str]]:
    """Extract relation IDs from labeled fields, never from matching prose words."""
    tokens = {"supersedes": set(), "superseded_by": set(), "related": set()}
    lines = _lines_outside_fences(text)
    index = 0
    in_related_decisions = False
    while index < len(lines):
        line = lines[index]
        if line is None:
            index += 1
            continue
        if re.match(r"^ {0,3}#{1,6}\s+", line):
            in_related_decisions = RELATED_DECISIONS_HEADING_RE.fullmatch(line) is not None

        match = RELATION_FIELD_RE.fullmatch(line) or RELATION_LABEL_FIELD_RE.fullmatch(line)
        if match is None:
            inline_match = INLINE_RELATED_FIELD_RE.search(line) if in_related_decisions else None
            if inline_match is not None:
                field_lines = [inline_match.group("value")]
                following_index = index + 1
                while following_index < len(lines):
                    following = lines[following_index]
                    if following is None or not following.strip():
                        break
                    if RELATION_FIELD_RE.fullmatch(following) or RELATION_LABEL_FIELD_RE.fullmatch(
                        following
                    ):
                        break
                    if re.match(r"^ {0,3}(?:[-*]\s+|#{1,6}\s)", following):
                        break
                    if re.match(r"^ {2,3}\S", following) is None:
                        break
                    field_lines.append(following.strip())
                    following_index += 1
                tokens["related"].update(RELATION_TOKEN_RE.findall("\n".join(field_lines)))
                index = following_index
                continue
            index += 1
            continue

        label = re.sub(r"\s+", " ", match.group("label").lower())
        if label == "supersedes":
            target = tokens["supersedes"]
        elif label == "superseded by":
            target = tokens["superseded_by"]
        else:
            target = tokens["related"]

        field_lines = [match.group("value")]
        following_index = index + 1
        while following_index < len(lines):
            following = lines[following_index]
            if following is None or not following.strip():
                break
            if RELATION_FIELD_RE.fullmatch(following) or RELATION_LABEL_FIELD_RE.fullmatch(
                following
            ):
                break
            if re.match(r"^ {0,3}(?:[-*]\s+|#{1,6}\s)", following):
                break
            if re.match(r"^ {2,3}\S", following) is None:
                break
            field_lines.append(following.strip())
            following_index += 1
        target.update(RELATION_TOKEN_RE.findall("\n".join(field_lines)))
        index = following_index

    declared_status = _status_value(text)
    if declared_status is not None and re.match(r"^\s*superseded\s+by\b", declared_status, re.I):
        tokens["superseded_by"].update(RELATION_TOKEN_RE.findall(declared_status))
    return tokens


def _entries(
    index_path: Path = DEFAULT_TOML,
    *,
    measurement: FileReadMeasurement | None = None,
    selection_receipt: dict[str, object] | None = None,
    source_inventory: dict[str, object] | None = None,
) -> tuple[list[AdrEntry], list[StaleReference]]:
    source_paths = _markdown_files(
        measurement=measurement,
        selection_receipt=selection_receipt,
    )
    indexed_entries = _index_entries_by_path(index_path)
    raw: list[tuple[Path, str, str, str]] = []
    source_bindings: list[tuple[str, str]] = []
    for path in source_paths:
        if not measured_is_file(path):
            raise FileNotFoundError(f"selected ADR source is absent: {_display_path(path)}")
        text = measured_read_text(path, encoding="utf-8")
        source_bindings.append(
            (
                _display_path(path),
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
        adr_id, title = _id_and_title(path, text)
        raw.append((path, text, adr_id, title))

    if source_inventory is not None:
        canonical_bindings = json.dumps(
            sorted(source_bindings), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        source_inventory.update(
            {
                "selected_count": len(source_bindings),
                "sha256": hashlib.sha256(canonical_bindings).hexdigest(),
                "binding": "sha256 of sorted [relative path, UTF-8 content sha256] pairs",
            }
        )

    known_ids = {adr_id for _, _, adr_id, _ in raw}
    entries: list[AdrEntry] = []
    stale: list[StaleReference] = []

    for path, text, adr_id, title in raw:
        all_tokens = set(RELATION_TOKEN_RE.findall(text))
        declared_relations = _declared_relation_tokens(text)
        supersedes_tokens = declared_relations["supersedes"]
        superseded_by_tokens = declared_relations["superseded_by"]
        related_tokens = declared_relations["related"]

        def resolve_many(
            tokens: set[str], *, source_path: Path = path, source_adr_id: str = adr_id
        ) -> tuple[str, ...]:
            resolved: set[str] = set()
            for token in tokens:
                normalized = _normalize_token(token, known_ids)
                if normalized is None:
                    stale.append(
                        StaleReference(
                            source=(source_path.relative_to(REPO_ROOT)).as_posix(),
                            token=token,
                            reason="referenced ADR id is not present in docs/adr",
                        )
                    )
                elif normalized != source_adr_id:
                    resolved.add(normalized)
            return tuple(sorted(resolved))

        resolve_many(all_tokens - supersedes_tokens - superseded_by_tokens - related_tokens)
        supersedes = resolve_many(supersedes_tokens)
        superseded_by = resolve_many(superseded_by_tokens)
        related = tuple(
            sorted(set(resolve_many(related_tokens)).union(supersedes).union(superseded_by))
        )

        relative_path = (path.relative_to(REPO_ROOT)).as_posix()
        indexed_entry = indexed_entries.get(relative_path)
        if indexed_entry is None:
            raise ValueError(
                f"{relative_path}: ADR file is missing from docs/adr/index.toml; "
                "add an [[adr]] row with a stable `topic` classification."
            )

        entries.append(
            AdrEntry(
                id=adr_id,
                title=title,
                status=_status(text),
                topic=indexed_entry.topic,
                package=indexed_entry.package,
                path=relative_path,
                supersedes=supersedes,
                superseded_by=superseded_by,
                related=related,
            )
        )

        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group("target").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if target.endswith(".md"):
                resolved = (path.parent / target).resolve()
                if not measured_is_file(resolved):
                    stale.append(
                        StaleReference(
                            source=(path.relative_to(REPO_ROOT)).as_posix(),
                            token=match.group("target"),
                            reason="markdown link target does not resolve",
                        )
                    )

    return sorted(entries, key=lambda entry: entry.id), sorted(
        set(stale), key=lambda item: (item.source, item.token, item.reason)
    )


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _escape_markdown_table_cell(value: str) -> str:
    escaped: list[str] = []
    backslash_count = 0
    for character in value:
        if character == "\\":
            escaped.append(character)
            backslash_count += 1
            continue
        if character == "|" and backslash_count % 2 == 0:
            escaped.append("\\")
        escaped.append(character)
        backslash_count = 0
    return "".join(escaped)


def render_toml(entries: list[AdrEntry], *, generated_on: str = DEFAULT_GENERATED_ON) -> str:
    lines = [
        "# Generated by tools/quality/validation/generate_adr_index.py.",
        "# Edit ADR Markdown files, then regenerate this index.",
        "",
        "[adr_index]",
        "schema_version = 1",
        f"generated_on = {_toml_string(generated_on)}",
        'source = "docs/adr"',
        "",
    ]
    for entry in entries:
        lines.extend(
            [
                "[[adr]]",
                f"id = {_toml_string(entry.id)}",
                f"title = {_toml_string(entry.title)}",
                f"status = {_toml_string(entry.status)}",
                f"topic = {_toml_string(entry.topic)}",
                f"package = {_toml_string(entry.package)}",
                f"path = {_toml_string(entry.path)}",
                f"supersedes = {_toml_array(entry.supersedes)}",
                f"superseded_by = {_toml_array(entry.superseded_by)}",
                f"related = {_toml_array(entry.related)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _link(entry: AdrEntry) -> str:
    name = Path(entry.path).name.replace("|", "%7C")
    return f"[{_escape_markdown_table_cell(entry.id)}]({name})"


def _table(entries: list[AdrEntry], *, include_topic: bool) -> list[str]:
    headers = (
        ["ADR", "Status", "Topic", "Package", "Title", "Related"]
        if include_topic
        else ["ADR", "Status", "Package", "Title", "Related"]
    )
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for entry in entries:
        related = _escape_markdown_table_cell(", ".join(entry.related) if entry.related else "-")
        row = [_link(entry), f"`{entry.status}`"]
        if include_topic:
            row.append(f"`{entry.topic}`")
        row.extend([f"`{entry.package}`", _escape_markdown_table_cell(entry.title), related])
        lines.append("| " + " | ".join(row) + " |")
    return lines


def render_index(entries: list[AdrEntry]) -> str:
    status_counts = Counter(entry.status for entry in entries)
    lines = [
        "# ADR Index",
        "",
        "> Generated from `docs/adr/index.toml`; do not hand-edit the tables.",
        "",
        "Theme navigation: [ADRs By Topic](by-topic.md).",
        "",
        "## Status Summary",
        "",
        "| Status | Count |",
        "| --- | --- |",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", "## ADRs By Status", ""])
    by_status: dict[str, list[AdrEntry]] = defaultdict(list)
    for entry in entries:
        by_status[entry.status].append(entry)
    for status in sorted(by_status):
        lines.extend([f"### {status}", "", *_table(by_status[status], include_topic=True), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_by_topic(entries: list[AdrEntry]) -> str:
    topic_counts = Counter(entry.topic for entry in entries)
    lines = [
        "# ADRs By Topic",
        "",
        "> Generated from `docs/adr/index.toml`; use this as the topic navigation surface.",
        "",
        "## Topic Summary",
        "",
        "| Topic | Description | Count |",
        "| --- | --- | --- |",
    ]
    for topic in STABLE_TOPICS:
        count = topic_counts.get(topic, 0)
        if count:
            lines.append(f"| `{topic}` | {TOPIC_DESCRIPTIONS[topic]} | {count} |")
    lines.extend(["", "## Topic Index", ""])
    by_topic: dict[str, list[AdrEntry]] = defaultdict(list)
    for entry in entries:
        by_topic[entry.topic].append(entry)
    for topic in STABLE_TOPICS:
        if topic not in by_topic:
            continue
        lines.extend([f"### {topic}", "", *_table(by_topic[topic], include_topic=False), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_stale_report(
    stale: list[StaleReference],
    *,
    generated_on: str = DEFAULT_GENERATED_ON,
    source_inventory: dict[str, object] | None = None,
    selection_receipt: dict[str, object] | None = None,
) -> str:
    lines = [
        "# ADR Stale Link Report",
        "",
    ]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", generated_on):
        lines.append(f"Generated on {generated_on} from selected Markdown files in `docs/adr/`.")
    else:
        lines.append(
            "Generated from selected Markdown files in `docs/adr/`; timestamp is source-controlled."
        )
    lines.append("")
    if source_inventory is not None and selection_receipt is not None:
        excluded_names = selection_receipt.get("excluded_names", [])
        excluded_text = ", ".join(f"`{name}`" for name in excluded_names) or "none"
        lines.extend(
            [
                "Input selector: `tools.lib.fs.iter_repository_files(REPO_ROOT)` paths whose "
                "parent is `docs/adr/` and suffix is `.md`.",
                f"Selected source inventory denominator: "
                f"{source_inventory.get('selected_count', 'unavailable')} documents; "
                f"excluded filename rules: {excluded_text}.",
                f"Source inventory SHA-256: `{source_inventory.get('sha256', 'unavailable')}` "
                "(sorted selected paths and each UTF-8 content SHA-256).",
                "Unresolved by construction: when Git metadata is available, untracked worktree "
                "paths are not selected; standalone-directory fallback enumerates filesystem "
                "paths. The Markdown-link regex does not implement full CommonMark; reference, "
                "nested, multiline, escaped, code-context and raw-HTML links, non-Markdown "
                "assets, external availability and fragment targets are not comprehensively "
                "checked. Git/process reads are not file-read receipts; parsed ADR status and "
                "relation fields do not prove decision authority or implementation.",
                "",
            ]
        )
    if not stale:
        lines.append("No stale ADR references were detected.")
        return "\n".join(lines).rstrip() + "\n"
    lines.extend(["| Source | Reference | Reason |", "| --- | --- | --- |"])
    for item in stale:
        lines.append(f"| `{item.source}` | `{item.token}` | {item.reason} |")
    return "\n".join(lines).rstrip() + "\n"


def _input_receipt(
    *,
    measurement: FileReadMeasurement,
    selection: dict[str, object],
    source_inventory: dict[str, object],
    output_operations: list[dict[str, object]],
    execution_status: str,
    verdict: str,
    complete_verdict: bool,
    error: str | None = None,
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema_version": "adr-index-input-receipt/v1",
        "execution_status": execution_status,
        "verdict": verdict,
        "selection": selection,
        "source_inventory": source_inventory,
        "output_operations": output_operations,
        "explicit_file_reads": measurement.snapshot(complete_verdict=complete_verdict),
        "unresolved_by_construction": [
            "With Git metadata, untracked working-tree paths are not selected by the cached-path "
            "enumerator; their existence and content are not established. Standalone-directory "
            "fallback has a different enumerator boundary.",
            "Git object/ref and subprocess internals are not observed by the explicit file-read "
            "receipt.",
            "Recognized ADR status and relation syntax is a parsed declaration; reading it does "
            "not prove decision authority, implementation, or operational behavior.",
            "The Markdown-link regex is not a full CommonMark parser; reference, nested, "
            "multiline, escaped, code-context, raw-HTML, non-Markdown, external and fragment "
            "targets are not comprehensively checked.",
        ],
    }
    if error is not None:
        receipt["error"] = error
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs differ.")
    parser.add_argument("--toml", type=Path, default=DEFAULT_TOML)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--by-topic", type=Path, default=DEFAULT_BY_TOPIC)
    parser.add_argument("--stale-report", type=Path, default=DEFAULT_STALE_REPORT)
    args = parser.parse_args(argv)

    selection: dict[str, object] = {}
    source_inventory: dict[str, object] = {}
    output_operations: list[dict[str, object]] = []
    summary = ""
    exit_code = 0
    execution_status = "COMPLETE"
    verdict = "not_established"
    error_text: str | None = None
    with measure_file_reads(REPO_ROOT) as measurement:
        try:
            entries, stale = _entries(
                args.toml,
                measurement=measurement,
                selection_receipt=selection,
                source_inventory=source_inventory,
            )
            generated_on = _generated_on_for_run(args)
            index_entries = (
                load_index_entries(args.toml, allow_legacy_topics=True) if args.check else entries
            )
            outputs = {
                args.toml: render_toml(entries, generated_on=generated_on),
                args.index: render_index(index_entries),
                args.by_topic: render_by_topic(index_entries),
                args.stale_report: render_stale_report(
                    stale,
                    generated_on=generated_on,
                    source_inventory=source_inventory,
                    selection_receipt=selection,
                ),
            }
        except (OSError, RuntimeError, UnicodeError, ValueError) as error:
            execution_status = "UNRUN"
            verdict = "not_established"
            error_text = f"{type(error).__name__}: {error}"
            summary = f"UNRUN: no complete ADR verdict; partial coverage: {error_text}"
            exit_code = 2
        else:
            changed: list[Path] = []
            try:
                for path, content in outputs.items():
                    exists = measured_is_file(path)
                    if exists and measured_read_text(path, encoding="utf-8") == content:
                        continue
                    changed.append(path)
                    if not args.check:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            path.write_text(content, encoding="utf-8")
                        except (OSError, UnicodeError) as error:
                            output_operations.append(
                                {
                                    "path": _display_path(path),
                                    "operation": "write_text",
                                    "status": "unwritable",
                                    "error": type(error).__name__,
                                }
                            )
                            raise
                        output_operations.append(
                            {
                                "path": _display_path(path),
                                "operation": "write_text",
                                "status": "written",
                                "encoding": "utf-8",
                                "characters": len(content),
                                "text_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                            }
                        )
            except (OSError, UnicodeError) as error:
                execution_status = "UNRUN"
                verdict = "not_established"
                error_text = f"{type(error).__name__}: {error}"
                summary = f"UNRUN: no complete ADR verdict; partial coverage: {error_text}"
                exit_code = 2
            else:
                if changed and args.check:
                    summary = "\n".join(f"out of date: {_display_path(path)}" for path in changed)
                    verdict = "drift"
                    exit_code = 1
                elif changed:
                    summary = "\n".join(f"updated: {_display_path(path)}" for path in changed)
                    verdict = "written"
                else:
                    summary = "ADR indexes are up to date."
                    verdict = "up_to_date"

        receipt = _input_receipt(
            measurement=measurement,
            selection=selection,
            source_inventory=source_inventory,
            output_operations=output_operations,
            execution_status=execution_status,
            verdict=verdict,
            complete_verdict=execution_status == "COMPLETE",
            error=error_text,
        )

    print(summary)
    print("Input receipt JSON:")
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return exit_code


def _generated_on_for_run(args: argparse.Namespace) -> str:
    if not args.check:
        return DEFAULT_GENERATED_ON

    if measured_is_file(args.toml):
        match = GENERATED_ON_RE.search(measured_read_text(args.toml, encoding="utf-8"))
        if match is not None:
            return match.group("date")

    if measured_is_file(args.stale_report):
        match = STALE_REPORT_DATE_RE.search(measured_read_text(args.stale_report, encoding="utf-8"))
        if match is not None:
            return match.group("date")

    return DEFAULT_GENERATED_ON


if __name__ == "__main__":
    raise SystemExit(main())
