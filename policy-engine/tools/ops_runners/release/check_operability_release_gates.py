"""Fail-closed Phase 6.3 operability, release, and supply-chain gates."""

from __future__ import annotations

import argparse
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
DEFAULT_CONTRACT = REPO_ROOT / "architecture" / "operability_release_supply_chain_gates.toml"
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
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = _resolve(repo_root, contract_path)
    contract = _read_toml(contract_path)
    findings: list[Finding] = []

    findings.extend(_check_conversion_contract(repo_root, contract_path, contract))
    operability_summary, operability_findings = _check_operability(repo_root)
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


def _check_operability(repo_root: Path) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    components_index = _read_toml(repo_root / "ops" / "components" / "index.toml")
    runbooks = _read_toml(repo_root / "architecture" / "runbook_coverage.toml")
    observability = _read_toml(repo_root / "architecture" / "component_observability.toml")
    components = {str(item.get("id", "")): item for item in components_index.get("component", [])}
    public_stable = _public_stable_components(repo_root)

    missing_components = sorted(public_stable - set(components))
    for component in missing_components:
        findings.append(
            Finding(
                "slo-runbook-coverage",
                component,
                "public-stable component is missing from ops/components/index.toml",
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
                for field in ("exception_reason", "exception_expires"):
                    if not str(component.get(field, "")).strip():
                        findings.append(
                            Finding("slo-runbook-coverage", component_id, f"`{field}` is required")
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

    alert_summary, alert_findings = _check_alert_coverage(repo_root, runbooks)
    findings.extend(alert_findings)
    return (
        {
            "component_count": len(components),
            "public_stable_component_count": len(public_stable),
            "observability_contract_count": len(observability_contracts),
            **alert_summary,
        },
        findings,
    )


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
    surface = _read_toml(repo_root / "architecture" / "public_surface.toml")
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


def _as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


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
