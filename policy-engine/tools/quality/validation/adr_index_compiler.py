"""Parse ADR sources and render the canonical ADR index artifacts."""

from __future__ import annotations

import re
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from tools.lib.fs import measured_read_text

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


def load_index_entries(path: Path, *, allow_legacy_topics: bool = False) -> list[AdrEntry]:
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
