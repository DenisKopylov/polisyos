"""Expose Scholar enrichment as a library function and a lightweight service wrapper."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.fabric.storage import StoragePort
from polisyos.scholar.orchestrator.enrich import enrich_topic as _enrich_topic
from polisyos.scholar.policies import ScholarPolicy
from polisyos.scholar.types import EnrichResultV1


def enrich_topic(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    intent: ResearchIntent,
    storage: StoragePort | None = None,
    db: Any | None = None,
    policy: ScholarPolicy | None = None,
) -> EnrichResultV1:
    """Run Scholar enrichment for one research intent and persist bundle artifacts.

    Args:
        cas: CAS store used for bundle/report artifact persistence.
        fact_log_root: Root directory for factual evidence logs.
        intent: Research intent that defines topic/domain/source requirements.
        storage: Optional document storage adapter for raw source payloads.
        db: Optional retrieval/index backend passed into the orchestrator.
        policy: Optional enrichment budgets/thresholds/freshness policy.

    Returns:
        `EnrichResultV1` with the knowledge-bundle reference and optional report ref.

    Raises:
        ScholarError: Domain-specific discover/acquire/docs/claims/reconcile failures
            raised by the orchestrator.
    """
    return _enrich_topic(
        cas=cas,
        fact_log_root=fact_log_root,
        intent=intent,
        storage=storage,
        db=db,
        policy=policy,
    )


@dataclass(frozen=True)
class ScholarService:
    """Provide an object-oriented boundary around `enrich_topic()` for runtime callers."""
    fact_log_root: Path
    storage: StoragePort | None = None
    db: Any | None = None
    policy: ScholarPolicy | None = None

    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:
        """Run enrichment and return only the resulting bundle reference."""
        result = enrich_topic(
            cas=store,
            fact_log_root=self.fact_log_root,
            intent=intent,
            storage=self.storage,
            db=self.db,
            policy=self.policy,
        )
        return result.knowledge_bundle_ref


__all__ = ["ScholarService", "enrich_topic"]
