#!/usr/bin/env python3
"""Compare Policy Design Case coverage rebaseline directories."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_coverage as coverage

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.rebaseline_diff.v1"
TOOL_NAME = "quality.validation.compare-policy-design-case-rebaseline"
DEFAULT_DIFF_FILENAME = "diff_from_wave_N_minus_1.json"


class RebaselineInputError(ValueError):
    """Raised when a rebaseline input cannot be read."""


def compare_rebaseline(
    *,
    current_dir: Path,
    previous_dir: Path,
    repo_root: Path = REPO_ROOT,
    metric_definitions: Mapping[str, Mapping[str, Any]] = coverage.METRIC_DEFINITIONS,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    current_payload = _load_coverage_dir(current_dir, required=True)
    previous_payload = _load_coverage_dir(previous_dir, required=False)
    coverage.validate_metric_definitions(metric_definitions)
    if previous_payload is None:
        return _no_prior_payload(
            current_dir=current_dir,
            previous_dir=previous_dir,
            current_payload=current_payload,
            repo_root=repo_root,
        )

    comparisons = {
        "missing": [],
        "improved": [],
        "regressed": [],
        "denominator_changed": [],
        "unchanged": [],
    }
    violations: list[dict[str, Any]] = []
    current_metrics = _metrics(current_payload)
    previous_metrics = _metrics(previous_payload)
    for metric_id in coverage.REQUIRED_METRIC_IDS:
        current = current_metrics.get(metric_id)
        previous = previous_metrics.get(metric_id)
        if current is None:
            row = {"metric_id": metric_id, "reason": "missing_from_current_coverage"}
            comparisons["missing"].append(row)
            violations.append(
                {
                    "code": "pdc_coverage_metric_missing",
                    "metric_id": metric_id,
                    "message": (
                        "Required Policy Design Case metric is missing from current "
                        "coverage.json."
                    ),
                }
            )
            continue
        if previous is None:
            comparisons["improved"].append(
                _comparison_row(metric_id, current=current, previous=None)
                | {"reason": "new_current_metric"}
            )
            continue
        denominator_changed = _denominator(current) != _denominator(previous) or bool(
            current.get("denominator_changed")
        )
        row = _comparison_row(
            metric_id,
            current=current,
            previous=previous,
            denominator_changed=denominator_changed,
        )
        if denominator_changed:
            comparisons["denominator_changed"].append(row)
        movement = _movement(
            metric_id,
            current=current,
            previous=previous,
            metric_definitions=metric_definitions,
        )
        comparisons[movement].append(row)
        if movement == "regressed":
            violations.append(
                {
                    "code": "pdc_coverage_metric_regressed",
                    "metric_id": metric_id,
                    "message": (
                        "Policy Design Case coverage metric regressed from the previous "
                        "baseline."
                    ),
                    "comparison": row,
                }
            )

    status = "fail" if violations else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "repo_root": str(repo_root),
        "current": _coverage_ref(current_dir, current_payload),
        "previous": _coverage_ref(previous_dir, previous_payload),
        "typed_result": {"type": status},
        "comparisons": comparisons,
        "violations": violations,
        "summary": {
            "missing": len(comparisons["missing"]),
            "improved": len(comparisons["improved"]),
            "regressed": len(comparisons["regressed"]),
            "denominator_changed": len(comparisons["denominator_changed"]),
            "unchanged": len(comparisons["unchanged"]),
            "violation_count": len(violations),
        },
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_text(payload: Mapping[str, Any]) -> str:
    lines = [
        f"{TOOL_NAME}: {payload['status']}",
        (
            "missing={missing} improved={improved} regressed={regressed} "
            "denominator_changed={denominator_changed} violations={violation_count}"
        ).format(**payload["summary"]),
    ]
    for violation in payload.get("violations", []):
        if isinstance(violation, dict):
            lines.append(
                f"[fail] {violation['metric_id']} {violation['code']}: {violation['message']}"
            )
    return "\n".join(lines) + "\n"


def _no_prior_payload(
    *,
    current_dir: Path,
    previous_dir: Path,
    current_payload: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    metrics = _metrics(current_payload)
    improved = [
        {
            "metric_id": metric_id,
            "current_value": _value(row),
            "previous_value": None,
            "reason": "no_prior_baseline",
        }
        for metric_id, row in sorted(metrics.items())
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": "no_prior_baseline",
        "repo_root": str(repo_root),
        "current": _coverage_ref(current_dir, current_payload),
        "previous": {
            "directory": str(previous_dir),
            "coverage_json": str(previous_dir / "coverage.json"),
            "status": "missing",
        },
        "typed_result": {
            "type": "no_prior_baseline",
            "message": "Previous Policy Design Case coverage baseline is absent.",
        },
        "comparisons": {
            "missing": [],
            "improved": improved,
            "regressed": [],
            "denominator_changed": [],
            "unchanged": [],
        },
        "violations": [],
        "summary": {
            "missing": 0,
            "improved": len(improved),
            "regressed": 0,
            "denominator_changed": 0,
            "unchanged": 0,
            "violation_count": 0,
        },
    }


def _load_coverage_dir(path: Path, *, required: bool) -> dict[str, Any] | None:
    coverage_path = path / "coverage.json"
    try:
        payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        if required:
            raise RebaselineInputError(f"coverage.json not found: {coverage_path}") from exc
        return None
    except json.JSONDecodeError as exc:
        raise RebaselineInputError(
            f"coverage.json is invalid JSON: {coverage_path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise RebaselineInputError(f"coverage.json must be a JSON object: {coverage_path}")
    return dict(payload)


def _metrics(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        return {}
    return {
        str(metric_id): dict(metric)
        for metric_id, metric in metrics.items()
        if isinstance(metric, Mapping)
    }


def _movement(
    metric_id: str,
    *,
    current: Mapping[str, Any],
    previous: Mapping[str, Any],
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> str:
    current_value = _value(current)
    previous_value = _value(previous)
    if (
        current_value is None
        or previous_value is None
        or math.isclose(current_value, previous_value)
    ):
        return "unchanged"
    direction = str(metric_definitions[metric_id]["direction"])
    if direction == "lower_is_better":
        return "improved" if current_value < previous_value else "regressed"
    return "improved" if current_value > previous_value else "regressed"


def _comparison_row(
    metric_id: str,
    *,
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    denominator_changed: bool = False,
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "current_value": _value(current),
        "previous_value": _value(previous) if previous is not None else None,
        "current_numerator": current.get("numerator"),
        "current_denominator": current.get("denominator"),
        "previous_numerator": previous.get("numerator") if previous is not None else None,
        "previous_denominator": previous.get("denominator") if previous is not None else None,
        "denominator_changed": denominator_changed,
        "current_denominator_changed_flag": bool(current.get("denominator_changed")),
    }


def _coverage_ref(directory: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return {
        "directory": str(directory),
        "coverage_json": str(directory / "coverage.json"),
        "schema_version": payload.get("schema_version"),
        "status": summary.get("status") if isinstance(summary, Mapping) else payload.get("status"),
    }


def _value(metric: Mapping[str, Any] | None) -> float | None:
    if metric is None:
        return None
    value = metric.get("value")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _denominator(metric: Mapping[str, Any]) -> float | None:
    denominator = metric.get("denominator")
    if isinstance(denominator, bool) or denominator is None:
        return None
    try:
        return float(denominator)
    except (TypeError, ValueError):
        return None


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    current = _resolve(repo_root, args.current)
    previous = _resolve(repo_root, args.previous)
    try:
        payload = compare_rebaseline(
            current_dir=current,
            previous_dir=previous,
            repo_root=repo_root,
        )
    except (RebaselineInputError, coverage.CoverageDefinitionError) as exc:
        sys.stderr.write(f"policy design case rebaseline comparison failed: {exc}\n")
        return 2

    rendered = dump_json(payload) if args.output_format == "json" else render_text(payload)
    output = (
        _resolve(repo_root, args.output)
        if args.output is not None
        else current / DEFAULT_DIFF_FILENAME
    )
    atomic_write_text(output, rendered)
    sys.stdout.write(rendered)
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
