from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.abstraction import load_abstraction_certificate
from polisyos.ir.analytics.abm_bridge import AlignmentStatus, load_abm_alignment_report
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import RunABMConsistencyCheckNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
)


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


def _finite_state_scm(*, macro: bool, mismatch: bool = False) -> StructuralCausalModelSpec:
    x_name = "X" if macro else "X_m"
    y_name = "Y" if macro else "Y_m"
    conditional = [
        {
            "when": {x_name: "0"},
            "distribution": {"low": 0.75 if mismatch and macro else 0.8, "high": 0.25 if mismatch and macro else 0.2},
        },
        {
            "when": {x_name: "1"},
            "distribution": {"low": 0.3, "high": 0.7},
        },
    ]
    return StructuralCausalModelSpec(
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=[x_name, y_name],
            edges=[CausalEdge(src=x_name, dst=y_name)],
            discovery_method="test",
        ),
        fitted=True,
        fit_method="manual",
        mechanisms=[
            NodeMechanism(
                variable=x_name,
                family=MechanismFamily.EMPIRICAL,
                family_params={
                    "state_space": ["0", "1"],
                    "distribution": {"0": 0.5, "1": 0.5},
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable=y_name,
                parents=[x_name],
                family=MechanismFamily.EMPIRICAL,
                family_params={
                    "state_space": ["low", "high"],
                    "conditional_distribution": conditional,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
    )


def _exact_abstraction_map() -> dict[str, object]:
    return {
        "variable_maps": [
            {
                "micro_variable": "X_m",
                "macro_variable": "X",
                "state_map": {"0": "0", "1": "1"},
            },
            {
                "micro_variable": "Y_m",
                "macro_variable": "Y",
                "state_map": {"low": "low", "high": "high"},
            },
        ]
    }


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


def test_run_abm_consistency_node_persists_exact_abstraction_certificate(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_exact")
    state = ExperimentState(
        run_id="R_abm_exact",
        params={
            "abm_macro_micro_mappings": _single_mapping(),
            "scm_effects": {"income_level": 1.0},
            "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
            "finite_state_micro_scm": _finite_state_scm(macro=False).model_dump(mode="json"),
            "finite_state_macro_scm": _finite_state_scm(macro=True).model_dump(mode="json"),
            "finite_state_abstraction_map": _exact_abstraction_map(),
            "abstraction_preserved_queries": ["observational", "interventional"],
        },
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF in outcome.state.artifacts_index
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF in outcome.state.artifacts_index
    certificate = load_abstraction_certificate(
        ctx.store,
        outcome.state.artifacts_index[ARTIFACT_ABSTRACTION_CERTIFICATE_REF],
    )
    assert certificate.preservation_type.value == "exact"
    assert outcome.state.params["abstraction_preservation_type"] == "exact"


def test_run_abm_consistency_node_warns_when_only_heuristic_alignment_is_available(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_heuristic")
    state = ExperimentState(
        run_id="R_abm_heuristic",
        params={
            "abm_macro_micro_mappings": _single_mapping(),
            "scm_effects": {"income_level": 1.0},
            "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
        },
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    report = load_abm_alignment_report(
        ctx.store, outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF]
    )
    assert "heuristic_aggregation_without_abstraction_certificate" in report.warnings
