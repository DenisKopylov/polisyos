"""Expose Scholar enrichment as a library function and a lightweight service wrapper."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent, SourceSpec
from polisyos.scholar.orchestrator.enrich import enrich_topic as _enrich_topic
from polisyos.scholar.search.jobs import DeepResearchJobManager
from polisyos.scholar.search.service import ScholarDeepSearchService

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.storage import StoragePort
    from polisyos.scholar.policies import ScholarPolicy
    from polisyos.scholar.search.models import (
        SearchBudgetControls,
        SearchConstraints,
        WebEvidenceBundle,
    )
    from polisyos.scholar.types import EnrichResultV1


def enrich_topic(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    intent: ResearchIntent,
    storage: StoragePort | None = None,
    db: Any | None = None,
    policy: ScholarPolicy | None = None,
    web_search_service: ScholarDeepSearchService | None = None,
    web_search_constraints: SearchConstraints | None = None,
    web_search_budgets: SearchBudgetControls | None = None,
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
    hydrated_intent = intent
    web_bundle: WebEvidenceBundle | None = None
    web_bundle_artifact_id: str | None = None
    if not intent.seed_sources:
        search_service = web_search_service or ScholarDeepSearchService(cas=cas)
        web_bundle = _run_async_factory_sync(
            lambda: search_service.deep_search(
                intent=intent,
                claim_texts=[intent.topic or intent.domain or "policy research"],
                constraints=web_search_constraints,
                budgets=web_search_budgets,
            )
        )
        if not web_bundle.sources:
            raise ValueError("web search bootstrap returned no sources")
        try:
            web_bundle_artifact_id = str(
                search_service.persist_bundle(web_bundle).artifact_id
            )
        except ValueError:
            web_bundle_artifact_id = None
        hydrated_intent = intent.model_copy(
            update={
                "seed_sources": _seed_sources_from_web_bundle(
                    web_bundle,
                    max_docs=(
                        intent.budgets_v1.max_docs
                        if intent.budgets_v1 is not None and intent.budgets_v1.max_docs is not None
                        else None
                    ),
                )
            }
        )

    return _enrich_topic(
        cas=cas,
        fact_log_root=fact_log_root,
        intent=hydrated_intent,
        storage=storage,
        db=db,
        policy=policy,
        web_evidence_bundle=web_bundle,
        web_evidence_artifact_id=web_bundle_artifact_id,
    )


@dataclass(frozen=True)
class ScholarService:
    """Provide an object-oriented boundary around `enrich_topic()` for runtime callers."""
    fact_log_root: Path
    storage: StoragePort | None = None
    db: Any | None = None
    policy: ScholarPolicy | None = None
    web_search_service: ScholarDeepSearchService | None = None
    web_search_constraints: SearchConstraints | None = None
    web_search_budgets: SearchBudgetControls | None = None
    _job_managers: dict[str, DeepResearchJobManager] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:
        """Run enrichment and return only the resulting bundle reference."""
        result = enrich_topic(
            cas=store,
            fact_log_root=self.fact_log_root,
            intent=intent,
            storage=self.storage,
            db=self.db,
            policy=self.policy,
            web_search_service=self.web_search_service,
            web_search_constraints=self.web_search_constraints,
            web_search_budgets=self.web_search_budgets,
        )
        return result.knowledge_bundle_ref

    def submit(
        self,
        store: ArtifactStore,
        *,
        question: str | None = None,
        brief: Any | None = None,
        query_graph: Any | None = None,
        claim_texts: list[str] | None = None,
        constraints: SearchConstraints | None = None,
        budgets: SearchBudgetControls | None = None,
    ) -> str:
        """Submit a background deep-research job and return the job ID."""
        manager = self._job_manager(store)
        job_id = manager.submit(
            question=question,
            brief=brief,
            query_graph=query_graph,
            claim_texts=claim_texts,
            constraints=constraints or self.web_search_constraints,
            budgets=budgets or self.web_search_budgets,
        )
        return str(job_id)

    async def resume(self, store: ArtifactStore, *, checkpoint_artifact_id: str) -> str:
        """Resume a deep-research job from a persisted checkpoint."""
        manager = self._job_manager(store)
        job_id = await manager.resume(checkpoint_artifact_id=checkpoint_artifact_id)
        return str(job_id)

    def get_status(self, store: ArtifactStore, job_id: str) -> Any:
        """Return the latest persisted job status."""
        return self._job_manager(store).get_status(job_id)

    def get_snapshot(self, store: ArtifactStore, job_id: str) -> WebEvidenceBundle | None:
        """Return the latest persisted partial/completed evidence bundle."""
        return self._job_manager(store).get_snapshot(job_id)

    async def wait(self, store: ArtifactStore, job_id: str) -> Any:
        """Wait for a background deep-research job to finish."""
        return await self._job_manager(store).wait(job_id)

    def _job_manager(self, store: ArtifactStore) -> DeepResearchJobManager:
        key = _job_manager_key(store)
        manager = self._job_managers.get(key)
        if manager is not None:
            return manager
        local_root = _store_root(store)
        service = self.web_search_service or ScholarDeepSearchService(
            cas=store,
            cache_index_root=local_root,
        )
        manager = DeepResearchJobManager(service=service, cas=store, status_root=local_root)
        self._job_managers[key] = manager
        return manager


def _store_root(store: ArtifactStore) -> Path | None:
    root_value = getattr(store, "root", None)
    if isinstance(root_value, Path):
        return root_value
    if isinstance(root_value, str):
        return Path(root_value)
    return None


def _job_manager_key(store: ArtifactStore) -> str:
    root = _store_root(store)
    if root is not None:
        return str(root.resolve())
    return f"artifact-store:{id(store)}"


def _seed_sources_from_web_bundle(
    bundle: WebEvidenceBundle,
    *,
    max_docs: int | None,
) -> list[SourceSpec]:
    selected = [
        source
        for source in bundle.sources
        if source.fetch_status in {"ok", "cached"}
        and not source.paywalled
        and source.duplicate_of_source_id is None
        and source.error is None
    ]
    if max_docs is not None:
        selected = selected[:max_docs]
    if not selected:
        raise ValueError("web search bootstrap produced no usable sources")
    return [
        SourceSpec(
            kind="url",
            canonical_url=str(source.url),
            url=str(source.url),
            license="public-web",
            mime_hint=source.content_type,
            props={
                "source_type": source.source_type,
                "title": source.title,
                "publisher": source.domain,
                "web_evidence_source_id": source.source_id,
                "web_search_provider": source.provider,
            },
        )
        for source in selected
    ]


def _run_async_factory_sync[T](factory: Callable[[], Awaitable[T]]) -> T:
    result: T = run_coro_sync(factory())
    return result


__all__ = ["ScholarService", "enrich_topic"]
