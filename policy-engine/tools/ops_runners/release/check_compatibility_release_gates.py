"""Report Phase 5.10 compatibility release-gate readiness."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from
from tools.ops_runners.release.build_release_notes import (
    load_fragments,
    structured_compatibility_changes,
)

REPO_ROOT = repo_root_from(__file__)
DEFAULT_POLICY = REPO_ROOT / "architecture" / "compatibility_release_gates.toml"


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
    contract_errors.extend(_validate_public_surface(repo_root, header))
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


def _validate_public_surface(repo_root: Path, header: dict[str, Any]) -> list[Finding]:
    path = repo_root / str(header["public_surface_contract"])
    data = _read_toml(path)
    surface = data["public_surface"]
    errors: list[Finding] = []
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
            errors.append(
                Finding("public-surface", "error", _relative(path, repo_root), f"missing `{field}`")
            )

    inventory_path = repo_root / str(
        surface.get("inventory", header.get("public_surface_inventory", ""))
    )
    if not inventory_path.exists():
        errors.append(
            Finding(
                "public-surface",
                "error",
                _relative(path, repo_root),
                "inventory path is missing",
                str(inventory_path),
            )
        )
        return errors

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    manifest_modules = {str(item["module"]) for item in data.get("package", [])}
    inventory_modules = {str(item["module"]) for item in inventory.get("packages", [])}
    missing = sorted(manifest_modules - inventory_modules)
    if missing:
        errors.append(
            Finding(
                "public-surface",
                "error",
                _relative(inventory_path, repo_root),
                "inventory missing package rows",
                ", ".join(missing),
            )
        )
    for package in data.get("package", []):
        version_owner = (
            package.get("version_owner") or surface.get("version_owner") or package.get("owner")
        )
        deprecation_window = package.get("deprecation_window") or surface.get("deprecation_window")
        if not str(version_owner or "").strip():
            errors.append(
                Finding(
                    "public-surface",
                    "error",
                    str(package.get("module", "")),
                    "missing version owner",
                )
            )
        if not str(deprecation_window or "").strip():
            errors.append(
                Finding(
                    "public-surface",
                    "error",
                    str(package.get("module", "")),
                    "missing deprecation window",
                )
            )
    return errors


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
