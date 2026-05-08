"""Typed dynamic causal semantics attachments for proof-kernel artifacts.

These models are intentionally small and proof-oriented. They let the public
``ProofBundle`` carry the minimum machine-checkable structure needed to explain
why a cyclic or continuous-time query was accepted, blocked, or kept at the
research boundary.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ForecastInterventionCertificateRef, ForecastInterventionQueryRef

_FORECAST_INTERVENTION_QUERY_SCHEMA_NAME = "ir.forecast_intervention_query"
_FORECAST_INTERVENTION_QUERY_SCHEMA_VERSION = "1.0"
_FORECAST_INTERVENTION_CERTIFICATE_SCHEMA_NAME = "ir.forecast_intervention_certificate"
_FORECAST_INTERVENTION_CERTIFICATE_SCHEMA_VERSION = "1.0"
_FORECAST_REPLAY_FINGERPRINT_KEYS = frozenset(
    {
        "announcement_timing_hash",
        "disclosure_rule_hash",
        "update_operator_hash",
        "graph_projection_hash",
        "decomposition_witness_hash",
    }
)


class DynamicSemanticsFamily(str, Enum):
    """Semantic family used to interpret a dynamic or cyclic causal query."""

    IOSCM = "ioSCM"
    SIMPLE_SCM = "simple_SCM"
    LOCAL_INDEPENDENCE_GRAPH = "local_independence_graph"
    ADMG = "admg"


class GraphicalOracleKind(str, Enum):
    """Graphical Markov criterion used by a dynamic proof path."""

    D = "d"
    SIGMA = "sigma"
    MU = "mu"
    DELTA = "delta"


class InterventionKind(str, Enum):
    """Intervention kinds currently distinguished by the proof kernel."""

    NODE_DO = "node_do"
    MECHANISM_SWAP = "mechanism_swap"
    INTENSITY_INTERVENTION = "intensity_intervention"
    FORECAST_PUBLICATION = "forecast_publication"


class ForecastSemanticsClass(str, Enum):
    """Semantic interpretation of a public forecast/guidance announcement."""

    DELPHIC = "delphic"
    ODYSSEAN = "odyssean"
    HYBRID = "hybrid"


class ForecastIdentifiedComponent(str, Enum):
    """Component that the forecast-intervention certificate is allowed to claim."""

    EXPECTATION_ONLY = "expectation_only"
    TOTAL_ANNOUNCEMENT = "total_announcement"
    POLICY_COMMITMENT = "policy_commitment"
    HYBRID_PARTIAL = "hybrid_partial"


class ForecastUpdateOperatorKind(str, Enum):
    """How the public message is interpreted as an update to beliefs/rules."""

    BAYES = "bayes"
    RULE_COMMITMENT = "rule_commitment"
    CALIBRATED_BEHAVIORAL = "calibrated_behavioral"
    UNKNOWN = "unknown"


class ForecastIdentificationMethod(str, Enum):
    """Recognized v1 designs for separating and identifying announcement effects."""

    LOCAL_INDEPENDENCE_REWEIGHTING = "local_independence_reweighting"
    HIGH_FREQUENCY_SIGN_DECOMPOSITION = "high_frequency_sign_decomposition"
    RANDOMIZED_DISCLOSURE = "randomized_disclosure"
    FRONTDOOR_OR_PROXY = "frontdoor_or_proxy"
    MIXED = "mixed"


class ForecastDownstreamChannel(str, Enum):
    """Channels allowed between the publication and the downstream outcome."""

    EXPECTATIONS = "expectations"
    POLICY_RULE = "policy_rule"


class DynamicReductionStatus(str, Enum):
    """How far the engine reduced the dynamic query to a certified backend."""

    VALIDATED_REDUCTION = "validated_reduction"
    HEURISTIC_ONLY = "heuristic_only"
    BLOCKED = "blocked"


class WellPosednessStatus(str, Enum):
    """Status of the well-posedness witness for a cyclic or dynamic fragment."""

    PROVED = "proved"
    REFUTED = "refuted"
    HEURISTIC_BLOCKED = "heuristic_blocked"


class InterventionScope(BaseModel):
    """Admissible intervention summary for a dynamic proof path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: InterventionKind
    targets: tuple[str, ...] = ()
    admissible: bool = True
    admissibility_theorem: str | None = None


class WellPosednessWitness(BaseModel):
    """Machine-checkable summary of the semantics well-posedness check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: WellPosednessStatus
    family: str
    method: str
    confidence: str
    lipschitz_constant: float | None = None
    warning: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class SeparationClaim(BaseModel):
    """Statement of a graphical separation query used in the proof path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x_set: tuple[str, ...] = ()
    y_set: tuple[str, ...] = ()
    z_set: tuple[str, ...] = ()
    holds: bool
    criterion: GraphicalOracleKind


class GraphicalMarkovCertificate(BaseModel):
    """Constructive graphical-causal certificate for dynamic semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    certificate_type: str = "graphical_markov"
    semantics_family: DynamicSemanticsFamily
    graphical_oracle: GraphicalOracleKind
    theorem_family: str
    source_graph_ref: str | None = None
    latent_projection_ref: str | None = None
    intervention_spec: InterventionScope | None = None
    separation_claim: SeparationClaim | None = None
    transformation_trace: tuple[str, ...] = ()
    required_distributions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class DynamicScopeStatement(BaseModel):
    """Declared supported and excluded dynamic-semantics families."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    covered_families: tuple[str, ...] = ()
    excluded_families: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class LocalIndependenceAttachment(BaseModel):
    """Continuous-time attachment for local-independence-based semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graphical_oracle: GraphicalOracleKind
    causal_validity_rule: str | None = None
    eliminable_processes: tuple[str, ...] = ()
    process_family: str | None = None
    policy_semantics: str | None = None
    censoring_mode: str | None = None
    identification_method: str | None = None
    weighting_components: tuple[str, ...] = ()
    independent_censoring_checked: bool | None = None
    positivity_assumed: bool | None = None
    notes: tuple[str, ...] = ()


def _clean_non_empty(value: object, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _clean_string_tuple(value: object, *, field_name: str) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    cleaned = tuple(_clean_non_empty(item, field_name=field_name) for item in value)
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field_name} must not contain duplicates")
    return cleaned


class ForecastAnnouncementWindow(BaseModel):
    """Time window used to localize pre/post announcement information."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: str
    end: str

    @field_validator("start", "end", mode="before")
    @classmethod
    def _validate_non_empty(cls, value: object) -> str:
        return _clean_non_empty(value, field_name="announcement window bound")


class ForecastContrastSpec(BaseModel):
    """Contrast between the published message and an alternative publication law."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str
    baseline_message: str
    assignment_law_ref: str | None = None

    @field_validator("message", "baseline_message", mode="before")
    @classmethod
    def _validate_message(cls, value: object) -> str:
        return _clean_non_empty(value, field_name="forecast contrast message")

    @model_validator(mode="after")
    def _validate_contrast(self) -> ForecastContrastSpec:
        if self.message == self.baseline_message:
            raise ValueError("forecast contrast messages must differ")
        return self


class ForecastInterventionQuery(BaseModel):
    """Typed forecast-as-treatment query over a localized announcement event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    message_var: str
    announcement_time: str
    semantics_class: ForecastSemanticsClass
    expectation_target: str
    outcome_target: str
    contrast_spec: ForecastContrastSpec
    decomposition_goal: ForecastIdentifiedComponent = ForecastIdentifiedComponent.EXPECTATION_ONLY
    update_operator_kind: ForecastUpdateOperatorKind = ForecastUpdateOperatorKind.UNKNOWN
    decomposition_method: ForecastIdentificationMethod | None = None
    pre_announcement_window: ForecastAnnouncementWindow | None = None
    post_announcement_window: ForecastAnnouncementWindow | None = None
    hard_actions_same_window: tuple[str, ...] = ()
    continuous_time: bool = True
    event_history_required: bool = True
    positivity_claimed: bool | None = None
    censoring_assessed: bool | None = None
    required_observables: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "message_var",
        "announcement_time",
        "expectation_target",
        "outcome_target",
        mode="before",
    )
    @classmethod
    def _validate_non_empty_fields(cls, value: object) -> str:
        return _clean_non_empty(value, field_name="forecast query field")

    @field_validator("hard_actions_same_window", "required_observables", mode="before")
    @classmethod
    def _validate_string_tuples(cls, value: object) -> tuple[str, ...]:
        return _clean_string_tuple(value, field_name="forecast query tuple field")

    @model_validator(mode="after")
    def _validate_goal_semantics(self) -> ForecastInterventionQuery:
        if (
            self.decomposition_goal is ForecastIdentifiedComponent.POLICY_COMMITMENT
            and self.semantics_class is ForecastSemanticsClass.DELPHIC
        ):
            raise ValueError("delphic forecast queries cannot request policy_commitment effects")
        return self

    @property
    def query_str(self) -> str:
        return (
            "forecast_intervention("
            f"{self.message_var}@{self.announcement_time}:"
            f"{self.contrast_spec.message} vs {self.contrast_spec.baseline_message}"
            f" -> {self.outcome_target}; semantics={self.semantics_class.value})"
        )


class ForecastExogeneityChecks(BaseModel):
    """Announcement-window checks needed to interpret the message as treatment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preannouncement_orthogonalization_passed: bool
    simultaneous_action_excluded: bool
    anticipation_excluded: bool


class ForecastSupportChecks(BaseModel):
    """Support/overlap checks for the message contrast."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    positivity_passed: bool
    overlap_notes: tuple[str, ...] = ()

    @field_validator("overlap_notes", mode="before")
    @classmethod
    def _validate_notes(cls, value: object) -> tuple[str, ...]:
        return _clean_string_tuple(value, field_name="overlap_notes")


class ForecastCensoringChecks(BaseModel):
    """Continuous-time censoring checks for event-history forecast queries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    independent_censoring_checked: bool | None = None
    causal_censoring_validity_checked: bool | None = None


class ForecastInterventionCertificate(BaseModel):
    """Certificate for treating a public forecast as an information-law intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    certificate_type: Literal["forecast_intervention"] = "forecast_intervention"
    semantics_class: ForecastSemanticsClass
    identified_component: ForecastIdentifiedComponent
    announcement_node: str
    intervention_time: str
    expectation_process_ref: str
    update_operator_kind: ForecastUpdateOperatorKind
    update_operator_ref: str | None = None
    admissible_intervention: bool
    intervention_kind: Literal["forecast_publication"] = "forecast_publication"
    downstream_channels_allowed: tuple[ForecastDownstreamChannel, ...] = (
        ForecastDownstreamChannel.EXPECTATIONS,
    )
    graphical_oracle: GraphicalOracleKind
    separation_claim_ref: str | None = None
    local_independence_claim_ref: str | None = None
    causal_validity_rule: str | None = None
    identification_method: ForecastIdentificationMethod
    exogeneity_checks: ForecastExogeneityChecks
    support_checks: ForecastSupportChecks
    censoring_checks: ForecastCensoringChecks = Field(default_factory=ForecastCensoringChecks)
    well_posedness_ref: str | None = None
    required_observables: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator(
        "announcement_node",
        "intervention_time",
        "expectation_process_ref",
        mode="before",
    )
    @classmethod
    def _validate_non_empty_fields(cls, value: object) -> str:
        return _clean_non_empty(value, field_name="forecast certificate field")

    @field_validator("required_observables", "blocking_reasons", "notes", mode="before")
    @classmethod
    def _validate_string_tuples(cls, value: object) -> tuple[str, ...]:
        return _clean_string_tuple(value, field_name="forecast certificate tuple field")

    @field_validator("downstream_channels_allowed", mode="before")
    @classmethod
    def _validate_channels(cls, value: object) -> tuple[ForecastDownstreamChannel, ...]:
        if value in (None, ()):
            raise ValueError("downstream_channels_allowed must be non-empty")
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("downstream_channels_allowed must be a sequence")
        return tuple(ForecastDownstreamChannel(item) for item in value)

    @model_validator(mode="after")
    def _validate_certificate_semantics(self) -> ForecastInterventionCertificate:
        channels = set(self.downstream_channels_allowed)
        if self.semantics_class is ForecastSemanticsClass.DELPHIC:
            if ForecastDownstreamChannel.POLICY_RULE in channels:
                raise ValueError("delphic forecast certificates cannot allow policy_rule channel")
            if self.identified_component is ForecastIdentifiedComponent.POLICY_COMMITMENT:
                raise ValueError("delphic forecast certificates cannot claim policy_commitment")
        if (
            self.identified_component is ForecastIdentifiedComponent.POLICY_COMMITMENT
            and self.update_operator_kind is not ForecastUpdateOperatorKind.RULE_COMMITMENT
        ):
            raise ValueError("policy_commitment claims require rule_commitment update operator")
        if (
            self.identified_component is ForecastIdentifiedComponent.EXPECTATION_ONLY
            and ForecastDownstreamChannel.EXPECTATIONS not in channels
        ):
            raise ValueError("expectation_only claims must allow the expectations channel")
        return self

    @property
    def proof_status(self) -> Literal["identified", "non_identified", "oracle_needed"]:
        """Map certificate checks onto the ProofBundle status triad."""

        return forecast_intervention_proof_status(self)


class ForecastInterventionAttachment(ForecastInterventionCertificate):
    """Dynamic semantics attachment carried inside ``DynamicSemanticsAttachment``."""

    query: ForecastInterventionQuery | None = None
    query_ref: str | None = None
    proof_support_fingerprints: dict[str, str] = Field(default_factory=dict)

    @field_validator("query_ref", mode="before")
    @classmethod
    def _validate_query_ref(cls, value: object) -> str | None:
        if value is None:
            return None
        return _clean_non_empty(value, field_name="query_ref")

    @field_validator("proof_support_fingerprints", mode="before")
    @classmethod
    def _validate_fingerprints(cls, value: object) -> dict[str, str]:
        if value in (None, {}):
            return {}
        if not isinstance(value, dict):
            raise ValueError("proof_support_fingerprints must be a mapping")
        return {
            _clean_non_empty(key, field_name="proof_support_fingerprint key"): _clean_non_empty(
                item, field_name="proof_support_fingerprint value"
            )
            for key, item in value.items()
        }

    @property
    def missing_replay_fingerprints(self) -> tuple[str, ...]:
        """Fingerprint obligations needed for reusable proof-trace replay."""

        return tuple(sorted(_FORECAST_REPLAY_FINGERPRINT_KEYS - self.proof_support_fingerprints.keys()))

    @property
    def replay_composability_status(self) -> Literal["reusable", "revalidate"]:
        """Return whether forecast replay has all required stability fingerprints."""

        return "reusable" if not self.missing_replay_fingerprints else "revalidate"


def forecast_intervention_proof_status(
    certificate: ForecastInterventionCertificate,
) -> Literal["identified", "non_identified", "oracle_needed"]:
    """Classify the narrow v1 forecast-intervention certificate.

    The ladder is intentionally conservative: explicit support/exclusion failures
    are non-identification, while missing update/decomposition/dynamic-validity
    witnesses stay at the research boundary.
    """

    if not certificate.admissible_intervention:
        return "non_identified"
    if certificate.support_checks.positivity_passed is False:
        return "non_identified"
    if certificate.exogeneity_checks.preannouncement_orthogonalization_passed is False:
        return "non_identified"
    if certificate.exogeneity_checks.simultaneous_action_excluded is False:
        return "non_identified"
    if certificate.exogeneity_checks.anticipation_excluded is False:
        return "non_identified"
    if certificate.censoring_checks.independent_censoring_checked is False:
        return "non_identified"
    if certificate.censoring_checks.causal_censoring_validity_checked is False:
        return "non_identified"
    if certificate.well_posedness_ref is None:
        return "oracle_needed"
    if certificate.update_operator_kind is ForecastUpdateOperatorKind.UNKNOWN:
        return "oracle_needed"
    if certificate.censoring_checks.independent_censoring_checked is None:
        return "oracle_needed"
    if certificate.censoring_checks.causal_censoring_validity_checked is None:
        return "oracle_needed"
    if not (certificate.local_independence_claim_ref or certificate.separation_claim_ref):
        return "oracle_needed"
    if certificate.causal_validity_rule is None:
        return "oracle_needed"
    if (
        certificate.identified_component is ForecastIdentifiedComponent.EXPECTATION_ONLY
        and certificate.identification_method
        not in {
            ForecastIdentificationMethod.LOCAL_INDEPENDENCE_REWEIGHTING,
            ForecastIdentificationMethod.HIGH_FREQUENCY_SIGN_DECOMPOSITION,
            ForecastIdentificationMethod.RANDOMIZED_DISCLOSURE,
            ForecastIdentificationMethod.FRONTDOOR_OR_PROXY,
            ForecastIdentificationMethod.MIXED,
        }
    ):
        return "oracle_needed"
    if certificate.semantics_class is ForecastSemanticsClass.HYBRID:
        if certificate.identified_component is ForecastIdentifiedComponent.EXPECTATION_ONLY:
            return "oracle_needed"
        if (
            certificate.identified_component is ForecastIdentifiedComponent.HYBRID_PARTIAL
            and certificate.identification_method is not ForecastIdentificationMethod.MIXED
        ):
            return "oracle_needed"
    if (
        certificate.identified_component is ForecastIdentifiedComponent.TOTAL_ANNOUNCEMENT
        and certificate.semantics_class is ForecastSemanticsClass.HYBRID
    ):
        return "identified"
    return "identified"


def _forecast_blocking_reasons(
    *,
    admissible_intervention: bool,
    exogeneity_checks: ForecastExogeneityChecks,
    support_checks: ForecastSupportChecks,
    censoring_checks: ForecastCensoringChecks,
    well_posedness_ref: str | None,
    update_operator_kind: ForecastUpdateOperatorKind,
    local_independence_claim_ref: str | None,
    separation_claim_ref: str | None,
    causal_validity_rule: str | None,
    semantics_class: ForecastSemanticsClass,
    identified_component: ForecastIdentifiedComponent,
    identification_method: ForecastIdentificationMethod,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not admissible_intervention:
        reasons.append("inadmissible_forecast_intervention")
    if not exogeneity_checks.preannouncement_orthogonalization_passed:
        reasons.append("preannouncement_orthogonalization_failed")
    if not exogeneity_checks.simultaneous_action_excluded:
        reasons.append("simultaneous_action_not_excluded")
    if not exogeneity_checks.anticipation_excluded:
        reasons.append("anticipation_not_excluded")
    if not support_checks.positivity_passed:
        reasons.append("positivity_failed")
    if censoring_checks.independent_censoring_checked is False:
        reasons.append("independent_censoring_failed")
    elif censoring_checks.independent_censoring_checked is None:
        reasons.append("independent_censoring_unverified")
    if censoring_checks.causal_censoring_validity_checked is False:
        reasons.append("causal_censoring_validity_failed")
    elif censoring_checks.causal_censoring_validity_checked is None:
        reasons.append("causal_censoring_validity_unverified")
    if well_posedness_ref is None:
        reasons.append("well_posedness_missing")
    if update_operator_kind is ForecastUpdateOperatorKind.UNKNOWN:
        reasons.append("update_operator_unknown")
    if not (local_independence_claim_ref or separation_claim_ref):
        reasons.append("graphical_claim_missing")
    if causal_validity_rule is None:
        reasons.append("causal_validity_rule_missing")
    if (
        semantics_class is ForecastSemanticsClass.HYBRID
        and identified_component is ForecastIdentifiedComponent.EXPECTATION_ONLY
    ):
        reasons.append("hybrid_expectation_only_requires_decomposition_witness")
    if (
        semantics_class is ForecastSemanticsClass.HYBRID
        and identified_component is ForecastIdentifiedComponent.HYBRID_PARTIAL
        and identification_method is not ForecastIdentificationMethod.MIXED
    ):
        reasons.append("hybrid_partial_requires_mixed_identification_method")
    return tuple(dict.fromkeys(reasons))


def build_forecast_intervention_attachment(
    *,
    query: ForecastInterventionQuery,
    graphical_oracle: GraphicalOracleKind,
    exogeneity_checks: ForecastExogeneityChecks,
    support_checks: ForecastSupportChecks,
    identification_method: ForecastIdentificationMethod | None = None,
    expectation_process_ref: str | None = None,
    update_operator_ref: str | None = None,
    admissible_intervention: bool = True,
    downstream_channels_allowed: tuple[ForecastDownstreamChannel, ...] | None = None,
    local_independence_claim_ref: str | None = None,
    separation_claim_ref: str | None = None,
    causal_validity_rule: str | None = None,
    censoring_checks: ForecastCensoringChecks | None = None,
    well_posedness_ref: str | None = None,
    query_ref: str | None = None,
    proof_support_fingerprints: dict[str, str] | None = None,
    blocking_reasons: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
) -> ForecastInterventionAttachment:
    """Build a conservative forecast intervention attachment from query witnesses."""

    resolved_method = identification_method or query.decomposition_method
    if resolved_method is None:
        resolved_method = ForecastIdentificationMethod.MIXED
    resolved_censoring = censoring_checks or ForecastCensoringChecks(
        independent_censoring_checked=query.censoring_assessed,
        causal_censoring_validity_checked=query.censoring_assessed,
    )
    if downstream_channels_allowed is None:
        if query.semantics_class is ForecastSemanticsClass.DELPHIC:
            downstream_channels_allowed = (ForecastDownstreamChannel.EXPECTATIONS,)
        else:
            downstream_channels_allowed = (
                ForecastDownstreamChannel.EXPECTATIONS,
                ForecastDownstreamChannel.POLICY_RULE,
            )
    derived_reasons = _forecast_blocking_reasons(
        admissible_intervention=admissible_intervention,
        exogeneity_checks=exogeneity_checks,
        support_checks=support_checks,
        censoring_checks=resolved_censoring,
        well_posedness_ref=well_posedness_ref,
        update_operator_kind=query.update_operator_kind,
        local_independence_claim_ref=local_independence_claim_ref,
        separation_claim_ref=separation_claim_ref,
        causal_validity_rule=causal_validity_rule,
        semantics_class=query.semantics_class,
        identified_component=query.decomposition_goal,
        identification_method=resolved_method,
    )
    return ForecastInterventionAttachment(
        semantics_class=query.semantics_class,
        identified_component=query.decomposition_goal,
        announcement_node=query.message_var,
        intervention_time=query.announcement_time,
        expectation_process_ref=expectation_process_ref or query.expectation_target,
        update_operator_kind=query.update_operator_kind,
        update_operator_ref=update_operator_ref,
        admissible_intervention=admissible_intervention,
        downstream_channels_allowed=downstream_channels_allowed,
        graphical_oracle=graphical_oracle,
        separation_claim_ref=separation_claim_ref,
        local_independence_claim_ref=local_independence_claim_ref,
        causal_validity_rule=causal_validity_rule,
        identification_method=resolved_method,
        exogeneity_checks=exogeneity_checks,
        support_checks=support_checks,
        censoring_checks=resolved_censoring,
        well_posedness_ref=well_posedness_ref,
        required_observables=query.required_observables,
        blocking_reasons=tuple(dict.fromkeys((*blocking_reasons, *derived_reasons))),
        notes=notes,
        query=query,
        query_ref=query_ref,
        proof_support_fingerprints=proof_support_fingerprints or {},
    )


class DynamicSemanticsAttachment(BaseModel):
    """Top-level proof attachment for cyclic and continuous-time semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantics_family: DynamicSemanticsFamily
    reduction_status: DynamicReductionStatus = DynamicReductionStatus.HEURISTIC_ONLY
    markov_criterion_certificate: GraphicalMarkovCertificate | None = None
    well_posedness_witness: WellPosednessWitness | None = None
    intervention_scope: InterventionScope | None = None
    continuous_time_attachment: LocalIndependenceAttachment | None = None
    forecast_intervention: ForecastInterventionAttachment | None = None
    scope_statement: DynamicScopeStatement | None = None

    @model_validator(mode="after")
    def _validate_forecast_integration(self) -> DynamicSemanticsAttachment:
        if self.forecast_intervention is None:
            return self
        if (
            self.intervention_scope is not None
            and self.intervention_scope.kind is not InterventionKind.FORECAST_PUBLICATION
        ):
            raise ValueError(
                "forecast_intervention requires intervention_scope.kind=forecast_publication"
            )
        if self.forecast_intervention.proof_status == "identified":
            if self.semantics_family is not DynamicSemanticsFamily.LOCAL_INDEPENDENCE_GRAPH:
                raise ValueError(
                    "identified forecast interventions require local_independence_graph semantics"
                )
            if self.continuous_time_attachment is None:
                raise ValueError(
                    "identified forecast interventions require continuous_time_attachment"
                )
        return self


def persist_forecast_intervention_query(
    store: ArtifactStore,
    query: ForecastInterventionQuery,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _FORECAST_INTERVENTION_QUERY_SCHEMA_NAME,
    schema_version: str = _FORECAST_INTERVENTION_QUERY_SCHEMA_VERSION,
) -> ForecastInterventionQueryRef:
    """Persist a forecast intervention query and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        query.model_dump(mode="json"),
        kind="ir.forecast_intervention_query",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ForecastInterventionQueryRef.model_validate(ref)


def load_forecast_intervention_query(
    store: ArtifactStore,
    ref: ForecastInterventionQueryRef,
) -> ForecastInterventionQuery:
    """Load a persisted forecast intervention query."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ForecastInterventionQuery.model_validate(payload)


def persist_forecast_intervention_certificate(
    store: ArtifactStore,
    certificate: ForecastInterventionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _FORECAST_INTERVENTION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _FORECAST_INTERVENTION_CERTIFICATE_SCHEMA_VERSION,
) -> ForecastInterventionCertificateRef:
    """Persist a forecast intervention certificate and return its typed artifact ref."""

    payload = certificate.model_dump(mode="json")
    payload.pop("query", None)
    payload.pop("query_ref", None)
    payload.pop("proof_support_fingerprints", None)
    payload = ForecastInterventionCertificate.model_validate(payload).model_dump(mode="json")
    ref = put_json_artifact(
        store,
        payload,
        kind="ir.forecast_intervention_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ForecastInterventionCertificateRef.model_validate(ref)


def load_forecast_intervention_certificate(
    store: ArtifactStore,
    ref: ForecastInterventionCertificateRef,
) -> ForecastInterventionCertificate:
    """Load a persisted forecast intervention certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ForecastInterventionCertificate.model_validate(payload)


__all__ = [
    "DynamicReductionStatus",
    "DynamicScopeStatement",
    "DynamicSemanticsAttachment",
    "DynamicSemanticsFamily",
    "ForecastAnnouncementWindow",
    "ForecastCensoringChecks",
    "ForecastContrastSpec",
    "ForecastDownstreamChannel",
    "ForecastExogeneityChecks",
    "ForecastIdentificationMethod",
    "ForecastIdentifiedComponent",
    "ForecastInterventionAttachment",
    "ForecastInterventionCertificate",
    "ForecastInterventionQuery",
    "ForecastSemanticsClass",
    "ForecastSupportChecks",
    "ForecastUpdateOperatorKind",
    "GraphicalMarkovCertificate",
    "GraphicalOracleKind",
    "InterventionKind",
    "InterventionScope",
    "LocalIndependenceAttachment",
    "SeparationClaim",
    "WellPosednessStatus",
    "WellPosednessWitness",
    "build_forecast_intervention_attachment",
    "forecast_intervention_proof_status",
    "load_forecast_intervention_certificate",
    "load_forecast_intervention_query",
    "persist_forecast_intervention_certificate",
    "persist_forecast_intervention_query",
]
