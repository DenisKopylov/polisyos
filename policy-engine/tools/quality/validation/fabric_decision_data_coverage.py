#!/usr/bin/env python3
"""Validate Fabric decision-data trust-envelope coverage."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.fabric.decision_data import FabricDecisionData  # noqa: E402
from polisyos.fabric.io.atomic import atomic_write_text  # noqa: E402

REPORT_SCHEMA_VERSION = "fabric.decision_data_coverage.v1"
GENERATED_AT = "2026-04-27T00:00:00Z"
DEFAULT_REPORT = (
    REPO_ROOT / "tools" / "quality" / "validation" / "fabric_decision_data_coverage.json"
)

ENDPOINTS = (
    {
        "id": "runtime.run_quantities",
        "path": "/api/v1/runs/{run_id}/quantities",
        "classification": "decision",
        "expected_wrapper": "QuantityValue",
        "operation_id": "get_run_quantities",
    },
    {
        "id": "runtime.run_fabric_decision_data",
        "path": "/api/v1/runs/{run_id}/fabric-decision-data",
        "classification": "decision",
        "expected_wrapper": "FabricDecisionData",
        "operation_id": "get_run_fabric_decision_data",
    },
    {
        "id": "runtime.lineage_batch",
        "path": "/api/v1/lineage/batch",
        "classification": "decision",
        "expected_wrapper": "LineageGraphView",
        "operation_id": "get_lineage_batch",
    },
)

TYPED_GAP_STATES = (
    "untraced",
    "unknown_quality",
    "restricted",
    "non_replayable",
    "unsupported_temporal_scope",
)

FIELD_CLASSIFICATIONS = (
    {
        "field": "FabricDecisionData.value",
        "classification": "decision",
        "wrapper": "FabricQuantityValue|AuthoredText",
    },
    {
        "field": "FabricDecisionData.quality",
        "classification": "decision",
        "wrapper": "QualityRef",
    },
    {
        "field": "FabricDecisionData.lineage",
        "classification": "decision",
        "wrapper": "LineageRef",
    },
    {
        "field": "FabricDecisionData.access",
        "classification": "decision",
        "wrapper": "AccessRef",
    },
    {
        "field": "FabricDecisionData.replay",
        "classification": "decision",
        "wrapper": "ReplayRef",
    },
    {
        "field": "FabricDecisionData.time",
        "classification": "decision",
        "wrapper": "TemporalRef",
    },
    {
        "field": "RunQuantitiesResponse.coverage",
        "classification": "telemetry",
        "wrapper": "QuantityCoverageSummary",
    },
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Print report JSON")
    parser.add_argument("--check", action="store_true", help="Fail on drift or coverage gaps")
    parser.add_argument("--update", action="store_true", help="Rewrite the checked-in report")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build the static Phase 6 decision-data coverage report."""
    decision_data_path = repo_root / "src" / "polisyos" / "fabric" / "decision_data.py"
    trust_schema_path = repo_root / "schemas" / "fabric" / "trust_envelope.schema.json"
    run_routes_path = repo_root / "src" / "polisyos" / "runtime" / "http" / "routes" / "runs.py"
    lineage_routes_path = (
        repo_root / "src" / "polisyos" / "runtime" / "http" / "routes" / "lineage.py"
    )
    lineage_service_path = (
        repo_root / "src" / "polisyos" / "runtime" / "http" / "services" / "lineage.py"
    )
    temporal_service_path = (
        repo_root / "src" / "polisyos" / "runtime" / "http" / "services" / "temporal.py"
    )
    runtime_contracts_path = repo_root / "src" / "polisyos" / "core" / "contracts" / "runtime.py"

    decision_data_text = _read(decision_data_path)
    run_routes_text = _read(run_routes_path)
    lineage_routes_text = _read(lineage_routes_path)
    lineage_service_text = _read(lineage_service_path)
    temporal_service_text = _read(temporal_service_path)
    runtime_contracts_text = _read(runtime_contracts_path)
    endpoint_rows = []
    naked_decision_values = []
    for endpoint in ENDPOINTS:
        operation_present = endpoint["operation_id"] in (
            run_routes_text + lineage_routes_text
        )
        wrapper_present = endpoint["expected_wrapper"] in (
            run_routes_text + lineage_routes_text + decision_data_text
        )
        status = "implemented" if operation_present and wrapper_present else "missing"
        endpoint_rows.append(
            {
                **endpoint,
                "status": status,
                "operation_present": operation_present,
                "wrapper_present": wrapper_present,
            }
        )
        if endpoint["classification"] == "decision" and not wrapper_present:
            naked_decision_values.append(
                {
                    "endpoint_id": endpoint["id"],
                    "reason": "decision endpoint lacks typed wrapper evidence",
                }
            )

    typed_gap_rows = [
        {
            "state": state,
            "status": "implemented" if state in decision_data_text else "missing",
        }
        for state in TYPED_GAP_STATES
    ]
    field_rows = [
        {
            **row,
            "status": "implemented"
            if _wrapper_present(
                str(row["wrapper"]),
                decision_data_text + run_routes_text + runtime_contracts_text,
            )
            else "missing",
        }
        for row in FIELD_CLASSIFICATIONS
    ]
    batch_lookup = {
        "lineage_route_uses_batch_service": "_build_runtime_lineage_batch" in lineage_routes_text,
        "lineage_service_deduplicates_refs": "if lineage_id not in resolved" in lineage_service_text,
        "quality_batch_adapter": "build_quality_refs_batch" in lineage_service_text,
        "trust_batch_adapter": "build_trust_refs_batch" in lineage_service_text,
        "benchmark_surface": "benchmark_compact_lineage_batch" in lineage_service_text,
        "full_graph_benchmark_surface": "benchmark_full_lineage_graph" in lineage_service_text,
        "p95_target_ms": 150,
        "full_graph_p95_target_ms": 500,
    }
    temporal_echo = {
        "runtime_surface_supported": "run_fabric_decision_data" in temporal_service_text,
        "envelope_temporal_ref": "class TemporalRef" in decision_data_text,
        "route_temporal_echo": "FabricTemporalRef.from_runtime_scope" in run_routes_text,
    }
    schema_payload = _load_json(trust_schema_path)
    required_contracts = {
        "decision_data_module": decision_data_path.exists(),
        "trust_envelope_schema": bool(schema_payload),
        "schema_matches_model": _schema_matches_model(schema_payload),
        "runtime_decision_data_route": "get_run_fabric_decision_data" in run_routes_text,
        "batch_lineage_lookup": all(batch_lookup.values()),
        "temporal_scope_echo": all(temporal_echo.values()),
        "typed_gap_states": all(row["status"] == "implemented" for row in typed_gap_rows),
        "field_classification": all(row["status"] == "implemented" for row in field_rows),
        "source_contract_v2_ref": "worldbank.wdi.generic" in lineage_service_text,
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "summary": {
            "status": "implemented"
            if all(required_contracts.values()) and not naked_decision_values
            else "partial",
            "endpoint_count": len(endpoint_rows),
            "decision_endpoint_count": sum(
                row["classification"] == "decision" for row in endpoint_rows
            ),
            "naked_decision_value_count": len(naked_decision_values),
            "transitional_waiver_count": 0,
            "typed_gap_state_count": len(typed_gap_rows),
            "field_count": len(field_rows),
            "unknown_field_count": sum(
                row["classification"] == "unknown" for row in field_rows
            ),
        },
        "required_contracts": required_contracts,
        "endpoints": endpoint_rows,
        "field_classifications": field_rows,
        "typed_gap_states": typed_gap_rows,
        "batch_lookup": batch_lookup,
        "temporal_echo": temporal_echo,
        "naked_decision_values": naked_decision_values,
        "transitional_waivers": [],
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def validate_report(report: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        errors.append("unexpected decision-data coverage schema_version")
    summary = report.get("summary")
    if not isinstance(summary, Mapping) or summary.get("status") != "implemented":
        errors.append("decision-data coverage is not fully implemented")
    required_contracts = report.get("required_contracts")
    if not isinstance(required_contracts, Mapping):
        errors.append("required_contracts missing")
    else:
        for key, value in required_contracts.items():
            if value is not True:
                errors.append(f"required contract missing: {key}")
    if report.get("naked_decision_values"):
        errors.append("naked decision values require typed wrappers or waivers")
    typed_gap_states = report.get("typed_gap_states")
    if isinstance(typed_gap_states, list):
        for row in typed_gap_states:
            if isinstance(row, Mapping) and row.get("status") != "implemented":
                errors.append(f"typed gap state missing: {row.get('state')}")
    else:
        errors.append("typed_gap_states missing")
    return errors


def check_artifact(output: Path = DEFAULT_REPORT) -> list[str]:
    expected = dump_json(build_report())
    if not output.exists():
        return [f"decision-data coverage report missing: {output}"]
    if output.read_text(encoding="utf-8") != expected:
        return [f"decision-data coverage report out of date: {output}"]
    return []


def update_artifact(output: Path = DEFAULT_REPORT) -> None:
    atomic_write_text(output, dump_json(build_report()))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _schema_matches_model(schema_payload: Mapping[str, Any]) -> bool:
    if not schema_payload:
        return False
    generated = FabricDecisionData.model_json_schema()
    return schema_payload.get("properties", {}) == generated.get("properties", {})


def _wrapper_present(wrapper: str, text: str) -> bool:
    return all(part.strip() in text for part in wrapper.split("|") if part.strip())


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.update:
        update_artifact(args.output)

    report = build_report()
    if args.report:
        sys.stdout.write(dump_json(report))

    errors = validate_report(report)
    if args.check:
        errors.extend(check_artifact(args.output))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if not args.report and not args.check:
        sys.stdout.write(dump_json(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
