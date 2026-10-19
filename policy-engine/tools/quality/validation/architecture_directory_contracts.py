"""Focused architecture report validator owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.quality.validation.architecture_package_contracts import (
        ArchitectureReportServices,
        FindingLike,
    )

from pathlib import Path
from typing import Any


def _validate_directory_contracts(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    relative_path = "architecture/policies/directory_contracts.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [
            _services.finding(
                "directory-contracts", "error", relative_path, "contract file is missing"
            )
        ]
    data = _services.read_toml(path)
    errors: list[FindingLike] = []
    header = data.get("directory_contracts", {})
    if not header.get("owner"):
        errors.append(
            _services.finding("directory-contracts", "error", relative_path, "missing owner")
        )
    for field in (
        "topology_source",
        "generated_artifacts_source",
        "local_runtime_state_source",
        "data_policy_source",
    ):
        value = str(header.get(field, ""))
        if not value:
            errors.append(
                _services.finding(
                    "directory-contracts", "error", relative_path, f"missing `{field}`"
                )
            )
        elif not _services.path_pattern_exists(repo_root, value):
            errors.append(
                _services.finding(
                    "directory-contracts",
                    "error",
                    relative_path,
                    f"`{field}` path is missing",
                    value,
                )
            )
    threshold = data.get("high_volume_subtree_threshold", {})
    for field in (
        "tracked_file_count_at_least",
        "immediate_child_directory_count_greater_than",
        "module_line_count_warning_source",
        "local_documentation_requirement",
    ):
        if threshold.get(field) in (None, "", []):
            errors.append(
                _services.finding(
                    "directory-contracts",
                    "error",
                    "high_volume_subtree_threshold",
                    f"missing `{field}`",
                )
            )
    required_contract_fields = (
        "path",
        "status",
        "role",
        "owner",
        "lifecycle_class",
        "topology_category",
        "topology_commit_policy",
        "allowed_file_kinds",
        "allowed_child_directory_kinds",
        "python_import_policy",
        "generated_output_policy",
        "committed_data_policy",
        "readme_index_requirement",
        "max_root_loose_files",
        "root_loose_file_policy",
        "ignored_descendant_retention",
        "evidence_or_generated_artifact_promotion_path",
    )
    contracts = {str(item.get("path", "")): item for item in data.get("contract", [])}
    expected_roots = {
        "architecture",
        "benchmarks",
        "data",
        "design",
        "docs",
        "examples",
        "frontend",
        "apps",
        "ops",
        "packages",
        "release",
        "release-fragments",
        "schemas",
        "src",
        "tests",
        "tools",
        "_build",
        "_cache",
        ".polisyos",
        ".venv",
        "node_modules",
    }
    for root in sorted(expected_roots - set(contracts)):
        errors.append(
            _services.finding("directory-contracts", "error", root, "missing top-level contract")
        )
    for subject, contract in contracts.items():
        for field in required_contract_fields:
            if contract.get(field) in (None, "", []):
                errors.append(
                    _services.finding(
                        "directory-contracts", "error", subject, f"missing required field `{field}`"
                    )
                )
        if (
            contract.get("status") != "reserved_future"
            and contract.get("owner") != "local"
            and subject
            and not _services.path_pattern_exists(repo_root, subject)
        ):
            errors.append(
                _services.finding(
                    "directory-contracts",
                    "error",
                    subject,
                    "contracted top-level path is missing",
                )
            )
    topology_paths = {
        str(item.get("path", "")): item
        for item in _services.read_toml(repo_root / "architecture" / "topology.toml").get(
            "path", []
        )
    }
    for subject, contract in contracts.items():
        if subject in topology_paths:
            topology_entry = topology_paths[subject]
            if contract.get("topology_category") != topology_entry.get("category"):
                errors.append(
                    _services.finding(
                        "directory-contracts",
                        "error",
                        subject,
                        "topology_category contradicts architecture/topology.toml",
                        (
                            f"contract={contract.get('topology_category')} "
                            f"topology={topology_entry.get('category')}"
                        ),
                    )
                )
            if contract.get("topology_commit_policy") != topology_entry.get("commit_policy"):
                errors.append(
                    _services.finding(
                        "directory-contracts",
                        "error",
                        subject,
                        "topology_commit_policy contradicts architecture/topology.toml",
                        (
                            f"contract={contract.get('topology_commit_policy')} "
                            f"topology={topology_entry.get('commit_policy')}"
                        ),
                    )
                )
    asset_classes = {str(item.get("id", "")): item for item in data.get("asset_class", [])}
    for asset_id in (
        "product_seed_assets",
        "test_fixtures",
        "golden_records",
        "examples_tutorial_assets",
    ):
        if asset_id not in asset_classes:
            errors.append(
                _services.finding("directory-contracts", "error", asset_id, "missing asset class")
            )
    ratchets = _services.read_toml(repo_root / "architecture" / "tests" / "ratchets.toml")
    fixture_policy = ratchets.get("fixture_policy", {})
    test_fixtures = asset_classes.get("test_fixtures", {})
    golden_records = asset_classes.get("golden_records", {})
    _services.dispatch(
        "_validate_root_transition",
        errors,
        asset_id="test_fixtures",
        asset=test_fixtures,
        current_root=str(fixture_policy.get("shared_fixture_root", "")),
        target_roots=fixture_policy.get("target_fixture_roots", []),
    )
    _services.dispatch(
        "_validate_root_transition",
        errors,
        asset_id="golden_records",
        asset=golden_records,
        current_root=str(fixture_policy.get("shared_golden_root", "")),
        target_roots=fixture_policy.get("target_golden_roots", []),
    )
    non_product_roots = {
        str(item.get("path", "")): item for item in data.get("non_product_python_root", [])
    }
    for root in ("tools", "tests", "benchmarks", "schemas"):
        item = non_product_roots.get(root)
        if item is None:
            errors.append(
                _services.finding(
                    "directory-contracts", "error", root, "missing non-product Python root policy"
                )
            )
            continue
        for field in ("policy", "owner", "allowed_reason", "product_import_policy"):
            if item.get(field) in (None, "", []):
                errors.append(
                    _services.finding(
                        "directory-contracts", "error", root, f"missing non-product field `{field}`"
                    )
                )
    archive_classes = {str(item.get("id", "")) for item in data.get("archive_class", [])}
    for archive_id in (
        "accepted_plans",
        "historical_plans",
        "release_evidence",
        "local_audit_reports",
        "generated_benchmark_reports",
        "incident_postmortem_records",
    ):
        if archive_id not in archive_classes:
            errors.append(
                _services.finding(
                    "directory-contracts", "error", archive_id, "missing archive class"
                )
            )
    overlay = data.get("phase_1_3_report_only_overlay", {})
    if overlay.get("status") != "report_only":
        errors.append(
            _services.finding(
                "directory-contracts",
                "error",
                relative_path,
                "Phase 1.3 overlay must be report_only",
                str(overlay.get("status")),
            )
        )
    for item in data.get("phase_1_3_directory", []):
        subject = str(item.get("path") or "phase_1_3_directory")
        for field in ("path", "group", "owner", "physical_status", "mode"):
            if not item.get(field):
                errors.append(
                    _services.finding("directory-contracts", "error", subject, f"missing `{field}`")
                )
        if item.get("mode") != "report_only":
            errors.append(
                _services.finding(
                    "directory-contracts",
                    "error",
                    subject,
                    "Phase 1.3 directory mode must be report_only",
                    str(item.get("mode")),
                )
            )
        directory = str(item.get("path", ""))
        if directory and not _services.path_pattern_exists(repo_root, directory):
            errors.append(
                _services.finding(
                    "directory-contracts", "error", subject, "directory is missing", directory
                )
            )
        for contract_file in item.get("contract_files", []):
            if not _services.path_pattern_exists(repo_root, str(contract_file)):
                errors.append(
                    _services.finding(
                        "directory-contracts",
                        "error",
                        subject,
                        "contract file is missing",
                        str(contract_file),
                    )
                )
    return errors


def _validate_directory_hygiene_assets(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    from tools.quality.validation import directory_hygiene_assets

    report = directory_hygiene_assets.build_report(repo_root)
    return [
        _services.finding(
            "directory-hygiene-assets",
            str(item.get("severity", "error")),
            str(item.get("subject", "unknown")),
            str(item.get("message", "")),
            str(item.get("detail", "")),
        )
        for item in report["contract_errors"]
    ]


def _normalize_contract_root(value: str, *, _services: ArchitectureReportServices) -> str:
    return value.removesuffix("/")


def _validate_root_transition(
    errors: list[FindingLike],
    *,
    asset_id: str,
    asset: dict[str, Any],
    current_root: str,
    target_roots: object,
    _services: ArchitectureReportServices,
) -> None:
    current = _services.dispatch("_normalize_contract_root", current_root)
    current_roots = {
        _services.dispatch("_normalize_contract_root", str(item))
        for item in asset.get("current_wave1_roots", [])
    }
    legacy_roots = {
        _services.dispatch("_normalize_contract_root", str(item).split(":", 1)[0])
        for item in asset.get("legacy_roots_until_phase", [])
    }
    allowed_roots = {
        _services.dispatch("_normalize_contract_root", str(item))
        for item in asset.get("allowed_roots", [])
    }
    targets = (
        {
            _services.dispatch("_normalize_contract_root", str(item))
            for item in target_roots
            if str(item)
        }
        if isinstance(target_roots, list)
        else set()
    )
    if current and current not in current_roots and current not in legacy_roots:
        errors.append(
            _services.finding(
                "directory-contracts",
                "error",
                asset_id,
                "current Wave 1 root is not declared as current or legacy",
                current,
            )
        )
    missing_targets = sorted(
        root for root in targets if root not in allowed_roots and "<package>" not in root
    )
    for target in missing_targets:
        errors.append(
            _services.finding(
                "directory-contracts",
                "error",
                asset_id,
                "target root from test_ratchets is not allowed by directory contract",
                target,
            )
        )
