#!/usr/bin/env python3
"""Inspect the read-only W1/W2/W3 seams for the GY-N13a acquisition census.

This command recomputes the complete metric/reverse-demand denominators and the
evidence-derived capstone route classes. Later workstreams extend it with artifact
validation and explicit live capture.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CatalogContractError,
    ProbeDisposition,
    canonical_json_bytes,
    capture_live_probe_journal,
    derive_connector_family_receipts,
    derive_family_scorecards,
    derive_metric_resolutions,
    generate_fetch_plan_proofs,
    measure_reverse_demand,
    measure_route_evidence,
    prepare_probe_records,
    read_catalog_source,
    read_live_probe_journal,
    read_reverse_demand_projection,
    read_route_projection,
    reverse_demand_residuals,
    select_stratified_probe_candidates,
    validate_live_probe_journal,
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
    parser.add_argument(
        "--capture-live-journal",
        type=Path,
        help="Explicitly spend safe live calls and create this new quarantine journal JSON",
    )
    parser.add_argument(
        "--probe-journal-path",
        type=Path,
        help="Offline strict validation of an existing frozen live-probe journal",
    )
    parser.add_argument(
        "--event-log-path",
        type=Path,
        help="New append+fsync JSONL path used by explicit live capture",
    )
    parser.add_argument(
        "--probes-per-family",
        type=int,
        choices=range(10, 16),
        default=12,
        metavar="10..15",
    )
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
        with tempfile.TemporaryDirectory(prefix="gy-n13a-fetch-plan-") as scratch:
            fetch_plan_proof = generate_fetch_plan_proofs(
                args.catalog_path,
                metric_resolutions=resolutions,
                route_evidence=route_rows,
                scratch_dir=Path(scratch),
                source_locator=args.source_locator,
            )
        selection_plan = select_stratified_probe_candidates(
            args.catalog_path,
            per_family=args.probes_per_family,
            source_locator=args.source_locator,
        )
        with tempfile.TemporaryDirectory(prefix="gy-n13a-simulator-") as fixtures:
            family_receipts = derive_connector_family_receipts(
                tuple(row.connector_id for row in selection_plan.sampling_receipts),
                fixture_root=Path(fixtures),
            )
        prepared_probes = prepare_probe_records(selection_plan, family_receipts)
        live_journal = None
        scorecards = ()
        journal_path = args.probe_journal_path
        if args.capture_live_journal is not None and args.probe_journal_path is not None:
            raise CatalogContractError(
                "probe_journal_mode_conflict",
                "choose capture or offline journal validation, not both",
            )
        if args.capture_live_journal is not None:
            if args.event_log_path is None:
                raise CatalogContractError(
                    "probe_event_log_path_required",
                    "--capture-live-journal requires --event-log-path",
                )
            if args.capture_live_journal.exists():
                raise CatalogContractError(
                    "probe_journal_already_exists", str(args.capture_live_journal)
                )
            live_journal = capture_live_probe_journal(
                selection_plan,
                family_receipts,
                event_log_path=args.event_log_path,
            )
            scorecards = derive_family_scorecards(live_journal.records)
            _write_new_json(args.capture_live_journal, live_journal.model_dump(mode="json"))
            journal_path = args.capture_live_journal
        elif args.probe_journal_path is not None:
            live_journal = read_live_probe_journal(args.probe_journal_path)
            scorecards = validate_live_probe_journal(
                live_journal,
                selection_plan=selection_plan,
                family_receipts=family_receipts,
            )
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
                "fetch_plan_summary": {
                    "capability_status": fetch_plan_proof.capability_status,
                    "sample_count": len(fetch_plan_proof.sample_rows),
                    "plan_count": len(fetch_plan_proof.plans),
                    "preview_calls": fetch_plan_proof.execution_fence.preview_calls,
                    "execute_calls": fetch_plan_proof.execution_fence.execute_calls,
                    "proof": fetch_plan_proof.model_dump(mode="json"),
                },
                "probe_plan_summary": {
                    "family_count": len(selection_plan.sampling_receipts),
                    "selected_probe_count": len(selection_plan.candidates),
                    "family_projection_binding": (
                        selection_plan.family_projection_binding.model_dump(mode="json")
                    ),
                    "sampling_receipts": [
                        row.model_dump(mode="json") for row in selection_plan.sampling_receipts
                    ],
                    "owner_receipts": [row.model_dump(mode="json") for row in family_receipts],
                    "preflight_counts": dict(
                        sorted(
                            Counter(
                                preflight.disposition.value for _, _, preflight in prepared_probes
                            ).items()
                        )
                    ),
                    "authorized_live_attempt_count": sum(
                        preflight.disposition is ProbeDisposition.LIVE_ATTEMPT_AUTHORIZED
                        for _, _, preflight in prepared_probes
                    ),
                },
                "live_probe_summary": (
                    {
                        "journal_path": str(journal_path),
                        "event_log_content_sha256": (live_journal.event_log_content_sha256),
                        "network_call_count": sum(card.network_call_count for card in scorecards),
                        "wall_time_seconds": sum(card.wall_time_seconds for card in scorecards),
                        "scorecards": [card.model_dump(mode="json") for card in scorecards],
                    }
                    if live_journal is not None
                    else None
                ),
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


def _write_new_json(path: Path, payload: object) -> None:
    """Create a new fsynced JSON artifact without overwriting prior census evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
