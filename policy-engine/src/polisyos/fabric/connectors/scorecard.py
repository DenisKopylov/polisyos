"""Source scorecards for the contracted Fabric source platform."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.fabric.connectors.contracts import SourceContract
from polisyos.fabric.finite import ensure_probability

ScorecardDimension = Literal[
    "freshness",
    "reliability",
    "schema_drift",
    "quality",
    "contract_violations",
    "quarantine_rate",
    "replay_success",
    "latency",
    "source_trust",
]


class SourceScorecardMetric(BaseModel):
    """One source scorecard metric."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: ScorecardDimension
    score: float = Field(ge=0.0, le=1.0)
    observed_value: float | None = None
    target_value: float | None = None
    status: Literal["healthy", "watch", "breached", "unknown"] = "unknown"
    reason: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _validate_score(cls, value: object) -> float:
        return ensure_probability(value, what="score")


class SourceScorecard(BaseModel):
    """Generated source health and governance scorecard."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "fabric.source_scorecard.v1"
    source_contract_id: str
    connector_id: str
    profile_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    window: str = "rolling_30d"
    metrics: tuple[SourceScorecardMetric, ...]
    overall_score: float = Field(ge=0.0, le=1.0)
    grade: Literal["A", "B", "C", "D", "F"]
    status: Literal["healthy", "watch", "breached", "unknown"]
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("generated_at", mode="after")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def build_source_scorecard(
    contract: SourceContract,
    observations: Mapping[str, float] | None = None,
    *,
    generated_at: datetime | None = None,
    window: str = "rolling_30d",
) -> SourceScorecard:
    """Score freshness, reliability, drift, quality, replay, latency, and trust."""

    observed = {str(key): float(value) for key, value in dict(observations or {}).items()}
    metrics = (
        _at_most_metric(
            "freshness",
            observed.get("freshness_age_seconds"),
            float(contract.sla.freshness_slo_seconds),
            unknown_score=0.75,
        ),
        _at_least_metric(
            "reliability",
            observed.get("fetch_success"),
            contract.sla.availability_target,
            unknown_score=0.75,
        ),
        _at_most_metric(
            "schema_drift",
            observed.get("schema_drift_rate"),
            0.0,
            unknown_score=1.0 if contract.schema.has_schema_evidence else 0.4,
        ),
        _at_least_metric("quality", observed.get("quality_score"), 0.8, unknown_score=0.75),
        _at_most_metric(
            "contract_violations",
            observed.get("contract_violation_rate"),
            0.0,
            unknown_score=0.85,
        ),
        _at_most_metric(
            "quarantine_rate",
            observed.get("quarantine_rate"),
            0.01,
            unknown_score=0.8,
        ),
        _at_least_metric(
            "replay_success",
            observed.get("replay_success"),
            contract.sla.replay_success_target,
            unknown_score=1.0 if contract.replay.has_replay_evidence else 0.5,
        ),
        _at_most_metric(
            "latency",
            observed.get("p95_latency_ms"),
            contract.sla.p95_latency_ms,
            unknown_score=0.75,
        ),
        SourceScorecardMetric(
            name="source_trust",
            score=_source_trust_score(contract),
            status="healthy" if contract.source_trust.tier != "unknown" else "unknown",
            reason=f"source_trust={contract.source_trust.tier}",
        ),
    )
    overall = sum(metric.score for metric in metrics) / len(metrics)
    return SourceScorecard(
        source_contract_id=contract.id,
        connector_id=contract.source.connector_id,
        profile_id=contract.source.profile_id,
        generated_at=generated_at or datetime.now(UTC),
        window=window,
        metrics=metrics,
        overall_score=overall,
        grade=_grade(overall),
        status=_status(metrics),
        evidence={
            "source_contract_hash": contract.content_hash,
            "replay_fixture": contract.replay.fixture_ref,
            "non_replayable_reason": contract.replay.non_replayable_reason,
        },
    )


def build_source_scorecards(
    contracts: Sequence[SourceContract],
    observations_by_contract: Mapping[str, Mapping[str, float]] | None = None,
    *,
    generated_at: datetime | None = None,
) -> tuple[SourceScorecard, ...]:
    """Build deterministic scorecards for a set of source contracts."""

    observations = observations_by_contract or {}
    return tuple(
        build_source_scorecard(
            contract,
            observations.get(contract.id, {}),
            generated_at=generated_at,
        )
        for contract in sorted(contracts, key=lambda item: item.id)
    )


def source_scorecards_snapshot_payload(
    scorecards: Sequence[SourceScorecard],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Serialize source scorecards for docs or CI artifacts."""

    return {
        "schema_version": "fabric.source_scorecard.v1",
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "scorecards": {
            scorecard.source_contract_id: scorecard.model_dump(mode="json")
            for scorecard in sorted(scorecards, key=lambda item: item.source_contract_id)
        },
    }


def render_scorecards_markdown(scorecards: Sequence[SourceScorecard]) -> str:
    """Render a compact scorecard table."""

    lines = [
        "| Source contract | Window | Freshness | Reliability | Schema drift | Quality | Replay | Overall | Status |",
        "| --------------- | ------ | --------- | ----------- | ------------ | ------- | ------ | ------- | ------ |",
    ]
    for scorecard in sorted(scorecards, key=lambda item: item.source_contract_id):
        metrics = {metric.name: metric for metric in scorecard.metrics}
        lines.append(
            "| "
            f"`{scorecard.source_contract_id}` | "
            f"`{scorecard.window}` | "
            f"{_metric_cell(metrics, 'freshness')} | "
            f"{_metric_cell(metrics, 'reliability')} | "
            f"{_metric_cell(metrics, 'schema_drift')} | "
            f"{_metric_cell(metrics, 'quality')} | "
            f"{_metric_cell(metrics, 'replay_success')} | "
            f"{scorecard.grade} / {scorecard.overall_score:.3f} | "
            f"{scorecard.status} |"
        )
    return "\n".join(lines)


def _at_least_metric(
    name: ScorecardDimension,
    observed: float | None,
    target: float,
    *,
    unknown_score: float,
) -> SourceScorecardMetric:
    if observed is None:
        return SourceScorecardMetric(
            name=name,
            score=unknown_score,
            target_value=target,
            status="unknown",
            reason="no observation yet",
        )
    score = min(max(observed / max(target, 1e-12), 0.0), 1.0)
    return SourceScorecardMetric(
        name=name,
        score=score,
        observed_value=observed,
        target_value=target,
        status="healthy" if observed >= target else "breached",
    )


def _at_most_metric(
    name: ScorecardDimension,
    observed: float | None,
    target: float,
    *,
    unknown_score: float,
) -> SourceScorecardMetric:
    if observed is None:
        return SourceScorecardMetric(
            name=name,
            score=unknown_score,
            target_value=target,
            status="unknown",
            reason="no observation yet",
        )
    if target <= 0.0:
        score = 1.0 if observed <= target else 0.0
    else:
        score = min(max(target / max(observed, 1e-12), 0.0), 1.0)
    return SourceScorecardMetric(
        name=name,
        score=score,
        observed_value=observed,
        target_value=target,
        status="healthy" if observed <= target else "breached",
    )


def _source_trust_score(contract: SourceContract) -> float:
    return {
        "institutional": 0.95,
        "government": 0.9,
        "vendor": 0.75,
        "internal": 0.8,
        "community": 0.65,
        "synthetic": 0.6,
        "unknown": 0.4,
    }.get(contract.source_trust.tier, 0.4)


def _grade(score: float) -> Literal["A", "B", "C", "D", "F"]:
    if score >= 0.9:
        return "A"
    if score >= 0.8:
        return "B"
    if score >= 0.7:
        return "C"
    if score >= 0.6:
        return "D"
    return "F"


def _status(metrics: Sequence[SourceScorecardMetric]) -> Literal[
    "healthy",
    "watch",
    "breached",
    "unknown",
]:
    if any(metric.status == "breached" for metric in metrics):
        return "breached"
    if any(metric.status == "unknown" for metric in metrics):
        return "watch"
    return "healthy"


def _metric_cell(
    metrics: Mapping[str, SourceScorecardMetric],
    name: ScorecardDimension,
) -> str:
    metric = metrics.get(name)
    if metric is None:
        return "-"
    return f"{metric.score:.3f} `{metric.status}`"


__all__ = [
    "SourceScorecard",
    "SourceScorecardMetric",
    "build_source_scorecard",
    "build_source_scorecards",
    "render_scorecards_markdown",
    "source_scorecards_snapshot_payload",
]
