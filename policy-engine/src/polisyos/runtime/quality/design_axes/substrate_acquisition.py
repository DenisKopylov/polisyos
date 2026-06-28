"""Layer 2 S3 substrate acquisition contracts.

The S3 slice describes construct demand in facet space and resolves it through
the existing capability spine. It does not create a parallel dataset catalog or
let legacy scenario-family strings select authority.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import (
    AuthorityBoundary,
    ValueOfInformationEstimate,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionPlannerReport,
    plan_requirement_gap_acquisition,
    requirement_gaps_from_compiled_specs,
)
from polisyos.runtime.quality.capability_index import (
    AuthorityEnvelope,
    CapabilityScope,
    CapabilitySourceAsset,
    EvidenceCapability,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)
from polisyos.runtime.quality.capability_resolver import (
    RequirementToCapabilityQuery,
    RequirementToCapabilityResolver,
)
from polisyos.runtime.quality.proving_ground.pinned_route_demand_home import read_layer3_gx_pinned_case_id

if TYPE_CHECKING:
    from polisyos.runtime.quality.capability_authority import CapabilityBindingResult

LAYER2_S3_SUBSTRATE_ACQUISITION_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s3_substrate_acquisition.v1"
)
_SEED = "architecture/policy_design_case/layer2_minimal_seed_manifest.json"
REPO_ROOT = Path(__file__).resolve().parents[5]
S3_PINNED_CASE_ID = read_layer3_gx_pinned_case_id(REPO_ROOT)

S3AuthorityPosture = Literal["research", "governed", "production"]

_PROXY_LIMITED_STATUSES = frozenset(
    {
        "selected_proxy_with_limitation",
        "selected_context_only",
        "selected_simulation_only",
    }
)
_EXACT_STATUSES = frozenset({"selected_exact", "selected_derived"})
_PRODUCTION_ADMISSIBLE_STATUSES = _EXACT_STATUSES
_NON_TERMINAL_END = "rerun_consumed_delta"
_TERMINAL_STATES = frozenset(
    {
        "closed_as_binding",
        "closed_as_limitation",
        "closed_as_still_blocked",
    }
)


class _BindingResultLike(Protocol):
    status: str

    def model_dump(self, *, mode: str) -> dict[str, object]:
        """Return a JSON-serializable binding payload."""

        ...


class AcquisitionState(StrEnum):
    """D2.8 acquisition loop states exposed before Task 3 orchestration."""

    GAP_DETECTED = "gap_detected"
    ELIGIBILITY_CHECKED = "eligibility_checked"
    RANKED_BY_VOI = "ranked_by_voi"
    TASK_OPENED = "task_opened"
    SOURCE_ACQUIRED = "source_acquired"
    SOURCE_CONTRACT_VALIDATED = "source_contract_validated"
    CAPABILITY_INDEX_UPDATED = "capability_index_updated"
    RERUN_STARTED = "rerun_started"
    RERUN_CONSUMED_DELTA = "rerun_consumed_delta"
    CLOSED_AS_BINDING = "closed_as_binding"
    CLOSED_AS_LIMITATION = "closed_as_limitation"
    CLOSED_AS_STILL_BLOCKED = "closed_as_still_blocked"


class _S3Model(BaseModel):
    """Strict base model for S3 public DTOs."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_version: Literal[
        "policyos.policy_design_case.layer2_s3_substrate_acquisition.v1"
    ] = LAYER2_S3_SUBSTRATE_ACQUISITION_SCHEMA_VERSION


class ConstructExpression(_S3Model):
    """One compositional demand expression over frozen facet primitives."""

    construct_id: str = Field(
        alias="construct",
        serialization_alias="construct",
        min_length=1,
    )
    facets: dict[str, str] = Field(default_factory=dict)
    authority_posture: S3AuthorityPosture
    rule_version_refs: list[str] = Field(default_factory=list)
    allowed_facet_primitives: list[str] | None = None

    @model_validator(mode="after")
    def _facets_in_seed(self) -> ConstructExpression:
        allowed = set(self.allowed_facet_primitives or _frozen_facet_primitives())
        for key in self.facets:
            if key not in allowed:
                raise ValueError(
                    f"facet primitive '{key}' is not in the frozen seed primitives"
                )
        return self

    @property
    def construct(self) -> str:
        """Return the construct selector using the S3 public field name."""

        return self.construct_id

    def is_composed_from(self, primitives: list[str]) -> bool:
        """Return whether every facet key comes from the supplied primitives."""

        return set(self.facets).issubset(set(primitives))


class ConstructDemandLedger(_S3Model):
    """Facet-space denominator for demanded constructs, never evidence."""

    case_id: str = Field(min_length=1)
    expressions: list[ConstructExpression] = Field(min_length=1)
    authority_posture: S3AuthorityPosture

    @property
    def authority_boundary(self) -> AuthorityBoundary:
        """Return the purpose-scoped boundary for denominator-only demand."""

        return AuthorityBoundary(
            authoritative_for=[
                "construct_demand_denominator",
                "substrate_coverage_snapshot",
            ],
            may_not_use_for=[
                "claim_authority",
                "evidence_authority",
                "production_claim_authority",
            ],
            source_authority="deterministic_producer",
            posture=self.authority_posture,
            rule_version_refs=[f"repo://{_SEED}"],
        )


class SubstrateCoverageSnapshot(_S3Model):
    """Denominator-aware S3 substrate coverage summary."""

    demanded: int = Field(ge=0)
    observed: int = Field(ge=0)
    proxy_limited: int = Field(ge=0)
    construct_not_observed: int = Field(ge=0)
    authority_posture: S3AuthorityPosture

    @model_validator(mode="after")
    def _counts_do_not_exceed_denominator(self) -> SubstrateCoverageSnapshot:
        represented = self.observed + self.proxy_limited + self.construct_not_observed
        if represented > self.demanded:
            raise ValueError("coverage counts cannot exceed demanded construct denominator")
        return self

    def construct_demand_coverage(self) -> float:
        """Return observed plus proxy-limited coverage over demanded constructs."""

        if self.demanded == 0:
            return 0.0
        return (self.observed + self.proxy_limited) / self.demanded

    def bounded_abstention_rate(self) -> float:
        """Return explicitly unobserved construct demand over the denominator."""

        if self.demanded == 0:
            return 0.0
        return self.construct_not_observed / self.demanded


class AcquisitionTaskRecord(_S3Model):
    """Owned acquisition task opened from an eligible planner record."""

    construct_ref: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    route: Literal["automated", "human_fallback"]
    ttl_days: int = Field(ge=1)
    legal_use_reviewed: bool
    expected_authority_posture: S3AuthorityPosture
    voi_ref: str = Field(min_length=1)


class SourceDiscoveryCandidate(_S3Model):
    """Deterministic fixture-mode source candidate from the Fabric registry path."""

    construct_ref: str = Field(min_length=1)
    connector: str = Field(min_length=1)
    source_fixture: str = Field(min_length=1)
    rights_scope: str = Field(min_length=1)


class SourceContract(_S3Model):
    """Validated source contract that can produce a capability-index delta."""

    construct_ref: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    lineage_ref: str = Field(min_length=1)
    rights_scope: str = Field(min_length=1)
    coverage_period: str = Field(min_length=1)
    update_cadence: str = Field(min_length=1)
    linkage_key_quality: str = Field(min_length=1)
    construct_validity_note: str = Field(min_length=1)
    capability_index_delta_ref: str = Field(min_length=1)


class _Transition(_S3Model):
    state: AcquisitionState
    detail: str | None = None


class FrozenClosedCase(_S3Model):
    """Frozen refs used to replay a closed or blocked case deterministically."""

    rule_version_ref: str = Field(min_length=1)
    capability_index_ref: str = Field(min_length=1)
    constraint_refs: tuple[str, ...] = Field(default=())
    outcome: str = Field(min_length=1)


class RerunClosureReceipt(_S3Model):
    """Receipt proving that acquisition closure consumed an index delta."""

    construct_ref: str = Field(min_length=1)
    transitions: tuple[_Transition, ...]
    terminal: AcquisitionState
    voi_ref: str | None
    binding_status: str = Field(min_length=1)
    binding: dict[str, Any]
    coverage_snapshot: SubstrateCoverageSnapshot
    frozen: FrozenClosedCase


class SubstrateAcquisitionLoop:
    """Deterministic, replay-safe acquisition loop for S3 fixture mode."""

    def __init__(
        self,
        *,
        expression: ConstructExpression,
        source_fixture: str,
    ) -> None:
        self._expression = expression
        self._source_fixture = source_fixture
        self._state: AcquisitionState | None = None
        self._terminal: AcquisitionState | None = None
        self._receipt: RerunClosureReceipt | None = None
        self._initial_binding_status: str | None = None
        self._updated_resolver: RequirementToCapabilityResolver | None = None
        self._capability_index_ref = "capability-index:policy-evidence-phase4-fixture"
        self._rule_version_ref = LAYER2_S3_SUBSTRATE_ACQUISITION_SCHEMA_VERSION
        self._constraint_refs = tuple(
            dict.fromkeys(
                (
                    *expression.rule_version_refs,
                    f"repo://{_SEED}",
                    f"fixture://{source_fixture}",
                )
            )
        )
        self._voi_ref: str | None = None

    @classmethod
    def from_fixture(
        cls,
        *,
        expression: ConstructExpression,
        source_fixture: str,
    ) -> SubstrateAcquisitionLoop:
        """Build the deterministic fixture loop; live network is never used."""

        return cls(expression=expression, source_fixture=source_fixture)

    def run_to_closure(self) -> RerunClosureReceipt:
        """Run gap detection, acquisition, index delta, rerun, and terminal closure."""

        transitions: list[_Transition] = []
        binding = resolve_expression(self._expression)
        self._initial_binding_status = binding.status
        self._append_transition(
            transitions,
            AcquisitionState.GAP_DETECTED,
            detail=binding.status,
        )

        if binding.status not in {
            "blocked_construct_not_observed",
            "blocked_acquisition_required",
        }:
            return self._close(transitions, binding)

        gaps = requirement_gaps_from_compiled_specs(
            data_requirement_specs=self._data_requirement_specs(),
        )
        self._append_transition(transitions, AcquisitionState.ELIGIBILITY_CHECKED)
        plan = plan_requirement_gap_acquisition(
            run_id=self._run_id,
            requirement_gaps=gaps,
            voi_report=self._voi_report(tuple(gap.requirement_gap_id for gap in gaps)),
        )
        self._append_transition(
            transitions,
            AcquisitionState.RANKED_BY_VOI,
            detail=self._voi_ref,
        )

        task = self._open_task(plan)
        self._append_transition(
            transitions,
            AcquisitionState.TASK_OPENED,
            detail=task.route,
        )
        candidate = self._discover_source(task)
        self._append_transition(
            transitions,
            AcquisitionState.SOURCE_ACQUIRED,
            detail=candidate.connector,
        )
        contract = self._validate_source_contract(candidate)
        self._append_transition(transitions, AcquisitionState.SOURCE_CONTRACT_VALIDATED)
        self._apply_index_delta(contract)
        self._append_transition(
            transitions,
            AcquisitionState.CAPABILITY_INDEX_UPDATED,
            detail=contract.capability_index_delta_ref,
        )
        self._append_transition(transitions, AcquisitionState.RERUN_STARTED)
        rebinding = resolve_expression(
            self._expression,
            resolver=self._updated_resolver,
        )
        self._append_transition(
            transitions,
            AcquisitionState.RERUN_CONSUMED_DELTA,
            detail=rebinding.status,
        )
        return self._close(transitions, rebinding)

    def advance_to(self, state: AcquisitionState) -> None:
        """Advance the loop state without fabricating closure."""

        order = (
            AcquisitionState.GAP_DETECTED,
            AcquisitionState.ELIGIBILITY_CHECKED,
            AcquisitionState.RANKED_BY_VOI,
            AcquisitionState.TASK_OPENED,
            AcquisitionState.SOURCE_ACQUIRED,
            AcquisitionState.SOURCE_CONTRACT_VALIDATED,
            AcquisitionState.CAPABILITY_INDEX_UPDATED,
            AcquisitionState.RERUN_STARTED,
            AcquisitionState.RERUN_CONSUMED_DELTA,
        )
        for candidate in order:
            self._state = candidate
            if candidate == state:
                return
        if state in {
            AcquisitionState.CLOSED_AS_BINDING,
            AcquisitionState.CLOSED_AS_LIMITATION,
            AcquisitionState.CLOSED_AS_STILL_BLOCKED,
        }:
            self._state = state

    def assert_closed(self) -> None:
        """Raise unless a rerun consumed the index delta and changed state."""

        if self._receipt is None:
            raise RuntimeError("closure requires a rerun that consumes the index delta")
        states = {transition.state for transition in self._receipt.transitions}
        if AcquisitionState.RERUN_CONSUMED_DELTA not in states:
            raise RuntimeError("closure requires a rerun that consumes the index delta")
        if self._receipt.terminal.value not in _TERMINAL_STATES:
            raise RuntimeError("closure requires a rerun that consumes the index delta")
        if self._initial_binding_status == self._receipt.binding_status:
            raise RuntimeError("closure requires a rerun that consumes the index delta")

    def freeze_closed_case_refs(self) -> FrozenClosedCase:
        """Freeze the current case refs for ADR-0174 C2 replay."""

        return FrozenClosedCase(
            rule_version_ref=self._rule_version_ref,
            capability_index_ref=str(self._capability_index_ref),
            constraint_refs=self._constraint_refs,
            outcome=self._current_outcome(),
        )

    def replay_closed_case(self, frozen: FrozenClosedCase) -> str:
        """Replay with frozen refs; later index deltas do not alter the outcome."""

        return frozen.outcome

    @property
    def _run_id(self) -> str:
        return f"layer2-s3-{self._expression.construct}"

    def _append_transition(
        self,
        transitions: list[_Transition],
        state: AcquisitionState,
        *,
        detail: str | None = None,
    ) -> None:
        transitions.append(_Transition(state=state, detail=detail))
        self._state = state

    def _data_requirement_specs(self) -> tuple[dict[str, Any], ...]:
        return (
            {
                "requirement_id": f"s3:{self._expression.construct}",
                "claim_id": f"s3:{S3_PINNED_CASE_ID}:{self._expression.construct}",
                "required_data_families": (self._expression.construct,),
                "mandatory_facets": tuple(self._expression.facets),
                "authority_level": self._expression.authority_posture,
                "metadata": {
                    "authority_level": self._expression.authority_posture,
                    "acquisition_gap_type": "scenario_source_family",
                    "mandatory_gate_state": "none",
                    "decision_owner_ref": "team-data-acquisition",
                    "mandatory_gate_refs": ("policyos.layer2.s3.acquisition_closure",),
                },
            },
        )

    def _voi_report(self, requirement_gap_ids: tuple[str, ...]) -> dict[str, Any]:
        estimate = ValueOfInformationEstimate(
            estimate_id=f"s3-voi-{self._expression.construct.replace('_', '-')}",
            purpose=f"Ground {self._expression.construct} through fixture acquisition",
            budget_dimensions=["engineering_days", "legal_review"],
            used_by_sites=["layer2_s3_substrate_acquisition"],
            owner="team-runtime-quality",
            rule_version_ref=self._rule_version_ref,
        )
        self._voi_ref = f"voi://{estimate.estimate_id}"
        return {
            "run_id": self._run_id,
            "metadata": {"artifact_ref": self._voi_ref},
            "decisions": [
                {
                    "decision_id": self._voi_ref,
                    "recommended_action": "public_registry",
                    "expected_value": 0.91,
                    "expected_cost": 0.15,
                    "metadata": {
                        "requirement_gap_id": gap_id,
                        "acquisition_strategy": "public_registry",
                        "voi_estimate_id": estimate.estimate_id,
                    },
                }
                for gap_id in requirement_gap_ids
            ],
        }

    def _open_task(self, plan: AcquisitionPlannerReport) -> AcquisitionTaskRecord:
        record = plan.acquisition_records[0]
        route: Literal["automated", "human_fallback"] = (
            "automated"
            if record.recommended_strategy.value != "closeout_block"
            else "human_fallback"
        )
        return AcquisitionTaskRecord(
            construct_ref=self._expression.construct,
            owner=record.decision_owner_ref or record.decision_owner,
            route=route,
            ttl_days=30,
            legal_use_reviewed=True,
            expected_authority_posture=self._expression.authority_posture,
            voi_ref=self._voi_ref or record.voi_ranking_ref or "voi://missing",
        )

    def _discover_source(self, task: AcquisitionTaskRecord) -> SourceDiscoveryCandidate:
        data = self._fixture_payload()
        return SourceDiscoveryCandidate(
            construct_ref=task.construct_ref,
            connector=str(data["connector"]),
            source_fixture=self._source_fixture,
            rights_scope=str(data["rights_scope"]),
        )

    def _validate_source_contract(self, candidate: SourceDiscoveryCandidate) -> SourceContract:
        data = self._fixture_payload()
        legal_use = _mapping(data.get("legal_use_scope"))
        if not data.get("rights_scope") or not legal_use.get("claim_evidence_use_allowed"):
            raise RuntimeError("source has no usable rights / legal-use scope")
        if not _mapping(data.get("data_dictionary")):
            raise RuntimeError("source has no usable data dictionary")
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("source has no rows for construct grounding")
        if str(data.get("linkage_key_quality", "")).casefold() == "unusable":
            raise RuntimeError("source linkage-key quality is unusable")
        source_id = str(data["source_id"])
        return SourceContract(
            construct_ref=candidate.construct_ref,
            source_id=source_id,
            lineage_ref=str(data["lineage_ref"]),
            rights_scope=candidate.rights_scope,
            coverage_period=str(data["coverage_period"]),
            update_cadence=str(data["update_cadence"]),
            linkage_key_quality=str(data["linkage_key_quality"]),
            construct_validity_note=str(data["construct_validity_note"]),
            capability_index_delta_ref=(
                f"capability-index:layer2-s3-delta:{self._expression.construct}:{source_id}"
            ),
        )

    def _apply_index_delta(self, contract: SourceContract) -> None:
        capability = self._capability_from_source_contract(contract)
        self._updated_resolver = RequirementToCapabilityResolver(
            capabilities=(capability,),
            capability_index_ref=contract.capability_index_delta_ref,
        )
        self._capability_index_ref = contract.capability_index_delta_ref

    def _capability_from_source_contract(self, contract: SourceContract) -> EvidenceCapability:
        data = self._fixture_payload()
        rows = data["rows"]
        dictionary = _mapping(data["data_dictionary"])
        quality = _mapping(data.get("quality"))
        legal_use = _mapping(data.get("legal_use_scope"))
        return EvidenceCapability(
            capability_id=f"capability:{self._expression.construct}:layer2_s3_fixture",
            construct=self._expression.construct,
            modality=("fabric_data",),
            evidence_mode="observed",
            concept_spine_refs=(f"concept:{self._expression.construct}",),
            scope=CapabilityScope(
                geography=_geography_for_expression(self._expression),
                time_start=contract.coverage_period.split("/", maxsplit=1)[0],
                time_end=contract.coverage_period.split("/", maxsplit=1)[-1],
                schema_regime=str(data.get("schema_regime") or "ukraine_schema_v2"),
                population="msme",
                entity_scope=_entity_scope_for_expression(self._expression),
            ),
            identification_mode="point_identified",
            trust_tier="authoritative_high_coverage",
            quality_score=QualityScore(
                composite=float(quality.get("composite", 0.9)),
                breakdown={
                    "construct_validity": float(quality.get("construct_validity", 0.9)),
                    "schema_profile_present": float(
                        quality.get("schema_profile_present", 1.0)
                    ),
                    "rights_access": float(quality.get("rights_access", 1.0)),
                },
            ),
            source_assets=(
                CapabilitySourceAsset(
                    ref=contract.source_id,
                    source_layer="L4",
                    asset_type="fixture_json",
                    role="direct_construct_observation",
                    path=self._source_fixture,
                    row_count=len(rows),
                    fields=tuple(dictionary),
                    metadata={"connector": data["connector"]},
                ),
            ),
            proxy_validation={
                "construct_validity_status": "directly_observed",
                "note": contract.construct_validity_note,
            },
            authority_envelope=AuthorityEnvelope(
                research="admissible",
                governed_pilot="admissible",
                production="blocked_until_production_source_contract",
                authoritative_for=("governed_construct_binding",),
                may_not_use_for=("production_claim_authority",),
                authority_basis=(contract.lineage_ref, contract.rights_scope),
            ),
            lineage_refs=(contract.lineage_ref,),
            freshness_envelope=FreshnessEnvelope(
                freshness_class="fresh_for_governed_pilot",
                observed_through=contract.coverage_period.split("/", maxsplit=1)[-1],
                source_release_ref=contract.lineage_ref,
            ),
            rights_envelope=RightsEnvelope(
                access_class="government_administrative_fixture",
                public_export_allowed=str(
                    legal_use.get("public_export_allowed") or "aggregate_only"
                ),
                claim_evidence_use_allowed=True,
                restrictions=("no_row_level_public_export",),
            ),
        )

    def _close(
        self,
        transitions: list[_Transition],
        binding: _BindingResultLike,
    ) -> RerunClosureReceipt:
        if binding.status in _EXACT_STATUSES:
            terminal = AcquisitionState.CLOSED_AS_BINDING
        elif binding.status in _PROXY_LIMITED_STATUSES:
            terminal = AcquisitionState.CLOSED_AS_LIMITATION
        else:
            terminal = AcquisitionState.CLOSED_AS_STILL_BLOCKED
        self._append_transition(transitions, terminal)
        self._terminal = terminal
        receipt = RerunClosureReceipt(
            construct_ref=self._expression.construct,
            transitions=tuple(transitions),
            terminal=terminal,
            voi_ref=self._voi_ref,
            binding_status=str(binding.status),
            binding=binding.model_dump(mode="json"),
            coverage_snapshot=self._coverage_snapshot(str(binding.status)),
            frozen=FrozenClosedCase(
                rule_version_ref=self._rule_version_ref,
                capability_index_ref=str(self._capability_index_ref),
                constraint_refs=self._constraint_refs,
                outcome=terminal.value,
            ),
        )
        self._receipt = receipt
        return receipt

    def _coverage_snapshot(self, binding_status: str) -> SubstrateCoverageSnapshot:
        return SubstrateCoverageSnapshot(
            demanded=1,
            observed=1 if binding_status in _EXACT_STATUSES else 0,
            proxy_limited=1 if binding_status in _PROXY_LIMITED_STATUSES else 0,
            construct_not_observed=0 if binding_status.startswith("selected_") else 1,
            authority_posture=self._expression.authority_posture,
        )

    def _current_outcome(self) -> str:
        if self._receipt is not None:
            return self._receipt.terminal.value
        if self._terminal is not None:
            return self._terminal.value
        binding = resolve_expression(self._expression)
        return str(binding.status)

    def _fixture_payload(self) -> dict[str, Any]:
        path = self._fixture_path()
        return json.loads(path.read_text())

    def _fixture_path(self) -> Path:
        path = Path(self._source_fixture)
        if path.is_absolute():
            return path
        return _repo_root() / path


def max_admissible_posture(status: str, posture: str) -> str:
    """Return the strongest posture allowed by the binding status."""

    if status in _PROXY_LIMITED_STATUSES and posture == "production":
        return "governed"
    return posture


def is_production_claim_admissible(status: str, posture: str) -> bool:
    """Return whether a binding status can satisfy production claim authority."""

    return status in _PRODUCTION_ADMISSIBLE_STATUSES and posture == "production"


def resolve_expression(
    expr: ConstructExpression,
    *,
    source: str | None = None,
    resolver: RequirementToCapabilityResolver | None = None,
) -> CapabilityBindingResult:
    """Resolve an S3 construct expression through the existing capability spine.

    The query selector is the construct plus scoped facets. The optional
    ``source`` is retained only as lineage context for later tasks; it is not a
    scenario-family authority selector.
    """

    del source
    query = _query_for_expression(expr)
    if resolver is None:
        result = RequirementToCapabilityResolver(capabilities=()).resolve(query)
        return result.model_copy(
            update={
                "status": "blocked_acquisition_required",
                "construct_ref": expr.construct,
                "blocked_reasons": tuple(
                    dict.fromkeys(
                        (
                            "governed_capability_index_required",
                            *result.blocked_reasons,
                        )
                    )
                ),
            }
        )
    result = resolver.resolve(query)
    return result.model_copy(update={"construct_ref": expr.construct})


def _query_for_expression(expr: ConstructExpression) -> RequirementToCapabilityQuery:
    return RequirementToCapabilityQuery.model_validate(
        {
            "requirement_id": f"s3-construct-demand:{expr.construct}",
            "construct": expr.construct,
            "entity_scope": _entity_scope_for_expression(expr),
            "population_filter": _population_filter_for_expression(expr),
            "geography": _geography_for_expression(expr),
            "authority_level": _resolver_posture(expr.authority_posture),
            "claim_use": "claim_evidence_closeout",
            "required_evidence_modes": ("observed", "derived", "proxy_observational"),
            "forbidden_evidence_modes": ("simulation_only", "candidate_unverified"),
            "source_family_alias": None,
        }
    )


def _entity_scope_for_expression(expr: ConstructExpression) -> str:
    return expr.facets.get("entity_scope") or "construct"


def _population_filter_for_expression(expr: ConstructExpression) -> dict[str, str]:
    population_scope = expr.facets.get("population_scope")
    if not population_scope:
        return {}
    if "msme" in population_scope.lower():
        return {"type": "msme", "scope": population_scope}
    return {"type": population_scope}


def _geography_for_expression(expr: ConstructExpression) -> str:
    jurisdiction = expr.facets.get("jurisdiction", "global")
    if jurisdiction.lower() == "ua":
        return "UA"
    return jurisdiction.upper()


def _resolver_posture(posture: S3AuthorityPosture) -> str:
    if posture == "governed":
        return "governed_pilot"
    return posture


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _frozen_facet_primitives(repo_root: Path | None = None) -> list[str]:
    root = repo_root or _repo_root()
    return list(json.loads((root / _SEED).read_text())["facet_primitives"])


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / _SEED).exists():
            return parent
    raise FileNotFoundError(f"Could not locate repo root containing {_SEED}")


__all__ = [
    "LAYER2_S3_SUBSTRATE_ACQUISITION_SCHEMA_VERSION",
    "AcquisitionState",
    "AcquisitionTaskRecord",
    "ConstructDemandLedger",
    "ConstructExpression",
    "FrozenClosedCase",
    "RerunClosureReceipt",
    "SourceContract",
    "SourceDiscoveryCandidate",
    "SubstrateAcquisitionLoop",
    "SubstrateCoverageSnapshot",
    "is_production_claim_admissible",
    "max_admissible_posture",
    "resolve_expression",
]
