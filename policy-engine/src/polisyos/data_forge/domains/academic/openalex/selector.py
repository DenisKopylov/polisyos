"""Topic-based OpenAlex selector for Pass 1 (150 works/topic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import log1p
from typing import TYPE_CHECKING, Any

from polisyos.data_forge.domains.academic.openalex.client import OpenAlexClient, OpenAlexRequest

if TYPE_CHECKING:
    from polisyos.data_forge.domains.academic.openalex.topic_catalog import TopicEntry


@dataclass(frozen=True)
class SelectedTopicWork:
    """Selected topic work public type."""

    run_id: str
    topic_id: str
    topic_display_name: str
    topic_policy_block: str
    topic_policy_subblock: str
    source_file: str
    work_id: str
    rank: int
    selection_score: float
    batch_origin: str
    selected_at: str
    work: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "topic_id": self.topic_id,
            "topic_display_name": self.topic_display_name,
            "topic_policy_block": self.topic_policy_block,
            "topic_policy_subblock": self.topic_policy_subblock,
            "source_file": self.source_file,
            "work_id": self.work_id,
            "rank": self.rank,
            "selection_score": self.selection_score,
            "batch_origin": self.batch_origin,
            "selected_at": self.selected_at,
            "work": self.work,
        }


def _keyword_presence_score(text: str, keywords: tuple[str, ...]) -> float:
    if not text:
        return 0.0
    lowered = text.lower()
    hits = sum(1 for kw in keywords if kw in lowered)
    return min(1.0, hits / max(1, len(keywords) / 3.0))


def _impact_norm(work: dict[str, Any]) -> float:
    p = work.get("citation_normalized_percentile")
    if isinstance(p, dict):
        if p.get("is_in_top_1_percent"):
            return 1.0
        if p.get("is_in_top_10_percent"):
            return 0.85

    fwci = work.get("fwci")
    if isinstance(fwci, (int, float)):
        return min(float(fwci) / 5.0, 1.0)

    cited = int(work.get("cited_by_count") or 0)
    return min(log1p(cited) / log1p(500), 1.0)


def _recency_norm(work: dict[str, Any]) -> float:
    year = int(work.get("publication_year") or 0)
    if year >= 2020:
        return 1.0
    if year >= 2015:
        return 0.75
    if year >= 2010:
        return 0.55
    if year >= 2005:
        return 0.35
    return 0.2


def _method_signal_norm(work: dict[str, Any]) -> float:
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
    title = str(work.get("title") or "")
    text = f"{title}\n{abstract}".lower()
    high = (
        "randomized",
        "randomised",
        "rct",
        "instrumental variable",
        "regression discontinuity",
        "difference-in-differences",
        "diff-in-diff",
        "natural experiment",
        "quasi-experiment",
    )
    medium = (
        "effect of",
        "impact of",
        "elasticity",
        "multiplier",
        "meta-analysis",
        "systematic review",
        "cross-country",
        "multi-country",
    )
    if any(kw in text for kw in high):
        return 1.0
    if any(kw in text for kw in medium):
        return 0.65
    return 0.2


def _content_availability_norm(work: dict[str, Any]) -> float:
    score = 0.0
    if work.get("abstract_inverted_index"):
        score += 0.5
    if work.get("has_fulltext") is True:
        score += 0.3
    oa = work.get("open_access")
    if isinstance(oa, dict) and oa.get("is_oa"):
        score += 0.2
    return min(score, 1.0)


def _transportability_signal_norm(work: dict[str, Any]) -> float:
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
    title = str(work.get("title") or "")
    text = f"{title}\n{abstract}".lower()
    keywords = (
        "cross-country",
        "multi-country",
        "external validity",
        "heterogeneous",
        "varies by",
        "conditional on",
        "boundary",
        "when",
        "in countries with",
    )
    return _keyword_presence_score(text, keywords)


def _first_author_id(work: dict[str, Any]) -> str:
    authorships = work.get("authorships")
    if not isinstance(authorships, list):
        return ""
    for a in authorships:
        if not isinstance(a, dict):
            continue
        author = a.get("author")
        if isinstance(author, dict):
            aid = str(author.get("id") or "")
            if aid:
                return aid
    return ""


def _journal_id(work: dict[str, Any]) -> str:
    primary = work.get("primary_location")
    if not isinstance(primary, dict):
        return ""
    source = primary.get("source")
    if not isinstance(source, dict):
        return ""
    sid = str(source.get("id") or "")
    if sid:
        return sid
    return str(source.get("display_name") or "")


def _is_review(work: dict[str, Any]) -> bool:
    wtype = str(work.get("type") or "").lower()
    if "review" in wtype:
        return True
    title = str(work.get("title") or "").lower()
    return "review" in title or "meta-analysis" in title


def _is_recent(work: dict[str, Any], year_min: int = 2018) -> bool:
    return int(work.get("publication_year") or 0) >= year_min


def _score(work: dict[str, Any]) -> float:
    return (
        0.30 * _impact_norm(work)
        + 0.20 * _recency_norm(work)
        + 0.20 * _method_signal_norm(work)
        + 0.15 * _content_availability_norm(work)
        + 0.15 * _transportability_signal_norm(work)
    )


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, pos_list in inverted_index.items():
        if not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            if isinstance(pos, int):
                positions.append((pos, word))
    positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in positions)


def _build_filter(
    *,
    topic_id: str,
    year_min: int,
    year_max: int,
    citation_gt: int,
    language_en: bool,
    include_review: bool,
) -> str:
    parts = [
        f"topics.id:{topic_id}",
        "is_retracted:false",
        "has_abstract:true",
        f"publication_year:{year_min}-{year_max}",
        f"cited_by_count:>{citation_gt}",
    ]
    if language_en:
        parts.append("language:en")
    if include_review:
        parts.append("type:article|review")
    else:
        parts.append("type:article")
    return ",".join(parts)


async def _fetch_batch(
    client: OpenAlexClient,
    *,
    topic_id: str,
    batch_origin: str,
    year_min: int,
    citation_gt: int,
    sort: str,
    language_en: bool,
    include_review: bool,
    per_page: int,
) -> list[dict[str, Any]]:
    year_max = datetime.now(UTC).year
    payload = await client.list_works(
        OpenAlexRequest(
            filter_expr=_build_filter(
                topic_id=topic_id,
                year_min=year_min,
                year_max=year_max,
                citation_gt=citation_gt,
                language_en=language_en,
                include_review=include_review,
            ),
            sort=sort,
            per_page=per_page,
        )
    )
    rows = payload.get("results", []) if isinstance(payload, dict) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({"work": row, "batch_origin": batch_origin})
    return out


async def select_topic_works(
    client: OpenAlexClient,
    *,
    topic: TopicEntry,
    run_id: str,
    target_per_topic: int,
    per_page: int,
) -> list[SelectedTopicWork]:
    """Select top-N works for one topic with fallback and diversity constraints."""
    target = max(1, int(target_per_topic))

    # strict two-batch retrieval
    candidates = []
    candidates.extend(
        await _fetch_batch(
            client,
            topic_id=topic.topic_id,
            batch_origin="strict_classic",
            year_min=2000,
            citation_gt=10,
            sort="cited_by_count:desc",
            language_en=True,
            include_review=False,
            per_page=per_page,
        )
    )
    candidates.extend(
        await _fetch_batch(
            client,
            topic_id=topic.topic_id,
            batch_origin="strict_recent",
            year_min=2018,
            citation_gt=2,
            sort="fwci:desc",
            language_en=True,
            include_review=False,
            per_page=per_page,
        )
    )

    # fallback ladder
    if len(candidates) < target:
        candidates.extend(
            await _fetch_batch(
                client,
                topic_id=topic.topic_id,
                batch_origin="fallback_citations_relaxed",
                year_min=2000,
                citation_gt=1,
                sort="cited_by_count:desc",
                language_en=True,
                include_review=False,
                per_page=per_page,
            )
        )
    if len(candidates) < target:
        candidates.extend(
            await _fetch_batch(
                client,
                topic_id=topic.topic_id,
                batch_origin="fallback_no_language",
                year_min=2000,
                citation_gt=1,
                sort="cited_by_count:desc",
                language_en=False,
                include_review=False,
                per_page=per_page,
            )
        )
    if len(candidates) < target:
        candidates.extend(
            await _fetch_batch(
                client,
                topic_id=topic.topic_id,
                batch_origin="fallback_with_reviews",
                year_min=2000,
                citation_gt=0,
                sort="cited_by_count:desc",
                language_en=False,
                include_review=True,
                per_page=per_page,
            )
        )

    deduped: dict[str, dict[str, Any]] = {}
    for item in candidates:
        work = item.get("work")
        if not isinstance(work, dict):
            continue
        wid = str(work.get("id") or "")
        if not wid:
            continue
        previous = deduped.get(wid)
        if previous is None:
            deduped[wid] = item
        else:
            # keep the item with stronger batch priority
            keep_new = str(item.get("batch_origin", "")).startswith("strict") and not str(
                previous.get("batch_origin", "")
            ).startswith("strict")
            if keep_new:
                deduped[wid] = item

    scored: list[dict[str, Any]] = []
    for item in deduped.values():
        work = item["work"]
        score = _score(work)
        scored.append({**item, "selection_score": score})
    scored.sort(key=lambda x: float(x.get("selection_score") or 0.0), reverse=True)

    journal_count: dict[str, int] = {}
    author_count: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def can_take(work: dict[str, Any]) -> bool:
        jid = _journal_id(work)
        if jid and journal_count.get(jid, 0) >= 5:
            return False
        aid = _first_author_id(work)
        return not (aid and author_count.get(aid, 0) >= 2)

    def take(candidate: dict[str, Any]) -> None:
        work = candidate["work"]
        wid = str(work.get("id") or "")
        if not wid or wid in selected_ids:
            return
        selected.append(candidate)
        selected_ids.add(wid)
        jid = _journal_id(work)
        if jid:
            journal_count[jid] = journal_count.get(jid, 0) + 1
        aid = _first_author_id(work)
        if aid:
            author_count[aid] = author_count.get(aid, 0) + 1

    # Quota prefill: reviews + recent
    for candidate in scored:
        if len(selected) >= target:
            break
        if sum(1 for s in selected if _is_review(s["work"])) >= 3:
            break
        if _is_review(candidate["work"]) and can_take(candidate["work"]):
            take(candidate)

    for candidate in scored:
        if len(selected) >= target:
            break
        if sum(1 for s in selected if _is_recent(s["work"], 2018)) >= 25:
            break
        if _is_recent(candidate["work"], 2018) and can_take(candidate["work"]):
            take(candidate)

    # Main fill with diversity constraints.
    for candidate in scored:
        if len(selected) >= target:
            break
        if can_take(candidate["work"]):
            take(candidate)

    # If constraints were too strict, fill remaining purely by score.
    if len(selected) < target:
        for candidate in scored:
            if len(selected) >= target:
                break
            wid = str(candidate["work"].get("id") or "")
            if wid and wid not in selected_ids:
                take(candidate)

    selected_at = datetime.now(UTC).isoformat()
    out: list[SelectedTopicWork] = []
    for idx, candidate in enumerate(selected, start=1):
        work = candidate["work"]
        out.append(
            SelectedTopicWork(
                run_id=run_id,
                topic_id=topic.topic_id,
                topic_display_name=topic.display_name,
                topic_policy_block=topic.policy_block,
                topic_policy_subblock=topic.policy_subblock,
                source_file=topic.source_file,
                work_id=str(work.get("id") or ""),
                rank=idx,
                selection_score=float(candidate.get("selection_score") or 0.0),
                batch_origin=str(candidate.get("batch_origin") or ""),
                selected_at=selected_at,
                work=work,
            )
        )
    return out


async def select_all_topics(
    client: OpenAlexClient,
    *,
    topics: list[TopicEntry],
    run_id: str,
    target_per_topic: int,
    per_page: int,
) -> list[SelectedTopicWork]:
    """Select works for all topics sequentially.

    Sequential processing keeps rate-limit behaviour predictable and reproducible.
    """
    all_selected: list[SelectedTopicWork] = []
    for topic in topics:
        selected = await select_topic_works(
            client,
            topic=topic,
            run_id=run_id,
            target_per_topic=target_per_topic,
            per_page=per_page,
        )
        all_selected.extend(selected)
    return all_selected
