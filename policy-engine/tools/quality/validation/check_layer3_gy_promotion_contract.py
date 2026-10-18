#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N9 canonical promotion contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

# Completed-work terminals per mode, owned here because this module's own return mapping is the
# only place that knows them. ``corrupt_field_drift_check`` reports "fail" when the drift was
# DETECTED (the correct outcome) and "pass" when it was missed, while ``main`` exits
# ``0 if status == "pass" else 1`` -- so this lane's healthy terminal is exit 1 and its DEFECT
# terminal is exit 0. The default {0} would admit exactly the failures and reject the good runs.
TIMING_HEALTHY_TERMINAL_EXIT_CODES: dict[str, list[int]] = {
    "corrupt-field-drift-check": [1],
}

import argparse
import copy
import json
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.pdc import (
    GY_COMPARISON_PROJECTION_LEGACY_SCHEMA_VERSION,
    GY_COMPARISON_PROJECTION_SCHEMA_VERSION,
    GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
    GY_VERIFICATION_COMPARISON_LEGACY_RULE_VERSION,
    GY_VERIFICATION_COMPARISON_RULE_VERSION,
    PROMOTION_RISK_CONDITIONALITY_CAVEAT,
    AuthorityBoundary,
    GyComparisonAdmission,
    GyComparisonProjectionPlan,
    PromotionObligationClass,
    build_gy_comparison_projection_plan,
    build_gy_comparison_projection_plan_from_manifest,
    gy_comparison_content_hash,
    gy_content_hash,
)
from polisyos.pdc._impl.layer2_design_search import (
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.confidence_ledger import (
    CONDITIONAL_VALIDITY_CLAUSE,
    ConfidenceLedgerSession,
)
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
    _component_versions,
    _reference_hash,
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
    CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
    CANONICAL_PROMOTION_VERIFICATION_COMPARISON_HISTORY_RULE,
    CANONICAL_PROMOTION_VERIFICATION_COMPARISON_V6_HISTORY_RULE,
    CanonicalPromotionInput,
    CanonicalPromotionReceipt,
    LegacyPromotionStrangleReceipt,
    N9DesignProblemBinding,
    _gate_outcome_hash,
    _run_canonical_promotion_sequence_for_verification,
    _validate_canonical_promotion_receipt_for_verification,
    admit_canonical_promotion_receipt_for_comparison,
    canonical_promotion_verification_comparison_owner_rule_registry,
    confidence_risk_scope_for_problem,
    parse_canonical_promotion_history_receipt,
)
from tools.lib.fs import measure_file_reads, measured_read_bytes
from tools.lib.timing import parse_args_for_timing, run_timed_entrypoint
from tools.quality.validation import layer3_gy_n9_comparison_custody as _comparison_owner
from tools.quality.validation import layer3_gy_n9_contract as _contract_owner
from tools.quality.validation import layer3_gy_n9_contract_inputs as _input_owner
from tools.quality.validation import layer3_gy_n9_promotion_mutations as _mutation_owner

# Keep the facade's historical private import bindings available to repository callers.
_HISTORIC_PRIVATE_IMPORT_BINDINGS = (
    _component_versions,
    _reference_hash,
    _gate_outcome_hash,
    _run_canonical_promotion_sequence_for_verification,
    _validate_canonical_promotion_receipt_for_verification,
)

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_promotion_contract.json"
_CONTRACT_SCHEMA_VERSION = _comparison_owner._CONTRACT_SCHEMA_VERSION
_CREDAL_REFERENCE_SOURCE = _comparison_owner._CREDAL_REFERENCE_SOURCE
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = _comparison_owner._CONTENT_HASH_EXCLUDED_TOP_LEVEL

_COMPARISON_IDENTITY_FIELDS = _comparison_owner._COMPARISON_IDENTITY_FIELDS


_PromotionContractReconciliationDriftError = (
    _comparison_owner._PromotionContractReconciliationDriftError
)


_SOURCE_FLIP_MUTATION_IDS = _mutation_owner._SOURCE_FLIP_MUTATION_IDS
_BEHAVIORAL_MUTATION_IDS = _mutation_owner._BEHAVIORAL_MUTATION_IDS


def _producer_bindings() -> _contract_owner._PromotionProducerBindings:
    return _contract_owner._PromotionProducerBindings(
        confidence_ledger_session=ConfidenceLedgerSession,
        behavioral_mutations=_behavioral_mutations,
        source_flip_mutation_ids=_SOURCE_FLIP_MUTATION_IDS,
    )


def _mutation_callbacks() -> _mutation_owner._MutationCallbacks:
    return _mutation_owner._MutationCallbacks(
        set_comparison_identity=_set_comparison_identity,
        contract_content_hash=_contract_content_hash,
        validate_payload=validate_payload,
    )


def _comparison_callbacks() -> _comparison_owner._ComparisonCallbacks:
    return _comparison_owner._ComparisonCallbacks(
        output_path=OUTPUT_PATH,
        is_authorized_corr_input_epoch_reissue=_is_authorized_corr_input_epoch_reissue,
        is_authorized_credal_input_epoch_reissue=_is_authorized_credal_input_epoch_reissue,
    )


_live_om01_witness = _contract_owner._live_om01_witness
run_source_flip_mutations = _mutation_owner.run_source_flip_mutations
_receipt_from_payload = _mutation_owner._receipt_from_payload
_validate_n11_projection = _mutation_owner._validate_n11_projection
_mutate_ledger_projection = _mutation_owner._mutate_ledger_projection
_mutate_gate_hash = _mutation_owner._mutate_gate_hash
_mutate_fixed_time_refusal = _mutation_owner._mutate_fixed_time_refusal
_mutate_vacuous_scope_pass = _mutation_owner._mutate_vacuous_scope_pass
_mutate_risk_budget = _mutation_owner._mutate_risk_budget
_mutate_conditionality_clause = _mutation_owner._mutate_conditionality_clause
_mutate_strangle = _mutation_owner._mutate_strangle
_SourceFlipReplacement = _mutation_owner._SourceFlipReplacement
_SourceFlipCase = _mutation_owner._SourceFlipCase
_run_source_flip_case = _mutation_owner._run_source_flip_case
_source_flip_cases = _mutation_owner._source_flip_cases
_pytest_probe = _mutation_owner._pytest_probe
_output_tail = _mutation_owner._output_tail
_obligation_denominator = _comparison_owner._obligation_denominator
_scope_insufficient_promotion_policy = _comparison_owner._scope_insufficient_promotion_policy
_contract_content_hash = _comparison_owner._contract_content_hash
_comparison_content_hash = _comparison_owner._comparison_content_hash
_frozen_comparison_identity_admissible = _comparison_owner._frozen_comparison_identity_admissible
_is_authorized_corr_input_epoch_reissue = _comparison_owner._is_authorized_corr_input_epoch_reissue
_is_authorized_credal_input_epoch_reissue = (
    _comparison_owner._is_authorized_credal_input_epoch_reissue
)
_is_authorized_v3_to_v6_comparison_reissue = (
    _comparison_owner._is_authorized_v3_to_v6_comparison_reissue
)
_n9_v6_scope_hash = _comparison_owner._n9_v6_scope_hash
_translate_n9_semantic_ledger_epoch = _comparison_owner._translate_n9_semantic_ledger_epoch
_translate_n9_v6_receipt_epoch = _comparison_owner._translate_n9_v6_receipt_epoch
_set_comparison_identity = _comparison_owner._set_comparison_identity
_comparison_identity_issues = _comparison_owner._comparison_identity_issues
_obligation_detail = _comparison_owner._obligation_detail
_promotion_input = _input_owner._promotion_input
_summary = _input_owner._summary
_value_receipt = _input_owner._value_receipt
_cg2_contract_bind = _input_owner._cg2_contract_bind
_proof_input_strangle = _input_owner._proof_input_strangle
_boundary = _input_owner._boundary
_s6_posture = _input_owner._s6_posture
_s7_posture = _input_owner._s7_posture
_s8_posture = _input_owner._s8_posture
_credal_reference = _input_owner._credal_reference
_operator_edge = _input_owner._operator_edge
_target_edge = _input_owner._target_edge
_lex_edge = _input_owner._lex_edge
_world_slot = _input_owner._world_slot
_policy_slot = _input_owner._policy_slot
_tax_atom = _input_owner._tax_atom
_pure_synonym_probe = _input_owner._pure_synonym_probe
_hash = _input_owner._hash


__all__ = (
    "CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION",
    "CANONICAL_PROMOTION_VERIFICATION_COMPARISON_HISTORY_RULE",
    "CANONICAL_PROMOTION_VERIFICATION_COMPARISON_V6_HISTORY_RULE",
    "CONDITIONAL_VALIDITY_CLAUSE",
    "CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION",
    "GY_COMPARISON_PROJECTION_LEGACY_SCHEMA_VERSION",
    "GY_COMPARISON_PROJECTION_SCHEMA_VERSION",
    "GY_PROMOTION_SEQUENCE_SCHEMA_VERSION",
    "GY_VERIFICATION_COMPARISON_LEGACY_RULE_VERSION",
    "GY_VERIFICATION_COMPARISON_RULE_VERSION",
    "OUTPUT_PATH",
    "PROMOTION_RISK_CONDITIONALITY_CAVEAT",
    "TIMING_HEALTHY_TERMINAL_EXIT_CODES",
    "UTC",
    "AdmissibleCompletion",
    "Any",
    "AuthorityBoundary",
    "CandidateSummary",
    "CanonicalPromotionInput",
    "CanonicalPromotionReceipt",
    "ConfidenceLedgerSession",
    "CredalReference",
    "CredalReferenceEdge",
    "DataTrust",
    "FileSystemCAS",
    "GroundingBindGate",
    "GroundingDecisionCertificate",
    "GroundingRelationEngine",
    "GyComparisonAdmission",
    "GyComparisonProjectionPlan",
    "Layer2S6BlindSpotPostureInput",
    "Layer2S7DelegationPostureInput",
    "Layer2S8ValuePostureInput",
    "LegacyPromotionStrangleReceipt",
    "N9DesignProblemBinding",
    "Path",
    "PromotionObligationClass",
    "TemporaryDirectory",
    "ValueCalibrationReceipt",
    "ValueGateReceipt",
    "ValueOuterSet",
    "ValueTransportReceipt",
    "admit_canonical_promotion_receipt_for_comparison",
    "argparse",
    "build_contract_json_for_write",
    "build_gy_comparison_projection_plan",
    "build_gy_comparison_projection_plan_from_manifest",
    "build_payload",
    "canonical_promotion_verification_comparison_owner_rule_registry",
    "confidence_risk_scope_for_problem",
    "copy",
    "corrupt_field_drift_check",
    "dataclass",
    "datetime",
    "declared_outputs",
    "gy_comparison_content_hash",
    "gy_content_hash",
    "json",
    "main",
    "measure_file_reads",
    "measured_read_bytes",
    "parse_args_for_timing",
    "parse_canonical_promotion_history_receipt",
    "recompute_grounding_decision_content_hash",
    "rederive_audit",
    "replace",
    "run_source_flip_mutations",
    "run_timed_entrypoint",
    "subprocess",
    "sys",
    "time",
    "validate",
    "validate_payload",
    "validate_payload_without_mutation_check",
    "write",
)


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _run_with_isolated_confidence_ledger(
    repo_root: Path,
    *,
    scenario_id: str,
    promotion_input: CanonicalPromotionInput,
    produce_om01_witness: bool = False,
) -> tuple[CanonicalPromotionReceipt, GyComparisonAdmission, dict[str, Any] | None]:
    """Replay one synthetic scenario using the current facade session class."""
    return _contract_owner._run_with_isolated_confidence_ledger(
        repo_root,
        scenario_id=scenario_id,
        promotion_input=promotion_input,
        produce_om01_witness=produce_om01_witness,
        bindings=_producer_bindings(),
    )


_live_om01_witness = _contract_owner._live_om01_witness


def build_payload(repo_root: Path) -> dict[str, Any]:
    """Build the frozen N9 payload from Lane-0 contract certificates."""

    payload, _ = _build_payload_with_comparison_plan(repo_root)
    return payload


def _build_payload_with_comparison_plan(
    repo_root: Path,
) -> tuple[dict[str, Any], GyComparisonProjectionPlan]:
    """Build N9 through the private producer while preserving facade injection seams."""
    return _contract_owner._build_payload_with_comparison_plan(
        repo_root,
        bindings=_producer_bindings(),
    )


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a frozen N9 contract payload without live gate re-derivation."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != _CONTRACT_SCHEMA_VERSION:
        issues.append({"code": "schema_version_drift"})
    if payload.get("synthetic") is not True:
        issues.append({"code": "synthetic_proof_marker_drift"})
    if payload.get("obligation_denominator") != _obligation_denominator():
        issues.append({"code": "obligation_denominator_drift"})
    witness = payload.get("obligation_instance_mutation_witness")
    witness_valid = isinstance(witness, dict)
    if witness_valid:
        removed_id = witness.get("removed_obligation_instance_id")
        witness_valid = bool(
            witness.get("mutation_id") == "om_01_decisive_obligation_omission"
            and witness.get("removed_obligation_role") == "decisive_predicate"
            and witness.get("removed_instance_count") == 1
            and witness.get("class_denominator_status") == "green"
            and witness.get("class_denominator_count") == len(PromotionObligationClass)
            and witness.get("authority_status") == "red"
            and witness.get("authority_issue_codes") == ["decisive_obligation_omitted"]
            and witness.get("verification_session_provenance") == "verification"
            and isinstance(removed_id, str)
            and witness.get("authority_issues")
            == [
                {
                    "code": "decisive_obligation_omitted",
                    "obligation_instance_id": removed_id,
                }
            ]
        )
    if not witness_valid:
        issues.append({"code": "obligation_instance_mutation_witness_invalid"})
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
        try:
            expected_input_strangle = _proof_input_strangle(
                consumed=contract_refusal.owner_projection.grounding_decision_certificate,
                reference=_credal_reference(),
            )
            if (
                not expected_input_strangle["default_flipped"]
                or payload.get("proof_input_strangle") != expected_input_strangle
            ):
                issues.append({"code": "proof_input_strangle_drift"})
        except (AttributeError, KeyError, TypeError, ValueError):
            issues.append({"code": "proof_input_strangle_drift"})
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
            PromotionObligationClass.MEASUREMENT,
            PromotionObligationClass.DATA,
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
    with measure_file_reads(repo_root) as reads:

        def finish(report: dict[str, Any]) -> dict[str, Any]:
            report["verdict"] = {
                "pass": "PASS",
                "fail": "FAIL",
                "unrun": "UNRUN",
            }.get(report.get("status"), "UNRUN")
            report["wall_time_seconds"] = round(time.monotonic() - started, 6)
            measurement = reads.snapshot(complete_verdict=report.get("status") != "unrun")
            issue_codes = {
                str(issue.get("code"))
                for issue in report.get("issues", [])
                if isinstance(issue, dict)
            }
            if report.get("status") == "unrun":
                verdict_scope = (
                    "No complete artifact/replay verdict was reached because the required "
                    "input or live replay was unavailable."
                )
                finding_coverage = "partial frozen-artifact reconciliation"
            elif "promotion_contract_frozen_payload_invalid" in issue_codes:
                verdict_scope = (
                    "Frozen bytes were read and rejected as invalid JSON; the owner replay "
                    "was not run and no reconciliation result was reached."
                )
                finding_coverage = "frozen artifact JSON syntax only"
            elif "promotion_comparison_admission_manifest_drift" in issue_codes:
                verdict_scope = (
                    "Frozen artifact validation and the canonical owner replay reached a "
                    "typed owner reconciliation refusal; byte equality was not established."
                )
                finding_coverage = "frozen-artifact validation and typed owner refusal"
            else:
                verdict_scope = (
                    "Frozen artifact validation and exact byte comparison with one canonical "
                    "owner replay in this checkout completed."
                )
                finding_coverage = "frozen artifact and canonical replay byte comparison"
            verdict_scope += (
                " This does not establish complete source, import, or data-input closure "
                "or production-wide truth."
            )
            measurement["finding_coverage"] = finding_coverage
            measurement["verdict_scope"] = verdict_scope
            measurement["complete_verdict_scope"] = (
                verdict_scope if measurement["complete_verdict"] else None
            )
            measurement["selection_status"] = "partial"
            measurement["selectors"] = {
                "frozen_output": OUTPUT_PATH,
                "live_replay": "build_contract_json_for_write(repo_root)",
                "comparison_custody": sorted(_COMPARISON_IDENTITY_FIELDS),
            }
            measurement["unresolved_by_construction"].extend(
                [
                    "Live owner replay imports and implicit filesystem reads outside the "
                    "measured frozen-output read are not operation-instrumented.",
                    "The complete loaded-code and data-input denominator for the live replay "
                    "is not established by this receipt.",
                ]
            )
            report["measurement"] = measurement
            return report

        try:
            frozen_bytes = measured_read_bytes(path)
        except FileNotFoundError:
            return finish(
                {
                    "status": "unrun",
                    "issues": [{"code": "promotion_contract_input_missing", "path": OUTPUT_PATH}],
                }
            )
        except OSError as exc:
            return finish(
                {
                    "status": "unrun",
                    "issues": [
                        {
                            "code": "promotion_contract_input_unreadable",
                            "path": OUTPUT_PATH,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    ],
                }
            )

        try:
            frozen_payload = json.loads(frozen_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return finish(
                {
                    "status": "fail",
                    "issues": [
                        {
                            "code": "promotion_contract_frozen_payload_invalid",
                            "path": OUTPUT_PATH,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    ],
                }
            )

        try:
            report = validate_payload(frozen_payload)
            expected_json = build_contract_json_for_write(repo_root)
        except _PromotionContractReconciliationDriftError as exc:
            report = locals().get("report", {"issues": []})
            report["issues"].append({"code": exc.code, "details": exc.details})
            report["status"] = "fail"
            return finish(report)
        except Exception as exc:
            partial_issues = locals().get("report", {}).get("issues", [])
            return finish(
                {
                    "status": "unrun",
                    "issues": [
                        {
                            "code": "promotion_contract_replay_unrun",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    ],
                    "partial_issues": partial_issues,
                }
            )

        if frozen_bytes != expected_json.encode("utf-8"):
            report["issues"].append(
                {
                    "code": "promotion_contract_canonical_drift",
                    "expected_hash": gy_content_hash(json.loads(expected_json)),
                    "actual_hash": gy_content_hash(frozen_payload),
                }
            )
            report["status"] = "fail"
        return finish(report)


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

    payload, plan = _build_payload_with_comparison_plan(repo_root)
    payload.pop("capture_wall_time_seconds", None)
    _set_comparison_identity(payload, plan)
    payload["contract_content_hash"] = _contract_content_hash(payload)
    payload = _reconcile_frozen_contract(repo_root, payload, plan)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


run_source_flip_mutations = _mutation_owner.run_source_flip_mutations


_receipt_from_payload = _mutation_owner._receipt_from_payload


_validate_n11_projection = _mutation_owner._validate_n11_projection


def _behavioral_mutations(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> list[dict[str, Any]]:
    """Run the complete behavioral mutation set with current facade callbacks."""
    return _mutation_owner._behavioral_mutations(
        payload,
        plan,
        callbacks=_mutation_callbacks(),
    )


def validate_payload_without_mutation_check(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> dict[str, Any]:
    """Validate a mutation without recursively re-running its mutation set."""
    return _mutation_owner.validate_payload_without_mutation_check(
        payload,
        plan,
        callbacks=_mutation_callbacks(),
    )


_mutate_ledger_projection = _mutation_owner._mutate_ledger_projection


_mutate_gate_hash = _mutation_owner._mutate_gate_hash


_mutate_fixed_time_refusal = _mutation_owner._mutate_fixed_time_refusal


_mutate_vacuous_scope_pass = _mutation_owner._mutate_vacuous_scope_pass


_mutate_risk_budget = _mutation_owner._mutate_risk_budget


_mutate_conditionality_clause = _mutation_owner._mutate_conditionality_clause


_mutate_strangle = _mutation_owner._mutate_strangle


_obligation_denominator = _comparison_owner._obligation_denominator


_scope_insufficient_promotion_policy = _comparison_owner._scope_insufficient_promotion_policy


_contract_content_hash = _comparison_owner._contract_content_hash


_comparison_content_hash = _comparison_owner._comparison_content_hash


def _reconcile_frozen_contract(
    repo_root: Path,
    live: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> dict[str, Any]:
    """Reconcile against current facade path and registered reissue callbacks."""
    return _comparison_owner._reconcile_frozen_contract(
        repo_root,
        live,
        plan,
        callbacks=_comparison_callbacks(),
    )


_frozen_comparison_identity_admissible = _comparison_owner._frozen_comparison_identity_admissible


_is_authorized_corr_input_epoch_reissue = _comparison_owner._is_authorized_corr_input_epoch_reissue


_is_authorized_credal_input_epoch_reissue = (
    _comparison_owner._is_authorized_credal_input_epoch_reissue
)


_is_authorized_v3_to_v6_comparison_reissue = (
    _comparison_owner._is_authorized_v3_to_v6_comparison_reissue
)


_N9_V6_EPOCH = _comparison_owner._N9_V6_EPOCH
_N9_V8_EPOCH = _comparison_owner._N9_V8_EPOCH
_N9_V6_SCOPE_RULE = _comparison_owner._N9_V6_SCOPE_RULE
_N9_V6_MEASUREMENT_OWNER = _comparison_owner._N9_V6_MEASUREMENT_OWNER


_n9_v6_scope_hash = _comparison_owner._n9_v6_scope_hash


_translate_n9_semantic_ledger_epoch = _comparison_owner._translate_n9_semantic_ledger_epoch


_translate_n9_v6_receipt_epoch = _comparison_owner._translate_n9_v6_receipt_epoch


def _is_authorized_v6_source_scope_epoch_reissue(
    frozen: dict[str, Any],
    live: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> bool:
    """Apply the registered v6 source/scope reissue with current facade callbacks."""
    return _comparison_owner._is_authorized_v6_source_scope_epoch_reissue(
        frozen,
        live,
        plan,
        callbacks=_comparison_callbacks(),
    )


_set_comparison_identity = _comparison_owner._set_comparison_identity


_comparison_identity_issues = _comparison_owner._comparison_identity_issues


_obligation_detail = _comparison_owner._obligation_detail


_SourceFlipReplacement = _mutation_owner._SourceFlipReplacement


_SourceFlipCase = _mutation_owner._SourceFlipCase


_run_source_flip_case = _mutation_owner._run_source_flip_case


_source_flip_cases = _mutation_owner._source_flip_cases


_pytest_probe = _mutation_owner._pytest_probe


_output_tail = _mutation_owner._output_tail


_promotion_input = _input_owner._promotion_input


_summary = _input_owner._summary


_value_receipt = _input_owner._value_receipt


_cg2_contract_bind = _input_owner._cg2_contract_bind


_proof_input_strangle = _input_owner._proof_input_strangle


_boundary = _input_owner._boundary


_s6_posture = _input_owner._s6_posture


_s7_posture = _input_owner._s7_posture


_s8_posture = _input_owner._s8_posture


_credal_reference = _input_owner._credal_reference


_operator_edge = _input_owner._operator_edge


_target_edge = _input_owner._target_edge


_lex_edge = _input_owner._lex_edge


_world_slot = _input_owner._world_slot


_policy_slot = _input_owner._policy_slot


_tax_atom = _input_owner._tax_atom


_pure_synonym_probe = _input_owner._pure_synonym_probe


_hash = _input_owner._hash


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
    args = parse_args_for_timing(
        parser,
        argv,
        mode_options=(
            "--check",
            "--corrupt-field-drift-check",
            "--rederive-audit",
            "--source-flip-mutations",
            "--write",
        ),
    )
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
    elif report["status"] == "unrun":
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
    else:
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
    return {"pass": 0, "fail": 1, "unrun": 2}.get(report.get("status"), 2)


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
