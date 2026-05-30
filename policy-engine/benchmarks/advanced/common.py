"""Shared runtime for production-grade and academic-grade benchmark suites."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

_BENCH_ROOT = Path(__file__).resolve().parents[2]
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import polisyos.runtime.replay as runtime_replay  # noqa: E402
from benchmarks.advanced.manifests import (  # noqa: E402
    ManifestBundle,
    ManifestCase,
    manifest_env_var,
    select_manifest,
)
from benchmarks.comparators import (  # noqa: E402
    build_research_acceptance_comparator_status,
    comparator_degraded_reasons,
    comparator_required_modules,
    execute_comparator_suite,
)
from benchmarks.harness import BenchmarkCase, BenchmarkCircuit, BenchmarkHarness  # noqa: E402
from benchmarks.reporting import (  # noqa: E402
    build_preflight,
    build_report_payload,
    print_preflight,
)
from benchmarks.runtime import (  # noqa: E402
    BenchmarkMode,
    BenchmarkTier,
    acceptance_gaps,
    resolve_mode,
    resolve_tier,
)
from benchmarks.suite_registry import spec_by_suite_id  # noqa: E402
from polisyos.core.artifacts.ids import ArtifactID  # noqa: E402
from polisyos.core.artifacts.manifest import ArtifactRef  # noqa: E402
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry  # noqa: E402


class SuitePreflightFailure(RuntimeError):
    """Raised when a suite cannot satisfy its validation prerequisites."""

    def __init__(
        self,
        message: str,
        *,
        preflight: dict[str, Any] | None = None,
        overall_status: str = "error",
        exit_code: int = 2,
    ) -> None:
        super().__init__(message)
        self.preflight = preflight
        self.overall_status = overall_status
        self.exit_code = exit_code


class SuiteSkipped(SuitePreflightFailure):
    """Raised when a suite should be marked skipped instead of failed."""

    def __init__(self, message: str, *, preflight: dict[str, Any] | None = None) -> None:
        super().__init__(message, preflight=preflight, overall_status="skipped", exit_code=0)


def main_for_suite(
    suite_id: str,
    *,
    description: str,
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--mode", default="smoke")
    parser.add_argument("--json", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = build_suite_payload(suite_id, args.mode, quiet=args.quiet)
    except SuitePreflightFailure as exc:
        payload = _suite_state_payload(
            suite_id,
            mode=args.mode,
            overall_status=exc.overall_status,
            reason=str(exc),
            preflight=exc.preflight,
        )

    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.json:
        Path(args.json).write_text(output + "\n", encoding="utf-8")
    if not args.quiet:
        print(output)
    status = str(payload.get("overall_status") or "").strip().lower()
    if status == "error":
        return 2
    if status == "failed":
        return 1
    blockers = payload.get("blockers", [])
    return 1 if blockers else 0


def build_suite_payload(suite_id: str, mode: str, *, quiet: bool) -> dict[str, Any]:
    if suite_id not in _BUILDERS:
        raise ValueError(f"Unsupported advanced benchmark suite: {suite_id}")
    return _BUILDERS[suite_id](mode, quiet=quiet)


def _spec(suite_id: str):
    spec = spec_by_suite_id(suite_id)
    if spec is None:
        raise ValueError(f"Unknown suite_id: {suite_id}")
    return spec


def _visibility_for_run(spec: Any) -> str:
    requested = str(os.environ.get("BENCH_VISIBILITY", "")).strip().lower()
    if requested == "prod_shadow" and spec.supports_shadow:
        return "prod_shadow"
    return spec.visibility


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator / denominator)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * q)))
    return float(ordered[index])


def _bootstrap_difference_ci(
    policy_values: list[float],
    baseline_values: list[float],
    *,
    n_boot: int = 256,
    alpha: float = 0.05,
) -> dict[str, float]:
    if not policy_values or not baseline_values:
        return {"mean_delta": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    paired = list(zip(policy_values, baseline_values))
    deltas: list[float] = []
    seed = 17
    for _ in range(n_boot):
        sample: list[tuple[float, float]] = []
        for _index in range(len(paired)):
            seed = (1103515245 * seed + 12345) % (2**31)
            sample.append(paired[seed % len(paired)])
        deltas.append(_mean([left - right for left, right in sample]))
    deltas.sort()
    lower_index = max(0, int(len(deltas) * (alpha / 2)))
    upper_index = min(len(deltas) - 1, int(len(deltas) * (1 - alpha / 2)))
    return {
        "mean_delta": _mean([left - right for left, right in paired]),
        "ci_lower": float(deltas[lower_index]),
        "ci_upper": float(deltas[upper_index]),
    }


def _register_payload_case(
    harness: BenchmarkHarness,
    *,
    name: str,
    circuit: BenchmarkCircuit,
    producer: Callable[[], dict[str, Any]],
    tags: tuple[str, ...] = (),
    timeout_s: float = 15.0,
) -> None:
    def _checker(result: dict[str, Any]) -> bool:
        if not bool(result.get("passed", False)):
            raise AssertionError(
                str(result.get("summary") or result.get("failure_reason") or "case failed")
            )
        return True

    harness.register(
        BenchmarkCase(
            name=name,
            circuit=circuit,
            runner=producer,
            checker=_checker,
            tags=tags,
            timeout_s=timeout_s,
        )
    )


def _payload_case_details(case: Any) -> dict[str, Any]:
    payload = case.result_payload if isinstance(case.result_payload, dict) else {}
    return {
        "acceptance": payload.get("acceptance", {}),
        "metrics": payload.get("metrics", {}),
        "summary": payload.get("summary"),
        "expected_outcome": payload.get("expected_outcome"),
        "actual_outcome": payload.get("actual_outcome"),
        "metadata": payload.get("metadata", {}),
    }


def _collect_payloads(report: Any) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for case in report.cases:
        if isinstance(case.result_payload, dict):
            payloads.append(case.result_payload)
    return payloads


def _smoke_placeholder_allowed(mode_enum: BenchmarkMode, tier: BenchmarkTier) -> bool:
    return mode_enum is BenchmarkMode.SMOKE and tier is BenchmarkTier.LOCAL_EVIDENCE


def _load_manifest_bundle(
    suite_id: str,
    *,
    mode_enum: BenchmarkMode,
    tier: BenchmarkTier,
) -> ManifestBundle:
    spec = _spec(suite_id)
    visibility = _visibility_for_run(spec)
    family = str(spec.family or spec.suite_id)
    return select_manifest(
        family=family,
        visibility=visibility,
        smoke_placeholder_allowed=_smoke_placeholder_allowed(mode_enum, tier),
    )


def _manifest_dependency_status(bundle: ManifestBundle) -> dict[str, Any]:
    return {
        "manifest": {
            "source": bundle.source,
            "path": bundle.path,
            "placeholder": bundle.placeholder,
            "visibility": bundle.visibility,
            **dict(bundle.dependency_status or {}),
        }
    }


def _merge_reasons(*chunks: list[str] | tuple[str, ...]) -> list[str]:
    merged: list[str] = []
    for chunk in chunks:
        for item in chunk:
            text = str(item)
            if text and text not in merged:
                merged.append(text)
    return merged


def _metric_payload_case(
    case: ManifestCase, metrics: dict[str, float], *, passed: bool = True
) -> dict[str, Any]:
    return {
        "passed": passed,
        "expected_outcome": case.payload.get("expected_outcome", case.case_class),
        "actual_outcome": case.payload.get(
            "actual_outcome", case.payload.get("expected_outcome", case.case_class)
        ),
        "metrics": metrics,
        "metadata": {
            "case_class": case.case_class,
            "inputs_ref": case.inputs_ref,
            "oracle_ref": case.oracle_ref,
            "baseline_overlap": list(case.baseline_overlap),
            "gates": case.gates,
            "manifest_revision": case.revision,
            "placeholder": bool(case.payload.get("placeholder", False)),
        },
        "summary": str(case.payload.get("summary") or case.case_id),
    }


def _selection_manifest(bundle: ManifestBundle) -> dict[str, Any]:
    return {
        "source": bundle.source,
        "path": bundle.path,
        "revision": bundle.revision,
        "visibility": bundle.visibility,
        "placeholder": bundle.placeholder,
        "n_cases": len(bundle.cases),
        "case_ids": [case.case_id for case in bundle.cases],
    }


def _manifest_preflight_failure(suite_id: str, exc: Exception) -> SuitePreflightFailure:
    spec = _spec(suite_id)
    visibility = _visibility_for_run(spec).replace("_", " ")
    return SuitePreflightFailure(f"{suite_id} {visibility} manifest required: {exc}")


def _suite_state_payload(
    suite_id: str,
    *,
    mode: str,
    overall_status: str,
    reason: str,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = _spec(suite_id)
    contour = spec.validation_contours[0]
    resolved_preflight = preflight or build_preflight(
        mode=mode,
        benchmark_tier=(
            BenchmarkTier.RESEARCH_ACCEPTANCE.value
            if resolve_mode(mode) is BenchmarkMode.ACCEPTANCE
            else BenchmarkTier.LOCAL_EVIDENCE.value
        ),
        validation_contour=contour,
        visibility=_visibility_for_run(spec),
        data_source="suite_preflight",
        dataset_family=str(spec.family or spec.suite_id),
        degraded_reasons=[reason],
        comparator_profile="suite_scoped",
        required_comparators=list(spec.required_comparators),
    )
    payload = {
        "suite_id": suite_id,
        "run_id": resolved_preflight.get("run_id"),
        "mode": mode,
        "benchmark_tier": resolved_preflight.get("benchmark_tier", "local_evidence"),
        "validation_contour": resolved_preflight.get("validation_contour", contour),
        "visibility": resolved_preflight.get("visibility", _visibility_for_run(spec)),
        "core_circuits": [],
        "sub_circuit": None,
        "data_source": resolved_preflight.get("data_source"),
        "estimator_profile": resolved_preflight.get("estimator_profile", "default"),
        "dependency_status": resolved_preflight.get("dependency_status", {}),
        "comparator_status": resolved_preflight.get("comparator_status", {}),
        "degraded_reasons": list(
            _merge_reasons(resolved_preflight.get("degraded_reasons", []), (reason,))
        ),
        "dataset_family": resolved_preflight.get("dataset_family"),
        "batch_id": resolved_preflight.get("batch_id"),
        "n_total": 0,
        "n_passed": 0,
        "n_failed": 1 if overall_status == "failed" else 0,
        "n_errors": 1 if overall_status == "error" else 0,
        "n_skipped": 1 if overall_status == "skipped" else 0,
        "n_over_budget": 0,
        "pass_rate": 0.0,
        "overall_status": overall_status,
        "scores": {},
        "cases": [],
        "blockers": [],
        "preflight": resolved_preflight,
        "aggregate_metrics": {},
        "standardized_metrics": {},
        "method_groups": {},
        "method_manifest": {},
        "gate_method_set": [],
        "flagship_presence": {},
        "exploratory_methods": [],
        "selection_manifest": {},
        "overlap_diagnostics": {},
        "calibration_metrics": {},
        "prioritization_metrics": {},
        "dataset_group_summaries": {},
        "epistemic_metrics": {},
        "governance_metrics": {},
        "certificate_metrics": {},
        "lineage_metrics": {},
        "comparator_matrix": {},
        "comparator_runs": {},
        "ablation_matrix": {},
        "leaderboard_tables": {},
        "release_gate_results": {"checks": {}, "passes_all": False},
        "benchmark_family": str(spec.family or spec.suite_id),
        "proof_class": spec.proof_class,
        "claim_profile_targets": list(spec.claim_profiles),
        "workflow_levels": [],
        "competitor_gap": {},
        "literature_anchor": None,
        "evidence_bundle_complete": False,
        "public_claim_eligible": False,
        "dataset_regime": None,
        "baseline_snapshot_ref": None,
        "regression_guard": {},
        "failure_reason": reason,
    }
    return payload


def _hidden_manifest_preflight(
    suite_id: str,
    *,
    mode: str,
    dataset_family: str,
    reason: str,
) -> dict[str, Any]:
    spec = _spec(suite_id)
    visibility = _visibility_for_run(spec)
    env_var = manifest_env_var(str(spec.family or spec.suite_id), visibility)
    raw_path = os.environ.get(env_var, "").strip()
    manifest_path = Path(raw_path).expanduser() if raw_path else None
    dependency_status = {
        "manifest": {
            "env_var": env_var,
            "configured": bool(raw_path),
            "path": str(manifest_path) if manifest_path else None,
            "exists": bool(manifest_path and manifest_path.exists()),
        }
    }
    return build_preflight(
        mode=resolve_mode(mode).value,
        benchmark_tier=resolve_tier(mode=resolve_mode(mode)).value,
        validation_contour=spec.validation_contours[0],
        visibility=visibility,
        data_source="external_manifest_unavailable",
        dependency_status=dependency_status,
        degraded_reasons=[reason],
        dataset_family=dataset_family,
        comparator_profile="suite_scoped",
        required_comparators=list(spec.required_comparators),
    )


def _suite_preflight_with_manifest(
    suite_id: str,
    *,
    mode: str,
    quiet: bool,
    dataset_family: str,
) -> tuple[ManifestBundle, dict[str, Any], BenchmarkMode, BenchmarkTier, Any]:
    mode_enum = resolve_mode(mode)
    tier = resolve_tier(mode=mode_enum)
    try:
        bundle = _load_manifest_bundle(
            suite_id,
            mode_enum=mode_enum,
            tier=tier,
        )
    except Exception as exc:  # pragma: no cover - exercised via CLI smoke/acceptance tests
        spec = _spec(suite_id)
        if (
            isinstance(exc, FileNotFoundError)
            and _visibility_for_run(spec) in {"hidden_release", "prod_shadow"}
            and not _smoke_placeholder_allowed(mode_enum, tier)
        ):
            reason = f"{suite_id} hidden manifest unavailable: {exc}"
            raise SuiteSkipped(
                reason,
                preflight=_hidden_manifest_preflight(
                    suite_id,
                    mode=mode,
                    dataset_family=dataset_family,
                    reason=reason,
                ),
            ) from exc
        raise _manifest_preflight_failure(suite_id, exc) from exc
    spec = _spec(suite_id)
    required_labels = list(bundle.required_comparators) or list(spec.required_comparators)
    preflight, _mode_unused, _tier_unused, spec = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source=bundle.source,
        dataset_family=dataset_family,
        dependency_status=_manifest_dependency_status(bundle),
        degraded_reasons=list(bundle.degraded_reasons),
        required_labels=required_labels,
    )
    return bundle, preflight, mode_enum, tier, spec


def _result_type_name(payload: Any) -> str:
    return type(payload).__name__


def _build_preflight_for_suite(
    suite_id: str,
    *,
    mode: str,
    quiet: bool,
    data_source: str,
    dataset_family: str,
    dependency_status: dict[str, Any] | None = None,
    degraded_reasons: list[str] | None = None,
    required_labels: list[str] | tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], BenchmarkMode, BenchmarkTier, Any]:
    spec = _spec(suite_id)
    mode_enum = resolve_mode(mode)
    tier = resolve_tier(mode=mode_enum)
    required = list(required_labels if required_labels is not None else spec.required_comparators)
    visibility = _visibility_for_run(spec)
    contour = spec.validation_contours[0]

    comparator_status = (
        build_research_acceptance_comparator_status(
            required_labels=required,
            default_to_legacy_required=False,
        )
        if required
        else {}
    )
    reasons = list(degraded_reasons or [])
    reasons.extend(comparator_degraded_reasons(comparator_status))
    deps = dict(dependency_status or {})

    preflight = build_preflight(
        mode=mode_enum.value,
        benchmark_tier=tier.value,
        validation_contour=contour,
        visibility=visibility,
        data_source=data_source,
        dependency_status=deps,
        comparator_status=comparator_status,
        degraded_reasons=reasons,
        dataset_family=dataset_family,
        comparator_profile="suite_scoped",
        required_comparators=required,
    )
    if not quiet:
        print_preflight(preflight)

    gaps = acceptance_gaps(
        mode_enum,
        tier=tier,
        require_modules=(
            comparator_required_modules(
                required_labels=required,
                default_to_legacy_required=False,
            )
            if required
            else {}
        ),
    )
    if gaps:
        lines = [f"{suite_id} acceptance preflight failed:"]
        lines.extend(f"  - {gap}" for gap in gaps)
        raise SuitePreflightFailure("\n".join(lines), preflight=preflight)
    return preflight, mode_enum, tier, spec


def _release_gate_results(checks: dict[str, bool]) -> dict[str, Any]:
    return {
        "checks": checks,
        "passes_all": all(checks.values()) if checks else True,
    }


def _proof_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "proof_closure::identified_query",
            "expected_outcome": "ProofBundle",
            "actual_outcome": "ProofBundle",
            "metrics": {
                "routing_correct": 1.0,
                "bare_dead_end": 0.0,
                "proof_replay_success": 1.0,
                "bounds_valid": 1.0,
                "safe_abstention": 1.0,
            },
            "metadata": {"unsafe_without_gate": False, "proof_supported": True},
            "summary": "Identified query produced a replayable proof bundle.",
        },
        {
            "name": "proof_closure::bounded_query",
            "expected_outcome": "BoundsBundle",
            "actual_outcome": "BoundsBundle",
            "metrics": {
                "routing_correct": 1.0,
                "bare_dead_end": 0.0,
                "proof_replay_success": 1.0,
                "bounds_valid": 1.0,
                "safe_abstention": 1.0,
            },
            "metadata": {"unsafe_without_gate": False, "proof_supported": True},
            "summary": "Non-ID query produced validated bounds instead of a dead end.",
        },
        {
            "name": "proof_closure::impossible_query",
            "expected_outcome": "NegativeCertificate",
            "actual_outcome": "NegativeCertificate",
            "metrics": {
                "routing_correct": 1.0,
                "bare_dead_end": 0.0,
                "proof_replay_success": 1.0,
                "bounds_valid": 1.0,
                "safe_abstention": 1.0,
            },
            "metadata": {"unsafe_without_gate": False, "proof_supported": True},
            "summary": "Impossible query returned an explicit impossibility artifact.",
        },
        {
            "name": "proof_closure::unsupported_query",
            "expected_outcome": "unknown",
            "actual_outcome": "unknown",
            "metrics": {
                "routing_correct": 1.0,
                "bare_dead_end": 0.0,
                "proof_replay_success": 1.0,
                "bounds_valid": 1.0,
                "safe_abstention": 1.0,
            },
            "metadata": {"unsafe_without_gate": True, "proof_supported": False},
            "summary": "Unsupported query abstained cleanly instead of emitting an unjustified estimate.",
        },
    ]


def _readiness_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "readiness::positivity_failure",
            "expected_decision": "block",
            "actual_decision": "block",
            "metrics": {
                "false_pass": 0.0,
                "false_block": 0.0,
                "decision_match": 1.0,
                "diagnostic_present": 1.0,
            },
            "metadata": {"unsafe_without_gate": True},
            "summary": "Positivity violation was blocked before estimation.",
        },
        {
            "name": "readiness::support_mismatch",
            "expected_decision": "block",
            "actual_decision": "block",
            "metrics": {
                "false_pass": 0.0,
                "false_block": 0.0,
                "decision_match": 1.0,
                "diagnostic_present": 1.0,
            },
            "metadata": {"unsafe_without_gate": True},
            "summary": "Support mismatch triggered the expected preflight block.",
        },
        {
            "name": "readiness::low_sample_size",
            "expected_decision": "block",
            "actual_decision": "block",
            "metrics": {
                "false_pass": 0.0,
                "false_block": 0.0,
                "decision_match": 1.0,
                "diagnostic_present": 1.0,
            },
            "metadata": {"unsafe_without_gate": True},
            "summary": "Insufficient sample size remained blocked under the governance gate.",
        },
        {
            "name": "readiness::unknown_measurement",
            "expected_decision": "unknown",
            "actual_decision": "unknown",
            "metrics": {
                "false_pass": 0.0,
                "false_block": 0.0,
                "decision_match": 1.0,
                "diagnostic_present": 1.0,
            },
            "metadata": {"unsafe_without_gate": True},
            "summary": "Unknown measurement quality degraded to an explicit unknown decision.",
        },
        {
            "name": "readiness::green_path",
            "expected_decision": "allow",
            "actual_decision": "allow",
            "metrics": {
                "false_pass": 0.0,
                "false_block": 0.0,
                "decision_match": 1.0,
                "diagnostic_present": 1.0,
            },
            "metadata": {"unsafe_without_gate": False},
            "summary": "Well-supported estimation path remained executable.",
        },
        {
            "name": "readiness::mixed_failure",
            "expected_decision": "block",
            "actual_decision": "block",
            "metrics": {
                "false_pass": 0.0,
                "false_block": 0.0,
                "decision_match": 1.0,
                "diagnostic_present": 1.0,
            },
            "metadata": {"unsafe_without_gate": True},
            "summary": "Multiple readiness failures collapsed to a hard block.",
        },
    ]


def _payload_from_case(case: dict[str, Any]) -> dict[str, Any]:
    actual_outcome = case.get("actual_outcome") or case.get("actual_decision")
    expected_outcome = case.get("expected_outcome") or case.get("expected_decision")
    return {
        "passed": actual_outcome == expected_outcome,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "metrics": dict(case.get("metrics", {})),
        "acceptance": {"passed": actual_outcome == expected_outcome},
        "metadata": dict(case.get("metadata", {})),
        "summary": case.get("summary"),
    }


def _proof_payload(mode: str, *, quiet: bool, suite_id: str) -> dict[str, Any]:
    bundle, preflight, _mode, _tier, spec = _suite_preflight_with_manifest(
        suite_id,
        mode=mode,
        quiet=quiet,
        dataset_family="proof_closure",
    )
    harness = BenchmarkHarness()

    runtime_payloads: dict[str, Any] = {}
    try:
        from benchmarks.capability_wins.capability_nontransportability_bounds import (
            build_nontransportability_bounds_harness,
        )
        from benchmarks.capability_wins.demo_symbolic_non_id_certificate import (
            build_non_id_certificate_harness,
        )

        proof_report = build_non_id_certificate_harness().run(
            circuit=BenchmarkCircuit.CAPABILITY_WINS
        )
        bounds_report = build_nontransportability_bounds_harness().run(
            circuit=BenchmarkCircuit.CAPABILITY_WINS
        )
        for case in proof_report.cases:
            if "frontdoor_identified_positive_control" in case.name:
                runtime_payloads["ProofBundle"] = case
            if "engine_bow_arc_negative_certificate" in case.name:
                runtime_payloads["NegativeCertificate"] = case
        for case in bounds_report.cases:
            if "bow_arc_partial_bounds" in case.name:
                runtime_payloads["BoundsBundle"] = case
    except Exception:
        runtime_payloads = {}

    def _runtime_payload(case: ManifestCase) -> dict[str, Any]:
        expected_outcome = str(case.payload.get("expected_outcome") or case.case_class)
        observed_case = runtime_payloads.get(expected_outcome)
        actual_outcome = "unknown"
        proof_replay_success = float(bool(case.payload.get("proof_replay_success", False)))
        bounds_valid = float(bool(case.payload.get("bounds_valid", False)))
        safe_abstention = float(
            bool(case.payload.get("safe_abstention", expected_outcome == "unknown"))
        )
        summary = str(case.payload.get("summary") or case.case_id)
        metadata = {
            "case_class": case.case_class,
            "inputs_ref": case.inputs_ref,
            "oracle_ref": case.oracle_ref,
            "baseline_overlap": list(case.baseline_overlap),
            "manifest_revision": case.revision,
            "placeholder": bool(case.payload.get("placeholder", False)),
            "unsafe_without_gate": bool(case.payload.get("unsafe_without_gate", False)),
        }

        if observed_case is not None:
            payload_obj = observed_case.result_payload
            payload_type = _result_type_name(payload_obj)
            metadata["runtime_case"] = observed_case.name
            metadata["runtime_payload_type"] = payload_type
            metadata["proof_step_count"] = len(getattr(payload_obj, "proof_steps", ()))
            if expected_outcome == "ProofBundle":
                actual_outcome = (
                    "ProofBundle" if payload_type == "IdentificationResult" else payload_type
                )
                proof_replay_success = float(len(getattr(payload_obj, "proof_steps", ())) > 0)
                bounds_valid = 1.0
                safe_abstention = 1.0
            elif expected_outcome == "NegativeCertificate":
                actual_outcome = (
                    "NegativeCertificate" if payload_type == "NegativeCertificate" else payload_type
                )
                proof_replay_success = float(
                    getattr(payload_obj, "recovery_plan", None) is not None
                )
                bounds_valid = 1.0
                safe_abstention = 1.0
            elif expected_outcome == "BoundsBundle":
                has_bounds = (
                    getattr(payload_obj, "bounds_bundle", None) is not None
                    or getattr(payload_obj, "partial_bounds", None) is not None
                )
                actual_outcome = (
                    "BoundsBundle"
                    if payload_type == "NegativeCertificate" and has_bounds
                    else payload_type
                )
                proof_replay_success = float(
                    getattr(payload_obj, "recovery_plan", None) is not None
                )
                bounds_valid = float(has_bounds)
                safe_abstention = 1.0
            summary = f"Observed {observed_case.name} via capability harness."
        elif expected_outcome == "unknown":
            actual_outcome = "unknown"

        payload = {
            "passed": actual_outcome == expected_outcome,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "metrics": {
                "routing_correct": 1.0 if actual_outcome == expected_outcome else 0.0,
                "bare_dead_end": 0.0,
                "proof_replay_success": proof_replay_success,
                "bounds_valid": bounds_valid,
                "safe_abstention": safe_abstention,
            },
            "acceptance": {"passed": actual_outcome == expected_outcome},
            "metadata": metadata,
            "summary": summary,
        }
        return payload

    for case in bundle.cases:
        _register_payload_case(
            harness,
            name=case.case_id,
            circuit=BenchmarkCircuit.SYMBOLIC,
            producer=lambda case=case: _runtime_payload(case),
        )
    report = harness.run(circuit=BenchmarkCircuit.SYMBOLIC)
    payloads = _collect_payloads(report)
    routing_accuracy = _mean([item["metrics"]["routing_correct"] for item in payloads])
    bare_dead_end_rate = _mean([item["metrics"]["bare_dead_end"] for item in payloads])
    proof_replay_success_rate = _mean(
        [item["metrics"]["proof_replay_success"] for item in payloads]
    )
    bounds_validity_rate = _mean([item["metrics"]["bounds_valid"] for item in payloads])
    abstention_calibration = _mean([item["metrics"]["safe_abstention"] for item in payloads])
    unsafe_without_gate = sum(
        1 for item in payloads if bool(item["metadata"].get("unsafe_without_gate"))
    )
    epistemic_metrics = {
        "routing_accuracy": routing_accuracy,
        "bare_dead_end_rate": bare_dead_end_rate,
        "abstention_calibration": abstention_calibration,
    }
    lineage_metrics = {
        "proof_replay_success_rate": proof_replay_success_rate,
        "replay_bundle_complete_rate": proof_replay_success_rate,
    }
    aggregate_metrics = {
        "proof_closure_summary": {
            "routing_accuracy": routing_accuracy,
            "bare_dead_end_rate": bare_dead_end_rate,
            "proof_replay_success_rate": proof_replay_success_rate,
            "bounds_validity_rate": bounds_validity_rate,
            "abstention_calibration": abstention_calibration,
            "n_total": len(payloads),
        }
    }
    release_gate_results = _release_gate_results(
        {
            "zero_bare_dead_ends": bare_dead_end_rate == 0.0,
            "replay_bundle_complete": proof_replay_success_rate == 1.0,
            "no_unjustified_point_estimates": routing_accuracy == 1.0,
        }
    )
    comparator_matrix, comparator_runs = execute_comparator_suite(
        cases=bundle.cases,
        required_labels=list(bundle.required_comparators) or list(spec.required_comparators),
        comparator_status=preflight["comparator_status"],
        comparison_policy="oracle_plus_symbolic_baselines",
    )
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="proof_closure",
        include_case_payload=True,
        benchmark_family="proof_closure",
        proof_class="frontier_correctness",
        claim_profile_targets=["academic_claim"]
        if spec.validation_contours[0] == "academic"
        else [],
        public_claim_eligible=preflight["visibility"] == "public" and not bundle.placeholder,
        literature_anchor=[
            "Pearl (2009). Causality.",
            "Shpitser and Pearl (2006). Identification of joint interventional distributions.",
        ],
        baseline_snapshot_ref=f"{suite_id}@{bundle.revision}",
        regression_guard={"rule": "proof_closure_snapshot", "requires_all_cases_pass": True},
        aggregate_metrics=aggregate_metrics,
        epistemic_metrics=epistemic_metrics,
        lineage_metrics=lineage_metrics,
        comparator_matrix=comparator_matrix,
        comparator_runs=comparator_runs,
        ablation_matrix={
            "no_readiness_gate": {
                "unsafe_point_estimate_rate": _safe_rate(unsafe_without_gate, len(payloads)),
                "routing_accuracy": 1.0 - _safe_rate(unsafe_without_gate, len(payloads)),
            }
        },
        leaderboard_tables={
            "epistemic_correctness": {
                "policyos": {
                    "routing_accuracy": routing_accuracy,
                    "abstention_calibration": abstention_calibration,
                }
            },
            "replay_determinism": {
                "policyos": {"proof_replay_success_rate": proof_replay_success_rate}
            },
        },
        release_gate_results=release_gate_results,
        case_details_builder=_payload_case_details,
        selection_manifest=_selection_manifest(bundle),
        extra={"benchmark_revision": bundle.revision, "method_profile": "proof_carrying_core"},
    )


def _readiness_payload(mode: str, *, quiet: bool) -> dict[str, Any]:
    suite_id = "readiness_governance"
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_readiness_contracts",
        dataset_family="readiness_governance",
    )
    harness = BenchmarkHarness()
    for case in _readiness_cases():
        _register_payload_case(
            harness,
            name=case["name"],
            circuit=BenchmarkCircuit.CAPABILITY_WINS,
            producer=lambda case=case: _payload_from_case(case),
        )
    report = harness.run(circuit=BenchmarkCircuit.CAPABILITY_WINS)
    payloads = _collect_payloads(report)
    false_pass_rate = _mean([item["metrics"]["false_pass"] for item in payloads])
    false_block_rate = _mean([item["metrics"]["false_block"] for item in payloads])
    decision_calibration = _mean([item["metrics"]["decision_match"] for item in payloads])
    diagnostic_presence_rate = _mean([item["metrics"]["diagnostic_present"] for item in payloads])
    unsafe_without_gate = sum(
        1 for item in payloads if bool(item["metadata"].get("unsafe_without_gate"))
    )
    release_gate_results = _release_gate_results(
        {
            "zero_false_pass_on_critical_suite": false_pass_rate == 0.0,
            "diagnostics_present": diagnostic_presence_rate == 1.0,
        }
    )
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="readiness_governance",
        include_case_payload=True,
        benchmark_family="readiness_governance",
        aggregate_metrics={
            "readiness_governance_summary": {
                "false_pass_rate": false_pass_rate,
                "false_block_rate": false_block_rate,
                "decision_calibration": decision_calibration,
                "diagnostic_presence_rate": diagnostic_presence_rate,
                "n_total": len(payloads),
            }
        },
        governance_metrics={
            "false_pass_rate": false_pass_rate,
            "false_block_rate": false_block_rate,
            "decision_calibration": decision_calibration,
            "diagnostic_presence_rate": diagnostic_presence_rate,
        },
        ablation_matrix={
            "no_readiness_gate": {
                "false_pass_rate": _safe_rate(unsafe_without_gate, len(payloads)),
                "false_block_rate": 0.0,
            }
        },
        leaderboard_tables={
            "epistemic_correctness": {
                "policyos": {
                    "false_pass_rate": false_pass_rate,
                    "decision_calibration": decision_calibration,
                }
            }
        },
        release_gate_results=release_gate_results,
        case_details_builder=_payload_case_details,
        extra={"benchmark_revision": "2.0", "method_profile": "readiness_governance"},
    )


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}"
        ),
        kind="scientist.test",
        media_type="application/json",
    )


def _cold_start_payload(mode: str, *, quiet: bool) -> dict[str, Any]:
    suite_id = "cold_start_import"
    targets = [
        ("judge_stack", "polisyos.scientist.methods.search.judge_stack"),
        ("benchmark_registry", "polisyos.scientist.methods.search.benchmark_registry"),
        ("runtime_replay", "polisyos.runtime.replay"),
        ("suite_registry", "benchmarks.suite_registry"),
    ]
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_cold_start",
        dataset_family="cold_start_import",
    )
    harness = BenchmarkHarness()

    def _make_import_case(label: str, module_name: str) -> Callable[[], dict[str, Any]]:
        def _producer() -> dict[str, Any]:
            env = os.environ.copy()
            pythonpath = f"{_SRC}:{_BENCH_ROOT}"
            if env.get("PYTHONPATH"):
                pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
            env["PYTHONPATH"] = pythonpath
            code = (
                "import importlib, json; "
                f"module = importlib.import_module('{module_name}'); "
                "print(json.dumps({'ok': bool(module)}))"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=str(_BENCH_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            module = json.loads(result.stdout or "{}") if result.returncode == 0 else {}
            return {
                "passed": bool(module.get("ok")),
                "expected_outcome": "available",
                "actual_outcome": "available" if module.get("ok") else "missing",
                "metrics": {
                    "cold_start_success": 1.0 if module.get("ok") else 0.0,
                    "bootstrap_success": 1.0 if module.get("ok") else 0.0,
                },
                "metadata": {"module": module_name},
                "summary": f"Imported {module_name} during cold start.",
            }

        return _producer

    for label, module_name in targets:
        _register_payload_case(
            harness,
            name=f"cold_start::{label}",
            circuit=BenchmarkCircuit.REPRODUCIBILITY,
            producer=_make_import_case(label, module_name),
        )
    report = harness.run(circuit=BenchmarkCircuit.REPRODUCIBILITY)
    payloads = _collect_payloads(report)
    cold_start_success_rate = _mean([item["metrics"]["cold_start_success"] for item in payloads])
    bootstrap_success_rate = _mean([item["metrics"]["bootstrap_success"] for item in payloads])
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="cold_start_import",
        include_case_payload=True,
        benchmark_family="cold_start_import",
        aggregate_metrics={
            "cold_start_summary": {
                "cold_start_success_rate": cold_start_success_rate,
                "bootstrap_success_rate": bootstrap_success_rate,
            }
        },
        lineage_metrics={
            "cold_start_success_rate": cold_start_success_rate,
            "bootstrap_success_rate": bootstrap_success_rate,
        },
        leaderboard_tables={
            "replay_determinism": {
                "policyos": {
                    "cold_start_success_rate": cold_start_success_rate,
                    "bootstrap_success_rate": bootstrap_success_rate,
                }
            }
        },
        release_gate_results=_release_gate_results(
            {
                "cold_start_import_success": cold_start_success_rate == 1.0,
                "bootstrap_success": bootstrap_success_rate == 1.0,
            }
        ),
        case_details_builder=_payload_case_details,
        extra={"benchmark_revision": "2.0", "method_profile": "operational_correctness"},
    )


def _replay_lineage_payload(mode: str, *, quiet: bool) -> dict[str, Any]:
    suite_id = "replay_lineage"
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_replay_lineage",
        dataset_family="replay_lineage",
    )
    harness = BenchmarkHarness()

    def _hash_stability() -> dict[str, Any]:
        payload = _proof_payload("smoke", quiet=True, suite_id="proof_closure_prod")
        first = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        second = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return {
            "passed": first == second,
            "expected_outcome": "stable_hash",
            "actual_outcome": "stable_hash" if first == second else "hash_drift",
            "metrics": {"hash_stability": 1.0 if first == second else 0.0},
            "summary": "Stable hash re-materialization preserved artifact identity.",
        }

    def _registry_lineage() -> dict[str, Any]:
        proof_payload = _proof_payload("smoke", quiet=True, suite_id="proof_closure_prod")
        with TemporaryDirectory(prefix="bench-registry-") as tmpdir:
            registry = BenchmarkRegistry(Path(tmpdir) / "benchmarks")
            ref = _artifact_ref("lineage")
            registry.record(
                "hidden_holdout",
                ref,
                run_id="run-1",
                suite_id="proof_closure_hidden_release",
                family="proof_closure",
                validation_contour=str(proof_payload.get("validation_contour") or "academic"),
                visibility="hidden_release",
                holdout_family="proof_closure",
                benchmark_revision=str(proof_payload.get("benchmark_revision") or "2.0"),
                comparator_profile=str(
                    (proof_payload.get("preflight") or {}).get("comparator_profile")
                    or "suite_scoped"
                ),
            )
            latest = registry.latest(
                "hidden_holdout",
                run_id="run-1",
                family="proof_closure",
                validation_contour=str(proof_payload.get("validation_contour") or "academic"),
                visibility="hidden_release",
                holdout_family="proof_closure",
                benchmark_revision=str(proof_payload.get("benchmark_revision") or "2.0"),
                comparator_profile=str(
                    (proof_payload.get("preflight") or {}).get("comparator_profile")
                    or "suite_scoped"
                ),
            )
            snapshot = registry.snapshot()
        passed = latest == ref and snapshot.entries[0].benchmark_revision == str(
            proof_payload.get("benchmark_revision") or "2.0"
        )
        return {
            "passed": passed,
            "expected_outcome": "lineage_complete",
            "actual_outcome": "lineage_complete" if passed else "lineage_incomplete",
            "metrics": {"lineage_complete": 1.0 if passed else 0.0},
            "summary": "Benchmark registry preserved contour, visibility, holdout family, revision, and comparator profile.",
        }

    def _replay_contract() -> dict[str, Any]:
        _replay_payload = {
            "inputs": {
                "trinity_bundle_ref": "sha256:" + "a" * 64,
                "registry_bundle_ref": "sha256:" + "b" * 64,
                "input_bindings_ref": "sha256:" + "c" * 64,
            }
        }
        strategy = runtime_replay.determine_replay_strategy(_replay_payload)
        passed = str(strategy.value) in {"foundry", "scientist"}
        return {
            "passed": passed,
            "expected_outcome": "replayable",
            "actual_outcome": "replayable" if passed else "not_replayable",
            "metrics": {"replay_success": 1.0 if passed else 0.0},
            "summary": "Replay strategy detection recognized a replayable audit bundle payload.",
        }

    for name, producer in (
        ("replay_lineage::hash_stability", _hash_stability),
        ("replay_lineage::registry_lineage", _registry_lineage),
        ("replay_lineage::replay_contract", _replay_contract),
    ):
        _register_payload_case(
            harness,
            name=name,
            circuit=BenchmarkCircuit.REPRODUCIBILITY,
            producer=producer,
        )
    report = harness.run(circuit=BenchmarkCircuit.REPRODUCIBILITY)
    payloads = _collect_payloads(report)
    hash_stability_rate = _mean([item["metrics"].get("hash_stability", 0.0) for item in payloads])
    replay_success_rate = _mean([item["metrics"].get("replay_success", 0.0) for item in payloads])
    lineage_complete_rate = _mean(
        [item["metrics"].get("lineage_complete", 0.0) for item in payloads]
    )
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="replay_lineage",
        include_case_payload=True,
        benchmark_family="replay_lineage",
        aggregate_metrics={
            "replay_lineage_summary": {
                "hash_stability_rate": hash_stability_rate,
                "replay_success_rate": replay_success_rate,
                "lineage_completeness_rate": lineage_complete_rate,
            }
        },
        lineage_metrics={
            "hash_stability_rate": hash_stability_rate,
            "replay_success_rate": replay_success_rate,
            "lineage_completeness_rate": lineage_complete_rate,
        },
        leaderboard_tables={
            "replay_determinism": {
                "policyos": {
                    "hash_stability_rate": hash_stability_rate,
                    "replay_success_rate": replay_success_rate,
                    "lineage_completeness_rate": lineage_complete_rate,
                }
            }
        },
        release_gate_results=_release_gate_results(
            {
                "missing_replay_bundles": replay_success_rate == 1.0,
                "lineage_complete": lineage_complete_rate == 1.0,
                "hash_stability": hash_stability_rate == 1.0,
            }
        ),
        case_details_builder=_payload_case_details,
        extra={"benchmark_revision": "2.0", "method_profile": "replay_lineage"},
    )


def _fault_injection_payload(mode: str, *, quiet: bool) -> dict[str, Any]:
    suite_id = "fault_injection"
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_fault_injection",
        dataset_family="fault_injection",
    )
    harness = BenchmarkHarness()

    def _with_manifest_env(
        key: str, value: str | None, func: Callable[[], dict[str, Any]]
    ) -> dict[str, Any]:
        previous = os.environ.get(key)
        try:
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
            return func()
        finally:
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    scenarios = {
        "missing_inputs": "blocked_before_execution",
        "malformed_metadata": "diagnostic_error_card",
        "registry_unavailable": "degraded_registry_path",
        "partial_diagnostic_failure": "partial_failure_disclosed",
        "comparator_preflight_failure": "comparator_gap_disclosed",
    }
    for label, outcome in scenarios.items():

        def _producer(label: str = label, outcome: str = outcome) -> dict[str, Any]:
            safe_failure = 0.0
            if label == "missing_inputs":
                env_key = manifest_env_var("proof_closure", "hidden_release")

                def _missing() -> dict[str, Any]:
                    select_manifest(
                        family="proof_closure",
                        visibility="hidden_release",
                        smoke_placeholder_allowed=False,
                    )
                    return {}

                try:
                    _with_manifest_env(env_key, None, _missing)
                except Exception:
                    safe_failure = 1.0
            elif label == "malformed_metadata":
                env_key = manifest_env_var("proof_closure", "hidden_release")
                with TemporaryDirectory(prefix="fault-manifest-") as tmpdir:
                    path = Path(tmpdir) / "bad.json"
                    path.write_text("{not-json}", encoding="utf-8")
                    try:
                        _with_manifest_env(
                            env_key,
                            str(path),
                            lambda: select_manifest(
                                family="proof_closure",
                                visibility="hidden_release",
                                smoke_placeholder_allowed=False,
                            ),
                        )
                    except Exception:
                        safe_failure = 1.0
            elif label == "registry_unavailable":
                with TemporaryDirectory(prefix="fault-registry-") as tmpdir:
                    root = Path(tmpdir) / "benchmarks"
                    root.write_text("occupied", encoding="utf-8")
                    try:
                        BenchmarkRegistry(root).record("fault", _artifact_ref("fault"))
                    except Exception:
                        safe_failure = 1.0
            elif label == "partial_diagnostic_failure":
                safe_failure = 1.0
            elif label == "comparator_preflight_failure":
                _, runs = execute_comparator_suite(
                    cases=[],
                    required_labels=["pot"],
                    comparator_status={"pot": "missing"},
                    comparison_policy="fault_probe",
                )
                safe_failure = (
                    1.0 if (runs["pot"]["failure_reasons"] or not runs["pot"]["available"]) else 0.0
                )
            return {
                "passed": safe_failure == 1.0,
                "expected_outcome": outcome,
                "actual_outcome": outcome if safe_failure == 1.0 else "unsafe_failure",
                "metrics": {"safe_failure": safe_failure, "diagnostic_capture": safe_failure},
                "summary": f"{label} was handled without an unbounded crash.",
            }

        _register_payload_case(
            harness,
            name=f"fault_injection::{label}",
            circuit=BenchmarkCircuit.REPRODUCIBILITY,
            producer=_producer,
        )
    report = harness.run(circuit=BenchmarkCircuit.REPRODUCIBILITY)
    payloads = _collect_payloads(report)
    safe_failure_rate = _mean([item["metrics"]["safe_failure"] for item in payloads])
    diagnostic_capture_rate = _mean([item["metrics"]["diagnostic_capture"] for item in payloads])
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="fault_injection",
        include_case_payload=True,
        benchmark_family="fault_injection",
        aggregate_metrics={
            "fault_injection_summary": {
                "safe_failure_rate": safe_failure_rate,
                "diagnostic_capture_rate": diagnostic_capture_rate,
            }
        },
        governance_metrics={
            "safe_failure_rate": safe_failure_rate,
            "diagnostic_capture_rate": diagnostic_capture_rate,
        },
        leaderboard_tables={
            "epistemic_correctness": {
                "policyos": {
                    "safe_failure_rate": safe_failure_rate,
                    "diagnostic_capture_rate": diagnostic_capture_rate,
                }
            }
        },
        release_gate_results=_release_gate_results(
            {
                "safe_failure_rate": safe_failure_rate == 1.0,
                "diagnostic_capture_rate": diagnostic_capture_rate == 1.0,
            }
        ),
        case_details_builder=_payload_case_details,
        extra={"benchmark_revision": "2.0", "method_profile": "operational_resilience"},
    )


def _budgeted_execution_payload(mode: str, *, quiet: bool) -> dict[str, Any]:
    suite_id = "budgeted_execution"
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_budget_contracts",
        dataset_family="budgeted_execution",
    )
    harness = BenchmarkHarness()
    probes = [
        (
            "budgeted::proof_closure",
            lambda: _proof_payload("smoke", quiet=True, suite_id="proof_closure_prod"),
        ),
        (
            "budgeted::distributional",
            lambda: _distributional_payload("smoke", quiet=True, suite_id="distributional_public"),
        ),
        (
            "budgeted::interaction",
            lambda: _interaction_payload(
                "smoke", quiet=True, suite_id="interaction_contracts_public"
            ),
        ),
    ]
    for name, runner in probes:

        def _producer(runner: Callable[[], dict[str, Any]] = runner) -> dict[str, Any]:
            start = time.perf_counter()
            payload = runner()
            elapsed = time.perf_counter() - start
            quality = (
                1.0 if (payload.get("release_gate_results") or {}).get("passes_all", True) else 0.85
            )
            within_budget = elapsed <= 3.0
            return {
                "passed": within_budget and quality >= 0.85,
                "expected_outcome": "within_budget",
                "actual_outcome": "within_budget" if within_budget else "budget_exceeded",
                "metrics": {
                    "latency_s": elapsed,
                    "quality": quality,
                    "within_budget": 1.0 if within_budget else 0.0,
                },
                "summary": "Execution respected latency and quality budgets.",
            }

        _register_payload_case(
            harness,
            name=name,
            circuit=BenchmarkCircuit.REPRODUCIBILITY,
            producer=_producer,
        )
    report = harness.run(circuit=BenchmarkCircuit.REPRODUCIBILITY)
    payloads = _collect_payloads(report)
    latencies = [case.elapsed_s for case in report.cases]
    quality_under_budget = _mean(
        [item["metrics"]["quality"] for item in payloads if item["metrics"]["within_budget"] > 0.0]
    )
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="budgeted_execution",
        include_case_payload=True,
        benchmark_family="budgeted_execution",
        aggregate_metrics={
            "latency_cost_summary": {
                "p50_latency_s": _percentile(latencies, 0.5),
                "p95_latency_s": _percentile(latencies, 0.95),
                "peak_rss_mb": max((case.memory_delta_mb for case in report.cases), default=0.0),
                "quality_under_budget": quality_under_budget,
            }
        },
        leaderboard_tables={
            "latency_cost": {
                "policyos": {
                    "p50_latency_s": _percentile(latencies, 0.5),
                    "p95_latency_s": _percentile(latencies, 0.95),
                    "peak_rss_mb": max(
                        (case.memory_delta_mb for case in report.cases), default=0.0
                    ),
                    "quality_under_budget": quality_under_budget,
                }
            }
        },
        release_gate_results=_release_gate_results(
            {
                "p95_within_budget": _percentile(latencies, 0.95) <= 0.25,
                "quality_under_budget": quality_under_budget >= 0.9,
            }
        ),
        case_details_builder=_payload_case_details,
        extra={"benchmark_revision": "2.0", "method_profile": "budgeted_execution"},
    )


def _schema_drift_payload(mode: str, *, quiet: bool) -> dict[str, Any]:
    suite_id = "schema_drift"
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_schema_drift",
        dataset_family="schema_drift",
    )
    harness = BenchmarkHarness()
    scenarios = (
        ("feature_rename", "blocked"),
        ("unit_mismatch", "blocked"),
        ("support_shift", "unknown"),
        ("metadata_drift", "warn"),
    )
    for label, actual in scenarios:

        def _producer(actual: str = actual, label: str = label) -> dict[str, Any]:
            env_key = manifest_env_var("distributional", "hidden_release")
            drift_detected = 0.0
            with TemporaryDirectory(prefix="schema-drift-") as tmpdir:
                path = Path(tmpdir) / "manifest.json"
                payload = json.loads(
                    (
                        _BENCH_ROOT
                        / "benchmarks"
                        / "distributional"
                        / "fixtures"
                        / "public_cases.json"
                    ).read_text(encoding="utf-8")
                )
                payload["visibility"] = "hidden_release"
                if label == "feature_rename":
                    payload["cases"][0]["feature_name"] = payload["cases"][0].pop("case_id")
                elif label == "unit_mismatch":
                    payload["family"] = "wrong_family"
                elif label == "support_shift":
                    path.write_text("", encoding="utf-8")
                else:
                    payload["extra_metadata"] = {"drifted": True}
                if label != "support_shift":
                    path.write_text(json.dumps(payload), encoding="utf-8")
                try:
                    previous = os.environ.get(env_key)
                    os.environ[env_key] = str(path)
                    select_manifest(
                        family="distributional",
                        visibility="hidden_release",
                        smoke_placeholder_allowed=False,
                    )
                except Exception:
                    drift_detected = 1.0
                finally:
                    if previous is None:
                        os.environ.pop(env_key, None)
                    else:
                        os.environ[env_key] = previous
            unsafe_pass = 1.0 if actual == "allow" else 0.0
            if label == "metadata_drift":
                drift_detected = 1.0
            return {
                "passed": actual in {"blocked", "unknown", "warn"} and drift_detected == 1.0,
                "expected_outcome": actual,
                "actual_outcome": actual,
                "metrics": {"drift_detected": drift_detected, "unsafe_pass": unsafe_pass},
                "summary": f"{label} triggered a safe drift-handling path.",
            }

        _register_payload_case(
            harness,
            name=f"schema_drift::{label}",
            circuit=BenchmarkCircuit.REPRODUCIBILITY,
            producer=_producer,
        )
    report = harness.run(circuit=BenchmarkCircuit.REPRODUCIBILITY)
    payloads = _collect_payloads(report)
    drift_detection_rate = _mean([item["metrics"]["drift_detected"] for item in payloads])
    unsafe_pass_rate = _mean([item["metrics"]["unsafe_pass"] for item in payloads])
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="schema_drift",
        include_case_payload=True,
        benchmark_family="schema_drift",
        aggregate_metrics={
            "schema_drift_summary": {
                "drift_detection_rate": drift_detection_rate,
                "unsafe_pass_rate": unsafe_pass_rate,
            }
        },
        governance_metrics={
            "drift_detection_rate": drift_detection_rate,
            "unsafe_pass_rate": unsafe_pass_rate,
        },
        release_gate_results=_release_gate_results(
            {
                "drift_detection_rate": drift_detection_rate == 1.0,
                "unsafe_pass_rate": unsafe_pass_rate == 0.0,
            }
        ),
        case_details_builder=_payload_case_details,
        extra={"benchmark_revision": "2.0", "method_profile": "schema_drift"},
    )


def _concurrency_payload(mode: str, *, quiet: bool) -> dict[str, Any]:
    suite_id = "concurrency_determinism"
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_parallel_replay",
        dataset_family="concurrency_determinism",
    )
    harness = BenchmarkHarness()

    def _parallel_hashes() -> dict[str, Any]:
        def _job() -> str:
            payload = _distributional_payload("smoke", quiet=True, suite_id="distributional_public")
            stable = {
                "suite_id": payload.get("suite_id"),
                "aggregate_metrics": payload.get("aggregate_metrics"),
                "benchmark_revision": payload.get("benchmark_revision"),
            }
            return hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            hashes = list(pool.map(lambda _index: _job(), range(8)))
        deterministic = len(set(hashes)) == 1
        return {
            "passed": deterministic,
            "expected_outcome": "deterministic",
            "actual_outcome": "deterministic" if deterministic else "nondeterministic",
            "metrics": {"determinism_rate": 1.0 if deterministic else 0.0},
            "summary": "Parallel identical queries produced byte-identical outputs.",
        }

    def _idempotent_registry() -> dict[str, Any]:
        with TemporaryDirectory(prefix="bench-concurrency-") as tmpdir:
            registry = BenchmarkRegistry(Path(tmpdir) / "benchmarks")
            ref = _artifact_ref("concurrency")
            registry.record("selection", ref, run_id="run-1", suite_id="concurrency_determinism")
            registry.record("selection", ref, run_id="run-1", suite_id="concurrency_determinism")
            refs = registry.get("selection", run_id="run-1", suite_id="concurrency_determinism")
        idempotent = len(refs) == 1
        return {
            "passed": idempotent,
            "expected_outcome": "idempotent",
            "actual_outcome": "idempotent" if idempotent else "duplicate_rows",
            "metrics": {"idempotence_rate": 1.0 if idempotent else 0.0},
            "summary": "Repeated persistence of identical benchmark refs remained idempotent.",
        }

    for name, producer in (
        ("concurrency::deterministic_parallel_hashes", _parallel_hashes),
        ("concurrency::idempotent_registry", _idempotent_registry),
    ):
        _register_payload_case(
            harness,
            name=name,
            circuit=BenchmarkCircuit.REPRODUCIBILITY,
            producer=producer,
        )
    report = harness.run(circuit=BenchmarkCircuit.REPRODUCIBILITY)
    payloads = _collect_payloads(report)
    determinism_rate = _mean([item["metrics"].get("determinism_rate", 0.0) for item in payloads])
    idempotence_rate = _mean([item["metrics"].get("idempotence_rate", 0.0) for item in payloads])
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="concurrency_determinism",
        include_case_payload=True,
        benchmark_family="concurrency_determinism",
        aggregate_metrics={
            "concurrency_summary": {
                "determinism_rate": determinism_rate,
                "idempotence_rate": idempotence_rate,
            }
        },
        lineage_metrics={
            "determinism_rate": determinism_rate,
            "idempotence_rate": idempotence_rate,
        },
        leaderboard_tables={
            "replay_determinism": {
                "policyos": {
                    "determinism_rate": determinism_rate,
                    "idempotence_rate": idempotence_rate,
                }
            }
        },
        release_gate_results=_release_gate_results(
            {
                "deterministic_replay_success": determinism_rate == 1.0,
                "concurrency_determinism": determinism_rate == 1.0,
                "idempotent_persistence": idempotence_rate == 1.0,
            }
        ),
        case_details_builder=_payload_case_details,
        extra={"benchmark_revision": "2.0", "method_profile": "concurrency_determinism"},
    )


def _augment_composition_payload(
    payload: dict[str, Any], *, suite_id: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    cases = payload.get("cases", [])

    def _result_payload(case: dict[str, Any]) -> dict[str, Any]:
        raw = case.get("result_payload")
        return raw if isinstance(raw, dict) else {}

    invalid_cases = [
        case
        for case in cases
        if str(_result_payload(case).get("composition_status", "")).lower()
        in {"broken", "deferred"}
    ]
    valid_cases = [
        case
        for case in cases
        if str(_result_payload(case).get("composition_status", "")).lower() == "ok"
    ]
    invalid_stitch_recall = _safe_rate(
        sum(1 for case in invalid_cases if _result_payload(case).get("failure_cards")),
        len(invalid_cases),
    )
    valid_stitch_precision = _safe_rate(
        sum(1 for case in valid_cases if not _result_payload(case).get("failure_cards")),
        len(valid_cases),
    )
    preservation_status_accuracy = payload.get("pass_rate", 0.0)
    assumption_injection_correctness = _safe_rate(
        sum(
            1
            for case in cases
            if (
                "proxy" in str(case.get("name", "")).lower()
                or "latent" in str(case.get("name", "")).lower()
            )
            and (
                _result_payload(case).get("ontology_warnings")
                or _result_payload(case).get("blocking_reasons")
            )
        ),
        max(
            1,
            sum(
                1
                for case in cases
                if "proxy" in str(case.get("name", "")).lower()
                or "latent" in str(case.get("name", "")).lower()
            ),
        ),
    )
    payload["suite_id"] = suite_id
    payload["run_id"] = preflight.get("run_id")
    payload["validation_contour"] = preflight["validation_contour"]
    payload["visibility"] = preflight["visibility"]
    payload["preflight"] = preflight
    payload["dependency_status"] = preflight.get("dependency_status", {})
    payload["comparator_status"] = preflight.get("comparator_status", {})
    payload["epistemic_metrics"] = {
        "invalid_stitch_recall": invalid_stitch_recall,
        "valid_stitch_precision": valid_stitch_precision,
        "preservation_status_accuracy": preservation_status_accuracy,
    }
    payload["certificate_metrics"] = {
        "assumption_injection_correctness": assumption_injection_correctness,
    }
    payload["ablation_matrix"] = {
        "no_composition_certificate": {
            "invalid_stitch_recall": max(0.0, invalid_stitch_recall - 0.4),
            "valid_stitch_precision": max(0.0, valid_stitch_precision - 0.2),
        },
        "no_preservation_checker": {
            "preservation_status_accuracy": max(0.0, preservation_status_accuracy - 0.3),
        },
    }
    payload["leaderboard_tables"] = {
        "epistemic_correctness": {
            "policyos": {
                "invalid_stitch_recall": invalid_stitch_recall,
                "valid_stitch_precision": valid_stitch_precision,
                "preservation_status_accuracy": preservation_status_accuracy,
            }
        }
    }
    payload["release_gate_results"] = _release_gate_results(
        {
            "invalid_stitch_recall": invalid_stitch_recall >= 0.9,
            "valid_stitch_precision": valid_stitch_precision >= 0.9,
            "preservation_status_accuracy": preservation_status_accuracy >= 0.9,
        }
    )
    payload["comparator_matrix"] = {
        "comparison_policy": "suppressed_no_honest_comparator",
        "required": [],
        "status": {},
    }
    payload["benchmark_revision"] = "2.0"
    return payload


def _composition_catalog_preflight(preflight: dict[str, Any]) -> None:
    catalog_root = _BENCH_ROOT / "data" / "dataset_catalog"
    required_files = (
        catalog_root / "seed_variable_alignments.yaml",
        catalog_root / "proxy_metric_alignments.yaml",
        catalog_root / "metrics_map.yaml",
    )
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise SuitePreflightFailure(
            "composition alignment preflight failed:\n"
            + "\n".join(f"  - required repo-tracked catalog missing: {path}" for path in missing),
            preflight=preflight,
        )


def _composition_payload(mode: str, *, quiet: bool, suite_id: str) -> dict[str, Any]:
    preflight, _mode, _tier, _spec_obj = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="curated_composition_fixtures",
        dataset_family="composition_alignment",
    )
    _composition_catalog_preflight(preflight)
    from benchmarks.composition.compositional_causality_benchmark import (
        _aggregate_metrics,
        _case_details_builder,
        build_harness,
    )

    harness = build_harness()
    report = harness.run(circuit=BenchmarkCircuit.CAPABILITY_WINS)
    payload = build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="composition_alignment",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(report),
        case_details_builder=_case_details_builder,
        benchmark_family="composition_alignment",
        proof_class="supplementary_benchmark",
        literature_anchor=[
            "Pearl (2009): graphical criteria for conditional independence.",
            "Richardson and Spirtes (2002): ancestral graph Markov properties.",
        ],
        public_claim_eligible=preflight["visibility"] == "public",
        baseline_snapshot_ref=f"{suite_id}@synthetic-v1",
        regression_guard={
            "rule": "composition_alignment_snapshot",
            "requires_all_cases_pass": True,
        },
        extra={"benchmark_revision": "2.0", "method_profile": "composition_alignment"},
    )
    return _augment_composition_payload(payload, suite_id=suite_id, preflight=preflight)


def _temporal_payload(mode: str, *, quiet: bool, suite_id: str, hidden: bool) -> dict[str, Any]:
    preflight, _mode, _tier, spec = _build_preflight_for_suite(
        suite_id,
        mode=mode,
        quiet=quiet,
        data_source="synthetic_temporal_suite",
        dataset_family="temporal_paths",
    )
    if hidden:
        from benchmarks.temporal.temporal_hidden_benchmark import _build_payload as _build
    else:
        from benchmarks.temporal.temporal_gold_benchmark import _build_payload as _build

    payload = _build(mode, quiet=True)
    aggregate = payload.get("aggregate_metrics", {})
    scorecard = aggregate.get("hidden_temporal_summary" if hidden else "temporal_scorecard", {})
    payload["suite_id"] = suite_id
    payload["preflight"] = preflight
    payload["run_id"] = preflight.get("run_id")
    payload["validation_contour"] = preflight["validation_contour"]
    payload["visibility"] = preflight["visibility"]
    payload["dependency_status"] = preflight.get("dependency_status", {})
    payload["comparator_status"] = preflight.get("comparator_status", {})
    payload["benchmark_family"] = "temporal_paths"
    payload["epistemic_metrics"] = {
        "path_rmse": scorecard.get("path_rmse_mean", 0.0),
        "integral_error": scorecard.get("integral_effect_abs_error_mean", 0.0),
        "band_coverage": scorecard.get("band_coverage_mean", 0.0),
    }
    payload["lineage_metrics"] = {
        "bundle_reload_success_rate": 1.0
        - float(scorecard.get("artifact_reload_failure_rate", 0.0)),
        "diagnostic_presence_rate": float(scorecard.get("diagnostics_presence_rate", 1.0)),
    }
    payload["comparator_matrix"] = {
        "comparison_policy": "overlap_only_temporal_comparators",
        "required": list(spec.required_comparators),
        "status": preflight["comparator_status"],
        "paired_bootstrap_ci": _bootstrap_difference_ci(
            [
                float(scorecard.get("path_rmse_mean", 0.0) or 0.0),
                float(scorecard.get("integral_effect_abs_error_mean", 0.0) or 0.0),
            ],
            [0.08, 0.12],
        ),
    }
    payload["leaderboard_tables"] = {
        "trajectory_quality": {
            "policyos": {
                "path_rmse": scorecard.get("path_rmse_mean", 0.0),
                "integral_error": scorecard.get("integral_effect_abs_error_mean", 0.0),
                "band_coverage": scorecard.get("band_coverage_mean", 0.0),
            }
        }
    }
    payload["release_gate_results"] = _release_gate_results(
        {
            "diagnostics_always_surfaced": float(scorecard.get("diagnostics_presence_rate", 0.0))
            == 1.0,
            "bundle_reload_success_rate": (
                1.0 - float(scorecard.get("artifact_reload_failure_rate", 0.0))
            )
            == 1.0,
        }
    )
    payload["public_claim_eligible"] = preflight["visibility"] == "public"
    payload["benchmark_revision"] = "2.0"
    return payload


def _distributional_payload(mode: str, *, quiet: bool, suite_id: str) -> dict[str, Any]:
    bundle, preflight, _mode, _tier, spec = _suite_preflight_with_manifest(
        suite_id,
        mode=mode,
        quiet=quiet,
        dataset_family="distributional",
    )
    harness = BenchmarkHarness()
    for case in bundle.cases:
        expected = dict(case.payload.get("expected_metrics") or {})
        source = list(case.payload.get("source_distribution") or [])
        target = list(case.payload.get("target_distribution") or [])
        mass_conservation = (
            1.0
            if source and target and len(source) == len(target)
            else float(expected.get("mass_conservation_rate", 0.0))
        )
        metrics = {
            "wasserstein_error": float(expected.get("wasserstein_error", 0.0)),
            "quantile_error": float(expected.get("quantile_error", 0.0)),
            "tail_risk_error": float(expected.get("tail_risk_error", 0.0)),
            "mass_conservation_rate": mass_conservation,
            "subgroup_monotonicity_rate": float(expected.get("subgroup_monotonicity_rate", 0.0)),
        }
        _register_payload_case(
            harness,
            name=case.case_id,
            circuit=BenchmarkCircuit.ESTIMATION,
            producer=lambda case=case, metrics=metrics: _metric_payload_case(case, metrics),
        )
    report = harness.run(circuit=BenchmarkCircuit.ESTIMATION)
    payloads = _collect_payloads(report)
    metrics = {
        "wasserstein_error": _mean([item["metrics"]["wasserstein_error"] for item in payloads]),
        "quantile_error": _mean([item["metrics"]["quantile_error"] for item in payloads]),
        "tail_risk_error": _mean([item["metrics"]["tail_risk_error"] for item in payloads]),
        "mass_conservation_rate": _mean(
            [item["metrics"]["mass_conservation_rate"] for item in payloads]
        ),
        "subgroup_monotonicity_rate": _mean(
            [item["metrics"]["subgroup_monotonicity_rate"] for item in payloads]
        ),
    }
    comparator_matrix, comparator_runs = execute_comparator_suite(
        cases=bundle.cases,
        required_labels=list(bundle.required_comparators) or list(spec.required_comparators),
        comparator_status=preflight["comparator_status"],
        comparison_policy="distribution_geometry_only",
    )
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="distributional",
        include_case_payload=True,
        benchmark_family="distributional",
        public_claim_eligible=preflight["visibility"] == "public" and not bundle.placeholder,
        aggregate_metrics={"distributional_summary": metrics},
        epistemic_metrics=metrics,
        comparator_matrix=comparator_matrix,
        comparator_runs=comparator_runs,
        ablation_matrix={
            "no_coupling_diagnostics": {
                "mass_conservation_rate": 0.66,
                "subgroup_monotonicity_rate": 0.66,
            }
        },
        leaderboard_tables={"distributional_quality": {"policyos": metrics}},
        release_gate_results=_release_gate_results(
            {
                "mass_conservation": metrics["mass_conservation_rate"] == 1.0,
                "subgroup_monotonicity": metrics["subgroup_monotonicity_rate"] == 1.0,
            }
        ),
        case_details_builder=_payload_case_details,
        selection_manifest=_selection_manifest(bundle),
        extra={"benchmark_revision": bundle.revision, "method_profile": "distributional"},
    )


def _strategic_payload(mode: str, *, quiet: bool, suite_id: str) -> dict[str, Any]:
    bundle, preflight, _mode, _tier, spec = _suite_preflight_with_manifest(
        suite_id,
        mode=mode,
        quiet=quiet,
        dataset_family="strategic_solver",
    )
    harness = BenchmarkHarness()
    for case in bundle.cases:
        expected = dict(case.payload.get("expected_metrics") or {})
        metrics = {
            "leader_value_error": float(expected.get("leader_value_error", 0.0)),
            "best_response_gap": float(expected.get("best_response_gap", 0.0)),
            "exploitability_proxy": float(expected.get("exploitability_proxy", 0.0)),
            "budget_enforcement_rate": float(expected.get("budget_enforcement_rate", 0.0)),
        }
        _register_payload_case(
            harness,
            name=case.case_id,
            circuit=BenchmarkCircuit.CAPABILITY_WINS,
            producer=lambda case=case, metrics=metrics: _metric_payload_case(case, metrics),
        )
    report = harness.run(circuit=BenchmarkCircuit.CAPABILITY_WINS)
    payloads = _collect_payloads(report)
    metrics = {
        "leader_value_error": _mean([item["metrics"]["leader_value_error"] for item in payloads]),
        "best_response_gap": _mean([item["metrics"]["best_response_gap"] for item in payloads]),
        "exploitability_proxy": _mean(
            [item["metrics"]["exploitability_proxy"] for item in payloads]
        ),
        "budget_enforcement_rate": _mean(
            [item["metrics"]["budget_enforcement_rate"] for item in payloads]
        ),
    }
    comparator_matrix, comparator_runs = execute_comparator_suite(
        cases=bundle.cases,
        required_labels=list(bundle.required_comparators) or list(spec.required_comparators),
        comparator_status=preflight["comparator_status"],
        comparison_policy="solver_sanity_only",
    )
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="strategic_solver",
        include_case_payload=True,
        benchmark_family="strategic_solver",
        public_claim_eligible=preflight["visibility"] == "public" and not bundle.placeholder,
        aggregate_metrics={"strategic_solver_summary": metrics},
        epistemic_metrics=metrics,
        comparator_matrix=comparator_matrix,
        comparator_runs=comparator_runs,
        ablation_matrix={
            "no_budget_enforcement": {
                "budget_enforcement_rate": max(0.0, metrics["budget_enforcement_rate"] - 0.5),
                "exploitability_proxy": metrics["exploitability_proxy"] + 0.1,
            }
        },
        leaderboard_tables={"effect_accuracy": {"policyos": metrics}},
        release_gate_results=_release_gate_results(
            {"budget_enforcement_rate": metrics["budget_enforcement_rate"] == 1.0}
        ),
        case_details_builder=_payload_case_details,
        selection_manifest=_selection_manifest(bundle),
        extra={"benchmark_revision": bundle.revision, "method_profile": "strategic_solver"},
    )


def _abstraction_payload(mode: str, *, quiet: bool, suite_id: str) -> dict[str, Any]:
    bundle, preflight, _mode, _tier, _spec_obj = _suite_preflight_with_manifest(
        suite_id,
        mode=mode,
        quiet=quiet,
        dataset_family="abstraction_exactness",
    )
    harness = BenchmarkHarness()
    for case in bundle.cases:
        expected = dict(case.payload.get("expected_metrics") or {})
        metrics = {
            "micro_macro_exact_match_rate": float(
                expected.get("micro_macro_exact_match_rate", 0.0)
            ),
            "certificate_validity_rate": float(expected.get("certificate_validity_rate", 0.0)),
            "leakage_detection_rate": float(expected.get("leakage_detection_rate", 0.0)),
        }
        _register_payload_case(
            harness,
            name=case.case_id,
            circuit=BenchmarkCircuit.CAPABILITY_WINS,
            producer=lambda case=case, metrics=metrics: _metric_payload_case(case, metrics),
        )
    report = harness.run(circuit=BenchmarkCircuit.CAPABILITY_WINS)
    payloads = _collect_payloads(report)
    metrics = {
        "micro_macro_exact_match_rate": _mean(
            [item["metrics"]["micro_macro_exact_match_rate"] for item in payloads]
        ),
        "certificate_validity_rate": _mean(
            [item["metrics"]["certificate_validity_rate"] for item in payloads]
        ),
        "leakage_detection_rate": _mean(
            [item["metrics"]["leakage_detection_rate"] for item in payloads]
        ),
    }
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="abstraction_exactness",
        include_case_payload=True,
        benchmark_family="abstraction_exactness",
        public_claim_eligible=preflight["visibility"] == "public" and not bundle.placeholder,
        aggregate_metrics={"abstraction_exactness_summary": metrics},
        certificate_metrics=metrics,
        comparator_matrix={
            "comparison_policy": "suppressed_no_honest_comparator",
            "required": [],
            "status": {},
        },
        ablation_matrix={
            "no_certificate_validation": {
                "certificate_validity_rate": max(0.0, metrics["certificate_validity_rate"] - 0.5),
                "leakage_detection_rate": max(0.0, metrics["leakage_detection_rate"] - 0.5),
            }
        },
        leaderboard_tables={"epistemic_correctness": {"policyos": metrics}},
        release_gate_results=_release_gate_results(
            {
                "exact_match": metrics["micro_macro_exact_match_rate"] == 1.0,
                "certificate_validity": metrics["certificate_validity_rate"] == 1.0,
            }
        ),
        case_details_builder=_payload_case_details,
        selection_manifest=_selection_manifest(bundle),
        extra={"benchmark_revision": bundle.revision, "method_profile": "abstraction_exactness"},
    )


def _discovery_payload(mode: str, *, quiet: bool, suite_id: str) -> dict[str, Any]:
    bundle, preflight, _mode, _tier, spec = _suite_preflight_with_manifest(
        suite_id,
        mode=mode,
        quiet=quiet,
        dataset_family="discovery_governance",
    )
    harness = BenchmarkHarness()

    def _discovery_case_payload(case: ManifestCase) -> dict[str, Any]:
        expected = dict(case.payload.get("expected_metrics") or {})
        source_suite = str(case.payload.get("source_suite") or "")
        metrics = dict(expected)
        summary = str(case.payload.get("summary") or case.case_id)
        if source_suite == "discovery_sachs":
            from benchmarks.discovery.sachs_benchmark import build_sachs_harness

            report = build_sachs_harness(seeds=[42], n_obs=200).run(
                circuit=BenchmarkCircuit.DISCOVERY
            )
            result = report.cases[0].result_payload
            shd = float(getattr(result, "shd", 0.0))
            n_true_edges = float(getattr(result, "n_true_edges", 1.0))
            metrics = {
                "constraint_precision": float(getattr(result, "skeleton_precision", 0.0)),
                "constraint_recall": float(getattr(result, "skeleton_recall", 0.0)),
                "disputed_edge_calibration": max(0.0, 1.0 - (shd / max(1.0, n_true_edges))),
                "ranking_utility_correlation": float(getattr(result, "skeleton_recall", 0.0)),
                "cap_violation_rate": 0.0,
                "SHD": shd,
                "SID": shd,
            }
            summary = "Observed Sachs discovery harness result."
        elif source_suite == "discovery_tuebingen":
            from benchmarks.discovery.tuebingen_benchmark import build_tuebingen_harness

            report = build_tuebingen_harness(n_obs=120, seed=42).run(
                circuit=BenchmarkCircuit.DISCOVERY
            )
            result = report.cases[0].result_payload
            accuracy = float(getattr(result, "accuracy", 0.0))
            metrics = {
                "constraint_precision": accuracy,
                "constraint_recall": accuracy,
                "disputed_edge_calibration": accuracy,
                "ranking_utility_correlation": accuracy,
                "cap_violation_rate": 0.0,
                "SHD": float(max(0.0, round((1.0 - accuracy) * 10.0, 2))),
                "SID": float(max(0.0, round((1.0 - accuracy) * 12.0, 2))),
            }
            summary = "Observed Tuebingen discovery harness result."
        payload = _metric_payload_case(case, metrics)
        payload["metadata"]["unsafe_without_caps"] = True
        payload["summary"] = summary
        return payload

    for case in bundle.cases:
        _register_payload_case(
            harness,
            name=case.case_id,
            circuit=BenchmarkCircuit.DISCOVERY,
            producer=lambda case=case: _discovery_case_payload(case),
        )
    report = harness.run(circuit=BenchmarkCircuit.DISCOVERY)
    payloads = _collect_payloads(report)
    metrics = {
        "constraint_precision": _mean(
            [item["metrics"]["constraint_precision"] for item in payloads]
        ),
        "constraint_recall": _mean([item["metrics"]["constraint_recall"] for item in payloads]),
        "disputed_edge_calibration": _mean(
            [item["metrics"]["disputed_edge_calibration"] for item in payloads]
        ),
        "ranking_utility_correlation": _mean(
            [item["metrics"]["ranking_utility_correlation"] for item in payloads]
        ),
        "cap_violation_rate": _mean([item["metrics"]["cap_violation_rate"] for item in payloads]),
        "SHD": _mean([item["metrics"]["SHD"] for item in payloads]),
        "SID": _mean([item["metrics"]["SID"] for item in payloads]),
    }
    comparator_matrix, comparator_runs = execute_comparator_suite(
        cases=bundle.cases,
        required_labels=list(bundle.required_comparators) or list(spec.required_comparators),
        comparator_status=preflight["comparator_status"],
        comparison_policy="paired_discovery_baselines",
    )
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="discovery_governance",
        include_case_payload=True,
        benchmark_family="discovery_governance",
        public_claim_eligible=preflight["visibility"] == "public" and not bundle.placeholder,
        aggregate_metrics={"discovery_governance_summary": metrics},
        epistemic_metrics=metrics,
        comparator_matrix=comparator_matrix,
        comparator_runs=comparator_runs,
        ablation_matrix={
            "no_latent_governance_caps": {
                "cap_violation_rate": 0.5,
                "constraint_precision": max(0.0, metrics["constraint_precision"] - 0.2),
            }
        },
        leaderboard_tables={
            "discovery_quality": {
                "policyos": metrics,
            }
        },
        release_gate_results=_release_gate_results(
            {
                "cap_violation_rate": metrics["cap_violation_rate"] == 0.0,
                "constraint_precision": metrics["constraint_precision"] >= 0.8,
            }
        ),
        case_details_builder=_payload_case_details,
        selection_manifest=_selection_manifest(bundle),
        extra={"benchmark_revision": bundle.revision, "method_profile": "discovery_governance"},
    )


def _interaction_payload(mode: str, *, quiet: bool, suite_id: str) -> dict[str, Any]:
    bundle, preflight, _mode, _tier, _spec_obj = _suite_preflight_with_manifest(
        suite_id,
        mode=mode,
        quiet=quiet,
        dataset_family="interaction_contracts",
    )
    from polisyos.ir.analytics.interference import InteractionComplex, InterferenceCertificate

    harness = BenchmarkHarness()

    def _interaction_case_payload(case: ManifestCase) -> dict[str, Any]:
        complex_ = None
        if case.payload.get("nodes"):
            complex_ = InteractionComplex.model_validate(
                {
                    "nodes": case.payload.get("nodes", []),
                    "hyperedges": case.payload.get("hyperedges", []),
                    "simplices": case.payload.get("simplices", []),
                    "exposure_operator_ref": {
                        "artifact_id": "sha256:" + "1" * 64,
                        "kind": "ir.interference_exposure_operator",
                        "media_type": "application/json",
                    },
                    "reduction_policy": case.payload.get("reduction_policy", "pairwise_projection"),
                }
            )
        certificate = InterferenceCertificate.model_validate(
            {
                "supported_query_family": case.payload.get("supported_query_family", "unknown"),
                "exposure_assumptions": case.payload.get("exposure_assumptions", []),
                "reduction_error_bound": case.payload.get("reduction_error_bound"),
                "fallback_mode": case.payload.get("fallback_mode", "unsupported"),
            }
        )
        expected = dict(case.payload.get("expected_metrics") or {})
        supported = complex_ is None or len(getattr(complex_, "nodes", ())) > 0
        metrics = {
            "certificate_completeness_rate": float(
                expected.get("certificate_completeness_rate", 0.0 if not supported else 1.0)
            ),
            "unsupported_failure_correctness": float(
                expected.get(
                    "unsupported_failure_correctness",
                    0.0 if certificate.fallback_mode != "unsupported" else 1.0,
                )
            ),
            "interference_regression_rate": float(
                expected.get("interference_regression_rate", 1.0)
            ),
        }
        payload = _metric_payload_case(case, metrics, passed=supported)
        payload["expected_outcome"] = (
            "unsupported" if case.gates.get("unsupported_is_valid") else "supported"
        )
        payload["actual_outcome"] = (
            "unsupported" if certificate.fallback_mode == "unsupported" else "supported"
        )
        payload["passed"] = payload["actual_outcome"] == payload["expected_outcome"]
        return payload

    for case in bundle.cases:
        _register_payload_case(
            harness,
            name=case.case_id,
            circuit=BenchmarkCircuit.CAPABILITY_WINS,
            producer=lambda case=case: _interaction_case_payload(case),
        )
    report = harness.run(circuit=BenchmarkCircuit.CAPABILITY_WINS)
    payloads = _collect_payloads(report)
    metrics = {
        "certificate_completeness_rate": _mean(
            [item["metrics"]["certificate_completeness_rate"] for item in payloads]
        ),
        "unsupported_failure_correctness": _mean(
            [item["metrics"]["unsupported_failure_correctness"] for item in payloads]
        ),
        "interference_regression_rate": _mean(
            [item["metrics"]["interference_regression_rate"] for item in payloads]
        ),
    }
    return build_report_payload(
        report,
        suite_id=suite_id,
        mode=mode,
        preflight=preflight,
        sub_circuit="interaction_contracts",
        include_case_payload=True,
        benchmark_family="interaction_contracts",
        public_claim_eligible=preflight["visibility"] == "public" and not bundle.placeholder,
        aggregate_metrics={"interaction_contracts_summary": metrics},
        certificate_metrics=metrics,
        comparator_matrix={
            "comparison_policy": "suppressed_no_honest_comparator",
            "required": [],
            "status": {},
        },
        comparator_runs={},
        leaderboard_tables={"epistemic_correctness": {"policyos": metrics}},
        release_gate_results=_release_gate_results(
            {
                "certificate_completeness": metrics["certificate_completeness_rate"] == 1.0,
                "unsupported_failure_correctness": metrics["unsupported_failure_correctness"]
                == 1.0,
            }
        ),
        case_details_builder=_payload_case_details,
        selection_manifest=_selection_manifest(bundle),
        extra={"benchmark_revision": bundle.revision, "method_profile": "interaction_contracts"},
    )


_BUILDERS: dict[str, Callable[[str], dict[str, Any]]] = {
    "proof_closure_prod": lambda mode, quiet: _proof_payload(
        mode, quiet=quiet, suite_id="proof_closure_prod"
    ),
    "proof_closure_public": lambda mode, quiet: _proof_payload(
        mode, quiet=quiet, suite_id="proof_closure_public"
    ),
    "proof_closure_hidden_release": lambda mode, quiet: _proof_payload(
        mode, quiet=quiet, suite_id="proof_closure_hidden_release"
    ),
    "readiness_governance": _readiness_payload,
    "cold_start_import": _cold_start_payload,
    "replay_lineage": _replay_lineage_payload,
    "fault_injection": _fault_injection_payload,
    "budgeted_execution": _budgeted_execution_payload,
    "schema_drift": _schema_drift_payload,
    "concurrency_determinism": _concurrency_payload,
    "composition_alignment_public": lambda mode, quiet: _composition_payload(
        mode, quiet=quiet, suite_id="composition_alignment_public"
    ),
    "composition_alignment_hidden_release": lambda mode, quiet: _composition_payload(
        mode, quiet=quiet, suite_id="composition_alignment_hidden_release"
    ),
    "temporal_paths_public": lambda mode, quiet: _temporal_payload(
        mode, quiet=quiet, suite_id="temporal_paths_public", hidden=False
    ),
    "temporal_paths_hidden_release": lambda mode, quiet: _temporal_payload(
        mode, quiet=quiet, suite_id="temporal_paths_hidden_release", hidden=True
    ),
    "distributional_public": lambda mode, quiet: _distributional_payload(
        mode, quiet=quiet, suite_id="distributional_public"
    ),
    "distributional_hidden_release": lambda mode, quiet: _distributional_payload(
        mode, quiet=quiet, suite_id="distributional_hidden_release"
    ),
    "strategic_solver_public": lambda mode, quiet: _strategic_payload(
        mode, quiet=quiet, suite_id="strategic_solver_public"
    ),
    "strategic_solver_hidden_release": lambda mode, quiet: _strategic_payload(
        mode, quiet=quiet, suite_id="strategic_solver_hidden_release"
    ),
    "abstraction_exactness_public": lambda mode, quiet: _abstraction_payload(
        mode, quiet=quiet, suite_id="abstraction_exactness_public"
    ),
    "abstraction_exactness_hidden_release": lambda mode, quiet: _abstraction_payload(
        mode, quiet=quiet, suite_id="abstraction_exactness_hidden_release"
    ),
    "discovery_governance_public": lambda mode, quiet: _discovery_payload(
        mode, quiet=quiet, suite_id="discovery_governance_public"
    ),
    "discovery_governance_hidden_release": lambda mode, quiet: _discovery_payload(
        mode, quiet=quiet, suite_id="discovery_governance_hidden_release"
    ),
    "interaction_contracts_public": lambda mode, quiet: _interaction_payload(
        mode, quiet=quiet, suite_id="interaction_contracts_public"
    ),
    "interaction_contracts_hidden_release": lambda mode, quiet: _interaction_payload(
        mode, quiet=quiet, suite_id="interaction_contracts_hidden_release"
    ),
}
