"""Public uncertainty protocol module API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from polisyos.ir.analytics.uncertainty import PropagationMethod, UncertaintyEnvelope


@dataclass(frozen=True)
class PropagationResult:
    """Propagation result data model."""
    metric_id: str
    envelope: UncertaintyEnvelope
    input_envelopes_used: list[str]
    method_used: PropagationMethod
    diagnostics: dict[str, Any]


class PropagationStrategy(Protocol):
    """Propagation strategy data model."""
    @property
    def method(self) -> PropagationMethod: ...

    def propagate(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
    ) -> list[PropagationResult]: ...
