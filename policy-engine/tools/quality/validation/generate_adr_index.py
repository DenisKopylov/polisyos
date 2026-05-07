#!/usr/bin/env python3
"""Generate ADR TOML and Markdown indexes from ``docs/adr``."""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

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
STATUS_SECTION_RE = re.compile(r"(?im)^## Status\s*\n\s*(?P<status>[A-Za-z_-]+)")
STATUS_LIST_RE = re.compile(r"(?im)^-\s*(?:\*\*)?Status(?:\*\*)?:\s*(?P<status>[A-Za-z_-]+)")
RELATION_TOKEN_RE = re.compile(r"\b(?:ADR-(?:RSR-)?\d{3,4}|RSR-\d{4})\b")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((?P<target>[^)]+)\)")
GENERATED_ON_RE = re.compile(r'^generated_on\s*=\s*"(?P<date>[^"]+)"$', flags=re.MULTILINE)
STALE_REPORT_DATE_RE = re.compile(r"^Generated on (?P<date>\d{4}-\d{2}-\d{2}) from ", flags=re.MULTILINE)
DEFAULT_GENERATED_ON = "source-controlled"

TOPIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("repository-structure", ("repository-structure", "workspace", "root", "package", "topology", "fixture", "codemod", "cycle", "decomposition")),
    ("docs", ("docs", "documentation", "diataxis", "archive", "plan")),
    ("release", ("release", "semver", "versioning", "deprecation")),
    ("security", ("security", "secret", "tenant", "signing", "key-rotation", "trust-store", "fedramp")),
    ("runtime", ("runtime", "rate-limiting", "idempotency", "audit-trail", "cas")),
    ("frontend-design", ("design", "atlas", "janus", "glyph", "theme", "frontend", "dashboard")),
    ("scientist", ("scientist", "claim", "research-dag", "voi", "node", "decision-packet", "readiness")),
    ("fabric", ("fabric", "connector", "world", "wvs", "wgi", "wdi", "streaming")),
    ("lex", ("lex", "legal", "law", "norm", "normpack")),
    ("foundry", ("foundry", "method", "simulation", "estimator", "causal-estimator")),
    ("data", ("data", "dataset", "lakehouse", "artifact", "knowledge", "skg", "snapshot")),
    ("ir", ("ir", "schema", "trinity", "policy-surface", "analytics", "transport")),
    ("causal", ("causal", "transportability", "sutva", "backdoor", "collider", "pag", "dag", "graph", "identification")),
    ("architecture", ("architecture", "boundary", "import", "layered", "governance")),
)

PACKAGE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("polisyos.scientist", ("scientist", "claim", "research-dag", "voi", "node", "decision-packet")),
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


def _markdown_files() -> list[Path]:
    return sorted(path for path in ADR_DIR.glob("*.md") if path.name not in SKIP_FILENAMES)


def _status(text: str) -> str:
    match = STATUS_SECTION_RE.search(text) or STATUS_LIST_RE.search(text)
    if match is None:
        return "accepted"
    return match.group("status").strip().lower().replace("_", "-")


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

    stem_match = re.match(r"(?P<id>\d{4}|ADR-\d{3}|repository-structure-\d{4})-(?P<slug>.+)", path.stem)
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
    return "architecture"


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


def _tokens_from_lines(text: str, labels: tuple[str, ...]) -> set[str]:
    tokens: set[str] = set()
    for line in text.splitlines():
        lowered = line.lower()
        if any(label in lowered for label in labels):
            tokens.update(RELATION_TOKEN_RE.findall(line))
    return tokens


def _entries() -> tuple[list[AdrEntry], list[StaleReference]]:
    raw: list[tuple[Path, str, str, str]] = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        adr_id, title = _id_and_title(path, text)
        raw.append((path, text, adr_id, title))

    known_ids = {adr_id for _, _, adr_id, _ in raw}
    entries: list[AdrEntry] = []
    stale: list[StaleReference] = []

    for path, text, adr_id, title in raw:
        all_tokens = set(RELATION_TOKEN_RE.findall(text))
        supersedes_tokens = _tokens_from_lines(text, ("supersedes", "replaces"))
        superseded_by_tokens = _tokens_from_lines(text, ("superseded by", "replaced by"))
        related_tokens = _tokens_from_lines(text, ("related", "extends", "extended by"))

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

        entries.append(
            AdrEntry(
                id=adr_id,
                title=title,
                status=_status(text),
                topic=_classify_topic(path, title),
                package=_classify_package(path, title),
                path=(path.relative_to(REPO_ROOT)).as_posix(),
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
                if not resolved.is_file():
                    stale.append(
                        StaleReference(
                            source=(path.relative_to(REPO_ROOT)).as_posix(),
                            token=match.group("target"),
                            reason="markdown link target does not resolve",
                        )
                    )

    return sorted(entries, key=lambda entry: entry.id), sorted(set(stale), key=lambda item: (item.source, item.token, item.reason))


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def render_toml(entries: list[AdrEntry], *, generated_on: str = DEFAULT_GENERATED_ON) -> str:
    lines = [
        "# Generated by tools/quality/validation/generate_adr_index.py.",
        "# Edit ADR Markdown files, then regenerate this index.",
        "",
        "[adr_index]",
        'schema_version = 1',
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
    name = Path(entry.path).name
    return f"[{entry.id}]({name})"


def _table(entries: list[AdrEntry], *, include_topic: bool) -> list[str]:
    headers = ["ADR", "Status", "Topic", "Package", "Title", "Related"] if include_topic else ["ADR", "Status", "Package", "Title", "Related"]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for entry in entries:
        related = ", ".join(entry.related) if entry.related else "-"
        row = [_link(entry), f"`{entry.status}`"]
        if include_topic:
            row.append(f"`{entry.topic}`")
        row.extend([f"`{entry.package}`", entry.title, related])
        lines.append("| " + " | ".join(row) + " |")
    return lines


def render_index(entries: list[AdrEntry]) -> str:
    status_counts = Counter(entry.status for entry in entries)
    lines = [
        "# ADR Index",
        "",
        "> Generated from `docs/adr/index.toml`; do not hand-edit the tables.",
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
        "| Topic | Count |",
        "| --- | --- |",
    ]
    for topic, count in sorted(topic_counts.items()):
        lines.append(f"| `{topic}` | {count} |")
    lines.extend(["", "## Topic Index", ""])
    by_topic: dict[str, list[AdrEntry]] = defaultdict(list)
    for entry in entries:
        by_topic[entry.topic].append(entry)
    for topic in sorted(by_topic):
        lines.extend([f"### {topic}", "", *_table(by_topic[topic], include_topic=False), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_stale_report(
    stale: list[StaleReference], *, generated_on: str = DEFAULT_GENERATED_ON
) -> str:
    lines = [
        "# ADR Stale Link Report",
        "",
    ]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", generated_on):
        lines.append(f"Generated on {generated_on} from `docs/adr/**`.")
    else:
        lines.append("Generated from `docs/adr/**`; timestamp is source-controlled.")
    lines.append("")
    if not stale:
        lines.append("No stale ADR references were detected.")
        return "\n".join(lines).rstrip() + "\n"
    lines.extend(["| Source | Reference | Reason |", "| --- | --- | --- |"])
    for item in stale:
        lines.append(f"| `{item.source}` | `{item.token}` | {item.reason} |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs differ.")
    parser.add_argument("--toml", type=Path, default=DEFAULT_TOML)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--by-topic", type=Path, default=DEFAULT_BY_TOPIC)
    parser.add_argument("--stale-report", type=Path, default=DEFAULT_STALE_REPORT)
    args = parser.parse_args()

    entries, stale = _entries()
    generated_on = _generated_on_for_run(args)
    outputs = {
        args.toml: render_toml(entries, generated_on=generated_on),
        args.index: render_index(entries),
        args.by_topic: render_by_topic(entries),
        args.stale_report: render_stale_report(stale, generated_on=generated_on),
    }
    changed: list[Path] = []
    for path, content in outputs.items():
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        changed.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    if changed and args.check:
        for path in changed:
            print(f"out of date: {path.relative_to(REPO_ROOT)}")
        return 1
    if changed:
        for path in changed:
            print(f"updated: {path.relative_to(REPO_ROOT)}")
    else:
        print("ADR indexes are up to date.")
    return 0


def _generated_on_for_run(args: argparse.Namespace) -> str:
    if not args.check:
        return DEFAULT_GENERATED_ON

    if args.toml.exists():
        match = GENERATED_ON_RE.search(args.toml.read_text(encoding="utf-8"))
        if match is not None:
            return match.group("date")

    if args.stale_report.exists():
        match = STALE_REPORT_DATE_RE.search(args.stale_report.read_text(encoding="utf-8"))
        if match is not None:
            return match.group("date")

    return DEFAULT_GENERATED_ON


if __name__ == "__main__":
    raise SystemExit(main())
