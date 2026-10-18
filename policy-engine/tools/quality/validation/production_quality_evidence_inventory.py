#!/usr/bin/env python3
# ruff: noqa: E501, T201
"""Inventory production-quality evidence refs, fields, producers, and validators.

This facade owns the public inventory payload and CLI. Source binding analysis,
report producer rows, and evidence contract rows live in focused sibling modules.
Closeout authority lives in canary bundles and the readiness aggregator.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.capability_white_space import (  # noqa: E402
    build_capability_white_space_report_from_duckdb,
    dump_capability_white_space_report,
)
from tools.quality.validation.production_quality_evidence_inventory_bindings import (  # noqa: E402
    _literal_assignment,
)
from tools.quality.validation.production_quality_evidence_inventory_contracts import (  # noqa: E402
    QUALITY_REPORT_IDS_BY_KEY as QUALITY_REPORT_IDS_BY_KEY,
)
from tools.quality.validation.production_quality_evidence_inventory_contracts import (
    _quality_artifact_fields,
    _serious_profile_required_refs,
    _validators,
)
from tools.quality.validation.production_quality_evidence_inventory_reports import (  # noqa: E402
    _quality_report_specs,
)

SCHEMA_VERSION = "policyos.production_quality_evidence_inventory.v1"

PHASE = "0.1"

SNAPSHOT_DATE = "2026-05-13"

OWNER = "team-quality"

STATUS_VALUES = ("manual_input", "fixture_input", "runtime_emitted", "missing")

DEFAULT_BASELINE = (
    REPO_ROOT / "architecture" / "baselines" / "production_quality" / "evidence_inventory.json"
)


_SCORECARD_PATH = REPO_ROOT / "src" / "polisyos" / "runtime" / "quality" / "scorecard.py"

QUALITY_REPORT_FILES: dict[str, str] = dict(
    _literal_assignment(_SCORECARD_PATH, "QUALITY_REPORT_FILES")
)
QUALITY_REPORT_RUNTIME_REFS: dict[str, str] = dict(
    _literal_assignment(_SCORECARD_PATH, "QUALITY_REPORT_RUNTIME_REFS")
)
REQUIRED_MATERIALIZATION_REFS: tuple[str, ...] = tuple(
    _literal_assignment(_SCORECARD_PATH, "REQUIRED_MATERIALIZATION_REFS")
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for capability white-space reports.",
    )
    parser.add_argument(
        "--capability-index",
        type=Path,
        default=None,
        help="Primary capability_index_v1.duckdb to query for Phase 6 white-space.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the baseline JSON drifts")
    return parser.parse_args(argv)


def _resolve(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _status_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("status")) for row in rows)
    return {status: counts.get(status, 0) for status in STATUS_VALUES}


def build_inventory(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build the stable Phase 0.1 evidence inventory payload."""
    repo_root = repo_root.resolve()
    reports = _quality_report_specs(
        repo_root,
        QUALITY_REPORT_FILES,
        REQUIRED_MATERIALIZATION_REFS,
        QUALITY_REPORT_IDS_BY_KEY,
    )
    fields = _quality_artifact_fields(reports, QUALITY_REPORT_RUNTIME_REFS)
    validators = _validators(
        repo_root,
        quality_report_files=QUALITY_REPORT_FILES,
        required_materialization_refs=REQUIRED_MATERIALIZATION_REFS,
    )
    required_refs = _serious_profile_required_refs(
        reports, QUALITY_REPORT_RUNTIME_REFS, REQUIRED_MATERIALIZATION_REFS
    )
    missing_required = [
        row
        for row in required_refs
        if row["status"] in {"manual_input", "fixture_input", "missing"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "snapshot_date": SNAPSHOT_DATE,
        "owner": OWNER,
        "mode": "read_only_inventory",
        "status_model": {
            "allowed_statuses": list(STATUS_VALUES),
            "definitions": {
                "manual_input": "Evidence is authored or selected by a human/operator.",
                "fixture_input": "Evidence can be supplied by fixtures or CLI input but is not emitted by the runtime path yet.",
                "runtime_emitted": "Evidence is emitted by the runtime/canary path today.",
                "missing": "The field/ref contract exists, but no current producer emits it.",
            },
        },
        "quality_reports": reports,
        "quality_artifact_fields": fields,
        "validators": validators,
        "serious_profile_required_refs": required_refs,
        "summary": {
            "quality_report_count": len(reports),
            "quality_artifact_field_count": len(fields),
            "validator_count": len(validators),
            "required_serious_profile_ref_count": len(required_refs),
            "quality_report_status_counts": _status_counts(reports),
            "required_ref_status_counts": _status_counts(required_refs),
            "missing_or_input_required_producers": [
                {
                    "expected_ref": row["expected_ref"],
                    "status": row["status"],
                    "first_missing_producer": row["first_missing_producer"],
                }
                for row in missing_required
            ],
        },
        "readiness_aggregator_contract": {
            "stable_json": True,
            "sort_keys": True,
            "primary_keys": {
                "quality_reports": "id",
                "quality_artifact_fields": "field_path",
                "validators": "id",
                "serious_profile_required_refs": "expected_ref",
            },
            "blocking_statuses_for_serious_profile": [
                "manual_input",
                "fixture_input",
                "missing",
            ],
        },
        "source_paths": {
            "scorecard": "src/polisyos/runtime/quality/scorecard.py",
            "canary_evidence": "tools/ops_runners/runtime/canary_evidence.py",
            "nl_pipeline": "src/polisyos/runtime/http/services/control/nl_pipeline.py",
            "run_lifecycle": "src/polisyos/runtime/http/services/control/run_lifecycle.py",
            "production_data": "src/polisyos/runtime/http/services/control/production_data.py",
        },
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    """Return canonical JSON suitable for checked-in baselines and aggregators."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def check_artifacts(
    *,
    repo_root: Path = REPO_ROOT,
    baseline_path: Path = DEFAULT_BASELINE,
) -> list[str]:
    baseline = _resolve(baseline_path, repo_root)
    expected = dump_json(build_inventory(repo_root))
    if not baseline.exists():
        return [f"baseline missing: {_rel(baseline, repo_root)}"]
    actual = baseline.read_text(encoding="utf-8")
    if actual != expected:
        return [f"baseline out of date: {_rel(baseline, repo_root)}"]
    return []


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.capability_index is not None:
        capability_index = _resolve(args.capability_index, repo_root)
        output = _resolve(args.output or args.json_output, repo_root)
        payload = build_capability_white_space_report_from_duckdb(capability_index)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dump_capability_white_space_report(payload), encoding="utf-8")
        return 0

    output = _resolve(args.json_output, repo_root)

    if args.check:
        failures = check_artifacts(repo_root=repo_root, baseline_path=output)
        if failures:
            for failure in failures:
                print(failure)
            return 1
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dump_json(build_inventory(repo_root)), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
