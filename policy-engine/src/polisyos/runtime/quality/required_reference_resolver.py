"""Canonical resolver for cross-slice runtime-quality references."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.core.contracts.reference_resolution import ResolvedRef

SHA256_PREFIX = "sha256:"
CAS_SHA256_PREFIXES = ("cas://sha256/", "cas://sha256:")
_HEX_64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def resolve_required_ref(
    repo_root: str | Path,
    ref: str,
    *,
    authority_bearing: bool = False,
    expected_content_hash: str | None = None,
    expected_schema_version: str | None = None,
    expected_rule_version: str | None = None,
    expected_authority_boundary: Mapping[str, Any] | None = None,
    allowed_producer_types: Sequence[str] = (),
    require_producer_root_refs: bool | None = None,
    supply_side_evidence: bool = False,
) -> ResolvedRef:
    """Dereference a runtime ref and return a fail-closed resolution record."""

    root = Path(repo_root)
    raw_ref = str(ref)
    issues: list[str] = []
    ref_digest_issue = _digest_issue(raw_ref)
    if ref_digest_issue:
        issues.append(ref_digest_issue)
    expected_digest_issue = _digest_issue(expected_content_hash)
    if expected_digest_issue:
        issues.append(expected_digest_issue)

    cas_digest = _cas_digest(raw_ref)
    if cas_digest is not None or raw_ref.startswith(SHA256_PREFIX):
        content_hash = cas_digest or raw_ref
        return ResolvedRef(
            ref=raw_ref,
            exists=not issues,
            content_hash=content_hash,
            issue_codes=_dedupe(issues),
        )

    path_ref = _normalize_path_ref(root, raw_ref)
    if path_ref.issue_codes:
        issues.extend(path_ref.issue_codes)
    if path_ref.relative_path is None:
        return ResolvedRef(
            ref=raw_ref,
            exists=False,
            artifact_path=None,
            json_pointer=path_ref.fragment,
            issue_codes=_dedupe(issues or ["required_ref_unsupported_scheme"]),
        )

    artifact_path = path_ref.relative_path.as_posix()
    absolute_path = root / path_ref.relative_path
    if not absolute_path.exists():
        issues.append("required_ref_missing_artifact")
        return ResolvedRef(
            ref=raw_ref,
            exists=False,
            artifact_path=artifact_path,
            json_pointer=path_ref.fragment,
            issue_codes=_dedupe(issues),
        )

    payload, read_issues = _read_payload(absolute_path)
    issues.extend(read_issues)
    if payload is None:
        return ResolvedRef(
            ref=raw_ref,
            exists=False,
            artifact_path=artifact_path,
            json_pointer=path_ref.fragment,
            issue_codes=_dedupe(issues),
        )

    target, pointer_issues = _resolve_fragment(payload, path_ref.fragment)
    issues.extend(pointer_issues)
    if pointer_issues:
        return ResolvedRef(
            ref=raw_ref,
            exists=False,
            artifact_path=artifact_path,
            json_pointer=path_ref.fragment,
            content_hash=_digest_payload(payload),
            schema_version=_metadata_text(payload, "schema_version"),
            rule_version=_metadata_text(payload, "rule_version"),
            issue_codes=_dedupe(issues),
        )

    target_mapping = target if isinstance(target, Mapping) else {}
    root_mapping = payload if isinstance(payload, Mapping) else {}
    content_hash = _digest_payload(target)
    if (
        expected_content_hash
        and not expected_digest_issue
        and _normalize_sha256(expected_content_hash) != content_hash
    ):
        issues.append("required_ref_stale_content_hash")

    schema_version = _first_text(
        target_mapping,
        root_mapping,
        keys=("schema_version",),
    )
    rule_version = _first_text(target_mapping, root_mapping, keys=("rule_version",))
    if expected_schema_version and schema_version != expected_schema_version:
        issues.append("required_ref_schema_mismatch")
    if expected_rule_version and rule_version != expected_rule_version:
        issues.append("required_ref_rule_mismatch")

    authority_boundary = _authority_boundary(target_mapping, root_mapping)
    if expected_authority_boundary and not _authority_boundary_matches(
        authority_boundary,
        expected_authority_boundary,
    ):
        issues.append("required_ref_authority_boundary_mismatch")

    producer_ref = _producer_ref(target_mapping, root_mapping)
    producer_type = _producer_type(target_mapping, root_mapping)
    producer_root_refs = _producer_root_refs(target_mapping, root_mapping)
    producer_root_required = (
        authority_bearing if require_producer_root_refs is None else require_producer_root_refs
    )
    if authority_bearing and not producer_ref:
        issues.append("required_ref_producer_ref_missing")
    if allowed_producer_types and producer_type not in set(allowed_producer_types):
        issues.append("required_ref_producer_type_invalid")
    if supply_side_evidence and producer_type in {
        "derivation",
        "derived_summary",
        "manifest_only",
        "manifest",
    }:
        issues.append("required_ref_producer_type_invalid")
    if producer_root_required and not producer_root_refs:
        issues.append("required_ref_producer_root_invalid")

    return ResolvedRef(
        ref=raw_ref,
        exists=not issues,
        artifact_path=artifact_path,
        json_pointer=path_ref.fragment,
        content_hash=content_hash,
        producer_ref=producer_ref,
        producer_type=producer_type,
        producer_root_refs=producer_root_refs,
        produced_at=_first_text(
            target_mapping,
            root_mapping,
            keys=("produced_at", "generated_at", "created_at", "observed_at"),
        ),
        schema_version=schema_version,
        rule_version=rule_version,
        authority_boundary=authority_boundary,
        issue_codes=_dedupe(issues),
    )


class _PathRef:
    def __init__(
        self,
        *,
        relative_path: Path | None,
        fragment: str | None,
        issue_codes: tuple[str, ...] = (),
    ) -> None:
        self.relative_path = relative_path
        self.fragment = fragment
        self.issue_codes = issue_codes


def _normalize_path_ref(repo_root: Path, ref: str) -> _PathRef:
    body = ref
    fragment: str | None = None
    if "#" in body:
        body, _, fragment = body.partition("#")
        fragment = fragment or None
    if body.startswith("repo://"):
        body = body.removeprefix("repo://")
    elif body.startswith("manifest://"):
        body = body.removeprefix("manifest://")
    elif body.startswith("generated-artifact://"):
        return _generated_artifact_ref(
            repo_root,
            body.removeprefix("generated-artifact://"),
            fragment,
        )
    elif "://" in body:
        return _PathRef(relative_path=None, fragment=fragment)
    return _PathRef(relative_path=Path(body), fragment=fragment)


def _generated_artifact_ref(
    repo_root: Path,
    body: str,
    fragment: str | None,
) -> _PathRef:
    by_family, outputs = _generated_artifact_outputs(repo_root)
    family_id, sep, output_ref = body.partition("/")
    if not sep:
        output_ref = family_id
        family_id = ""
    if output_ref in outputs:
        return _PathRef(relative_path=Path(output_ref), fragment=fragment)
    basename_matches = [output for output in outputs if output.endswith(f"/{output_ref}")]
    if len(basename_matches) == 1:
        return _PathRef(relative_path=Path(basename_matches[0]), fragment=fragment)
    family_outputs = by_family.get(family_id, ())
    if output_ref in family_outputs:
        return _PathRef(relative_path=Path(output_ref), fragment=fragment)
    return _PathRef(
        relative_path=None,
        fragment=fragment,
        issue_codes=("required_ref_missing_artifact",),
    )


def _generated_artifact_outputs(
    repo_root: Path,
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    path = repo_root / "architecture/generated_artifacts.toml"
    if not path.exists():
        return {}, ()
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}, ()
    outputs: set[str] = set()
    by_family: dict[str, tuple[str, ...]] = {}
    for family in payload.get("family", ()):
        if not isinstance(family, Mapping):
            continue
        family_id = str(family.get("id") or "")
        family_outputs = tuple(
            str(output)
            for output in family.get("outputs", ())
            if isinstance(output, str)
        )
        outputs.update(family_outputs)
        if family_id:
            by_family[family_id] = family_outputs
    return by_family, tuple(sorted(outputs))


def _read_payload(path: Path) -> tuple[object | None, tuple[str, ...]]:
    try:
        raw = path.read_text(encoding="utf-8")
        if path.suffix == ".toml":
            return tomllib.loads(raw), ()
        return json.loads(raw), ()
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError):
        return None, ("required_ref_artifact_unreadable",)


def _resolve_fragment(
    payload: object,
    fragment: str | None,
) -> tuple[object | None, tuple[str, ...]]:
    if not fragment:
        return payload, ()
    tokens = _fragment_tokens(fragment)
    if not tokens:
        return payload, ()
    target = _walk_pointer(payload, tokens)
    if target is not _MISSING:
        return target, ()
    alias_target = _resolve_artifact_alias(payload, tokens)
    if alias_target is not _MISSING:
        return alias_target, ()
    if tokens[0] == "bindings":
        binding = _resolve_binding_alias(payload, tokens[1:])
        if binding is not _MISSING:
            return binding, ()
    return None, ("required_ref_pointer_missing",)


_MISSING = object()


def _fragment_tokens(fragment: str) -> list[str]:
    pointer = fragment.removeprefix("#")
    pointer = pointer.removeprefix("/")
    if not pointer:
        return []
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer.split("/")]


def _walk_pointer(payload: object, tokens: Sequence[str]) -> object:
    current = payload
    for token in tokens:
        if isinstance(current, Mapping):
            if token not in current:
                return _MISSING
            current = current[token]
            continue
        if isinstance(current, Sequence) and not isinstance(current, str | bytes):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return _MISSING
            continue
        return _MISSING
    return current


def _resolve_artifact_alias(payload: object, tokens: Sequence[str]) -> object:
    if not tokens or not isinstance(payload, Mapping):
        return _MISSING
    joined = ".".join(tokens)
    dotted = _walk_pointer(payload, joined.split("."))
    if dotted is not _MISSING:
        return dotted
    selector = tokens[0]
    for container_key in ("metrics", "readings", "metric_statuses"):
        container = payload.get(container_key)
        if isinstance(container, Mapping) and selector in container:
            return container[selector]
    health_delta = payload.get("health_metric_delta")
    if isinstance(health_delta, Mapping):
        for container_key in ("metrics", "readings", "metric_statuses"):
            container = health_delta.get(container_key)
            if isinstance(container, Mapping) and selector in container:
                return container[selector]
    ledgers = payload.get("health_metric_ledgers")
    if isinstance(ledgers, Sequence) and not isinstance(ledgers, str | bytes):
        for ledger in ledgers:
            if isinstance(ledger, Mapping) and ledger.get("metric_id") == selector:
                return ledger
    return _MISSING


def _resolve_binding_alias(payload: object, tokens: Sequence[str]) -> object:
    selector = tokens[0] if tokens else ""
    if not isinstance(payload, Mapping):
        return _MISSING
    raw_bindings = payload.get("bindings")
    nested = payload.get("grounded_source_contracts")
    if raw_bindings is None and isinstance(nested, Mapping):
        raw_bindings = nested.get("bindings")
    if isinstance(raw_bindings, Mapping):
        return raw_bindings.get(selector, _MISSING)
    if isinstance(raw_bindings, Sequence) and not isinstance(raw_bindings, str | bytes):
        try:
            return raw_bindings[int(selector)]
        except (ValueError, IndexError):
            pass
        normalized_selector = _normalize_binding_selector(selector)
        for binding in raw_bindings:
            if not isinstance(binding, Mapping):
                continue
            candidates = {
                _normalize_binding_selector(_optional_text(binding.get("binding_id"))),
                _normalize_binding_selector(_optional_text(binding.get("construct_ref"))),
                _normalize_binding_selector(
                    _optional_text(binding.get("source_contract_ref"))
                ),
            }
            if normalized_selector in candidates:
                return binding
    return _MISSING


def _normalize_binding_selector(value: str | None) -> str:
    return (
        str(value or "")
        .removeprefix("construct:")
        .removeprefix("source-contract://")
        .strip()
    )


def _digest_payload(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{SHA256_PREFIX}{hashlib.sha256(raw).hexdigest()}"


def _digest_issue(value: str | None) -> str | None:
    if not value:
        return None
    digest = _extract_sha256_hex(value)
    if digest is None:
        if value.startswith(SHA256_PREFIX) or value.startswith(CAS_SHA256_PREFIXES):
            return "required_ref_malformed_digest"
        return None
    if len(digest) != 64 or not _HEX_64_RE.fullmatch(digest):
        return "required_ref_malformed_digest"
    if len(set(digest.lower())) == 1:
        return "required_ref_placeholder_digest"
    return None


def _extract_sha256_hex(value: str) -> str | None:
    if value.startswith(SHA256_PREFIX):
        return value.removeprefix(SHA256_PREFIX)
    for prefix in CAS_SHA256_PREFIXES:
        if value.startswith(prefix):
            return value.removeprefix(prefix)
    return None


def _cas_digest(value: str) -> str | None:
    for prefix in CAS_SHA256_PREFIXES:
        if value.startswith(prefix):
            return f"{SHA256_PREFIX}{value.removeprefix(prefix)}"
    return None


def _normalize_sha256(value: str) -> str:
    digest = _extract_sha256_hex(value)
    return f"{SHA256_PREFIX}{digest.lower()}" if digest else value


def _metadata_text(payload: object, key: str) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    return _optional_text(payload.get(key))


def _producer_ref(*mappings: Mapping[str, Any]) -> str | None:
    direct = _first_text(
        *mappings,
        keys=("producer_ref", "producer_id", "producer", "produced_by"),
    )
    if direct:
        return direct
    for mapping in mappings:
        producer = mapping.get("producer")
        if isinstance(producer, Mapping):
            nested = _optional_text(producer.get("ref") or producer.get("id"))
            if nested:
                return nested
    return None


def _producer_type(*mappings: Mapping[str, Any]) -> str | None:
    direct = _first_text(
        *mappings,
        keys=("producer_type", "producer_kind", "source_type"),
    )
    if direct:
        return direct
    for mapping in mappings:
        producer = mapping.get("producer")
        if isinstance(producer, Mapping):
            nested = _optional_text(producer.get("type") or producer.get("kind"))
            if nested:
                return nested
    return None


def _producer_root_refs(*mappings: Mapping[str, Any]) -> tuple[str, ...]:
    for mapping in mappings:
        refs = _as_str_tuple(
            mapping.get("producer_root_refs")
            or mapping.get("producer_roots")
            or mapping.get("root_refs")
        )
        if refs:
            return refs
        producer = mapping.get("producer")
        if isinstance(producer, Mapping):
            refs = _as_str_tuple(producer.get("root_refs") or producer.get("root_ref"))
            if refs:
                return refs
    return ()


def _authority_boundary(*mappings: Mapping[str, Any]) -> dict[str, Any]:
    for mapping in mappings:
        boundary = mapping.get("authority_boundary")
        if isinstance(boundary, Mapping):
            return dict(boundary)
    boundary: dict[str, Any] = {}
    for key in ("authoritative_for", "may_not_use_for"):
        values = _as_str_tuple(*(mapping.get(key) for mapping in mappings))
        if values:
            boundary[key] = values
    return boundary


def _authority_boundary_matches(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bool:
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if isinstance(expected_value, Sequence) and not isinstance(
            expected_value,
            str | bytes,
        ):
            actual_values = set(_as_str_tuple(actual_value))
            if not set(_as_str_tuple(expected_value)) <= actual_values:
                return False
        elif actual_value != expected_value:
            return False
    return True


def _first_text(*mappings: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for mapping in mappings:
        for key in keys:
            value = _optional_text(mapping.get(key))
            if value:
                return value
    return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_str_tuple(*values: object) -> tuple[str, ...]:
    refs: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value:
                refs.append(value)
            continue
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            refs.extend(str(item) for item in value if item)
            continue
        refs.append(str(value))
    return tuple(dict.fromkeys(refs))


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
