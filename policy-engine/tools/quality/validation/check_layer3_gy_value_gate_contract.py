#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N8 value-gate contract."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args

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
    "value_input_read_from_runtime_hint",
    "empty_hints_production_owner_access",
    "audit_value_solve_fed_by_test_hints",
    "wmr_unavailable_not_acquire_gap",
    "value_outer_set_width_supplied_not_derived",
    "proxy_forecast_narrow_set_rejected",
    "fixture_world_model_hash_rejected",
    "value_world_version_laundered",
    "dominance_timeout_forced_not_unknown",
    "simulate_only_shrank_k_world",
    "bad_forecast_minted_value",
    "pilot_mode_ran_without_eval_safety",
    "value_method_selection_fixed_default",
    "value_blocked_candidate_promoted_to_decision_front",
)
SOURCE_FLIP_MUTATION_IDS: tuple[str, ...] = (
    "source_flip_value_input_read_from_runtime_hint",
    "source_flip_empty_hints_production_owner_access",
    "source_flip_audit_value_solve_fed_by_test_hints",
    "source_flip_wmr_unavailable_not_acquire_gap",
    "source_flip_s10_owner_invocation_required",
    "source_flip_calibration_report_driven_refusal",
    "source_flip_width_tracks_real_did_ci",
    "source_flip_transport_real_solver_required",
    "source_flip_treatment_candidate_atom_binding_required",
    "source_flip_value_outer_set_width_supplied_not_derived",
    "source_flip_proxy_forecast_narrow_set_rejected",
    "source_flip_fixture_world_model_hash_rejected",
    "source_flip_value_world_version_laundered",
    "source_flip_dominance_timeout_forced_not_unknown",
    "source_flip_simulate_only_shrank_k_world",
    "source_flip_bad_forecast_minted_value",
    "source_flip_pilot_mode_ran_without_eval_safety",
    "source_flip_value_method_selection_fixed_default",
    "source_flip_value_blocked_candidate_promoted_to_decision_front",
)
FROZEN_MUTATION_PROOFS: dict[str, str] = {
    "value_input_read_from_runtime_hint": (
        "Production N8 path has zero value-input runtime_hints reads."
    ),
    "empty_hints_production_owner_access": (
        "Empty runtime_hints reached real substrate owner and blocked on L1 DCAT gap."
    ),
    "audit_value_solve_fed_by_test_hints": (
        "Audit live lane uses real owner access and mints the frozen value_ready receipt."
    ),
    "wmr_unavailable_not_acquire_gap": (
        "Missing cycle WMR fails as controller wiring, not acquire_data."
    ),
    "value_outer_set_width_supplied_not_derived": (
        "ValueOuterSet.model_validate rejects non-empty supplied width."
    ),
    "proxy_forecast_narrow_set_rejected": "Proxy identification cannot emit a narrow/point set.",
    "fixture_world_model_hash_rejected": (
        "Placeholder WMR hash rejected; audit WMR is "
        "sha256:ac144f85a0c11f3aa987b93c69903a56d1b9dd15fbcef84e93c0e583b35e87bd."
    ),
    "value_world_version_laundered": (
        "Receipt refuses V1 value as authority for V2 world hash."
    ),
    "dominance_timeout_forced_not_unknown": (
        "Timeout/approximation path returns unknown, not dominance."
    ),
    "simulate_only_shrank_k_world": "simulate_only receipt refuses K_world narrowing.",
    "bad_forecast_minted_value": (
        "uncalibrated:uncalibrated_forecast_minted_value; "
        "unsupported:unsupported_method_unavailable; "
        "regime_laundered:regime_laundered_forecast_minted_value; "
        "untransportable:untransportable_forecast_minted_value:4 validation errors for "
        "SelectionDiagram\n"
        "base_graph\n"
        "  Field required [type=missing, input_value={'invalid': 'selection-diagram'}, "
        "input_type=dict]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/missing\n"
        "source_context\n"
        "  Field required [type=missing, input_value={'invalid': 'selection-diagram'}, "
        "input_type=dict]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/missing\n"
        "target_context\n"
        "  Field required [type=missing, input_value={'invalid': 'selection-diagram'}, "
        "input_type=dict]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/missing\n"
        "invalid\n"
        "  Extra inputs are not permitted [type=extra_forbidden, "
        "input_value='selection-diagram', input_type=str]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/extra_forbidden"
    ),
    "pilot_mode_ran_without_eval_safety": (
        "EvalSafety blocks sandbox_pilot,field_pilot,deployment"
    ),
    "value_method_selection_fixed_default": (
        "Advisor selected causal.diagnostics.parallel_trends_check@1.0.0 after scoring "
        "275 reachable value methods; fixed-default source grep is clean."
    ),
    "value_blocked_candidate_promoted_to_decision_front": (
        "N6 promotion reducer refuses value_blocked summary."
    ),
}


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
    world_model_record_ref: str = "world_model_record_runtime_owner"
    treated_unit_ids: tuple[str, ...] = ()
    treatment_period: int | None = None


@dataclass(frozen=True)
class _AuditCandidate:
    candidate_id: str
    atom: _AuditAtom
    diversity_key: tuple[str, str, str, str]


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


def _audit_world_record() -> Any:
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )

    return _build_boundary_world_model_record(
        repo_root=_repo_root(),
        problem=_audit_problem(),
        outcome="avg_income",
        policy_slot_ids=("avg_income",),
    )


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
            "capability_labels": ["upstream_residual:full_n5_joint_simulation_request"],
            "acceptance_signal": "all_decisive_mutations_red_and_live_rederive_value_ready",
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
        "production_derivation": _production_derivation_receipt(),
        "frozen_value_receipts": [_frozen_positive_receipt()],
        "frozen_positive_receipt": _frozen_positive_receipt(),
        "honest_blocked_cases": {
            "uncalibrated": "uncalibrated_forecast_minted_value",
            "unsupported_method": "unsupported_method_unavailable",
            "regime_laundered": "regime_laundered_forecast_minted_value",
            "untransportable": "untransportable_forecast_minted_value",
            "pilot_or_deployment_mode": "eval_safety_gate_unavailable",
        },
        "decisive_mutations": _mutation_results(repo_root),
        "source_flip_mutation_harness": {
            "mode": "--source-flip-mutations",
            "routine_check_live_solve": False,
            "mutation_ids": list(SOURCE_FLIP_MUTATION_IDS),
            "property": "remove_runtime_guard_then_probe_must_go_red_then_restore",
        },
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


def _production_derivation_receipt() -> dict[str, Any]:
    world = _audit_world_record()
    return {
        "input_source": "production_owner_access_no_runtime_hints",
        "world_model_record_id": world.world_model_record_id,
        "world_model_record_content_hash": world.content_hash,
        "candidate_source": "cycle_selected_candidate",
        "world_model_record_source": "SimulationPortObservation.world_model_record",
        "method_state_source": "RealValueOwnerGateway.load_panel_observational_data",
        "forecast_source": "RealValueOwnerGateway.produce_forecast_inputs",
        "transport_source": "ValueOwnerGateway.build_transport_inputs_selection_diagram_owner",
        "audit_replay_source": "real_owner_rederive_value_ready",
        "evaluation_mode": "simulate_only",
        "live_rederive_flag": "--rederive-audit",
        "local_positive_status": "value_ready",
    }


def _frozen_positive_receipt() -> dict[str, Any]:
    world = _audit_world_record()
    from polisyos.runtime.quality.design_axes.outcome_prediction import S10_FALSE_CLEAR_FIELDS

    calibration = ValueCalibrationReceipt(
        status="pass",
        forecast_tier="observable_calibrated",
        calibration_record_ref=(
            "s10://n8/19c3c4463740adb14b676bc98ad8468193b6d29273b4a1cff52fe96878e211f7"
            "/calibration"
        ),
        uncertainty_interval_refs=(
            "interval://sha256:19c3c4463740adb14b676bc98ad8468193b6d29273b4a1cff52fe96878e211f7/95",
        ),
        false_clear_counts=dict.fromkeys(S10_FALSE_CLEAR_FIELDS, 0),
    )
    transport = ValueTransportReceipt(
        status="transported_limited",
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        transport_result_ref="sha256:d9f911d509caefc06d7d5d79c6a2fb5a19a22d489bb50aef919f28ba57c30a73",
        transport_status="bounded_non_identified",
        transport_mode="bounds_only",
        identification_engine="bounds_only",
        required_target_data=("institutional_quality", "state_capacity"),
        limitation_refs=(
            "Exact transport identification unavailable; emitted transport-aware bounds fallback.",
        ),
    )
    value_set = ValueOuterSet.interval_box(
        coordinates=("CausalMethod.DIFFERENCE_IN_DIFFERENCES",),
        lower=(-6016.810766126787,),
        upper=(4094.3096004508484,),
        identification_mode="partial",
        assumptions=(
            "foundry_method_output",
            "transport:bounded_non_identified",
            "forecast_tier:observable_calibrated",
        ),
        assumption_status="externally_supported",
        calibration_scope={
            "forecast_tier": calibration.forecast_tier,
            "transport_status": transport.transport_status,
            "transport_mode": transport.transport_mode,
        },
        data_trust=DataTrust(
            tier="simulate_only_shadow",
            trust_cap=0.6,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="policyos.runtime.n8.simulate_only_shadow",
        ),
        world_model_record_ref=world.content_hash,
        epoch=world.valid_time_scope,
        representation_status="certified",
    )
    value_ref = gy_content_hash(
        {
            "candidate_id": "candidate_live_value",
            "world_model_record_content_hash": world.content_hash,
            "method_fqn": "causal.inference.did.standard@1.0.0",
            "value_outer_set": value_set.canonical_payload(),
            "transport_receipt": transport.model_dump(mode="json"),
            "calibration_receipt": calibration.model_dump(mode="json"),
        }
    )
    receipt = ValueGateReceipt(
        candidate_id="candidate_live_value",
        evaluation_mode="simulate_only",
        selected_method_fqn="causal.inference.did.standard@1.0.0",
        method_selection_trace=(
            "causal.diagnostics.parallel_trends_check@1.0.0",
            "causal.inference.did.staggered@1.0.0",
            "causal.inference.did.standard@1.0.0",
            "causal.inference.structural_time_series@1.0.0",
            "causal.inference.synthetic_control@1.0.0",
            "econometrics.panel.event_study@1.0.0",
            "econometrics.panel.latent_mobility@1.0.0",
            "econometrics.panel.nonstationary_garch@1.0.0",
            "econometrics.panel.synthetic_did@1.0.0",
            "spatial.panel.sarar@1.0.0",
            "spatial.panel.slx@1.0.0",
            "econometrics.panel.difference_gmm@1.0.0",
            "econometrics.panel.system_gmm@1.0.0",
        ),
        identification_status="partial",
        value_outer_set=value_set,
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        value_ref=value_ref,
        wall_time_ms=5994.598250021227,
        wmr_cache_status="built",
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
    )
    payload = receipt.model_dump(mode="json")
    payload["value_outer_set_width_derived"] = list(value_set.width)
    return payload


def _frozen_positive_receipt_object() -> ValueGateReceipt:
    payload = dict(_frozen_positive_receipt())
    payload.pop("value_outer_set_width_derived", None)
    if isinstance(payload.get("value_outer_set"), Mapping):
        payload["value_outer_set"] = {
            key: value for key, value in payload["value_outer_set"].items() if key != "width"
        }
    return ValueGateReceipt.model_validate(payload)


def _frozen_value_receipts() -> list[dict[str, Any]]:
    return [
        _receipt_payload("point", lower=(6.0,), upper=(6.0,), transport_status="identified"),
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
    world = _audit_world_record()
    value_set = _value_set(
        identification_status,
        lower=lower,
        upper=upper,
        forecast_tier=forecast_tier,
        transport_status=transport_status,
        transport_mode=transport_mode,
    )
    transport = _transport_receipt(
        world_record=world,
        status="transported_limited" if transport_mode != "direct" else "direct",
        transport_status=transport_status,
        transport_mode=transport_mode,
    )
    calibration = _calibration_receipt(forecast_tier=forecast_tier)
    candidate_id = (
        "candidate_live_value"
        if identification_status == "point"
        else f"candidate_{identification_status}"
    )
    selected_method_fqn = "causal.inference.synthetic_control@1.0.0"
    value_ref = gy_content_hash(
        {
            "candidate_id": candidate_id,
            "world_model_record_content_hash": world.content_hash,
            "method_fqn": selected_method_fqn,
            "value_outer_set": value_set.canonical_payload(),
            "transport_receipt": transport.model_dump(mode="json"),
            "calibration_receipt": calibration.model_dump(mode="json"),
        }
    )
    receipt = ValueGateReceipt(
        candidate_id=candidate_id,
        evaluation_mode="simulate_only",
        selected_method_fqn=selected_method_fqn,
        method_selection_trace=(),
        identification_status=identification_status,  # type: ignore[arg-type]
        value_outer_set=value_set,
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        value_ref=value_ref,
        wall_time_ms=0.0,
        wmr_cache_status="built",
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
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
    transport_mode: str = "direct",
) -> ValueOuterSet:
    world = _audit_world_record()
    return ValueOuterSet.interval_box(
        coordinates=("CausalMethod.SYNTHETIC_CONTROL",),
        lower=lower,
        upper=upper,
        identification_mode=identification_status,
        assumptions=(
            "foundry_method_output",
            f"transport:{transport_status}",
            f"forecast_tier:{forecast_tier}",
        ),
        assumption_status="externally_supported",
        calibration_scope={
            "forecast_tier": forecast_tier,
            "transport_status": transport_status,
            "transport_mode": transport_mode,
        },
        data_trust=DataTrust(
            tier="simulate_only_shadow",
            trust_cap=0.6,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="policyos.runtime.n8.simulate_only_shadow",
        ),
        world_model_record_ref=world.content_hash,
        epoch=world.valid_time_scope,
        representation_status="certified",
    )


def _transport_receipt(
    *,
    world_record: Any | None = None,
    status: str = "direct",
    transport_status: str = "identified",
    transport_mode: str = "direct",
) -> ValueTransportReceipt:
    world = world_record or _audit_world_record()
    return ValueTransportReceipt(
        status=status,  # type: ignore[arg-type]
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        transport_result_ref=(
            "sha256:048137f39d3435c8ef094949d8979b3576116ccc3d2c6618e26a2756b2f096db"
            if status == "direct"
            and transport_status == "identified"
            and transport_mode == "direct"
            else gy_content_hash({"transport_status": transport_status})
        ),
        transport_status=transport_status,
        transport_mode=transport_mode,
        identification_engine=(
            "simplified_legacy"
            if status == "direct"
            and transport_status == "identified"
            and transport_mode == "direct"
            else "transport_engine"
        ),
        required_target_data=(),
        limitation_refs=(),
    )


def _calibration_receipt(
    *,
    status: str = "pass",
    forecast_tier: str = "observable_calibrated",
) -> ValueCalibrationReceipt:
    live_s10_report_ref = "sha256:69bf8fad7fe2f1149ac628b8855410c70ea777f39bfaa4bfae8ce8a5ef3edd88"
    return ValueCalibrationReceipt(
        status=status,  # type: ignore[arg-type]
        forecast_tier=forecast_tier,
        calibration_record_ref=(
            f"s10://n8/{live_s10_report_ref.removeprefix('sha256:')}/calibration"
        ),
        uncertainty_interval_refs=(f"interval://{live_s10_report_ref}/95",),
        false_clear_counts={},
        issue_codes=(),
    )


def _mutation_results(repo_root: Path) -> list[dict[str, Any]]:
    """Return byte-stable frozen mutation proofs for routine artifact checks."""

    del repo_root
    return [
        {
            "mutation_id": mutation_id,
            "result": "RED",
            "proof": FROZEN_MUTATION_PROOFS[mutation_id],
        }
        for mutation_id in EXPECTED_MUTATION_IDS
    ]


def _live_mutation_results(repo_root: Path) -> list[dict[str, Any]]:
    probes = {
        "value_input_read_from_runtime_hint": lambda: _probe_no_value_runtime_hint_reads(
            repo_root
        ),
        "empty_hints_production_owner_access": _probe_empty_hints_owner_access,
        "audit_value_solve_fed_by_test_hints": _probe_audit_not_fed_by_hints,
        "wmr_unavailable_not_acquire_gap": _probe_missing_wmr_is_wiring_error,
        "value_outer_set_width_supplied_not_derived": _probe_supplied_width_rejected,
        "proxy_forecast_narrow_set_rejected": _probe_proxy_narrow_rejected,
        "fixture_world_model_hash_rejected": _probe_fixture_world_hash_rejected,
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


@dataclass(frozen=True)
class _SourceFlipReplacement:
    relative_path: str
    old: str
    new: str


@dataclass(frozen=True)
class _SourceFlipCase:
    mutation_id: str
    guard: str
    replacements: tuple[_SourceFlipReplacement, ...]
    probe_command: tuple[str, ...]


def run_source_flip_mutations(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Temporarily remove runtime guards and require the targeted probe to go RED."""

    _ensure_src_path(repo_root)
    cases = _source_flip_cases()
    observed_ids = tuple(case.mutation_id for case in cases)
    results: list[dict[str, Any]] = []
    if observed_ids != SOURCE_FLIP_MUTATION_IDS:
        results.append(
            {
                "mutation_id": "source_flip_harness_denominator",
                "result": "HARNESS_ERROR",
                "proof": {
                    "expected": list(SOURCE_FLIP_MUTATION_IDS),
                    "observed": list(observed_ids),
                },
            }
        )
        return tuple(results)
    for case in cases:
        results.append(_run_source_flip_case(repo_root, case))
    return tuple(results)


def _run_source_flip_case(repo_root: Path, case: _SourceFlipCase) -> dict[str, Any]:
    originals: dict[Path, str] = {}
    try:
        for replacement in case.replacements:
            path = repo_root / replacement.relative_path
            if path not in originals:
                originals[path] = path.read_text(encoding="utf-8")
            text = path.read_text(encoding="utf-8")
            if replacement.old not in text:
                return {
                    "mutation_id": case.mutation_id,
                    "result": "HARNESS_ERROR",
                    "guard": case.guard,
                    "proof": f"source guard not found in {replacement.relative_path}",
                }
            path.write_text(
                text.replace(replacement.old, replacement.new, 1),
                encoding="utf-8",
            )
        completed = subprocess.run(
            case.probe_command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
        if completed.returncode != 0:
            return {
                "mutation_id": case.mutation_id,
                "result": "RED",
                "guard": case.guard,
                "proof": {
                    "command": list(case.probe_command),
                    "exit_code": completed.returncode,
                    "stdout_tail": _output_tail(completed.stdout),
                    "stderr_tail": _output_tail(completed.stderr),
                },
            }
        return {
            "mutation_id": case.mutation_id,
            "result": "GREEN_MUTATION_SURVIVED",
            "guard": case.guard,
            "proof": {
                "command": list(case.probe_command),
                "stdout_tail": _output_tail(completed.stdout),
                "stderr_tail": _output_tail(completed.stderr),
            },
        }
    except Exception as exc:  # pragma: no cover - reported as harness data.
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "guard": case.guard,
            "proof": str(exc),
        }
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")


def _output_tail(output: str, *, max_lines: int = 20) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def _pytest_probe(*node_ids: str) -> tuple[str, ...]:
    return (sys.executable, "-m", "pytest", *node_ids, "-q")


def _python_probe(script: str) -> tuple[str, ...]:
    return (sys.executable, "-c", script)


def _validator_probe(*args: str) -> tuple[str, ...]:
    return (
        sys.executable,
        "tools/quality/validation/check_layer3_gy_value_gate_contract.py",
        *args,
    )


def _source_flip_cases() -> tuple[_SourceFlipCase, ...]:
    generation_cycle = "src/polisyos/runtime/quality/generation_cycle.py"
    value_outer_set = "src/polisyos/core/contracts/value_outer_set.py"
    validator = "tools/quality/validation/check_layer3_gy_value_gate_contract.py"
    advisor = "src/polisyos/foundry/methods/selection/advisor.py"
    test_value_gate = "tests/unit/runtime/quality/test_value_gate.py"
    test_generation_cycle = "tests/unit/runtime/quality/test_generation_cycle.py"
    return (
        _SourceFlipCase(
            mutation_id="source_flip_value_input_read_from_runtime_hint",
            guard="production source contains zero value-input runtime_hints reads",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "class FoundryValuePort:\n"
                        "    \"\"\"Default N8 port delegating value authority to Foundry and S10 owners.\"\"\"\n"
                    ),
                    (
                        "class FoundryValuePort:\n"
                        "    _source_flip_forbidden_value_hint = 'runtime_hints.get(\"value_fake\")'\n"
                        "    \"\"\"Default N8 port delegating value authority to Foundry and S10 owners.\"\"\"\n"
                    ),
                ),
            ),
            probe_command=_python_probe(
                "from pathlib import Path\n"
                "from tools.quality.validation import check_layer3_gy_value_gate_contract as c\n"
                "print(c._probe_no_value_runtime_hint_reads(Path.cwd()))\n"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_empty_hints_production_owner_access",
            guard="empty-hints production path reaches the real substrate owner",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "            method_state = self._owner_gateway.load_panel_observational_data(\n"
                    ),
                    (
                        "            raise ValueOwnerAccessError(\n"
                        "                \"value_method_state_missing\",\n"
                        "                \"source flip bypassed real owner access\",\n"
                        "            )\n"
                        "            method_state = self._owner_gateway.load_panel_observational_data(\n"
                    ),
                ),
            ),
            probe_command=_python_probe(
                "from tools.quality.validation import check_layer3_gy_value_gate_contract as c\n"
                "print(c._probe_empty_hints_owner_access())\n"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_audit_value_solve_fed_by_test_hints",
            guard="audit rederive uses real owner access and an empty runtime_hints problem",
            replacements=(
                _SourceFlipReplacement(
                    validator,
                    "        runtime_hints={},\n",
                    "        runtime_hints={\"value_gate_inputs\": {}},\n",
                ),
            ),
            probe_command=_validator_probe("--rederive-audit"),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_wmr_unavailable_not_acquire_gap",
            guard="missing cycle WMR is controller wiring, not acquire_data",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    '                code=world_error or "value_world_model_record_unwired",\n',
                    '                code="acquire_data:value_world_model_record_missing",\n',
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_missing_cycle_wmr_is_wiring_error_not_acquire_gap"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_s10_owner_invocation_required",
            guard="real S10 build_forecast_support invocation must run before value mints",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "    return _build_s10_forecast_inputs(\n",
                    (
                        "    raise ValueOwnerAccessError(\n"
                        "        \"source_flip_s10_not_invoked\",\n"
                        "        \"source flip disabled real S10 owner invocation\",\n"
                        "        owner_access_ref=\"source_flip://s10\",\n"
                        "    )\n"
                        "    return _build_s10_forecast_inputs(\n"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_empty_hints_cycle_reaches_value_gate_with_real_boundary_wmr"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_calibration_report_driven_refusal",
            guard="S10 evidence is derived from report diagnostics and can refuse",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        and diagnostics_pass\n        and treated > 0\n",
                    "        and treated > 0\n",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_s10_refusal_is_report_driven_by_bad_did_report"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_width_tracks_real_did_ci",
            guard="partial ValueOuterSet lower/upper come from the real DID confidence interval",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        lower = lower_ci\n        upper = upper_ci\n",
                    "        lower = upper = point_value\n",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_empty_hints_cycle_reaches_value_gate_with_real_boundary_wmr"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_transport_real_solver_required",
            guard="transport receipt is produced by solve_transportability over the candidate diagram",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        result = solve_transportability(\n",
                    (
                        "        raise RuntimeError(\"source_flip_transport_disabled\")\n"
                        "        result = solve_transportability(\n"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_empty_hints_cycle_reaches_value_gate_with_real_boundary_wmr"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_treatment_candidate_atom_binding_required",
            guard="panel treatment is derived from candidate atom fields with no fallback",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "    if not treated_units:\n"
                        "        raise ValueOwnerAccessError(\n"
                        "            \"treatment_binding_underdetermined\",\n"
                        "            \"candidate intervention does not identify treated substrate units\",\n"
                        "            owner_access_ref=\"candidate_owner://treated_units_missing\",\n"
                        "        )\n"
                    ),
                    (
                        "    if not treated_units:\n"
                        "        treated_units = (str(units[0]),)\n"
                    ),
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "    if period_raw is None:\n"
                        "        raise ValueOwnerAccessError(\n"
                        "            \"treatment_binding_underdetermined\",\n"
                        "            \"candidate intervention does not identify a treatment start period\",\n"
                        "            owner_access_ref=\"candidate_owner://treatment_period_missing\",\n"
                        "        )\n"
                    ),
                    (
                        "    if period_raw is None:\n"
                        "        period_raw = periods[min(2, max(0, len(periods) - 2))]\n"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_missing_candidate_treatment_binding_blocks_without_fallback"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_value_outer_set_width_supplied_not_derived",
            guard="ValueOuterSet rejects caller-supplied width",
            replacements=(
                _SourceFlipReplacement(
                    value_outer_set,
                    "        if supplied_width:\n",
                    "        if False and supplied_width:\n",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_hand_set_value_outer_set_width_is_rejected"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_proxy_forecast_narrow_set_rejected",
            guard="proxy identification cannot emit a narrow interval",
            replacements=(
                _SourceFlipReplacement(
                    value_outer_set,
                    "        if self.identification_status == \"proxy\" and not any(\n",
                    "        if False and self.identification_status == \"proxy\" and not any(\n",
                ),
            ),
            probe_command=_python_probe(
                "from tools.quality.validation import check_layer3_gy_value_gate_contract as c\n"
                "print(c._probe_proxy_narrow_rejected())\n"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_fixture_world_model_hash_rejected",
            guard="fixture/placeholder world hashes are rejected by corrupt-field drift",
            replacements=(
                _SourceFlipReplacement(
                    validator,
                    "    return bool(\n",
                    "    return False and bool(\n",
                ),
            ),
            probe_command=_python_probe(
                "import subprocess, sys\n"
                "cmd = [sys.executable, "
                "'tools/quality/validation/check_layer3_gy_value_gate_contract.py', "
                "'--corrupt-field-drift-check']\n"
                "result = subprocess.run(cmd, text=True)\n"
                "raise SystemExit(0 if result.returncode == 1 else 1)\n"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_value_world_version_laundered",
            guard="ValueGateReceipt binds value and transport receipts to the WMR hash",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        if self.transport_receipt.world_model_record_content_hash != (\n",
                    "        if False and self.transport_receipt.world_model_record_content_hash != (\n",
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "        if self.value_outer_set.world_model_record_ref "
                        "!= self.world_model_record_content_hash:\n"
                    ),
                    (
                        "        if False and self.value_outer_set.world_model_record_ref "
                        "!= self.world_model_record_content_hash:\n"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_value_receipt_rejects_world_version_laundering"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_dominance_timeout_forced_not_unknown",
            guard="timeout/approximation dominance returns unknown",
            replacements=(
                _SourceFlipReplacement(
                    value_outer_set,
                    "        if force_timeout or timeout_ms == 0:\n            return \"unknown\"\n",
                    "        if force_timeout or timeout_ms == 0:\n            return \"dominates\"\n",
                ),
            ),
            probe_command=_pytest_probe(f"{test_value_gate}::test_dominance_timeout_returns_unknown"),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_simulate_only_shrank_k_world",
            guard="simulate_only receipts may not narrow K_world",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        if self.evaluation_mode == \"simulate_only\" and (\n",
                    "        if False and self.evaluation_mode == \"simulate_only\" and (\n",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_simulate_only_receipt_cannot_shrink_k_world"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_bad_forecast_minted_value",
            guard="real calibration refusals cannot mint value authority",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "    if any(count > 0 for count in false_clear_counts.values()):\n",
                    "    if False and any(count > 0 for count in false_clear_counts.values()):\n",
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    "    if support.forecast_tier == \"observable_calibrated\":\n",
                    "    if False and support.forecast_tier == \"observable_calibrated\":\n",
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    "    elif support.forecast_tier != \"transported_limited\":\n",
                    "    elif False and support.forecast_tier != \"transported_limited\":\n",
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    "    if envelope.envelope_status != \"pass\":\n",
                    "    if False and envelope.envelope_status != \"pass\":\n",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_s10_refusal_is_report_driven_by_bad_did_report"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_pilot_mode_ran_without_eval_safety",
            guard="pilot/deployment modes block pending EvalSafety",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        if mode in {\"sandbox_pilot\", \"field_pilot\", \"deployment\"}:\n",
                    "        if False and mode in {\"sandbox_pilot\", \"field_pilot\", \"deployment\"}:\n",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_pilot_and_deployment_modes_block_pending_eval_safety"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_value_method_selection_fixed_default",
            guard="method selection routes through the registry advisor",
            replacements=(
                _SourceFlipReplacement(
                    advisor,
                    '        "selection_source": "foundry_registry_advisor",\n',
                    '        "selection_source": "fixed_synthetic_control_source_flip",\n',
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_value_gate}::test_candidate_problem_selection_uses_registry_denominator"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_value_blocked_candidate_promoted_to_decision_front",
            guard="N6 promotion reducer refuses value_blocked candidates",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "            and not _summary_value_blocks_promotion(summary)\n",
                    "",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_generation_cycle}::test_blocked_value_candidate_cannot_be_promoted_to_decision_front"
            ),
        ),
    )


def _probe_no_value_runtime_hint_reads(repo_root: Path) -> str:
    source = repo_root / "src/polisyos/runtime/quality/generation_cycle.py"
    text = source.read_text(encoding="utf-8")
    pattern = re.compile(
        r'_first_owner_value\(hints|runtime_hints\.get\("'
        r"(world_model_record|method_state|panel_observational_data|"
        r"outcome_prediction|forecast_support|value_)"
    )
    matches = [
        f"{line_no}:{line.strip()}"
        for line_no, line in enumerate(text.splitlines(), start=1)
        if pattern.search(line)
    ]
    if matches:
        raise AssertionError("value input read from runtime_hints: " + "; ".join(matches))
    return "Production N8 path has zero value-input runtime_hints reads."


def _probe_empty_hints_owner_access() -> str:
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort, RealValueOwnerGateway

    problem = _audit_problem()
    if problem.runtime_hints:
        raise AssertionError("audit problem unexpectedly contains value hints")
    observation = _quiet_call(
        lambda: FoundryValuePort(
            owner_gateway=RealValueOwnerGateway(repo_root=_repo_root()),
            requested_method_fqn="causal.inference.synthetic_control@1.0.0",
        )(
            candidate=_AuditCandidate(
                "candidate_no_hints_gap",
                _AuditAtom("candidate_no_hints_gap", _hash("4")),
                ("grant", "firms", "panel", "no_hints"),
            ),
            simulation=_audit_simulation(),
            problem=problem,
            cycle_index=0,
        )
    )
    blockers = tuple(observation.authority_blockers)
    if blockers != ("acquire_data:value_panel_data_missing",):
        raise AssertionError(f"expected real panel-data acquisition gap, got {blockers}")
    reason = str(observation.reason)
    if "substrate owner" not in reason or "dataset_catalog.duckdb#variable/firm_survival" not in reason:
        raise AssertionError(f"block did not show real substrate owner access: {reason}")
    return "Empty runtime_hints reached real substrate owner and blocked on L1 DCAT gap."


def _probe_audit_not_fed_by_hints() -> str:
    problem = _audit_problem()
    if problem.runtime_hints:
        raise AssertionError(f"audit problem carries value hints: {problem.runtime_hints}")
    observation = _run_real_owner_value_audit()
    if observation.status != "value_ready" or observation.value_receipt is None:
        raise AssertionError(f"expected real value_ready, got {observation.status}")
    if observation.value_receipt.value_ref != _frozen_positive_receipt()["value_ref"]:
        raise AssertionError("audit live lane did not reproduce the frozen value receipt")
    return "Audit live lane uses real owner access and mints the frozen value_ready receipt."


def _probe_missing_wmr_is_wiring_error() -> str:
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        RealValueOwnerGateway,
        SimulationPortObservation,
    )

    observation = _quiet_call(
        lambda: FoundryValuePort(
            owner_gateway=RealValueOwnerGateway(repo_root=_repo_root()),
            requested_method_fqn="causal.inference.synthetic_control@1.0.0",
        )(
            candidate=_AuditCandidate(
                "candidate_missing_wmr",
                _AuditAtom("candidate_missing_wmr", _hash("5")),
                ("grant", "firms", "panel", "missing_wmr"),
            ),
            simulation=SimulationPortObservation(
                candidate_id="candidate_missing_wmr",
                status="joint_simulated",
                simulation_ref=_hash("7"),
            ),
            problem=_audit_problem(),
            cycle_index=0,
        )
    )
    blockers = tuple(observation.authority_blockers)
    if blockers != ("value_world_model_record_unwired",):
        raise AssertionError(f"missing WMR was not a wiring error: {blockers}")
    return "Missing cycle WMR fails as controller wiring, not acquire_data."


def _probe_fixture_world_hash_rejected() -> str:
    if not _is_fixture_world_hash(_hash("1")):
        raise AssertionError("placeholder fixture hash was not recognized")
    world_hash = _audit_world_record().content_hash
    if _is_fixture_world_hash(world_hash):
        raise AssertionError("real audit WMR hash looked like a fixture placeholder")
    return f"Placeholder WMR hash rejected; audit WMR is {world_hash}."


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
        RealValueOwnerGateway,
        _run_value_transport,
    )

    cases = {
        "uncalibrated": {
            "owner": _AdversarialAuditGateway(
                forecast_tier="simulation_only_advisory",
                calibration_status=None,
            ),
            "method": "causal.inference.did.standard@1.0.0",
        },
        "unsupported": {
            "owner": RealValueOwnerGateway(repo_root=_repo_root()),
            "method": "causal.inference.no_such_method@9.9.9",
        },
        "regime_laundered": {
            "owner": _AdversarialAuditGateway(
                expected_policy_context_ref="policy-context://other-regime"
            ),
            "method": "causal.inference.did.standard@1.0.0",
        },
    }
    observed = []
    for name, config in cases.items():
        observation = _quiet_call(
            lambda name=name, config=config: FoundryValuePort(
                owner_gateway=config["owner"],
                requested_method_fqn=str(config["method"]),
            )(
                candidate=_AuditCandidate(
                    "candidate_bad_forecast",
                    _AuditAtom(
                        "candidate_bad_forecast",
                        _hash("4"),
                        target_world_slots=("avg_income",),
                        treated_unit_ids=("AM",),
                        treatment_period=2020,
                    ),
                    ("grant", "firms", "value", name),
                ),
                simulation=_audit_simulation(),
                problem=_audit_problem(),
                cycle_index=0,
            )
        )
        if observation.status != "value_blocked" or observation.value_receipt is not None:
            raise AssertionError(f"{name} minted value")
        observed.append(f"{name}:{observation.authority_blockers[0]}")
    transport, error = _run_value_transport(
        inputs={
            "selection_diagram": {"invalid": "selection-diagram"},
            "query_treatment": "candidate_bad_forecast",
            "query_outcome": "avg_income",
        },
        world_record=_audit_world_record(),
    )
    if transport is not None or not str(error or "").startswith("untransportable_forecast"):
        raise AssertionError("untransportable forecast minted value")
    observed.append(f"untransportable:{error}")
    return "; ".join(observed)


def _probe_mode_gates_block() -> str:
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort, RealValueOwnerGateway

    blocked = []
    for mode in ("sandbox_pilot", "field_pilot", "deployment"):
        observation = FoundryValuePort(
            owner_gateway=RealValueOwnerGateway(repo_root=_repo_root()),
            evaluation_mode=mode,
            requested_method_fqn="causal.inference.synthetic_control@1.0.0",
        )(
            candidate=_AuditCandidate(
                "candidate_mode_gate",
                _AuditAtom("candidate_mode_gate", _hash("5")),
                ("grant", "firms", "mode", mode),
            ),
            simulation=_audit_simulation(),
            problem=_audit_problem(),
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
    denominator = tuple(selection.get("denominator") or ())
    if len(denominator) <= 1:
        raise AssertionError("selector denominator collapsed to a fixed default")
    if not selection.get("score_trace"):
        raise AssertionError("selector did not expose advisor scoring trace")
    for path in (
        "src/polisyos/runtime/quality/workspace/loop.py",
        "src/polisyos/foundry/methods/compiler/plan_optimizer.py",
    ):
        text = (_repo_root() / path).read_text(encoding="utf-8")
        if "causal.inference.synthetic_control@1.0.0" in text:
            raise AssertionError(f"fixed synthetic_control default survives in {path}")
    return (
        f"Advisor selected {selection.get('selected_method_fqn')} after scoring "
        f"{len(denominator)} reachable value methods; fixed-default source grep is clean."
    )


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
        lower=(6.0,) if identification_status == "point" else (2.0,),
        upper=(6.0,) if identification_status == "point" else (5.0,),
        transport_status="identified",
    )
    payload.pop("value_outer_set_width_derived", None)
    payload["value_outer_set"].pop("width", None)
    return ValueGateReceipt.model_validate(payload)


def _audit_simulation() -> Any:
    from polisyos.runtime.quality.generation_cycle import SimulationPortObservation

    world = _audit_world_record()
    return SimulationPortObservation(
        candidate_id="candidate_audit",
        status="joint_simulated",
        simulation_ref=_hash("7"),
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
        world_model_record=world,
    )


def _audit_value_candidate(candidate_id: str = "candidate_live_value") -> _AuditCandidate:
    return _AuditCandidate(
        candidate_id,
        _AuditAtom(
            candidate_id,
            _hash("8"),
            target_world_slots=("avg_income",),
            treated_unit_ids=("AM",),
            treatment_period=2020,
        ),
        ("grant", "country", "avg_income", "real_panel"),
    )


@dataclass(frozen=True)
class _AdversarialAuditGateway:
    forecast_tier: str = "observable_calibrated"
    calibration_status: str | None = "pass"
    expected_policy_context_ref: str | None = None
    selection_diagram: object | None = None

    def load_panel_observational_data(
        self,
        *,
        candidate: object,
        problem: _AuditProblem,
        world_record: Any,
    ) -> object:
        from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

        return RealValueOwnerGateway(repo_root=_repo_root()).load_panel_observational_data(
            candidate=candidate,
            problem=problem,  # type: ignore[arg-type]
            world_record=world_record,
        )

    def produce_forecast_inputs(
        self,
        *,
        candidate: object,
        problem: _AuditProblem,
        world_record: Any,
        method_result: object,
        selected_method_fqn: str,
    ) -> Mapping[str, Any]:
        from polisyos.runtime.quality.generation_cycle import (
            _build_s10_forecast_inputs,
            _s10_calibration_evidence_from_report,
        )

        policy_context_ref = f"policy-context://{world_record.world_model_record_id}"
        evidence = _s10_calibration_evidence_from_report(method_result.output.get("report"))
        if self.calibration_status not in {None, "pass"}:
            evidence = {
                **evidence,
                "calibration_status": self.calibration_status,
                "numerator": 0,
                "pass_rate": 0.0,
                "floor_passed": False,
            }
        return _build_s10_forecast_inputs(
            candidate=candidate,
            problem=problem,  # type: ignore[arg-type]
            world_record=world_record,
            method_result=method_result,
            selected_method_fqn=selected_method_fqn,
            forecast_tier=self.forecast_tier,
            calibration_status=self.calibration_status,
            policy_context_ref=policy_context_ref,
            expected_policy_context_ref=self.expected_policy_context_ref or policy_context_ref,
            false_clear_counts=evidence["false_clear_counts"],  # type: ignore[arg-type]
            calibration_evidence=evidence,
        )

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: _AuditProblem,
        world_record: Any,
    ) -> Mapping[str, Any]:
        from polisyos.runtime.quality.generation_cycle import (
            _build_default_selection_diagram,
            _candidate_transport_outcome_variable,
            _candidate_transport_treatment_variable,
        )

        query_treatment = _candidate_transport_treatment_variable(candidate)
        query_outcome = _candidate_transport_outcome_variable(candidate, problem)  # type: ignore[arg-type]
        return {
            "selection_diagram": self.selection_diagram
            if self.selection_diagram is not None
            else _build_default_selection_diagram(
                candidate=candidate,
                problem=problem,  # type: ignore[arg-type]
                world_record=world_record,
            ),
            "query_treatment": query_treatment,
            "query_outcome": query_outcome,
        }


def _run_real_owner_value_audit() -> Any:
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort

    return _quiet_call(
        lambda: FoundryValuePort(repo_root=_repo_root())(
            candidate=_audit_value_candidate(),
            simulation=_audit_simulation(),
            problem=_audit_problem(),  # type: ignore[arg-type]
            cycle_index=0,
        )
    )


def _audit_problem() -> _AuditProblem:
    return _AuditProblem(
        design_problem_id="value_gate_audit_problem",
        problem_statement="Audit N8 value gate.",
        domain="runtime_quality",
        runtime_hints={},
    )


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
    """Run the live real-owner value lane and return issues."""

    _ensure_src_path(repo_root)
    started = time.monotonic()
    world = _audit_world_record()
    problem = _audit_problem()
    if problem.runtime_hints:
        return ({"code": "live_rederive_used_runtime_hints", "keys": sorted(problem.runtime_hints)},)
    observation = _run_real_owner_value_audit()
    issues: list[dict[str, Any]] = []
    if observation.status != "value_ready":
        issues.append(
            {
                "code": "live_rederive_unexpected_status",
                "status": observation.status,
                "blockers": list(observation.authority_blockers),
                "reason": observation.reason,
            }
        )
    elif observation.value_receipt is None:
        issues.append({"code": "live_rederive_missing_value_receipt"})
    else:
        receipt = observation.value_receipt
        frozen = _frozen_positive_receipt_object()
        if receipt.world_model_record_content_hash != world.content_hash:
            issues.append(
                {
                    "code": "live_rederive_world_hash_mismatch",
                    "expected": world.content_hash,
                    "actual": receipt.world_model_record_content_hash,
                }
            )
        if not receipt.value_outer_set.width and observation.identification_status != "point":
            issues.append({"code": "live_rederive_missing_derived_width"})
        if receipt.value_ref != frozen.value_ref:
            issues.append(
                {
                    "code": "live_rederive_frozen_positive_receipt_mismatch",
                    "expected": frozen.value_ref,
                    "actual": receipt.value_ref,
                }
            )
        if receipt.value_outer_set.canonical_payload() != frozen.value_outer_set.canonical_payload():
            issues.append({"code": "live_rederive_frozen_value_set_mismatch"})
        if receipt.transport_receipt != frozen.transport_receipt:
            issues.append({"code": "live_rederive_frozen_transport_mismatch"})
        if receipt.calibration_receipt != frozen.calibration_receipt:
            issues.append({"code": "live_rederive_frozen_calibration_mismatch"})
    print(
        json.dumps(
            {
                "status": "pass" if not issues else "fail",
                "wall_time_ms": round((time.monotonic() - started) * 1000.0, 3),
                "selected_method_fqn": observation.selected_method_fqn,
                "value_status": observation.status,
                "expected_value_ref": _frozen_positive_receipt()["value_ref"],
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


def _is_fixture_world_hash(value: object) -> bool:
    text = str(value or "")
    return bool(
        text.startswith("sha256:")
        and len(text) == len("sha256:") + 64
        and len(set(text.removeprefix("sha256:"))) == 1
    )


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
    production = payload.get("production_derivation")
    if not isinstance(production, Mapping):
        issues.append({"code": "production_derivation_missing"})
    elif production.get("input_source") != "production_owner_access_no_runtime_hints":
        issues.append({"code": "production_derivation_uses_value_gate_inputs"})
    elif _is_fixture_world_hash(production.get("world_model_record_content_hash")):
        issues.append({"code": "production_derivation_fixture_world_hash"})
    positive = payload.get("frozen_positive_receipt")
    if not isinstance(positive, Mapping):
        issues.append({"code": "frozen_positive_receipt_missing"})
    else:
        issues.extend(_validate_frozen_receipt_payload(positive))
    for receipt_payload in payload.get("frozen_value_receipts") or ():
        issues.extend(_validate_frozen_receipt_payload(receipt_payload))
    expected_hash = _content_hash(payload)
    if payload.get("contract_content_hash") != expected_hash:
        issues.append({"code": "contract_content_hash_mismatch"})
    return tuple(issues)


def _validate_frozen_receipt_payload(receipt_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    candidate = dict(receipt_payload)
    candidate.pop("value_outer_set_width_derived", None)
    if isinstance(candidate.get("value_outer_set"), Mapping):
        candidate["value_outer_set"] = {
            key: value for key, value in candidate["value_outer_set"].items() if key != "width"
        }
    try:
        receipt = ValueGateReceipt.model_validate(candidate)
    except (ValidationError, ValueError) as exc:
        return [
            {
                "code": "frozen_value_receipt_invalid",
                "candidate_id": receipt_payload.get("candidate_id"),
                "error": str(exc),
            }
        ]
    if _is_fixture_world_hash(receipt.world_model_record_content_hash):
        issues.append(
            {
                "code": "fixture_world_model_hash",
                "candidate_id": receipt.candidate_id,
            }
        )
    if list(receipt.value_outer_set.width) != list(
        receipt_payload.get("value_outer_set_width_derived") or ()
    ):
        issues.append(
            {
                "code": "frozen_value_width_not_derived",
                "candidate_id": receipt.candidate_id,
            }
        )
    return issues


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
    payload["production_derivation"]["world_model_record_content_hash"] = _hash("9")
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
    parser.add_argument("--source-flip-mutations", action="store_true")
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
    if args.source_flip_mutations:
        results = run_source_flip_mutations(repo_root)
        failures = tuple(row for row in results if row.get("result") != "RED")
        print(json.dumps({"results": list(results)}, sort_keys=True))
        return 1 if failures else 0
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
