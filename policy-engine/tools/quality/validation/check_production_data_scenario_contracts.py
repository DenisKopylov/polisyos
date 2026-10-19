#!/usr/bin/env python3
"""Check that production-data contracts satisfy scenario source-family obligations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.runtime.http.services.control.production_data import (
    PRODUCTION_DATA_ROOT_ENV,
    load_production_data_manifest,
)
from polisyos.runtime.quality.production_data_contract_index import (
    SCENARIO_ADMISSIBLE_REQUIRED_FACETS,
    ProductionDataContractIndex,
)
from tools.ops_runners.runtime.canary_matrix import SCENARIO_ID
from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_QUALITY_SCENARIO_ID,
    QualityScenarioContractError,
    load_quality_scenario_contract,
)

SCHEMA_VERSION = "policyos.production_data_scenario_contract_check.v2"
DEFAULT_SCENARIO_ALIAS = "scenario-public_golden"


def build_report(
    *,
    repo_root: Path,
    production_data_root: Path | None = None,
    scenario: str = DEFAULT_SCENARIO_ALIAS,
) -> dict[str, Any]:
    """Build a scenario-admissibility report for production-data contracts."""

    resolved_root = _resolve_production_data_root(
        repo_root=repo_root,
        production_data_root=production_data_root,
    )
    scenario_id = _resolve_scenario_id(scenario)
    base_report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "fail",
        "scenario": scenario,
        "scenario_id": scenario_id,
        "production_data_root": str(resolved_root) if resolved_root else None,
        "required_scenario_facets": list(SCENARIO_ADMISSIBLE_REQUIRED_FACETS),
        "summary": {
            "requirements": 0,
            "satisfied": 0,
            "failed": 0,
            "blocked": 0,
            "finding_count": 0,
        },
        "requirement_source": None,
        "requirement_basis": None,
        "authority_eligible": False,
        "compiled_data_requirement_specs": [],
        "source_contract_bindings": [],
        "missing_scenario_source_families": [],
        "scenario_binding_findings": [],
        "findings": [],
    }
    if resolved_root is None:
        base_report["findings"] = [
            _finding(
                code="production_data_root_missing",
                message=(
                    "Production data root was not provided and could not be discovered "
                    "from POLISYOS_PRODUCTION_DATA_ROOT or repo-root/production_data."
                ),
                next_action=(
                    "Set POLISYOS_PRODUCTION_DATA_ROOT or pass --production-data-root "
                    "to the scenario contract checker."
                ),
            )
        ]
        base_report["summary"]["finding_count"] = 1
        return base_report

    manifest_path = resolved_root / "manifest.json"
    base_report["manifest_path"] = str(manifest_path)
    if not manifest_path.exists() or not load_production_data_manifest(resolved_root):
        base_report["findings"] = [
            _finding(
                code="production_data_manifest_missing",
                message=f"Production data manifest is missing or unreadable: {manifest_path}",
                next_action=(
                    "Provide a production_data/manifest.json before checking scenario "
                    "source-family admissibility."
                ),
                artifact_ref=str(manifest_path),
            )
        ]
        base_report["summary"]["finding_count"] = 1
        return base_report

    try:
        scenario_contract = load_quality_scenario_contract(scenario_id).get(
            "scenario_evidence_contract"
        )
    except QualityScenarioContractError as exc:
        base_report["findings"] = [
            _finding(
                code="scenario_contract_unavailable",
                message=str(exc),
                next_action="Fix the golden scenario catalog or pass a known scenario id.",
                details={"failures": exc.failures},
            )
        ]
        base_report["summary"]["finding_count"] = 1
        return base_report
    if not isinstance(scenario_contract, Mapping):
        base_report["findings"] = [
            _finding(
                code="scenario_evidence_contract_missing",
                message=f"Scenario {scenario_id} does not expose scenario_evidence_contract.",
                next_action="Normalize the scenario evidence contract before running this check.",
            )
        ]
        base_report["summary"]["finding_count"] = 1
        return base_report

    contract_report = ProductionDataContractIndex.load(resolved_root).build_scenario_binding_report(
        scenario_contract
    )
    construct_findings = _construct_capability_findings(contract_report)
    contract_findings = [*construct_findings, *_diagnostic_findings(contract_report)]
    basis_findings = _requirement_basis_findings(contract_report)
    hard_basis_findings = [item for item in basis_findings if item["severity"] == "error"]
    candidate_findings = [item for item in basis_findings if item["severity"] != "error"]
    findings = [*contract_findings, *hard_basis_findings, *candidate_findings]
    if contract_findings or hard_basis_findings:
        status = "fail"
    elif candidate_findings:
        status = "candidate"
    else:
        status = "pass"
    summary = dict(contract_report.get("summary") or {})
    summary["construct_capability_blockers"] = len(construct_findings)
    summary["candidate_limitations"] = len(candidate_findings)
    summary["finding_count"] = len(findings)
    return {
        **base_report,
        "status": status,
        "scenario_contract_id": contract_report.get("scenario_contract_id"),
        "requirement_source": contract_report.get("requirement_source"),
        "requirement_basis": contract_report.get("requirement_basis"),
        "requirement_basis_error": contract_report.get("requirement_basis_error"),
        "producer_report_ref": contract_report.get("producer_report_ref"),
        "subject_refs": list(contract_report.get("subject_refs") or []),
        "rule_version_refs": list(contract_report.get("rule_version_refs") or []),
        "input_content_hash": contract_report.get("input_content_hash"),
        "authority_eligible": False,
        "compiled_data_requirement_specs": list(
            contract_report.get("compiled_data_requirement_specs") or []
        ),
        "summary": summary,
        "source_families": list(contract_report.get("source_families") or []),
        "source_contract_bindings": list(contract_report.get("source_contract_bindings") or []),
        "missing_scenario_source_families": list(
            contract_report.get("missing_scenario_source_families") or []
        ),
        "construct_capability_blockers": construct_findings,
        "scenario_binding_findings": list(contract_report.get("scenario_binding_findings") or []),
        "findings": findings,
    }


def _requirement_basis_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Preserve unknown or consumer-asserted basis as non-passing candidate status."""

    basis_error = report.get("requirement_basis_error")
    if basis_error:
        return [
            _finding(
                code="production_data_requirement_basis_invalid",
                message="Scenario requirement basis is malformed or lacks producer binding.",
                next_action=(
                    "Recompile and persist the typed producer report with its subject/rule/content "
                    "binding."
                ),
                root_cause_class="production_data_requirement_basis",
                details={"basis_error": str(basis_error)},
            )
        ]
    basis = report.get("requirement_basis")
    if not isinstance(basis, Mapping):
        finding = _finding(
            code="production_data_requirement_basis_not_carried",
            message="Scenario contract has no validated producer-owned requirement basis.",
            next_action=(
                "Carry the typed compiler basis and its report/input bindings through "
                "normalization."
            ),
            root_cause_class="production_data_requirement_basis",
            severity="warning",
        )
        finding["status"] = "candidate"
        return [finding]
    state = str(basis.get("state") or "")
    grade = str(basis.get("basis_grade") or "")
    if state == "not_established":
        finding = _finding(
            code="production_data_requirement_basis_not_established",
            message="No complete data-requirement basis was established for this scenario.",
            next_action=(
                "Keep the result candidate with this limitation; provide governed requirements "
                "before any positive gate."
            ),
            root_cause_class="production_data_requirement_basis",
            severity="warning",
            details={
                "basis_source": basis.get("source"),
                "basis_grade": grade,
                "reason_codes": list(basis.get("reason_codes") or []),
                "source_refs": list(basis.get("source_refs") or []),
            },
        )
        finding["status"] = "candidate"
        return [finding]
    if state != "established" or grade != "recomputed":
        finding = _finding(
            code="production_data_requirement_basis_candidate_only",
            message=(
                "The declared requirement basis is candidate-scoped and cannot support a "
                "passing gate."
            ),
            next_action=(
                "Resolve the basis from governed, content-bound producer inputs before a positive "
                "scenario status."
            ),
            root_cause_class="production_data_requirement_basis",
            severity="warning",
            details={
                "basis_source": basis.get("source"),
                "basis_grade": grade,
                "reason_codes": list(basis.get("reason_codes") or []),
                "source_refs": list(basis.get("source_refs") or []),
            },
        )
        finding["status"] = "candidate"
        return [finding]
    return []


def _compiled_construct_bindings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for spec in report.get("compiled_data_requirement_specs") or []:
        if not isinstance(spec, Mapping):
            continue
        metadata = spec.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        binding = metadata.get("capability_binding")
        if isinstance(binding, Mapping) and binding.get("construct_ref"):
            bindings.append(dict(binding))
    return bindings


def _construct_capability_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    blocker_statuses = {
        "selected_proxy_with_limitation",
        "selected_with_conflict_marker",
        "selected_context_only",
        "selected_simulation_only",
    }
    for binding in _compiled_construct_bindings(report):
        status = str(binding.get("status") or "").strip()
        if not (status.startswith("blocked_") or status in blocker_statuses):
            continue
        construct_ref = str(binding.get("construct_ref") or "construct:unknown")
        findings.append(
            _finding(
                code="production_data_construct_capability_blocker",
                message=(
                    f"Construct-resolved capability binding for {construct_ref} returned {status}."
                ),
                next_action=(
                    "Use the resolver acquisition strategies, limitations, and "
                    "review queues rather than restoring scenario-family authority."
                ),
                root_cause_class="production_data_construct_capability",
                requirement_id=binding.get("requirement_id"),
                construct_ref=construct_ref,
                capability_ref=binding.get("selected_capability_ref"),
                blocker_code=status,
                blocked_reasons=list(binding.get("blocked_reasons") or []),
                limitations=list(binding.get("limitations") or []),
                acquisition_strategies=list(binding.get("acquisition_strategies") or []),
                rejected_alternatives=list(binding.get("rejected_alternatives") or []),
            )
        )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    production_data_root = args.production_data_root
    if production_data_root is not None and not production_data_root.is_absolute():
        production_data_root = repo_root / production_data_root
    report = build_report(
        repo_root=repo_root,
        production_data_root=production_data_root,
        scenario=args.scenario,
    )
    if args.json_output is not None:
        output = args.json_output
        if not output.is_absolute():
            output = repo_root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    else:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.require_passing and report["status"] != "pass":
        return 2
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--production-data-root", type=Path, default=None)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO_ALIAS)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--require-passing", action="store_true")
    return parser.parse_args(argv)


def _resolve_production_data_root(
    *,
    repo_root: Path,
    production_data_root: Path | None,
) -> Path | None:
    if production_data_root is not None:
        return production_data_root.expanduser()
    configured = os.getenv(PRODUCTION_DATA_ROOT_ENV)
    if configured:
        configured_path = Path(configured).expanduser()
        return configured_path if configured_path.is_absolute() else repo_root / configured_path
    candidate = repo_root / "production_data"
    return candidate if candidate.exists() else None


def _resolve_scenario_id(scenario: str) -> str:
    normalized = str(scenario or "").strip() or DEFAULT_QUALITY_SCENARIO_ID
    if normalized.startswith("scenario-"):
        normalized = normalized.removeprefix("scenario-")
    return SCENARIO_ID.get(normalized, normalized)


def _diagnostic_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in report.get("scenario_binding_findings") or []:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "").strip().casefold()
        if status == "satisfied":
            continue
        expected_family = str(item.get("expected_family") or "unknown").strip()
        if status == "blocked":
            findings.append(
                _finding(
                    code="production_data_scenario_family_missing",
                    message=(
                        f"No curated production-data contract satisfies scenario "
                        f"source family {expected_family}."
                    ),
                    next_action=(
                        "Package an admissible curated data contract and source binding "
                        "for this scenario source family before Fabric selection."
                    ),
                    requirement_id=item.get("requirement_id"),
                    expected_family=expected_family,
                    missing_facets=list(item.get("missing_facets") or []),
                    rejected_candidate_source_families=list(
                        item.get("rejected_candidate_source_families") or []
                    ),
                )
            )
        else:
            findings.append(
                _finding(
                    code="production_data_scenario_contract_incomplete",
                    message=(
                        f"Curated production-data contract for {expected_family} "
                        "is present but not scenario-admissible."
                    ),
                    next_action=(
                        "Fill the missing OpenLineage-like facets or export them as "
                        "claim-bound limitations before allowing source selection."
                    ),
                    requirement_id=item.get("requirement_id"),
                    expected_family=expected_family,
                    candidate_ref=item.get("candidate_ref"),
                    missing_facets=list(item.get("missing_facets") or []),
                    claim_bound_limitations=list(item.get("claim_bound_limitations") or []),
                )
            )
    return findings


def _finding(
    *,
    code: str,
    message: str,
    next_action: str,
    severity: str = "error",
    root_cause_class: str = "production_data_scenario_admissibility",
    artifact_ref: str | None = None,
    details: Mapping[str, Any] | None = None,
    **extra: object,
) -> dict[str, Any]:
    payload = {
        "status": "fail",
        "severity": severity,
        "code": code,
        "message": message,
        "root_cause_class": root_cause_class,
        "next_action": next_action,
    }
    if artifact_ref:
        payload["artifact_ref"] = artifact_ref
    if details:
        payload["details"] = dict(details)
    payload.update({key: value for key, value in extra.items() if value not in (None, "")})
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
