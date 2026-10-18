"""Build the N9 contract by replaying the canonical promotion owner.

The source of truth remains ``polisyos.runtime.quality.promotion_sequence`` and
the historical CLI/import surface remains
``check_layer3_gy_promotion_contract``. Comparison custody, typed synthetic
inputs, and mutation probes are separate sibling owners.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from polisyos.core.artifacts import FileSystemCAS
from polisyos.pdc import (
    GyComparisonAdmission,
    GyComparisonProjectionPlan,
    PromotionObligationClass,
    build_gy_comparison_projection_plan,
)
from polisyos.runtime.quality.confidence_ledger import (
    CONDITIONAL_VALIDITY_CLAUSE,
    ConfidenceLedgerSession,
)
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalPromotionInput,
    CanonicalPromotionReceipt,
    LegacyPromotionStrangleReceipt,
    _gate_outcome_hash,
    _run_canonical_promotion_sequence_for_verification,
    _validate_canonical_promotion_receipt_for_verification,
    admit_canonical_promotion_receipt_for_comparison,
    confidence_risk_scope_for_problem,
)
from tools.quality.validation import layer3_gy_n9_comparison_custody as comparison_owner
from tools.quality.validation import layer3_gy_n9_contract_inputs as input_owner


@dataclass(frozen=True, slots=True)
class _PromotionProducerBindings:
    """Facade-owned callbacks for patch-compatible promotion construction."""

    confidence_ledger_session: type[ConfidenceLedgerSession]
    behavioral_mutations: Callable[
        [dict[str, Any], GyComparisonProjectionPlan], list[dict[str, Any]]
    ]
    source_flip_mutation_ids: tuple[str, ...]


def _run_with_isolated_confidence_ledger(
    repo_root: Path,
    *,
    scenario_id: str,
    promotion_input: CanonicalPromotionInput,
    produce_om01_witness: bool = False,
    bindings: _PromotionProducerBindings,
) -> tuple[CanonicalPromotionReceipt, GyComparisonAdmission, dict[str, Any] | None]:
    """Replay one synthetic scenario against a fresh deterministic N11 scope."""

    risk_scope = confidence_risk_scope_for_problem(promotion_input.design_problem_binding)
    with TemporaryDirectory(prefix=f"gy-n9-{scenario_id}-") as temp_dir:
        state_root = Path(temp_dir)
        session = bindings.confidence_ledger_session._for_verification(
            repo_root,
            risk_scope=risk_scope,
            artifact_store=FileSystemCAS(state_root / "cas"),
            state_root=state_root / "state",
        )
        receipt = _run_canonical_promotion_sequence_for_verification(
            promotion_input,
            confidence_ledger_session=session,
        )
        admission = admit_canonical_promotion_receipt_for_comparison(
            receipt,
            repo_root=repo_root,
            confidence_ledger_session=session,
        )
        witness = (
            _live_om01_witness(repo_root, receipt=receipt, session=session)
            if produce_om01_witness
            else None
        )
        return receipt, admission, witness


def _live_om01_witness(
    repo_root: Path,
    *,
    receipt: CanonicalPromotionReceipt,
    session: ConfidenceLedgerSession,
) -> dict[str, Any]:
    """Remove one decisive row and run the authority validator before session close."""

    targets = [
        row
        for row in receipt.obligations
        if row.obligation_role == "decisive_predicate"
        and row.source_obligation_ref.endswith("#transport_wmr_hash_equals_receipt_wmr_hash")
    ]
    if len(targets) != 1:
        raise ValueError("om01_decisive_obligation_target_denominator_mismatch")
    target = targets[0]
    obligations = tuple(
        row
        for row in receipt.obligations
        if row.obligation_instance_id != target.obligation_instance_id
    )
    removed_count = len(receipt.obligations) - len(obligations)
    class_rows = tuple(row for row in obligations if row.obligation_role == "class_gate")
    class_total = tuple(row.obligation_class for row in class_rows) == tuple(
        PromotionObligationClass
    )
    mutated = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
        }
    )
    authority_issues = _validate_canonical_promotion_receipt_for_verification(
        mutated,
        repo_root=repo_root,
        confidence_ledger_session=session,
    )
    expected_issue = {
        "code": "decisive_obligation_omitted",
        "obligation_instance_id": target.obligation_instance_id,
    }
    authority_red = authority_issues == (expected_issue,)
    if removed_count != 1 or not class_total or not authority_red:
        raise ValueError("om01_live_authority_witness_failed")
    return {
        "mutation_id": "om_01_decisive_obligation_omission",
        "removed_obligation_role": target.obligation_role,
        "removed_source_obligation_ref": target.source_obligation_ref,
        "removed_obligation_instance_id": target.obligation_instance_id,
        "removed_instance_count": removed_count,
        "class_denominator_status": "green",
        "class_denominator_count": len(class_rows),
        "authority_status": "red",
        "authority_issue_codes": [str(item["code"]) for item in authority_issues],
        "authority_issues": list(authority_issues),
        "verification_session_provenance": session.authority_provenance,
    }


def _build_payload_with_comparison_plan(
    repo_root: Path,
    *,
    bindings: _PromotionProducerBindings,
) -> tuple[dict[str, Any], GyComparisonProjectionPlan]:
    """Build N9 plus the ephemeral owner-bound comparison plan."""

    started = time.monotonic()
    contract_input = input_owner._promotion_input()
    (
        contract_refusal,
        contract_refusal_admission,
        obligation_instance_mutation_witness,
    ) = _run_with_isolated_confidence_ledger(
        repo_root,
        scenario_id="contract-lane-anytime-refusal",
        promotion_input=contract_input,
        produce_om01_witness=True,
        bindings=bindings,
    )
    production_shadow, production_shadow_admission, _ = _run_with_isolated_confidence_ledger(
        repo_root,
        scenario_id="production-honest-shadow",
        promotion_input=contract_input.model_copy(
            update={
                "candidate_summary": input_owner._summary(
                    current_valid=False,
                    grounding_status="grounded_shadow",
                ),
                "grounding_decision_certificate": None,
                "credal_reference": None,
            }
        ),
        bindings=bindings,
    )
    non_promotable, non_promotable_admission, _ = _run_with_isolated_confidence_ledger(
        repo_root,
        scenario_id="non-promotable-contract-stamp",
        promotion_input=contract_input,
        bindings=bindings,
    )
    payload: dict[str, Any] = {
        "schema_version": comparison_owner._CONTRACT_SCHEMA_VERSION,
        "synthetic": True,
        "proof_input_strangle": input_owner._proof_input_strangle(
            consumed=contract_input.grounding_decision_certificate,
            reference=contract_input.credal_reference,
        ),
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
            comparison_owner._CREDAL_REFERENCE_SOURCE,
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
        "obligation_denominator": comparison_owner._obligation_denominator(),
        "obligation_instance_mutation_witness": obligation_instance_mutation_witness,
        "scope_insufficient_promotion_policy": comparison_owner._scope_insufficient_promotion_policy(),
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
            "mutation_ids": list(bindings.source_flip_mutation_ids),
        },
    }
    plan = build_gy_comparison_projection_plan(
        payload,
        admissions=(
            contract_refusal_admission,
            production_shadow_admission,
            non_promotable_admission,
        ),
    )
    payload["behavioral_mutations"] = bindings.behavioral_mutations(payload, plan)
    payload["capture_wall_time_seconds"] = round(time.monotonic() - started, 6)
    comparison_owner._set_comparison_identity(payload, plan)
    payload["contract_content_hash"] = comparison_owner._contract_content_hash(payload)
    return payload, plan
