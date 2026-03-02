from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.abm_bridge import AlignmentStatus, load_abm_alignment_report
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import RunABMConsistencyCheckNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_ABM_ALIGNMENT_REPORT_REF


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _single_mapping() -> list[dict[str, object]]:
    return [
        {
            "macro_variable": "income_level",
            "abm_aggregation": "mean(agent.income)",
            "aggregation_function": "mean",
            "agent_property": "income",
            "tolerance_method": "adaptive",
        }
    ]


def test_run_abm_consistency_node_skips_without_mappings(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_skip")
    state = ExperimentState(run_id="R_abm_skip")

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "skip"


def test_run_abm_consistency_node_consistent_with_adaptive_tolerance(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_consistent")
    state = ExperimentState(
        run_id="R_abm_consistent",
        params={
            "abm_macro_micro_mappings": _single_mapping(),
            "scm_effects": {"income_level": 1.0},
            "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
        },
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    ref = outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF]
    report = load_abm_alignment_report(ctx.store, ref)
    result = report.alignment_results["income_level"]

    assert result.status is AlignmentStatus.CONSISTENT
    assert report.overall_consistent is True


def test_run_abm_consistency_node_marks_insufficient_runs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_insufficient")
    state = ExperimentState(
        run_id="R_abm_insufficient",
        params={
            "abm_macro_micro_mappings": _single_mapping(),
            "scm_effects": {"income_level": 1.0},
            "abm_run_stats": {"income_level": {"effects": [1.0, 1.1]}},
        },
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    ref = outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF]
    report = load_abm_alignment_report(ctx.store, ref)
    result = report.alignment_results["income_level"]

    assert result.status is AlignmentStatus.INSUFFICIENT_RUNS
    assert report.overall_consistent is False


def test_run_abm_consistency_node_detects_non_linear_divergence(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_phase")
    state = ExperimentState(
        run_id="R_abm_phase",
        params={
            "abm_macro_micro_mappings": _single_mapping(),
            "scm_effects": {"income_level": 0.5},
            "abm_bridge_config": {"phase_jump_sigma_mult": 1.0},
            "abm_run_stats": {
                "income_level": {
                    "effects": [0.45, 0.5, 0.55, 0.6],
                    "response_curve": [
                        {"intervention": 0.0, "effect": 0.1},
                        {"intervention": 0.1, "effect": 0.12},
                        {"intervention": 0.2, "effect": 0.14},
                        {"intervention": 0.3, "effect": 0.8},
                        {"intervention": 0.4, "effect": 1.2},
                    ],
                }
            },
        },
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    ref = outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF]
    report = load_abm_alignment_report(ctx.store, ref)
    result = report.alignment_results["income_level"]

    assert result.status is AlignmentStatus.NON_LINEAR_DIVERGENCE
    assert len(report.phase_transitions) >= 1


def test_run_abm_consistency_node_emits_wide_tolerance_warning(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_wide_tol")
    state = ExperimentState(
        run_id="R_abm_wide_tol",
        params={
            "abm_macro_micro_mappings": _single_mapping(),
            "scm_effects": {"income_level": 0.1},
            "abm_run_stats": {
                "income_level": {
                    "effects": [-0.1, 0.0, 0.2, 0.1, 0.3],
                }
            },
        },
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert any(event.level == "warn" for event in outcome.events)

    ref = outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF]
    report = load_abm_alignment_report(ctx.store, ref)
    result = report.alignment_results["income_level"]

    assert result.status is AlignmentStatus.CONSISTENT
    assert any("wide_tolerance_consistent_warning" in item for item in report.warnings)
