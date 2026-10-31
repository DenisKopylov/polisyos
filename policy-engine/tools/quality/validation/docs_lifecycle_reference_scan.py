"""Owner for the docs lifecycle checker's removed-reference scan."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.lib.fs import FileReadMeasurement

type _ReferencePathSelection = tuple[
    tuple[Path, ...],
    tuple[Path, ...],
    dict[str, tuple[Path, ...]],
]

_AUTHORED_REFERENCE_SUFFIXES = frozenset(
    {
        ".md",
        ".mdx",
        ".rst",
        ".txt",
        ".html",
        ".htm",
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".bat",
        ".sql",
        ".graphql",
        ".proto",
        ".xml",
    }
)
_AUTHORED_REFERENCE_FILENAMES = frozenset(
    {"Dockerfile", "Makefile", "CODEOWNERS", ".gitignore", ".dockerignore", ".npmrc"}
)
_DOCUMENT_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".html", ".htm"})
_OUTSIDE_AUTHORED_PREFIX = "outside-live-authored:"
_NON_TEXT_CONTROL = re.compile(rb"[\x00-\x08\x0b\x0e-\x1f\x7f]")
_MAINTAINED_ROOTS = frozenset(
    {"src", "tools", "apps", "packages", "architecture", "schemas", "examples"}
)
_AMBIGUOUS_RESOURCE_NAMES = frozenset({"runs", "production_data", "_cache", "_build"})


def _outside_live_authored_role(relative: Path) -> str | None:
    """Classify paths outside the explicit authored-text reference claim.

    Documentation remains selected even inside fixture or vendor directories.
    Research scripts remain selected; captured payloads and source snapshots do not.
    This classification says nothing about references within omitted bytes.
    """
    suffix = relative.suffix.lower()
    if suffix in _DOCUMENT_SUFFIXES:
        return None
    parts = relative.parts
    if parts and parts[0] == "tests":
        return "test-source-literal-or-fixture"
    if parts and parts[0] == "vendor":
        return "vendor-payload"
    if parts[:2] in {("docs", "research"), ("docs", "archive"), ("docs", "superpowers")}:
        if any(part in {"raw", "postimages", "preimages", "source-snapshots"} for part in parts):
            return "captured-source-or-output"
        if suffix in {".txt", ".json", ".jsonl", ".log", ".xml", ".csv", ".tsv"}:
            return "recorded-research-or-archive-payload"
    if (
        suffix not in _AUTHORED_REFERENCE_SUFFIXES
        and relative.name not in _AUTHORED_REFERENCE_FILENAMES
    ):
        return "file-type-outside-authored-reference-grammar"
    return None


@dataclass(frozen=True, slots=True)
class _ReferenceScanDependencies[FindingT]:
    """Bind this scan to its facade's readers, selector, and finding type."""

    selection: Callable[[Path], _ReferencePathSelection]
    repo_path: Callable[[Path, Path], str]
    measure_file_reads: Callable[[Path], AbstractContextManager[FileReadMeasurement]]
    measured_read_bytes: Callable[[Path], bytes]
    reference_scan_text: Callable[[Path, str], str]
    path_set_sha256: Callable[[Iterable[str]], str]
    opaque_reference_format: Callable[[bytes], str | None]
    finding_factory: Callable[[str, str, str], FindingT]
    removed_redirect_stubs: Mapping[str, str]
    stale_direct_reference_targets: Mapping[str, str]
    reference_scope: str = "exhaustive"


def _path_set_sha256(paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.encode("utf-8", errors="surrogatepass"))
        digest.update(b"\0")
    return digest.hexdigest()


def _opaque_reference_format(payload: bytes) -> str | None:
    """Identify strong signatures for formats this text scanner does not decode."""
    if payload.startswith(b"\x1f\x8b"):
        return "gzip"
    if payload.startswith(b"\xfd7zXZ\x00"):
        return "xz"
    if payload.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip-container"
    if payload.startswith(b"SQLite format 3\x00"):
        return "sqlite-database"
    if payload.startswith(b"\x37\x7f\x06\x82"):
        return "sqlite-write-ahead-log"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png-image"
    if payload.startswith(b"\x1a\x45\xdf\xa3"):
        return "ebml-container"
    if payload.startswith(b"%PDF-"):
        return "pdf-document"
    if payload.startswith(b"\xff\xd8\xff"):
        return "jpeg-image"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return "gif-image"
    if payload.startswith(b"RIFF") and len(payload) >= 12:
        return "riff-container"
    if payload.startswith(b"\x80") and len(payload) > 1 and payload[1] in range(2, 6):
        return "python-pickle"
    if len(payload) >= 262 and payload[257:262] == b"ustar":
        return "tar-archive"
    return None


def _reference_scan_selection(
    repo_root: Path,
    *,
    iter_repository_files: Callable[[Path], Iterable[Path]],
    excluded_dirs: AbstractSet[str],
    excluded_filenames: AbstractSet[str],
    reference_scope: str = "exhaustive",
) -> _ReferencePathSelection:
    """Return the full tracked set, text selection, and selector exclusions."""
    if reference_scope not in {"exhaustive", "live-authored"}:
        raise ValueError(f"Unknown reference scope: {reference_scope}")
    tracked: list[Path] = []
    selected: list[Path] = []
    excluded: dict[str, list[Path]] = {}
    for path in iter_repository_files(repo_root):
        tracked.append(path)
        relative = path.relative_to(repo_root)
        excluded_directory = next(
            (part for part in relative.parts if part in excluded_dirs),
            None,
        )
        reason = None
        if excluded_directory is not None:
            reason = excluded_directory
        elif path.name in excluded_filenames:
            reason = f"filename:{path.name}"
        if reference_scope == "live-authored":
            if relative.suffix.lower() in _DOCUMENT_SUFFIXES:
                reason = None
            elif path.name in excluded_filenames:
                reason = f"filename:{path.name}"
            else:
                # Resolve the whole precedence class from the facade's actual policy:
                # dependencies/state win; resource basenames cannot hide owned code.
                environment_directory = next(
                    (
                        part
                        for part in relative.parts
                        if part in excluded_dirs - _AMBIGUOUS_RESOURCE_NAMES
                    ),
                    None,
                )
                if environment_directory is not None:
                    reason = f"dependency-or-environment:{environment_directory}"
                else:
                    reason = _outside_live_authored_role(relative)
                    if reason is None and relative.parts[0] not in _MAINTAINED_ROOTS:
                        reason = excluded_directory
            if reason is not None:
                reason = f"{_OUTSIDE_AUTHORED_PREFIX}{reason}"
        if reason is None:
            selected.append(path)
        else:
            excluded.setdefault(reason, []).append(path)
    return (
        tuple(tracked),
        tuple(selected),
        {reason: tuple(paths) for reason, paths in sorted(excluded.items())},
    )


def _iter_reference_scan_files(
    repo_root: Path, *, selection: Callable[[Path], _ReferencePathSelection]
) -> Iterable[Path]:
    _, selected, _ = selection(repo_root)
    yield from selected


def _reference_scan_text(
    relative: Path, text: str, *, reference_scan_text: Callable[[Path, str], str]
) -> str:
    if relative.suffix.lower() == ".json" and not text.strip():
        raise json.JSONDecodeError("empty JSON document", text, 0)
    return reference_scan_text(relative, text)


def _check_removed_stub_references[FindingT](
    repo_root: Path,
    *,
    dependencies: _ReferenceScanDependencies[FindingT],
    receipt: dict[str, object] | None = None,
) -> list[FindingT]:
    findings: list[FindingT] = []
    seen: set[tuple[str, str, str]] = set()

    def add_reference(relative: str, token: str, target: str) -> None:
        message = f"stale direct reference `{token}`; use `{target}`."
        key = ("removed_stub_reference", relative, message)
        if key in seen:
            return
        seen.add(key)
        findings.append(dependencies.finding_factory(key[0], relative, message))

    all_tracked_paths, tracked_paths, excluded_paths = dependencies.selection(repo_root)
    outside_scope = {
        reason: paths
        for reason, paths in excluded_paths.items()
        if dependencies.reference_scope == "live-authored"
        and reason.startswith(_OUTSIDE_AUTHORED_PREFIX)
    }
    unresolved_exclusions = {
        reason: paths for reason, paths in excluded_paths.items() if reason not in outside_scope
    }
    file_type_counts: dict[str, Counter[str]] = {}
    for label, path_group in (
        ("tracked", all_tracked_paths),
        ("selected", tracked_paths),
        (
            "outside_authored_claim",
            tuple(path for paths in outside_scope.values() for path in paths),
        ),
        (
            "unresolved_selector",
            tuple(path for paths in unresolved_exclusions.values() for path in paths),
        ),
    ):
        for path in path_group:
            file_type = path.suffix.lower() or "no-suffix"
            file_type_counts.setdefault(file_type, Counter())[label] += 1
    tracked_names = [path.relative_to(repo_root).as_posix() for path in tracked_paths]
    all_names = [path.relative_to(repo_root).as_posix() for path in all_tracked_paths]
    opaque_paths: dict[str, list[str]] = {}
    ambiguous_paths: list[str] = []
    scanned_names: list[str] = []
    input_hash_rows: list[str] = []

    for reason, paths in unresolved_exclusions.items():
        for path in paths:
            relative = dependencies.repo_path(repo_root, path)
            findings.append(
                dependencies.finding_factory(
                    "reference_scan_unresolved",
                    relative,
                    f"tracked input is outside the reference-scan selector ({reason}); "
                    "the lifecycle check cannot establish whether it contains a stale reference.",
                )
            )

    for removed_path, target in dependencies.removed_redirect_stubs.items():
        absolute = repo_root / removed_path
        members = [
            path for path in all_tracked_paths if path == absolute or absolute in path.parents
        ]
        if members:
            findings.append(
                dependencies.finding_factory(
                    "removed_stub_path",
                    removed_path,
                    f"removed redirect stub directory still exists; use `{target}`.",
                )
            )
            for path in members:
                add_reference(dependencies.repo_path(repo_root, path), removed_path, target)

    with dependencies.measure_file_reads(repo_root) as measured_reads:
        reads_before_scan = measured_reads.snapshot()["inputs"]
        assert isinstance(reads_before_scan, list)
        for path in tracked_paths:
            relative_path = path.relative_to(repo_root)
            relative = relative_path.as_posix()
            try:
                if path.is_symlink():
                    text = os.readlink(path)
                    content_sha256 = hashlib.sha256(
                        text.encode("utf-8", errors="surrogatepass")
                    ).hexdigest()
                    measured_reads.record(
                        path,
                        "readlink",
                        status="read",
                        text_sha256=content_sha256,
                    )
                else:
                    payload = dependencies.measured_read_bytes(path)
                    content_sha256 = hashlib.sha256(payload).hexdigest()
                    opaque_format = dependencies.opaque_reference_format(payload)
                    if (
                        opaque_format is None
                        and dependencies.reference_scope == "live-authored"
                        and _NON_TEXT_CONTROL.search(payload) is not None
                    ):
                        opaque_format = "non-text-control-bytes"
                    if opaque_format is not None:
                        opaque_paths.setdefault(opaque_format, []).append(relative)
                        input_hash_rows.append(
                            f"{relative}\0opaque:{opaque_format}\0{content_sha256}"
                        )
                        findings.append(
                            dependencies.finding_factory(
                                "reference_scan_unresolved",
                                relative,
                                f"tracked input has a `{opaque_format}` signature; the reference "
                                "scanner does not decode container payloads, so stale references "
                                "inside this input remain unresolved.",
                            )
                        )
                        continue
                    text = payload.decode("utf-8")
                scan_text = dependencies.reference_scan_text(relative_path, text)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                ambiguous_paths.append(relative)
                input_hash_rows.append(f"{relative}\0ambiguous:{type(exc).__name__}")
                findings.append(
                    dependencies.finding_factory(
                        "reference_scan_ambiguous",
                        relative,
                        "committed reference input is unreadable or malformed "
                        f"({type(exc).__name__}).",
                    )
                )
                continue
            scanned_names.append(relative)
            input_hash_rows.append(f"{relative}\0text\0{content_sha256}")
            for token, target in dependencies.stale_direct_reference_targets.items():
                if token in scan_text:
                    add_reference(relative, token, target)

        read_snapshot = measured_reads.snapshot(complete_verdict=True)
        read_records = read_snapshot["inputs"]
        assert isinstance(read_records, list)
        read_records = read_records[len(reads_before_scan) :]

    coverage_complete = not unresolved_exclusions and not opaque_paths and not ambiguous_paths
    if receipt is not None:
        receipt.update(
            {
                "schema": "docs-reference-scan-receipt/v1",
                "scope": (
                    "live-authored-removed-stub-reference-scan-only"
                    if dependencies.reference_scope == "live-authored"
                    else "removed-stub-reference-scan-only"
                ),
                "reference_scope": dependencies.reference_scope,
                "measured_property": (
                    "Known removed topology references in selected maintained authored text "
                    "after the declared documentary-reference role projection, "
                    "plus removed directory presence across every tracked path. No absence "
                    "claim is made about outside-scope payload contents."
                    if dependencies.reference_scope == "live-authored"
                    else "Known removed topology references across the exhaustive tracked-byte basis."
                ),
                "receipt_coverage": "partial",
                "lifecycle_gate_input_coverage": "not-measured-by-this-receipt",
                "reference_scan_status": "complete" if coverage_complete else "partial",
                "selected_reference_scan_complete": coverage_complete,
                "outside_authored_claim_path_count": sum(
                    len(paths) for paths in outside_scope.values()
                ),
                "unresolved_selector_path_count": sum(
                    len(paths) for paths in unresolved_exclusions.values()
                ),
                "authored_reference_grammar": (
                    {
                        "suffixes": sorted(_AUTHORED_REFERENCE_SUFFIXES),
                        "filenames": sorted(_AUTHORED_REFERENCE_FILENAMES),
                        "maintained_roots": sorted(_MAINTAINED_ROOTS),
                        "resource_name_disambiguation": sorted(_AMBIGUOUS_RESOURCE_NAMES),
                        "dependency_environment_rule": (
                            "Configured excluded directories minus resource_name_disambiguation; "
                            "explicit filename exclusions retain precedence."
                        ),
                    }
                    if dependencies.reference_scope == "live-authored"
                    else None
                ),
                "file_type_counts": {
                    file_type: dict(sorted(counts.items()))
                    for file_type, counts in sorted(file_type_counts.items())
                },
                "path_role_counts": {
                    **(
                        {
                            "selected-document": sum(
                                path.suffix.lower() in _DOCUMENT_SUFFIXES for path in tracked_paths
                            ),
                            "selected-source-config-or-text": sum(
                                path.suffix.lower() not in _DOCUMENT_SUFFIXES
                                for path in tracked_paths
                            ),
                        }
                        if dependencies.reference_scope == "live-authored"
                        else {"selected-exhaustive-input": len(tracked_paths)}
                    ),
                    **{reason: len(paths) for reason, paths in excluded_paths.items()},
                },
                "enumerator": (
                    "iter_repository_files: Git tracked paths for repositories, recursive walk "
                    "for standalone fixtures"
                ),
                "denominator": {
                    "tracked_path_count": len(all_names),
                    "tracked_path_sha256": dependencies.path_set_sha256(all_names),
                    "selected_path_count": len(tracked_paths),
                    "selected_path_sha256": dependencies.path_set_sha256(tracked_names),
                    "excluded_path_count": sum(len(paths) for paths in excluded_paths.values()),
                    "excluded_path_sha256": dependencies.path_set_sha256(
                        path.relative_to(repo_root).as_posix()
                        for paths in excluded_paths.values()
                        for path in paths
                    ),
                },
                "selector_exclusions": {
                    reason: {
                        "path_count": len(paths),
                        "path_sha256": dependencies.path_set_sha256(
                            path.relative_to(repo_root).as_posix() for path in paths
                        ),
                        "read_status": "not-read-by-selector",
                        "claim_role": "outside-live-authored-claim"
                        if reason in outside_scope
                        else "unresolved",
                    }
                    for reason, paths in excluded_paths.items()
                },
                "read_evidence": {
                    "operation_count": len(read_records),
                    "operation_sha256": hashlib.sha256(
                        json.dumps(read_records, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                    "input_outcomes_sha256": dependencies.path_set_sha256(input_hash_rows),
                    "operations": read_records,
                },
                "scanned_text_path_count": len(scanned_names),
                "opaque_formats": {
                    format_name: len(paths) for format_name, paths in sorted(opaque_paths.items())
                },
                "opaque_reference_status": (
                    "byte-read-but-not-decoded" if opaque_paths else "none"
                ),
                "ambiguous_input_count": len(ambiguous_paths),
                "excluded_inputs": {
                    reason: [path.relative_to(repo_root).as_posix() for path in paths]
                    for reason, paths in excluded_paths.items()
                },
                "unresolved_by_construction": [
                    "This receipt measures only the removed-stub reference scan, not the full "
                    "docs lifecycle gate. Other docs lifecycle checks inspect ADR/TOML and "
                    "generator inputs, MkDocs YAML, PDC/plan/redirect/archive/README documents, "
                    "package contracts, and extension-example manifests; their reads and "
                    "presence probes are outside this receipt.",
                    "Tracked-path enumeration via iter_repository_files is outside the explicit "
                    "file-reader receipt (Git subprocess for repositories; recursive walk for "
                    "standalone fixtures).",
                    "Historical research-audit suppression still trusts front-matter markers and "
                    "40-hex commit shape; it is not content-bound proof (P32).",
                    "Archive-map member-path suppression trusts digest-string, count, and member "
                    "metadata shapes; it does not resolve the archive or verify member bytes "
                    "against those digests, so archive content and historical reference role "
                    "remain unverified (P32).",
                    "Markdown archive-table suppression follows recognized column headings, "
                    "while journal suppression follows the docs/superpowers/journals path and "
                    ".md/.json suffix; these are separate bounded reference-role rules and do "
                    "not attest record authenticity or authority.",
                    *(
                        [
                            "Selector-excluded tracked paths are named in selector_exclusions "
                            "and have per-path unresolved findings."
                        ]
                        if unresolved_exclusions
                        else []
                    ),
                    *(
                        [
                            "Typed outside-live-authored classes are not searched or certified "
                            "free of references. Their complete path counts and digests remain "
                            "in the denominator and selector_exclusions. Exhaustive mode retains "
                            "the unknown/UNRUN boundary for these same inputs."
                        ]
                        if outside_scope
                        else []
                    ),
                    *(
                        [
                            "Opaque container payloads are not decoded; format counts and "
                            "path-set digests identify each unresolved class."
                        ]
                        if opaque_paths
                        else []
                    ),
                    *(
                        [
                            "Unknown invalid-UTF-8 or malformed JSON inputs remain ambiguous "
                            "and blocking."
                        ]
                        if ambiguous_paths
                        else []
                    ),
                ],
            }
        )

    return findings
