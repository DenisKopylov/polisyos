#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N8 value-gate contract."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

import numpy as np
from pydantic import ValidationError

from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.generation_cycle import (
    ValueCalibrationReceipt,
    ValueEvaluationMode,
    ValueGateReceipt,
    ValueTransportReceipt,
)

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.value_gate_contract.v1"
VALUE_GATE_RULE_VERSION = "policyos.layer3.gy.n8.value_gate.v1"
CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"contract_content_hash"}
EXPECTED_MUTATION_IDS: tuple[str, ...] = (
    "value_outer_set_width_supplied_not_derived",
    "proxy_forecast_narrow_set_rejected",
    "value_world_version_laundered",
    "dominance_timeout_forced_not_unknown",
    "simulate_only_shrank_k_world",
    "bad_forecast_minted_value",
    "pilot_mode_ran_without_eval_safety",
    "value_method_selection_fixed_default",
    "value_blocked_candidate_promoted_to_decision_front",
)


@dataclass(frozen=True)
class _AuditProblem:
    design_problem_id: str
    problem_statement: str
    domain: str
    runtime_hints: dict[str, Any]


@dataclass(frozen=True)
class _AuditAtom:
    intervention_id: str
    content_hash: str
    target_world_slots: tuple[str, ...] = ("firm_survival",)
    world_model_record_ref: str = "world_model_record_1111111111111111"


@dataclass(frozen=True)
class _AuditCandidate:
    candidate_id: str
    atom: _AuditAtom
    diversity_key: tuple[str, str, str, str]


@dataclass(frozen=True)
class _AuditWorld:
    world_model_record_id: str = "world_model_record_1111111111111111"
    content_hash: str = "sha256:" + "1" * 64
    valid_time_scope: str = "2026"


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_src_path(repo_root: Path) -> None:
    src = repo_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _quiet_call(func: Callable[[], Any]) -> Any:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        return func()


def build_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Build the cheap frozen N8 contract payload without a live foundry solve."""

    repo_root = (repo_root or _repo_root()).resolve()
    _ensure_src_path(repo_root)
    methods = _quiet_call(_reachable_value_methods)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "produced_by": "tools/quality/validation/check_layer3_gy_value_gate_contract.py",
        "disposition": {
            "task": "GY-N8",
            "disposition": "rework_existing_wire",
            "owner_surface": "polisyos.runtime.quality.generation_cycle.FoundryValuePort",
            "selector_surface": "polisyos.foundry.methods.selection.select_value_method_for_problem",
            "parallel_value_engine": "blocked_by_P27",
        },
        "pattern_pass": {
            "relevant_ids": ["P10", "P14", "P27", "P29", "P32"],
            "target_correct_pattern": (
                "Foundry value method execution + S10 calibration + transport receipt "
                "over a named WorldModelRecord mints the only N8 value authority."
            ),
            "capability_labels": [],
            "acceptance_signal": "all_decisive_mutations_red_and_live_rederive_passes",
        },
        "denominators": {
            "evaluation_modes": list(get_args(ValueEvaluationMode)),
            "identification_statuses": ["point", "partial", "proxy"],
            "reachable_value_methods_count": len(methods),
            "reachable_value_methods": list(methods),
            "python314_unavailable_method_blockers": _python314_blockers(methods),
        },
        "mode_gates": {
            "simulate_only": "runs_value_gate_without_narrowing_k_world",
            "retrospective": "requires_data_trust",
            "measurement_audit": "requires_data_trust",
            "sandbox_pilot": "blocked_pending_GY_O0_eval_safety",
            "field_pilot": "blocked_pending_GY_O0_eval_safety",
            "deployment": "blocked_pending_GY_O0_eval_safety",
        },
        "frozen_value_receipts": _frozen_value_receipts(),
        "honest_blocked_cases": {
            "uncalibrated": "uncalibrated_forecast_minted_value",
            "unsupported_method": "unsupported_method_unavailable",
            "regime_laundered": "regime_laundered_forecast_minted_value",
            "untransportable": "untransportable_forecast_minted_value",
            "pilot_or_deployment_mode": "eval_safety_gate_unavailable",
        },
        "decisive_mutations": _mutation_results(repo_root),
        "compute_economics": {
            "routine_check_live_solve": False,
            "live_resolve_flag": "--rederive-audit",
            "wmr_cache_rule": "build_once_per_world_model_record_content_hash",
            "wall_time_recorded_by_validator": True,
            "wall_time_reported_outside_byte_stable_artifact": True,
        },
    }
    payload["contract_content_hash"] = _content_hash(payload)
    return payload


def _reachable_value_methods() -> tuple[str, ...]:
    from polisyos.foundry.methods.selection import reachable_value_method_fqns
    from polisyos.foundry.methods.selection.registry import MethodRegistry

    MethodRegistry.reset_instance()
    return reachable_value_method_fqns()


def _python314_blockers(methods: tuple[str, ...]) -> list[dict[str, Any]]:
    blockers = []
    for family in ("dowhy", "econml", "cvxpy"):
        matching = tuple(method for method in methods if family in method)
        blockers.append(
            {
                "dependency_family": family,
                "status": "honest_blocker_if_backend_unavailable_under_python_3_14",
                "registered_methods": list(matching),
            }
        )
    return blockers


def _frozen_value_receipts() -> list[dict[str, Any]]:
    return [
        _receipt_payload("point", lower=(4.0,), upper=(4.0,), transport_status="identified"),
        _receipt_payload(
            "partial",
            lower=(2.0,),
            upper=(5.5,),
            transport_status="bounded_non_identified",
        ),
        _receipt_payload(
            "proxy",
            lower=(0.5,),
            upper=(8.0,),
            transport_status="transported_limited",
            forecast_tier="transported_limited",
            transport_mode="bounds_only",
        ),
    ]


def _receipt_payload(
    identification_status: str,
    *,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    transport_status: str,
    forecast_tier: str = "observable_calibrated",
    transport_mode: str = "direct",
) -> dict[str, Any]:
    value_set = _value_set(
        identification_status,
        lower=lower,
        upper=upper,
        forecast_tier=forecast_tier,
        transport_status=transport_status,
    )
    transport = _transport_receipt(
        status="transported_limited" if transport_mode != "direct" else "direct",
        transport_status=transport_status,
        transport_mode=transport_mode,
    )
    calibration = _calibration_receipt(forecast_tier=forecast_tier)
    value_ref = gy_content_hash(
        {
            "value_outer_set": value_set.canonical_payload(),
            "transport_receipt": transport.model_dump(mode="json"),
            "calibration_receipt": calibration.model_dump(mode="json"),
        }
    )
    receipt = ValueGateReceipt(
        candidate_id=f"candidate_{identification_status}",
        evaluation_mode="simulate_only",
        selected_method_fqn="causal.inference.synthetic_control@1.0.0",
        method_selection_trace=("foundry_registry_advisor",),
        identification_status=identification_status,  # type: ignore[arg-type]
        value_outer_set=value_set,
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_model_record_id="world_model_record_1111111111111111",
        world_model_record_content_hash=_hash("1"),
        value_ref=value_ref,
        wall_time_ms=0.0,
        wmr_cache_status="built",
        k_world_ref_before=_hash("1"),
        k_world_ref_after=_hash("1"),
    )
    return {
        **receipt.model_dump(mode="json"),
        "value_outer_set_width_derived": list(value_set.width),
    }


def _value_set(
    identification_status: str,
    *,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    forecast_tier: str = "observable_calibrated",
    transport_status: str = "identified",
) -> ValueOuterSet:
    return ValueOuterSet.interval_box(
        coordinates=("firm_survival",),
        lower=lower,
        upper=upper,
        identification_mode=identification_status,
        assumptions=("foundry_method_output", f"transport:{transport_status}"),
        assumption_status="externally_supported",
        calibration_scope={
            "forecast_tier": forecast_tier,
            "transport_status": transport_status,
        },
        data_trust=DataTrust(
            tier="observable_calibrated",
            trust_cap=0.85,
            trust_multiplier=0.95,
            min_coverage=0.5,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="policyos.layer3.gy.n8.frozen_receipt",
        ),
        world_model_record_ref=_hash("1"),
        epoch="2026",
        representation_status="certified",
    )


def _transport_receipt(
    *,
    status: str = "direct",
    transport_status: str = "identified",
    transport_mode: str = "direct",
) -> ValueTransportReceipt:
    return ValueTransportReceipt(
        status=status,  # type: ignore[arg-type]
        world_model_record_id="world_model_record_1111111111111111",
        world_model_record_content_hash=_hash("1"),
        transport_result_ref=gy_content_hash({"transport_status": transport_status}),
        transport_status=transport_status,
        transport_mode=transport_mode,
        identification_engine="transport_engine",
        required_target_data=(),
        limitation_refs=(),
    )


def _calibration_receipt(
    *,
    status: str = "pass",
    forecast_tier: str = "observable_calibrated",
) -> ValueCalibrationReceipt:
    return ValueCalibrationReceipt(
        status=status,  # type: ignore[arg-type]
        forecast_tier=forecast_tier,
        calibration_record_ref="pdc://layer3/gy/n8/calibration/observable-subset",
        uncertainty_interval_refs=("interval://layer3/gy/n8/95",),
        false_clear_counts={},
        issue_codes=(),
    )


def _mutation_results(repo_root: Path) -> list[dict[str, Any]]:
    del repo_root
    probes = {
        "value_outer_set_width_supplied_not_derived": _probe_supplied_width_rejected,
        "proxy_forecast_narrow_set_rejected": _probe_proxy_narrow_rejected,
        "value_world_version_laundered": _probe_world_laundering_rejected,
        "dominance_timeout_forced_not_unknown": _probe_timeout_unknown,
        "simulate_only_shrank_k_world": _probe_simulate_only_shrink_rejected,
        "bad_forecast_minted_value": _probe_bad_forecast_cases_blocked,
        "pilot_mode_ran_without_eval_safety": _probe_mode_gates_block,
        "value_method_selection_fixed_default": _probe_selection_not_fixed_default,
        "value_blocked_candidate_promoted_to_decision_front": _probe_value_blocks_promotion,
    }
    results = []
    for mutation_id, probe in probes.items():
        try:
            detail = probe()
            results.append(
                {
                    "mutation_id": mutation_id,
                    "result": "RED",
                    "proof": detail,
                }
            )
        except Exception as exc:  # pragma: no cover - validator emits this as data.
            results.append(
                {
                    "mutation_id": mutation_id,
                    "result": "GREEN_MUTATION_SURVIVED",
                    "proof": str(exc),
                }
            )
    return results


def _probe_supplied_width_rejected() -> str:
    value_set = _value_set("point", lower=(1.0,), upper=(1.0,))
    payload = value_set.model_dump(mode="json")
    try:
        ValueOuterSet.model_validate(payload)
    except ValueError as exc:
        if "value_outer_set_width_supplied_not_derived" in str(exc):
            return "ValueOuterSet.model_validate rejects non-empty supplied width."
    raise AssertionError("supplied width accepted")


def _probe_proxy_narrow_rejected() -> str:
    try:
        _value_set("proxy", lower=(1.0,), upper=(1.0,), forecast_tier="transported_limited")
    except ValueError as exc:
        if "bounded_identification_requires_nonzero_interval" in str(exc):
            return "Proxy identification cannot emit a narrow/point set."
    raise AssertionError("proxy narrow set accepted")


def _probe_world_laundering_rejected() -> str:
    receipt = _receipt_object("point")
    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
    payload["world_model_record_content_hash"] = _hash("2")
    try:
        ValueGateReceipt.model_validate(payload)
    except ValueError as exc:
        if "value_world_version_laundered" in str(exc):
            return "Receipt refuses V1 value as authority for V2 world hash."
    raise AssertionError("world-version laundering accepted")


def _probe_timeout_unknown() -> str:
    left = _value_set("partial", lower=(3.0,), upper=(4.0,))
    right = _value_set("partial", lower=(1.0,), upper=(2.0,))
    if left.compare(right) != "dominates":
        raise AssertionError("fixture does not dominate without timeout")
    if left.compare(right, force_timeout=True) != "unknown":
        raise AssertionError("timeout did not return unknown")
    return "Timeout/approximation path returns unknown, not dominance."


def _probe_simulate_only_shrink_rejected() -> str:
    receipt = _receipt_object("point")
    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
    payload["k_world_ref_after"] = _hash("3")
    try:
        ValueGateReceipt.model_validate(payload)
    except ValueError as exc:
        if "simulate_only_shrank_k_world" in str(exc):
            return "simulate_only receipt refuses K_world narrowing."
    raise AssertionError("simulate_only K_world shrink accepted")


def _probe_bad_forecast_cases_blocked() -> str:
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        _run_value_transport,
    )

    cases = {
        "uncalibrated": {"forecast_support": None},
        "unsupported": {"method_fqn": "causal.inference.no_such_method@9.9.9"},
        }
    observed = []
    for name, overrides in cases.items():
        observation = _quiet_call(
            lambda name=name, overrides=overrides: FoundryValuePort()(
                candidate=_AuditCandidate(
                    "candidate_bad_forecast",
                    _AuditAtom("candidate_bad_forecast", _hash("4")),
                    ("grant", "firms", "value", name),
                ),
                simulation=_audit_simulation(),
                problem=_audit_problem(overrides=overrides),
                cycle_index=0,
            )
        )
        if observation.status != "value_blocked" or observation.value_receipt is not None:
            raise AssertionError(f"{name} minted value")
        observed.append(f"{name}:{observation.authority_blockers[0]}")
    transport, error = _run_value_transport(
        inputs={
            "selection_diagram": {"invalid": "selection-diagram"},
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        world_record=_AuditWorld(),
    )
    if transport is not None or not str(error or "").startswith("untransportable_forecast"):
        raise AssertionError("untransportable forecast minted value")
    observed.append(f"untransportable:{error}")
    return "; ".join(observed)


def _probe_mode_gates_block() -> str:
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort

    blocked = []
    for mode in ("sandbox_pilot", "field_pilot", "deployment"):
        observation = FoundryValuePort()(
            candidate=_AuditCandidate(
                "candidate_mode_gate",
                _AuditAtom("candidate_mode_gate", _hash("5")),
                ("grant", "firms", "mode", mode),
            ),
            simulation=_audit_simulation(),
            problem=_audit_problem(overrides={"evaluation_mode": mode}),
            cycle_index=0,
        )
        if observation.authority_blockers != ("eval_safety_gate_unavailable",):
            raise AssertionError(f"{mode} did not block on EvalSafety")
        blocked.append(mode)
    return "EvalSafety blocks " + ",".join(blocked)


def _probe_selection_not_fixed_default() -> str:
    from polisyos.foundry.methods.selection import select_value_method_for_problem

    selection = _quiet_call(
        lambda: select_value_method_for_problem(
            candidate={
                "candidate_id": "candidate_panel",
                "atom": {"target_world_slots": ("panel", "firm_survival")},
            },
            problem={
                "design_problem_id": "selector_problem",
                "runtime_hints": {
                    "value_method_hint": "panel",
                    "value_required_data_modalities": ("panel",),
                },
            },
        )
    )
    if selection.get("selection_source") != "foundry_registry_advisor":
        raise AssertionError("selector did not use Foundry advisor")
    for path in (
        "src/polisyos/runtime/quality/workspace/loop.py",
        "src/polisyos/foundry/methods/compiler/plan_optimizer.py",
    ):
        text = (_repo_root() / path).read_text(encoding="utf-8")
        if "causal.inference.synthetic_control@1.0.0" in text:
            raise AssertionError(f"fixed synthetic_control default survives in {path}")
    return f"Advisor selected {selection.get('selected_method_fqn')} from registry denominator."


def _probe_value_blocks_promotion() -> str:
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSummary,
        PromotionPortObservation,
        _apply_promotion_to_summaries,
    )

    summary = CandidateSummary(
        candidate_id="candidate_value_blocked",
        content_hash=_hash("6"),
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.9,
        current_valid=True,
        value_status="value_blocked",
        value_decision_grade="blocked",
        value_blockers=("uncalibrated_forecast_minted_value",),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )
    promoted = _apply_promotion_to_summaries(
        (summary,),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_value_blocked",),
        ),
    )
    if promoted[0].front == "decision":
        raise AssertionError("blocked value promoted to DecisionFront")
    return "N6 promotion reducer refuses value_blocked summary."


def _receipt_object(identification_status: str) -> ValueGateReceipt:
    payload = _receipt_payload(
        identification_status,
        lower=(4.0,) if identification_status == "point" else (2.0,),
        upper=(4.0,) if identification_status == "point" else (5.0,),
        transport_status="identified",
    )
    payload.pop("value_outer_set_width_derived", None)
    payload["value_outer_set"].pop("width", None)
    return ValueGateReceipt.model_validate(payload)


def _audit_simulation() -> Any:
    from polisyos.runtime.quality.generation_cycle import SimulationPortObservation

    return SimulationPortObservation(
        candidate_id="candidate_audit",
        status="joint_simulated",
        simulation_ref=_hash("7"),
        k_world_ref_before=_hash("1"),
        k_world_ref_after=_hash("1"),
    )


def _audit_problem(*, overrides: Mapping[str, Any] | None = None) -> _AuditProblem:
    inputs = _audit_value_inputs()
    inputs.update(dict(overrides or {}))
    return _AuditProblem(
        design_problem_id="value_gate_audit_problem",
        problem_statement="Audit N8 value gate.",
        domain="runtime_quality",
        runtime_hints={"value_gate_inputs": inputs},
    )


def _audit_value_inputs() -> dict[str, Any]:
    from polisyos.foundry.methods.causal import PanelObservationalData
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.transportability import SelectionDiagram
    from polisyos.runtime.quality.design_axes.outcome_prediction import (
        build_forecast_calibration_record,
        build_forecast_support,
    )
    from polisyos.runtime.quality.world_model_record import WorldModelRecord

    now = datetime(2026, 6, 2, tzinfo=UTC)
    authority = _authority_boundary()
    calibration = build_forecast_calibration_record(
        calibration_id="layer3.gy.n8.calibration",
        calibration_ref="pdc://layer3/gy/n8/calibration",
        case_id="layer3_gy_n8",
        forecast_support_ref="pdc://layer3/gy/n8/forecast-support",
        observable_subset_ref="pdc://layer3/gy/n8/observable-subset",
        prediction_ref="forecast://layer3/gy/n8/prediction",
        observed_outcome_ref="outcome://layer3/gy/n8/observed",
        historical_implementation_ref="implementation://layer3/gy/n8",
        evaluation_design_ref="eval://layer3/gy/n8/credible-counterfactual",
        credible_evaluation_evidence_ref="evidence://layer3/gy/n8/credible",
        counterfactual_credibility="credible",
        prediction_time=now,
        observation_time=now,
        policy_effective_time=now,
        data_valid_time=now,
        calibration_window_start=now,
        calibration_window_end=now,
        metric_name="observable_subset_calibration",
        denominator=4,
        numerator=4,
        pass_rate=1.0,
        calibration_threshold_ref="repo://architecture/policy_design_case/layer2_floor_governance.toml#s10",
        floor_passed=True,
        calibration_status="pass",
        interval_coverage_metric=1.0,
        calibration_error_metric=0.0,
        source_lineage_refs=["lineage://layer3/gy/n8/source"],
        method_lineage_refs=["lineage://layer3/gy/n8/foundry"],
        floor_id="s10_calibration",
        authority_boundary=authority,
        may_not_use_for=authority["may_not_use_for"],
        rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
    )
    support = build_forecast_support(
        support_id="layer3.gy.n8.forecast-support",
        support_ref="pdc://layer3/gy/n8/forecast-support",
        case_id="layer3_gy_n8",
        source_design_record_ref="pdc://layer3/gy/n8/design-record",
        design_graph_ref="pdc://layer3/gy/n8/design-graph",
        prediction_context_ref="pdc://layer3/gy/n8/prediction-context",
        policy_context_ref="policy-context://layer3/gy/n8",
        candidate_design_ref="candidate://layer3/gy/n8",
        baseline_design_ref="baseline://layer3/gy/n8",
        alternative_design_refs=["alternative://layer3/gy/n8"],
        prediction_horizon_ref="horizon://12-months",
        target_outcome_refs=["outcome://firm-survival"],
        jurisdiction_scope_ref="UA",
        s5_forecast_support_ref="pdc://layer3/gy/n8/s5",
        s5_support_label="validated_local_dynamic_model",
        s5_base_origin="validated_local_model",
        s5_claim_scope="system_effect",
        s6_firewall_status_refs=["pdc://layer3/gy/n8/s6"],
        s6_limitation_refs=["pdc://layer3/gy/n8/limitation"],
        s8_value_choice_provenance_ref="pdc://layer3/gy/n8/s8",
        s8_value_tradeoff_disclosure_ref="pdc://layer3/gy/n8/s8-disclosure",
        source_contract_ref="source-contract://layer3/gy/n8/panel",
        method_validity_ref="method-validity://foundry/causal/local",
        sensitivity_analysis_ref="sensitivity://layer3/gy/n8",
        dynamic_equilibrium_check_ref="equilibrium-check://layer3/gy/n8",
        equilibrium_caveat_refs=["caveat://partial-equilibrium"],
        strategic_response_caveat_refs=["caveat://strategic-response"],
        outcome_distribution_refs=["pdc://layer3/gy/n8/distribution"],
        welfare_comparison_ref="pdc://layer3/gy/n8/welfare",
        forecast_tier="observable_calibrated",
        forecast_authority_disposition_reason="validated local model",
        method_family="foundry_causal",
        observable_subset_ref="pdc://layer3/gy/n8/observable-subset",
        calibration_record_ref="pdc://layer3/gy/n8/calibration",
        uncertainty_interval_refs=["interval://layer3/gy/n8/95"],
        limitation_refs=["limitation://layer3/gy/n8/support-only"],
        abstention_refs=[],
        authority_boundary=authority,
        may_not_use_for=authority["may_not_use_for"],
        rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
    )
    panel = PanelObservationalData(
        outcome=np.array(
            [
                [10.0, 11.0, 12.0, 13.0, 18.0, 19.0, 20.0, 21.0],
                [8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
                [9.0, 9.0, 10.0, 10.0, 10.0, 11.0, 11.0, 12.0],
            ]
        ),
        treatment=np.array([1, 0, 0]),
        time_treatment=4,
    )
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    selection_diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
    )
    world_record = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_1111111111111111",
        content_hash=_hash("1"),
        valid_time_scope="2026",
        producer_ref="tools.quality.validation.check_layer3_gy_value_gate_contract",
    )
    return {
        "evaluation_mode": "simulate_only",
        "world_model_record": world_record,
        "forecast_support": support,
        "forecast_calibration_record": calibration,
        "policy_context_ref": "policy-context://layer3/gy/n8",
        "method_state": panel,
        "method_fqn": "causal.inference.synthetic_control@1.0.0",
        "selection_diagram": selection_diagram,
        "query_treatment": "X",
        "query_outcome": "Y",
    }


def _authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["forecast_support_tiering", "observable_subset_calibration"],
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
        ],
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": ["policyos.layer2.s10.outcome_prediction.v1"],
    }


def run_rederive_audit(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Run the live Foundry/S10/transport solve lane and return issues."""

    _ensure_src_path(repo_root)
    started = time.monotonic()
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort

    observation = _quiet_call(
        lambda: FoundryValuePort()(
            candidate=_AuditCandidate(
                "candidate_live_value",
                _AuditAtom("candidate_live_value", _hash("8")),
                ("grant", "firms", "panel", "audit"),
            ),
            simulation=_audit_simulation(),
            problem=_audit_problem(),
            cycle_index=0,
        )
    )
    issues: list[dict[str, Any]] = []
    if observation.status != "value_ready":
        issues.append(
            {
                "code": "live_rederive_value_blocked",
                "blockers": list(observation.authority_blockers),
                "reason": observation.reason,
            }
        )
    elif observation.value_receipt is None:
        issues.append({"code": "live_rederive_missing_value_receipt"})
    else:
        receipt = observation.value_receipt
        if receipt.world_model_record_content_hash != _hash("1"):
            issues.append({"code": "live_rederive_world_hash_mismatch"})
        if not receipt.value_outer_set.width and observation.identification_status != "point":
            issues.append({"code": "live_rederive_missing_derived_width"})
    print(
        json.dumps(
            {
                "status": "pass" if not issues else "fail",
                "wall_time_ms": round((time.monotonic() - started) * 1000.0, 3),
                "selected_method_fqn": observation.selected_method_fqn,
                "value_status": observation.status,
                "identification_status": observation.identification_status,
                "world_model_record_content_hash": observation.world_model_record_content_hash,
                "authority_blockers": list(observation.authority_blockers),
            },
            sort_keys=True,
        )
    )
    return tuple(issues)


def _content_hash(payload: Mapping[str, Any]) -> str:
    filtered = {
        key: value
        for key, value in payload.items()
        if key not in CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    encoded = json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import hashlib

    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "schema_version_mismatch"})
    denominators = payload.get("denominators")
    if not isinstance(denominators, Mapping):
        issues.append({"code": "denominators_missing"})
    else:
        modes = tuple(denominators.get("evaluation_modes") or ())
        if modes != tuple(get_args(ValueEvaluationMode)):
            issues.append({"code": "evaluation_mode_denominator_not_full"})
        statuses = tuple(denominators.get("identification_statuses") or ())
        if statuses != ("point", "partial", "proxy"):
            issues.append({"code": "identification_status_denominator_not_full"})
        if int(denominators.get("reachable_value_methods_count") or 0) < 2:
            issues.append({"code": "reachable_value_method_denominator_too_small"})
    mutation_by_id = {
        row.get("mutation_id"): row for row in payload.get("decisive_mutations") or ()
    }
    for mutation_id in EXPECTED_MUTATION_IDS:
        row = mutation_by_id.get(mutation_id)
        if row is None:
            issues.append({"code": "decisive_mutation_missing", "mutation_id": mutation_id})
        elif row.get("result") != "RED":
            issues.append({"code": "decisive_mutation_not_red", "mutation_id": mutation_id})
    for receipt_payload in payload.get("frozen_value_receipts") or ():
        candidate = dict(receipt_payload)
        candidate.pop("value_outer_set_width_derived", None)
        if isinstance(candidate.get("value_outer_set"), Mapping):
            candidate["value_outer_set"] = {
                key: value
                for key, value in candidate["value_outer_set"].items()
                if key != "width"
            }
        try:
            receipt = ValueGateReceipt.model_validate(candidate)
        except (ValidationError, ValueError) as exc:
            issues.append(
                {
                    "code": "frozen_value_receipt_invalid",
                    "candidate_id": receipt_payload.get("candidate_id"),
                    "error": str(exc),
                }
            )
            continue
        if list(receipt.value_outer_set.width) != list(
            receipt_payload.get("value_outer_set_width_derived") or ()
        ):
            issues.append(
                {
                    "code": "frozen_value_width_not_derived",
                    "candidate_id": receipt.candidate_id,
                }
            )
    expected_hash = _content_hash(payload)
    if payload.get("contract_content_hash") != expected_hash:
        issues.append({"code": "contract_content_hash_mismatch"})
    return tuple(issues)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check(repo_root: Path) -> tuple[dict[str, Any], ...]:
    path = repo_root / OUTPUT_PATH
    if not path.exists():
        return ({"code": "artifact_missing", "path": OUTPUT_PATH},)
    expected = build_payload(repo_root)
    actual = _load_json(path)
    issues = list(validate_payload(actual))
    if actual != expected:
        issues.append({"code": "artifact_drift", "path": OUTPUT_PATH})
    return tuple(issues)


def corrupt_field_drift_check(repo_root: Path) -> int:
    payload = build_payload(repo_root)
    payload["frozen_value_receipts"][0]["world_model_record_content_hash"] = _hash("9")
    payload["contract_content_hash"] = _content_hash(payload)
    issues = validate_payload(payload)
    if issues:
        print(
            "corrupt-field drift check: PASS corruption rejected "
            + json.dumps(list(issues), sort_keys=True)
        )
        return 1
    print("corrupt-field drift check: FAIL corruption was accepted")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--rederive-audit", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    repo_root = _repo_root()
    _ensure_src_path(repo_root)
    if args.corrupt_field_drift_check:
        return corrupt_field_drift_check(repo_root)
    if args.rederive_audit:
        issues = run_rederive_audit(repo_root)
        if issues:
            print(json.dumps({"issues": list(issues)}, sort_keys=True))
            return 1
        return 0
    if args.write:
        payload = build_payload(repo_root)
        _write_json(repo_root / OUTPUT_PATH, payload)
        if args.output_format == "json":
            print(json.dumps({"status": "written", "path": OUTPUT_PATH}, sort_keys=True))
        else:
            print(f"wrote {OUTPUT_PATH}")
        return 0
    issues = check(repo_root)
    if issues:
        print(json.dumps({"status": "fail", "issues": list(issues)}, sort_keys=True))
        return 1
    print(json.dumps({"status": "pass", "path": OUTPUT_PATH}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
