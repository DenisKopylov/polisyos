#!/usr/bin/env python3
"""Recompute, freeze, and mutation-test the GY-N13a acquisition census.

The default mode prints an inspection report. ``--check`` and ``--write`` use an
existing journal and never make network calls. Live calls require the explicit
``--capture-live-journal`` mode and always create a new quarantine journal.
"""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tools.lib.timing import run_timed_entrypoint
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CatalogContractError,
    CensusManifest,
    LiveProbeJournal,
    ProbeDisposition,
    assemble_census_manifest,
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
    read_census_manifest,
    read_live_probe_journal,
    read_reverse_demand_projection,
    read_route_projection,
    reverse_demand_residuals,
    select_stratified_probe_candidates,
    semantic_content_hash,
    validate_census_manifest,
    validate_live_probe_journal,
    validate_probe_family_denominator,
)

DEFAULT_SOURCE_LOCATOR = (
    "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = POLICY_ENGINE_ROOT / "architecture" / "policy_design_case"
DEFAULT_CAPSTONE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_depth_n_universality_contract.json"
DEFAULT_SUBSTRATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_intervention_substrate_contract.json"
DEFAULT_VALUE_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_value_gate_contract.json"
DEFAULT_JOURNAL_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_n13a_live_probe_journal.json"
DEFAULT_OUTPUT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gy_n13a_acquisition_census.json"
SOURCE_MODULE_PATH = Path(
    "tools/quality/validation/layer3_gy_n13a_acquisition_census.py"
)
TEST_MODULE_PATH = Path(
    "tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py"
)


@dataclass(frozen=True)
class _RecomputedCensus:
    """All recomputed workstream evidence for one offline census pass."""

    source: Any
    resolutions: tuple[Any, ...]
    demand_projection: Any
    demand_rows: tuple[Any, ...]
    route_projection: Any
    route_rows: tuple[Any, ...]
    fetch_plan_proof: Any
    selection_plan: Any
    family_receipts: tuple[Any, ...]
    prepared_probes: tuple[Any, ...]
    live_journal: LiveProbeJournal | None
    scorecards: tuple[Any, ...]
    journal_path: Path | None
    manifest: CensusManifest | None


@dataclass(frozen=True)
class _SourceFlipCase:
    """One guarded behavioral source mutation and its focused red probe."""

    mutation_id: str
    replacements: tuple[tuple[str, str], ...]
    probe_nodeid: str
    expected_red_signal: str


def build_parser() -> argparse.ArgumentParser:
    """Build the recurring census lifecycle CLI."""

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
    parser.add_argument(
        "--intervention-substrate-path", type=Path, default=DEFAULT_SUBSTRATE_PATH
    )
    parser.add_argument("--value-gate-path", type=Path, default=DEFAULT_VALUE_GATE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--probe-journal-path",
        type=Path,
        help="Existing frozen journal; defaults to the committed journal in lifecycle modes",
    )
    parser.add_argument(
        "--event-log-path",
        type=Path,
        help="New append+fsync JSONL path used only by explicit live capture",
    )
    parser.add_argument(
        "--probes-per-family",
        type=int,
        choices=range(10, 16),
        default=12,
        metavar="10..15",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    modes.add_argument("--source-flip-mutations", action="store_true")
    modes.add_argument(
        "--capture-live-journal",
        type=Path,
        help="Explicitly spend safe live calls and create this new quarantine journal JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one inspection, lifecycle, capture, or mutation mode."""

    args = build_parser().parse_args(argv)
    if args.source_flip_mutations:
        report = run_source_flip_mutations(POLICY_ENGINE_ROOT)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "pass" else 1
    try:
        recomputed = _recompute(args)
        if args.write:
            report = _write_mode(args, recomputed)
        elif args.check:
            report = _check_mode(args, recomputed)
        elif args.corrupt_field_drift_check:
            report = _corrupt_field_mode(args, recomputed)
        elif args.capture_live_journal is not None:
            report = _capture_mode(args, recomputed)
        else:
            report = _inspection_report(recomputed)
    except (CatalogContractError, ValidationError) as exc:
        if isinstance(exc, CatalogContractError):
            issue = {"code": exc.code, "detail": exc.detail}
        else:
            issue = {"code": "census_validation_error", "detail": str(exc)}
        print(json.dumps({"issues": [issue], "status": "fail"}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("status") == "pass" else 1


def _recompute(args: argparse.Namespace) -> _RecomputedCensus:
    source = read_catalog_source(args.catalog_path, source_locator=args.source_locator)
    resolutions = derive_metric_resolutions(args.catalog_path)
    demand_projection = read_reverse_demand_projection(
        capstone_path=args.capstone_path,
        intervention_substrate_path=args.intervention_substrate_path,
        value_gate_path=args.value_gate_path,
        capstone_source=_stable_artifact_locator(args.capstone_path),
        intervention_substrate_source=_stable_artifact_locator(
            args.intervention_substrate_path
        ),
        value_gate_source=_stable_artifact_locator(args.value_gate_path),
    )
    demand_rows = measure_reverse_demand(args.catalog_path, demand_projection.demands)
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
    validate_probe_family_denominator(source, selection_plan)
    with tempfile.TemporaryDirectory(prefix="gy-n13a-simulator-") as fixtures:
        family_receipts = derive_connector_family_receipts(
            selection_plan,
            fixture_root=Path(fixtures),
        )
    prepared_probes = prepare_probe_records(selection_plan, family_receipts)

    lifecycle_mode = args.check or args.write or args.corrupt_field_drift_check
    journal_path = args.probe_journal_path
    if lifecycle_mode and journal_path is None:
        journal_path = DEFAULT_JOURNAL_PATH
    live_journal: LiveProbeJournal | None = None
    scorecards: tuple[Any, ...] = ()
    if args.capture_live_journal is not None:
        if args.event_log_path is None:
            raise CatalogContractError(
                "probe_event_log_path_required",
                "--capture-live-journal requires --event-log-path",
            )
        if args.event_log_path.exists():
            raise CatalogContractError(
                "probe_event_log_already_exists", str(args.event_log_path)
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
    elif journal_path is not None:
        live_journal = read_live_probe_journal(journal_path)
        scorecards = validate_live_probe_journal(
            live_journal,
            selection_plan=selection_plan,
            family_receipts=family_receipts,
        )

    manifest = None
    if live_journal is not None:
        manifest = assemble_census_manifest(
            catalog_source=source,
            projection_bindings=(
                *demand_projection.projection_bindings,
                route_projection.projection_binding,
                selection_plan.family_projection_binding,
            ),
            metric_resolutions=resolutions,
            reverse_demand_variables=demand_rows,
            route_evidence=route_rows,
            fetch_plan_generation=fetch_plan_proof,
            family_scorecards=scorecards,
            journal_content_sha256=semantic_content_hash(live_journal),
            observed_at=live_journal.observed_at,
            capture_wall_time_seconds=live_journal.capture_wall_time_seconds,
        )
    if lifecycle_mode and manifest is None:
        raise CatalogContractError(
            "probe_journal_required", "lifecycle modes require a frozen probe journal"
        )
    return _RecomputedCensus(
        source=source,
        resolutions=resolutions,
        demand_projection=demand_projection,
        demand_rows=demand_rows,
        route_projection=route_projection,
        route_rows=route_rows,
        fetch_plan_proof=fetch_plan_proof,
        selection_plan=selection_plan,
        family_receipts=family_receipts,
        prepared_probes=prepared_probes,
        live_journal=live_journal,
        scorecards=scorecards,
        journal_path=journal_path,
        manifest=manifest,
    )


def _write_mode(args: argparse.Namespace, recomputed: _RecomputedCensus) -> dict[str, Any]:
    assert recomputed.manifest is not None
    payload = canonical_json_bytes(recomputed.manifest.model_dump(mode="json"))
    _write_replace_bytes(args.output, payload)
    return {
        **_inspection_report(recomputed),
        "artifact_path": _stable_artifact_locator(args.output),
        "artifact_sha256": _bytes_sha256(payload),
        "mode": "write",
        "status": "pass",
    }


def _capture_mode(args: argparse.Namespace, recomputed: _RecomputedCensus) -> dict[str, Any]:
    """Freeze one new dated census after its journal-first live capture completes."""

    assert recomputed.manifest is not None
    output = args.output
    if output == DEFAULT_OUTPUT_PATH:
        stamp = recomputed.manifest.observed_at.strftime("%Y%m%dT%H%M%SZ")
        output = DEFAULT_OUTPUT_PATH.with_name(
            f"layer3_gy_n13a_acquisition_census_{stamp}.json"
        )
    if output.exists():
        raise CatalogContractError("census_artifact_already_exists", str(output))
    payload = recomputed.manifest.model_dump(mode="json")
    _write_new_json(output, payload)
    report = _inspection_report(recomputed)
    report.update(
        {
            "artifact_path": _stable_artifact_locator(output),
            "artifact_sha256": _bytes_sha256(canonical_json_bytes(payload)),
            "journal_first": True,
            "mode": "capture_live_journal",
            "status": "pass",
        }
    )
    return report


def _check_mode(args: argparse.Namespace, recomputed: _RecomputedCensus) -> dict[str, Any]:
    assert recomputed.manifest is not None
    stored = read_census_manifest(args.output)
    validate_census_manifest(stored, recomputed=recomputed.manifest)
    canonical = canonical_json_bytes(stored.model_dump(mode="json"))
    if args.output.read_bytes() != canonical:
        raise CatalogContractError(
            "census_artifact_noncanonical", "stored artifact bytes are not canonical"
        )
    return {
        **_inspection_report(recomputed),
        "artifact_path": _stable_artifact_locator(args.output),
        "artifact_sha256": _bytes_sha256(canonical),
        "mode": "check",
        "status": "pass",
    }


def _corrupt_field_mode(
    args: argparse.Namespace,
    recomputed: _RecomputedCensus,
) -> dict[str, Any]:
    assert recomputed.manifest is not None
    stored = read_census_manifest(args.output)
    validate_census_manifest(stored, recomputed=recomputed.manifest)
    payload = stored.model_dump(mode="json")
    mutations: list[tuple[str, dict[str, Any]]] = []

    metric = copy.deepcopy(payload)
    metric["metric_resolutions"][0]["binding_count"] += 1
    metric["metric_resolutions"][0]["binding_tier_counts"][
        next(iter(metric["metric_resolutions"][0]["binding_tier_counts"]))
    ] += 1
    mutations.append(("nested_metric_binding_count", metric))

    route = copy.deepcopy(payload)
    original_class = route["route_evidence"][0]["route_class"]
    route["route_evidence"][0]["route_class"] = (
        "live_fetchable" if original_class != "live_fetchable" else "not_a_data_gap"
    )
    mutations.append(("route_class_pinned", route))

    plan = copy.deepcopy(payload)
    plan["fetch_plan_generation"]["plans"][0]["connector_id"] += ".corrupt"
    mutations.append(("fetch_plan_owner_edge", plan))

    scorecard = copy.deepcopy(payload)
    scorecard["family_scorecards"][0]["tier_decay_findings"].append(
        "corrupt_decisive_tier_decay"
    )
    mutations.append(("scorecard_tier_decay_finding", scorecard))

    backlog = copy.deepcopy(payload)
    if len(backlog["growth_backlog"]) > 1:
        backlog["growth_backlog"][0], backlog["growth_backlog"][1] = (
            backlog["growth_backlog"][1],
            backlog["growth_backlog"][0],
        )
    else:
        backlog["growth_backlog"][0]["rank"] += 1
    mutations.append(("growth_backlog_reordered", backlog))

    cases = [
        {"mutation_id": mutation_id, "result": _mutation_result(mutated, stored)}
        for mutation_id, mutated in mutations
    ]
    all_red = all(case["result"] == "RED" for case in cases)
    return {
        "cases": cases,
        "expected": "every corrupt decisive field is RED",
        "issues": [] if all_red else [{"code": "corrupt_field_drift_survived"}],
        "mode": "corrupt_field_drift_check",
        "status": "pass" if all_red else "fail",
    }


def _mutation_result(payload: dict[str, Any], recomputed: CensusManifest) -> str:
    try:
        candidate = CensusManifest.model_validate(payload)
        validate_census_manifest(candidate, recomputed=recomputed)
    except (ValidationError, CatalogContractError):
        return "RED"
    return "GREEN_MUTATION_SURVIVED"


def _inspection_report(recomputed: _RecomputedCensus) -> dict[str, Any]:
    residuals = reverse_demand_residuals(recomputed.demand_rows)
    report: dict[str, Any] = {
        "catalog_source": recomputed.source.model_dump(mode="json"),
        "metric_resolution_summary": {
            "counts": dict(
                sorted(
                    Counter(row.resolution_status.value for row in recomputed.resolutions).items()
                )
            ),
            "denominator_count": len(recomputed.resolutions),
            "proxy_only_resolved_count": sum(
                row.proxy_only
                for row in recomputed.resolutions
                if row.resolution_status.value != "unresolved"
            ),
            "unresolved_metric_ids": [
                row.metric_id
                for row in recomputed.resolutions
                if row.resolution_status.value == "unresolved"
            ],
        },
        "reverse_demand_summary": {
            "denominator_count": len(recomputed.demand_rows),
            "gap_counts": dict(
                sorted(
                    Counter(
                        row.gap_kind.value if row.gap_kind else "supported"
                        for row in recomputed.demand_rows
                    ).items()
                )
            ),
            "projection_bindings": [
                binding.model_dump(mode="json")
                for binding in recomputed.demand_projection.projection_bindings
            ],
            "residuals": [row.model_dump(mode="json") for row in residuals],
        },
        "route_summary": {
            "counts": dict(
                sorted(Counter(row.route_class.value for row in recomputed.route_rows).items())
            ),
            "denominator_count": len(recomputed.route_rows),
            "projection_binding": (
                recomputed.route_projection.projection_binding.model_dump(mode="json")
            ),
            "routes": [row.model_dump(mode="json") for row in recomputed.route_rows],
        },
        "fetch_plan_summary": {
            "capability_status": recomputed.fetch_plan_proof.capability_status,
            "sample_count": len(recomputed.fetch_plan_proof.sample_rows),
            "plan_count": len(recomputed.fetch_plan_proof.plans),
            "preview_calls": recomputed.fetch_plan_proof.execution_fence.preview_calls,
            "execute_calls": recomputed.fetch_plan_proof.execution_fence.execute_calls,
            "proof": recomputed.fetch_plan_proof.model_dump(mode="json"),
        },
        "probe_plan_summary": {
            "family_count": len(recomputed.selection_plan.sampling_receipts),
            "selected_probe_count": len(recomputed.selection_plan.candidates),
            "family_projection_binding": (
                recomputed.selection_plan.family_projection_binding.model_dump(mode="json")
            ),
            "sampling_receipts": [
                row.model_dump(mode="json")
                for row in recomputed.selection_plan.sampling_receipts
            ],
            "owner_receipts": [
                row.model_dump(mode="json") for row in recomputed.family_receipts
            ],
            "preflight_counts": dict(
                sorted(
                    Counter(
                        preflight.disposition.value
                        for _, _, preflight in recomputed.prepared_probes
                    ).items()
                )
            ),
            "authorized_live_attempt_count": sum(
                preflight.disposition is ProbeDisposition.LIVE_ATTEMPT_AUTHORIZED
                for _, _, preflight in recomputed.prepared_probes
            ),
        },
        "live_probe_summary": None,
        "status": "pass",
    }
    if recomputed.live_journal is not None:
        report["live_probe_summary"] = {
            "journal_path": str(recomputed.journal_path),
            "journal_content_sha256": semantic_content_hash(recomputed.live_journal),
            "event_log_content_sha256": recomputed.live_journal.event_log_content_sha256,
            "network_call_count": sum(card.network_call_count for card in recomputed.scorecards),
            "wall_time_seconds": sum(card.wall_time_seconds for card in recomputed.scorecards),
            "scorecards": [row.model_dump(mode="json") for row in recomputed.scorecards],
        }
    if recomputed.manifest is not None:
        report["growth_backlog"] = [
            row.model_dump(mode="json") for row in recomputed.manifest.growth_backlog
        ]
    return report


def _source_flip_cases() -> tuple[_SourceFlipCase, ...]:
    test_prefix = f"{TEST_MODULE_PATH}::"
    return (
        _SourceFlipCase(
            mutation_id="liveness_dead_relabelled_alive",
            replacements=((
                "    if status in {404, 410}:\n        return LivenessState.DEAD\n",
                "    if status in {404, 410}:\n        return LivenessState.ALIVE_SCHEMA_UNVERIFIED\n",
            ),),
            probe_nodeid=(
                test_prefix + "test_live_liveness_requires_raw_journal_and_rejects_relabeling"
            ),
            expected_red_signal="test_live_liveness_requires_raw_journal_and_rejects_relabeling",
        ),
        _SourceFlipCase(
            mutation_id="scorecard_live_row_without_raw_response",
            replacements=(
                (
                    "        if live_authorized and self.raw_response is None:\n"
                    "            raise ValueError(\"an authorized live result requires journaled raw response evidence\")\n",
                    "        if False and live_authorized and self.raw_response is None:\n"
                    "            raise ValueError(\"an authorized live result requires journaled raw response evidence\")\n",
                ),
                (
                    "    if request is None or raw_response is None:\n"
                    "        raise ValueError(\"authorized probe requires request and raw response\")\n",
                    "    if request is None:\n"
                    "        raise ValueError(\"authorized probe requires request and raw response\")\n"
                    "    if raw_response is None:\n"
                    "        return LivenessState.ALIVE_SCHEMA_UNVERIFIED\n",
                ),
            ),
            probe_nodeid=(
                test_prefix + "test_live_liveness_requires_raw_journal_and_rejects_relabeling"
            ),
            expected_red_signal="test_live_liveness_requires_raw_journal_and_rejects_relabeling",
        ),
        _SourceFlipCase(
            mutation_id="route_class_pinning_accepted",
            replacements=((
                "        if self.route_class is not expected:\n",
                "        if False and self.route_class is not expected:\n",
            ),),
            probe_nodeid=(
                test_prefix + "test_route_class_label_is_rejected_when_it_disagrees_with_evidence"
            ),
            expected_red_signal="test_route_class_label_is_rejected_when_it_disagrees_with_evidence",
        ),
        _SourceFlipCase(
            mutation_id="fetch_plan_execution_fence_removed",
            replacements=((
                "    def preview(self, *_: object, **__: object) -> None:\n"
                "        self.preview_calls += 1\n"
                "        raise CensusExecutionFenceError(\n"
                "            \"fetch_plan_execution_forbidden\",\n"
                "            \"FetchExecutor.preview is forbidden during N13a plan generation\",\n"
                "        )\n",
                "    def preview(self, *_: object, **__: object) -> None:\n"
                "        self.preview_calls += 1\n",
            ),),
            probe_nodeid=test_prefix + "test_fetch_plan_execution_attempt_is_hard_red",
            expected_red_signal="test_fetch_plan_execution_attempt_is_hard_red",
        ),
        _SourceFlipCase(
            mutation_id="growth_backlog_order_reversed",
            replacements=((
                "            -row.ranking_score,\n",
                "            row.ranking_score,\n",
            ),),
            probe_nodeid=(
                test_prefix
                + "test_growth_backlog_ranks_full_residual_denominator_without_claiming_voi"
            ),
            expected_red_signal=(
                "test_growth_backlog_ranks_full_residual_denominator_without_claiming_voi"
            ),
        ),
        _SourceFlipCase(
            mutation_id="connector_family_denominator_hardcoded",
            replacements=((
                "    for connector_id in sorted(populations):\n",
                "    for connector_id in (\"family.alpha\", \"family.beta\"):\n",
            ),),
            probe_nodeid=(
                test_prefix
                + "test_probe_selector_grows_for_a_new_catalog_family_without_code_changes"
            ),
            expected_red_signal=(
                "test_probe_selector_grows_for_a_new_catalog_family_without_code_changes"
            ),
        ),
        _SourceFlipCase(
            mutation_id="connector_fetch_replaced_by_marker_only_dry_run",
            replacements=((
                "                    await asyncio.wait_for(\n"
                "                        harness.test_fetch_returns_fetch_result((connector, handle)),\n"
                "                        timeout=5.0,\n"
                "                    )\n",
                "                    await asyncio.wait_for(asyncio.sleep(0), timeout=5.0)\n",
            ),),
            probe_nodeid=(
                test_prefix
                + "test_connector_owner_dry_run_uses_registry_protocol_owner_and_simulator"
            ),
            expected_red_signal=(
                "test_connector_owner_dry_run_uses_registry_protocol_owner_and_simulator"
            ),
        ),
        _SourceFlipCase(
            mutation_id="progressing_live_probe_given_total_kill_timeout",
            replacements=((
                "        total=None,\n",
                "        total=request.budget.timeout_seconds,\n",
            ),),
            probe_nodeid=(
                test_prefix
                + "test_live_transport_uses_inactivity_timeouts_not_a_total_progress_kill"
            ),
            expected_red_signal=(
                "test_live_transport_uses_inactivity_timeouts_not_a_total_progress_kill"
            ),
        ),
        _SourceFlipCase(
            mutation_id="nested_run_economics_left_in_semantic_hash",
            replacements=((
                "            key: _without_run_economics(item)\n",
                "            key: item\n",
            ),),
            probe_nodeid=(
                test_prefix
                + "test_semantic_content_hash_recursively_excludes_declared_run_economics"
            ),
            expected_red_signal=(
                "test_semantic_content_hash_recursively_excludes_declared_run_economics"
            ),
        ),
    )


def run_source_flip_mutations(repo_root: Path) -> dict[str, Any]:
    """Mutate decisive source properties serially and restore exact original bytes."""

    results = [_run_source_flip(repo_root, case) for case in _source_flip_cases()]
    all_red = all(row["result"] == "RED" for row in results)
    return {
        "issues": [] if all_red else [{"code": "source_flip_mutation_survived"}],
        "results": results,
        "status": "pass" if all_red else "fail",
    }


def _run_source_flip(repo_root: Path, case: _SourceFlipCase) -> dict[str, Any]:
    source_path = repo_root / SOURCE_MODULE_PATH
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    source_text = original.decode("utf-8")
    for old, _ in case.replacements:
        if source_text.count(old) != 1:
            return {
                "mutation_id": case.mutation_id,
                "result": "HARNESS_ERROR",
                "proof": {"source_guard_count": source_text.count(old)},
            }
    mutated = source_text
    for old, new in case.replacements:
        mutated = mutated.replace(old, new, 1)
    completed: subprocess.CompletedProcess[str] | None = None
    error: str | None = None
    started = time.monotonic()
    try:
        source_path.write_text(mutated, encoding="utf-8")
        completed = subprocess.run(
            ("uv", "run", "--extra", "test", "pytest", case.probe_nodeid, "-q"),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            },
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - reported as harness evidence.
        error = str(exc)
    finally:
        source_path.write_bytes(original)
    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    if error is not None or completed is None:
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "proof": error or "source_flip_probe_not_run",
        }
    output = f"{completed.stdout}\n{completed.stderr}"
    red = completed.returncode != 0 and case.expected_red_signal in output
    return {
        "mutation_id": case.mutation_id,
        "result": "RED" if red else "GREEN_MUTATION_SURVIVED",
        "proof": {
            "exit_code": completed.returncode,
            "expected_red_signal": case.expected_red_signal,
            "signal_observed": case.expected_red_signal in output,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-12:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-12:]),
        },
    }


def _stable_artifact_locator(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(POLICY_ENGINE_ROOT.resolve()))
    except ValueError:
        return f"external://{path.name}"


def _write_new_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())


def _write_replace_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _bytes_sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
