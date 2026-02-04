from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.fabric.io.db import SimulationDB

from polisyos.scholar.orchestrator.enrich import enrich_topic as _enrich_topic
from polisyos.scholar.policies import ScholarPolicy
from polisyos.scholar.types import EnrichResultV1


def enrich_topic(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    intent: ResearchIntent,
    db: SimulationDB | None = None,
    policy: ScholarPolicy | None = None,
) -> EnrichResultV1:
    return _enrich_topic(
        cas=cas,
        fact_log_root=fact_log_root,
        intent=intent,
        db=db,
        policy=policy,
    )


@dataclass(frozen=True)
class ScholarService:
    fact_log_root: Path
    db: SimulationDB | None = None
    policy: ScholarPolicy | None = None

    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:
        result = enrich_topic(
            cas=store,
            fact_log_root=self.fact_log_root,
            intent=intent,
            db=self.db,
            policy=self.policy,
        )
        return result.knowledge_bundle_ref


__all__ = ["ScholarService", "enrich_topic"]
