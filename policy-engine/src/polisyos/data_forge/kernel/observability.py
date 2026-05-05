"""OpenTelemetry trace metadata helpers for Data Forge artifacts."""

from __future__ import annotations

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.artifacts import (
    SPAN_ID_PATTERN,
    TRACE_ID_PATTERN,
    ArtifactRef,
)

ZERO_TRACE_ID = "0" * 32
ZERO_SPAN_ID = "0" * 16


class TraceContext(DataForgeModel):
    """Minimal W3C/OpenTelemetry trace context carried into artifact metadata."""

    trace_id: str = Field(pattern=TRACE_ID_PATTERN)
    span_id: str = Field(pattern=SPAN_ID_PATTERN)
    trace_flags: str = Field(default="00", pattern=r"^[0-9a-f]{2}$")
    is_sampled: bool = False
    is_valid: bool = False

    @classmethod
    def empty(cls) -> TraceContext:
        """Return the deterministic no-active-span context."""
        return cls(
            trace_id=ZERO_TRACE_ID,
            span_id=ZERO_SPAN_ID,
            trace_flags="00",
            is_sampled=False,
            is_valid=False,
        )


def current_trace_context() -> TraceContext:
    """Read the current OpenTelemetry span context without configuring OTel."""
    try:
        from opentelemetry import trace

        span_context = trace.get_current_span().get_span_context()
    except Exception:
        return TraceContext.empty()

    if not getattr(span_context, "is_valid", False):
        return TraceContext.empty()

    trace_flags = _trace_flags_hex(getattr(span_context, "trace_flags", 0))
    return TraceContext(
        trace_id=f"{span_context.trace_id:032x}",
        span_id=f"{span_context.span_id:016x}",
        trace_flags=trace_flags,
        is_sampled=bool(int(trace_flags, 16) & 1),
        is_valid=True,
    )


def artifact_trace_metadata(context: TraceContext | None = None) -> dict[str, str]:
    """Return metadata fields suitable for manifest labels or logs."""
    resolved = context or current_trace_context()
    return {
        "trace_id": resolved.trace_id,
        "span_id": resolved.span_id,
        "otel.trace_flags": resolved.trace_flags,
        "otel.trace_valid": str(resolved.is_valid).lower(),
        "otel.trace_sampled": str(resolved.is_sampled).lower(),
    }


def attach_artifact_trace_metadata(
    artifact: ArtifactRef,
    *,
    context: TraceContext | None = None,
) -> ArtifactRef:
    """Return an ArtifactRef copy carrying the active trace id and OTel labels."""
    resolved = context or current_trace_context()
    labels = dict(artifact.labels)
    labels.update(
        {
            "otel.trace_flags": resolved.trace_flags,
            "otel.trace_valid": str(resolved.is_valid).lower(),
            "otel.trace_sampled": str(resolved.is_sampled).lower(),
        }
    )
    return artifact.model_copy(
        update={
            "trace_id": resolved.trace_id,
            "span_id": resolved.span_id,
            "labels": labels,
        }
    )


def _trace_flags_hex(trace_flags: object) -> str:
    try:
        return f"{int(trace_flags):02x}"
    except Exception:
        return "00"


__all__ = [
    "ZERO_SPAN_ID",
    "ZERO_TRACE_ID",
    "TraceContext",
    "artifact_trace_metadata",
    "attach_artifact_trace_metadata",
    "current_trace_context",
]
