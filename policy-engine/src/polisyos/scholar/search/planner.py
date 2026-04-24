"""Research brief generation and adaptive query-graph planning."""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from polisyos.scholar.search.models import QueryGraph, QueryNode, ResearchBrief

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.core.contracts.scholar import ResearchIntent

_DEFAULT_PERSPECTIVES = [
    "official policy source",
    "fiscal cost and budget impact",
    "implementation evidence",
    "causal evaluation and outcomes",
    "legal constraints",
    "equity and distributional impact",
    "cross-jurisdiction comparison",
]

_DOMAIN_PERSPECTIVES: dict[str, list[str]] = {
    "fiscal": [
        "official budget authority",
        "fiscal cost and budget impact",
        "macroeconomic spillovers",
        "implementation evidence",
        "cross-jurisdiction comparison",
    ],
    "health": [
        "official health authority",
        "clinical outcomes",
        "public health implementation",
        "equity and access",
        "cost effectiveness",
    ],
    "education": [
        "education ministry or agency guidance",
        "learning outcomes evidence",
        "program implementation",
        "equity and inclusion",
        "budget impact",
    ],
    "labor": [
        "official labor regulation",
        "employment and wage outcomes",
        "firm compliance and implementation",
        "worker equity and segmentation",
        "cross-jurisdiction comparison",
    ],
}

_SOURCE_TYPE_HINTS = {
    "official policy source": ["government", "law", "policy"],
    "official budget authority": ["budget", "government"],
    "official health authority": ["government", "health"],
    "official labor regulation": ["law", "government"],
    "education ministry or agency guidance": ["government", "education"],
    "clinical outcomes": ["academic", "health"],
    "causal evaluation and outcomes": ["academic"],
    "learning outcomes evidence": ["academic", "education"],
    "cross-jurisdiction comparison": ["government", "academic"],
}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "has",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "which",
    "with",
}


def build_research_brief(
    *,
    question: str | None = None,
    intent: ResearchIntent | None = None,
    locale: str = "en-US",
    perspectives: Sequence[str] | None = None,
) -> ResearchBrief:
    """Normalize a free-form research request or `ResearchIntent` into a search brief."""
    if intent is not None:
        question_text = (intent.topic or intent.domain or question or "").strip()
        domain = (intent.domain or "").strip().lower()
        jurisdictions = [value.strip() for value in intent.jurisdictions if value.strip()]
        if intent.jurisdiction and intent.jurisdiction.strip():
            jurisdictions.append(intent.jurisdiction.strip())
        time_window_start = intent.time_window.start if intent.time_window else None
        time_window_end = intent.time_window.end if intent.time_window else None
        notes = list(intent.notes)
    else:
        question_text = (question or "").strip()
        domain = ""
        jurisdictions = []
        time_window_start = None
        time_window_end = None
        notes = []

    if not question_text:
        raise ValueError("question or intent.topic/domain is required")

    selected_perspectives = list(
        perspectives or _DOMAIN_PERSPECTIVES.get(domain, _DEFAULT_PERSPECTIVES)
    )
    seed_terms = _extract_seed_terms(question_text)
    required_source_types = sorted(
        {
            hint
            for perspective in selected_perspectives
            for hint in _SOURCE_TYPE_HINTS.get(perspective, ["web"])
        }
    )
    preferred_domains = _infer_preferred_domains(domain, jurisdictions)
    return ResearchBrief(
        question=question_text,
        domain=domain,
        jurisdictions=sorted(dict.fromkeys(jurisdictions)),
        time_window_start=time_window_start,
        time_window_end=time_window_end,
        locale=locale,
        perspectives=selected_perspectives,
        required_source_types=required_source_types,
        preferred_domains=preferred_domains,
        seed_terms=seed_terms,
        notes=notes,
    )


def plan_query_graph(
    brief: ResearchBrief,
    *,
    max_depth: int = 2,
    per_perspective_queries: int = 2,
) -> QueryGraph:
    """Build an initial query DAG with one root node and perspective expansion nodes."""
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if per_perspective_queries < 1:
        raise ValueError("per_perspective_queries must be >= 1")

    root_query = _compose_query(
        brief.question,
        jurisdiction=None,
        perspective=None,
        time_window_start=brief.time_window_start,
        time_window_end=brief.time_window_end,
    )
    root_id = _node_id(root_query, perspective="root", depth=0, parent_id=None)
    nodes = [
        QueryNode(
            node_id=root_id,
            query=root_query,
            perspective="root",
            depth=0,
            parent_id=None,
            rationale="root broad query",
        )
    ]

    if max_depth >= 1:
        for perspective in brief.perspectives:
            for jurisdiction in _jurisdictions_or_none(brief.jurisdictions):
                for variant_index in range(per_perspective_queries):
                    query = _compose_query(
                        brief.question,
                        jurisdiction=jurisdiction,
                        perspective=perspective,
                        time_window_start=brief.time_window_start,
                        time_window_end=brief.time_window_end,
                        preferred_domains=brief.preferred_domains if variant_index == 0 else [],
                        source_hints=_SOURCE_TYPE_HINTS.get(perspective, []),
                        variant_index=variant_index,
                    )
                    nodes.append(
                        QueryNode(
                            node_id=_node_id(
                                query,
                                perspective=perspective,
                                depth=1,
                                parent_id=root_id,
                            ),
                            query=query,
                            perspective=perspective,
                            depth=1,
                            parent_id=root_id,
                            rationale=f"perspective expansion: {perspective}",
                        )
                    )

    return QueryGraph(brief=brief, nodes=nodes, root_node_ids=[root_id])


def apply_adaptive_query_reformulation(
    graph: QueryGraph,
    *,
    node_id: str,
    min_hit_count: int = 2,
    max_children: int = 2,
) -> list[QueryNode]:
    """Expand a low-yield query node with broader and domain-focused reformulations."""
    node = graph.node_by_id(node_id)
    if node.hit_count >= min_hit_count or node.depth >= 8:
        return []

    query_variants = _reformulate_query(
        node.query,
        perspective=node.perspective,
        brief=graph.brief,
    )[:max_children]
    children: list[QueryNode] = []
    for variant in query_variants:
        if variant == node.query:
            continue
        child = QueryNode(
            node_id=_node_id(
                variant,
                perspective=node.perspective,
                depth=node.depth + 1,
                parent_id=node.node_id,
            ),
            query=variant,
            perspective=node.perspective,
            depth=node.depth + 1,
            parent_id=node.node_id,
            rationale="adaptive reformulation after low search yield",
        )
        if child.node_id not in {existing.node_id for existing in graph.nodes}:
            graph.nodes.append(child)
            children.append(child)
            node.reformulations.append(variant)
    if children:
        node.status = "expanded"
    return children


def _compose_query(
    question: str,
    *,
    jurisdiction: str | None,
    perspective: str | None,
    time_window_start: str | None,
    time_window_end: str | None,
    preferred_domains: Sequence[str] | None = None,
    source_hints: Sequence[str] | None = None,
    variant_index: int = 0,
) -> str:
    parts = [question.strip()]
    if jurisdiction:
        parts.append(jurisdiction.strip())
    if perspective:
        parts.append(perspective.strip())
    if time_window_start or time_window_end:
        if time_window_start and time_window_end:
            parts.append(f"{time_window_start}..{time_window_end}")
        elif time_window_start:
            parts.append(f"since {time_window_start}")
        elif time_window_end:
            parts.append(f"before {time_window_end}")
    if source_hints:
        parts.extend(hint.strip() for hint in source_hints if hint.strip())
    if preferred_domains and variant_index == 0:
        parts.extend(f"site:{domain}" for domain in preferred_domains if domain)
    if variant_index == 1:
        parts.append("report OR analysis")
    elif variant_index >= 2:
        parts.append("evidence OR evaluation")
    return " ".join(part for part in parts if part).strip()


def _reformulate_query(query: str, *, perspective: str, brief: ResearchBrief) -> list[str]:
    broad = re.sub(r"\bsite:[^\s]+\b", "", query, flags=re.IGNORECASE)
    broad = re.sub(r"\s+", " ", broad).strip()
    variants = [
        f"{broad} official report policy",
        f"{broad} evidence evaluation filetype:pdf",
    ]
    if brief.jurisdictions:
        variants.append(f"{brief.question} {' '.join(brief.jurisdictions)} {perspective}")
    if brief.seed_terms:
        variants.append(f"{' '.join(brief.seed_terms[:6])} {perspective}")
    return [variant.strip() for variant in variants if variant.strip()]


def _extract_seed_terms(question: str, *, limit: int = 12) -> list[str]:
    words = re.findall(r"[\w'-]+", question.lower())
    ordered: list[str] = []
    for word in words:
        if len(word) <= 2 or word in _STOPWORDS:
            continue
        if word not in ordered:
            ordered.append(word)
        if len(ordered) >= limit:
            break
    return ordered


def _infer_preferred_domains(domain: str, jurisdictions: Sequence[str]) -> list[str]:
    preferred = [".gov", ".edu", ".org", "oecd.org", "worldbank.org", "who.int"]
    if domain == "health":
        preferred.extend(["who.int", "cdc.gov", "nih.gov"])
    elif domain == "education":
        preferred.extend(["ed.gov", "oecd.org", "unesco.org"])
    elif domain == "labor":
        preferred.extend(["ilo.org", "dol.gov", "oecd.org"])
    elif domain == "fiscal":
        preferred.extend(["imf.org", "worldbank.org", "treasury.gov"])
    for jurisdiction in jurisdictions:
        key = jurisdiction.lower()
        if key in {"us", "usa", "united states"}:
            preferred.extend(["usa.gov", "cbo.gov", "congress.gov"])
        if key in {"uk", "united kingdom", "gb"}:
            preferred.extend(["gov.uk"])
        if key in {"eu", "european union"}:
            preferred.extend(["europa.eu"])
    return sorted(dict.fromkeys(preferred))


def _jurisdictions_or_none(jurisdictions: Sequence[str]) -> list[str | None]:
    values = [value for value in jurisdictions if value]
    return values or [None]


def _node_id(
    query: str,
    *,
    perspective: str,
    depth: int,
    parent_id: str | None,
) -> str:
    payload = f"{query}|{perspective}|{depth}|{parent_id or ''}".encode()
    return f"qg.{hashlib.sha256(payload).hexdigest()[:24]}"


__all__ = [
    "apply_adaptive_query_reformulation",
    "build_research_brief",
    "plan_query_graph",
]
