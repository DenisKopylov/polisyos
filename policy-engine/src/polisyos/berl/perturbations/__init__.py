"""BERL perturbation types and package-level function exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class FeatureConstraint:
    """Closed numeric support interval for a feature."""

    lower: float | None = None
    upper: float | None = None

    def contains(self, value: float) -> bool:
        """Return whether value is inside the declared feature support."""

        if self.lower is not None and value < self.lower:
            return False
        return not (self.upper is not None and value > self.upper)


@dataclass(frozen=True, slots=True)
class PerturbedPoint:
    """One local perturbation plus its explanation representation."""

    features: Mapping[str, float]
    deltas: Mapping[str, float]
    weight: float = 1.0
    ood: bool = False
    constraint_violation: bool = False


from polisyos.berl.perturbations.heldout import (  # noqa: E402
    build_heldout_records as build_heldout_records,
)
from polisyos.berl.perturbations.heldout import (  # noqa: E402
    perturbation_support_rates as perturbation_support_rates,
)
from polisyos.berl.perturbations.sampling import (  # noqa: E402
    sample_local_perturbations as sample_local_perturbations,
)
