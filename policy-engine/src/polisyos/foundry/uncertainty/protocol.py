"""Define the result and strategy contracts for Foundry uncertainty propagation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from polisyos.ir.analytics.uncertainty import PropagationMethod, UncertaintyEnvelope


@dataclass(frozen=True)
class PropagationResult:
    """Capture one propagated envelope plus the diagnostics needed for replay and audit."""
    metric_id: str
    envelope: UncertaintyEnvelope
    input_envelopes_used: list[str]
    method_used: PropagationMethod
    diagnostics: dict[str, Any]


class PropagationStrategy(Protocol):
    """Protocol implemented by uncertainty backends that propagate input envelopes forward."""
    @property
    def method(self) -> PropagationMethod: ...

    def propagate(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
    ) -> list[PropagationResult]: ...
