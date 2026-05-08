"""Fail-closed Phase 6.3 operability, release, and supply-chain gates."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from
from tools.ops_runners.release import check_compatibility_release_gates
from tools.quality.validation import control_plane_supply_chain_contracts

REPO_ROOT = repo_root_from(__file__)
WORKSPACE_ROOT = REPO_ROOT.parent
DEFAULT_CONTRACT = REPO_ROOT / "architecture" / "gates" / "operability_release_supply_chain.toml"
PHASE = "repository-best-in-class-phase-6.3"
GATE_COMMAND = "uv run polisyos-tools release check-operability-release-gates --fail-closed"
REQUIRED_DEPLOYMENT_UNITS = {
    "control_plane",
    "runtime_api",
    "data_plane",
    "frontend",
    "cli",
    "python_packages",
}
REQUIRED_PROMOTION_GATES = {
    "component_observability_coverage",
    "runbook_alert_coverage",
    "breaking_migration_runbook_docs",
    "compatibility_release_metadata",
    "security_sbom_provenance",
    "operability_release_supply_chain",
}
REQUIRED_MIGRATION_CLASSES = {"db", "runtime_state", "api_schemas", "ir"}
DEFAULT_REQUIRED_OPERABILITY_BUNDLE_FILES = (
    "README.md",
    "alerts.yml",
    "dashboard.json",
    "retention-policy.toml",
    "runbooks.md",
    "runtime-contract.toml",
    "slo.yaml",
)
DEFAULT_PHASE_6_6_PLAN_WINDOW_START = dt.date(2026, 5, 7)
DEFAULT_PHASE_6_6_PLAN_COMPLETION_TARGET = dt.date(2026, 5, 31)
EXCEPTION_MINIMUM_DAYS_AFTER_COMPLETION = 90
COMPONENT_SLO_REQUIRED_CLASSIFICATIONS = {
    "public_stable",
    "public_experimental",
    "public_experimental_phase_4_9_required",
    "public_experimental_phase_4_9_exception",
    "internal_with_compatibility_alias_phase_4_9_exception",
    "operational_control",
}
PROMETHEUS_ALERT_RE = re.compile(r"^\s*-\s+alert:\s+([A-Za-z0-9_]+)\s*$", re.MULTILINE)
COMPONENT_ALERT_RE = re.compile(r"^\s*-\s+name:\s+([A-Za-z0-9_]+)\s*$")
COMPONENT_RUNBOOK_RE = re.compile(r"^\s+runbook:\s+(.+)\s*$")


@dataclass(frozen=True)
class Finding:
    check: str
    subject: str
    message: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "subject": self.subject,
            "message": self.message,
            "detail": self.detail,
        }

    def render(self) -> str:
        suffix = f" :: {self.detail}" if self.detail else ""
        return f"[{self.check}] {self.subject}: {self.message}{suffix}"


def build_report(
    *,
    repo_root: Path = REPO_ROOT,
    contract_path: Path = DEFAULT_CONTRACT,
    fragments_dir: Path | None = None,
    breaking_classes: tuple[str, ...] = (),
    current_date: dt.date | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = _resolve(repo_root, contract_path)
    contract = _read_toml(contract_path)
    findings: list[Finding] = []

    findings.extend(_check_conversion_contract(repo_root, contract_path, contract))
    operability_summary, operability_findings = _check_operability(
        repo_root,
        current_date=current_date,
    )
    findings.extend(operability_findings)
    release_summary, release_findings = _check_release_promotion(
        repo_root,
        fragments_dir=fragments_dir,
        breaking_classes=breaking_classes,
    )
    findings.extend(release_findings)
    supply_chain_summary, supply_chain_findings = _check_supply_chain(repo_root, contract)
    findings.extend(supply_chain_findings)

    return {
        "phase": PHASE,
        "mode": "fail_closed",
        "status": "failed" if findings else "passed",
        "contract": _relative(contract_path, repo_root),
        "finding_count": len(findings),
        "findings": [finding.as_dict() for finding in findings],
        "summary": {
            "operability": operability_summary,
            "release_promotion": release_summary,
            "supply_chain": supply_chain_summary,
        },
    }


def _check_conversion_contract(
    repo_root: Path,
    contract_path: Path,
    contract: dict[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []
    header = contract.get("operability_release_supply_chain_gates", {})
    subject = _relative(contract_path, repo_root)
    expected = {
        "status": "fail_closed",
        "phase": PHASE,
        "gate_command": GATE_COMMAND,
        "release_workflow": ".github/workflows/release.yml",
        "release_workflow_job": "operability-release-gate",
        "promotion_gate_id": "operability_release_supply_chain",
    }
    for field, expected_value in expected.items():
        if header.get(field) != expected_value:
            findings.append(
                Finding(
                    "conversion-contract",
                    subject,
                    f"`{field}` must be {expected_value!r}",
                    str(header.get(field, "")),
                )
            )
    for field in ("owner", "source_contracts"):
        if not header.get(field):
            findings.append(Finding("conversion-contract", subject, f"`{field}` is required"))

    gate_ids = {str(item.get("id", "")): item for item in contract.get("gate", [])}
    expected_gate_ids = {
        "slo-runbook-coverage",
        "component-observability",
        "alert-to-runbook",
        "migration-classes",
        "release-topology",
        "promotion-gates",
        "compatibility-release-metadata",
        "release-supply-chain",
        "workflow-permissions-oidc",
    }
    missing = sorted(expected_gate_ids - set(gate_ids))
    if missing:
        findings.append(
            Finding(
                "conversion-contract", subject, "missing converted gate ids", ", ".join(missing)
            )
        )
    for gate_id, gate in sorted(gate_ids.items()):
        if gate.get("mode") != "fail_closed":
            findings.append(Finding("conversion-contract", gate_id, "gate is not fail_closed"))
        for field in ("owner", "source_contracts", "blocks"):
            if not gate.get(field):
                findings.append(Finding("conversion-contract", gate_id, f"`{field}` is required"))
        for raw_path in gate.get("source_contracts", []):
            if not _path_or_glob_exists(repo_root, str(raw_path)):
                findings.append(
                    Finding(
                        "conversion-contract",
                        gate_id,
                        "source contract path is missing",
                        str(raw_path),
                    )
                )
    for raw_path in header.get("source_contracts", []):
        if not _path_or_glob_exists(repo_root, str(raw_path)):
            findings.append(
                Finding(
                    "conversion-contract",
                    subject,
                    "header source contract path is missing",
                    str(raw_path),
                )
            )
    return findings


def _check_operability(
    repo_root: Path,
    *,
    current_date: dt.date | None = None,
) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    current_date = current_date or dt.date.today()
    components_index = _read_toml(repo_root / "ops" / "components" / "index.toml")
    runbooks = _read_toml(repo_root / "architecture" / "runbook_coverage.toml")
    observability = _read_toml(repo_root / "architecture" / "component_observability.toml")
    components = {str(item.get("id", "")): item for item in components_index.get("component", [])}
    public_stable = _public_stable_components(repo_root)
    bundle_policy, bundle_policy_findings = _component_bundle_policy(
        repo_root=repo_root,
        components_index=components_index,
        runbooks=runbooks,
        observability=observability,
    )
    findings.extend(bundle_policy_findings)
    index_public_stable = {
        component_id
        for component_id, component in components.items()
        if str(component.get("classification", "")) == "public_stable"
    }

    missing_components = sorted(public_stable - set(components))
    for component in missing_components:
        findings.append(
            Finding(
                "slo-runbook-coverage",
                component,
                "public-stable component is missing from ops/components/index.toml",
            )
        )

    for component_id in sorted(index_public_stable):
        findings.extend(
            _check_public_stable_bundle(
                repo_root=repo_root,
                component_id=component_id,
                component=components[component_id],
                required_files=bundle_policy["required_files"],
            )
        )

    for component_id, component in sorted(components.items()):
        classification = str(component.get("classification", ""))
        requires_slo = (
            component_id in public_stable
            or classification in COMPONENT_SLO_REQUIRED_CLASSIFICATIONS
        )
        if not requires_slo:
            continue
        runbook_paths = _as_string_list(component.get("runbooks"))
        if not runbook_paths:
            findings.append(
                Finding("slo-runbook-coverage", component_id, "component has no runbooks")
            )
        for runbook in runbook_paths:
            if not _path_or_glob_exists(repo_root, runbook):
                findings.append(
                    Finding(
                        "slo-runbook-coverage", component_id, "runbook path is missing", runbook
                    )
                )

        slo_status = str(component.get("slo_status", ""))
        slo_file = str(component.get("slo_file", ""))
        if slo_status not in {"present", "exception"}:
            findings.append(
                Finding(
                    "slo-runbook-coverage",
                    component_id,
                    "slo_status must be present or exception",
                    slo_status,
                )
            )
        if slo_file and not _path_or_glob_exists(repo_root, slo_file):
            findings.append(
                Finding("slo-runbook-coverage", component_id, "slo_file is missing", slo_file)
            )
        elif slo_file:
            slo_text = (repo_root / slo_file).read_text(encoding="utf-8")
            if slo_status == "present" and (
                "objectives:" not in slo_text or "runbook:" not in slo_text
            ):
                findings.append(
                    Finding(
                        "slo-runbook-coverage",
                        component_id,
                        "present SLO file must declare objectives and runbook links",
                        slo_file,
                    )
                )
            if slo_status == "exception":
                findings.extend(
                    _check_exception_record(
                        component,
                        subject=component_id,
                        prefix="exception",
                        policy=bundle_policy,
                        current_date=current_date,
                        source="ops/components/index.toml",
                    )
                )
                if "status: exception" not in slo_text:
                    findings.append(
                        Finding(
                            "slo-runbook-coverage",
                            component_id,
                            "exception SLO file must carry status: exception",
                            slo_file,
                        )
                    )

    observability_contracts = {
        str(item.get("component", "")): item for item in observability.get("component_contract", [])
    }
    for component_id in sorted(public_stable):
        if component_id not in observability_contracts:
            findings.append(
                Finding(
                    "component-observability",
                    component_id,
                    "public-stable component is missing component_observability contract",
                )
            )
    for component_id, component in sorted(observability_contracts.items()):
        if component.get("slo_status") == "required_missing":
            findings.append(
                Finding("component-observability", component_id, "slo_status is required_missing")
            )
        if component.get("slo_status") == "exception":
            findings.extend(
                _check_exception_record(
                    component,
                    subject=component_id,
                    prefix="exception",
                    policy=bundle_policy,
                    current_date=current_date,
                    source="architecture/component_observability.toml",
                )
            )
        for field in (
            "owner",
            "slo_file",
            "slo_status",
            "trace_context_keys",
            "log_context_keys",
            "release_gate",
        ):
            if not component.get(field):
                findings.append(
                    Finding("component-observability", component_id, f"`{field}` is required")
                )
        for raw_path in [
            str(component.get("slo_file", "")),
            str(component.get("grafana_dashboard", "")),
        ]:
            if raw_path and not _path_or_glob_exists(repo_root, raw_path):
                findings.append(
                    Finding(
                        "component-observability",
                        component_id,
                        "observability path is missing",
                        raw_path,
                    )
                )
        for raw_path in component.get("prometheus_rules", []):
            if not _path_or_glob_exists(repo_root, str(raw_path)):
                findings.append(
                    Finding(
                        "component-observability",
                        component_id,
                        "Prometheus rule path is missing",
                        str(raw_path),
                    )
                )

    for component in runbooks.get("component_contract", []):
        if component.get("slo_exception"):
            findings.extend(
                _check_exception_record(
                    component,
                    subject=str(component.get("component", "")),
                    prefix="slo_exception",
                    policy=bundle_policy,
                    current_date=current_date,
                    source="architecture/runbook_coverage.toml",
                )
            )

    alert_summary, alert_findings = _check_alert_coverage(repo_root, runbooks)
    findings.extend(alert_findings)
    return (
        {
            "component_count": len(components),
            "public_stable_component_count": len(public_stable),
            "public_stable_index_component_count": len(index_public_stable),
            "observability_contract_count": len(observability_contracts),
            "required_bundle_files": bundle_policy["required_files"],
            **alert_summary,
        },
        findings,
    )


def _component_bundle_policy(
    *,
    repo_root: Path,
    components_index: dict[str, Any],
    runbooks: dict[str, Any],
    observability: dict[str, Any],
) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    header = components_index.get("component_bundles", {})
    required_files = tuple(
        _as_string_list(header.get("required_public_stable_bundle_files"))
        or DEFAULT_REQUIRED_OPERABILITY_BUNDLE_FILES
    )
    plan_window_start = _parse_date(
        header.get("phase_6_6_plan_window_start"),
        default=DEFAULT_PHASE_6_6_PLAN_WINDOW_START,
    )
    plan_completion_target = _parse_date(
        header.get("phase_6_6_plan_completion_target"),
        default=DEFAULT_PHASE_6_6_PLAN_COMPLETION_TARGET,
    )
    if plan_window_start is None:
        plan_window_start = DEFAULT_PHASE_6_6_PLAN_WINDOW_START
        findings.append(
            Finding(
                "operability-bundle-completeness",
                "ops/components/index.toml",
                "phase_6_6_plan_window_start must be an ISO date",
            )
        )
    if plan_completion_target is None:
        plan_completion_target = DEFAULT_PHASE_6_6_PLAN_COMPLETION_TARGET
        findings.append(
            Finding(
                "operability-bundle-completeness",
                "ops/components/index.toml",
                "phase_6_6_plan_completion_target must be an ISO date",
            )
        )

    expected_required_files = set(DEFAULT_REQUIRED_OPERABILITY_BUNDLE_FILES)
    if set(required_files) != expected_required_files:
        findings.append(
            Finding(
                "operability-bundle-completeness",
                "ops/components/index.toml",
                "required public-stable bundle files do not match Phase 6.6",
                ", ".join(sorted(set(required_files) ^ expected_required_files)),
            )
        )
    expected_gate = "fail_closed"
    for subject, contract, table_name in (
        ("ops/components/index.toml", components_index, "component_bundles"),
        ("architecture/runbook_coverage.toml", runbooks, "runbook_coverage"),
        (
            "architecture/component_observability.toml",
            observability,
            "component_observability",
        ),
    ):
        contract_header = contract.get(table_name, {})
        if contract_header.get("phase_6_6_completeness_gate") != expected_gate:
            findings.append(
                Finding(
                    "operability-bundle-completeness",
                    subject,
                    "phase_6_6_completeness_gate must be fail_closed",
                    str(contract_header.get("phase_6_6_completeness_gate", "")),
                )
            )
        if set(_as_string_list(contract_header.get("required_public_stable_bundle_files"))) != (
            expected_required_files
        ):
            findings.append(
                Finding(
                    "operability-bundle-completeness",
                    subject,
                    "required_public_stable_bundle_files must mirror Phase 6.6",
                )
            )
    minimum_expiration = plan_completion_target + dt.timedelta(
        days=EXCEPTION_MINIMUM_DAYS_AFTER_COMPLETION
    )
    return (
        {
            "required_files": tuple(required_files),
            "plan_window_start": plan_window_start,
            "plan_completion_target": plan_completion_target,
            "minimum_exception_expiration": minimum_expiration,
        },
        findings,
    )


def _check_public_stable_bundle(
    *,
    repo_root: Path,
    component_id: str,
    component: dict[str, Any],
    required_files: tuple[str, ...],
) -> list[Finding]:
    bundle = str(component.get("bundle", ""))
    if not bundle:
        return [
            Finding(
                "operability-bundle-completeness",
                component_id,
                "`bundle` is required for public-stable components",
            )
        ]
    bundle_path = repo_root / bundle
    if not bundle_path.is_dir():
        return [
            Finding(
                "operability-bundle-completeness",
                component_id,
                "public-stable component bundle directory is missing",
                bundle,
            )
        ]
    present_files = {path.name for path in bundle_path.iterdir() if path.is_file()}
    missing = sorted(set(required_files) - present_files)
    if not missing:
        return []
    return [
        Finding(
            "operability-bundle-completeness",
            component_id,
            "public-stable component bundle is missing required files",
            ", ".join(missing),
        )
    ]


def _check_exception_record(
    record: dict[str, Any],
    *,
    subject: str,
    prefix: str,
    policy: dict[str, Any],
    current_date: dt.date,
    source: str,
) -> list[Finding]:
    findings: list[Finding] = []
    required_fields = (
        f"{prefix}_owner",
        f"{prefix}_reason",
        f"{prefix}_expires",
        f"{prefix}_action_plan",
        f"{prefix}_action_due",
    )
    missing_fields = [field for field in required_fields if not str(record.get(field, "")).strip()]
    for field in missing_fields:
        findings.append(
            Finding(
                "operability-exception-policy",
                subject,
                f"`{field}` is required",
                source,
            )
        )

    expires = _parse_date(record.get(f"{prefix}_expires"))
    if expires is None:
        if f"{prefix}_expires" not in missing_fields:
            findings.append(
                Finding(
                    "operability-exception-policy",
                    subject,
                    f"`{prefix}_expires` must be an ISO date",
                    source,
                )
            )
        return findings
    if expires < current_date:
        findings.append(
            Finding(
                "operability-exception-policy",
                subject,
                "exception expired",
                f"{source}: {expires.isoformat()}",
            )
        )

    minimum_expiration = policy["minimum_exception_expiration"]
    if expires >= minimum_expiration:
        return findings

    action_plan = str(record.get(f"{prefix}_action_plan", "")).strip()
    action_due = _parse_date(record.get(f"{prefix}_action_due"))
    plan_window_start = policy["plan_window_start"]
    plan_completion_target = policy["plan_completion_target"]
    if not action_plan or action_due is None or not (
        plan_window_start <= action_due <= plan_completion_target
    ):
        findings.append(
            Finding(
                "operability-exception-policy",
                subject,
                "short exception must have an action plan due inside the plan window",
                (
                    f"{source}: expires={expires.isoformat()} "
                    f"minimum={minimum_expiration.isoformat()}"
                ),
            )
        )
    return findings


def _check_alert_coverage(
    repo_root: Path, runbooks: dict[str, Any]
) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    prometheus_alerts = _prometheus_alert_names(repo_root)
    component_alerts = _component_alert_runbooks(repo_root)
    central_mappings = {
        str(item.get("alert", "")): _as_string_list(item.get("runbooks"))
        for item in runbooks.get("alert_mapping", [])
    }
    component_index = _read_toml(repo_root / "ops" / "components" / "index.toml")
    indexed_alerts = {
        str(alert)
        for component in component_index.get("component", [])
        for alert in component.get("alerts", [])
    }
    all_alerts = prometheus_alerts | set(component_alerts) | indexed_alerts

    for alert in sorted(all_alerts):
        mapped_runbooks = list(
            dict.fromkeys([*central_mappings.get(alert, []), *component_alerts.get(alert, [])])
        )
        if alert not in central_mappings:
            findings.append(
                Finding(
                    "alert-to-runbook",
                    alert,
                    "alert is missing from architecture/runbook_coverage.toml",
                )
            )
        if not mapped_runbooks:
            findings.append(Finding("alert-to-runbook", alert, "alert has no runbook mapping"))
            continue
        for runbook in mapped_runbooks:
            if not _path_or_glob_exists(repo_root, runbook):
                findings.append(
                    Finding("alert-to-runbook", alert, "mapped runbook path is missing", runbook)
                )
    return (
        {
            "prometheus_alert_count": len(prometheus_alerts),
            "component_alert_count": len(component_alerts),
            "central_alert_mapping_count": len(central_mappings),
        },
        findings,
    )


def _check_release_promotion(
    repo_root: Path,
    *,
    fragments_dir: Path | None,
    breaking_classes: tuple[str, ...],
) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    topology = _read_toml(repo_root / "ops" / "release" / "deployment-topology.toml")
    promotion = _read_toml(repo_root / "ops" / "release" / "promotion-gates.toml")
    migrations = _read_toml(repo_root / "ops" / "migrations" / "migration-contracts.toml")

    if topology.get("deployment_topology", {}).get("mode") != "fail_closed":
        findings.append(
            Finding("release-topology", "deployment-topology.toml", "mode must be fail_closed")
        )
    if promotion.get("promotion_gates", {}).get("mode") != "fail_closed":
        findings.append(
            Finding("promotion-gates", "promotion-gates.toml", "mode must be fail_closed")
        )

    units = {str(item.get("id", "")): item for item in topology.get("deployment_unit", [])}
    missing_units = sorted(REQUIRED_DEPLOYMENT_UNITS - set(units))
    if missing_units:
        findings.append(
            Finding(
                "release-topology",
                "deployment units",
                "missing required deployment units",
                ", ".join(missing_units),
            )
        )
    promotion_gates = {str(item.get("id", "")): item for item in promotion.get("gate", [])}
    missing_gates = sorted(REQUIRED_PROMOTION_GATES - set(promotion_gates))
    if missing_gates:
        findings.append(
            Finding(
                "promotion-gates",
                "promotion gates",
                "missing required promotion gates",
                ", ".join(missing_gates),
            )
        )

    for gate_id, gate in sorted(promotion_gates.items()):
        for raw_path in gate.get("required_evidence", []):
            if not _path_or_glob_exists(repo_root, str(raw_path)):
                findings.append(
                    Finding(
                        "promotion-gates",
                        gate_id,
                        "required evidence path is missing",
                        str(raw_path),
                    )
                )
    for unit_id, unit in sorted(units.items()):
        required_gates = {str(item) for item in unit.get("required_gates", [])}
        unknown = sorted(required_gates - set(promotion_gates))
        if unknown:
            findings.append(
                Finding(
                    "release-topology",
                    unit_id,
                    "unit references unknown required gates",
                    ", ".join(unknown),
                )
            )
        if "operability_release_supply_chain" not in required_gates:
            findings.append(
                Finding(
                    "release-topology",
                    unit_id,
                    "unit must require the Phase 6.3 operability release gate",
                )
            )
        for raw_path in unit.get("rollback_runbooks", []):
            if not _path_or_glob_exists(repo_root, str(raw_path)):
                findings.append(
                    Finding(
                        "release-topology",
                        unit_id,
                        "rollback runbook path is missing",
                        str(raw_path),
                    )
                )

    migration_classes = {
        str(item.get("id", "")): item for item in migrations.get("migration_class", [])
    }
    missing_classes = sorted(REQUIRED_MIGRATION_CLASSES - set(migration_classes))
    if missing_classes:
        findings.append(
            Finding(
                "migration-classes",
                "migration-contracts.toml",
                "missing migration classes",
                ", ".join(missing_classes),
            )
        )
    for class_id, migration_class in sorted(migration_classes.items()):
        for field in (
            "target_path",
            "operator_docs",
            "release_gate",
            "version_owner",
            "release_fragment_change_class",
        ):
            if not migration_class.get(field):
                findings.append(Finding("migration-classes", class_id, f"`{field}` is required"))
        for raw_path in [
            str(migration_class.get("target_path", "")),
            *migration_class.get("operator_docs", []),
        ]:
            if raw_path and not _path_or_glob_exists(repo_root, raw_path):
                findings.append(
                    Finding("migration-classes", class_id, "migration path is missing", raw_path)
                )

    compatibility_report = check_compatibility_release_gates.build_report(
        repo_root=repo_root,
        policy_path=repo_root / "architecture" / "gates" / "compatibility_release.toml",
        fragments_dir=fragments_dir,
        breaking_classes=breaking_classes,
    )
    for finding in compatibility_report.get("contract_errors", []):
        findings.append(
            Finding(
                "compatibility-release-metadata",
                str(finding.get("subject", "")),
                str(finding.get("message", "")),
                str(finding.get("detail", "")),
            )
        )
    return (
        {
            "deployment_unit_count": len(units),
            "promotion_gate_count": len(promotion_gates),
            "migration_class_count": len(migration_classes),
            "compatibility_contract_error_count": compatibility_report.get(
                "contract_error_count", 0
            ),
            "structured_compatibility_change_count": compatibility_report.get(
                "structured_compatibility_change_count", 0
            ),
        },
        findings,
    )


def _check_supply_chain(
    repo_root: Path,
    conversion_contract: dict[str, Any],
) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    supply_chain_findings = control_plane_supply_chain_contracts.validate_contract(
        contract_path=repo_root / "architecture" / "control_plane_supply_chain.toml"
    )
    for finding in control_plane_supply_chain_contracts.blockers(supply_chain_findings):
        findings.append(
            Finding("release-supply-chain", finding.check, finding.message, finding.detail)
        )

    release_workflow = WORKSPACE_ROOT / ".github" / "workflows" / "release.yml"
    workflow_text = (
        release_workflow.read_text(encoding="utf-8") if release_workflow.exists() else ""
    )
    required_needles = {
        "operability-release-gate:": "Release workflow must define the Phase 6.3 gate job",
        "check-operability-release-gates": (
            "Release workflow must invoke the Phase 6.3 gate command"
        ),
        "release-supply-chain": "Release workflow must publish supply-chain evidence",
        "actions/attest-build-provenance": "Release workflow must attest release artifacts",
        'cosign" sign-blob': "Release workflow must sign release artifacts",
    }
    for needle, message in required_needles.items():
        if needle not in workflow_text:
            findings.append(
                Finding(
                    "workflow-permissions-oidc", ".github/workflows/release.yml", message, needle
                )
            )

    header = conversion_contract.get("operability_release_supply_chain_gates", {})
    if (
        header.get("release_workflow_job")
        and f"{header['release_workflow_job']}:" not in workflow_text
    ):
        findings.append(
            Finding(
                "workflow-permissions-oidc",
                ".github/workflows/release.yml",
                "release_workflow_job is not present in workflow",
                str(header.get("release_workflow_job")),
            )
        )

    control = control_plane_supply_chain_contracts.load_contract(
        repo_root / "architecture" / "control_plane_supply_chain.toml"
    )
    release_candidate = {
        str(item.get("phase", "")): item for item in control.get("release_phase_gate", [])
    }.get("release_candidate", {})
    if "operability release gate" not in set(release_candidate.get("checks", [])):
        findings.append(
            Finding(
                "release-supply-chain",
                "release_candidate",
                "release candidate checks must include the Phase 6.3 operability release gate",
            )
        )

    return (
        {
            "control_plane_finding_count": len(supply_chain_findings),
            "control_plane_blocker_count": len(
                control_plane_supply_chain_contracts.blockers(supply_chain_findings)
            ),
            "release_workflow": ".github/workflows/release.yml",
        },
        findings,
    )


def _public_stable_components(repo_root: Path) -> set[str]:
    surface_path = _first_existing(
        repo_root,
        ("architecture/public_surface/contract.toml",),
    )
    surface = _read_toml(surface_path)
    components: set[str] = set()
    for package in surface.get("package", []):
        if package.get("classification") != "public_stable":
            continue
        module = str(package.get("module", "")).removeprefix("polisyos.")
        components.add(module.split(".", 1)[0])
    return components


def _prometheus_alert_names(repo_root: Path) -> set[str]:
    names: set[str] = set()
    prometheus = repo_root / "ops" / "observability" / "prometheus"
    for suffix in ("*.yml", "*.yaml"):
        for path in prometheus.rglob(suffix):
            names.update(PROMETHEUS_ALERT_RE.findall(path.read_text(encoding="utf-8")))
    return names


def _component_alert_runbooks(repo_root: Path) -> dict[str, list[str]]:
    mappings: dict[str, list[str]] = {}
    for path in sorted((repo_root / "ops" / "components").glob("*/alerts.yml")):
        current_alert = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            alert_match = COMPONENT_ALERT_RE.match(line)
            if alert_match:
                current_alert = alert_match.group(1)
                mappings.setdefault(current_alert, [])
                continue
            runbook_match = COMPONENT_RUNBOOK_RE.match(line)
            if current_alert and runbook_match:
                mappings.setdefault(current_alert, []).append(runbook_match.group(1).strip())
    return mappings


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
        try:
            return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
        except ValueError:
            return path.as_posix()


def _path_or_glob_exists(repo_root: Path, path: str) -> bool:
    if not path:
        return False
    base = (
        WORKSPACE_ROOT if path.startswith((".github/", "policy-engine/")) else repo_root
    )
    normalized = path
    if path.startswith("../"):
        base = repo_root
    if any(char in normalized for char in "*?["):
        return bool(list(base.glob(normalized)))
    return (base / normalized).exists()


def _first_existing(repo_root: Path, paths: tuple[str, ...]) -> Path:
    for path in paths:
        candidate = repo_root / path
        if candidate.exists():
            return candidate
    return repo_root / paths[0]


def _as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _parse_date(value: object, *, default: dt.date | None = None) -> dt.date | None:
    if value is None or value == "":
        return default
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--fragments-dir", type=Path)
    parser.add_argument(
        "--breaking-class",
        action="append",
        default=[],
        help="Compatibility change_class that is breaking in this release candidate.",
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--fail-closed",
        action="store_true",
        help="Return non-zero when any Phase 6.3 gate finding is present.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_report(
        repo_root=repo_root,
        contract_path=args.contract,
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
    if args.fail_closed and payload["finding_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
