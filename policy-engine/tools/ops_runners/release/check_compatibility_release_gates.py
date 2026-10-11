"""Report Phase 5.10 compatibility release-gate readiness."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tomllib
import types
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from tools.lib.fs import measure_file_reads, measured_read_bytes
from tools.lib.imports import repo_root_from
from tools.ops_runners.release.build_release_notes import (
    SECTION_TITLES,
    load_fragments,
    structured_compatibility_changes,
)

REPO_ROOT = repo_root_from(__file__)
DEFAULT_POLICY = REPO_ROOT / "architecture" / "gates" / "compatibility_release.toml"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    subject: str
    message: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "severity": self.severity,
            "subject": self.subject,
            "message": self.message,
            "detail": self.detail,
        }


def build_report(
    *,
    repo_root: Path = REPO_ROOT,
    policy_path: Path = DEFAULT_POLICY,
    fragments_dir: Path | None = None,
    breaking_classes: tuple[str, ...] = (),
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    policy_path = _resolve(repo_root, policy_path)
    policy = _read_toml(policy_path)
    header = policy["compatibility_release_gates"]
    fragments_dir = _resolve(
        repo_root,
        fragments_dir
        or repo_root
        / str(header.get("release_fragment_unreleased_root", "release-fragments/unreleased")),
    )

    contract_errors: list[Finding] = []
    findings: list[Finding] = []

    contract_errors.extend(_validate_policy(repo_root, policy_path, policy))
    public_surface_errors, public_surface_evidence = _validate_public_surface(repo_root, header)
    contract_errors.extend(public_surface_errors)
    contract_errors.extend(_validate_extension_points(repo_root, header))
    contract_errors.extend(_validate_generated_artifacts(repo_root, policy, header))
    contract_errors.extend(_validate_runtime_state(repo_root, header))
    contract_errors.extend(_validate_migrations(repo_root, header))
    contract_errors.extend(_validate_schema_manifests(repo_root, header))
    contract_errors.extend(_validate_release_template(repo_root, policy, header))

    fragments = load_fragments(fragments_dir) if fragments_dir.exists() else []
    fragment_errors, fragment_findings = _validate_fragments(
        repo_root,
        policy,
        fragments,
        breaking_classes=breaking_classes,
    )
    contract_errors.extend(fragment_errors)
    findings.extend(fragment_findings)

    changes = structured_compatibility_changes(fragments)
    return {
        "phase": "repository-best-in-class-phase-5.10",
        "mode": "report_only",
        "status": "contract_errors" if contract_errors else "reported",
        "policy": _relative(policy_path, repo_root),
        "fragments_dir": _relative(fragments_dir, repo_root),
        "fragment_count": len(fragments),
        "structured_compatibility_change_count": len(changes),
        "breaking_classes_checked": list(breaking_classes),
        "contract_error_count": len(contract_errors),
        "finding_count": len(findings),
        "contract_errors": [finding.as_dict() for finding in contract_errors],
        "public_surface_inventory_evidence": public_surface_evidence,
        "findings": [finding.as_dict() for finding in findings],
        "summary": {
            "compatibility_surfaces": len(policy.get("compatibility_surface", [])),
            "promotion_checks": len(policy.get("promotion_check", [])),
            "generated_families": len(policy.get("generated_family", [])),
        },
    }


def _validate_policy(repo_root: Path, policy_path: Path, policy: dict[str, Any]) -> list[Finding]:
    errors: list[Finding] = []
    subject = _relative(policy_path, repo_root)
    header = policy.get("compatibility_release_gates", {})
    for field in (
        "status",
        "owner",
        "mode",
        "release_fragment_policy",
        "release_fragment_template",
        "public_surface_contract",
        "generated_artifact_contract",
        "extension_point_contract",
        "runtime_state_contract",
        "migration_contract",
        "gate_command",
    ):
        if not str(header.get(field, "")).strip():
            errors.append(Finding("policy", "error", subject, f"missing `{field}`"))
    if header.get("status") != "report_only" or header.get("mode") != "report_only":
        errors.append(Finding("policy", "error", subject, "Phase 5.10 gate must stay report_only"))

    for path_field in (
        "release_fragment_policy",
        "release_fragment_template",
        "public_surface_contract",
        "public_surface_inventory",
        "generated_artifact_contract",
        "extension_point_contract",
        "runtime_state_contract",
        "migration_contract",
    ):
        raw_path = str(header.get(path_field, ""))
        if raw_path and not _path_or_glob_exists(repo_root, raw_path):
            errors.append(
                Finding(
                    "policy-paths", "error", subject, f"`{path_field}` path is missing", raw_path
                )
            )

    allowed = set(header.get("allowed_change_classes", []))
    if "internal" not in allowed:
        errors.append(
            Finding("policy", "error", subject, "allowed_change_classes must include internal")
        )

    for check in policy.get("promotion_check", []):
        check_id = str(check.get("id", ""))
        for field in ("owner", "mode", "description", "source_contracts"):
            if not check.get(field):
                errors.append(Finding("promotion-check", "error", check_id, f"missing `{field}`"))
        if check.get("mode") != "report_only":
            errors.append(Finding("promotion-check", "error", check_id, "mode must be report_only"))
        for raw_path in check.get("source_contracts", []):
            if not _path_or_glob_exists(repo_root, str(raw_path)):
                errors.append(
                    Finding(
                        "promotion-check",
                        "error",
                        check_id,
                        "source contract path is missing",
                        str(raw_path),
                    )
                )
    return errors


def _placeholder_for_schema(annotation: object) -> object:
    """Build a typed placeholder consumed only by the canonical JSON renderer."""
    from typing import Any as TypingAny

    if annotation is TypingAny:
        return {}
    if annotation is Path:
        return Path("schema-placeholder")
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (tuple, list):
        item_type = arguments[0] if arguments else TypingAny
        if dataclasses.is_dataclass(item_type):
            return (_placeholder_for_schema(item_type),)
        return ()
    if origin is dict:
        return {}
    if origin in (types.UnionType, Union):
        if type(None) in arguments:
            return None
        return _placeholder_for_schema(arguments[0])
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        hints = get_type_hints(annotation)
        return annotation(
            **{
                field.name: _placeholder_for_schema(hints[field.name])
                for field in dataclasses.fields(annotation)
            }
        )
    if annotation is str:
        return ""
    if annotation is bool:
        return False
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if annotation is type(None):
        return None
    raise TypeError(f"unsupported canonical schema annotation: {annotation!r}")


def _matches_declared_value(value: object, annotation: object) -> bool:
    """Check represented values against a canonical dataclass annotation."""
    from typing import Any as TypingAny

    if annotation is TypingAny:
        return True
    if dataclasses.is_dataclass(annotation):
        return _matches_model_json(value, annotation)
    if annotation is Path:
        return isinstance(value, str)
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (types.UnionType, Union):
        return any(
            _matches_declared_value(value, option)
            for option in arguments
        )
    if origin in (tuple, list):
        if not isinstance(value, list):
            return False
        item_type = arguments[0] if arguments else TypingAny
        return all(
            _matches_declared_value(item, item_type)
            for item in value
        )
    if origin is dict:
        if not isinstance(value, dict):
            return False
        key_type, value_type = arguments if len(arguments) == 2 else (TypingAny, TypingAny)
        return all(
            _matches_declared_value(key, key_type)
            and _matches_declared_value(item, value_type)
            for key, item in value.items()
        )
    if annotation is bool:
        return type(value) is bool
    if annotation is int:
        return type(value) is int
    if annotation is float:
        return type(value) is float
    if annotation is str:
        return type(value) is str
    if annotation is type(None):
        return value is None
    return isinstance(annotation, type) and isinstance(value, annotation)


def _matches_model_json(value: object, model: type[object], *, aliases: dict[str, str] | None = None) -> bool:
    """Validate serialized fields against the actual canonical dataclass schema."""
    if not isinstance(value, dict) or not dataclasses.is_dataclass(model):
        return False
    aliases = aliases or {}
    hints = get_type_hints(model)
    wire_names = {
        aliases.get(field.name, field.name): field.name
        for field in dataclasses.fields(model)
    }
    if set(value) != set(wire_names):
        return False
    return all(
        _matches_declared_value(value[wire_name], hints[attribute])
        for wire_name, attribute in wire_names.items()
    )


def _canonical_public_surface_context() -> tuple[object, dict[str, str], dict[str, Any]]:
    """Bind the release check to the canonical declaration model and JSON producer."""
    from tools.devx.architecture import guardrails

    policy_model = guardrails.PackagePolicy
    inventory_model = guardrails.PackageInventory
    inventory_fields = {field.name for field in fields(inventory_model)}
    field_map: dict[str, str] = {}
    for field in fields(policy_model):
        inventory_field = (
            "facade_mode_expected" if field.name == "facade_mode" else field.name
        )
        if inventory_field not in inventory_fields:
            raise TypeError(
                f"canonical package field has no inventory projection: {field.name}"
            )
        field_map[field.name] = inventory_field

    policy_hints = get_type_hints(policy_model)
    for field_name in field_map:
        if field_name not in policy_hints:
            raise TypeError(f"canonical package field has no resolved type: {field_name}")

    package_placeholder = _placeholder_for_schema(inventory_model)
    family_placeholder = _placeholder_for_schema(guardrails.PublicGeneratedArtifactFamily)
    payload_schema = json.loads(
        guardrails.render_public_surface_json(
            [package_placeholder],
            generated_artifact_families=[family_placeholder],
        )
    )
    return guardrails, field_map, payload_schema


def _validate_public_surface(
    repo_root: Path, header: dict[str, Any]
) -> tuple[list[Finding], dict[str, Any]]:
    """Reconcile declarations with the canonical package and inventory models."""
    contract_rel = str(header.get("public_surface_contract", "")).strip()
    contract_path = _resolve(repo_root, contract_rel) if contract_rel else repo_root
    errors: list[Finding] = []
    quality = {"complete": True, "uncertain": False}
    contract: dict[str, Any] | None = None
    inventory: dict[str, Any] | None = None
    contract_bytes: bytes | None = None
    surface: dict[str, Any] = {}
    inventory_path: Path | None = None
    public_surface_source: object | None = None
    field_map: dict[str, str] = {}
    payload_schema: dict[str, Any] = {}
    canonical_policies: list[object] = []
    canonical_families: list[object] = []

    def add_error(subject: str, message: str, detail: str = "") -> None:
        errors.append(Finding("public-surface", "error", subject, message, detail))

    def mark_unestablished(subject: str, message: str, detail: str = "") -> None:
        quality["complete"] = False
        quality["uncertain"] = True
        add_error(subject, message, detail)

    try:
        public_surface_source, field_map, payload_schema = _canonical_public_surface_context()
    except (ImportError, AttributeError, TypeError, ValueError) as error:
        mark_unestablished(
            "tools/devx/architecture/guardrails.py",
            "canonical public-surface model or renderer is unavailable",
            type(error).__name__,
        )

    with measure_file_reads(repo_root) as reads:
        if public_surface_source is not None:
            source_path = Path(public_surface_source.__file__)
            try:
                measured_read_bytes(source_path)
            except OSError as error:
                mark_unestablished(
                    str(source_path), "canonical public-surface source is unreadable", type(error).__name__
                )

        if not contract_rel:
            mark_unestablished(".", "public-surface contract path is missing")
        else:
            try:
                contract_bytes = measured_read_bytes(contract_path)
                contract_value = tomllib.loads(contract_bytes.decode("utf-8"))
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
                mark_unestablished(
                    _relative(contract_path, repo_root),
                    "public-surface contract is unreadable or malformed",
                    type(error).__name__,
                )
            else:
                if not isinstance(contract_value, dict):
                    mark_unestablished(
                        _relative(contract_path, repo_root),
                        "public-surface contract root must be a table",
                    )
                else:
                    contract = contract_value

        if contract is not None:
            raw_surface = contract.get("public_surface")
            if not isinstance(raw_surface, dict):
                mark_unestablished(
                    _relative(contract_path, repo_root),
                    "public_surface must be a table",
                )
            else:
                surface = raw_surface

            for field in (
                "version_owner",
                "deprecation_window",
                "release_fragment_change_class",
                "inventory",
                "inventory_regenerate_command",
                "inventory_review_owner",
                "inventory_review_policy",
            ):
                if not str(surface.get(field, "")).strip():
                    add_error(
                        _relative(contract_path, repo_root),
                        f"missing field: {field}",
                    )

            raw_packages = contract.get("package", [])
            if isinstance(raw_packages, list):
                for package in raw_packages:
                    if not isinstance(package, dict):
                        continue
                    version_owner = (
                        package.get("version_owner")
                        or surface.get("version_owner")
                        or package.get("owner")
                    )
                    deprecation_window = (
                        package.get("deprecation_window") or surface.get("deprecation_window")
                    )
                    module = str(package.get("module", ""))
                    if not str(version_owner or "").strip():
                        add_error(module, "missing version owner")
                    if not str(deprecation_window or "").strip():
                        add_error(module, "missing deprecation window")

            declared_inventory = str(surface.get("inventory", "")).strip()
            header_inventory = str(header.get("public_surface_inventory", "")).strip()
            inventory_rel = declared_inventory or header_inventory
            if not inventory_rel:
                mark_unestablished(
                    _relative(contract_path, repo_root),
                    "public-surface inventory path is missing",
                )
            else:
                inventory_path = _resolve(repo_root, inventory_rel)
                if declared_inventory and header_inventory:
                    policy_inventory_path = _resolve(repo_root, header_inventory)
                    if policy_inventory_path != inventory_path:
                        add_error(
                            _relative(contract_path, repo_root),
                            "release policy and public-surface contract name different inventories",
                            (
                                f"contract={_relative(inventory_path, repo_root)}; "
                                f"policy={_relative(policy_inventory_path, repo_root)}"
                            ),
                        )

        inventory_bytes: bytes | None = None
        if inventory_path is not None:
            try:
                inventory_bytes = measured_read_bytes(inventory_path)
                inventory_value = json.loads(inventory_bytes.decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                mark_unestablished(
                    _relative(inventory_path, repo_root),
                    "public-surface inventory is unreadable or malformed",
                    type(error).__name__,
                )
            else:
                if not isinstance(inventory_value, dict):
                    mark_unestablished(
                        _relative(inventory_path, repo_root),
                        "public-surface inventory root must be an object",
                    )
                else:
                    inventory = inventory_value

        if (
            contract_bytes is not None
            and public_surface_source is not None
            and isinstance(contract, dict)
        ):
            import tempfile

            with tempfile.TemporaryDirectory(prefix="e02-public-surface-contract-") as directory:
                declaration_path = Path(directory) / "contract.toml"
                declaration_path.write_bytes(contract_bytes)
                try:
                    canonical_policies = public_surface_source._parse_public_surface(
                        declaration_path
                    )
                    canonical_families = (
                        public_surface_source._parse_public_generated_artifact_families(
                            declaration_path
                        )
                    )
                except (KeyError, TypeError, ValueError, OSError, tomllib.TOMLDecodeError) as error:
                    mark_unestablished(
                        _relative(contract_path, repo_root),
                        "canonical declaration parser could not establish package/family models",
                        type(error).__name__,
                    )

    contract = contract or {}
    inventory = inventory or {}
    contract_subject = _relative(contract_path, repo_root)
    inventory_subject = (
        _relative(inventory_path, repo_root) if inventory_path is not None else contract_subject
    )

    def rows_for(
        source: dict[str, Any],
        key: str,
        subject: str,
        label: str,
    ) -> tuple[object, list[dict[str, Any]]]:
        raw_rows = source.get(key)
        if not isinstance(raw_rows, list):
            mark_unestablished(subject, f"{label} rows must be a list")
            return raw_rows, []
        rows: list[dict[str, Any]] = []
        malformed_count = 0
        for row in raw_rows:
            if isinstance(row, dict):
                rows.append(row)
            else:
                malformed_count += 1
        if malformed_count:
            mark_unestablished(
                subject,
                f"{label} rows contain malformed entries",
                str(malformed_count),
            )
        return raw_rows, rows

    _, contract_packages = rows_for(contract, "package", contract_subject, "contract package")
    _, inventory_packages = rows_for(inventory, "packages", inventory_subject, "inventory package")
    _, contract_families = rows_for(
        contract, "generated_artifact_family", contract_subject, "contract generated-artifact family"
    )
    _, inventory_families = rows_for(
        inventory,
        "generated_artifact_families",
        inventory_subject,
        "inventory generated-artifact family",
    )

    from dataclasses import fields
    from typing import get_type_hints

    if public_surface_source is not None:
        policy_fields = fields(public_surface_source.PackagePolicy)
        policy_hints = get_type_hints(public_surface_source.PackagePolicy)
        family_hints = get_type_hints(public_surface_source.PublicGeneratedArtifactFamily)
        for row in contract_packages:
            for field in policy_fields:
                if field.name in row and not _matches_declared_value(
                    row[field.name], policy_hints[field.name]
                ):
                    mark_unestablished(
                        str(row.get("module", contract_subject)),
                        "contract package field has a value outside the canonical declaration type",
                        field.name,
                    )
        for row in contract_families:
            for field_name, annotation in family_hints.items():
                raw_name = "id" if field_name == "family_id" else field_name
                if raw_name in row and not _matches_declared_value(
                    row[raw_name], annotation
                ):
                    mark_unestablished(
                        str(row.get("id", contract_subject)),
                        "contract generated-artifact field has a value outside the canonical declaration type",
                        raw_name,
                    )

    def index_rows(
        rows: list[dict[str, Any]],
        key: str,
        subject: str,
        label: str,
    ) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        duplicates: set[str] = set()
        for row in rows:
            identity = row.get(key)
            if not isinstance(identity, str) or not identity:
                mark_unestablished(subject, f"{label} row has no valid {key}")
                continue
            if identity in indexed:
                duplicates.add(identity)
            indexed[identity] = row
        if duplicates:
            mark_unestablished(
                subject,
                f"duplicate {label} identities",
                ", ".join(sorted(duplicates)),
            )
        return indexed

    contract_package_by_module = index_rows(
        contract_packages, "module", contract_subject, "contract package"
    )
    inventory_package_by_module = index_rows(
        inventory_packages, "module", inventory_subject, "inventory package"
    )
    missing_modules = sorted(set(contract_package_by_module) - set(inventory_package_by_module))
    extra_modules = sorted(set(inventory_package_by_module) - set(contract_package_by_module))
    if missing_modules:
        add_error(
            inventory_subject,
            "inventory missing package rows",
            ", ".join(missing_modules),
        )
    if extra_modules:
        add_error(
            inventory_subject,
            "inventory has package rows outside the contract",
            ", ".join(extra_modules),
        )

    policy_by_module = {
        str(policy.module): policy
        for policy in canonical_policies
        if getattr(policy, "module", None)
    }
    if len(canonical_policies) != len(contract_packages):
        mark_unestablished(
            contract_subject,
            "canonical package parser did not produce one model per contract row",
            f"contract={len(contract_packages)}; parsed={len(canonical_policies)}",
        )

    package_schema = payload_schema.get("packages", [{}])[0]
    entrypoint_schema = package_schema.get("entrypoints", [{}])[0]
    family_schema = payload_schema.get("generated_artifact_families", [{}])[0]
    expected_top_fields = set(payload_schema)
    if set(inventory) != expected_top_fields:
        mark_unestablished(
            inventory_subject,
            "inventory root does not match the canonical renderer schema",
            f"missing={sorted(expected_top_fields - set(inventory))!r}; "
            f"extra={sorted(set(inventory) - expected_top_fields)!r}",
        )
    expected_version = payload_schema.get("version")
    if expected_version is None:
        mark_unestablished(
            "tools/devx/architecture/guardrails.py",
            "canonical renderer did not establish the inventory version schema",
        )
    elif type(inventory.get("version")) is not int or inventory.get("version") != expected_version:
        add_error(inventory_subject, "inventory version differs from canonical renderer")
    if type(inventory.get("internal_rule")) is not str:
        mark_unestablished(inventory_subject, "inventory internal_rule must be a string")
    elif inventory.get("internal_rule") != payload_schema["internal_rule"]:
        add_error(inventory_subject, "inventory internal rule differs from canonical renderer")

    for module, inventory_package in inventory_package_by_module.items():
        inventory_package_schema_valid = (
            public_surface_source is not None
            and _matches_model_json(inventory_package, public_surface_source.PackageInventory)
        )
        if not inventory_package_schema_valid:
            mark_unestablished(
                module,
                "inventory package row does not match the canonical inventory schema",
                f"missing={sorted(set(package_schema) - set(inventory_package))!r}; "
                f"extra={sorted(set(inventory_package) - set(package_schema))!r}",
            )
        parsed = policy_by_module.get(module)
        if parsed is None or public_surface_source is None:
            continue
        for contract_field, inventory_field in field_map.items():
            value = getattr(parsed, contract_field)
            try:
                if isinstance(value, Path):
                    expected_value = str(value.relative_to(public_surface_source.REPO_ROOT))
                elif isinstance(value, tuple):
                    expected_value = list(value)
                else:
                    expected_value = value
            except ValueError:
                mark_unestablished(
                    module,
                    "canonical package path is outside the repository-relative inventory root",
                    contract_field,
                )
                continue
            if inventory_package.get(inventory_field) != expected_value:
                add_error(
                    module,
                    f"{inventory_field} drift",
                    (
                        f"contract={expected_value!r}; "
                        f"inventory={inventory_package.get(inventory_field)!r}"
                    ),
                )

        contract_entries = list(parsed.supported_entrypoints)
        inventory_entries = inventory_package.get("supported_entrypoints")
        raw_entrypoint_rows = inventory_package.get("entrypoints")
        entrypoint_modules: list[str] = []
        if isinstance(raw_entrypoint_rows, list):
            for row in raw_entrypoint_rows:
                if isinstance(row, dict) and isinstance(row.get("module"), str):
                    entrypoint_modules.append(row["module"])
        if len(contract_entries) != len(set(contract_entries)):
            mark_unestablished(module, "contract supported_entrypoints contains duplicates")
        if (
            contract_entries != inventory_entries
            or contract_entries != entrypoint_modules
        ):
            add_error(
                module,
                "supported entrypoint inventory differs from contract",
                (
                    f"contract={contract_entries!r}; inventory={inventory_entries!r}; "
                    f"entrypoint_rows={entrypoint_modules!r}"
                ),
            )

    for row in inventory_families:
        if public_surface_source is not None and not _matches_model_json(
            row,
            public_surface_source.PublicGeneratedArtifactFamily,
            aliases={"family_id": "id"},
        ):
            mark_unestablished(
                inventory_subject,
                "generated-artifact family row does not match the canonical renderer schema",
                f"missing={sorted(set(family_schema) - set(row))!r}; "
                f"extra={sorted(set(row) - set(family_schema))!r}",
            )

    contract_family_by_id = index_rows(
        contract_families, "id", contract_subject, "contract generated-artifact family"
    )
    inventory_family_by_id = index_rows(
        inventory_families, "id", inventory_subject, "inventory generated-artifact family"
    )
    canonical_family_payload: list[dict[str, Any]] = []
    if public_surface_source is not None:
        rendered_families = json.loads(
            public_surface_source.render_public_surface_json(
                [], generated_artifact_families=canonical_families
            )
        )
        canonical_family_payload = rendered_families["generated_artifact_families"]
    canonical_family_by_id = {
        str(row["id"]): row
        for row in canonical_family_payload
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    missing_families = sorted(set(canonical_family_by_id) - set(inventory_family_by_id))
    extra_families = sorted(set(inventory_family_by_id) - set(canonical_family_by_id))
    changed_families = sorted(
        family_id
        for family_id in set(canonical_family_by_id) & set(inventory_family_by_id)
        if canonical_family_by_id[family_id] != inventory_family_by_id[family_id]
    )
    if missing_families or extra_families or changed_families:
        add_error(
            inventory_subject,
            "generated-artifact family inventory differs from contract",
            (
                f"missing={missing_families!r}; extra={extra_families!r}; "
                f"changed={changed_families!r}"
            ),
        )

    package_policy_field_count = len(field_map)
    inventory_package_schema_field_count = len(package_schema)
    inventory_entrypoint_schema_field_count = len(entrypoint_schema)
    family_schema_field_count = len(family_schema)
    contract_package_field_present = sum(
        1
        for row in contract_packages
        for field_name in field_map
        if field_name in row
    )
    inventory_package_field_present = sum(
        1
        for row in inventory_packages
        for field_name in package_schema
        if field_name in row
    )
    inventory_entrypoint_rows = [
        child
        for row in inventory_packages
        if isinstance(row.get("entrypoints"), list)
        for child in row["entrypoints"]
        if isinstance(child, dict)
    ]
    inventory_entrypoint_field_present = sum(
        1
        for row in inventory_entrypoint_rows
        for field_name in entrypoint_schema
        if field_name in row
    )
    inventory_family_field_present = sum(
        1 for row in inventory_families for field_name in family_schema if field_name in row
    )
    canonical_source_path = "not_established"
    if public_surface_source is not None:
        resolved_source = Path(public_surface_source.__file__).resolve()
        canonical_source_path = (
            str(resolved_source.relative_to(repo_root.resolve()))
            if resolved_source.is_relative_to(repo_root.resolve())
            else str(resolved_source)
        )
    read_complete = bool(quality["complete"])
    snapshot = reads.snapshot(complete_verdict=read_complete)
    contract_entrypoint_count = sum(
        len(policy.supported_entrypoints)
        for policy in canonical_policies
        if isinstance(getattr(policy, "supported_entrypoints", None), tuple)
    )
    inventory_entrypoint_count = sum(
        len(row.get("supported_entrypoints", []))
        for row in inventory_packages
        if isinstance(row.get("supported_entrypoints"), list)
    )
    evidence = {
        "complete_verdict": read_complete,
        "finding_coverage": (
            "all canonical package fields, full rendered package/entrypoint/family schema fields, "
            "declared and materialized route rows, and generated-artifact-family content"
        ),
        "predicate_status": (
            "not_established"
            if quality["uncertain"]
            else "mismatch"
            if errors
            else "consistent"
        ),
        "predicate_basis": {
            "package_metadata_and_set_parity": "recomputed",
            "inventory_schema_presence_and_types": "recomputed",
            "supported_entrypoint_set_parity": "recomputed",
            "generated_artifact_family_parity": "recomputed",
            "runtime_export_resolution": "not_established_by_this_checker",
            "inventory_review_owner_identity": "not_established",
            "public_surface_inventory_reviewed_flag": "consumer_asserted",
        },
        "denominator": {
            "contract_package_rows": len(contract_packages),
            "inventory_package_rows": len(inventory_packages),
            "canonical_package_model_fields_per_row": package_policy_field_count,
            "contract_package_model_field_slots_present": contract_package_field_present,
            "contract_package_model_field_slots_expected": len(contract_packages)
            * package_policy_field_count,
            "inventory_package_schema_fields_per_row": inventory_package_schema_field_count,
            "inventory_package_schema_field_slots_present": inventory_package_field_present,
            "inventory_package_schema_field_slots_expected": len(inventory_packages)
            * inventory_package_schema_field_count,
            "contract_supported_entrypoints": contract_entrypoint_count,
            "inventory_supported_entrypoints": inventory_entrypoint_count,
            "inventory_entrypoint_rows": len(inventory_entrypoint_rows),
            "inventory_entrypoint_schema_fields_per_row": inventory_entrypoint_schema_field_count,
            "inventory_entrypoint_schema_field_slots_present": inventory_entrypoint_field_present,
            "inventory_entrypoint_schema_field_slots_expected": len(inventory_entrypoint_rows)
            * inventory_entrypoint_schema_field_count,
            "contract_generated_artifact_families": len(canonical_families),
            "inventory_generated_artifact_families": len(inventory_families),
            "generated_artifact_family_schema_fields_per_row": family_schema_field_count,
            "inventory_generated_artifact_family_schema_field_slots_present": inventory_family_field_present,
            "inventory_generated_artifact_family_schema_field_slots_expected": len(inventory_families)
            * family_schema_field_count,
        },
        "canonical_schema_source": canonical_source_path,
        "inputs": snapshot["inputs"],
        "unresolved_by_construction": [
            *snapshot["unresolved_by_construction"],
            (
                "This checker reconciles static declarations with the canonical rendered inventory "
                "schema. It does not execute facades or independently resolve runtime exports; "
                "canonical architecture guardrails retain that separate predicate."
            ),
            (
                "The public_surface_inventory_reviewed field is a local owner attestation. "
                "This report does not authenticate the reviewer and is not G acceptance."
            ),
        ],
    }
    return errors, evidence


def _validate_extension_points(repo_root: Path, header: dict[str, Any]) -> list[Finding]:
    path = repo_root / str(header["extension_point_contract"])
    data = _read_toml(path)
    defaults = data.get("defaults", {})
    errors: list[Finding] = []
    for category in data.get("compatibility_category", []):
        subject = str(category.get("id", ""))
        for field in ("version_owner", "deprecation_window", "release_fragment_change_class"):
            if not str(category.get(field, "")).strip():
                errors.append(Finding("extension-category", "error", subject, f"missing `{field}`"))
    for window in data.get("deprecation_window", []):
        subject = str(window.get("id", ""))
        if (
            not str(window.get("owner", "")).strip()
            or not str(window.get("minimum_notice", "")).strip()
        ):
            errors.append(
                Finding("deprecation-window", "error", subject, "missing owner or minimum_notice")
            )
    for row in data.get("extension_point", []):
        subject = str(row.get("name", ""))
        for field in ("contract_version", "abi_compatibility", "deprecation_notice_window"):
            if not str(row.get(field, defaults.get(field, ""))).strip():
                errors.append(Finding("extension-point", "error", subject, f"missing `{field}`"))
        version_owner = row.get("version_owner") or row.get("owner")
        if not str(version_owner or "").strip():
            errors.append(Finding("extension-point", "error", subject, "missing version owner"))
        release_class = row.get("release_fragment_change_class") or defaults.get(
            "release_fragment_change_class"
        )
        if release_class != "extension-plugin-abi":
            errors.append(
                Finding(
                    "extension-point",
                    "error",
                    subject,
                    "release_fragment_change_class must be extension-plugin-abi",
                    str(release_class),
                )
            )
    return errors


def _validate_generated_artifacts(
    repo_root: Path,
    policy: dict[str, Any],
    header: dict[str, Any],
) -> list[Finding]:
    path = repo_root / str(header["generated_artifact_contract"])
    data = _read_toml(path)
    families = {str(item["id"]): item for item in data.get("family", [])}
    errors: list[Finding] = []
    for expected in policy.get("generated_family", []):
        family_id = str(expected.get("id", ""))
        family = families.get(family_id)
        if family is None:
            errors.append(
                Finding(
                    "generated-artifact",
                    "error",
                    family_id,
                    "registered compatibility family is missing",
                )
            )
            continue
        for field in (
            "compatibility_class",
            "version_owner",
            "deprecation_window",
            "release_fragment_change_class",
        ):
            if not str(family.get(field, "")).strip():
                errors.append(
                    Finding("generated-artifact", "error", family_id, f"missing `{field}`")
                )
        if (
            expected.get("requires_generated_client_compatibility")
            and not str(family.get("generated_client_compatibility", "")).strip()
        ):
            errors.append(
                Finding(
                    "generated-artifact",
                    "error",
                    family_id,
                    "missing generated_client_compatibility declaration",
                )
            )
        if (
            expected.get("requires_inventory_review_policy")
            and not str(family.get("review_policy", "")).strip()
        ):
            errors.append(
                Finding("generated-artifact", "error", family_id, "missing review_policy")
            )
    return errors


def _validate_runtime_state(repo_root: Path, header: dict[str, Any]) -> list[Finding]:
    path = repo_root / str(header["runtime_state_contract"])
    data = _read_toml(path)
    layout = data["runtime_state_layout"]
    errors: list[Finding] = []
    for field in (
        "compatibility_class",
        "version_owner",
        "deprecation_window",
        "release_fragment_change_class",
        "reader_policy",
    ):
        if not str(layout.get(field, "")).strip():
            errors.append(
                Finding("runtime-state", "error", _relative(path, repo_root), f"missing `{field}`")
            )
    for slot in data.get("migration_slot", []):
        if slot.get("compatibility_policy") and not layout.get("version_owner"):
            errors.append(
                Finding(
                    "runtime-state",
                    "error",
                    str(slot.get("id", "")),
                    "migration slot lacks inherited version owner",
                )
            )
    return errors


def _validate_migrations(repo_root: Path, header: dict[str, Any]) -> list[Finding]:
    path = repo_root / str(header["migration_contract"])
    data = _read_toml(path)
    errors: list[Finding] = []
    for item in data.get("migration_class", []):
        subject = str(item.get("id", ""))
        for field in ("version_owner", "deprecation_window", "release_fragment_change_class"):
            if not str(item.get(field, "")).strip():
                errors.append(Finding("migration-class", "error", subject, f"missing `{field}`"))
        for doc in item.get("operator_docs", []):
            if not _path_or_glob_exists(repo_root, str(doc)):
                errors.append(
                    Finding(
                        "migration-class",
                        "error",
                        subject,
                        "operator doc path is missing",
                        str(doc),
                    )
                )
    return errors


def _validate_schema_manifests(repo_root: Path, header: dict[str, Any]) -> list[Finding]:
    errors: list[Finding] = []
    for raw_path in header.get("schema_manifest_paths", []):
        path = repo_root / str(raw_path)
        if not path.exists():
            errors.append(
                Finding("schema-manifest", "error", str(raw_path), "manifest path is missing")
            )
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        compatibility = payload.get("compatibility")
        if not isinstance(compatibility, dict):
            errors.append(
                Finding("schema-manifest", "error", str(raw_path), "missing compatibility metadata")
            )
            continue
        for field in (
            "compatibility_class",
            "version_owner",
            "deprecation_window",
            "release_fragment_change_class",
        ):
            if not str(compatibility.get(field, "")).strip():
                errors.append(
                    Finding(
                        "schema-manifest", "error", str(raw_path), f"missing compatibility.{field}"
                    )
                )
    return errors


def _validate_release_template(
    repo_root: Path,
    policy: dict[str, Any],
    header: dict[str, Any],
) -> list[Finding]:
    template_path = repo_root / str(header["release_fragment_template"])
    template = _read_toml(template_path)
    required = tuple(str(field) for field in header.get("required_structured_fields", []))
    changes = template.get("compatibility_change", [])
    errors: list[Finding] = []
    if not isinstance(changes, list) or not changes:
        errors.append(
            Finding(
                "release-template",
                "error",
                _relative(template_path, repo_root),
                "missing [[compatibility_change]] template",
            )
        )
        return errors
    first = changes[0]
    for field in required:
        if field not in first:
            errors.append(
                Finding(
                    "release-template",
                    "error",
                    _relative(template_path, repo_root),
                    f"missing compatibility_change.{field}",
                )
            )
    fragment_policy = _read_toml(repo_root / str(header["release_fragment_policy"]))
    policy_fields = fragment_policy.get("release_fragments", {}).get(
        "structured_compatibility_required_fields", []
    )
    if list(required) != list(policy_fields):
        errors.append(
            Finding(
                "release-template",
                "error",
                _relative(template_path, repo_root),
                "template required fields disagree with release-fragment policy",
            )
        )
    return errors


def _field_values(value: object, field_name: str, path: str = "") -> list[tuple[str, object]]:
    found: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == field_name:
                found.append((child_path, child))
            found.extend(_field_values(child, field_name, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_field_values(child, field_name, f"{path}[{index}]"))
    return found


def _required_fragment_field_is_missing(field: str, value: object) -> bool:
    if field in {"id", "title", "type", "owner", "summary"}:
        return not isinstance(value, str) or not value.strip()
    if field == "evidence":
        return (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) or not item.strip() for item in value)
        )
    return value in (None, "", [], {})


def _validate_fragments(
    repo_root: Path,
    policy: dict[str, Any],
    fragments: list[dict[str, object]],
    *,
    breaking_classes: tuple[str, ...],
) -> tuple[list[Finding], list[Finding]]:
    header = policy["compatibility_release_gates"]
    allowed_classes = {str(item) for item in header.get("allowed_change_classes", [])}
    breaking_impacts = {str(item) for item in header.get("breaking_impacts", [])}
    required = tuple(str(field) for field in header.get("required_structured_fields", []))
    errors: list[Finding] = []
    findings: list[Finding] = []
    fragment_policy_path = _resolve(
        repo_root, str(header.get("release_fragment_policy", ""))
    )
    fragment_policy = (
        _read_toml(fragment_policy_path).get("release_fragments", {})
        if fragment_policy_path.is_file()
        else {}
    )
    required_fragment_fields = tuple(
        str(field) for field in fragment_policy.get("required_fields", [])
    )
    typed_root_fields = {"id", "title", "type", "owner", "summary", "evidence"}
    if set(required_fragment_fields) != typed_root_fields:
        errors.append(
            Finding(
                "fragment-schema-policy",
                "error",
                _relative(fragment_policy_path, repo_root),
                "required fragment fields do not match the typed root schema",
                f"policy={sorted(set(required_fragment_fields))}; schema={sorted(typed_root_fields)}",
            )
        )
    allowed_fragment_types = {
        str(item).strip().lower() for item in fragment_policy.get("allowed_types", [])
    }
    allowed_generated_client_values = {
        str(item) for item in fragment_policy.get("generated_client_compatibility_values", [])
    }
    renderer_fragment_types = {str(item).strip().lower() for item in SECTION_TITLES}
    if allowed_fragment_types != renderer_fragment_types:
        errors.append(
            Finding(
                "fragment-schema-policy",
                "error",
                _relative(fragment_policy_path, repo_root),
                "allowed fragment types do not match release-note renderer categories",
                f"policy={sorted(allowed_fragment_types)}; renderer={sorted(renderer_fragment_types)}",
            )
        )
    structured_changes = structured_compatibility_changes(fragments)

    breaking_seen = {
        str(change.get("change_class", ""))
        for change in structured_changes
        if str(change.get("impact", "")).strip().lower() in breaking_impacts
    }
    for change_class in breaking_classes:
        if change_class not in breaking_seen:
            errors.append(
                Finding(
                    "breaking-fragment",
                    "error",
                    change_class,
                    "breaking compatibility class has no structured release fragment",
                )
            )

    for fragment in fragments:
        fragment_path = str(fragment.get("__path__", ""))
        for field in required_fragment_fields:
            value = fragment.get(field)
            if _required_fragment_field_is_missing(field, value):
                errors.append(
                    Finding(
                        "fragment-schema",
                        "error",
                        fragment_path,
                        (
                            f"invalid `{field}`; expected a non-empty list of non-empty strings"
                            if field == "evidence" and value not in (None, "", [], {})
                            else f"missing `{field}`"
                        ),
                    )
                )
        fragment_type_value = fragment.get("type")
        fragment_type = (
            fragment_type_value.strip().lower()
            if isinstance(fragment_type_value, str)
            else ""
        )
        if fragment_type not in allowed_fragment_types:
            errors.append(
                Finding(
                    "fragment-schema",
                    "error",
                    fragment_path,
                    "unsupported fragment type",
                    fragment_type,
                )
            )

        for field_path, value in _field_values(
            fragment, "generated_client_compatibility"
        ):
            if not isinstance(value, str) or value not in allowed_generated_client_values:
                errors.append(
                    Finding(
                        "generated-client-enum",
                        "error",
                        f"{fragment_path}:{field_path}",
                        "unsupported generated_client_compatibility",
                        repr(value),
                    )
                )

        changes = fragment.get("compatibility_change", [])
        if isinstance(changes, dict):
            changes = [changes]
        if not isinstance(changes, list):
            errors.append(
                Finding(
                    "fragment-compatibility",
                    "error",
                    fragment_path,
                    "compatibility_change must be a table array",
                )
            )
            continue
        for raw_change in changes:
            if not isinstance(raw_change, dict):
                errors.append(
                    Finding(
                        "fragment-compatibility",
                        "error",
                        fragment_path,
                        "compatibility_change entry must be a table",
                    )
                )
                continue
            change = {str(key): value for key, value in raw_change.items()}
            subject = f"{fragment_path}:{change.get('id', '<missing-id>')}"
            for field in required:
                if not str(change.get(field, "")).strip():
                    errors.append(
                        Finding("fragment-compatibility", "error", subject, f"missing `{field}`")
                    )
            change_class = str(change.get("change_class", ""))
            if change_class and change_class not in allowed_classes:
                errors.append(
                    Finding(
                        "fragment-compatibility",
                        "error",
                        subject,
                        "unsupported change_class",
                        change_class,
                    )
                )
            impact = str(change.get("impact", "")).lower()
            is_breaking = impact in breaking_impacts
            migration_docs = _as_string_list(change.get("migration_docs")) or _as_string_list(
                fragment.get("migration_docs")
            )
            runbook_docs = _as_string_list(change.get("runbook_docs")) or _as_string_list(
                fragment.get("runbook_docs")
            )
            for doc in migration_docs + runbook_docs:
                if not _path_or_glob_exists(repo_root, doc):
                    errors.append(
                        Finding(
                            "fragment-docs",
                            "error",
                            subject,
                            "linked migration/runbook doc is missing",
                            doc,
                        )
                    )
            if (
                is_breaking
                and change_class
                in {"runtime-state-format", "schema-openapi-abi", "persisted-artifact-format"}
                and not migration_docs
            ):
                errors.append(
                    Finding(
                        "fragment-docs",
                        "error",
                        subject,
                        "breaking migration class requires migration_docs",
                    )
                )
            if is_breaking and change_class == "runtime-state-format" and not runbook_docs:
                errors.append(
                    Finding(
                        "fragment-docs",
                        "error",
                        subject,
                        "breaking runtime-state change requires runbook_docs",
                    )
                )
            if change_class == "python-public-api":
                reviewed = bool(fragment.get("public_surface_inventory_reviewed")) or bool(
                    change.get("public_surface_inventory_reviewed")
                )
                if not reviewed:
                    errors.append(
                        Finding(
                            "public-surface-review",
                            "error",
                            subject,
                            "python public API change requires "
                            "public_surface_inventory_reviewed=true",
                        )
                    )
            if change_class in {"schema-openapi-abi", "js-package-api"}:
                generated_client = str(
                    change.get(
                        "generated_client_compatibility",
                        fragment.get("generated_client_compatibility", ""),
                    )
                )
                if not generated_client or generated_client == "not_applicable":
                    errors.append(
                        Finding(
                            "generated-client",
                            "error",
                            subject,
                            "generated client compatibility must be declared",
                        )
                    )
    if not structured_changes:
        findings.append(
            Finding(
                "fragment-compatibility",
                "warning",
                "release-fragments",
                "no structured compatibility changes found in selected fragments",
            )
        )
    return errors, findings


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _resolve(repo_root: Path, path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _path_or_glob_exists(repo_root: Path, path: str) -> bool:
    if any(char in path for char in "*?["):
        return bool(list(repo_root.glob(path)))
    return (repo_root / path).exists()


def _as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build report-only evidence for compatibility release gates."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--fragments-dir", type=Path)
    parser.add_argument(
        "--breaking-class",
        action="append",
        default=[],
        help="Compatibility change_class that is breaking in this release candidate.",
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--fail-on-contract-errors",
        action="store_true",
        help="Return non-zero when compatibility release-gate contracts are malformed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_report(
        repo_root=repo_root,
        policy_path=args.policy,
        fragments_dir=args.fragments_dir,
        breaking_classes=tuple(args.breaking_class),
    )
    output = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_output is not None:
        output_path = _resolve(repo_root, args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    if args.fail_on_contract_errors and payload["contract_error_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
