#!/usr/bin/env python3
"""Build the Honest Diagnostics substrate coverage dashboard."""

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

from polisyos.runtime.quality.invariants import MINIMUM_CLOSEOUT_GATES  # noqa: E402
from tools.quality.validation import (
    honest_diagnostics_coverage_metrics as _coverage_metrics,  # noqa: E402
)

METRIC_DEFINITIONS = _coverage_metrics.METRIC_DEFINITIONS
REQUIRED_METRIC_IDS = _coverage_metrics.REQUIRED_METRIC_IDS
REQUIRED_INVARIANT_FIELDS = _coverage_metrics.REQUIRED_INVARIANT_FIELDS
REQUIRED_STRING_INVARIANT_FIELDS = _coverage_metrics.REQUIRED_STRING_INVARIANT_FIELDS
REQUIRED_LIST_INVARIANT_FIELDS = _coverage_metrics.REQUIRED_LIST_INVARIANT_FIELDS
OPTIONAL_LIST_INVARIANT_FIELDS = _coverage_metrics.OPTIONAL_LIST_INVARIANT_FIELDS
CoverageDefinitionError = _coverage_metrics.CoverageDefinitionError
CoverageInputError = _coverage_metrics.CoverageInputError


def _coverage_metric_dependencies(
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> _coverage_metrics.CoverageMetricDependencies:
    """Bind metric calculation to the facade's current public contract values."""

    return _coverage_metrics.CoverageMetricDependencies(
        metric_definitions=metric_definitions,
        required_metric_ids=REQUIRED_METRIC_IDS,
        minimum_closeout_gates=MINIMUM_CLOSEOUT_GATES,
        required_invariant_fields=REQUIRED_INVARIANT_FIELDS,
        required_string_invariant_fields=REQUIRED_STRING_INVARIANT_FIELDS,
        required_list_invariant_fields=REQUIRED_LIST_INVARIANT_FIELDS,
        optional_list_invariant_fields=OPTIONAL_LIST_INVARIANT_FIELDS,
    )


def validate_metric_definitions(
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> None:
    """Validate definitions against the facade's current required-ID binding."""

    _coverage_metrics.validate_metric_definitions(
        metric_definitions,
        dependencies=_coverage_metric_dependencies(metric_definitions),
    )


SCHEMA_VERSION = "policyos.honest_diagnostics_coverage.v1"
TOOL_NAME = "quality.validation.build-honest-diagnostics-coverage"
GENERATED_AT = "2026-05-15T00:00:00Z"
DEFAULT_REGISTRY = Path("architecture/production_quality/invariant_registry.toml")
DEFAULT_OUTPUT_DIR = Path("_build/honest-diagnostics/coverage")
DEFAULT_OPERATIONAL_CLOSEOUT_REPORT = Path(
    "_build/honest-diagnostics/rebaseline/wave-4/wave4_operational_closeout.json"
)


def build_coverage_payload(
    *,
    repo_root: Path = REPO_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    operational_closeout_report_path: Path | None = DEFAULT_OPERATIONAL_CLOSEOUT_REPORT,
    wave5_metamorphic_report_path: Path | None = None,
    wave5_resilience_report_path: Path | None = None,
    wave5_replay_report_path: Path | None = None,
    substrate_drift_report_path: Path | None = None,
    metric_definitions: Mapping[str, Mapping[str, Any]] = METRIC_DEFINITIONS,
    wave: str | None = None,
    require_targets: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    registry_file = _resolve(repo_root, registry_path)
    validate_metric_definitions(metric_definitions)
    dependencies = _coverage_metric_dependencies(metric_definitions)
    invariants = _coverage_metrics._load_invariants(registry_file)
    closeout_report = _coverage_metrics._load_optional_closeout_report(
        _resolve(repo_root, operational_closeout_report_path)
        if operational_closeout_report_path is not None
        else None
    )
    wave5_metamorphic_report = _coverage_metrics._load_optional_json_report(
        _resolve(repo_root, wave5_metamorphic_report_path)
        if wave5_metamorphic_report_path is not None
        else None
    )
    wave5_resilience_report = _coverage_metrics._load_optional_json_report(
        _resolve(repo_root, wave5_resilience_report_path)
        if wave5_resilience_report_path is not None
        else None
    )
    wave5_replay_report = _coverage_metrics._load_optional_json_report(
        _resolve(repo_root, wave5_replay_report_path)
        if wave5_replay_report_path is not None
        else None
    )
    substrate_drift_report = _coverage_metrics._load_optional_json_report(
        _resolve(repo_root, substrate_drift_report_path)
        if substrate_drift_report_path is not None
        else None
    )
    metric_rows = _coverage_metrics._build_metric_rows(
        invariants,
        dependencies,
        closeout_report,
        wave5_metamorphic_report=wave5_metamorphic_report,
        wave5_resilience_report=wave5_resilience_report,
        wave5_replay_report=wave5_replay_report,
    )
    invalid_invariants = _coverage_metrics._invalid_invariants(
        invariants, dependencies=dependencies
    )
    missing_evidence = _coverage_metrics._missing_wave5_evidence(
        require_targets=require_targets,
        wave5_metamorphic_report=wave5_metamorphic_report,
        wave5_resilience_report=wave5_resilience_report,
        wave5_replay_report=wave5_replay_report,
        substrate_drift_report=substrate_drift_report,
    )
    target_violations = (
        _coverage_metrics._target_violations(metric_rows, wave=wave)
        if require_targets and wave is not None
        else []
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": GENERATED_AT,
        "repo_root": str(repo_root),
        "source": {
            "invariant_registry": _rel(registry_file, repo_root),
            "invariant_count": len(invariants),
            "operational_closeout_report": (
                _rel(
                    _resolve(repo_root, operational_closeout_report_path),
                    repo_root,
                )
                if operational_closeout_report_path is not None
                and _resolve(repo_root, operational_closeout_report_path).is_file()
                else None
            ),
            "wave5_metamorphic_report": (
                _rel(_resolve(repo_root, wave5_metamorphic_report_path), repo_root)
                if wave5_metamorphic_report_path is not None
                else None
            ),
            "wave5_resilience_report": (
                _rel(_resolve(repo_root, wave5_resilience_report_path), repo_root)
                if wave5_resilience_report_path is not None
                else None
            ),
            "wave5_replay_report": (
                _rel(_resolve(repo_root, wave5_replay_report_path), repo_root)
                if wave5_replay_report_path is not None
                else None
            ),
            "substrate_drift_report": (
                _rel(_resolve(repo_root, substrate_drift_report_path), repo_root)
                if substrate_drift_report_path is not None
                else None
            ),
        },
        "summary": {
            "status": (
                "pass"
                if not invalid_invariants and not target_violations and not missing_evidence
                else "fail"
            ),
            "metric_count": len(metric_rows),
            "required_metric_count": len(REQUIRED_METRIC_IDS),
            "invariant_count": len(invariants),
            "known_minimum_closeout_gate_count": len(MINIMUM_CLOSEOUT_GATES),
            "invalid_invariant_count": len(invalid_invariants),
            "target_violation_count": len(target_violations),
            "missing_evidence_count": len(missing_evidence),
            "wave": wave,
        },
        "metrics": metric_rows,
        "invalid_invariants": invalid_invariants,
        "missing_evidence": missing_evidence,
        "target_violations": target_violations,
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["metrics"]
    if not isinstance(metrics, Mapping):
        raise CoverageInputError("Coverage payload metrics must be a mapping.")
    source = payload["source"]
    summary = payload["summary"]
    lines = [
        "# Honest Diagnostics Coverage",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Invariant registry: `{source['invariant_registry']}`",
        f"- Invariants: {source['invariant_count']}",
        f"- Status: `{summary['status']}`",
        "",
        "## Metrics",
        "",
        (
            "| Metric | Value | Numerator | Denominator | Denominator Changed | "
            "Wave 0 | Wave 1 | Wave 3 | Wave 4 | Final |"
        ),
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for metric_id in REQUIRED_METRIC_IDS:
        row = metrics[metric_id]
        definition = row["definition"]
        target = definition["target"]
        lines.append(
            "| "
            f"`{metric_id}` | {_render_value(row['value'])} | "
            f"{_render_value(row['numerator'])} | {_render_value(row['denominator'])} | "
            f"{str(row['denominator_changed']).lower()} | "
            f"{target['wave0']} | {target['wave1']} | {target['wave3']} | "
            f"{target.get('wave4', '')} | {target['final']} |"
        )

    invalid = payload.get("invalid_invariants")
    if invalid:
        lines.extend(["", "## Invalid Invariants", ""])
        for row in invalid:
            lines.append(f"- `{row['invariant_id']}` missing: {', '.join(row['missing_fields'])}")

    return "\n".join(lines) + "\n"


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _render_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--wave", choices=("wave-0", "wave-1", "wave-3", "wave-4", "final"))
    parser.add_argument(
        "--operational-closeout-report",
        type=Path,
        default=DEFAULT_OPERATIONAL_CLOSEOUT_REPORT,
    )
    parser.add_argument("--wave5-metamorphic-report", type=Path)
    parser.add_argument("--wave5-resilience-report", type=Path)
    parser.add_argument("--wave5-replay-report", type=Path)
    parser.add_argument("--substrate-drift-report", type=Path)
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        help=(
            "Use the Wave 4 operational closeout report written inside this bundle "
            "when --operational-closeout-report is not set."
        ),
    )
    parser.add_argument("--require-targets", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if any invariant row is incomplete.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = _resolve(repo_root, args.output_dir)
    json_output = (
        _resolve(repo_root, args.json_output) if args.json_output else output_dir / "coverage.json"
    )
    markdown_output = (
        _resolve(repo_root, args.markdown_output)
        if args.markdown_output
        else output_dir / "coverage.md"
    )

    try:
        payload = build_coverage_payload(
            repo_root=repo_root,
            registry_path=args.registry,
            operational_closeout_report_path=(
                args.operational_closeout_report
                if args.operational_closeout_report != DEFAULT_OPERATIONAL_CLOSEOUT_REPORT
                else (
                    args.bundle_dir / "quality_evidence" / "wave4_operational_closeout.json"
                    if args.bundle_dir is not None
                    else args.operational_closeout_report
                )
            ),
            wave5_metamorphic_report_path=args.wave5_metamorphic_report,
            wave5_resilience_report_path=args.wave5_resilience_report,
            wave5_replay_report_path=args.wave5_replay_report,
            substrate_drift_report_path=args.substrate_drift_report,
            wave=args.wave,
            require_targets=args.require_targets,
        )
    except (CoverageDefinitionError, CoverageInputError) as exc:
        sys.stderr.write(f"honest diagnostics coverage failed: {exc}\n")
        return 2

    atomic_write_text(json_output, dump_json(payload))
    atomic_write_text(markdown_output, render_markdown(payload))
    if (args.check or args.require_targets) and payload["summary"]["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
