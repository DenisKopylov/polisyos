"""Shared JSON/reporting helpers for benchmark entrypoints."""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Callable

from benchmarks.comparators.stack import REQUIRED_ACCEPTANCE_COMPARATORS, OPTIONAL_LEGACY_COMPARATORS

WORKFLOW_LEVELS = (
    "expressible",
    "identifiable",
    "estimable_or_bounded",
    "audit_trace",
    "reproducible",
)


def dataclasses_to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {k: dataclasses_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, enum.Enum):
        return obj.value
    if hasattr(obj, "model_dump"):
        return dataclasses_to_dict(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {str(k): dataclasses_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [dataclasses_to_dict(v) for v in obj]
    if hasattr(obj, "tolist"):
        try:
            return obj.tolist()
        except Exception:
            pass
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def build_preflight(
    *,
    mode: str,
    benchmark_tier: str | None = None,
    data_source: str,
    dependency_status: dict[str, Any] | None = None,
    comparator_status: dict[str, Any] | None = None,
    degraded_reasons: list[str] | None = None,
    dataset_family: str | None = None,
    batch_id: str | None = None,
    run_id: str | None = None,
    estimator_profile: str | None = None,
) -> dict[str, Any]:
    preflight = {
        "run_id": run_id or os.environ.get("BENCH_RUN_ID"),
        "mode": mode,
        "benchmark_tier": benchmark_tier or os.environ.get("BENCH_TIER", "local_evidence"),
        "data_source": data_source,
        "dataset_family": dataset_family,
        "batch_id": batch_id,
        "estimator_profile": estimator_profile or os.environ.get("BENCH_ESTIMATOR_PROFILE", "default"),
        "dependency_status": dependency_status or {},
        "comparator_status": comparator_status or {},
        "degraded_reasons": degraded_reasons or [],
        "environment": _environment_metadata(),
        "benchmark_env_spec": _benchmark_env_spec(),
        "installed_comparator_versions": _installed_comparator_versions(),
        "data_manifest_path": _detect_data_manifest_path(),
        "data_manifest_hash": _detect_data_manifest_hash(),
    }
    preflight["run_config_hash"] = _stable_hash(
        {
            key: value
            for key, value in preflight.items()
            if key != "run_config_hash"
        }
    )
    return preflight


def build_report_payload(
    report: Any,
    *,
    suite_id: str,
    mode: str,
    preflight: dict[str, Any],
    sub_circuit: str | None = None,
    include_case_payload: bool = False,
    dataset_family: str | None = None,
    batch_id: str | None = None,
    aggregate_metrics: dict[str, Any] | None = None,
    standardized_metrics: dict[str, Any] | None = None,
    method_groups: dict[str, Any] | None = None,
    benchmark_family: str | None = None,
    proof_class: str | None = None,
    claim_profile_targets: list[str] | None = None,
    workflow_levels: list[str] | None = None,
    competitor_gap: dict[str, Any] | None = None,
    literature_anchor: str | list[str] | None = None,
    evidence_bundle_complete: bool | None = None,
    public_claim_eligible: bool | None = None,
    dataset_regime: str | None = None,
    baseline_snapshot_ref: str | None = None,
    regression_guard: dict[str, Any] | None = None,
    method_manifest: dict[str, Any] | None = None,
    gate_method_set: list[str] | None = None,
    flagship_presence: dict[str, Any] | None = None,
    exploratory_methods: list[str] | None = None,
    selection_manifest: dict[str, Any] | None = None,
    overlap_diagnostics: dict[str, Any] | None = None,
    calibration_metrics: dict[str, Any] | None = None,
    prioritization_metrics: dict[str, Any] | None = None,
    dataset_group_summaries: dict[str, Any] | None = None,
    blockers: list[str] | None = None,
    case_details_builder: Callable[[Any], dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in report.cases:
        raw_status = str(case.verdict.value if hasattr(case.verdict, "value") else case.verdict).strip().lower()
        status = {
            "pass": "passed",
            "fail": "failed",
            "timeout": "timeout",
            "skip": "skipped",
            "error": "error",
        }.get(raw_status, raw_status)
        payload = {
            "case_id": case.name,
            "name": case.name,
            "status": status,
            "circuit": case.circuit.value,
            "verdict": case.verdict.value,
            "elapsed_s": case.elapsed_s,
            "memory_delta_mb": case.memory_delta_mb,
            "error_msg": case.error_msg,
            "proof_step_count": len(case.proof_steps),
            "is_identifiable_gt": case.is_identifiable_gt,
            "is_identifiable_pred": case.is_identifiable_pred,
            "formula_correct": case.formula_correct,
            "runtime": {
                "elapsed_s": case.elapsed_s,
                "memory_delta_mb": case.memory_delta_mb,
                "proof_step_count": len(case.proof_steps),
            },
        }
        if case_details_builder is not None:
            payload.update(dataclasses_to_dict(case_details_builder(case) or {}))
        if include_case_payload:
            payload["result_payload"] = dataclasses_to_dict(case.result_payload)
        cases.append(payload)

    output = {
        "suite_id": suite_id,
        "run_id": preflight.get("run_id"),
        "mode": mode,
        "benchmark_tier": preflight.get("benchmark_tier", "local_evidence"),
        "core_circuits": [c.value for c in report.circuits],
        "sub_circuit": sub_circuit,
        "data_source": preflight.get("data_source"),
        "estimator_profile": preflight.get("estimator_profile", "default"),
        "dependency_status": dataclasses_to_dict(preflight.get("dependency_status", {})),
        "comparator_status": dataclasses_to_dict(preflight.get("comparator_status", {})),
        "degraded_reasons": list(preflight.get("degraded_reasons", [])),
        "dataset_family": dataset_family if dataset_family is not None else preflight.get("dataset_family"),
        "batch_id": batch_id if batch_id is not None else preflight.get("batch_id"),
        "n_total": report.n_total(),
        "n_passed": report.n_passed(),
        "pass_rate": report.n_passed() / report.n_total() if report.n_total() else 0.0,
        "scores": dataclasses_to_dict(report.circuit_scores),
        "cases": cases,
        "blockers": list(blockers) if blockers is not None else [case.name for case in report.blocker_cases()],
        "preflight": preflight,
        "aggregate_metrics": dataclasses_to_dict(aggregate_metrics or {}),
        "standardized_metrics": dataclasses_to_dict(standardized_metrics or {}),
        "method_groups": dataclasses_to_dict(method_groups or {}),
        "method_manifest": dataclasses_to_dict(method_manifest if method_manifest is not None else (method_groups or {})),
        "gate_method_set": list(gate_method_set or []),
        "flagship_presence": dataclasses_to_dict(flagship_presence or {}),
        "exploratory_methods": list(exploratory_methods or []),
        "selection_manifest": dataclasses_to_dict(selection_manifest or {}),
        "overlap_diagnostics": dataclasses_to_dict(overlap_diagnostics or {}),
        "calibration_metrics": dataclasses_to_dict(calibration_metrics or {}),
        "prioritization_metrics": dataclasses_to_dict(prioritization_metrics or {}),
        "dataset_group_summaries": dataclasses_to_dict(dataset_group_summaries or {}),
        "benchmark_family": benchmark_family,
        "proof_class": proof_class or "standard",
        "claim_profile_targets": list(claim_profile_targets or []),
        "workflow_levels": list(workflow_levels or []),
        "competitor_gap": dataclasses_to_dict(competitor_gap or {}),
        "literature_anchor": dataclasses_to_dict(literature_anchor),
        "evidence_bundle_complete": evidence_bundle_complete,
        "public_claim_eligible": public_claim_eligible,
        "dataset_regime": dataset_regime,
        "baseline_snapshot_ref": baseline_snapshot_ref,
        "regression_guard": dataclasses_to_dict(regression_guard or {}),
    }
    if extra:
        output.update(extra)
    return output


def print_preflight(preflight: dict[str, Any]) -> None:
    print("--- preflight ---")
    print(json.dumps(preflight, indent=2))


def validate_publication_payload(payload: dict[str, Any]) -> list[str]:
    """Validate proof-oriented benchmark payload fields.

    The checks are intentionally additive and lightweight: they do not block
    ordinary smoke reports, but they do mark claim-ready reports incomplete
    when proof-carrying metadata is missing.
    """
    errors: list[str] = []
    suite_id = str(payload.get("suite_id") or "")
    proof_class = str(payload.get("proof_class") or "standard")
    claim_targets = payload.get("claim_profile_targets")

    if claim_targets is not None and not isinstance(claim_targets, list):
        errors.append("claim_profile_targets must be a list")

    if payload.get("public_claim_eligible") and not payload.get("literature_anchor"):
        errors.append("public_claim_eligible suites require literature_anchor")

    if proof_class == "capability_gap" or suite_id.startswith("capability_"):
        workflow_levels = payload.get("workflow_levels")
        competitor_gap = payload.get("competitor_gap")
        if workflow_levels != list(WORKFLOW_LEVELS):
            errors.append("capability_gap suites require canonical workflow_levels ordering")
        if not isinstance(competitor_gap, dict) or not competitor_gap:
            errors.append("capability_gap suites require a non-empty competitor_gap matrix")
        if payload.get("evidence_bundle_complete") is not True:
            errors.append("capability_gap suites require evidence_bundle_complete=true")
        if not payload.get("literature_anchor"):
            errors.append("capability_gap suites require literature_anchor")
        if payload.get("public_claim_eligible") is not True:
            errors.append("capability_gap suites require public_claim_eligible=true")

    if suite_id.startswith("discovery_"):
        if not payload.get("baseline_snapshot_ref"):
            errors.append("discovery suites require baseline_snapshot_ref")
        regression_guard = payload.get("regression_guard")
        if not isinstance(regression_guard, dict) or not regression_guard:
            errors.append("discovery suites require non-empty regression_guard")

    if suite_id in {"policy_natural_experiments", "policy_did_interference"}:
        if not payload.get("benchmark_family"):
            errors.append("policy benchmark suites require benchmark_family")
        if not payload.get("dataset_regime"):
            errors.append("policy benchmark suites require dataset_regime")
        if not payload.get("baseline_snapshot_ref"):
            errors.append("policy benchmark suites require baseline_snapshot_ref")
        regression_guard = payload.get("regression_guard")
        if not isinstance(regression_guard, dict) or not regression_guard:
            errors.append("policy benchmark suites require non-empty regression_guard")
        aggregate = payload.get("aggregate_metrics", {})
        if not isinstance(aggregate.get("ranking_summary"), dict):
            errors.append("policy benchmark suites require aggregate_metrics.ranking_summary")
        if not isinstance(aggregate.get("case_groups"), dict):
            errors.append("policy benchmark suites require aggregate_metrics.case_groups")

    if suite_id.startswith("estimation_"):
        aggregate = payload.get("aggregate_metrics", {})
        scorecard = aggregate.get("flagship_scorecard")
        if isinstance(scorecard, dict) and scorecard.get("flagship_status") == "flagship_missing":
            errors.append("estimation suites require flagship presence in every case payload")
        if not isinstance(payload.get("blockers"), list):
            errors.append("estimation suites require blockers list")
        if not isinstance(payload.get("selection_manifest"), dict):
            errors.append("estimation suites require selection_manifest")
        if not isinstance(payload.get("overlap_diagnostics"), dict):
            errors.append("estimation suites require overlap_diagnostics")
        if not isinstance(payload.get("calibration_metrics"), dict):
            errors.append("estimation suites require calibration_metrics")

    if suite_id == "estimation_realcause":
        group_summaries = payload.get("dataset_group_summaries")
        if not isinstance(group_summaries, dict) or not group_summaries:
            errors.append("estimation_realcause requires non-empty dataset_group_summaries")

    if suite_id == "hte_interpretable":
        if not isinstance(payload.get("blockers"), list):
            errors.append("hte_interpretable requires blockers list")
        if not isinstance(payload.get("selection_manifest"), dict):
            errors.append("hte_interpretable requires selection_manifest")
        if not isinstance(payload.get("calibration_metrics"), dict):
            errors.append("hte_interpretable requires calibration_metrics")
        if not isinstance(payload.get("prioritization_metrics"), dict):
            errors.append("hte_interpretable requires prioritization_metrics")
        cases = payload.get("cases", [])
        if not isinstance(cases, list) or not cases:
            errors.append("hte_interpretable requires non-empty cases")
        else:
            for case in cases:
                if not isinstance(case, dict):
                    errors.append("hte_interpretable cases must be objects")
                    break
                for field in ("case_id", "status", "acceptance", "metrics", "runtime"):
                    if field not in case:
                        errors.append(f"hte_interpretable cases require {field}")
                        break

    if proof_class == "stress_evidence" or suite_id == "adversarial_symbolic_stress":
        aggregate = payload.get("aggregate_metrics", {})
        if not payload.get("benchmark_family"):
            errors.append("stress_evidence suites require benchmark_family")
        if not isinstance(aggregate.get("accuracy"), dict):
            errors.append("stress_evidence suites require aggregate_metrics.accuracy")
        if not payload.get("baseline_snapshot_ref"):
            errors.append("stress_evidence suites require baseline_snapshot_ref")

    return errors


def _environment_metadata() -> dict[str, Any]:
    return {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def _benchmark_env_spec() -> str | None:
    spec_path = Path(__file__).resolve().parent / "comparators" / "research_acceptance_environment.yml"
    return str(spec_path) if spec_path.exists() else None


def _installed_comparator_versions() -> dict[str, str | None]:
    packages = {
        **dict(REQUIRED_ACCEPTANCE_COMPARATORS),
        **dict(OPTIONAL_LEGACY_COMPARATORS),
    }
    versions: dict[str, str | None] = {}
    for label, dist_name in packages.items():
        try:
            versions[label] = importlib.metadata.version(dist_name)
        except Exception:
            versions[label] = None
    return versions


def _detect_data_manifest_path() -> str | None:
    explicit = os.environ.get("BENCH_DATA_MANIFEST")
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return str(path)
    candidates: list[Path] = []
    for env_var in ("ACIC_DATA_DIR", "LBIDD_DATA_DIR", "REALCAUSE_DATA_DIR"):
        raw = os.environ.get(env_var)
        if not raw:
            continue
        path = Path(raw).expanduser()
        candidates.extend(
            [
                path / "manifest.json",
                path.parent / "manifest.json",
                path.parent.parent / "manifest.json",
            ]
        )
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return str(candidate)
    return None


def _detect_data_manifest_hash() -> str | None:
    manifest_path = _detect_data_manifest_path()
    if manifest_path is None:
        return None
    try:
        return hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()
    except Exception:
        return None


def _stable_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(dataclasses_to_dict(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
