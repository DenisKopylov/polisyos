"""Hyperband scheduler for multi-fidelity autotune."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class HyperbandBracket:
    """One bracket of the Hyperband algorithm."""

    bracket_id: int
    rungs: list[HyperbandRung]
    current_rung: int = 0

    @property
    def is_complete(self) -> bool:
        return self.current_rung >= len(self.rungs)

    @property
    def active_rung(self) -> HyperbandRung | None:
        if self.is_complete:
            return None
        return self.rungs[self.current_rung]


@dataclass
class HyperbandRung:
    """A single rung (resource level) within a bracket."""

    n_configs: int
    resource: float
    survivors: list[str] = field(default_factory=list)


@dataclass
class HyperbandScheduler:
    """Hyperband successive halving scheduler.

    Parameters
    ----------
    max_budget:
        Maximum resource budget per configuration.
    reduction_factor:
        Factor by which to reduce survivors at each rung (default 3).
    min_budget:
        Minimum resource budget for initial rung.
    """

    max_budget: float = 81.0
    reduction_factor: int = 3
    min_budget: float = 1.0

    def get_brackets(self, n_candidates: int | None = None) -> list[HyperbandBracket]:
        """Generate all Hyperband brackets.

        Each bracket starts with a different tradeoff between number of
        configs and minimum resource.
        """
        eta = self.reduction_factor
        s_max = max(0, int(math.floor(math.log(self.max_budget / self.min_budget) / math.log(eta))))
        brackets: list[HyperbandBracket] = []

        for s in range(s_max, -1, -1):
            n = int(math.ceil((s_max + 1) / (s + 1)) * (eta**s))
            if n_candidates is not None:
                n = min(n, n_candidates)
            r = self.max_budget * (eta ** (-s))

            rungs: list[HyperbandRung] = []
            for i in range(s + 1):
                n_i = max(1, int(math.floor(n * (eta ** (-i)))))
                r_i = r * (eta**i)
                rungs.append(HyperbandRung(n_configs=n_i, resource=min(r_i, self.max_budget)))

            brackets.append(HyperbandBracket(bracket_id=s, rungs=rungs))

        return brackets

    def advance_bracket(
        self,
        bracket: HyperbandBracket,
        scores: dict[str, float],
    ) -> list[str]:
        """Advance a bracket by one rung using successive halving.

        Parameters
        ----------
        bracket:
            The bracket to advance.
        scores:
            Mapping of candidate_id -> score (lower is better).

        Returns
        -------
        List of surviving candidate IDs.
        """
        if bracket.is_complete:
            return []

        rung = bracket.active_rung
        if rung is None:
            return []

        # Sort by score ascending (lower = better)
        sorted_candidates = sorted(scores.keys(), key=lambda c: scores[c])

        # Next rung survivor count
        next_rung_idx = bracket.current_rung + 1
        if next_rung_idx < len(bracket.rungs):
            n_survivors = bracket.rungs[next_rung_idx].n_configs
        else:
            n_survivors = max(1, len(sorted_candidates) // self.reduction_factor)

        survivors = sorted_candidates[:n_survivors]
        rung.survivors = list(survivors)
        bracket.current_rung = next_rung_idx

        if next_rung_idx < len(bracket.rungs):
            bracket.rungs[next_rung_idx].survivors = list(survivors)

        return survivors

    def total_budget(self) -> float:
        """Compute total resource budget across all brackets."""
        total = 0.0
        for bracket in self.get_brackets():
            for rung in bracket.rungs:
                total += rung.n_configs * rung.resource
        return total
