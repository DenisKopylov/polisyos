"""Run ordered governance passes with telemetry, short-circuiting, and degraded paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.pipeline import LinearPipeline
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

from .telemetry import PassSpan, ValidationTrace

if TYPE_CHECKING:
    from polisyos.core.governance.profiles import ValidationProfile
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

logger = get_logger(__name__)

_VALIDATOR_PASS_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


def _load_runtime_trace_types() -> tuple[Any, Any]:
    try:
        from opentelemetry.trace import Status, StatusCode
    except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency

        class _FallbackStatusCode(str, Enum):
            OK = "OK"
            ERROR = "ERROR"

        class _FallbackStatus:
            def __init__(
                self,
                status_code: _FallbackStatusCode,
                description: str | None = None,
            ) -> None:
                self.status_code = status_code
                self.description = description

        return _FallbackStatus, _FallbackStatusCode
    return Status, StatusCode


Status, StatusCode = _load_runtime_trace_types()


def _default_tracer() -> PolicyOSTracer | Any:
    return get_tracer()


def _default_metrics() -> MetricsRegistry | Any:
    return get_metrics()


@dataclass
class _ValidationRunState:
    all_issues: list[ComplianceIssue]
    trace: ValidationTrace
    short_circuit: bool = False


class ValidationPipeline:
    """
    Orchestrates validation passes using Chain of Responsibility pattern.

    Features:
    - Pass ordering by estimated cost (cheapest first)
    - Short-circuit on blocker (configurable per profile)
    - Comprehensive telemetry capture
    - Graceful error handling per pass
    """

    def __init__(
        self,
        passes: list[ValidatorPass],
        *,
        tracer: PolicyOSTracer | Any | None = None,
        metrics: MetricsRegistry | Any | None = None,
    ) -> None:
        self._pipeline = LinearPipeline(passes, stage_id=lambda p: p.pass_id)
        self._tracer = tracer if tracer is not None else _default_tracer()
        self._metrics = metrics if metrics is not None else _default_metrics()

    def validate(
        self,
        ctx: PassContext,
        profile: ValidationProfile,
    ) -> tuple[list[ComplianceIssue], ValidationTrace]:
        tracer = self._tracer
        metrics = self._metrics

        trace = ValidationTrace(run_id=ctx.run_id, profile=profile.level.value)
        state = _ValidationRunState(all_issues=[], trace=trace)
        ordered_pass_ids = [
            validator.pass_id
            for validator in self._pipeline.select(
                profile.pass_ids,
                sort_key=lambda p: p.estimated_cost_ms,
                strict=False,
            )
        ]

        with tracer.start_as_current_span(
            "governance.validation_pipeline",
            attributes={
                "polisyos.run_id": ctx.run_id,
                "polisyos.phase": "VALIDATE",
                "polisyos.validation.profile": profile.level.value,
                "polisyos.validation.pass_count": len(ordered_pass_ids),
            },
        ) as pipeline_span:
            run = self._pipeline.run(
                initial_state=state,
                stage_ids=ordered_pass_ids,
                run_stage=lambda validator, run_state: self._run_validator_pass(
                    validator=validator,
                    run_state=run_state,
                    ctx=ctx,
                    tracer=tracer,
                    metrics=metrics,
                ),
                stop_after=lambda _validator, run_state: (
                    profile.short_circuit_on_blocker and run_state.short_circuit
                ),
            )
            state = run.state

            if run.short_circuited:
                pipeline_span.set_attribute("polisyos.validation.short_circuited", True)
                pipeline_span.set_status(Status(StatusCode.ERROR, "short_circuit_on_blocker"))
                state.trace.complete(short_circuited=True)
                return state.all_issues, state.trace

            pipeline_span.set_attribute("polisyos.validation.total_issues", len(state.all_issues))
            pipeline_span.set_attribute("polisyos.validation.short_circuited", False)
            total_blockers = sum(
                1 for issue in state.all_issues if issue.severity == IssueSeverity.BLOCKER
            )
            if total_blockers > 0:
                pipeline_span.set_status(Status(StatusCode.ERROR, f"{total_blockers} blockers"))
            else:
                pipeline_span.set_status(Status(StatusCode.OK))

            state.trace.complete(short_circuited=False)
            return state.all_issues, state.trace

    def _run_validator_pass(
        self,
        *,
        validator: ValidatorPass,
        run_state: _ValidationRunState,
        ctx: PassContext,
        tracer: PolicyOSTracer | Any,
        metrics: MetricsRegistry | Any,
    ) -> _ValidationRunState:
        with tracer.start_as_current_span(
            f"governance.pass.{validator.pass_id}",
            attributes={
                "polisyos.pass_id": validator.pass_id,
                "polisyos.pass.estimated_cost_ms": validator.estimated_cost_ms,
            },
        ) as pass_span:
            span = PassSpan(pass_id=validator.pass_id, start_time=datetime.now(UTC))

            if ctx.ir:
                try:
                    span.set_inputs_hash(ctx.ir.model_dump(mode="json"))
                except (AttributeError, TypeError, ValueError) as exc:
                    envelope = emit_degraded_path(
                        component="governance.pipeline",
                        operation="set_inputs_hash",
                        reason="input_hash_failed",
                        exc=exc,
                        details={"pass_id": validator.pass_id, "run_id": ctx.run_id},
                        log=logger,
                        metrics=metrics,
                    )
                    span.error = json.dumps(envelope, sort_keys=True, default=str)

            with metrics.time_governance_pass({"pass_id": validator.pass_id}):
                try:
                    issues = validator.validate(ctx)
                    span.issue_count = len(issues)
                    span.blocker_count = sum(
                        1 for issue in issues if issue.severity == IssueSeverity.BLOCKER
                    )
                    span.warning_count = sum(
                        1 for issue in issues if issue.severity == IssueSeverity.WARNING
                    )
                    for issue in issues:
                        metrics.record_validation_issue(
                            severity=issue.severity.value,
                            pass_id=validator.pass_id,
                            error_type=issue.code,
                        )
                    run_state.all_issues.extend(issues)

                    pass_span.set_attribute("polisyos.validation.issue_count", len(issues))
                    pass_span.set_attribute(
                        "polisyos.validation.blocker_count",
                        span.blocker_count,
                    )
                    if span.blocker_count > 0:
                        pass_span.set_status(Status(StatusCode.ERROR, "blockers_found"))
                    else:
                        pass_span.set_status(Status(StatusCode.OK))

                except _VALIDATOR_PASS_ERRORS as exc:
                    span.error = str(exc)
                    pass_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    pass_span.record_exception(exc)
                    envelope = emit_degraded_path(
                        component="governance.pipeline",
                        operation="validator_pass",
                        reason="validator_pass_failed",
                        exc=exc,
                        details={"pass_id": validator.pass_id, "run_id": ctx.run_id},
                        log=logger,
                        metrics=metrics,
                    )
                    span.error = json.dumps(envelope, sort_keys=True, default=str)
                    pass_span.set_attribute(
                        "polisyos.validation.error_envelope.reason",
                        str(envelope.get("reason", "")),
                    )
                    metrics.record_validation_issue(
                        severity="blocker",
                        pass_id=validator.pass_id,
                        error_type="PASS_EXECUTION_ERROR",
                    )
                    run_state.all_issues.append(
                        ComplianceIssue(
                            pass_id=validator.pass_id,
                            path=["_internal", "pass_error"],
                            message=f"Pass '{validator.pass_id}' failed: {exc}",
                            severity=IssueSeverity.BLOCKER,
                            code="PASS_EXECUTION_ERROR",
                            suggestion=(
                                "Inspect validation_trace span.error and degraded_path "
                                "metrics for the structured root-cause envelope."
                            ),
                            input_value=json.dumps(envelope, sort_keys=True, default=str),
                        )
                    )
                    span.blocker_count = 1
                finally:
                    span.close()
                    run_state.trace.add_span(span)

            if span.blocker_count > 0:
                run_state.short_circuit = True

        return run_state

    def get_pass(self, pass_id: str) -> ValidatorPass | None:
        """Retrieve a specific pass by ID."""
        return self._pipeline.get_stage(pass_id)

    @property
    def available_passes(self) -> list[str]:
        """List of available pass IDs."""
        return cast("list[str]", list(self._pipeline.stage_ids()))
