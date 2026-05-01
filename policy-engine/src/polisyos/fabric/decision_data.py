"""Fabric decision-data trust envelope.

The models in this module are intentionally independent of Runtime HTTP and
frontend packages. Runtime adapters may import them, but Fabric can serialize a
decision-bearing value with its quality, lineage, replay, access, and temporal
context without knowing how the UI renders that value.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DecisionDataKind = Literal["quantity", "authored_text", "fact", "event", "claim"]
TypedGapState = Literal[
    "untraced",
    "unknown_quality",
    "restricted",
    "non_replayable",
    "unsupported_temporal_scope",
]
QualityStatus = Literal["passed", "warning", "failed", "unknown_quality"]
LineageStatus = Literal["verified", "pending", "disputed", "untraced"]
ReplayStatus = Literal["replayable", "non_replayable", "unknown"]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("temporal references must be timezone-aware")
    return value.astimezone(UTC)


class UnitRef(BaseModel):
    """Unit identity for a Fabric decision quantity."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    system: str = Field(default="ucum", min_length=1)
    display: str | None = None


class TemporalRef(BaseModel):
    """Temporal scope echoed by every Fabric trust envelope."""

    model_config = ConfigDict(extra="forbid")

    valid_at: datetime | None = None
    tx_at: datetime | None = None
    branch: str | None = None
    snapshot_id: str | None = None
    scenario_id: str | None = None

    @field_validator("valid_at", "tx_at")
    @classmethod
    def _normalize_utc(cls, value: datetime | None) -> datetime | None:
        return _utc(value)

    @classmethod
    def from_runtime_scope(cls, scope: Any | None) -> TemporalRef | None:
        """Project Runtime `TemporalScope` / `TemporalRef` objects into Fabric."""
        if scope is None:
            return None
        if hasattr(scope, "model_dump"):
            payload = scope.model_dump(mode="python")
        elif isinstance(scope, Mapping):
            payload = dict(scope)
        else:
            payload = {
                "valid_at": getattr(scope, "valid_at", None),
                "tx_at": getattr(scope, "tx_at", None),
                "branch": getattr(scope, "branch", None),
                "snapshot_id": getattr(scope, "snapshot_id", None),
                "scenario_id": getattr(scope, "scenario_id", None),
            }
        return cls.model_validate(payload)


class SourceContractRef(BaseModel):
    """SourceContract v2 identity carried by decision-bearing values."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class AuthoredText(BaseModel):
    """Textual decision surface with the same trust spine as quantities."""

    model_config = ConfigDict(extra="forbid")

    text: str
    format: Literal["plain", "markdown", "html", "json"] = "plain"
    semantic_type: str | None = None


class FabricQuantityValue(BaseModel):
    """Fabric-side quantity value compatible with the Runtime `QuantityValue` shape."""

    model_config = ConfigDict(extra="forbid")

    point: float | None = None
    unit: UnitRef
    semantic_type: str | None = None
    metric_id: str | None = None
    label: str | None = None

    @field_validator("point")
    @classmethod
    def _finite_point(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("FabricDecisionData quantities require finite numeric points")
        return value


class QualityRef(BaseModel):
    """Quality evidence reference embedded in a Fabric trust envelope."""

    model_config = ConfigDict(extra="forbid")

    status: QualityStatus = "unknown_quality"
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    report_ref: str | None = None
    reason_code: str | None = None
    quality_surface: str | None = None
    remediation_link: str | None = None

    @model_validator(mode="after")
    def _validate_unknown_quality(self) -> QualityRef:
        if self.status == "unknown_quality":
            if not self.reason_code:
                raise ValueError("unknown_quality requires reason_code")
            if not self.quality_surface:
                raise ValueError("unknown_quality requires quality_surface")
            if not self.remediation_link:
                raise ValueError("unknown_quality requires remediation_link")
        return self


class AccessRef(BaseModel):
    """Access policy and redaction state for a decision-bearing value."""

    model_config = ConfigDict(extra="forbid")

    classification: str = Field(default="public", min_length=1)
    pii_tier: str = Field(default="none", min_length=1)
    tenant_scope: str = Field(default="shared_public", min_length=1)
    redaction: Literal["none", "masked", "redacted", "aggregate_only", "denied"] = "none"
    policy_ref: str | None = None

    @model_validator(mode="after")
    def _validate_restricted_policy(self) -> AccessRef:
        if self.classification == "restricted" or self.redaction != "none":
            if not self.policy_ref:
                raise ValueError("restricted access requires policy_ref")
        return self


def access_ref_from_source_field_policy(
    source_contract: Any,
    *,
    field_id: str,
) -> AccessRef:
    """Resolve a Fabric access ref from a SourceContract field policy."""

    security = getattr(source_contract, "security", None)
    policies = tuple(getattr(security, "field_policies", ()) or ())
    selected = next(
        (policy for policy in policies if getattr(policy, "field_id", None) == field_id),
        None,
    )
    if selected is None:
        selected = next(
            (policy for policy in policies if getattr(policy, "field_id", None) == "*"),
            None,
        )
    if selected is None and policies:
        selected = policies[0]
    if selected is None:
        return AccessRef()
    return AccessRef(
        classification=str(selected.classification),
        pii_tier=str(selected.pii_tier),
        tenant_scope=str(selected.tenant_scope),
        redaction=selected.redaction,
        policy_ref=getattr(selected, "policy_ref", None),
    )


class ReplayRef(BaseModel):
    """Replay or retention alternative reference for the value."""

    model_config = ConfigDict(extra="forbid")

    status: ReplayStatus = "unknown"
    manifest_ref: str | None = None
    reason_code: str | None = None
    source_reason: str | None = None
    retention_alternative: str | None = None

    @model_validator(mode="after")
    def _validate_replay_contract(self) -> ReplayRef:
        if self.status == "replayable" and not self.manifest_ref:
            raise ValueError("replayable values require manifest_ref")
        if self.status == "non_replayable":
            if not self.reason_code:
                raise ValueError("non_replayable requires reason_code")
            if not self.source_reason:
                raise ValueError("non_replayable requires source_reason")
            if not self.retention_alternative:
                raise ValueError("non_replayable requires retention_alternative")
        return self


class LineageRef(BaseModel):
    """Lineage reference rich enough for compact UI and lazy full graph loading."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    status: LineageStatus = "untraced"
    hash: str | None = None
    compact_summary_ref: str | None = None
    full_graph_ref: str | None = None
    raw_evidence_refs: list[str] = Field(default_factory=list)
    export_links: dict[str, str] = Field(default_factory=dict)
    reason_code: str | None = None
    owner: str | None = None
    tracking_issue: str | None = None

    @model_validator(mode="after")
    def _validate_untraced_contract(self) -> LineageRef:
        if self.status == "untraced":
            if not self.reason_code:
                raise ValueError("untraced lineage requires reason_code")
            if not self.owner:
                raise ValueError("untraced lineage requires owner")
        return self


class TypedGap(BaseModel):
    """Typed gap state for explicit waivers and unknowns in the trust envelope."""

    model_config = ConfigDict(extra="forbid")

    status: TypedGapState
    reason_code: str | None = None
    owner: str | None = None
    quality_surface: str | None = None
    remediation_link: str | None = None
    access_policy: str | None = None
    redaction_behavior: str | None = None
    source_reason: str | None = None
    retention_alternative: str | None = None
    capability_endpoint: str | None = None

    @model_validator(mode="after")
    def _validate_gap_contract(self) -> TypedGap:
        required_by_state = {
            "untraced": ("reason_code", "owner"),
            "unknown_quality": ("quality_surface", "remediation_link"),
            "restricted": ("access_policy", "redaction_behavior"),
            "non_replayable": ("source_reason", "retention_alternative"),
            "unsupported_temporal_scope": ("capability_endpoint",),
        }
        for field_name in required_by_state[self.status]:
            if not getattr(self, field_name):
                raise ValueError(f"{self.status} gap requires {field_name}")
        return self


class FabricDecisionData(BaseModel):
    """Decision-bearing Fabric value plus its trust envelope."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: DecisionDataKind = "quantity"
    value: FabricQuantityValue | AuthoredText | dict[str, Any]
    source_contract: SourceContractRef
    quality: QualityRef
    lineage: LineageRef
    access: AccessRef
    time: TemporalRef
    replay: ReplayRef
    gaps: list[TypedGap] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_gap_echoes(self) -> FabricDecisionData:
        gap_states = {gap.status for gap in self.gaps}
        if self.lineage.status == "untraced" and "untraced" not in gap_states:
            raise ValueError("untraced lineage requires matching untraced gap")
        if self.quality.status == "unknown_quality" and "unknown_quality" not in gap_states:
            raise ValueError("unknown_quality requires matching gap")
        if self.access.classification == "restricted" and "restricted" not in gap_states:
            raise ValueError("restricted access requires matching gap")
        if self.replay.status == "non_replayable" and "non_replayable" not in gap_states:
            raise ValueError("non_replayable replay requires matching gap")
        return self


class FabricDecisionDataCoverage(BaseModel):
    """Coverage report for Fabric-backed decision data."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(default=0, ge=0)
    decision: int = Field(default=0, ge=0)
    telemetry: int = Field(default=0, ge=0)
    layout: int = Field(default=0, ge=0)
    debug: int = Field(default=0, ge=0)
    traced: int = Field(default=0, ge=0)
    untraced: int = Field(default=0, ge=0)
    naked_decision_values: int = Field(default=0, ge=0)
    transitional_waivers: int = Field(default=0, ge=0)


class FabricDecisionDataResponse(BaseModel):
    """Runtime response model for batch Fabric decision-data lookup."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any]
    run_id: str
    source_kind: str
    temporal_scope: TemporalRef | None = None
    decision_data: list[FabricDecisionData] = Field(default_factory=list)
    coverage: FabricDecisionDataCoverage = Field(default_factory=FabricDecisionDataCoverage)


def from_runtime_quantity(
    quantity: Any,
    *,
    index: int,
    source_contract: SourceContractRef,
    temporal_scope: Any | None,
    access: AccessRef | None = None,
    owner: str = "@fabric-owners",
) -> FabricDecisionData:
    """Build a Fabric trust envelope from a Runtime `QuantityValue` instance."""
    time = TemporalRef.from_runtime_scope(temporal_scope) or TemporalRef.from_runtime_scope(
        getattr(quantity, "time", None)
    )
    if time is None:
        now = datetime.now(UTC).replace(microsecond=0)
        time = TemporalRef(valid_at=now, tx_at=now)

    lineage = _lineage_from_runtime(getattr(quantity, "lineage", None), owner=owner)
    quality, quality_gaps = _quality_for_runtime_quantity(quantity, lineage=lineage)
    replay, replay_gaps = _replay_for_runtime_lineage(lineage)
    gaps = [
        *_gaps_for_lineage(lineage),
        *quality_gaps,
        *replay_gaps,
    ]
    metric_id = getattr(quantity, "metric_id", None) or f"quantity_{index}"
    unit = UnitRef.model_validate(_model_dump(getattr(quantity, "unit", None)) or {"code": "1"})
    value = FabricQuantityValue(
        point=getattr(quantity, "point", None),
        unit=unit,
        semantic_type=str(metric_id),
        metric_id=str(metric_id),
        label=getattr(quantity, "label", None),
    )
    return FabricDecisionData(
        id=f"fabric_decision_data:{metric_id}",
        kind="quantity",
        value=value,
        source_contract=source_contract,
        quality=quality,
        lineage=lineage,
        access=access or AccessRef(),
        time=time,
        replay=replay,
        gaps=gaps,
        metadata={
            "quantity_class": getattr(quantity, "quantity_class", "decision"),
            "runtime_metric_id": metric_id,
        },
    )


def from_runtime_quantities(
    quantities: Iterable[Any],
    *,
    source_contract: SourceContractRef,
    temporal_scope: Any | None = None,
    access_resolver: Callable[[Any, int], AccessRef | None] | None = None,
    owner: str = "@fabric-owners",
) -> list[FabricDecisionData]:
    """Project decision-class Runtime quantities into Fabric trust envelopes."""
    decision_quantities = [
        quantity
        for quantity in quantities
        if getattr(quantity, "quantity_class", "decision") == "decision"
    ]
    return [
        from_runtime_quantity(
            quantity,
            index=index,
            source_contract=source_contract,
            temporal_scope=temporal_scope,
            access=access_resolver(quantity, index) if access_resolver else None,
            owner=owner,
        )
        for index, quantity in enumerate(decision_quantities)
    ]


def coverage_from_decision_data(
    decision_data: Iterable[FabricDecisionData],
    *,
    telemetry: int = 0,
    layout: int = 0,
    debug: int = 0,
    transitional_waivers: int = 0,
) -> FabricDecisionDataCoverage:
    """Summarize trust-envelope coverage for a batch."""
    rows = list(decision_data)
    return FabricDecisionDataCoverage(
        total=len(rows) + telemetry + layout + debug,
        decision=len(rows),
        telemetry=telemetry,
        layout=layout,
        debug=debug,
        traced=sum(row.lineage.status != "untraced" for row in rows),
        untraced=sum(row.lineage.status == "untraced" for row in rows),
        naked_decision_values=0,
        transitional_waivers=transitional_waivers,
    )


def to_runtime_quantity_value(data: FabricDecisionData) -> Any:
    """Convert a Fabric quantity envelope to the Runtime `QuantityValue` contract."""
    if not isinstance(data.value, FabricQuantityValue):
        raise TypeError("only quantity FabricDecisionData can convert to QuantityValue")
    from polisyos.core.contracts.runtime import (
        LineageCompactSummaryItem,
        QuantityValue,
    )
    from polisyos.core.contracts.runtime import (
        LineageRef as RuntimeLineageRef,
    )
    from polisyos.core.contracts.runtime import (
        TemporalRef as RuntimeTemporalRef,
    )
    from polisyos.core.contracts.runtime import (
        UnitRef as RuntimeUnitRef,
    )

    compact_summary = [
        LineageCompactSummaryItem(kind="result", label=data.value.label or data.id, id=data.id)
    ]
    runtime_lineage = RuntimeLineageRef(
        id=data.lineage.id,
        hash=data.lineage.hash,
        status=data.lineage.status,
        freshness="unknown" if data.lineage.status == "untraced" else "current",
        summary={"source": data.source_contract.id},
        compact_summary=compact_summary,
        reason_code=data.lineage.reason_code,
        tracking_issue=(
            data.lineage.tracking_issue
            if data.lineage.status != "untraced"
            else data.lineage.tracking_issue or "policyos://fabric-decision-data/untraced"
        ),
    )
    return QuantityValue(
        point=data.value.point,
        unit=RuntimeUnitRef.model_validate(data.value.unit.model_dump(mode="python")),
        metric_id=data.value.metric_id,
        label=data.value.label,
        lineage=runtime_lineage,
        time=RuntimeTemporalRef.model_validate(data.time.model_dump(mode="python")),
        quantity_class="decision",
    )


def fabric_fact_to_quantity_value(
    fact: Mapping[str, Any] | Any,
    *,
    unit: UnitRef | Mapping[str, Any] | None = None,
    semantic_type: str | None = None,
) -> FabricQuantityValue:
    """Map a Fabric fact payload into a serializable quantity value."""
    payload = _model_dump(fact)
    point = _first_present(payload, "value", "numeric_value", "amount", "point")
    metric_id = _first_present(payload, "metric_id", "field_id", "fact_id", "id")
    label = _first_present(payload, "label", "name", "title")
    resolved_unit = UnitRef.model_validate(unit or payload.get("unit") or {"code": "1"})
    return FabricQuantityValue(
        point=float(point) if point is not None else None,
        unit=resolved_unit,
        semantic_type=semantic_type or _as_optional_str(payload.get("semantic_type")),
        metric_id=_as_optional_str(metric_id),
        label=_as_optional_str(label),
    )


def fabric_claim_to_authored_text(claim: Mapping[str, Any] | Any) -> AuthoredText:
    """Map a Fabric claim payload into authored text with semantic identity."""
    payload = _model_dump(claim)
    text = _first_present(payload, "text", "claim_text", "body", "description")
    if text is None:
        raise ValueError("Fabric claim mapping requires text, claim_text, body, or description")
    semantic_type = _first_present(payload, "semantic_type", "claim_type", "type")
    return AuthoredText(text=str(text), semantic_type=_as_optional_str(semantic_type))


def fabric_event_to_authored_text(event: Mapping[str, Any] | Any) -> AuthoredText:
    """Map a Fabric event payload into authored text for provenance UI surfaces."""
    payload = _model_dump(event)
    text = _first_present(payload, "description", "label", "event_type", "type")
    if text is None:
        raise ValueError("Fabric event mapping requires description, label, event_type, or type")
    semantic_type = _first_present(payload, "semantic_type", "event_type", "type")
    return AuthoredText(text=str(text), semantic_type=_as_optional_str(semantic_type))


def _lineage_from_runtime(runtime_lineage: Any | None, *, owner: str) -> LineageRef:
    if runtime_lineage is None:
        return LineageRef(
            id="untraced",
            status="untraced",
            reason_code="runtime_quantity_lineage_missing",
            owner=owner,
            tracking_issue="policyos://fabric-decision-data/runtime-lineage-missing",
        )
    payload = _model_dump(runtime_lineage)
    lineage_id = str(payload.get("id") or "untraced")
    status = str(payload.get("status") or "untraced")
    summary = payload.get("summary", {})
    raw_evidence_refs = []
    if isinstance(summary, Mapping) and summary.get("artifact"):
        raw_evidence_refs.append(f"cas://{summary['artifact']}")
    if status == "untraced":
        return LineageRef(
            id=lineage_id,
            status="untraced",
            hash=payload.get("hash"),
            compact_summary_ref=f"/api/v1/lineage/{lineage_id}",
            full_graph_ref=f"/api/v1/lineage/{lineage_id}?view=full",
            raw_evidence_refs=raw_evidence_refs,
            export_links=_export_links(lineage_id),
            reason_code=str(payload.get("reason_code") or "lineage_untraced"),
            owner=owner,
            tracking_issue=payload.get("tracking_issue"),
        )
    return LineageRef(
        id=lineage_id,
        status=status if status in {"verified", "pending", "disputed"} else "pending",
        hash=payload.get("hash"),
        compact_summary_ref=f"/api/v1/lineage/{lineage_id}",
        full_graph_ref=f"/api/v1/lineage/{lineage_id}?view=full",
        raw_evidence_refs=raw_evidence_refs,
        export_links=_export_links(lineage_id),
    )


def _quality_for_runtime_quantity(
    quantity: Any,
    *,
    lineage: LineageRef,
) -> tuple[QualityRef, list[TypedGap]]:
    metric_id = str(getattr(quantity, "metric_id", None) or "quantity")
    if lineage.status == "untraced":
        remediation = f"policyos://fabric-decision-data/quality/{metric_id}"
        return (
            QualityRef(
                status="unknown_quality",
                reason_code="lineage_untraced_quality_not_proven",
                quality_surface=metric_id,
                remediation_link=remediation,
            ),
            [
                TypedGap(
                    status="unknown_quality",
                    quality_surface=metric_id,
                    remediation_link=remediation,
                )
            ],
        )
    return (
        QualityRef(
            status="passed",
            score=1.0,
            report_ref=f"runtime://quantity-quality/{metric_id}",
        ),
        [],
    )


def _replay_for_runtime_lineage(lineage: LineageRef) -> tuple[ReplayRef, list[TypedGap]]:
    if lineage.raw_evidence_refs:
        return ReplayRef(status="replayable", manifest_ref=lineage.raw_evidence_refs[0]), []
    reason = "no_raw_evidence_ref_available"
    return (
        ReplayRef(
            status="non_replayable",
            reason_code=reason,
            source_reason="runtime lineage did not expose a raw evidence reference",
            retention_alternative="lineage graph and audit metadata retained",
        ),
        [
            TypedGap(
                status="non_replayable",
                source_reason="runtime lineage did not expose a raw evidence reference",
                retention_alternative="lineage graph and audit metadata retained",
            )
        ],
    )


def _gaps_for_lineage(lineage: LineageRef) -> list[TypedGap]:
    if lineage.status != "untraced":
        return []
    return [
        TypedGap(
            status="untraced",
            reason_code=lineage.reason_code,
            owner=lineage.owner,
        )
    ]


def _model_dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _first_present(payload: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _as_optional_str(value: Any | None) -> str | None:
    return None if value is None else str(value)


def _export_links(lineage_id: str) -> dict[str, str]:
    return {
        "openlineage": f"/api/v1/lineage/{lineage_id}/export/openlineage",
        "prov": f"/api/v1/lineage/{lineage_id}/export/prov",
    }


__all__ = [
    "AccessRef",
    "AuthoredText",
    "DecisionDataKind",
    "FabricDecisionData",
    "FabricDecisionDataCoverage",
    "FabricDecisionDataResponse",
    "FabricQuantityValue",
    "LineageRef",
    "LineageStatus",
    "QualityRef",
    "QualityStatus",
    "ReplayRef",
    "ReplayStatus",
    "SourceContractRef",
    "TemporalRef",
    "TypedGap",
    "TypedGapState",
    "UnitRef",
    "access_ref_from_source_field_policy",
    "coverage_from_decision_data",
    "fabric_claim_to_authored_text",
    "fabric_event_to_authored_text",
    "fabric_fact_to_quantity_value",
    "from_runtime_quantities",
    "from_runtime_quantity",
    "to_runtime_quantity_value",
]
