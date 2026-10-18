"""Run behavioral mutation and source-flip probes against GY-N9 promotion.

The probes exercise existing runtime owners and report whether their guards turn
red; they do not authorize promotion. The CLI and import facade remains
``check_layer3_gy_promotion_contract``.
"""

from __future__ import annotations

import copy
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.pdc import (
    PROMOTION_RISK_CONDITIONALITY_CAVEAT,
    GyComparisonProjectionPlan,
    PromotionObligationClass,
    gy_content_hash,
)
from polisyos.runtime.quality.confidence_ledger import CONDITIONAL_VALIDITY_CLAUSE
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalPromotionReceipt,
    parse_canonical_promotion_history_receipt,
)
from tools.quality.validation.layer3_gy_n9_contract_inputs import _hash

_BEHAVIORAL_MUTATION_IDS: tuple[str, ...] = (
    "ledger_projection_hand_edit",
    "gate_outcome_drift",
    "fixed_time_refusal_laundered",
    "vacuous_scope_pass",
    "risk_budget_ignored",
    "conditionality_clause_deleted",
    "strangle_drift",
)
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


@dataclass(frozen=True, slots=True)
class _MutationCallbacks:
    """Current facade callbacks used by mutation validation."""

    set_comparison_identity: Callable[[dict[str, Any], GyComparisonProjectionPlan], None]
    contract_content_hash: Callable[[dict[str, Any]], str]
    validate_payload: Callable[[dict[str, Any]], dict[str, Any]]


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
        return parse_canonical_promotion_history_receipt(value)
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


def _behavioral_mutations(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
    *,
    callbacks: _MutationCallbacks,
) -> list[dict[str, Any]]:
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
        report = validate_payload_without_mutation_check(mutated, plan, callbacks=callbacks)
        reports.append(
            {
                "mutation_id": mutation_id,
                "status": "red" if report["issues"] else "green",
                "issue_codes": [str(issue.get("code")) for issue in report["issues"]],
            }
        )
    return reports


def validate_payload_without_mutation_check(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
    *,
    callbacks: _MutationCallbacks,
) -> dict[str, Any]:
    """Core payload check used by behavioral mutations to avoid recursion."""

    stripped = copy.deepcopy(payload)
    stripped["behavioral_mutations"] = [
        {"mutation_id": item, "status": "red"} for item in _BEHAVIORAL_MUTATION_IDS
    ]
    try:
        callbacks.set_comparison_identity(stripped, plan)
    except ValueError as exc:
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "comparison_projection_rejected_mutation",
                    "error": str(exc),
                }
            ],
        }
    stripped["contract_content_hash"] = callbacks.contract_content_hash(stripped)
    return callbacks.validate_payload(stripped)


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
            guard="missing EFFECT evidence stays unknown despite the legacy timeout flag",
            replacements=(
                _SourceFlipReplacement(
                    relative_path=source,
                    old=(
                        "        gate_id=PromotionGateId.GYK_ENTAILMENT,\n"
                        "        status=PromotionObligationStatus.UNKNOWN,\n"
                        "        reason=PromotionFailClosedReason.UNKNOWN,"
                    ),
                    new=(
                        "        gate_id=PromotionGateId.GYK_ENTAILMENT,\n"
                        "        status=PromotionObligationStatus.SATISFIED,\n"
                        "        reason=None,"
                    ),
                ),
            ),
            probe_command=_pytest_probe(
                f"{test_file}::test_timeout_knob_cannot_decide_effect_or_fabricate_block"
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
                    old="    return promotion_receipt_allows_decision_front(",
                    new="    return True or promotion_receipt_allows_decision_front(",
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
