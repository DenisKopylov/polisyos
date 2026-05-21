"""Metric registry definitions shared by problem frames, evidence, and runtime reporting."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from difflib import get_close_matches

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel

PRODUCTION_METRIC_TAXONOMY_VERSION = "2026.05.19"
PRODUCTION_METRIC_CANONICALIZER = "production_metric_taxonomy.v1"


class MetricSpec(KernelModel):
    """Describe a named metric id plus the unit and semantics other contracts should reuse."""

    metric_id: str = Field(..., pattern=ID_PATTERN)
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=200)


class MetricRegistry(KernelModel):
    """Registry of metric definitions that problem frames and compiled artifacts reference by id."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    metrics: dict[str, MetricSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_metrics(self) -> MetricRegistry:
        for key, spec in self.metrics.items():
            if not key or not isinstance(key, str):
                raise ValueError("metric id must be a non-empty string")
            if key != spec.metric_id:
                raise ValueError(f"metric id mismatch: '{key}' != '{spec.metric_id}'")
        return self


class MetricTaxonomyEntry(KernelModel):
    """Versioned production metric taxonomy entry."""

    metric_id: str = Field(..., pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=240)
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    owner: str = Field("team-ir", max_length=80)
    sources: tuple[str, ...] = Field(default_factory=tuple)
    aliases: tuple[str, ...] = Field(default_factory=tuple)


class ProductionMetricTaxonomy(KernelModel):
    """Canonical production metric ids, aliases, provenance, and evidence."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    taxonomy_version: str = Field(default=PRODUCTION_METRIC_TAXONOMY_VERSION)
    canonicalizer: str = Field(default=PRODUCTION_METRIC_CANONICALIZER)
    metrics: dict[str, MetricTaxonomyEntry] = Field(default_factory=dict)
    aliases: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_taxonomy(self) -> ProductionMetricTaxonomy:
        for metric_id, entry in self.metrics.items():
            if metric_id != entry.metric_id:
                raise ValueError(f"metric taxonomy id mismatch: {metric_id} != {entry.metric_id}")
        for alias, metric_id in self.aliases.items():
            if metric_id not in self.metrics:
                raise ValueError(f"metric alias '{alias}' points to unknown metric '{metric_id}'")
        return self

    @property
    def fingerprint(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "taxonomy_version": self.taxonomy_version,
            "canonicalizer": self.canonicalizer,
            "metrics": {
                metric_id: self.metrics[metric_id].model_dump(mode="json")
                for metric_id in sorted(self.metrics)
            },
            "aliases": {alias: self.aliases[alias] for alias in sorted(self.aliases)},
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def evidence(self) -> dict[str, object]:
        """Return the stable evidence payload persisted by runtime canaries."""
        return {
            "schema_version": self.schema_version,
            "taxonomy_version": self.taxonomy_version,
            "metric_count": len(self.metrics),
            "alias_count": len(self.aliases),
            "canonicalizer": self.canonicalizer,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class MetricCanonicalizationResult:
    """Canonical metric id plus diagnostics safe to store in evidence."""

    metric_id: str
    changed: bool
    diagnostics: list[dict[str, object]]


class MetricTaxonomyValidationError(ValueError):
    """Unknown production metric failure with suggestions and evidence context."""

    def __init__(
        self,
        unknown_metrics: Sequence[str],
        *,
        suggestions: Mapping[str, Sequence[str]],
        taxonomy: ProductionMetricTaxonomy,
        diagnostics: Sequence[Mapping[str, object]] | None = None,
    ) -> None:
        self.unknown_metrics = [str(item) for item in unknown_metrics]
        self.suggestions = {
            str(metric): [str(item) for item in values]
            for metric, values in suggestions.items()
        }
        self.diagnostics = [dict(item) for item in diagnostics or []]
        suggestion_parts = []
        for metric in self.unknown_metrics:
            matches = self.suggestions.get(metric) or []
            suggestion_parts.append(
                f"{metric} -> {', '.join(matches)}" if matches else f"{metric} -> no close match"
            )
        message = "Unknown production metric(s): " + "; ".join(suggestion_parts)
        super().__init__(message)
        self.failure = {
            "code": "unknown_production_metric",
            "layer": "metric_taxonomy",
            "phase": "metric_taxonomy",
            "message": message,
            "retryable": False,
            "unknown_metrics": self.unknown_metrics,
            "suggestions": self.suggestions,
            "diagnostics": self.diagnostics,
            "taxonomy": taxonomy.evidence(),
            "next_action": (
                "Use one of the suggested canonical production metric ids or add the metric "
                "to the versioned production metric taxonomy before running a serious workflow."
            ),
        }


_METRIC_ID_ALIASES = {
    "macro.gdp": "gdp",
    "gross_domestic_product": "gdp",
    "gdp_pct_change": "gdp_change",
    "gdp_percent_change": "gdp_change",
    "msme_credit_volume": "msme_loan_volume",
    "msme_credit_disbursed": "msme_loan_volume",
    "sme_credit_volume": "msme_loan_volume",
    "loan_volume_msme": "msme_loan_volume",
    "msme_survival": "msme_survival_rate",
    "msme_survival_pct": "msme_survival_rate",
    "sme_survival": "sme_survival_rate",
    "small_business_survival": "small_business_survival_rate",
    "small_business_survival_pct": "small_business_survival_rate",
    "jobs_retention": "employment_retention",
    "jobs_retained": "employment_retention",
    "employment_retained": "employment_retention",
    "employment_preservation": "employment_retention",
    "employment_retention_pct": "employment_retention_rate",
    "fraud_rate": "fraud_incidence_rate",
    "fraud_incidence": "fraud_incidence_rate",
    "treatment_effect": "ate_estimate",
    "average_treatment_effect": "ate_estimate",
    "causal_paths": "causal_pathway_count",
    "transportability_score": "model_transport_score",
}


_PRODUCTION_DATA_CONTRACT_METRICS = {
    "msme_survival_rate": "MSME survival outcome used by production-data canaries",
    "employment_retention_rate": "Employment retention outcome used by labor policy canaries",
    "small_business_survival_rate": "Small business survival outcome from golden scenarios",
    "digital_productivity_gain": "Digital training productivity outcome from golden scenarios",
    "farm_recovery_rate": "Agricultural recovery outcome from golden scenarios",
    "household_disposable_income_stability": (
        "Household disposable-income stability outcome for social benefit and tax relief scenarios"
    ),
    "essential_medicine_access_rate": (
        "Essential medicine access-rate outcome for healthcare shortage scenarios"
    ),
    "critical_outage_hours_reduced": (
        "Critical outage-hours reduction outcome for infrastructure and energy scenarios"
    ),
    "post_training_employment_rate": (
        "Post-training employment-rate outcome for education and reskilling scenarios"
    ),
    "eligible_household_access_rate": (
        "Eligible household access-rate outcome for benefit exclusion scenarios"
    ),
}

_BENCHMARK_METRICS = {
    "ate_rmse": "Average treatment effect benchmark RMSE",
    "failure_rate": "Benchmark failure rate",
    "ci_coverage": "Confidence interval coverage benchmark metric",
    "ci_width": "Confidence interval width benchmark metric",
    "policy_value_top_q": "Top-quantile policy value benchmark metric",
    "wasserstein_error": "Distributional benchmark Wasserstein error",
    "quantile_error": "Distributional benchmark quantile error",
    "tail_risk_error": "Distributional benchmark tail-risk error",
    "budget_enforcement_rate": "Strategic solver budget enforcement benchmark metric",
    "replay_success_rate": "Replay benchmark success rate",
    "lineage_complete_rate": "Lineage benchmark completion rate",
}


def _metric_lookup_key(metric_id: str) -> str:
    key = str(metric_id or "").strip().lower()
    key = re.sub(r"[\s\-/]+", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    return key


def _iter_metric_ids(value: object) -> Iterable[str]:
    if isinstance(value, str):
        text = value.strip()
        if text:
            yield text
        return
    if isinstance(value, Mapping):
        for key in (
            "metric",
            "metric_id",
            "output_metric",
            "outcome_metric",
            "query_outcome",
            "primary_metric",
        ):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                yield raw.strip()
        for nested_key in ("metrics", "expected_metrics", "outputs", "expected_outputs"):
            nested = value.get(nested_key)
            yield from _iter_metric_ids(nested)
        return
    if isinstance(value, Iterable):
        for item in value:
            yield from _iter_metric_ids(item)


def _entry_with_source(
    spec: MetricSpec,
    *,
    source: str,
    owner: str,
    aliases: Sequence[str] = (),
) -> MetricTaxonomyEntry:
    return MetricTaxonomyEntry(
        metric_id=spec.metric_id,
        description=spec.description,
        unit_id=spec.unit_id,
        owner=owner,
        sources=(source,),
        aliases=tuple(sorted({_metric_lookup_key(alias) for alias in aliases if alias})),
    )


def _merge_entry(
    entries: dict[str, MetricTaxonomyEntry],
    metric_id: str,
    *,
    description: str | None,
    unit_id: str | None = None,
    owner: str,
    source: str,
    aliases: Sequence[str] = (),
) -> None:
    existing = entries.get(metric_id)
    alias_values = tuple(sorted({_metric_lookup_key(alias) for alias in aliases if alias}))
    if existing is None:
        entries[metric_id] = MetricTaxonomyEntry(
            metric_id=metric_id,
            description=description,
            unit_id=unit_id,
            owner=owner,
            sources=(source,),
            aliases=alias_values,
        )
        return
    entries[metric_id] = existing.model_copy(
        update={
            "description": existing.description or description,
            "unit_id": existing.unit_id or unit_id,
            "sources": tuple(sorted({*existing.sources, source})),
            "aliases": tuple(sorted({*existing.aliases, *alias_values})),
        }
    )


def build_production_metric_taxonomy(
    *,
    registry: MetricRegistry | None = None,
    production_contract_metrics: Mapping[str, str] | Sequence[str] | None = None,
    benchmark_metrics: Mapping[str, str] | Sequence[str] | None = None,
    scenario_expected_outputs: object = None,
) -> ProductionMetricTaxonomy:
    """Build the versioned taxonomy used before Trinity linking and workflow execution."""
    source_registry = registry or DEFAULT_METRIC_REGISTRY
    entries: dict[str, MetricTaxonomyEntry] = {
        metric_id: _entry_with_source(spec, source="metric_registry", owner="team-ir")
        for metric_id, spec in source_registry.metrics.items()
    }

    def _merge_source(source_metrics: Mapping[str, str] | Sequence[str], *, source: str) -> None:
        if isinstance(source_metrics, Mapping):
            items = source_metrics.items()
        else:
            items = ((str(metric_id), None) for metric_id in source_metrics)
        for raw_metric_id, raw_description in items:
            metric_id = _metric_lookup_key(str(raw_metric_id))
            if not metric_id:
                continue
            _merge_entry(
                entries,
                metric_id,
                description=str(raw_description) if raw_description else None,
                owner="team-runtime" if source.startswith("production") else "team-quality",
                source=source,
            )

    _merge_source(
        production_contract_metrics or _PRODUCTION_DATA_CONTRACT_METRICS,
        source="production_data_contract",
    )
    _merge_source(benchmark_metrics or _BENCHMARK_METRICS, source="benchmark_metric")
    scenario_metric_ids = sorted(
        {_metric_lookup_key(item) for item in _iter_metric_ids(scenario_expected_outputs)}
    )
    if scenario_metric_ids:
        _merge_source(scenario_metric_ids, source="scenario_expected_output")

    aliases: dict[str, str] = {}
    for raw_alias, raw_metric_id in _METRIC_ID_ALIASES.items():
        alias = _metric_lookup_key(raw_alias)
        metric_id = _metric_lookup_key(raw_metric_id)
        if not alias or not metric_id:
            continue
        if metric_id not in entries:
            _merge_entry(
                entries,
                metric_id,
                description=None,
                owner="team-ir",
                source="alias_target",
            )
        aliases[alias] = metric_id
        existing = entries[metric_id]
        entries[metric_id] = existing.model_copy(
            update={
                "sources": tuple(sorted({*existing.sources, "alias"})),
                "aliases": tuple(sorted({*existing.aliases, alias})),
            }
        )

    return ProductionMetricTaxonomy(metrics=entries, aliases=aliases)


def _suggest_metric_ids(
    normalized_metric_id: str,
    taxonomy: ProductionMetricTaxonomy,
) -> list[str]:
    candidates = sorted({*taxonomy.metrics.keys(), *taxonomy.aliases.keys()})
    matches = get_close_matches(normalized_metric_id, candidates, n=5, cutoff=0.55)
    suggestions: list[str] = []
    for match in matches:
        canonical = taxonomy.aliases.get(match, match)
        if canonical in taxonomy.metrics and canonical not in suggestions:
            suggestions.append(canonical)
    return suggestions


def canonicalize_metric_id_with_diagnostics(
    metric_id: str,
    *,
    taxonomy: ProductionMetricTaxonomy | None = None,
    path: str | None = None,
    fail_unknown: bool = False,
) -> MetricCanonicalizationResult:
    """Canonicalize a metric id and return evidence-grade diagnostics."""
    active_taxonomy = taxonomy or build_production_metric_taxonomy()
    raw_metric_id = str(metric_id or "").strip()
    normalized_metric_id = _metric_lookup_key(raw_metric_id)
    canonical_metric_id = active_taxonomy.aliases.get(normalized_metric_id, normalized_metric_id)

    diagnostics: list[dict[str, object]] = []
    if canonical_metric_id in active_taxonomy.metrics:
        reason = "alias" if normalized_metric_id in active_taxonomy.aliases else "normalized"
        changed = raw_metric_id != canonical_metric_id
        if changed:
            diagnostics.append(
                {
                    "path": path or "metric_id",
                    "raw": raw_metric_id,
                    "normalized": canonical_metric_id,
                    "canonical_metric_id": canonical_metric_id,
                    "canonicalizer": active_taxonomy.canonicalizer,
                    "taxonomy_version": active_taxonomy.taxonomy_version,
                    "reason": reason,
                }
            )
        return MetricCanonicalizationResult(
            metric_id=canonical_metric_id,
            changed=changed,
            diagnostics=diagnostics,
        )

    if fail_unknown:
        suggestions = {
            normalized_metric_id or raw_metric_id: _suggest_metric_ids(
                normalized_metric_id,
                active_taxonomy,
            )
        }
        diagnostics.append(
            {
                "path": path or "metric_id",
                "raw": raw_metric_id,
                "normalized": normalized_metric_id,
                "canonicalizer": active_taxonomy.canonicalizer,
                "taxonomy_version": active_taxonomy.taxonomy_version,
                "reason": "unknown",
                "suggestions": suggestions[normalized_metric_id or raw_metric_id],
            }
        )
        raise MetricTaxonomyValidationError(
            [normalized_metric_id or raw_metric_id],
            suggestions=suggestions,
            taxonomy=active_taxonomy,
            diagnostics=diagnostics,
        )

    return MetricCanonicalizationResult(
        metric_id=canonical_metric_id,
        changed=raw_metric_id != canonical_metric_id,
        diagnostics=diagnostics,
    )


def canonicalize_metric_id(metric_id: str) -> str:
    """Map common production KPI aliases to registered metric ids."""
    return canonicalize_metric_id_with_diagnostics(metric_id).metric_id


def taxonomy_diagnostic_note(diagnostic: Mapping[str, object]) -> str:
    """Compact note form carried by Trinity bundles for variant evidence."""
    return (
        "metric_canonicalized:"
        f"{diagnostic.get('path')}:{diagnostic.get('raw')}->{diagnostic.get('normalized')}"
    )


DEFAULT_METRIC_REGISTRY = MetricRegistry(
    metrics={
        "avg_income": MetricSpec(metric_id="avg_income", description="Average agent income"),
        "gdp": MetricSpec(metric_id="gdp", description="Gross Domestic Product"),
        "unemployment_rate": MetricSpec(
            metric_id="unemployment_rate", description="Unemployment rate"
        ),
        "inflation_rate": MetricSpec(metric_id="inflation_rate", description="Inflation rate"),
        "avg_price": MetricSpec(metric_id="avg_price", description="Average price level"),
        "gov_balance": MetricSpec(metric_id="gov_balance", description="Government balance"),
        "government_balance": MetricSpec(
            metric_id="government_balance", description="Government balance"
        ),
        "policy_value": MetricSpec(
            metric_id="policy_value", description="Scalar policy value or objective score"
        ),
        "welfare": MetricSpec(metric_id="welfare", description="Aggregate welfare score"),
        "gdp_change": MetricSpec(metric_id="gdp_change", description="Change in GDP"),
        "msme_survival_24m": MetricSpec(
            metric_id="msme_survival_24m", description="MSME survival over 24 months"
        ),
        "msme_survival_rate": MetricSpec(
            metric_id="msme_survival_rate", description="MSME survival rate"
        ),
        "msme_loan_volume": MetricSpec(
            metric_id="msme_loan_volume",
            description="Total loan volume delivered to MSMEs",
        ),
        "sme_survival_rate": MetricSpec(
            metric_id="sme_survival_rate", description="SME survival rate"
        ),
        "small_business_survival_rate": MetricSpec(
            metric_id="small_business_survival_rate",
            description="Small business survival rate",
        ),
        "employment_retention": MetricSpec(
            metric_id="employment_retention", description="Employment retention"
        ),
        "employment_retention_rate": MetricSpec(
            metric_id="employment_retention_rate", description="Employment retention rate"
        ),
        "employment_stability": MetricSpec(
            metric_id="employment_stability", description="Employment stability"
        ),
        "reconstruction_speed": MetricSpec(
            metric_id="reconstruction_speed", description="Reconstruction speed"
        ),
        "digital_productivity_gain": MetricSpec(
            metric_id="digital_productivity_gain",
            description="Digital productivity gain",
        ),
        "farm_recovery_rate": MetricSpec(
            metric_id="farm_recovery_rate", description="Farm recovery rate"
        ),
        "fraud_incidence_rate": MetricSpec(
            metric_id="fraud_incidence_rate", description="Fraud incidence rate"
        ),
        "ate_estimate": MetricSpec(
            metric_id="ate_estimate",
            description="Estimated average treatment effect",
        ),
        "causal_pathway_count": MetricSpec(
            metric_id="causal_pathway_count",
            description="Number of causal pathways represented in the model",
        ),
        "model_transport_score": MetricSpec(
            metric_id="model_transport_score",
            description="Transportability score for model assumptions and evidence",
        ),
    },
    notes=["default metrics"],
)
