"""Generate ADR TOML and Markdown indexes from ``docs/adr``."""

from __future__ import annotations

import argparse
import hashlib
import json
import re  # noqa: F401 - preserve the historical facade namespace
from pathlib import Path

from tools.lib.fs import (
    FileReadMeasurement,
    iter_repository_files,
    measure_file_reads,
    measured_is_file,
    measured_read_text,
)
from tools.quality.validation.adr_index_compiler import (  # noqa: F401 - retained caller seams
    ADR_HEADING_RE,
    DEFAULT_GENERATED_ON,
    FENCE_RE,
    GENERATED_ON_RE,
    INLINE_RELATED_FIELD_RE,
    KNOWN_STATUSES,
    LEGACY_TOPIC_ALIASES,
    MARKDOWN_LINK_RE,
    PACKAGE_KEYWORDS,
    RELATED_DECISIONS_HEADING_RE,
    RELATION_FIELD_RE,
    RELATION_LABEL_FIELD_RE,
    RELATION_TOKEN_RE,
    SKIP_FILENAMES,
    STABLE_TOPICS,
    STALE_REPORT_DATE_RE,
    STATUS_FIELD_RE,
    STATUS_HEADING_RE,
    STATUS_TOKEN_RE,
    TOPIC_DEFINITIONS,
    TOPIC_DESCRIPTIONS,
    TOPIC_KEYWORDS,
    AdrEntry,
    StaleReference,
    _classify_package,
    _classify_topic,
    _declared_relation_tokens,
    _escape_markdown_table_cell,
    _has_keyword,
    _id_and_title,
    _lines_outside_fences,
    _link,
    _normalize_token,
    _normalize_topic,
    _required_string,
    _status,
    _status_value,
    _string_array,
    _table,
    _toml_array,
    _toml_string,
    _topic_error_prefix,
    render_by_topic,
    render_index,
    render_stale_report,
    render_toml,
)
from tools.quality.validation.adr_index_compiler import (
    load_index_entries as _load_index_entries,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR_DIR = REPO_ROOT / "docs" / "adr"
DEFAULT_TOML = ADR_DIR / "index.toml"
DEFAULT_INDEX = ADR_DIR / "index.md"
DEFAULT_BY_TOPIC = ADR_DIR / "by-topic.md"
DEFAULT_STALE_REPORT = REPO_ROOT / "docs" / "archive" / "reports" / "ADR_STALE_LINK_REPORT.md"


def load_index_entries(
    path: Path = DEFAULT_TOML, *, allow_legacy_topics: bool = False
) -> list[AdrEntry]:
    """Load and validate ADR index entries while preserving the facade default path."""
    return _load_index_entries(path, allow_legacy_topics=allow_legacy_topics)


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


def _index_entries_by_path(index_path: Path) -> dict[str, AdrEntry]:
    if not measured_is_file(index_path):
        raise ValueError(
            f"{_display_path(index_path)} is missing; add ADR rows with stable topics."
        )
    return {entry.path: entry for entry in load_index_entries(index_path, allow_legacy_topics=True)}


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
