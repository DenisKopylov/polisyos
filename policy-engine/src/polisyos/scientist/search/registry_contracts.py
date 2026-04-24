"""Protocol-first registry contracts for Scientist runtime."""

from __future__ import annotations

from typing import Any, Protocol

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.autotune.models import (
    ChampionPointer,
    PromotionDecision,
    PromotionPolicy,
)


class ChampionRegistryContract(Protocol):
    """Protocol for the authoritative champion registry that stores promoted candidates per loop."""

    def get(self, loop_id: str) -> ChampionPointer | None: ...

    def consider_promotion(
        self,
        loop_id: str,
        candidate_ref: ArtifactRef,
        evaluation_ref: ArtifactRef,
        policy: PromotionPolicy,
        *,
        pareto_promoter: Any | None = None,
    ) -> PromotionDecision: ...

    def write_pointer(self, loop_id: str, pointer: ChampionPointer) -> None: ...


class ParetoRegistryContract(Protocol):
    """Protocol for the Pareto snapshot store that seeds later search iterations."""

    def get_snapshot(self, loop_id: str) -> Any: ...

    def update(self, loop_id: str, **kwargs: Any) -> Any: ...

    def get_seed_bundle(self, target_context: Any, *, max_seeds: int = 5) -> Any: ...


class LessonRegistryContract(Protocol):
    """Protocol for recording and retrieving reusable lessons from prior search runs."""

    def record_local(self, card: Any, *, context: Any) -> Any: ...

    def query(self, query: Any) -> list[Any]: ...

    def query_with_transfer(self, query: Any, *, target_context: Any) -> list[Any]: ...


class BenchmarkRegistryContract(Protocol):
    """Protocol for resolving benchmark assets by split, run, and suite identifier."""

    def record(
        self,
        split_type: str,
        ref: ArtifactRef,
        *,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
        suite_id: str | None = None,
    ) -> None: ...

    def get(
        self,
        split_type: str,
        *,
        run_id: str | None = None,
        suite_id: str | None = None,
    ) -> list[ArtifactRef]: ...

    def latest(
        self,
        split_type: str,
        *,
        run_id: str | None = None,
        suite_id: str | None = None,
    ) -> ArtifactRef | None: ...

    def resolve_family_bundle(
        self,
        *,
        family: str,
        claim_mode: str,
        run_id: str | None = None,
        loop_id: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
    ) -> Any: ...

    def require_promotion_evidence(
        self,
        *,
        family: str,
        claim_mode: str,
        run_id: str | None = None,
        loop_id: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
    ) -> list[str]: ...


class DiscoveryHypothesisRegistryContract(Protocol):
    """Protocol for publishing discovery hypotheses back into the runtime search surface."""

    def publish(
        self, run_id: str, artifact_ref: ArtifactRef, *, metadata: dict[str, Any] | None = None
    ) -> None: ...

    def latest(self, run_id: str) -> ArtifactRef | None: ...


__all__ = [
    "BenchmarkRegistryContract",
    "ChampionRegistryContract",
    "DiscoveryHypothesisRegistryContract",
    "LessonRegistryContract",
    "ParetoRegistryContract",
]
