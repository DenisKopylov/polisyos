#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ChangeKind(str, Enum):
    MODEL_ADDED = "model_added"
    MODEL_REMOVED = "model_removed"
    MODEL_RENAMED = "model_renamed"
    PROPERTY_ADDED = "property_added"
    PROPERTY_REMOVED = "property_removed"
    PROPERTY_TYPE_CHANGED = "property_type_changed"
    PROPERTY_REQUIRED_ADDED = "property_required_added"
    PROPERTY_REQUIRED_REMOVED = "property_required_removed"
    CONSTRAINT_CHANGED = "constraint_changed"
    ENUM_VALUE_ADDED = "enum_value_added"
    ENUM_VALUE_REMOVED = "enum_value_removed"
    REF_CHANGED = "ref_changed"
    METADATA_CHANGED = "metadata_changed"


@dataclass(frozen=True)
class ModelSnapshot:
    abi_key: str
    module: str
    schema_path: Path
    schema: dict[str, Any]
    schema_version: str | None
    priority: str
    compat_mode: str
    version_field: str | None
    aliases: tuple[str, ...]
    lifecycle: str
    sha256_full: str | None
    sha256_semantic: str | None


@dataclass(frozen=True)
class SchemaChange:
    model: str
    module: str
    path: str
    kind: ChangeKind
    breaking: bool
    priority: str
    message: str
    old_value: Any = None
    new_value: Any = None


@dataclass
class DiffReport:
    changes: list[SchemaChange] = field(default_factory=list)
    version_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    baseline_versions: dict[str, str | None] = field(default_factory=dict)
    current_versions: dict[str, str | None] = field(default_factory=dict)

    @property
    def breaking_count(self) -> int:
        return sum(1 for change in self.changes if change.breaking)

    @property
    def compatible_count(self) -> int:
        return sum(1 for change in self.changes if not change.breaking)

    @property
    def verdict(self) -> str:
        if self.version_errors:
            return "FAIL"
        has_p0_breaking = any(
            change.breaking and change.priority == "p0" for change in self.changes
        )
        if has_p0_breaking:
            return "WARN"
        return "PASS"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Semantic diff between ABI schema snapshot directories"
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "github"),
        default="json",
    )
    parser.add_argument("--github-comment", type=Path)
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def _load_snapshots(root: Path) -> dict[str, ModelSnapshot]:
    snapshots: dict[str, ModelSnapshot] = {}
    for module in ("ir", "fabric"):
        manifest_path = root / module / "_manifest.json"
        if not manifest_path.exists():
            continue

        manifest = _load_json(manifest_path)
        models = manifest.get("models", {})
        if not isinstance(models, dict):
            continue

        for abi_key, meta_any in models.items():
            if not isinstance(meta_any, dict):
                continue
            schema_file = str(meta_any.get("schema_file", ""))
            if not schema_file:
                continue
            schema_path = root / module / schema_file
            if not schema_path.exists():
                continue
            schema = _load_json(schema_path)
            snapshot = ModelSnapshot(
                abi_key=abi_key,
                module=module,
                schema_path=schema_path,
                schema=schema,
                schema_version=(
                    str(meta_any.get("schema_version"))
                    if meta_any.get("schema_version") is not None
                    else None
                ),
                priority=str(meta_any.get("priority", "p1")),
                compat_mode=str(meta_any.get("compat_mode", "strict")),
                version_field=(
                    str(meta_any.get("version_field"))
                    if meta_any.get("version_field") is not None
                    else None
                ),
                aliases=tuple(meta_any.get("aliases", []) or []),
                lifecycle=str(meta_any.get("lifecycle", "active")),
                sha256_full=(
                    str(meta_any.get("sha256_full"))
                    if meta_any.get("sha256_full") is not None
                    else None
                ),
                sha256_semantic=(
                    str(meta_any.get("sha256_semantic"))
                    if meta_any.get("sha256_semantic") is not None
                    else None
                ),
            )
            snapshots[f"{module}:{abi_key}"] = snapshot
    return snapshots


def _schema_canonical(schema: dict[str, Any]) -> str:
    return json.dumps(schema, sort_keys=True, separators=(",", ":"))


def _match_renamed_models(
    *,
    baseline_only: dict[str, ModelSnapshot],
    current_only: dict[str, ModelSnapshot],
) -> list[tuple[ModelSnapshot, ModelSnapshot, str]]:
    matches: list[tuple[ModelSnapshot, ModelSnapshot, str]] = []
    consumed_baseline: set[str] = set()
    consumed_current: set[str] = set()

    # 1) alias-based match
    for b_key, b_model in baseline_only.items():
        for c_key, c_model in current_only.items():
            if b_key in consumed_baseline or c_key in consumed_current:
                continue
            c_aliases = {alias.lower() for alias in c_model.aliases}
            b_aliases = {alias.lower() for alias in b_model.aliases}
            b_name = b_model.abi_key.lower()
            c_name = c_model.abi_key.lower()
            if b_name in c_aliases or c_name in b_aliases:
                matches.append((b_model, c_model, "alias"))
                consumed_baseline.add(b_key)
                consumed_current.add(c_key)

    # 2) semantic hash exact match fallback
    for b_key, b_model in baseline_only.items():
        if b_key in consumed_baseline:
            continue
        for c_key, c_model in current_only.items():
            if c_key in consumed_current:
                continue
            if (
                b_model.sha256_semantic
                and c_model.sha256_semantic
                and b_model.sha256_semantic == c_model.sha256_semantic
            ):
                matches.append((b_model, c_model, "semantic_hash"))
                consumed_baseline.add(b_key)
                consumed_current.add(c_key)
                break

    # 3) structural similarity fallback
    for b_key, b_model in baseline_only.items():
        if b_key in consumed_baseline:
            continue
        best: tuple[str, ModelSnapshot, float] | None = None
        b_data = _schema_canonical(b_model.schema)
        for c_key, c_model in current_only.items():
            if c_key in consumed_current:
                continue
            ratio = difflib.SequenceMatcher(
                a=b_data,
                b=_schema_canonical(c_model.schema),
            ).ratio()
            if ratio >= 0.90 and (best is None or ratio > best[2]):
                best = (c_key, c_model, ratio)
        if best is not None:
            c_key, c_model, ratio = best
            matches.append((b_model, c_model, f"similarity:{ratio:.2f}"))
            consumed_baseline.add(b_key)
            consumed_current.add(c_key)

    return matches


def _property_nodes(schema: dict[str, Any], prefix: str = "") -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    schema_type = _normalize_type(schema)

    if schema_type == "object" and isinstance(schema.get("properties"), dict):
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        for prop, prop_schema_any in properties.items():
            if not isinstance(prop_schema_any, dict):
                continue
            path = f"{prefix}properties.{prop}" if prefix else f"properties.{prop}"
            nodes[path] = {
                "required": prop in required,
                "schema": prop_schema_any,
                "type": _normalize_type(prop_schema_any),
            }
            nodes.update(_property_nodes(prop_schema_any, prefix=path + "."))

    if schema_type == "array" and isinstance(schema.get("items"), dict):
        items = schema["items"]
        path = f"{prefix}items" if prefix else "items"
        nodes[path] = {
            "required": True,
            "schema": items,
            "type": _normalize_type(items),
        }
        nodes.update(_property_nodes(items, prefix=path + "."))

    return nodes


def _normalize_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return f"ref:{schema['$ref']}"
    type_value = schema.get("type")
    if isinstance(type_value, list):
        return "|".join(sorted(str(item) for item in type_value))
    if isinstance(type_value, str):
        return type_value
    if "enum" in schema:
        return "enum"
    if "oneOf" in schema:
        return "oneOf"
    if "anyOf" in schema:
        return "anyOf"
    if "allOf" in schema:
        return "allOf"
    return "unknown"


def _constraint_payload(schema: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "pattern",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "format",
        "const",
        "default",
        "additionalProperties",
    )
    return {key: schema[key] for key in keys if key in schema}


def _is_tightened_constraint(key: str, old: Any, new: Any) -> bool | None:
    higher_is_tighter = {
        "minLength",
        "minimum",
        "exclusiveMinimum",
        "minItems",
        "minProperties",
    }
    lower_is_tighter = {
        "maxLength",
        "maximum",
        "exclusiveMaximum",
        "maxItems",
        "maxProperties",
    }

    if key in higher_is_tighter and isinstance(old, (int, float)) and isinstance(new, (int, float)):
        return new > old
    if key in lower_is_tighter and isinstance(old, (int, float)) and isinstance(new, (int, float)):
        return new < old
    if key == "uniqueItems" and isinstance(old, bool) and isinstance(new, bool):
        return old is False and new is True
    if key == "additionalProperties":
        if old is True and new is False:
            return True
        if old is False and new is True:
            return False
    if key in {"pattern", "format", "multipleOf", "const"} and old != new:
        return True
    return None


def _additional_properties_disallow_unknown(schema: dict[str, Any]) -> bool:
    value = schema.get("additionalProperties", True)
    return value is False


def _property_addition_breaking(
    *,
    required: bool,
    compat_mode: str,
    baseline_schema: dict[str, Any],
) -> bool:
    if required:
        return True
    if compat_mode == "strict":
        return True
    return _additional_properties_disallow_unknown(baseline_schema)


def _metadata_only_changed(old: ModelSnapshot, new: ModelSnapshot) -> bool:
    if old.sha256_semantic and new.sha256_semantic:
        if old.sha256_semantic == new.sha256_semantic and old.sha256_full != new.sha256_full:
            return True
    return False


def _diff_model(old: ModelSnapshot, new: ModelSnapshot) -> list[SchemaChange]:
    changes: list[SchemaChange] = []

    if _metadata_only_changed(old, new):
        changes.append(
            SchemaChange(
                model=new.abi_key,
                module=new.module,
                path="$",
                kind=ChangeKind.METADATA_CHANGED,
                breaking=False,
                priority=new.priority,
                message="Schema metadata changed (title/description/etc)",
            )
        )
        return changes

    old_nodes = _property_nodes(old.schema)
    new_nodes = _property_nodes(new.schema)

    removed_paths = sorted(set(old_nodes) - set(new_nodes))
    added_paths = sorted(set(new_nodes) - set(old_nodes))
    common_paths = sorted(set(old_nodes) & set(new_nodes))

    for path in removed_paths:
        changes.append(
            SchemaChange(
                model=new.abi_key,
                module=new.module,
                path=path,
                kind=ChangeKind.PROPERTY_REMOVED,
                breaking=True,
                priority=new.priority,
                message=f"Property removed: {path}",
                old_value=old_nodes[path]["schema"],
            )
        )

    for path in added_paths:
        node = new_nodes[path]
        breaking = _property_addition_breaking(
            required=bool(node["required"]),
            compat_mode=new.compat_mode,
            baseline_schema=old.schema,
        )
        required_tag = "required" if node["required"] else "optional"
        mode_tag = "strict" if new.compat_mode == "strict" else "tolerant"
        changes.append(
            SchemaChange(
                model=new.abi_key,
                module=new.module,
                path=path,
                kind=ChangeKind.PROPERTY_ADDED,
                breaking=breaking,
                priority=new.priority,
                message=f"Property added ({required_tag}, compat_mode={mode_tag})",
                new_value=node["schema"],
            )
        )

    for path in common_paths:
        old_node = old_nodes[path]
        new_node = new_nodes[path]

        if old_node["required"] != new_node["required"]:
            became_required = (not old_node["required"]) and bool(new_node["required"])
            changes.append(
                SchemaChange(
                    model=new.abi_key,
                    module=new.module,
                    path=path,
                    kind=(
                        ChangeKind.PROPERTY_REQUIRED_ADDED
                        if became_required
                        else ChangeKind.PROPERTY_REQUIRED_REMOVED
                    ),
                    breaking=became_required,
                    priority=new.priority,
                    message=(
                        "Property became required"
                        if became_required
                        else "Property became optional"
                    ),
                )
            )

        old_type = old_node["type"]
        new_type = new_node["type"]
        if old_type != new_type:
            changes.append(
                SchemaChange(
                    model=new.abi_key,
                    module=new.module,
                    path=path,
                    kind=ChangeKind.PROPERTY_TYPE_CHANGED,
                    breaking=True,
                    priority=new.priority,
                    message=f"Property type changed: {old_type} -> {new_type}",
                    old_value=old_type,
                    new_value=new_type,
                )
            )

        old_schema = old_node["schema"]
        new_schema = new_node["schema"]

        old_ref = old_schema.get("$ref")
        new_ref = new_schema.get("$ref")
        if old_ref != new_ref:
            changes.append(
                SchemaChange(
                    model=new.abi_key,
                    module=new.module,
                    path=path + ".$ref",
                    kind=ChangeKind.REF_CHANGED,
                    breaking=True,
                    priority=new.priority,
                    message=f"$ref changed: {old_ref} -> {new_ref}",
                    old_value=old_ref,
                    new_value=new_ref,
                )
            )

        old_constraints = _constraint_payload(old_schema)
        new_constraints = _constraint_payload(new_schema)
        for key in sorted(set(old_constraints) | set(new_constraints)):
            if old_constraints.get(key) == new_constraints.get(key):
                continue
            old_value = old_constraints.get(key)
            new_value = new_constraints.get(key)
            tightened = _is_tightened_constraint(key, old_value, new_value)
            breaking = True if tightened is None else tightened
            message = f"Constraint changed for {key}: {old_value} -> {new_value}"
            changes.append(
                SchemaChange(
                    model=new.abi_key,
                    module=new.module,
                    path=f"{path}.{key}",
                    kind=ChangeKind.CONSTRAINT_CHANGED,
                    breaking=breaking,
                    priority=new.priority,
                    message=message,
                    old_value=old_value,
                    new_value=new_value,
                )
            )

        old_enum = set(old_schema.get("enum", []))
        new_enum = set(new_schema.get("enum", []))
        for value in sorted(old_enum - new_enum):
            changes.append(
                SchemaChange(
                    model=new.abi_key,
                    module=new.module,
                    path=f"{path}.enum",
                    kind=ChangeKind.ENUM_VALUE_REMOVED,
                    breaking=True,
                    priority=new.priority,
                    message=f"Enum value removed: {value}",
                    old_value=value,
                )
            )
        for value in sorted(new_enum - old_enum):
            changes.append(
                SchemaChange(
                    model=new.abi_key,
                    module=new.module,
                    path=f"{path}.enum",
                    kind=ChangeKind.ENUM_VALUE_ADDED,
                    breaking=False,
                    priority=new.priority,
                    message=f"Enum value added: {value}",
                    new_value=value,
                )
            )

    # Root-level enum models.
    old_root_enum = set(old.schema.get("enum", []))
    new_root_enum = set(new.schema.get("enum", []))
    for value in sorted(old_root_enum - new_root_enum):
        changes.append(
            SchemaChange(
                model=new.abi_key,
                module=new.module,
                path="enum",
                kind=ChangeKind.ENUM_VALUE_REMOVED,
                breaking=True,
                priority=new.priority,
                message=f"Enum value removed: {value}",
                old_value=value,
            )
        )
    for value in sorted(new_root_enum - old_root_enum):
        changes.append(
            SchemaChange(
                model=new.abi_key,
                module=new.module,
                path="enum",
                kind=ChangeKind.ENUM_VALUE_ADDED,
                breaking=False,
                priority=new.priority,
                message=f"Enum value added: {value}",
                new_value=value,
            )
        )

    if not changes and old.sha256_full != new.sha256_full:
        changes.append(
            SchemaChange(
                model=new.abi_key,
                module=new.module,
                path="$",
                kind=ChangeKind.METADATA_CHANGED,
                breaking=False,
                priority=new.priority,
                message="Non-semantic schema metadata changed",
            )
        )

    return changes


def _parse_version(version: str) -> tuple[int, int]:
    parts = version.split(".")
    if len(parts) != 2:
        raise ValueError(f"version must be MAJOR.MINOR, got: {version}")
    major = int(parts[0])
    minor = int(parts[1])
    return major, minor


def _verify_version_bumps(
    report: DiffReport,
    baseline: dict[str, ModelSnapshot],
    current: dict[str, ModelSnapshot],
) -> None:
    breaking_by_model: dict[str, list[SchemaChange]] = {}
    for change in report.changes:
        if change.breaking:
            key = f"{change.module}:{change.model}"
            breaking_by_model.setdefault(key, []).append(change)

    for model_key, model_changes in sorted(breaking_by_model.items()):
        priority = model_changes[0].priority
        baseline_model = baseline.get(model_key)
        current_model = current.get(model_key)

        old_version = baseline_model.schema_version if baseline_model else None
        new_version = current_model.schema_version if current_model else None
        report.baseline_versions[model_key] = old_version
        report.current_versions[model_key] = new_version

        if priority != "p0":
            report.warnings.append(
                f"{model_key}: breaking changes detected on priority {priority} (non-blocking)"
            )
            continue

        if current_model is None:
            report.version_errors.append(
                f"{model_key}: model removed with breaking changes (no replacement version)"
            )
            continue

        if current_model.version_field is None:
            report.warnings.append(
                f"{model_key}: version check skipped (version_field is None)"
            )
            continue

        if old_version is None or new_version is None:
            report.version_errors.append(
                f"{model_key}: breaking change requires major version bump, "
                "but schema_version is missing"
            )
            continue

        try:
            old_major, _ = _parse_version(old_version)
            new_major, _ = _parse_version(new_version)
        except ValueError as exc:
            report.version_errors.append(f"{model_key}: invalid schema_version format ({exc})")
            continue

        if new_major <= old_major:
            report.version_errors.append(
                f"{model_key}: breaking changes detected but major version not bumped "
                f"({old_version} -> {new_version})"
            )


def _report_to_dict(report: DiffReport) -> dict[str, Any]:
    payload_changes = [
        {
            "model": change.model,
            "module": change.module,
            "path": change.path,
            "kind": change.kind.value,
            "breaking": change.breaking,
            "priority": change.priority,
            "message": change.message,
            "old_value": change.old_value,
            "new_value": change.new_value,
        }
        for change in report.changes
    ]
    return {
        "verdict": report.verdict,
        "summary": {
            "total_changes": len(report.changes),
            "breaking_changes": report.breaking_count,
            "compatible_changes": report.compatible_count,
            "version_errors": len(report.version_errors),
            "warnings": len(report.warnings),
        },
        "version_errors": report.version_errors,
        "warnings": report.warnings,
        "baseline_versions": report.baseline_versions,
        "current_versions": report.current_versions,
        "changes": payload_changes,
    }


def _format_markdown(report: DiffReport, github: bool = False) -> str:
    if not report.changes and not report.version_errors:
        return "### ✅ ABI Schema Diff Report\n\nNo schema changes detected."

    icon = "✅"
    if report.verdict == "WARN":
        icon = "⚠️"
    if report.verdict == "FAIL":
        icon = "🚨"

    lines = [f"### {icon} ABI Schema Diff Report", ""]
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Verdict | **{report.verdict}** |")
    lines.append(f"| Total changes | {len(report.changes)} |")
    lines.append(f"| Breaking changes | **{report.breaking_count}** |")
    lines.append(f"| Compatible changes | {report.compatible_count} |")
    lines.append(f"| Version errors | {len(report.version_errors)} |")
    lines.append("")

    if report.version_errors:
        lines.append("#### Blocking Version Errors")
        for item in report.version_errors:
            lines.append(f"- {item}")
        lines.append("")

    if report.warnings:
        lines.append("#### Warnings")
        for item in report.warnings:
            lines.append(f"- {item}")
        lines.append("")

    breaking_changes = [change for change in report.changes if change.breaking]
    compatible_changes = [change for change in report.changes if not change.breaking]

    if breaking_changes:
        if github:
            lines.append("<details><summary>🔴 Breaking Changes</summary>")
            lines.append("")
        else:
            lines.append("#### Breaking Changes")
        for change in breaking_changes:
            lines.append(
                f"- **{change.module}:{change.model}** `{change.path}` "
                f"({change.kind.value}): {change.message}"
            )
        if github:
            lines.extend(["", "</details>"])
        lines.append("")

    if compatible_changes:
        if github:
            lines.append("<details><summary>🟢 Compatible Changes</summary>")
            lines.append("")
        else:
            lines.append("#### Compatible Changes")
        for change in compatible_changes:
            lines.append(
                f"- **{change.module}:{change.model}** `{change.path}` "
                f"({change.kind.value}): {change.message}"
            )
        if github:
            lines.extend(["", "</details>"])
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _build_diff_report(
    baseline: dict[str, ModelSnapshot],
    current: dict[str, ModelSnapshot],
) -> DiffReport:
    report = DiffReport()

    baseline_only = {key: baseline[key] for key in sorted(set(baseline) - set(current))}
    current_only = {key: current[key] for key in sorted(set(current) - set(baseline))}

    rename_matches = _match_renamed_models(
        baseline_only=baseline_only,
        current_only=current_only,
    )

    renamed_baseline_keys: set[str] = set()
    renamed_current_keys: set[str] = set()
    for old_model, new_model, reason in rename_matches:
        renamed_baseline_keys.add(f"{old_model.module}:{old_model.abi_key}")
        renamed_current_keys.add(f"{new_model.module}:{new_model.abi_key}")
        report.changes.append(
            SchemaChange(
                model=new_model.abi_key,
                module=new_model.module,
                path="$",
                kind=ChangeKind.MODEL_RENAMED,
                breaking=True,
                priority=new_model.priority,
                message=(
                    f"Model renamed from {old_model.abi_key} to {new_model.abi_key} "
                    f"(match={reason})"
                ),
            )
        )
        report.changes.extend(_diff_model(old_model, new_model))

    for key, model in baseline_only.items():
        full_key = f"{model.module}:{model.abi_key}"
        if full_key in renamed_baseline_keys:
            continue
        report.changes.append(
            SchemaChange(
                model=model.abi_key,
                module=model.module,
                path="$",
                kind=ChangeKind.MODEL_REMOVED,
                breaking=True,
                priority=model.priority,
                message="Model removed from ABI registry/snapshots",
            )
        )

    for key, model in current_only.items():
        full_key = f"{model.module}:{model.abi_key}"
        if full_key in renamed_current_keys:
            continue
        report.changes.append(
            SchemaChange(
                model=model.abi_key,
                module=model.module,
                path="$",
                kind=ChangeKind.MODEL_ADDED,
                breaking=False,
                priority=model.priority,
                message="Model added to ABI registry/snapshots",
            )
        )

    for key in sorted(set(baseline) & set(current)):
        report.changes.extend(_diff_model(baseline[key], current[key]))

    _verify_version_bumps(report, baseline, current)
    return report


def main() -> int:
    args = _parse_args()

    baseline = _load_snapshots(args.baseline)
    current = _load_snapshots(args.current)
    report = _build_diff_report(baseline, current)

    payload = _report_to_dict(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.format == "markdown":
        print(_format_markdown(report, github=False), end="")
    elif args.format == "github":
        print(_format_markdown(report, github=True), end="")

    if args.github_comment:
        args.github_comment.parent.mkdir(parents=True, exist_ok=True)
        args.github_comment.write_text(_format_markdown(report, github=True), "utf-8")

    return 1 if report.verdict == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
