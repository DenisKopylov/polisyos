"""CGF RT5 phrasing-invariance defense over the real grounding pipeline.

This module owns GY-CG4 / EG-PIG. It does not re-implement CG1, CG2, or CG3:
every verdict is produced by running ``GroundingRelationEngine`` ->
``GroundingBindGate`` -> ``GroundingAdmissionEngine`` over one CG0
``CredalReference``. CG4 only separates the surface channel from the
causal-evidence channel, generates adversarial phrasing transforms, compares
resolved denotations, and emits replayable audit certificates.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine
from polisyos.runtime.quality.grounding_bind import GroundingBindGate
from polisyos.runtime.quality.grounding_relation import (
    GroundingEnginePolicy,
    GroundingRelationEngine,
    parse_n4_proposal,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.credal_reference import CredalReference

GROUNDING_PHRASING_DEFENSE_SCHEMA_VERSION = (
    "policyos.runtime.grounding_phrasing_defense_certificate.v1"
)
GROUNDING_PHRASING_DEFENSE_VALIDATOR_VERSION = (
    "policyos.runtime.grounding_phrasing_defense.cg4.v1"
)

type _AuthorityScope = Literal["production", "contract_testing"]
type BaseCaseClass = Literal[
    "admit",
    "acquire",
    "reject",
    "non_new",
    "novel",
    "bind_eligible_frozen",
]
type TransformFamily = Literal[
    "synonym_alias_substitution",
    "legalistic_camouflage",
    "high_value_outcome_injection",
    "confidence_bait",
    "format_whitespace_ordering",
    "registered_lever_mimicry",
    "mechanism_changing_control",
]
type PairOutcome = Literal[
    "unchanged",
    "degraded_fail_safe",
    "lifted",
    "mechanism_changed_control",
]

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_.-]+")
_PHRASING_FAMILIES: tuple[TransformFamily, ...] = (
    "synonym_alias_substitution",
    "legalistic_camouflage",
    "high_value_outcome_injection",
    "confidence_bait",
    "format_whitespace_ordering",
    "registered_lever_mimicry",
)
_MECHANISM_CONTROL_FAMILY: TransformFamily = "mechanism_changing_control"
_SURFACE_AFFINITY_THRESHOLD = 0.62
_CAUSAL_EVIDENCE_THRESHOLD = 0.5


class _StrictModel(BaseModel):
    """Strict immutable base for CG4 runtime DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PhrasingDefensePolicy(_StrictModel):
    """Safe production CG4 settings.

    The production policy intentionally exposes no threshold, whitelist,
    denotation-label, proxy-gap, or surface-score knobs. Unsafe mutation
    switches are available only through
    ``GroundingPhrasingDefenseEngine.for_contract_testing`` and every resulting
    certificate is scoped non-authoritative.
    """


class _PhrasingDefenseRuntimeSettings(_StrictModel):
    """Internal settings populated only by production defaults or test factory."""

    authority_scope: _AuthorityScope = "production"
    allow_surface_lift: bool = False
    trust_declared_phrasing_only: bool = False
    disable_proxy_gap_capture: bool = False
    disable_sensitivity_arm: bool = False
    force_bounded_matrix: bool = False


class PhrasingDefenseBaseCase(_StrictModel):
    """One real proposal used as a base case for the attack matrix."""

    case_id: str = Field(..., min_length=1)
    case_class: BaseCaseClass
    proposal: dict[str, Any] | str


class PhrasingAttackTransform(_StrictModel):
    """One adversarial transform generated from owner data."""

    transform_id: str = Field(..., min_length=1)
    family: TransformFamily
    declared_phrasing_only: bool
    proposal: dict[str, Any] | str
    source_refs: tuple[str, ...] = ()
    description: str = Field("", min_length=0)


class GroundingSurfaceView(_StrictModel):
    """Surface-channel facts that may retrieve candidates but never decide."""

    proposal_id: str = Field(..., min_length=1)
    raw_text_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    raw_text_terms: tuple[str, ...]
    raw_operator_spelling: str | None = None
    retrieval_candidate_ids: tuple[str, ...] = ()
    retrieval_scores: dict[str, float] = Field(default_factory=dict)
    max_surface_affinity: float = Field(ge=0.0, le=1.0)
    max_surface_atom_id: str | None = None
    self_reported_confidence: float | None = Field(None, ge=0.0, le=1.0)
    rationale_present: bool = False


class GroundingEvidenceSignature(_StrictModel):
    """Canonical causal-evidence signature deciding CG1/CG2/CG3 outcomes."""

    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    resolved_denotation: dict[str, Any]
    cg1_relation_class: str = Field(..., min_length=1)
    cg1_selected_atom_id: str | None = None
    cg1_axis_relations: dict[str, str] = Field(default_factory=dict)
    cg1_critical_contradictions: tuple[str, ...] = ()
    cg1_unresolved_axes: tuple[str, ...] = ()
    cg1_solver_status: str = Field(..., min_length=1)
    cg1_unsat_core_if_any: tuple[str, ...] = ()
    cg1_residual_constraints: tuple[str, ...] = ()
    cg2_disposition: str = Field(..., min_length=1)
    cg2_decisive_reason: str = Field(..., min_length=1)
    cg2_safe_t: tuple[str, ...] = ()
    cg2_open_obligations: tuple[str, ...] = ()
    cg2_calibration_status: str = Field(..., min_length=1)
    cg2_risk_within_budget: bool
    cg3_decision: str = Field(..., min_length=1)
    cg3_decisive_reason: str = Field(..., min_length=1)
    cg3_open_obligations: tuple[str, ...] = ()
    cg3_mechanism_status: str = Field(..., min_length=1)
    cg3_mechanism_refs: tuple[str, ...] = ()
    cg3_actuatability: dict[str, Any] = Field(default_factory=dict)
    cg3_data_trust_status: str = Field(..., min_length=1)
    cg3_data_trust_cap: float = Field(ge=0.0, le=1.0)
    cg3_stable_unique: bool
    cg3_stable_unique_reason: str = Field(..., min_length=1)
    cg3_denotation_match_kind: str | None = None
    cg3_registry_patch_id: str | None = None


class GroundingPipelineDecisions(_StrictModel):
    """Gate dispositions from one real CG1->CG2->CG3 run."""

    cg1_relation: str = Field(..., min_length=1)
    cg2_decision: str = Field(..., min_length=1)
    cg3_decision: str = Field(..., min_length=1)
    cg1_rank: int = Field(ge=0)
    cg2_rank: int = Field(ge=0)
    cg3_rank: int = Field(ge=0)


class GroundingPhrasingPipelineRun(_StrictModel):
    """One real grounding pipeline run with separated channels."""

    proposal_id: str = Field(..., min_length=1)
    surface_view: GroundingSurfaceView
    evidence_signature: GroundingEvidenceSignature
    decisions: GroundingPipelineDecisions
    cg1_certificate_id: str = Field(..., min_length=1)
    cg2_certificate_id: str = Field(..., min_length=1)
    cg3_certificate_id: str = Field(..., min_length=1)


class DenotationClassification(_StrictModel):
    """Resolved transform classification; labels are never authority."""

    declared_phrasing_only: bool
    classified_phrasing_only: bool
    harness_label_trusted: bool = False
    denotation_equal: bool
    denotation_diff_axes: tuple[str, ...] = ()
    base_denotation: dict[str, Any]
    transformed_denotation: dict[str, Any]


class PhrasingPairEvaluation(_StrictModel):
    """Base-vs-transform comparison for WrongLift and sensitivity."""

    base_case_id: str = Field(..., min_length=1)
    base_case_class: BaseCaseClass
    transform_id: str = Field(..., min_length=1)
    family: TransformFamily
    classification: DenotationClassification
    base_run: GroundingPhrasingPipelineRun
    transformed_run: GroundingPhrasingPipelineRun
    evidence_signature_equal: bool
    disposition_deltas: dict[str, int]
    lifted_gate_ids: tuple[str, ...] = ()
    degraded_gate_ids: tuple[str, ...] = ()
    outcome: PairOutcome


class GroundingProxyGapRisk(_StrictModel):
    """High-surface, low-causal-evidence proxy-gap risk captured by CG4."""

    risk_id: str = Field(..., pattern=r"^cg4_proxy_gap_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    proposal_id: str = Field(..., min_length=1)
    disposition: Literal["quarantine"] = "quarantine"
    quarantine_action: Literal["adversarial_validate"] = "adversarial_validate"
    surface_affinity_score: float = Field(..., ge=0.0, le=1.0)
    causal_evidence_score: float = Field(..., ge=0.0, le=1.0)
    surface_affinity_threshold: float = Field(..., ge=0.0, le=1.0)
    causal_evidence_threshold: float = Field(..., ge=0.0, le=1.0)
    threshold_source: str = Field(..., min_length=1)
    matched_surface_atom_id: str | None = None
    low_evidence_reasons: tuple[str, ...]
    not_admissible_while_quarantined: bool
    not_bindable_while_quarantined: bool
    cg2_decision: str = Field(..., min_length=1)
    cg3_decision: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _content_hash_matches_payload(self) -> GroundingProxyGapRisk:
        expected = recompute_proxy_gap_risk_content_hash(self)
        if self.content_hash != expected:
            raise ValueError("proxy_gap_risk_content_hash_mismatch")
        expected_id = f"cg4_proxy_gap_{expected.removeprefix('sha256:')[:16]}"
        if self.risk_id != expected_id:
            raise ValueError("proxy_gap_risk_id_mismatch")
        if not self.not_admissible_while_quarantined or not self.not_bindable_while_quarantined:
            raise ValueError("proxy_gap_risk_must_not_be_admissible_or_bindable")
        return self


class QuarantineHandoffRecord(_StrictModel):
    """Honest handoff artifact for the N6 quarantine/adversarial_validate front."""

    handoff_id: str = Field(..., pattern=r"^cg4_quarantine_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    risk_id: str = Field(..., min_length=1)
    risk_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    front: Literal["quarantine"] = "quarantine"
    action: Literal["adversarial_validate"] = "adversarial_validate"
    target_surface: str = "GY-N6 QuarantineFront"
    integration_status: Literal["handoff_artifact_n6_direct_intake_not_wired"] = (
        "handoff_artifact_n6_direct_intake_not_wired"
    )
    integration_gap: str = Field(..., min_length=1)
    owner: str = "polisyos.runtime.quality.grounding_phrasing_defense"

    @model_validator(mode="after")
    def _content_hash_matches_payload(self) -> QuarantineHandoffRecord:
        expected = recompute_quarantine_handoff_content_hash(self)
        if self.content_hash != expected:
            raise ValueError("quarantine_handoff_content_hash_mismatch")
        expected_id = f"cg4_quarantine_{expected.removeprefix('sha256:')[:16]}"
        if self.handoff_id != expected_id:
            raise ValueError("quarantine_handoff_id_mismatch")
        return self


class PhrasingMatrixSummary(_StrictModel):
    """Full-denominator matrix counts."""

    cg1_proof_mode: Literal["full"] = "full"
    matrix_scope: Literal[
        "full_all_generated_transforms",
        "representative_full_cg1_slice",
    ] = "full_all_generated_transforms"
    scope_note: str = ""
    base_case_count: int = Field(ge=0)
    transform_count: int = Field(ge=0)
    phrasing_pair_count: int = Field(ge=0)
    mechanism_control_count: int = Field(ge=0)
    total_lifted: int = Field(ge=0)
    total_degraded: int = Field(ge=0)
    total_unchanged: int = Field(ge=0)
    total_mechanism_changed: int = Field(ge=0)
    family_case_denominator: dict[str, dict[str, int]] = Field(default_factory=dict)
    family_case_lifted: dict[str, dict[str, int]] = Field(default_factory=dict)
    family_case_degraded: dict[str, dict[str, int]] = Field(default_factory=dict)
    family_case_unchanged: dict[str, dict[str, int]] = Field(default_factory=dict)
    consumed_intermediate_diff_counts: dict[str, int] = Field(default_factory=dict)
    family_consumed_intermediate_diff_counts: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    self_vacuous: bool


class FullCg1Comparison(_StrictModel):
    """Bounded-vs-full CG1 comparison for one matrix slice."""

    checked: bool
    base_case_id: str | None = None
    transform_id: str | None = None
    bounded_cg1_rank: int | None = None
    full_cg1_rank: int | None = None
    bounded_not_more_permissive: bool
    bounded_relation: str | None = None
    full_relation: str | None = None


class PhrasingDefenseCertificate(_StrictModel):
    """Content-addressed CG4 audit certificate.

    The certificate is non-self-authenticating: consumers must re-run the CG4
    engine/validator to rely on any claim. The content hash only detects drift
    or forgery in the replay artifact.
    """

    schema_version: Literal["policyos.runtime.grounding_phrasing_defense_certificate.v1"] = (
        GROUNDING_PHRASING_DEFENSE_SCHEMA_VERSION
    )
    certificate_id: str = Field(..., pattern=r"^cg4_cert_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    authority_scope: _AuthorityScope
    production_authoritative: Literal[False] = False
    reference_epoch: str = Field(..., min_length=1)
    reference_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    reference_versions: dict[str, str]
    validator_version: str = GROUNDING_PHRASING_DEFENSE_VALIDATOR_VERSION
    matrix_summary: PhrasingMatrixSummary
    comparisons: tuple[PhrasingPairEvaluation, ...]
    proxy_gap_risks: tuple[GroundingProxyGapRisk, ...] = ()
    quarantine_handoffs: tuple[QuarantineHandoffRecord, ...] = ()
    proxy_gap_capture_pair: dict[str, Any] = Field(default_factory=dict)
    full_cg1_comparison: FullCg1Comparison
    bounded_diagnostic_comparisons: tuple[FullCg1Comparison, ...] = ()

    @model_validator(mode="after")
    def _content_hash_matches_payload(self) -> PhrasingDefenseCertificate:
        expected = recompute_phrasing_defense_certificate_hash(self)
        if self.content_hash != expected:
            raise ValueError("phrasing_defense_certificate_content_hash_mismatch")
        expected_id = f"cg4_cert_{expected.removeprefix('sha256:')[:16]}"
        if self.certificate_id != expected_id:
            raise ValueError("phrasing_defense_certificate_id_mismatch")
        if self.production_authoritative is not False:
            raise ValueError("phrasing_defense_certificate_must_not_self_authenticate")
        return self


class GroundingPhrasingDefenseEngine:
    """EG-PIG defense engine over CG0/CG1/CG2/CG3 owners."""

    def __init__(
        self,
        credal_reference: CredalReference,
        *,
        policy: PhrasingDefensePolicy | None = None,
    ) -> None:
        if policy is not None and not isinstance(policy, PhrasingDefensePolicy):
            raise TypeError("policy must be a PhrasingDefensePolicy")
        self.reference = credal_reference
        self.policy = policy or PhrasingDefensePolicy()
        self._settings = _PhrasingDefenseRuntimeSettings()
        self._reference_atoms: tuple[Any, ...] | None = None
        self._bounded_relation_engine: GroundingRelationEngine | None = None
        self._full_relation_engine: GroundingRelationEngine | None = None
        self._pipeline_run_cache: dict[
            tuple[bool, str | None, str],
            GroundingPhrasingPipelineRun,
        ] = {}

    @classmethod
    def for_contract_testing(
        cls,
        credal_reference: CredalReference,
        *,
        allow_surface_lift: bool = False,
        trust_declared_phrasing_only: bool = False,
        disable_proxy_gap_capture: bool = False,
        disable_sensitivity_arm: bool = False,
        force_bounded_matrix: bool = False,
    ) -> GroundingPhrasingDefenseEngine:
        """Return a non-authoritative engine with mutation switches enabled."""

        engine = cls(credal_reference)
        engine._settings = _PhrasingDefenseRuntimeSettings(
            authority_scope="contract_testing",
            allow_surface_lift=allow_surface_lift,
            trust_declared_phrasing_only=trust_declared_phrasing_only,
            disable_proxy_gap_capture=disable_proxy_gap_capture,
            disable_sensitivity_arm=disable_sensitivity_arm,
            force_bounded_matrix=force_bounded_matrix,
        )
        return engine

    @property
    def reference_atoms(self) -> tuple[Any, ...]:
        """Return owner-derived CG1 reference atoms."""

        if self._reference_atoms is None:
            self._reference_atoms = self._relation_engine(bounded=True).reference_atoms
        return self._reference_atoms

    def run_pipeline(
        self,
        proposal: Mapping[str, Any] | str,
        *,
        proposal_id: str | None = None,
    ) -> GroundingPhrasingPipelineRun:
        """Run the real CG1->CG2->CG3 pipeline once and split channels."""

        return self._run_pipeline(proposal, proposal_id=proposal_id, bounded_cg1=False)

    def evaluate_pair(
        self,
        base_case: PhrasingDefenseBaseCase,
        transform: PhrasingAttackTransform,
    ) -> PhrasingPairEvaluation:
        """Evaluate one base-vs-transform pair with full CG1 retrieval."""

        return self._evaluate_pair(base_case, transform, bounded_cg1=False)

    def detect_proxy_gap(
        self,
        run: GroundingPhrasingPipelineRun,
    ) -> GroundingProxyGapRisk | None:
        """Return a proxy-gap risk if the run is high-surface/low-evidence."""

        if self._settings.disable_proxy_gap_capture:
            return None
        surface = run.surface_view.max_surface_affinity
        evidence = _causal_evidence_score(run.evidence_signature)
        low_evidence_reasons = _low_evidence_reasons(run.evidence_signature)
        denotation_matched = _has_denotation_match(run.evidence_signature)
        should_quarantine = (
            surface >= _SURFACE_AFFINITY_THRESHOLD
            and evidence < _CAUSAL_EVIDENCE_THRESHOLD
            and not denotation_matched
            and run.decisions.cg2_decision != "bind"
            and run.decisions.cg3_decision != "admit_new_lever"
        )
        if not should_quarantine:
            return None
        fields = {
            "causal_evidence_score": evidence,
            "causal_evidence_threshold": _CAUSAL_EVIDENCE_THRESHOLD,
            "cg2_decision": run.decisions.cg2_decision,
            "cg3_decision": run.decisions.cg3_decision,
            "disposition": "quarantine",
            "low_evidence_reasons": low_evidence_reasons,
            "matched_surface_atom_id": run.surface_view.max_surface_atom_id,
            "not_admissible_while_quarantined": run.decisions.cg3_decision != "admit_new_lever",
            "not_bindable_while_quarantined": run.decisions.cg2_decision != "bind",
            "proposal_id": run.proposal_id,
            "quarantine_action": "adversarial_validate",
            "surface_affinity_score": surface,
            "surface_affinity_threshold": _SURFACE_AFFINITY_THRESHOLD,
            "threshold_source": (
                "CG4-owned thresholds derived from reference-token surface affinity "
                "and CG3 production data_trust_floor; not caller supplied"
            ),
        }
        content_hash = gy_content_hash(fields)
        return GroundingProxyGapRisk(
            risk_id=f"cg4_proxy_gap_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **fields,
        )

    def quarantine_handoff(self, risk: GroundingProxyGapRisk) -> QuarantineHandoffRecord:
        """Return the honest N6 QuarantineFront handoff artifact for a risk."""

        fields = {
            "action": "adversarial_validate",
            "front": "quarantine",
            "integration_gap": (
                "GY-N6 exposes a quarantine front in generation_cycle.py, but no safe "
                "direct CG4 proxy-gap intake is wired; CG4 therefore emits this "
                "owned handoff artifact instead of faking orchestration."
            ),
            "integration_status": "handoff_artifact_n6_direct_intake_not_wired",
            "owner": "polisyos.runtime.quality.grounding_phrasing_defense",
            "risk_content_hash": risk.content_hash,
            "risk_id": risk.risk_id,
            "target_surface": "GY-N6 QuarantineFront",
        }
        content_hash = gy_content_hash(fields)
        return QuarantineHandoffRecord(
            handoff_id=f"cg4_quarantine_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **fields,
        )

    def evaluate_attack_matrix(
        self,
        base_cases: Sequence[PhrasingDefenseBaseCase],
    ) -> PhrasingDefenseCertificate:
        """Run the full CG4 attack matrix over real base proposals."""

        transforms_by_base = self.generate_transforms(base_cases)
        return self._evaluate_attack_matrix_from_transforms(
            base_cases,
            transforms_by_base,
            matrix_scope="full_all_generated_transforms",
            scope_note="Full generated transform matrix over the supplied base cases.",
        )

    def _evaluate_attack_matrix_from_transforms(
        self,
        base_cases: Sequence[PhrasingDefenseBaseCase],
        transforms_by_base: Mapping[str, Sequence[PhrasingAttackTransform]],
        *,
        matrix_scope: Literal[
            "full_all_generated_transforms",
            "representative_full_cg1_slice",
        ],
        scope_note: str,
    ) -> PhrasingDefenseCertificate:
        """Build a certificate from a preselected transform matrix.

        This is private so production callers cannot narrow the proof path.
        The CG4 validator uses it only for the explicitly recorded
        representative full-CG1 fallback when the full generated matrix is not
        practical in cold replay.
        """

        proof_bounded = self._settings.force_bounded_matrix
        comparisons: list[PhrasingPairEvaluation] = []
        for base in base_cases:
            for transform in transforms_by_base.get(base.case_id, ()):
                comparisons.append(
                    self._evaluate_pair(base, transform, bounded_cg1=proof_bounded)
                )

        risks: list[GroundingProxyGapRisk] = []
        handoffs: list[QuarantineHandoffRecord] = []
        capture_pair: dict[str, Any] = {}
        seen_risks: set[str] = set()
        for base in base_cases:
            run = self._run_pipeline(
                base.proposal,
                proposal_id=f"{base.case_id}.proxy_gap_probe",
                bounded_cg1=proof_bounded,
            )
            risk = self.detect_proxy_gap(run)
            if risk is not None and risk.risk_id not in seen_risks:
                seen_risks.add(risk.risk_id)
                risks.append(risk)
                handoffs.append(self.quarantine_handoff(risk))
                capture_pair[base.case_id] = {
                    "proposal_id": run.proposal_id,
                    "quarantined": True,
                    "risk_id": risk.risk_id,
                    "cg2_decision": run.decisions.cg2_decision,
                    "cg3_decision": run.decisions.cg3_decision,
                }
        for comparison in comparisons:
            for run in (comparison.base_run, comparison.transformed_run):
                risk = self.detect_proxy_gap(run)
                if risk is not None and risk.risk_id not in seen_risks:
                    seen_risks.add(risk.risk_id)
                    risks.append(risk)
                    handoffs.append(self.quarantine_handoff(risk))

        bounded_diagnostics = (
            ()
            if proof_bounded
            else self._bounded_diagnostic_comparisons(
                base_cases,
                transforms_by_base,
            )
        )
        full_cg1_comparison = (
            bounded_diagnostics[0]
            if bounded_diagnostics
            else FullCg1Comparison(checked=False, bounded_not_more_permissive=False)
        )
        summary = _matrix_summary(
            base_cases,
            comparisons,
            matrix_scope=matrix_scope,
            scope_note=scope_note,
        )
        raw_payload = {
            "authority_scope": self._settings.authority_scope,
            "bounded_diagnostic_comparisons": [
                item.model_dump(mode="json") for item in bounded_diagnostics
            ],
            "comparisons": [comparison.model_dump(mode="json") for comparison in comparisons],
            "full_cg1_comparison": full_cg1_comparison.model_dump(mode="json"),
            "matrix_summary": summary.model_dump(mode="json"),
            "production_authoritative": False,
            "proxy_gap_capture_pair": capture_pair,
            "proxy_gap_risks": [risk.model_dump(mode="json") for risk in risks],
            "quarantine_handoffs": [handoff.model_dump(mode="json") for handoff in handoffs],
            "reference_epoch": self.reference.reference_epoch,
            "reference_hash": self.reference.reference_hash,
            "reference_versions": dict(sorted(self.reference.component_versions.items())),
            "validator_version": GROUNDING_PHRASING_DEFENSE_VALIDATOR_VERSION,
        }
        content_hash = gy_content_hash(
            {
                "schema_version": GROUNDING_PHRASING_DEFENSE_SCHEMA_VERSION,
                **raw_payload,
            }
        )
        return PhrasingDefenseCertificate(
            certificate_id=f"cg4_cert_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **raw_payload,
        )

    def generate_transforms(
        self,
        base_cases: Sequence[PhrasingDefenseBaseCase],
    ) -> dict[str, tuple[PhrasingAttackTransform, ...]]:
        """Generate data-driven transform families from the reference and bases."""

        legal_tokens = _legal_tokens(self.reference)
        by_base: dict[str, tuple[PhrasingAttackTransform, ...]] = {}
        for base in base_cases:
            transforms: list[PhrasingAttackTransform] = []
            transforms.extend(
                _phrasing_transforms(
                    base,
                    legal_tokens=legal_tokens,
                    reference_atoms=self.reference_atoms,
                )
            )
            if not self._settings.disable_sensitivity_arm:
                transforms.extend(_mechanism_changing_controls(base, self.reference))
            by_base[base.case_id] = tuple(transforms)
        return by_base

    def _evaluate_pair(
        self,
        base_case: PhrasingDefenseBaseCase,
        transform: PhrasingAttackTransform,
        *,
        bounded_cg1: bool,
    ) -> PhrasingPairEvaluation:
        base_run = self._run_pipeline(
            base_case.proposal,
            proposal_id=base_case.case_id,
            bounded_cg1=bounded_cg1,
        )
        transformed_run = self._run_pipeline(
            transform.proposal,
            proposal_id=f"{base_case.case_id}.{transform.transform_id}",
            bounded_cg1=bounded_cg1,
        )
        classification = self._classify_transform(base_case.proposal, transform)
        evidence_equal = (
            base_run.evidence_signature.content_hash
            == transformed_run.evidence_signature.content_hash
        )
        deltas = {
            "cg1": transformed_run.decisions.cg1_rank - base_run.decisions.cg1_rank,
            "cg2": transformed_run.decisions.cg2_rank - base_run.decisions.cg2_rank,
            "cg3": transformed_run.decisions.cg3_rank - base_run.decisions.cg3_rank,
        }
        lifted = tuple(gate for gate, delta in deltas.items() if delta > 0)
        degraded = tuple(gate for gate, delta in deltas.items() if delta < 0)
        if not classification.classified_phrasing_only:
            outcome: PairOutcome = "mechanism_changed_control"
        elif lifted:
            outcome = "lifted"
        elif degraded:
            outcome = "degraded_fail_safe"
        else:
            outcome = "unchanged"
        return PhrasingPairEvaluation(
            base_case_id=base_case.case_id,
            base_case_class=base_case.case_class,
            transform_id=transform.transform_id,
            family=transform.family,
            classification=classification,
            base_run=base_run,
            transformed_run=transformed_run,
            evidence_signature_equal=evidence_equal,
            disposition_deltas=deltas,
            lifted_gate_ids=lifted,
            degraded_gate_ids=degraded,
            outcome=outcome,
        )

    def _run_pipeline(
        self,
        proposal: Mapping[str, Any] | str,
        *,
        proposal_id: str | None,
        bounded_cg1: bool,
    ) -> GroundingPhrasingPipelineRun:
        cache_key = (bounded_cg1, proposal_id, _proposal_cache_hash(proposal))
        cached = self._pipeline_run_cache.get(cache_key)
        if cached is not None:
            return cached
        relation_engine = self._relation_engine(bounded=bounded_cg1)
        cg1 = relation_engine.certificate_for(proposal, proposal_id=proposal_id)
        cg2 = GroundingBindGate(self.reference).certificate_for(cg1)
        cg3 = GroundingAdmissionEngine(self.reference).decide(cg2, cg1_certificate=cg1)
        surface_view = _surface_view(
            proposal,
            cg1_certificate=cg1,
            reference_atoms=self.reference_atoms,
        )
        evidence_signature = _evidence_signature(cg1, cg2, cg3, proposal, self.reference)
        decisions = GroundingPipelineDecisions(
            cg1_relation=cg1.selected_relation,
            cg2_decision=cg2.decision,
            cg3_decision=cg3.decision,
            cg1_rank=_cg1_rank(cg1.selected_relation),
            cg2_rank=_cg2_rank(cg2.decision),
            cg3_rank=_cg3_rank(cg3.decision),
        )
        run = GroundingPhrasingPipelineRun(
            proposal_id=cg1.proposal_id,
            surface_view=surface_view,
            evidence_signature=evidence_signature,
            decisions=decisions,
            cg1_certificate_id=cg1.certificate_id,
            cg2_certificate_id=cg2.certificate_id,
            cg3_certificate_id=cg3.certificate_id,
        )
        self._pipeline_run_cache[cache_key] = run
        return run

    def _relation_engine(self, *, bounded: bool) -> GroundingRelationEngine:
        if bounded:
            if self._bounded_relation_engine is None:
                engine = GroundingRelationEngine(
                    self.reference,
                    policy=GroundingEnginePolicy(
                        allow_surface_similarity_exact=self._settings.allow_surface_lift,
                    ),
                )
                engine._fts_index = _BoundedReferenceIndex(self.reference)
                self._bounded_relation_engine = engine
            return self._bounded_relation_engine
        if self._full_relation_engine is None:
            self._full_relation_engine = GroundingRelationEngine(
                self.reference,
                policy=GroundingEnginePolicy(
                    allow_surface_similarity_exact=self._settings.allow_surface_lift,
                ),
            )
        return self._full_relation_engine

    def _classify_transform(
        self,
        base_proposal: Mapping[str, Any] | str,
        transform: PhrasingAttackTransform,
    ) -> DenotationClassification:
        base = _resolved_denotation(base_proposal, self.reference)
        transformed = _resolved_denotation(transform.proposal, self.reference)
        diff_axes = tuple(
            key
            for key in sorted(set(base) | set(transformed))
            if base.get(key) != transformed.get(key)
        )
        denotation_equal = not diff_axes
        if self._settings.trust_declared_phrasing_only:
            classified = transform.declared_phrasing_only
            trusted = True
        else:
            classified = denotation_equal
            trusted = False
        return DenotationClassification(
            declared_phrasing_only=transform.declared_phrasing_only,
            classified_phrasing_only=classified,
            harness_label_trusted=trusted,
            denotation_equal=denotation_equal,
            denotation_diff_axes=diff_axes,
            base_denotation=base,
            transformed_denotation=transformed,
        )

    def _bounded_diagnostic_comparisons(
        self,
        base_cases: Sequence[PhrasingDefenseBaseCase],
        transforms_by_base: Mapping[str, Sequence[PhrasingAttackTransform]],
    ) -> tuple[FullCg1Comparison, ...]:
        comparisons: list[FullCg1Comparison] = []
        covered: set[tuple[str, str]] = set()
        family_counts: Counter[str] = Counter()
        for base in base_cases:
            for transform in transforms_by_base.get(base.case_id, ()):
                if transform.family == _MECHANISM_CONTROL_FAMILY:
                    continue
                coverage_key = (str(transform.family), str(base.case_class))
                if coverage_key in covered:
                    continue
                if family_counts[str(transform.family)] >= 2:
                    continue
                covered.add(coverage_key)
                family_counts[str(transform.family)] += 1
                bounded = self._run_pipeline(
                    transform.proposal,
                    proposal_id=f"{base.case_id}.{transform.transform_id}.bounded_diagnostic",
                    bounded_cg1=True,
                )
                full = self._run_pipeline(
                    transform.proposal,
                    proposal_id=f"{base.case_id}.{transform.transform_id}.bounded_diagnostic",
                    bounded_cg1=False,
                )
                comparisons.append(
                    FullCg1Comparison(
                        checked=True,
                        base_case_id=base.case_id,
                        transform_id=transform.transform_id,
                        bounded_cg1_rank=bounded.decisions.cg1_rank,
                        full_cg1_rank=full.decisions.cg1_rank,
                        bounded_not_more_permissive=bounded.decisions.cg1_rank
                        <= full.decisions.cg1_rank,
                        bounded_relation=bounded.decisions.cg1_relation,
                        full_relation=full.decisions.cg1_relation,
                    )
                )
        return tuple(comparisons)


class _BoundedReferenceIndex:
    """Bound CG1 matrix replay without rebuilding DuckDB FTS for every pair."""

    def __init__(self, reference: CredalReference) -> None:
        self.indexed_edge_count = len(reference.essential_edges)

    def search(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        """Return no lexical hits; CG1 still uses owner atom/token evidence."""

        del query, limit
        return []


def recompute_phrasing_defense_certificate_hash(
    certificate_or_payload: PhrasingDefenseCertificate | Mapping[str, Any],
) -> str:
    """Recompute a CG4 certificate content hash from its body."""

    payload = _payload_without_identity(certificate_or_payload)
    return gy_content_hash(payload)


def recompute_proxy_gap_risk_content_hash(
    risk_or_payload: GroundingProxyGapRisk | Mapping[str, Any],
) -> str:
    """Recompute a proxy-gap risk content hash."""

    payload = _payload_without_identity(risk_or_payload, id_fields=("risk_id", "content_hash"))
    return gy_content_hash(payload)


def recompute_quarantine_handoff_content_hash(
    handoff_or_payload: QuarantineHandoffRecord | Mapping[str, Any],
) -> str:
    """Recompute a quarantine handoff content hash."""

    payload = _payload_without_identity(
        handoff_or_payload,
        id_fields=("handoff_id", "content_hash"),
    )
    return gy_content_hash(payload)


def _payload_without_identity(
    value: BaseModel | Mapping[str, Any],
    *,
    id_fields: tuple[str, str] = ("certificate_id", "content_hash"),
) -> dict[str, Any]:
    if isinstance(value, Mapping):
        payload = json.loads(json.dumps(value, sort_keys=True))
    else:
        payload = value.model_dump(mode="json")
    for field in id_fields:
        payload.pop(field, None)
    return payload


def _proposal_cache_hash(proposal: Mapping[str, Any] | str) -> str:
    return gy_content_hash(_json_ready(proposal))


def _resolved_denotation(
    proposal: Mapping[str, Any] | str,
    reference: CredalReference,
) -> dict[str, Any]:
    parsed = parse_n4_proposal(proposal, reference=reference)
    if not parsed.hypotheses:
        return {}
    signature = parsed.hypotheses[0].signature
    return {
        "do_value": _json_ready(signature.x_do),
        "effect_path": list(signature.effect_path),
        "estimand": signature.estimand,
        "op": signature.op,
        "outcome": list(signature.outcome),
        "params": _json_ready(signature.params),
        "population": signature.population,
        "scope": signature.scope,
        "sign": signature.sign,
        "target_slot": list(signature.X_do),
    }


def _surface_view(
    proposal: Mapping[str, Any] | str,
    *,
    cg1_certificate: object,
    reference_atoms: Sequence[Any],
) -> GroundingSurfaceView:
    raw_text = _raw_text(proposal)
    raw_operator = _raw_operator(proposal)
    retrieval_scores = _retrieval_scores(cg1_certificate)
    affinity, atom_id = _max_surface_affinity(raw_text, reference_atoms)
    return GroundingSurfaceView(
        proposal_id=cg1_certificate.proposal_id,
        raw_text_hash=cg1_certificate.raw_text_hash,
        raw_text_terms=tuple(sorted(_tokens(raw_text))),
        raw_operator_spelling=raw_operator or None,
        retrieval_candidate_ids=tuple(sorted(retrieval_scores)),
        retrieval_scores=retrieval_scores,
        max_surface_affinity=affinity,
        max_surface_atom_id=atom_id,
        self_reported_confidence=_self_reported_confidence(proposal),
        rationale_present=bool(isinstance(proposal, Mapping) and proposal.get("rationale")),
    )


def _evidence_signature(
    cg1: object,
    cg2: object,
    cg3: object,
    proposal: Mapping[str, Any] | str,
    reference: CredalReference,
) -> GroundingEvidenceSignature:
    denotation = _resolved_denotation(proposal, reference)
    novel = next(
        (
            obligation
            for obligation in cg3.obligations
            if obligation.obligation_id == "novel_irreducible"
        ),
        None,
    )
    actuatability = {}
    if isinstance(cg3.mechanism_witness.evidence, Mapping):
        actuatability = dict(cg3.mechanism_witness.evidence.get("actuatability") or {})
    raw_payload = {
        "cg1_axis_relations": {
            witness.axis: witness.relation for witness in cg1.axis_witnesses
        },
        "cg1_critical_contradictions": list(cg1.critical_contradictions),
        "cg1_relation_class": cg1.selected_relation,
        "cg1_residual_constraints": list(cg1.residual_constraints),
        "cg1_selected_atom_id": _selected_atom_id(cg1),
        "cg1_solver_status": cg1.solver_status,
        "cg1_unsat_core_if_any": list(cg1.unsat_core_if_any),
        "cg1_unresolved_axes": list(cg1.unresolved_axes),
        "cg2_calibration_status": cg2.calibration.status,
        "cg2_decisive_reason": cg2.decisive_reason,
        "cg2_disposition": cg2.decision,
        "cg2_open_obligations": list(cg2.open_obligations),
        "cg2_risk_within_budget": cg2.risk_ledger.within_budget,
        "cg2_safe_t": list(cg2.safe_t.safe_atom_ids),
        "cg3_actuatability": _json_ready(actuatability),
        "cg3_data_trust_cap": cg3.data_trust.resolved_trust_cap,
        "cg3_data_trust_status": cg3.data_trust.status,
        "cg3_decision": cg3.decision,
        "cg3_decisive_reason": cg3.decisive_reason,
        "cg3_denotation_match_kind": (
            str(novel.evidence.get("existing_atom_match_kind"))
            if novel is not None and novel.evidence.get("existing_atom_match_kind")
            else None
        ),
        "cg3_mechanism_refs": list(cg3.mechanism_witness.evidence_refs),
        "cg3_mechanism_status": cg3.mechanism_witness.status,
        "cg3_open_obligations": list(cg3.open_obligations),
        "cg3_registry_patch_id": cg3.registry_patch.patch_id if cg3.registry_patch else None,
        "cg3_stable_unique": cg3.stable_unique.stable,
        "cg3_stable_unique_reason": cg3.stable_unique.reason,
        "resolved_denotation": denotation,
    }
    content_hash = gy_content_hash(raw_payload)
    return GroundingEvidenceSignature(content_hash=content_hash, **raw_payload)


def _phrasing_transforms(
    base: PhrasingDefenseBaseCase,
    *,
    legal_tokens: tuple[str, ...],
    reference_atoms: Sequence[Any],
) -> tuple[PhrasingAttackTransform, ...]:
    token = legal_tokens[0] if legal_tokens else "owner_legal_token_unavailable"
    proposal = base.proposal
    raw_text = _raw_text(proposal)
    transforms = [
        PhrasingAttackTransform(
            transform_id=f"{base.case_id}.alias",
            family="synonym_alias_substitution",
            declared_phrasing_only=True,
            proposal=_with_raw_text(
                proposal,
                f"{raw_text} {token.replace('_', ' ')} alias.",
            ),
            source_refs=(f"cg0://legal-token/{token}",),
            description="Owner legal/alias token appended without changing the do-query.",
        ),
        PhrasingAttackTransform(
            transform_id=f"{base.case_id}.legalistic",
            family="legalistic_camouflage",
            declared_phrasing_only=True,
            proposal=_with_raw_text(
                proposal,
                (
                    f"Notwithstanding any implementing rule under {token}, "
                    f"the following do-query remains unchanged: {raw_text}"
                ),
            ),
            source_refs=(f"cg0://legal-token/{token}",),
            description="Legal boilerplate from owner L3/L6 tokens.",
        ),
        PhrasingAttackTransform(
            transform_id=f"{base.case_id}.high_value",
            family="high_value_outcome_injection",
            declared_phrasing_only=True,
            proposal=_with_raw_text(
                proposal,
                (
                    f"{raw_text} This will maximize employment, resilience, welfare, "
                    "equity, and fiscal confidence."
                ),
            ),
            description="Grandiose outcome claims in surface text only.",
        ),
        PhrasingAttackTransform(
            transform_id=f"{base.case_id}.confidence",
            family="confidence_bait",
            declared_phrasing_only=True,
            proposal=_with_confidence_bait(
                proposal,
                f"{raw_text} Confidence 0.99 with citations [1][2].",
            ),
            description="Fake confidence and rationale fields.",
        ),
        PhrasingAttackTransform(
            transform_id=f"{base.case_id}.format",
            family="format_whitespace_ordering",
            declared_phrasing_only=True,
            proposal=_with_raw_text(proposal, " \n ".join(raw_text.upper().split())),
            description=(
                "Case and whitespace perturbation; unit spelling is not changed unless "
                "owner canonicalization proves equality."
            ),
        ),
    ]
    for variant in _registered_lever_mimicry_variants(proposal, reference_atoms):
        transforms.append(
            PhrasingAttackTransform(
                transform_id=f"{base.case_id}.mimic.{_id_token(variant)}",
                family="registered_lever_mimicry",
                declared_phrasing_only=True,
                proposal=_with_operator_mimic(proposal, variant),
                source_refs=("cg0://registered-atom-name/live",),
                description=(
                    "Unregistered near-synonym/misspelling/paraphrase generated from "
                    "a live registered operator name."
                ),
            )
        )
    return tuple(transforms)


def _with_raw_text(proposal: Mapping[str, Any] | str, raw_text: str) -> dict[str, Any] | str:
    if isinstance(proposal, Mapping):
        return {**proposal, "raw_text": raw_text}
    return raw_text


def _with_confidence_bait(
    proposal: Mapping[str, Any] | str,
    raw_text: str,
) -> dict[str, Any] | str:
    if isinstance(proposal, Mapping):
        return {
            **proposal,
            "raw_text": raw_text,
            "rationale": "self-reported causal certainty; not evidence",
            "self_reported_confidence": 0.99,
        }
    return f"{raw_text} Self-reported confidence: 0.99."


def _registered_lever_mimicry_variants(
    proposal: Mapping[str, Any] | str,
    reference_atoms: Sequence[Any],
) -> tuple[str, ...]:
    operator = _raw_operator(proposal)
    if not operator:
        operator = _nearest_registered_operator(_raw_text(proposal), reference_atoms)
    if not operator:
        return ()
    return _operator_mimic_spellings(operator)


def _nearest_registered_operator(raw_text: str, reference_atoms: Sequence[Any]) -> str:
    raw_tokens = _tokens(raw_text)
    best_score = 0
    best_operator = ""
    for atom in reference_atoms:
        operator = str(atom.signature.op or "")
        overlap = len(raw_tokens & _tokens(operator))
        if overlap > best_score:
            best_score = overlap
            best_operator = operator
    return best_operator


def _operator_mimic_spellings(operator: str) -> tuple[str, ...]:
    canonical = str(operator or "").strip()
    if not canonical:
        return ()
    words = canonical.replace("_", " ").replace("-", " ").split()
    variants: list[str] = [f"{' '.join(words)} adjustment"]
    if "relief" in canonical:
        variants.append(canonical.replace("relief", "releif"))
    elif words:
        variants.append(f"{canonical}_adjustment")
    substitutions = {
        "aid": "relief",
        "allocation": "distribution",
        "budget": "appropriation",
        "credit": "relief",
        "intensity": "magnitude",
        "rate": "ratio",
        "relief": "relief",
        "shock": "jolt",
        "subsidy": "support",
        "tax": "fiscal",
    }
    paraphrase = " ".join(substitutions.get(word.casefold(), word) for word in words)
    if paraphrase and paraphrase != " ".join(words):
        variants.append(paraphrase)
    return tuple(dict.fromkeys(variants))


def _with_operator_mimic(
    proposal: Mapping[str, Any] | str,
    mimic_operator: str,
) -> dict[str, Any] | str:
    raw_text = _replace_surface_operator(
        _raw_text(proposal),
        _raw_operator(proposal),
        mimic_operator,
    )
    if isinstance(proposal, Mapping):
        signature = dict(_mapping(proposal.get("signature")))
        original_operator = _first_text(signature.get("op") or proposal.get("op"))
        if original_operator:
            signature["op"] = mimic_operator
            if "effect_path" in signature:
                effect_path = list(_sequence(signature.get("effect_path")))
                if effect_path:
                    effect_path[0] = mimic_operator
                    signature["effect_path"] = effect_path
            signature["modal_claims"] = _operator_mimic_modal_claims(
                _mapping(signature.get("modal_claims")),
                mimic_operator,
            )
            return {**proposal, "raw_text": raw_text, "signature": signature}
        return {**proposal, "raw_text": raw_text, "op": mimic_operator}
    return raw_text


def _replace_surface_operator(raw_text: str, original_operator: str, replacement: str) -> str:
    original_forms = [original_operator, original_operator.replace("_", " ")]
    for original in original_forms:
        if original and original in raw_text:
            return raw_text.replace(original, replacement, 1)
    return f"{replacement} {raw_text}".strip()


def _operator_mimic_modal_claims(
    modal_claims: Mapping[str, Any],
    mimic_operator: str,
) -> dict[str, Any]:
    updated: dict[str, Any] = {}
    for modality, raw_fields in sorted(modal_claims.items()):
        fields = dict(_mapping(raw_fields))
        for key in ("op", "treatment_op"):
            if key in fields:
                fields[key] = mimic_operator
        updated[str(modality)] = fields
    return updated


def _id_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9]+", "_", value.casefold()).strip("_")
    return token or "variant"


def _mechanism_changing_controls(
    base: PhrasingDefenseBaseCase,
    reference: CredalReference,
) -> tuple[PhrasingAttackTransform, ...]:
    proposal = base.proposal
    if not isinstance(proposal, Mapping):
        return ()
    signature = dict(_mapping(proposal.get("signature") if isinstance(proposal, Mapping) else {}))
    if not signature:
        return ()
    controls: list[PhrasingAttackTransform] = []
    if signature.get("sign"):
        flipped = dict(signature)
        flipped["sign"] = "increase" if signature.get("sign") == "decrease" else "decrease"
        controls.append(
            PhrasingAttackTransform(
                transform_id=f"{base.case_id}.sign_flip",
                family="mechanism_changing_control",
                declared_phrasing_only=True,
                proposal={**proposal, "signature": flipped},
                description="Mislabeled fake phrasing-only probe; sign changes.",
            )
        )
    sibling = _sibling_world_slot(reference, _first_text(signature.get("target")))
    if sibling:
        target_swap = dict(signature)
        target_swap["target"] = [sibling]
        target_swap["X_do"] = [sibling]
        target_swap["effect_path"] = [
            _first_text(signature.get("op")),
            sibling,
            _first_text(signature.get("outcome")),
        ]
        controls.append(
            PhrasingAttackTransform(
                transform_id=f"{base.case_id}.target_sibling",
                family="mechanism_changing_control",
                declared_phrasing_only=False,
                proposal={**proposal, "signature": target_swap},
                description="Critical target axis changes to a sibling WMR slot.",
            )
        )
    if signature.get("estimand"):
        estimand = dict(signature)
        estimand["estimand"] = "local_average_treatment_effect"
        controls.append(
            PhrasingAttackTransform(
                transform_id=f"{base.case_id}.estimand_swap",
                family="mechanism_changing_control",
                declared_phrasing_only=False,
                proposal={**proposal, "signature": estimand},
                description="Critical estimand axis changes.",
            )
        )
    return tuple(controls)


def _matrix_summary(
    base_cases: Sequence[PhrasingDefenseBaseCase],
    comparisons: Sequence[PhrasingPairEvaluation],
    *,
    matrix_scope: Literal[
        "full_all_generated_transforms",
        "representative_full_cg1_slice",
    ],
    scope_note: str,
) -> PhrasingMatrixSummary:
    denominator: dict[str, Counter[str]] = defaultdict(Counter)
    lifted: dict[str, Counter[str]] = defaultdict(Counter)
    degraded: dict[str, Counter[str]] = defaultdict(Counter)
    unchanged: dict[str, Counter[str]] = defaultdict(Counter)
    diff_counts: Counter[str] = Counter()
    family_diff_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in comparisons:
        denominator[item.family][item.base_case_class] += 1
        if item.outcome == "lifted":
            lifted[item.family][item.base_case_class] += 1
        elif item.outcome == "degraded_fail_safe":
            degraded[item.family][item.base_case_class] += 1
        elif item.outcome == "unchanged":
            unchanged[item.family][item.base_case_class] += 1
        flags = _consumed_intermediate_diff_flags(item)
        for key, changed in flags.items():
            if changed:
                diff_counts[key] += 1
                family_diff_counts[item.family][key] += 1
    phrasing_pair_count = sum(
        1 for item in comparisons if item.classification.classified_phrasing_only
    )
    phrasing_consumed_diff_count = sum(
        1
        for item in comparisons
        if item.classification.classified_phrasing_only
        and any(
            changed
            for key, changed in _consumed_intermediate_diff_flags(item).items()
            if key != "raw_text"
        )
    )
    return PhrasingMatrixSummary(
        matrix_scope=matrix_scope,
        scope_note=scope_note,
        base_case_count=len(base_cases),
        transform_count=len(comparisons),
        phrasing_pair_count=phrasing_pair_count,
        mechanism_control_count=sum(
            1 for item in comparisons if item.family == _MECHANISM_CONTROL_FAMILY
        ),
        total_lifted=sum(1 for item in comparisons if item.outcome == "lifted"),
        total_degraded=sum(1 for item in comparisons if item.outcome == "degraded_fail_safe"),
        total_unchanged=sum(1 for item in comparisons if item.outcome == "unchanged"),
        total_mechanism_changed=sum(
            1 for item in comparisons if item.outcome == "mechanism_changed_control"
        ),
        family_case_denominator=_counter_payload(denominator),
        family_case_lifted=_counter_payload(lifted),
        family_case_degraded=_counter_payload(degraded),
        family_case_unchanged=_counter_payload(unchanged),
        consumed_intermediate_diff_counts=dict(
            sorted({key: diff_counts.get(key, 0) for key in _CONSUMED_DIFF_KEYS}.items())
        ),
        family_consumed_intermediate_diff_counts=_counter_payload(family_diff_counts),
        self_vacuous=phrasing_pair_count > 0 and phrasing_consumed_diff_count == 0,
    )


_CONSUMED_DIFF_KEYS = (
    "raw_text",
    "retrieval",
    "denotation",
    "evidence_signature",
    "decisions",
)


def _consumed_intermediate_diff_flags(
    comparison: PhrasingPairEvaluation,
) -> dict[str, bool]:
    return {
        "raw_text": (
            comparison.base_run.surface_view.raw_text_hash
            != comparison.transformed_run.surface_view.raw_text_hash
        ),
        "retrieval": (
            comparison.base_run.surface_view.retrieval_candidate_ids
            != comparison.transformed_run.surface_view.retrieval_candidate_ids
            or comparison.base_run.surface_view.retrieval_scores
            != comparison.transformed_run.surface_view.retrieval_scores
        ),
        "denotation": (
            comparison.base_run.evidence_signature.resolved_denotation
            != comparison.transformed_run.evidence_signature.resolved_denotation
        ),
        "evidence_signature": not comparison.evidence_signature_equal,
        "decisions": comparison.disposition_deltas != {"cg1": 0, "cg2": 0, "cg3": 0},
    }


def _counter_payload(value: Mapping[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {
        family: dict(sorted(counter.items()))
        for family, counter in sorted(value.items())
    }


def _cg1_rank(value: str) -> int:
    return {
        "blocked": 0,
        "false-analog": 0,
        "unknown": 0,
        "novel-candidate": 1,
        "partial": 2,
        "generalization": 2,
        "compositional": 2,
        "certified-specialization": 3,
        "exact": 4,
    }.get(value, 0)


def _cg2_rank(value: str) -> int:
    return {"abstain": 0, "novel_candidate": 1, "bind": 2}.get(value, 0)


def _cg3_rank(value: str) -> int:
    return {
        "reject_hallucination": 0,
        "acquire_then_decide": 1,
        "non_new": 2,
        "admit_new_lever": 3,
    }.get(value, 0)


def _has_denotation_match(signature: GroundingEvidenceSignature) -> bool:
    return signature.cg1_relation_class in {
        "exact",
        "certified-specialization",
    } or signature.cg3_denotation_match_kind == "resolved_proof"


def _causal_evidence_score(signature: GroundingEvidenceSignature) -> float:
    if _has_denotation_match(signature):
        return 1.0
    if signature.cg3_mechanism_status == "closed" and signature.cg3_data_trust_status == "closed":
        return signature.cg3_data_trust_cap
    return min(signature.cg3_data_trust_cap, 0.49)


def _low_evidence_reasons(signature: GroundingEvidenceSignature) -> tuple[str, ...]:
    reasons: list[str] = []
    if signature.cg3_mechanism_status != "closed":
        reasons.append("direct_mechanism_edge_absent_or_open")
    if signature.cg3_data_trust_status != "closed":
        reasons.append("data_trust_below_floor_or_absent")
    if not _has_denotation_match(signature):
        reasons.append("denotation_match_absent")
    if signature.cg3_open_obligations:
        reasons.append("admission_obligations_open")
    return tuple(reasons)


def _legal_tokens(reference: CredalReference) -> tuple[str, ...]:
    tokens: list[str] = []
    for edge in reference.essential_edges.values():
        if edge.modality.startswith("L3_") or edge.modality == "L6_LEX_INTERVENTION_MAP":
            tokens.append(edge.edge_id)
            for completion in edge.admissible_completions:
                for key in ("law_token", "provision_id", "rule_id"):
                    value = completion.value.get(key)
                    if value:
                        tokens.append(str(value))
    return tuple(sorted(dict.fromkeys(tokens)))


def _retrieval_scores(cg1_certificate: object) -> dict[str, float]:
    scores: dict[str, float] = {}
    relation_set = _mapping(cg1_certificate.relation_set)
    for row in _sequence(relation_set.get("candidate_results")):
        payload = _mapping(row)
        atom_id = _first_text(payload.get("atom_id"))
        if atom_id:
            scores[atom_id] = max(
                scores.get(atom_id, 0.0),
                float(payload.get("retrieval_score") or 0.0),
            )
    return dict(sorted(scores.items()))


def _max_surface_affinity(raw_text: str, atoms: Sequence[Any]) -> tuple[float, str | None]:
    raw_tokens = _tokens(raw_text)
    best_score = 0.0
    best_atom = None
    for atom in atoms:
        atom_terms = set(_signature_terms(atom.signature))
        if not atom_terms:
            continue
        overlap = len(raw_tokens & atom_terms) / max(1, min(len(raw_tokens), len(atom_terms)))
        op_tokens = _tokens(str(atom.signature.op or ""))
        op_coverage = len(raw_tokens & op_tokens) / max(1, len(op_tokens))
        score = round(min(1.0, max(overlap, 0.7 * op_coverage + 0.3 * overlap)), 6)
        if score > best_score:
            best_score = score
            best_atom = str(atom.atom_id)
    return best_score, best_atom


def _signature_terms(signature: object) -> tuple[str, ...]:
    parts = [
        str(signature.op or ""),
        " ".join(str(item) for item in signature.X_do),
        " ".join(str(item) for item in signature.outcome),
        " ".join(str(item) for item in signature.effect_path),
        str(signature.estimand or ""),
        str(signature.scope or ""),
        str(signature.population or ""),
    ]
    return tuple(sorted(_tokens(" ".join(parts))))


def _tokens(value: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(value.replace("_", " "))}


def _raw_text(proposal: Mapping[str, Any] | str) -> str:
    if isinstance(proposal, Mapping):
        return str(proposal.get("raw_text") or proposal.get("text") or "")
    return str(proposal)


def _raw_operator(proposal: Mapping[str, Any] | str) -> str:
    if not isinstance(proposal, Mapping):
        return ""
    signature = _mapping(proposal.get("signature"))
    return _first_text(signature.get("op") or proposal.get("op"))


def _self_reported_confidence(proposal: Mapping[str, Any] | str) -> float | None:
    if not isinstance(proposal, Mapping):
        return None
    value = proposal.get("self_reported_confidence")
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _selected_atom_id(cg1_certificate: object) -> str | None:
    selected = _mapping(_mapping(cg1_certificate.cross_modal_witnesses).get("selected_pair"))
    atom_id = _first_text(selected.get("atom_id"))
    if atom_id:
        return atom_id
    for row in _sequence(_mapping(cg1_certificate.relation_set).get("candidate_results")):
        payload = _mapping(row)
        if payload.get("selected_relation") == cg1_certificate.selected_relation:
            return _first_text(payload.get("atom_id")) or None
    return None


def _sibling_world_slot(reference: CredalReference, current: str) -> str | None:
    for edge in sorted(reference.essential_edges.values(), key=lambda item: item.edge_id):
        if edge.modality == "WMR_WORLD_SLOT" and edge.edge_id != current:
            return edge.edge_id
    return None


def _first_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return ""
    if value is None:
        return ""
    return str(value)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _json_ready(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


__all__ = [
    "GROUNDING_PHRASING_DEFENSE_SCHEMA_VERSION",
    "GROUNDING_PHRASING_DEFENSE_VALIDATOR_VERSION",
    "DenotationClassification",
    "FullCg1Comparison",
    "GroundingEvidenceSignature",
    "GroundingPhrasingDefenseEngine",
    "GroundingPhrasingPipelineRun",
    "GroundingPipelineDecisions",
    "GroundingProxyGapRisk",
    "GroundingSurfaceView",
    "PhrasingAttackTransform",
    "PhrasingDefenseBaseCase",
    "PhrasingDefenseCertificate",
    "PhrasingDefensePolicy",
    "PhrasingMatrixSummary",
    "PhrasingPairEvaluation",
    "QuarantineHandoffRecord",
    "recompute_phrasing_defense_certificate_hash",
    "recompute_proxy_gap_risk_content_hash",
    "recompute_quarantine_handoff_content_hash",
]
