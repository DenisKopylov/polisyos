"""Requirement-to-capability resolver for Policy Evidence Capability Graph Phase 4.

The resolver is the bridge from W7.A data requirements to the Phase 1-3
capability graph contracts. It resolves by construct and scope, preserves W8.E
conflicts, keeps legacy scenario families as projections, and treats
HypothesisLedger entries as reviewer/acquisition signals rather than evidence
authority.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from polisyos.core import contracts as core_contracts
from polisyos.runtime.quality.capability_authority import (
    CapabilityBindingResult as _AuthorityCapabilityBindingResult,
)
from polisyos.runtime.quality.capability_authority import compose_capability_authority
from polisyos.runtime.quality.capability_index import (
    AcquisitionStrategy,
    AuthorityEnvelope,
    CapabilityConflictRecord,
    CapabilityIndex,
    CapabilityScope,
    EvidenceCapability,
    FailureModeNode,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)
from polisyos.runtime.quality.hypothesis_ledger import (
    LLM_SOURCE_CLASSES,
    HypothesisLedgerInput,
    deserialize_hypothesis_ledger,
)

REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION = (
    core_contracts.REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION
)
AuthorityPosture = core_contracts.AuthorityPosture
RequirementTimeWindow = core_contracts.RequirementTimeWindow
RequirementToCapabilityQuery = core_contracts.RequirementToCapabilityQuery
construct_for_legacy_family = core_contracts.construct_for_legacy_family
legacy_family_for_construct = core_contracts.legacy_family_for_construct

REQUIREMENT_TO_CAPABILITY_RESOLVER_RULE_VERSION = (
    "requirement-to-capability-resolver-v1.0"
)
DEFAULT_CAPABILITY_INDEX_REF = "capability-index:policy-evidence-phase4-governed-rows"
GOVERNED_CAPABILITY_ROWS_PATH = (
    Path("architecture/policy_design_case/layer2_s3_governed_capability_rows.json")
)

type CapabilityBindingResult = _AuthorityCapabilityBindingResult

_DIRECT_MODES = frozenset({"observed"})
_DERIVED_MODES = frozenset({"derived", "derived_administrative_with_proxy_validation"})
_PROXY_MODES = frozenset({"proxy_observational", "bounds_only"})
_CONTEXT_MODES = frozenset({"context_only", "scholarly_causal_support", "legal_threshold"})
_SIMULATION_MODES = frozenset({"simulation_only"})
_CANDIDATE_MODES = frozenset({"candidate_unverified"})
_STATUS_RANK = {
    "selected_exact": 0,
    "selected_with_conflict_marker": 1,
    "selected_derived": 2,
    "selected_proxy_with_limitation": 3,
    "selected_context_only": 4,
    "selected_simulation_only": 5,
}
_POPULATION_COMPATIBILITY: dict[str, frozenset[str]] = {
    "msme": frozenset({"msme", "registered_firms", "registered_firm", "firm"}),
    "registered_firms": frozenset({"registered_firms", "registered_firm", "firm", "msme"}),
    "registered_firm": frozenset({"registered_firms", "registered_firm", "firm", "msme"}),
    "firm": frozenset({"registered_firms", "registered_firm", "firm", "msme"}),
    "displacement_affected": frozenset(
        {"displacement_affected", "displacement_affected_regions", "region"}
    ),
    "displacement_affected_regions": frozenset(
        {"displacement_affected", "displacement_affected_regions", "region"}
    ),
    "region": frozenset({"displacement_affected", "displacement_affected_regions", "region"}),
}


class _CandidateEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: EvidenceCapability
    result: CapabilityBindingResult | None = None
    rejected: dict[str, Any] | None = None


class RequirementToCapabilityResolver:
    """Resolve semantic evidence requirements against a capability index slice."""

    def __init__(
        self,
        *,
        capabilities: Sequence[EvidenceCapability | Mapping[str, Any]],
        failure_modes: Sequence[FailureModeNode | Mapping[str, Any]] = (),
        acquisition_strategies: Sequence[AcquisitionStrategy | Mapping[str, Any]] = (),
        conflicts: Sequence[CapabilityConflictRecord | Mapping[str, Any]] = (),
        capability_index_ref: str = DEFAULT_CAPABILITY_INDEX_REF,
    ) -> None:
        self.capabilities = tuple(_capability_model(item) for item in capabilities)
        self.failure_modes = tuple(_failure_mode_model(item) for item in failure_modes)
        self.acquisition_strategies = tuple(
            _acquisition_strategy_model(item) for item in acquisition_strategies
        )
        self.conflicts = tuple(_conflict_model(item) for item in conflicts)
        self.capability_index_ref = _required_text(capability_index_ref)

    @classmethod
    def default_fixture(cls) -> RequirementToCapabilityResolver:
        """Block legacy runtime fixture construction."""

        raise RuntimeError(
            "A governed capability index is required; load persisted governed capability rows."
        )

    @classmethod
    def governed_fixture(cls, repo_root: Path | None = None) -> RequirementToCapabilityResolver:
        """Load governed capability rows from the persisted Policy Design Case artifact."""

        root = _repo_root() if repo_root is None else Path(repo_root)
        payload = json.loads(
            (root / GOVERNED_CAPABILITY_ROWS_PATH).read_text(encoding="utf-8")
        )
        return cls(
            capabilities=tuple(
                _capability_payload_from_json(row)
                for row in payload.get("capabilities") or ()
            ),
            failure_modes=tuple(payload.get("failure_modes") or ()),
            acquisition_strategies=tuple(payload.get("acquisition_strategies") or ()),
            conflicts=tuple(payload.get("conflicts") or ()),
            capability_index_ref=str(
                payload.get("capability_index_ref") or DEFAULT_CAPABILITY_INDEX_REF
            ),
        )

    @classmethod
    def from_capability_index(
        cls,
        capability_index: CapabilityIndex | Mapping[str, Any],
    ) -> RequirementToCapabilityResolver:
        """Build a resolver from an in-memory capability index payload."""

        model = (
            capability_index
            if isinstance(capability_index, CapabilityIndex)
            else CapabilityIndex.model_validate(capability_index)
        )
        return cls(
            capabilities=model.capabilities,
            failure_modes=model.failure_modes,
            acquisition_strategies=model.acquisition_strategies,
            conflicts=model.conflicts,
            capability_index_ref=model.release_ref,
        )

    @classmethod
    def from_duckdb(cls, path: str | Path) -> RequirementToCapabilityResolver:
        """Load the resolver slice from a Phase 1 capability-index DuckDB."""

        import duckdb

        db_path = Path(path)
        with duckdb.connect(str(db_path), read_only=True) as con:
            capabilities = [
                EvidenceCapability.model_validate_json(row[0])
                for row in con.execute(
                    "SELECT capability_json FROM capabilities ORDER BY capability_id"
                ).fetchall()
            ]
            conflicts = [
                CapabilityConflictRecord.model_validate_json(row[0])
                for row in con.execute(
                    "SELECT conflict_json FROM conflicts ORDER BY conflict_id"
                ).fetchall()
            ]
            failures = [
                FailureModeNode.model_validate_json(row[0])
                for row in con.execute(
                    "SELECT failure_json FROM failure_modes ORDER BY failure_id"
                ).fetchall()
            ]
            strategies = [
                AcquisitionStrategy.model_validate_json(row[0])
                for row in con.execute(
                    "SELECT strategy_json FROM acquisition_strategies ORDER BY strategy_id"
                ).fetchall()
            ]
            release_row = con.execute(
                "SELECT value_json FROM index_metadata WHERE key = 'release_ref'"
            ).fetchone()
        return cls(
            capabilities=capabilities,
            failure_modes=failures,
            acquisition_strategies=strategies,
            conflicts=conflicts,
            capability_index_ref=(
                json.loads(release_row[0]) if release_row else f"capability-index:{db_path.name}"
            ),
        )

    def resolve(
        self,
        query: RequirementToCapabilityQuery | Mapping[str, Any],
        *,
        hypothesis_ledger: HypothesisLedgerInput | None = None,
    ) -> CapabilityBindingResult:
        """Resolve one query into a typed selected or blocked binding result."""

        model = (
            query
            if isinstance(query, RequirementToCapabilityQuery)
            else RequirementToCapabilityQuery.model_validate(query)
        )
        reviewer_queue = _reviewer_queue_for_query(
            model,
            hypothesis_ledger=hypothesis_ledger,
        )
        ledger_rejections = _ledger_rejections(reviewer_queue)
        evaluations = self._evaluate_candidates(model)
        selected = _select_best_binding(evaluations)
        rejected = _rejected_alternatives(
            evaluations,
            selected_capability_ref=selected.selected_capability_ref if selected else None,
            ledger_rejections=ledger_rejections,
        )
        strategies = self._acquisition_strategies_for(model)

        if selected is not None:
            return self._with_resolver_fields(
                selected,
                model,
                rejected_alternatives=rejected,
                acquisition_strategies=strategies,
                reviewer_queue=reviewer_queue,
            )

        blocked = self._blocked_result_for(model, evaluations=evaluations, strategies=strategies)
        return self._with_resolver_fields(
            blocked,
            model,
            rejected_alternatives=rejected,
            acquisition_strategies=strategies,
            reviewer_queue=reviewer_queue,
        )

    def _evaluate_candidates(
        self,
        query: RequirementToCapabilityQuery,
    ) -> tuple[_CandidateEvaluation, ...]:
        construct = _bare_construct(query.construct)
        rows: list[_CandidateEvaluation] = []
        for capability in self.capabilities:
            if _bare_construct(capability.construct_id) != construct:
                continue
            rejection = _candidate_rejection(query, capability)
            if rejection is not None:
                rows.append(_CandidateEvaluation(capability=capability, rejected=rejection))
                continue
            conflicts = self._conflicts_for(query, capability)
            result = compose_capability_authority(
                capability,
                posture=query.authority_level,
                claim_use=query.claim_use,
                requirement_id=query.requirement_id,
                conflict_markers=conflicts,
                required_schema_regime=query.required_schema_regime,
                min_sample_size=query.min_sample_size,
            )
            rows.append(_CandidateEvaluation(capability=capability, result=result))
        return tuple(rows)

    def _conflicts_for(
        self,
        query: RequirementToCapabilityQuery,
        capability: EvidenceCapability,
    ) -> tuple[dict[str, Any], ...]:
        refs = {capability.capability_id}
        return tuple(
            conflict.model_dump(mode="json")
            for conflict in self.conflicts
            if _bare_construct(conflict.construct_id) == _bare_construct(query.construct)
            and (
                not conflict.capability_refs
                or refs.intersection(set(conflict.capability_refs))
            )
            and _geography_matches(query.geography, conflict.geography)
        )

    def _acquisition_strategies_for(
        self,
        query: RequirementToCapabilityQuery,
    ) -> tuple[dict[str, Any], ...]:
        construct = _bare_construct(query.construct)
        refs = {
            ref
            for node in self.failure_modes
            if _bare_construct(node.construct_id) == construct
            and _geography_matches(query.geography, node.geography)
            for ref in node.acquisition_strategy_refs
        }
        strategies = [
            strategy
            for strategy in self.acquisition_strategies
            if _bare_construct(strategy.target_construct) == construct
            and (not refs or strategy.strategy_id in refs)
        ]
        return tuple(strategy.model_dump(mode="json") for strategy in strategies)

    def _blocked_result_for(
        self,
        query: RequirementToCapabilityQuery,
        *,
        evaluations: Sequence[_CandidateEvaluation],
        strategies: Sequence[Mapping[str, Any]],
    ) -> CapabilityBindingResult:
        placeholder = _placeholder_capability(query)
        if strategies:
            return compose_capability_authority(
                placeholder,
                posture=query.authority_level,
                claim_use=query.claim_use,
                requirement_id=query.requirement_id,
                acquisition_required=True,
            )
        if evaluations:
            blocked_results = [
                item.result
                for item in evaluations
                if item.result is not None and item.result.status.startswith("blocked_")
            ]
            if blocked_results:
                return sorted(blocked_results, key=_blocked_result_rank)[0]
            return compose_capability_authority(
                placeholder,
                posture=query.authority_level,
                claim_use=query.claim_use,
                requirement_id=query.requirement_id,
                acquisition_required=True,
            )
        return compose_capability_authority(
            placeholder,
            posture=query.authority_level,
            claim_use=query.claim_use,
            requirement_id=query.requirement_id,
            construct_observed=False,
        )

    def _with_resolver_fields(
        self,
        result: CapabilityBindingResult,
        query: RequirementToCapabilityQuery,
        *,
        rejected_alternatives: Sequence[Mapping[str, Any]],
        acquisition_strategies: Sequence[Mapping[str, Any]],
        reviewer_queue: Sequence[Mapping[str, Any]],
    ) -> CapabilityBindingResult:
        blocked_reasons = result.blocked_reasons
        if result.status.startswith("blocked_") and not blocked_reasons:
            blocked_reasons = (_reason_from_status(result.status),)
        return result.model_copy(
            update={
                "rule_version_ref": REQUIREMENT_TO_CAPABILITY_RESOLVER_RULE_VERSION,
                "requirement_id": query.requirement_id,
                "construct_ref": f"construct:{_bare_construct(query.construct)}",
                "capability_index_ref": self.capability_index_ref,
                "rejected_alternatives": tuple(dict(item) for item in rejected_alternatives),
                "acquisition_strategies": tuple(
                    dict(item) for item in acquisition_strategies
                ),
                "reviewer_queue": tuple(dict(item) for item in reviewer_queue),
                "blocked_reasons": tuple(blocked_reasons),
            }
        )


def _select_best_binding(
    evaluations: Sequence[_CandidateEvaluation],
) -> CapabilityBindingResult | None:
    selected = [
        item.result
        for item in evaluations
        if item.result is not None and item.result.status.startswith("selected_")
    ]
    if not selected:
        return None
    return sorted(selected, key=_result_rank)[0]


def _result_rank(result: CapabilityBindingResult) -> tuple[int, int, str]:
    return (
        _STATUS_RANK.get(result.status, 99),
        _evidence_mode_rank_from_result(result),
        result.selected_capability_ref or "",
    )


def _blocked_result_rank(result: CapabilityBindingResult) -> tuple[int, str]:
    priority = {
        "blocked_acquisition_required": 0,
        "blocked_authority_boundary": 1,
        "blocked_rights_boundary": 2,
        "blocked_construct_not_observed": 3,
    }
    return (priority.get(result.status, 99), result.selected_capability_ref or "")


def _evidence_mode_rank_from_result(result: CapabilityBindingResult) -> int:
    reasons = set(result.binding_reasons)
    if "derived_capability_selected" in reasons:
        return 1
    if result.status == "selected_proxy_with_limitation":
        return 2
    if result.status == "selected_context_only":
        return 3
    if result.status == "selected_simulation_only":
        return 4
    return 0


def _candidate_rejection(
    query: RequirementToCapabilityQuery,
    capability: EvidenceCapability,
) -> dict[str, Any] | None:
    capability_ref = capability.capability_id
    if query.required_modalities and not set(query.required_modalities).intersection(
        set(capability.modality)
    ):
        return _rejection(
            capability_ref,
            "required_modality_missing",
            "hard",
            capability=capability,
        )
    if any(
        _mode_matches(capability.evidence_mode, mode)
        for mode in query.forbidden_evidence_modes
    ):
        reason = (
            "llm_candidate_unverified"
            if capability.evidence_mode == "candidate_unverified"
            else "evidence_mode_forbidden"
        )
        return _rejection(capability_ref, reason, "hard", capability=capability)
    if query.required_evidence_modes and not any(
        _mode_matches(capability.evidence_mode, mode)
        for mode in query.required_evidence_modes
    ):
        return _rejection(
            capability_ref,
            "required_evidence_mode_missing",
            "hard",
            capability=capability,
        )
    if not _population_matches(query.population_filter, capability.scope.population):
        return _rejection(
            capability_ref,
            "population_filter_mismatch",
            "hard",
            capability=capability,
        )
    if not _geography_matches(query.geography, capability.scope.geography):
        return _rejection(capability_ref, "geography_mismatch", "hard", capability=capability)
    if not _entity_scope_matches(query.entity_scope, capability.scope.entity_scope):
        return _rejection(
            capability_ref,
            "entity_scope_mismatch",
            "hard",
            capability=capability,
        )
    if not _time_window_matches(query.time_window, capability.scope):
        return _rejection(
            capability_ref,
            "time_window_outside_claim",
            "hard",
            capability=capability,
        )
    return None


def _rejected_alternatives(
    evaluations: Sequence[_CandidateEvaluation],
    *,
    selected_capability_ref: str | None,
    ledger_rejections: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for item in evaluations:
        capability_ref = item.capability.capability_id
        if capability_ref == selected_capability_ref:
            continue
        if item.rejected is not None:
            rows.append(dict(item.rejected))
            continue
        if item.result is not None and item.result.status.startswith("blocked_"):
            rows.append(
                _rejection(
                    capability_ref,
                    _reason_from_status(item.result.status),
                    "hard",
                    capability=item.capability,
                )
            )
            continue
        rows.append(
            _rejection(
                capability_ref,
                "lower_ranked_evidence_mode",
                "soft",
                capability=item.capability,
            )
        )
    rows.extend(dict(item) for item in ledger_rejections)
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped.setdefault(str(row["capability_ref"]), row)
    return tuple(deduped.values())


def _reviewer_queue_for_query(
    query: RequirementToCapabilityQuery,
    *,
    hypothesis_ledger: HypothesisLedgerInput | None,
) -> tuple[dict[str, Any], ...]:
    if hypothesis_ledger is None:
        return ()
    ledger = deserialize_hypothesis_ledger(hypothesis_ledger)
    rows: list[dict[str, Any]] = []
    for entry in ledger.entries:
        if entry.source_class not in LLM_SOURCE_CLASSES:
            continue
        if entry.candidate_kind not in {"candidate_requirement", "candidate_capability"}:
            continue
        content_construct = _optional_text(entry.content.get("construct"))
        if content_construct and _bare_construct(content_construct) != query.construct:
            continue
        rows.append(
            {
                "candidate_id": entry.candidate_id,
                "candidate_ref": entry.candidate_ref,
                "candidate_kind": entry.candidate_kind,
                "source_class": entry.source_class,
                "admission_state": entry.admission_state,
                "construct_ref": f"construct:{query.construct}",
                "queue_reason": "llm_candidate_requires_human_reviewer_and_producer_backing",
                "may_influence": ["acquisition_planning", "reviewer_queue"],
                "may_not_satisfy": ["selected_exact", "selected_derived"],
            }
        )
    return tuple(rows)


def _ledger_rejections(
    reviewer_queue: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "capability_ref": str(row.get("candidate_ref")),
            "rejection_reason": "llm_candidate_unverified",
            "rejection_severity": "hard",
            "construct_ref": row.get("construct_ref"),
            "reviewer_queue_ref": row.get("candidate_id"),
        }
        for row in reviewer_queue
        if row.get("candidate_ref")
    )


def _rejection(
    capability_ref: str,
    reason: str,
    severity: str,
    *,
    capability: EvidenceCapability,
) -> dict[str, Any]:
    return {
        "capability_ref": capability_ref,
        "rejection_reason": reason,
        "rejection_severity": severity,
        "construct_ref": f"construct:{_bare_construct(capability.construct_id)}",
        "evidence_mode": capability.evidence_mode,
    }


def _reason_from_status(status: str) -> str:
    return status.removeprefix("blocked_") or "capability_not_selected"


def _mode_matches(actual: str, requested: str) -> bool:
    actual = _slug(actual)
    requested = _slug(requested)
    if actual == requested:
        return True
    if requested == "derived" and actual in _DERIVED_MODES:
        return True
    if requested == "proxy_observational" and actual in _PROXY_MODES:
        return True
    if requested == "context_only" and actual in _CONTEXT_MODES:
        return True
    if requested == "simulation_only" and actual in _SIMULATION_MODES:
        return True
    if requested == "candidate_unverified" and actual in _CANDIDATE_MODES:
        return True
    return requested == "observed" and actual in _DIRECT_MODES


def _geography_matches(query_geography: str, capability_geography: str) -> bool:
    query = _slug(query_geography)
    capability = _slug(capability_geography)
    return query == capability or capability in {"global", "multi_context"}


def _entity_scope_matches(query_scope: str, capability_scope: str) -> bool:
    query = _slug(query_scope)
    capability = _slug(capability_scope)
    if query in {"construct", "unspecified"}:
        return True
    if query == capability:
        return True
    query_parts = set(query.split("_or_"))
    capability_parts = set(capability.split("_or_"))
    return bool(query_parts.intersection(capability_parts))


def _time_window_matches(
    query_window: RequirementTimeWindow,
    capability_scope: CapabilityScope,
) -> bool:
    if (
        query_window.start
        and capability_scope.time_end
        and capability_scope.time_end < query_window.start
    ):
        return False
    return not (
        query_window.end
        and capability_scope.time_start
        and capability_scope.time_start > query_window.end
    )


def _population_matches(
    population_filter: Mapping[str, Any],
    capability_population: str | None,
) -> bool:
    requested = _population_filter_values(population_filter)
    if not requested:
        return True
    candidate = _canonical_population(capability_population)
    if candidate is None:
        return True
    return any(
        candidate == item
        or candidate in _POPULATION_COMPATIBILITY.get(item, frozenset({item}))
        or item in _POPULATION_COMPATIBILITY.get(candidate, frozenset({candidate}))
        for item in requested
    )


def _population_filter_values(population_filter: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in (
        "type",
        "population",
        "target_population",
        "population_type",
        "segment",
        "segments",
        "groups",
    ):
        for item in _text_tuple(population_filter.get(key)):
            canonical = _canonical_population(item)
            if canonical and canonical not in values:
                values.append(canonical)
    return tuple(values)


def _canonical_population(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    slug = _slug(text)
    return {
        "msmes": "msme",
        "micro_small_and_medium_enterprises": "msme",
        "small_and_medium_enterprises": "msme",
        "smes": "msme",
        "firms": "firm",
        "regions": "region",
        "displacement_affected_region": "displacement_affected_regions",
    }.get(slug, slug)


def _placeholder_capability(query: RequirementToCapabilityQuery) -> EvidenceCapability:
    return EvidenceCapability(
        capability_id=f"capability:placeholder:{query.construct}:{_slug(query.geography)}",
        construct=query.construct,
        modality=("fabric_data",),
        evidence_mode="context_only",
        concept_spine_refs=(f"concept:{query.construct}",),
        scope=CapabilityScope(
            geography=query.geography,
            entity_scope=query.entity_scope,
            population=_population_label(query.population_filter),
        ),
        identification_mode="context_only",
        trust_tier="context_only",
        quality_score=QualityScore(composite=0.2, breakdown={"construct_validity": 0.2}),
        source_assets=(),
        authority_envelope=AuthorityEnvelope(
            research="blocked_construct_not_observed",
            governed_pilot="blocked_construct_not_observed",
            production="blocked_construct_not_observed",
            may_not_use_for=("claim_evidence_closeout", "production_claim_evidence"),
        ),
        freshness_envelope=FreshnessEnvelope(freshness_class="resolver_placeholder"),
        rights_envelope=RightsEnvelope(access_class="none", claim_evidence_use_allowed=False),
    )


def _capability_model(value: EvidenceCapability | Mapping[str, Any]) -> EvidenceCapability:
    if isinstance(value, EvidenceCapability):
        return value
    return EvidenceCapability.model_validate(value)


def _capability_payload_from_json(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    if "source_assets" in payload:
        payload["source_assets"] = tuple(payload["source_assets"] or ())
    return payload


def _failure_mode_model(value: FailureModeNode | Mapping[str, Any]) -> FailureModeNode:
    if isinstance(value, FailureModeNode):
        return value
    return FailureModeNode.model_validate(value)


def _acquisition_strategy_model(
    value: AcquisitionStrategy | Mapping[str, Any],
) -> AcquisitionStrategy:
    if isinstance(value, AcquisitionStrategy):
        return value
    return AcquisitionStrategy.model_validate(value)


def _conflict_model(
    value: CapabilityConflictRecord | Mapping[str, Any],
) -> CapabilityConflictRecord:
    if isinstance(value, CapabilityConflictRecord):
        return value
    return CapabilityConflictRecord.model_validate(value)


def _population_label(population_filter: Mapping[str, Any]) -> str:
    return _optional_text(population_filter.get("type")) or "population"


def _bare_construct(value: object) -> str:
    text = _required_text(value)
    return _slug(text.removeprefix("construct:"))


def _slug(value: object) -> str:
    return _required_text(value).strip().casefold().replace("-", "_").replace(" ", "_")


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("required text is missing")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, Iterable):
        values = value
    else:
        values = (value,)
    rows: list[str] = []
    for item in values:
        text = _optional_text(item)
        if text and text not in rows:
            rows.append(text)
    return tuple(rows)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


__all__ = [
    "DEFAULT_CAPABILITY_INDEX_REF",
    "REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION",
    "REQUIREMENT_TO_CAPABILITY_RESOLVER_RULE_VERSION",
    "CapabilityBindingResult",
    "RequirementTimeWindow",
    "RequirementToCapabilityQuery",
    "RequirementToCapabilityResolver",
    "construct_for_legacy_family",
    "legacy_family_for_construct",
]
