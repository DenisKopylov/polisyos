"""Search diversity helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ExclusionListBuilder:
    """Extract mechanism exclusions from search history."""

    @staticmethod
    def build_from_history(
        history: list[Any],
        *,
        max_mechanisms: int = 20,
    ) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for iteration in history:
            candidate = iteration.candidate if hasattr(iteration, "candidate") else iteration
            interventions = ExclusionListBuilder._extract_interventions(candidate)
            for intervention in interventions:
                if not isinstance(intervention, dict):
                    continue
                mechanism = intervention.get("mechanism_type")
                if mechanism is None:
                    mechanism = intervention.get("kind")
                if not isinstance(mechanism, str):
                    continue
                token = mechanism.strip()
                if not token or token in seen:
                    continue
                seen.add(token)
                ordered.append(token)
                if len(ordered) >= max_mechanisms:
                    return ordered
        return ordered

    @staticmethod
    def _extract_interventions(candidate: dict[str, Any]) -> list[Any]:
        if not isinstance(candidate, dict):
            return []
        semantic = candidate.get("semantic")
        if isinstance(semantic, dict):
            interventions = semantic.get("interventions")
            if isinstance(interventions, list):
                return interventions
        direct = candidate.get("interventions")
        if isinstance(direct, list):
            return direct
        policy_spec = candidate.get("policy_spec")
        if isinstance(policy_spec, dict):
            nested = policy_spec.get("interventions")
            if isinstance(nested, list):
                return nested
        return []

    @staticmethod
    def format_exclusion_prompt(mechanisms: list[str]) -> str:
        if not mechanisms:
            return ""
        names = ", ".join(mechanisms)
        return (
            "## EXCLUSION CONSTRAINTS\n"
            "Do NOT use already explored mechanisms: "
            f"{names}\n"
            "## DIVERSITY REQUIREMENT\n"
            "Propose a meaningfully different policy approach."
        )


def enrich_context_with_diversity(
    context: dict[str, Any],
    history: list[Any],
) -> dict[str, Any]:
    """Attach diversity metadata and exclusion prompt to generator context."""

    mechanisms = ExclusionListBuilder.build_from_history(history)
    prompt = ExclusionListBuilder.format_exclusion_prompt(mechanisms)
    enriched = dict(context)
    enriched["excluded_mechanisms"] = mechanisms
    if prompt:
        enriched["diversity_constraints"] = prompt
    return enriched


@dataclass(slots=True)
class DiversityTracker:
    """Tracks mechanism diversity across search iterations."""

    _mechanisms_per_iteration: list[set[str]] = field(default_factory=list)

    def record_iteration(self, candidate: dict[str, Any]) -> None:
        interventions = ExclusionListBuilder._extract_interventions(candidate)
        mechanisms: set[str] = set()
        for intervention in interventions:
            if not isinstance(intervention, dict):
                continue
            mechanism = intervention.get("mechanism_type")
            if mechanism is None:
                mechanism = intervention.get("kind")
            if isinstance(mechanism, str) and mechanism.strip():
                mechanisms.add(mechanism.strip())
        self._mechanisms_per_iteration.append(mechanisms)

    @property
    def unique_mechanisms_total(self) -> int:
        merged: set[str] = set()
        for item in self._mechanisms_per_iteration:
            merged.update(item)
        return len(merged)

    @property
    def diversity_ratio(self) -> float:
        total = sum(len(item) for item in self._mechanisms_per_iteration)
        if total == 0:
            return 0.0
        return float(self.unique_mechanisms_total) / float(total)
