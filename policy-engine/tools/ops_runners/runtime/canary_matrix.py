#!/usr/bin/env python3
"""List the PolicyOS production-quality canary matrix baseline."""

from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "policyos.canary_matrix.v1"

DIMENSIONS: dict[str, list[str]] = {
    "profile": ["dev", "research", "governed", "production"],
    "provider": ["simulated", "live_gonka_proxy"],
    "data": ["fixture", "canonical_production"],
    "scenario": [
        "public_golden",
        "negative",
        "adversarial",
        "hidden_quarantined",
    ],
    "ui": ["api_only", "dashboard_smoke"],
}

PROFILE_ENV: dict[str, dict[str, str]] = {
    "dev": {"POLISYOS_EXECUTION_PROFILE": "dev"},
    "research": {"POLISYOS_EXECUTION_PROFILE": "research"},
    "governed": {"POLISYOS_EXECUTION_PROFILE": "governed"},
    "production": {"POLISYOS_EXECUTION_PROFILE": "production"},
}
PROVIDER_MODE = {
    "simulated": "simulated",
    "live_gonka_proxy": "real",
}
PROVIDER_ENV: dict[str, dict[str, str]] = {
    "simulated": {"POLISYOS_LLM_SIMULATION_MODE": "1"},
    "live_gonka_proxy": {
        "POLISYOS_LLM_GATEWAY_BASE_URL": "https://proxy.gonka.gg/v1",
        "POLISYOS_LLM_GATEWAY_PROVIDER": "gonka_proxy",
        "POLISYOS_LLM_GATEWAY_API_KEY": "<required>",
    },
}
DATA_ROOT = {
    "fixture": "tests/_data/data_forge/ukraine_shadow",
    "canonical_production": "production_data",
}
SCENARIO_ID = {
    "public_golden": "ukraine_msme_wartime_credit_support",
    "negative": "deferred_negative_quality_regression_suite",
    "adversarial": "deferred_adversarial_quality_regression_suite",
    "hidden_quarantined": "hidden_quarantined_quality_suite",
}

COMMON_EVIDENCE_FILES = (
    "bundle.json",
    "request.sanitized.json",
    "env.sanitized.json",
    "artifacts.json",
    "job.json",
    "quality_evidence/quality_scorecard.json",
    "quality_evidence/golden_scenario_contract.json",
    "quality_evidence/normative_evidence.json",
    "quality_evidence/fabric_retrieval_trace.json",
    "quality_evidence/foundry_method_report.json",
    "quality_evidence/policy_grounding_matrix.json",
    "quality_evidence/conflict_check.json",
    "quality_evidence/provider_model_quality_ledger.json",
)
API_EVIDENCE_FILES = (
    "run.json",
    "agents.json",
    "timeline.json",
    "lineage.json",
)
PROFILE_EVIDENCE_FILES = {
    "dev": (),
    "research": ("performance.json",),
    "governed": ("performance.json",),
    "production": ("performance.json",),
}


def _lane_id(
    *,
    profile: str,
    provider: str,
    data: str,
    scenario: str,
    ui: str,
) -> str:
    return (
        f"profile-{profile}__provider-{provider}__data-{data}"
        f"__scenario-{scenario}__ui-{ui}"
    )


def _required_evidence_files(
    *,
    profile: str,
    provider: str,
    data: str,
    ui: str,
) -> list[str]:
    files = [
        *COMMON_EVIDENCE_FILES,
        *API_EVIDENCE_FILES,
        *PROFILE_EVIDENCE_FILES[profile],
    ]
    if provider == "live_gonka_proxy":
        files.append("provider_preflight.json")
    if data == "canonical_production":
        files.append("production_data_evidence.json")
    if ui == "dashboard_smoke":
        files.append("dashboard.json")
    return sorted(set(files))


def _classify_lane(
    *,
    profile: str,
    provider: str,
    data: str,
    scenario: str,
    ui: str,
) -> tuple[str, str, str | None]:
    if provider == "live_gonka_proxy":
        return (
            "quarantined",
            "requires live Gonka-compatible LLM proxy",
            "runtime-quality",
        )
    if scenario == "hidden_quarantined":
        return (
            "skipped",
            "hidden/quarantined scenario catalog is not checked into the repo",
            "runtime-quality",
        )
    if scenario == "negative":
        return (
            "deferred",
            "negative quality regression scenarios are not implemented yet",
            "runtime-quality",
        )
    if scenario == "adversarial":
        return (
            "deferred",
            "adversarial quality regression scenarios are not implemented yet",
            "runtime-quality",
        )
    if ui == "dashboard_smoke":
        return (
            "deferred",
            "dashboard smoke evidence harness is not wired into canary lanes yet",
            "runtime-dashboard",
        )
    if profile in {"governed", "production"}:
        return (
            "quarantined",
            "local governed/production lanes require PostgreSQL-backed control-plane state",
            "runtime-platform",
        )
    if profile == "research" and data == "fixture":
        return (
            "deferred",
            "fixture data cannot satisfy serious production-data quality closeout",
            "runtime-quality",
        )
    if profile == "dev" and data == "canonical_production":
        return (
            "deferred",
            "dev profile canonical-data lane is redundant with research closeout lane",
            "runtime-quality",
        )
    return (
        "ready",
        "covered by local_production_canary public golden API baseline",
        None,
    )


def _missing_or_deferred_gaps(
    *,
    profile: str,
    provider: str,
    data: str,
    scenario: str,
    ui: str,
) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if provider == "live_gonka_proxy":
        gaps.append(
            {
                "dimension": "provider",
                "value": provider,
                "status": "quarantined",
                "reason": "requires live Gonka-compatible LLM proxy",
                "owner": "runtime-quality",
            }
        )
    if scenario == "hidden_quarantined":
        gaps.append(
            {
                "dimension": "scenario",
                "value": scenario,
                "status": "skipped",
                "reason": "hidden/quarantined scenario catalog is not checked into the repo",
                "owner": "runtime-quality",
            }
        )
    elif scenario == "negative":
        gaps.append(
            {
                "dimension": "scenario",
                "value": scenario,
                "status": "deferred",
                "reason": "negative quality regression scenarios are not implemented yet",
                "owner": "runtime-quality",
            }
        )
    elif scenario == "adversarial":
        gaps.append(
            {
                "dimension": "scenario",
                "value": scenario,
                "status": "deferred",
                "reason": "adversarial quality regression scenarios are not implemented yet",
                "owner": "runtime-quality",
            }
        )
    if ui == "dashboard_smoke":
        gaps.append(
            {
                "dimension": "ui",
                "value": ui,
                "status": "deferred",
                "reason": "dashboard smoke evidence harness is not wired into canary lanes yet",
                "owner": "runtime-dashboard",
            }
        )
    if profile in {"governed", "production"} and provider != "live_gonka_proxy":
        gaps.append(
            {
                "dimension": "profile",
                "value": profile,
                "status": "quarantined",
                "reason": (
                    "local governed/production lanes require PostgreSQL-backed "
                    "control-plane state"
                ),
                "owner": "runtime-platform",
            }
        )
    if profile == "research" and data == "fixture":
        gaps.append(
            {
                "dimension": "data",
                "value": data,
                "status": "deferred",
                "reason": "fixture data cannot satisfy serious production-data quality closeout",
                "owner": "runtime-quality",
            }
        )
    if profile == "dev" and data == "canonical_production":
        gaps.append(
            {
                "dimension": "data",
                "value": data,
                "status": "deferred",
                "reason": "dev profile canonical-data lane is redundant with research closeout lane",
                "owner": "runtime-quality",
            }
        )
    return gaps


def _setup_error(
    *,
    profile: str,
    provider: str,
    owner: str | None,
) -> dict[str, Any] | None:
    if provider == "live_gonka_proxy" or profile not in {"governed", "production"}:
        return None
    profile_label = "Governed" if profile == "governed" else "Production"
    return {
        "type": "local_backing_service_unavailable",
        "code": "canary_postgresql_state_store_unavailable",
        "readiness_state": "not_ready",
        "phase": "setup",
        "service": "postgresql_control_state_store",
        "required_backend": "postgresql",
        "detected_backend": "sqlite_or_unset",
        "retryable": True,
        "message": (
            f"{profile_label} profile canary lanes require PostgreSQL-backed "
            "control-plane state before they can be declared ready."
        ),
        "owner": owner or "runtime-platform",
        "next_action": (
            "Start a PostgreSQL-backed control-plane state store or choose a "
            "non-production local lane."
        ),
    }


def _ci_safe(
    *,
    profile: str,
    provider: str,
    data: str,
    scenario: str,
    ui: str,
    status: str,
) -> bool:
    return (
        status == "ready"
        and profile == "dev"
        and provider == "simulated"
        and data == "fixture"
        and scenario == "public_golden"
        and ui == "api_only"
    )


def _closeout_required(
    *,
    profile: str,
    provider: str,
    data: str,
    scenario: str,
    ui: str,
    status: str,
) -> bool:
    return (
        status == "ready"
        and profile == "research"
        and provider == "simulated"
        and data == "canonical_production"
        and scenario == "public_golden"
        and ui == "api_only"
    )


def _runner(
    *,
    profile: str,
    provider: str,
    data: str,
    scenario: str,
    ui: str,
) -> dict[str, Any]:
    env = {
        **PROFILE_ENV[profile],
        **PROVIDER_ENV[provider],
    }
    if data == "canonical_production":
        env["POLISYOS_PRODUCTION_DATA_ROOT"] = DATA_ROOT[data]
    if ui == "dashboard_smoke":
        env["POLISYOS_DASHBOARD_SMOKE"] = "1"

    return {
        "kind": "python_module",
        "module": "tools.ops_runners.runtime.local_production_canary",
        "entrypoint": "main",
        "argv": [
            f"--mode={PROVIDER_MODE[provider]}",
            f"--execution-profile={profile}",
            f"--canary-kind={profile}",
            f"--production-data-root={DATA_ROOT[data]}",
            f"--quality-scenario={SCENARIO_ID[scenario]}",
            "--max-iterations=1",
        ],
        "env": env,
    }


def _quarantine(
    *,
    status: str,
    reason: str,
    owner: str | None,
) -> dict[str, str] | None:
    if status != "quarantined":
        return None
    return {
        "reason": reason,
        "owner": owner or "runtime-quality",
        "exit_criteria": (
            "Run manually with an approved Gonka-compatible proxy budget and attach "
            "the declared evidence bundle."
        ),
    }


def build_canary_lanes() -> list[dict[str, Any]]:
    """Return every declared Phase 0.4 matrix lane in stable order."""
    lanes: list[dict[str, Any]] = []
    for profile, provider, data, scenario, ui in product(
        DIMENSIONS["profile"],
        DIMENSIONS["provider"],
        DIMENSIONS["data"],
        DIMENSIONS["scenario"],
        DIMENSIONS["ui"],
    ):
        status, reason, owner = _classify_lane(
            profile=profile,
            provider=provider,
            data=data,
            scenario=scenario,
            ui=ui,
        )
        gaps = _missing_or_deferred_gaps(
            profile=profile,
            provider=provider,
            data=data,
            scenario=scenario,
            ui=ui,
        )
        ci_safe = _ci_safe(
            profile=profile,
            provider=provider,
            data=data,
            scenario=scenario,
            ui=ui,
            status=status,
        )
        closeout_required = _closeout_required(
            profile=profile,
            provider=provider,
            data=data,
            scenario=scenario,
            ui=ui,
            status=status,
        )
        lane = {
            "lane_id": _lane_id(
                profile=profile,
                provider=provider,
                data=data,
                scenario=scenario,
                ui=ui,
            ),
            "profile": profile,
            "provider": provider,
            "data": data,
            "scenario": scenario,
            "ui": ui,
            "status": status,
            "ci_safe": ci_safe,
            "closeout_required": closeout_required,
            "quarantine": _quarantine(
                status=status,
                reason=reason,
                owner=owner,
            ),
            "setup_error": _setup_error(
                profile=profile,
                provider=provider,
                owner=owner,
            ),
            "runner": _runner(
                profile=profile,
                provider=provider,
                data=data,
                scenario=scenario,
                ui=ui,
            ),
            "required_evidence_files": _required_evidence_files(
                profile=profile,
                provider=provider,
                data=data,
                ui=ui,
            ),
            "coverage": {
                "status": status,
                "missing_or_deferred_reason": reason,
                "missing_or_deferred_gaps": gaps,
                "owner": owner,
                "setup_error": _setup_error(
                    profile=profile,
                    provider=provider,
                    owner=owner,
                ),
            },
        }
        lanes.append(lane)
    return sorted(lanes, key=lambda item: str(item["lane_id"]))


def _summary(lanes: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = ("ready", "quarantined", "deferred", "skipped")
    return {
        "total_lanes": len(lanes),
        **{
            status: sum(1 for lane in lanes if lane["status"] == status)
            for status in statuses
        },
        "ci_safe": sum(1 for lane in lanes if lane["ci_safe"] is True),
        "closeout_required": sum(1 for lane in lanes if lane["closeout_required"] is True),
    }


def build_matrix_payload() -> dict[str, Any]:
    """Return the stable JSON payload emitted by the CLI."""
    lanes = build_canary_lanes()
    return {
        "schema_version": SCHEMA_VERSION,
        "dimensions": DIMENSIONS,
        "summary": _summary(lanes),
        "lanes": lanes,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _print_lanes(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print(
        "Canary matrix: "
        f"{summary['total_lanes']} lanes, "
        f"{summary['ready']} ready, "
        f"{summary['quarantined']} quarantined, "
        f"{summary['deferred']} deferred, "
        f"{summary['skipped']} skipped, "
        f"{summary['ci_safe']} CI-safe"
    )
    for lane in payload["lanes"]:
        ci_marker = " ci" if lane["ci_safe"] else ""
        print(f"{lane['lane_id']} [{lane['status']}{ci_marker}]")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the stable canary lane list.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path to write the canary matrix JSON payload.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = build_matrix_payload()
    if args.json_output:
        _write_json(Path(args.json_output), payload)
    if args.list or not args.json_output:
        _print_lanes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
