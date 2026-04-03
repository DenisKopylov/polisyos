"""Public kernel metrics module API."""
from __future__ import annotations

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel


class MetricSpec(KernelModel):
    """Metric spec data model."""
    metric_id: str = Field(..., pattern=ID_PATTERN)
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=200)


class MetricRegistry(KernelModel):
    """Metric registry implementation."""
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    metrics: dict[str, MetricSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_metrics(self) -> "MetricRegistry":
        for key, spec in self.metrics.items():
            if not key or not isinstance(key, str):
                raise ValueError("metric id must be a non-empty string")
            if key != spec.metric_id:
                raise ValueError(f"metric id mismatch: '{key}' != '{spec.metric_id}'")
        return self


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
    },
    notes=["default metrics"],
)
