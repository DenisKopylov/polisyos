"""Production CAAB bind gate over CG1 relation certificates.

This module owns GY-CG2 only: it consumes the real CG1
``GroundingRelationCertificate`` plus the real CG0 ``CredalReference`` and emits
a deterministic decision certificate. It does not re-create CG0/CG1 stores, and
it treats every CG1 relation as a candidate until revalidated against the live
reference.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import grounding_relation as _cg1
from polisyos.runtime.quality.grounding_relation import (
    CRITICAL_AXES,
    GROUNDING_RELATION_SCHEMA_VERSION,
    GROUNDING_RELATION_VALIDATOR_VERSION,
    GroundingRelationCertificate,
    GroundingRelationEngine,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.credal_reference import CredalReference

GROUNDING_BIND_SCHEMA_VERSION = "policyos.runtime.grounding_decision_certificate.v1"
GROUNDING_BIND_VALIDATOR_VERSION = "policyos.runtime.grounding_bind.cg2.v1"

type GroundingDecision = Literal["bind", "abstain", "novel_candidate"]
type CalibrationStatus = Literal["calibrated", "cold_start", "drift", "frozen"]
type CalibrationSource = Literal["production"]
type _OwnedCalibrationSource = Literal["production", "cg2_contract_seed_anchor"]
type _AuthorityScope = Literal["production", "contract_testing"]
type ObligationStatus = Literal["closed", "open"]
type RevalidationStatus = Literal["current", "stale", "tampered", "passed", "mismatch"]
type BindReason = Literal[
    "bind_eligible",
    "tampered_cg1_certificate",
    "stale_cg1_certificate",
    "relation_revalidation_mismatch",
    "false_analog_hard_abstain",
    "novel_candidate_handoff",
    "relation_not_bind_eligible",
    "robust_singleton_empty",
    "robust_singleton_ambiguous",
    "open_obligation",
    "risk_budget_exceeded",
    "cold_start_conservative",
    "calibration_drift_frozen",
    "calibration_frozen",
]

_BIND_ELIGIBLE_RELATIONS = frozenset({"exact", "certified-specialization"})
_RELATION_OUTCOME_SET = (
    "exact",
    "certified-specialization",
    "generalization",
    "partial",
    "compositional",
    "false-analog",
    "novel-candidate",
    "unknown",
    "blocked",
)
_DEFAULT_RISK_BOUNDS = {
    "delta_RT1": 0.0002,
    "delta_ref": 0.0001,
    "delta_type_adm": 0.0001,
    "delta_retrieval_novel": 0.0001,
    "delta_runtime": 0.0001,
    "delta_monitor": 0.0001,
}
_DEFAULT_DELTA_GROUND = 0.01
_DEFAULT_CALIBRATION_MIN_SAMPLES = 20
_CALIBRATION_OWNER_ALLOWLIST = frozenset({"cg2_contract_seed_anchor"})
_CG1_HASH_EXCLUDE_FIELDS = {
    "certificate_id",
    "content_hash",
    "relation_confidence_scope",
}


class _StrictModel(BaseModel):
    """Strict immutable base for CG2 runtime DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GroundingBindPolicy(_StrictModel):
    """Safe production bind settings.

    The production API intentionally exposes no calibration-source selector,
    mutation switch, or risk-bound override. Those are bind-authority knobs and
    are quarantined behind ``GroundingBindGate.for_contract_testing``.
    """


class _GroundingBindRuntimeSettings(_StrictModel):
    """Internal settings, with unsafe controls only set by the test constructor."""

    authority_scope: _AuthorityScope = "production"
    delta_ground_budget: float = Field(_DEFAULT_DELTA_GROUND, gt=0.0)
    risk_component_bounds: Mapping[str, float] = Field(
        default_factory=lambda: dict(_DEFAULT_RISK_BOUNDS)
    )
    calibration_source: _OwnedCalibrationSource = "production"
    calibration_min_samples: int = Field(_DEFAULT_CALIBRATION_MIN_SAMPLES, ge=1)
    disable_certificate_revalidation: bool = False
    disable_content_hash_check: bool = False
    disable_robust_singleton_check: bool = False
    disable_false_analog_hard_abstain: bool = False
    disable_exact_spec_only_rule: bool = False
    disable_calibration_freeze: bool = False
    disable_calibration_owner_validation: bool = False
    disable_epoch_binding: bool = False


class CalibrationStratumRecord(_StrictModel):
    """Observed calibration state for one bind stratum."""

    operator_family: str = Field(..., min_length=1)
    reference_region: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    status: CalibrationStatus
    reference_epoch: str | None = None
    sample_count: int = Field(0, ge=0)
    provenance: str | None = None
    owner_anchor_id: str | None = None
    evidence_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _content_hash_matches_payload(self) -> CalibrationStratumRecord:
        if self.content_hash is None:
            return self
        payload = self.model_dump(mode="json", exclude={"content_hash"})
        expected = gy_content_hash(payload)
        if self.content_hash != expected:
            raise ValueError("calibration_stratum_content_hash_mismatch")
        return self

    def with_content_hash(self) -> CalibrationStratumRecord:
        """Return this record with its deterministic content hash populated."""

        payload = self.model_dump(mode="json", exclude={"content_hash"})
        return self.model_copy(update={"content_hash": gy_content_hash(payload)})


class GroundingCalibrationLedger(_StrictModel):
    """Calibration ledger for CG2 strata.

    Empty ledgers are honest cold-start ledgers, not permission to bind.
    """

    records: tuple[CalibrationStratumRecord, ...] = ()
    ledger_id: str = "cg2_calibration_ledger.inline"
    source_id: str = "caller_supplied"
    n11_confidence_ledger_ref: str | None = None
    n11_composition_status: Literal["not_wired", "composed"] = "not_wired"

    def record_for(
        self,
        *,
        operator_family: str,
        reference_region: str,
        relation_type: str,
        reference_epoch: str,
    ) -> CalibrationStratumRecord | None:
        """Return the exact stratum record when present and epoch-current."""

        for record in self.records:
            if (
                record.operator_family == operator_family
                and record.reference_region == reference_region
                and record.relation_type == relation_type
            ):
                if record.reference_epoch and record.reference_epoch != reference_epoch:
                    return record.model_copy(update={"status": "drift"})
                return record
        return None


class _OwnedCalibrationStore(_StrictModel):
    """Owned calibration anchors loaded by CG2 itself, never caller-supplied."""

    authority_scope: _AuthorityScope
    ledger: GroundingCalibrationLedger

    def record_by_anchor_id(self, anchor_id: str | None) -> CalibrationStratumRecord | None:
        """Return the store-owned anchor by id when present."""

        if not anchor_id:
            return None
        for record in self.ledger.records:
            if record.owner_anchor_id == anchor_id:
                return record
        return None


class GroundingRevalidationRecord(_StrictModel):
    """Owner-validation result for the consumed CG1 certificate."""

    status: RevalidationStatus
    content_hash_valid: bool
    expected_content_hash: str
    reference_versions_match: bool
    stale_reasons: tuple[str, ...] = ()
    replayed: bool = False
    replayed_certificate_id: str | None = None
    replayed_content_hash: str | None = None
    replayed_selected_relation: str | None = None
    replayed_selected_atom_id: str | None = None
    replayed_critical_contradictions: tuple[str, ...] = ()
    selected_relation_reproduced: bool = False
    selected_atom_reproduced: bool = False
    critical_contradictions_reproduced: bool = False
    critical_contradiction_tuple_reproduced: bool = False
    not_more_permissive_than_full: bool = False


class GroundingSafeCandidate(_StrictModel):
    """One candidate atom's robust-safe classification."""

    atom_id: str = Field(..., min_length=1)
    relation: str = Field(..., min_length=1)
    support_edge_scope: tuple[str, ...] = ()
    support_statuses: Mapping[str, str] = Field(default_factory=dict)
    is_adversarial_countercandidate: bool = False
    safe: bool
    reason: str = Field(..., min_length=1)


class GroundingSafeSet(_StrictModel):
    """Set-valued safe-bind witness over the live credal reference."""

    safe_atom_ids: tuple[str, ...]
    candidates: tuple[GroundingSafeCandidate, ...]
    robust_singleton: bool


class GroundingObligationCheck(_StrictModel):
    """One recomputed production-bind obligation."""

    obligation_id: str = Field(..., min_length=1)
    status: ObligationStatus
    reason: str = Field(..., min_length=1)
    evidence: Mapping[str, Any] = Field(default_factory=dict)


class GroundingRiskLedgerEntry(_StrictModel):
    """One bounded contribution to ``delta_ground``."""

    component: str = Field(..., min_length=1)
    spend: float = Field(..., ge=0.0)
    bound: float = Field(..., ge=0.0)
    source: str = Field(..., min_length=1)
    conservative_bound: bool = False

    @model_validator(mode="after")
    def _spend_within_bound(self) -> GroundingRiskLedgerEntry:
        if self.spend > self.bound:
            raise ValueError("risk_component_spend_exceeds_bound")
        return self


class GroundingRiskLedger(_StrictModel):
    """Composable ``delta_ground`` accounting for a CG2 decision."""

    delta_ground_budget: float = Field(..., gt=0.0)
    entries: tuple[GroundingRiskLedgerEntry, ...]
    total_spend: float = Field(..., ge=0.0)
    within_budget: bool
    n11_composition_status: Literal["not_wired", "composed"] = "not_wired"
    n11_confidence_ledger_ref: str | None = None


class GroundingCalibrationDecision(_StrictModel):
    """Calibration stratum resolved for this bind attempt."""

    operator_family: str = Field(..., min_length=1)
    reference_region: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    status: CalibrationStatus
    stratum_key: str = Field(..., min_length=1)
    sample_count: int = Field(0, ge=0)
    reference_epoch: str
    decisive_freeze: bool
    reason: str = Field(..., min_length=1)
    calibration_source: str = Field(..., min_length=1)
    owner_validated: bool = False
    owned_anchor_id: str | None = None
    owned_anchor_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    validation_reasons: tuple[str, ...] = ()


class GroundingPromotabilityResolution(_StrictModel):
    """Authoritative owner-store resolution of a CG2 bind certificate."""

    promotable: bool
    reason: str = Field(..., min_length=1)
    certificate_id: str
    decision: GroundingDecision
    authority_scope: _AuthorityScope
    certificate_promotable_claim: bool
    store_authority_scope: _AuthorityScope
    owned_anchor_id: str | None = None
    certificate_anchor_content_hash: str | None = None
    store_anchor_content_hash: str | None = None
    reference_epoch_match: bool
    content_hash_valid: bool


class GroundingDecisionCertificate(_StrictModel):
    """Content-addressed CG2 decision certificate."""

    schema_version: Literal["policyos.runtime.grounding_decision_certificate.v1"] = (
        GROUNDING_BIND_SCHEMA_VERSION
    )
    certificate_id: str = Field(..., pattern=r"^cg2_cert_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    decision: GroundingDecision
    decisive_reason: BindReason
    selected_relation: str
    bound_atom_id: str | None = None
    cg1_certificate_id: str
    cg1_content_hash: str
    cg1_expected_content_hash: str
    reference_epoch: str
    reference_hash: str
    reference_versions: Mapping[str, str]
    safe_t: GroundingSafeSet
    closed_obligations: tuple[str, ...]
    open_obligations: tuple[str, ...]
    obligations: tuple[GroundingObligationCheck, ...]
    risk_ledger: GroundingRiskLedger
    calibration: GroundingCalibrationDecision
    revalidation: GroundingRevalidationRecord
    authority_scope: _AuthorityScope = "production"
    production_promotable: bool = False
    cg3_handoff: bool = False
    selected_critical_contradictions: tuple[str, ...] = ()
    relation_outcome_set: tuple[str, ...] = _RELATION_OUTCOME_SET
    validator_version: str = GROUNDING_BIND_VALIDATOR_VERSION

    @model_validator(mode="after")
    def _bind_requires_safety_evidence(self) -> GroundingDecisionCertificate:
        expected_hash = recompute_grounding_decision_content_hash(self)
        if self.content_hash != expected_hash:
            raise ValueError("decision_certificate_content_hash_mismatch")
        expected_id = _decision_certificate_id(expected_hash)
        if self.certificate_id != expected_id:
            raise ValueError("decision_certificate_id_mismatch")
        if self.production_promotable:
            if self.authority_scope != "production":
                raise ValueError("promotable_certificate_requires_production_scope")
            if self.calibration.status != "calibrated" or not self.calibration.owner_validated:
                raise ValueError("promotable_certificate_requires_calibrated_stratum")
            if self.calibration.calibration_source == "caller_supplied_unvalidated":
                raise ValueError("promotable_certificate_rejects_caller_supplied_calibration")
            if (
                not self.calibration.owned_anchor_id
                or not self.calibration.owned_anchor_content_hash
                or "owned_calibration_anchor_validated"
                not in self.calibration.validation_reasons
            ):
                raise ValueError("promotable_certificate_requires_owned_calibration_anchor")
        if self.decision != "bind":
            if self.production_promotable:
                raise ValueError("non_bind_certificate_cannot_be_production_promotable")
            return self
        if self.authority_scope == "contract_testing":
            if self.production_promotable:
                raise ValueError("contract_testing_bind_must_not_be_production_promotable")
        elif not self.production_promotable:
            raise ValueError("production_bind_requires_promotable_scope")
        if self.calibration.status != "calibrated" or not self.calibration.owner_validated:
            raise ValueError("bind_certificate_requires_calibrated_stratum")
        if self.calibration.calibration_source == "caller_supplied_unvalidated":
            raise ValueError("bind_certificate_rejects_caller_supplied_calibration")
        if (
            not self.calibration.owned_anchor_id
            or not self.calibration.owned_anchor_content_hash
            or "owned_calibration_anchor_validated"
            not in self.calibration.validation_reasons
        ):
            raise ValueError("bind_certificate_requires_owned_calibration_anchor")
        if self.calibration.calibration_source == "cg2_contract_seed_anchor":
            if self.authority_scope != "contract_testing":
                raise ValueError("seed_anchor_bind_requires_contract_testing_scope")
            if not self.calibration.owned_anchor_id.startswith("cg2_contract_seed_anchor:"):
                raise ValueError("seed_anchor_bind_requires_seed_anchor_id")
        if (
            not self.risk_ledger.within_budget
            or self.risk_ledger.total_spend > self.risk_ledger.delta_ground_budget
        ):
            raise ValueError("bind_certificate_requires_risk_within_budget")
        if self.open_obligations:
            raise ValueError("bind_certificate_requires_closed_obligations")
        if (
            len(self.safe_t.safe_atom_ids) != 1
            or not self.safe_t.robust_singleton
            or self.bound_atom_id != self.safe_t.safe_atom_ids[0]
        ):
            raise ValueError("bind_certificate_requires_robust_singleton")
        if (
            self.revalidation.status != "passed"
            or not self.revalidation.selected_relation_reproduced
            or not self.revalidation.selected_atom_reproduced
            or not self.revalidation.not_more_permissive_than_full
        ):
            raise ValueError("bind_certificate_requires_passed_revalidation")
        if self.selected_relation not in _BIND_ELIGIBLE_RELATIONS:
            raise ValueError("bind_certificate_requires_exact_or_specialization")
        if self.selected_critical_contradictions:
            raise ValueError("bind_certificate_requires_no_critical_contradictions")
        if "no_unresolved_critical_axis" not in self.closed_obligations:
            raise ValueError("bind_certificate_requires_no_critical_axis_obligation")
        return self


class GroundingBindGate:
    """CAAB gate that turns revalidated CG1 relation candidates into decisions."""

    def __init__(
        self,
        credal_reference: CredalReference,
        *,
        policy: GroundingBindPolicy | None = None,
    ) -> None:
        if policy is not None and not isinstance(policy, GroundingBindPolicy):
            raise TypeError("policy must be a GroundingBindPolicy")
        self.reference = credal_reference
        self.policy = policy or GroundingBindPolicy()
        self._settings = _GroundingBindRuntimeSettings()
        self._relation_engine: GroundingRelationEngine | None = None
        self._replay_cache: dict[tuple[str, str], GroundingRelationCertificate] = {}

    @classmethod
    def for_contract_testing(
        cls,
        credal_reference: CredalReference,
        *,
        calibration_seed_anchor: bool = False,
        calibration_min_samples: int = _DEFAULT_CALIBRATION_MIN_SAMPLES,
        risk_component_bounds: Mapping[str, float] | None = None,
        disable_certificate_revalidation: bool = False,
        disable_content_hash_check: bool = False,
        disable_robust_singleton_check: bool = False,
        disable_false_analog_hard_abstain: bool = False,
        disable_exact_spec_only_rule: bool = False,
        disable_calibration_freeze: bool = False,
        disable_calibration_owner_validation: bool = False,
        disable_epoch_binding: bool = False,
    ) -> GroundingBindGate:
        """Return a non-promotable gate for CG2 contract probes only."""

        gate = cls(credal_reference)
        gate._settings = _GroundingBindRuntimeSettings(
            authority_scope="contract_testing",
            calibration_source="cg2_contract_seed_anchor"
            if calibration_seed_anchor
            else "production",
            calibration_min_samples=calibration_min_samples,
            risk_component_bounds=dict(risk_component_bounds or _DEFAULT_RISK_BOUNDS),
            disable_certificate_revalidation=disable_certificate_revalidation,
            disable_content_hash_check=disable_content_hash_check,
            disable_robust_singleton_check=disable_robust_singleton_check,
            disable_false_analog_hard_abstain=disable_false_analog_hard_abstain,
            disable_exact_spec_only_rule=disable_exact_spec_only_rule,
            disable_calibration_freeze=disable_calibration_freeze,
            disable_calibration_owner_validation=disable_calibration_owner_validation,
            disable_epoch_binding=disable_epoch_binding,
        )
        return gate

    def certificate_for(
        self,
        cg1_certificate: GroundingRelationCertificate,
        *,
        calibration_ledger: GroundingCalibrationLedger | None = None,
        epoch: str | None = None,
    ) -> GroundingDecisionCertificate:
        """Return a deterministic CG2 bind/abstain/novel decision certificate."""

        ledger = calibration_ledger or GroundingCalibrationLedger()
        expected_hash = recompute_grounding_relation_content_hash(cg1_certificate)
        content_hash_valid = cg1_certificate.content_hash == expected_hash
        version_match = _reference_versions_match(cg1_certificate, self.reference)
        stale_reasons = _stale_reasons(
            cg1_certificate,
            self.reference,
            epoch=epoch,
        )

        revalidation = GroundingRevalidationRecord(
            status="current",
            content_hash_valid=content_hash_valid,
            expected_content_hash=expected_hash,
            reference_versions_match=version_match,
            stale_reasons=stale_reasons,
        )
        active_certificate = cg1_certificate
        if not self._settings.disable_content_hash_check and not content_hash_valid:
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation.model_copy(update={"status": "tampered"}),
                ledger=ledger,
                decision="abstain",
                reason="tampered_cg1_certificate",
            )
        if not self._settings.disable_epoch_binding and stale_reasons:
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation.model_copy(update={"status": "stale"}),
                ledger=ledger,
                decision="abstain",
                reason="stale_cg1_certificate",
            )
        if not self._settings.disable_certificate_revalidation:
            replayed = self._replay_certificate(cg1_certificate)
            selected_matches = replayed.selected_relation == cg1_certificate.selected_relation
            full_selected_atom = _selected_atom_id(cg1_certificate)
            replayed_selected_atom = _selected_atom_id(replayed)
            bind_relevant = (
                cg1_certificate.selected_relation in _BIND_ELIGIBLE_RELATIONS
                or replayed.selected_relation in _BIND_ELIGIBLE_RELATIONS
            )
            selected_atom_matches = full_selected_atom == replayed_selected_atom
            critical_tuple_matches = tuple(replayed.critical_contradictions) == tuple(
                cg1_certificate.critical_contradictions
            )
            critical_presence_matches = bool(replayed.critical_contradictions) == bool(
                cg1_certificate.critical_contradictions
            )
            critical_matches = (
                critical_tuple_matches if bind_relevant else critical_presence_matches
            )
            not_more_permissive = not (
                replayed.selected_relation in _BIND_ELIGIBLE_RELATIONS
                and cg1_certificate.selected_relation not in _BIND_ELIGIBLE_RELATIONS
            )
            if replayed.selected_relation in _BIND_ELIGIBLE_RELATIONS:
                not_more_permissive = (
                    not_more_permissive
                    and selected_atom_matches
                    and not replayed.critical_contradictions
                    and not cg1_certificate.critical_contradictions
                )
            revalidation_passed = (
                selected_matches
                and critical_matches
                and (selected_atom_matches or not bind_relevant)
                and not_more_permissive
            )
            revalidation = revalidation.model_copy(
                update={
                    "status": "passed" if revalidation_passed else "mismatch",
                    "replayed": True,
                    "replayed_certificate_id": replayed.certificate_id,
                    "replayed_content_hash": replayed.content_hash,
                    "replayed_selected_relation": replayed.selected_relation,
                    "replayed_selected_atom_id": replayed_selected_atom,
                    "replayed_critical_contradictions": replayed.critical_contradictions,
                    "selected_relation_reproduced": selected_matches,
                    "selected_atom_reproduced": selected_atom_matches,
                    "critical_contradictions_reproduced": critical_matches,
                    "critical_contradiction_tuple_reproduced": critical_tuple_matches,
                    "not_more_permissive_than_full": not_more_permissive,
                }
            )
            active_certificate = replayed
            if not revalidation_passed:
                return self._decision(
                    cg1_certificate,
                    active_certificate=active_certificate,
                    revalidation=revalidation,
                    ledger=ledger,
                    decision="abstain",
                    reason="relation_revalidation_mismatch",
                )
        else:
            revalidation = revalidation.model_copy(
                update={
                    "status": "passed",
                    "selected_relation_reproduced": True,
                    "selected_atom_reproduced": True,
                    "critical_contradictions_reproduced": True,
                    "critical_contradiction_tuple_reproduced": True,
                    "not_more_permissive_than_full": True,
                }
            )

        selected_relation = active_certificate.selected_relation
        if selected_relation == "novel-candidate" and _is_out_of_lever(active_certificate):
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation,
                ledger=ledger,
                decision="novel_candidate",
                reason="novel_candidate_handoff",
                cg3_handoff=True,
            )
        if (
            _has_selected_critical_veto(active_certificate)
            and not self._settings.disable_false_analog_hard_abstain
        ):
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation,
                ledger=ledger,
                decision="abstain",
                reason="false_analog_hard_abstain",
            )
        if selected_relation == "novel-candidate" and not _has_selected_critical_veto(
            active_certificate
        ):
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation,
                ledger=ledger,
                decision="novel_candidate",
                reason="novel_candidate_handoff",
                cg3_handoff=True,
            )
        if (
            selected_relation not in _BIND_ELIGIBLE_RELATIONS
            and not self._settings.disable_exact_spec_only_rule
            and not self._settings.disable_false_analog_hard_abstain
        ):
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation,
                ledger=ledger,
                decision="abstain",
                reason="relation_not_bind_eligible",
            )

        safe_t = self._safe_set(active_certificate)
        skip_robust_for_false_analog_mutation = (
            self._settings.disable_false_analog_hard_abstain
            and _has_selected_critical_veto(active_certificate)
        )
        if (
            not self._settings.disable_robust_singleton_check
            and not skip_robust_for_false_analog_mutation
        ):
            if len(safe_t.safe_atom_ids) == 0:
                return self._decision(
                    cg1_certificate,
                    active_certificate=active_certificate,
                    revalidation=revalidation,
                    ledger=ledger,
                    decision="abstain",
                    reason="robust_singleton_empty",
                    safe_t=safe_t,
                )
            if len(safe_t.safe_atom_ids) > 1:
                return self._decision(
                    cg1_certificate,
                    active_certificate=active_certificate,
                    revalidation=revalidation,
                    ledger=ledger,
                    decision="abstain",
                    reason="robust_singleton_ambiguous",
                    safe_t=safe_t,
                )

        obligations = self._obligations(active_certificate)
        open_obligations = tuple(
            item.obligation_id for item in obligations if item.status == "open"
        )
        if open_obligations:
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation,
                ledger=ledger,
                decision="abstain",
                reason="open_obligation",
                safe_t=safe_t,
                obligations=obligations,
            )

        calibration = self._calibration_decision(active_certificate, ledger)
        risk_ledger = self._risk_ledger(ledger, calibration=calibration)
        if calibration.decisive_freeze and not self._settings.disable_calibration_freeze:
            reason: BindReason = "calibration_frozen"
            if calibration.status == "cold_start":
                reason = "cold_start_conservative"
            elif calibration.status == "drift":
                reason = "calibration_drift_frozen"
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation,
                ledger=ledger,
                decision="abstain",
                reason=reason,
                safe_t=safe_t,
                obligations=obligations,
                calibration=calibration,
                risk_ledger=risk_ledger,
            )
        if not risk_ledger.within_budget:
            return self._decision(
                cg1_certificate,
                active_certificate=active_certificate,
                revalidation=revalidation,
                ledger=ledger,
                decision="abstain",
                reason="risk_budget_exceeded",
                safe_t=safe_t,
                obligations=obligations,
                calibration=calibration,
                risk_ledger=risk_ledger,
            )

        safe_atom_ids = safe_t.safe_atom_ids
        bound_atom_id = safe_atom_ids[0] if safe_atom_ids else _selected_atom_id(active_certificate)
        return self._decision(
            cg1_certificate,
            active_certificate=active_certificate,
            revalidation=revalidation,
            ledger=ledger,
            decision="bind",
            reason="bind_eligible",
            safe_t=safe_t,
            obligations=obligations,
            calibration=calibration,
            risk_ledger=risk_ledger,
            bound_atom_id=bound_atom_id,
        )

    @property
    def _engine(self) -> GroundingRelationEngine:
        if self._relation_engine is None:
            self._relation_engine = GroundingRelationEngine(self.reference)
        return self._relation_engine

    def _replay_certificate(
        self,
        certificate: GroundingRelationCertificate,
    ) -> GroundingRelationCertificate:
        cache_key = (certificate.content_hash, self.reference.reference_hash)
        cached = self._replay_cache.get(cache_key)
        if cached is not None:
            return cached
        proposal = _proposal_from_certificate(certificate)
        replayed = self._fast_live_atom_replay(certificate, proposal)
        self._replay_cache[cache_key] = replayed
        return replayed

    def _fast_live_atom_replay(
        self,
        certificate: GroundingRelationCertificate,
        proposal: Mapping[str, Any],
    ) -> GroundingRelationCertificate:
        parsed = _cg1.parse_n4_proposal(
            proposal,
            proposal_id=certificate.proposal_id,
            reference=self.reference,
        )
        base_candidates = tuple(self._engine.reference_atoms)
        candidates = (
            *base_candidates,
            *_cg1._adversarial_countercandidates(base_candidates, parsed),
        )
        pair_results = self._engine._candidate_relation_results(parsed, candidates)
        verdict = _cg1._proposal_verdict(
            pair_results,
            candidates=candidates,
            parsed=parsed,
            reference=self.reference,
            retrieval_indexed_edge_count=len(self.reference.essential_edges),
            policy=self._engine.policy,
        )
        selected = verdict.representative
        if selected is None:
            selected_relation = verdict.selected_relation
            solver_status = "SAT"
            axis_witnesses = ()
            critical = ()
            unresolved = ()
            residual = ()
            unsat_core = ()
        else:
            selected_relation = verdict.selected_relation
            solver_status = selected.solver_status
            axis_witnesses = selected.axis_witnesses
            critical = selected.critical_contradictions
            unresolved = selected.unresolved_axes
            residual = selected.residual_constraints
            unsat_core = selected.unsat_core_if_any
        raw_payload = {
            "candidate_atom_ids": [candidate.atom_id for candidate in candidates],
            "proposal_id": parsed.proposal_id,
            "raw_text_hash": parsed.raw_text_hash,
            "proposal_signature": _cg1._proposal_signature_payload(parsed),
            "atom_signature_or_bundle": _cg1._atom_signature_payload(candidates),
            "relation_set": _cg1._relation_set_payload(
                pair_results,
                candidates=candidates,
                coverage_claim=verdict.coverage_claim,
            ),
            "selected_relation": selected_relation,
            "reference_versions": dict(sorted(self.reference.component_versions.items())),
            "axis_witnesses": [item.model_dump(mode="json") for item in axis_witnesses],
            "critical_contradictions": list(critical),
            "unresolved_axes": list(unresolved),
            "residual_constraints": list(residual),
            "compositional_cover": None,
            "cross_modal_witnesses": _cg1._cross_modal_payload(
                pair_results,
                selected,
                gy_k_witness_mode="structural_only_no_runtime_gy_k_provider",
            ),
            "solver_status": solver_status,
            "unsat_core_if_any": list(unsat_core),
            "recommended_transition": _cg1._recommended_transition(
                selected_relation,
                allow_bind_recommendations=False,
            ),
            "validator_version": GROUNDING_RELATION_VALIDATOR_VERSION,
            "stale_conditions": _cg1._stale_conditions(),
            "shadow_only": True,
            "no_bind_admit_promote": True,
        }
        content_hash = gy_content_hash(
            {
                "schema_version": GROUNDING_RELATION_SCHEMA_VERSION,
                **raw_payload,
            }
        )
        return GroundingRelationCertificate(
            certificate_id=f"cg1_cert_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **raw_payload,
        )

    def _safe_set(self, certificate: GroundingRelationCertificate) -> GroundingSafeSet:
        atom_payloads = _mapping(certificate.atom_signature_or_bundle)
        candidates: list[GroundingSafeCandidate] = []
        safe_ids: set[str] = set()
        eligible = set(_BIND_ELIGIBLE_RELATIONS)
        if self._settings.disable_exact_spec_only_rule:
            eligible.update({"generalization", "partial", "compositional"})
        if self._settings.disable_false_analog_hard_abstain:
            eligible.update({"false-analog", "novel-candidate"})

        for result in _candidate_results(certificate):
            atom_id = str(result.get("atom_id") or "")
            relation = str(result.get("selected_relation") or "")
            atom_payload = _mapping(atom_payloads.get(atom_id))
            edge_scope = tuple(str(item) for item in _sequence(atom_payload.get("edge_scope")))
            support_lift = self.reference.reference_lift(edge_scope)
            support_statuses = {
                key: str(value.get("status"))
                for key, value in sorted(support_lift.items())
                if isinstance(value, Mapping)
            }
            support_confirmed = bool(edge_scope) and all(
                status == "confirmed" for status in support_statuses.values()
            )
            is_counter = bool(atom_payload.get("is_adversarial_countercandidate"))
            reason = "relation_not_bind_eligible"
            is_safe = False
            if relation in eligible:
                if str(result.get("solver_status")) != "SAT":
                    reason = "solver_not_sat"
                elif (
                    result.get("critical_contradictions")
                    and not self._settings.disable_false_analog_hard_abstain
                ):
                    reason = "critical_axis_veto"
                elif not support_confirmed:
                    reason = "support_not_confirmed"
                else:
                    reason = "safe_across_all_admissible_completions"
                    is_safe = True
                    safe_ids.add(atom_id)
            candidates.append(
                GroundingSafeCandidate(
                    atom_id=atom_id,
                    relation=relation,
                    support_edge_scope=edge_scope,
                    support_statuses=support_statuses,
                    is_adversarial_countercandidate=is_counter,
                    safe=is_safe,
                    reason=reason,
                )
            )
        safe_atom_ids = tuple(sorted(safe_ids))
        return GroundingSafeSet(
            safe_atom_ids=safe_atom_ids,
            candidates=tuple(sorted(candidates, key=lambda item: (item.atom_id, item.relation))),
            robust_singleton=len(safe_atom_ids) == 1,
        )

    def _obligations(
        self,
        certificate: GroundingRelationCertificate,
    ) -> tuple[GroundingObligationCheck, ...]:
        signature = _first_signature(certificate)
        target = _first_text(signature.get("X_do"))
        op = str(signature.get("op") or "")
        unit = str(signature.get("unit") or "")
        estimand = str(signature.get("estimand") or "")
        admissibility = str(signature.get("admissibility") or "")
        axis_relations = {item.axis: item.relation for item in certificate.axis_witnesses}
        unresolved_critical = sorted(
            axis for axis in certificate.unresolved_axes if axis in CRITICAL_AXES
        )
        critical_closed = (
            True
            if self._settings.disable_false_analog_hard_abstain
            else not unresolved_critical and not certificate.critical_contradictions
        )
        checks = [
            _obligation(
                "admissibility_closed",
                bool(admissibility)
                and admissibility
                not in {"candidate_unverified", "failed", "reference_contested"},
                "proposal admissibility is owner-closed",
                {"admissibility": admissibility},
            ),
            _obligation(
                "estimand_grounded",
                bool(estimand and estimand != "unknown"),
                "estimand is grounded",
                {"estimand": estimand},
            ),
            _obligation(
                "unit_scale_consistent",
                bool(unit) and _cg1._unit_compatible(self.reference, target, unit),
                "unit/scale is consistent with the owner WMR target slot",
                {
                    "unit": unit,
                    "target": target,
                    "axis_relation": axis_relations.get("unit"),
                },
            ),
            _obligation(
                "target_writable_wmr_slot",
                _target_is_writable(self.reference, target),
                "target resolves to a writable WorldModelRecord policy slot",
                {"target": target},
            ),
            _obligation(
                "operator_registered_lever",
                _operator_registered(self.reference, op),
                "operator resolves to a registered L6 lever",
                {"operator": op},
            ),
            _obligation(
                "l3_l6_consistency",
                certificate.solver_status == "SAT" and not certificate.unsat_core_if_any,
                "JTCG cross-modal consistency is SAT",
                {
                    "solver_status": certificate.solver_status,
                    "unsat_core_if_any": list(certificate.unsat_core_if_any),
                },
            ),
            _obligation(
                "no_unresolved_critical_axis",
                critical_closed,
                "no critical relation axis remains unresolved or vetoed",
                {
                    "unresolved_critical_axes": unresolved_critical,
                    "critical_contradictions": list(certificate.critical_contradictions),
                },
            ),
        ]
        return tuple(checks)

    def _calibration_decision(
        self,
        certificate: GroundingRelationCertificate,
        ledger: GroundingCalibrationLedger,
    ) -> GroundingCalibrationDecision:
        signature = _first_signature(certificate)
        operator = str(signature.get("op") or "unknown")
        region = str(signature.get("scope") or "unknown")
        relation = str(certificate.selected_relation)
        owned_ledger = self._owned_calibration_ledger()
        owned_record = owned_ledger.record_for(
            operator_family=operator,
            reference_region=region,
            relation_type=relation,
            reference_epoch=self.reference.reference_epoch,
        )
        caller_record = ledger.record_for(
            operator_family=operator,
            reference_region=region,
            relation_type=relation,
            reference_epoch=self.reference.reference_epoch,
        )
        if self._settings.disable_calibration_owner_validation and caller_record is not None:
            return GroundingCalibrationDecision(
                operator_family=operator,
                reference_region=region,
                relation_type=relation,
                status=caller_record.status,
                stratum_key=f"{operator}|{region}|{relation}",
                sample_count=caller_record.sample_count,
                reference_epoch=self.reference.reference_epoch,
                decisive_freeze=caller_record.status != "calibrated",
                reason="unsafe caller calibration accepted by mutation switch",
                calibration_source="caller_supplied_unvalidated",
                owner_validated=True,
                owned_anchor_id=caller_record.owner_anchor_id,
                owned_anchor_content_hash=None,
                validation_reasons=("calibration_owner_validation_disabled",),
            )
        validation_reasons: list[str] = []
        if caller_record is not None:
            if owned_record is None or caller_record.content_hash != owned_record.content_hash:
                validation_reasons.append("caller_calibration_not_owner_validated")
                return GroundingCalibrationDecision(
                    operator_family=operator,
                    reference_region=region,
                    relation_type=relation,
                    status="cold_start",
                    stratum_key=f"{operator}|{region}|{relation}",
                    sample_count=0,
                    reference_epoch=self.reference.reference_epoch,
                    decisive_freeze=True,
                    reason="caller calibration record failed owned-source validation",
                    calibration_source=self._calibration_source_label(),
                    owner_validated=False,
                    owned_anchor_id=None,
                    owned_anchor_content_hash=None,
                    validation_reasons=tuple(validation_reasons),
                )
            validation_reasons.append("caller_calibration_matches_owned_anchor")

        if owned_record is None:
            status: CalibrationStatus = "cold_start"
            sample_count = 0
            reason = "no owned calibration history for stratum"
            validation_reasons.append("owned_calibration_anchor_missing")
            owner_validated = False
            owned_anchor_id = None
            owned_anchor_content_hash = None
        else:
            status, validation_reasons = self._recompute_owned_calibration_status(
                owned_record,
                validation_reasons=validation_reasons,
            )
            sample_count = owned_record.sample_count
            reason = f"owned_ledger:{owned_ledger.ledger_id}"
            owner_validated = status == "calibrated"
            owned_anchor_id = owned_record.owner_anchor_id
            owned_anchor_content_hash = owned_record.content_hash
        return GroundingCalibrationDecision(
            operator_family=operator,
            reference_region=region,
            relation_type=relation,
            status=status,
            stratum_key=f"{operator}|{region}|{relation}",
            sample_count=sample_count,
            reference_epoch=self.reference.reference_epoch,
            decisive_freeze=status != "calibrated",
            reason=reason,
            calibration_source=self._calibration_source_label(),
            owner_validated=owner_validated,
            owned_anchor_id=owned_anchor_id,
            owned_anchor_content_hash=owned_anchor_content_hash,
            validation_reasons=tuple(validation_reasons),
        )

    def _owned_calibration_ledger(self) -> GroundingCalibrationLedger:
        return _owned_calibration_store(
            self.reference.reference_epoch,
            source=self._settings.calibration_source,
            calibration_min_samples=self._settings.calibration_min_samples,
        ).ledger

    def _owned_calibration_store(self) -> _OwnedCalibrationStore:
        return _owned_calibration_store(
            self.reference.reference_epoch,
            source=self._settings.calibration_source,
            calibration_min_samples=self._settings.calibration_min_samples,
        )

    def _calibration_source_label(self) -> str:
        if self._settings.calibration_source == "production":
            return "none_wired_production_freezes"
        return self._settings.calibration_source

    def _recompute_owned_calibration_status(
        self,
        record: CalibrationStratumRecord,
        *,
        validation_reasons: list[str],
    ) -> tuple[CalibrationStatus, list[str]]:
        if record.reference_epoch != self.reference.reference_epoch:
            validation_reasons.append("owned_calibration_epoch_mismatch")
            return "drift", validation_reasons
        failures: list[str] = []
        if record.provenance not in _CALIBRATION_OWNER_ALLOWLIST:
            failures.append("owned_calibration_provenance_not_allowed")
        if not record.content_hash:
            failures.append("owned_calibration_content_hash_missing")
        if not record.owner_anchor_id:
            failures.append("owned_calibration_anchor_id_missing")
        if record.sample_count < self._settings.calibration_min_samples:
            failures.append("owned_calibration_sample_count_below_minimum")
        expected_evidence_hash = _calibration_evidence_hash(record)
        if record.evidence_hash != expected_evidence_hash:
            failures.append("owned_calibration_evidence_hash_mismatch")
        validation_reasons.extend(failures)
        if failures:
            return "cold_start", validation_reasons
        validation_reasons.append("owned_calibration_anchor_validated")
        return "calibrated", validation_reasons

    def _risk_ledger(
        self,
        ledger: GroundingCalibrationLedger,
        *,
        calibration: GroundingCalibrationDecision,
    ) -> GroundingRiskLedger:
        conservative = calibration.status != "calibrated"
        entries_list: list[GroundingRiskLedgerEntry] = []
        for component, bound in sorted(self._settings.risk_component_bounds.items()):
            spend = float(bound)
            entry_bound = float(bound)
            if conservative and component == "delta_monitor":
                spend = max(float(bound), self._settings.delta_ground_budget)
                entry_bound = spend
            entries_list.append(
                GroundingRiskLedgerEntry(
                    component=component,
                    spend=spend,
                    bound=entry_bound,
                    source=(
                        "conservative_cold_start_bound"
                        if conservative
                        else "calibrated_stratum_bound"
                    ),
                    conservative_bound=conservative,
                )
            )
        entries = tuple(entries_list)
        total = round(sum(entry.spend for entry in entries), 12)
        return GroundingRiskLedger(
            delta_ground_budget=self._settings.delta_ground_budget,
            entries=entries,
            total_spend=total,
            within_budget=total <= self._settings.delta_ground_budget,
            n11_composition_status=ledger.n11_composition_status,
            n11_confidence_ledger_ref=ledger.n11_confidence_ledger_ref,
        )

    def _decision(
        self,
        consumed_certificate: GroundingRelationCertificate,
        *,
        active_certificate: GroundingRelationCertificate,
        revalidation: GroundingRevalidationRecord,
        ledger: GroundingCalibrationLedger,
        decision: GroundingDecision,
        reason: BindReason,
        safe_t: GroundingSafeSet | None = None,
        obligations: tuple[GroundingObligationCheck, ...] | None = None,
        calibration: GroundingCalibrationDecision | None = None,
        risk_ledger: GroundingRiskLedger | None = None,
        bound_atom_id: str | None = None,
        cg3_handoff: bool = False,
    ) -> GroundingDecisionCertificate:
        safe = safe_t or self._safe_set(active_certificate)
        obligation_checks = obligations or self._obligations(active_certificate)
        calibration_decision = calibration or self._calibration_decision(active_certificate, ledger)
        risk = risk_ledger or self._risk_ledger(ledger, calibration=calibration_decision)
        closed = tuple(
            item.obligation_id for item in obligation_checks if item.status == "closed"
        )
        open_obligations = tuple(
            item.obligation_id for item in obligation_checks if item.status == "open"
        )
        raw_payload = {
            "calibration": calibration_decision.model_dump(mode="json"),
            "authority_scope": self._settings.authority_scope,
            "cg1_certificate_id": consumed_certificate.certificate_id,
            "cg1_content_hash": consumed_certificate.content_hash,
            "cg1_expected_content_hash": revalidation.expected_content_hash,
            "cg3_handoff": cg3_handoff,
            "closed_obligations": list(closed),
            "decision": decision,
            "decisive_reason": reason,
            "open_obligations": list(open_obligations),
            "obligations": [item.model_dump(mode="json") for item in obligation_checks],
            "production_promotable": (
                decision == "bind" and self._settings.authority_scope == "production"
            ),
            "reference_epoch": self.reference.reference_epoch,
            "reference_hash": self.reference.reference_hash,
            "reference_versions": dict(sorted(self.reference.component_versions.items())),
            "revalidation": revalidation.model_dump(mode="json"),
            "risk_ledger": risk.model_dump(mode="json"),
            "safe_t": safe.model_dump(mode="json"),
            "selected_relation": str(active_certificate.selected_relation),
            "selected_critical_contradictions": list(active_certificate.critical_contradictions),
            "bound_atom_id": bound_atom_id,
            "relation_outcome_set": list(_RELATION_OUTCOME_SET),
            "validator_version": GROUNDING_BIND_VALIDATOR_VERSION,
        }
        content_hash = gy_content_hash(
            {
                "schema_version": GROUNDING_BIND_SCHEMA_VERSION,
                **raw_payload,
            }
        )
        return GroundingDecisionCertificate(
            certificate_id=_decision_certificate_id(content_hash),
            content_hash=content_hash,
            **raw_payload,
        )


def build_grounding_decision_certificate(
    cg1_certificate: GroundingRelationCertificate,
    credal_reference: CredalReference,
    *,
    calibration_ledger: GroundingCalibrationLedger | None = None,
    epoch: str | None = None,
    policy: GroundingBindPolicy | None = None,
) -> GroundingDecisionCertificate:
    """Build a CG2 decision certificate from a CG1 certificate and CG0 reference."""

    return GroundingBindGate(credal_reference, policy=policy).certificate_for(
        cg1_certificate,
        calibration_ledger=calibration_ledger,
        epoch=epoch,
    )


def resolve_grounding_decision_promotability(
    certificate: GroundingDecisionCertificate,
    credal_reference: CredalReference,
) -> GroundingPromotabilityResolution:
    """Resolve production promotability from the owned production anchor store."""

    return _resolve_grounding_decision_promotability(
        certificate,
        credal_reference,
        store=_owned_calibration_store(
            credal_reference.reference_epoch,
            source="production",
            calibration_min_samples=_DEFAULT_CALIBRATION_MIN_SAMPLES,
        ),
    )


def resolve_grounding_decision_promotability_for_contract_testing(
    certificate: GroundingDecisionCertificate,
    credal_reference: CredalReference,
) -> GroundingPromotabilityResolution:
    """Resolve contract-test bind certificates against the non-promotable seed store."""

    return _resolve_grounding_decision_promotability(
        certificate,
        credal_reference,
        store=_owned_calibration_store(
            credal_reference.reference_epoch,
            source="cg2_contract_seed_anchor",
            calibration_min_samples=_DEFAULT_CALIBRATION_MIN_SAMPLES,
        ),
    )


def _resolve_grounding_decision_promotability(
    certificate: GroundingDecisionCertificate,
    credal_reference: CredalReference,
    *,
    store: _OwnedCalibrationStore,
) -> GroundingPromotabilityResolution:
    expected_hash = recompute_grounding_decision_content_hash(certificate)
    content_hash_valid = certificate.content_hash == expected_hash
    reference_epoch_match = (
        certificate.reference_epoch == credal_reference.reference_epoch
        and certificate.reference_hash == credal_reference.reference_hash
    )
    anchor_id = certificate.calibration.owned_anchor_id
    certificate_anchor_hash = certificate.calibration.owned_anchor_content_hash
    store_record = store.record_by_anchor_id(anchor_id)
    store_anchor_hash = store_record.content_hash if store_record is not None else None

    promotable = False
    if not content_hash_valid:
        reason = "decision_certificate_content_hash_mismatch"
    elif certificate.certificate_id != _decision_certificate_id(expected_hash):
        reason = "decision_certificate_id_mismatch"
    elif certificate.decision != "bind":
        reason = "not_bind_decision"
    elif not reference_epoch_match:
        reason = "reference_epoch_or_hash_mismatch"
    elif not anchor_id or not certificate_anchor_hash:
        reason = "owned_anchor_claim_missing"
    elif store_record is None:
        reason = "owned_anchor_missing"
    elif store_record.reference_epoch != credal_reference.reference_epoch:
        reason = "owned_anchor_epoch_mismatch"
    elif store_anchor_hash != certificate_anchor_hash:
        reason = "owned_anchor_content_hash_mismatch"
    elif store.authority_scope != "production":
        reason = "non_production_anchor_scope"
    elif certificate.authority_scope != "production":
        reason = "non_production_certificate_scope"
    else:
        promotable = True
        reason = "owned_production_anchor_resolved"
    return GroundingPromotabilityResolution(
        promotable=promotable,
        reason=reason,
        certificate_id=certificate.certificate_id,
        decision=certificate.decision,
        authority_scope=certificate.authority_scope,
        certificate_promotable_claim=certificate.production_promotable,
        store_authority_scope=store.authority_scope,
        owned_anchor_id=anchor_id,
        certificate_anchor_content_hash=certificate_anchor_hash,
        store_anchor_content_hash=store_anchor_hash,
        reference_epoch_match=reference_epoch_match,
        content_hash_valid=content_hash_valid,
    )


def recompute_grounding_relation_content_hash(
    certificate: GroundingRelationCertificate,
) -> str:
    """Recompute CG1's content hash from the certificate body."""

    payload = certificate.model_dump(mode="json")
    for field_name in _CG1_HASH_EXCLUDE_FIELDS:
        payload.pop(field_name, None)
    return gy_content_hash(payload)


def recompute_grounding_decision_content_hash(
    certificate_or_payload: GroundingDecisionCertificate | Mapping[str, Any],
) -> str:
    """Recompute CG2's content hash from the certificate body."""

    if isinstance(certificate_or_payload, Mapping):
        payload = json.loads(json.dumps(certificate_or_payload, sort_keys=True))
    else:
        payload = certificate_or_payload.model_dump(mode="json")
    payload.pop("certificate_id", None)
    payload.pop("content_hash", None)
    return gy_content_hash(payload)


def _decision_certificate_id(content_hash: str) -> str:
    return f"cg2_cert_{content_hash.removeprefix('sha256:')[:16]}"


def _owned_calibration_store(
    reference_epoch: str,
    *,
    source: _OwnedCalibrationSource,
    calibration_min_samples: int,
) -> _OwnedCalibrationStore:
    if source == "production":
        return _OwnedCalibrationStore(
            authority_scope="production",
            ledger=GroundingCalibrationLedger(
                records=(),
                ledger_id="cg2_production_calibration_empty",
                source_id="none_wired_production_freezes",
            ),
        )
    records = tuple(
        _owned_seed_anchor(
            reference_epoch,
            operator_family="tax_relief_rate",
            reference_region="global",
            relation_type=relation,
            sample_count=calibration_min_samples,
        )
        for relation in sorted(_RELATION_OUTCOME_SET)
    )
    return _OwnedCalibrationStore(
        authority_scope="contract_testing",
        ledger=GroundingCalibrationLedger(
            records=records,
            ledger_id="cg2_contract_seed_anchor",
            source_id="cg2_contract_seed_anchor",
        ),
    )


def _owned_seed_anchor(
    reference_epoch: str,
    *,
    operator_family: str,
    reference_region: str,
    relation_type: str,
    sample_count: int,
) -> CalibrationStratumRecord:
    anchor_id = (
        "cg2_contract_seed_anchor:"
        f"{reference_epoch}:{operator_family}:{reference_region}:{relation_type}"
    )
    record = CalibrationStratumRecord(
        operator_family=operator_family,
        reference_region=reference_region,
        relation_type=relation_type,
        status="calibrated",
        reference_epoch=reference_epoch,
        sample_count=sample_count,
        provenance="cg2_contract_seed_anchor",
        owner_anchor_id=anchor_id,
        evidence_hash=gy_content_hash(
            {
                "owner_anchor_id": anchor_id,
                "operator_family": operator_family,
                "reference_epoch": reference_epoch,
                "reference_region": reference_region,
                "relation_type": relation_type,
                "sample_count": sample_count,
            }
        ),
    )
    return record.with_content_hash()


def _calibration_evidence_hash(record: CalibrationStratumRecord) -> str:
    return gy_content_hash(
        {
            "owner_anchor_id": record.owner_anchor_id,
            "operator_family": record.operator_family,
            "reference_epoch": record.reference_epoch,
            "reference_region": record.reference_region,
            "relation_type": record.relation_type,
            "sample_count": record.sample_count,
        }
    )


def _reference_versions_match(
    certificate: GroundingRelationCertificate,
    reference: CredalReference,
) -> bool:
    return dict(sorted(certificate.reference_versions.items())) == dict(
        sorted(reference.component_versions.items())
    )


def _stale_reasons(
    certificate: GroundingRelationCertificate,
    reference: CredalReference,
    *,
    epoch: str | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not _reference_versions_match(certificate, reference):
        reasons.append("reference_versions_changed")
    if epoch is not None and epoch != reference.reference_epoch:
        reasons.append("epoch_argument_not_current_reference_epoch")
    return tuple(reasons)


def _proposal_from_certificate(certificate: GroundingRelationCertificate) -> dict[str, Any]:
    signature = _first_signature(certificate)
    return {
        "raw_text": json.dumps(signature, sort_keys=True, default=str),
        "signature": signature,
    }


def _first_signature(certificate: GroundingRelationCertificate) -> dict[str, Any]:
    proposal_signature = _mapping(certificate.proposal_signature)
    hypotheses = _sequence(proposal_signature.get("hypotheses"))
    for hypothesis in hypotheses:
        payload = _mapping(hypothesis)
        signature = _mapping(payload.get("signature"))
        if signature:
            return dict(signature)
    signature = _mapping(proposal_signature.get("signature"))
    return dict(signature)


def _has_selected_critical_veto(certificate: GroundingRelationCertificate) -> bool:
    if certificate.selected_relation == "false-analog":
        return True
    if certificate.critical_contradictions:
        return True
    selected_atom_id = _selected_atom_id(certificate)
    if selected_atom_id:
        for result in _candidate_results(certificate):
            if str(result.get("atom_id")) == selected_atom_id and result.get(
                "critical_contradictions"
            ):
                return True
    return False


def _is_out_of_lever(certificate: GroundingRelationCertificate) -> bool:
    coverage = _mapping(certificate.relation_set).get("known_space_coverage")
    if not isinstance(coverage, Mapping):
        return False
    if coverage.get("known_space_verdict") == "out_of_lever":
        return True
    return bool(coverage.get("out_of_lever_ops") or coverage.get("out_of_lever_targets"))


def _selected_atom_id(certificate: GroundingRelationCertificate) -> str | None:
    selected = _mapping(certificate.cross_modal_witnesses).get("selected_pair")
    if isinstance(selected, Mapping):
        atom_id = str(selected.get("atom_id") or "")
        if atom_id:
            return atom_id
    for result in _candidate_results(certificate):
        if str(result.get("selected_relation")) == str(certificate.selected_relation):
            return str(result.get("atom_id") or "") or None
    return None


def _candidate_results(certificate: GroundingRelationCertificate) -> list[Mapping[str, Any]]:
    results = _mapping(certificate.relation_set).get("candidate_results")
    return [item for item in _sequence(results) if isinstance(item, Mapping)]


def _obligation(
    obligation_id: str,
    is_closed: bool,
    closed_reason: str,
    evidence: Mapping[str, Any],
) -> GroundingObligationCheck:
    return GroundingObligationCheck(
        obligation_id=obligation_id,
        status="closed" if is_closed else "open",
        reason=closed_reason if is_closed else f"{obligation_id}_open",
        evidence=dict(evidence),
    )


def _target_is_writable(reference: CredalReference, target: str) -> bool:
    if not target:
        return False
    has_world_slot = any(
        edge.modality == "WMR_WORLD_SLOT" and edge.edge_id == target and edge.status == "confirmed"
        for edge in reference.essential_edges.values()
    )
    has_policy_slot = False
    for edge in reference.essential_edges.values():
        if edge.modality != "WMR_POLICY_SLOT_MAP" or edge.status != "confirmed":
            continue
        if edge.edge_id.endswith(f":{target}") or edge.edge_id == target:
            has_policy_slot = True
        for completion in edge.admissible_completions:
            if str(
                completion.value.get("world_slot")
                or completion.value.get("slot_id")
                or ""
            ) == target:
                has_policy_slot = True
    return has_world_slot and has_policy_slot


def _operator_registered(reference: CredalReference, operator: str) -> bool:
    if not operator:
        return False
    canonical = _canonical_operator(operator)
    return any(
        edge.modality == "L6_KNOB_OPERATOR"
        and edge.status == "confirmed"
        and _canonical_operator(edge.edge_id) == canonical
        for edge in reference.essential_edges.values()
    )


def _canonical_operator(value: object) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "budget": "budget_allocation_multiplier",
        "budget_allocation": "budget_allocation_multiplier",
        "budget_multiplier": "budget_allocation_multiplier",
        "tax_subsidy": "income_tax",
        "tax_credit": "tax_relief_rate",
        "tax_credit_rate": "tax_relief_rate",
        "income_tax_credit": "tax_relief_rate",
        "corporate_tax_credit": "tax_relief_rate",
        "payroll_tax_credit": "tax_relief_rate",
        "tax_relief": "tax_relief_rate",
        "procurement": "procurement_shock_intensity",
        "procurement_shock": "procurement_shock_intensity",
    }
    return aliases.get(text, text)


def _first_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            text = str(item or "")
            if text:
                return text
    return str(value or "")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return value
    return ()


__all__ = [
    "GROUNDING_BIND_SCHEMA_VERSION",
    "GROUNDING_BIND_VALIDATOR_VERSION",
    "CalibrationStratumRecord",
    "GroundingBindGate",
    "GroundingBindPolicy",
    "GroundingCalibrationDecision",
    "GroundingCalibrationLedger",
    "GroundingDecisionCertificate",
    "GroundingObligationCheck",
    "GroundingPromotabilityResolution",
    "GroundingRevalidationRecord",
    "GroundingRiskLedger",
    "GroundingRiskLedgerEntry",
    "GroundingSafeCandidate",
    "GroundingSafeSet",
    "build_grounding_decision_certificate",
    "recompute_grounding_decision_content_hash",
    "recompute_grounding_relation_content_hash",
    "resolve_grounding_decision_promotability",
    "resolve_grounding_decision_promotability_for_contract_testing",
]
