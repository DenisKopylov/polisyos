#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from schemas.abi_models import ABIModelEntry, select_abi_entries  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "schemas" / "snapshots"
GENERATOR_VERSION = "1.0.0"
METADATA_KEYS = {"title", "description", "$comment", "examples"}


class GenerationError(RuntimeError):
    pass


def _parse_args() -> argparse.Namespace:
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
        help=(
            "Optional model filters by abi_key/module/priority/fqn "
            "(e.g. --models claim p0 ir)"
        ),
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

    # Deprecated flags kept for backward compatibility with older scripts.
    parser.add_argument("--model", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)

    return parser.parse_args()


def _resolve_class(fqn: str) -> type[Any]:
    module_path, class_name = fqn.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name, None)
    if cls is None:
        raise AttributeError(f"Class not found: {fqn}")
    return cls


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
    if entry.version_field is None:
        return None
    model_fields = getattr(cls, "model_fields", None)
    if isinstance(model_fields, dict) and entry.version_field in model_fields:
        field_info = model_fields[entry.version_field]
        default = getattr(field_info, "default", None)
        if default is not None:
            return str(default)
    value = getattr(cls, entry.version_field, None)
    if value is not None:
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


def _generate_model_schema(cls: type[Any]) -> dict[str, Any]:
    if hasattr(cls, "model_json_schema"):
        return cls.model_json_schema(mode="validation", by_alias=True)
    if isinstance(cls, type) and issubclass(cls, Enum):
        return _generate_enum_schema(cls)
    raise TypeError(f"Unsupported ABI class (not Pydantic model or Enum): {cls}")


def _write_text_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text("utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _manifest_content_changed(path: Path, payload: dict[str, Any]) -> bool:
    if not path.exists():
        return True
    existing = json.loads(path.read_text("utf-8"))
    existing.pop("generated_at", None)
    candidate = dict(payload)
    candidate.pop("generated_at", None)
    return existing != candidate


def _build_manifest(
    *,
    module: str,
    model_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    manifest = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "generator_version": GENERATOR_VERSION,
        "python_version": platform.python_version(),
        "pydantic_version": _import_version("pydantic"),
        "module": module,
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
    current_clean = dict(current)
    current_clean.pop("generated_at", None)
    expected_clean = dict(expected)
    expected_clean.pop("generated_at", None)
    if current_clean != expected_clean:
        errors.append(f"snapshot out of date: {path}")


def _process_module(
    *,
    module: str,
    entries: tuple[ABIModelEntry, ...],
    output_dir: Path,
    fmt: str,
    check: bool,
    errors: list[str],
) -> tuple[int, dict[str, dict[str, Any]]]:
    updated = 0
    manifest_entries: dict[str, dict[str, Any]] = {}

    module_dir = output_dir / module
    seen_schema_files: set[str] = set()

    for entry in sorted(entries, key=lambda item: item.abi_key):
        try:
            cls = _resolve_class(entry.fqn)
        except Exception as exc:
            if entry.allow_missing:
                print(f"[WARN] skipped missing optional ABI entry {entry.abi_key}: {exc}")
                continue
            raise GenerationError(f"Failed to import ABI entry '{entry.abi_key}': {exc}") from exc

        schema_payload = _generate_model_schema(cls)
        semantic_payload = _strip_metadata(schema_payload)
        schema_version = _schema_version_for(entry, cls)

        target = module_dir / entry.schema_file
        content = _json_dump(schema_payload, fmt=fmt)

        if check:
            _assert_file_equals(target, content, errors)
        else:
            if _write_text_if_changed(target, content):
                updated += 1

        manifest_entries[entry.abi_key] = {
            "fqn": entry.fqn,
            "schema_file": entry.schema_file,
            "schema_version": schema_version,
            "priority": entry.priority.value,
            "compat_mode": entry.compat_mode.value,
            "version_field": entry.version_field,
            "aliases": list(entry.aliases),
            "lifecycle": entry.lifecycle.value,
            "sha256_full": _schema_hash(schema_payload),
            "sha256_semantic": _schema_hash(semantic_payload),
        }
        seen_schema_files.add(entry.schema_file)

    manifest_payload = _build_manifest(module=module, model_entries=manifest_entries)
    manifest_path = module_dir / "_manifest.json"
    manifest_content = _json_dump(manifest_payload, fmt="pretty")

    if check:
        _assert_manifest_equals(manifest_path, manifest_payload, errors)
    else:
        if _manifest_content_changed(manifest_path, manifest_payload):
            if _write_text_if_changed(manifest_path, manifest_content):
                updated += 1

    if check and module_dir.exists():
        tracked = seen_schema_files | {"_manifest.json"}
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


def main() -> int:
    args = _parse_args()
    _handle_deprecated_single_model_mode(args)

    entries = select_abi_entries(args.models, include_deprecated=args.include_deprecated)
    if not entries:
        print("No ABI entries selected. Nothing to do.")
        return 0

    by_module: dict[str, list[ABIModelEntry]] = {}
    for entry in entries:
        by_module.setdefault(entry.module, []).append(entry)

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
        )
        total_updates += updated
        total_models += len(manifest_entries)

    if args.check:
        if errors:
            print("ABI schema snapshot check failed:")
            for err in errors:
                print(f"- {err}")
            return 1
        print(f"ABI schema snapshot check passed ({total_models} models)")
        return 0

    print(
        f"Generated ABI schema snapshots for {total_models} models "
        f"({total_updates} file updates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
