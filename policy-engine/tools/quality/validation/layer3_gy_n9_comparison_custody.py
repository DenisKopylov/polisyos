"""Own frozen GY-N9 comparison identity and registered epoch reissue checks.

The canonical promotion and confidence-ledger authorities remain in
``polisyos.runtime.quality.promotion_sequence`` and
``polisyos.runtime.quality.confidence_ledger``. The compatibility facade supplies
current callbacks; payload production, typed inputs, and mutation probes live in
the sibling ``layer3_gy_n9_contract``, ``layer3_gy_n9_contract_inputs``, and
``layer3_gy_n9_promotion_mutations`` owners.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.pdc import (
    GY_COMPARISON_PROJECTION_LEGACY_SCHEMA_VERSION,
    GY_COMPARISON_PROJECTION_SCHEMA_VERSION,
    GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
    GY_VERIFICATION_COMPARISON_LEGACY_RULE_VERSION,
    GY_VERIFICATION_COMPARISON_RULE_VERSION,
    GyComparisonProjectionPlan,
    PromotionObligationClass,
    build_gy_comparison_projection_plan_from_manifest,
    gy_comparison_content_hash,
    gy_content_hash,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingDecisionCertificate,
    recompute_grounding_decision_content_hash,
)
from polisyos.runtime.quality.promotion_sequence import (
    CANONICAL_PROMOTION_VERIFICATION_COMPARISON_HISTORY_RULE,
    CANONICAL_PROMOTION_VERIFICATION_COMPARISON_V6_HISTORY_RULE,
    CanonicalPromotionReceipt,
    canonical_promotion_verification_comparison_owner_rule_registry,
)
from tools.quality.validation.layer3_gy_n9_contract_inputs import (
    _credal_reference,
    _proof_input_strangle,
)

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_promotion_contract.json"
_CONTRACT_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.n9_promotion_contract.v2"
_CREDAL_REFERENCE_SOURCE = "src/polisyos/runtime/quality/credal_reference.py"
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"capture_wall_time_seconds", "contract_content_hash"}
_COMPARISON_IDENTITY_FIELDS = {
    "comparison_admission_manifest",
    "comparison_content_hash",
    "comparison_projection_schema_version",
    "comparison_rule_version",
}
_N9_V6_EPOCH = "policyos.policy_design_case.layer3_gy.n9_promotion.v6"
_N9_V8_EPOCH = "policyos.policy_design_case.layer3_gy.n9_promotion.v8"
_N9_V6_SCOPE_RULE = "polisyos.policy_design_case.layer3_gy.n9_obligation_scope.v3"
_N9_V6_MEASUREMENT_OWNER = (
    "polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer.produce_from_catalog"
)


class _PromotionContractReconciliationDriftError(ValueError):
    """A completed live replay rejected frozen comparison custody."""

    def __init__(self, code: str, *, details: dict[str, Any]) -> None:
        super().__init__(code)
        self.code = code
        self.details = details


@dataclass(frozen=True, slots=True)
class _ComparisonCallbacks:
    """Current facade callbacks used by fenced comparison reconciliation."""

    output_path: str
    is_authorized_corr_input_epoch_reissue: Callable[
        [dict[str, Any], dict[str, Any], GyComparisonProjectionPlan], bool
    ]
    is_authorized_credal_input_epoch_reissue: Callable[
        [dict[str, Any], dict[str, Any], GyComparisonProjectionPlan], bool
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


def _comparison_content_hash(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL | _COMPARISON_IDENTITY_FIELDS
    }
    return gy_comparison_content_hash(
        stable,
        comparison_plan=plan,
    )


def _reconcile_frozen_contract(
    repo_root: Path,
    live: dict[str, Any],
    plan: GyComparisonProjectionPlan,
    *,
    callbacks: _ComparisonCallbacks,
) -> dict[str, Any]:
    path = repo_root / callbacks.output_path
    if not path.is_file():
        return live
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen.get("contract_content_hash") != _contract_content_hash(frozen):
        raise ValueError("promotion_legacy_contract_content_hash_drift")
    if not _frozen_comparison_identity_admissible(frozen, plan):
        raise _PromotionContractReconciliationDriftError(
            "promotion_comparison_admission_manifest_drift",
            details={
                "stage": "frozen_identity",
                "frozen_manifest": frozen.get("comparison_admission_manifest"),
                "live_manifest": plan.manifest,
                "frozen_comparison_identity": {
                    field: frozen.get(field) for field in _COMPARISON_IDENTITY_FIELDS
                },
                "frozen_comparison_content_hash": frozen.get("comparison_content_hash"),
            },
        )
    if frozen.get("comparison_admission_manifest") not in (None, plan.manifest):
        v6_source_scope_reissue = _is_authorized_v6_source_scope_epoch_reissue(
            frozen, live, plan, callbacks=callbacks
        )
        if v6_source_scope_reissue:
            return live
        v3_to_v6_reissue = _is_authorized_v3_to_v6_comparison_reissue(frozen, live, plan.manifest)
        if not v3_to_v6_reissue:
            receipt_keys = (
                "contract_lane_anytime_refusal",
                "production_honest_shadow",
                "non_promotable_contract_stamp",
            )
            raise _PromotionContractReconciliationDriftError(
                "promotion_comparison_admission_manifest_drift",
                details={
                    "stage": "unauthorized_manifest_epoch_transition",
                    "frozen_manifest": frozen.get("comparison_admission_manifest"),
                    "live_manifest": plan.manifest,
                    "frozen_receipt_schema_versions": {
                        key: (frozen.get(key) or {}).get("schema_version") for key in receipt_keys
                    },
                    "live_receipt_schema_versions": {
                        key: (live.get(key) or {}).get("schema_version") for key in receipt_keys
                    },
                    "authorized_transition_predicates": {
                        "v6_source_scope_reissue": v6_source_scope_reissue,
                        "v3_to_v6_comparison_reissue": v3_to_v6_reissue,
                    },
                    "live_source_modules": live.get("source_modules", []),
                },
            )
        return live
    if callbacks.is_authorized_credal_input_epoch_reissue(frozen, live, plan):
        return live
    if callbacks.is_authorized_corr_input_epoch_reissue(frozen, live, plan):
        return live
    identity_fields = _COMPARISON_IDENTITY_FIELDS | {"contract_content_hash"}
    frozen_body = {key: value for key, value in frozen.items() if key not in identity_fields}
    live_body = {key: value for key, value in live.items() if key not in identity_fields}
    reconciled = plan.preserve_admitted_blocks(frozen_body, live_body)
    if not isinstance(reconciled, dict):  # pragma: no cover - mapping inputs
        raise ValueError("promotion_contract_comparison_projection_invalid")
    _set_comparison_identity(reconciled, plan)
    reconciled["contract_content_hash"] = _contract_content_hash(reconciled)
    return reconciled


def _frozen_comparison_identity_admissible(
    frozen: dict[str, Any],
    live_plan: GyComparisonProjectionPlan,
) -> bool:
    """Accept only absent/current or self-validating registered comparison custody."""

    manifest = frozen.get("comparison_admission_manifest")
    if manifest in (None, live_plan.manifest):
        return True
    comparison_identity = (
        frozen.get("comparison_projection_schema_version"),
        frozen.get("comparison_rule_version"),
    )
    if comparison_identity not in {
        (
            GY_COMPARISON_PROJECTION_LEGACY_SCHEMA_VERSION,
            GY_VERIFICATION_COMPARISON_LEGACY_RULE_VERSION,
        ),
        (
            GY_COMPARISON_PROJECTION_SCHEMA_VERSION,
            GY_VERIFICATION_COMPARISON_RULE_VERSION,
        ),
    }:
        return False
    try:
        legacy_plan = build_gy_comparison_projection_plan_from_manifest(
            frozen,
            manifest=manifest,
            owner_rule_registry=(canonical_promotion_verification_comparison_owner_rule_registry()),
        )
    except ValueError:
        return False
    return frozen.get("comparison_content_hash") == _comparison_content_hash(
        frozen,
        legacy_plan,
    )


def _is_authorized_corr_input_epoch_reissue(
    frozen: dict[str, Any],
    live: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> bool:
    """Reissue only the governed CG2 input epoch and its measured dependencies.

    Historical inputs are retired, never asserted to be equivalent to the new
    producer output. Every other governing field remains under its typed owner.
    """
    if (
        frozen.get("schema_version") != GY_PROMOTION_SEQUENCE_SCHEMA_VERSION
        or live.get("schema_version") != _CONTRACT_SCHEMA_VERSION
        or frozen.get("comparison_admission_manifest") != plan.manifest
        or live.get("comparison_admission_manifest") != plan.manifest
        or any(
            frozen.get(field) != live.get(field)
            for field in _COMPARISON_IDENTITY_FIELDS - {"comparison_content_hash"}
        )
        or frozen.get("comparison_content_hash") != _comparison_content_hash(frozen, plan)
        or "proof_input_strangle" in frozen
        or "synthetic" in frozen
        or live.get("synthetic") is not True
        or live.get("source_modules")
        != [*frozen.get("source_modules", ()), _CREDAL_REFERENCE_SOURCE]
    ):
        return False
    excluded = _COMPARISON_IDENTITY_FIELDS | _CONTENT_HASH_EXCLUDED_TOP_LEVEL
    before = plan.project({key: value for key, value in frozen.items() if key not in excluded})
    after = plan.project({key: value for key, value in live.items() if key not in excluded})
    transitioned = False
    try:
        for entry in plan.entries:
            old, new = before, after
            old_record, new_record = frozen, live
            for segment in entry.path:
                old, new = old[segment], new[segment]
                old_record, new_record = old_record[segment], new_record[segment]
            previous = old["owner_projection"]["grounding_decision_certificate"]
            current = new["owner_projection"]["grounding_decision_certificate"]
            if previous is None and current is None:
                if old != new:
                    return False
                continue
            old_input = GroundingDecisionCertificate.model_validate(
                old_record["owner_projection"]["grounding_decision_certificate"]
            )
            new_input = GroundingDecisionCertificate.model_validate(
                new_record["owner_projection"]["grounding_decision_certificate"]
            )
            if (
                old_input.schema_version != "policyos.runtime.grounding_decision_certificate.v1"
                or new_input.schema_version != "policyos.runtime.grounding_decision_certificate.v2"
                or old_input.authority_scope != "contract_testing"
                or new_input.authority_scope != "contract_testing"
                or old_input.production_promotable
                or new_input.production_promotable
                or old_input.content_hash != recompute_grounding_decision_content_hash(old_input)
                or new_input.content_hash != recompute_grounding_decision_content_hash(new_input)
                or old["cg2_resolution_reason"] != "non_production_anchor_scope"
                or new["cg2_resolution_reason"] != "synthetic_input_cannot_grant_authority"
            ):
                return False
            packet = _proof_input_strangle(consumed=new_input, reference=_credal_reference())
            if not packet["default_flipped"] or live["proof_input_strangle"] != packet:
                return False
            old_reference = old["owner_projection"]["credal_reference"]
            new_reference = new["owner_projection"]["credal_reference"]
            if (
                old_reference["schema_version"]
                not in {
                    "policyos.runtime.grounding_credal_reference.v1",
                    "policyos.runtime.grounding_credal_reference.v2",
                }
                or new_reference["schema_version"]
                != "policyos.runtime.grounding_credal_reference.v2"
                or old_reference["reference_hash"] != old_input.reference_hash
                or old_reference["reference_epoch"] != old_input.reference_epoch
                or new_reference["reference_hash"] != new_input.reference_hash
                or new_reference["reference_epoch"] != new_input.reference_epoch
            ):
                return False
            old["owner_projection"]["grounding_decision_certificate"] = current
            for field in ("schema_version", "reference_hash", "reference_epoch"):
                old_reference[field] = new_reference[field]
            old["cg2_resolution_reason"] = new["cg2_resolution_reason"]
            for obligation in old["obligations"]:
                obligation["evidence_refs"] = [
                    new_input.certificate_id if ref == old_input.certificate_id else ref
                    for ref in obligation["evidence_refs"]
                ]
            transitioned = True
        before["schema_version"] = after["schema_version"]
        before["synthetic"] = after["synthetic"]
        before["proof_input_strangle"] = after["proof_input_strangle"]
        before["source_modules"] = after["source_modules"]
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        return False
    return transitioned and before == after


def _is_authorized_credal_input_epoch_reissue(
    frozen: dict[str, Any],
    live: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> bool:
    """Admit only the governed v1-to-v2 credal input transition after live replay.

    Every receipt is projected by its existing typed owner. Only the explicit
    nested input epoch may differ; all other governing receipt and envelope
    values retain the ordinary comparison semantics. The returned live record
    is newly owner-produced, never a restamp of the historical custody bytes.
    """

    if (
        frozen.get("comparison_admission_manifest") != plan.manifest
        or live.get("comparison_admission_manifest") != plan.manifest
        or any(
            frozen.get(field) != live.get(field)
            for field in _COMPARISON_IDENTITY_FIELDS - {"comparison_content_hash"}
        )
        or frozen.get("comparison_content_hash") != _comparison_content_hash(frozen, plan)
    ):
        return False
    identity_fields = _COMPARISON_IDENTITY_FIELDS | {"contract_content_hash"}
    frozen_body = {key: value for key, value in frozen.items() if key not in identity_fields}
    live_body = {key: value for key, value in live.items() if key not in identity_fields}
    frozen_projection = plan.project(frozen_body)
    live_projection = plan.project(live_body)
    transitioned = False
    try:
        for entry in plan.entries:
            previous: Any = frozen_body
            current: Any = live_body
            projected_previous: Any = frozen_projection
            for segment in entry.path:
                previous = previous[segment]
                current = current[segment]
                projected_previous = projected_previous[segment]
            previous_receipt = entry.projector(previous)
            current_receipt = entry.projector(current)
            previous_reference = previous_receipt["owner_projection"]["credal_reference"]
            current_reference = current_receipt["owner_projection"]["credal_reference"]
            if previous_reference is None and current_reference is None:
                if previous_receipt != current_receipt:
                    return False
                continue
            if (
                previous_reference["schema_version"]
                != "policyos.runtime.grounding_credal_reference.v1"
                or current_reference["schema_version"]
                != "policyos.runtime.grounding_credal_reference.v2"
            ):
                return False
            previous_reference["schema_version"] = current_reference["schema_version"]
            if previous_receipt != current_receipt:
                return False
            projected_previous["owner_projection"]["credal_reference"]["schema_version"] = (
                current_reference["schema_version"]
            )
            transitioned = True
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    return transitioned and frozen_projection == live_projection


def _is_authorized_v3_to_v6_comparison_reissue(
    frozen: dict[str, Any],
    live: dict[str, Any],
    live_plan_manifest: list[dict[str, str]],
) -> bool:
    """Recognize only the one frozen v3-receipt to live v6-receipt reissue."""

    receipt_keys = (
        "contract_lane_anytime_refusal",
        "production_honest_shadow",
        "non_promotable_contract_stamp",
    )
    expected_pointers = {f"/{key}" for key in receipt_keys}

    def receipt_epochs(payload: dict[str, Any]) -> tuple[object, ...]:
        return tuple(
            payload.get(key, {}).get("schema_version")
            if isinstance(payload.get(key), dict)
            else None
            for key in receipt_keys
        )

    frozen_manifest = frozen.get("comparison_admission_manifest")
    live_manifest = live.get("comparison_admission_manifest")
    if not isinstance(frozen_manifest, list) or not isinstance(live_manifest, list):
        return False
    if live_manifest != live_plan_manifest:
        return False
    if {row.get("json_pointer") for row in frozen_manifest if isinstance(row, dict)} != (
        expected_pointers
    ):
        return False
    if {row.get("json_pointer") for row in live_manifest if isinstance(row, dict)} != (
        expected_pointers
    ):
        return False
    return (
        len(frozen_manifest) == len(receipt_keys)
        and len(live_manifest) == len(receipt_keys)
        and frozen.get("comparison_projection_schema_version")
        == GY_COMPARISON_PROJECTION_SCHEMA_VERSION
        and frozen.get("comparison_rule_version") == GY_VERIFICATION_COMPARISON_RULE_VERSION
        and live.get("comparison_projection_schema_version")
        == GY_COMPARISON_PROJECTION_SCHEMA_VERSION
        and live.get("comparison_rule_version") == GY_VERIFICATION_COMPARISON_RULE_VERSION
        and receipt_epochs(frozen) == (GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,) * len(receipt_keys)
        and receipt_epochs(live)
        == ("policyos.policy_design_case.layer3_gy.n9_promotion.v6",) * len(receipt_keys)
        and {row.get("owner_rule") for row in frozen_manifest if isinstance(row, dict)}
        == {CANONICAL_PROMOTION_VERIFICATION_COMPARISON_HISTORY_RULE}
        and {row.get("owner_rule") for row in live_manifest if isinstance(row, dict)}
        == {CANONICAL_PROMOTION_VERIFICATION_COMPARISON_V6_HISTORY_RULE}
    )


def _n9_v6_scope_hash(receipt: Any) -> str:
    """Recompute the frozen v6 scope formula from its typed, complete owner input."""
    owner = receipt.owner_projection
    return gy_content_hash(
        {
            "rule_version": _N9_V6_SCOPE_RULE,
            "promotion_rule_version": _N9_V6_EPOCH,
            "design_problem_id": owner.design_problem_binding.design_problem_id,
            "problem_content_hash": owner.design_problem_binding.problem_content_hash,
            "candidate_id": owner.candidate_summary.candidate_id,
            "candidate_content_hash": owner.candidate_summary.content_hash,
            "operation_invocation_id": owner.operation_invocation_id,
        }
    )


def _translate_n9_semantic_ledger_epoch(value: dict[str, Any]) -> dict[str, Any]:
    """Recompute hash descendants of one typed rule transition without dropping fields."""
    from polisyos.runtime.quality import confidence_ledger as owner

    previous = owner.N9PromotionSemanticLedgerProjection.model_validate(value)
    if previous.risk_scope.rule_ref != _N9_V6_EPOCH:
        raise ValueError("promotion_reissue_ledger_epoch_invalid")
    scope = owner.ConfidenceRiskBudgetScope.model_validate(
        {**previous.risk_scope.model_dump(mode="json"), "rule_ref": _N9_V8_EPOCH}
    )
    scoped = previous.model_copy(update={"risk_scope": scope, "scope_id": scope.scope_id})
    root_hash = owner._content_hash(
        owner._n9_semantic_ledger_root_values(
            receipt=scoped,
            risk_scope=scope,
        )
    )
    translated_hashes = {previous.root_projection_hash: root_hash}
    events = []
    checks = {}
    for event in previous.events:
        check = event.check.model_dump(mode="json")
        check["filtration_projection_hash"] = translated_hashes[
            event.check.filtration_projection_hash
        ]
        check["claim_execution_projection_hash"] = (
            owner._semantic_claim_execution_projection_hash_from_projection(
                owner.ConfidenceLedgerSemanticCheck.model_validate(check)
            )
        )
        check["check_projection_hash"] = owner._content_hash(
            {key: item for key, item in check.items() if key != "check_projection_hash"}
        )
        values = {
            **event.model_dump(mode="json"),
            "check": check,
            "parent_event_projection_hash": translated_hashes[event.parent_event_projection_hash],
        }
        values["event_projection_hash"] = owner._content_hash(
            {key: item for key, item in values.items() if key != "event_projection_hash"}
        )
        translated = owner.ConfidenceLedgerSemanticEvent.model_validate(values)
        translated_hashes[event.event_projection_hash] = translated.event_projection_hash
        events.append(translated.model_dump(mode="json"))
        checks[translated.check.request_key] = translated.check.model_dump(mode="json")
    payload = {
        **scoped.model_dump(mode="json"),
        "root_projection_hash": root_hash,
        "events": events,
        "checks": [checks[key] for key in sorted(checks)],
        "head_event_projection_hash": translated_hashes[previous.head_event_projection_hash],
    }
    payload["projection_hash"] = owner._content_hash(
        {key: item for key, item in payload.items() if key != "projection_hash"}
    )
    return owner.N9PromotionSemanticLedgerProjection.model_validate(payload).model_dump(mode="json")


def _translate_n9_v6_receipt_epoch(
    value: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, tuple[str, str, str]]]:
    """Translate only the verified v6 source/scope derivation into current comparison custody."""
    from polisyos.pdc import PromotionObligationDraft, PromotionObligationRecord
    from polisyos.runtime.quality import confidence_ledger as ledger_owner
    from polisyos.runtime.quality import promotion_sequence as owner

    previous = owner.parse_canonical_promotion_history_receipt(value)
    if previous.historical_projection() != value:
        raise ValueError("promotion_reissue_historical_receipt_incomplete")
    if previous.schema_version != _N9_V6_EPOCH or previous.promoted or previous.consumer_promotable:
        raise ValueError("promotion_reissue_receipt_epoch_or_authority_invalid")
    historical_owner = previous.owner_projection
    historical_summary = historical_owner.candidate_summary.model_dump(mode="json")
    current_summary = owner.CandidateSummary.model_validate(
        {
            **historical_summary,
            "source_content_hash": None,
            "grounding_issue_codes": [],
            "grounding_report_ref": None,
        }
    )
    current_owner_payload = historical_owner.model_dump(mode="json")
    current_owner_payload["schema_version"] = (
        owner.CANONICAL_PROMOTION_OWNER_PROJECTION_SCHEMA_VERSION
    )
    current_owner_payload["candidate_summary"] = current_summary.model_dump(mode="json")
    current_owner_payload.pop("projection_hash", None)
    current_owner_payload["projection_hash"] = gy_content_hash(current_owner_payload)
    current_owner = owner.CanonicalPromotionOwnerProjection.model_validate(current_owner_payload)
    current_input = owner._input_from_owner_projection(current_owner, repo_root=None)
    if current_input.schema_version != _N9_V8_EPOCH or current_input.producer_root_refs:
        raise ValueError("promotion_reissue_requires_unbridged_contract_replay")
    old_scope_hash = _n9_v6_scope_hash(previous)
    old_drafts = [
        PromotionObligationDraft.model_validate(
            row.model_dump(
                mode="json",
                exclude=owner._PROMOTION_OBLIGATION_IDENTITY_FIELDS,
            )
        )
        for row in previous.obligations
        if row.obligation_role == "class_gate"
    ]
    new_drafts = []
    for draft in old_drafts:
        if draft.obligation_class == PromotionObligationClass.MEASUREMENT:
            if draft.owner_ref != _N9_V6_MEASUREMENT_OWNER:
                raise ValueError("promotion_reissue_measurement_source_invalid")
            draft = draft.model_copy(update={"owner_ref": owner._MEASUREMENT_ROOT_OWNER_REF})
        new_drafts.append(draft)
    current_rows = owner._finalize_obligations(current_input, new_drafts)
    if len(current_rows) != len(previous.obligations):
        raise ValueError("promotion_reissue_obligation_identity_denominator_drift")
    identity_map = {}
    for old, current in zip(previous.obligations, current_rows, strict=True):
        if (old.obligation_role, old.source_obligation_ref) != (
            current.obligation_role,
            current.source_obligation_ref,
        ):
            raise ValueError("promotion_reissue_obligation_order_drift")
        old_draft = PromotionObligationDraft.model_validate(
            old.model_dump(
                mode="json",
                exclude=owner._PROMOTION_OBLIGATION_IDENTITY_FIELDS,
            )
        )
        if old.obligation_role == "class_gate":
            source_ref, source_hash = owner._class_gate_source(old_draft)
        else:
            source_ref = current.source_obligation_ref
            source_hash = current.source_obligation_content_hash
            if source_ref == f"{owner.PROMOTION_SEQUENCE_REF}#effective_independence":
                resolution = owner._evidence_resolution(None, "effective_independence")
                source_hash = gy_content_hash(
                    {
                        "rule_version": _N9_V6_SCOPE_RULE,
                        "source_obligation_ref": source_ref,
                        "predicate_provenance": resolution.predicate_class,
                        "capability_state": resolution.status,
                        "owner_ref": owner._effective_independence_obligation(resolution).owner_ref,
                    }
                )
            current_draft = PromotionObligationDraft.model_validate(
                current.model_dump(
                    mode="json",
                    exclude=owner._PROMOTION_OBLIGATION_IDENTITY_FIELDS,
                )
            )
            if old_draft != current_draft:
                raise ValueError("promotion_reissue_decisive_predicate_drift")
        expected_old = PromotionObligationRecord.from_draft(
            old_draft,
            obligation_role=old.obligation_role,
            source_obligation_ref=source_ref,
            source_obligation_content_hash=source_hash,
            instance_scope_content_hash=old_scope_hash,
        )
        if old != expected_old:
            raise ValueError("promotion_reissue_historical_obligation_derivation_invalid")
        identity_map[old.obligation_instance_id] = (
            current.obligation_instance_id,
            old.source_obligation_ref,
            old.obligation_role,
        )
    payload = previous.historical_projection()
    payload["schema_version"] = _N9_V8_EPOCH
    payload["owner_projection"] = current_owner.model_dump(mode="json")
    payload["obligations"] = [row.model_dump(mode="json") for row in current_rows]
    rules = payload["computed_authority_boundary"]["rule_version_refs"]
    if _N9_V6_EPOCH not in rules:
        raise ValueError("promotion_reissue_boundary_epoch_missing")
    payload["computed_authority_boundary"]["rule_version_refs"] = [
        _N9_V8_EPOCH if rule == _N9_V6_EPOCH else rule for rule in rules
    ]
    certificate = payload["confidence_ledger_projection"]
    if certificate["risk_scope"]["rule_ref"] != _N9_V6_EPOCH:
        raise ValueError("promotion_reissue_certificate_epoch_invalid")
    certificate["risk_scope"]["rule_ref"] = _N9_V8_EPOCH
    certificate["projection_hash"] = ledger_owner._content_hash(
        {key: item for key, item in certificate.items() if key != "projection_hash"}
    )
    payload["confidence_ledger_semantic_projection"] = _translate_n9_semantic_ledger_epoch(
        payload["confidence_ledger_semantic_projection"]
    )
    payload["gate_outcome_hash"] = owner._gate_outcome_hash(
        current_rows,
        open_world_gate=current_input.open_world_gate,
        epoch_validity_projection=current_input.epoch_validity_projection,
    )
    current = owner.CanonicalPromotionReceipt.model_validate(payload)
    return current.model_dump(mode="json"), identity_map


def _is_authorized_v6_source_scope_epoch_reissue(
    frozen: dict[str, Any],
    live: dict[str, Any],
    plan: GyComparisonProjectionPlan,
    *,
    callbacks: _ComparisonCallbacks,
) -> bool:
    """Reconcile the entire admitted set through exact typed epoch derivations."""
    if (
        "comparison_admission_manifest" not in frozen
        or not isinstance(frozen["comparison_admission_manifest"], list)
        or live.get("comparison_admission_manifest") != plan.manifest
    ):
        return False
    expected_manifest = [
        {**entry, "owner_rule": CANONICAL_PROMOTION_VERIFICATION_COMPARISON_V6_HISTORY_RULE}
        for entry in plan.manifest
    ]
    if frozen["comparison_admission_manifest"] != expected_manifest:
        return False
    if any(
        frozen.get(field) != live.get(field)
        for field in (
            "comparison_projection_schema_version",
            "comparison_rule_version",
        )
    ):
        return False
    try:
        historical_plan = build_gy_comparison_projection_plan_from_manifest(
            frozen,
            manifest=frozen["comparison_admission_manifest"],
            owner_rule_registry=canonical_promotion_verification_comparison_owner_rule_registry(),
        )
        if frozen.get("comparison_content_hash") != _comparison_content_hash(
            frozen, historical_plan
        ):
            return False
        # The earlier S3 input epoch is a separately governed transition. Keep
        # its registered v6 owner and its exact predicate when composing it with
        # this source/scope epoch; never normalize credal fields in the new one.
        source = frozen
        credal_transition = copy.deepcopy(frozen)
        has_previous_credal = False
        for entry in historical_plan.entries:
            target: Any = credal_transition
            for segment in entry.path:
                target = target[segment]
            reference = target["owner_projection"]["credal_reference"]
            if reference is not None and reference["schema_version"] == (
                "policyos.runtime.grounding_credal_reference.v1"
            ):
                reference["schema_version"] = "policyos.runtime.grounding_credal_reference.v2"
                projection = target["owner_projection"]
                projection["projection_hash"] = gy_content_hash(
                    {key: item for key, item in projection.items() if key != "projection_hash"}
                )
                has_previous_credal = True
        if has_previous_credal:
            _set_comparison_identity(credal_transition, historical_plan)
            credal_transition["contract_content_hash"] = _contract_content_hash(credal_transition)
            if not callbacks.is_authorized_credal_input_epoch_reissue(
                frozen, credal_transition, historical_plan
            ):
                return False
            source = credal_transition
        excluded = _CONTENT_HASH_EXCLUDED_TOP_LEVEL | _COMPARISON_IDENTITY_FIELDS
        previous_body = {key: value for key, value in source.items() if key not in excluded}
        current_body = {key: value for key, value in live.items() if key not in excluded}
        translated_body = copy.deepcopy(previous_body)
        current_projection = plan.project(current_body)
        identity_map = {}
        for entry in historical_plan.entries:
            raw: Any = previous_body
            target: Any = translated_body
            for segment in entry.path[:-1]:
                raw = raw[segment]
                target = target[segment]
            projected, identities = _translate_n9_v6_receipt_epoch(raw[entry.path[-1]])
            target[entry.path[-1]] = projected
            for before, after in identities.items():
                if before in identity_map and identity_map[before] != after:
                    return False
                identity_map[before] = after
        witness = translated_body["obligation_instance_mutation_witness"]
        old_id = witness["removed_obligation_instance_id"]
        new_id, source_ref, role = identity_map[old_id]
        if (
            witness["removed_source_obligation_ref"] != source_ref
            or witness["removed_obligation_role"] != role
            or witness["authority_issues"]
            != [
                {
                    "code": "decisive_obligation_omitted",
                    "obligation_instance_id": old_id,
                }
            ]
        ):
            return False
        witness["removed_obligation_instance_id"] = new_id
        witness["authority_issues"][0]["obligation_instance_id"] = new_id
        # The registered comparison plan owns both typed receipt projection and
        # its outer operational-time semantics. Apply it to the entire translated
        # body, just as for the actual live producer, rather than inserting an
        # already projected receipt after that outer pass has completed.
        if plan.project(translated_body) == current_projection:
            return True

        # The stored v6 source/scope epoch and the live CG2 input epoch are two
        # independently governed transitions from this same frozen base. First
        # derive the complete v8 receipt/scope projection above; then present that
        # exact intermediate to the existing CORR verifier. It may authorize only
        # its typed certificate/reference, reason, source-module and strangle
        # changes, while comparing the remaining full projected body. Neither
        # transition can stand in for the other, and any unrelated drift stays red.
        intermediate = copy.deepcopy(source)
        intermediate.update(translated_body)
        _set_comparison_identity(intermediate, plan)
        intermediate["contract_content_hash"] = _contract_content_hash(intermediate)
        return callbacks.is_authorized_corr_input_epoch_reissue(intermediate, live, plan)
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def _set_comparison_identity(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> None:
    payload["comparison_admission_manifest"] = plan.manifest
    payload["comparison_projection_schema_version"] = GY_COMPARISON_PROJECTION_SCHEMA_VERSION
    payload["comparison_rule_version"] = GY_VERIFICATION_COMPARISON_RULE_VERSION
    payload["comparison_content_hash"] = _comparison_content_hash(payload, plan)


def _comparison_identity_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if (
        payload.get("comparison_projection_schema_version")
        != GY_COMPARISON_PROJECTION_SCHEMA_VERSION
    ):
        issues.append({"code": "comparison_projection_schema_version_invalid"})
    if payload.get("comparison_rule_version") != GY_VERIFICATION_COMPARISON_RULE_VERSION:
        issues.append({"code": "comparison_rule_version_invalid"})
    manifest = payload.get("comparison_admission_manifest")
    try:
        plan = build_gy_comparison_projection_plan_from_manifest(
            payload,
            manifest=manifest,
            owner_rule_registry=(canonical_promotion_verification_comparison_owner_rule_registry()),
        )
    except ValueError as exc:
        issues.append({"code": "comparison_admission_manifest_invalid", "error": str(exc)})
    else:
        if payload.get("comparison_content_hash") != _comparison_content_hash(payload, plan):
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
