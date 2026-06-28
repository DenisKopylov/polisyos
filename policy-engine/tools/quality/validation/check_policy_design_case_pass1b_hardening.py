#!/usr/bin/env python3
"""Validate Policy Design Case Pass 1B hardening coverage."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.config_release_hardening import (  # noqa: E402
    CONFIG_RELEASE_HARDENING_CONTRACT_ID,
    CONFIG_RELEASE_HARDENING_PDD_IDS,
    CONFIG_RELEASE_HARDENING_RECORD_FAMILY,
    CONFIG_RELEASE_HARDENING_SCHEMA_VERSION,
)
from polisyos.runtime.quality.external_client_surface import (  # noqa: E402
    EXTERNAL_CLIENT_SURFACE_PDDS,
    EXTERNAL_CLIENT_SURFACE_RECORD_FAMILY,
    EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
)
from polisyos.runtime.quality.observability_static_audit import (  # noqa: E402
    DORMANT_CAPABILITY_INVENTORY_RECORD_KEY,
    DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION,
    FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY,
    FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION,
    SKIP_CAUSALITY_LEDGER_RECORD_KEY,
    SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION,
)
from polisyos.runtime.quality.tenant_cas_approval_governance import (  # noqa: E402
    PASS1B_HARDENING_READINESS_CHECK,
    PASS1B_HARDENING_SCORECARD_GATE,
    PASS1B_PDD_REQUIRED_SURFACES,
    PASS1B_REQUIRED_CASE_BINDING_FIELDS,
    PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID,
    PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS,
    PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY,
    PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION,
)
from polisyos.runtime.quality.policy_design_case import (  # noqa: E402
    DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS,
    POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS,
    SUBSTRATE_RESIDUAL_BINDINGS_READINESS_CHECK,
    SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_FAMILY,
    SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_KEY,
    SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION,
)

SCHEMA_VERSION = "policyos.policy_design_case.pass1b_hardening_coverage.v1"
TOOL_NAME = "quality.validation.check-policy-design-case-pass1b-hardening"
DEFAULT_OUTPUT = Path(
    "_build/policy-design-case/rebaseline/wave-32/pass1b_hardening_coverage.json"
)

PASS1B_GROUP_EXPECTED_PDDS: dict[str, tuple[str, ...]] = {
    "tenant_cas_approval_governance": PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS,
    "substrate_residual": POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS,
    "observability_orchestration_static_audit": ("PDD-017", "PDD-018", "PDD-045"),
    "config_release_deployment_migration": CONFIG_RELEASE_HARDENING_PDD_IDS,
    "external_dependency": ("PDD-073", "PDD-085", "PDD-102"),
    "client_surface": ("PDD-089", "PDD-091", "PDD-092", "PDD-093", "PDD-094"),
}

_EXTERNAL_CLIENT_SURFACE_SPLIT = (
    PASS1B_GROUP_EXPECTED_PDDS["external_dependency"]
    + PASS1B_GROUP_EXPECTED_PDDS["client_surface"]
)
if set(_EXTERNAL_CLIENT_SURFACE_SPLIT) != set(EXTERNAL_CLIENT_SURFACE_PDDS):
    raise RuntimeError("Phase 28.5 Pass 1B closeout split drifted from runtime contract.")

PASS1B_GROUP_EXPECTED_SURFACES: dict[str, dict[str, tuple[str, ...]]] = {
    "tenant_cas_approval_governance": PASS1B_PDD_REQUIRED_SURFACES,
    "substrate_residual": {
        binding.diagnostic_id: tuple(binding.record_facets)
        for binding in DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS
    },
    "observability_orchestration_static_audit": {
        "PDD-017": (DORMANT_CAPABILITY_INVENTORY_RECORD_KEY,),
        "PDD-018": (SKIP_CAUSALITY_LEDGER_RECORD_KEY,),
        "PDD-045": (FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY,),
    },
    "config_release_deployment_migration": {
        "PDD-072": ("deployment_parity",),
        "PDD-075": ("release_supply_chain",),
        "PDD-076": ("persisted_state_migration",),
        "PDD-079": ("quarantine_shim_lifecycle",),
        "PDD-080": ("generated_surface_drift",),
        "PDD-081": ("runbook_automation",),
        "PDD-082": ("retention_deletion_replay",),
    },
    "external_dependency": {
        "PDD-073": ("connector_acquisition",),
        "PDD-085": ("plugin_capability_isolation",),
        "PDD-102": ("external_dependency_contracts", "external_evidence_provenance"),
    },
    "client_surface": {
        "PDD-089": ("offline_mutation_authority",),
        "PDD-091": ("collaboration_attribution",),
        "PDD-092": ("assistant_composer_provenance",),
        "PDD-093": ("bureaucratic_rendering_export",),
        "PDD-094": ("client_persistence_privacy",),
    },
}


def _pdd_closeout_row(
    *,
    phase: str,
    owner: str,
    evidence_contract: str,
    scorecard_gate: str,
    readiness_check: str,
    surfaces: Sequence[str],
) -> dict[str, Any]:
    return {
        "phase": phase,
        "owner": owner,
        "implemented_evidence_contract": evidence_contract,
        "scorecard_gate": scorecard_gate,
        "readiness_check": readiness_check,
        "closeout_gate": scorecard_gate,
        "remaining_blocker": "none",
        "coverage_kind": "concrete_evidence_contract",
        "surfaces": list(surfaces),
        "authority_boundary": "record_is_evidence_only",
    }


def _pdd_closeout_rows(
    *,
    phase: str,
    pdd_required_surfaces: Mapping[str, Sequence[str]],
    owner: str,
    evidence_contract: str,
    scorecard_gate: str,
    readiness_check: str,
) -> dict[str, dict[str, Any]]:
    return {
        pdd_id: _pdd_closeout_row(
            phase=phase,
            owner=owner,
            evidence_contract=evidence_contract,
            scorecard_gate=scorecard_gate,
            readiness_check=readiness_check,
            surfaces=surfaces,
        )
        for pdd_id, surfaces in pdd_required_surfaces.items()
    }


PASS1B_HARDENING_GROUPS: dict[str, dict[str, Any]] = {
    "tenant_cas_approval_governance": {
        "title": "Tenant, CAS, approval, and governance hardening",
        "phase": "28.1",
        "record_key": PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY,
        "record_family": PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID.removeprefix(
            "policy_design_case."
        ),
        "schema_version": PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION,
        "pdds": PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS,
        "required_case_bindings": tuple(PASS1B_REQUIRED_CASE_BINDING_FIELDS),
        "pdd_required_surfaces": PASS1B_PDD_REQUIRED_SURFACES,
        "scorecard_gate": PASS1B_HARDENING_SCORECARD_GATE,
        "readiness_check": PASS1B_HARDENING_READINESS_CHECK,
        "owner": "team-quality-closeout",
        "implemented_evidence_contract": (
            PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID
        ),
        "remaining_blocker": "none",
        "authority_boundary": "record_is_evidence_only",
        "pdd_closeout": _pdd_closeout_rows(
            phase="28.1",
            pdd_required_surfaces=PASS1B_PDD_REQUIRED_SURFACES,
            owner="team-quality-closeout",
            evidence_contract=PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID,
            scorecard_gate=PASS1B_HARDENING_SCORECARD_GATE,
            readiness_check=PASS1B_HARDENING_READINESS_CHECK,
        ),
    },
    "substrate_residual": {
        "title": "Substrate-residual verification",
        "phase": "28.2",
        "record_key": SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_KEY,
        "record_family": SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_FAMILY,
        "schema_version": SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION,
        "pdds": POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_DIAGNOSTICS,
        "required_case_bindings": tuple(
            surface
            for surfaces in PASS1B_GROUP_EXPECTED_SURFACES["substrate_residual"].values()
            for surface in surfaces
        ),
        "pdd_required_surfaces": PASS1B_GROUP_EXPECTED_SURFACES["substrate_residual"],
        "scorecard_gate": "policy_design_substrate_residual_verification",
        "readiness_check": SUBSTRATE_RESIDUAL_BINDINGS_READINESS_CHECK,
        "owner": "team-runtime-quality",
        "implemented_evidence_contract": SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION,
        "remaining_blocker": "none",
        "authority_boundary": "record_is_evidence_only",
        "pdd_closeout": {
            binding.diagnostic_id: _pdd_closeout_row(
                phase="28.2",
                owner=binding.owner,
                evidence_contract=SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION,
                scorecard_gate="policy_design_substrate_residual_verification",
                readiness_check=binding.readiness_check,
                surfaces=binding.record_facets,
            )
            for binding in DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS
        },
    },
    "observability_orchestration_static_audit": {
        "title": "Observability and orchestration static audit",
        "phase": "28.3",
        "record_key": "observability_orchestration_static_audit",
        "record_family": "capability_mode_and_fallback_selection.v1",
        "schema_version": "policyos.runtime.policy_design_case.observability_static_audit.v1",
        "pdds": PASS1B_GROUP_EXPECTED_PDDS["observability_orchestration_static_audit"],
        "required_case_bindings": tuple(
            surface
            for surfaces in PASS1B_GROUP_EXPECTED_SURFACES[
                "observability_orchestration_static_audit"
            ].values()
            for surface in surfaces
        ),
        "pdd_required_surfaces": PASS1B_GROUP_EXPECTED_SURFACES[
            "observability_orchestration_static_audit"
        ],
        "scorecard_gate": "policy_design_observability_orchestration_static_audit",
        "readiness_check": "policy_design_case.observability_orchestration_static_audit",
        "owner": "team-observability",
        "implemented_evidence_contract": ";".join(
            (
                DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION,
                SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION,
                FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION,
            )
        ),
        "remaining_blocker": "none",
        "authority_boundary": "record_is_evidence_only",
        "pdd_closeout": {
            "PDD-017": _pdd_closeout_row(
                phase="28.3",
                owner="team-observability",
                evidence_contract=DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION,
                scorecard_gate="policy_design_observability_orchestration_static_audit",
                readiness_check="policy_design_case.observability_orchestration_static_audit",
                surfaces=(DORMANT_CAPABILITY_INVENTORY_RECORD_KEY,),
            ),
            "PDD-018": _pdd_closeout_row(
                phase="28.3",
                owner="team-runtime-quality",
                evidence_contract=SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION,
                scorecard_gate="policy_design_observability_orchestration_static_audit",
                readiness_check="policy_design_case.observability_orchestration_static_audit",
                surfaces=(SKIP_CAUSALITY_LEDGER_RECORD_KEY,),
            ),
            "PDD-045": _pdd_closeout_row(
                phase="28.3",
                owner="team-quality-closeout",
                evidence_contract=FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION,
                scorecard_gate="policy_design_observability_orchestration_static_audit",
                readiness_check="policy_design_case.observability_orchestration_static_audit",
                surfaces=(FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY,),
            ),
        },
    },
    "config_release_deployment_migration": {
        "title": "Config, release, deployment, and migration hardening",
        "phase": "28.4",
        "record_key": "config_release_deployment_migration_hardening",
        "record_family": CONFIG_RELEASE_HARDENING_RECORD_FAMILY,
        "schema_version": CONFIG_RELEASE_HARDENING_SCHEMA_VERSION,
        "pdds": CONFIG_RELEASE_HARDENING_PDD_IDS,
        "required_case_bindings": tuple(
            surface
            for surfaces in PASS1B_GROUP_EXPECTED_SURFACES[
                "config_release_deployment_migration"
            ].values()
            for surface in surfaces
        ),
        "pdd_required_surfaces": PASS1B_GROUP_EXPECTED_SURFACES[
            "config_release_deployment_migration"
        ],
        "scorecard_gate": "policy_design_config_release_deployment_migration_hardening",
        "readiness_check": "policy_design_case.config_release_deployment_migration",
        "owner": "team-core-audit",
        "implemented_evidence_contract": CONFIG_RELEASE_HARDENING_CONTRACT_ID,
        "remaining_blocker": "none",
        "authority_boundary": "record_is_evidence_only",
        "pdd_closeout": _pdd_closeout_rows(
            phase="28.4",
            pdd_required_surfaces=PASS1B_GROUP_EXPECTED_SURFACES[
                "config_release_deployment_migration"
            ],
            owner="team-core-audit",
            evidence_contract=CONFIG_RELEASE_HARDENING_CONTRACT_ID,
            scorecard_gate="policy_design_config_release_deployment_migration_hardening",
            readiness_check="policy_design_case.config_release_deployment_migration",
        ),
    },
    "external_dependency": {
        "title": "External, plugin, and dependency hardening",
        "phase": "28.5",
        "record_key": "external_plugin_dependency_client_surface",
        "record_family": EXTERNAL_CLIENT_SURFACE_RECORD_FAMILY,
        "schema_version": EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
        "pdds": PASS1B_GROUP_EXPECTED_PDDS["external_dependency"],
        "required_case_bindings": tuple(
            surface
            for surfaces in PASS1B_GROUP_EXPECTED_SURFACES["external_dependency"].values()
            for surface in surfaces
        ),
        "pdd_required_surfaces": PASS1B_GROUP_EXPECTED_SURFACES["external_dependency"],
        "scorecard_gate": "policy_design_external_client_surface",
        "readiness_check": "policy_design_case.external_dependency",
        "owner": "team-runtime-platform",
        "implemented_evidence_contract": EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
        "remaining_blocker": "none",
        "authority_boundary": "record_is_evidence_only",
        "pdd_closeout": _pdd_closeout_rows(
            phase="28.5",
            pdd_required_surfaces=PASS1B_GROUP_EXPECTED_SURFACES["external_dependency"],
            owner="team-runtime-platform",
            evidence_contract=EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
            scorecard_gate="policy_design_external_client_surface",
            readiness_check="policy_design_case.external_dependency",
        ),
    },
    "client_surface": {
        "title": "Client-surface authority hardening",
        "phase": "28.5",
        "record_key": "external_plugin_dependency_client_surface",
        "record_family": EXTERNAL_CLIENT_SURFACE_RECORD_FAMILY,
        "schema_version": EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
        "pdds": PASS1B_GROUP_EXPECTED_PDDS["client_surface"],
        "required_case_bindings": tuple(
            surface
            for surfaces in PASS1B_GROUP_EXPECTED_SURFACES["client_surface"].values()
            for surface in surfaces
        ),
        "pdd_required_surfaces": PASS1B_GROUP_EXPECTED_SURFACES["client_surface"],
        "scorecard_gate": "policy_design_external_client_surface",
        "readiness_check": "policy_design_case.client_surface_authority",
        "owner": "team-runtime-dashboard",
        "implemented_evidence_contract": EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
        "remaining_blocker": "none",
        "authority_boundary": "record_is_evidence_only",
        "pdd_closeout": _pdd_closeout_rows(
            phase="28.5",
            pdd_required_surfaces=PASS1B_GROUP_EXPECTED_SURFACES["client_surface"],
            owner="team-runtime-dashboard",
            evidence_contract=EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION,
            scorecard_gate="policy_design_external_client_surface",
            readiness_check="policy_design_case.client_surface_authority",
        ),
    },
}


def build_pass1b_hardening_payload(
    *,
    repo_root: Path = REPO_ROOT,
    groups: Mapping[str, Mapping[str, Any]] = PASS1B_HARDENING_GROUPS,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Build a static coverage report for Pass 1B hardening rows."""

    repo_root = repo_root.resolve()
    group_payloads: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    expected_group_ids = set(PASS1B_GROUP_EXPECTED_PDDS)

    for group_id in sorted(expected_group_ids - set(groups)):
        issues.append(
            _issue(
                "policy_design_pass1b_hardening_group_missing",
                f"Pass 1B hardening coverage is missing group {group_id}.",
                group_id=group_id,
            )
        )
        for pdd_id in PASS1B_GROUP_EXPECTED_PDDS[group_id]:
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_missing",
                    f"Pass 1B hardening group {group_id} is missing {pdd_id}.",
                    group_id=group_id,
                    pdd_id=pdd_id,
                )
            )

    for group_id, group in groups.items():
        pdds = _string_tuple(group.get("pdds"))
        required_case_bindings = _string_tuple(group.get("required_case_bindings"))
        pdd_required_surfaces = _normalize_pdd_required_surfaces(
            group.get("pdd_required_surfaces")
        )
        pdd_closeout = _normalize_pdd_closeout(group.get("pdd_closeout"))
        expected_pdds = set(PASS1B_GROUP_EXPECTED_PDDS.get(group_id, ()))
        expected_surfaces = PASS1B_GROUP_EXPECTED_SURFACES.get(group_id, {})
        if not expected_pdds:
            issues.append(
                _issue(
                    "policy_design_pass1b_hardening_group_unknown",
                    f"Pass 1B hardening coverage references unknown group {group_id}.",
                    group_id=group_id,
                )
            )
        missing_pdds = sorted(expected_pdds - set(pdds))
        extra_pdds = sorted(set(pdds) - expected_pdds)
        expected_case_bindings = {
            surface
            for surfaces in expected_surfaces.values()
            for surface in surfaces
        }
        missing_surfaces = sorted(
            expected_case_bindings - set(required_case_bindings)
        )
        issues.extend(_group_contract_issues(group_id, group))
        for pdd_id in missing_pdds:
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_missing",
                    f"Pass 1B hardening group is missing {pdd_id}.",
                    group_id=group_id,
                    pdd_id=pdd_id,
                )
            )
        for pdd_id in extra_pdds:
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_unknown",
                    f"Pass 1B hardening group references unknown {pdd_id}.",
                    group_id=group_id,
                    pdd_id=pdd_id,
                )
            )
        for surface in missing_surfaces:
            issues.append(
                _issue(
                    "policy_design_pass1b_case_binding_missing",
                    f"Pass 1B hardening group is missing case binding {surface}.",
                    group_id=group_id,
                    surface=surface,
                )
            )
        for pdd_id, surfaces in expected_surfaces.items():
            actual_surfaces = set(pdd_required_surfaces.get(pdd_id, ()))
            missing = sorted(set(surfaces) - actual_surfaces)
            if missing:
                issues.append(
                    _issue(
                        "policy_design_pass1b_pdd_surface_missing",
                        (
                            f"Pass 1B hardening group is missing {pdd_id} "
                            f"surfaces: {', '.join(missing)}."
                        ),
                        group_id=group_id,
                        pdd_id=pdd_id,
                        surface=",".join(missing),
                    )
                )
        for pdd_id in sorted(expected_pdds):
            closeout = pdd_closeout.get(pdd_id)
            if not isinstance(closeout, Mapping):
                issues.append(
                    _issue(
                        "policy_design_pass1b_pdd_closeout_missing",
                        f"Pass 1B {pdd_id} is missing concrete closeout coverage.",
                        group_id=group_id,
                        pdd_id=pdd_id,
                    )
                )
                continue
            issues.extend(
                _pdd_closeout_issues(
                    group_id=group_id,
                    pdd_id=pdd_id,
                    row=closeout,
                    expected_phase=str(group.get("phase") or ""),
                    expected_surfaces=expected_surfaces.get(pdd_id, ()),
                )
            )
        for pdd_id in sorted(set(pdd_closeout) - expected_pdds):
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_closeout_unknown",
                    f"Pass 1B hardening closeout references unknown {pdd_id}.",
                    group_id=group_id,
                    pdd_id=pdd_id,
                )
            )
        group_payloads[group_id] = {
            "title": str(group.get("title") or group_id),
            "phase": str(group.get("phase") or "28.1"),
            "record_key": str(group.get("record_key") or ""),
            "record_family": str(group.get("record_family") or ""),
            "schema_version": str(group.get("schema_version") or ""),
            "pdds": list(pdds),
            "required_case_bindings": list(required_case_bindings),
            "pdd_required_surfaces": {
                pdd_id: list(surfaces)
                for pdd_id, surfaces in sorted(pdd_required_surfaces.items())
            },
            "scorecard_gate": str(group.get("scorecard_gate") or ""),
            "readiness_check": str(group.get("readiness_check") or ""),
            "owner": str(group.get("owner") or ""),
            "implemented_evidence_contract": str(
                group.get("implemented_evidence_contract") or ""
            ),
            "remaining_blocker": str(group.get("remaining_blocker") or ""),
            "authority_boundary": str(group.get("authority_boundary") or ""),
            "pdd_closeout": {
                pdd_id: _payload_closeout_row(row)
                for pdd_id, row in sorted(pdd_closeout.items())
            },
        }
    status = "fail" if issues else "pass"
    output = output_path if output_path is not None else repo_root / DEFAULT_OUTPUT
    implemented_pdds = {
        f"{group_id}:{pdd}"
        for group_id, group in group_payloads.items()
        for pdd in group["pdds"]
        if pdd in PASS1B_GROUP_EXPECTED_PDDS.get(group_id, ())
        and _pdd_has_concrete_closeout(group["pdd_closeout"].get(pdd))
    }
    required_pdd_count = sum(len(pdds) for pdds in PASS1B_GROUP_EXPECTED_PDDS.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "repo_root": str(repo_root),
        "wave": "32",
        "phase": "32.1",
        "groups": group_payloads,
        "summary": {
            "group_count": len(group_payloads),
            "pdd_count": required_pdd_count,
            "implemented_pdd_count": len(implemented_pdds),
            "issue_count": len(issues),
        },
        "issues": issues,
        "authority_policy": {
            "governance_audit_client_release_projection_records": "evidence_only",
            "authority_minting_allowed": False,
        },
        "output": {"path": str(output), "format": "json"},
        "verification": {
            "acceptance_commands": [
                (
                    "uv run pytest tests/unit/runtime/quality/"
                    "test_policy_design_case_pass1b_hardening.py "
                    "tests/repo_quality/tools/test_policy_design_case_pass1b_hardening.py -q"
                ),
                (
                    "uv run python tools/quality/validation/"
                    "check_policy_design_case_pass1b_hardening.py --repo-root . "
                    "--output _build/policy-design-case/rebaseline/wave-32/"
                    "pass1b_hardening_coverage.json"
                ),
            ]
        },
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    """Return deterministic JSON for CLI output."""

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--output-format",
        choices=("json", "text"),
        default="json",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Compatibility flag for closeout loops; this checker already exits nonzero on fail.",
    )
    args = parser.parse_args(argv)

    output_path = (
        args.output
        if args.output is not None
        else args.repo_root / DEFAULT_OUTPUT
    )
    payload = build_pass1b_hardening_payload(
        repo_root=args.repo_root,
        output_path=output_path,
    )
    atomic_write_text(output_path, dump_json(payload))
    if args.output_format == "json":
        sys.stdout.write(dump_json(payload))
    else:
        sys.stdout.write(f"{payload['status']}: {payload['summary']}\n")
    return 0 if payload["status"] == "pass" else 1


def _group_contract_issues(
    group_id: str,
    group: Mapping[str, Any],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for field in (
        "owner",
        "implemented_evidence_contract",
        "scorecard_gate",
        "readiness_check",
        "remaining_blocker",
        "record_key",
        "record_family",
        "schema_version",
    ):
        if not _text(group.get(field)):
            issues.append(
                _issue(
                    "policy_design_pass1b_group_contract_field_missing",
                    f"Pass 1B hardening group {group_id} is missing {field}.",
                    group_id=group_id,
                )
            )
    owner = _text(group.get("owner"))
    if owner and not owner.startswith("team-"):
        issues.append(
            _issue(
                "policy_design_pass1b_group_owner_invalid",
                "Pass 1B hardening group must name a team owner.",
                group_id=group_id,
            )
        )
    scorecard_gate = _text(group.get("scorecard_gate"))
    if scorecard_gate and not scorecard_gate.startswith("policy_design"):
        issues.append(
            _issue(
                "policy_design_pass1b_group_scorecard_gate_invalid",
                "Pass 1B hardening group must name a scorecard gate.",
                group_id=group_id,
            )
        )
    readiness_check = _text(group.get("readiness_check"))
    if readiness_check and not readiness_check.startswith("policy_design_case."):
        issues.append(
            _issue(
                "policy_design_pass1b_group_readiness_check_invalid",
                "Pass 1B hardening group must name a readiness check.",
                group_id=group_id,
            )
        )
    if group.get("authority_boundary") != "record_is_evidence_only":
        issues.append(
            _issue(
                "policy_design_pass1b_authority_boundary_missing",
                (
                    "Pass 1B closeout records must be evidence-only and cannot "
                    "mint governance, audit, client, release, or projection authority."
                ),
                group_id=group_id,
            )
        )
    return issues


def _pdd_closeout_issues(
    *,
    group_id: str,
    pdd_id: str,
    row: Mapping[str, Any],
    expected_phase: str,
    expected_surfaces: Sequence[str],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if _generic_hardening_note_only(row):
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_generic_hardening_note",
                (
                    f"Pass 1B {pdd_id} is only covered by a generic hardening note; "
                    "it needs concrete evidence, owner, gate, and blocker coverage."
                ),
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    required_fields = (
        "phase",
        "owner",
        "implemented_evidence_contract",
        "scorecard_gate",
        "readiness_check",
        "closeout_gate",
        "remaining_blocker",
        "coverage_kind",
    )
    for field in required_fields:
        if not _text(row.get(field)):
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_closeout_field_missing",
                    f"Pass 1B {pdd_id} closeout is missing {field}.",
                    group_id=group_id,
                    pdd_id=pdd_id,
                )
            )
    phase = _text(row.get("phase"))
    if phase and expected_phase and phase != expected_phase:
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_closeout_phase_mismatch",
                f"Pass 1B {pdd_id} closeout must map to phase {expected_phase}.",
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    owner = _text(row.get("owner"))
    if owner and not owner.startswith("team-"):
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_closeout_owner_invalid",
                f"Pass 1B {pdd_id} closeout must name a team owner.",
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    scorecard_gate = _text(row.get("scorecard_gate"))
    closeout_gate = _text(row.get("closeout_gate"))
    if scorecard_gate and not scorecard_gate.startswith("policy_design"):
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_closeout_gate_invalid",
                f"Pass 1B {pdd_id} closeout must name a scorecard gate.",
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    if closeout_gate and not closeout_gate.startswith("policy_design"):
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_closeout_gate_invalid",
                f"Pass 1B {pdd_id} closeout must name a closeout gate.",
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    readiness_check = _text(row.get("readiness_check"))
    if readiness_check and not readiness_check.startswith("policy_design_case."):
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_closeout_readiness_check_invalid",
                f"Pass 1B {pdd_id} closeout must name a readiness check.",
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    if _text(row.get("coverage_kind")) != "concrete_evidence_contract":
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_closeout_kind_invalid",
                f"Pass 1B {pdd_id} closeout must be concrete evidence coverage.",
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    if row.get("authority_boundary") != "record_is_evidence_only":
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_authority_boundary_missing",
                f"Pass 1B {pdd_id} closeout must be evidence-only.",
                group_id=group_id,
                pdd_id=pdd_id,
            )
        )
    surfaces = set(_string_tuple(row.get("surfaces")))
    missing_surfaces = sorted(set(expected_surfaces) - surfaces)
    if missing_surfaces:
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_closeout_surface_missing",
                (
                    f"Pass 1B {pdd_id} closeout is missing surfaces: "
                    f"{', '.join(missing_surfaces)}."
                ),
                group_id=group_id,
                pdd_id=pdd_id,
                surface=",".join(missing_surfaces),
            )
        )
    return issues


def _normalize_pdd_closeout(value: object) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, Mapping)
    }


def _payload_closeout_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["surfaces"] = list(_string_tuple(row.get("surfaces")))
    return payload


def _pdd_has_concrete_closeout(row: object) -> bool:
    return (
        isinstance(row, Mapping)
        and _text(row.get("coverage_kind")) == "concrete_evidence_contract"
        and bool(_text(row.get("implemented_evidence_contract")))
        and bool(_text(row.get("owner")))
        and bool(_text(row.get("closeout_gate")))
        and bool(_text(row.get("remaining_blocker")))
        and not _generic_hardening_note_only(row)
    )


def _generic_hardening_note_only(row: Mapping[str, Any]) -> bool:
    note = (_text(row.get("generic_note")) or "").casefold()
    if "hardening" not in note:
        return False
    concrete_fields = (
        "implemented_evidence_contract",
        "scorecard_gate",
        "readiness_check",
        "closeout_gate",
        "remaining_blocker",
        "coverage_kind",
    )
    return any(not _text(row.get(field)) for field in concrete_fields)


def _normalize_pdd_required_surfaces(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): _string_tuple(item)
        for key, item in value.items()
    }


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(
            text
            for item in value
            if isinstance(item, str) and (text := item.strip())
        )
    return ()


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _issue(
    code: str,
    message: str,
    *,
    group_id: str,
    pdd_id: str | None = None,
    surface: str | None = None,
) -> dict[str, str]:
    issue = {
        "code": code,
        "group_id": group_id,
        "message": message,
        "severity": "error",
    }
    if pdd_id is not None:
        issue["pdd_id"] = pdd_id
    if surface is not None:
        issue["surface"] = surface
    return issue


if __name__ == "__main__":
    raise SystemExit(main())
