"""Knowledge graph tools for scientist agents (PI, Drafter, DataNeedExtractor).

Provides typed methods that agents call directly (no LangChain tool wrappers).
Follows the same pattern as ``rag.py`` and ``knowledge_base.py``.

Usage::

    toolkit = KnowledgeToolkit(
        dataset_catalog=DatasetCatalogGraph(...),
        scholar_graph=ScholarKnowledgeGraph(...),
    )
    datasets = toolkit.search_datasets("GDP per capita", domain="fiscal")
    prior = toolkit.get_parameter_prior("min_wage_employment_elasticity")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from polisyos.academic.knowledge.search import ScholarKnowledgeGraph
    from polisyos.academic.knowledge.types import (
        CausalClaimResult,
        ParameterPrior,
        WorkSearchResult,
    )
    from polisyos.datasets.knowledge.search import DatasetCatalogGraph
    from polisyos.datasets.knowledge.types import DatasetSearchResult
    from polisyos.lex.knowledge.search import LegalKnowledgeGraph
    from polisyos.lex.knowledge.types import (
        LegalDocVersionResult,
        LegalFactResult,
        LegalProvisionResult,
        LegalReferenceEdgeResult,
        LegalSourceAnchor,
        LegalSourceBundle,
    )
    from polisyos.scholar.search.models import WebEvidenceBundle
    from polisyos.scientist.policy_verified.models import LegalCandidatePack, LegalSourcePack


class KnowledgeToolkit:
    """Typed tool methods for PI/Drafter agents to query knowledge graphs.

    All methods are synchronous and return typed Pydantic models.
    Agents decide *when* and *what* to search, keeping control of token budget.
    """

    def __init__(
        self,
        *,
        dataset_catalog: DatasetCatalogGraph | None = None,
        scholar_graph: ScholarKnowledgeGraph | None = None,
        legal_graph: LegalKnowledgeGraph | None = None,
        persistent_memory: object | None = None,
    ) -> None:
        self._dataset_catalog = dataset_catalog
        self._scholar_graph = scholar_graph
        self._legal_graph = legal_graph
        self._persistent_memory = persistent_memory  # PersistentMemoryStore

    @property
    def has_dataset_catalog(self) -> bool:
        return self._dataset_catalog is not None

    @property
    def has_scholar_graph(self) -> bool:
        return self._scholar_graph is not None

    @property
    def has_legal_graph(self) -> bool:
        return self._legal_graph is not None

    # ------------------------------------------------------------------
    # Dataset catalog tools
    # ------------------------------------------------------------------

    def search_datasets(
        self,
        query: str,
        *,
        domain: str | None = None,
        top_k: int = 10,
    ) -> list[DatasetSearchResult]:
        """Find datasets by natural language query."""
        if self._dataset_catalog is None:
            return []
        return self._dataset_catalog.search_datasets(
            query,
            domain_filter=domain,
            top_k=top_k,
        )

    def find_datasets_for_metric(
        self,
        metric_name: str,
        *,
        top_k: int = 20,
    ) -> list[DatasetSearchResult]:
        """Deterministic lookup: PolicyOS metric → datasets with connector params."""
        if self._dataset_catalog is None:
            return []
        return self._dataset_catalog.find_by_polisyos_metric(metric_name, top_k=top_k)

    def get_dataset_connector(self, dataset_id: str) -> dict | None:
        """Get connector params for pulling actual data from a discovered dataset."""
        if self._dataset_catalog is None:
            return None
        return self._dataset_catalog.get_connector_params(dataset_id)

    # ------------------------------------------------------------------
    # Academic evidence tools
    # ------------------------------------------------------------------

    def search_evidence(
        self,
        query: str,
        *,
        domain: str | None = None,
        top_k: int = 20,
    ) -> list[WorkSearchResult]:
        """Find academic works by query. Returns works with pre-extracted estimates."""
        if self._scholar_graph is None:
            return []
        return self._scholar_graph.find_relevant_works(
            query,
            domain=domain,
            top_k=top_k,
        )

    def get_parameter_prior(
        self,
        variable: str,
        *,
        domain: str | None = None,
        country: str | None = None,
        prefer_simulation_ready: bool = True,
    ) -> ParameterPrior | None:
        """Get aggregated prior distribution from literature.

        Returns a ParameterPrior with ``as_calibration_prior`` dict
        ready for ``foundry/calibration/`` TrainableHandle.
        """
        if self._scholar_graph is None:
            return None
        try:
            return self._scholar_graph.get_parameter_prior(
                variable,
                domain=domain,
                country=country,
                prefer_simulation_ready=prefer_simulation_ready,
            )
        except TypeError:
            # Backward-compatible fallback for older Scholar graph adapters/mocks.
            return self._scholar_graph.get_parameter_prior(
                variable,
                domain=domain,
                country=country,
            )

    def find_causal_evidence(
        self,
        cause: str,
        effect: str,
        *,
        min_trust: float = 0.5,
        support_mode: str = "exact",
    ) -> list[CausalClaimResult]:
        """Is there evidence that cause → effect? Returns ranked claims."""
        if self._scholar_graph is None:
            return []
        return self._scholar_graph.find_causal_evidence(
            cause,
            effect,
            min_trust=min_trust,
            support_mode=support_mode,
        )

    def get_mechanism_evidence(
        self,
        mechanism_name: str,
        *,
        top_k: int = 20,
    ) -> list[CausalClaimResult]:
        """Find evidence for a specific causal mechanism."""
        if self._scholar_graph is None:
            return []
        return self._scholar_graph.get_mechanism_evidence(
            mechanism_name,
            top_k=top_k,
        )

    # ------------------------------------------------------------------
    # Legal knowledge tools
    # ------------------------------------------------------------------

    def search_legal_facts(
        self,
        query: str,
        *,
        top_k: int = 20,
        trust_tier: str | None = "grounded_fact",
        jurisdiction: str | None = "UA",
        domain: str | None = None,
        as_of: str | None = None,
        include_candidates: bool = False,
    ) -> list[LegalFactResult]:
        """Search legal facts with trust-tier filtering."""
        if self._legal_graph is None:
            return []
        return self._legal_graph.hybrid_search(
            query,
            top_k=top_k,
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            include_candidates=include_candidates,
        )

    def search_legal_provisions(
        self,
        query: str,
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[LegalProvisionResult]:
        """Fallback retrieval of raw provisions for legal review."""
        if self._legal_graph is None:
            return []
        return self._legal_graph.search_provisions(
            query,
            top_k=top_k,
            min_similarity=min_similarity,
        )

    def find_legal_constraints(
        self,
        *,
        query: str | None = None,
        top_k: int = 50,
        jurisdiction: str | None = "UA",
        domain: str | None = None,
        as_of: str | None = None,
    ) -> list[LegalFactResult]:
        """Retrieve high-trust obligations, prohibitions and related clauses."""
        if self._legal_graph is None:
            return []
        return self._legal_graph.find_legal_constraints(
            query=query,
            top_k=top_k,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
        )

    def search_legal_thresholds(
        self,
        metric: str,
        *,
        top_k: int = 50,
        jurisdiction: str | None = "UA",
        domain: str | None = None,
        as_of: str | None = None,
    ) -> list[LegalFactResult]:
        """Retrieve quantitative legal thresholds from high-trust facts."""
        if self._legal_graph is None:
            return []
        return self._legal_graph.search_facts_with_threshold(
            metric,
            top_k=top_k,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
        )

    def get_applicable_norms(
        self,
        *,
        domain: str | None = None,
        jurisdiction: str | None = "UA",
        as_of: str | None = None,
        top_k: int = 100,
    ) -> list[LegalFactResult]:
        """Retrieve applicable norms for a domain/jurisdiction/time slice."""
        if self._legal_graph is None:
            return []
        return self._legal_graph.get_applicable_norms(
            domain=domain,
            jurisdiction=jurisdiction,
            as_of=as_of,
            top_k=top_k,
        )

    def load_provisions_by_anchor(
        self,
        doc_id: str,
        anchors: list[str],
    ) -> list[LegalSourceAnchor]:
        if self._legal_graph is None:
            return []
        return self._legal_graph.load_provisions_by_anchor(doc_id, anchors)

    def load_doc_version_chain(
        self,
        *,
        doc_id: str | None = None,
        doc_family_id: str | None = None,
    ) -> list[LegalDocVersionResult]:
        if self._legal_graph is None:
            return []
        return self._legal_graph.load_doc_version_chain(doc_id=doc_id, doc_family_id=doc_family_id)

    def load_appendix_context(
        self,
        doc_id: str,
        anchor: str,
        *,
        max_depth: int = 4,
    ) -> list[str]:
        if self._legal_graph is None:
            return []
        return self._legal_graph.load_appendix_context(doc_id, anchor, max_depth=max_depth)

    def expand_reference_neighborhood(
        self,
        doc_id: str,
        anchors: list[str],
        *,
        max_hops: int = 2,
    ) -> list[LegalReferenceEdgeResult]:
        if self._legal_graph is None:
            return []
        return self._legal_graph.expand_reference_neighborhood(doc_id, anchors, max_hops=max_hops)

    def load_source_bundle(
        self,
        *,
        doc_id: str,
        anchors: list[str],
        version_id: str | None = None,
        max_reference_hops: int = 2,
        candidate_fact_ids: list[str] | None = None,
        candidate_provision_ids: list[str] | None = None,
    ) -> LegalSourceBundle | None:
        if self._legal_graph is None:
            return None
        return self._legal_graph.load_source_bundle(
            doc_id=doc_id,
            anchors=anchors,
            version_id=version_id,
            max_reference_hops=max_reference_hops,
            candidate_fact_ids=candidate_fact_ids,
            candidate_provision_ids=candidate_provision_ids,
        )

    def get_versioned_source_refs(
        self,
        *,
        doc_id: str | None = None,
        doc_family_id: str | None = None,
    ) -> list[LegalDocVersionResult]:
        if self._legal_graph is None:
            return []
        return self._legal_graph.get_versioned_source_refs(
            doc_id=doc_id, doc_family_id=doc_family_id
        )

    def assemble_legal_candidate_pack(
        self,
        query: str,
        *,
        jurisdiction: str = "UA",
        domain: str | None = None,
        as_of: str | None = None,
        top_k_facts: int = 25,
        top_k_provisions: int = 15,
    ) -> LegalCandidatePack:
        from polisyos.scientist.policy_verified.models import LegalCandidatePack

        fact_hits = self.search_legal_facts(
            query,
            top_k=top_k_facts,
            trust_tier="grounded_fact",
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
        )
        constraint_hits = self.find_legal_constraints(
            query=query,
            top_k=max(10, top_k_facts // 2),
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
        )
        provision_hits = self.search_legal_provisions(query, top_k=top_k_provisions)
        fact_map = {item.fact_id: item for item in [*fact_hits, *constraint_hits]}
        return LegalCandidatePack(
            request_id="toolkit",
            queries=[query],
            fact_hits=list(fact_map.values()),
            provision_hits=provision_hits,
            hit_reasons={item.fact_id: "legal_search" for item in fact_map.values()},
            source_family_hints={
                item.fact_id: (item.legal_unit_subtype or item.top_domain or "")
                for item in fact_map.values()
            },
            anchor_coverage_hints={
                item.fact_id: [item.provision_anchor or item.provision_citation]
                for item in fact_map.values()
                if item.provision_anchor or item.provision_citation
            },
        )

    def expand_legal_source_pack(
        self,
        candidate_pack: LegalCandidatePack,
        *,
        max_source_docs: int = 120,
        max_reference_hops: int = 2,
    ) -> LegalSourcePack:
        from polisyos.scientist.policy_verified.models import LegalSourcePack

        if self._legal_graph is None:
            return LegalSourcePack(request_id=candidate_pack.request_id)
        bundles: list[LegalSourceBundle] = []
        grouped: dict[str, dict[str, set[str] | list[str]]] = {}
        for fact in candidate_pack.fact_hits:
            if not fact.doc_id:
                continue
            bucket = grouped.setdefault(
                fact.doc_id,
                {"anchors": set(), "fact_ids": [], "provision_ids": []},
            )
            if fact.provision_anchor:
                bucket["anchors"].add(fact.provision_anchor)
            bucket["fact_ids"].append(fact.fact_id)
        for provision in candidate_pack.provision_hits:
            if not provision.doc_id:
                continue
            bucket = grouped.setdefault(
                provision.doc_id,
                {"anchors": set(), "fact_ids": [], "provision_ids": []},
            )
            if provision.anchor_path:
                bucket["anchors"].add(provision.anchor_path)
            bucket["provision_ids"].append(provision.provision_id)
        for doc_id, payload in list(grouped.items())[:max_source_docs]:
            bundle = self.load_source_bundle(
                doc_id=doc_id,
                anchors=sorted(payload["anchors"]),
                max_reference_hops=max_reference_hops,
                candidate_fact_ids=list(payload["fact_ids"]),
                candidate_provision_ids=list(payload["provision_ids"]),
            )
            if bundle is not None:
                bundles.append(bundle)
        return LegalSourcePack(request_id=candidate_pack.request_id, source_bundles=bundles)

    # ------------------------------------------------------------------
    # Persistent memory tools
    # ------------------------------------------------------------------

    @property
    def has_persistent_memory(self) -> bool:
        return self._persistent_memory is not None

    def remember(
        self,
        content: str,
        *,
        tags: list[str] | None = None,
        kind: str = "episodic",
        source_run_id: str = "",
        source_node_alias: str | None = None,
        confidence: float = 1.0,
    ) -> dict:
        """Store a memory entry for recall in future runs.

        Returns a dict with ``memory_id`` and ``artifact_id``.
        """
        if self._persistent_memory is None:
            return {"error": "persistent_memory not available"}

        from polisyos.scientist.agent.persistent_memory import MemoryEntry, MemoryKind

        entry = MemoryEntry(
            kind=MemoryKind(kind),
            content=content,
            tags=tags or [],
            source_run_id=source_run_id,
            source_node_alias=source_node_alias,
            confidence=confidence,
        )
        ref = self._persistent_memory.store_memory(entry)
        return {"memory_id": entry.memory_id, "artifact_id": ref.artifact_id}

    def recall(
        self,
        query: str,
        *,
        kind: str | None = None,
        tags: list[str] | None = None,
        max_results: int = 5,
        min_confidence: float = 0.0,
    ) -> list[dict]:
        """Retrieve memories matching a query.

        Returns a list of dicts with ``memory_id``, ``kind``, ``content``, ``tags``,
        ``confidence``, and ``created_at``.
        """
        if self._persistent_memory is None:
            return []

        from polisyos.scientist.agent.persistent_memory import MemoryKind, MemoryQuery

        q = MemoryQuery(
            query_text=query,
            kind=MemoryKind(kind) if kind else None,
            tags=tags or [],
            max_results=max_results,
            min_confidence=min_confidence,
        )
        entries = self._persistent_memory.query(q)
        return [
            {
                "memory_id": e.memory_id,
                "kind": e.kind.value,
                "content": e.content,
                "tags": e.tags,
                "confidence": e.confidence,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]

    # ------------------------------------------------------------------
    # Prompt context helpers
    # ------------------------------------------------------------------

    def format_dataset_context(
        self,
        results: list[DatasetSearchResult],
        *,
        max_results: int = 5,
    ) -> str:
        """Format dataset search results for LLM prompt injection."""
        if not results:
            return ""
        lines = ["## AVAILABLE DATASETS"]
        for r in results[:max_results]:
            lines.append(f"- **{r.title}** (publisher: {r.publisher}, portal: {r.source_portal})")
            if r.variables:
                lines.append(f"  Variables: {', '.join(r.variables[:10])}")
            if r.polisyos_metrics:
                lines.append(f"  PolicyOS metrics: {', '.join(r.polisyos_metrics)}")
        return "\n".join(lines)

    def format_evidence_context(
        self,
        results: list[WorkSearchResult],
        *,
        max_results: int = 5,
    ) -> str:
        """Format academic evidence for LLM prompt injection."""
        if not results:
            return ""
        lines = ["## ACADEMIC EVIDENCE"]
        for r in results[:max_results]:
            lines.append(
                f"- **{r.title}** ({r.year}, {r.journal}, "
                f"citations: {r.cited_by_count}, trust: {r.trust_score:.2f})"
            )
            if r.pre_extracted_estimates:
                for est in r.pre_extracted_estimates[:2]:
                    ci = ""
                    if est.ci_low is not None and est.ci_high is not None:
                        ci = f" [{est.ci_low:.3f}, {est.ci_high:.3f}]"
                    lines.append(f"  >> {est.variable_name}: {est.estimate:.4f}{ci}")
        return "\n".join(lines)

    def format_prior_context(self, prior: ParameterPrior | None) -> str:
        """Format parameter prior for LLM prompt injection."""
        if prior is None:
            return ""
        return (
            f"## LITERATURE PRIOR: {prior.variable}\n"
            f"Mean: {prior.prior_mean:.4f}, Std: {prior.prior_std:.4f}, "
            f"Range: [{prior.prior_low:.4f}, {prior.prior_high:.4f}], "
            f"N studies: {prior.n_studies}, Best design: {prior.best_design}"
        )

    def format_legal_context(
        self,
        results: list[LegalFactResult],
        *,
        max_results: int = 8,
    ) -> str:
        """Format legal facts for prompt injection in drafting/review flows."""
        if not results:
            return ""
        lines = ["## LEGAL CONTEXT"]
        for result in results[:max_results]:
            lines.append(
                f"- [{result.trust_tier}] {result.fact_text} "
                f"({result.doc_name}, {result.provision_citation})"
            )
            if result.source_quote_uk:
                lines.append(f"  Quote: {result.source_quote_uk[:240]}")
            if result.top_domain:
                lines.append(f"  Domain: {result.top_domain}")
        return "\n".join(lines)

    def format_web_evidence_context(
        self,
        bundle: WebEvidenceBundle,
        *,
        max_claims: int = 8,
        max_snippets: int = 8,
    ) -> str:
        """Format deep-search claim snippets with source URLs for prompt injection."""
        if not bundle.sources and not bundle.snippets and not bundle.claim_supports:
            return ""

        source_by_id = {source.source_id: source for source in bundle.sources}
        snippet_by_id = {snippet.snippet_id: snippet for snippet in bundle.snippets}
        lines = ["## WEB EVIDENCE"]

        for support in bundle.claim_supports[:max_claims]:
            lines.append(f"- Claim: {support.claim_text}")
            if support.uncertainty_note:
                lines.append(f"  Uncertainty: {support.uncertainty_note}")
            for snippet_id in support.snippet_ids[:max_snippets]:
                snippet = snippet_by_id.get(snippet_id)
                if snippet is None:
                    continue
                source = source_by_id.get(snippet.source_id)
                title = source.title if source is not None and source.title else str(snippet.url)
                url = str(source.url if source is not None else snippet.url)
                text = snippet.text.replace("\n", " ").strip()
                lines.append(f"  [{title}]({url}) [{snippet.start_char}:{snippet.end_char}] {text}")

        if bundle.uncertainty_notes:
            lines.append(f"Bundle notes: {', '.join(bundle.uncertainty_notes[:8])}")
        return "\n".join(lines)
