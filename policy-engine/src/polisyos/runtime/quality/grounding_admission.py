"""RT3 free-grow admission over CG2 novel candidates.

This module owns GY-CG3: it consumes a real CG2
``GroundingDecisionCertificate`` that handed off ``novel_candidate``, rebinds
the matching CG1 proposal certificate when available, and resolves admission
obligations against the live CG0 credal reference, WMR/L6 edges, L2 causal
evidence, and L5 substrate-trust owner surfaces. The admission certificate is a
content-addressed claim envelope only; registry patch authority is re-resolved
against the owners at the point of use.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common import serialization
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.grounding_bind import (
    GroundingDecisionCertificate,
    recompute_grounding_decision_content_hash,
    recompute_grounding_relation_content_hash,
)
from polisyos.runtime.quality.grounding_relation import (
    GroundingRelationCertificate,
    GroundingRelationEngine,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.credal_reference import CredalReference, CredalReferenceEdge

GROUNDING_ADMISSION_SCHEMA_VERSION = "policyos.runtime.grounding_admission_certificate.v1"
GROUNDING_ADMISSION_VALIDATOR_VERSION = "policyos.runtime.grounding_admission.cg3.v1"

type GroundingAdmissionDecision = Literal[
    "admit_new_lever",
    "acquire_then_decide",
    "reject_hallucination",
    "non_new",
]
type GroundingAdmissionReason = Literal[
    "all_obligations_closed",
    "cg2_not_novel_candidate",
    "cg2_revalidation_failed",
    "cg1_binding_missing_or_mismatch",
    "open_obligation",
    "mechanism_witness_missing",
    "mechanism_composition_unverified",
    "world_slot_acquisition_required",
    "data_trust_below_floor",
    "ambiguous_completion_requires_acquisition",
    "novel_irreducible_failed_existing_atom",
    "outcome_wish",
    "proxy_manipulation",
    "impossible_type",
]
type CompletionKind = Literal["existing_slot", "contested", "NEW_SLOT_acquirable"]
type AdmissionObligationStatus = Literal["closed", "open"]
type _AuthorityScope = Literal["production", "contract_testing"]

_DEFAULT_DELTA_ADM = 0.01
_DEFAULT_COMPONENT_RISKS: dict[str, float] = {
    "parse": 0.0004,
    "novel_irreducible": 0.0007,
    "type": 0.0005,
    "world_bindable_or_acquirable": 0.0007,
    "do_semantics": 0.0005,
    "mechanism_witness": 0.0015,
    "estimand": 0.0004,
    "admissibility": 0.0005,
    "data_trust": 0.0006,
    "ambiguity": 0.0007,
}
_L2_MECHANISM_MODALITIES = frozenset(
    {
        "L2_CAUSAL_EDGE",
        "L2_CAUSAL_CLAIM",
    }
)
_L2_CONTESTED_MECHANISM_MODALITIES = frozenset(
    {
        "L2_CAUSAL_EDGE",
        "L2_CAUSAL_CLAIM",
        "L2_CONTESTED_EDGE",
    }
)
_HARD_OBLIGATIONS = (
    "parse",
    "novel_irreducible",
    "type",
    "world_bindable_or_acquirable",
    "do_semantics",
    "mechanism_witness",
    "estimand",
    "admissibility",
    "data_trust",
    "ambiguity",
)


class _StrictModel(BaseModel):
    """Strict immutable base for CG3 runtime DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GroundingAdmissionPolicy(_StrictModel):
    """Safe production admission settings.

    This public policy intentionally exposes no admit-authority knobs: no force
    admit, no obligation disabling, no mechanism injection, and no risk-budget
    override. Mutation switches live only behind
    ``GroundingAdmissionEngine.for_contract_testing``.
    """


class _GroundingAdmissionRuntimeSettings(_StrictModel):
    """Internal settings populated only by production defaults or test factory."""

    authority_scope: _AuthorityScope = "production"
    delta_adm_budget: float = Field(_DEFAULT_DELTA_ADM, gt=0.0)
    component_risk_bounds: Mapping[str, float] = Field(
        default_factory=lambda: dict(_DEFAULT_COMPONENT_RISKS)
    )
    data_trust_floor: float = Field(0.5, ge=0.0, le=1.0)
    disable_mechanism_witness_resolution: bool = False
    disable_do_path_resolution: bool = False
    allow_composed_mechanism_witness: bool = False
    use_best_edge_trust: bool = False
    disable_novel_irreducible: bool = False
    disable_denotation_novelty: bool = False
    explicit_only_denotation_match: bool = False
    disable_stable_unique: bool = False
    reject_unknown: bool = False
    enable_keyword_proxy_reject: bool = False
    allow_policy_map_mention_actuatability: bool = False
    disable_registry_patch_reresolution: bool = False
    allow_substrate_registry_authority: bool = False


class AdmissionObligationCheck(_StrictModel):
    """One CG3 admission obligation resolved against an owner."""

    obligation_id: str = Field(..., min_length=1)
    status: AdmissionObligationStatus
    reason: str = Field(..., min_length=1)
    owner: str = Field(..., min_length=1)
    evidence: Mapping[str, Any] = Field(default_factory=dict)


class AdmissionCompletion(_StrictModel):
    """One admissible free-grow completion for the proposed lever."""

    kind: CompletionKind
    target_slot: str = Field(..., min_length=1)
    evidence_ref: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class StableUniqueResolution(_StrictModel):
    """Free-grow analogue of robust-singleton over admissible completions."""

    stable: bool
    reason: str = Field(..., min_length=1)
    completions: tuple[AdmissionCompletion, ...]
    stable_new_lever_key: str | None = None


class MechanismWitnessResolution(_StrictModel):
    """Owner-resolved causal mechanism witness."""

    status: AdmissionObligationStatus
    owner: str = Field(..., min_length=1)
    evidence_refs: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = Field(default_factory=dict)


class DataTrustResolution(_StrictModel):
    """L5/SKG trust-floor resolution for the mechanism evidence."""

    status: AdmissionObligationStatus
    owner: str = Field(..., min_length=1)
    trust_floor: float = Field(..., ge=0.0, le=1.0)
    resolved_trust_cap: float = Field(..., ge=0.0, le=1.0)
    evidence_ref: str | None = None
    reason: str = Field(..., min_length=1)


class AcquisitionNeed(_StrictModel):
    """Typed GY-N7 blocker emitted when proof is missing."""

    blocker_id: str = Field(..., min_length=1)
    owner: str = "GY-N7.grounding_acquisition"
    needed_evidence: tuple[str, ...]
    redecide_after: str = "owner_evidence_persisted"
    full_voi_evsi_deferred_to: str = "CG5"


class DeltaAdmissionLedgerEntry(_StrictModel):
    """One bounded false-admit risk contribution."""

    component: str = Field(..., min_length=1)
    spend: float = Field(..., ge=0.0)
    bound: float = Field(..., ge=0.0)
    source: str = Field(..., min_length=1)
    conservative_bound: bool = True

    @model_validator(mode="after")
    def _spend_within_bound(self) -> DeltaAdmissionLedgerEntry:
        if self.spend > self.bound:
            raise ValueError("delta_adm_component_spend_exceeds_bound")
        return self


class DeltaAdmissionLedger(_StrictModel):
    """Composable ``delta_adm`` accounting for a CG3 decision."""

    delta_adm_budget: float = Field(..., gt=0.0)
    entries: tuple[DeltaAdmissionLedgerEntry, ...]
    total_spend: float = Field(..., ge=0.0)
    within_budget: bool
    guarantee_statement: str = Field(..., min_length=1)
    calibration_status: str = "cold_start_no_admission_history"
    n11_composition_status: Literal["not_wired", "composed"] = "not_wired"
    n11_confidence_ledger_ref: str | None = None


class GroundingLeverRegistryPatch(_StrictModel):
    """Content-addressed GY-S0 free-grow registry patch claim."""

    patch_id: str = Field(..., pattern=r"^cg3_patch_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    authority_scope: _AuthorityScope
    operator_kind: str = Field(..., min_length=1)
    target_world_slots: tuple[str, ...]
    parameter_domain: Mapping[str, Any]
    lex_map: Mapping[str, Any] = Field(default_factory=dict)
    owner: str = "GY-S0/L6 intervention substrate"
    source_reference_epoch: str = Field(..., min_length=1)
    source_reference_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    application_status: Literal["shadow_applied", "contract_testing_shadow"] = (
        "shadow_applied"
    )
    reversible: bool = True
    idempotency_key: str = Field(..., min_length=1)
    decision_front_created: bool = False

    @model_validator(mode="after")
    def _patch_hash_matches_payload(self) -> GroundingLeverRegistryPatch:
        expected = recompute_registry_patch_content_hash(self)
        if self.content_hash != expected:
            raise ValueError("registry_patch_content_hash_mismatch")
        expected_id = f"cg3_patch_{expected.removeprefix('sha256:')[:16]}"
        if self.patch_id != expected_id:
            raise ValueError("registry_patch_id_mismatch")
        if self.decision_front_created:
            raise ValueError("registry_patch_must_not_create_decision_front")
        return self


class GroundingAdmissionLedger(_StrictModel):
    """Auditable ledger row for CG3 admission patching."""

    ledger_id: str = Field(..., pattern=r"^cg3_ledger_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    patch_ids: tuple[str, ...]
    admission_certificate_id: str = Field(..., min_length=1)
    authority_scope: _AuthorityScope
    reversible: bool = True
    application_scope: str = "shadow_until_live_gy_s0_writer_is_declared_safe"

    @model_validator(mode="after")
    def _ledger_hash_matches_payload(self) -> GroundingAdmissionLedger:
        expected = recompute_admission_ledger_content_hash(self)
        if self.content_hash != expected:
            raise ValueError("admission_ledger_content_hash_mismatch")
        expected_id = f"cg3_ledger_{expected.removeprefix('sha256:')[:16]}"
        if self.ledger_id != expected_id:
            raise ValueError("admission_ledger_id_mismatch")
        return self


class RegistryPatchApplicationResolution(_StrictModel):
    """Owner re-resolution result for applying an admission registry patch."""

    applied: bool
    reason: str = Field(..., min_length=1)
    recomputed_certificate_id: str | None = None
    recomputed_patch_id: str | None = None
    certificate_patch_id: str | None = None
    patch: GroundingLeverRegistryPatch | None = None


class GroundingAdmissionCertificate(_StrictModel):
    """Content-addressed CG3 admission certificate.

    The model validates deterministic identity only. It deliberately does not
    make admission authoritative from its own fields; consumers must re-resolve
    with ``apply_grounding_admission_registry_patch`` or the admission engine.
    """

    schema_version: Literal["policyos.runtime.grounding_admission_certificate.v1"] = (
        GROUNDING_ADMISSION_SCHEMA_VERSION
    )
    certificate_id: str = Field(..., pattern=r"^cg3_cert_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    decision: GroundingAdmissionDecision
    decisive_reason: GroundingAdmissionReason
    cg2_certificate_id: str = Field(..., min_length=1)
    cg2_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    cg2_expected_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    cg1_certificate_id: str | None = None
    cg1_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    cg1_expected_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    reference_epoch: str = Field(..., min_length=1)
    reference_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    reference_versions: Mapping[str, str]
    authority_scope: _AuthorityScope = "production"
    production_promotable: bool = False
    proposal_signature: Mapping[str, Any] = Field(default_factory=dict)
    closed_obligations: tuple[str, ...]
    open_obligations: tuple[str, ...]
    obligations: tuple[AdmissionObligationCheck, ...]
    stable_unique: StableUniqueResolution
    mechanism_witness: MechanismWitnessResolution
    data_trust: DataTrustResolution
    acquisition_need: AcquisitionNeed | None = None
    decisive_reject_proof: str | None = None
    delta_adm_ledger: DeltaAdmissionLedger
    registry_patch: GroundingLeverRegistryPatch | None = None
    admission_ledger: GroundingAdmissionLedger | None = None
    validator_version: str = GROUNDING_ADMISSION_VALIDATOR_VERSION

    @model_validator(mode="after")
    def _content_hash_matches_payload(self) -> GroundingAdmissionCertificate:
        expected = recompute_grounding_admission_content_hash(self)
        if self.content_hash != expected:
            raise ValueError("admission_certificate_content_hash_mismatch")
        expected_id = f"cg3_cert_{expected.removeprefix('sha256:')[:16]}"
        if self.certificate_id != expected_id:
            raise ValueError("admission_certificate_id_mismatch")
        if self.authority_scope == "contract_testing" and self.production_promotable:
            raise ValueError("contract_testing_admission_must_not_be_promotable")
        return self


class GroundingAdmissionEngine:
    """RT3 engine that admits, acquires, rejects, or routes non-new levers."""

    def __init__(
        self,
        credal_reference: CredalReference,
        *,
        policy: GroundingAdmissionPolicy | None = None,
    ) -> None:
        if policy is not None and not isinstance(policy, GroundingAdmissionPolicy):
            raise TypeError("policy must be a GroundingAdmissionPolicy")
        self.reference = credal_reference
        self.policy = policy or GroundingAdmissionPolicy()
        self._contract_testing_substrate_registry: object | None = None
        self._settings = _GroundingAdmissionRuntimeSettings()
        self._relation_engine: GroundingRelationEngine | None = None

    @classmethod
    def for_contract_testing(
        cls,
        credal_reference: CredalReference,
        *,
        substrate_registry: object | None = None,
        disable_mechanism_witness_resolution: bool = False,
        disable_do_path_resolution: bool = False,
        allow_composed_mechanism_witness: bool = False,
        use_best_edge_trust: bool = False,
        disable_novel_irreducible: bool = False,
        disable_denotation_novelty: bool = False,
        explicit_only_denotation_match: bool = False,
        disable_stable_unique: bool = False,
        reject_unknown: bool = False,
        enable_keyword_proxy_reject: bool = False,
        allow_policy_map_mention_actuatability: bool = False,
        disable_registry_patch_reresolution: bool = False,
        allow_substrate_registry_authority: bool = False,
    ) -> GroundingAdmissionEngine:
        """Return a non-promotable admission engine for behavioral probes only."""

        engine = cls(credal_reference)
        engine._contract_testing_substrate_registry = substrate_registry
        engine._settings = _GroundingAdmissionRuntimeSettings(
            authority_scope="contract_testing",
            disable_mechanism_witness_resolution=disable_mechanism_witness_resolution,
            disable_do_path_resolution=disable_do_path_resolution,
            allow_composed_mechanism_witness=allow_composed_mechanism_witness,
            use_best_edge_trust=use_best_edge_trust,
            disable_novel_irreducible=disable_novel_irreducible,
            disable_denotation_novelty=disable_denotation_novelty,
            explicit_only_denotation_match=explicit_only_denotation_match,
            disable_stable_unique=disable_stable_unique,
            reject_unknown=reject_unknown,
            enable_keyword_proxy_reject=enable_keyword_proxy_reject,
            allow_policy_map_mention_actuatability=allow_policy_map_mention_actuatability,
            disable_registry_patch_reresolution=disable_registry_patch_reresolution,
            allow_substrate_registry_authority=allow_substrate_registry_authority,
        )
        return engine

    def decide(
        self,
        cg2_certificate: GroundingDecisionCertificate,
        *,
        cg1_certificate: GroundingRelationCertificate | None = None,
    ) -> GroundingAdmissionCertificate:
        """Resolve the CG3 admission decision for one CG2 novel handoff."""

        cg2_validation = _validate_cg2_binding(cg2_certificate, self.reference)
        cg1_validation = _validate_cg1_binding(cg2_certificate, cg1_certificate)
        signature = _signature_from_inputs(cg2_certificate, cg1_certificate)
        stable_unique = self._stable_unique(signature)
        mechanism = self._mechanism_witness(signature)
        data_trust = self._data_trust(mechanism)
        reject_proof = _proven_hallucination(
            signature,
            self.reference,
            disable_do_path_resolution=self._settings.disable_do_path_resolution,
            enable_keyword_proxy_reject=self._settings.enable_keyword_proxy_reject,
        )
        novel = self._novel_irreducible(signature, cg1_certificate=cg1_certificate)
        obligations = self._obligations(
            signature,
            stable_unique=stable_unique,
            mechanism=mechanism,
            data_trust=data_trust,
            novel_irreducible=novel,
            cg2_validation=cg2_validation,
            cg1_validation=cg1_validation,
        )
        open_obligations = tuple(
            item.obligation_id for item in obligations if item.status == "open"
        )
        closed_obligations = tuple(
            item.obligation_id for item in obligations if item.status == "closed"
        )
        decision, reason, acquisition = self._decision_kind(
            signature,
            open_obligations=open_obligations,
            stable_unique=stable_unique,
            mechanism=mechanism,
            data_trust=data_trust,
            novel_irreducible=novel,
            reject_proof=reject_proof,
            cg2_validation=cg2_validation,
            cg1_validation=cg1_validation,
        )
        patch = None
        if decision == "admit_new_lever":
            patch = self._registry_patch(signature, stable_unique=stable_unique)
        ledger = None
        raw_payload = {
            "acquisition_need": acquisition.model_dump(mode="json") if acquisition else None,
            "admission_ledger": None,
            "authority_scope": self._settings.authority_scope,
            "cg1_certificate_id": cg1_certificate.certificate_id if cg1_certificate else None,
            "cg1_content_hash": cg1_certificate.content_hash if cg1_certificate else None,
            "cg1_expected_content_hash": cg1_validation.get("expected_hash"),
            "cg2_certificate_id": cg2_certificate.certificate_id,
            "cg2_content_hash": cg2_certificate.content_hash,
            "cg2_expected_content_hash": cg2_validation["expected_hash"],
            "closed_obligations": list(closed_obligations),
            "data_trust": data_trust.model_dump(mode="json"),
            "decision": decision,
            "decisive_reason": reason,
            "decisive_reject_proof": reject_proof,
            "delta_adm_ledger": self._delta_adm_ledger().model_dump(mode="json"),
            "mechanism_witness": mechanism.model_dump(mode="json"),
            "obligations": [item.model_dump(mode="json") for item in obligations],
            "open_obligations": list(open_obligations),
            "production_promotable": (
                decision == "admit_new_lever" and self._settings.authority_scope == "production"
            ),
            "proposal_signature": _json_ready(signature),
            "reference_epoch": self.reference.reference_epoch,
            "reference_hash": self.reference.reference_hash,
            "reference_versions": dict(sorted(self.reference.component_versions.items())),
            "registry_patch": patch.model_dump(mode="json") if patch else None,
            "stable_unique": stable_unique.model_dump(mode="json"),
            "validator_version": GROUNDING_ADMISSION_VALIDATOR_VERSION,
        }
        if patch is not None:
            provisional_hash = gy_content_hash(
                {
                    "schema_version": GROUNDING_ADMISSION_SCHEMA_VERSION,
                    **raw_payload,
                }
            )
            provisional_id = f"cg3_cert_{provisional_hash.removeprefix('sha256:')[:16]}"
            ledger = self._admission_ledger(
                patch,
                admission_certificate_id=provisional_id,
            )
            raw_payload["admission_ledger"] = ledger.model_dump(mode="json")
        content_hash = gy_content_hash(
            {
                "schema_version": GROUNDING_ADMISSION_SCHEMA_VERSION,
                **raw_payload,
            }
        )
        return GroundingAdmissionCertificate(
            certificate_id=f"cg3_cert_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **raw_payload,
        )

    def apply_registry_patch(
        self,
        certificate: GroundingAdmissionCertificate,
        cg2_certificate: GroundingDecisionCertificate,
        *,
        cg1_certificate: GroundingRelationCertificate | None = None,
    ) -> RegistryPatchApplicationResolution:
        """Re-resolve and apply a registry patch claim in shadow scope."""

        if self._settings.disable_registry_patch_reresolution:
            patch = certificate.registry_patch
            return RegistryPatchApplicationResolution(
                applied=patch is not None,
                reason="registry_patch_re_resolution_disabled_contract_testing",
                certificate_patch_id=patch.patch_id if patch else None,
                patch=patch,
            )
        recomputed = self.decide(cg2_certificate, cg1_certificate=cg1_certificate)
        certificate_patch = certificate.registry_patch
        recomputed_patch = recomputed.registry_patch
        if (
            certificate.decision != recomputed.decision
            or certificate.content_hash != recomputed.content_hash
            or certificate_patch is None
            or recomputed_patch is None
            or certificate_patch.patch_id != recomputed_patch.patch_id
        ):
            return RegistryPatchApplicationResolution(
                applied=False,
                reason="admission_re_resolution_mismatch",
                recomputed_certificate_id=recomputed.certificate_id,
                recomputed_patch_id=recomputed_patch.patch_id if recomputed_patch else None,
                certificate_patch_id=certificate_patch.patch_id if certificate_patch else None,
            )
        return RegistryPatchApplicationResolution(
            applied=True,
            reason="owner_re_resolution_passed_shadow_patch_applied",
            recomputed_certificate_id=recomputed.certificate_id,
            recomputed_patch_id=recomputed_patch.patch_id,
            certificate_patch_id=certificate_patch.patch_id,
            patch=recomputed_patch,
        )

    @property
    def _engine(self) -> GroundingRelationEngine:
        if self._relation_engine is None:
            self._relation_engine = GroundingRelationEngine(self.reference)
        return self._relation_engine

    def _stable_unique(self, signature: Mapping[str, Any]) -> StableUniqueResolution:
        completions = _admissible_completions(signature, self.reference)
        if self._settings.disable_stable_unique and completions:
            first = completions[0]
            return StableUniqueResolution(
                stable=True,
                reason="stable_unique_disabled_contract_testing",
                completions=(first,),
                stable_new_lever_key=_lever_key(signature, first.target_slot),
            )
        if not completions:
            return StableUniqueResolution(
                stable=False,
                reason="no_admissible_completion",
                completions=(),
            )
        if len(completions) > 1 or any(item.kind == "contested" for item in completions):
            return StableUniqueResolution(
                stable=False,
                reason="multiple_incompatible_completions",
                completions=completions,
            )
        completion = completions[0]
        if completion.kind != "existing_slot":
            return StableUniqueResolution(
                stable=False,
                reason="new_slot_requires_acquisition",
                completions=completions,
            )
        return StableUniqueResolution(
            stable=True,
            reason="single_existing_world_slot_completion",
            completions=completions,
            stable_new_lever_key=_lever_key(signature, completion.target_slot),
        )

    def _mechanism_witness(
        self,
        signature: Mapping[str, Any],
    ) -> MechanismWitnessResolution:
        target = _first_text(signature.get("X_do") or signature.get("target"))
        outcome = _first_text(signature.get("outcome"))
        caller_claims = _caller_mechanism_claims(signature)
        if self._settings.disable_mechanism_witness_resolution and caller_claims:
            return MechanismWitnessResolution(
                status="closed",
                owner="caller_claim_accepted_by_contract_testing_mutation",
                evidence_refs=tuple(caller_claims),
                evidence={"caller_claims_ignored": False},
            )
        if self._settings.disable_do_path_resolution:
            matches = [
                edge
                for edge in self.reference.essential_edges.values()
                if edge.modality in _L2_MECHANISM_MODALITIES
                and edge.status == "confirmed"
                and _edge_mentions_mechanism(edge, target=target, outcome=outcome)
            ]
            if matches:
                return MechanismWitnessResolution(
                    status="closed",
                    owner="text_mechanism_contract_testing_mutation",
                    evidence_refs=tuple(_edge_key_text(edge.key) for edge in matches),
                    evidence={
                        "caller_claims_ignored": bool(caller_claims),
                        "mutation": "do_path_resolution_disabled",
                    },
                )
        actuatability = _target_actuatability(
            self.reference,
            target,
            atoms=self._engine.reference_atoms,
            allow_policy_map_mention=self._settings.allow_policy_map_mention_actuatability,
        )
        if not target or not outcome or target == outcome or not actuatability["actuatable"]:
            return MechanismWitnessResolution(
                status="open",
                owner="L2/SKG causal evidence",
                evidence_refs=tuple(
                    _edge_key_text(edge.key)
                    for edge in _contested_causal_edges(
                        self.reference,
                        target=target,
                        outcome=outcome,
                    )
                ),
                evidence={
                    "actuatability": actuatability,
                    "caller_claims_ignored": bool(caller_claims),
                    "reason": "do_target_not_actuatable_or_no_mediated_outcome_path",
                    "target": target,
                    "outcome": outcome,
                },
            )
        path = _confirmed_causal_path(self.reference, source=target, outcome=outcome, max_depth=3)
        path_trust, _path_ref = _mechanism_edge_trust_cap(
            self.reference,
            tuple(_edge_key_text(edge.key) for edge in path),
            use_best=self._settings.use_best_edge_trust,
        )
        if (
            (len(path) == 1 and path_trust >= self._settings.data_trust_floor)
            or (self._settings.allow_composed_mechanism_witness and path)
        ):
            return MechanismWitnessResolution(
                status="closed",
                owner="L2/SKG causal evidence",
                evidence_refs=tuple(_edge_key_text(edge.key) for edge in path),
                evidence={
                    "caller_claims_ignored": bool(caller_claims),
                    "path": [_edge_structural_endpoints(edge) for edge in path],
                    "path_length": len(path),
                    "path_trust_cap": path_trust,
                    "source_modalities": sorted({edge.modality for edge in path}),
                },
            )
        if path:
            return MechanismWitnessResolution(
                status="open",
                owner="L2/SKG causal evidence",
                evidence_refs=tuple(_edge_key_text(edge.key) for edge in path),
                evidence={
                    "caller_claims_ignored": bool(caller_claims),
                    "path": [_edge_structural_endpoints(edge) for edge in path],
                    "path_length": len(path),
                    "path_trust_cap": path_trust,
                    "reason": (
                        "mechanism_composition_unverified"
                        if len(path) > 1
                        else "mechanism_trust_below_floor"
                    ),
                    "source_modalities": sorted({edge.modality for edge in path}),
                    "trust_floor": self._settings.data_trust_floor,
                },
            )
        contested = _contested_causal_edges(self.reference, target=target, outcome=outcome)
        return MechanismWitnessResolution(
            status="open",
            owner="L2/SKG causal evidence",
            evidence_refs=tuple(_edge_key_text(edge.key) for edge in contested),
            evidence={
                "contested_count": len(contested),
                "caller_claims_ignored": bool(caller_claims),
                "target": target,
                "outcome": outcome,
            },
        )

    def _data_trust(self, mechanism: MechanismWitnessResolution) -> DataTrustResolution:
        edge_cap, edge_ref = _mechanism_edge_trust_cap(
            self.reference,
            mechanism.evidence_refs,
            use_best=self._settings.use_best_edge_trust,
        )
        registry_cap = 0.0
        registry_ref = None
        if (
            self._settings.authority_scope == "contract_testing"
            and self._settings.allow_substrate_registry_authority
        ):
            registry_cap, registry_ref = _substrate_registry_trust_cap(
                self._contract_testing_substrate_registry
            )
        resolved = max(registry_cap, edge_cap)
        evidence_ref = registry_ref or edge_ref
        if resolved >= self._settings.data_trust_floor:
            return DataTrustResolution(
                status="closed",
                owner="CG0/L2 owner-lifted L5 trust signals",
                trust_floor=self._settings.data_trust_floor,
                resolved_trust_cap=resolved,
                evidence_ref=evidence_ref,
                reason="l5_trust_floor_met",
            )
        return DataTrustResolution(
            status="open",
            owner="CG0/L2 owner-lifted L5 trust signals",
            trust_floor=self._settings.data_trust_floor,
            resolved_trust_cap=resolved,
            evidence_ref=evidence_ref,
            reason="l5_trust_floor_not_met",
        )

    def _novel_irreducible(
        self,
        signature: Mapping[str, Any],
        *,
        cg1_certificate: GroundingRelationCertificate | None,
    ) -> AdmissionObligationCheck:
        if self._settings.disable_novel_irreducible:
            return _obligation(
                "novel_irreducible",
                True,
                "novel_irreducible_disabled_contract_testing",
                "CG0/L6 atom universe",
                {"mutation": "disabled"},
            )
        existing = _matching_existing_atom(
            signature,
            self._engine.reference_atoms,
            disable_denotation_novelty=self._settings.disable_denotation_novelty,
            explicit_only_denotation_match=self._settings.explicit_only_denotation_match,
            cg1_relation=cg1_certificate.selected_relation if cg1_certificate else None,
        )
        return _obligation(
            "novel_irreducible",
            existing is None,
            "no_existing_atom_paraphrase_bundle_or_specialization",
            "CG0/L6 atom universe",
            {
                "existing_atom_id": existing.get("atom_id") if existing else None,
                "existing_atom_match_kind": existing.get("match_kind") if existing else None,
                "existing_atom_match_basis": existing.get("match_basis") if existing else None,
                "existing_atom_operator": existing.get("operator") if existing else None,
                "operator_denotation_proof": (
                    existing.get("operator_denotation_proof") if existing else None
                ),
            },
        )

    def _obligations(
        self,
        signature: Mapping[str, Any],
        *,
        stable_unique: StableUniqueResolution,
        mechanism: MechanismWitnessResolution,
        data_trust: DataTrustResolution,
        novel_irreducible: AdmissionObligationCheck,
        cg2_validation: Mapping[str, Any],
        cg1_validation: Mapping[str, Any],
    ) -> tuple[AdmissionObligationCheck, ...]:
        target = _first_text(signature.get("X_do") or signature.get("target"))
        op = _first_text(signature.get("op"))
        estimand = _first_text(signature.get("estimand"))
        admissibility = _first_text(signature.get("admissibility"))
        actuatability = _target_actuatability(
            self.reference,
            target,
            atoms=self._engine.reference_atoms,
            allow_policy_map_mention=self._settings.allow_policy_map_mention_actuatability,
        )
        return (
            _obligation(
                "parse",
                bool(op and target),
                "coherent_do_hypothesis_parsed",
                "CG1 parsed proposal",
                {"operator": op, "target": target},
            ),
            novel_irreducible,
            _obligation(
                "type",
                _target_is_world_slot(self.reference, target) or _target_acquirable(target),
                "operator_target_typed_against_world_model",
                "WMR type system",
                {"target": target, "operator": op},
            ),
            _obligation(
                "world_bindable_or_acquirable",
                bool(stable_unique.completions),
                "target_has_existing_or_acquirable_world_completion",
                "WMR/CG0 reference",
                {"completion_count": len(stable_unique.completions)},
            ),
            _obligation(
                "do_semantics",
                bool(
                    op
                    and target
                    and (signature.get("x_do") or signature.get("params"))
                    and actuatability["actuatable"]
                ),
                "actuatable_do_semantics_present",
                "CG1 do_AST + WMR policy slot taxonomy",
                {
                    "actuatability": actuatability,
                    "x_do": _json_ready(signature.get("x_do") or {}),
                },
            ),
            _obligation(
                "mechanism_witness",
                mechanism.status == "closed",
                "real_l2_skg_mechanism_witness_resolved",
                mechanism.owner,
                mechanism.model_dump(mode="json"),
            ),
            _obligation(
                "estimand",
                bool(estimand and estimand != "unknown"),
                "effect_estimand_defined",
                "CG1 proposal signature",
                {"estimand": estimand},
            ),
            _obligation(
                "admissibility",
                bool(admissibility and admissibility not in {"candidate_unverified", "failed"}),
                "l3_admissibility_closed",
                "L3/Lex admissibility",
                {"admissibility": admissibility},
            ),
            _obligation(
                "data_trust",
                data_trust.status == "closed",
                "l5_data_trust_floor_met",
                data_trust.owner,
                data_trust.model_dump(mode="json"),
            ),
            _obligation(
                "ambiguity",
                stable_unique.stable,
                "stable_unique_single_completion",
                "CG0 credal completions",
                stable_unique.model_dump(mode="json"),
            ),
            _obligation(
                "cg2_novel_handoff",
                bool(cg2_validation.get("valid")),
                "cg2_novel_candidate_handoff_resolved",
                "CG2 GroundingDecisionCertificate",
                dict(cg2_validation),
            ),
            _obligation(
                "cg1_content_bound",
                bool(cg1_validation.get("valid")),
                "cg1_proposal_certificate_content_bound_to_cg2",
                "CG1 GroundingRelationCertificate",
                dict(cg1_validation),
            ),
        )

    def _decision_kind(
        self,
        signature: Mapping[str, Any],
        *,
        open_obligations: tuple[str, ...],
        stable_unique: StableUniqueResolution,
        mechanism: MechanismWitnessResolution,
        data_trust: DataTrustResolution,
        novel_irreducible: AdmissionObligationCheck,
        reject_proof: str | None,
        cg2_validation: Mapping[str, Any],
        cg1_validation: Mapping[str, Any],
    ) -> tuple[GroundingAdmissionDecision, GroundingAdmissionReason, AcquisitionNeed | None]:
        if (
            novel_irreducible.status == "open"
            and cg2_validation.get("valid")
            and cg1_validation.get("valid")
        ):
            return "non_new", "novel_irreducible_failed_existing_atom", None
        if reject_proof is not None:
            return "reject_hallucination", reject_proof, None
        if not cg2_validation.get("valid"):
            return (
                "acquire_then_decide",
                "cg2_revalidation_failed",
                AcquisitionNeed(
                    blocker_id="cg2_novel_handoff_required",
                    needed_evidence=("current_cg2_novel_candidate_certificate",),
                ),
            )
        if not cg1_validation.get("valid"):
            return (
                "acquire_then_decide",
                "cg1_binding_missing_or_mismatch",
                AcquisitionNeed(
                    blocker_id="cg1_content_bound_replay_required",
                    needed_evidence=("matching_cg1_grounding_relation_certificate",),
                ),
            )
        if novel_irreducible.status == "open":
            return "non_new", "novel_irreducible_failed_existing_atom", None
        if self._settings.reject_unknown and open_obligations:
            return "reject_hallucination", "impossible_type", None
        if mechanism.status == "open":
            mechanism_reason = _first_text(mechanism.evidence.get("reason"))
            if mechanism_reason == "mechanism_composition_unverified":
                return (
                    "acquire_then_decide",
                    "mechanism_composition_unverified",
                    AcquisitionNeed(
                        blocker_id="mechanism_composition_unverified",
                        needed_evidence=("L2_direct_causal_witness_or_transport_assumptions",),
                    ),
                )
            if mechanism_reason == "mechanism_trust_below_floor":
                return (
                    "acquire_then_decide",
                    "data_trust_below_floor",
                    AcquisitionNeed(
                        blocker_id="l5_data_trust_floor_required",
                        needed_evidence=("higher_trust_L2_direct_causal_witness",),
                    ),
                )
            return (
                "acquire_then_decide",
                "mechanism_witness_missing",
                AcquisitionNeed(
                    blocker_id="mechanism_witness_required",
                    needed_evidence=("L2_CAUSAL_CLAIM_or_L2_CAUSAL_EDGE",),
                ),
            )
        if data_trust.status == "open":
            return (
                "acquire_then_decide",
                "data_trust_below_floor",
                AcquisitionNeed(
                    blocker_id="l5_data_trust_floor_required",
                    needed_evidence=("L5_trust_tier_for_mechanism_evidence",),
                ),
            )
        if not stable_unique.stable:
            blocker = "stable_unique_acquisition_required"
            if stable_unique.reason == "new_slot_requires_acquisition":
                return (
                    "acquire_then_decide",
                    "world_slot_acquisition_required",
                    AcquisitionNeed(
                        blocker_id="world_slot_measurement_required",
                        needed_evidence=("WMR_WORLD_SLOT_or_GY-N7_NEW_SLOT_measurement",),
                    ),
                )
            return (
                "acquire_then_decide",
                "ambiguous_completion_requires_acquisition",
                AcquisitionNeed(
                    blocker_id=blocker,
                    needed_evidence=("disambiguating_CG0_completion_or_GY-N7_measurement",),
                ),
            )
        hard_open = tuple(item for item in open_obligations if item in _HARD_OBLIGATIONS)
        if hard_open:
            return (
                "acquire_then_decide",
                "open_obligation",
                AcquisitionNeed(
                    blocker_id=f"{hard_open[0]}_required",
                    needed_evidence=hard_open,
                ),
            )
        return "admit_new_lever", "all_obligations_closed", None

    def _registry_patch(
        self,
        signature: Mapping[str, Any],
        *,
        stable_unique: StableUniqueResolution,
    ) -> GroundingLeverRegistryPatch:
        target = stable_unique.completions[0].target_slot
        operator = _canonical_token(_first_text(signature.get("op")))
        domain = _domain_from_signature(signature, self.reference, target)
        fields = {
            "application_status": "contract_testing_shadow"
            if self._settings.authority_scope == "contract_testing"
            else "shadow_applied",
            "authority_scope": self._settings.authority_scope,
            "decision_front_created": False,
            "idempotency_key": gy_content_hash(
                {
                    "operator_kind": operator,
                    "reference_hash": self.reference.reference_hash,
                    "target_world_slots": [target],
                }
            ),
            "lex_map": {},
            "operator_kind": operator,
            "parameter_domain": domain,
            "reversible": True,
            "source_reference_epoch": self.reference.reference_epoch,
            "source_reference_hash": self.reference.reference_hash,
            "target_world_slots": (target,),
        }
        content_hash = gy_content_hash(
            {"owner": "GY-S0/L6 intervention substrate", **_json_ready(fields)}
        )
        return GroundingLeverRegistryPatch(
            patch_id=f"cg3_patch_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **fields,
        )

    def _admission_ledger(
        self,
        patch: GroundingLeverRegistryPatch,
        *,
        admission_certificate_id: str,
    ) -> GroundingAdmissionLedger:
        fields = {
            "admission_certificate_id": admission_certificate_id,
            "application_scope": "shadow_until_live_gy_s0_writer_is_declared_safe",
            "authority_scope": self._settings.authority_scope,
            "patch_ids": (patch.patch_id,),
            "reversible": True,
        }
        content_hash = gy_content_hash(fields)
        return GroundingAdmissionLedger(
            ledger_id=f"cg3_ledger_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **fields,
        )

    def _delta_adm_ledger(self) -> DeltaAdmissionLedger:
        entries = tuple(
            DeltaAdmissionLedgerEntry(
                component=component,
                spend=float(bound),
                bound=float(bound),
                source="conservative_cold_start_obligation_soundness_bound",
                conservative_bound=True,
            )
            for component, bound in sorted(self._settings.component_risk_bounds.items())
        )
        total = round(sum(entry.spend for entry in entries), 12)
        return DeltaAdmissionLedger(
            delta_adm_budget=self._settings.delta_adm_budget,
            entries=entries,
            total_spend=total,
            within_budget=total <= self._settings.delta_adm_budget,
            guarantee_statement=(
                "P(hallucinated admit) <= delta_adm conditional on obligation/"
                "validator soundness and CG0 reference completeness; GY-N11 confidence "
                "ledger composition is not wired."
            ),
        )


def apply_grounding_admission_registry_patch(
    certificate: GroundingAdmissionCertificate,
    cg2_certificate: GroundingDecisionCertificate,
    reference: CredalReference,
    *,
    cg1_certificate: GroundingRelationCertificate | None = None,
) -> RegistryPatchApplicationResolution:
    """Re-resolve a CG3 certificate before applying its GY-S0 patch claim."""

    return GroundingAdmissionEngine(reference).apply_registry_patch(
        certificate,
        cg2_certificate,
        cg1_certificate=cg1_certificate,
    )


def recompute_grounding_admission_content_hash(
    certificate_or_payload: GroundingAdmissionCertificate | Mapping[str, Any],
) -> str:
    """Recompute a CG3 admission certificate hash from its body."""

    payload = serialization.artifact_self_identity_projection(certificate_or_payload)
    payload.pop("certificate_id", None)
    return gy_content_hash(payload)


def recompute_registry_patch_content_hash(
    patch_or_payload: GroundingLeverRegistryPatch | Mapping[str, Any],
) -> str:
    """Recompute a registry patch content hash."""

    payload = serialization.artifact_self_identity_projection(patch_or_payload)
    payload.pop("patch_id", None)
    return gy_content_hash(payload)


def recompute_admission_ledger_content_hash(
    ledger_or_payload: GroundingAdmissionLedger | Mapping[str, Any],
) -> str:
    """Recompute a CG3 admission ledger content hash."""

    payload = serialization.artifact_self_identity_projection(ledger_or_payload)
    payload.pop("ledger_id", None)
    return gy_content_hash(payload)


def _validate_cg2_binding(
    certificate: GroundingDecisionCertificate,
    reference: CredalReference,
) -> dict[str, Any]:
    expected_hash = recompute_grounding_decision_content_hash(certificate)
    valid = (
        certificate.content_hash == expected_hash
        and certificate.certificate_id == f"cg2_cert_{expected_hash.removeprefix('sha256:')[:16]}"
        and certificate.decision == "novel_candidate"
        and certificate.cg3_handoff
        and certificate.reference_epoch == reference.reference_epoch
        and certificate.reference_hash == reference.reference_hash
    )
    reason = "cg2_novel_candidate_handoff_resolved" if valid else "cg2_not_novel_candidate"
    return {
        "valid": valid,
        "expected_hash": expected_hash,
        "decision": certificate.decision,
        "cg3_handoff": certificate.cg3_handoff,
        "reason": reason,
    }


def _validate_cg1_binding(
    cg2_certificate: GroundingDecisionCertificate,
    cg1_certificate: GroundingRelationCertificate | None,
) -> dict[str, Any]:
    if cg1_certificate is None:
        return {
            "valid": False,
            "expected_hash": None,
            "reason": "cg1_certificate_missing",
        }
    expected_hash = recompute_grounding_relation_content_hash(cg1_certificate)
    valid = (
        cg1_certificate.content_hash == expected_hash
        and cg1_certificate.content_hash == cg2_certificate.cg1_content_hash
        and expected_hash == cg2_certificate.cg1_expected_content_hash
        and cg1_certificate.certificate_id == cg2_certificate.cg1_certificate_id
    )
    return {
        "valid": valid,
        "expected_hash": expected_hash,
        "reason": "cg1_content_bound" if valid else "cg1_content_mismatch",
    }


def _signature_from_inputs(
    cg2_certificate: GroundingDecisionCertificate,
    cg1_certificate: GroundingRelationCertificate | None,
) -> dict[str, Any]:
    if cg1_certificate is not None:
        proposal_signature = _mapping(cg1_certificate.proposal_signature)
        hypotheses = _sequence(proposal_signature.get("hypotheses"))
        for hypothesis in hypotheses:
            payload = _mapping(hypothesis)
            signature = _mapping(payload.get("signature"))
            if signature:
                return dict(signature)
        signature = _mapping(proposal_signature.get("signature"))
        if signature:
            return dict(signature)
    facts: dict[str, Any] = {}
    for obligation in cg2_certificate.obligations:
        evidence = _mapping(obligation.evidence)
        if "operator" in evidence:
            facts["op"] = evidence.get("operator")
        if "target" in evidence:
            facts["X_do"] = (evidence.get("target"),)
        if "estimand" in evidence:
            facts["estimand"] = evidence.get("estimand")
        if "admissibility" in evidence:
            facts["admissibility"] = evidence.get("admissibility")
        if "unit" in evidence:
            facts["unit"] = evidence.get("unit")
    return facts


def _admissible_completions(
    signature: Mapping[str, Any],
    reference: CredalReference,
) -> tuple[AdmissionCompletion, ...]:
    target = _first_text(signature.get("X_do") or signature.get("target"))
    if not target:
        return ()
    completions: list[AdmissionCompletion] = []
    for edge in reference.essential_edges.values():
        if edge.modality != "WMR_WORLD_SLOT" or edge.edge_id != target:
            continue
        if edge.status == "confirmed":
            completions.append(
                AdmissionCompletion(
                    kind="existing_slot",
                    target_slot=target,
                    evidence_ref=_edge_key_text(edge.key),
                    status=edge.status,
                    reason="existing_wmr_world_slot",
                )
            )
        elif edge.status == "contested":
            completions.append(
                AdmissionCompletion(
                    kind="contested",
                    target_slot=target,
                    evidence_ref=_edge_key_text(edge.key),
                    status=edge.status,
                    reason="target_world_slot_contested",
                )
            )
    for edge in reference.essential_edges.values():
        if (
            edge.modality not in _L2_CONTESTED_MECHANISM_MODALITIES
            or edge.status != "contested"
        ):
            continue
        endpoints = _edge_structural_endpoints(edge)
        if endpoints["src"] == target and endpoints["dst"] == _first_text(signature.get("outcome")):
            completions.append(
                AdmissionCompletion(
                    kind="contested",
                    target_slot=target,
                    evidence_ref=_edge_key_text(edge.key),
                    status=edge.status,
                    reason="mechanism_maps_to_contested_edge",
                )
            )
    if not completions and _target_acquirable(target):
        completions.append(
            AdmissionCompletion(
                kind="NEW_SLOT_acquirable",
                target_slot=target,
                evidence_ref="GY-N7.new_slot_acquisition",
                status="acquirable",
                reason="syntactically_acquirable_new_slot",
            )
        )
    return tuple(sorted(completions, key=lambda item: (item.kind, item.evidence_ref)))


def _proven_hallucination(
    signature: Mapping[str, Any],
    reference: CredalReference,
    *,
    disable_do_path_resolution: bool = False,
    enable_keyword_proxy_reject: bool = False,
) -> GroundingAdmissionReason | None:
    target = _first_text(signature.get("X_do") or signature.get("target"))
    op = _first_text(signature.get("op"))
    outcome = _first_text(signature.get("outcome"))
    if outcome and not op and not target:
        return "outcome_wish"
    if target and outcome and target == outcome and not disable_do_path_resolution:
        return "outcome_wish"
    if enable_keyword_proxy_reject and "proxy" in " ".join([op, target, outcome]).casefold():
        return "proxy_manipulation"
    if _measurement_proxy_proven(reference, target=target, outcome=outcome):
        return "proxy_manipulation"
    if target and not _target_is_world_slot(reference, target) and not _target_acquirable(target):
        return "impossible_type"
    return None


def _matching_existing_atom(
    signature: Mapping[str, Any],
    atoms: Sequence[Any],
    *,
    disable_denotation_novelty: bool = False,
    explicit_only_denotation_match: bool = False,
    cg1_relation: str | None = None,
) -> dict[str, str] | None:
    target = _first_text(signature.get("X_do") or signature.get("target"))
    outcome = _first_text(signature.get("outcome"))
    estimand = _first_text(signature.get("estimand"))
    sign = _first_text(signature.get("sign"))
    scope = _first_text(signature.get("scope"))
    population = _first_text(signature.get("population"))
    operator = _canonical_operator(_first_text(signature.get("op")))
    for atom in atoms:
        atom_sig = atom.signature
        cg1_claim = _mapping(atom_sig.modal_claims.get("CG1"))
        explicit = cg1_claim.get("explicit_knob_world_slot") is True
        if explicit_only_denotation_match and not explicit:
            continue
        atom_target = atom_sig.X_do[0] if atom_sig.X_do else ""
        atom_outcome = atom_sig.outcome[0] if atom_sig.outcome else ""
        if disable_denotation_novelty:
            continue
        if (
            target
            and target == atom_target
            and (not outcome or not atom_outcome or outcome == atom_outcome)
            and (not estimand or estimand == (atom_sig.estimand or ""))
            and (not sign or sign == (atom_sig.sign or ""))
            and (not scope or scope == (atom_sig.scope or ""))
            and (not population or population == (atom_sig.population or ""))
        ):
            atom_operator = _canonical_operator(atom_sig.op)
            operator_resolved = bool(
                (operator and atom_operator and operator == atom_operator)
                or cg1_relation in {"exact", "certified-specialization"}
            )
            return {
                "atom_id": str(atom.atom_id),
                "match_basis": "explicit_binding" if explicit else "compatibility_derived",
                "match_kind": "resolved_proof" if operator_resolved else "signature_only",
                "operator": str(atom_sig.op),
                "operator_denotation_proof": "resolved" if operator_resolved else "unresolved",
            }
    return None


def _target_is_world_slot(reference: CredalReference, target: str) -> bool:
    if not target:
        return False
    return any(
        edge.modality == "WMR_WORLD_SLOT" and edge.edge_id == target and edge.status == "confirmed"
        for edge in reference.essential_edges.values()
    )


def _target_acquirable(target: str) -> bool:
    if not target:
        return False
    return "." in target and all(part for part in target.split("."))


def _target_actuatability(
    reference: CredalReference,
    target: str,
    *,
    atoms: Sequence[Any] = (),
    allow_policy_map_mention: bool = False,
) -> dict[str, Any]:
    if not target:
        return {"actuatable": False, "reason": "target_missing"}
    if not _target_is_world_slot(reference, target):
        return {
            "actuatable": _target_acquirable(target),
            "reason": (
                "new_slot_acquisition_required"
                if _target_acquirable(target)
                else "slot_missing"
            ),
        }
    if _slot_is_measurement_or_reporting(reference, target):
        return {
            "actuatable": False,
            "reason": "wmr_measurement_or_reporting_slot",
            "target": target,
        }
    metadata = _slot_policy_input_metadata(reference, target)
    if metadata:
        return {
            "actuatable": True,
            "reason": "wmr_positive_policy_input_metadata",
            "target": target,
            "evidence": metadata,
        }
    atom_evidence = _positive_atom_write_evidence(atoms, target)
    if atom_evidence:
        return {
            "actuatable": True,
            "reason": "cg1_explicit_non_identity_write_target",
            "target": target,
            "evidence": atom_evidence,
        }
    if allow_policy_map_mention and _target_is_policy_slot(reference, target):
        return {
            "actuatable": True,
            "reason": "wmr_policy_map_mention_contract_testing",
            "target": target,
        }
    return {
        "actuatable": False,
        "reason": "no_positive_writability_proof",
        "target": target,
    }


def _target_is_policy_slot(reference: CredalReference, target: str) -> bool:
    if not target:
        return False
    for edge in reference.essential_edges.values():
        if edge.modality != "WMR_POLICY_SLOT_MAP" or edge.status != "confirmed":
            continue
        for completion in edge.admissible_completions:
            if target in {
                _first_text(completion.value.get("world_slot")),
                _first_text(completion.value.get("slot_id")),
                _first_text(completion.value.get("state_path")),
            }:
                return True
    return False


def _slot_is_measurement_or_reporting(reference: CredalReference, target: str) -> bool:
    metadata: list[Mapping[str, Any]] = []
    for edge in reference.essential_edges.values():
        if edge.modality != "WMR_WORLD_SLOT" or edge.edge_id != target:
            continue
        metadata.append(edge.provenance)
        metadata.extend(completion.value for completion in edge.admissible_completions)
    for item in metadata:
        role = _first_text(
            item.get("slot_role")
            or item.get("role")
            or item.get("measurement_role")
            or item.get("kind")
        ).casefold()
        if role in {"measurement", "reporting", "proxy", "outcome_measurement"}:
            return True
        if _bool(item.get("is_measurement")) or _bool(item.get("is_reporting")):
            return True
        signals = _mapping(item.get("signals"))
        signal_role = _first_text(
            signals.get("slot_role")
            or signals.get("role")
            or signals.get("measurement_role")
            or signals.get("kind")
        ).casefold()
        if signal_role in {"measurement", "reporting", "proxy", "outcome_measurement"}:
            return True
        if _bool(signals.get("is_measurement")) or _bool(signals.get("is_reporting")):
            return True
        if _first_text(item.get("temporal_granularity")).casefold() == "flow":
            return True
        if _first_text(signals.get("temporal_granularity")).casefold() == "flow":
            return True
    return False


def _slot_policy_input_metadata(reference: CredalReference, target: str) -> dict[str, Any] | None:
    metadata: list[Mapping[str, Any]] = []
    for edge in reference.essential_edges.values():
        if edge.modality not in {"WMR_WORLD_SLOT", "WMR_POLICY_SLOT_MAP"} or edge.edge_id != target:
            continue
        metadata.append(edge.provenance)
        metadata.extend(completion.value for completion in edge.admissible_completions)
    for item in metadata:
        role = _first_text(item.get("slot_role") or item.get("role") or item.get("kind")).casefold()
        if role in {"policy_input", "write_target", "actuatable", "control"}:
            return {"role": role, "source": _first_text(item.get("source"))}
        if _bool(item.get("is_policy_input")) or _bool(item.get("is_writable")):
            return {
                "flag": "is_policy_input_or_writable",
                "source": _first_text(item.get("source")),
            }
        signals = _mapping(item.get("signals"))
        signal_role = _first_text(
            signals.get("slot_role") or signals.get("role") or signals.get("kind")
        ).casefold()
        if signal_role in {"policy_input", "write_target", "actuatable", "control"}:
            return {"role": signal_role, "source": _first_text(item.get("source"))}
        if _bool(signals.get("is_policy_input")) or _bool(signals.get("is_writable")):
            return {
                "flag": "is_policy_input_or_writable",
                "source": _first_text(item.get("source")),
            }
    return None


def _positive_atom_write_evidence(atoms: Sequence[Any], target: str) -> dict[str, str] | None:
    for atom in atoms:
        atom_sig = atom.signature
        cg1_claim = _mapping(atom_sig.modal_claims.get("CG1"))
        if cg1_claim.get("explicit_knob_world_slot") is not True:
            continue
        atom_target = atom_sig.X_do[0] if atom_sig.X_do else ""
        atom_outcome = atom_sig.outcome[0] if atom_sig.outcome else ""
        if atom_target == target and atom_outcome and atom_outcome != target:
            return {
                "atom_id": str(atom.atom_id),
                "operator": str(atom_sig.op),
                "outcome": atom_outcome,
            }
    return None


def _measurement_proxy_proven(
    reference: CredalReference,
    *,
    target: str,
    outcome: str,
) -> bool:
    if not target or not outcome or not _slot_is_measurement_or_reporting(reference, target):
        return False
    return bool(_confirmed_causal_path(reference, source=target, outcome=outcome))


def _confirmed_causal_path(
    reference: CredalReference,
    *,
    source: str,
    outcome: str,
    max_depth: int = 3,
) -> tuple[CredalReferenceEdge, ...]:
    if not source or not outcome or source == outcome:
        return ()
    adjacency: dict[str, list[tuple[str, CredalReferenceEdge]]] = {}
    for edge in reference.essential_edges.values():
        if edge.modality not in _L2_MECHANISM_MODALITIES or edge.status != "confirmed":
            continue
        endpoints = _edge_structural_endpoints(edge)
        src = endpoints["src"]
        dst = endpoints["dst"]
        if not src or not dst or src == dst:
            continue
        adjacency.setdefault(src, []).append((dst, edge))
    queue: deque[tuple[str, tuple[CredalReferenceEdge, ...]]] = deque([(source, ())])
    seen = {source}
    while queue:
        node, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        for dst, edge in sorted(
            adjacency.get(node, ()),
            key=lambda item: (_edge_key_text(item[1].key), item[0]),
        ):
            next_path = (*path, edge)
            if dst == outcome:
                return next_path
            if dst in seen:
                continue
            seen.add(dst)
            queue.append((dst, next_path))
    return ()


def _contested_causal_edges(
    reference: CredalReference,
    *,
    target: str,
    outcome: str,
) -> tuple[CredalReferenceEdge, ...]:
    if not target or not outcome:
        return ()
    matches: list[CredalReferenceEdge] = []
    for edge in reference.essential_edges.values():
        if edge.modality not in _L2_CONTESTED_MECHANISM_MODALITIES or edge.status != "contested":
            continue
        endpoints = _edge_structural_endpoints(edge)
        if endpoints["src"] == target and endpoints["dst"] == outcome:
            matches.append(edge)
    return tuple(sorted(matches, key=lambda edge: edge.key))


def _edge_structural_endpoints(edge: CredalReferenceEdge) -> dict[str, str]:
    for completion in edge.admissible_completions:
        src = _first_text(completion.value.get("src") or completion.value.get("source"))
        dst = _first_text(
            completion.value.get("dst")
            or completion.value.get("target")
            or completion.value.get("destination")
        )
        direction = _first_text(completion.value.get("direction"))
        if src and dst and direction and src != dst:
            return {"direction": direction, "dst": dst, "src": src}
        if src and dst and direction:
            return {"direction": direction, "dst": dst, "src": src}
    return {"direction": "", "dst": "", "src": ""}


def _edge_mentions_mechanism(
    edge: CredalReferenceEdge,
    *,
    target: str,
    outcome: str,
) -> bool:
    if not target:
        return False
    haystack_items: list[str] = [edge.edge_id]
    haystack_items.extend(str(value) for value in _flatten_mapping(edge.provenance))
    for completion in edge.admissible_completions:
        haystack_items.extend(str(value) for value in _flatten_mapping(completion.value))
    haystack = " ".join(haystack_items).casefold()
    return target.casefold() in haystack and (not outcome or outcome.casefold() in haystack)


def _caller_mechanism_claims(signature: Mapping[str, Any]) -> list[str]:
    claims: list[str] = []
    for item in _sequence(signature.get("evidence")):
        text = str(item or "")
        if "mechanism" in text.casefold():
            claims.append(text)
    modal = _mapping(signature.get("modal_claims"))
    for value in modal.values():
        payload = _mapping(value)
        if payload.get("mechanism_witness") is not None:
            claims.append(json.dumps(_json_ready(payload), sort_keys=True))
    return claims


def _substrate_registry_trust_cap(registry: object | None) -> tuple[float, str | None]:
    entries = getattr(registry, "entries", None)
    if not isinstance(entries, Sequence):
        return 0.0, None
    best = 0.0
    ref = None
    for entry in entries:
        layer = str(getattr(getattr(entry, "layer", ""), "value", getattr(entry, "layer", "")))
        family = str(getattr(entry, "family_id", ""))
        trust = getattr(entry, "trust_tier", None)
        cap = float(getattr(trust, "trust_cap", 0.0) or 0.0)
        if layer == "L2" and "causal" in family and cap >= best:
            best = cap
            refs = getattr(entry, "authority_refs", ())
            ref = str(refs[0]) if refs else getattr(entry, "entry_content_hash", None)
    return best, ref


def _mechanism_edge_trust_cap(
    reference: CredalReference,
    evidence_refs: Sequence[str],
    *,
    use_best: bool = False,
) -> tuple[float, str | None]:
    refs = set(evidence_refs)
    scores: list[tuple[float, str]] = []
    for edge in reference.essential_edges.values():
        key = _edge_key_text(edge.key)
        if key not in refs:
            continue
        signals = _mapping(edge.provenance.get("signals"))
        score = max(
            _float(signals.get("trust_score")),
            _float(signals.get("confidence")),
        )
        scores.append((score, key))
    if not scores:
        return 0.0, None
    selected = max(scores) if use_best else min(scores)
    return selected[0], selected[1]


def _domain_from_signature(
    signature: Mapping[str, Any],
    reference: CredalReference,
    target: str,
) -> dict[str, Any]:
    unit = _first_text(signature.get("unit")) or _unit_for_target(reference, target)
    params = _mapping(signature.get("params"))
    values = [_float(value, default=None) for value in params.values()]
    numeric = [value for value in values if value is not None]
    max_value = max([1.0, *numeric])
    return {
        "kind": "range",
        "max_value": max_value,
        "min_value": 0.0,
        "unit": unit or None,
        "value_type": "float",
    }


def _unit_for_target(reference: CredalReference, target: str) -> str:
    for edge in reference.essential_edges.values():
        if edge.modality == "WMR_WORLD_SLOT" and edge.edge_id == target and edge.unit:
            return edge.unit
    return ""


def _lever_key(signature: Mapping[str, Any], target: str) -> str:
    return gy_content_hash(
        {
            "operator": _canonical_token(_first_text(signature.get("op"))),
            "target": target,
            "estimand": _first_text(signature.get("estimand")),
            "outcome": _first_text(signature.get("outcome")),
        }
    )


def _canonical_operator(value: object) -> str:
    text = _canonical_token(value)
    aliases = {
        "budget": "budget_allocation_multiplier",
        "budget_allocation": "budget_allocation_multiplier",
        "budget_multiplier": "budget_allocation_multiplier",
        "tax_credit": "tax_relief_rate",
        "tax_credit_rate": "tax_relief_rate",
        "income_tax_credit": "tax_relief_rate",
        "corporate_tax_credit": "tax_relief_rate",
        "payroll_tax_credit": "tax_relief_rate",
        "tax_relief": "tax_relief_rate",
    }
    return aliases.get(text, text)


def _canonical_token(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _obligation(
    obligation_id: str,
    is_closed: bool,
    closed_reason: str,
    owner: str,
    evidence: Mapping[str, Any],
) -> AdmissionObligationCheck:
    return AdmissionObligationCheck(
        obligation_id=obligation_id,
        status="closed" if is_closed else "open",
        reason=closed_reason if is_closed else f"{obligation_id}_open",
        owner=owner,
        evidence=dict(evidence),
    )


def _edge_key_text(key: tuple[str, str]) -> str:
    return f"{key[0]}::{key[1]}"


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


def _float(value: object, default: float | None = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0 if default is None else default


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return bool(value)


def _flatten_mapping(value: object) -> list[object]:
    if isinstance(value, Mapping):
        flattened: list[object] = []
        for key, item in value.items():
            flattened.append(key)
            flattened.extend(_flatten_mapping(item))
        return flattened
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        flattened = []
        for item in value:
            flattened.extend(_flatten_mapping(item))
        return flattened
    return [value]


def _json_ready(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


__all__ = [
    "GROUNDING_ADMISSION_SCHEMA_VERSION",
    "GROUNDING_ADMISSION_VALIDATOR_VERSION",
    "AcquisitionNeed",
    "AdmissionCompletion",
    "AdmissionObligationCheck",
    "DataTrustResolution",
    "DeltaAdmissionLedger",
    "DeltaAdmissionLedgerEntry",
    "GroundingAdmissionCertificate",
    "GroundingAdmissionEngine",
    "GroundingAdmissionLedger",
    "GroundingAdmissionPolicy",
    "GroundingLeverRegistryPatch",
    "MechanismWitnessResolution",
    "RegistryPatchApplicationResolution",
    "StableUniqueResolution",
    "apply_grounding_admission_registry_patch",
    "recompute_admission_ledger_content_hash",
    "recompute_grounding_admission_content_hash",
    "recompute_registry_patch_content_hash",
]
