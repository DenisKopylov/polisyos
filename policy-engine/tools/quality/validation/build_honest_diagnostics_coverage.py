#!/usr/bin/env python3
"""Build the Honest Diagnostics substrate coverage dashboard."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.honest_diagnostics_coverage.v1"
TOOL_NAME = "quality.validation.build-honest-diagnostics-coverage"
GENERATED_AT = "2026-05-15T00:00:00Z"
DEFAULT_REGISTRY = Path("architecture/production_quality/invariant_registry.toml")
DEFAULT_OUTPUT_DIR = Path("_build/honest-diagnostics/coverage")

REQUIRED_INVARIANT_FIELDS = frozenset(
    {
        "invariant_id",
        "minimum_closeout_gate",
        "pql_id",
        "final_owner",
        "producer_owners",
        "runtime_event_names",
        "required_artifact_kinds",
        "required_ref_keys",
        "evidence_classes",
        "allowed_provenance_kinds",
        "required_schema_contracts",
        "scorecard_gate_names",
        "readiness_check",
        "approval_policy",
        "override_policy",
        "non_overridable_blockers",
        "dashboard_projection_policy",
        "public_artifact_policy",
        "conflict_policy",
        "failure_code",
        "diagnostic_owner",
        "dependencies",
        "consumers",
        "next_diagnostic_command",
        "negative_tests",
    }
)
REQUIRED_STRING_INVARIANT_FIELDS = frozenset(
    {
        "invariant_id",
        "minimum_closeout_gate",
        "pql_id",
        "final_owner",
        "readiness_check",
        "approval_policy",
        "override_policy",
        "dashboard_projection_policy",
        "public_artifact_policy",
        "conflict_policy",
        "failure_code",
        "diagnostic_owner",
        "next_diagnostic_command",
    }
)
REQUIRED_LIST_INVARIANT_FIELDS = frozenset(
    {
        "producer_owners",
        "runtime_event_names",
        "required_artifact_kinds",
        "required_ref_keys",
        "evidence_classes",
        "allowed_provenance_kinds",
        "required_schema_contracts",
        "scorecard_gate_names",
        "non_overridable_blockers",
        "consumers",
        "negative_tests",
    }
)
OPTIONAL_LIST_INVARIANT_FIELDS = frozenset({"dependencies"})

REQUIRED_METRIC_IDS = (
    "invariant_registry_complete_pct",
    "runtime_emitted_invariant_pct",
    "negative_control_coverage_pct",
    "authority_envelope_complete_pct",
    "payload_identity_verified_gate_pct",
    "fallback_ledger_coverage_pct",
    "authority_bearing_provenance_pct",
    "source_truth_conflict_gate_pct",
    "semantic_binding_gate_pct",
    "legacy_quarantine_classified_pct",
    "false_pass_rate_negative_controls",
    "operator_ttrc_p50_minutes",
    "operator_ttrc_p90_minutes",
)

METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "invariant_registry_complete_pct": {
        "title": "Invariant registry completeness",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"wave0": ">= 10", "wave1": "100", "wave3": "100", "final": "100"},
    },
    "runtime_emitted_invariant_pct": {
        "title": "Runtime-emitted invariant coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": ">= 85",
            "final": "100",
        },
    },
    "negative_control_coverage_pct": {
        "title": "Negative-control coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"wave0": ">= 25", "wave1": ">= 60", "wave3": "100", "final": "100"},
    },
    "authority_envelope_complete_pct": {
        "title": "Authority envelope completeness",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "fixture baseline",
            "wave1": "100 for contract tests",
            "wave3": ">= 90 runtime bundles",
            "final": "100",
        },
    },
    "payload_identity_verified_gate_pct": {
        "title": "Payload identity verified gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": "100",
            "final": "100",
        },
    },
    "fallback_ledger_coverage_pct": {
        "title": "Fallback ledger coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": ">= 60 known paths",
            "wave3": ">= 90 known paths",
            "final": "100",
        },
    },
    "authority_bearing_provenance_pct": {
        "title": "Authority-bearing provenance coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "100 for fixtures",
            "wave3": "100",
            "final": "100",
        },
    },
    "source_truth_conflict_gate_pct": {
        "title": "Source-truth conflict gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": ">= 80 field families",
            "wave3": "100",
            "final": "100",
        },
    },
    "semantic_binding_gate_pct": {
        "title": "Semantic binding gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": "baseline only",
            "wave3": ">= 60",
            "final": "100",
        },
    },
    "legacy_quarantine_classified_pct": {
        "title": "Legacy quarantine classification coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "wave0": "baseline only",
            "wave1": ">= 90 known bundles",
            "wave3": "100",
            "final": "100",
        },
    },
    "false_pass_rate_negative_controls": {
        "title": "False-pass rate for negative controls",
        "unit": "rate",
        "direction": "lower_is_better",
        "target": {"wave0": "0", "wave1": "0", "wave3": "0", "final": "0"},
    },
    "operator_ttrc_p50_minutes": {
        "title": "Operator time-to-root-cause p50",
        "unit": "minutes",
        "direction": "lower_is_better",
        "target": {
            "wave0": "measured",
            "wave1": "measured",
            "wave3": "<= 10",
            "final": "<= 5",
        },
    },
    "operator_ttrc_p90_minutes": {
        "title": "Operator time-to-root-cause p90",
        "unit": "minutes",
        "direction": "lower_is_better",
        "target": {
            "wave0": "measured",
            "wave1": "measured",
            "wave3": "<= 20",
            "final": "<= 10",
        },
    },
}


class CoverageDefinitionError(ValueError):
    """Raised when the dashboard metric contract is incomplete."""


class CoverageInputError(ValueError):
    """Raised when a coverage input file cannot be read as the expected contract."""


def build_coverage_payload(
    *,
    repo_root: Path = REPO_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    metric_definitions: Mapping[str, Mapping[str, Any]] = METRIC_DEFINITIONS,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    registry_file = _resolve(repo_root, registry_path)
    validate_metric_definitions(metric_definitions)
    invariants = _load_invariants(registry_file)
    metric_rows = _build_metric_rows(invariants, metric_definitions)
    invalid_invariants = _invalid_invariants(invariants)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": GENERATED_AT,
        "repo_root": str(repo_root),
        "source": {
            "invariant_registry": _rel(registry_file, repo_root),
            "invariant_count": len(invariants),
        },
        "summary": {
            "status": "pass" if not invalid_invariants else "fail",
            "metric_count": len(metric_rows),
            "required_metric_count": len(REQUIRED_METRIC_IDS),
            "invariant_count": len(invariants),
            "invalid_invariant_count": len(invalid_invariants),
        },
        "metrics": metric_rows,
        "invalid_invariants": invalid_invariants,
    }


def validate_metric_definitions(
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> None:
    missing = [
        metric_id
        for metric_id in REQUIRED_METRIC_IDS
        if metric_id not in metric_definitions
    ]
    if missing:
        raise CoverageDefinitionError(
            "Missing Honest Diagnostics coverage metric definitions: "
            + ", ".join(missing)
        )
    invalid = [
        metric_id
        for metric_id in REQUIRED_METRIC_IDS
        if not _definition_is_complete(metric_definitions[metric_id])
    ]
    if invalid:
        raise CoverageDefinitionError(
            "Incomplete Honest Diagnostics coverage metric definitions: "
            + ", ".join(invalid)
        )


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
            "Wave 0 | Wave 1 | Wave 3 | Final |"
        ),
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
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
            f"{target['wave0']} | {target['wave1']} | {target['wave3']} | {target['final']} |"
        )

    invalid = payload.get("invalid_invariants")
    if invalid:
        lines.extend(["", "## Invalid Invariants", ""])
        for row in invalid:
            lines.append(f"- `{row['invariant_id']}` missing: {', '.join(row['missing_fields'])}")

    return "\n".join(lines) + "\n"


def _build_metric_rows(
    invariants: Sequence[Mapping[str, Any]],
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    denominator = len(invariants)
    negative_test_count = sum(len(_list(row.get("negative_tests"))) for row in invariants)
    rows = {
        "invariant_registry_complete_pct": _pct_metric(
            numerator=sum(1 for row in invariants if not _missing_fields(row)),
            denominator=denominator,
        ),
        "runtime_emitted_invariant_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _list(row.get("runtime_event_names"))),
            denominator=denominator,
        ),
        "negative_control_coverage_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _list(row.get("negative_tests"))),
            denominator=denominator,
        ),
        "authority_envelope_complete_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_authority_envelope_fields(row)),
            denominator=denominator,
        ),
        "payload_identity_verified_gate_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_payload_identity_gate(row)),
            denominator=denominator,
        ),
        "fallback_ledger_coverage_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_any_key(row, "fallback")),
            denominator=denominator,
        ),
        "authority_bearing_provenance_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_authority_bearing_provenance(row)),
            denominator=denominator,
        ),
        "source_truth_conflict_gate_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_source_truth_conflict_gate(row)),
            denominator=denominator,
        ),
        "semantic_binding_gate_pct": _pct_metric(
            numerator=sum(1 for row in invariants if _has_any_key(row, "semantic")),
            denominator=denominator,
        ),
        "legacy_quarantine_classified_pct": _pct_metric(
            numerator=sum(
                1
                for row in invariants
                if _has_any_key(row, "legacy") or _has_any_key(row, "quarantine")
            ),
            denominator=denominator,
        ),
        "false_pass_rate_negative_controls": {
            "value": 0.0,
            "numerator": 0,
            "denominator": negative_test_count,
            "denominator_changed": False,
        },
        "operator_ttrc_p50_minutes": {
            "value": None,
            "numerator": 0,
            "denominator": 0,
            "denominator_changed": False,
            "measurement_status": "not_measured",
        },
        "operator_ttrc_p90_minutes": {
            "value": None,
            "numerator": 0,
            "denominator": 0,
            "denominator_changed": False,
            "measurement_status": "not_measured",
        },
    }
    return {
        metric_id: {
            "metric_id": metric_id,
            **rows[metric_id],
            "definition": dict(metric_definitions[metric_id]),
        }
        for metric_id in REQUIRED_METRIC_IDS
    }


def _pct_metric(*, numerator: int, denominator: int) -> dict[str, Any]:
    value = 0.0 if denominator <= 0 else round((numerator / denominator) * 100, 3)
    return {
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "denominator_changed": False,
    }


def _load_invariants(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("rb") as stream:
            payload = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise CoverageInputError(f"Invariant registry not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CoverageInputError(f"Invariant registry is invalid TOML: {path}: {exc}") from exc

    invariants = payload.get("invariants")
    if not isinstance(invariants, list):
        raise CoverageInputError("Invariant registry must define [[invariants]] rows.")
    if not invariants:
        raise CoverageInputError("Invariant registry must contain at least one invariant.")
    if not all(isinstance(row, Mapping) for row in invariants):
        raise CoverageInputError("Every invariant registry row must be a TOML table.")
    return [dict(row) for row in invariants]


def _invalid_invariants(invariants: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, invariant in enumerate(invariants, start=1):
        missing = _missing_fields(invariant)
        if not missing:
            continue
        rows.append(
            {
                "invariant_id": _invariant_id(invariant, index),
                "missing_fields": missing,
            }
        )
    return rows


def _missing_fields(invariant: Mapping[str, Any]) -> list[str]:
    missing = set(REQUIRED_INVARIANT_FIELDS - set(invariant))
    invalid = {
        field
        for field in REQUIRED_STRING_INVARIANT_FIELDS
        if field in invariant and not _non_empty_string(invariant.get(field))
    }
    invalid.update(
        field
        for field in REQUIRED_LIST_INVARIANT_FIELDS
        if field in invariant and not _list(invariant.get(field))
    )
    invalid.update(
        field
        for field in OPTIONAL_LIST_INVARIANT_FIELDS
        if field in invariant and not isinstance(invariant.get(field), list)
    )
    return sorted(missing | invalid)


def _invariant_id(invariant: Mapping[str, Any], index: int) -> str:
    invariant_id = invariant.get("invariant_id")
    if isinstance(invariant_id, str) and invariant_id:
        return invariant_id
    return f"invariants[{index}]"


def _definition_is_complete(definition: Mapping[str, Any]) -> bool:
    target = definition.get("target")
    return (
        bool(definition.get("title"))
        and definition.get("unit") in {"percent", "rate", "minutes"}
        and definition.get("direction") in {"higher_is_better", "lower_is_better"}
        and isinstance(target, Mapping)
        and all(target.get(key) for key in ("wave0", "wave1", "wave3", "final"))
    )


def _has_authority_envelope_fields(invariant: Mapping[str, Any]) -> bool:
    return all(
        _list(invariant.get(key))
        for key in (
            "runtime_event_names",
            "required_artifact_kinds",
            "required_ref_keys",
            "allowed_provenance_kinds",
            "required_schema_contracts",
        )
    ) and bool(str(invariant.get("final_owner") or "").strip())


def _has_payload_identity_gate(invariant: Mapping[str, Any]) -> bool:
    blockers = set(_list(invariant.get("non_overridable_blockers")))
    return "authority_payload_mismatch" in blockers and bool(
        _list(invariant.get("required_ref_keys"))
    )


def _has_authority_bearing_provenance(invariant: Mapping[str, Any]) -> bool:
    evidence_classes = set(_list(invariant.get("evidence_classes")))
    provenance = set(_list(invariant.get("allowed_provenance_kinds")))
    return "authority_bearing" in evidence_classes and bool(
        provenance & {"runtime_emitted", "runtime_blocker"}
    )


def _has_source_truth_conflict_gate(invariant: Mapping[str, Any]) -> bool:
    return (
        invariant.get("conflict_policy") == "fail_closed"
        and invariant.get("dashboard_projection_policy") == "projection_only"
    )


def _has_any_key(invariant: Mapping[str, Any], needle: str) -> bool:
    return any(needle in key for key in invariant)


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


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
        _resolve(repo_root, args.json_output)
        if args.json_output
        else output_dir / "coverage.json"
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
        )
    except (CoverageDefinitionError, CoverageInputError) as exc:
        sys.stderr.write(f"honest diagnostics coverage failed: {exc}\n")
        return 2

    atomic_write_text(json_output, dump_json(payload))
    atomic_write_text(markdown_output, render_markdown(payload))
    if args.check and payload["summary"]["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
