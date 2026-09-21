"""Expose Scholar enrichment as a library function and a lightweight service wrapper."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.canon import content_hash
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent, SourceSpec
from polisyos.scholar.orchestrator.enrich import enrich_topic as _enrich_topic
from polisyos.scholar.errors import ScholarAcquireError
from polisyos.scholar.search.jobs import DeepResearchJobManager
from polisyos.scholar.search.service import ScholarDeepSearchService

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.storage import StoragePort
    from polisyos.scholar.policies import ScholarPolicy
    from polisyos.scholar.search.models import (
        QueryGraph,
        ResearchBrief,
        ResearchJobStatus,
        SearchBudgetControls,
        SearchConstraints,
        WebEvidenceBundle,
    )
    from polisyos.scholar.types import EnrichResultV1
    from polisyos.scholar_requirement import ScholarSupportRequirementSpec


def enrich_topic(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    intent: ResearchIntent,
    storage: StoragePort | None = None,
    db: object | None = None,
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
            web_bundle_artifact_id = str(search_service.persist_bundle(web_bundle).artifact_id)
        except ValueError:
            web_bundle_artifact_id = None
        hydrated_intent = intent.model_copy(
            update={
                "seed_sources": _seed_sources_from_web_bundle(
                    web_bundle,
                    cas=cas,
                    cache=getattr(search_service, "_cache", None),
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
    db: object | None = None
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
        brief: ResearchBrief | None = None,
        query_graph: QueryGraph | None = None,
        claim_texts: list[str] | None = None,
        requirement_specs: list[ScholarSupportRequirementSpec | Mapping[str, object]]
        | None = None,
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
            requirement_specs=requirement_specs,
            constraints=constraints or self.web_search_constraints,
            budgets=budgets or self.web_search_budgets,
        )
        return str(job_id)

    async def resume(self, store: ArtifactStore, *, checkpoint_artifact_id: str) -> str:
        """Resume a deep-research job from a persisted checkpoint."""
        manager = self._job_manager(store)
        job_id = await manager.resume(checkpoint_artifact_id=checkpoint_artifact_id)
        return str(job_id)

    def get_status(self, store: ArtifactStore, job_id: str) -> ResearchJobStatus:
        """Return the latest persisted job status."""
        return self._job_manager(store).get_status(job_id)

    def get_snapshot(self, store: ArtifactStore, job_id: str) -> WebEvidenceBundle | None:
        """Return the latest persisted partial/completed evidence bundle."""
        return self._job_manager(store).get_snapshot(job_id)

    async def wait(self, store: ArtifactStore, job_id: str) -> ResearchJobStatus:
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
    cas: FileSystemCAS,
    cache: Any | None = None,
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
    return [_source_spec_from_snapshot(source, cas=cas, cache=cache) for source in selected]


def _source_spec_from_snapshot(
    source: Any,
    *,
    cas: FileSystemCAS,
    cache: Any | None = None,
) -> SourceSpec:
    """Resolve one search source to its exact CAS snapshot before enrichment."""
    cached_record = _cache_record_for_source(source, cache)
    source_identity = str(getattr(source, "url", "")) or None
    expected_digest = _normalize_digest(getattr(source, "content_sha256", None))
    candidate_ref = (
        getattr(source, "artifact_id", None)
        or getattr(source, "raw_artifact_id", None)
        or getattr(cached_record, "artifact_id", None)
    )
    if candidate_ref is None and expected_digest is not None:
        candidate_ref = f"sha256:{expected_digest}"
    if candidate_ref is None:
        raise ScholarAcquireError(
            "web source has no reusable raw snapshot",
            source_identity=source_identity,
            details={"reason": "missing_raw_artifact_ref"},
        )

    try:
        artifact_id = ArtifactID.model_validate(str(candidate_ref))
    except Exception as exc:
        raise ScholarAcquireError(
            "web source raw snapshot reference is invalid",
            source_identity=source_identity,
            details={"artifact_id": str(candidate_ref)},
        ) from exc

    if expected_digest is not None and artifact_id.hex != expected_digest:
        raise ScholarAcquireError(
            "web source raw snapshot reference does not match its digest",
            source_identity=source_identity,
            details={
                "artifact_id": str(artifact_id),
                "content_sha256": expected_digest,
            },
        )

    try:
        raw_bytes = cas.get_bytes(artifact_id)
    except Exception as exc:
        raise ScholarAcquireError(
            "web source raw snapshot is unavailable",
            source_identity=source_identity,
            details={"artifact_id": str(artifact_id)},
        ) from exc

    actual_digest = content_hash(raw_bytes)
    if expected_digest is not None and actual_digest != expected_digest:
        raise ScholarAcquireError(
            "web source raw snapshot digest mismatch",
            source_identity=source_identity,
            details={
                "artifact_id": str(artifact_id),
                "expected_sha256": expected_digest,
                "actual_sha256": actual_digest,
            },
        )
    if actual_digest != artifact_id.hex:
        raise ScholarAcquireError(
            "web source raw snapshot artifact identity mismatch",
            source_identity=source_identity,
            details={
                "artifact_id": str(artifact_id),
                "actual_sha256": actual_digest,
            },
        )

    declared_size = getattr(source, "byte_size", None) or getattr(cached_record, "byte_size", None)
    if declared_size is not None:
        try:
            declared_size = int(declared_size)
        except (TypeError, ValueError) as exc:
            raise ScholarAcquireError(
                "web source raw snapshot byte size is invalid",
                source_identity=source_identity,
                details={"byte_size": str(declared_size)},
            ) from exc
        if declared_size != len(raw_bytes):
            raise ScholarAcquireError(
                "web source raw snapshot byte size mismatch",
                source_identity=source_identity,
                details={"expected": declared_size, "actual": len(raw_bytes)},
            )

    props = {
        "source_type": str(getattr(source, "source_type", "web")),
        "title": str(getattr(source, "title", "")),
        "publisher": str(getattr(source, "domain", "")),
        "web_evidence_source_id": str(getattr(source, "source_id", "")),
        "web_search_provider": str(getattr(source, "provider", "")),
        "canonical_url": source_identity or "",
        "final_url": str(
            getattr(source, "final_url", None)
            or getattr(cached_record, "final_url", None)
            or source_identity
            or ""
        ),
        "raw_artifact_id": str(artifact_id),
        "content_sha256": actual_digest,
        "byte_size": str(len(raw_bytes)),
        "fetch_status": str(getattr(source, "fetch_status", "ok")),
        "fetch_profile": _json_prop(
            getattr(source, "fetch_profile", None)
            or getattr(cached_record, "fetch_profile", {})
        ),
        "redirect_chain": _json_prop(
            getattr(source, "redirect_chain", None)
            or getattr(cached_record, "redirect_chain", [])
        ),
    }
    for field in (
        "etag",
        "last_modified",
        "lineage_parent_artifact_id",
        "refresh_reason",
    ):
        value = getattr(source, field, None) or getattr(cached_record, field, None)
        if value is not None:
            props[field] = str(value)
    props = {key: value for key, value in props.items() if value != ""}

    source_license = getattr(source, "license", None)
    cached_license = getattr(cached_record, "license", None)
    if (not source_license or source_license == "public-web") and cached_license:
        source_license = cached_license
    license_value = str(source_license or "public-web").strip()
    if not license_value:
        raise ScholarAcquireError(
            "web source raw snapshot has no license",
            source_identity=source_identity,
            details={"artifact_id": str(artifact_id)},
        )
    return SourceSpec(
        kind="bytes",
        source_locator=str(artifact_id),
        license=license_value,
        mime_hint=str(getattr(source, "content_type", "application/octet-stream")),
        props=props,
        data=raw_bytes,
    )


def _cache_record_for_source(source: Any, cache: Any | None) -> Any | None:
    if cache is None:
        return None
    getter = getattr(cache, "get", None)
    source_url = getattr(source, "url", None)
    if not callable(getter) or source_url is None:
        return None
    try:
        return getter(str(source_url))
    except Exception:
        return None


def _normalize_digest(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().lower()
    if candidate.startswith("sha256:"):
        candidate = candidate[7:]
    if len(candidate) != 64 or any(char not in "0123456789abcdef" for char in candidate):
        raise ScholarAcquireError(
            "web source content digest is invalid",
            details={"content_sha256": value},
        )
    return candidate


def _json_prop(value: object) -> str:
    if isinstance(value, Mapping):
        value = {str(key): item for key, item in value.items()}
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _run_async_factory_sync[T](factory: Callable[[], Awaitable[T]]) -> T:
    result: T = run_coro_sync(factory())
    return result


__all__ = ["ScholarService", "enrich_topic"]
