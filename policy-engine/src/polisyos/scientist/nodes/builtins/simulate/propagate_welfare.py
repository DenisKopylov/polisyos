"""Public simulate propagate welfare module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState

from .welfare_draws import _sample_param_draw
from .welfare_node import execute_welfare_node
from .welfare_propagation import (
    _build_simulation_fn as _build_simulation_fn_impl,
)
from .welfare_propagation import (
    _propagate_credible_interval as _propagate_credible_interval_impl,
)
from .welfare_types import _SPEC, _PropagationOutcome


class WelfareSampleDomainError(Exception):
    """Declare that one sampled input is outside an evaluator's defined domain.

    This signal is diagnostic input from the evaluator, not independent proof of the
    domain predicate. Welfare propagation records it as a consumer assertion and
    withholds an unconditional Monte Carlo interval when any draw is unavailable.
    """

    def __init__(self, message: str, *, predicate_id: str) -> None:
        normalized_predicate_id = predicate_id.strip() if isinstance(predicate_id, str) else ""
        if (
            not normalized_predicate_id
            or len(normalized_predicate_id) > 128
            or not normalized_predicate_id[0].isascii()
            or not normalized_predicate_id[0].isalnum()
            or any(
                not (character.isascii() and (character.isalnum() or character in "._:-"))
                for character in normalized_predicate_id
            )
        ):
            raise ValueError("sample-domain failures require a bounded identifier predicate_id")
        super().__init__(message)
        self.predicate_id = normalized_predicate_id


def _build_simulation_fn(*args: Any, **kwargs: Any) -> Any:
    """Forward through the public module so existing monkeypatch seams remain stable."""
    return _build_simulation_fn_impl(
        *args, sampled_ge_domain_error_factory=WelfareSampleDomainError, **kwargs
    )


def _propagate_credible_interval(*args: Any, **kwargs: Any) -> _PropagationOutcome:
    """Forward the public sampler seam and stable sampled-domain error type."""
    return _propagate_credible_interval_impl(
        *args,
        sample_domain_error_type=WelfareSampleDomainError,
        sample_param_draw=_sample_param_draw,
        **kwargs,
    )


@dataclass(frozen=True)
class PropagateWelfareNode:
    """Propagate welfare under PE/GE uncertainty into a typed top-level bundle."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return execute_welfare_node(
            ctx,
            state,
            build_simulation_fn=_build_simulation_fn,
            propagate_credible_interval=_propagate_credible_interval,
        )


__all__ = ["PropagateWelfareNode"]
