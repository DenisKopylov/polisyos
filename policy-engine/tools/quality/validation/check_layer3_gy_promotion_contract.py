#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N9 canonical promotion contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import copy
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.pdc import (
    GY_COMPARISON_PROJECTION_SCHEMA_VERSION,
    GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
    GY_VERIFICATION_COMPARISON_RULE_VERSION,
    PROMOTION_RISK_CONDITIONALITY_CAVEAT,
    AuthorityBoundary,
    PromotionObligationClass,
    gy_comparison_content_hash,
    gy_content_hash,
    reconcile_gy_operational_leaves,
)
from polisyos.pdc._impl.layer2_design_search import (
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.confidence_ledger import (
    CONDITIONAL_VALIDITY_CLAUSE,
    ConfidenceLedgerSession,
    n9_promotion_projection_comparison_eligible,
)
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateSummary,
    ValueCalibrationReceipt,
    ValueGateReceipt,
    ValueTransportReceipt,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingBindGate,
    GroundingDecisionCertificate,
    recompute_grounding_decision_content_hash,
)
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalPromotionInput,
    CanonicalPromotionReceipt,
    LegacyPromotionStrangleReceipt,
    N9DesignProblemBinding,
    _run_canonical_promotion_sequence_for_verification,
    _validate_canonical_promotion_receipt_for_verification,
    confidence_risk_scope_for_problem,
)
from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_promotion_contract.json"
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"capture_wall_time_seconds", "contract_content_hash"}

_COMPARISON_IDENTITY_FIELDS = {
    "comparison_content_hash",
    "comparison_projection_schema_version",
    "comparison_rule_version",
}

_SOURCE_FLIP_MUTATION_IDS: tuple[str, ...] = (
    "source_flip_no_self_promotion_guard",
    "source_flip_non_anytime_preflight_guard",
    "source_flip_real_transport_refusal",
    "source_flip_cg2_owner_call_removed",
    "source_flip_g4_owner_resolution_removed",
    "source_flip_timeout_to_favorable",
    "source_flip_lower_boundary_meet",
    "source_flip_non_promotable_bind_stamp",
    "source_flip_n6_ledger_revalidation_removed",
    "source_flip_vacuous_scope_autopass",
    "source_flip_scope_insufficient_authority_guard",
    "source_flip_invented_measurement_marker_reintroduced",
    "source_flip_unseen_shape_panel_coupling",
    "source_flip_live_champion_path",
    "source_flip_confidence_projection_recompute_guard",
    "source_flip_ledger_bypass_guard",
)
_BEHAVIORAL_MUTATION_IDS: tuple[str, ...] = (
    "ledger_projection_hand_edit",
    "gate_outcome_drift",
    "fixed_time_refusal_laundered",
    "vacuous_scope_pass",
    "risk_budget_ignored",
    "conditionality_clause_deleted",
    "strangle_drift",
)


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _run_with_isolated_confidence_ledger(
    repo_root: Path,
    *,
    scenario_id: str,
    promotion_input: CanonicalPromotionInput,
) -> CanonicalPromotionReceipt:
    """Replay one synthetic scenario against a fresh deterministic N11 scope."""

    risk_scope = confidence_risk_scope_for_problem(promotion_input.design_problem_binding)
    with TemporaryDirectory(prefix=f"gy-n9-{scenario_id}-") as temp_dir:
        state_root = Path(temp_dir)
        session = ConfidenceLedgerSession._for_verification(
            repo_root,
            risk_scope=risk_scope,
            artifact_store=FileSystemCAS(state_root / "cas"),
            state_root=state_root / "state",
        )
        receipt = _run_canonical_promotion_sequence_for_verification(
            promotion_input,
            confidence_ledger_session=session,
        )
        issues = _validate_canonical_promotion_receipt_for_verification(
            receipt,
            repo_root=repo_root,
            confidence_ledger_session=session,
        )
        if issues:
            raise RuntimeError(
                "canonical_n9_replay_invalid: " + json.dumps(issues, sort_keys=True, default=str)
            )
        return receipt


def build_payload(repo_root: Path) -> dict[str, Any]:
    """Build the frozen N9 payload from Lane-0 contract certificates."""

    started = time.monotonic()
    contract_input = _promotion_input()
    contract_refusal = _run_with_isolated_confidence_ledger(
        repo_root,
        scenario_id="contract-lane-anytime-refusal",
        promotion_input=contract_input,
    )
    production_shadow = _run_with_isolated_confidence_ledger(
        repo_root,
        scenario_id="production-honest-shadow",
        promotion_input=contract_input.model_copy(
            update={
                "candidate_summary": _summary(
                    current_valid=False,
                    grounding_status="grounded_shadow",
                ),
                "grounding_decision_certificate": None,
                "credal_reference": None,
            }
        ),
    )
    non_promotable = _run_with_isolated_confidence_ledger(
        repo_root,
        scenario_id="non-promotable-contract-stamp",
        promotion_input=contract_input,
    )
    payload: dict[str, Any] = {
        "schema_version": GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        "contract_id": "policyos.runtime.quality.canonical_n9_promotion_sequence",
        "produced_by": "tools/quality/validation/check_layer3_gy_promotion_contract.py",
        "source_modules": [
            "src/polisyos/pdc/_impl/gy_waist.py",
            "src/polisyos/pdc/_impl/layer2_design_search.py",
            "src/polisyos/runtime/quality/promotion_sequence.py",
            "src/polisyos/runtime/quality/confidence_ledger.py",
            "architecture/production_quality/confidence_ledger.toml",
            "src/polisyos/runtime/quality/generation_cycle.py",
            "src/polisyos/runtime/quality/grounding_bind.py",
            "src/polisyos/core/contracts/value_outer_set.py",
            "src/polisyos/scientist/methods/search/judge_stack.py",
        ],
        "pattern_pass": {
            "relevant_ids": ["P05", "P10", "P14", "P15", "P27", "P28", "P29", "P32"],
            "existing_anti_patterns_found": [
                "Scientist champion registry could previously write promoted pointers beside PDC gates",
                "G4 governed-promotion artifacts existed as a parallel promotion surface",
            ],
            "target_correct_pattern": (
                "single N6/N9 sequence over Ring-2 waist, CGF/CG2, N8 value/calibration/"
                "transport, authority meet, S6/S7/S8, G4 record refs, and the N11 "
                "current-head confidence-ledger projection"
            ),
            "missing_capability_labels": ["surface_out_of_scope"],
            "acceptance_signal": "frozen_receipt_validates_rederive_audit_and_source_flips_red",
        },
        "owner_inventory": {
            "waist_trace": "src/polisyos/pdc/_impl/gy_waist.py",
            "s6_s7_s8": "src/polisyos/pdc/_impl/layer2_design_search.py",
            "n6_port": "src/polisyos/runtime/quality/generation_cycle.py",
            "n8_value_receipt": "src/polisyos/runtime/quality/generation_cycle.py",
            "cg2_promotability": "src/polisyos/runtime/quality/grounding_bind.py",
            "n11_confidence_ledger": "src/polisyos/runtime/quality/confidence_ledger.py",
            "scientist_champion_strangled": "src/polisyos/scientist/methods/search/judge_stack.py",
        },
        "obligation_denominator": _obligation_denominator(),
        "scope_insufficient_promotion_policy": _scope_insufficient_promotion_policy(),
        "contract_lane_anytime_refusal": contract_refusal.model_dump(mode="json"),
        "production_honest_shadow": production_shadow.model_dump(mode="json"),
        "non_promotable_contract_stamp": non_promotable.model_dump(mode="json"),
        "strangle_receipt": LegacyPromotionStrangleReceipt.recompute(repo_root).model_dump(
            mode="json"
        ),
        "compute_economics": {
            "lane0_sequence_logic": (
                "synthetic_contract_certificates_with_non_authority_n11_replay"
            ),
            "e1_cached_obligation_solves": True,
            "routine_check": "canonical_owner_recomputation_and_exact_byte_comparison",
            "cold_rederive_lane": "--rederive-audit",
            "wall_time_recorded_by_validator": True,
        },
        "delta_caveat": CONDITIONAL_VALIDITY_CLAUSE,
        "source_flip_mutation_harness": {
            "mode": "--source-flip-mutations",
            "mutation_ids": list(_SOURCE_FLIP_MUTATION_IDS),
        },
    }
    payload["behavioral_mutations"] = _behavioral_mutations(payload)
    payload["capture_wall_time_seconds"] = round(time.monotonic() - started, 6)
    _set_comparison_identity(payload)
    payload["contract_content_hash"] = _contract_content_hash(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a frozen N9 contract payload without live gate re-derivation."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != GY_PROMOTION_SEQUENCE_SCHEMA_VERSION:
        issues.append({"code": "schema_version_drift"})
    if payload.get("obligation_denominator") != _obligation_denominator():
        issues.append({"code": "obligation_denominator_drift"})
    if payload.get("scope_insufficient_promotion_policy") != _scope_insufficient_promotion_policy():
        issues.append({"code": "scope_insufficient_promotion_policy_drift"})
    if payload.get("delta_caveat") != CONDITIONAL_VALIDITY_CLAUSE:
        issues.append({"code": "conditionality_clause_drift"})
    issues.extend(_comparison_identity_issues(payload))
    expected_hash = _contract_content_hash(payload)
    if payload.get("contract_content_hash") != expected_hash:
        issues.append(
            {
                "code": "contract_content_hash_drift",
                "expected": expected_hash,
                "actual": payload.get("contract_content_hash"),
            }
        )
    contract_refusal = _receipt_from_payload(
        payload,
        "contract_lane_anytime_refusal",
        issues,
    )
    production_shadow = _receipt_from_payload(payload, "production_honest_shadow", issues)
    non_promotable = _receipt_from_payload(payload, "non_promotable_contract_stamp", issues)
    if contract_refusal is not None:
        _validate_n11_projection(
            contract_refusal,
            receipt_key="contract_lane_anytime_refusal",
            issues=issues,
        )
        if contract_refusal.promoted:
            issues.append({"code": "fixed_time_refusal_promoted"})
        if contract_refusal.promotion_lane != "contract_testing":
            issues.append({"code": "contract_lane_refusal_missing_lane_stamp"})
        if contract_refusal.consumer_promotable:
            issues.append({"code": "contract_lane_refusal_launderable"})
        if contract_refusal.non_promotable_reason != "verification_only_replay":
            issues.append({"code": "contract_lane_refusal_missing_non_promotable_stamp"})
        if contract_refusal.authority_derivation_trace is not None:
            issues.append({"code": "refused_contract_lane_minted_trace"})
        if "calibration:single_obligation_fail" not in contract_refusal.refusal_reasons:
            issues.append({"code": "fixed_time_refusal_missing_typed_calibration_refusal"})
        scope_gaps = {
            obligation.obligation_class
            for obligation in contract_refusal.obligations
            if obligation.status.value == "scope_insufficient"
        }
        expected_scope_gaps = {
            PromotionObligationClass.EFFECT,
            PromotionObligationClass.MEASUREMENT,
        }
        if scope_gaps != expected_scope_gaps:
            issues.append(
                {
                    "code": "contract_lane_refusal_scope_gap_denominator_drift",
                    "expected": sorted(item.value for item in expected_scope_gaps),
                    "actual": sorted(item.value for item in scope_gaps),
                }
            )
    if production_shadow is not None:
        _validate_n11_projection(
            production_shadow,
            receipt_key="production_honest_shadow",
            issues=issues,
        )
        if production_shadow.promoted:
            issues.append({"code": "production_shadow_promoted"})
        if "identification:single_obligation_fail" not in production_shadow.refusal_reasons:
            issues.append({"code": "production_shadow_missing_typed_grounding_refusal"})
        if "measurement:scope_insufficient" not in production_shadow.refusal_reasons:
            issues.append({"code": "production_shadow_missing_measurement_scope_refusal"})
        if "calibration:single_obligation_fail" not in production_shadow.refusal_reasons:
            issues.append({"code": "production_shadow_missing_calibration_refusal"})
    if non_promotable is not None:
        _validate_n11_projection(
            non_promotable,
            receipt_key="non_promotable_contract_stamp",
            issues=issues,
        )
        if non_promotable.promoted:
            issues.append({"code": "non_promotable_contract_stamp_promoted"})
        if non_promotable.consumer_promotable:
            issues.append({"code": "non_promotable_bind_laundered"})
        if non_promotable.non_promotable_reason != "verification_only_replay":
            issues.append({"code": "non_promotable_bind_reason_missing"})
    strangle = payload.get("strangle_receipt")
    if not isinstance(strangle, dict) or strangle.get("status") != "strangled":
        issues.append({"code": "parallel_champion_path_not_strangled"})
    mutation_status = {
        str(item.get("mutation_id")): str(item.get("status"))
        for item in payload.get("behavioral_mutations", [])
        if isinstance(item, dict)
    }
    if tuple(mutation_status) != _BEHAVIORAL_MUTATION_IDS:
        issues.append(
            {
                "code": "behavioral_mutation_denominator_mismatch",
                "expected": list(_BEHAVIORAL_MUTATION_IDS),
                "actual": list(mutation_status),
            }
        )
    for mutation_id in _BEHAVIORAL_MUTATION_IDS:
        if mutation_status.get(mutation_id) != "red":
            issues.append({"code": "behavioral_mutation_not_red", "mutation_id": mutation_id})
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path) -> dict[str, Any]:
    """Recompute the canonical contract and reject frozen-byte drift."""

    started = time.monotonic()
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        return {
            "status": "fail",
            "issues": [{"code": "promotion_contract_missing", "path": OUTPUT_PATH}],
            "wall_time_seconds": round(time.monotonic() - started, 6),
        }
    committed_json = path.read_text(encoding="utf-8")
    report = validate_payload(json.loads(committed_json))
    expected_json = build_contract_json_for_write(repo_root)
    if committed_json != expected_json:
        report["issues"].append(
            {
                "code": "promotion_contract_canonical_drift",
                "expected_hash": gy_content_hash(json.loads(expected_json)),
                "actual_hash": gy_content_hash(json.loads(committed_json)),
            }
        )
        report["status"] = "fail"
    report["wall_time_seconds"] = round(time.monotonic() - started, 6)
    return report


def rederive_audit(repo_root: Path) -> dict[str, Any]:
    """Run the explicit cold Lane-0 re-derivation path."""

    started = time.monotonic()
    payload = build_payload(repo_root)
    report = validate_payload(payload)
    report["wall_time_seconds"] = round(time.monotonic() - started, 6)
    report["compute_economics"] = payload["compute_economics"]
    return report


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Mutate a decisive field and require the frozen validator to turn red."""

    started = time.monotonic()
    payload = json.loads((repo_root / OUTPUT_PATH).read_text(encoding="utf-8"))
    del payload["contract_lane_anytime_refusal"]["confidence_ledger_projection"][
        "conditionality_clause"
    ]
    report = validate_payload(payload)
    if report["status"] == "fail":
        return {
            "status": "fail",
            "issues": [
                {"code": "corrupt_field_drift_detected"},
                *report["issues"],
            ],
            "wall_time_seconds": round(time.monotonic() - started, 6),
        }
    return {
        "status": "pass",
        "issues": [{"code": "corrupt_field_drift_not_detected"}],
        "wall_time_seconds": round(time.monotonic() - started, 6),
    }


def write(repo_root: Path) -> None:
    """Write the byte-stable frozen N9 contract."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_contract_json_for_write(repo_root), encoding="utf-8")


def build_contract_json_for_write(repo_root: Path) -> str:
    """Return byte-stable canonical JSON for the reissued N9 contract."""

    payload = build_payload(repo_root)
    payload.pop("capture_wall_time_seconds", None)
    _set_comparison_identity(payload)
    payload["contract_content_hash"] = _contract_content_hash(payload)
    payload = _reconcile_frozen_contract(repo_root, payload)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def run_source_flip_mutations(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Temporarily remove source guards and require every probe to go red."""

    cases = _source_flip_cases()
    if tuple(case.mutation_id for case in cases) != _SOURCE_FLIP_MUTATION_IDS:
        return (
            {
                "mutation_id": "source_flip_harness_denominator",
                "result": "HARNESS_ERROR",
                "proof": {
                    "expected": list(_SOURCE_FLIP_MUTATION_IDS),
                    "actual": [case.mutation_id for case in cases],
                },
            },
        )
    return tuple(_run_source_flip_case(repo_root, case) for case in cases)


def _receipt_from_payload(
    payload: dict[str, Any],
    key: str,
    issues: list[dict[str, Any]],
) -> CanonicalPromotionReceipt | None:
    value = payload.get(key)
    if not isinstance(value, dict):
        issues.append({"code": f"{key}_missing"})
        return None
    try:
        return CanonicalPromotionReceipt.model_validate(value)
    except ValueError as exc:
        issues.append({"code": f"{key}_invalid", "error": str(exc)})
        return None


def _validate_n11_projection(
    receipt: CanonicalPromotionReceipt,
    *,
    receipt_key: str,
    issues: list[dict[str, Any]],
) -> None:
    """Validate the exact narrow N11 projection carried by one N9 receipt."""

    projection = receipt.confidence_ledger_projection
    if projection.authority_provenance != "verification":
        issues.append(
            {
                "code": "confidence_ledger_replay_provenance_drift",
                "receipt_key": receipt_key,
            }
        )
    expected_gate_hash = gy_content_hash(
        [item.model_dump(mode="json") for item in receipt.obligations]
    )
    if receipt.gate_outcome_hash != expected_gate_hash:
        issues.append(
            {
                "code": "gate_outcome_hash_drift",
                "receipt_key": receipt_key,
            }
        )
    expected_projection_hash = gy_content_hash(
        projection.model_dump(mode="json", exclude={"projection_hash"})
    )
    if projection.projection_hash != expected_projection_hash:
        issues.append(
            {
                "code": "confidence_ledger_projection_hash_drift",
                "receipt_key": receipt_key,
            }
        )
    if projection.conditionality_clause != CONDITIONAL_VALIDITY_CLAUSE:
        issues.append(
            {
                "code": "confidence_ledger_conditionality_clause_drift",
                "receipt_key": receipt_key,
            }
        )
    if projection.maintained_assumptions != (
        "obligation_completeness",
        "validator_soundness",
    ):
        issues.append(
            {
                "code": "confidence_ledger_assumption_denominator_drift",
                "receipt_key": receipt_key,
            }
        )
    if (
        receipt.risk_spend.caveat != PROMOTION_RISK_CONDITIONALITY_CAVEAT
        or receipt.risk_spend.total_declared_delta != float(projection.total_spend.fraction)
        or receipt.risk_spend.budget_delta != float(projection.budget_delta.fraction)
        or receipt.risk_spend.within_budget is not projection.within_budget
    ):
        issues.append(
            {
                "code": "risk_spend_not_derived_from_confidence_ledger",
                "receipt_key": receipt_key,
            }
        )
    if projection.total_spend.numerator != 0 or not projection.within_budget:
        issues.append(
            {
                "code": "fixed_time_refusal_spend_invalid",
                "receipt_key": receipt_key,
            }
        )
    rows = tuple(
        row
        for row in projection.promotion_rows
        if row.obligation_class == PromotionObligationClass.CALIBRATION
    )
    if len(rows) != 1:
        issues.append(
            {
                "code": "calibration_ledger_row_denominator_mismatch",
                "receipt_key": receipt_key,
                "actual": len(rows),
            }
        )
        return
    row = rows[0]
    if (
        row.instrument_id != "fixed_time_confidence_interval"
        or row.execution_status != "refused"
        or row.outcome != "preflight_refusal"
        or row.anytime_valid
        or row.eligible_for_promotion
        or row.spend.numerator != 0
    ):
        issues.append(
            {
                "code": "fixed_time_calibration_not_fail_closed",
                "receipt_key": receipt_key,
            }
        )
    calibration = next(
        (
            item
            for item in receipt.obligations
            if item.obligation_class == PromotionObligationClass.CALIBRATION
        ),
        None,
    )
    spend = calibration.risk_spend if calibration is not None else None
    if (
        spend is None
        or spend.n11_confidence_ledger_ref != row.check_id
        or spend.certificate_ref != row.certificate_ref
        or spend.instrument != row.instrument_id
        or spend.declared_delta_spend != float(row.spend.fraction)
    ):
        issues.append(
            {
                "code": "calibration_obligation_ledger_binding_invalid",
                "receipt_key": receipt_key,
            }
        )


def _behavioral_mutations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mutations = {
        "ledger_projection_hand_edit": _mutate_ledger_projection,
        "gate_outcome_drift": _mutate_gate_hash,
        "fixed_time_refusal_laundered": _mutate_fixed_time_refusal,
        "vacuous_scope_pass": _mutate_vacuous_scope_pass,
        "risk_budget_ignored": _mutate_risk_budget,
        "conditionality_clause_deleted": _mutate_conditionality_clause,
        "strangle_drift": _mutate_strangle,
    }
    reports: list[dict[str, Any]] = []
    for mutation_id, mutator in mutations.items():
        mutated = copy.deepcopy(payload)
        mutator(mutated)
        report = validate_payload_without_mutation_check(mutated)
        reports.append(
            {
                "mutation_id": mutation_id,
                "status": "red" if report["issues"] else "green",
                "issue_codes": [str(issue.get("code")) for issue in report["issues"]],
            }
        )
    return reports


def validate_payload_without_mutation_check(payload: dict[str, Any]) -> dict[str, Any]:
    """Core payload check used by behavioral mutations to avoid recursion."""

    stripped = copy.deepcopy(payload)
    stripped["behavioral_mutations"] = [
        {"mutation_id": item, "status": "red"} for item in _BEHAVIORAL_MUTATION_IDS
    ]
    _set_comparison_identity(stripped)
    stripped["contract_content_hash"] = _contract_content_hash(stripped)
    return validate_payload(stripped)


def _mutate_ledger_projection(payload: dict[str, Any]) -> None:
    payload["contract_lane_anytime_refusal"]["confidence_ledger_projection"]["projection_hash"] = (
        _hash("8")
    )


def _mutate_gate_hash(payload: dict[str, Any]) -> None:
    payload["contract_lane_anytime_refusal"]["gate_outcome_hash"] = _hash("7")


def _mutate_fixed_time_refusal(payload: dict[str, Any]) -> None:
    row = payload["contract_lane_anytime_refusal"]["confidence_ledger_projection"][
        "promotion_rows"
    ][0]
    row["anytime_valid"] = True
    row["eligible_for_promotion"] = True


def _mutate_vacuous_scope_pass(payload: dict[str, Any]) -> None:
    for obligation in payload["contract_lane_anytime_refusal"]["obligations"]:
        if obligation["obligation_class"] == PromotionObligationClass.EFFECT.value:
            obligation["status"] = "satisfied"
            obligation["reason"] = None
            obligation["semantic_scope"] = "scope_insufficient"
            return
    raise AssertionError("effect_scope_gap_missing")


def _mutate_risk_budget(payload: dict[str, Any]) -> None:
    payload["contract_lane_anytime_refusal"]["risk_spend"]["within_budget"] = False


def _mutate_conditionality_clause(payload: dict[str, Any]) -> None:
    del payload["contract_lane_anytime_refusal"]["confidence_ledger_projection"][
        "conditionality_clause"
    ]


def _mutate_strangle(payload: dict[str, Any]) -> None:
    payload["strangle_receipt"]["status"] = "drift"
    payload["strangle_receipt"]["live_policy_champion_callers"] = [
        "src/polisyos/scientist/methods/search/judge_stack.py:1648"
    ]


def _obligation_denominator() -> list[dict[str, Any]]:
    owner_by_class = {
        PromotionObligationClass.SYNTAX: ("gy_waist", "real_semantics"),
        PromotionObligationClass.TYPE: ("n8_value_receipt", "real_semantics"),
        PromotionObligationClass.SLOT: ("n8_transport_receipt", "real_semantics"),
        PromotionObligationClass.PARAM: (
            "g4_persisted_owner_record_resolution",
            "real_semantics_record_resolution_only_g4_minting_strangled",
        ),
        PromotionObligationClass.COUPLING: ("n5_coupling_gate", "real_semantics"),
        PromotionObligationClass.EFFECT: (
            "gyk_entailment_owner_unwired",
            "scope_insufficient",
        ),
        PromotionObligationClass.IDENTIFICATION: ("cgf_plus_cg2_promotability", "real_semantics"),
        PromotionObligationClass.CALIBRATION: ("n8_s10_calibration_receipt", "real_semantics"),
        PromotionObligationClass.MEASUREMENT: (
            "measurement_rooted_owner_unwired",
            "scope_insufficient",
        ),
        PromotionObligationClass.DATA: (
            "l5_data_trust_typed_fields",
            "real_semantics",
        ),
        PromotionObligationClass.IMPLEMENTATION: (
            "s6_typed_blind_spot_posture",
            "real_semantics",
        ),
        PromotionObligationClass.EQUILIBRIUM: ("n5_value_assumption_gate", "real_semantics"),
        PromotionObligationClass.NORMATIVE: ("s7_mandate_delegation_gate", "real_semantics"),
        PromotionObligationClass.EVAL_SAFETY: (
            "gy_o0_eval_safety",
            "data_only_not_required_scope_insufficient_for_pilot_deployment",
        ),
        PromotionObligationClass.VALUE: ("n8_value_plus_s8_value_posture", "real_semantics"),
    }
    return [
        {
            "obligation_class": item.value,
            "owner": owner_by_class[item][0],
            "semantic_scope": owner_by_class[item][1],
        }
        for item in PromotionObligationClass
    ]


def _scope_insufficient_promotion_policy() -> dict[str, str]:
    """Return the frozen authority rule for unwired obligation owners."""

    return {
        "production": (
            "Every scope_insufficient obligation is a typed refusal and prevents "
            "authoritative promotion."
        ),
        "contract_testing": (
            "A CG2-derived contract-testing lane may retain scope_insufficient obligations "
            "only as unsatisfied, non-authoritative sequence coverage; consumer_promotable "
            "remains false and no production authority is minted."
        ),
    }


def _contract_content_hash(payload: dict[str, Any]) -> str:
    stable = {
        key: value for key, value in payload.items() if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    return gy_content_hash(stable)


def _comparison_content_hash(payload: dict[str, Any]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL | _COMPARISON_IDENTITY_FIELDS
    }
    return gy_comparison_content_hash(
        stable,
        admit_non_authority_block=n9_promotion_projection_comparison_eligible,
    )

def _reconcile_frozen_contract(
    repo_root: Path,
    live: dict[str, Any],
) -> dict[str, Any]:
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        return live
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if not frozen.get("comparison_content_hash") or frozen.get(
        "comparison_content_hash"
    ) != live.get("comparison_content_hash"):
        return live
    identity_fields = _COMPARISON_IDENTITY_FIELDS | {"contract_content_hash"}
    frozen_body = {key: value for key, value in frozen.items() if key not in identity_fields}
    live_body = {key: value for key, value in live.items() if key not in identity_fields}
    reconciled = reconcile_gy_operational_leaves(
        frozen_body,
        live_body,
        admit_non_authority_block=n9_promotion_projection_comparison_eligible,
    )
    if not isinstance(reconciled, dict):  # pragma: no cover - mapping inputs
        raise ValueError("promotion_contract_comparison_projection_invalid")
    _set_comparison_identity(reconciled)
    reconciled["contract_content_hash"] = _contract_content_hash(reconciled)
    return reconciled

def _set_comparison_identity(payload: dict[str, Any]) -> None:
    payload["comparison_projection_schema_version"] = GY_COMPARISON_PROJECTION_SCHEMA_VERSION
    payload["comparison_rule_version"] = GY_VERIFICATION_COMPARISON_RULE_VERSION
    payload["comparison_content_hash"] = _comparison_content_hash(payload)

def _comparison_identity_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if (
        payload.get("comparison_projection_schema_version")
        != GY_COMPARISON_PROJECTION_SCHEMA_VERSION
    ):
        issues.append({"code": "comparison_projection_schema_version_invalid"})
    if payload.get("comparison_rule_version") != GY_VERIFICATION_COMPARISON_RULE_VERSION:
        issues.append({"code": "comparison_rule_version_invalid"})
    if payload.get("comparison_content_hash") != _comparison_content_hash(payload):
        issues.append({"code": "comparison_content_hash_drift"})
    return issues

def _obligation_detail(
    receipt: CanonicalPromotionReceipt,
    obligation_class: PromotionObligationClass,
) -> str:
    for obligation in receipt.obligations:
        if obligation.obligation_class == obligation_class:
            return obligation.detail
    return ""


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
            path.write_text(text.replace(replacement.old, replacement.new, 1), encoding="utf-8")
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
    except Exception as exc:  # pragma: no cover - surfaced as harness data.
        return {
            "mutation_id": case.mutation_id,
            "result": "HARNESS_ERROR",
            "guard": case.guard,
            "proof": str(exc),
        }
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")


def _source_flip_cases() -> tuple[_SourceFlipCase, ...]:
    test_file = "tests/unit/runtime/quality/test_promotion_sequence.py"
    source = "src/polisyos/runtime/quality/promotion_sequence.py"
    confidence_source = "src/polisyos/runtime/quality/confidence_ledger.py"
    generation_source = "src/polisyos/runtime/quality/generation_cycle.py"
    return (
        _SourceFlipCase(
            mutation_id="source_flip_no_self_promotion_guard",
            guard="AuthorityDerivationTrace._reject_self_promotion",
            replacements=(
                _SourceFlipReplacement(
                    relative_path="src/polisyos/pdc/_impl/gy_waist.py",
                    old='        if self.transform_mismatch_disposition not in {"matched", "downgraded", "rejected"}:\n            raise ValueError("authority_transform hints cannot self-promote")',
                    new='        if False and self.transform_mismatch_disposition not in {"matched", "downgraded", "rejected"}:\n            raise ValueError("authority_transform hints cannot self-promote")',
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_no_self_promotion_rejected_by_trace_guard"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_non_anytime_preflight_guard",
            guard="non-anytime-valid proof profiles must fail before execution",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=confidence_source,
                    old='    if profile.proof_kernel_id == "ineligible_v1":',
                    new='    if False and profile.proof_kernel_id == "ineligible_v1":',
                ),
                _SourceFlipReplacement(
                    relative_path=confidence_source,
                    old="    if not profile.deterministic and not profile.anytime_valid:",
                    new="    if False and not profile.deterministic and not profile.anytime_valid:",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_real_transport_refusal",
            guard="N8 transport receipt must not be blocked",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old='    if receipt.transport_receipt.status == "blocked":',
                    new='    if False and receipt.transport_receipt.status == "blocked":',
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_untransportable_candidate_stays_shadow"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_cg2_owner_call_removed",
            guard="CG2 promotability must be resolved by the owner call",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old="        resolution = resolver(certificate, reference)",
                    new="        resolution = None",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_g4_owner_resolution_removed",
            guard="G4 record ref must dereference the persisted owner artifact",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old='    return None, "governed_promotion_record_not_found"',
                    new=(
                        '    return {"promotion_record_id": record_ref, '
                        '"promotion_state": "promotion_blocked"}, None'
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_forged_g4_ref_is_refused_by_owner_resolution"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_timeout_to_favorable",
            guard="proof timeout carried as unknown",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old="    if promotion_input.force_proof_timeout:",
                    new="    if False and promotion_input.force_proof_timeout:",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_timeout_unknown_never_promotes_or_fabricates_block"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_lower_boundary_meet",
            guard="authority meet keeps lower boundary",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old=(
                        '        value_grade = "advisory_admissible" '
                        'if decision.promotable else "unsupported"'
                    ),
                    new=(
                        '        value_grade = "decision_admissible" '
                        'if decision.promotable else "unsupported"'
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_lower_boundary_wins_over_optimistic_declared_transform"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_non_promotable_bind_stamp",
            guard="CG2 owner-store non-promotable stamp",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old="    return resolution.reason",
                    new="    return None",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_contract_testing_bind_receipt_is_intrinsically_non_promotable"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_n6_ledger_revalidation_removed",
            guard="N6 revalidates the typed N9/N11 receipt before DecisionFront",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=generation_source,
                    old=(
                        "        if validate_canonical_promotion_receipt(\n"
                        "            parsed,\n"
                        "            candidate_summary=summary,\n"
                        "            design_problem=problem,\n"
                        "            value_receipt=summary.value_receipt,\n"
                        "        ):\n"
                        "            return False"
                    ),
                    new=(
                        "        if False and validate_canonical_promotion_receipt(\n"
                        "            parsed,\n"
                        "            candidate_summary=summary,\n"
                        "            design_problem=problem,\n"
                        "            value_receipt=summary.value_receipt,\n"
                        "        ):\n"
                        "            return False"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_failed_obligation_cannot_be_relabelled_into_decision_front"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_vacuous_scope_autopass",
            guard="scope_insufficient cannot become satisfied in frozen receipt",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old='            obligation.status == PromotionObligationStatus.SATISFIED\n            and obligation.semantic_scope == "scope_insufficient"',
                    new='            False and obligation.status == PromotionObligationStatus.SATISFIED\n            and obligation.semantic_scope == "scope_insufficient"',
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_scope_insufficient_obligation_does_not_vacuously_pass"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_scope_insufficient_authority_guard",
            guard="scope-insufficient obligations cannot mint production authority",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old=("        if (\n            self.promoted\n            and scope_gaps"),
                    new=(
                        "        if (\n"
                        "            False\n"
                        "            and self.promoted\n"
                        "            and scope_gaps"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_scope_insufficient_cannot_mint_production_authority"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_invented_measurement_marker_reintroduced",
            guard="measurement obligation cannot read a synthetic calibration-scope marker",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old="    del receipt",
                    new=(
                        "    if receipt is not None and "
                        'receipt.value_outer_set.calibration_scope.get("measurement_status"):\n'
                        "        return _satisfied_obligation(\n"
                        "            obligation_class=PromotionObligationClass.MEASUREMENT,\n"
                        "            gate_id=PromotionGateId.N8_VALUE,\n"
                        '            owner_ref="synthetic measurement marker",\n'
                        '            detail="Synthetic marker was treated as measurement authority.",\n'
                        "        )\n"
                        "    del receipt"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_invented_measurement_marker_does_not_supply_authority"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_unseen_shape_panel_coupling",
            guard="generic ValueGateReceipt consumption",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old="    _assert_generic_value_receipt(receipt)",
                    new="    _assert_panel_specific_value_receipt(receipt)",
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_unseen_non_panel_value_receipt_flows_unchanged"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_live_champion_path",
            guard="legacy champion path strangle",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old="    return tuple(sorted(dict.fromkeys(callers)))",
                    new='    return ("src/polisyos/scientist/methods/search/judge_stack.py:1648",)',
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_reintroduced_champion_path_turns_strangle_receipt_red"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_confidence_projection_recompute_guard",
            guard="N11 promotion projection must be recomputed from the current ledger head",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old="        and receipt.confidence_ledger_projection != expected_projection",
                    new=(
                        "        and False\n"
                        "        and receipt.confidence_ledger_projection != expected_projection"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_hand_edited_confidence_projection_is_rejected"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_ledger_bypass_guard",
            guard="a satisfied probabilistic obligation must bind an eligible N11 row",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old=(
                        "        if (\n"
                        "            obligation.status == PromotionObligationStatus.SATISFIED\n"
                        "            and ledger_required\n"
                        "            and not any("
                    ),
                    new=(
                        "        if (\n"
                        "            False\n"
                        "            and obligation.status == PromotionObligationStatus.SATISFIED\n"
                        "            and ledger_required\n"
                        "            and not any("
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_probabilistic_certificate_bypassing_ledger_is_rejected"
            ),
        ),
    )


def _pytest_probe(*node_ids: str) -> tuple[str, ...]:
    return ("python3", "-m", "pytest", *node_ids, "-q")


def _output_tail(output: str, *, max_lines: int = 20) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def _promotion_input(**overrides: object) -> CanonicalPromotionInput:
    reference, decision = _cg2_contract_bind()
    kwargs: dict[str, Any] = {
        "design_problem_binding": N9DesignProblemBinding(
            design_problem_id="frozen_n9_contract",
            problem_content_hash=gy_content_hash(
                {
                    "design_problem_id": "frozen_n9_contract",
                    "schema_version": "policyos.runtime.design_problem.frozen-n9.v1",
                }
            ),
            model_spec_ref=None,
            problem_schema_version="policyos.runtime.design_problem.frozen-n9.v1",
        ),
        "candidate_summary": _summary(),
        "value_receipt": _value_receipt(),
        "grounding_decision_certificate": decision,
        "credal_reference": reference,
        "s6_blind_spot_posture": _s6_posture(),
        "s7_delegation_posture": _s7_posture(),
        "s8_value_posture": _s8_posture(),
        "declared_authority_transform": {
            "requested_evidence_kind": "transport",
            "requested_decision_grade": "advisory_admissible",
        },
    }
    kwargs.update(overrides)
    return CanonicalPromotionInput(**kwargs)


def _summary(
    *,
    current_valid: bool = True,
    grounding_status: str = "current_valid",
) -> CandidateSummary:
    return CandidateSummary(
        candidate_id="candidate_n9",
        content_hash=_hash("2"),
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status=grounding_status,  # type: ignore[arg-type]
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.95,
        current_valid=current_valid,
        value_status="value_ready",
        value_decision_grade="high",
        value_ref=_hash("3"),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )


def _value_receipt() -> ValueGateReceipt:
    world_hash = _hash("4")
    data_trust = DataTrust(
        tier="unit",
        trust_cap=1.0,
        trust_multiplier=1.0,
        promotion_floor=0.5,
        authority_ref="data-trust://unit",
    )
    value_set = ValueOuterSet.interval_box(
        coordinates=("welfare",),
        lower=(1.0,),
        upper=(1.0,),
        identification_mode="point",
        assumptions=(),
        assumption_status="externally_supported",
        calibration_scope={"scope": "unit"},
        data_trust=data_trust,
        world_model_record_ref=world_hash,
        epoch="2026",
        representation_status="certified",
    )
    return ValueGateReceipt(
        candidate_id="candidate_n9",
        evaluation_mode="simulate_only",
        selected_method_fqn="causal.inference.did.standard@1",
        method_selection_trace=("causal.inference.did.standard@1",),
        identification_status=value_set.identification_status,
        value_outer_set=value_set,
        transport_receipt=ValueTransportReceipt(
            status="direct",
            world_model_record_id="wmr_n9",
            world_model_record_content_hash=world_hash,
            transport_result_ref="transport://unit",
            transport_status="identified",
            transport_mode="direct",
            identification_engine="unit",
        ),
        calibration_receipt=ValueCalibrationReceipt(
            status="pass",
            forecast_tier="observable_calibrated",
            calibration_record_ref="s10://unit",
        ),
        world_model_record_id="wmr_n9",
        world_model_record_content_hash=world_hash,
        value_ref=_hash("3"),
        wall_time_ms=1.0,
        wmr_cache_status="built",
        k_world_ref_before=world_hash,
        k_world_ref_after=world_hash,
    )


def _cg2_contract_bind() -> tuple[CredalReference, GroundingDecisionCertificate]:
    reference = _credal_reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="n9-cg2-bind")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    payload = decision.model_dump(mode="json")
    safe_candidate = next(
        item
        for item in payload["safe_t"]["candidates"]
        if item["relation"] == "exact" and not item["is_adversarial_countercandidate"]
    )
    safe_candidate = {**safe_candidate, "safe": True, "reason": "contract_owner_bind"}
    safe_atom_id = str(safe_candidate["atom_id"])
    payload.update(
        {
            "decision": "bind",
            "decisive_reason": "bind_eligible",
            "selected_relation": "exact",
            "bound_atom_id": safe_atom_id,
            "closed_obligations": tuple(
                sorted({*payload["closed_obligations"], "unit_scale_consistent"})
            ),
            "open_obligations": (),
            "safe_t": {
                "safe_atom_ids": (safe_atom_id,),
                "candidates": (safe_candidate,),
                "robust_singleton": True,
            },
            "revalidation": {
                **payload["revalidation"],
                "replayed_selected_relation": "exact",
                "replayed_selected_atom_id": safe_atom_id,
                "selected_relation_reproduced": True,
                "selected_atom_reproduced": True,
            },
        }
    )
    payload["content_hash"] = recompute_grounding_decision_content_hash(payload)
    payload["certificate_id"] = f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    return reference, GroundingDecisionCertificate.model_validate(payload)


def _boundary() -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id="n9.contract.boundary",
        authoritative_for=["grounded_partial_admissible_policy_design"],
        may_not_use_for=["production_deployment"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[GY_PROMOTION_SEQUENCE_SCHEMA_VERSION],
        evidence_kind="measurement",
        decision_grade="decision_admissible",
    )


def _s6_posture() -> Layer2S6BlindSpotPostureInput:
    return Layer2S6BlindSpotPostureInput(
        overall_posture="clear_fail_closed",
        measurability_record_ref="s6://measure",
        aggregation_validity_record_ref="s6://aggregation",
        capacity_feasibility_record_ref="s6://capacity",
        mandate_legitimacy_record_ref="s6://mandate",
        strategic_response_record_ref="s6://strategic",
        system_dynamics_handoff_required=False,
        regime_reissue_required=False,
        limitation_summary="S6 clear for N9 contract lane.",
        false_clear_penalty=0.0,
    )


def _s7_posture() -> Layer2S7DelegationPostureInput:
    now = datetime(2026, 7, 8, tzinfo=UTC)
    return Layer2S7DelegationPostureInput(
        delegation_contract_ref="s7://delegation",
        decision_rights_matrix_ref="s7://rights",
        human_decision_request_ref="s7://request",
        human_decision_record_ref="s7://decision",
        decision_class_id="governed_pilot",
        required_role="policy_owner",
        interaction_mode="recorded_decision",
        disposition="recorded_valid_decision",
        available_actions=["approve"],
        decision_action_exercised="approve",
        five_rights_requirement={"required": True},
        five_rights_check={"status": "pass"},
        value_stakes_impact="bounded",
        attention_cost_rank=1,
        responsibility_integrity_status="pass",
        mandate_record_ref="s6://mandate",
        s6_mandate_firewall_disposition="pass",
        requested_at=now,
        decided_at=now,
        voi_rank=1,
        authority_boundary=_boundary(),
        governed_pilot_eligible=True,
        limitation_summary="S7 valid governed-pilot decision.",
    )


def _s8_posture() -> Layer2S8ValuePostureInput:
    return Layer2S8ValuePostureInput(
        value_choice_provenance_ref="s8://value-choice",
        authorized_value_schedule_ref="s8://schedule",
        objective_function_provenance_ref="s8://objective",
        pareto_archive_ref="s8://pareto",
        value_tradeoff_disclosure_ref="s8://tradeoff",
        mandate_record_ref="s6://mandate",
        s6_mandate_firewall_disposition="pass",
        ranking_mode="ranked_with_authorized_values",
        disposition="authorized",
        p20_firewall_status="pass",
        p22_firewall_status="pass",
        value_provenance_completeness=1.0,
        value_authorization_decision_refs=["s8://decision"],
        handoff_rows=[{"handoff": "s8"}],
        limitation_summary="S8 authorized value posture.",
        authority_boundary=_boundary(),
    )


def _credal_reference() -> CredalReference:
    edges = [
        _operator_edge("tax_relief_rate", minimum=0.0, maximum=0.5, unit="ratio"),
        _target_edge("tax_relief_rate", "global.tax_rate"),
        _lex_edge("tax_relief_statute", "tax_relief_rate"),
        _operator_edge("budget_allocation_multiplier", minimum=0.0, maximum=2.0, unit="ratio"),
        _target_edge("budget_allocation_multiplier", "government.balance"),
        _lex_edge("budget_law", "budget_allocation_multiplier"),
        _world_slot("global.tax_rate", unit="ratio"),
        _world_slot("government.balance", unit="usd"),
        _world_slot("household_cells.disposable_income", unit="usd"),
        _world_slot("household_cells.transfer_intensity", unit="ratio"),
        _policy_slot("tax_slot", "global.tax_rate"),
        _policy_slot("budget_slot", "government.balance"),
        _policy_slot("transfer_slot", "household_cells.transfer_intensity"),
    ]
    edge_index = {edge.key: edge for edge in edges}
    component_versions = {
        "L2": "unit-l2",
        "L3": "unit-l3",
        "L6": _component_hash(edges, prefix="L6_"),
        "WMR": "unit-wmr",
    }
    reference_hash = gy_content_hash(
        {
            "component_versions": component_versions,
            "edges": [edge.to_payload() for edge in sorted(edges, key=lambda item: item.key)],
        }
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=edge_index,
    )


def _operator_edge(
    op: str,
    *,
    minimum: float,
    maximum: float,
    unit: str,
) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "parameter_domain": {
                        "kind": "range",
                        "max_value": maximum,
                        "min_value": minimum,
                        "unit": unit,
                        "value_type": "float",
                    },
                },
                "unit_test_operator",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _target_edge(op: str, target: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_WORLD_SLOT",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "target_world_slots": [target],
                    "world_model_record_id": "unit-wmr",
                },
                "unit_test_target",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _lex_edge(law_token: str, op: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_LEX_INTERVENTION_MAP",
        edge_id=law_token,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"law_token": law_token, "knob_id": op},
                "unit_test_lex_map",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _world_slot(slot: str, *, unit: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_WORLD_SLOT",
        edge_id=slot,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion("fixed", {"world_slot": slot}, "unit_test_wmr_slot"),
        ),
        provenance={"owner": "WMR", "source": "unit"},
        unit=unit,
    ).with_content_hash()


def _policy_slot(policy_slot: str, world_slot: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_POLICY_SLOT_MAP",
        edge_id=f"{policy_slot}:{world_slot}",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"policy_slot": policy_slot, "world_slot": world_slot},
                "unit_test_policy_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "unit"},
    ).with_content_hash()


def _component_hash(edges: list[CredalReferenceEdge], *, prefix: str) -> str:
    return gy_content_hash(
        [
            edge.content_hash
            for edge in sorted(edges, key=lambda item: item.key)
            if edge.modality.startswith(prefix)
        ]
    )


def _tax_atom(engine: GroundingRelationEngine) -> object:
    return next(
        item
        for item in engine.reference_atoms
        if item.signature.op == "tax_relief_rate" and "global.tax_rate" in item.signature.X_do
    )


def _pure_synonym_probe(engine: GroundingRelationEngine) -> dict[str, object]:
    atom = _tax_atom(engine)
    signature = atom.signature.model_dump(mode="json")
    signature["op"] = "tax_credit_rate"
    signature["effect_path"] = [
        "tax_credit_rate",
        *list(atom.signature.X_do),
        *list(atom.signature.outcome),
    ]
    signature["modal_claims"] = {
        "NL": {
            "op": "tax_credit_rate",
            "target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
        "L6": {"knob": "tax_relief_rate"},
        "do_AST": {"op": "tax_credit_rate", "target": atom.signature.X_do[0]},
        "method": {
            "treatment_op": "tax_credit_rate",
            "treatment_target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
    }
    return {
        "raw_text": "levy credit-rate alias for the exact same tax relief do-query.",
        "signature": signature,
    }


def _hash(seed: str) -> str:
    return "sha256:" + seed * 64


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_src_path(repo_root: Path) -> None:
    src = repo_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

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
    if args.write:
        write(repo_root)
        report = {"status": "pass", "outputs": declared_outputs()}
    elif args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
    elif args.rederive_audit:
        report = rederive_audit(repo_root)
    elif args.source_flip_mutations:
        results = run_source_flip_mutations(repo_root)
        failures = [item for item in results if item.get("result") != "RED"]
        report = {"status": "pass" if not failures else "fail", "results": list(results)}
    else:
        report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        print(
            "PASS layer3_gy_promotion_contract "
            f"wall_time_seconds={report.get('wall_time_seconds', 0)}"
        )
    else:
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
