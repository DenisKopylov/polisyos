#!/usr/bin/env python3
"""Build runtime-backed Wave 5 Honest Diagnostics evidence reports."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.core.artifacts.store import FileSystemCAS  # noqa: E402
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore  # noqa: E402
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog  # noqa: E402
from polisyos.runtime.quality.metamorphic_controls import (  # noqa: E402
    PHASE56_CROSS_DOMAIN_SCENARIO_IDS,
    build_cross_domain_control_report,
    build_metamorphic_prompt_report,
    build_negative_control_report,
    build_scenario_semantic_binding_report,
)
from polisyos.runtime.quality.replay import (  # noqa: E402
    build_replay_manifest,
    explain_replay_drift,
)
from tools.ops_runners.runtime.quality_scenarios import (  # noqa: E402
    load_quality_scenario_contract,
)
from tools.quality.testing.runtime_resilience_matrix import (  # noqa: E402
    emit_runtime_resilience_matrix,
)
from tools.quality.validation.check_substrate_drift import (  # noqa: E402
    build_substrate_drift_payload,
)

SCHEMA_VERSION = "policyos.hds.wave5.closeout_evidence.v1"
GENERATED_AT = "2026-05-15T00:00:00Z"
DEFAULT_OUTPUT_DIR = Path("_build/honest-diagnostics/rebaseline/wave-5/evidence")


def build_wave5_evidence_payloads(*, repo_root: Path, output_dir: Path) -> dict[str, Any]:
    """Build all explicit Wave 5 evidence inputs consumed by strict coverage."""

    output_dir = output_dir.resolve()
    runtime_dir = output_dir / "runtime-owned"
    artifact_store = FileSystemCAS(runtime_dir / "cas").for_tenant(
        "tenant-wave5",
        cell_id="cell-wave5",
    )
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=runtime_dir / "control-plane.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )
    return {
        "metamorphic": build_wave5_metamorphic_report(),
        "resilience": emit_runtime_resilience_matrix(
            artifact_store=artifact_store,
            event_log=event_log,
            deterministic=True,
        ),
        "replay": build_wave5_replay_report(),
        "substrate_drift": build_substrate_drift_payload(repo_root=repo_root),
    }


def build_wave5_metamorphic_report() -> dict[str, Any]:
    scenario_reports: list[dict[str, Any]] = []
    for scenario_id in PHASE56_CROSS_DOMAIN_SCENARIO_IDS:
        contract = load_quality_scenario_contract(
            scenario_id,
            include_quarantined=True,
        )
        cross_domain = build_cross_domain_control_report(contract)
        metamorphic = build_metamorphic_prompt_report(contract)
        negative_controls = build_negative_control_report(contract)
        semantic_binding_report = build_scenario_semantic_binding_report(contract)
        scenario_reports.append(
            {
                "scenario_id": scenario_id,
                "status": _scenario_status(
                    cross_domain,
                    metamorphic,
                    negative_controls,
                    semantic_binding_report,
                ),
                "cross_domain": cross_domain,
                "metamorphic": metamorphic,
                "negative_controls": negative_controls,
                "semantic_binding_report": semantic_binding_report,
            }
        )
    return {
        "schema_version": "policyos.hds.wave5.metamorphic_controls_report.v1",
        "generated_at": GENERATED_AT,
        "status": (
            "pass"
            if all(report["status"] == "pass" for report in scenario_reports)
            else "fail"
        ),
        "scenario_count": len(scenario_reports),
        "scenario_reports": scenario_reports,
    }


def build_wave5_replay_report() -> dict[str, Any]:
    cases = [
        _replay_case(
            case_id="identical_runtime_evidence_replay",
            expected_status="match",
            explanation=explain_replay_drift(
                baseline_manifest=_serious_manifest(),
                replay_manifest=_serious_manifest(),
            ),
        ),
        _replay_case(
            case_id="accepted_low_impact_data_drift_ready",
            expected_status="accepted_drift",
            expected_readiness="pass",
            explanation=explain_replay_drift(
                baseline_manifest=_serious_manifest(),
                replay_manifest=_manifest_with_data_snapshot(_sha("a")),
                accepted_differences=[
                    {
                        "path": "$.data_refs.production_snapshot",
                        "drift_source": "data",
                        "impact": "low",
                        "reason": "Approved refresh of the production data snapshot.",
                    }
                ],
            ),
        ),
        _replay_case(
            case_id="newer_normpack_without_explanation_blocks",
            expected_status="unexplained_drift",
            expected_readiness="fail",
            explanation=explain_replay_drift(
                baseline_manifest=_serious_manifest(),
                replay_manifest=_manifest_with_normpack(_sha("b")),
            ),
        ),
        _replay_case(
            case_id="accepted_high_impact_registry_drift_non_ready",
            expected_status="accepted_drift_non_ready",
            expected_readiness="fail",
            expected_blocker="authority_replay_drift_unbounded",
            explanation=explain_replay_drift(
                baseline_manifest=_manifest_with_registry(
                    "invariant_registry",
                    version="2026.05",
                    ref=_sha("1"),
                ),
                replay_manifest=_manifest_with_registry(
                    "invariant_registry",
                    version="2026.06",
                    ref=_sha("2"),
                ),
                accepted_differences=[
                    {
                        "path_prefix": "$.registry_refs.invariant_registry",
                        "drift_source": "registry",
                        "impact": "high",
                        "reason": "Operator accepted a registry refresh.",
                    }
                ],
            ),
        ),
    ]
    return {
        "schema_version": "policyos.hds.wave5.replay_drift_report.v1",
        "generated_at": GENERATED_AT,
        "status": "pass" if all(case["status"] == "pass" for case in cases) else "fail",
        "cases": cases,
    }


def write_wave5_evidence_reports(
    *,
    repo_root: Path,
    output_dir: Path,
) -> dict[str, Path]:
    payloads = build_wave5_evidence_payloads(repo_root=repo_root, output_dir=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "metamorphic": output_dir / "wave5_metamorphic_report.json",
        "resilience": output_dir / "wave5_resilience_report.json",
        "replay": output_dir / "wave5_replay_report.json",
        "substrate_drift": output_dir / "substrate_drift_report.json",
    }
    for key, path in paths.items():
        atomic_write_text(path, _dump_json(payloads[key]))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "status": (
            "pass"
            if all(_payload_status(payloads[key]) == "pass" for key in paths)
            else "fail"
        ),
        "reports": {key: _rel(path, repo_root) for key, path in paths.items()},
    }
    atomic_write_text(output_dir / "wave5_evidence_summary.json", _dump_json(summary))
    return paths


def _scenario_status(*reports: dict[str, Any]) -> str:
    return "pass" if all(report.get("status") == "pass" for report in reports) else "fail"


def _replay_case(
    *,
    case_id: str,
    expected_status: str,
    explanation: dict[str, Any],
    expected_readiness: str = "pass",
    expected_blocker: str | None = None,
) -> dict[str, Any]:
    observed_status = str(explanation.get("status") or "")
    observed_readiness = str(explanation.get("production_readiness") or "")
    blocker = explanation.get("blocking_failure")
    blocker_code = str(blocker.get("code")) if isinstance(blocker, dict) else None
    matches = (
        observed_status == expected_status
        and observed_readiness == expected_readiness
        and (expected_blocker is None or blocker_code == expected_blocker)
    )
    return {
        "case_id": case_id,
        "status": "pass" if matches else "fail",
        "expected_status": expected_status,
        "observed_status": observed_status,
        "expected_production_readiness": expected_readiness,
        "observed_production_readiness": observed_readiness,
        "expected_blocker": expected_blocker,
        "observed_blocker": blocker_code,
        "summary": explanation.get("summary", {}),
    }


def _serious_manifest() -> dict[str, Any]:
    return build_replay_manifest(
        request_payload={"question": "Can this serious run be approved?"},
        git_sha="abc123",
        dependency_fingerprints={
            "uv.lock": _sha("1"),
            "pyproject.toml": _sha("2"),
        },
        feature_flags={"scientist_v2": True, "swarm": False},
        provider_model_metadata={
            "provider": "gonka_proxy",
            "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            "temperature": 0,
        },
        prompt_template_fingerprints={
            "formalizer": _sha("3"),
            "critic": _sha("4"),
        },
        data_refs={"production_snapshot": _sha("5")},
        source_refs={"fabric_trace": _sha("6")},
        norm_refs={"ua_credit_normpack": _sha("7")},
        cas_refs={"policy_output": _sha("8")},
        random_seeds={"python": 1729, "numpy": 31415},
        run_params={"max_iterations": 1, "run_budget_usd": 0.05},
        quality_scorecard_ref="quality_evidence/quality_scorecard.json",
        runtime_event_log={
            "runtime_event_log_ref": _sha("e"),
            "event_count": 7,
        },
        authority_envelopes=[
            {
                "evidence_id": "evidence-runtime-replay",
                "artifact_kind": "drift_explanation",
                "cas_ref": _sha("f"),
            }
        ],
        schema_compatibility_decisions={
            "scorecard": {"decision": "compatible", "registry_version": "2026.05"}
        },
        effective_mode_ledger={
            "mode_ledger_id": "mode-ledger-1",
            "effective_execution_profile": "production",
        },
        degradation_ledger={
            "degradation_ledger_ref": _sha("d"),
            "blocking_record_count": 0,
        },
        semantic_binding_ledger={
            "semantic_binding_ledger_ref": _sha("c"),
            "status": "pass",
        },
        prompt_tool_parser_ledger={
            "prompt_tool_ledger_ref": _sha("p"),
            "status": "pass",
        },
        assurance_case={
            "assurance_case_ref": _sha("q"),
            "claim": {"status": "supported"},
        },
        registry_refs={
            "invariant_registry": {"version": "2026.05", "ref": _sha("i")},
            "schema_compatibility_registry": {"version": "2026.05", "ref": _sha("s")},
            "source_truth_lattice": {"version": "2026.05", "ref": _sha("t")},
            "mode_fallback_policy": {"version": "2026.05", "ref": _sha("m")},
            "event_type_registry": {"version": "2026.05", "ref": _sha("v")},
        },
        execution_summary={
            "status": "completed",
            "run_id": "R_wave5_replay",
            "policy_output_ref": _sha("9"),
        },
        quality_summary={
            "quality_status": "pass",
            "overall_score": 1.0,
            "blocking_quality_failures": [],
        },
    )


def _manifest_with_data_snapshot(ref: str) -> dict[str, Any]:
    manifest = _serious_manifest()
    manifest["data_refs"] = {"production_snapshot": ref}
    return manifest


def _manifest_with_normpack(ref: str) -> dict[str, Any]:
    manifest = _serious_manifest()
    manifest["norm_refs"] = {"ua_credit_normpack": ref}
    return manifest


def _manifest_with_registry(key: str, *, version: str, ref: str) -> dict[str, Any]:
    manifest = _serious_manifest()
    manifest["registry_refs"] = {key: {"version": version, "ref": ref}}
    return manifest


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _payload_status(payload: dict[str, Any]) -> str:
    violations = payload.get("violations")
    if isinstance(violations, list):
        return "pass" if not violations else "fail"
    return str(payload.get("status") or "pass")


def _dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    try:
        paths = write_wave5_evidence_reports(
            repo_root=repo_root,
            output_dir=output_dir,
        )
    except Exception as exc:
        sys.stderr.write(f"wave5 evidence build failed: {exc}\n")
        return 2
    sys.stdout.write(
        "wave5 evidence reports written:\n"
        + "\n".join(f"- {key}: {_rel(path, repo_root)}" for key, path in paths.items())
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
