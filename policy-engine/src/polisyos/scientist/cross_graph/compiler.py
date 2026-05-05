"""Compiler and config for turning policy bundles into cross-graph evidence profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.data_forge.read_api.academic import ParameterCandidate, SKGQuery
from polisyos.data_forge.read_api.catalog import DatasetRegistry, resolve_proxy
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import (
    BridgeRelation,
    CanonicalConcept,
    ConceptBridge,
    CrossGraphDiagnostic,
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    CrossGraphSourceRefs,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
    build_evidence_need_id,
)
from polisyos.ir.analytics.literature import LiteratureCausalPrior
from polisyos.ir.analytics.transportability import TransportMode
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.lex.api import evaluate_transport_constraints
from polisyos.lex.errors import LexError
from polisyos.lex.legal_evaluation.transport_constraints import LegalConstraintSet
from polisyos.scientist.cross_graph.alignment import (
    alignment_tokens,
    concept_tokens,
    diagnostic_key,
)
from polisyos.scientist.cross_graph.gatherers.academic import AcademicGatherer
from polisyos.scientist.evidence.sources import build_path_source_status, update_source_status

_CROSS_GRAPH_QUERY_ERRORS = (
    duckdb.Error,
    LexError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CROSS_GRAPH_INIT_ERRORS = (
    duckdb.Error,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CROSS_GRAPH_DISTANCE_ERRORS = (
    ArithmeticError,
    AttributeError,
    LookupError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CROSS_GRAPH_MODEL_ERRORS = (TypeError, ValueError, ValidationError)


class CrossGraphEvidenceConfig(BaseModel):
    """Runtime configuration describing which evidence backends, ontology, and context the compiler should use."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    jurisdiction: str | None = None
    policy_domain: str | None = None
    country_code: str | None = None
    target_year: int | None = None
    academic_db_path: str | None = None
    academic_index_dir: str | None = None
    datasets_db_path: str | None = None
    legal_db_path: str | None = None
    backlog_output_path: str | None = None
    benchmark_suite_path: str | None = None
    benchmark_report_path: str | None = None
    academic_demand_backlog_path: str | None = None
    ontology: list[CanonicalConcept] = Field(default_factory=list)


@dataclass(frozen=True)
class _LegalResult:
    status: LegalStatus
    confidence: float
    requires_expert_review: bool
    blocking_reasons: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    diagnostics: tuple[CrossGraphDiagnostic, ...]


@dataclass(frozen=True)
class _DatasetResult:
    status: ObservabilityStatus
    confidence: float
    requires_expert_review: bool
    recommended_actions: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    diagnostics: tuple[CrossGraphDiagnostic, ...]


@dataclass(frozen=True)
class _AcademicResult:
    status: EvidenceStatus
    confidence: float
    requires_expert_review: bool
    recommended_actions: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    diagnostics: tuple[CrossGraphDiagnostic, ...]
    best_context_distance: float | None = None
    transport_confidence: float | None = None
    transport_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class _TransportResult:
    status: TransportStatus
    mode: TransportMode
    confidence: float
    requires_expert_review: bool
    blocking_reasons: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    diagnostics: tuple[CrossGraphDiagnostic, ...]


class CrossGraphEvidenceCompiler:
    """Compile a Trinity bundle into evidence-need assessments across legal, dataset, and academic channels."""

    def __init__(self, config: CrossGraphEvidenceConfig) -> None:
        self.config = config

    def compile(
        self,
        bundle: TrinityBundle,
        *,
        target_context: ContextProfile | None = None,
        causal_graph: CausalGraphModel | None = None,
        literature_prior: LiteratureCausalPrior | None = None,
        literature_prior_ref: str | None = None,
    ) -> CrossGraphEvidenceProfile:
        policy_domain = self.config.policy_domain or bundle.problem_frame.domain.value
        jurisdiction = (
            self.config.jurisdiction or self.config.country_code or _country_code(target_context)
        )
        target_year = self.config.target_year or _target_year(target_context)

        needs = extract_evidence_needs(
            bundle,
            target_context=target_context,
            causal_graph=causal_graph,
            jurisdiction=jurisdiction,
            policy_domain=policy_domain,
            country_code=self.config.country_code or _country_code(target_context),
            target_year=target_year,
        )

        diagnostics: list[CrossGraphDiagnostic] = []
        diagnostic_keys: set[tuple[str, str, str | None, str, str]] = set()
        bridges: list[ConceptBridge] = []
        used_concepts: dict[str, CanonicalConcept] = {}
        assessments: list[EvidenceNeedAssessment] = []

        academic_query, academic_status = _build_academic_query(self.config)
        dataset_registry, dataset_status = _build_dataset_registry(self.config)
        legal_status = _build_legal_source_status(self.config)
        academic_gatherer = AcademicGatherer()
        legal_adapter = _LegalGraphAdapter(
            config=self.config,
            bundle=bundle,
            causal_graph=causal_graph,
            jurisdiction=jurisdiction,
            policy_domain=policy_domain,
        )

        try:
            for need in needs:
                resolved_concepts, need_bridges, need_diagnostics = _resolve_ontology_for_need(
                    need,
                    ontology=self.config.ontology,
                )
                _append_unique_diagnostics(
                    diagnostics,
                    diagnostic_keys,
                    need_diagnostics,
                )
                bridges.extend(need_bridges)
                for concept in resolved_concepts:
                    used_concepts[concept.concept_id] = concept

                legal_result = legal_adapter.assess_need(need)
                dataset_result = _assess_dataset_need(
                    need,
                    concepts=resolved_concepts,
                    registry=dataset_registry,
                    academic_query=academic_query,
                    country_code=self.config.country_code or _country_code(target_context),
                    target_year=target_year,
                )
                academic_result = _academic_result_from_gatherer(
                    academic_gatherer.assess(
                        need,
                        concepts=resolved_concepts,
                        context={
                            "academic_query": academic_query,
                            "target_context": target_context,
                            "_assess_academic_need": _assess_academic_need,
                            "literature_prior": literature_prior,
                            "literature_prior_ref": literature_prior_ref,
                            "environment_audit": (
                                literature_prior.environment_audit
                                if literature_prior is not None
                                else None
                            ),
                            "environment_audit_summary": _environment_audit_summary(
                                literature_prior
                            ),
                        },
                    )
                )
                transport_result = _compose_transportability_view(
                    need,
                    target_context=target_context,
                    observability_status=dataset_result.status,
                    evidence_result=academic_result,
                )

                need_diagnostic_list = [
                    *need_diagnostics,
                    *legal_result.diagnostics,
                    *dataset_result.diagnostics,
                    *academic_result.diagnostics,
                    *transport_result.diagnostics,
                ]
                _append_unique_diagnostics(
                    diagnostics,
                    diagnostic_keys,
                    need_diagnostic_list,
                )

                recommended_actions = _dedupe_preserve(
                    [
                        *legal_result.recommended_actions,
                        *dataset_result.recommended_actions,
                        *academic_result.recommended_actions,
                        *transport_result.recommended_actions,
                    ]
                )
                blocking_reasons = _dedupe_preserve(
                    [
                        *legal_result.blocking_reasons,
                        *transport_result.blocking_reasons,
                    ]
                )
                provenance_refs = _dedupe_preserve(
                    [
                        *[bridge.src_id for bridge in need_bridges],
                        *legal_result.provenance_refs,
                        *dataset_result.provenance_refs,
                        *academic_result.provenance_refs,
                    ]
                )
                requires_expert_review = any(
                    (
                        legal_result.requires_expert_review,
                        dataset_result.requires_expert_review,
                        academic_result.requires_expert_review,
                        transport_result.requires_expert_review,
                    )
                )
                confidence = _aggregate_confidence(
                    legal_result.status,
                    dataset_result.status,
                    academic_result.status,
                    transport_result.status,
                    requires_expert_review=requires_expert_review,
                )

                assessments.append(
                    EvidenceNeedAssessment(
                        need=need,
                        resolved_concept_ids=[concept.concept_id for concept in resolved_concepts],
                        legal_status=legal_result.status,
                        observability_status=dataset_result.status,
                        evidence_status=academic_result.status,
                        transport_status=transport_result.status,
                        transport_mode=transport_result.mode,
                        confidence=confidence,
                        requires_expert_review=requires_expert_review,
                        blocking_reasons=blocking_reasons,
                        recommended_actions=recommended_actions,
                        provenance_refs=provenance_refs,
                        diagnostics=need_diagnostic_list,
                    )
                )
        finally:
            if academic_query is not None:
                close = getattr(academic_query, "close", None)
                if callable(close):
                    close()

        assessments.sort(key=lambda item: item.need.need_id)
        summary = _build_summary(assessments)
        source_statuses = {
            EvidenceSourceKind.ACADEMIC.value: academic_status,
            EvidenceSourceKind.DATASETS.value: dataset_status,
            EvidenceSourceKind.LEGAL.value: legal_adapter.source_status(legal_status),
        }
        return CrossGraphEvidenceProfile(
            summary=summary,
            needs=assessments,
            diagnostics=_dedupe_diagnostics(
                [
                    *diagnostics,
                    *_literature_prior_diagnostics(
                        literature_prior=literature_prior,
                        literature_prior_ref=literature_prior_ref,
                    ),
                ]
            ),
            ontology_snapshot=[used_concepts[key] for key in sorted(used_concepts)],
            bridges=_dedupe_bridges(bridges),
            source_refs=CrossGraphSourceRefs(
                academic_db_path=self.config.academic_db_path,
                academic_index_dir=self.config.academic_index_dir,
                datasets_db_path=self.config.datasets_db_path,
                legal_db_path=self.config.legal_db_path,
            ),
            source_statuses=source_statuses,
            benchmark_summary={},
            target_context=target_context,
            notes=[
                *_profile_notes(self.config),
                *_literature_prior_notes(
                    literature_prior=literature_prior,
                    literature_prior_ref=literature_prior_ref,
                ),
            ],
        )


def extract_evidence_needs(
    bundle: TrinityBundle,
    *,
    target_context: ContextProfile | None = None,
    causal_graph: CausalGraphModel | None = None,
    jurisdiction: str | None = None,
    policy_domain: str | None = None,
    country_code: str | None = None,
    target_year: int | None = None,
) -> list[EvidenceNeed]:
    """Derive the evidence needs implied by a policy bundle, causal graph, and target context."""
    problem_frame = bundle.problem_frame
    policy_spec = bundle.policy_spec
    resolved_policy_domain = policy_domain or problem_frame.domain.value
    time_window = str(target_year) if target_year is not None else _time_window(target_context)
    target_context_id = target_context.context_id if target_context else None

    kpi_by_id = {kpi.kpi_id: kpi for kpi in problem_frame.kpis}
    parameter_need_keys: set[tuple[str | None, str | None, str | None]] = set()
    needs: list[EvidenceNeed] = []

    for index, objective in enumerate(problem_frame.objectives):
        needs.append(
            _metric_need(
                need_type=EvidenceNeedType.OBJECTIVE_METRIC,
                source_path=f"problem_frame.objectives[{index}]",
                metric_id=objective.metric_id,
                jurisdiction=jurisdiction,
                policy_domain=resolved_policy_domain,
                country_code=country_code,
                time_window=time_window,
                target_context_id=target_context_id,
            )
        )

    for index, kpi in enumerate(problem_frame.kpis):
        needs.append(
            _metric_need(
                need_type=EvidenceNeedType.KPI_METRIC,
                source_path=f"problem_frame.kpis[{index}]",
                metric_id=kpi.metric_id,
                jurisdiction=jurisdiction,
                policy_domain=resolved_policy_domain,
                country_code=country_code,
                time_window=time_window,
                target_context_id=target_context_id,
                kpi_id=kpi.kpi_id,
            )
        )

    for index, criterion in enumerate(problem_frame.success_criteria):
        kpi = kpi_by_id.get(criterion.kpi_id)
        needs.append(
            _metric_need(
                need_type=EvidenceNeedType.SUCCESS_CRITERION_METRIC,
                source_path=f"problem_frame.success_criteria[{index}]",
                metric_id=(kpi.metric_id if kpi is not None else None),
                jurisdiction=jurisdiction,
                policy_domain=resolved_policy_domain,
                country_code=country_code,
                time_window=time_window,
                target_context_id=target_context_id,
                kpi_id=criterion.kpi_id,
                criterion_id=criterion.criterion_id,
            )
        )

    for group_name, constraints in (
        ("hard_constraints", problem_frame.hard_constraints),
        ("soft_constraints", problem_frame.soft_constraints),
    ):
        for index, constraint in enumerate(constraints):
            needs.append(
                _constraint_need(
                    source_path=f"problem_frame.{group_name}[{index}]",
                    constraint=constraint,
                    jurisdiction=jurisdiction,
                    policy_domain=resolved_policy_domain,
                    country_code=country_code,
                    time_window=time_window,
                    target_context_id=target_context_id,
                )
            )

    for index, intervention in enumerate(policy_spec.interventions):
        needs.append(
            _intervention_need(
                need_type=EvidenceNeedType.MECHANISM_NEED,
                source_path=f"policy_spec.interventions[{index}]",
                intervention=intervention,
                jurisdiction=jurisdiction,
                policy_domain=resolved_policy_domain,
                country_code=country_code,
                time_window=time_window,
                target_context_id=target_context_id,
            )
        )
        needs.append(
            _intervention_need(
                need_type=EvidenceNeedType.LEGAL_APPLICABILITY_NEED,
                source_path=f"policy_spec.interventions[{index}]",
                intervention=intervention,
                jurisdiction=jurisdiction,
                policy_domain=resolved_policy_domain,
                country_code=country_code,
                time_window=time_window,
                target_context_id=target_context_id,
            )
        )
        for param_key in sorted(intervention.params):
            unique_key = (intervention.intervention_id, param_key, param_key)
            if unique_key in parameter_need_keys:
                continue
            parameter_need_keys.add(unique_key)
            needs.append(
                _parameter_need(
                    source_path=(f"policy_spec.interventions[{index}].params.{param_key}"),
                    parameter_name=param_key,
                    param_path=param_key,
                    intervention_id=intervention.intervention_id,
                    jurisdiction=jurisdiction,
                    policy_domain=resolved_policy_domain,
                    country_code=country_code,
                    time_window=time_window,
                    target_context_id=target_context_id,
                )
            )

    for index, parameter in enumerate(policy_spec.parameters):
        parameter_name = _parameter_name(parameter)
        unique_key = (parameter.intervention_id, parameter_name, parameter.param_path)
        if unique_key in parameter_need_keys:
            continue
        parameter_need_keys.add(unique_key)
        needs.append(
            _parameter_need(
                source_path=f"policy_spec.parameters[{index}]",
                parameter_name=parameter_name,
                param_path=parameter.param_path,
                intervention_id=parameter.intervention_id,
                jurisdiction=jurisdiction,
                policy_domain=resolved_policy_domain,
                country_code=country_code,
                time_window=time_window,
                target_context_id=target_context_id,
            )
        )

    if causal_graph is not None:
        for index, edge in enumerate(causal_graph.edges):
            needs.append(
                _causal_edge_need(
                    source_path=f"causal_graph.edges[{index}]",
                    edge=edge,
                    jurisdiction=jurisdiction,
                    policy_domain=resolved_policy_domain,
                    country_code=country_code,
                    time_window=time_window,
                    target_context_id=target_context_id,
                )
            )

    return needs


class _LegalGraphAdapter:
    def __init__(
        self,
        *,
        config: CrossGraphEvidenceConfig,
        bundle: TrinityBundle,
        causal_graph: CausalGraphModel | None,
        jurisdiction: str | None,
        policy_domain: str | None,
    ) -> None:
        self._config = config
        self._bundle = bundle
        self._causal_graph = causal_graph
        self._jurisdiction = jurisdiction
        self._policy_domain = policy_domain
        self._constraint_set: LegalConstraintSet | None = None
        self._diagnostics: list[CrossGraphDiagnostic] | None = None
        self._source_status_override: EvidenceSourceStatus | None = None

    def source_status(
        self,
        default: EvidenceSourceStatus,
    ) -> EvidenceSourceStatus:
        return self._source_status_override or default

    def assess_need(self, need: EvidenceNeed) -> _LegalResult:
        constraint_set, diagnostics = self._resolve_constraint_set(need)
        if constraint_set is None:
            return _LegalResult(
                status=LegalStatus.UNKNOWN,
                confidence=0.4,
                requires_expert_review=True,
                blocking_reasons=(),
                recommended_actions=("Configure legal evidence backend or jurisdiction.",),
                provenance_refs=(),
                diagnostics=tuple(diagnostics),
            )

        provenance_refs = tuple(
            sorted(
                {
                    *(constraint.legal_source for constraint in constraint_set.hard_constraints),
                    *(constraint.legal_source for constraint in constraint_set.soft_constraints),
                    *(
                        constraint.legal_source
                        for constraint in constraint_set.data_license_constraints
                    ),
                }
            )
        )
        requires_expert_review = bool(
            constraint_set.hard_constraints
            or constraint_set.soft_constraints
            or constraint_set.data_license_constraints
            or constraint_set.legal_dag_mappings
        )
        constrained = bool(
            constraint_set.soft_constraints or constraint_set.data_license_constraints
        )
        prohibited = bool(constraint_set.hard_constraints) and need.need_type in {
            EvidenceNeedType.MECHANISM_NEED,
            EvidenceNeedType.LEGAL_APPLICABILITY_NEED,
        }
        if prohibited:
            return _LegalResult(
                status=LegalStatus.PROHIBITED,
                confidence=0.0,
                requires_expert_review=True,
                blocking_reasons=("legal_status=prohibited",),
                recommended_actions=("Review target-jurisdiction legal blockers.",),
                provenance_refs=provenance_refs,
                diagnostics=tuple(diagnostics),
            )
        if constrained:
            return _LegalResult(
                status=LegalStatus.CONSTRAINED,
                confidence=0.65,
                requires_expert_review=requires_expert_review,
                blocking_reasons=(),
                recommended_actions=("Review legal soft constraints and licensing limits.",),
                provenance_refs=provenance_refs,
                diagnostics=tuple(diagnostics),
            )
        return _LegalResult(
            status=LegalStatus.ALLOWED,
            confidence=1.0,
            requires_expert_review=requires_expert_review,
            blocking_reasons=(),
            recommended_actions=(),
            provenance_refs=provenance_refs,
            diagnostics=tuple(diagnostics),
        )

    def _resolve_constraint_set(
        self,
        need: EvidenceNeed,
    ) -> tuple[LegalConstraintSet | None, list[CrossGraphDiagnostic]]:
        if self._diagnostics is not None:
            return self._constraint_set, list(self._diagnostics)

        diagnostics: list[CrossGraphDiagnostic] = []
        if not self._config.legal_db_path:
            diagnostics.append(
                CrossGraphDiagnostic(
                    code="cross_graph.legal.not_configured",
                    need_id=need.need_id,
                    message="Legal evidence backend is not configured.",
                )
            )
            self._constraint_set = None
            self._diagnostics = diagnostics
            return None, diagnostics

        if not self._jurisdiction or not self._policy_domain:
            diagnostics.append(
                CrossGraphDiagnostic(
                    code="cross_graph.legal.context_missing",
                    need_id=need.need_id,
                    message="Jurisdiction or policy domain is missing for legal applicability.",
                )
            )
            self._constraint_set = None
            self._diagnostics = diagnostics
            return None, diagnostics

        try:
            self._constraint_set = evaluate_transport_constraints(
                jurisdiction=self._jurisdiction,
                policy_domain=self._policy_domain,
                policy_spec=self._bundle.policy_spec.model_dump(mode="json"),
                causal_graph=(
                    self._causal_graph.model_dump(mode="json")
                    if self._causal_graph is not None
                    else None
                ),
                legal_kg_db_path=Path(self._config.legal_db_path),
            )
        except _CROSS_GRAPH_QUERY_ERRORS as exc:
            diagnostics.append(
                CrossGraphDiagnostic(
                    code="cross_graph.legal.query_failed",
                    need_id=need.need_id,
                    message="Legal evidence query failed.",
                    details={"error": str(exc)},
                )
            )
            self._constraint_set = None
            self._source_status_override = update_source_status(
                _build_legal_source_status(self._config),
                state=EvidenceSourceState.QUERY_FAILED,
                detail=f"{type(exc).__name__}:{exc}",
                warnings=[f"legal_query_failed:{type(exc).__name__}:{exc}"],
            )

        self._diagnostics = diagnostics
        return self._constraint_set, list(diagnostics)


def _assess_dataset_need(
    need: EvidenceNeed,
    *,
    concepts: list[CanonicalConcept],
    registry: DatasetRegistry | None,
    academic_query: SKGQuery | None,
    country_code: str | None,
    target_year: int | None,
) -> _DatasetResult:
    if registry is None:
        return _DatasetResult(
            status=ObservabilityStatus.UNKNOWN,
            confidence=0.4,
            requires_expert_review=True,
            recommended_actions=("Configure datasets evidence backend.",),
            provenance_refs=(),
            diagnostics=(
                CrossGraphDiagnostic(
                    code="cross_graph.datasets.not_configured",
                    need_id=need.need_id,
                    message="Dataset evidence backend is not configured.",
                ),
            ),
        )

    canonical_variables = _canonical_variables_for_concepts(concepts)
    if not canonical_variables:
        return _DatasetResult(
            status=ObservabilityStatus.UNKNOWN,
            confidence=0.4,
            requires_expert_review=True,
            recommended_actions=("Add dataset-variable ontology bridges for this need.",),
            provenance_refs=(),
            diagnostics=(
                CrossGraphDiagnostic(
                    code="cross_graph.datasets.join_key_missing",
                    need_id=need.need_id,
                    message="No dataset canonical variable is available for this need.",
                ),
            ),
        )

    if not country_code:
        return _DatasetResult(
            status=ObservabilityStatus.UNKNOWN,
            confidence=0.4,
            requires_expert_review=True,
            recommended_actions=("Provide target country or jurisdiction for dataset matching.",),
            provenance_refs=(),
            diagnostics=(
                CrossGraphDiagnostic(
                    code="cross_graph.datasets.country_missing",
                    need_id=need.need_id,
                    message="Target geography is missing for dataset observability lookup.",
                ),
            ),
        )

    year_range = (target_year, target_year) if target_year is not None else None
    direct_refs: list[str] = []
    proxy_refs: list[str] = []

    for canonical_var in canonical_variables:
        matches = registry.find_datasets_for_variable(
            canonical_var=canonical_var,
            country_code=country_code,
            year_range=year_range,
        )
        direct_matches = [
            match for match in matches if not match.is_proxy and match.coverage_match != "none"
        ]
        if direct_matches:
            best = direct_matches[0]
            direct_refs.append(f"{best.dataset_id}:{best.raw_variable}")
            continue

        proxy_chain = resolve_proxy(
            target_var=canonical_var,
            target_context=country_code,
            dataset_registry=registry,
            skg_query=academic_query,
        )
        if proxy_chain.proxies:
            best_proxy = proxy_chain.proxies[0]
            proxy_refs.append(
                f"{best_proxy.proxy_dataset_id}:{best_proxy.proxy_raw_name}->{canonical_var}"
            )

    if direct_refs:
        return _DatasetResult(
            status=ObservabilityStatus.DIRECT,
            confidence=1.0,
            requires_expert_review=False,
            recommended_actions=(),
            provenance_refs=tuple(sorted(set(direct_refs))),
            diagnostics=(),
        )
    if proxy_refs:
        return _DatasetResult(
            status=ObservabilityStatus.PROXY_ONLY,
            confidence=0.6,
            requires_expert_review=True,
            recommended_actions=(
                "Review proxy-chain quality before relying on this evidence need.",
            ),
            provenance_refs=tuple(sorted(set(proxy_refs))),
            diagnostics=(),
        )
    return _DatasetResult(
        status=ObservabilityStatus.MISSING,
        confidence=0.0,
        requires_expert_review=True,
        recommended_actions=("Add a direct dataset mapping or acceptable proxy chain.",),
        provenance_refs=(),
        diagnostics=(),
    )


def _assess_academic_need(
    need: EvidenceNeed,
    *,
    concepts: list[CanonicalConcept],
    academic_query: SKGQuery | None,
    target_context: ContextProfile | None,
) -> _AcademicResult:
    if academic_query is None:
        return _AcademicResult(
            status=EvidenceStatus.INSUFFICIENT,
            confidence=0.4,
            requires_expert_review=True,
            recommended_actions=("Configure academic evidence backend.",),
            provenance_refs=(),
            diagnostics=(
                CrossGraphDiagnostic(
                    code="cross_graph.academic.not_configured",
                    need_id=need.need_id,
                    message="Academic evidence backend is not configured.",
                ),
            ),
            best_context_distance=None,
            transport_confidence=None,
            transport_reasons=(),
        )

    if need.need_type is EvidenceNeedType.PARAMETER_NEED and need.parameter_name:
        candidates = academic_query.query_parameters(
            need.parameter_name,
            target_context=target_context,
            layer="auto",
            require_simulation_ready=True,
        )
        if not candidates:
            return _AcademicResult(
                status=EvidenceStatus.UNSUPPORTED,
                confidence=0.0,
                requires_expert_review=True,
                recommended_actions=("Add literature support for the target parameter.",),
                provenance_refs=(),
                diagnostics=(),
                best_context_distance=None,
                transport_confidence=None,
                transport_reasons=(),
            )
        best = _best_parameter_candidate(candidates)
        distance = _candidate_distance(best, target_context)
        score = _parameter_candidate_score(best)
        critical_quality_flags = {
            flag
            for flag in set(best.quality_flags) | set(best.transport_notes)
            if flag
            in {
                "raw_parameter_fallback",
                "no_uncertainty",
                "context_mismatch",
                "canonical_gap_resolved",
            }
        }
        status = (
            EvidenceStatus.SUPPORTED
            if score >= 0.75 and not critical_quality_flags
            else EvidenceStatus.MIXED
            if score >= 0.45
            else EvidenceStatus.INSUFFICIENT
        )
        refs = [best.parameter.name]
        if best.source_context is not None and best.source_context.context_id:
            refs.append(best.source_context.context_id)
        refs.extend(list(best.linked_claim_ids[:3]))
        refs.extend(list(best.linked_edge_ids[:3]))
        recommended_actions: list[str] = []
        if distance is not None and distance > 0.1:
            recommended_actions.append("Review context mismatch for selected literature parameter.")
        for note in best.transport_notes:
            action = _parameter_reason_to_action(note)
            if action:
                recommended_actions.append(action)
        for flag in best.quality_flags:
            action = _parameter_reason_to_action(flag)
            if action:
                recommended_actions.append(action)
        return _AcademicResult(
            status=status,
            confidence=score,
            requires_expert_review=bool(best.requires_expert_review),
            recommended_actions=tuple(_dedupe_preserve(recommended_actions)),
            provenance_refs=tuple(_dedupe_preserve(refs)),
            diagnostics=(),
            best_context_distance=distance,
            transport_confidence=max(0.0, 1.0 - float(best.transport_penalty or 0.0)),
            transport_reasons=tuple(best.transport_notes),
        )

    if need.need_type is EvidenceNeedType.CAUSAL_EDGE_NEED and need.cause and need.effect:
        support_rows = academic_query.query_edge_support(
            cause=need.cause,
            effect=need.effect,
            min_confidence=0.25,
            support_mode="hybrid",
        )
        if not support_rows:
            return _AcademicResult(
                status=EvidenceStatus.UNSUPPORTED,
                confidence=0.0,
                requires_expert_review=True,
                recommended_actions=("Add literature or empirical support for this causal edge.",),
                provenance_refs=(),
                diagnostics=(),
                best_context_distance=None,
            )
        best_row = sorted(
            support_rows,
            key=lambda item: (item.confidence, item.n_unique_works, item.n_claims),
            reverse=True,
        )[0]
        best_trust = float(best_row.confidence or 0.0)
        credible_rows = [row for row in support_rows if float(row.confidence or 0.0) >= 0.25]
        has_conflict = any(bool(row.conflict_flag) for row in credible_rows)
        has_moderated_conflict = any(
            str(row.resolution_status or "") == "moderated" for row in credible_rows
        )
        transport_records = []
        transport_reasons: list[str] = []
        best_transport_confidence: float | None = None
        if target_context is not None:
            transport_records = academic_query.query_edge_transport(
                [row.edge_id for row in credible_rows],
                target_context_id=target_context.context_id,
            )
            if transport_records:
                best_transport_confidence = max(
                    float(record.transport_confidence or 0.0) for record in transport_records
                )
                if best_transport_confidence < 0.45:
                    transport_reasons.append("weak_transfer_evidence")
                if not any(record.matched_moderators_count > 0 for record in transport_records):
                    transport_reasons.append("moderator_mismatch")
                if not any(
                    float(record.context_match_reward or 0.0) > 0.0 for record in transport_records
                ):
                    transport_reasons.append("source_context_missing")
            else:
                transport_reasons.append("transport_score_unavailable")
        status = EvidenceStatus.MIXED
        if (
            best_trust >= 0.7
            and int(best_row.n_unique_works or 0) >= 2
            and (not has_conflict or has_moderated_conflict)
        ):
            status = EvidenceStatus.SUPPORTED
        elif not credible_rows:
            status = EvidenceStatus.UNSUPPORTED
        if (
            status is EvidenceStatus.SUPPORTED
            and best_transport_confidence is not None
            and best_transport_confidence < 0.45
        ):
            status = EvidenceStatus.MIXED
        recommended_actions: list[str] = []
        if status is EvidenceStatus.MIXED and has_conflict:
            recommended_actions.append("Review mixed evidence directions for this causal edge.")
        if has_moderated_conflict:
            recommended_actions.append(
                "Directional disagreement appears moderator-explained rather than purely contradictory."
            )
        for reason in transport_reasons:
            if reason == "transport_score_unavailable":
                recommended_actions.append(
                    "Transport rationale: target_profile_missing_or_transport_score_unavailable."
                )
            elif reason == "moderator_mismatch":
                recommended_actions.append("Transport rationale: moderator_mismatch.")
            elif reason == "source_context_missing":
                recommended_actions.append("Transport rationale: source_context_missing.")
            elif reason == "weak_transfer_evidence":
                recommended_actions.append("Transport rationale: weak_transfer_evidence.")
        return _AcademicResult(
            status=status,
            confidence=max(0.4, min(1.0, best_trust)),
            requires_expert_review=(status is EvidenceStatus.MIXED or bool(transport_reasons)),
            recommended_actions=tuple(_dedupe_preserve(recommended_actions)),
            provenance_refs=tuple(
                sorted(
                    {
                        *[row.edge_id for row in support_rows],
                        *[ref for row in support_rows for ref in row.article_refs],
                    }
                )
            ),
            diagnostics=(),
            best_context_distance=None,
            transport_confidence=best_transport_confidence,
            transport_reasons=tuple(_dedupe_preserve(transport_reasons)),
        )

    canonical_variables = _canonical_variables_for_concepts(concepts)
    for canonical_var in canonical_variables:
        prior_result = academic_query.query_prior(variable=canonical_var)
        if prior_result.prior is None:
            continue
        n_studies = int(prior_result.prior.n_studies)
        status = (
            EvidenceStatus.SUPPORTED
            if n_studies >= 3
            else EvidenceStatus.MIXED
            if n_studies >= 1
            else EvidenceStatus.INSUFFICIENT
        )
        confidence = min(1.0, 0.35 + 0.15 * n_studies)
        provenance_refs = tuple(
            sorted({estimate.work_id or estimate.id for estimate in prior_result.estimates})
        )
        return _AcademicResult(
            status=status,
            confidence=confidence,
            requires_expert_review=(status is not EvidenceStatus.SUPPORTED),
            recommended_actions=(
                ("Review study-design quality before reusing this literature evidence.",)
                if status is not EvidenceStatus.SUPPORTED
                else ()
            ),
            provenance_refs=provenance_refs,
            diagnostics=(),
            best_context_distance=None,
            transport_confidence=None,
            transport_reasons=(),
        )

    return _AcademicResult(
        status=EvidenceStatus.INSUFFICIENT,
        confidence=0.3,
        requires_expert_review=True,
        recommended_actions=(
            "Add academic ontology bridges or literature evidence for this need.",
        ),
        provenance_refs=(),
        diagnostics=(),
        best_context_distance=None,
        transport_confidence=None,
        transport_reasons=(),
    )


def _academic_result_from_gatherer(result: Any) -> _AcademicResult:
    status_raw = str(getattr(result, "status", EvidenceStatus.INSUFFICIENT.value))
    try:
        status = EvidenceStatus(status_raw)
    except ValueError:
        status = EvidenceStatus.INSUFFICIENT
    metadata = dict(getattr(result, "metadata", {}) or {})
    transport_reasons = tuple(
        str(item) for item in list(metadata.get("transport_reasons", []) or [])
    )
    confidence = max(0.0, min(1.0, float(getattr(result, "confidence", 0.0) or 0.0)))
    return _AcademicResult(
        status=status,
        confidence=confidence,
        requires_expert_review=(
            status is not EvidenceStatus.SUPPORTED
            or bool(metadata.get("environment_audit_summary"))
        ),
        recommended_actions=(),
        provenance_refs=tuple(
            str(item) for item in list(getattr(result, "provenance_refs", []) or [])
        ),
        diagnostics=tuple(getattr(result, "diagnostics", []) or ()),
        best_context_distance=None,
        transport_confidence=confidence,
        transport_reasons=transport_reasons,
    )


def _environment_audit_summary(
    literature_prior: LiteratureCausalPrior | None,
) -> dict[str, Any]:
    if literature_prior is None or literature_prior.environment_audit is None:
        return {}
    audit = literature_prior.environment_audit
    return {
        "status": audit.status,
        "n_environments": audit.n_environments,
        "ks_passed": audit.ks_passed,
        "ks_rejected_variables": list(audit.ks_rejected_variables),
        "icp_run": audit.icp_run,
        "icp_passed": audit.icp_passed,
        "variant_features": list(audit.variant_features),
        "warnings": list(audit.warnings),
    }


def _literature_prior_diagnostics(
    *,
    literature_prior: LiteratureCausalPrior | None,
    literature_prior_ref: str | None,
) -> list[CrossGraphDiagnostic]:
    if literature_prior is None:
        return []
    details: dict[str, Any] = {
        "literature_prior_ref": literature_prior_ref,
        "build_status": literature_prior.metadata.get("build_status"),
        "edge_count": len(literature_prior.edges),
    }
    environment_summary = _environment_audit_summary(literature_prior)
    if environment_summary:
        details["environment_audit_summary"] = environment_summary
    return [
        CrossGraphDiagnostic(
            code="cross_graph.academic.literature_prior_context",
            message="Cross-graph compiler incorporated literature prior and environment audit context.",
            details=details,
        )
    ]


def _literature_prior_notes(
    *,
    literature_prior: LiteratureCausalPrior | None,
    literature_prior_ref: str | None,
) -> list[str]:
    if literature_prior is None:
        return []
    notes = ["literature_prior_context_attached"]
    if literature_prior_ref:
        notes.append(f"literature_prior_ref:{literature_prior_ref}")
    if literature_prior.environment_audit is not None:
        notes.append(f"environment_audit_status:{literature_prior.environment_audit.status}")
    return notes


def _compose_transportability_view(
    need: EvidenceNeed,
    *,
    target_context: ContextProfile | None,
    observability_status: ObservabilityStatus,
    evidence_result: _AcademicResult,
) -> _TransportResult:
    if evidence_result.status is EvidenceStatus.UNSUPPORTED:
        return _TransportResult(
            status=TransportStatus.UNSUPPORTED,
            mode=TransportMode.NONE,
            confidence=0.0,
            requires_expert_review=True,
            blocking_reasons=(),
            recommended_actions=(),
            diagnostics=(),
        )

    if target_context is not None and evidence_result.transport_confidence is not None:
        confidence = max(0.0, min(1.0, float(evidence_result.transport_confidence)))
        recommended_actions = [
            _transport_reason_to_action(reason)
            for reason in evidence_result.transport_reasons
            if _transport_reason_to_action(reason)
        ]
        if confidence >= 0.70:
            return _TransportResult(
                status=TransportStatus.IDENTIFIED,
                mode=TransportMode.TRANSPORT_FORMULA,
                confidence=confidence,
                requires_expert_review=bool(recommended_actions),
                blocking_reasons=(),
                recommended_actions=tuple(_dedupe_preserve(recommended_actions)),
                diagnostics=(),
            )
        if confidence >= 0.45:
            return _TransportResult(
                status=TransportStatus.PARTIALLY_IDENTIFIED,
                mode=TransportMode.TRANSPORT_FORMULA,
                confidence=confidence,
                requires_expert_review=True,
                blocking_reasons=(),
                recommended_actions=tuple(
                    _dedupe_preserve(
                        [
                            *recommended_actions,
                            "Review transport assumptions for this evidence need.",
                        ]
                    )
                ),
                diagnostics=(),
            )
        return _TransportResult(
            status=TransportStatus.BOUNDED_NON_IDENTIFIED,
            mode=TransportMode.BOUNDS_ONLY,
            confidence=confidence,
            requires_expert_review=True,
            blocking_reasons=("transport_status=bounded_non_identified",),
            recommended_actions=tuple(
                _dedupe_preserve(
                    [
                        *recommended_actions,
                        "Generate target-context evidence or run transportability analysis.",
                    ]
                )
            ),
            diagnostics=(),
        )

    if target_context is None:
        status = (
            TransportStatus.IDENTIFIED
            if evidence_result.status in {EvidenceStatus.SUPPORTED, EvidenceStatus.MIXED}
            else TransportStatus.UNSUPPORTED
        )
        mode = TransportMode.DIRECT if status is TransportStatus.IDENTIFIED else TransportMode.NONE
        confidence = 1.0 if status is TransportStatus.IDENTIFIED else 0.4
        return _TransportResult(
            status=status,
            mode=mode,
            confidence=confidence,
            requires_expert_review=False,
            blocking_reasons=(),
            recommended_actions=(),
            diagnostics=(),
        )

    if evidence_result.best_context_distance is not None:
        if evidence_result.best_context_distance <= 0.1:
            return _TransportResult(
                status=TransportStatus.IDENTIFIED,
                mode=TransportMode.DIRECT,
                confidence=1.0,
                requires_expert_review=False,
                blocking_reasons=(),
                recommended_actions=(),
                diagnostics=(),
            )
        if evidence_result.best_context_distance <= 0.6:
            return _TransportResult(
                status=TransportStatus.IDENTIFIED,
                mode=TransportMode.TRANSPORT_FORMULA,
                confidence=max(0.5, 1.0 - evidence_result.best_context_distance),
                requires_expert_review=True,
                blocking_reasons=(),
                recommended_actions=("Review transport assumptions for this evidence need.",),
                diagnostics=(),
            )
        return _TransportResult(
            status=TransportStatus.UNSUPPORTED,
            mode=TransportMode.NONE,
            confidence=0.0,
            requires_expert_review=True,
            blocking_reasons=("transport_status=unsupported",),
            recommended_actions=(
                "Generate target-context evidence or run transportability analysis.",
            ),
            diagnostics=(),
        )

    if evidence_result.status in {
        EvidenceStatus.SUPPORTED,
        EvidenceStatus.MIXED,
        EvidenceStatus.INSUFFICIENT,
    }:
        if observability_status is ObservabilityStatus.DIRECT:
            return _TransportResult(
                status=TransportStatus.IDENTIFIED,
                mode=TransportMode.TRANSPORT_FORMULA,
                confidence=0.75,
                requires_expert_review=(evidence_result.status is not EvidenceStatus.SUPPORTED),
                blocking_reasons=(),
                recommended_actions=("Confirm target-context transfer assumptions.",),
                diagnostics=(),
            )
        if observability_status is ObservabilityStatus.PROXY_ONLY:
            return _TransportResult(
                status=TransportStatus.PARTIALLY_IDENTIFIED,
                mode=TransportMode.TRANSPORT_FORMULA,
                confidence=0.55,
                requires_expert_review=True,
                blocking_reasons=(),
                recommended_actions=("Validate proxy-mediated transport assumptions.",),
                diagnostics=(),
            )
        if observability_status is ObservabilityStatus.MISSING:
            return _TransportResult(
                status=TransportStatus.BOUNDED_NON_IDENTIFIED,
                mode=TransportMode.BOUNDS_ONLY,
                confidence=0.0,
                requires_expert_review=True,
                blocking_reasons=("transport_status=bounded_non_identified",),
                recommended_actions=(
                    "Acquire target-context data before reusing external evidence.",
                ),
                diagnostics=(),
            )

    return _TransportResult(
        status=TransportStatus.UNSUPPORTED,
        mode=TransportMode.NONE,
        confidence=0.4,
        requires_expert_review=True,
        blocking_reasons=(),
        recommended_actions=("Review transportability assumptions manually.",),
        diagnostics=(),
    )


def _transport_reason_to_action(reason: str) -> str:
    if reason == "source_context_missing":
        return "Source context is missing for this literature evidence."
    if reason == "moderator_mismatch":
        return "Observed moderators do not align cleanly with the target context."
    if reason == "weak_transfer_evidence":
        return "Transport evidence is weak for the target context."
    if reason == "transport_score_unavailable":
        return "Target profile is missing or academic transport scores are unavailable."
    return ""


def _resolve_ontology_for_need(
    need: EvidenceNeed,
    *,
    ontology: list[CanonicalConcept],
) -> tuple[list[CanonicalConcept], list[ConceptBridge], list[CrossGraphDiagnostic]]:
    resolved: list[CanonicalConcept] = []
    bridges: list[ConceptBridge] = []
    diagnostics: list[CrossGraphDiagnostic] = []

    for concept in ontology:
        for key_name, relation in _need_key_relation_pairs(need):
            values = concept.join_keys.get(key_name, [])
            if not values:
                continue
            need_value = _need_key_value(need, key_name)
            if need_value is None:
                continue
            if str(need_value) not in {str(value) for value in values}:
                continue
            resolved.append(concept)
            if relation is not None:
                bridges.append(
                    ConceptBridge(
                        src_system=_source_system_for_key(key_name),
                        src_kind=key_name,
                        src_id=str(need_value),
                        dst_concept_id=concept.concept_id,
                        relation=relation,
                        confidence=1.0,
                        provenance=[f"ontology:{concept.concept_id}"],
                    )
                )
            break

    if not resolved:
        diagnostics.append(
            CrossGraphDiagnostic(
                code="cross_graph.ontology.unknown_concept",
                need_id=need.need_id,
                message="No ontology bridge resolved this evidence need.",
                details={"source_path": need.source_path, "need_type": need.need_type.value},
            )
        )

    deduped = {concept.concept_id: concept for concept in resolved}
    return list(deduped.values()), _dedupe_bridges(bridges), diagnostics


def _metric_need(
    *,
    need_type: EvidenceNeedType,
    source_path: str,
    metric_id: str | None,
    jurisdiction: str | None,
    policy_domain: str | None,
    country_code: str | None,
    time_window: str | None,
    target_context_id: str | None,
    kpi_id: str | None = None,
    criterion_id: str | None = None,
) -> EvidenceNeed:
    payload = {
        "metric_id": metric_id,
        "kpi_id": kpi_id,
        "criterion_id": criterion_id,
        "jurisdiction": jurisdiction,
        "policy_domain": policy_domain,
    }
    return EvidenceNeed(
        need_id=build_evidence_need_id(need_type, source_path=source_path, payload=payload),
        need_type=need_type,
        source_path=source_path,
        metric_id=metric_id,
        kpi_id=kpi_id,
        criterion_id=criterion_id,
        jurisdiction=jurisdiction,
        policy_domain=policy_domain,
        geography=country_code,
        time_window=time_window,
        target_context_id=target_context_id,
    )


def _constraint_need(
    *,
    source_path: str,
    constraint: ConstraintSpec,
    jurisdiction: str | None,
    policy_domain: str | None,
    country_code: str | None,
    time_window: str | None,
    target_context_id: str | None,
) -> EvidenceNeed:
    payload = {
        "constraint_id": constraint.constraint_id,
        "slot_id": constraint.slot_id,
        "jurisdiction": jurisdiction,
        "policy_domain": policy_domain,
    }
    return EvidenceNeed(
        need_id=build_evidence_need_id(
            EvidenceNeedType.CONSTRAINT_METRIC_OR_SLOT,
            source_path=source_path,
            payload=payload,
        ),
        need_type=EvidenceNeedType.CONSTRAINT_METRIC_OR_SLOT,
        source_path=source_path,
        constraint_id=constraint.constraint_id,
        slot_id=constraint.slot_id,
        jurisdiction=jurisdiction,
        policy_domain=policy_domain,
        geography=country_code,
        time_window=time_window,
        target_context_id=target_context_id,
    )


def _intervention_need(
    *,
    need_type: EvidenceNeedType,
    source_path: str,
    intervention: InterventionSpec,
    jurisdiction: str | None,
    policy_domain: str | None,
    country_code: str | None,
    time_window: str | None,
    target_context_id: str | None,
) -> EvidenceNeed:
    payload = {
        "intervention_id": intervention.intervention_id,
        "intervention_kind": intervention.kind,
        "jurisdiction": jurisdiction,
        "policy_domain": policy_domain,
    }
    return EvidenceNeed(
        need_id=build_evidence_need_id(need_type, source_path=source_path, payload=payload),
        need_type=need_type,
        source_path=source_path,
        intervention_id=intervention.intervention_id,
        intervention_kind=intervention.kind,
        jurisdiction=jurisdiction,
        policy_domain=policy_domain,
        geography=country_code,
        time_window=time_window,
        target_context_id=target_context_id,
    )


def _parameter_need(
    *,
    source_path: str,
    parameter_name: str,
    param_path: str,
    intervention_id: str | None,
    jurisdiction: str | None,
    policy_domain: str | None,
    country_code: str | None,
    time_window: str | None,
    target_context_id: str | None,
) -> EvidenceNeed:
    payload = {
        "parameter_name": parameter_name,
        "param_path": param_path,
        "intervention_id": intervention_id,
        "jurisdiction": jurisdiction,
        "policy_domain": policy_domain,
    }
    return EvidenceNeed(
        need_id=build_evidence_need_id(
            EvidenceNeedType.PARAMETER_NEED,
            source_path=source_path,
            payload=payload,
        ),
        need_type=EvidenceNeedType.PARAMETER_NEED,
        source_path=source_path,
        parameter_name=parameter_name,
        param_path=param_path,
        intervention_id=intervention_id,
        jurisdiction=jurisdiction,
        policy_domain=policy_domain,
        geography=country_code,
        time_window=time_window,
        target_context_id=target_context_id,
    )


def _causal_edge_need(
    *,
    source_path: str,
    edge: CausalEdge,
    jurisdiction: str | None,
    policy_domain: str | None,
    country_code: str | None,
    time_window: str | None,
    target_context_id: str | None,
) -> EvidenceNeed:
    payload = {
        "cause": edge.src,
        "effect": edge.dst,
        "lag": edge.lag,
        "jurisdiction": jurisdiction,
        "policy_domain": policy_domain,
    }
    return EvidenceNeed(
        need_id=build_evidence_need_id(
            EvidenceNeedType.CAUSAL_EDGE_NEED,
            source_path=source_path,
            payload=payload,
        ),
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path=source_path,
        jurisdiction=jurisdiction,
        policy_domain=policy_domain,
        geography=country_code,
        time_window=time_window,
        target_context_id=target_context_id,
        cause=edge.src,
        effect=edge.dst,
    )


def _country_code(target_context: ContextProfile | None) -> str | None:
    if target_context is None or not target_context.countries:
        return None
    candidate = str(target_context.countries[0]).strip().upper()
    return candidate or None


def _target_year(target_context: ContextProfile | None) -> int | None:
    if target_context is None:
        return None
    return target_context.publication_year


def _time_window(target_context: ContextProfile | None) -> str | None:
    if target_context is None:
        return None
    if target_context.time_period:
        return target_context.time_period
    if target_context.publication_year is not None:
        return str(target_context.publication_year)
    return None


def _parameter_name(parameter: ParameterSpec) -> str:
    tail = str(parameter.param_path).split(".")[-1].strip()
    return tail or parameter.param_id


def _build_academic_query(
    config: CrossGraphEvidenceConfig,
) -> tuple[SKGQuery | None, EvidenceSourceStatus]:
    status = build_path_source_status(
        EvidenceSourceKind.ACADEMIC,
        config.academic_db_path,
        detail="cross_graph_compiler",
    )
    if status.status is not EvidenceSourceState.AVAILABLE:
        return None, status
    db_path = Path(config.academic_db_path)
    index_dir = Path(config.academic_index_dir) if config.academic_index_dir else db_path.parent
    if not index_dir.exists():
        index_dir = db_path.parent
    try:
        return SKGQuery(db_path=db_path, index_dir=index_dir), status
    except _CROSS_GRAPH_INIT_ERRORS as exc:
        return None, update_source_status(
            status,
            state=EvidenceSourceState.INIT_FAILED,
            detail=f"{type(exc).__name__}:{exc}",
            warnings=[f"academic_init_failed:{type(exc).__name__}:{exc}"],
        )


def _build_dataset_registry(
    config: CrossGraphEvidenceConfig,
) -> tuple[DatasetRegistry | None, EvidenceSourceStatus]:
    status = build_path_source_status(
        EvidenceSourceKind.DATASETS,
        config.datasets_db_path,
        detail="cross_graph_compiler",
    )
    if status.status is not EvidenceSourceState.AVAILABLE:
        return None, status
    db_path = Path(config.datasets_db_path)
    try:
        return DatasetRegistry(db_path), status
    except _CROSS_GRAPH_INIT_ERRORS as exc:
        return None, update_source_status(
            status,
            state=EvidenceSourceState.INIT_FAILED,
            detail=f"{type(exc).__name__}:{exc}",
            warnings=[f"dataset_registry_init_failed:{type(exc).__name__}:{exc}"],
        )


def _build_legal_source_status(config: CrossGraphEvidenceConfig) -> EvidenceSourceStatus:
    return build_path_source_status(
        EvidenceSourceKind.LEGAL,
        config.legal_db_path,
        detail="cross_graph_compiler",
    )


def _best_parameter_candidate(candidates: list[ParameterCandidate]) -> ParameterCandidate:
    return sorted(candidates, key=_parameter_candidate_score, reverse=True)[0]


def _candidate_distance(
    candidate: ParameterCandidate,
    target_context: ContextProfile | None,
) -> float | None:
    if target_context is None or candidate.source_context is None:
        return None
    try:
        return float(candidate.source_context.distance_to(target_context))
    except _CROSS_GRAPH_DISTANCE_ERRORS:
        return None


def _parameter_candidate_score(candidate: ParameterCandidate) -> float:
    strength = getattr(candidate.parameter.evidence_strength, "value", "unknown")
    strength_weight = {
        "rct": 1.0,
        "meta_analysis": 0.95,
        "quasi_natural": 0.8,
        "quasi_natural_event": 0.75,
        "panel_fe": 0.65,
        "structural": 0.55,
        "observational": 0.45,
        "cross_sectional": 0.35,
        "theoretical": 0.15,
        "unknown": 0.25,
    }.get(str(strength), 0.25)
    transport_factor = max(0.0, 1.0 - float(candidate.transport_penalty or 0.0))
    review_penalty = 0.85 if candidate.requires_expert_review else 1.0
    layer_factor = 1.0 if candidate.source_layer in {"simulation_ready", "simulation"} else 0.7
    uncertainty_factor = 1.0
    if candidate.uncertainty_source == "heuristic":
        uncertainty_factor = 0.8
    elif candidate.parameter.confidence_interval is None and candidate.parameter.std_error is None:
        uncertainty_factor = 0.6
    if "context_mismatch" in candidate.transport_notes:
        transport_factor *= 0.8
    if (
        "canonical_gap_resolved" in candidate.quality_flags
        or "canonical_gap_resolved" in candidate.transport_notes
    ):
        review_penalty *= 0.9
    return max(
        0.0,
        min(
            1.0,
            strength_weight * transport_factor * review_penalty * layer_factor * uncertainty_factor,
        ),
    )


def _parameter_reason_to_action(reason: str) -> str:
    if reason == "source_context_missing":
        return "Transport rationale: source_context_missing."
    if reason == "target_context_profile_missing":
        return "Transport rationale: target_context_profile_missing."
    if reason == "transport_score_unavailable":
        return "Transport rationale: target_profile_missing_or_transport_score_unavailable."
    if reason == "raw_parameter_fallback":
        return "Prefer a simulation-ready literature estimate instead of raw parameter fallback."
    if reason == "no_uncertainty":
        return "Add uncertainty-bearing evidence (CI or SE) before relying on this parameter in simulation."
    if reason == "context_mismatch":
        return "Context mismatch detected between source evidence and target context."
    if reason == "canonical_gap_resolved":
        return (
            "Verify the canonical mapping between the requested parameter and literature variable."
        )
    return ""


def _canonical_variables_for_concepts(concepts: list[CanonicalConcept]) -> list[str]:
    values: list[str] = []
    for concept in concepts:
        for key_name in (
            "canonical_var",
            "canonical_variable",
            "dataset_variable",
            "variable",
            "cause",
            "effect",
        ):
            values.extend(str(item) for item in concept.join_keys.get(key_name, []))
    return sorted({value for value in values if value})


def _need_key_relation_pairs(
    need: EvidenceNeed,
) -> list[tuple[str, BridgeRelation | None]]:
    pairs: list[tuple[str, BridgeRelation | None]] = []
    if need.metric_id:
        pairs.append(("metric_id", BridgeRelation.METRIC_TO_VARIABLE))
    if need.parameter_name:
        pairs.append(("parameter_name", BridgeRelation.PARAMETER_TO_VARIABLE))
    if need.param_path:
        pairs.append(("param_path", BridgeRelation.PARAMETER_TO_VARIABLE))
    if need.intervention_kind and need.need_type is EvidenceNeedType.LEGAL_APPLICABILITY_NEED:
        pairs.append(("intervention_kind", BridgeRelation.LEGAL_TO_VARIABLE))
    if need.constraint_id:
        pairs.append(("constraint_id", BridgeRelation.LEGAL_TO_VARIABLE))
    if need.slot_id:
        pairs.append(("slot_id", BridgeRelation.LEGAL_TO_VARIABLE))
    if need.cause:
        pairs.append(("cause", BridgeRelation.CLAIM_TO_EDGE))
    if need.effect:
        pairs.append(("effect", BridgeRelation.CLAIM_TO_EDGE))
    if need.target_context_id:
        pairs.append(("context_id", BridgeRelation.CONTEXT_DIMENSION_TO_VARIABLE))
    return pairs


def _need_key_value(need: EvidenceNeed, key_name: str) -> str | None:
    mapping = {
        "metric_id": need.metric_id,
        "parameter_name": need.parameter_name,
        "param_path": need.param_path,
        "intervention_kind": need.intervention_kind,
        "constraint_id": need.constraint_id,
        "slot_id": need.slot_id,
        "cause": need.cause,
        "effect": need.effect,
        "context_id": need.target_context_id,
    }
    return mapping.get(key_name)


def _source_system_for_key(key_name: str) -> str:
    if key_name in {
        "metric_id",
        "parameter_name",
        "param_path",
        "intervention_kind",
        "constraint_id",
        "slot_id",
    }:
        return "trinity"
    if key_name in {"cause", "effect"}:
        return "academic"
    if key_name == "context_id":
        return "context"
    return "ontology"


def _aggregate_confidence(
    legal_status: LegalStatus,
    observability_status: ObservabilityStatus,
    evidence_status: EvidenceStatus,
    transport_status: TransportStatus,
    *,
    requires_expert_review: bool,
) -> float:
    confidence = (
        _legal_confidence(legal_status)
        + _observability_confidence(observability_status)
        + _evidence_confidence(evidence_status)
        + _transport_confidence(transport_status)
    ) / 4.0
    if requires_expert_review:
        confidence *= 0.9
    return max(0.0, min(1.0, confidence))


def _legal_confidence(status: LegalStatus) -> float:
    return {
        LegalStatus.ALLOWED: 1.0,
        LegalStatus.CONSTRAINED: 0.65,
        LegalStatus.PROHIBITED: 0.0,
        LegalStatus.UNKNOWN: 0.4,
    }[status]


def _observability_confidence(status: ObservabilityStatus) -> float:
    return {
        ObservabilityStatus.DIRECT: 1.0,
        ObservabilityStatus.PROXY_ONLY: 0.6,
        ObservabilityStatus.MISSING: 0.0,
        ObservabilityStatus.UNKNOWN: 0.4,
    }[status]


def _evidence_confidence(status: EvidenceStatus) -> float:
    return {
        EvidenceStatus.SUPPORTED: 1.0,
        EvidenceStatus.MIXED: 0.7,
        EvidenceStatus.INSUFFICIENT: 0.45,
        EvidenceStatus.UNSUPPORTED: 0.0,
    }[status]


def _transport_confidence(status: TransportStatus) -> float:
    return {
        TransportStatus.IDENTIFIED: 1.0,
        TransportStatus.PARTIALLY_IDENTIFIED: 0.65,
        TransportStatus.BOUNDED_NON_IDENTIFIED: 0.35,
        TransportStatus.UNSUPPORTED: 0.0,
    }[status]


def _build_summary(assessments: list[EvidenceNeedAssessment]) -> CrossGraphEvidenceSummary:
    blocking_need_ids = [
        assessment.need.need_id
        for assessment in assessments
        if _is_strict_blocking_assessment(assessment)
    ]
    requires_expert_review_count = sum(
        1 for assessment in assessments if assessment.requires_expert_review
    )
    status = (
        "warning"
        if blocking_need_ids
        or requires_expert_review_count
        or any(assessment.diagnostics for assessment in assessments)
        else "ok"
    )
    return CrossGraphEvidenceSummary(
        status=status,
        total_needs=len(assessments),
        requires_expert_review_count=requires_expert_review_count,
        blocking_need_ids=blocking_need_ids,
        legal_status_counts=_status_counts(
            assessment.legal_status.value for assessment in assessments
        ),
        observability_status_counts=_status_counts(
            assessment.observability_status.value for assessment in assessments
        ),
        evidence_status_counts=_status_counts(
            assessment.evidence_status.value for assessment in assessments
        ),
        transport_status_counts=_status_counts(
            assessment.transport_status.value for assessment in assessments
        ),
    )


def _status_counts(values: list[str] | Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _is_strict_blocking_assessment(assessment: EvidenceNeedAssessment) -> bool:
    return any(
        (
            assessment.legal_status is LegalStatus.PROHIBITED,
            assessment.observability_status is ObservabilityStatus.MISSING,
            assessment.evidence_status is EvidenceStatus.UNSUPPORTED,
            assessment.transport_status is TransportStatus.UNSUPPORTED,
        )
    )


def _profile_notes(config: CrossGraphEvidenceConfig) -> list[str]:
    notes: list[str] = ["cross_graph_join_layer_v1"]
    if not config.ontology:
        notes.append("ontology_empty")
    return notes


def _dedupe_bridges(bridges: list[ConceptBridge]) -> list[ConceptBridge]:
    unique: dict[tuple[str, str, str, str, str], ConceptBridge] = {}
    for bridge in bridges:
        key = (
            bridge.src_system,
            bridge.src_kind,
            bridge.src_id,
            bridge.dst_concept_id,
            bridge.relation.value,
        )
        unique[key] = bridge
    return [unique[key] for key in sorted(unique)]


def _dedupe_diagnostics(
    diagnostics: list[CrossGraphDiagnostic],
) -> list[CrossGraphDiagnostic]:
    unique: dict[tuple[str, str, str | None, str, str], CrossGraphDiagnostic] = {}
    for diagnostic in diagnostics:
        unique[diagnostic_key(diagnostic)] = diagnostic
    return [unique[key] for key in sorted(unique)]


def _dedupe_preserve(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        output.append(token)
    return output


def _append_unique_diagnostics(
    target: list[CrossGraphDiagnostic],
    seen: set[tuple[str, str, str | None, str, str]],
    additions: list[CrossGraphDiagnostic] | tuple[CrossGraphDiagnostic, ...],
) -> None:
    for diagnostic in additions:
        key = diagnostic_key(diagnostic)
        if key in seen:
            continue
        seen.add(key)
        target.append(diagnostic)


def build_fragment_alignment_ontology_warnings(
    *,
    fragment_a: Any,
    fragment_b: Any,
    certificates: list[Any] | tuple[Any, ...],
    ontology: list[CanonicalConcept],
) -> list[str]:
    """Build fragment alignment ontology warnings."""
    normalized_ontology: list[CanonicalConcept] = []
    for concept in ontology:
        if isinstance(concept, CanonicalConcept):
            normalized_ontology.append(concept)
        elif isinstance(concept, dict):
            try:
                normalized_ontology.append(CanonicalConcept.model_validate(concept))
            except _CROSS_GRAPH_MODEL_ERRORS:
                continue
    if not normalized_ontology:
        return []

    warnings: list[str] = []
    for certificate in certificates:
        if getattr(certificate, "alignment_type", None) == "incompatible":
            continue
        if (
            getattr(certificate, "alignment_type", None) is not None
            and getattr(
                getattr(certificate, "alignment_type", None),
                "value",
                None,
            )
            == "incompatible"
        ):
            continue

        concept_a = _resolve_alignment_concept(
            ontology=normalized_ontology,
            semantic_namespace=str(getattr(fragment_a, "semantic_namespace", "") or ""),
            variable_name=str(getattr(certificate, "variable_a", "") or ""),
            definition=str(
                getattr(getattr(fragment_a, "variable_definitions", {}), "get", lambda *_: "")(
                    getattr(certificate, "variable_a", "")
                )
                or ""
            ),
        )
        concept_b = _resolve_alignment_concept(
            ontology=normalized_ontology,
            semantic_namespace=str(getattr(fragment_b, "semantic_namespace", "") or ""),
            variable_name=str(getattr(certificate, "variable_b", "") or ""),
            definition=str(
                getattr(getattr(fragment_b, "variable_definitions", {}), "get", lambda *_: "")(
                    getattr(certificate, "variable_b", "")
                )
                or ""
            ),
        )

        pair_label = (
            f"{getattr(certificate, 'fragment_a_id', '?')}:{getattr(certificate, 'variable_a', '?')}"
            f" <-> {getattr(certificate, 'fragment_b_id', '?')}:{getattr(certificate, 'variable_b', '?')}"
        )
        if concept_a is None or concept_b is None:
            warnings.append(f"Ontology unresolved for alignment pair {pair_label}.")
            continue
        if concept_a.concept_id != concept_b.concept_id:
            warnings.append(
                "Ontology mismatch for alignment pair "
                f"{pair_label}: {concept_a.concept_id} vs {concept_b.concept_id}."
            )

    return _dedupe_preserve(sorted(warnings))


def _resolve_alignment_concept(
    *,
    ontology: list[CanonicalConcept],
    semantic_namespace: str,
    variable_name: str,
    definition: str,
) -> CanonicalConcept | None:
    query_tokens = alignment_tokens((semantic_namespace, variable_name, definition))
    if not query_tokens:
        return None

    best: tuple[int, str, CanonicalConcept] | None = None
    for concept in ontology:
        current_concept_tokens = concept_tokens(concept)
        if not current_concept_tokens:
            continue
        overlap = len(query_tokens.intersection(current_concept_tokens))
        if overlap <= 0:
            continue
        candidate = (overlap, concept.concept_id, concept)
        if best is None or candidate > best:
            best = candidate
    return best[2] if best is not None else None


__all__ = [
    "CrossGraphEvidenceCompiler",
    "CrossGraphEvidenceConfig",
    "build_fragment_alignment_ontology_warnings",
    "extract_evidence_needs",
]
