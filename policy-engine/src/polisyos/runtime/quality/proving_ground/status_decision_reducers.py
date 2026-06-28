"""Pure Layer 3 GX status reducers.

Reducers are the only Task 4 path allowed to author positive closure,
admission, promotion, conversion, and ceiling decisions. Callers may assemble
typed inputs and persist the returned decision, but reducers do not read files
or inspect repository state.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LAYER3_REDUCER_SCHEMA_VERSION = "policyos.policy_design_case.layer3_reducer_decision.v1"
LAYER3_REDUCER_RULE_VERSION = "policyos.layer3.gx.reducer_only_status.v1"
LAYER3_REDUCER_VERSION = "v1"

INVALID_SUPPLY_PRODUCER_TYPES: frozenset[str] = frozenset(
    {"derivation", "untyped", "test_fixture", "test-only", "unverified"}
)
INVALID_SUPPLY_ROOT_STATUSES: frozenset[str] = frozenset(
    {"derivation_only", "untyped", "test_only", "test-only", "unverified"}
)


class _ReducerModel(BaseModel):
    """Strict base for reducer input and output models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3ReducerInputRef(_ReducerModel):
    """A typed, hash-bearing lower-level artifact consumed by a reducer."""

    ref: str | None = None
    exists: bool = True
    content_hash: str | None = None
    producer_ref: str | None = None
    producer_type: str | None = None
    producer_root_refs: tuple[str, ...] = Field(default=())
    producer_root_status: str = "validated"
    required: bool = True
    supply_side: bool = True
    fixture_input: bool = False


class Layer3ReducerDecision(_ReducerModel):
    """Pure reducer decision with provenance for persisted status records."""

    schema_version: str = LAYER3_REDUCER_SCHEMA_VERSION
    reducer_id: str
    reducer_version: str = LAYER3_REDUCER_VERSION
    rule_version: str = LAYER3_REDUCER_RULE_VERSION
    status_field: str
    status: str
    readiness_status: Literal["pass", "fail", "blocked", "limited", "review_required"]
    vocabulary_status_id: str
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    input_refs: tuple[str, ...] = Field(default=())
    input_hashes: dict[str, str] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    produced_by: dict[str, Any] = Field(default_factory=dict)

    def status_record(self) -> dict[str, Any]:
        """Return the minimal persisted status record guarded by output_hash."""

        return {self.status_field: self.status, "produced_by": dict(self.produced_by)}


class G1SourceGroundingClosureInputs(_ReducerModel):
    """Inputs for reducing G1 source-grounding closure."""

    canonical_store: bool
    binding_count: int = Field(default=0, ge=0)
    binding_statuses: tuple[str, ...] = Field(default=())
    measured_no_hit: bool = False
    search_recall_status: str = "not_measured"
    index_freshness_status: str = "not_measured"
    overlay_injection_status: str = "not_measured"
    candidate_exists: bool = False
    admission_status: str = "not_attempted"
    abstention_vocabulary_approved: bool = False
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


class G2ForecastAdmissionInputs(_ReducerModel):
    """Inputs for reducing G2 forecast admission."""

    method_binding_status: str = "missing"
    calibration_status: str = "missing"
    skg_edge_type: str = "missing"
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


class G3ProofAuthorityInputs(_ReducerModel):
    """Inputs for reducing G3 proof authority."""

    proof_candidate_status: str = "missing"
    certificate_status: str = "missing"
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


class GLLegalAuthorityInputs(_ReducerModel):
    """Inputs for reducing GL legal authority."""

    legal_basis_status: str = "missing"
    applicability_status: str = "missing"
    mandate_status: str = "missing"
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


class G4PromotionStateInputs(_ReducerModel):
    """Inputs for reducing G4 promotion state."""

    dependency_statuses: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


class G5ConversionOutcomeInputs(_ReducerModel):
    """Inputs for reducing G5 conversion outcome."""

    requested_conversion_outcome: str = "unchanged_blocker"
    g4_promotion_state: str = "promotion_blocked"
    g1_grounding_closure: str = "typed_blocker"
    demand_pull_status: str = "missing"
    cross_slice_status: str = "missing"
    grounded_evidence_ref_count: int = Field(default=0, ge=0)
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


class G7RegionClosureInputs(_ReducerModel):
    """Inputs for reducing G7 region closure."""

    gx_migration_state: str = "blocked_by_gx_migration"
    g5_conversion_outcome: str = "unchanged_blocker"
    regional_breadth_status: str = "missing"
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


class G8DomainVsSearchCeilingInputs(_ReducerModel):
    """Inputs for reducing G8 domain-vs-search ceiling."""

    g5_conversion_outcome: str = "unchanged_blocker"
    g7_region_closure: str = "blocked_by_gx_migration"
    search_recall_status: str = "not_measured"
    index_freshness_status: str = "not_measured"
    input_refs: tuple[Layer3ReducerInputRef, ...] = Field(default=())


def reduce_g1_source_grounding_closure(
    inputs: G1SourceGroundingClosureInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce G1 closure from materialized bindings and measured search health."""

    data = _coerce(inputs, G1SourceGroundingClosureInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    limitations: list[str] = []
    status = "typed_blocker"
    readiness_status: Literal["pass", "fail", "blocked", "limited", "review_required"] = "fail"

    if blockers:
        blockers.append("layer3_gx_required_input_ref_blocked")
    elif not data.canonical_store:
        status = "bounded_surrogate"
        readiness_status = "limited"
        limitations.append("layer3_g1_noncanonical_store_cannot_close_grounding")
    elif data.candidate_exists and data.admission_status != "pass":
        blockers.append("layer3_g1_candidate_admission_blocked")
    elif data.binding_count > 0:
        if set(data.binding_statuses) == {"observed_but_uncertain"}:
            status = "observed_but_uncertain"
            readiness_status = "limited"
            limitations.append("layer3_g1_observed_but_uncertain")
        else:
            status = "grounded_or_uncertain"
            readiness_status = "pass"
    elif (
        data.measured_no_hit
        and data.search_recall_status == "pass"
        and data.index_freshness_status == "pass"
        and data.overlay_injection_status == "pass"
    ):
        if data.abstention_vocabulary_approved:
            status = "grounded_abstention_candidate"
            readiness_status = "review_required"
            limitations.append("layer3_g1_abstention_candidate_requires_g5_conversion")
        else:
            blockers.append("layer3_g1_grounded_abstention_candidate_vocabulary_unapproved")
    elif data.search_recall_status != "pass" or data.index_freshness_status != "pass":
        status = "search_ceiling_repair_required"
        readiness_status = "blocked"
        blockers.append("layer3_g1_search_health_not_measured_or_failed")
    else:
        blockers.append("layer3_g1_materialized_binding_missing")

    if blockers and status in {"typed_blocker", "grounded_or_uncertain"}:
        status = "typed_blocker"
        readiness_status = "fail"
    return _decision(
        reducer_id="reduce_g1_source_grounding_closure",
        status_field="grounding_closure_outcome",
        status=status,
        readiness_status=readiness_status,
        input_refs=data.input_refs,
        blocker_refs=blockers,
        limitation_refs=limitations,
    )


def reduce_g2_forecast_admission(
    inputs: G2ForecastAdmissionInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce G2 forecast admission from method, calibration, and SKG edge inputs."""

    data = _coerce(inputs, G2ForecastAdmissionInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    if data.skg_edge_type != "ForecastSupport":
        blockers.append("layer3_g2_skg_edge_not_forecast_support")
    if data.method_binding_status != "pass":
        blockers.append("layer3_g2_method_binding_not_admitted")
    if data.calibration_status != "pass":
        blockers.append("layer3_g2_calibration_not_admitted")
    status = "forecast_admitted" if not blockers else "typed_blocker"
    return _decision(
        reducer_id="reduce_g2_forecast_admission",
        status_field="forecast_admission_status",
        status=status,
        readiness_status="pass" if not blockers else "fail",
        input_refs=data.input_refs,
        blocker_refs=blockers,
    )


def reduce_g3_proof_authority(
    inputs: G3ProofAuthorityInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce G3 proof authority without treating candidates as authority."""

    data = _coerce(inputs, G3ProofAuthorityInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    if data.proof_candidate_status != "proof_authority":
        blockers.append("layer3_g3_proof_candidate_not_authority")
    if data.certificate_status != "pass":
        blockers.append("layer3_g3_certificate_not_valid")
    status = "proof_authority" if not blockers else "typed_blocker"
    return _decision(
        reducer_id="reduce_g3_proof_authority",
        status_field="proof_authority_status",
        status=status,
        readiness_status="pass" if not blockers else "fail",
        input_refs=data.input_refs,
        blocker_refs=blockers,
    )


def reduce_gl_legal_authority(
    inputs: GLLegalAuthorityInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce GL legal authority from legal basis, applicability, and mandate."""

    data = _coerce(inputs, GLLegalAuthorityInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    if data.legal_basis_status != "pass":
        blockers.append("layer3_gl_legal_basis_not_authoritative")
    if data.applicability_status != "pass":
        blockers.append("layer3_gl_applicability_not_authoritative")
    if data.mandate_status != "pass":
        blockers.append("layer3_gl_mandate_not_authoritative")
    status = "legal_authority" if not blockers else "typed_blocker"
    return _decision(
        reducer_id="reduce_gl_legal_authority",
        status_field="legal_authority_status",
        status=status,
        readiness_status="pass" if not blockers else "fail",
        input_refs=data.input_refs,
        blocker_refs=blockers,
    )


def reduce_g4_promotion_state(
    inputs: G4PromotionStateInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce G4 promotion from dependency statuses and materialized blockers."""

    data = _coerce(inputs, G4PromotionStateInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    blockers.extend(data.blocker_refs)
    blockers.extend(
        f"layer3_g4_dependency_not_ready:{status}"
        for status in data.dependency_statuses
        if status not in {"pass", "limited"}
    )
    status = "governed_promoted" if not blockers else "promotion_blocked"
    return _decision(
        reducer_id="reduce_g4_promotion_state",
        status_field="promotion_state",
        status=status,
        readiness_status="pass" if not blockers else "fail",
        input_refs=data.input_refs,
        blocker_refs=blockers,
        limitation_refs=data.limitation_refs,
    )


def reduce_g5_conversion_outcome(
    inputs: G5ConversionOutcomeInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce G5 conversion; only G5 can convert an abstention candidate."""

    data = _coerce(inputs, G5ConversionOutcomeInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    limitations: list[str] = []
    status = "unchanged_blocker"
    if data.cross_slice_status != "pass":
        blockers.append("layer3_g5_cross_slice_checks_not_ready")
    if data.grounded_evidence_ref_count < 1:
        blockers.append("layer3_g5_grounded_evidence_ref_missing")
    if data.requested_conversion_outcome == "grounded_limited":
        if data.g4_promotion_state != "governed_promoted":
            blockers.append("layer3_g5_governed_promotion_missing")
        if not blockers:
            status = "grounded_limited"
    elif data.requested_conversion_outcome == "grounded_abstention":
        if data.g1_grounding_closure != "grounded_abstention_candidate":
            blockers.append("layer3_g5_abstention_candidate_missing")
        if data.demand_pull_status != "pass":
            blockers.append("layer3_g5_demand_pull_not_ready")
        if not blockers:
            status = "grounded_abstention"
            limitations.append("layer3_g5_abstention_not_useful_design_credit")
    else:
        blockers.append("layer3_g5_requested_conversion_not_positive")
    return _decision(
        reducer_id="reduce_g5_conversion_outcome",
        status_field="conversion_outcome",
        status=status,
        readiness_status="pass" if status != "unchanged_blocker" else "fail",
        input_refs=data.input_refs,
        blocker_refs=blockers,
        limitation_refs=limitations,
    )


def reduce_g7_region_closure(
    inputs: G7RegionClosureInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce G7 region closure under the GX migration boundary."""

    data = _coerce(inputs, G7RegionClosureInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    if data.gx_migration_state != "gx_hardened":
        blockers.append("layer3_g7_blocked_by_gx_migration")
        status = "blocked_by_gx_migration"
    elif data.g5_conversion_outcome not in {"grounded_limited", "grounded_abstention"}:
        blockers.append("layer3_g7_g5_conversion_not_grounded")
        status = "region_blocked"
    elif data.regional_breadth_status != "pass":
        blockers.append("layer3_g7_regional_breadth_not_ready")
        status = "region_blocked"
    else:
        status = "region_closed"
    return _decision(
        reducer_id="reduce_g7_region_closure",
        status_field="g7_region_value_closure_status",
        status=status,
        readiness_status="pass" if status == "region_closed" else "fail",
        input_refs=data.input_refs,
        blocker_refs=blockers,
    )


def reduce_g8_domain_vs_search_ceiling(
    inputs: G8DomainVsSearchCeilingInputs | Mapping[str, object],
) -> Layer3ReducerDecision:
    """Reduce whether a current blocker is a domain ceiling or search ceiling."""

    data = _coerce(inputs, G8DomainVsSearchCeilingInputs)
    blockers = list(_input_issue_codes(data.input_refs))
    if data.search_recall_status != "pass" or data.index_freshness_status != "pass":
        status = "search_ceiling_repair_required"
        blockers.append("layer3_g8_search_health_not_sufficient_for_domain_ceiling")
        readiness: Literal["pass", "fail", "blocked", "limited", "review_required"] = "blocked"
    elif (
        data.g5_conversion_outcome == "grounded_abstention"
        and data.g7_region_closure == "region_closed"
    ):
        status = "domain_ceiling_supported"
        readiness = "pass"
    else:
        status = "domain_ceiling_blocked"
        readiness = "fail"
        blockers.append("layer3_g8_domain_ceiling_not_proven")
    return _decision(
        reducer_id="reduce_g8_domain_vs_search_ceiling",
        status_field="domain_vs_search_ceiling_status",
        status=status,
        readiness_status=readiness,
        input_refs=data.input_refs,
        blocker_refs=blockers,
    )


def _coerce[ReducerInputT: _ReducerModel](
    value: BaseModel | Mapping[str, object],
    model: type[ReducerInputT],
) -> ReducerInputT:
    if isinstance(value, model):
        return value
    return model.model_validate(value)


def _input_issue_codes(input_refs: Sequence[Layer3ReducerInputRef]) -> tuple[str, ...]:
    issues: list[str] = []
    if not input_refs:
        issues.append("layer3_gx_required_input_ref_missing")
    for input_ref in input_refs:
        if input_ref.required and (not input_ref.exists or not input_ref.ref):
            issues.append("layer3_gx_required_input_ref_missing")
        if not input_ref.fixture_input and (
            not input_ref.content_hash or not input_ref.producer_ref
        ):
            issues.append("layer3_gx_inline_input_forbidden")
        if (
            input_ref.supply_side
            and not input_ref.fixture_input
            and (
                str(input_ref.producer_type or "") in INVALID_SUPPLY_PRODUCER_TYPES
                or input_ref.producer_root_status in INVALID_SUPPLY_ROOT_STATUSES
            )
        ):
            issues.append("layer3_gx_producer_root_invalid")
    return _dedupe(issues)


def _decision(
    *,
    reducer_id: str,
    status_field: str,
    status: str,
    readiness_status: Literal["pass", "fail", "blocked", "limited", "review_required"],
    input_refs: Sequence[Layer3ReducerInputRef],
    blocker_refs: Sequence[str] = (),
    limitation_refs: Sequence[str] = (),
) -> Layer3ReducerDecision:
    input_hashes = {
        str(input_ref.ref): str(input_ref.content_hash)
        for input_ref in input_refs
        if input_ref.ref and input_ref.content_hash
    }
    produced_by_without_hash = {
        "reducer_id": reducer_id,
        "reducer_version": LAYER3_REDUCER_VERSION,
        "rule_version": LAYER3_REDUCER_RULE_VERSION,
        "input_hashes": input_hashes,
        "vocabulary_status_id": status,
    }
    output_hash = _hash_payload(
        {
            status_field: status,
            "produced_by": produced_by_without_hash,
        }
    )
    issue_codes = _dedupe((*blocker_refs, *_input_issue_codes(input_refs)))
    produced_by = {**produced_by_without_hash, "output_hash": output_hash}
    return Layer3ReducerDecision(
        reducer_id=reducer_id,
        rule_version=LAYER3_REDUCER_RULE_VERSION,
        status_field=status_field,
        status=status,
        readiness_status=readiness_status,
        vocabulary_status_id=status,
        blocker_refs=_dedupe(blocker_refs),
        limitation_refs=_dedupe(limitation_refs),
        input_refs=tuple(ref for ref in input_hashes),
        input_hashes=input_hashes,
        issue_codes=issue_codes,
        produced_by=produced_by,
    )


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _json_dumps(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _hash_payload(payload: object) -> str:
    encoded = _json_dumps(payload).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
