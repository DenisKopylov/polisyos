#!/usr/bin/env python3
"""Inspect the read-only W1/W2 seams for the GY-N13a acquisition census.

This command recomputes the complete metric/reverse-demand denominators and the
evidence-derived capstone route classes. Later workstreams extend it with artifact
validation and explicit live capture.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CatalogContractError,
    derive_metric_resolutions,
    measure_reverse_demand,
    measure_route_evidence,
    read_catalog_source,
    read_reverse_demand_projection,
    read_route_projection,
    reverse_demand_residuals,
)

DEFAULT_SOURCE_LOCATOR = (
    "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = POLICY_ENGINE_ROOT / "architecture" / "policy_design_case"
DEFAULT_CAPSTONE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_depth_n_universality_contract.json"
DEFAULT_SUBSTRATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_intervention_substrate_contract.json"
DEFAULT_VALUE_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_value_gate_contract.json"


def build_parser() -> argparse.ArgumentParser:
    """Build the W1/W2 catalog seam inspection CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-path",
        required=True,
        type=Path,
        help="Read-only path to dataset_catalog.duckdb",
    )
    parser.add_argument(
        "--source-locator",
        default=DEFAULT_SOURCE_LOCATOR,
        help="Stable logical locator recorded in catalog identity",
    )
    parser.add_argument("--capstone-path", type=Path, default=DEFAULT_CAPSTONE_PATH)
    parser.add_argument("--intervention-substrate-path", type=Path, default=DEFAULT_SUBSTRATE_PATH)
    parser.add_argument("--value-gate-path", type=Path, default=DEFAULT_VALUE_GATE_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Print recomputed W1/W2 identity and denominator summaries as JSON."""

    args = build_parser().parse_args(argv)
    try:
        source = read_catalog_source(
            args.catalog_path,
            source_locator=args.source_locator,
        )
        resolutions = derive_metric_resolutions(args.catalog_path)
        projection = read_reverse_demand_projection(
            capstone_path=args.capstone_path,
            intervention_substrate_path=args.intervention_substrate_path,
            value_gate_path=args.value_gate_path,
            capstone_source=_stable_artifact_locator(args.capstone_path),
            intervention_substrate_source=_stable_artifact_locator(
                args.intervention_substrate_path
            ),
            value_gate_source=_stable_artifact_locator(args.value_gate_path),
        )
        demand_rows = measure_reverse_demand(args.catalog_path, projection.demands)
        route_projection = read_route_projection(
            capstone_path=args.capstone_path,
            capstone_source=_stable_artifact_locator(args.capstone_path),
        )
        route_rows = measure_route_evidence(args.catalog_path, route_projection)
    except CatalogContractError as exc:
        print(
            json.dumps(
                {"issues": [{"code": exc.code, "detail": exc.detail}], "status": "fail"},
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "catalog_source": source.model_dump(mode="json"),
                "metric_resolution_summary": {
                    "counts": dict(
                        sorted(Counter(row.resolution_status.value for row in resolutions).items())
                    ),
                    "denominator_count": len(resolutions),
                    "proxy_only_resolved_count": sum(
                        row.proxy_only
                        for row in resolutions
                        if row.resolution_status.value != "unresolved"
                    ),
                    "unresolved_metric_ids": [
                        row.metric_id
                        for row in resolutions
                        if row.resolution_status.value == "unresolved"
                    ],
                },
                "reverse_demand_summary": {
                    "denominator_count": len(demand_rows),
                    "gap_counts": dict(
                        sorted(
                            Counter(
                                row.gap_kind.value if row.gap_kind else "supported"
                                for row in demand_rows
                            ).items()
                        )
                    ),
                    "projection_bindings": [
                        binding.model_dump(mode="json")
                        for binding in projection.projection_bindings
                    ],
                    "residuals": [
                        row.model_dump(mode="json") for row in reverse_demand_residuals(demand_rows)
                    ],
                },
                "route_summary": {
                    "counts": dict(
                        sorted(Counter(row.route_class.value for row in route_rows).items())
                    ),
                    "denominator_count": len(route_rows),
                    "projection_binding": (
                        route_projection.projection_binding.model_dump(mode="json")
                    ),
                    "routes": [row.model_dump(mode="json") for row in route_rows],
                },
                "status": "pass",
            },
            sort_keys=True,
        )
    )
    return 0


def _stable_artifact_locator(path: Path) -> str:
    """Return a repo-relative locator or a stable filename for an external source."""

    try:
        return str(path.resolve().relative_to(POLICY_ENGINE_ROOT.resolve()))
    except ValueError:
        return f"external://{path.name}"


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
