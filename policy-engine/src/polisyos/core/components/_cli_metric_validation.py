"""CLI sub-module: formal metric validation reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from polisyos.core.components._cli_store import build_cli_filesystem_cas
from polisyos.scientist.validation.metrics import (
    TestConfig,
    compare_metric_family,
    load_metric_observation_bundle,
)
from polisyos.ir.analytics.metric_validation_report import MetricValidationReport, persist_metric_validation_report
from polisyos.core.contracts.foundry import MetricObservationBundleRef

__all__ = ["_cmd_metric_validate"]


def _cmd_metric_validate(args: Any) -> int:
    cas = build_cli_filesystem_cas(Path(args.cas_root))
    ref = MetricObservationBundleRef(
        artifact_id=_normalize_artifact_id(args.observation_bundle_ref),
        kind="foundry.metric_observation_bundle",
        media_type="application/json",
    )
    try:
        bundle = load_metric_observation_bundle(cas, ref)
    except Exception as exc:
        print(f"ERROR: failed to load observation bundle: {exc}", file=sys.stderr)
        return 2

    try:
        report = compare_metric_family(
            bundle=bundle,
            baseline_model_id=args.baseline,
            candidate_model_ids=list(args.candidates),
            metric_ids=list(args.metrics),
            config=TestConfig(
                alpha=args.alpha,
                alternative=args.alternative,
                n_resamples=args.n_resamples,
                confidence_level=args.confidence_level,
                correction=args.correction,
                random_seed=args.random_seed,
                exact_if_feasible=bool(args.exact_if_feasible),
            ),
            family_scope=args.family_scope,
        )
    except Exception as exc:
        print(f"ERROR: metric validation failed: {exc}", file=sys.stderr)
        return 1

    report_ref = persist_metric_validation_report(
        cas,
        report,
    )
    payload = _render_payload(report, report_ref.artifact_id.root, args.format)
    rendered = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"metric_validation_report={args.output}")
    else:
        print(rendered)
    return 0


def _normalize_artifact_id(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("sha256:"):
        return normalized
    return f"sha256:{normalized}"


def _render_payload(
    report: MetricValidationReport,
    artifact_id: str,
    format_name: str,
) -> dict[str, Any]:
    if format_name == "json":
        payload = report.model_dump(mode="json")
        payload["cas_artifact_id"] = artifact_id
        return payload
    if format_name == "avro-json":
        payload = report.model_dump(mode="json")
        payload["avro_schema"] = "polisyos.scientist.metric_validation_report"
        payload["cas_artifact_id"] = artifact_id
        return payload
    if format_name == "proto-json":
        payload = _camelize_keys(report.model_dump(mode="json"))
        payload["casArtifactId"] = artifact_id
        return payload
    return _summary_payload(report, artifact_id)


def _summary_payload(report: MetricValidationReport, artifact_id: str) -> dict[str, Any]:
    improvements: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    for comparison in report.comparisons:
        significance = comparison.significance
        is_significant = (
            significance.reject_null_adj
            if significance.reject_null_adj is not None
            else significance.reject_null_raw
        )
        if not is_significant:
            continue
        item = {
            "baseline": comparison.baseline_model_id,
            "candidate": comparison.candidate_model_id,
            "metric": comparison.metric_id,
            "delta": comparison.delta_value,
            "p_adj": significance.p_value_adj,
        }
        if _is_improvement(comparison.metric_direction, comparison.delta_value):
            improvements.append(item)
        else:
            regressions.append(item)
    return {
        "family_method": report.family_adjustment.method,
        "alpha": report.family_adjustment.alpha,
        "comparison_count": len(report.comparisons),
        "significant_improvements": improvements,
        "significant_regressions": regressions,
        "cas_artifact_id": artifact_id,
    }


def _is_improvement(metric_direction: str, delta_value: float) -> bool:
    if metric_direction == "lower_is_better":
        return delta_value < 0.0
    return delta_value > 0.0


def _camelize_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {_snake_to_camel(key): _camelize_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camelize_keys(item) for item in value]
    return value


def _snake_to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)
