"""Fail-closed Phase 6.3 operability, release, and supply-chain gates."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib
import inspect
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tools.lib.fs import write_scoped_report_text
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
    dependent_binding_summary, dependent_binding_findings = _check_dependent_binding_contracts(
        repo_root
    )
    findings.extend(dependent_binding_findings)
    return (
        {
            "component_count": len(components),
            "public_stable_component_count": len(public_stable),
            "public_stable_index_component_count": len(index_public_stable),
            "observability_contract_count": len(observability_contracts),
            "required_bundle_files": bundle_policy["required_files"],
            **alert_summary,
            **dependent_binding_summary,
        },
        findings,
    )


_DEPENDENT_BINDING_VERSION = "1.0"
_DEPENDENT_BINDING_REQUIRED_FIELDS = {
    "id",
    "schema_version",
    "dependent_package",
    "eligibility_start",
    "runbook_paths",
    "outcome_success_report_status",
    "outcome_success_metric_status",
    "outcome_failure_metric_status",
    "shared_operation",
    "consumer_operation",
    "callsite_operation",
    "profile_operation",
    "executor_operation",
    "report_model",
    "manifest_model",
    "artifact_ref_model",
    "objective",
    "trace",
}
_OPERATION_REFERENCE_FIELDS = (
    "shared_operation",
    "consumer_operation",
    "callsite_operation",
    "profile_operation",
    "executor_operation",
    "report_model",
    "manifest_model",
    "artifact_ref_model",
)


def _package_contracts(repo_root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    contracts: dict[str, tuple[Path, dict[str, Any]]] = {}
    directory = repo_root / "architecture" / "packages"
    for path in sorted(directory.glob("*.toml")):
        data = _read_toml(path)
        package = data.get("package", {})
        if not isinstance(package, dict):
            continue
        package_id = str(package.get("id", ""))
        if package_id:
            contracts[package_id] = (path, data)
    return contracts


def _binding_rows(
    contracts: dict[str, tuple[Path, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for package_id, (_, document) in sorted(contracts.items()):
        slo_runbook = document.get("slo_runbook", {})
        for binding in slo_runbook.get("dependent_bindings", []):
            if isinstance(binding, dict):
                rows.append((package_id, document, binding))
    return rows


def validate_dependent_binding_graph(
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> list[str]:
    """Return cycles in the declared package dependency edges."""
    graph: dict[str, set[str]] = {}
    for package_id, _, binding in rows:
        dependent = str(binding.get("dependent_package", ""))
        if dependent:
            graph.setdefault(package_id, set()).add(dependent)
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: set[str] = set()

    def visit(package_id: str, trail: tuple[str, ...]) -> None:
        if package_id in visiting:
            start = trail.index(package_id) if package_id in trail else 0
            cycles.add(" -> ".join((*trail[start:], package_id)))
            return
        if package_id in visited:
            return
        visiting.add(package_id)
        for dependent in sorted(graph.get(package_id, set())):
            visit(dependent, (*trail, package_id))
        visiting.remove(package_id)
        visited.add(package_id)

    for package_id in sorted(graph):
        visit(package_id, ())
    return sorted(cycles)


def _package_source_root(
    repo_root: Path,
    package_id: str,
    contracts: dict[str, tuple[Path, dict[str, Any]]],
) -> Path:
    """Resolve a package source root from its current package contract."""
    row = contracts.get(package_id)
    if row is None:
        raise ValueError(f"package_source_owner_missing:{package_id}")
    layout = row[1].get("layout", {})
    raw_root = layout.get("source_root") if isinstance(layout, dict) else None
    relative_root = Path(str(raw_root or ""))
    if not raw_root or relative_root.is_absolute() or ".." in relative_root.parts:
        raise ValueError(f"package_source_root_invalid:{package_id}")
    root = (repo_root / relative_root).resolve(strict=True)
    source = (repo_root / "src").resolve(strict=True)
    if not root.is_relative_to(source):
        raise ValueError(f"package_source_root_outside_product:{package_id}")
    return root


def _binding_package_role_errors(
    owner_package_id: str,
    binding: dict[str, Any],
    contracts: dict[str, tuple[Path, dict[str, Any]]],
) -> list[str]:
    """Check edge roles against package IDs in current package contracts."""
    dependent = str(binding.get("dependent_package", ""))
    if owner_package_id not in contracts or dependent not in contracts:
        return []
    roles = {
        "shared_operation": owner_package_id,
        "profile_operation": owner_package_id,
        "executor_operation": owner_package_id,
        "consumer_operation": dependent,
        "callsite_operation": dependent,
    }
    errors: list[str] = []
    for role, expected_package in roles.items():
        reference = binding.get(role)
        if isinstance(reference, dict) and str(reference.get("package", "")) != expected_package:
            errors.append(f"{role}:expected_package={expected_package}")
    return errors


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Reject duplicate YAML fields that could hide selected SLO meaning."""


def _construct_unique_yaml_mapping(
    loader: _UniqueKeySafeLoader, node: Any, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ValueError("slo_yaml_unhashable_mapping_key") from exc
        if duplicate:
            raise ValueError(f"slo_yaml_duplicate_key:{key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_yaml_mapping
)


def _load_slo_document(path: Path) -> dict[str, Any]:
    try:
        loader = _UniqueKeySafeLoader(path.read_text(encoding="utf-8"))
        try:
            value = loader.get_single_data()
        finally:
            loader.dispose()
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ValueError(f"slo_yaml_not_unambiguous:{path}") from exc
    if type(value) is not dict:
        raise ValueError(f"slo_yaml_root_not_mapping:{path}")
    return value


def _bound_objective(
    repo_root: Path,
    objective: dict[str, Any],
    *,
    dependent_contract: dict[str, Any],
    binding_runbooks: list[str],
) -> dict[str, Any]:
    """Resolve a unique objective from the dependent package's declared SLO file."""
    relative = str(objective.get("path", ""))
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise ValueError("objective_path_is_not_repo_relative")
    slo_contract = dependent_contract.get("slo_runbook", {})
    declared_files = slo_contract.get("slo_files", []) if isinstance(slo_contract, dict) else []
    if not isinstance(declared_files, list) or relative not in declared_files:
        raise ValueError("objective_file_not_owned_by_dependent_package")
    document = _load_slo_document(repo_root / path)
    package = dependent_contract.get("package", {})
    if not isinstance(package, dict) or document.get("service") != package.get("name"):
        raise ValueError("objective_service_does_not_match_dependent_package")
    if document.get("owner") != package.get("owner"):
        raise ValueError("objective_owner_does_not_match_dependent_package")
    rows = document.get("objectives")
    if not isinstance(rows, list):
        raise ValueError("slo_objectives_not_a_list")
    names: list[str] = []
    for row in rows:
        if type(row) is not dict:
            raise ValueError("slo_objective_not_a_mapping")
        name = row.get("name")
        if type(name) is not str or not name.strip():
            raise ValueError("slo_objective_name_missing")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("slo_objective_name_ambiguous")
    name = str(objective.get("name", ""))
    selected = [row for row in rows if row.get("name") == name]
    if len(selected) != 1:
        raise ValueError(f"objective_reference_not_unique:{name}")
    result = selected[0]
    sli, runbook = result.get("sli"), result.get("runbook")
    if type(sli) is not str or not sli.strip():
        raise ValueError(f"objective_sli_missing_or_unsupported:{name}")
    if type(runbook) is not str or not runbook.strip():
        raise ValueError(f"objective_runbook_missing_or_unsupported:{name}")
    if type(objective.get("runbook_path")) is not str or runbook != objective["runbook_path"]:
        raise ValueError(f"objective_runbook_not_exactly_bound:{name}")
    package_runbooks = slo_contract.get("runbooks", []) if isinstance(slo_contract, dict) else []
    if (
        not isinstance(binding_runbooks, list)
        or runbook not in binding_runbooks
        or not isinstance(package_runbooks, list)
        or runbook not in package_runbooks
    ):
        raise ValueError(f"objective_runbook_not_owned_by_dependent_package:{name}")
    return result


def _strip_promql_comments(expression: str) -> str:
    """Remove PromQL comments while preserving quoted strings."""
    result: list[str] = []
    quoted = False
    escaped = False
    i = 0
    while i < len(expression):
        char = expression[i]
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            i += 1
        elif char == '"':
            quoted = True
            result.append(char)
            i += 1
        elif char == "#":
            while i < len(expression) and expression[i] != "\n":
                i += 1
            if i < len(expression):
                result.append("\n")
                i += 1
        else:
            result.append(char)
            i += 1
    if quoted:
        raise ValueError("objective_sli_unclosed_string")
    return "".join(result)


def _parse_promql_matchers(raw: str) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    parts: list[str] = []
    start = 0
    quoted = False
    escaped = False
    for i, char in enumerate(raw):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == ",":
            parts.append(raw[start:i])
            start = i + 1
    if quoted:
        raise ValueError("objective_sli_unclosed_label_string")
    parts.append(raw[start:])
    pattern = r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*(=~|!~|!=|=)\s*"((?:\\.|[^"\\])*)"\s*'
    for part in parts:
        if not part.strip():
            continue
        match = re.fullmatch(pattern, part)
        if match is None:
            raise ValueError("objective_sli_label_matcher_unsupported")
        key, operator, value = match.groups()
        if key in result:
            raise ValueError(f"objective_sli_duplicate_label:{key}")
        result[key] = (operator, value)
    return result


def _promql_metric_selectors(
    expression: str,
) -> list[tuple[str, dict[str, tuple[str, str]]]]:
    """Extract actual selectors from SLI syntax, ignoring comments and quoted text."""
    source = _strip_promql_comments(expression)
    result: list[tuple[str, dict[str, tuple[str, str]]]] = []
    i = 0
    while i < len(source):
        char = source[i]
        if char == '"':
            i += 1
            escaped = False
            while i < len(source):
                current = source[i]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    i += 1
                    break
                i += 1
            else:
                raise ValueError("objective_sli_unclosed_string")
            continue
        if char.isalpha() or char in "_:":
            start = i
            i += 1
            while i < len(source) and (source[i].isalnum() or source[i] in "_:"):
                i += 1
            metric = source[start:i]
            selector = i
            while selector < len(source) and source[selector].isspace():
                selector += 1
            if selector >= len(source) or source[selector] != "{":
                continue
            cursor = selector + 1
            quoted = False
            escaped = False
            while cursor < len(source):
                current = source[cursor]
                if quoted:
                    if escaped:
                        escaped = False
                    elif current == "\\":
                        escaped = True
                    elif current == '"':
                        quoted = False
                elif current == '"':
                    quoted = True
                elif current == "}":
                    break
                cursor += 1
            if cursor >= len(source) or quoted:
                raise ValueError("objective_sli_unclosed_selector")
            result.append((metric, _parse_promql_matchers(source[selector + 1 : cursor])))
            i = cursor + 1
            continue
        i += 1
    return result


def _objective_instrument_contract(
    repo_root: Path,
    objective_refs: list[dict[str, Any]],
    *,
    dependent_contract: dict[str, Any],
    binding_runbooks: list[str],
) -> tuple[set[str], str, set[str]]:
    instruments: set[str] = set()
    scopes: set[str] = set()
    scope_fields: set[str] = set()
    statuses: set[str] = set()
    for reference in objective_refs:
        selected = _bound_objective(
            repo_root,
            reference,
            dependent_contract=dependent_contract,
            binding_runbooks=binding_runbooks,
        )
        scope_field = str(reference["measurement_scope_attribute"])
        scope_fields.add(scope_field)
        selectors = _promql_metric_selectors(str(selected["sli"]))
        if not selectors:
            raise ValueError("objective_sli_has_no_supported_metric_selectors")
        objective_scopes: set[str] = set()
        for metric, labels in selectors:
            instruments.add(metric)
            scope = labels.get(scope_field)
            if scope is not None:
                operator, value = scope
                if operator != "=":
                    raise ValueError("objective_scope_matcher_must_be_exact")
                objective_scopes.add(value)
                scopes.add(value)
            status = labels.get("status")
            if status is not None:
                operator, value = status
                if operator not in {"=", "=~"}:
                    raise ValueError("objective_status_matcher_unsupported")
                statuses.update(value.split("|") if operator == "=~" else {value})
        if not objective_scopes:
            raise ValueError("objective_sli_scope_selector_missing")
        if len(objective_scopes) != 1:
            raise ValueError("objective_sli_scope_selector_ambiguous")
    if len(scope_fields) != 1:
        raise ValueError("dependent_objective_scope_attribute_not_unique")
    if len(scopes) != 1:
        raise ValueError("dependent_objective_scope_not_unique")
    return instruments, next(iter(scopes)), statuses


def _check_dependent_binding_contracts(
    repo_root: Path,
) -> tuple[dict[str, Any], list[Finding]]:
    contracts = _package_contracts(repo_root)
    rows = _binding_rows(contracts)
    findings: list[Finding] = []
    ids: set[str] = set()
    for package_id, _document, binding in rows:
        binding_id = str(binding.get("id", ""))
        subject = binding_id or package_id
        if not binding_id or binding_id in ids:
            findings.append(
                Finding(
                    "dependent-execution-binding", subject, "binding id is missing or duplicate"
                )
            )
        ids.add(binding_id)
        if set(binding) != _DEPENDENT_BINDING_REQUIRED_FIELDS:
            findings.append(
                Finding(
                    "dependent-execution-binding",
                    subject,
                    "binding fields do not match the current strict schema",
                    ", ".join(sorted(set(binding) ^ _DEPENDENT_BINDING_REQUIRED_FIELDS)),
                )
            )
        if binding.get("schema_version") != _DEPENDENT_BINDING_VERSION:
            findings.append(
                Finding("dependent-execution-binding", subject, "schema version is unsupported")
            )
        dependent = str(binding.get("dependent_package", ""))
        if dependent not in contracts:
            findings.append(
                Finding("dependent-execution-binding", subject, "dependent package is unknown")
            )
            continue
        for role_error in _binding_package_role_errors(package_id, binding, contracts):
            findings.append(
                Finding(
                    "dependent-execution-binding",
                    subject,
                    "operation package role does not match the dependency edge",
                    role_error,
                )
            )
        for field in _OPERATION_REFERENCE_FIELDS:
            reference = binding.get(field, {})
            if (
                not isinstance(reference, dict)
                or not reference.get("module")
                or not reference.get("symbol")
                or str(reference.get("package", "")) not in contracts
            ):
                findings.append(
                    Finding("dependent-execution-binding", subject, f"{field} is incomplete")
                )
                continue
            owner_id = str(reference["package"])
            owner_module = str(contracts[owner_id][1].get("package", {}).get("module", ""))
            module_name = str(reference["module"])
            if not owner_module or not (
                module_name == owner_module or module_name.startswith(owner_module + ".")
            ):
                findings.append(
                    Finding(
                        "dependent-execution-binding",
                        subject,
                        f"{field} module is outside its package boundary",
                        module_name,
                    )
                )
        trace_fields = {
            "api_span_name",
            "api_run_id_attribute",
            "api_workflow_id_attribute",
            "node_run_id_attribute",
            "node_workflow_id_attribute",
            "event_name",
        }
        if not isinstance(binding.get("trace"), dict) or set(binding["trace"]) != trace_fields:
            findings.append(
                Finding("dependent-execution-binding", subject, "trace references are malformed")
            )
        if binding.get("eligibility_start") != "workflow_resolved":
            findings.append(
                Finding(
                    "dependent-execution-binding",
                    subject,
                    "eligibility boundary must begin after workflow resolution",
                )
            )
        runbook_paths = binding.get("runbook_paths", [])
        if not isinstance(runbook_paths, list) or not runbook_paths:
            findings.append(
                Finding("dependent-execution-binding", subject, "runbook targets are required")
            )
            runbook_paths = []
        for runbook_path in runbook_paths:
            if not _path_or_glob_exists(repo_root, str(runbook_path)):
                findings.append(
                    Finding(
                        "dependent-execution-binding",
                        subject,
                        "runbook target is missing",
                        str(runbook_path),
                    )
                )
        objective_refs = binding.get("objective", [])
        if not isinstance(objective_refs, list) or not objective_refs:
            findings.append(
                Finding("dependent-execution-binding", subject, "objective references are required")
            )
            continue
        for objective in objective_refs:
            if not isinstance(objective, dict) or set(objective) != {
                "path",
                "name",
                "measurement_scope_attribute",
                "runbook_path",
            }:
                findings.append(
                    Finding(
                        "dependent-execution-binding", subject, "objective reference is malformed"
                    )
                )
                continue
            objective_path = str(objective.get("path", ""))
            if not _path_or_glob_exists(repo_root, objective_path):
                findings.append(
                    Finding(
                        "dependent-execution-binding",
                        subject,
                        "objective target is missing",
                        objective_path,
                    )
                )
                continue
            try:
                _bound_objective(
                    repo_root,
                    objective,
                    dependent_contract=contracts[dependent][1],
                    binding_runbooks=runbook_paths,
                )
            except (OSError, ValueError) as exc:
                findings.append(
                    Finding(
                        "dependent-execution-binding",
                        subject,
                        "objective cannot be resolved",
                        str(exc),
                    )
                )
    cycles = validate_dependent_binding_graph(rows)
    for cycle in cycles:
        findings.append(Finding("dependent-execution-binding", cycle, "declared dependency cycle"))
    return (
        {
            "dependent_binding_declaration_count": len(rows),
            "dependent_binding_runtime_qualifications": 0,
            "dependent_binding_admission": "not_established",
        },
        findings,
    )


def _operation_code(reference: dict[str, Any], operation: Any) -> Any:
    """Resolve a declared code object, including one nested in an operation."""
    nested_name = reference.get("nested_code_name")
    code = getattr(operation, "__code__", None)
    if code is None:
        raise ValueError("operation_code_not_established")
    if not nested_name:
        return code
    pending = list(code.co_consts)
    matches = []
    while pending:
        candidate = pending.pop()
        if not isinstance(candidate, type(code)):
            continue
        if candidate.co_name == str(nested_name):
            matches.append(candidate)
        pending.extend(candidate.co_consts)
    if len(matches) != 1:
        raise ValueError(f"nested_operation_code_not_unique:{nested_name}")
    return matches[0]


def _resolve_operation_reference(
    repo_root: Path, reference: dict[str, Any]
) -> tuple[Any, Any, Path]:
    module = importlib.import_module(str(reference["module"]))
    value: Any = module
    for part in str(reference["symbol"]).split("."):
        value = getattr(value, part)
    if not callable(value):
        raise ValueError(
            f"operation_reference_not_callable:{reference['module']}:{reference['symbol']}"
        )
    source = inspect.getsourcefile(value) or getattr(module, "__file__", None)
    if source is None:
        raise ValueError(f"operation_source_not_established:{reference['module']}")
    source_path = Path(source).resolve(strict=True)
    source_root = (repo_root / "src").resolve(strict=True)
    if not source_path.is_relative_to(source_root):
        raise ValueError(f"operation_source_outside_current_checkout:{source_path}")
    contracts = _package_contracts(repo_root)
    package_id = str(reference["package"])
    package = contracts.get(package_id)
    if package is None:
        raise ValueError(f"operation_package_owner_missing:{package_id}")
    package_module = str(package[1].get("package", {}).get("module", ""))
    module_name = str(reference["module"])
    if not package_module or not (
        module_name == package_module or module_name.startswith(package_module + ".")
    ):
        raise ValueError(f"operation_module_outside_declared_package:{module_name}")
    package_source = _package_source_root(repo_root, package_id, contracts)
    if not source_path.is_relative_to(package_source):
        raise ValueError(f"operation_source_outside_declared_package:{package_id}:{source_path}")
    return value, module, source_path


def _dependent_binding(repo_root: Path, binding_id: str) -> dict[str, Any]:
    contracts = _package_contracts(repo_root)
    matches = [
        binding for _, _, binding in _binding_rows(contracts) if binding.get("id") == binding_id
    ]
    if len(matches) != 1:
        raise ValueError(f"dependent_binding_not_unique:{binding_id}")
    binding = matches[0]
    if set(binding) != _DEPENDENT_BINDING_REQUIRED_FIELDS:
        raise ValueError("dependent_binding_schema_mismatch")
    if binding.get("schema_version") != _DEPENDENT_BINDING_VERSION:
        raise ValueError("dependent_binding_version_mismatch")
    if validate_dependent_binding_graph(_binding_rows(contracts)):
        raise ValueError("dependent_binding_cycle")
    _, findings = _check_dependent_binding_contracts(repo_root)
    if any(item.subject == binding_id for item in findings):
        raise ValueError("dependent_binding_source_contract_invalid")
    return binding


def _metric_totals(metrics_data: Any) -> dict[tuple[str, tuple[tuple[str, str], ...]], int]:
    totals: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}
    for resource_metrics in getattr(metrics_data, "resource_metrics", ()):
        for scope_metrics in getattr(resource_metrics, "scope_metrics", ()):
            for metric in getattr(scope_metrics, "metrics", ()):
                for point in getattr(metric.data, "data_points", ()):
                    attributes = tuple(
                        sorted((str(k), str(v)) for k, v in point.attributes.items())
                    )
                    value = getattr(point, "value", None)
                    if value is None:
                        value = getattr(point, "count", None)
                    if value is not None:
                        key = (str(metric.name), attributes)
                        totals[key] = totals.get(key, 0) + int(value)
    return totals


def _selected_metric_deltas(
    before: Any,
    after: Any,
    *,
    counter_name: str,
    histogram_bucket_name: str,
    scope_attribute: str,
    scope_value: str,
    workflow_id: str,
    environment: str,
) -> tuple[dict[str, int], int]:
    before_totals = _metric_totals(before)
    after_totals = _metric_totals(after)
    status_deltas: dict[str, int] = {}
    for (name, attributes), value in after_totals.items():
        if name != counter_name:
            continue
        labels = dict(attributes)
        if (
            labels.get(scope_attribute) != scope_value
            or labels.get("workflow_id") != workflow_id
            or labels.get("env") != environment
        ):
            continue
        previous = before_totals.get((name, attributes), 0)
        delta = value - previous
        if delta:
            status = labels.get("status", "")
            status_deltas[status] = status_deltas.get(status, 0) + delta
    histogram_name = histogram_bucket_name.removesuffix("_bucket")
    histogram_count = 0
    for (name, attributes), value in after_totals.items():
        if name != histogram_name:
            continue
        labels = dict(attributes)
        if (
            labels.get(scope_attribute) != scope_value
            or labels.get("workflow_id") != workflow_id
            or labels.get("env") != environment
        ):
            continue
        histogram_count += value - before_totals.get((name, attributes), 0)
    return status_deltas, histogram_count


def verify_controlled_dependent_execution(
    repo_root: Path,
    *,
    binding_id: str,
    receipt_path: Path,
    observations: tuple[Any, ...],
    span_exporter: Any,
    metric_reader: Any,
    metrics_registry: Any,
    metrics_before: Any,
    consumer_operation: Any,
    run_state: dict[str, Any],
    run_ref: Any,
    artifact_store: Any,
    expected_environment: str,
) -> dict[str, Any]:
    """Recompute one controlled runtime witness from live code, CAS, spans, and SDK metrics.

    This proves only the tested in-process path; it cannot attest production
    operation selection, traffic, or SLI attainment.
    """
    repo_root = repo_root.resolve(strict=True)
    binding = _dependent_binding(repo_root, binding_id)
    resolved = {
        field: _resolve_operation_reference(repo_root, binding[field])
        for field in _OPERATION_REFERENCE_FIELDS
    }
    shared_operation, common_module, shared_source = resolved["shared_operation"]
    consumer, _, _ = resolved["consumer_operation"]
    callsite, _, callsite_source = resolved["callsite_operation"]
    callsite_code = _operation_code(binding["callsite_operation"], callsite)
    profile_provider, _, _ = resolved["profile_operation"]
    executor_provider, _, _ = resolved["executor_operation"]
    if consumer_operation is not consumer:
        raise ValueError("consumer_operation_identity_mismatch")
    if consumer.__name__ != str(binding["consumer_operation"]["symbol"]).split(".")[-1]:
        raise ValueError("consumer_operation_name_mismatch")
    observation_type = getattr(common_module, "_SharedExecutorCallObservation", None)
    if observation_type is None or not observations:
        raise ValueError("actual_common_call_observation_missing")
    if any(type(item) is not observation_type for item in observations):
        raise ValueError("observation_type_not_owned_by_loaded_common_module")
    related_candidates = tuple(item for item in observations if item.caller_code is callsite_code)
    if not related_candidates:
        raise ValueError("declared_callsite_not_observed")

    current_source_digest = hashlib.sha256(shared_source.read_bytes()).hexdigest()
    current_callsite_digest = hashlib.sha256(callsite_source.read_bytes()).hexdigest()
    from polisyos.scientist.orchestration.engine.component_identity import _code_sha256

    common_code_sha256 = _code_sha256(shared_operation)
    callsite_code_sha256 = _code_sha256(callsite)
    if str(binding["trace"]["event_name"]) != getattr(
        common_module, "SHARED_EXECUTOR_CALL_EVENT_NAME", None
    ):
        raise ValueError("trace_event_contract_mismatch")

    state_run_id = str(run_state.get("run_id", ""))
    report_ref_raw = run_state.get("reports_index", {}).get("workflow_report")
    if not state_run_id or not report_ref_raw:
        raise ValueError("workflow_report_reference_missing")
    artifact_ref_model, _, _ = resolved["artifact_ref_model"]
    report_ref = artifact_ref_model.model_validate(report_ref_raw)
    report_model, _, _ = resolved["report_model"]
    manifest_model, _, _ = resolved["manifest_model"]
    from polisyos.core.artifacts.canonical_profile import load_core_json_artifact

    report = report_model.model_validate(load_core_json_artifact(artifact_store, report_ref))
    manifest_ref = artifact_ref_model.model_validate(run_ref)
    run_manifest = manifest_model.model_validate(
        load_core_json_artifact(artifact_store, manifest_ref)
    )
    workflow_id = str(report.workflow_id)
    if (
        report.run_id != state_run_id
        or run_manifest.run_id != state_run_id
        or str(run_state.get("params", {}).get("workflow_id", workflow_id)) != workflow_id
    ):
        raise ValueError("cas_report_run_workflow_binding_mismatch")
    report_status = str(report.status)
    api_status = (
        str(binding["outcome_success_metric_status"])
        if report_status == str(binding["outcome_success_report_status"])
        else str(binding["outcome_failure_metric_status"])
    )

    objective_refs = binding["objective"]
    contracts = _package_contracts(repo_root)
    dependent_contract = contracts[str(binding["dependent_package"])][1]
    binding_runbooks = binding["runbook_paths"]
    instrument_names, scope_value, query_statuses = _objective_instrument_contract(
        repo_root,
        objective_refs,
        dependent_contract=dependent_contract,
        binding_runbooks=binding_runbooks,
    )
    counter_names = sorted(name for name in instrument_names if name.endswith("_total"))
    histogram_names = sorted(name for name in instrument_names if name.endswith("_bucket"))
    if len(counter_names) != 1 or len(histogram_names) != 1:
        raise ValueError("objective_instrument_pair_not_unique")
    if api_status not in query_statuses:
        raise ValueError("api_status_not_in_objective_denominator")
    config = getattr(metrics_registry, "_config", None)
    actual_environment = getattr(config, "environment", None)
    if not actual_environment or expected_environment != actual_environment:
        raise ValueError("expected_environment_not_bound_to_metrics_registry")
    counter_delta, before_histogram_count = _selected_metric_deltas(
        metrics_before,
        metrics_before,
        counter_name=counter_names[0],
        histogram_bucket_name=histogram_names[0],
        scope_attribute=str(objective_refs[0]["measurement_scope_attribute"]),
        scope_value=scope_value,
        workflow_id=workflow_id,
        environment=actual_environment,
    )
    if counter_delta or before_histogram_count:
        raise ValueError("controlled_metrics_baseline_is_not_empty")
    counter_name = counter_names[0]
    histogram_name = histogram_names[0].removesuffix("_bucket")
    baseline_has_eligible_samples = any(
        name in {counter_name, histogram_name}
        and dict(attributes).get(str(objective_refs[0]["measurement_scope_attribute"]))
        == scope_value
        and dict(attributes).get("workflow_id") == workflow_id
        and dict(attributes).get("env") == actual_environment
        and value != 0
        for (name, attributes), value in _metric_totals(metrics_before).items()
    )
    if baseline_has_eligible_samples:
        raise ValueError("controlled_metrics_baseline_is_not_empty")
    metrics_after = metric_reader.get_metrics_data()
    counter_delta, histogram_delta = _selected_metric_deltas(
        metrics_before,
        metrics_after,
        counter_name=counter_names[0],
        histogram_bucket_name=histogram_names[0],
        scope_attribute=str(objective_refs[0]["measurement_scope_attribute"]),
        scope_value=scope_value,
        workflow_id=workflow_id,
        environment=actual_environment,
    )
    if counter_delta != {api_status: 1} or histogram_delta != 1:
        raise ValueError("eligible_sli_observation_missing_or_duplicated")

    span_rows = tuple(span_exporter.get_finished_spans())
    by_context: dict[tuple[int, int], Any] = {}
    ambiguous_contexts: set[tuple[int, int]] = set()
    for span in span_rows:
        context = getattr(span, "context", None)
        if context is None or not getattr(context, "is_valid", False):
            continue
        key = (context.trace_id, context.span_id)
        if key in ambiguous_contexts:
            continue
        if key in by_context:
            by_context.pop(key)
            ambiguous_contexts.add(key)
        else:
            by_context[key] = span

    api_span_name = str(binding["trace"]["api_span_name"])
    api_run_attribute = str(binding["trace"]["api_run_id_attribute"])
    api_workflow_attribute = str(binding["trace"]["api_workflow_id_attribute"])

    def classify_api_root_for_span(span: Any) -> tuple[Any | None, str | None]:
        """Resolve the nearest API root, or report why ancestry is unknown."""
        trace_id = span.context.trace_id
        key = (trace_id, span.context.span_id)
        visited: set[tuple[int, int]] = set()
        while True:
            if key in visited:
                return None, "api_root_parent_cycle"
            visited.add(key)
            if key in ambiguous_contexts:
                return None, "span_identity_ambiguous"
            current = by_context.get(key)
            if current is None:
                return None, "api_root_parent_missing"
            if current.name == api_span_name:
                return current, None
            parent = getattr(current, "parent", None)
            if parent is None or not getattr(parent, "is_valid", False):
                return None, "api_root_parentage_refused"
            if parent.trace_id != trace_id:
                return None, "api_root_parent_trace_mismatch"
            key = (parent.trace_id, parent.span_id)

    selected_root_ids: set[tuple[int, int]] = set()
    selected_trace_ids: set[int] = set()
    root_membership_by_id: dict[tuple[int, int], str] = {}
    for span in span_rows:
        context = getattr(span, "context", None)
        if context is None or not getattr(context, "is_valid", False) or span.name != api_span_name:
            continue
        attributes = dict(span.attributes or {})
        run_value = attributes.get(api_run_attribute)
        workflow_value = attributes.get(api_workflow_attribute)
        has_run_value = run_value is not None and str(run_value).strip() != ""
        has_workflow_value = workflow_value is not None and str(workflow_value).strip() != ""
        run_matches = has_run_value and str(run_value) == state_run_id
        workflow_matches = has_workflow_value and str(workflow_value) == workflow_id
        if (has_run_value and not run_matches) or (has_workflow_value and not workflow_matches):
            membership = "other"
        elif run_matches and workflow_matches:
            membership = "selected"
        else:
            membership = "unknown"
        root_key = (context.trace_id, context.span_id)
        root_membership_by_id[root_key] = membership
        if membership == "selected":
            if root_key in ambiguous_contexts:
                raise ValueError("selected_api_root_identity_ambiguous")
            selected_root_ids.add(root_key)
            selected_trace_ids.add(context.trace_id)
    if not selected_root_ids:
        raise ValueError("selected_api_root_missing")

    def classify_api_root_membership(root: Any) -> str:
        """Return selected, proven-other, or unknown membership for an API root."""
        root_key = (root.context.trace_id, root.context.span_id)
        return root_membership_by_id.get(root_key, "unknown")

    related_list: list[Any] = []
    for item in related_candidates:
        span_key = (item.trace_id, item.span_id)
        if span_key in ambiguous_contexts:
            if item.trace_id in selected_trace_ids:
                raise ValueError("span_identity_ambiguous")
            continue
        span = by_context.get(span_key)
        if span is None:
            if item.trace_id in selected_trace_ids:
                raise ValueError("common_call_span_missing")
            continue
        root, ancestry_issue = classify_api_root_for_span(span)
        if ancestry_issue is not None:
            if item.trace_id in selected_trace_ids:
                raise ValueError(ancestry_issue)
            continue
        if root is None:
            if item.trace_id in selected_trace_ids:
                raise ValueError("api_root_ancestry_not_established")
            continue
        membership = classify_api_root_membership(root)
        if membership == "selected":
            related_list.append(item)
        elif membership == "unknown" and item.trace_id in selected_trace_ids:
            raise ValueError("api_root_membership_not_established")

    related = tuple(related_list)
    if not related:
        raise ValueError("declared_callsite_not_observed_under_selected_api_root")
    if any(item.caller_module != callsite.__module__ for item in related):
        raise ValueError("callsite_module_mismatch")
    if any(
        item.helper_function is not shared_operation
        or item.helper_code is not shared_operation.__code__
        or item.source_path != str(shared_source)
        or item.source_sha256 != current_source_digest
        or item.caller_code is not callsite_code
        or item.caller_source_path != str(callsite_source)
        or item.caller_source_sha256 != current_callsite_digest
        or item.target_function is None
        or item.target_code is not getattr(item.target_function, "__code__", None)
        or item.worker_is_executor is not True
        or item.worker_thread_ident == item.caller_thread_ident
        or item.trace_id == 0
        or item.span_id == 0
        for item in related
    ):
        raise ValueError("actual_common_code_or_worker_identity_mismatch")
    profile = profile_provider()
    executor = executor_provider()
    executor_ref = binding["executor_operation"]
    if any(
        item.profile is not profile
        or item.executor is not executor
        or getattr(executor, str(executor_ref["capacity_attribute"]), None) != profile.capacity
        or getattr(executor, str(executor_ref["queue_capacity_attribute"]), None)
        != profile.queue_capacity
        for item in related
    ):
        raise ValueError("calltime_profile_executor_join_mismatch")

    observations_by_span: dict[tuple[int, int], dict[str, Any]] = {}
    expected_call_ids: set[str] = set()
    for item in related:
        if not item.call_id or item.call_id in expected_call_ids:
            raise ValueError("duplicate_or_missing_live_common_call_id")
        expected_call_ids.add(item.call_id)
        span_key = (item.trace_id, item.span_id)
        observations_by_span.setdefault(span_key, {})[item.call_id] = item
        span = by_context.get(span_key)
        if span is None:
            raise ValueError("common_call_span_missing")
        attributes = dict(span.attributes or {})
        run_id_attribute = (
            api_run_attribute
            if span.name == api_span_name
            else str(binding["trace"]["node_run_id_attribute"])
        )
        workflow_id_attribute = (
            api_workflow_attribute
            if span.name == api_span_name
            else str(binding["trace"]["node_workflow_id_attribute"])
        )
        if (
            str(attributes.get(run_id_attribute, "")) != state_run_id
            or str(attributes.get(workflow_id_attribute, "")) != workflow_id
        ):
            raise ValueError("common_call_span_run_workflow_mismatch")
    if not observations_by_span:
        raise ValueError("api_root_for_live_common_calls_missing")
    event_name = str(binding["trace"]["event_name"])
    callsite_module = str(binding["callsite_operation"]["module"])
    callsite_code_id = hex(id(callsite_code))
    common_code_id = hex(id(shared_operation.__code__))
    selected_trace_ids = {trace_id for trace_id, _ in selected_root_ids}
    observations_by_call_id = {
        call_id: item for calls in observations_by_span.values() for call_id, item in calls.items()
    }
    expected_span_by_call_id = {
        call_id: span_key for span_key, calls in observations_by_span.items() for call_id in calls
    }
    seen_event_ids: set[str] = set()
    for span in span_rows:
        context = getattr(span, "context", None)
        valid_context = context is not None and getattr(context, "is_valid", False)
        span_key = (context.trace_id, context.span_id) if valid_context else None
        in_selected_trace = valid_context and context.trace_id in selected_trace_ids
        for event in getattr(span, "events", ()):
            event_attributes = dict(getattr(event, "attributes", None) or {})
            call_id = str(event_attributes.get("call_id", ""))
            observation = observations_by_call_id.get(call_id)
            claims_declared_callsite = (
                event_attributes.get("caller_module") == callsite_module
                and event_attributes.get("caller_code_object_id") == callsite_code_id
            )
            if observation is not None:
                # Expected IDs are reconciled across the exported span set,
                # independent of trace and selected-root membership.
                if getattr(event, "name", None) != event_name:
                    raise ValueError("common_call_event_name_mismatch")
                if span_key != expected_span_by_call_id[call_id]:
                    raise ValueError("common_call_event_attached_to_wrong_span")
                if not claims_declared_callsite or (
                    event_attributes.get("caller_source_sha256") != current_callsite_digest
                ):
                    raise ValueError("span_event_callsite_does_not_match_live_common_call")
                if call_id in seen_event_ids:
                    raise ValueError("duplicate_actual_common_call_event")
                if (
                    event_attributes.get("helper_module")
                    != str(binding["shared_operation"]["module"])
                    or event_attributes.get("helper_code_object_id") != common_code_id
                    or event_attributes.get("helper_source_sha256") != current_source_digest
                    or event_attributes.get("worker_is_executor") is not True
                    or event_attributes.get("status") != observation.status
                ):
                    raise ValueError("span_event_does_not_match_live_common_call")
                seen_event_ids.add(call_id)
                continue

            if not claims_declared_callsite or not in_selected_trace:
                continue
            # Unknown callsite events count only under a selected root. A valid
            # different root proves they are unrelated; unknown ancestry on the
            # selected trace is not such proof and therefore fails closed.
            event_root, ancestry_issue = classify_api_root_for_span(span)
            if ancestry_issue is not None:
                raise ValueError(ancestry_issue)
            if event_root is None:
                raise ValueError("api_root_ancestry_not_established")
            membership = classify_api_root_membership(event_root)
            if membership == "selected":
                raise ValueError("unobserved_common_call_event")
            if membership == "unknown":
                raise ValueError("api_root_membership_not_established")
    if seen_event_ids != expected_call_ids:
        raise ValueError("span_events_and_live_calls_not_bijective")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_fields = {
        "schema_version",
        "binding_id",
        "run_id",
        "workflow_id",
        "objective_names",
        "helper_source_sha256",
        "helper_code_sha256",
        "callsite_code_sha256",
        "call_ids",
        "profile",
        "report_status",
        "metric_status",
        "counter_count",
        "duration_count",
        "cas_report_ref",
        "run_manifest_ref",
        "evidence_scope",
        "deployment_receipt",
    }
    if type(receipt) is not dict or set(receipt) != receipt_fields:
        raise ValueError("controlled_receipt_schema_mismatch")
    expected_receipt = {
        "schema_version": _DEPENDENT_BINDING_VERSION,
        "binding_id": binding_id,
        "run_id": state_run_id,
        "workflow_id": workflow_id,
        "objective_names": [str(item["name"]) for item in objective_refs],
        "helper_source_sha256": current_source_digest,
        "helper_code_sha256": common_code_sha256,
        "callsite_code_sha256": callsite_code_sha256,
        "call_ids": sorted(expected_call_ids),
        "profile": {
            "revision": profile.revision,
            "capacity": profile.capacity,
            "queue_capacity": profile.queue_capacity,
            "source": profile.source,
            "authority": profile.authority,
        },
        "report_status": report_status,
        "metric_status": api_status,
        "counter_count": 1,
        "duration_count": histogram_delta,
        "cas_report_ref": report_ref.model_dump(mode="json"),
        "run_manifest_ref": manifest_ref.model_dump(mode="json"),
        "evidence_scope": "ephemeral_controlled_runtime_capture",
        "deployment_receipt": False,
    }
    if receipt != expected_receipt:
        raise ValueError("controlled_receipt_does_not_match_recomputed_sources")
    return {
        "status": "controlled_witness_verified",
        "binding_id": binding_id,
        "run_id": state_run_id,
        "call_count": len(related),
        "runtime_admission": "not_established",
        "production_attainment": "not_established",
        "evidence_scope": "ephemeral_controlled_runtime_capture",
        "durable_deployment_receipt": False,
    }


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
    if (
        not action_plan
        or action_due is None
        or not (plan_window_start <= action_due <= plan_completion_target)
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
    base = WORKSPACE_ROOT if path.startswith((".github/", "policy-engine/")) else repo_root
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
        write_scoped_report_text(output_path, output, encoding="utf-8", atomic=False)
    else:
        sys.stdout.write(output)
    if args.fail_closed and payload["finding_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
