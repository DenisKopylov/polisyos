#!/usr/bin/env python3
"""Inventory and classify legacy production-quality evidence files.

The inventory is intentionally metadata-only. It may parse JSON-shaped reports to
read schema/provenance/ref fields, but it never copies report payloads into the
generated artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.legacy_quality_evidence_inventory.v1"
RULES_SCHEMA_VERSION = "policyos.legacy_evidence_classification_rules.v1"
TOOL_NAME = "quality.validation.inventory-legacy-quality-evidence"
GENERATED_AT = "2026-05-15T00:00:00Z"

CLASSIFICATIONS = (
    "legacy_supported",
    "legacy_quarantined",
    "legacy_rejected",
    "unknown_schema_blocked",
    "non_authority_debug_only",
)
FAIL_CLOSED_CLASSIFICATIONS = frozenset(
    {"legacy_quarantined", "legacy_rejected", "unknown_schema_blocked"}
)

DEFAULT_CLASSIFICATION_RULES_PATH = (
    REPO_ROOT / "architecture" / "production_quality" / "legacy_evidence_classification.toml"
)
DEFAULT_OUTPUT_DIR = Path("_build/honest-diagnostics/legacy")

_DEFAULT_RULES: dict[str, Any] = {
    "schema_version": RULES_SCHEMA_VERSION,
    "classification": {
        "allowed_classes": list(CLASSIFICATIONS),
        "fail_closed_classes": sorted(FAIL_CLOSED_CLASSIFICATIONS),
        "serious_closeout_supported_classes": ["legacy_supported"],
    },
    "discovery": {
        "root_paths": [
            "_build",
            ".polisyos",
            "docs/archive/reports",
            "docs/reference/runtime",
            "docs/reference/scientist",
            "docs/runbooks",
            "tests/_golden/quality",
        ],
        "include_extensions": [".json", ".jsonl", ".md"],
        "candidate_keywords": [
            "approval",
            "benchmark",
            "bundle",
            "canary",
            "coverage",
            "deterministic",
            "diagnostic",
            "evidence",
            "ledger",
            "manifest",
            "matrix",
            "quality",
            "readiness",
            "report",
            "scorecard",
            "summary",
            "validation",
        ],
        "exclude_path_prefixes": ["_build/honest-diagnostics/legacy"],
        "sensitive_path_markers": [
            ".env",
            "answer_key",
            "api_key",
            "auth_token",
            "credential",
            "hidden_answer",
            "password",
            "private_key",
            "secret",
            "token",
        ],
        "debug_path_markers": [
            "_build/frontend/",
            "_build/logs/",
            "_build/scratch/",
            "coverage/",
            "playwright-report/",
            "storybook-static/",
            "test-results/",
        ],
    },
    "schema_policy": {
        "known_schema_prefixes": ["policyos.", "runtime_quality."],
        "known_schema_names": [
            "runtime_quality.evidence_authority_envelope",
            "runtime_quality.diagnostic_event",
            "runtime_quality.normative_applicability_report",
            "runtime_quality.fabric_retrieval_trace",
            "runtime_quality.foundry_method_report",
            "runtime_quality.policy_grounding_matrix",
            "runtime_quality.conflict_check_report",
        ],
        "debug_schema_prefixes": ["debug.", "local_debug.", "storybook."],
        "unknown_schema_tokens": ["", "unknown", "legacy.unknown_quality_report"],
    },
    "provenance_policy": {
        "supported_provenance_kinds": [
            "runtime_emitted",
            "runtime_blocker",
            "deterministic_runtime_emitted",
        ],
        "quarantined_provenance_kinds": [
            "bundle_overlay",
            "fixture_input",
            "generated_substitute",
            "legacy_quarantined",
            "manual_input",
            "projection",
            "simulation",
        ],
        "required_supported_ref_schemes": ["cas://sha256/"],
    },
}

_REF_KEY_SUFFIXES = ("_ref", "_refs", "ref", "refs")
_STATUS_KEYS = ("status", "quality_status", "validation_status", "blocking_status")


class LegacyInventoryInputError(ValueError):
    """Raised when classification rules or input roots are malformed."""


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Classification TOML. Defaults to architecture/production_quality/legacy_evidence_classification.toml.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs drift")
    return parser.parse_args(argv)


def build_inventory(
    *,
    repo_root: Path = REPO_ROOT,
    rules_path: Path | None = None,
) -> dict[str, Any]:
    """Build a metadata-only legacy evidence inventory."""

    repo_root = repo_root.resolve()
    rules_file = _rules_path_for(repo_root, rules_path)
    rules = load_rules(rules_file)
    entries = [
        classify_file(path=path, repo_root=repo_root, rules=rules)
        for path in _discover_candidate_files(repo_root=repo_root, rules=rules)
    ]
    entries.sort(key=lambda row: str(row["path"]))
    counts = Counter(str(row["classification"]) for row in entries)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": GENERATED_AT,
        "repo_root": str(repo_root),
        "rules": {
            "path": _rel(rules_file, repo_root),
            "schema_version": rules.get("schema_version"),
        },
        "classification_model": {
            "allowed_classes": list(CLASSIFICATIONS),
            "fail_closed_classes": sorted(FAIL_CLOSED_CLASSIFICATIONS),
            "supported_for_serious_closeout": ["legacy_supported"],
        },
        "source_roots": _list_at(rules, "discovery", "root_paths"),
        "summary": {
            "entry_count": len(entries),
            "supported_for_serious_closeout_count": sum(
                1 for row in entries if row["supported_for_serious_closeout"]
            ),
            "fail_closed_count": sum(
                1 for row in entries if row["classification"] in FAIL_CLOSED_CLASSIFICATIONS
            ),
            "classification_counts": {
                classification: counts.get(classification, 0)
                for classification in CLASSIFICATIONS
            },
        },
        "content_safety": {
            "payloads_copied": False,
            "sensitive_path_policy": "skip_content_and_hash",
            "source_tracked_outputs": False,
        },
        "entries": entries,
    }


def classify_file(
    *,
    path: Path,
    repo_root: Path = REPO_ROOT,
    rules: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    rules = dict(rules or load_rules(_rules_path_for(repo_root, None)))
    rel_path = _rel(path, repo_root)
    rel_for_match = f"{rel_path}/" if path.is_dir() else rel_path
    suffix = path.suffix.lower()
    sensitive = _contains_any(rel_path.lower(), _list_at(rules, "discovery", "sensitive_path_markers"))
    debug_path = _contains_any(rel_for_match.lower(), _list_at(rules, "discovery", "debug_path_markers"))
    stat = path.stat()

    read_status = "parsed"
    digest: str | None = None
    payload: Any = None
    parse_error: str | None = None
    if sensitive:
        read_status = "skipped_sensitive_path"
    elif suffix == ".json":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            read_status = "parse_error"
            parse_error = exc.__class__.__name__
    elif suffix == ".jsonl":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        payload, parse_error = _parse_first_jsonl_row(raw)
        read_status = "parsed" if parse_error is None else "parse_error"
    else:
        read_status = "metadata_only"

    metadata = _extract_metadata(payload)
    reason_codes: list[str] = []
    if sensitive:
        reason_codes.append("sensitive_path_skipped")
    if debug_path:
        reason_codes.append("debug_only_path")
    if parse_error:
        reason_codes.append("parse_error")

    if _is_debug_schema(metadata, rules):
        reason_codes.append("debug_only_schema")
    if payload is not None and _has_bundle_local_runtime_ref(payload):
        reason_codes.append("bundle_local_runtime_ref")
    if payload is not None and _payload_sha256_mismatch(payload):
        reason_codes.append("payload_sha256_mismatch")
    if payload is not None and _has_redaction_loss(payload):
        reason_codes.append("redaction_loss")

    schema_known = _schema_is_known(metadata, rules)
    if not schema_known and "debug_only_schema" not in reason_codes and not sensitive:
        reason_codes.append("unknown_schema")

    provenance_kind = metadata.get("provenance_kind")
    if schema_known and not provenance_kind and not sensitive:
        reason_codes.append("missing_provenance")
    elif provenance_kind in set(_list_at(rules, "provenance_policy", "quarantined_provenance_kinds")):
        reason_codes.append("legacy_or_non_runtime_provenance")

    if (
        schema_known
        and provenance_kind in set(_list_at(rules, "provenance_policy", "supported_provenance_kinds"))
        and not _has_supported_authority_ref(metadata, rules)
        and not _has_any(
            reason_codes,
            (
                "bundle_local_runtime_ref",
                "payload_sha256_mismatch",
                "redaction_loss",
                "sensitive_path_skipped",
            ),
        )
    ):
        reason_codes.append("missing_authority_ref")

    classification = _classify_from_reasons(
        reason_codes=reason_codes,
        schema_known=schema_known,
        metadata=metadata,
        rules=rules,
    )
    return {
        "path": rel_path,
        "root_path": _matching_root(rel_path, _list_at(rules, "discovery", "root_paths")),
        "file_kind": _file_kind(rel_path, suffix),
        "classification": classification,
        "supported_for_serious_closeout": classification == "legacy_supported",
        "reason_codes": sorted(set(reason_codes)) or ["legacy_supported"],
        "read_status": read_status,
        "parse_error": parse_error,
        "size_bytes": stat.st_size,
        "sha256": digest,
        "schema": {
            "schema_version": metadata.get("schema_version"),
            "schema_name": metadata.get("schema_name"),
        },
        "provenance": {
            "provenance_kind": provenance_kind,
            "producer_component": metadata.get("producer_component"),
            "owner": metadata.get("owner"),
            "runtime_event_ref_present": bool(metadata.get("runtime_event_ref")),
        },
        "authority_ref": {
            "artifact_ref_scheme": _ref_scheme(metadata.get("artifact_ref")),
            "cas_ref_scheme": _ref_scheme(metadata.get("cas_ref")),
            "payload_sha256_present": bool(metadata.get("payload_sha256")),
        },
        "status_values": {
            key: value
            for key, value in metadata.items()
            if key in _STATUS_KEYS and isinstance(value, str)
        },
    }


def load_rules(path: Path) -> dict[str, Any]:
    if not path.exists():
        return dict(_DEFAULT_RULES)
    try:
        with path.open("rb") as stream:
            rules = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise LegacyInventoryInputError(f"Invalid legacy classification TOML: {path}: {exc}") from exc
    if rules.get("schema_version") != RULES_SCHEMA_VERSION:
        raise LegacyInventoryInputError(
            f"Unsupported legacy classification rules schema: {rules.get('schema_version')!r}"
        )
    allowed = set(_list_at(rules, "classification", "allowed_classes"))
    if allowed != set(CLASSIFICATIONS):
        raise LegacyInventoryInputError(
            "legacy classification rules must declare exactly: "
            + ", ".join(CLASSIFICATIONS)
        )
    return rules


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Legacy Evidence Inventory",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Rules: `{payload['rules']['path']}`",
        f"- Entries: {summary['entry_count']}",
        f"- Supported for serious closeout: {summary['supported_for_serious_closeout_count']}",
        f"- Fail-closed entries: {summary['fail_closed_count']}",
        "",
        "## Classification Counts",
        "",
        "| Classification | Count |",
        "| --- | ---: |",
    ]
    counts = summary["classification_counts"]
    for classification in CLASSIFICATIONS:
        lines.append(f"| `{classification}` | {counts[classification]} |")

    lines.extend(
        [
            "",
            "## Entries",
            "",
            "| Path | Classification | Reasons | Schema | Provenance | Read Status |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["entries"]:
        schema = row["schema"]
        provenance = row["provenance"]
        schema_label = schema.get("schema_version") or schema.get("schema_name") or ""
        reasons = ", ".join(f"`{reason}`" for reason in row["reason_codes"])
        lines.append(
            "| "
            f"`{row['path']}` | "
            f"`{row['classification']}` | "
            f"{reasons} | "
            f"`{schema_label}` | "
            f"`{provenance.get('provenance_kind') or ''}` | "
            f"`{row['read_status']}` |"
        )
    return "\n".join(lines) + "\n"


def check_artifacts(
    *,
    repo_root: Path = REPO_ROOT,
    rules_path: Path | None = None,
    json_output: Path | None = None,
    markdown_output: Path | None = None,
) -> list[str]:
    repo_root = repo_root.resolve()
    json_path, markdown_path = _output_paths(
        repo_root=repo_root,
        output_dir=DEFAULT_OUTPUT_DIR,
        json_output=json_output,
        markdown_output=markdown_output,
    )
    payload = build_inventory(repo_root=repo_root, rules_path=rules_path)
    expected = {
        json_path: dump_json(payload),
        markdown_path: render_markdown(payload),
    }
    failures: list[str] = []
    for path, expected_content in expected.items():
        if not path.exists():
            failures.append(f"generated inventory missing: {_rel(path, repo_root)}")
            continue
        if path.read_text(encoding="utf-8") != expected_content:
            failures.append(f"generated inventory out of date: {_rel(path, repo_root)}")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    json_output, markdown_output = _output_paths(
        repo_root=repo_root,
        output_dir=args.output_dir,
        json_output=args.json_output,
        markdown_output=args.markdown_output,
    )

    if args.check:
        failures = check_artifacts(
            repo_root=repo_root,
            rules_path=args.rules,
            json_output=json_output,
            markdown_output=markdown_output,
        )
        if failures:
            for failure in failures:
                print(failure)
            return 1
        return 0

    payload = build_inventory(repo_root=repo_root, rules_path=args.rules)
    atomic_write_text(json_output, dump_json(payload))
    atomic_write_text(markdown_output, render_markdown(payload))
    return 0


def _rules_path_for(repo_root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return _resolve(repo_root, explicit)
    repo_rules = repo_root / "architecture" / "production_quality" / "legacy_evidence_classification.toml"
    if repo_rules.exists():
        return repo_rules
    return DEFAULT_CLASSIFICATION_RULES_PATH


def _output_paths(
    *,
    repo_root: Path,
    output_dir: Path,
    json_output: Path | None,
    markdown_output: Path | None,
) -> tuple[Path, Path]:
    resolved_dir = _resolve(repo_root, output_dir)
    return (
        _resolve(repo_root, json_output) if json_output else resolved_dir / "legacy_inventory.json",
        _resolve(repo_root, markdown_output) if markdown_output else resolved_dir / "legacy_inventory.md",
    )


def _discover_candidate_files(
    *,
    repo_root: Path,
    rules: Mapping[str, Any],
) -> list[Path]:
    include_extensions = {ext.lower() for ext in _list_at(rules, "discovery", "include_extensions")}
    roots = _list_at(rules, "discovery", "root_paths")
    paths: list[Path] = []
    for root in roots:
        root_path = _resolve(repo_root, Path(root))
        if not root_path.exists():
            continue
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            rel = _rel(path, repo_root)
            if _is_excluded_path(rel, rules):
                continue
            if _has_hidden_part(rel):
                continue
            if path.suffix.lower() not in include_extensions:
                continue
            if _is_candidate_report_file(rel, rules) or _is_sensitive_path(rel, rules):
                paths.append(path)
    return sorted(set(paths), key=lambda item: _rel(item, repo_root))


def _is_candidate_report_file(rel_path: str, rules: Mapping[str, Any]) -> bool:
    lowered = rel_path.lower()
    return _contains_any(lowered, _list_at(rules, "discovery", "candidate_keywords"))


def _is_sensitive_path(rel_path: str, rules: Mapping[str, Any]) -> bool:
    return _contains_any(rel_path.lower(), _list_at(rules, "discovery", "sensitive_path_markers"))


def _is_excluded_path(rel_path: str, rules: Mapping[str, Any]) -> bool:
    lowered = rel_path.lower()
    prefixes = [prefix.lower().rstrip("/") for prefix in _list_at(rules, "discovery", "exclude_path_prefixes")]
    return any(lowered == prefix or lowered.startswith(f"{prefix}/") for prefix in prefixes)


def _has_hidden_part(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return any(part.startswith(".") and part != ".polisyos" for part in parts)


def _extract_metadata(payload: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if not isinstance(payload, Mapping):
        return metadata
    for key in (
        "schema_version",
        "schema_name",
        "provenance_kind",
        "producer_component",
        "owner",
        "artifact_ref",
        "cas_ref",
        "payload_sha256",
        "runtime_event_ref",
        *_STATUS_KEYS,
    ):
        value = payload.get(key)
        if isinstance(value, str):
            metadata[key] = value

    if "schema" in payload and isinstance(payload["schema"], Mapping):
        schema = payload["schema"]
        if isinstance(schema.get("name"), str):
            metadata.setdefault("schema_name", schema["name"])
        if isinstance(schema.get("version"), str):
            metadata.setdefault("schema_version", schema["version"])
    if "producer" in payload and isinstance(payload["producer"], Mapping):
        producer = payload["producer"]
        if isinstance(producer.get("component"), str):
            metadata.setdefault("producer_component", producer["component"])
    return metadata


def _classify_from_reasons(
    *,
    reason_codes: Sequence[str],
    schema_known: bool,
    metadata: Mapping[str, Any],
    rules: Mapping[str, Any],
) -> str:
    reasons = set(reason_codes)
    if reasons & {"debug_only_path", "debug_only_schema", "sensitive_path_skipped", "parse_error"}:
        return "non_authority_debug_only"
    if reasons & {"bundle_local_runtime_ref", "payload_sha256_mismatch"}:
        return "legacy_rejected"
    if "unknown_schema" in reasons or not schema_known:
        return "unknown_schema_blocked"
    if reasons & {
        "missing_provenance",
        "legacy_or_non_runtime_provenance",
        "missing_authority_ref",
        "redaction_loss",
    }:
        return "legacy_quarantined"
    provenance = metadata.get("provenance_kind")
    if provenance in set(_list_at(rules, "provenance_policy", "supported_provenance_kinds")):
        return "legacy_supported"
    return "legacy_quarantined"


def _schema_is_known(metadata: Mapping[str, Any], rules: Mapping[str, Any]) -> bool:
    schema_values = [
        str(value).strip()
        for value in (metadata.get("schema_version"), metadata.get("schema_name"))
        if isinstance(value, str)
    ]
    if not schema_values:
        return False
    unknown_tokens = {token.lower() for token in _list_at(rules, "schema_policy", "unknown_schema_tokens")}
    if all(value.lower() in unknown_tokens for value in schema_values):
        return False
    known_prefixes = tuple(_list_at(rules, "schema_policy", "known_schema_prefixes"))
    known_names = set(_list_at(rules, "schema_policy", "known_schema_names"))
    return any(value.startswith(known_prefixes) or value in known_names for value in schema_values)


def _is_debug_schema(metadata: Mapping[str, Any], rules: Mapping[str, Any]) -> bool:
    values = [
        str(value).strip()
        for value in (metadata.get("schema_version"), metadata.get("schema_name"))
        if isinstance(value, str)
    ]
    prefixes = tuple(_list_at(rules, "schema_policy", "debug_schema_prefixes"))
    return any(value.startswith(prefixes) for value in values)


def _has_supported_authority_ref(metadata: Mapping[str, Any], rules: Mapping[str, Any]) -> bool:
    schemes = tuple(_list_at(rules, "provenance_policy", "required_supported_ref_schemes"))
    return any(
        isinstance(metadata.get(key), str) and str(metadata[key]).startswith(schemes)
        for key in ("artifact_ref", "cas_ref")
    )


def _has_bundle_local_runtime_ref(payload: Any) -> bool:
    for key_path, value in _walk_payload(payload):
        if not isinstance(value, str):
            continue
        key = key_path[-1] if key_path else ""
        if not _is_ref_key(key):
            continue
        if _is_bundle_local_ref(value):
            return True
    return False


def _is_ref_key(key: str) -> bool:
    lowered = key.lower()
    return lowered.endswith(_REF_KEY_SUFFIXES) or lowered in {"artifact_ref", "cas_ref"}


def _is_bundle_local_ref(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith(("bundle://", "file://")):
        return True
    if "://" in stripped or stripped.startswith("urn:"):
        return False
    return (
        stripped.startswith(("./", "../", "_build/", ".polisyos/", "quality_evidence/"))
        or stripped.endswith((".json", ".jsonl", ".md"))
        or "/" in stripped
    )


def _payload_sha256_mismatch(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    declared = payload.get("payload_sha256")
    embedded_payload = payload.get("payload")
    if not isinstance(declared, str) or embedded_payload is None:
        return False
    actual = hashlib.sha256(
        json.dumps(
            embedded_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return actual != declared.lower()


def _has_redaction_loss(payload: Any) -> bool:
    for key_path, value in _walk_payload(payload):
        key = key_path[-1].lower() if key_path else ""
        if key in {"redaction_loss", "lossy_redaction"} and value is True:
            return True
        if key in {"lost_fields", "dropped_fields", "removed_evidence_refs"} and isinstance(value, list) and value:
            return True
        if key in {"lossy", "lossy_redaction"} and value is True and any(
            "redact" in part.lower() for part in key_path
        ):
            return True
        if key in {"redaction_status", "redaction_integrity"} and str(value).lower() in {
            "lossy",
            "lost",
            "failed",
        }:
            return True
    return False


def _walk_payload(payload: Any, key_path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            rendered_key = str(key)
            yield key_path + (rendered_key,), value
            yield from _walk_payload(value, key_path + (rendered_key,))
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_payload(item, key_path)


def _parse_first_jsonl_row(raw: bytes) -> tuple[Any, str | None]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, exc.__class__.__name__
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped), None
        except json.JSONDecodeError as exc:
            return None, exc.__class__.__name__
    return None, "empty_jsonl"


def _file_kind(rel_path: str, suffix: str) -> str:
    lowered = rel_path.lower()
    if "bundle" in lowered:
        return "bundle"
    if "scorecard" in lowered:
        return "scorecard"
    if "ledger" in lowered:
        return "ledger"
    if "matrix" in lowered:
        return "matrix"
    if "manifest" in lowered:
        return "manifest"
    if "report" in lowered or "evidence" in lowered:
        return "report"
    if suffix == ".md":
        return "markdown_projection"
    return "artifact"


def _matching_root(rel_path: str, roots: Sequence[str]) -> str:
    lowered = rel_path.lower()
    for root in sorted(roots, key=len, reverse=True):
        normalized = root.strip("/").lower()
        if lowered == normalized or lowered.startswith(f"{normalized}/"):
            return root
    return ""


def _ref_scheme(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("cas://sha256/"):
        return "cas://sha256/"
    if "://" in value:
        return value.split("://", 1)[0] + "://"
    if value.startswith("urn:"):
        return "urn:"
    return "local_or_relative"


def _resolve(repo_root: Path, path: Path | str | None) -> Path:
    if path is None:
        return repo_root
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _contains_any(value: str, markers: Sequence[str]) -> bool:
    return any(marker and marker.lower() in value for marker in markers)


def _has_any(values: Sequence[str], candidates: Sequence[str]) -> bool:
    value_set = set(values)
    return any(candidate in value_set for candidate in candidates)


def _list_at(payload: Mapping[str, Any], section: str, key: str) -> list[str]:
    section_payload = payload.get(section)
    if not isinstance(section_payload, Mapping):
        return []
    value = section_payload.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
