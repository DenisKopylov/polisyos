"""Semantic binding ledger contracts for honest diagnostics."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.runtime.quality.candidate_firewall import (
    candidate_firewall_issues_for_payload,
)

SEMANTIC_BINDING_SCHEMA_VERSION = "policyos.semantic_binding_ledger.v1"
PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION = "policyos.producer_spine_context.v1"
GY_SEMANTIC_BENCHMARK_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.semantic_benchmark.v1"
PRODUCER_SPINE_CONSUMER_COMPONENTS = (
    "lex",
    "fabric",
    "scholar",
    "foundry",
    "scientist",
    "final_compiler",
)

SemanticBindingStatus = Literal["pass", "blocked", "fail"]
RuntimeReportStatus = Literal["pass", "blocked", "fail", "warn", "degraded"]
SemanticIssueSeverity = Literal["fail", "warn"]

_GENERIC_TOKENS = frozenset(
    {
        "default",
        "demo",
        "fixture",
        "generic",
        "manifest",
        "mock",
        "placeholder",
        "stub",
        "unknown",
    }
)
_SEMANTIC_SPINE_NEXT_COMMAND = (
    "uv run pytest tests/unit/runtime/quality/test_semantic_binding.py "
    "tests/unit/runtime/quality/test_scorecard.py -q"
)


class GySemanticBenchmark(BaseModel):
    """Committed governed benchmark used by the GY semantic adequacy gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    benchmark_id: str
    catalog_corpus_kind: Literal[
        "slice0_representative_fixture_corpus",
        "production_dataset_catalog_graph_snapshot",
    ]
    closure_scope: Literal["slice0_gate_only", "production_closure"]
    open_production_findings: list[str] = Field(default_factory=list)
    label_owner: str
    expert_author: str
    reviewer: str
    provenance: dict[str, str]
    thresholds: dict[str, dict[str, float]]
    labels: list[dict[str, Any]]


class SemanticBenchmarkRun(BaseModel):
    """Result of evaluating catalog search against the governed benchmark."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    benchmark_id: str
    benchmark_ref: str
    benchmark_version: str
    catalog_corpus_kind: str
    closure_scope: str
    label_owner: str
    reviewer: str
    rule_version_ref: str
    construct_scope: str
    queries: list[str]
    returned_hits: list[dict[str, Any]]
    posture: str
    precision_at_5: float
    recall_at_known_seeds: float
    freshness_ok: bool
    missed_known_seeds: list[str]
    negative_controls_passed: list[str]
    threshold_disposition: Literal["pass", "fail"]


class SemanticAdequacyGate:
    """Evaluate construct/scope search adequacy against a governed benchmark."""

    def __init__(self, benchmark: GySemanticBenchmark | None = None) -> None:
        self._benchmark = benchmark or load_gy_semantic_benchmark()

    def evaluate(
        self,
        *,
        construct_scope: str,
        returned_hits: list[dict[str, Any]],
        posture: str = "pre_decision",
        freshness_ok: bool = True,
    ) -> SemanticBenchmarkRun:
        """Compute calibrated precision/recall and negative-control failures."""

        label = self._label_for(construct_scope)
        known = set(label.get("known_admissible_dataset_ids") or ())
        negatives = set(label.get("negative_control_dataset_ids") or ())
        accepted_hits = [
            hit
            for hit in returned_hits
            if float(hit.get("calibrated_relevance") or 0.0) >= 0.5
        ]
        top_hits = accepted_hits[:5]
        returned_ids = [
            str(hit.get("dataset_id") or hit.get("id") or "") for hit in accepted_hits
        ]
        top_ids = [str(hit.get("dataset_id") or hit.get("id") or "") for hit in top_hits]
        negative_controls_passed = [hit_id for hit_id in returned_ids if hit_id in negatives]
        known_returned = known.intersection(returned_ids)
        precision_at_5 = len(known.intersection(top_ids)) / len(top_ids) if top_ids else 0.0
        recall_at_known_seeds = len(known_returned) / len(known) if known else 1.0
        floors = self._benchmark.thresholds.get(posture) or self._benchmark.thresholds[
            "pre_decision"
        ]
        failed = bool(
            negative_controls_passed
            or precision_at_5 < floors["precision_at_5"]
            or recall_at_known_seeds < floors["recall_at_known_seeds"]
            or not freshness_ok
        )
        return SemanticBenchmarkRun(
            run_id=f"semantic-run-{_slug(construct_scope)}",
            benchmark_id=self._benchmark.benchmark_id,
            benchmark_ref="architecture/policy_design_case/layer3_gy_semantic_benchmark.json",
            benchmark_version=self._benchmark.schema_version,
            catalog_corpus_kind=self._benchmark.catalog_corpus_kind,
            closure_scope=self._benchmark.closure_scope,
            label_owner=self._benchmark.label_owner,
            reviewer=self._benchmark.reviewer,
            rule_version_ref=self._benchmark.provenance["rule_version"],
            construct_scope=construct_scope,
            queries=[str(label.get("construct_scope_query") or construct_scope)],
            returned_hits=returned_hits,
            posture=posture,
            precision_at_5=precision_at_5,
            recall_at_known_seeds=recall_at_known_seeds,
            freshness_ok=freshness_ok,
            missed_known_seeds=sorted(known - known_returned),
            negative_controls_passed=negative_controls_passed,
            threshold_disposition="fail" if failed else "pass",
        )

    def _label_for(self, construct_scope: str) -> dict[str, Any]:
        for label in self._benchmark.labels:
            if construct_scope in {
                label.get("fixture_id"),
                label.get("construct_scope"),
                label.get("construct_scope_query"),
            }:
                return label
        raise KeyError(construct_scope)


def load_gy_semantic_benchmark() -> GySemanticBenchmark:
    """Load the committed governed semantic benchmark artifact."""

    payload = json.loads(_semantic_benchmark_path().read_text(encoding="utf-8"))
    return GySemanticBenchmark.model_validate(payload)


def _semantic_benchmark_path() -> Path:
    return _repo_root() / "architecture/policy_design_case/layer3_gy_semantic_benchmark.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


class SemanticBindingError(ValueError):
    """Typed fail-closed semantic-binding contract violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class SemanticBindingIssue(BaseModel):
    """One scorecard-consumable semantic-binding issue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    severity: SemanticIssueSeverity = "fail"
    layer: str = Field(default="semantic_binding", min_length=1)
    phase: str = Field(default="semantic_binding", min_length=1)
    message: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    claim_id: str | None = None
    refs: tuple[str, ...] = Field(default=())
    missing_input: str | None = None
    conflicting_producer: str | None = None
    affected_claim: str | None = None
    next_command: str | None = None

    @field_validator("code", "layer", "phase", "message", "next_action")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "claim_id",
        "missing_input",
        "conflicting_producer",
        "affected_claim",
        "next_command",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("refs")
    @classmethod
    def _strip_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class ProducerSpineReadContext(BaseModel):
    """Read interface exposing previous-wave spine refs to producer code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.producer_spine_context.v1"]
    context_id: str = Field(min_length=1)
    concept_spine_ref: str = Field(min_length=1)
    jurisdiction_spine_ref: str = Field(min_length=1)
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    jurisdiction_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())
    period_refs: tuple[str, ...] = Field(default=())
    geography_refs: tuple[str, ...] = Field(default=())
    consumer_components: tuple[str, ...] = Field(default=PRODUCER_SPINE_CONSUMER_COMPONENTS)

    @field_validator("context_id", "concept_spine_ref", "jurisdiction_spine_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "canonical_concept_refs",
        "jurisdiction_refs",
        "unit_refs",
        "period_refs",
        "geography_refs",
        "consumer_components",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)

    @model_validator(mode="after")
    def _validate_consumers(self) -> ProducerSpineReadContext:
        unsupported = sorted(
            set(self.consumer_components) - set(PRODUCER_SPINE_CONSUMER_COMPONENTS)
        )
        if unsupported:
            raise ValueError(
                "consumer_components contains unsupported producer spine consumers: "
                + ", ".join(unsupported)
            )
        missing = sorted(set(PRODUCER_SPINE_CONSUMER_COMPONENTS) - set(self.consumer_components))
        if missing:
            raise ValueError(
                "consumer_components must expose every producer spine consumer: "
                + ", ".join(missing)
            )
        return self


class ProducerSpineBindingFields(BaseModel):
    """Common spine-consumer fields shared by producer binding records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consumed_concept_spine_ref: str | None = None
    consumed_jurisdiction_spine_ref: str | None = None
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    jurisdiction_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())
    period_refs: tuple[str, ...] = Field(default=())
    geography_refs: tuple[str, ...] = Field(default=())
    candidate_spine_binding_refs: tuple[str, ...] = Field(default=())
    spine_blocker_refs: tuple[str, ...] = Field(default=())
    local_labels: tuple[str, ...] = Field(default=())

    @field_validator("consumed_concept_spine_ref", "consumed_jurisdiction_spine_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator(
        "canonical_concept_refs",
        "jurisdiction_refs",
        "unit_refs",
        "period_refs",
        "geography_refs",
        "candidate_spine_binding_refs",
        "spine_blocker_refs",
        "local_labels",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class IntentBindingRecord(BaseModel):
    """How policy intent is canonicalized before evidence selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_intent_ref: str = Field(min_length=1)
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    jurisdiction: str = Field(min_length=1)
    time_context: str = Field(min_length=1)
    population: str = Field(min_length=1)
    intervention: str = Field(min_length=1)
    treatment: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    legal_domain: str = Field(min_length=1)
    data_source_family: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    columns: tuple[str, ...] = Field(default=())
    method_family: str = Field(min_length=1)
    final_claim: str = Field(min_length=1)
    monitoring_signal: str = Field(min_length=1)
    public_artifact_section: str = Field(min_length=1)

    @field_validator(
        "policy_intent_ref",
        "jurisdiction",
        "time_context",
        "population",
        "intervention",
        "treatment",
        "outcome",
        "legal_domain",
        "data_source_family",
        "dataset",
        "method_family",
        "final_claim",
        "monitoring_signal",
        "public_artifact_section",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("canonical_concept_refs", "columns")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class LexBindingRecord(ProducerSpineBindingFields):
    """Lex legal-query, candidate, selected, rejected, and blocker refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1)
    legal_query_terms: tuple[str, ...] = Field(default=())
    legal_query_refs: tuple[str, ...] = Field(default=())
    concept_refs: tuple[str, ...] = Field(default=())
    candidate_norm_refs: tuple[str, ...] = Field(default=())
    selected_norm_refs: tuple[str, ...] = Field(default=())
    rejected_norm_refs: tuple[str, ...] = Field(default=())
    legal_snapshot_refs: tuple[str, ...] = Field(default=())
    jurisdiction_filters: tuple[str, ...] = Field(default=())
    effective_date_filters: tuple[str, ...] = Field(default=())
    hierarchy_conflict_refs: tuple[str, ...] = Field(default=())
    competence_refs: tuple[str, ...] = Field(default=())
    no_norm_blocker_refs: tuple[str, ...] = Field(default=())
    retrieval_error_blocker_refs: tuple[str, ...] = Field(default=())
    legal_authority_required: bool = False
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    legal_authority_blocker_refs: tuple[str, ...] = Field(default=())
    legal_admissibility_grades: tuple[str, ...] = Field(default=())
    legal_authority_types: tuple[str, ...] = Field(default=())
    legal_window_segment_refs: tuple[str, ...] = Field(default=())
    jurisdiction_fallback_policy_refs: tuple[str, ...] = Field(default=())

    @field_validator("binding_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "legal_query_terms",
        "legal_query_refs",
        "concept_refs",
        "candidate_norm_refs",
        "selected_norm_refs",
        "rejected_norm_refs",
        "legal_snapshot_refs",
        "jurisdiction_filters",
        "effective_date_filters",
        "hierarchy_conflict_refs",
        "competence_refs",
        "no_norm_blocker_refs",
        "retrieval_error_blocker_refs",
        "legal_authority_record_refs",
        "legal_authority_blocker_refs",
        "legal_authority_types",
        "legal_window_segment_refs",
        "jurisdiction_fallback_policy_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)

    @field_validator("legal_admissibility_grades")
    @classmethod
    def _strip_grades(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            text
            for value in values
            for text in (_optional_text(value),)
            if text is not None
        )


class MetricBinding(BaseModel):
    """Metric-to-claim/source binding emitted by Fabric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(default=())
    source_refs: tuple[str, ...] = Field(default=())

    @field_validator("metric_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("claim_ids", "source_refs")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class ColumnBinding(BaseModel):
    """Column-level evidence for a claim and selected source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    column_refs: tuple[str, ...] = Field(default=())

    @field_validator("claim_id", "source_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("column_refs")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class CoverageBinding(BaseModel):
    """Claim/source coverage evidence emitted by Fabric."""

    model_config = ConfigDict(extra="allow", frozen=True)

    source_ref: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(default=())
    status: str = Field(default="covers", min_length=1)

    @field_validator("source_ref", "status")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("claim_ids")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)

    @property
    def covers_claim(self) -> bool:
        return self.status.casefold() in {"cover", "covers", "pass", "covered", "relevant"}


class SourceFacetBinding(BaseModel):
    """Field-level Fabric source evidence bound to a Data Forge snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref: str = Field(min_length=1)
    source_family: str = Field(min_length=1)
    source_rights: str = Field(min_length=1)
    dataset_ref: str = Field(min_length=1)
    dictionary_ref: str = Field(min_length=1)
    schema_ref: str = Field(min_length=1)
    field_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())
    geography_refs: tuple[str, ...] = Field(default=())
    time_coverage_refs: tuple[str, ...] = Field(default=())
    quality_refs: tuple[str, ...] = Field(default=())
    missingness_refs: tuple[str, ...] = Field(default=())
    freshness_refs: tuple[str, ...] = Field(default=())
    lineage_refs: tuple[str, ...] = Field(default=())
    transformation_refs: tuple[str, ...] = Field(default=())
    data_forge_snapshot_refs: tuple[str, ...] = Field(default=())
    selected_candidate_ref: str | None = None
    rejected_candidate_refs: tuple[str, ...] = Field(default=())

    @field_validator(
        "source_ref",
        "source_family",
        "source_rights",
        "dataset_ref",
        "dictionary_ref",
        "schema_ref",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("selected_candidate_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator(
        "field_refs",
        "unit_refs",
        "geography_refs",
        "time_coverage_refs",
        "quality_refs",
        "missingness_refs",
        "freshness_refs",
        "lineage_refs",
        "transformation_refs",
        "data_forge_snapshot_refs",
        "rejected_candidate_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class DerivedFeatureBinding(BaseModel):
    """Derived Fabric feature bound to source facets and claim-support refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_facet_refs: tuple[str, ...] = Field(default=())
    claim_ids: tuple[str, ...] = Field(default=())
    claim_support_feature_refs: tuple[str, ...] = Field(default=())
    lineage_refs: tuple[str, ...] = Field(default=())
    transformation_refs: tuple[str, ...] = Field(default=())

    @field_validator("feature_ref", "source_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "source_facet_refs",
        "claim_ids",
        "claim_support_feature_refs",
        "lineage_refs",
        "transformation_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class FabricBindingRecord(ProducerSpineBindingFields):
    """Fabric dataset/source, metric, column, unit, geo, time, and lineage refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1)
    candidate_dataset_source_refs: tuple[str, ...] = Field(default=())
    selected_dataset_source_refs: tuple[str, ...] = Field(default=())
    rejected_dataset_source_refs: tuple[str, ...] = Field(default=())
    metric_bindings: tuple[MetricBinding, ...] = Field(default=())
    column_bindings: tuple[ColumnBinding, ...] = Field(default=())
    unit_bindings: tuple[dict[str, Any], ...] = Field(default=())
    geography_bindings: tuple[dict[str, Any], ...] = Field(default=())
    calendar_time_bindings: tuple[dict[str, Any], ...] = Field(default=())
    source_freshness: tuple[dict[str, Any], ...] = Field(default=())
    data_coverage: tuple[CoverageBinding, ...] = Field(default=())
    dictionary_refs: tuple[str, ...] = Field(default=())
    lineage_refs: tuple[str, ...] = Field(default=())
    data_forge_snapshot_refs: tuple[str, ...] = Field(default=())
    source_facets: tuple[SourceFacetBinding, ...] = Field(default=())
    derived_features: tuple[DerivedFeatureBinding, ...] = Field(default=())
    claim_support_feature_refs: tuple[str, ...] = Field(default=())
    data_gap_blocker_refs: tuple[str, ...] = Field(default=())
    ambiguity_blocker_refs: tuple[str, ...] = Field(default=())

    @field_validator("binding_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "candidate_dataset_source_refs",
        "selected_dataset_source_refs",
        "rejected_dataset_source_refs",
        "dictionary_refs",
        "lineage_refs",
        "data_forge_snapshot_refs",
        "claim_support_feature_refs",
        "data_gap_blocker_refs",
        "ambiguity_blocker_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)

    @field_validator(
        "unit_bindings",
        "geography_bindings",
        "calendar_time_bindings",
        "source_freshness",
    )
    @classmethod
    def _strip_mapping_tuple(cls, values: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
        return _coerce_mapping_tuple(values)


class ScholarBindingRecord(ProducerSpineBindingFields):
    """Scholar literature selection, support/conflict, and blocker refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1)
    candidate_literature_refs: tuple[str, ...] = Field(default=())
    selected_literature_refs: tuple[str, ...] = Field(default=())
    rejected_literature_refs: tuple[str, ...] = Field(default=())
    support_link_refs: tuple[str, ...] = Field(default=())
    conflict_link_refs: tuple[str, ...] = Field(default=())
    retrieval_blocker_refs: tuple[str, ...] = Field(default=())

    @field_validator("binding_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "candidate_literature_refs",
        "selected_literature_refs",
        "rejected_literature_refs",
        "support_link_refs",
        "conflict_link_refs",
        "retrieval_blocker_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class FoundryBindingRecord(ProducerSpineBindingFields):
    """Foundry method selection, diagnostics, assumptions, and blocker refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1)
    selected_method_refs: tuple[str, ...] = Field(default=())
    rejected_method_refs: tuple[str, ...] = Field(default=())
    rejected_method_reasons: tuple[dict[str, Any], ...] = Field(default=())
    scenario_method_expectation_refs: tuple[str, ...] = Field(default=())
    assumptions: tuple[str, ...] = Field(default=())
    assumption_gate_refs: tuple[str, ...] = Field(default=())
    runtime_assumption_gates: tuple[dict[str, Any], ...] = Field(default=())
    input_coverage: tuple[dict[str, Any], ...] = Field(default=())
    sample_power_adequacy: tuple[dict[str, Any], ...] = Field(default=())
    placebo_negative_control_refs: tuple[str, ...] = Field(default=())
    sensitivity_refs: tuple[str, ...] = Field(default=())
    uncertainty_refs: tuple[str, ...] = Field(default=())
    uncertainty_envelopes: tuple[dict[str, Any], ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    simulation_assumption_lineage_refs: tuple[str, ...] = Field(default=())
    method_output_refs: tuple[str, ...] = Field(default=())
    method_incompatibility_blocker_refs: tuple[str, ...] = Field(default=())

    @field_validator("binding_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "selected_method_refs",
        "rejected_method_refs",
        "scenario_method_expectation_refs",
        "assumptions",
        "assumption_gate_refs",
        "placebo_negative_control_refs",
        "sensitivity_refs",
        "uncertainty_refs",
        "limitation_refs",
        "simulation_assumption_lineage_refs",
        "method_output_refs",
        "method_incompatibility_blocker_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)

    @field_validator(
        "rejected_method_reasons",
        "runtime_assumption_gates",
        "input_coverage",
        "sample_power_adequacy",
        "uncertainty_envelopes",
    )
    @classmethod
    def _strip_mapping_tuple(cls, values: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
        return _coerce_mapping_tuple(values)


class ClaimEvidencePath(BaseModel):
    """Per-material-claim closure from scenario obligations to final claim support."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    claim_type: str | None = None
    claim_family: str | None = None
    claim_use: str | None = None
    scenario_requirement_refs: tuple[str, ...] = Field(default=())
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    fabric_binding_refs: tuple[str, ...] = Field(default=())
    source_refs: tuple[str, ...] = Field(default=())
    column_refs: tuple[str, ...] = Field(default=())
    lex_binding_refs: tuple[str, ...] = Field(default=())
    selected_norm_refs: tuple[str, ...] = Field(default=())
    foundry_binding_refs: tuple[str, ...] = Field(default=())
    selected_method_refs: tuple[str, ...] = Field(default=())
    method_output_refs: tuple[str, ...] = Field(default=())
    assumption_gate_refs: tuple[str, ...] = Field(default=())
    uncertainty_refs: tuple[str, ...] = Field(default=())
    scientist_claim_refs: tuple[str, ...] = Field(default=())
    argument_refs: tuple[str, ...] = Field(default=())
    warrant_refs: tuple[str, ...] = Field(default=())
    rebuttal_refs: tuple[str, ...] = Field(default=())
    counter_evidence_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    baseline_refs: tuple[str, ...] = Field(default=())
    alternative_refs: tuple[str, ...] = Field(default=())
    comparison_refs: tuple[str, ...] = Field(default=())

    @field_validator("claim_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("claim_type", "claim_family", "claim_use")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator(
        "scenario_requirement_refs",
        "canonical_concept_refs",
        "fabric_binding_refs",
        "source_refs",
        "column_refs",
        "lex_binding_refs",
        "selected_norm_refs",
        "foundry_binding_refs",
        "selected_method_refs",
        "method_output_refs",
        "assumption_gate_refs",
        "uncertainty_refs",
        "scientist_claim_refs",
        "argument_refs",
        "warrant_refs",
        "rebuttal_refs",
        "counter_evidence_refs",
        "limitation_refs",
        "blocker_refs",
        "baseline_refs",
        "alternative_refs",
        "comparison_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


class ClaimBindingRecord(ProducerSpineBindingFields):
    """Scientist/final-compiler claim-to-required-evidence binding refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1)
    major_claim_ids: tuple[str, ...] = Field(default=())
    recommendation_ids: tuple[str, ...] = Field(default=())
    legal_assertion_ids: tuple[str, ...] = Field(default=())
    budget_feasibility_ids: tuple[str, ...] = Field(default=())
    distributional_impact_ids: tuple[str, ...] = Field(default=())
    implementation_risk_ids: tuple[str, ...] = Field(default=())
    monitoring_ids: tuple[str, ...] = Field(default=())
    residual_uncertainty_ids: tuple[str, ...] = Field(default=())
    required_data_refs: tuple[str, ...] = Field(default=())
    required_method_refs: tuple[str, ...] = Field(default=())
    required_norm_refs: tuple[str, ...] = Field(default=())
    required_literature_refs: tuple[str, ...] = Field(default=())
    required_uncertainty_refs: tuple[str, ...] = Field(default=())
    required_blocker_refs: tuple[str, ...] = Field(default=())
    public_artifact_section_refs: tuple[str, ...] = Field(default=())
    claim_evidence_paths: tuple[ClaimEvidencePath, ...] = Field(default=())

    @field_validator("binding_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "major_claim_ids",
        "recommendation_ids",
        "legal_assertion_ids",
        "budget_feasibility_ids",
        "distributional_impact_ids",
        "implementation_risk_ids",
        "monitoring_ids",
        "residual_uncertainty_ids",
        "required_data_refs",
        "required_method_refs",
        "required_norm_refs",
        "required_literature_refs",
        "required_uncertainty_refs",
        "required_blocker_refs",
        "public_artifact_section_refs",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)

    @property
    def claim_ids(self) -> tuple[str, ...]:
        ids = [
            *self.major_claim_ids,
            *self.recommendation_ids,
            *self.legal_assertion_ids,
            *self.budget_feasibility_ids,
            *self.distributional_impact_ids,
            *self.implementation_risk_ids,
            *self.monitoring_ids,
            *self.residual_uncertainty_ids,
        ]
        return tuple(dict.fromkeys(ids))


class SemanticBindingLedger(BaseModel):
    """Runtime-owned semantic lineage between intent, evidence, and claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.semantic_binding_ledger.v1"]
    semantic_binding_ref: str = Field(min_length=1)
    status: SemanticBindingStatus = "pass"
    runtime_report_status: RuntimeReportStatus | None = None
    policy_intent_ref: str = Field(min_length=1)
    spine_context: ProducerSpineReadContext | None = None
    producer_handshake_ledger: Mapping[str, Any] | None = None
    hypothesis_ledger: Mapping[str, Any] | None = None
    intent: IntentBindingRecord
    lex: tuple[LexBindingRecord, ...] = Field(default=())
    fabric: tuple[FabricBindingRecord, ...] = Field(default=())
    scholar: tuple[ScholarBindingRecord, ...] = Field(default=())
    foundry: tuple[FoundryBindingRecord, ...] = Field(default=())
    scientist: tuple[ClaimBindingRecord, ...] = Field(default=())
    final_compiler: tuple[ClaimBindingRecord, ...] = Field(default=())
    authority_envelope: Mapping[str, Any] | None = None
    schema_compatibility: Mapping[str, Any] | None = None
    same_input_closure_ref: str | None = None
    effective_mode_ref: str | None = None
    degradation_ledger_ref: str | None = None
    projection_boundaries_ref: str | None = None
    runtime_event_ref: str | None = None
    diagnostic_event_ref: str | None = None
    cas_artifact_refs: Mapping[str, Any] | None = None
    issues: tuple[SemanticBindingIssue, ...] = Field(default=())
    blocking_issue_count: int = 0
    semantic_closure: Mapping[str, Any] | None = None

    @field_validator("semantic_binding_ref", "policy_intent_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("runtime_report_status", mode="before")
    @classmethod
    def _normalize_runtime_report_status(cls, value: object) -> str | None:
        text = _optional_text(value)
        if text is None:
            return None
        normalized = text.casefold().replace("-", "_")
        if normalized in {"pass", "passed", "ok", "success"}:
            return "pass"
        if normalized in {"block", "blocked"}:
            return "blocked"
        if normalized in {"fail", "failed", "error"}:
            return "fail"
        if normalized in {"warn", "warning"}:
            return "warn"
        if normalized in {"degraded", "degrade"}:
            return "degraded"
        raise ValueError(f"unsupported runtime_report_status: {text}")

    @model_validator(mode="after")
    def _validate_policy_intent_identity(self) -> SemanticBindingLedger:
        if self.intent.policy_intent_ref != self.policy_intent_ref:
            raise ValueError("intent.policy_intent_ref must match policy_intent_ref")
        return self


class SemanticBindingEvaluation(BaseModel):
    """Evaluation result consumed by scorecard/readiness readers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: SemanticBindingStatus
    reason_family: Literal[
        "complete",
        "binding_failure",
        "retrieval_failure",
        "no_relevant_evidence",
    ]
    issues: tuple[SemanticBindingIssue, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    selected_evidence_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())


SemanticBindingLedgerInput = SemanticBindingLedger | Mapping[str, Any]


def build_producer_spine_read_context(
    *,
    concept_spine: Mapping[str, Any] | None = None,
    jurisdiction_spine: Mapping[str, Any] | None = None,
    concept_spine_ref: str | None = None,
    jurisdiction_spine_ref: str | None = None,
    canonical_concept_refs: Sequence[str] | None = None,
    jurisdiction_refs: Sequence[str] | None = None,
    unit_refs: Sequence[str] | None = None,
    period_refs: Sequence[str] | None = None,
    geography_refs: Sequence[str] | None = None,
    context_id: str | None = None,
) -> dict[str, Any]:
    """Build the read context Lex/Fabric/Scholar/Foundry/Scientist/compiler consume."""

    concept_ref = _first_text(
        concept_spine_ref,
        _spine_ref_from_mapping(concept_spine, "concept_ref", "cas_ref"),
    )
    jurisdiction_ref = _first_text(
        jurisdiction_spine_ref,
        _spine_ref_from_mapping(jurisdiction_spine, "jurisdiction_spine_ref", "cas_ref"),
    )
    if concept_ref == "unbound":
        raise SemanticBindingError(
            "semantic_concept_spine_ref_missing",
            "Producer spine read context requires concept_spine_ref.",
        )
    if jurisdiction_ref == "unbound":
        raise SemanticBindingError(
            "semantic_jurisdiction_spine_ref_missing",
            "Producer spine read context requires jurisdiction_spine_ref.",
        )
    concepts = tuple(
        dict.fromkeys(
            [
                *(canonical_concept_refs or ()),
                *_refs_from_value(
                    (concept_spine or {}).get("canonical_concept_ids")
                    if isinstance(concept_spine, Mapping)
                    else None
                ),
            ]
        )
    )
    jurisdictions = tuple(
        dict.fromkeys(
            [
                *(jurisdiction_refs or ()),
                *_jurisdiction_refs_from_spine(jurisdiction_spine),
            ]
        )
    )
    units = tuple(
        dict.fromkeys(
            [
                *(unit_refs or ()),
                *_concept_spine_semantic_refs(concept_spine, "units", "unit_refs"),
            ]
        )
    )
    periods = tuple(
        dict.fromkeys(
            [
                *(period_refs or ()),
                *_concept_spine_semantic_refs(concept_spine, "time", "period_refs"),
            ]
        )
    )
    geographies = tuple(
        dict.fromkeys(
            [
                *(geography_refs or ()),
                *_concept_spine_semantic_refs(
                    concept_spine,
                    "geography",
                    "geography_refs",
                ),
            ]
        )
    )
    payload = {
        "schema_version": PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
        "context_id": context_id
        or _stable_ref(
            {
                "concept_spine_ref": concept_ref,
                "jurisdiction_spine_ref": jurisdiction_ref,
                "canonical_concept_refs": concepts,
                "jurisdiction_refs": jurisdictions,
                "unit_refs": units,
                "period_refs": periods,
                "geography_refs": geographies,
            }
        ),
        "concept_spine_ref": concept_ref,
        "jurisdiction_spine_ref": jurisdiction_ref,
        "canonical_concept_refs": concepts,
        "jurisdiction_refs": jurisdictions,
        "unit_refs": units,
        "period_refs": periods,
        "geography_refs": geographies,
        "consumer_components": PRODUCER_SPINE_CONSUMER_COMPONENTS,
    }
    return ProducerSpineReadContext.model_validate(payload).model_dump(mode="json")


def producer_spine_read_context_for(
    component: str,
    context: ProducerSpineReadContext | Mapping[str, Any],
) -> dict[str, Any]:
    """Return the stable per-producer view of the shared spine read context."""

    validated = (
        context
        if isinstance(context, ProducerSpineReadContext)
        else ProducerSpineReadContext.model_validate(dict(context))
    )
    consumer = _non_empty(component)
    if consumer not in validated.consumer_components:
        raise SemanticBindingError(
            "semantic_spine_consumer_unsupported",
            f"{consumer} is not listed as a spine consumer.",
        )
    return {
        "schema_version": PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
        "consumer_component": consumer,
        "context_id": validated.context_id,
        "concept_spine_ref": validated.concept_spine_ref,
        "jurisdiction_spine_ref": validated.jurisdiction_spine_ref,
        "canonical_concept_refs": validated.canonical_concept_refs,
        "jurisdiction_refs": validated.jurisdiction_refs,
        "unit_refs": validated.unit_refs,
        "period_refs": validated.period_refs,
        "geography_refs": validated.geography_refs,
    }


def build_producer_spine_binding_fields(
    *,
    component: str,
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
    candidate_refs: Sequence[Any] | None = None,
    blocker_refs: Sequence[Any] | None = None,
    local_labels: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build the required spine-consumer fields for a producer report."""

    return _spine_fields_from_report(
        {"local_labels": tuple(_refs_from_value(local_labels))},
        spine_context,
        component=component,
        candidate_refs=tuple(_refs_from_value(candidate_refs)),
        blocker_refs=tuple(_refs_from_value(blocker_refs)),
    )


def build_semantic_binding_ledger(
    *,
    policy_intent: Mapping[str, Any] | None = None,
    runtime_refs: Mapping[str, Any] | None = None,
    normative_evidence: Mapping[str, Any] | None = None,
    fabric_retrieval_trace: Mapping[str, Any] | None = None,
    data_forge_snapshot_binding: Mapping[str, Any] | None = None,
    scholar_evidence: Mapping[str, Any] | None = None,
    foundry_method_report: Mapping[str, Any] | None = None,
    policy_grounding_matrix: Mapping[str, Any] | None = None,
    decision_artifact_contract: Mapping[str, Any] | None = None,
    final_claims: Sequence[Mapping[str, Any]] | None = None,
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None = None,
    semantic_binding_ref: str | None = None,
) -> dict[str, Any]:
    """Build a runtime-owned semantic binding ledger from closeout reports.

    The builder is intentionally conservative: it preserves available
    candidate/selected/rejected/blocker refs and leaves missing authority as
    empty fields so the existing evaluator can fail closed.
    """

    runtime_ref_map = dict(runtime_refs or {})
    lex_report = dict(normative_evidence or {})
    fabric_report = dict(fabric_retrieval_trace or {})
    scholar_report = dict(scholar_evidence or {})
    foundry_report = dict(foundry_method_report or {})
    grounding_report = dict(policy_grounding_matrix or {})
    decision_contract = dict(decision_artifact_contract or {})
    claims = _claim_rows(final_claims=final_claims, grounding_report=grounding_report)
    policy_intent_ref = (
        _optional_text(runtime_ref_map.get("policy_intent_ref"))
        or _optional_text(runtime_ref_map.get("request_ref"))
        or _stable_ref(
            {
                "policy_intent": dict(policy_intent or {}),
                "claims": claims,
                "lex": lex_report,
                "fabric": fabric_report,
            }
        )
    )
    intent = _build_intent_record(
        policy_intent=dict(policy_intent or {}),
        policy_intent_ref=policy_intent_ref,
        lex_report=lex_report,
        fabric_report=fabric_report,
        foundry_report=foundry_report,
        claims=claims,
    )
    spine = _producer_spine_context_from_inputs(
        spine_context=spine_context,
        runtime_refs=runtime_ref_map,
        policy_intent=dict(policy_intent or {}),
    )
    lex = _build_lex_record(lex_report=lex_report, claims=claims, spine_context=spine)
    fabric = _build_fabric_record(
        fabric_report=fabric_report,
        data_forge_snapshot_binding=dict(data_forge_snapshot_binding or {}),
        claims=claims,
        intent=intent,
        spine_context=spine,
    )
    scholar = _build_scholar_record(
        scholar_report=scholar_report,
        claims=claims,
        spine_context=spine,
    )
    foundry = _build_foundry_record(
        foundry_report=foundry_report,
        claims=claims,
        spine_context=spine,
    )
    scientist = _build_claim_binding_record(
        binding_id="scientist-binding-runtime",
        claims=claims,
        decision_contract=decision_contract,
        lex_bindings=(lex,),
        fabric_bindings=(fabric,),
        foundry_bindings=(foundry,),
        final_compiler=False,
        spine_context=spine,
    )
    final_compiler = _build_claim_binding_record(
        binding_id="final-compiler-binding-runtime",
        claims=claims,
        decision_contract=decision_contract,
        lex_bindings=(lex,),
        fabric_bindings=(fabric,),
        foundry_bindings=(foundry,),
        final_compiler=True,
        spine_context=spine,
    )
    status: SemanticBindingStatus = (
        "blocked"
        if lex["no_norm_blocker_refs"]
        or lex["retrieval_error_blocker_refs"]
        or fabric["data_gap_blocker_refs"]
        or fabric["ambiguity_blocker_refs"]
        or scholar["retrieval_blocker_refs"]
        or foundry["method_incompatibility_blocker_refs"]
        or scientist["required_blocker_refs"]
        or final_compiler["required_blocker_refs"]
        else "pass"
    )
    payload = {
        "schema_version": SEMANTIC_BINDING_SCHEMA_VERSION,
        "semantic_binding_ref": semantic_binding_ref or "pending",
        "status": status,
        "policy_intent_ref": policy_intent_ref,
        "spine_context": spine,
        "intent": intent,
        "lex": [lex],
        "fabric": [fabric],
        "scholar": [scholar],
        "foundry": [foundry],
        "scientist": [scientist],
        "final_compiler": [final_compiler],
    }
    return close_semantic_binding_ledger(payload)


def close_semantic_binding_ledger(
    ledger: SemanticBindingLedgerInput,
) -> dict[str, Any]:
    """Apply reader semantic closure to the producer ledger payload."""

    payload = deserialize_semantic_binding_ledger(ledger).model_dump(mode="json")
    evaluation = evaluate_semantic_binding_ledger(payload)
    closed_status = _producer_semantic_status(
        evaluation=evaluation,
        existing_status=str(payload.get("status") or "pass"),
    )
    issue_payloads = [issue.model_dump(mode="json") for issue in evaluation.issues]
    payload["status"] = closed_status
    payload["runtime_report_status"] = closed_status
    payload["issues"] = issue_payloads
    payload["blocking_issue_count"] = sum(
        1 for issue in issue_payloads if issue.get("severity") == "fail"
    )
    payload["semantic_closure"] = {
        "status": evaluation.status,
        "reason_family": evaluation.reason_family,
        "issue_codes": sorted(
            {
                str(issue.get("code"))
                for issue in issue_payloads
                if str(issue.get("code") or "").strip()
            }
        ),
        "selected_evidence_refs": list(evaluation.selected_evidence_refs),
        "rejected_candidate_refs": list(evaluation.rejected_candidate_refs),
        "blocker_refs": list(evaluation.blocker_refs),
    }
    if payload.get("semantic_binding_ref") in {"", "pending", None}:
        payload["semantic_binding_ref"] = _stable_ref(
            {key: value for key, value in payload.items() if key != "semantic_binding_ref"}
        )
    return SemanticBindingLedger.model_validate(payload).model_dump(mode="json")


def _producer_semantic_status(
    *,
    evaluation: SemanticBindingEvaluation,
    existing_status: str,
) -> SemanticBindingStatus:
    if evaluation.issues or evaluation.status == "fail":
        return "fail"
    if (
        evaluation.status == "blocked"
        or existing_status.strip().casefold() in {"blocked", "block"}
    ):
        return "blocked"
    return "pass"


def deserialize_semantic_binding_ledger(
    ledger: SemanticBindingLedgerInput,
) -> SemanticBindingLedger:
    """Deserialize and validate one semantic binding ledger."""

    if isinstance(ledger, SemanticBindingLedger):
        return ledger
    if isinstance(ledger, Mapping):
        return SemanticBindingLedger.model_validate(dict(ledger))
    raise TypeError("semantic binding ledger must be a mapping or model")


def evaluate_semantic_binding_ledger(
    ledger: SemanticBindingLedgerInput,
) -> SemanticBindingEvaluation:
    """Evaluate semantic relevance, selection authority, and typed blockers."""

    validated = deserialize_semantic_binding_ledger(ledger)
    issues: list[SemanticBindingIssue] = []
    issues.extend(_record_presence_issues(validated))
    issues.extend(_producer_handshake_ledger_issues(validated))
    issues.extend(_lex_selection_issues(validated))
    issues.extend(_fabric_selection_issues(validated))
    issues.extend(_fabric_lineage_issues(validated))
    issues.extend(_fabric_false_pass_issues(validated))
    issues.extend(_scholar_selection_issues(validated))
    issues.extend(_claim_coverage_issues(validated))
    issues.extend(_claim_evidence_closure_issues(validated))
    issues.extend(_candidate_firewall_semantic_issues(validated))
    issues.extend(_producer_spine_binding_issues(validated))
    issues.extend(_final_claim_spine_ref_issues(validated))
    issues.extend(_generic_collapse_issues(validated))
    issues = _dedupe_issues(issues)

    rejected_candidate_refs = tuple(
        sorted(
            {
                *(ref for lex in validated.lex for ref in lex.rejected_norm_refs),
                *(
                    ref
                    for fabric in validated.fabric
                    for ref in fabric.rejected_dataset_source_refs
                ),
                *(ref for scholar in validated.scholar for ref in scholar.rejected_literature_refs),
                *(ref for foundry in validated.foundry for ref in foundry.rejected_method_refs),
            }
        )
    )
    selected_evidence_refs = tuple(
        sorted(
            {
                *(ref for lex in validated.lex for ref in lex.selected_norm_refs),
                *(ref for lex in validated.lex for ref in lex.legal_authority_record_refs),
                *(
                    ref
                    for fabric in validated.fabric
                    for ref in fabric.selected_dataset_source_refs
                ),
                *(ref for scholar in validated.scholar for ref in scholar.selected_literature_refs),
                *(ref for foundry in validated.foundry for ref in foundry.selected_method_refs),
            }
        )
    )
    blocker_refs = _blocker_refs(validated)
    reason_family = _reason_family(
        ledger=validated,
        issues=issues,
        blocker_refs=blocker_refs,
    )
    if issues:
        status: SemanticBindingStatus = "fail"
    elif (
        blocker_refs
        or validated.status == "blocked"
        or validated.runtime_report_status == "blocked"
    ):
        status = "blocked"
    else:
        status = "pass"
    return SemanticBindingEvaluation(
        status=status,
        reason_family=reason_family,
        issues=tuple(issues),
        rejected_candidate_refs=rejected_candidate_refs,
        selected_evidence_refs=selected_evidence_refs,
        blocker_refs=blocker_refs,
    )


def authority_envelopes_missing_semantic_binding_ref(
    *,
    ledger: SemanticBindingLedger,
    quality_evidence: Mapping[str, Any],
    report_keys: Sequence[str],
) -> tuple[SemanticBindingIssue, ...]:
    """Return envelope wiring issues for reports that should point at the ledger."""

    issues: list[SemanticBindingIssue] = []
    expected_ref = ledger.semantic_binding_ref
    for report_key in report_keys:
        report = quality_evidence.get(report_key)
        if not isinstance(report, Mapping):
            continue
        envelope = report.get("authority_envelope")
        if not isinstance(envelope, Mapping):
            continue
        actual_ref = _optional_text(envelope.get("semantic_binding_ref"))
        if actual_ref is None:
            issues.append(
                _issue(
                    "semantic_binding_ref_missing",
                    "Authority envelope is missing semantic_binding_ref.",
                    next_action=(
                        "Wire the runtime semantic binding ledger ref into this evidence envelope."
                    ),
                    refs=(report_key,),
                )
            )
        elif actual_ref != expected_ref:
            issues.append(
                _issue(
                    "semantic_binding_ref_mismatch",
                    "Authority envelope semantic_binding_ref does not match the ledger ref.",
                    next_action=(
                        "Regenerate the evidence envelope from the same semantic binding ledger."
                    ),
                    refs=(report_key, actual_ref, expected_ref),
                )
            )
    return tuple(issues)


def _candidate_firewall_semantic_issues(
    ledger: SemanticBindingLedger,
) -> list[SemanticBindingIssue]:
    hypothesis_ledger = ledger.hypothesis_ledger
    if hypothesis_ledger is None:
        return []
    issues: list[SemanticBindingIssue] = []
    for binding in (*ledger.scientist, *ledger.final_compiler):
        for path in binding.claim_evidence_paths:
            slot_payloads = (
                (
                    "legal_authority",
                    {"selected_norm_refs": path.selected_norm_refs},
                ),
                (
                    "data_authority",
                    {
                        "source_refs": path.source_refs,
                        "column_refs": path.column_refs,
                    },
                ),
                (
                    "method_authority",
                    {
                        "selected_method_refs": path.selected_method_refs,
                        "method_output_refs": path.method_output_refs,
                    },
                ),
                (
                    "claim_authority",
                    {"scientist_claim_refs": path.scientist_claim_refs},
                ),
                (
                    "closeout_authority",
                    {"blocker_refs": path.blocker_refs},
                ),
            )
            for authority_slot, payload in slot_payloads:
                for issue in candidate_firewall_issues_for_payload(
                    payload,
                    hypothesis_ledger=hypothesis_ledger,
                    authority_slots=(authority_slot,),
                    surface="semantic_binding",
                ):
                    issues.append(
                        SemanticBindingIssue(
                            code=str(issue["code"]),
                            severity="fail",
                            layer="candidate_firewall",
                            phase="semantic_binding",
                            message=str(issue["message"]),
                            next_action=str(issue["next_action"]),
                            claim_id=path.claim_id,
                            refs=tuple(
                                ref
                                for key in ("candidate_ref", "candidate_id")
                                for ref in (_optional_text(issue.get(key)),)
                                if ref is not None
                            ),
                            missing_input=str(issue.get("authority_slot") or authority_slot),
                            affected_claim=path.claim_id,
                            next_command=(
                                "uv run pytest "
                                "tests/unit/runtime/quality/"
                                "test_hypothesis_ledger_candidate_firewall.py "
                                "tests/unit/runtime/quality/test_semantic_binding.py -q"
                            ),
                        )
                    )
    return issues


def _build_intent_record(
    *,
    policy_intent: Mapping[str, Any],
    policy_intent_ref: str,
    lex_report: Mapping[str, Any],
    fabric_report: Mapping[str, Any],
    foundry_report: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    target = _mapping_value(lex_report, "target_context")
    query_intent = _mapping_value(fabric_report, "query_intent")
    selected_sources = _selected_source_refs(fabric_report)
    candidate_sources = _candidate_source_refs(fabric_report)
    dataset = _first_text(
        policy_intent.get("dataset"),
        *(selected_sources or candidate_sources),
        "unbound_dataset",
    )
    first_claim = _first_claim_id(claims)
    return {
        "policy_intent_ref": policy_intent_ref,
        "canonical_concept_refs": _refs_from(policy_intent, "canonical_concept_refs"),
        "jurisdiction": _first_text(
            policy_intent.get("jurisdiction"),
            target.get("jurisdiction"),
            "unbound_jurisdiction",
        ),
        "time_context": _first_text(
            policy_intent.get("time_context"),
            target.get("as_of"),
            target.get("effective_date"),
            "unbound_time_context",
        ),
        "population": _first_text(policy_intent.get("population"), "unbound_population"),
        "intervention": _first_text(
            policy_intent.get("intervention"),
            query_intent.get("query_intervention"),
            query_intent.get("query_treatment"),
            "unbound_intervention",
        ),
        "treatment": _first_text(
            policy_intent.get("treatment"),
            query_intent.get("query_treatment"),
            "unbound_treatment",
        ),
        "outcome": _first_text(
            policy_intent.get("outcome"),
            query_intent.get("query_outcome"),
            _first_claim_text(claims),
            "unbound_outcome",
        ),
        "legal_domain": _first_text(
            policy_intent.get("legal_domain"),
            target.get("policy_domain"),
            query_intent.get("policy_domain"),
            "unbound_legal_domain",
        ),
        "data_source_family": _first_text(
            policy_intent.get("data_source_family"),
            _first_candidate_field(fabric_report, "source_family"),
            "unbound_data_source_family",
        ),
        "dataset": dataset,
        "columns": tuple(
            dict.fromkeys(
                [
                    *_refs_from(policy_intent, "columns"),
                    *_candidate_columns(fabric_report, dataset),
                ]
            )
        ),
        "method_family": _first_text(
            policy_intent.get("method_family"),
            _first_selected_method_field(foundry_report, "method_family"),
            "unbound_method_family",
        ),
        "final_claim": first_claim or "unbound_final_claim",
        "monitoring_signal": _first_text(
            policy_intent.get("monitoring_signal"),
            query_intent.get("query_outcome"),
            "unbound_monitoring_signal",
        ),
        "public_artifact_section": _first_text(
            policy_intent.get("public_artifact_section"),
            "recommendations" if first_claim else "unbound_public_section",
        ),
    }


def _build_lex_record(
    *,
    lex_report: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
) -> dict[str, Any]:
    selected = tuple(
        dict.fromkeys(
            [
                *_norm_refs_from_rows(lex_report.get("applied_norms")),
                *_norm_refs_from_rows(lex_report.get("selected_norms")),
            ]
        )
    )
    claim_norms = _refs_from_claims(claims, "norm_refs")
    if not selected:
        selected = claim_norms
    candidate = tuple(
        dict.fromkeys(
            [
                *_norm_refs_from_rows(lex_report.get("candidate_norms")),
                *selected,
                *_norm_refs_from_rows(lex_report.get("applied_norms")),
            ]
        )
    )
    authority_blockers = _blocker_ref_tuple(lex_report, "authority_blockers", "blockers")
    typed_retrieval_blockers = _authority_blocker_refs_by_family(
        lex_report,
        {"retrieval_failure", "missing_store"},
    )
    typed_no_norm_blockers = _authority_blocker_refs_by_family(
        lex_report,
        {"no_relevant_norm_found"},
    )
    blockers = typed_no_norm_blockers or tuple(
        ref for ref in authority_blockers if ref not in typed_retrieval_blockers
    )
    retrieval_blockers = _blocker_ref_tuple(
        lex_report,
        "retrieval_error_blocker_refs",
        "retrieval_errors",
    )
    target = _mapping_value(lex_report, "target_context")
    spine_fields = _spine_fields_from_report(
        lex_report,
        spine_context,
        component="lex",
        candidate_refs=candidate,
        blocker_refs=(*blockers, *retrieval_blockers, *typed_retrieval_blockers),
    )
    legal_authority_fields = _lex_legal_authority_fields(lex_report)
    return {
        "binding_id": "lex-binding-runtime",
        "legal_query_terms": _refs_from(
            lex_report,
            "query_terms",
            "legal_query_terms",
            "queries",
        ),
        "legal_query_refs": _refs_from(
            lex_report,
            "legal_query_refs",
            "query_refs",
            "normative_query_refs",
        ),
        "concept_refs": _refs_from(
            lex_report,
            "concept_refs",
            "canonical_concept_refs",
            "legal_concept_refs",
        ),
        "candidate_norm_refs": candidate,
        "selected_norm_refs": selected,
        "rejected_norm_refs": _norm_refs_from_rows(lex_report.get("rejected_norms")),
        "legal_snapshot_refs": _refs_from(
            lex_report,
            "legal_corpus_snapshot",
            "legal_snapshot_refs",
            "snapshot_refs",
            "source_refs",
        ),
        "jurisdiction_filters": tuple(
            dict.fromkeys(
                [
                    *_refs_from(lex_report, "jurisdiction_filters"),
                    *(item for item in (_optional_text(target.get("jurisdiction")),) if item),
                ]
            )
        ),
        "effective_date_filters": tuple(
            dict.fromkeys(
                [
                    *_refs_from(lex_report, "time_filters", "effective_date_filters"),
                    *(
                        item
                        for item in (
                            _optional_text(target.get("as_of")),
                            _optional_text(target.get("effective_date")),
                        )
                        if item
                    ),
                ]
            )
        ),
        "hierarchy_conflict_refs": _refs_from(
            lex_report,
            "hierarchy_conflict_refs",
            "conflict_refs",
            "conflicts",
        ),
        "competence_refs": _refs_from(
            lex_report,
            "competence_refs",
            "competence",
            "competence_assessments",
        ),
        "no_norm_blocker_refs": blockers if not selected else (),
        "retrieval_error_blocker_refs": tuple(
            dict.fromkeys([*retrieval_blockers, *typed_retrieval_blockers])
        ),
        **legal_authority_fields,
        **spine_fields,
    }


def _lex_legal_authority_fields(lex_report: Mapping[str, Any]) -> dict[str, Any]:
    records = _rows_from(lex_report.get("legal_authority_records"))
    anchors = _rows_from(lex_report.get("claim_legal_anchors"))
    splits = _rows_from(lex_report.get("claim_window_splits"))
    record_refs = tuple(
        dict.fromkeys(
            ref
            for record in records
            for ref in (
                _optional_text(
                    record.get("legal_authority_record_id")
                    or record.get("legal_authority_record_ref")
                    or record.get("record_ref")
                    or record.get("ref")
                ),
            )
            if ref
        )
    )
    anchor_record_refs = tuple(
        dict.fromkeys(
            ref
            for anchor in anchors
            for ref in _refs_from_value(anchor.get("legal_authority_record_refs"))
        )
    )
    blocker_refs = tuple(
        dict.fromkeys(
            [
                *(
                    ref
                    for record in records
                    for ref in _refs_from_value(
                        record.get("blocker_ref")
                        or record.get("limitation_ref")
                        or record.get("legal_authority_blocker_refs")
                    )
                ),
                *(
                    ref
                    for anchor in anchors
                    for ref in _refs_from_value(anchor.get("legal_authority_blocker_refs"))
                ),
            ]
        )
    )
    grades = tuple(
        grade
        for record in records
        for grade in (_optional_text(record.get("admissibility_grade")),)
        if grade
    )
    authority_types = tuple(
        dict.fromkeys(
            [
                *(
                    ref
                    for record in records
                    for ref in _refs_from_value(
                        record.get("authority_types") or record.get("authority_type")
                    )
                ),
                *(
                    ref
                    for anchor in anchors
                    for ref in _refs_from_value(anchor.get("selected_authority_types"))
                ),
            ]
        )
    )
    segment_refs = tuple(
        dict.fromkeys(
            [
                *(
                    ref
                    for record in records
                    for ref in _refs_from_value(record.get("claim_segment_ref"))
                ),
                *(
                    ref
                    for split in splits
                    for ref in _refs_from_value(split.get("claim_segment_ref"))
                ),
                *(
                    ref
                    for anchor in anchors
                    for ref in _refs_from_value(anchor.get("blocked_segment_refs"))
                ),
            ]
        )
    )
    fallback_policy_refs = tuple(
        dict.fromkeys(
            ref
            for record in records
            for ref in _refs_from_value(record.get("jurisdiction_fallback_policy_ref"))
        )
    )
    legal_required = bool(lex_report.get("legal_authority_required")) or any(
        bool(anchor.get("legal_authority_required")) for anchor in anchors
    )
    return {
        "legal_authority_required": legal_required,
        "legal_authority_record_refs": record_refs or anchor_record_refs,
        "legal_authority_blocker_refs": blocker_refs,
        "legal_admissibility_grades": grades,
        "legal_authority_types": authority_types,
        "legal_window_segment_refs": segment_refs,
        "jurisdiction_fallback_policy_refs": fallback_policy_refs,
    }


def _build_fabric_record(
    *,
    fabric_report: Mapping[str, Any],
    data_forge_snapshot_binding: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    intent: Mapping[str, Any],
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
) -> dict[str, Any]:
    candidates = _candidate_source_refs(fabric_report)
    selected = _selected_source_refs(fabric_report)
    rejected = _source_refs_from_rows(fabric_report.get("rejected_sources"))
    claim_ids = tuple(dict.fromkeys(_claim_id(row) for row in claims if _claim_id(row)))
    metric_id = _first_text(intent.get("monitoring_signal"), intent.get("outcome"))
    data_gap_blockers = _blocker_ref_tuple(
        fabric_report,
        "data_gap_blocker_refs",
        "data_gap_blockers",
    )
    ambiguity_blockers = _blocker_ref_tuple(
        fabric_report,
        "ambiguity_blocker_refs",
        "ambiguity_blockers",
    )
    data_forge_snapshot_refs = _data_forge_snapshot_refs(
        fabric_report=fabric_report,
        data_forge_snapshot_binding=data_forge_snapshot_binding,
    )
    source_facets = _source_facets_from_fabric_report(
        fabric_report=fabric_report,
        selected=selected,
        rejected=rejected,
        data_forge_snapshot_refs=data_forge_snapshot_refs,
    )
    derived_features = _derived_features_from_fabric_report(
        fabric_report=fabric_report,
        selected=selected,
        claims=claims,
        metric_id=metric_id,
        source_facets=source_facets,
    )
    claim_support_feature_refs = tuple(
        dict.fromkeys(
            ref
            for feature in derived_features
            for ref in _refs_from_value(feature.get("claim_support_feature_refs"))
        )
    )
    spine_fields = _spine_fields_from_report(
        fabric_report,
        spine_context,
        component="fabric",
        candidate_refs=(*candidates, *selected),
        blocker_refs=(*data_gap_blockers, *ambiguity_blockers),
    )
    return {
        "binding_id": "fabric-binding-runtime",
        "candidate_dataset_source_refs": candidates,
        "selected_dataset_source_refs": selected,
        "rejected_dataset_source_refs": rejected,
        "metric_bindings": [
            {
                "metric_id": metric_id,
                "claim_ids": claim_ids,
                "source_refs": selected,
            }
        ]
        if metric_id and claim_ids
        else [],
        "column_bindings": [
            {
                "claim_id": claim_id,
                "source_ref": source_ref,
                "column_refs": _candidate_columns(fabric_report, source_ref),
            }
            for claim in claims
            for claim_id in [_claim_id(claim)]
            if claim_id
            for source_ref in _refs_from_value(claim.get("data_refs")) or selected
        ],
        "unit_bindings": _mapping_tuple_from(fabric_report, "unit_bindings"),
        "geography_bindings": _mapping_tuple_from(fabric_report, "geography_bindings"),
        "calendar_time_bindings": _mapping_tuple_from(
            fabric_report,
            "calendar_time_bindings",
            "time_bindings",
        ),
        "source_freshness": _source_freshness(fabric_report),
        "data_coverage": [
            {
                "source_ref": source_ref,
                "claim_ids": [
                    _claim_id(claim)
                    for claim in claims
                    if _claim_id(claim)
                    and (
                        not _refs_from_value(claim.get("data_refs"))
                        or source_ref in _refs_from_value(claim.get("data_refs"))
                    )
                ],
                "status": "covers",
            }
            for source_ref in selected
        ],
        "dictionary_refs": _refs_from(fabric_report, "dictionary_refs", "data_dictionary_refs"),
        "lineage_refs": _refs_from(fabric_report, "lineage_refs"),
        "data_forge_snapshot_refs": data_forge_snapshot_refs,
        "source_facets": source_facets,
        "derived_features": derived_features,
        "claim_support_feature_refs": claim_support_feature_refs,
        "data_gap_blocker_refs": data_gap_blockers,
        "ambiguity_blocker_refs": ambiguity_blockers,
        **spine_fields,
    }


def _build_scholar_record(
    *,
    scholar_report: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
) -> dict[str, Any]:
    selected = _literature_refs_from_rows(
        scholar_report.get("selected_literature")
        or scholar_report.get("selected_sources")
        or scholar_report.get("selected_evidence")
    )
    claim_literature = _refs_from_claims(claims, "literature_refs")
    claim_scholar = _refs_from_claims(claims, "scholar_refs")
    if not selected:
        selected = tuple(dict.fromkeys([*claim_literature, *claim_scholar]))
    candidate = tuple(
        dict.fromkeys(
            [
                *_literature_refs_from_rows(scholar_report.get("candidate_literature")),
                *_literature_refs_from_rows(scholar_report.get("candidate_sources")),
                *selected,
            ]
        )
    )
    retrieval_blockers = _blocker_ref_tuple(
        scholar_report,
        "retrieval_blocker_refs",
        "retrieval_error_blocker_refs",
        "blockers",
    )
    spine_fields = _spine_fields_from_report(
        scholar_report,
        spine_context,
        component="scholar",
        candidate_refs=(*candidate, *selected),
        blocker_refs=retrieval_blockers,
    )
    return {
        "binding_id": "scholar-binding-runtime",
        "candidate_literature_refs": candidate,
        "selected_literature_refs": selected,
        "rejected_literature_refs": _literature_refs_from_rows(
            scholar_report.get("rejected_literature") or scholar_report.get("rejected_sources")
        ),
        "support_link_refs": _refs_from(
            scholar_report,
            "support_link_refs",
            "claim_support_refs",
            "citation_lineage_refs",
        ),
        "conflict_link_refs": _refs_from(
            scholar_report,
            "conflict_link_refs",
            "contradiction_refs",
            "disagreement_refs",
        ),
        "retrieval_blocker_refs": retrieval_blockers,
        **spine_fields,
    }


def _build_foundry_record(
    *,
    foundry_report: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
) -> dict[str, Any]:
    selected = _selected_method_refs(foundry_report, claims)
    selected_rows = _rows_from(foundry_report.get("selected_methods"))
    rejected_rows = _rows_from(foundry_report.get("rejected_methods"))
    method_blockers = _blocker_ref_tuple(
        foundry_report,
        "method_incompatibility_blocker_refs",
        "method_blockers",
    )
    spine_fields = _spine_fields_from_report(
        foundry_report,
        spine_context,
        component="foundry",
        candidate_refs=selected,
        blocker_refs=method_blockers,
    )
    return {
        "binding_id": "foundry-binding-runtime",
        "selected_method_refs": selected,
        "rejected_method_refs": _method_refs_from_rows(rejected_rows),
        "rejected_method_reasons": _rejected_method_reasons(rejected_rows),
        "scenario_method_expectation_refs": tuple(
            ref
            for ref in dict.fromkeys(
                [
                    *_refs_from(foundry_report, "scenario_method_expectation_refs"),
                    *(_optional_text(row.get("method_family")) for row in selected_rows),
                ]
            )
            if ref
        ),
        "assumptions": tuple(
            dict.fromkeys(
                [
                    *_refs_from(foundry_report, "assumptions"),
                    *(
                        assumption
                        for row in selected_rows
                        for assumption in _refs_from_value(row.get("assumptions"))
                    ),
                ]
            )
        ),
        "assumption_gate_refs": tuple(
            dict.fromkeys(
                [
                    *_refs_from(foundry_report, "assumption_gate_refs"),
                    *(
                        ref
                        for row in selected_rows
                        for ref in _refs_from_value(row.get("assumption_gate_refs"))
                    ),
                    *(
                        ref
                        for row in selected_rows
                        for gate in _rows_from(row.get("runtime_assumption_gates"))
                        for ref in _refs_from_value(
                            gate.get("gate_ref")
                            or gate.get("assumption_gate_ref")
                            or gate.get("ref")
                        )
                    ),
                ]
            )
        ),
        "runtime_assumption_gates": _mapping_tuple_from(foundry_report, "runtime_assumption_gates")
        or tuple(
            gate
            for row in selected_rows
            for gate in _rows_from(row.get("runtime_assumption_gates"))
        ),
        "input_coverage": _mapping_tuple_from(foundry_report, "input_coverage")
        or tuple({"method_ref": method_ref, "status": "pass"} for method_ref in selected),
        "sample_power_adequacy": _mapping_tuple_from(foundry_report, "sample_power_adequacy")
        or tuple(
            {
                "method_ref": _optional_text(row.get("method_id"))
                or _optional_text(row.get("method_ref"))
                or "method",
                "status": _sample_power_status(row),
            }
            for row in selected_rows
        ),
        "placebo_negative_control_refs": _refs_from(
            foundry_report,
            "placebo_negative_control_refs",
            "negative_control_refs",
        ),
        "sensitivity_refs": _refs_from(foundry_report, "sensitivity_refs"),
        "uncertainty_refs": tuple(
            dict.fromkeys(
                [
                    *_refs_from(foundry_report, "uncertainty_refs", "uncertainty_envelope_refs"),
                    *(
                        ref
                        for row in selected_rows
                        for ref in _refs_from_value(
                            row.get("uncertainty_envelope_refs")
                            or row.get("uncertainty_refs")
                        )
                    ),
                ]
            )
        ),
        "uncertainty_envelopes": _mapping_tuple_from(foundry_report, "uncertainty_envelopes")
        or tuple(
            uncertainty
            for row in selected_rows
            for uncertainty in (
                _mapping_from(row.get("uncertainty") or row.get("uncertainty_envelope")),
            )
            if uncertainty
        ),
        "limitation_refs": tuple(
            dict.fromkeys(
                [
                    *_refs_from(foundry_report, "limitation_refs", "method_limitation_refs"),
                    *(
                        ref
                        for row in selected_rows
                        for ref in _refs_from_value(row.get("limitation_refs"))
                    ),
                ]
            )
        ),
        "simulation_assumption_lineage_refs": tuple(
            dict.fromkeys(
                [
                    *_refs_from(
                        foundry_report,
                        "simulation_assumption_lineage_refs",
                        "assumption_lineage_refs",
                    ),
                    *(
                        ref
                        for row in selected_rows
                        for ref in _refs_from_value(
                            row.get("simulation_assumption_lineage_refs")
                            or row.get("assumption_lineage_refs")
                        )
                    ),
                ]
            )
        ),
        "method_output_refs": tuple(
            dict.fromkeys(
                [
                    *_refs_from(foundry_report, "method_output_refs", "method_result_refs"),
                    *(
                        ref
                        for row in selected_rows
                        for ref in _method_output_refs_from_method(row)
                    ),
                ]
            )
        ),
        "method_incompatibility_blocker_refs": method_blockers,
        **spine_fields,
    }


def _build_claim_binding_record(
    *,
    binding_id: str,
    claims: Sequence[Mapping[str, Any]],
    decision_contract: Mapping[str, Any],
    lex_bindings: Sequence[Mapping[str, Any]],
    fabric_bindings: Sequence[Mapping[str, Any]],
    foundry_bindings: Sequence[Mapping[str, Any]],
    final_compiler: bool,
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
) -> dict[str, Any]:
    claim_ids = tuple(dict.fromkeys(_claim_id(row) for row in claims if _claim_id(row)))
    recommendation_ids = tuple(
        claim_id
        for row in claims
        for claim_id in [_claim_id(row)]
        if claim_id
        and (
            bool(row.get("major"))
            or str(row.get("claim_type") or "").casefold() == "recommendation"
        )
    )
    contract_statements = _rows_from(decision_contract.get("statements"))
    blockers = tuple(
        dict.fromkeys(
            [
                *(
                    _optional_text(blocker.get("blocker_ref"))
                    or _optional_text(blocker.get("blocker_type"))
                    or _optional_text(blocker.get("code"))
                    or ""
                    for row in claims
                    for blocker in _rows_from(row.get("typed_blockers"))
                ),
                *(
                    _optional_text(blocker.get("blocker_ref"))
                    or _optional_text(blocker.get("blocker_type"))
                    or _optional_text(blocker.get("code"))
                    or ""
                    for statement in contract_statements
                    for blocker in _rows_from(statement.get("typed_blockers"))
                ),
            ]
        )
    )
    public_sections = tuple(
        dict.fromkeys(
            f"section:{_optional_text(statement.get('statement_scope'))}"
            for statement in contract_statements
            if _optional_text(statement.get("statement_scope"))
        )
    )
    spine_fields = _spine_fields_from_report(
        decision_contract,
        spine_context,
        component="final_compiler" if final_compiler else "scientist",
        candidate_refs=claim_ids,
        blocker_refs=blockers,
    )
    candidate_binding_refs = tuple(
        dict.fromkeys(
            [
                *spine_fields["candidate_spine_binding_refs"],
                *_refs_from_claims(claims, "candidate_spine_binding_refs"),
                *_refs_from_claims(claims, "candidate_binding_refs"),
            ]
        )
    )
    spine_blocker_refs = tuple(
        dict.fromkeys(
            [
                *spine_fields["spine_blocker_refs"],
                *_refs_from_claims(claims, "spine_blocker_refs"),
                *_refs_from_claims(claims, "binding_blocker_refs"),
            ]
        )
    )
    local_labels = tuple(
        dict.fromkeys(
            [
                *spine_fields["local_labels"],
                *_refs_from_claims(claims, "local_labels"),
            ]
        )
    )
    return {
        "binding_id": binding_id,
        "major_claim_ids": claim_ids,
        "recommendation_ids": recommendation_ids,
        "legal_assertion_ids": _ids_by_type(claims, "legal", "legal_assertion"),
        "budget_feasibility_ids": _ids_by_type(claims, "budget", "budget_feasibility"),
        "distributional_impact_ids": _ids_by_type(claims, "distributional_impact"),
        "implementation_risk_ids": _ids_by_type(claims, "implementation_risk", "risk"),
        "monitoring_ids": _ids_by_type(claims, "monitoring", "monitoring_plan"),
        "residual_uncertainty_ids": _ids_by_type(claims, "residual_uncertainty", "uncertainty"),
        "required_data_refs": _refs_from_claims(claims, "data_refs"),
        "required_method_refs": _refs_from_claims(claims, "method_refs"),
        "required_norm_refs": _refs_from_claims(claims, "norm_refs"),
        "required_literature_refs": tuple(
            dict.fromkeys(
                [
                    *_refs_from_claims(claims, "literature_refs"),
                    *_refs_from_claims(claims, "scholar_refs"),
                ]
            )
        ),
        "required_uncertainty_refs": _refs_from_claims(claims, "uncertainty_refs"),
        "required_blocker_refs": tuple(ref for ref in blockers if ref),
        "public_artifact_section_refs": public_sections
        if final_compiler and public_sections
        else (("section:recommendations",) if final_compiler and recommendation_ids else ()),
        "claim_evidence_paths": _build_claim_evidence_paths(
            claims=claims,
            lex_bindings=lex_bindings,
            fabric_bindings=fabric_bindings,
            foundry_bindings=foundry_bindings,
            spine_context=spine_context,
        ),
        **{
            **spine_fields,
            "candidate_spine_binding_refs": candidate_binding_refs,
            "spine_blocker_refs": spine_blocker_refs,
            "local_labels": local_labels,
        },
    }


def _build_claim_evidence_paths(
    *,
    claims: Sequence[Mapping[str, Any]],
    lex_bindings: Sequence[Mapping[str, Any]],
    fabric_bindings: Sequence[Mapping[str, Any]],
    foundry_bindings: Sequence[Mapping[str, Any]],
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
) -> list[dict[str, Any]]:
    context = (
        spine_context.model_dump(mode="json")
        if isinstance(spine_context, ProducerSpineReadContext)
        else dict(spine_context or {})
    )
    paths: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = _claim_id(claim)
        if not claim_id:
            continue
        claim_type = str(claim.get("claim_type") or claim.get("statement_type") or "").casefold()
        if claim.get("major") is False and "recommendation" not in claim_type:
            continue
        data_refs = _refs_from_value(claim.get("data_refs"))
        method_refs = _refs_from_value(claim.get("method_refs"))
        norm_refs = _refs_from_value(claim.get("norm_refs"))
        relevant_fabric = _claim_fabric_bindings(
            fabric_bindings,
            claim_id=claim_id,
            data_refs=data_refs,
        )
        relevant_lex = _claim_lex_bindings(lex_bindings, norm_refs=norm_refs)
        relevant_foundry = _claim_foundry_bindings(
            foundry_bindings,
            method_refs=method_refs,
        )
        paths.append(
            {
                "claim_id": claim_id,
                "claim_type": _optional_text(claim.get("claim_type")),
                "claim_family": _optional_text(claim.get("claim_family")),
                "claim_use": _optional_text(claim.get("claim_use")),
                "scenario_requirement_refs": _refs_from(
                    claim,
                    "scenario_requirement_refs",
                    "scenario_requirements",
                    "requirement_refs",
                ),
                "canonical_concept_refs": tuple(
                    dict.fromkeys(
                        [
                            *_refs_from(
                                claim,
                                "canonical_concept_refs",
                                "concept_refs",
                            ),
                            *_refs_from_value(context.get("canonical_concept_refs")),
                        ]
                    )
                ),
                "fabric_binding_refs": tuple(
                    dict.fromkeys(
                        _optional_text(binding.get("binding_id"))
                        for binding in relevant_fabric
                        if _optional_text(binding.get("binding_id"))
                    )
                ),
                "source_refs": data_refs
                or tuple(
                    dict.fromkeys(
                        ref
                        for binding in relevant_fabric
                        for ref in _refs_from_value(
                            binding.get("selected_dataset_source_refs")
                        )
                    )
                ),
                "column_refs": _refs_from(
                    claim,
                    "column_refs",
                    "data_column_refs",
                    "field_refs",
                )
                or tuple(
                    dict.fromkeys(
                        ref
                        for binding in relevant_fabric
                        for column in _rows_from(binding.get("column_bindings"))
                        if _claim_id(column) == claim_id
                        for ref in _refs_from_value(column.get("column_refs"))
                    )
                ),
                "lex_binding_refs": tuple(
                    dict.fromkeys(
                        _optional_text(binding.get("binding_id"))
                        for binding in relevant_lex
                        if _optional_text(binding.get("binding_id"))
                    )
                ),
                "selected_norm_refs": norm_refs
                or tuple(
                    dict.fromkeys(
                        ref
                        for binding in relevant_lex
                        for ref in _refs_from_value(binding.get("selected_norm_refs"))
                    )
                ),
                "foundry_binding_refs": tuple(
                    dict.fromkeys(
                        _optional_text(binding.get("binding_id"))
                        for binding in relevant_foundry
                        if _optional_text(binding.get("binding_id"))
                    )
                ),
                "selected_method_refs": method_refs
                or tuple(
                    dict.fromkeys(
                        ref
                        for binding in relevant_foundry
                        for ref in _refs_from_value(binding.get("selected_method_refs"))
                    )
                ),
                "method_output_refs": _refs_from(
                    claim,
                    "method_output_refs",
                    "method_result_refs",
                    "foundry_output_refs",
                )
                or tuple(
                    dict.fromkeys(
                        ref
                        for binding in relevant_foundry
                        for ref in _refs_from_value(binding.get("method_output_refs"))
                    )
                ),
                "assumption_gate_refs": _refs_from(
                    claim,
                    "assumption_gate_refs",
                    "method_assumption_gate_refs",
                    "foundry_assumption_gate_refs",
                )
                or tuple(
                    dict.fromkeys(
                        ref
                        for binding in relevant_foundry
                        for ref in _refs_from_value(binding.get("assumption_gate_refs"))
                    )
                ),
                "uncertainty_refs": _refs_from(
                    claim,
                    "uncertainty_refs",
                    "residual_uncertainty_refs",
                    "foundry_uncertainty_refs",
                )
                or tuple(
                    dict.fromkeys(
                        ref
                        for binding in relevant_foundry
                        for ref in _refs_from_value(binding.get("uncertainty_refs"))
                    )
                ),
                "scientist_claim_refs": _refs_from(
                    claim,
                    "scientist_claim_refs",
                    "claim_refs",
                    "claim_ref",
                    "assurance_node_ref",
                    "assurance_node_id",
                )
                or (f"claim:{claim_id}",),
                "argument_refs": _refs_from(claim, "argument_refs", "argument_node_refs"),
                "warrant_refs": _refs_from(claim, "warrant_refs", "warrant_node_refs"),
                "rebuttal_refs": _refs_from(claim, "rebuttal_refs", "rebuttal_node_refs"),
                "counter_evidence_refs": _refs_from(
                    claim,
                    "counter_evidence_refs",
                    "counter_evidence_node_refs",
                ),
                "limitation_refs": _refs_from(
                    claim,
                    "limitation_refs",
                    "assurance_deficit_refs",
                    "accepted_deficit_refs",
                    "deficit_refs",
                ),
                "blocker_refs": _refs_from(claim, "blocker_refs", "typed_blockers"),
                "baseline_refs": _refs_from(claim, "baseline_refs", "baseline_ref"),
                "alternative_refs": _refs_from(
                    claim,
                    "alternative_refs",
                    "alternative_ref",
                ),
                "comparison_refs": _refs_from(
                    claim,
                    "comparison_refs",
                    "comparison_record_refs",
                    "baseline_comparison_refs",
                ),
            }
        )
    return paths


def _claim_fabric_bindings(
    bindings: Sequence[Mapping[str, Any]],
    *,
    claim_id: str,
    data_refs: Sequence[str],
) -> tuple[Mapping[str, Any], ...]:
    wanted_data = set(data_refs)
    matched: list[Mapping[str, Any]] = []
    for binding in bindings:
        selected = set(_refs_from_value(binding.get("selected_dataset_source_refs")))
        if wanted_data and not wanted_data.intersection(selected):
            continue
        if any(
            claim_id in _refs_from_value(column.get("claim_ids"))
            or _claim_id(column) == claim_id
            for column in _rows_from(binding.get("column_bindings"))
        ) or not wanted_data or wanted_data.intersection(selected):
            matched.append(binding)
    return tuple(matched)


def _claim_lex_bindings(
    bindings: Sequence[Mapping[str, Any]],
    *,
    norm_refs: Sequence[str],
) -> tuple[Mapping[str, Any], ...]:
    wanted_norms = set(norm_refs)
    if not wanted_norms:
        return tuple(bindings)
    return tuple(
        binding
        for binding in bindings
        if wanted_norms.intersection(_refs_from_value(binding.get("selected_norm_refs")))
    )


def _claim_foundry_bindings(
    bindings: Sequence[Mapping[str, Any]],
    *,
    method_refs: Sequence[str],
) -> tuple[Mapping[str, Any], ...]:
    wanted_methods = set(method_refs)
    if not wanted_methods:
        return tuple(bindings)
    return tuple(
        binding
        for binding in bindings
        if wanted_methods.intersection(_refs_from_value(binding.get("selected_method_refs")))
    )


def _record_presence_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    missing: list[tuple[str, str]] = []
    if not ledger.lex:
        missing.append(("lex", "Lex binding records are missing."))
    if not ledger.fabric:
        missing.append(("fabric", "Fabric binding records are missing."))
    if not ledger.scholar:
        missing.append(("scholar", "Scholar binding records are missing."))
    if not ledger.foundry:
        missing.append(("foundry", "Foundry binding records are missing."))
    if not ledger.scientist:
        missing.append(("scientist", "Scientist claim binding records are missing."))
    if not ledger.final_compiler:
        missing.append(("final_compiler", "Final compiler binding records are missing."))
    return [
        _issue(
            "semantic_binding_phase_record_missing",
            message,
            next_action="Emit the full semantic binding ledger before serious closeout.",
            refs=(phase,),
        )
        for phase, message in missing
    ]


def _producer_handshake_ledger_issues(
    ledger: SemanticBindingLedger,
) -> list[SemanticBindingIssue]:
    if not isinstance(ledger.producer_handshake_ledger, Mapping):
        return []
    status = str(ledger.producer_handshake_ledger.get("status") or "").strip().casefold()
    findings = _rows_from(ledger.producer_handshake_ledger.get("findings"))
    if status not in {"fail", "failed"} and not findings:
        return []
    issue_codes = tuple(
        str(finding.get("code"))
        for finding in findings
        if str(finding.get("code") or "").strip()
    )
    return [
        _issue(
            "semantic_producer_handshake_ledger_failed",
            "Producer handshake ledger failed before semantic binding could trust producers.",
            next_action=(
                "Resolve missing producer handshakes, bridge authority, or finite wait "
                "conditions before claim-bound semantic binding."
            ),
            refs=(
                str(ledger.producer_handshake_ledger.get("producer_handshake_ledger_ref") or ""),
                *issue_codes,
            ),
        )
    ]


def _lex_selection_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    if not _domain_specific_intent(ledger.intent):
        return issues
    for binding in ledger.lex:
        has_typed_blocker = bool(
            binding.no_norm_blocker_refs or binding.retrieval_error_blocker_refs
        )
        if (
            binding.legal_authority_required
            and binding.selected_norm_refs
            and not binding.legal_authority_record_refs
        ):
            issues.append(
                _issue(
                    "semantic_lex_legal_authority_record_missing",
                    (
                        "Lex selected norm refs for a legally constrained claim without "
                        "claim-level legal authority records."
                    ),
                    next_action=(
                        "Produce Lex legal_authority_records with norm version, provenance, "
                        "competence, authority type, jurisdiction fallback, and legal-window "
                        "facets before treating the selected norm as recommendation authority."
                    ),
                    refs=(binding.binding_id, *binding.selected_norm_refs),
                    missing_input="claim-level legal authority record refs",
                    conflicting_producer="lex",
                )
            )
        if binding.selected_norm_refs or has_typed_blocker:
            continue
        issues.append(
            _issue(
                "semantic_no_norm_false_pass",
                "Domain-specific legal intent has no selected norm and no typed Lex blocker.",
                next_action=(
                    "Select applicable norm refs for the canonical legal query or emit "
                    "a no-norm/retrieval typed blocker."
                ),
                refs=(binding.binding_id, ledger.intent.legal_domain),
            )
        )
    return issues


def _fabric_selection_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    for binding in ledger.fabric:
        candidates = set(binding.candidate_dataset_source_refs)
        selected = set(binding.selected_dataset_source_refs)
        rejected = set(binding.rejected_dataset_source_refs)
        has_typed_blocker = bool(binding.data_gap_blocker_refs or binding.ambiguity_blocker_refs)
        if len(candidates) > 1 and not selected and not has_typed_blocker:
            issues.append(
                _issue(
                    "semantic_dataset_selection_ambiguous",
                    (
                        "Multiple candidate datasets require explicit selection authority "
                        "or an ambiguity blocker."
                    ),
                    next_action=(
                        "Select the dataset/source with authority evidence, reject the "
                        "others with reasons, or emit a typed ambiguity blocker."
                    ),
                    refs=tuple(sorted(candidates)),
                )
            )
        if not selected and not rejected and not has_typed_blocker:
            issues.append(
                _issue(
                    "semantic_selected_dataset_missing",
                    "Fabric has no selected dataset/source and no typed blocker.",
                    next_action=(
                        "Persist selected dataset/source refs or emit data-gap/ambiguity blockers."
                    ),
                    refs=(binding.binding_id,),
                )
            )
        unknown_selected = sorted(selected - candidates) if candidates else []
        if unknown_selected:
            issues.append(
                _issue(
                    "semantic_selected_dataset_missing_candidate",
                    "Selected dataset/source refs are absent from candidate refs.",
                    next_action="Preserve every selected source in candidate evidence.",
                    refs=tuple(unknown_selected),
                )
            )
    return issues


def _fabric_lineage_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    for binding in ledger.fabric:
        selected = tuple(binding.selected_dataset_source_refs)
        has_typed_blocker = bool(binding.data_gap_blocker_refs or binding.ambiguity_blocker_refs)
        if not selected or has_typed_blocker:
            continue
        if not binding.data_forge_snapshot_refs:
            issues.append(
                _issue(
                    "semantic_fabric_data_forge_snapshot_ref_missing",
                    "Fabric source evidence is missing consumed Data Forge snapshot refs.",
                    next_action=(
                        "Bind Fabric source evidence to the previous-wave Data Forge "
                        "snapshot binding refs."
                    ),
                    refs=(binding.binding_id,),
                    missing_input="data_forge_snapshot_refs",
                    conflicting_producer="fabric",
                    affected_claim=_affected_claim_for_producer_binding(
                        ledger,
                        component="fabric",
                        binding=binding,
                    ),
                )
            )
        facets_by_source = {facet.source_ref: facet for facet in binding.source_facets}
        derived_by_source_claim = {
            (feature.source_ref, claim_id)
            for feature in binding.derived_features
            for claim_id in feature.claim_ids
        }
        for source_ref in selected:
            facet = facets_by_source.get(source_ref)
            affected_claim = _first_claim_requiring(
                (*ledger.scientist, *ledger.final_compiler),
                lambda claim, ref=source_ref: ref in claim.required_data_refs,
            )
            if facet is None:
                issues.append(
                    _issue(
                        "semantic_fabric_source_facet_missing",
                        "Selected Fabric source is missing field-level source facets.",
                        next_action=(
                            "Emit source family, rights, dataset, dictionary, schema, "
                            "fields, units, geography, time, quality, missingness, "
                            "freshness, lineage, transformations, and Data Forge refs."
                        ),
                        refs=(binding.binding_id, source_ref),
                        missing_input="source_facets",
                        conflicting_producer="fabric",
                        affected_claim=affected_claim,
                    )
                )
                continue
            issues.extend(
                _source_facet_completeness_issues(
                    binding=binding,
                    facet=facet,
                    affected_claim=affected_claim,
                )
            )
            for column_binding in binding.column_bindings:
                if column_binding.source_ref != source_ref or not column_binding.column_refs:
                    continue
                if not facet.field_refs or not facet.lineage_refs:
                    issues.append(
                        _issue(
                            "semantic_fabric_field_lineage_missing",
                            "Claim-bound Fabric columns are missing field refs or lineage refs.",
                            next_action=(
                                "Bind every claim column to source facet field_refs and "
                                "lineage_refs before final claim support."
                            ),
                            claim_id=column_binding.claim_id,
                            refs=(source_ref, *column_binding.column_refs),
                            missing_input="field_refs and lineage_refs",
                            conflicting_producer="fabric",
                            affected_claim=column_binding.claim_id,
                        )
                    )
                    continue
                missing_columns = tuple(
                    column_ref
                    for column_ref in column_binding.column_refs
                    if not _field_ref_matches_any(column_ref, facet.field_refs)
                )
                if missing_columns:
                    issues.append(
                        _issue(
                            "semantic_fabric_column_not_in_source_facet",
                            "Claim-bound Fabric column refs are absent from source facets.",
                            next_action=(
                                "Use stable source facet field refs for claim column bindings."
                            ),
                            claim_id=column_binding.claim_id,
                            refs=(source_ref, *missing_columns),
                            missing_input="matching source facet field refs",
                            conflicting_producer="fabric",
                            affected_claim=column_binding.claim_id,
                        )
                    )
        for metric in binding.metric_bindings:
            for source_ref in metric.source_refs:
                for claim_id in metric.claim_ids:
                    if (source_ref, claim_id) in derived_by_source_claim:
                        continue
                    issues.append(
                        _issue(
                            "semantic_fabric_derived_feature_binding_missing",
                            "Metric-to-claim Fabric evidence lacks a derived-feature binding.",
                            next_action=(
                                "Bind derived Fabric features to source facets and "
                                "claim-support feature refs."
                            ),
                            claim_id=claim_id,
                            refs=(source_ref, metric.metric_id),
                            missing_input="derived_features",
                            conflicting_producer="fabric",
                            affected_claim=claim_id,
                        )
                    )
        facet_refs = {
            field_ref
            for facet in binding.source_facets
            for field_ref in facet.field_refs
        }
        for feature in binding.derived_features:
            if not feature.source_facet_refs:
                issues.append(
                    _issue(
                        "semantic_derived_feature_source_facet_ref_missing",
                        "Derived Fabric feature is missing source_facet_refs.",
                        next_action=(
                            "Bind each derived feature to the source facet fields it uses."
                        ),
                        refs=(feature.feature_ref, feature.source_ref),
                        missing_input="source_facet_refs",
                        conflicting_producer="fabric",
                        affected_claim=_first_optional_ref(feature.claim_ids),
                    )
                )
            if not feature.claim_support_feature_refs:
                issues.append(
                    _issue(
                        "semantic_derived_feature_claim_support_ref_missing",
                        "Derived Fabric feature is missing claim_support_feature_refs.",
                        next_action=(
                            "Bind each derived feature to the claim-support features it supports."
                        ),
                        refs=(feature.feature_ref, feature.source_ref),
                        missing_input="claim_support_feature_refs",
                        conflicting_producer="fabric",
                        affected_claim=_first_optional_ref(feature.claim_ids),
                    )
                )
            missing_facet_refs = tuple(
                ref
                for ref in feature.source_facet_refs
                if not _field_ref_matches_any(ref, facet_refs)
            )
            if missing_facet_refs:
                issues.append(
                    _issue(
                        "semantic_derived_feature_source_facet_ref_unknown",
                        "Derived Fabric feature references unknown source facets.",
                        next_action=(
                            "Use source_facet_refs emitted by the selected source facets."
                        ),
                        refs=(feature.feature_ref, *missing_facet_refs),
                        missing_input="known source facet refs",
                        conflicting_producer="fabric",
                        affected_claim=_first_optional_ref(feature.claim_ids),
                    )
                )
    return issues


def _source_facet_completeness_issues(
    *,
    binding: FabricBindingRecord,
    facet: SourceFacetBinding,
    affected_claim: str | None,
) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    requirements: tuple[tuple[str, Sequence[str], str], ...] = (
        ("field_refs", facet.field_refs, "field refs"),
        ("unit_refs", facet.unit_refs, "unit refs"),
        ("geography_refs", facet.geography_refs, "geography refs"),
        ("time_coverage_refs", facet.time_coverage_refs, "time coverage refs"),
        ("quality_refs", facet.quality_refs, "quality refs"),
        ("missingness_refs", facet.missingness_refs, "missingness refs"),
        ("freshness_refs", facet.freshness_refs, "freshness refs"),
        ("lineage_refs", facet.lineage_refs, "lineage refs"),
        ("transformation_refs", facet.transformation_refs, "transformation refs"),
        ("data_forge_snapshot_refs", facet.data_forge_snapshot_refs, "Data Forge refs"),
    )
    for field, values, label in requirements:
        if values:
            continue
        issues.append(
            _issue(
                "semantic_fabric_source_facet_incomplete",
                f"Selected Fabric source facet is missing {label}.",
                next_action=(
                    "Emit complete field-level Fabric source facets before claim support."
                ),
                refs=(binding.binding_id, facet.source_ref, field),
                missing_input=field,
                conflicting_producer="fabric",
                affected_claim=affected_claim,
            )
        )
    return issues


def _fabric_false_pass_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    for binding in ledger.fabric:
        manifest_refs = [
            *binding.selected_dataset_source_refs,
            *binding.candidate_dataset_source_refs,
            *(
                column_ref
                for column in binding.column_bindings
                for column_ref in column.column_refs
            ),
        ]
        if not any(_looks_manifest_role_ref(ref) for ref in manifest_refs):
            continue
        issues.append(
            _issue(
                "semantic_manifest_role_source_selection_false_pass",
                "Fabric selected manifest-role metadata as if it were claim data.",
                next_action=(
                    "Select a domain source with field-level lineage, or emit a "
                    "data-gap blocker instead of using manifest-role metadata."
                ),
                refs=tuple(ref for ref in manifest_refs if _looks_manifest_role_ref(ref)),
                missing_input="domain source fields, not manifest-role metadata",
                conflicting_producer="fabric",
                affected_claim=_affected_claim_for_producer_binding(
                    ledger,
                    component="fabric",
                    binding=binding,
                ),
            )
        )
    return issues


def _scholar_selection_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    for binding in ledger.scholar:
        has_typed_blocker = bool(binding.retrieval_blocker_refs)
        if binding.selected_literature_refs or has_typed_blocker:
            continue
        if binding.candidate_literature_refs or binding.rejected_literature_refs:
            issues.append(
                _issue(
                    "semantic_scholar_selection_missing",
                    "Scholar has literature candidates but no selected literature ref.",
                    next_action=(
                        "Select support/conflict literature refs or emit a Scholar "
                        "retrieval/no-relevant-evidence blocker."
                    ),
                    refs=(binding.binding_id,),
                )
            )
    return issues


def _claim_coverage_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    selected_sources = {
        ref for binding in ledger.fabric for ref in binding.selected_dataset_source_refs
    }
    coverage = {
        (item.source_ref, claim_id)
        for binding in ledger.fabric
        for item in binding.data_coverage
        if item.covers_claim
        for claim_id in item.claim_ids
    }
    irrelevant_coverage = {
        (item.source_ref, claim_id, item.status)
        for binding in ledger.fabric
        for item in binding.data_coverage
        if item.status.casefold() in {"irrelevant", "not_relevant", "unrelated"}
        for claim_id in item.claim_ids
    }
    column_coverage = {
        (item.source_ref, item.claim_id)
        for binding in ledger.fabric
        for item in binding.column_bindings
        if item.column_refs
    }
    data_blockers = {ref for binding in ledger.fabric for ref in binding.data_gap_blocker_refs}
    if not selected_sources and not data_blockers:
        return issues
    claim_bindings = (*ledger.scientist, *ledger.final_compiler)
    for claim_binding in claim_bindings:
        for claim_id in claim_binding.claim_ids:
            for data_ref in claim_binding.required_data_refs:
                if data_ref not in selected_sources:
                    if data_blockers:
                        continue
                    issues.append(
                        _issue(
                            "semantic_required_data_not_selected",
                            "Claim requires a data ref that Fabric did not select.",
                            next_action=(
                                "Bind the claim to a selected dataset/source or emit "
                                "a data-gap blocker."
                            ),
                            claim_id=claim_id,
                            refs=(data_ref,),
                        )
                    )
                    continue
                if (data_ref, claim_id) not in coverage and (
                    data_ref,
                    claim_id,
                ) not in column_coverage:
                    irrelevant = tuple(
                        status
                        for source_ref, covered_claim_id, status in irrelevant_coverage
                        if source_ref == data_ref and covered_claim_id == claim_id
                    )
                    if irrelevant:
                        issues.append(
                            _issue(
                                "semantic_data_present_but_irrelevant",
                                "Selected data is present but explicitly irrelevant to the claim.",
                                next_action=(
                                    "Bind the claim to relevant field-level coverage or "
                                    "emit a data-gap blocker."
                                ),
                                claim_id=claim_id,
                                refs=(data_ref, *irrelevant),
                                missing_input="relevant claim coverage",
                                conflicting_producer="fabric",
                                affected_claim=claim_id,
                            )
                        )
                        continue
                    issues.append(
                        _issue(
                            "semantic_data_claim_uncovered",
                            "Selected dataset exists but does not cover the claim.",
                            next_action=(
                                "Record claim-level data coverage and column bindings, "
                                "or block the claim with a data-gap ref."
                            ),
                            claim_id=claim_id,
                            refs=(data_ref,),
                        )
                    )
    return issues


_CLAIM_EVIDENCE_CLOSURE_REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    (
        "scenario_requirement_refs",
        "semantic_major_claim_scenario_requirement_refs_missing",
        "scenario requirement refs",
    ),
    (
        "canonical_concept_refs",
        "semantic_major_claim_canonical_concept_refs_missing",
        "canonical concept refs",
    ),
    (
        "source_refs",
        "semantic_major_claim_source_refs_missing",
        "selected data source refs",
    ),
    (
        "column_refs",
        "semantic_major_claim_column_refs_missing",
        "claim-bound data column refs",
    ),
    (
        "selected_norm_refs",
        "semantic_major_claim_selected_norm_refs_missing",
        "selected legal norm refs",
    ),
    (
        "selected_method_refs",
        "semantic_major_claim_selected_method_refs_missing",
        "selected analytical method refs",
    ),
    (
        "method_output_refs",
        "semantic_major_claim_method_output_refs_missing",
        "method output refs",
    ),
    (
        "assumption_gate_refs",
        "semantic_major_claim_assumption_gate_refs_missing",
        "runtime method assumption gate refs",
    ),
    (
        "uncertainty_refs",
        "semantic_major_claim_uncertainty_refs_missing",
        "method uncertainty envelope refs",
    ),
    (
        "argument_refs",
        "semantic_major_claim_argument_refs_missing",
        "argument refs",
    ),
    (
        "warrant_refs",
        "semantic_major_claim_warrant_refs_missing",
        "warrant refs",
    ),
    (
        "rebuttal_refs",
        "semantic_major_claim_rebuttal_refs_missing",
        "rebuttal refs",
    ),
    (
        "counter_evidence_refs",
        "semantic_major_claim_counter_evidence_refs_missing",
        "counter-evidence refs",
    ),
    (
        "limitation_refs",
        "semantic_major_claim_limitation_refs_missing",
        "accepted limitation or deficit refs",
    ),
)


def _claim_evidence_closure_issues(
    ledger: SemanticBindingLedger,
) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    for component, binding in (
        *tuple(("scientist", item) for item in ledger.scientist),
        *tuple(("final_compiler", item) for item in ledger.final_compiler),
    ):
        material_claim_ids = tuple(
            dict.fromkeys([*binding.major_claim_ids, *binding.recommendation_ids])
        )
        for claim_id in material_claim_ids:
            paths = tuple(
                path for path in binding.claim_evidence_paths if path.claim_id == claim_id
            )
            if not paths:
                issues.append(
                    _issue(
                        "semantic_major_claim_evidence_path_missing",
                        "Material claim has no complete semantic evidence path.",
                        next_action=(
                            "Bind the material claim to scenario requirements, Fabric "
                            "columns, Lex norms, Foundry method outputs, and claim "
                            "argument surfaces before serious closeout."
                        ),
                        claim_id=claim_id,
                        refs=(component, binding.binding_id, claim_id),
                        missing_input="claim_evidence_paths",
                        conflicting_producer=component,
                        affected_claim=claim_id,
                    )
                )
            for field, code, label in _CLAIM_EVIDENCE_CLOSURE_REQUIREMENTS:
                refs = _claim_path_axis_refs(paths, field)
                if refs:
                    continue
                issues.append(
                    _issue(
                        code,
                        f"Material claim is missing {label} in its semantic evidence path.",
                        next_action=(
                            "Regenerate claim evidence paths from scenario, Fabric, Lex, "
                            "Foundry, Scientist claim argument, and final compiler refs."
                        ),
                        claim_id=claim_id,
                        refs=(component, binding.binding_id, claim_id, field),
                        missing_input=field,
                        conflicting_producer=component,
                        affected_claim=claim_id,
                    )
                )
            has_superiority_path = any(_claim_path_is_superiority(path) for path in paths)
            has_comparison_refs = bool(_claim_path_axis_refs(paths, "comparison_refs"))
            if has_superiority_path and not has_comparison_refs:
                issues.append(
                    _issue(
                        "semantic_superiority_claim_comparison_refs_missing",
                        (
                            "Superiority claims cannot pass semantic binding without "
                            "W8.C baseline/alternative comparison records."
                        ),
                        next_action=(
                            "Compile baseline and alternative comparison records with "
                            "BaselineComparisonCompiler and bind comparison_refs to "
                            "the superiority claim before closeout."
                        ),
                        claim_id=claim_id,
                        refs=(component, binding.binding_id, claim_id, "comparison_refs"),
                        missing_input="comparison_refs",
                        conflicting_producer=component,
                        affected_claim=claim_id,
                    )
                )
    return issues


def _claim_path_is_superiority(path: ClaimEvidencePath) -> bool:
    tokens = {
        _optional_text(path.claim_use),
        _optional_text(path.claim_type),
        _optional_text(path.claim_family),
    }
    normalized = {token.casefold().replace("-", "_") for token in tokens if token}
    return bool(
        normalized
        & {
            "superiority",
            "comparative_superiority",
            "selected_option_superiority",
        }
    )


def _claim_path_axis_refs(
    paths: Sequence[ClaimEvidencePath],
    field: str,
) -> tuple[str, ...]:
    refs: list[str] = []
    for path in paths:
        refs.extend(_refs_from_value(getattr(path, field, ())))
    return tuple(dict.fromkeys(refs))


def _producer_spine_binding_issues(
    ledger: SemanticBindingLedger,
) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    if ledger.spine_context is None:
        if any(binding.claim_ids for binding in (*ledger.scientist, *ledger.final_compiler)):
            issues.append(
                _issue(
                    "semantic_spine_context_missing",
                    "Final claim bindings require a producer spine read context.",
                    next_action=(
                        "Build ProducerSpineReadContext from the per-run concept and "
                        "jurisdiction spine before producer evidence selection."
                    ),
                    refs=("spine_context",),
                )
            )
        return issues

    for component, binding in _producer_spine_records(ledger):
        affected_claim = _affected_claim_for_producer_binding(
            ledger,
            component=component,
            binding=binding,
        )
        if not binding.consumed_concept_spine_ref and not binding.spine_blocker_refs:
            issues.append(
                _issue(
                    "semantic_producer_concept_spine_ref_missing",
                    "Producer binding did not record the consumed concept spine ref.",
                    next_action=(
                        "Read concept_spine_ref from ProducerSpineReadContext or emit "
                        "a typed spine blocker."
                    ),
                    missing_input="consumed concept spine ref or typed spine blocker",
                    conflicting_producer=component,
                    affected_claim=affected_claim,
                    refs=(component, binding.binding_id),
                )
            )
        if not binding.consumed_jurisdiction_spine_ref and not binding.spine_blocker_refs:
            issues.append(
                _issue(
                    "semantic_producer_jurisdiction_spine_ref_missing",
                    "Producer binding did not record the consumed jurisdiction spine ref.",
                    next_action=(
                        "Read jurisdiction_spine_ref from ProducerSpineReadContext or emit "
                        "a typed spine blocker."
                    ),
                    missing_input="consumed jurisdiction spine ref or typed spine blocker",
                    conflicting_producer=component,
                    affected_claim=affected_claim,
                    refs=(component, binding.binding_id),
                )
            )
        if not binding.candidate_spine_binding_refs and not binding.spine_blocker_refs:
            issues.append(
                _issue(
                    "semantic_spine_candidate_binding_or_blocker_missing",
                    (
                        "Producer returned local labels without candidate spine "
                        "bindings or typed blockers."
                    ),
                    next_action=(
                        "Return candidate_spine_binding_refs from the shared spine "
                        "context or emit spine_blocker_refs."
                    ),
                    missing_input="candidate spine binding refs or typed spine blockers",
                    conflicting_producer=component,
                    affected_claim=affected_claim,
                    refs=(component, binding.binding_id, *binding.local_labels),
                )
            )
        if binding.local_labels:
            issues.append(
                _issue(
                    "semantic_local_concept_leakage",
                    "Producer leaked local concept labels into spine-bound evidence.",
                    next_action=(
                        "Replace local labels with stable candidate_spine_binding_refs "
                        "from the shared per-run spine."
                    ),
                    missing_input="stable spine refs replacing local concept labels",
                    conflicting_producer=component,
                    affected_claim=affected_claim,
                    refs=(component, binding.binding_id, *binding.local_labels),
                )
            )
        if (
            binding.consumed_concept_spine_ref
            and binding.consumed_concept_spine_ref != ledger.spine_context.concept_spine_ref
        ):
            issues.append(
                _issue(
                    "semantic_producer_concept_spine_ref_mismatch",
                    "Producer consumed a concept spine ref outside the shared run context.",
                    next_action=("Regenerate producer evidence against the per-run concept spine."),
                    missing_input="matching consumed concept spine ref",
                    conflicting_producer=component,
                    affected_claim=affected_claim,
                    refs=(
                        component,
                        binding.binding_id,
                        binding.consumed_concept_spine_ref,
                        ledger.spine_context.concept_spine_ref,
                    ),
                )
            )
        if (
            binding.consumed_jurisdiction_spine_ref
            and binding.consumed_jurisdiction_spine_ref
            != ledger.spine_context.jurisdiction_spine_ref
        ):
            issues.append(
                _issue(
                    "semantic_producer_jurisdiction_spine_ref_mismatch",
                    ("Producer consumed a jurisdiction spine ref outside the shared run context."),
                    next_action=(
                        "Regenerate producer evidence against the per-run jurisdiction spine."
                    ),
                    missing_input="matching consumed jurisdiction spine ref",
                    conflicting_producer=component,
                    affected_claim=affected_claim,
                    refs=(
                        component,
                        binding.binding_id,
                        binding.consumed_jurisdiction_spine_ref,
                        ledger.spine_context.jurisdiction_spine_ref,
                    ),
                )
            )
        issues.extend(
            _producer_semantic_dimension_mismatch_issues(
                ledger,
                component=component,
                binding=binding,
                affected_claim=affected_claim,
            )
        )
    return issues


def _producer_semantic_dimension_mismatch_issues(
    ledger: SemanticBindingLedger,
    *,
    component: str,
    binding: ProducerSpineBindingFields,
    affected_claim: str | None,
) -> list[SemanticBindingIssue]:
    if ledger.spine_context is None:
        return []
    issues: list[SemanticBindingIssue] = []
    for dimension, producer_values, spine_values, code in (
        (
            "concept",
            binding.canonical_concept_refs,
            ledger.spine_context.canonical_concept_refs,
            "semantic_producer_concept_mismatch",
        ),
        (
            "jurisdiction",
            binding.jurisdiction_refs,
            ledger.spine_context.jurisdiction_refs,
            "semantic_producer_jurisdiction_mismatch",
        ),
        (
            "unit",
            binding.unit_refs,
            ledger.spine_context.unit_refs,
            "semantic_producer_unit_mismatch",
        ),
        (
            "period",
            binding.period_refs,
            ledger.spine_context.period_refs,
            "semantic_producer_period_mismatch",
        ),
        (
            "geography",
            binding.geography_refs,
            ledger.spine_context.geography_refs,
            "semantic_producer_geography_mismatch",
        ),
    ):
        unexpected = _unexpected_semantic_refs(
            producer_values=producer_values,
            spine_values=spine_values,
        )
        if not unexpected:
            continue
        issues.append(
            _issue(
                code,
                f"Producer emitted {dimension} semantics outside the shared spine.",
                next_action=(
                    "Regenerate producer evidence against the per-run spine refs "
                    f"and reconciled {dimension} closure."
                ),
                missing_input=f"one reconciled {dimension} value from the shared spine",
                conflicting_producer=component,
                affected_claim=affected_claim,
                refs=(
                    component,
                    binding.binding_id,
                    *unexpected,
                    *tuple(spine_values),
                ),
            )
        )
    return issues


def _unexpected_semantic_refs(
    *,
    producer_values: Sequence[str],
    spine_values: Sequence[str],
) -> tuple[str, ...]:
    if not producer_values or not spine_values:
        return ()
    expected = {value.casefold() for value in spine_values}
    return tuple(value for value in producer_values if value.casefold() not in expected)


def _field_ref_matches_any(column_ref: str, field_refs: Sequence[str]) -> bool:
    column = column_ref.casefold()
    for field_ref in field_refs:
        normalized = field_ref.casefold()
        if normalized == column:
            return True
        if normalized.rsplit(".", maxsplit=1)[-1] == column:
            return True
        if normalized.rsplit(":", maxsplit=1)[-1] == column:
            return True
    return False


def _looks_manifest_role_ref(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return "manifest_role" in normalized or normalized in {
        "manifest",
        "source_manifest",
        "selected_manifest",
    }


def _affected_claim_for_producer_binding(
    ledger: SemanticBindingLedger,
    *,
    component: str,
    binding: ProducerSpineBindingFields,
) -> str | None:
    if isinstance(binding, ClaimBindingRecord):
        return _first_optional_ref(binding.claim_ids)
    claim_bindings = (*ledger.scientist, *ledger.final_compiler)
    if component == "fabric" and isinstance(binding, FabricBindingRecord):
        direct = _first_optional_ref(
            tuple(claim_id for metric in binding.metric_bindings for claim_id in metric.claim_ids)
        )
        if direct is not None:
            return direct
        refs = set(binding.selected_dataset_source_refs)
        return _first_claim_requiring(
            claim_bindings,
            lambda claim: bool(refs.intersection(claim.required_data_refs)),
        )
    if component == "lex" and isinstance(binding, LexBindingRecord):
        refs = set(binding.selected_norm_refs)
        return _first_claim_requiring(
            claim_bindings,
            lambda claim: bool(refs.intersection(claim.required_norm_refs)),
        )
    if component == "scholar" and isinstance(binding, ScholarBindingRecord):
        refs = set(binding.selected_literature_refs)
        return _first_claim_requiring(
            claim_bindings,
            lambda claim: bool(refs.intersection(claim.required_literature_refs)),
        )
    if component == "foundry" and isinstance(binding, FoundryBindingRecord):
        refs = set(binding.selected_method_refs)
        return _first_claim_requiring(
            claim_bindings,
            lambda claim: bool(refs.intersection(claim.required_method_refs)),
        )
    return None


def _first_claim_requiring(
    claims: Sequence[ClaimBindingRecord],
    predicate: Callable[[ClaimBindingRecord], bool],
) -> str | None:
    for claim in claims:
        if predicate(claim):
            return _first_optional_ref(claim.claim_ids)
    return None


def _first_optional_ref(values: object) -> str | None:
    for value in _refs_from_value(values):
        return value
    return None


def _final_claim_spine_ref_issues(
    ledger: SemanticBindingLedger,
) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    for final_binding in ledger.final_compiler:
        for data_ref in final_binding.required_data_refs:
            for fabric in _fabric_bindings_for_ref(ledger, data_ref):
                issues.extend(
                    _producer_claim_spine_mismatch_issues(
                        claim_binding=final_binding,
                        producer_component="fabric",
                        producer_binding=fabric,
                        evidence_ref=data_ref,
                    )
                )
        for norm_ref in final_binding.required_norm_refs:
            for lex in _lex_bindings_for_ref(ledger, norm_ref):
                issues.extend(
                    _producer_claim_spine_mismatch_issues(
                        claim_binding=final_binding,
                        producer_component="lex",
                        producer_binding=lex,
                        evidence_ref=norm_ref,
                    )
                )
        for literature_ref in final_binding.required_literature_refs:
            for scholar in _scholar_bindings_for_ref(ledger, literature_ref):
                issues.extend(
                    _producer_claim_spine_mismatch_issues(
                        claim_binding=final_binding,
                        producer_component="scholar",
                        producer_binding=scholar,
                        evidence_ref=literature_ref,
                    )
                )
        for method_ref in final_binding.required_method_refs:
            for foundry in _foundry_bindings_for_ref(ledger, method_ref):
                issues.extend(
                    _producer_claim_spine_mismatch_issues(
                        claim_binding=final_binding,
                        producer_component="foundry",
                        producer_binding=foundry,
                        evidence_ref=method_ref,
                    )
                )
    return issues


def _producer_claim_spine_mismatch_issues(
    *,
    claim_binding: ClaimBindingRecord,
    producer_component: str,
    producer_binding: ProducerSpineBindingFields,
    evidence_ref: str,
) -> list[SemanticBindingIssue]:
    issues: list[SemanticBindingIssue] = []
    for dimension, claim_ref, producer_ref in (
        (
            "concept",
            claim_binding.consumed_concept_spine_ref,
            producer_binding.consumed_concept_spine_ref,
        ),
        (
            "jurisdiction",
            claim_binding.consumed_jurisdiction_spine_ref,
            producer_binding.consumed_jurisdiction_spine_ref,
        ),
    ):
        if not claim_ref or not producer_ref or claim_ref == producer_ref:
            continue
        for claim_id in claim_binding.claim_ids or (claim_binding.binding_id,):
            issues.append(
                _issue(
                    "semantic_final_claim_spine_ref_mismatch",
                    (f"Final claim consumed evidence bound to a mismatched {dimension} spine ref."),
                    next_action=(
                        "Regenerate the final claim and producer evidence against the "
                        "same per-run spine refs."
                    ),
                    claim_id=claim_id,
                    missing_input=f"matching {dimension} spine ref across claim and producer",
                    conflicting_producer=producer_component,
                    affected_claim=claim_id,
                    refs=(
                        producer_component,
                        producer_binding.binding_id,
                        evidence_ref,
                        producer_ref,
                        claim_ref,
                    ),
                )
            )
    return issues


def _generic_collapse_issues(ledger: SemanticBindingLedger) -> list[SemanticBindingIssue]:
    if not _domain_specific_intent(ledger.intent):
        return []

    generic_refs: list[str] = []
    if _is_generic_text(ledger.intent.dataset):
        generic_refs.append(ledger.intent.dataset)
    for binding in ledger.fabric:
        generic_refs.extend(
            ref for ref in binding.selected_dataset_source_refs if _is_generic_text(ref)
        )
        generic_refs.extend(
            metric.metric_id
            for metric in binding.metric_bindings
            if _is_generic_text(metric.metric_id)
        )
    for binding in ledger.foundry:
        generic_refs.extend(ref for ref in binding.selected_method_refs if _is_generic_method(ref))
    lex_generic_no_law = any(
        lex.no_norm_blocker_refs
        and not lex.selected_norm_refs
        and any(
            _is_generic_text(ref) or "no-law" in ref.casefold() for ref in lex.no_norm_blocker_refs
        )
        for lex in ledger.lex
    )
    if not generic_refs and not lex_generic_no_law:
        return []
    refs = tuple(sorted(set(generic_refs)))
    if lex_generic_no_law:
        refs = (*refs, "generic_no_law_conclusion")
    return [
        _issue(
            "semantic_intent_collapsed_to_generic_evidence",
            "Domain-specific intent collapsed into generic legal/data/metric/method evidence.",
            next_action=(
                "Bind the domain-specific intent to domain-specific norms, datasets, "
                "metrics, and methods, or emit typed blockers."
            ),
            refs=refs,
        )
    ]


def _reason_family(
    *,
    ledger: SemanticBindingLedger,
    issues: list[SemanticBindingIssue],
    blocker_refs: tuple[str, ...],
) -> Literal["complete", "binding_failure", "retrieval_failure", "no_relevant_evidence"]:
    if issues:
        return "binding_failure"
    if any(lex.retrieval_error_blocker_refs for lex in ledger.lex) or any(
        scholar.retrieval_blocker_refs for scholar in ledger.scholar
    ):
        return "retrieval_failure"
    if blocker_refs:
        return "no_relevant_evidence"
    return "complete"


def _blocker_refs(ledger: SemanticBindingLedger) -> tuple[str, ...]:
    refs = {
        *_producer_handshake_blocker_refs(ledger.producer_handshake_ledger),
        *(ref for lex in ledger.lex for ref in lex.no_norm_blocker_refs),
        *(ref for lex in ledger.lex for ref in lex.retrieval_error_blocker_refs),
        *(ref for lex in ledger.lex for ref in lex.legal_authority_blocker_refs),
        *(ref for lex in ledger.lex for ref in lex.spine_blocker_refs),
        *(ref for fabric in ledger.fabric for ref in fabric.data_gap_blocker_refs),
        *(ref for fabric in ledger.fabric for ref in fabric.ambiguity_blocker_refs),
        *(ref for fabric in ledger.fabric for ref in fabric.spine_blocker_refs),
        *(ref for scholar in ledger.scholar for ref in scholar.retrieval_blocker_refs),
        *(ref for scholar in ledger.scholar for ref in scholar.spine_blocker_refs),
        *(ref for foundry in ledger.foundry for ref in foundry.method_incompatibility_blocker_refs),
        *(ref for foundry in ledger.foundry for ref in foundry.spine_blocker_refs),
        *(ref for claim in ledger.scientist for ref in claim.required_blocker_refs),
        *(ref for claim in ledger.scientist for ref in claim.spine_blocker_refs),
        *(ref for claim in ledger.final_compiler for ref in claim.required_blocker_refs),
        *(ref for claim in ledger.final_compiler for ref in claim.spine_blocker_refs),
    }
    return tuple(sorted(refs))


def _producer_handshake_blocker_refs(
    producer_handshake_ledger: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if not isinstance(producer_handshake_ledger, Mapping):
        return ()
    refs: list[str] = []
    for record in _rows_from(producer_handshake_ledger.get("records")):
        refs.extend(_refs_from_value(record.get("blocked_binding_refs")))
        for blocker in _rows_from(record.get("blockers")):
            refs.extend(_refs_from_value(blocker.get("refs")))
            code = _optional_text(blocker.get("code"))
            if code:
                refs.append(code)
    return tuple(dict.fromkeys(refs))


def _dedupe_issues(issues: list[SemanticBindingIssue]) -> list[SemanticBindingIssue]:
    seen: set[tuple[str, str | None, tuple[str, ...]]] = set()
    result: list[SemanticBindingIssue] = []
    for issue in issues:
        key = (issue.code, issue.claim_id, issue.refs)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _issue(
    code: str,
    message: str,
    *,
    next_action: str,
    claim_id: str | None = None,
    refs: Sequence[str] = (),
    missing_input: str | None = None,
    conflicting_producer: str | None = None,
    affected_claim: str | None = None,
    next_command: str | None = None,
) -> SemanticBindingIssue:
    has_operator_diagnostic = (
        missing_input is not None or conflicting_producer is not None or affected_claim is not None
    )
    return SemanticBindingIssue(
        code=code,
        message=message,
        next_action=next_action,
        claim_id=claim_id,
        refs=tuple(refs),
        missing_input=missing_input,
        conflicting_producer=conflicting_producer,
        affected_claim=affected_claim,
        next_command=next_command
        or (_SEMANTIC_SPINE_NEXT_COMMAND if has_operator_diagnostic else None),
    )


def _domain_specific_intent(intent: IntentBindingRecord) -> bool:
    values = (
        intent.legal_domain,
        intent.data_source_family,
        intent.outcome,
        intent.method_family,
        intent.population,
        intent.treatment,
    )
    return any(value and not _is_generic_text(value) for value in values)


def _is_generic_method(value: str) -> bool:
    normalized = value.casefold()
    return _is_generic_text(value) or normalized in {
        "descriptive.summary",
        "generic_descriptive_summary",
        "method_execution",
    }


def _is_generic_text(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    tokens = {token for token in normalized.replace(".", "_").split("_") if token}
    return bool(tokens.intersection(_GENERIC_TOKENS))


def _coerce_ref_tuple(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_non_empty(value) for value in values))


def _coerce_mapping_tuple(values: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise TypeError("binding entries must be mappings")
        result.append({str(key): item for key, item in value.items()})
    return tuple(result)


def _non_empty(value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("value must be non-empty")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_ref(payload: Mapping[str, Any] | Sequence[Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _mapping_value(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _producer_spine_context_from_inputs(
    *,
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
    runtime_refs: Mapping[str, Any],
    policy_intent: Mapping[str, Any],
) -> dict[str, Any] | None:
    if isinstance(spine_context, ProducerSpineReadContext):
        return spine_context.model_dump(mode="json")
    if isinstance(spine_context, Mapping):
        return ProducerSpineReadContext.model_validate(dict(spine_context)).model_dump(mode="json")
    concept_ref = _first_text(
        runtime_refs.get("concept_spine_ref"),
        runtime_refs.get("concept_ref"),
        policy_intent.get("concept_spine_ref"),
    )
    jurisdiction_ref = _first_text(
        runtime_refs.get("jurisdiction_spine_ref"),
        runtime_refs.get("jurisdiction_ref"),
        policy_intent.get("jurisdiction_spine_ref"),
    )
    if concept_ref == "unbound" or jurisdiction_ref == "unbound":
        return None
    return build_producer_spine_read_context(
        concept_spine_ref=concept_ref,
        jurisdiction_spine_ref=jurisdiction_ref,
        canonical_concept_refs=_refs_from(policy_intent, "canonical_concept_refs"),
        jurisdiction_refs=_refs_from(policy_intent, "jurisdiction_refs", "jurisdictions"),
        unit_refs=_refs_from(policy_intent, "unit_refs", "units"),
        period_refs=_refs_from(policy_intent, "period_refs", "periods", "time_windows"),
        geography_refs=_refs_from(policy_intent, "geography_refs", "geographies"),
    )


def _spine_fields_from_report(
    report: Mapping[str, Any],
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
    *,
    component: str | None = None,
    candidate_refs: Sequence[Any] | None = None,
    blocker_refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    context = (
        spine_context.model_dump(mode="json")
        if isinstance(spine_context, ProducerSpineReadContext)
        else dict(spine_context or {})
    )
    concept_ref = _first_text(
        report.get("consumed_concept_spine_ref"),
        report.get("concept_spine_ref"),
        context.get("concept_spine_ref"),
    )
    jurisdiction_ref = _first_text(
        report.get("consumed_jurisdiction_spine_ref"),
        report.get("jurisdiction_spine_ref"),
        context.get("jurisdiction_spine_ref"),
    )
    canonical_concepts = _refs_from(
        report,
        "canonical_concept_refs",
        "concept_refs",
        "consumed_concept_refs",
    ) or _refs_from_value(context.get("canonical_concept_refs"))
    jurisdictions = _refs_from(
        report,
        "jurisdiction_refs",
        "jurisdictions",
        "consumed_jurisdiction_refs",
    ) or _refs_from_value(context.get("jurisdiction_refs"))
    units = _refs_from(
        report,
        "unit_refs",
        "units",
        "consumed_unit_refs",
    ) or _refs_from_value(context.get("unit_refs"))
    periods = _refs_from(
        report,
        "period_refs",
        "periods",
        "time_refs",
        "time_windows",
        "consumed_period_refs",
    ) or _refs_from_value(context.get("period_refs"))
    geographies = _refs_from(
        report,
        "geography_refs",
        "geographies",
        "geo_refs",
        "consumed_geography_refs",
    ) or _refs_from_value(context.get("geography_refs"))
    explicit_candidates = _refs_from(
        report,
        "candidate_spine_binding_refs",
        "candidate_binding_refs",
        "spine_candidate_refs",
    )
    explicit_blockers = _blocker_ref_tuple(
        report,
        "spine_blocker_refs",
        "binding_blocker_refs",
        "spine_blockers",
    )
    generated_candidates = _producer_spine_candidate_binding_refs(
        component=component,
        context=context,
        candidate_refs=tuple(_refs_from_value(candidate_refs)),
    )
    generated_blockers = tuple(_refs_from_value(blocker_refs))
    candidates = tuple(dict.fromkeys([*explicit_candidates, *generated_candidates]))
    blockers = tuple(dict.fromkeys([*explicit_blockers, *generated_blockers]))
    if context and component and not candidates and not blockers:
        context_id = _optional_text(context.get("context_id")) or "unbound_context"
        blockers = (f"spine-blocker:{component}:candidate-binding-missing:{context_id}",)
    return {
        "consumed_concept_spine_ref": None if concept_ref == "unbound" else concept_ref,
        "consumed_jurisdiction_spine_ref": (
            None if jurisdiction_ref == "unbound" else jurisdiction_ref
        ),
        "canonical_concept_refs": canonical_concepts,
        "jurisdiction_refs": jurisdictions,
        "unit_refs": units,
        "period_refs": periods,
        "geography_refs": geographies,
        "candidate_spine_binding_refs": candidates,
        "spine_blocker_refs": blockers,
        "local_labels": _refs_from(
            report,
            "local_labels",
            "local_only_labels",
            "local_concept_labels",
        ),
    }


def _producer_spine_candidate_binding_refs(
    *,
    component: str | None,
    context: Mapping[str, Any],
    candidate_refs: Sequence[str],
) -> tuple[str, ...]:
    if not component or not context or not candidate_refs:
        return ()
    context_id = _optional_text(context.get("context_id")) or "unbound_context"
    concept_refs = _refs_from_value(context.get("canonical_concept_refs")) or ("unbound_concept",)
    jurisdiction_refs = _refs_from_value(context.get("jurisdiction_refs")) or (
        "unbound_jurisdiction",
    )
    refs: list[str] = []
    for candidate in candidate_refs:
        if candidate.startswith("spine-binding:"):
            refs.append(candidate)
            continue
        candidate_key = _stable_ref(
            {
                "context_id": context_id,
                "component": component,
                "candidate_ref": candidate,
            }
        ).removeprefix("sha256:")[:16]
        for concept_ref in concept_refs:
            for jurisdiction_ref in jurisdiction_refs:
                refs.append(
                    f"spine-binding:{component}:{concept_ref}:{jurisdiction_ref}:{candidate_key}"
                )
    return tuple(dict.fromkeys(refs))


def _spine_ref_from_mapping(
    spine: Mapping[str, Any] | None,
    *keys: str,
) -> str | None:
    if not isinstance(spine, Mapping):
        return None
    direct = _first_text(*(spine.get(key) for key in keys))
    if direct != "unbound":
        return direct
    authority = spine.get("runtime_authority_envelope") or spine.get("runtime_authority")
    if isinstance(authority, Mapping):
        return _first_text(authority.get("artifact_ref"), authority.get("cas_ref"))
    return None


def _jurisdiction_refs_from_spine(
    spine: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if not isinstance(spine, Mapping):
        return ()
    refs: list[str] = []
    for row in _rows_from(spine.get("jurisdictions")):
        ref = (
            _optional_text(row.get("jurisdiction_id"))
            or _optional_text(row.get("jurisdiction"))
            or _optional_text(row.get("id"))
        )
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _concept_spine_semantic_refs(
    spine: Mapping[str, Any] | None,
    *keys: str,
) -> tuple[str, ...]:
    if not isinstance(spine, Mapping):
        return ()
    refs: list[str] = []
    for key in keys:
        refs.extend(_refs_from_value(spine.get(key)))
    for row in _rows_from(spine.get("canonical_concepts")):
        for key in keys:
            refs.extend(_refs_from_value(row.get(key)))
    return tuple(dict.fromkeys(refs))


def _producer_spine_records(
    ledger: SemanticBindingLedger,
) -> tuple[tuple[str, ProducerSpineBindingFields], ...]:
    records: list[tuple[str, ProducerSpineBindingFields]] = []
    records.extend(("lex", binding) for binding in ledger.lex)
    records.extend(("fabric", binding) for binding in ledger.fabric)
    records.extend(("scholar", binding) for binding in ledger.scholar)
    records.extend(("foundry", binding) for binding in ledger.foundry)
    records.extend(("scientist", binding) for binding in ledger.scientist)
    records.extend(("final_compiler", binding) for binding in ledger.final_compiler)
    return tuple(records)


def _fabric_bindings_for_ref(
    ledger: SemanticBindingLedger,
    ref: str,
) -> tuple[FabricBindingRecord, ...]:
    return tuple(
        binding for binding in ledger.fabric if ref in binding.selected_dataset_source_refs
    )


def _lex_bindings_for_ref(
    ledger: SemanticBindingLedger,
    ref: str,
) -> tuple[LexBindingRecord, ...]:
    return tuple(binding for binding in ledger.lex if ref in binding.selected_norm_refs)


def _scholar_bindings_for_ref(
    ledger: SemanticBindingLedger,
    ref: str,
) -> tuple[ScholarBindingRecord, ...]:
    return tuple(binding for binding in ledger.scholar if ref in binding.selected_literature_refs)


def _foundry_bindings_for_ref(
    ledger: SemanticBindingLedger,
    ref: str,
) -> tuple[FoundryBindingRecord, ...]:
    return tuple(binding for binding in ledger.foundry if ref in binding.selected_method_refs)


def _rows_from(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _mapping_from(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _refs_from(payload: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    refs: list[str] = []
    for key in keys:
        refs.extend(_refs_from_value(payload.get(key)))
    return tuple(dict.fromkeys(refs))


def _refs_from_value(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        ref = (
            _optional_text(value.get("ref"))
            or _optional_text(value.get("id"))
            or _optional_text(value.get("snapshot_ref"))
            or _optional_text(value.get("legal_snapshot_ref"))
            or _optional_text(value.get("query_ref"))
            or _optional_text(value.get("concept_ref"))
            or _optional_text(value.get("conflict_id"))
            or _optional_text(value.get("competence_ref"))
            or _optional_text(value.get("field_ref"))
            or _optional_text(value.get("feature_ref"))
            or _optional_text(value.get("unit_ref"))
            or _optional_text(value.get("lineage_ref"))
            or _optional_text(value.get("transformation_ref"))
            or _optional_text(value.get("source_id"))
            or _optional_text(value.get("source_ref"))
            or _optional_text(value.get("norm_id"))
            or _optional_text(value.get("method_id"))
            or _optional_text(value.get("method_ref"))
            or _optional_text(value.get("method_output_ref"))
            or _optional_text(value.get("method_result_ref"))
            or _optional_text(value.get("result_ref"))
            or _optional_text(value.get("assumption_gate_ref"))
            or _optional_text(value.get("gate_ref"))
            or _optional_text(value.get("uncertainty_envelope_ref"))
            or _optional_text(value.get("limitation_ref"))
            or _optional_text(value.get("claim_id"))
        )
        if ref:
            return (ref,)
        refs: list[str] = []
        for item in value.values():
            refs.extend(_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    text = _optional_text(value)
    return (text,) if text else ()


def _json_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_value(value) for key, value in payload.items()}


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _json_mapping(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            for item in value:
                text = _optional_text(item)
                if text:
                    return text
            continue
        text = _optional_text(value)
        if text:
            return text
    return "unbound"


def _claim_rows(
    *,
    final_claims: Sequence[Mapping[str, Any]] | None,
    grounding_report: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if final_claims:
        return tuple(item for item in final_claims if isinstance(item, Mapping))
    claims = grounding_report.get("claims")
    return _rows_from(claims)


def _claim_id(claim: Mapping[str, Any]) -> str | None:
    return (
        _optional_text(claim.get("claim_id"))
        or _optional_text(claim.get("id"))
        or _optional_text(claim.get("statement_id"))
    )


def _first_claim_id(claims: Sequence[Mapping[str, Any]]) -> str | None:
    for claim in claims:
        claim_id = _claim_id(claim)
        if claim_id:
            return claim_id
    return None


def _first_claim_text(claims: Sequence[Mapping[str, Any]]) -> str | None:
    for claim in claims:
        text = _optional_text(claim.get("text")) or _optional_text(claim.get("statement"))
        if text:
            return text
    return None


def _refs_from_claims(claims: Sequence[Mapping[str, Any]], key: str) -> tuple[str, ...]:
    refs: list[str] = []
    for claim in claims:
        refs.extend(_refs_from_value(claim.get(key)))
    return tuple(dict.fromkeys(refs))


def _ids_by_type(claims: Sequence[Mapping[str, Any]], *tokens: str) -> tuple[str, ...]:
    wanted = {token.casefold() for token in tokens}
    ids: list[str] = []
    for claim in claims:
        claim_type = str(claim.get("claim_type") or claim.get("statement_type") or "").casefold()
        claim_id = _claim_id(claim)
        if claim_id and any(token in claim_type for token in wanted):
            ids.append(claim_id)
    return tuple(dict.fromkeys(ids))


def _norm_refs_from_rows(value: object) -> tuple[str, ...]:
    refs: list[str] = []
    for row in _rows_from(value):
        ref = (
            _optional_text(row.get("norm_id"))
            or _optional_text(row.get("norm_ref"))
            or _optional_text(row.get("ref"))
            or _optional_text(row.get("id"))
        )
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _source_refs_from_rows(value: object) -> tuple[str, ...]:
    refs: list[str] = []
    for row in _rows_from(value):
        ref = (
            _optional_text(row.get("source_id"))
            or _optional_text(row.get("source_ref"))
            or _optional_text(row.get("dataset_id"))
            or _optional_text(row.get("ref"))
            or _optional_text(row.get("id"))
        )
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _method_refs_from_rows(value: object) -> tuple[str, ...]:
    refs: list[str] = []
    for row in _rows_from(value):
        ref = (
            _optional_text(row.get("method_id"))
            or _optional_text(row.get("method_ref"))
            or _optional_text(row.get("ref"))
            or _optional_text(row.get("id"))
        )
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _rejected_method_reasons(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    reasons: list[dict[str, Any]] = []
    for row in rows:
        method_ref = (
            _optional_text(row.get("method_id"))
            or _optional_text(row.get("method_ref"))
            or _optional_text(row.get("id"))
        )
        reason_code = _optional_text(row.get("reason_code") or row.get("code"))
        reason = _optional_text(row.get("reason") or row.get("rationale"))
        if not method_ref and not reason_code and not reason:
            continue
        payload: dict[str, Any] = {}
        if method_ref:
            payload["method_ref"] = method_ref
        if reason_code:
            payload["reason_code"] = reason_code
        if reason:
            payload["reason"] = reason
        result_refs = _refs_from_value(row.get("result_refs"))
        if result_refs:
            payload["result_refs"] = result_refs
        reasons.append(payload)
    return tuple(reasons)


def _method_output_refs_from_method(method: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(_refs_from(method, "method_output_refs", "method_result_refs", "result_refs"))
    for key in ("method_result_refs", "result_refs"):
        value = method.get(key)
        if isinstance(value, Mapping):
            for item in value.values():
                refs.extend(_refs_from_value(item))
    method_id = _optional_text(method.get("method_id") or method.get("method_ref"))
    if not refs and method_id:
        refs.append(f"method-output:{method_id}")
    return tuple(dict.fromkeys(refs))


def _literature_refs_from_rows(value: object) -> tuple[str, ...]:
    refs: list[str] = []
    for row in _rows_from(value):
        ref = (
            _optional_text(row.get("literature_ref"))
            or _optional_text(row.get("source_ref"))
            or _optional_text(row.get("paper_ref"))
            or _optional_text(row.get("citation_ref"))
            or _optional_text(row.get("ref"))
            or _optional_text(row.get("id"))
        )
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _candidate_source_refs(fabric_report: Mapping[str, Any]) -> tuple[str, ...]:
    return _source_refs_from_rows(
        fabric_report.get("candidate_sources") or fabric_report.get("source_candidates")
    )


def _selected_source_refs(fabric_report: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = _refs_from(fabric_report, "selected_source_ids", "selected_dataset_source_refs")
    if explicit:
        return explicit
    return _source_refs_from_rows(fabric_report.get("selected_sources"))


def _selected_method_refs(
    foundry_report: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    explicit = _refs_from(foundry_report, "selected_method_refs")
    rows = _method_refs_from_rows(foundry_report.get("selected_methods"))
    claim_refs = _refs_from_claims(claims, "method_refs")
    return tuple(dict.fromkeys([*explicit, *rows, *claim_refs]))


def _first_candidate_field(fabric_report: Mapping[str, Any], field: str) -> str | None:
    for row in _rows_from(fabric_report.get("candidate_sources")):
        text = _optional_text(row.get(field))
        if text:
            return text
    return None


def _first_selected_method_field(foundry_report: Mapping[str, Any], field: str) -> str | None:
    for row in _rows_from(foundry_report.get("selected_methods")):
        text = _optional_text(row.get(field))
        if text:
            return text
    return None


def _candidate_columns(
    fabric_report: Mapping[str, Any],
    source_ref: str | None,
) -> tuple[str, ...]:
    if source_ref is None:
        return ()
    for row in _rows_from(fabric_report.get("candidate_sources")):
        row_ref = (
            _optional_text(row.get("source_id"))
            or _optional_text(row.get("source_ref"))
            or _optional_text(row.get("dataset_id"))
        )
        if row_ref == source_ref:
            return _refs_from_value(row.get("available_columns") or row.get("columns"))
    return ()


def _data_forge_snapshot_refs(
    *,
    fabric_report: Mapping[str, Any],
    data_forge_snapshot_binding: Mapping[str, Any],
) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(_refs_from(fabric_report, "data_forge_snapshot_refs", "data_forge_refs"))
    for row in [
        *_rows_from(fabric_report.get("selected_sources")),
        *_rows_from(fabric_report.get("candidate_sources")),
        *_rows_from(fabric_report.get("source_candidates")),
    ]:
        refs.extend(_refs_from_value(row.get("data_forge_snapshot_refs")))
    for row in _rows_from(data_forge_snapshot_binding.get("bindings")):
        refs.extend(
            _refs_from_value(
                row.get("snapshot_ref")
                or row.get("manifest_ref")
                or row.get("manifest_artifact_id")
            )
        )
    refs.extend(_refs_from_value(data_forge_snapshot_binding.get("data_forge_snapshot_refs")))
    return tuple(dict.fromkeys(refs))


def _source_facets_from_fabric_report(
    *,
    fabric_report: Mapping[str, Any],
    selected: Sequence[str],
    rejected: Sequence[str],
    data_forge_snapshot_refs: Sequence[str],
) -> tuple[dict[str, Any], ...]:
    rows_by_ref = _source_rows_by_ref(fabric_report)
    explicit_rows = _rows_from(fabric_report.get("source_facets"))
    facets: list[dict[str, Any]] = []
    for explicit in explicit_rows:
        facet = dict(explicit)
        source_ref = _first_text(facet.get("source_ref"), facet.get("source_id"))
        if source_ref == "unbound":
            continue
        facet.setdefault("source_ref", source_ref)
        facet.setdefault("data_forge_snapshot_refs", tuple(data_forge_snapshot_refs))
        facets.append(_json_mapping(facet))
    existing = {_optional_text(facet.get("source_ref")) for facet in facets}
    for source_ref in selected:
        if source_ref in existing:
            continue
        row = rows_by_ref.get(source_ref, {})
        facets.append(
            _json_mapping(
                _source_facet_from_row(
                    row=row,
                    source_ref=source_ref,
                    rejected=rejected,
                    data_forge_snapshot_refs=data_forge_snapshot_refs,
                )
            )
        )
    return tuple(facets)


def _source_rows_by_ref(fabric_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for key in ("selected_sources", "candidate_sources", "source_candidates"):
        for row in _rows_from(fabric_report.get(key)):
            source_ref = (
                _optional_text(row.get("source_id"))
                or _optional_text(row.get("source_ref"))
                or _optional_text(row.get("dataset_id"))
                or _optional_text(row.get("id"))
            )
            if source_ref:
                rows.setdefault(source_ref, row)
    return rows


def _source_facet_from_row(
    *,
    row: Mapping[str, Any],
    source_ref: str,
    rejected: Sequence[str],
    data_forge_snapshot_refs: Sequence[str],
) -> dict[str, Any]:
    freshness = row.get("freshness") if isinstance(row.get("freshness"), Mapping) else {}
    coverage = row.get("coverage") if isinstance(row.get("coverage"), Mapping) else {}
    schema_compatibility = (
        row.get("schema_compatibility")
        if isinstance(row.get("schema_compatibility"), Mapping)
        else {}
    )
    return {
        "source_ref": source_ref,
        "source_family": _first_text(
            row.get("source_family"),
            row.get("family"),
            row.get("data_source_family"),
            "unbound_source_family",
        ),
        "source_rights": _first_text(
            row.get("source_rights"),
            row.get("rights"),
            row.get("license"),
            "unbound_source_rights",
        ),
        "dataset_ref": _first_text(row.get("dataset_ref"), row.get("dataset_id"), source_ref),
        "dictionary_ref": _first_text(
            row.get("dictionary_ref"),
            row.get("data_dictionary_ref"),
            row.get("dictionary_refs"),
            "unbound_dictionary",
        ),
        "schema_ref": _first_text(row.get("schema_ref"), row.get("schema_id"), "unbound_schema"),
        "field_refs": _refs_from_value(
            row.get("field_refs")
            or row.get("fields")
            or row.get("available_columns")
            or row.get("columns")
            or schema_compatibility.get("required_fields")
        ),
        "unit_refs": _refs_from_value(row.get("unit_refs") or row.get("units")),
        "geography_refs": _refs_from_value(
            row.get("geography_refs")
            or row.get("geography")
            or coverage.get("geography")
        ),
        "time_coverage_refs": _refs_from_value(
            row.get("time_coverage_refs")
            or row.get("time_coverage")
            or row.get("time_window")
            or coverage.get("time_window")
        ),
        "quality_refs": _refs_from_value(row.get("quality_refs") or row.get("quality")),
        "missingness_refs": _refs_from_value(
            row.get("missingness_refs")
            or row.get("missingness")
        ),
        "freshness_refs": _refs_from_value(row.get("freshness_refs") or freshness.get("ref")),
        "lineage_refs": _refs_from_value(row.get("lineage_refs") or row.get("lineage")),
        "transformation_refs": _refs_from_value(
            row.get("transformation_refs")
            or row.get("transformations")
        ),
        "data_forge_snapshot_refs": tuple(
            dict.fromkeys(
                [
                    *_refs_from_value(row.get("data_forge_snapshot_refs")),
                    *data_forge_snapshot_refs,
                ]
            )
        ),
        "selected_candidate_ref": source_ref,
        "rejected_candidate_refs": tuple(rejected),
    }


def _derived_features_from_fabric_report(
    *,
    fabric_report: Mapping[str, Any],
    selected: Sequence[str],
    claims: Sequence[Mapping[str, Any]],
    metric_id: str,
    source_facets: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    source_facet_refs = {
        str(facet.get("source_ref")): _refs_from_value(facet.get("field_refs"))
        for facet in source_facets
    }
    raw_rows: list[Mapping[str, Any]] = []
    raw_rows.extend(_rows_from(fabric_report.get("derived_features")))
    for row in [
        *_rows_from(fabric_report.get("selected_sources")),
        *_rows_from(fabric_report.get("candidate_sources")),
    ]:
        raw_rows.extend(_rows_from(row.get("derived_features")))
    rows: list[dict[str, Any]] = []
    claim_ids = tuple(dict.fromkeys(_claim_id(row) for row in claims if _claim_id(row)))
    for raw in raw_rows:
        feature = dict(raw)
        source_ref = _first_text(feature.get("source_ref"), *(selected or ("unbound",)))
        feature.setdefault("source_ref", source_ref)
        feature.setdefault("feature_ref", _first_text(feature.get("feature_id"), metric_id))
        feature.setdefault("source_facet_refs", source_facet_refs.get(source_ref, ()))
        feature.setdefault("claim_ids", claim_ids)
        feature.setdefault(
            "claim_support_feature_refs",
            tuple(
                f"claim-feature:{claim_id}:{feature['feature_ref']}"
                for claim_id in claim_ids
                if claim_id
            ),
        )
        rows.append(_json_mapping(feature))
    return tuple(rows)


def _mapping_tuple_from(payload: Mapping[str, Any], *keys: str) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for key in keys:
        value = payload.get(key)
        rows.extend(dict(row) for row in _rows_from(value))
    return tuple(rows)


def _source_freshness(fabric_report: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    explicit = _mapping_tuple_from(fabric_report, "source_freshness")
    if explicit:
        return explicit
    rows: list[dict[str, Any]] = []
    for row in _rows_from(fabric_report.get("candidate_sources")):
        source_ref = (
            _optional_text(row.get("source_id"))
            or _optional_text(row.get("source_ref"))
            or _optional_text(row.get("dataset_id"))
        )
        freshness = row.get("freshness")
        if source_ref and isinstance(freshness, Mapping):
            rows.append({"source_ref": source_ref, **dict(freshness)})
    return tuple(rows)


def _blocker_ref_tuple(payload: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    refs: list[str] = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            refs.append(value)
        else:
            for row in _rows_from(value):
                ref = (
                    _optional_text(row.get("blocker_ref"))
                    or _optional_text(row.get("ref"))
                    or _optional_text(row.get("code"))
                    or _optional_text(row.get("reason_code"))
                    or _optional_text(row.get("id"))
                )
                if ref:
                    refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _authority_blocker_refs_by_family(
    payload: Mapping[str, Any],
    families: set[str],
) -> tuple[str, ...]:
    refs: list[str] = []
    for row in [
        *_rows_from(payload.get("authority_blockers")),
        *_rows_from(payload.get("blockers")),
    ]:
        code = _optional_text(row.get("code")) or _optional_text(row.get("reason_code"))
        blocker_type = _optional_text(row.get("blocker_type")) or _optional_text(
            row.get("family")
        )
        tokens = {code.casefold(), blocker_type.casefold()}
        if not tokens.intersection(families):
            continue
        ref = (
            _optional_text(row.get("blocker_ref"))
            or _optional_text(row.get("ref"))
            or code
            or blocker_type
            or _optional_text(row.get("id"))
        )
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _sample_power_status(row: Mapping[str, Any]) -> str:
    diagnostics = row.get("input_diagnostics")
    if not isinstance(diagnostics, Mapping):
        return "unknown"
    sample_size = diagnostics.get("sample_size")
    minimum = diagnostics.get("min_required_sample_size")
    try:
        return "adequate" if float(sample_size) >= float(minimum) else "inadequate"
    except (TypeError, ValueError):
        return "unknown"


__all__ = [
    "PRODUCER_SPINE_CONSUMER_COMPONENTS",
    "PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION",
    "SEMANTIC_BINDING_SCHEMA_VERSION",
    "ClaimBindingRecord",
    "ColumnBinding",
    "CoverageBinding",
    "DerivedFeatureBinding",
    "FabricBindingRecord",
    "FoundryBindingRecord",
    "GySemanticBenchmark",
    "IntentBindingRecord",
    "LexBindingRecord",
    "MetricBinding",
    "ProducerSpineReadContext",
    "ScholarBindingRecord",
    "SemanticAdequacyGate",
    "SemanticBenchmarkRun",
    "SemanticBindingError",
    "SemanticBindingEvaluation",
    "SemanticBindingIssue",
    "SemanticBindingLedger",
    "SourceFacetBinding",
    "authority_envelopes_missing_semantic_binding_ref",
    "build_producer_spine_binding_fields",
    "build_producer_spine_read_context",
    "build_semantic_binding_ledger",
    "close_semantic_binding_ledger",
    "deserialize_semantic_binding_ledger",
    "evaluate_semantic_binding_ledger",
    "load_gy_semantic_benchmark",
    "producer_spine_read_context_for",
]
