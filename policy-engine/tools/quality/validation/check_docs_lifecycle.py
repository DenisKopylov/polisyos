#!/usr/bin/env python3
"""Validate the Phase 6.4 documentation lifecycle conversion contract."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lib.document_references import reference_scan_text
from tools.lib.fs import (
    iter_repository_files as _iter_repository_files,
)
from tools.lib.fs import (
    measure_file_reads,
    measured_read_bytes,
)
from tools.lib.imports import repo_root_from
from tools.quality.validation import check_extension_examples, generate_adr_index

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

REPO_ROOT = repo_root_from(__file__)

AUTHORING_SECTIONS = (
    "## Purpose",
    "## Allowed File Categories",
    "## Public/Private Boundary",
    "## Naming Convention",
    "## Test Location",
    "## Fixture/Data Policy",
    "## Generated File Policy",
    "## Extension Points",
    "## Deprecation And Shim Policy",
)

HIGH_VOLUME_SUBTREE_DOCS: dict[str, tuple[str, ...]] = {
    "docs/adr": ("README.md", "AUTHORING.md", "index.md", "by-topic.md", "index.toml"),
    "docs/archive/reports": ("README.md", "AUTHORING.md", "index.md"),
    "schemas/snapshots/ir": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/foundry/methods/catalog/causal": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/ir/analytics": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/foundry/methods": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/data_forge/domains/legal/batch": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/data_forge/domains/catalog/batch": ("README.md", "AUTHORING.md"),
    "src/polisyos/scientist/agent": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/scientist/methods/search": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/scientist/orchestration/engine": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/runtime/http/services": ("README.md", "AUTHORING.md"),
    "src/polisyos/fabric/connectors/sources": ("README.md", "AUTHORING.md"),
    "apps/runtime-dashboard/src/shared/ui": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/api": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/features": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/test": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/methods/catalog/causal": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "tests/unit/core/security": ("README.md", "AUTHORING.md"),
    "tests/unit/data_forge": ("README.md", "AUTHORING.md", "index.md"),
    "tests/unit/data_forge/domains/academic/batch": ("README.md", "AUTHORING.md"),
    "tests/unit/data_forge/legal_batch": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/agent_sim": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/methods": ("README.md", "AUTHORING.md"),
    "tests/unit/ir/analytics": ("README.md", "AUTHORING.md"),
    "tests/unit/runtime/http": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/agent": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/governance": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/orchestration/engine": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/search": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/nodes": ("README.md", "AUTHORING.md", "index.md"),
    "tests/_data": ("README.md", "AUTHORING.md", "index.md"),
    "tests/_golden": ("README.md", "AUTHORING.md"),
    "tests/_helpers": ("README.md", "AUTHORING.md"),
}

NAV_REQUIRED_TOKENS = (
    "ADR Index: adr/index.md",
    "ADRs By Topic: adr/by-topic.md",
    "Authoring Contract: adr/AUTHORING.md",
)
POLICY_DESIGN_CASE_SECOND_PACK_ADRS = {
    "0162": "docs/adr/0162-human-oversight-publication-external-audit-authority.md",
    "0163": "docs/adr/0163-lifecycle-ddm-ex-post-calibration.md",
    "0164": "docs/adr/0164-run-cost-proportionality-evidence-budget-governance.md",
    "0165": "docs/adr/0165-formal-policy-case-substrate-invariant-specs.md",
}
POLICY_DESIGN_CASE_SECOND_PACK_SURFACES = (
    "docs/system-design-decisions/policy-design-best-in-class-operating-model.md",
    "docs/plans/archive/2026-05-19-policyos-policy-design-case-implementation-plan.md",
    "docs/system-design-decisions/policy-design-case-decision-log.md",
)
POLICY_DESIGN_CASE_WAVE26_PLAN_CHECKBOXES = (
    "- [x] Second ADR pack is accepted and indexed.",
    "- [x] Later governance work has explicit ADR authority.",
)
KNOWN_REDIRECT_STUBS = ("frontend",)
REDIRECT_REQUIRED_FIELDS = (
    "owner",
    "target_path",
    "reason",
    "created_date",
    "sunset_date",
    "removal_gate",
)
REDIRECT_COMPATIBILITY_ADR_FIELD = "compatibility_adr"
REDIRECT_MAX_LIFETIME_DAYS = 90
REMOVED_REDIRECT_STUBS = {
    "/".join(("tests", "architecture")): "/".join(("tests", "repo_quality", "architecture")),
}
STALE_DIRECT_REFERENCE_TARGETS = {
    **REMOVED_REDIRECT_STUBS,
    "/".join(("frontend", "runtime-dashboard")): "/".join(("apps", "runtime-dashboard")),
    "/".join(("frontend", "runtime-api-client")): "/".join(("packages", "runtime-api-client")),
}
REFERENCE_SCAN_EXCLUDED_DIRS = frozenset(
    (
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".polisyos",
        "_build",
        "_cache",
        "__pycache__",
        "node_modules",
        "production_data",
        "runs",
    )
)
REFERENCE_SCAN_EXCLUDED_FILENAMES = frozenset(("package-lock.json", "pnpm-lock.yaml"))
GENERATED_PLAN_AGGREGATES = {
    "LEDGER.md": "tools/quality/validation/check_debt_ledger.py",
}


@dataclass(frozen=True)
class LifecycleFinding:
    check: str
    path: str
    message: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing docs/, architecture/, and examples/.",
    )
    return parser


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _repo_path(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return {}


def _parse_iso_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _public_surface_contract(repo_root: Path) -> Path:
    return repo_root / "architecture" / "public_surface" / "contract.toml"


def _is_redirect_stub(path: Path) -> bool:
    metadata = _front_matter(path)
    if metadata.get("redirect_stub", "").lower() == "true":
        return True
    text = path.read_text(encoding="utf-8").lower()
    relative = path.as_posix()
    if relative.endswith("frontend/README.md"):
        return "legacy handoff path" in text or "active javascript workspaces moved" in text
    return False


def _redirect_stub_directory(relative: str) -> str:
    return f"{relative.removesuffix('/README.md')}/"


def _compatibility_adr_finding(
    repo_root: Path,
    relative: str,
    metadata: dict[str, str],
) -> LifecycleFinding | None:
    adr = metadata.get(REDIRECT_COMPATIBILITY_ADR_FIELD, "").strip()
    if not adr:
        return LifecycleFinding(
            "redirect_stub",
            relative,
            "redirect stub sunset exceeds the 90-day policy without `compatibility_adr`.",
        )
    adr_path = repo_root / adr
    if not adr.startswith("docs/adr/") or not adr_path.is_file():
        return LifecycleFinding(
            "redirect_stub",
            relative,
            "redirect stub `compatibility_adr` must reference an existing ADR.",
        )
    stub_directory = _redirect_stub_directory(relative)
    if stub_directory not in adr_path.read_text(encoding="utf-8"):
        return LifecycleFinding(
            "redirect_stub",
            relative,
            f"redirect stub `compatibility_adr` must declare `{stub_directory}`.",
        )
    return None


def check_adr_index(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    adr_root = repo_root / "docs" / "adr"
    index_toml = adr_root / "index.toml"
    index_md = adr_root / "index.md"
    by_topic = adr_root / "by-topic.md"
    stale_report = repo_root / "docs" / "archive" / "reports" / "ADR_STALE_LINK_REPORT.md"

    if not index_toml.is_file():
        return [
            LifecycleFinding(
                "adr_index",
                _repo_path(repo_root, index_toml),
                "ADR machine-readable index is missing.",
            )
        ]

    data = _load_toml(index_toml)
    rows = data.get("adr", [])
    if not isinstance(rows, list):
        findings.append(
            LifecycleFinding("adr_index", _repo_path(repo_root, index_toml), "adr rows missing.")
        )
        rows = []

    indexed_paths = {str(row.get("path", "")) for row in rows if isinstance(row, dict)}
    expected_paths = {_repo_path(repo_root, path) for path in generate_adr_index._markdown_files()}
    for path in sorted(expected_paths - indexed_paths):
        findings.append(LifecycleFinding("adr_index", path, "ADR file is not indexed."))
    for path in sorted(indexed_paths - expected_paths):
        findings.append(
            LifecycleFinding("adr_index", path, "ADR index references a missing ADR file.")
        )

    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path", "docs/adr/index.toml"))
        for field in ("id", "title", "status", "topic", "package"):
            if not str(row.get(field, "")).strip():
                findings.append(LifecycleFinding("adr_index", path, f"ADR row missing `{field}`."))

    selection_receipt: dict[str, object] = {}
    source_inventory: dict[str, object] = {}
    entries, stale = generate_adr_index._entries(
        index_toml,
        selection_receipt=selection_receipt,
        source_inventory=source_inventory,
    )
    generated_on = str(data.get("adr_index", {}).get("generated_on", "source-controlled"))
    expected_outputs = {
        index_toml: generate_adr_index.render_toml(entries, generated_on=generated_on),
        index_md: generate_adr_index.render_index(entries),
        by_topic: generate_adr_index.render_by_topic(entries),
        stale_report: generate_adr_index.render_stale_report(
            stale,
            generated_on=generated_on,
            source_inventory=source_inventory,
            selection_receipt=selection_receipt,
        ),
    }
    for path, expected in expected_outputs.items():
        if not path.is_file():
            findings.append(
                LifecycleFinding(
                    "adr_index", _repo_path(repo_root, path), "generated file missing."
                )
            )
            continue
        if path.read_text(encoding="utf-8") != expected:
            findings.append(
                LifecycleFinding(
                    "adr_index",
                    _repo_path(repo_root, path),
                    "generated ADR output is stale; run generate-adr-index.",
                )
            )

    return findings


def check_docs_nav(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    nav_fragment = repo_root / "architecture" / "tooling" / "mkdocs" / "nav" / "70-adrs.yml"
    generated = repo_root / "architecture" / "tooling" / "mkdocs" / "generated.yml"
    for path in (nav_fragment, generated):
        if not path.is_file():
            findings.append(
                LifecycleFinding(
                    "docs_nav", _repo_path(repo_root, path), "MkDocs nav file missing."
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        for token in NAV_REQUIRED_TOKENS:
            if token not in text:
                findings.append(
                    LifecycleFinding("docs_nav", _repo_path(repo_root, path), f"missing {token}")
                )
    return findings


def check_policy_design_case_second_governance_pack(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    index_path = repo_root / "docs" / "adr" / "index.toml"
    indexed_rows: dict[str, dict[str, object]] = {}
    if index_path.is_file():
        data = _load_toml(index_path)
        rows = data.get("adr", [])
        if isinstance(rows, list):
            indexed_rows = {
                str(row.get("id", "")): row
                for row in rows
                if isinstance(row, dict) and str(row.get("id", "")).startswith("016")
            }

    for adr_id, adr_path in POLICY_DESIGN_CASE_SECOND_PACK_ADRS.items():
        full_path = repo_root / adr_path
        if not full_path.is_file():
            findings.append(
                LifecycleFinding("pdc_second_adr_pack", adr_path, "second-pack ADR file missing.")
            )
            continue
        row = indexed_rows.get(adr_id)
        if row is None:
            findings.append(
                LifecycleFinding(
                    "pdc_second_adr_pack",
                    adr_path,
                    "second-pack ADR is missing from docs/adr/index.toml.",
                )
            )
            continue
        if row.get("path") != adr_path or row.get("status") != "accepted":
            findings.append(
                LifecycleFinding(
                    "pdc_second_adr_pack",
                    adr_path,
                    "second-pack ADR index row must preserve accepted status and path.",
                )
            )

    for surface in POLICY_DESIGN_CASE_SECOND_PACK_SURFACES:
        path = repo_root / surface
        if not path.is_file():
            findings.append(
                LifecycleFinding(
                    "pdc_second_adr_pack",
                    surface,
                    "second-pack governance surface missing.",
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        for adr_id, adr_path in POLICY_DESIGN_CASE_SECOND_PACK_ADRS.items():
            if f"ADR-{adr_id}" not in text:
                findings.append(
                    LifecycleFinding(
                        "pdc_second_adr_pack",
                        surface,
                        f"surface does not cite ADR-{adr_id}.",
                    )
                )
            if surface.endswith("policyos-policy-design-case-implementation-plan.md"):
                filename = Path(adr_path).name
                if filename not in text:
                    findings.append(
                        LifecycleFinding(
                            "pdc_second_adr_pack",
                            surface,
                            f"plan does not link {filename}.",
                        )
                    )
        if surface.endswith("policyos-policy-design-case-implementation-plan.md"):
            for checkbox in POLICY_DESIGN_CASE_WAVE26_PLAN_CHECKBOXES:
                if checkbox not in text:
                    findings.append(
                        LifecycleFinding(
                            "pdc_second_adr_pack",
                            surface,
                            f"Wave 26 exit fence is not checked: {checkbox}",
                        )
                    )
    return findings


def check_active_plans(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    active_root = repo_root / "docs" / "plans" / "active"
    for path in _iter_repository_files(repo_root):
        if path.parent != active_root or path.suffix != ".md":
            continue
        producer = GENERATED_PLAN_AGGREGATES.get(path.name)
        if producer is not None:
            if f"Generated by `{producer} --write`." not in path.read_text(encoding="utf-8"):
                findings.append(
                    LifecycleFinding(
                        "active_plan_aggregate",
                        _repo_path(repo_root, path),
                        "generated aggregate identity is ambiguous; expected its canonical producer.",
                    )
                )
            continue
        front_matter = _front_matter(path)
        for field in ("status", "owner"):
            if not front_matter.get(field):
                findings.append(
                    LifecycleFinding(
                        "active_plan_metadata",
                        _repo_path(repo_root, path),
                        f"active plan missing `{field}` front matter.",
                    )
                )
        text = path.read_text(encoding="utf-8").lower()
        if "accepted final closeout" in text:
            findings.append(
                LifecycleFinding(
                    "active_plan_metadata",
                    _repo_path(repo_root, path),
                    "active plan contains accepted final closeout evidence; move it to docs/plans/archive.",
                )
            )
    return findings


def check_redirect_stubs(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    readmes = (path for path in _iter_repository_files(repo_root) if path.name == "README.md")

    for readme in sorted(readmes):
        if not _is_redirect_stub(readme):
            continue
        metadata = _front_matter(readme)
        relative = _repo_path(repo_root, readme)
        if not metadata.get("sunset_date"):
            findings.append(
                LifecycleFinding(
                    "redirect_stub",
                    relative,
                    "redirect stub missing `sunset_date` metadata.",
                )
            )
            continue
        missing_required_field = False
        for field in REDIRECT_REQUIRED_FIELDS:
            if not metadata.get(field):
                findings.append(
                    LifecycleFinding(
                        "redirect_stub",
                        relative,
                        f"redirect stub missing `{field}` metadata.",
                    )
                )
                missing_required_field = True
                break
        if missing_required_field:
            continue
        created_date = _parse_iso_date(metadata.get("created_date", ""))
        sunset_date = _parse_iso_date(metadata.get("sunset_date", ""))
        if created_date is None:
            findings.append(
                LifecycleFinding(
                    "redirect_stub",
                    relative,
                    "redirect stub has invalid `created_date` metadata.",
                )
            )
            continue
        if sunset_date is None:
            findings.append(
                LifecycleFinding(
                    "redirect_stub",
                    relative,
                    "redirect stub has invalid `sunset_date` metadata.",
                )
            )
            continue
        if (sunset_date - created_date).days > REDIRECT_MAX_LIFETIME_DAYS:
            compatibility_finding = _compatibility_adr_finding(repo_root, relative, metadata)
            if compatibility_finding is not None:
                findings.append(compatibility_finding)
    return findings


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
) -> tuple[tuple[Path, ...], tuple[Path, ...], dict[str, tuple[Path, ...]]]:
    """Return the full tracked set, text selection, and selector exclusions."""
    tracked: list[Path] = []
    selected: list[Path] = []
    excluded: dict[str, list[Path]] = {}
    for path in _iter_repository_files(repo_root):
        tracked.append(path)
        relative = path.relative_to(repo_root)
        excluded_directory = next(
            (part for part in relative.parts if part in REFERENCE_SCAN_EXCLUDED_DIRS),
            None,
        )
        if excluded_directory is not None:
            excluded.setdefault(excluded_directory, []).append(path)
        elif path.name in REFERENCE_SCAN_EXCLUDED_FILENAMES:
            excluded.setdefault(f"filename:{path.name}", []).append(path)
        else:
            selected.append(path)
    return (
        tuple(tracked),
        tuple(selected),
        {reason: tuple(paths) for reason, paths in sorted(excluded.items())},
    )


def _iter_reference_scan_files(repo_root: Path) -> Iterable[Path]:
    _, selected, _ = _reference_scan_selection(repo_root)
    yield from selected


def _reference_scan_text(relative: Path, text: str) -> str:
    if relative.suffix.lower() == ".json" and not text.strip():
        raise json.JSONDecodeError("empty JSON document", text, 0)
    return reference_scan_text(relative, text)


def check_removed_stub_references(
    repo_root: Path,
    *,
    receipt: dict[str, object] | None = None,
) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    seen: set[tuple[str, str, str]] = set()

    def add_reference(relative: str, token: str, target: str) -> None:
        message = f"stale direct reference `{token}`; use `{target}`."
        key = ("removed_stub_reference", relative, message)
        if key in seen:
            return
        seen.add(key)
        findings.append(LifecycleFinding(key[0], relative, message))

    all_tracked_paths, tracked_paths, excluded_paths = _reference_scan_selection(repo_root)
    tracked_names = [path.relative_to(repo_root).as_posix() for path in tracked_paths]
    all_names = [path.relative_to(repo_root).as_posix() for path in all_tracked_paths]
    opaque_paths: dict[str, list[str]] = {}
    ambiguous_paths: list[str] = []
    scanned_names: list[str] = []
    input_hash_rows: list[str] = []

    for reason, paths in excluded_paths.items():
        for path in paths:
            relative = _repo_path(repo_root, path)
            findings.append(
                LifecycleFinding(
                    "reference_scan_unresolved",
                    relative,
                    f"tracked input is outside the reference-scan selector ({reason}); "
                    "the lifecycle check cannot establish whether it contains a stale reference.",
                )
            )

    for removed_path, target in REMOVED_REDIRECT_STUBS.items():
        absolute = repo_root / removed_path
        members = [
            path for path in all_tracked_paths if path == absolute or absolute in path.parents
        ]
        if members:
            findings.append(
                LifecycleFinding(
                    "removed_stub_path",
                    removed_path,
                    f"removed redirect stub directory still exists; use `{target}`.",
                )
            )
            for path in members:
                add_reference(_repo_path(repo_root, path), removed_path, target)

    with measure_file_reads(repo_root) as measured_reads:
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
                    payload = measured_read_bytes(path)
                    content_sha256 = hashlib.sha256(payload).hexdigest()
                    opaque_format = _opaque_reference_format(payload)
                    if opaque_format is not None:
                        opaque_paths.setdefault(opaque_format, []).append(relative)
                        input_hash_rows.append(
                            f"{relative}\0opaque:{opaque_format}\0{content_sha256}"
                        )
                        findings.append(
                            LifecycleFinding(
                                "reference_scan_unresolved",
                                relative,
                                f"tracked input has a `{opaque_format}` signature; the reference "
                                "scanner does not decode container payloads, so stale references "
                                "inside this input remain unresolved.",
                            )
                        )
                        continue
                    text = payload.decode("utf-8")
                scan_text = _reference_scan_text(relative_path, text)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                ambiguous_paths.append(relative)
                input_hash_rows.append(f"{relative}\0ambiguous:{type(exc).__name__}")
                findings.append(
                    LifecycleFinding(
                        "reference_scan_ambiguous",
                        relative,
                        "committed reference input is unreadable or malformed "
                        f"({type(exc).__name__}).",
                    )
                )
                continue
            scanned_names.append(relative)
            input_hash_rows.append(f"{relative}\0text\0{content_sha256}")
            for token, target in STALE_DIRECT_REFERENCE_TARGETS.items():
                if token in scan_text:
                    add_reference(relative, token, target)

        read_snapshot = measured_reads.snapshot(complete_verdict=True)
        read_records = read_snapshot["inputs"]
        assert isinstance(read_records, list)
        read_records = read_records[len(reads_before_scan) :]

    coverage_complete = not excluded_paths and not opaque_paths and not ambiguous_paths
    if receipt is not None:
        receipt.update(
            {
                "schema": "docs-reference-scan-receipt/v1",
                "scope": "removed-stub-reference-scan-only",
                "receipt_coverage": "partial",
                "lifecycle_gate_input_coverage": "not-measured-by-this-receipt",
                "reference_scan_status": "complete" if coverage_complete else "partial",
                "selected_reference_scan_complete": coverage_complete,
                "enumerator": (
                    "iter_repository_files: Git tracked paths for repositories, recursive walk "
                    "for standalone fixtures"
                ),
                "denominator": {
                    "tracked_path_count": len(all_names),
                    "tracked_path_sha256": _path_set_sha256(all_names),
                    "selected_path_count": len(tracked_paths),
                    "selected_path_sha256": _path_set_sha256(tracked_names),
                    "excluded_path_count": sum(len(paths) for paths in excluded_paths.values()),
                    "excluded_path_sha256": _path_set_sha256(
                        path.relative_to(repo_root).as_posix()
                        for paths in excluded_paths.values()
                        for path in paths
                    ),
                },
                "selector_exclusions": {
                    reason: {
                        "path_count": len(paths),
                        "path_sha256": _path_set_sha256(
                            path.relative_to(repo_root).as_posix() for path in paths
                        ),
                        "read_status": "not-read-by-selector",
                    }
                    for reason, paths in excluded_paths.items()
                },
                "read_evidence": {
                    "operation_count": len(read_records),
                    "operation_sha256": hashlib.sha256(
                        json.dumps(read_records, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                    "input_outcomes_sha256": _path_set_sha256(input_hash_rows),
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
                        if excluded_paths
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


def check_archive_reports(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    legacy_archive_plans = repo_root / "docs" / "archive" / "plans"
    repository_files = tuple(_iter_repository_files(repo_root))
    if any(legacy_archive_plans in path.parents for path in repository_files):
        findings.append(
            LifecycleFinding(
                "archive_promotion",
                _repo_path(repo_root, legacy_archive_plans),
                "legacy archive plans must be promoted to docs/plans/archive.",
            )
        )

    for path in repository_files:
        if path.suffix != ".py" or repo_root / "docs" / "archive" not in path.parents:
            continue
        findings.append(
            LifecycleFinding(
                "archive_promotion",
                _repo_path(repo_root, path),
                "retained archive code belongs under tools/archive.",
            )
        )

    report_readme = repo_root / "docs" / "archive" / "reports" / "README.md"
    report_authoring = repo_root / "docs" / "archive" / "reports" / "AUTHORING.md"
    for path in (report_readme, report_authoring, report_readme.parent / "index.md"):
        if not path.is_file():
            findings.append(
                LifecycleFinding(
                    "archive_promotion",
                    _repo_path(repo_root, path),
                    "archive reports lifecycle document missing.",
                )
            )

    if report_readme.is_file():
        text = report_readme.read_text(encoding="utf-8")
        for token in ("Promotion criteria", "Raw logs", "Benchmark evidence"):
            if token not in text:
                findings.append(
                    LifecycleFinding(
                        "archive_promotion",
                        _repo_path(repo_root, report_readme),
                        f"archive reports README missing `{token}`.",
                    )
                )
    return findings


def check_readme_authoring(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    for subtree, filenames in HIGH_VOLUME_SUBTREE_DOCS.items():
        root = repo_root / subtree
        if not root.is_dir():
            findings.append(LifecycleFinding("authoring", subtree, "documented subtree missing."))
            continue
        for filename in filenames:
            path = root / filename
            if not path.is_file():
                findings.append(
                    LifecycleFinding("authoring", _repo_path(repo_root, path), "doc missing.")
                )
        authoring = root / "AUTHORING.md"
        if not authoring.is_file():
            continue
        text = authoring.read_text(encoding="utf-8")
        for section in AUTHORING_SECTIONS:
            if section not in text:
                findings.append(
                    LifecycleFinding(
                        "authoring",
                        _repo_path(repo_root, authoring),
                        f"missing section {section}",
                    )
                )

    public_surface = _load_toml(_public_surface_contract(repo_root))
    for package in public_surface.get("package", []):
        if not isinstance(package, dict) or package.get("classification") != "public_stable":
            continue
        readme = repo_root / str(package.get("readme", ""))
        if not readme.is_file():
            findings.append(
                LifecycleFinding(
                    "readme_coverage",
                    _repo_path(repo_root, readme),
                    "public-stable package README missing.",
                )
            )

    budget = _load_toml(repo_root / "architecture" / "module_size_budget.toml")
    for item in budget.get("budget", []):
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path", "")))
        if len(path.parts) < 3 or path.parts[:2] != ("src", "polisyos"):
            continue
        readme = repo_root / "src" / "polisyos" / path.parts[2] / "README.md"
        if not readme.is_file():
            findings.append(
                LifecycleFinding(
                    "readme_coverage",
                    _repo_path(repo_root, readme),
                    f"high-complexity package README missing for {path.as_posix()}.",
                )
            )

    return findings


def check_extension_example_structure(repo_root: Path) -> list[LifecycleFinding]:
    return [
        LifecycleFinding("extension_examples", "examples/extensions", message)
        for message in check_extension_examples.validate_pyproject(
            repo_root, check_extension_examples.EXAMPLES
        )
    ]


def run_checks(
    repo_root: Path,
    *,
    reference_scan_receipt: dict[str, object] | None = None,
) -> list[LifecycleFinding]:
    checks = (
        check_adr_index,
        check_docs_nav,
        check_policy_design_case_second_governance_pack,
        check_active_plans,
        check_redirect_stubs,
        check_removed_stub_references,
        check_archive_reports,
        check_readme_authoring,
        check_extension_example_structure,
    )
    findings: list[LifecycleFinding] = []
    for check in checks:
        try:
            if check is check_removed_stub_references:
                findings.extend(
                    check_removed_stub_references(
                        repo_root,
                        receipt=reference_scan_receipt,
                    )
                )
            else:
                findings.extend(check(repo_root))
        except (OSError, UnicodeError, RuntimeError, ValueError) as exc:
            if check is check_removed_stub_references and reference_scan_receipt is not None:
                reference_scan_receipt.update(
                    {
                        "schema": "docs-reference-scan-receipt/v1",
                        "scope": "removed-stub-reference-scan-only",
                        "receipt_coverage": "partial",
                        "lifecycle_gate_input_coverage": "not-measured-by-this-receipt",
                        "reference_scan_status": "partial",
                        "selected_reference_scan_complete": False,
                        "scan_error": type(exc).__name__,
                        "unresolved_by_construction": [
                            "This receipt measures only the removed-stub reference scan, not the "
                            "full docs lifecycle gate; other checks read inputs outside this "
                            "receipt.",
                            "Reference scan did not complete; tracked-path selection or input "
                            "evaluation raised before a denominator was established.",
                        ],
                    }
                )
            findings.append(
                LifecycleFinding(
                    "lifecycle_scan_ambiguous",
                    ".",
                    f"{check.__name__} input could not be evaluated ({type(exc).__name__}).",
                )
            )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    reference_scan_receipt: dict[str, object] = {}
    findings = run_checks(repo_root, reference_scan_receipt=reference_scan_receipt)
    print("Docs lifecycle reference-scan receipt:")
    print(json.dumps(reference_scan_receipt, indent=2, sort_keys=True))
    if reference_scan_receipt.get("reference_scan_status") != "complete":
        reference_checks = {
            "removed_stub_path",
            "removed_stub_reference",
            "reference_scan_unresolved",
            "reference_scan_ambiguous",
        }
        reference_findings = [finding for finding in findings if finding.check in reference_checks]
        other_findings = [finding for finding in findings if finding.check not in reference_checks]
        print(
            "Docs lifecycle gate UNRUN: reference-scan coverage is partial; "
            "the other lifecycle checks still ran."
        )
        if reference_findings:
            print("Reference-scan findings:")
            for finding in reference_findings:
                print(f"- [{finding.check}] {finding.path}: {finding.message}")
        if other_findings:
            print("Other lifecycle findings:")
            for finding in other_findings:
                print(f"- [{finding.check}] {finding.path}: {finding.message}")
        return 2
    if findings:
        print("Docs lifecycle gate FAILED:")
        for finding in findings:
            print(f"- [{finding.check}] {finding.path}: {finding.message}")
        return 1
    print("Docs lifecycle gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
