#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

from pydantic import Field, create_model
from pydantic_core import PydanticUndefined

from tools.lib.cache import (
    cache_path,
    content_addressable_key,
    default_cache_root,
    file_sha256,
    git_changed_files,
    persist_baseline,
    read_json_cache,
    stable_json_hash,
    write_json_cache,
)
from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.schemas.abi_models import (  # noqa: E402
    ABIModelEntry,
    SchemaMode,
    select_abi_entries,
)
from tools.quality.diagnostics.generate_ir_reference_catalog import (  # noqa: E402
    generate_reference_docs,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "schemas" / "snapshots"
GENERATOR_VERSION = "1.1.0"
METADATA_KEYS = {"title", "description", "$comment", "examples"}
# These record where/when the snapshot was produced, not its ABI. If a supported
# interpreter or Pydantic release changes a schema, the freshly generated payload
# and its model hashes must expose that difference instead of the version header.
MANIFEST_PROVENANCE_KEYS = {"generated_at", "python_version", "pydantic_version"}
CACHE_NAMESPACE = "diagnostics.gen_schema"
CACHE_VERSION = "2026.10.schema-variant"
DEFAULT_BASELINE_LABEL = "default"
MODULE_COMPATIBILITY: dict[str, dict[str, str]] = {
    "fabric": {
        "compatibility_class": "schema-openapi-abi",
        "version_owner": "team-fabric",
        "deprecation_window": "2 minor releases",
        "release_fragment_change_class": "schema-openapi-abi",
        "breaking_change_requires_fragment": "true",
    },
    "ir": {
        "compatibility_class": "persisted-artifact-format",
        "version_owner": "team-ir",
        "deprecation_window": "2 minor releases",
        "release_fragment_change_class": "persisted-artifact-format",
        "breaking_change_requires_fragment": "true",
    },
    "scientist": {
        "compatibility_class": "persisted-artifact-format",
        "version_owner": "team-scientist",
        "deprecation_window": "2 minor releases",
        "release_fragment_change_class": "persisted-artifact-format",
        "breaking_change_requires_fragment": "true",
    },
}
FULL_REBUILD_SENTINELS = {
    REPO_ROOT / "src" / "polisyos" / "schemas" / "abi_models" / "__init__.py",
    REPO_ROOT / "src" / "polisyos" / "schemas" / "abi_models" / "catalog.py",
    REPO_ROOT / "tools" / "quality" / "diagnostics" / "gen_schema.py",
    REPO_ROOT / "tools" / "quality" / "diagnostics" / "generate_ir_reference_catalog.py",
}
GOVERNED_NON_ABI_SNAPSHOT_FILES: dict[str, set[str]] = {
    # This registry is generated and drift-checked by dedicated Fabric tooling.
    "fabric": {
        "connector_contract_registry.json",
        "source_contracts_v2.json",
        "source_scorecards.json",
    },
}


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedABIEntry:
    entry: ABIModelEntry
    cls: type[Any]
    source_path: Path | None
    source_hash: str | None


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or validate committed ABI JSON Schema snapshots "
            "for IR/fabric compatibility checks."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Snapshot output directory (default: schemas/snapshots)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when committed snapshots do not match generated schemas",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        help=("Optional model filters by abi_key/module/priority/fqn (e.g. --models claim p0 ir)"),
    )
    parser.add_argument(
        "--format",
        choices=("pretty", "compact"),
        default="pretty",
        help="Snapshot JSON formatting (default: pretty)",
    )
    parser.add_argument(
        "--include-deprecated",
        action="store_true",
        help="Include deprecated ABI entries from registry",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Validate the Git change scope, then run a full check (legacy optimisation hint).",
    )
    parser.add_argument(
        "--git-base-ref",
        default="HEAD",
        help="Git base ref used by --changed-only.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory for content-addressable schema cache and persisted baselines.",
    )
    parser.add_argument(
        "--skip-if-unchanged",
        action="store_true",
        help="Record a successful baseline after a full run (legacy optimisation hint).",
    )
    parser.add_argument(
        "--baseline-label",
        help="Named baseline label used by --skip-if-unchanged and persisted cache state.",
    )

    # Deprecated flags kept for backward compatibility with older scripts.
    parser.add_argument("--model", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)

    return parser.parse_args(argv)


def _resolve_class(fqn: str) -> type[Any]:
    module_path, class_name = fqn.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name, None)
    if cls is None:
        raise AttributeError(f"Class not found: {fqn}")
    return cls


def _class_source_path(cls: type[Any]) -> Path | None:
    module = importlib.import_module(cls.__module__)
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return None
    path = Path(module_file)
    if path.suffix == ".pyc" and path.with_suffix(".py").exists():
        path = path.with_suffix(".py")
    return path.resolve()


def _resolve_entry(entry: ABIModelEntry) -> ResolvedABIEntry:
    cls = _resolve_class(entry.fqn)
    source_path = _class_source_path(cls)
    source_hash = (
        file_sha256(source_path) if source_path is not None and source_path.exists() else None
    )
    return ResolvedABIEntry(
        entry=entry,
        cls=cls,
        source_path=source_path,
        source_hash=source_hash,
    )


def _strip_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in METADATA_KEYS:
                continue
            cleaned[key] = _strip_metadata(item)
        return cleaned
    if isinstance(value, list):
        return [_strip_metadata(item) for item in value]
    return value


def _json_dump(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "compact":
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _schema_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _schema_version_for(entry: ABIModelEntry, cls: type[Any]) -> str | None:
    if entry.schema_variant_version is not None:
        return entry.schema_variant_version
    if entry.version_field is None:
        return None
    model_fields = getattr(cls, "model_fields", None)
    if isinstance(model_fields, dict) and entry.version_field in model_fields:
        field_info = model_fields[entry.version_field]
        default = getattr(field_info, "default", PydanticUndefined)
        if default is not PydanticUndefined:
            return str(default) if default is not None else None
        if getattr(field_info, "default_factory", None) is not None:
            return None
        annotation = getattr(field_info, "annotation", None)
        if get_origin(annotation) is Literal:
            literal_values = get_args(annotation)
            if literal_values and all(isinstance(value, str) for value in literal_values):
                unique_values = set(literal_values)
                if len(unique_values) == 1:
                    return next(iter(unique_values))
        return None
    value = getattr(cls, entry.version_field, None)
    if value is not None and value is not PydanticUndefined:
        return str(value)
    return None


def _generate_enum_schema(cls: type[Enum]) -> dict[str, Any]:
    enum_values = sorted(member.value for member in cls)
    return {
        "type": "string",
        "enum": enum_values,
        "title": cls.__name__,
        "x-fqn": f"{cls.__module__}.{cls.__qualname__}",
    }


def _schema_variant_model(entry: ABIModelEntry, cls: type[Any]) -> type[Any]:
    """Bind a requested schema version to the source model's typed version field."""
    requested_version = entry.schema_variant_version
    if requested_version is None:
        return cls

    field_name = entry.version_field
    model_fields = getattr(cls, "model_fields", None)
    if field_name is None or not isinstance(model_fields, dict) or field_name not in model_fields:
        raise GenerationError(
            f"Schema variant {requested_version!r} for {entry.abi_key!r} "
            "requires a declared version field"
        )

    field_info = model_fields[field_name]
    annotation = getattr(field_info, "annotation", None)
    if get_origin(annotation) is not Literal or requested_version not in get_args(annotation):
        raise GenerationError(
            f"Schema variant {requested_version!r} for {entry.abi_key!r} "
            f"is not allowed by the typed {field_name!r} field"
        )
    if (
        getattr(field_info, "alias", None) is not None
        or getattr(field_info, "validation_alias", None) is not None
        or getattr(field_info, "serialization_alias", None) is not None
        or getattr(field_info, "metadata", ())
        or getattr(field_info, "json_schema_extra", None) is not None
    ):
        raise GenerationError(
            f"Schema variant field {field_name!r} on {entry.abi_key!r} "
            "uses unsupported schema metadata"
        )

    return create_model(
        cls.__name__,
        __base__=cls,
        __module__=cls.__module__,
        **{field_name: (Literal[requested_version], Field(default=requested_version))},
    )


def _generate_model_schema(
    cls: type[Any], *, mode: SchemaMode = SchemaMode.VALIDATION
) -> dict[str, Any]:
    if hasattr(cls, "model_json_schema"):
        return cls.model_json_schema(mode=mode.value, by_alias=True)
    if isinstance(cls, type) and issubclass(cls, Enum):
        return _generate_enum_schema(cls)
    raise TypeError(f"Unsupported ABI class (not Pydantic model or Enum): {cls}")


def _write_text_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text("utf-8") == content:
        return False
    atomic_write_text(path, content, encoding="utf-8")
    return True


def _manifest_content(payload: dict[str, Any]) -> dict[str, Any]:
    # Top-level only: an identically named model field is still schema content.
    return {key: value for key, value in payload.items() if key not in MANIFEST_PROVENANCE_KEYS}


def _manifest_content_changed(path: Path, payload: dict[str, Any]) -> bool:
    if not path.exists():
        return True
    existing = json.loads(path.read_text("utf-8"))
    return _manifest_content(existing) != _manifest_content(payload)


def _build_manifest(
    *,
    module: str,
    model_entries: dict[str, dict[str, Any]],
    pydantic_version: str,
) -> dict[str, Any]:
    compatibility = MODULE_COMPATIBILITY.get(
        module,
        {
            "compatibility_class": "schema-openapi-abi",
            "version_owner": "team-polisyos",
            "deprecation_window": "2 minor releases",
            "release_fragment_change_class": "schema-openapi-abi",
            "breaking_change_requires_fragment": "true",
        },
    )
    manifest = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "generator_version": GENERATOR_VERSION,
        "python_version": platform.python_version(),
        "pydantic_version": pydantic_version,
        "module": module,
        "compatibility": compatibility,
        "models": model_entries,
    }
    manifest["content_hash"] = _schema_hash(manifest["models"])
    return manifest


def _import_version(module_name: str) -> str:
    module = importlib.import_module(module_name)
    return str(getattr(module, "__version__", "unknown"))


def _assert_file_equals(path: Path, expected: str, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing snapshot: {path}")
        return
    current = path.read_text("utf-8")
    if current != expected:
        errors.append(f"snapshot out of date: {path}")


def _assert_manifest_equals(path: Path, expected: dict[str, Any], errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing snapshot: {path}")
        return
    try:
        current = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        errors.append(f"invalid manifest JSON: {path}")
        return
    if _manifest_content(current) != _manifest_content(expected):
        errors.append(f"snapshot out of date: {path}")


def _entry_cache_key(
    resolved: ResolvedABIEntry,
    *,
    pydantic_version: str,
) -> str:
    return content_addressable_key(
        version=CACHE_VERSION,
        payload={
            "generator_version": GENERATOR_VERSION,
            "pydantic_version": pydantic_version,
            "abi_key": resolved.entry.abi_key,
            "module": resolved.entry.module,
            "fqn": resolved.entry.fqn,
            "schema_file": resolved.entry.schema_file,
            "priority": resolved.entry.priority.value,
            "compat_mode": resolved.entry.compat_mode.value,
            "version_field": resolved.entry.version_field,
            "schema_mode": resolved.entry.schema_mode.value,
            "schema_variant_version": resolved.entry.schema_variant_version,
            "aliases": list(resolved.entry.aliases),
            "lifecycle": resolved.entry.lifecycle.value,
            "source_path": str(resolved.source_path) if resolved.source_path is not None else None,
            "source_hash": resolved.source_hash,
        },
    )


def _load_or_generate_entry_payload(
    resolved: ResolvedABIEntry,
    *,
    cache_root: Path | None,
    pydantic_version: str,
) -> dict[str, Any]:
    # A defining-file hash does not bind imported models, enums, base classes or
    # schema hooks. Recompute the complete runtime payload before consulting any
    # persisted candidate; the cache may avoid a write, never establish a schema.
    schema_model = _schema_variant_model(resolved.entry, resolved.cls)
    schema_payload = _generate_model_schema(schema_model, mode=resolved.entry.schema_mode)
    semantic_payload = _strip_metadata(schema_payload)
    schema_version = _schema_version_for(resolved.entry, resolved.cls)
    payload = {
        "schema_payload": schema_payload,
        "schema_version": schema_version,
        "sha256_full": _schema_hash(schema_payload),
        "sha256_semantic": _schema_hash(semantic_payload),
    }
    if cache_root is not None:
        target = cache_path(
            cache_root,
            CACHE_NAMESPACE,
            _entry_cache_key(resolved, pydantic_version=pydantic_version),
        )
        if read_json_cache(target) != payload:
            write_json_cache(target, payload)
    return payload


def _process_module(
    *,
    module: str,
    entries: tuple[ABIModelEntry, ...],
    output_dir: Path,
    fmt: str,
    check: bool,
    errors: list[str],
    cache_root: Path | None = None,
    resolved_entries: dict[str, ResolvedABIEntry] | None = None,
    pydantic_version: str | None = None,
) -> tuple[int, dict[str, dict[str, Any]]]:
    updated = 0
    manifest_entries: dict[str, dict[str, Any]] = {}

    module_dir = output_dir / module
    seen_schema_files: set[str] = set()
    resolved_map = resolved_entries or {}
    effective_pydantic_version = pydantic_version or _import_version("pydantic")

    for entry in sorted(entries, key=lambda item: item.abi_key):
        resolved = resolved_map.get(entry.abi_key)
        if resolved is None:
            try:
                resolved = _resolve_entry(entry)
            except Exception as exc:
                if entry.allow_missing:
                    print(f"[WARN] skipped missing optional ABI entry {entry.abi_key}: {exc}")
                    continue
                raise GenerationError(
                    f"Failed to import ABI entry '{entry.abi_key}': {exc}"
                ) from exc

        payload = _load_or_generate_entry_payload(
            resolved,
            cache_root=cache_root,
            pydantic_version=effective_pydantic_version,
        )
        schema_payload = payload["schema_payload"]
        assert isinstance(schema_payload, dict)
        schema_version = payload.get("schema_version")

        target = module_dir / entry.schema_file
        content = _json_dump(schema_payload, fmt=fmt)

        if check:
            _assert_file_equals(target, content, errors)
        else:
            if _write_text_if_changed(target, content):
                updated += 1

        manifest_entry = {
            "fqn": entry.fqn,
            "schema_file": entry.schema_file,
            "schema_version": schema_version,
            "priority": entry.priority.value,
            "compat_mode": entry.compat_mode.value,
            "version_field": entry.version_field,
            "aliases": list(entry.aliases),
            "lifecycle": entry.lifecycle.value,
            "sha256_full": str(payload["sha256_full"]),
            "sha256_semantic": str(payload["sha256_semantic"]),
        }
        if (
            entry.schema_mode is not SchemaMode.VALIDATION
            or entry.schema_variant_version is not None
        ):
            manifest_entry["schema_mode"] = entry.schema_mode.value
            manifest_entry["schema_variant_version"] = entry.schema_variant_version
        manifest_entries[entry.abi_key] = manifest_entry
        seen_schema_files.add(entry.schema_file)

    manifest_payload = _build_manifest(
        module=module,
        model_entries=manifest_entries,
        pydantic_version=effective_pydantic_version,
    )
    manifest_path = module_dir / "_manifest.json"
    manifest_content = _json_dump(manifest_payload, fmt="pretty")

    if check:
        _assert_manifest_equals(manifest_path, manifest_payload, errors)
    else:
        if _manifest_content_changed(manifest_path, manifest_payload):
            if _write_text_if_changed(manifest_path, manifest_content):
                updated += 1

    if check and module_dir.exists():
        tracked = (
            seen_schema_files
            | {"_manifest.json"}
            | GOVERNED_NON_ABI_SNAPSHOT_FILES.get(module, set())
        )
        for path in sorted(module_dir.glob("*.json")):
            if path.name not in tracked:
                errors.append(f"unexpected snapshot file (not in registry): {path}")

    return updated, manifest_entries


def _handle_deprecated_single_model_mode(args: argparse.Namespace) -> bool:
    if not args.model and not args.output:
        return False
    print("[WARN] --model/--output are deprecated. Use ABI registry via --models/--output-dir.")
    if args.model and not args.models:
        args.models = [args.model]
    if args.output:
        if args.output.suffix == ".json":
            args.output_dir = args.output.parent
        else:
            args.output_dir = args.output
    return True


def _resolve_entries(entries: Sequence[ABIModelEntry]) -> tuple[ResolvedABIEntry, ...]:
    resolved: list[ResolvedABIEntry] = []
    for entry in entries:
        try:
            resolved.append(_resolve_entry(entry))
        except Exception as exc:
            if entry.allow_missing:
                print(f"[WARN] skipped missing optional ABI entry {entry.abi_key}: {exc}")
                continue
            raise GenerationError(f"Failed to import ABI entry '{entry.abi_key}': {exc}") from exc
    return tuple(resolved)


def _changed_source_scope(base_ref: str) -> tuple[set[Path], bool]:
    changed_paths = set(git_changed_files(REPO_ROOT, base_ref=base_ref))
    if not changed_paths:
        return set(), False
    if any(path in FULL_REBUILD_SENTINELS for path in changed_paths):
        return set(), True
    changed_under_src = {
        path.resolve() for path in changed_paths if path.resolve().is_relative_to(SRC_ROOT)
    }
    if any(path.suffix == ".py" and not path.exists() for path in changed_under_src):
        return set(), True
    changed_sources = {path for path in changed_under_src if path.suffix == ".py" and path.exists()}
    return changed_sources, False


def _build_run_fingerprint(
    *,
    resolved_entries: Sequence[ResolvedABIEntry],
    output_dir: Path,
    fmt: str,
    check: bool,
    include_deprecated: bool,
    scan_mode: str,
) -> str:
    return stable_json_hash(
        {
            "cache_version": CACHE_VERSION,
            "generator_version": GENERATOR_VERSION,
            "pydantic_version": _import_version("pydantic"),
            "tool_sha256": file_sha256(Path(__file__)),
            "output_dir": str(output_dir),
            "format": fmt,
            "check": check,
            "include_deprecated": include_deprecated,
            "scan_mode": scan_mode,
            "entries": [
                {
                    "abi_key": resolved.entry.abi_key,
                    "module": resolved.entry.module,
                    "schema_file": resolved.entry.schema_file,
                    "schema_mode": resolved.entry.schema_mode.value,
                    "schema_variant_version": resolved.entry.schema_variant_version,
                    "fqn": resolved.entry.fqn,
                    "source_path": str(resolved.source_path) if resolved.source_path else None,
                    "source_hash": resolved.source_hash,
                }
                for resolved in sorted(resolved_entries, key=lambda item: item.entry.abi_key)
            ],
        }
    )


def _nearest_existing_path(path: Path) -> tuple[Path, tuple[str, ...]]:
    """Return the nearest existing path and the unresolved suffix below it."""
    unresolved: list[str] = []
    current = path.resolve(strict=False)
    while not current.exists():
        parent = current.parent
        if parent == current:
            break
        unresolved.append(current.name)
        current = parent
    return current, tuple(reversed(unresolved))


def _same_directory_identity(left: Path, right: Path) -> bool | None:
    """Compare physical directory identity, or return None when it is unprovable.

    Existing destinations use the filesystem identity check, which follows
    symlinks and case-insensitive aliases. Missing destinations are compared by
    their nearest existing physical directory and the full unresolved suffix.
    Different unresolved spellings under the same physical parent remain
    ambiguous, so callers must not treat them as a separate preview.
    """
    try:
        resolved_left = left.resolve(strict=False)
        resolved_right = right.resolve(strict=False)
        if resolved_left.exists() and resolved_right.exists():
            if not resolved_left.is_dir() or not resolved_right.is_dir():
                return False
            return resolved_left.samefile(resolved_right)

        left_parent, left_suffix = _nearest_existing_path(resolved_left)
        right_parent, right_suffix = _nearest_existing_path(resolved_right)
        if not left_parent.is_dir() or not right_parent.is_dir():
            return False
        if not left_parent.samefile(right_parent):
            return False
        if left_suffix == right_suffix:
            return True
        if len(left_suffix) != len(right_suffix):
            return False
        return None
    except (OSError, RuntimeError):
        return None


def _is_canonical_output_dir(output_dir: Path) -> bool:
    """Classify the destination or fail closed when physical identity is unknown."""
    same_directory = _same_directory_identity(output_dir, DEFAULT_OUTPUT_DIR)
    if same_directory is None:
        raise GenerationError(
            "Cannot establish whether --output-dir is separate from canonical "
            "schemas/snapshots: physical directory identity could not be proven. "
            "Refusing an ambiguous destination; "
            "use the canonical path, an existing separate preview directory, or "
            "a path under a distinct existing parent."
        )
    return same_directory


def _select_run_entries(
    args: argparse.Namespace,
    *,
    canonical_output: bool,
) -> tuple[tuple[ABIModelEntry, ...], str, int]:
    """Resolve a truthful registry scope for generation or checking."""
    registry_entries = select_abi_entries(None, include_deprecated=args.include_deprecated)
    selected_entries = select_abi_entries(args.models, include_deprecated=args.include_deprecated)
    has_model_filter = bool(args.models and any(token.strip() for token in args.models))
    if not has_model_filter:
        return registry_entries, "full", len(registry_entries)

    selected_modules = {entry.module for entry in selected_entries}
    module_entries = tuple(entry for entry in registry_entries if entry.module in selected_modules)
    selected_by_module: dict[str, set[str]] = {}
    registry_by_module: dict[str, set[str]] = {}
    for entry in selected_entries:
        selected_by_module.setdefault(entry.module, set()).add(entry.abi_key)
    for entry in module_entries:
        registry_by_module.setdefault(entry.module, set()).add(entry.abi_key)
    partial_modules = [
        f"{module} ({len(selected_by_module.get(module, set()))}/{len(keys)} entries)"
        for module, keys in sorted(registry_by_module.items())
        if selected_by_module.get(module, set()) != keys
    ]

    if args.check and canonical_output:
        # Canonical manifests cover complete modules; a model selector narrows
        # which modules are checked, never the files within those modules.
        return module_entries, "complete_modules", len(registry_entries)

    if not args.check and canonical_output and partial_modules:
        details = ", ".join(partial_modules)
        raise GenerationError(
            "Refusing partial canonical schema generation: --models selects "
            f"{details}, which would replace a complete module manifest with a "
            "partial registry. Select complete module(s), or use a noncanonical "
            "--output-dir for an isolated preview."
        )

    scope = "complete_modules" if not partial_modules else "selected_entries"
    return selected_entries, scope, len(registry_entries)


def _run(args: argparse.Namespace) -> int:
    _handle_deprecated_single_model_mode(args)
    canonical_output = _is_canonical_output_dir(args.output_dir)

    entries, selection_scope, registry_entry_count = _select_run_entries(
        args, canonical_output=canonical_output
    )
    if not entries:
        if args.check:
            raise GenerationError("No ABI entries selected; no snapshots were measured.")
        print("No ABI entries selected. Nothing to do.")
        return 0

    resolved_entries = _resolve_entries(entries)
    if not resolved_entries:
        if args.check:
            raise GenerationError("No ABI entries resolved; no snapshots were measured.")
        print("No ABI entries selected. Nothing to do.")
        return 0

    scan_mode = "full"
    changed_sources: set[Path] = set()
    if args.changed_only:
        try:
            changed_sources, _ = _changed_source_scope(args.git_base_ref)
        except ValueError as exc:
            print(f"ABI schema snapshot check UNRUN: {exc}", file=sys.stderr)
            return 2

    # Git scope and saved baselines are diagnostic metadata, not sufficient
    # evidence about transitive schemas or the current snapshot/reference bytes.
    if args.changed_only or args.skip_if_unchanged:
        print("[INFO] Legacy incremental hint: recomputing all selected schemas and references.")

    cache_root = args.cache_dir.resolve() if args.cache_dir else default_cache_root(REPO_ROOT)
    baseline_label = args.baseline_label or (
        DEFAULT_BASELINE_LABEL if args.skip_if_unchanged else None
    )
    fingerprint = _build_run_fingerprint(
        resolved_entries=resolved_entries,
        output_dir=args.output_dir,
        fmt=args.format,
        check=args.check,
        include_deprecated=args.include_deprecated,
        scan_mode=scan_mode,
    )
    resolved_entries_by_key = {resolved.entry.abi_key: resolved for resolved in resolved_entries}
    by_module: dict[str, list[ABIModelEntry]] = {}
    for entry in entries:
        if entry.abi_key in resolved_entries_by_key:
            by_module.setdefault(entry.module, []).append(entry)

    pydantic_version = _import_version("pydantic")
    errors: list[str] = []
    total_updates = 0
    total_models = 0

    for module, module_entries in sorted(by_module.items()):
        updated, manifest_entries = _process_module(
            module=module,
            entries=tuple(module_entries),
            output_dir=args.output_dir,
            fmt=args.format,
            check=args.check,
            errors=errors,
            cache_root=cache_root,
            resolved_entries=resolved_entries_by_key,
            pydantic_version=pydantic_version,
        )
        total_updates += updated
        total_models += len(manifest_entries)

    if canonical_output:
        errors.extend(generate_reference_docs(check=args.check))
    elif not args.check:
        print(
            "[INFO] Skipped canonical IR reference-page generation for noncanonical --output-dir."
        )

    if args.check:
        if errors:
            print(
                "ABI schema snapshot check failed "
                f"(scope={selection_scope}, "
                f"registry={total_models}/{registry_entry_count}):"
            )
            for err in errors:
                print(f"- {err}")
            return 1
        if baseline_label is not None:
            persist_baseline(
                cache_root,
                CACHE_NAMESPACE,
                baseline_label,
                fingerprint=fingerprint,
                exit_code=0,
                metadata={
                    "scan_mode": scan_mode,
                    "changed_source_count": len(changed_sources),
                    "selection_scope": selection_scope,
                    "registry_entry_count": registry_entry_count,
                },
            )
        print(
            "ABI schema snapshot check passed "
            f"({total_models} models, scope={selection_scope}, "
            f"registry={total_models}/{registry_entry_count}, scan_mode={scan_mode})"
        )
        return 0

    if baseline_label is not None:
        persist_baseline(
            cache_root,
            CACHE_NAMESPACE,
            baseline_label,
            fingerprint=fingerprint,
            exit_code=0,
            metadata={
                "scan_mode": scan_mode,
                "changed_source_count": len(changed_sources),
                "selection_scope": selection_scope,
                "registry_entry_count": registry_entry_count,
            },
        )
    print(
        f"Generated ABI schema snapshots for {total_models} models "
        f"({total_updates} file updates, scope={selection_scope}, "
        f"registry={total_models}/{registry_entry_count}, scan_mode={scan_mode})"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Return a measured verdict, or exit 2 when schema execution is unavailable."""
    args = _parse_args(argv)
    try:
        return _run(args)
    except Exception as error:
        # Exit 1 belongs only to a completed artifact comparison. Every producer
        # (models, references, cache I/O) must complete before that verdict exists.
        action = "check" if args.check else "generation"
        print(
            f"ABI schema snapshot {action} UNRUN: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
