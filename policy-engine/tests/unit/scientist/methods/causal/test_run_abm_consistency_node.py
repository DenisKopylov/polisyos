from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts import (
    profile_bound_ref,
)
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.abm_bridge import AlignmentStatus, load_abm_alignment_report
from polisyos.ir.analytics.abstraction import (
    FiniteStateAbstractionMap,
    load_abstraction_certificate,
    persist_finite_state_abstraction_map,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import (
    RunABMConsistencyCheckNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


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
            "distribution": {
                "low": 0.75 if mismatch and macro else 0.8,
                "high": 0.25 if mismatch and macro else 0.2,
            },
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


def _continuous_linear_gaussian_scm(
    *,
    macro: bool,
    outcome_intercept: float,
    outcome_slope: float,
    outcome_noise_std: float,
) -> StructuralCausalModelSpec:
    treatment = "T" if macro else "T_m"
    outcome = "Y" if macro else "Y_m"
    return StructuralCausalModelSpec(
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=[treatment, outcome],
            edges=[CausalEdge(src=treatment, dst=outcome)],
            discovery_method="test",
        ),
        fitted=True,
        fit_method="manual",
        mechanisms=[
            NodeMechanism(
                variable=treatment,
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable=outcome,
                parents=[treatment],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": outcome_intercept,
                    "coefficients": {treatment: outcome_slope},
                    "noise_std": outcome_noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
    )


def _continuous_abstraction_map() -> dict[str, object]:
    return {
        "variable_maps": [
            {
                "micro_variable": "T_m",
                "macro_variable": "T",
                "state_map": {"__continuous__": "__continuous__"},
            },
            {
                "micro_variable": "Y_m",
                "macro_variable": "Y",
                "state_map": {"__continuous__": "__continuous__"},
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
    report = load_abm_alignment_report(_ensure_ir_artifact_store(ctx.store), ref)
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
    report = load_abm_alignment_report(_ensure_ir_artifact_store(ctx.store), ref)
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
    report = load_abm_alignment_report(_ensure_ir_artifact_store(ctx.store), ref)
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
    report = load_abm_alignment_report(_ensure_ir_artifact_store(ctx.store), ref)
    result = report.alignment_results["income_level"]

    assert result.status is AlignmentStatus.CONSISTENT
    assert any("wide_tolerance_consistent_warning" in item for item in report.warnings)


def _graph_refs_from_abm_report(ctx, report_ref):
    report_manifest = ctx.store.get_manifest(report_ref)
    refs = {}
    for role in ("micro_graph", "macro_graph"):
        edge = next(item for item in report_manifest.inputs if item.role == role)
        refs[role] = CausalGraphModelRef.model_validate(
            {
                "artifact_id": str(edge.artifact_id),
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
                "manifest_profile_sha256": edge.manifest_profile_sha256,
            }
        )
    return refs


def _abm_inline_input_cases(
    ctx: ExecutionContext,
    family: str,
) -> tuple[dict[str, Any], dict[str, tuple[str, str, Any, Callable[[Any], Any]]]]:
    store = _ensure_ir_artifact_store(ctx.store)
    params: dict[str, Any] = {
        "abm_macro_micro_mappings": _single_mapping(),
        "scm_effects": {"income_level": 1.0},
        "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
    }
    if family == "finite":
        micro = _finite_state_scm(macro=False)
        macro = _finite_state_scm(macro=True)
        abstraction_map = FiniteStateAbstractionMap.model_validate(_exact_abstraction_map())
        payload_prefix = "finite_state"
    elif family == "continuous":
        micro = _continuous_linear_gaussian_scm(
            macro=False,
            outcome_intercept=0.2,
            outcome_slope=1.2,
            outcome_noise_std=0.1,
        )
        macro = _continuous_linear_gaussian_scm(
            macro=True,
            outcome_intercept=0.1,
            outcome_slope=1.0,
            outcome_noise_std=0.2,
        )
        abstraction_map = FiniteStateAbstractionMap.model_validate(
            _continuous_abstraction_map()
        )
        payload_prefix = "continuous"
        params["continuous_abstraction_bound_config"] = {
            "family": "continuous_linear_gaussian",
            "preservation_type": "policy_value_only",
            "intervention_ranges": {"T": [-1.0, 1.0]},
            "policy_value_weights": {"Y": 1.0},
            "state_weights": {"T": 1.0, "Y": 1.0},
            "proof_obligations_satisfied": ["linear_gaussian_closed_form"],
        }
    else:
        raise AssertionError(f"unknown ABM abstraction family: {family}")

    params.update(
        {
            f"{payload_prefix}_micro_scm": micro.model_dump(mode="json"),
            f"{payload_prefix}_macro_scm": macro.model_dump(mode="json"),
            f"{payload_prefix}_abstraction_map": abstraction_map.model_dump(mode="json"),
        }
    )
    cases = {
        "micro_scm": (
            f"{payload_prefix}_micro_scm",
            f"{payload_prefix}_micro_scm_ref",
            micro,
            lambda value: persist_structural_causal_model_spec(store, value),
        ),
        "macro_scm": (
            f"{payload_prefix}_macro_scm",
            f"{payload_prefix}_macro_scm_ref",
            macro,
            lambda value: persist_structural_causal_model_spec(store, value),
        ),
        "abstraction_map": (
            f"{payload_prefix}_abstraction_map",
            f"{payload_prefix}_abstraction_map_ref",
            abstraction_map,
            lambda value: persist_finite_state_abstraction_map(store, value),
        ),
    }
    return params, cases


def _different_abm_input(slot: str, value: Any) -> Any:
    if slot == "abstraction_map":
        payload = value.model_dump(mode="json")
        first_map = payload["variable_maps"][0]
        state_map = first_map["state_map"]
        first_state = next(iter(state_map))
        state_map[first_state] = "__different_selected_content__"
        return FiniteStateAbstractionMap.model_validate(payload)
    return value.model_copy(update={"fit_metrics": {"different_selected_content": 1.0}})


def test_run_abm_consistency_node_persists_exact_abstraction_certificate(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_abm_exact")
    store = _ensure_ir_artifact_store(ctx.store)
    micro_spec = _finite_state_scm(macro=False)
    macro_spec = _finite_state_scm(macro=True)
    abstraction_map = FiniteStateAbstractionMap.model_validate(_exact_abstraction_map())
    micro_source_ref = profile_bound_ref(
        store,
        persist_structural_causal_model_spec(store, micro_spec),
    )
    macro_source_ref = profile_bound_ref(
        store,
        persist_structural_causal_model_spec(store, macro_spec),
    )
    unselected_map_view = profile_bound_ref(
        store,
        persist_finite_state_abstraction_map(store, abstraction_map),
    )
    map_source_ref = profile_bound_ref(
        store,
        persist_finite_state_abstraction_map(
            store,
            abstraction_map,
            inputs=[
                InputRef(
                    artifact_id=str(micro_source_ref.artifact_id),
                    role="profile_pair_fixture",
                )
            ],
        ),
    )
    assert map_source_ref.artifact_id == unselected_map_view.artifact_id
    assert map_source_ref.manifest_profile_sha256 != unselected_map_view.manifest_profile_sha256
    conflicting_fallback_ref = profile_bound_ref(
        store,
        persist_structural_causal_model_spec(
            store, _finite_state_scm(macro=True, mismatch=True)
        ),
    )
    state = ExperimentState(
        run_id="R_abm_exact",
        artifacts_index={
            ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF: conflicting_fallback_ref,
        },
        params={
            "abm_macro_micro_mappings": _single_mapping(),
            "scm_effects": {"income_level": 1.0},
            "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
            "finite_state_micro_scm": micro_spec.model_dump(mode="json"),
            "finite_state_micro_scm_ref": micro_source_ref.model_dump(mode="json"),
            "finite_state_macro_scm": macro_spec.model_dump(mode="json"),
            "finite_state_macro_scm_ref": macro_source_ref.model_dump(mode="json"),
            "finite_state_abstraction_map": abstraction_map.model_dump(mode="json"),
            "finite_state_abstraction_map_ref": map_source_ref.model_dump(mode="json"),
            "abstraction_preserved_queries": ["observational", "interventional"],
        },
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF in outcome.state.artifacts_index
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF in outcome.state.artifacts_index
    certificate = load_abstraction_certificate(
        _ensure_ir_artifact_store(ctx.store),
        outcome.state.artifacts_index[ARTIFACT_ABSTRACTION_CERTIFICATE_REF],
    )
    assert certificate.preservation_type.value == "exact"
    assert str(certificate.abstraction_map_ref.artifact_id) == str(map_source_ref.artifact_id)
    assert (
        certificate.abstraction_map_ref.manifest_profile_sha256
        == map_source_ref.manifest_profile_sha256
    )
    assert outcome.state.params["abstraction_preservation_type"] == "exact"

    generated_graph_refs = _graph_refs_from_abm_report(
        ctx, outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF]
    )
    for graph_role, source_role, selected_source in (
        ("micro_graph", "micro_structural_causal_model_spec", micro_source_ref),
        ("macro_graph", "macro_structural_causal_model_spec", macro_source_ref),
    ):
        graph_manifest = ctx.store.get_manifest(generated_graph_refs[graph_role])
        source_edges = [edge for edge in graph_manifest.inputs if edge.role == source_role]
        assert len(source_edges) == 1
        assert str(source_edges[0].artifact_id) == str(selected_source.artifact_id)
        assert source_edges[0].manifest_profile_sha256 == selected_source.manifest_profile_sha256
        assert str(source_edges[0].artifact_id) != str(conflicting_fallback_ref.artifact_id)


@pytest.mark.parametrize(
    ("family", "slot"),
    [
        ("finite", "micro_scm"),
        ("finite", "macro_scm"),
        ("finite", "abstraction_map"),
        ("continuous", "micro_scm"),
        ("continuous", "macro_scm"),
        ("continuous", "abstraction_map"),
    ],
)
def test_abm_rejects_conflicting_inline_and_ref_for_every_selected_input_pair(
    tmp_path,
    family: str,
    slot: str,
) -> None:
    run_id = f"R_abm_pair_mismatch_{family}_{slot}"
    ctx = _build_ctx(tmp_path, run_id=run_id)
    params, cases = _abm_inline_input_cases(ctx, family)
    _payload_key, ref_key, selected_value, persist = cases[slot]
    params[ref_key] = persist(_different_abm_input(slot, selected_value)).model_dump(
        mode="json"
    )

    outcome = RunABMConsistencyCheckNode().execute(
        ctx,
        ExperimentState(run_id=run_id, params=params),
    )

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "inline_payload_ref_content_mismatch" in outcome.error.message
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize(
    ("family", "slot"),
    [
        ("finite", "micro_scm"),
        ("finite", "macro_scm"),
        ("finite", "abstraction_map"),
        ("continuous", "micro_scm"),
        ("continuous", "macro_scm"),
        ("continuous", "abstraction_map"),
    ],
)
def test_abm_validates_malformed_inline_even_when_a_ref_is_supplied(
    tmp_path,
    family: str,
    slot: str,
) -> None:
    run_id = f"R_abm_pair_bad_inline_{family}_{slot}"
    ctx = _build_ctx(tmp_path, run_id=run_id)
    params, cases = _abm_inline_input_cases(ctx, family)
    payload_key, ref_key, selected_value, persist = cases[slot]
    params[payload_key] = {"unexpected": "malformed"}
    params[ref_key] = persist(selected_value).model_dump(mode="json")

    outcome = RunABMConsistencyCheckNode().execute(
        ctx,
        ExperimentState(run_id=run_id, params=params),
    )

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "Invalid abstraction payload" in outcome.error.message
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize(
    ("family", "slot"),
    [
        ("finite", "micro_scm"),
        ("finite", "macro_scm"),
        ("finite", "abstraction_map"),
        ("continuous", "micro_scm"),
        ("continuous", "macro_scm"),
        ("continuous", "abstraction_map"),
    ],
)
def test_abm_refuses_malformed_selected_ref_even_when_inline_content_is_valid(
    tmp_path,
    family: str,
    slot: str,
) -> None:
    run_id = f"R_abm_pair_bad_ref_{family}_{slot}"
    ctx = _build_ctx(tmp_path, run_id=run_id)
    params, cases = _abm_inline_input_cases(ctx, family)
    _payload_key, ref_key, _selected_value, _persist = cases[slot]
    params[ref_key] = {"unexpected": "malformed"}

    outcome = RunABMConsistencyCheckNode().execute(
        ctx,
        ExperimentState(run_id=run_id, params=params),
    )

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "Invalid abstraction payload" in outcome.error.message
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize(
    ("family", "slot"),
    [
        ("finite", "micro_scm"),
        ("finite", "macro_scm"),
        ("finite", "abstraction_map"),
        ("continuous", "micro_scm"),
        ("continuous", "macro_scm"),
        ("continuous", "abstraction_map"),
    ],
)
def test_abm_refuses_stale_selected_ref_profile_with_inline_content(
    tmp_path,
    family: str,
    slot: str,
) -> None:
    run_id = f"R_abm_pair_stale_profile_{family}_{slot}"
    ctx = _build_ctx(tmp_path, run_id=run_id)
    params, cases = _abm_inline_input_cases(ctx, family)
    _payload_key, ref_key, selected_value, persist = cases[slot]
    ref = persist(selected_value).model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    params[ref_key] = ref.model_dump(mode="json")

    outcome = RunABMConsistencyCheckNode().execute(
        ctx,
        ExperimentState(run_id=run_id, params=params),
    )

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "Invalid abstraction payload" in outcome.error.message
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF not in outcome.state.artifacts_index


def test_abm_explicit_null_is_not_true_absence(tmp_path) -> None:
    absent_ctx = _build_ctx(tmp_path, run_id="R_abm_true_absence")
    absent = RunABMConsistencyCheckNode().execute(
        absent_ctx,
        ExperimentState(
            run_id="R_abm_true_absence",
            params={
                "abm_macro_micro_mappings": _single_mapping(),
                "scm_effects": {"income_level": 1.0},
                "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
            },
        ),
    )
    assert absent.status == "ok"
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF not in absent.state.artifacts_index

    null_ctx = _build_ctx(tmp_path, run_id="R_abm_explicit_null")
    explicit_null = RunABMConsistencyCheckNode().execute(
        null_ctx,
        ExperimentState(
            run_id="R_abm_explicit_null",
            params={
                "abm_macro_micro_mappings": _single_mapping(),
                "scm_effects": {"income_level": 1.0},
                "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
                "finite_state_micro_scm": None,
            },
        ),
    )
    assert explicit_null.status == "fail"
    assert explicit_null.error is not None
    assert "Invalid abstraction payload" in explicit_null.error.message


def test_run_abm_consistency_node_warns_when_only_heuristic_alignment_is_available(
    tmp_path,
) -> None:
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
        _ensure_ir_artifact_store(ctx.store),
        outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF],
    )
    assert "heuristic_aggregation_without_abstraction_certificate" in report.warnings


@pytest.mark.parametrize("source_mode", ["inline", "explicit_refs", "paired"])
def test_run_abm_consistency_node_persists_continuous_abstraction_certificate(
    tmp_path,
    source_mode: str,
) -> None:
    run_id = f"R_abm_continuous_{source_mode}"
    ctx = _build_ctx(tmp_path, run_id=run_id)
    store = _ensure_ir_artifact_store(ctx.store)
    micro_spec = _continuous_linear_gaussian_scm(
        macro=False,
        outcome_intercept=0.2,
        outcome_slope=1.2,
        outcome_noise_std=0.1,
    )
    macro_spec = _continuous_linear_gaussian_scm(
        macro=True,
        outcome_intercept=0.1,
        outcome_slope=1.0,
        outcome_noise_std=0.2,
    )
    unused_fallback_ref = profile_bound_ref(
        store,
        persist_structural_causal_model_spec(
            store,
            _continuous_linear_gaussian_scm(
                macro=True,
                outcome_intercept=0.9,
                outcome_slope=0.9,
                outcome_noise_std=0.3,
            ),
        ),
    )
    params = {
        "abm_macro_micro_mappings": _single_mapping(),
        "scm_effects": {"income_level": 1.0},
        "abm_run_stats": {"income_level": {"effects": [0.95, 1.0, 1.05]}},
        "continuous_abstraction_bound_config": {
            "family": "continuous_linear_gaussian",
            "preservation_type": "policy_value_only",
            "intervention_ranges": {"T": [-1.0, 1.0]},
            "policy_value_weights": {"Y": 1.0},
            "state_weights": {"T": 1.0, "Y": 1.0},
            "proof_obligations_satisfied": ["linear_gaussian_closed_form"],
        },
        "abstraction_preserved_queries": ["policy_value:planner_welfare"],
    }
    expected_sources = {}
    map_spec = FiniteStateAbstractionMap.model_validate(_continuous_abstraction_map())
    if source_mode == "inline":
        params.update(
            {
                "continuous_micro_scm": micro_spec.model_dump(mode="json"),
                "continuous_macro_scm": macro_spec.model_dump(mode="json"),
                "continuous_abstraction_map": map_spec.model_dump(mode="json"),
            }
        )
    else:
        micro_source_ref = profile_bound_ref(
            store, persist_structural_causal_model_spec(store, micro_spec)
        )
        macro_source_ref = profile_bound_ref(
            store, persist_structural_causal_model_spec(store, macro_spec)
        )
        map_source_ref = profile_bound_ref(
            store, persist_finite_state_abstraction_map(store, map_spec)
        )
        expected_sources = {
            "micro_graph": (
                "micro_structural_causal_model_spec",
                micro_source_ref,
            ),
            "macro_graph": (
                "macro_structural_causal_model_spec",
                macro_source_ref,
            ),
        }
        params.update(
            {
                "continuous_micro_scm_ref": micro_source_ref.model_dump(mode="json"),
                "continuous_macro_scm_ref": macro_source_ref.model_dump(mode="json"),
                "continuous_abstraction_map_ref": map_source_ref.model_dump(mode="json"),
            }
        )
        if source_mode == "paired":
            params.update(
                {
                    "continuous_micro_scm": micro_spec.model_dump(mode="json"),
                    "continuous_macro_scm": macro_spec.model_dump(mode="json"),
                    "continuous_abstraction_map": map_spec.model_dump(mode="json"),
                }
            )
    state = ExperimentState(
        run_id=run_id,
        artifacts_index={ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF: unused_fallback_ref},
        params=params,
    )

    outcome = RunABMConsistencyCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF in outcome.state.artifacts_index
    assert ARTIFACT_ABSTRACTION_CERTIFICATE_REF in outcome.state.artifacts_index
    certificate = load_abstraction_certificate(
        _ensure_ir_artifact_store(ctx.store),
        outcome.state.artifacts_index[ARTIFACT_ABSTRACTION_CERTIFICATE_REF],
    )
    assert certificate.preservation_type.value == "policy_value_only"
    if source_mode != "inline":
        assert str(certificate.abstraction_map_ref.artifact_id) == str(map_source_ref.artifact_id)
        assert (
            certificate.abstraction_map_ref.manifest_profile_sha256
            == map_source_ref.manifest_profile_sha256
        )
    assert certificate.error_bound == pytest.approx(0.3)
    assert certificate.metadata["error_bound_spec"]["recommendation_margin_required"] == (
        pytest.approx(0.6)
    )
    assert outcome.state.params["abstraction_preservation_type"] == "policy_value_only"
    report_ref = outcome.state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF]
    report = load_abm_alignment_report(
        _ensure_ir_artifact_store(ctx.store),
        report_ref,
    )
    for graph_role, graph_ref in _graph_refs_from_abm_report(ctx, report_ref).items():
        graph_manifest = ctx.store.get_manifest(graph_ref)
        source_role_ref = expected_sources.get(graph_role)
        if source_role_ref is None:
            assert all(
                str(edge.artifact_id) != str(unused_fallback_ref.artifact_id)
                for edge in graph_manifest.inputs
            )
            assert not graph_manifest.inputs
            continue
        source_role, selected_source_ref = source_role_ref
        selected_edges = [edge for edge in graph_manifest.inputs if edge.role == source_role]
        assert len(selected_edges) == 1
        assert str(selected_edges[0].artifact_id) == str(selected_source_ref.artifact_id)
        assert selected_edges[0].manifest_profile_sha256 == (
            selected_source_ref.manifest_profile_sha256
        )
        assert str(selected_edges[0].artifact_id) != str(unused_fallback_ref.artifact_id)
    assert "heuristic_aggregation_without_abstraction_certificate" not in report.warnings
