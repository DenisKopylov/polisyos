"""Derive every structured receipt that binds regenerated clients.

The primary census discovers explicitly named anchor records. An independent
shape census discovers any target-associated semantic receipt without depending
on its container name. Navigation references remain a separate population.
Identity-mode anchors replay the shared TypeScript v1 resolver while their
numeric coordinates remain navigation-only. Missing-export anchors recompute
complete module-export and generated-schema-owner sets without inventing an
identity for an absent construct. A mismatch fails closed so a new receipt
shape cannot silently shrink the denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from collections import namedtuple
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path

DEFAULT_TARGET_PATHS = (
    "schemas/runtime_api_v1.openapi.json",
    "packages/runtime-api-client/types.ts",
    "packages/runtime-api-client/runtimeApiClient.ts",
    "packages/runtime-api-client/runtimeApiClient.js",
    "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
    "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    "apps/runtime-dashboard/src/api/types.ts",
)
STRUCTURED_SUFFIXES = frozenset({".json", ".toml"})
SYMBOL_KEYS = frozenset({"export_symbol", "symbol"})
PATH_SUFFIXES = (".js", ".json", ".py", ".toml", ".ts", ".tsx")
GENERATED_CLIENT_ABSENCE_SCOPE = (
    "canonical_module_exports_and_schema_owners"
)


def _walk(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], object]]:
    """Yield every node in a JSON/TOML value with its stable structural path."""
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _key_tokens(key: object) -> tuple[str, ...]:
    """Split snake, kebab, and camel-case keys into normalized tokens."""
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return tuple(token for token in re.split(r"[^a-z0-9]+", expanded.lower()) if token)


def _line_items(value: Mapping[object, object]) -> list[tuple[str, int]]:
    """Return direct integer fields whose key has a distinct ``line`` token."""
    return sorted(
        (
            (str(key), child)
            for key, child in value.items()
            if "line" in _key_tokens(key)
            and isinstance(child, int)
            and not isinstance(child, bool)
        ),
        key=lambda item: item[0],
    )


def _identity_items(value: Mapping[object, object]) -> list[tuple[str, object]]:
    """Return direct fields explicitly declaring a construct identity."""
    return sorted(
        (
            (str(key), child)
            for key, child in value.items()
            if "identity" in _key_tokens(key)
        ),
        key=lambda item: item[0],
    )


def _binding_stem(key: str, terminal: str) -> tuple[str, ...] | None:
    """Return the normalized key stem before a terminal binding token."""
    tokens = _key_tokens(key)
    if not tokens or tokens[-1] != terminal:
        return None
    return tokens[:-1]


def _anchor_binding_mode(
    lines: Sequence[tuple[str, int]],
    identities: Sequence[tuple[str, object]],
    *,
    anchor_kind: object,
    absence_scope: object,
) -> str:
    """Classify one complete anchor as legacy, identity, absence, or mixed."""
    if anchor_kind == "missing_export":
        if (
            absence_scope == GENERATED_CLIENT_ABSENCE_SCOPE
            and not lines
            and not identities
        ):
            return "recomputed_absence"
        if absence_scope is None and lines and not identities:
            return "legacy_line"
        return "mixed"
    if not identities:
        return "legacy_line"
    line_stems = {
        stem
        for key, _value in lines
        if (stem := _binding_stem(key, "line")) is not None
    }
    identity_stems = {
        stem
        for key, _value in identities
        if (stem := _binding_stem(key, "identity")) is not None
    }
    if (
        len(lines) == len(identities)
        and line_stems == identity_stems
        and all(isinstance(value, str) for _key, value in identities)
    ):
        return "identity"
    return "mixed"


@lru_cache(maxsize=1)
def _typescript_identity_engine() -> object:
    """Load the one DS5 v1 identity engine only when identities are present."""
    try:
        from architecture.atlas_surfaces import check_frontend_disposition_register
    except ModuleNotFoundError as error:
        if error.name != "architecture":  # pragma: no cover - preserve nested failure
            raise
        import check_frontend_disposition_register

    return check_frontend_disposition_register


def _document_target_slots(
    value: object, target_paths: frozenset[str]
) -> dict[str, str]:
    """Derive canonical/schema target roles from declared source-path fields."""
    field_roles = {
        ("canonical", "path"): "canonical",
        ("types", "path"): "schema",
    }
    candidates: dict[str, set[str]] = {}
    for _path, node in _walk(value):
        if not isinstance(node, Mapping):
            continue
        for key, child in node.items():
            role = field_roles.get(_key_tokens(key))
            if role is not None and isinstance(child, str) and child in target_paths:
                candidates.setdefault(role, set()).add(child)
    return {
        role: next(iter(paths))
        for role, paths in candidates.items()
        if len(paths) == 1
    }


def _exact_targets(value: object, target_paths: frozenset[str]) -> frozenset[str]:
    """Return target paths represented as exact string values in ``value``."""
    return frozenset(
        child
        for _, child in _walk(value)
        if isinstance(child, str) and child in target_paths
    )


def _parse_structured(path: Path) -> object:
    """Parse one JSON or TOML candidate without changing its bytes."""
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix == ".toml":
        with path.open("rb") as stream:
            return tomllib.load(stream)
    raise ValueError(f"unsupported structured artifact: {path}")


def _json_pointer(path: tuple[str, ...]) -> str:
    """Encode a structural path as a JSON pointer for stable diagnostics."""
    if not path:
        return ""
    return "/" + "/".join(
        part.replace("~", "~0").replace("/", "~1") for part in path
    )


def _direct_navigation_references(
    value: object,
    *,
    artifact_path: str,
    target_paths: Sequence[str],
) -> list[dict[str, object]]:
    """Enumerate ``target:line`` strings as navigation, never as bindings."""
    patterns = tuple(
        (
            target,
            re.compile(rf"^{re.escape(target)}:(?P<line>[0-9]+)(?:$|[#?])"),
        )
        for target in target_paths
    )
    references: list[dict[str, object]] = []
    for path, child in _walk(value):
        if not isinstance(child, str):
            continue
        for target, pattern in patterns:
            match = pattern.match(child)
            if match is None:
                continue
            references.append(
                {
                    "artifact_path": artifact_path,
                    "line": int(match.group("line")),
                    "pointer": _json_pointer(path),
                    "target_path": target,
                }
            )
            break
    return references


def _associated_targets(
    candidate: Mapping[object, object],
    *,
    document_targets: frozenset[str],
    target_paths: frozenset[str],
) -> frozenset[str]:
    """Associate one coordinate record with regenerated target paths."""
    direct_targets = frozenset(
        child
        for child in candidate.values()
        if isinstance(child, str) and child in target_paths
    )
    if direct_targets:
        return direct_targets
    direct_foreign_paths = tuple(
        child
        for key, child in candidate.items()
        if isinstance(child, str)
        and ("path" in str(key).lower() or child.endswith(PATH_SUFFIXES))
    )
    if direct_foreign_paths:
        return frozenset()
    return document_targets


def _value_at_path(value: object, path: tuple[str, ...]) -> object:
    """Resolve one structural path within a parsed JSON/TOML value."""
    current = value
    for part in path:
        if isinstance(current, Mapping):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:  # pragma: no cover - paths are produced by _walk
            raise KeyError(path)
    return current


def _record_id(value: object, path: tuple[str, ...]) -> str | None:
    """Find the nearest owning record identifier for an enumerated binding."""
    for length in range(len(path) - 1, -1, -1):
        parent = _value_at_path(value, path[:length])
        if not isinstance(parent, Mapping):
            continue
        for preferred in ("unit_id", "debt_id", "record_id", "id"):
            candidate = parent.get(preferred)
            if isinstance(candidate, str):
                return candidate
        for key, candidate in parent.items():
            if str(key).endswith("_id") and isinstance(candidate, str):
                return candidate
    return None


def _anchor_records(
    value: object,
    *,
    artifact_path: str,
    target_paths: frozenset[str],
    target_slots: Mapping[str, str],
    explicit: bool,
) -> dict[tuple[str, ...], dict[str, object]]:
    """Discover anchor records by explicit or independent structural rules."""
    document_targets = _exact_targets(value, target_paths)
    records: dict[tuple[str, ...], dict[str, object]] = {}
    for path, candidate in _walk(value):
        if not isinstance(candidate, Mapping) or not path:
            continue
        if explicit and (
            "anchor" not in path[-1].lower()
            or not any(
                key in candidate and isinstance(candidate[key], str)
                for key in SYMBOL_KEYS
            )
        ):
            continue
        lines = _line_items(candidate)
        identities = _identity_items(candidate)
        anchor_kind = candidate.get("anchor_kind")
        absence_scope = candidate.get("absence_scope")
        has_ts_identity = bool(identities) and all(
            isinstance(value, str) and "#ts-identity=" in value
            for _key, value in identities
        )
        if (
            not lines
            and anchor_kind != "missing_export"
            and not has_ts_identity
        ):
            continue
        candidate_targets = _associated_targets(
            candidate,
            document_targets=document_targets,
            target_paths=target_paths,
        )
        if not candidate_targets:
            continue
        symbol = next(
            (
                candidate.get(key)
                for key in ("export_symbol", "symbol", "type_name")
                if isinstance(candidate.get(key), str)
            ),
            None,
        )
        binding_mode = _anchor_binding_mode(
            lines,
            identities,
            anchor_kind=anchor_kind,
            absence_scope=absence_scope,
        )
        absence_bindings = (
            [
                {
                    "slot": "canonical",
                    "predicate": "module_export_absent",
                    "symbol": symbol,
                },
                {
                    "slot": "schema",
                    "predicate": "generated_schema_owner_absent",
                    "symbol": symbol,
                },
            ]
            if binding_mode == "recomputed_absence"
            else []
        )
        records[path] = {
            "absence_bindings": absence_bindings,
            "absence_scope": absence_scope,
            "artifact_path": artifact_path,
            "field": candidate.get("field")
            if isinstance(candidate.get("field"), str)
            else None,
            "line_bindings": [
                {"key": key, "value": line} for key, line in lines
            ],
            "identity_bindings": [
                {"key": key, "value": value} for key, value in identities
            ],
            "binding_mode": binding_mode,
            "pointer": _json_pointer(path),
            "record_id": _record_id(value, path),
            "record_name": path[-1],
            "symbol": symbol,
            "target_paths": sorted(candidate_targets),
            "target_slots": dict(target_slots),
        }
    return records


def _validate_absence_bindings(
    bindings: Sequence[dict[str, object]],
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    """Recompute absence against complete canonical and schema-owner sets."""
    engine: object | None = None
    for binding in bindings:
        if binding["binding_mode"] != "recomputed_absence":
            continue
        prefix = f"{binding['artifact_path']}:{binding['pointer']}"
        target_slots = binding["target_slots"]
        if set(target_slots) != {"canonical", "schema"}:
            errors.append(f"anchor_absence_slot_set_drift:{prefix}")
            continue
        sources: dict[str, str] = {}
        for slot in ("canonical", "schema"):
            source_path = str(target_slots[slot])
            absolute_path = repo_root / source_path
            if not absolute_path.is_file():
                errors.append(
                    f"anchor_absence_source_missing:{prefix}:{slot}"
                )
                continue
            sources[source_path] = absolute_path.read_text(encoding="utf-8")
        if len(sources) != 2:
            continue
        if engine is None:
            engine = _typescript_identity_engine()
        facts = engine._typescript_generated_client_absence_facts(  # type: ignore[attr-defined]
            sources,
            canonical_path=str(target_slots["canonical"]),
            types_path=str(target_slots["schema"]),
        )
        errors.extend(
            f"anchor_absence_source_invalid:{prefix}:{error}"
            for error in facts["errors"]
        )
        for slot, count in (
            ("canonical", facts["canonicalScopeCount"]),
            ("schema", facts["schemaScopeCount"]),
        ):
            if count == 0:
                errors.append(f"anchor_absence_scope_missing:{prefix}:{slot}")
            elif count != 1:
                errors.append(
                    f"anchor_absence_scope_ambiguous:{prefix}:{slot}:count={count}"
                )
        symbol = str(binding["symbol"])
        for slot, names in (
            ("canonical", facts["canonicalExports"]),
            ("schema", facts["schemaOwners"]),
        ):
            if symbol in names:
                errors.append(
                    f"anchor_absence_unexpected_presence:{prefix}:{slot}:{symbol}"
                )


def _validate_identity_bindings(
    bindings: Sequence[dict[str, object]],
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    """Replay every discovered identity through the shared DS5 v1 engine."""
    identity_references: list[str] = []
    engine: object | None = None
    alias_rows: list[tuple[dict[str, object], dict[str, object]]] = []
    for binding in bindings:
        identity_bindings = binding["identity_bindings"]
        if not identity_bindings:
            continue
        if engine is None:
            engine = _typescript_identity_engine()
        slots: dict[str, dict[str, object]] = {}
        for identity_binding in identity_bindings:
            stem = _binding_stem(str(identity_binding["key"]), "identity")
            slot = "_".join(stem or ())
            if not slot or slot in slots:
                errors.append(
                    "anchor_identity_slot_set_drift:"
                    f"{binding['artifact_path']}:{binding['pointer']}"
                )
                continue
            slots[slot] = identity_binding
            encoded_identity = identity_binding["value"]
            if not isinstance(encoded_identity, str):
                errors.append(
                    "typescript_identity_validation:"
                    f"{binding['artifact_path']}:{binding['pointer']}:"
                    f"{identity_binding['key']}:typescript_reference_identity_invalid"
                )
                continue
            try:
                record = engine._typescript_reference_identity_record(  # type: ignore[attr-defined]
                    encoded_identity
                )
            except (KeyError, TypeError, ValueError):
                errors.append(
                    "typescript_identity_validation:"
                    f"{binding['artifact_path']}:{binding['pointer']}:"
                    f"{identity_binding['key']}:typescript_reference_identity_invalid"
                )
                continue
            identity_binding.update(
                {
                    "source_path": record["source_path"],
                    "role": record["role"],
                    "discriminator": record["discriminator"],
                }
            )
            identity_references.append(encoded_identity)
        if set(slots) != {"canonical", "schema"}:
            errors.append(
                "anchor_identity_slot_set_drift:"
                f"{binding['artifact_path']}:{binding['pointer']}"
            )
            continue
        target_slots = binding["target_slots"]
        for slot, identity_binding in slots.items():
            expected_source = target_slots.get(slot)
            if identity_binding.get("source_path") != expected_source:
                errors.append(
                    "anchor_identity_slot_drift:"
                    f"{binding['artifact_path']}:{binding['pointer']}:{slot}:source_path"
                )
        symbol = binding.get("symbol")
        canonical = slots["canonical"]
        if (
            canonical.get("role") != "exported_declaration"
            or canonical.get("discriminator") != symbol
        ):
            errors.append(
                "anchor_identity_slot_drift:"
                f"{binding['artifact_path']}:{binding['pointer']}:canonical:construct"
            )
        if isinstance(symbol, str) and isinstance(target_slots.get("canonical"), str):
            alias_rows.append((binding, slots["schema"]))
    if engine is not None and alias_rows:
        alias_sources = {
            str(binding["target_slots"]["canonical"]): (
                repo_root / str(binding["target_slots"]["canonical"])
            ).read_text(encoding="utf-8")
            for binding, _schema in alias_rows
            if (repo_root / str(binding["target_slots"]["canonical"])).is_file()
        }
        alias_requests = [
            {
                "sourcePath": binding["target_slots"]["canonical"],
                "role": "exported_declaration",
                "discriminator": binding["symbol"],
            }
            for binding, _schema in alias_rows
        ]
        alias_facts = engine._typescript_reference_construct_facts_batch(  # type: ignore[attr-defined]
            alias_sources, alias_requests, closed_universe=True
        )
        for (binding, schema), facts in zip(
            alias_rows, alias_facts, strict=True
        ):
            matches = facts["matches"]
            if len(matches) > 1:
                errors.append(
                    "anchor_identity_alias_relation_ambiguous:"
                    f"{binding['artifact_path']}:{binding['pointer']}"
                )
                continue
            owners = [
                match["generatedSchemaOwner"]
                for match in matches
                if isinstance(match.get("generatedSchemaOwner"), str)
            ]
            if len(owners) != 1:
                errors.append(
                    "anchor_identity_alias_relation_drift:"
                    f"{binding['artifact_path']}:{binding['pointer']}"
                )
                continue
            owner = owners[0]
            field = binding.get("field")
            expected_role = "generated_schema_property" if field else "type_property"
            expected_discriminator = (
                f"components.schemas.{owner}.{field}"
                if field
                else f"components.{owner}"
            )
            if (
                schema.get("role") != expected_role
                or schema.get("discriminator") != expected_discriminator
            ):
                errors.append(
                    "anchor_identity_slot_drift:"
                    f"{binding['artifact_path']}:{binding['pointer']}:schema:construct"
                )
    if engine is not None:
        errors.extend(
            "typescript_identity_validation:" + error
            for error in engine._typescript_identity_reference_errors(  # type: ignore[attr-defined]
                identity_references,
                source_root=repo_root,
            )
        )


_DocumentAnchorCensus = namedtuple(
    "_DocumentAnchorCensus",
    (
        "primary",
        "independent",
        "navigation",
        "primary_lines",
        "independent_lines",
        "identity_bindings",
        "absence_predicates",
        "legacy_line_bindings",
        "navigation_line_hints",
        "errors",
    ),
)


def _document_anchor_census(
    value: object,
    *,
    artifact_path: str,
    target_paths: Sequence[str],
) -> _DocumentAnchorCensus:
    """Enumerate and independently reconcile one structured document."""
    normalized_targets = tuple(dict.fromkeys(str(path) for path in target_paths))
    target_set = frozenset(normalized_targets)
    target_slots = _document_target_slots(value, target_set)
    primary = _anchor_records(
        value,
        artifact_path=artifact_path,
        target_paths=target_set,
        target_slots=target_slots,
        explicit=True,
    )
    independent = _anchor_records(
        value,
        artifact_path=artifact_path,
        target_paths=target_set,
        target_slots=target_slots,
        explicit=False,
    )
    navigation = _direct_navigation_references(
        value,
        artifact_path=artifact_path,
        target_paths=normalized_targets,
    )
    errors: list[str] = []
    for pointer in sorted(set(primary) ^ set(independent)):
        primary_state = "present" if pointer in primary else "absent"
        independent_state = "present" if pointer in independent else "absent"
        errors.append(
            "anchor_population_mismatch:"
            f"{artifact_path}:{_json_pointer(pointer)}:"
            f"primary={primary_state}:independent={independent_state}"
        )
    primary_lines = sum(
        len(record["line_bindings"]) for record in primary.values()
    )
    independent_lines = sum(
        len(record["line_bindings"]) for record in independent.values()
    )
    if primary_lines != independent_lines:
        errors.append(
            "anchor_line_population_mismatch:"
            f"{artifact_path}:primary={primary_lines}:independent={independent_lines}"
        )
    primary_identities = sum(
        len(record["identity_bindings"]) for record in primary.values()
    )
    independent_identities = sum(
        len(record["identity_bindings"]) for record in independent.values()
    )
    if primary_identities != independent_identities:
        errors.append(
            "anchor_identity_population_mismatch:"
            f"{artifact_path}:primary={primary_identities}:"
            f"independent={independent_identities}"
        )
    binding_modes = {
        str(record["binding_mode"]) for record in independent.values()
    }
    if "mixed" in binding_modes or (
        "legacy_line" in binding_modes and len(binding_modes) > 1
    ):
        errors.append(f"anchor_identity_mode_mixed:{artifact_path}")
    identity_bindings = sum(
        len(record["identity_bindings"]) for record in independent.values()
    )
    absence_predicates = sum(
        len(record["absence_bindings"]) for record in independent.values()
    )
    legacy_line_bindings = sum(
        len(record["line_bindings"])
        for record in independent.values()
        if record["binding_mode"] == "legacy_line"
    )
    navigation_line_hints = sum(
        len(record["line_bindings"])
        for record in independent.values()
        if record["binding_mode"] == "identity"
    )
    return _DocumentAnchorCensus(
        primary=primary,
        independent=independent,
        navigation=navigation,
        primary_lines=primary_lines,
        independent_lines=independent_lines,
        identity_bindings=identity_bindings,
        absence_predicates=absence_predicates,
        legacy_line_bindings=legacy_line_bindings,
        navigation_line_hints=navigation_line_hints,
        errors=errors,
    )


def validate_anchor_identity_document(
    value: object,
    *,
    artifact_path: str,
    repo_root: Path,
    target_paths: Sequence[str],
) -> list[str]:
    """Validate one in-memory anchor document through the shared identity engine."""
    census = _document_anchor_census(
        value,
        artifact_path=artifact_path,
        target_paths=target_paths,
    )
    errors = list(census.errors)
    _validate_identity_bindings(
        list(census.independent.values()),
        repo_root=repo_root,
        errors=errors,
    )
    _validate_absence_bindings(
        list(census.independent.values()),
        repo_root=repo_root,
        errors=errors,
    )
    return sorted(set(errors))


def build_report(
    *,
    repo_root: Path,
    target_paths: Sequence[str],
    candidate_paths: Sequence[Path],
) -> dict[str, object]:
    """Build a reconciled census over a complete candidate population.

    Args:
        repo_root: Root against which candidate paths resolve.
        target_paths: Generated files whose line-bound receipts must be found.
        candidate_paths: Complete structured-artifact population to inspect.

    Returns:
        A deterministic JSON-compatible report with per-artifact evidence and
        fail-closed reconciliation errors.
    """
    normalized_targets = tuple(dict.fromkeys(str(path) for path in target_paths))
    normalized_candidates = tuple(
        sorted(
            {
                Path(path)
                for path in candidate_paths
                if Path(path).suffix in STRUCTURED_SUFFIXES
            },
            key=str,
        )
    )
    artifacts: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []
    navigation_references: list[dict[str, object]] = []
    errors: list[str] = []
    primary_total = 0
    independent_total = 0
    primary_lines_total = 0
    independent_lines_total = 0
    identity_bindings_total = 0
    absence_predicates_total = 0
    legacy_line_bindings_total = 0
    navigation_line_hints_total = 0

    for relative_path in normalized_candidates:
        absolute_path = repo_root / relative_path
        try:
            value = _parse_structured(absolute_path)
        except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
            errors.append(f"parse_error:{relative_path.as_posix()}:{type(error).__name__}")
            continue

        document = _document_anchor_census(
            value,
            artifact_path=relative_path.as_posix(),
            target_paths=normalized_targets,
        )
        primary = document.primary
        independent = document.independent
        navigation = document.navigation
        if not (primary or independent or navigation):
            continue
        errors.extend(document.errors)
        primary_lines = document.primary_lines
        independent_lines = document.independent_lines
        identity_bindings = document.identity_bindings
        absence_predicates = document.absence_predicates
        legacy_line_bindings = document.legacy_line_bindings
        navigation_line_hints = document.navigation_line_hints
        artifacts.append(
            {
                "path": relative_path.as_posix(),
                "file_type": relative_path.suffix,
                "primary_anchor_records": len(primary),
                "independent_anchor_records": len(independent),
                "line_bindings": independent_lines,
                "identity_bindings": identity_bindings,
                "absence_predicates": absence_predicates,
                "semantic_bindings": identity_bindings + absence_predicates,
                "legacy_line_bindings": legacy_line_bindings,
                "navigation_line_hints": navigation_line_hints,
                "navigation_references": len(navigation),
            }
        )
        bindings.extend(independent.values())
        navigation_references.extend(navigation)
        primary_total += len(primary)
        independent_total += len(independent)
        primary_lines_total += primary_lines
        independent_lines_total += independent_lines
        identity_bindings_total += identity_bindings
        absence_predicates_total += absence_predicates
        legacy_line_bindings_total += legacy_line_bindings
        navigation_line_hints_total += navigation_line_hints

    _validate_identity_bindings(bindings, repo_root=repo_root, errors=errors)
    _validate_absence_bindings(bindings, repo_root=repo_root, errors=errors)

    by_suffix = {
        suffix: sum(path.suffix == suffix for path in normalized_candidates)
        for suffix in sorted(STRUCTURED_SUFFIXES)
    }
    candidate_manifest = "\n".join(path.as_posix() for path in normalized_candidates)
    binding_artifacts = {
        binding["artifact_path"] for binding in bindings
    }
    navigation_artifacts = {
        reference["artifact_path"] for reference in navigation_references
    }

    summary = {
        "binding_artifacts": len(binding_artifacts),
        "navigation_artifacts": len(navigation_artifacts),
        "primary_anchor_records": primary_total,
        "independent_anchor_records": independent_total,
        "line_bindings": primary_lines_total,
        "independent_line_bindings": independent_lines_total,
        "identity_bindings": identity_bindings_total,
        "absence_predicates": absence_predicates_total,
        "semantic_bindings": (
            identity_bindings_total + absence_predicates_total
        ),
        "legacy_line_bindings": legacy_line_bindings_total,
        "navigation_line_hints": navigation_line_hints_total,
        "navigation_references": len(navigation_references),
    }
    return {
        "schema_version": "generated-client-receipt-census.v3",
        "target_paths": list(normalized_targets),
        "candidate_population": {
            "total": len(normalized_candidates),
            "by_suffix": by_suffix,
            "path_sha256": hashlib.sha256(
                candidate_manifest.encode("utf-8")
            ).hexdigest(),
        },
        "summary": summary,
        "artifacts": sorted(artifacts, key=lambda artifact: str(artifact["path"])),
        "bindings": sorted(
            bindings,
            key=lambda binding: (
                str(binding["artifact_path"]),
                str(binding["pointer"]),
            ),
        ),
        "navigation_references": sorted(
            navigation_references,
            key=lambda reference: (
                str(reference["artifact_path"]),
                str(reference["pointer"]),
            ),
        ),
        "errors": sorted(set(errors)),
    }


def _repository_candidates(repo_root: Path) -> tuple[Path, ...]:
    """Derive every Git-visible JSON/TOML candidate, including new files."""
    git_executable = shutil.which("git")
    if git_executable is None:
        raise FileNotFoundError("git executable is required for receipt discovery")
    result = subprocess.run(  # noqa: S603 - resolved Git binary with fixed arguments
        [
            git_executable,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.json",
            "*.toml",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return tuple(
        sorted(
            (Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw),
            key=str,
        )
    )


def build_repository_report(*, repo_root: Path) -> dict[str, object]:
    """Build the live repository report without a remembered artifact list."""
    candidates = _repository_candidates(repo_root)
    return build_report(
        repo_root=repo_root,
        target_paths=DEFAULT_TARGET_PATHS,
        candidate_paths=candidates,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the census CLI and fail ``--check`` on population disagreement."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--target", action="append", dest="targets")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    candidates = _repository_candidates(arguments.repo_root)
    report = build_report(
        repo_root=arguments.repo_root,
        target_paths=arguments.targets or DEFAULT_TARGET_PATHS,
        candidate_paths=candidates,
    )
    print(json.dumps(report, indent=2, sort_keys=True))  # noqa: T201 - CLI boundary
    return 1 if arguments.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
