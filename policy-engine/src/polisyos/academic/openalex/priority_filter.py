"""Priority filter for selecting policy-relevant OpenAlex works."""

from __future__ import annotations

TIER_1_KEYWORDS = {
    "economic policy",
    "fiscal policy",
    "tax policy",
    "public policy",
    "policy analysis",
    "policy evaluation",
    "governance",
    "corruption",
    "institutional quality",
    "state capacity",
    "social policy",
    "welfare state",
}

TIER_2_KEYWORDS = {
    "natural resources",
    "immigration",
    "legal reform",
    "labor market",
    "gender equality",
    "trade policy",
    "education policy",
    "health policy",
    "environmental policy",
    "agent-based model",
    "computational social science",
}


def should_process(
    work: dict,
    domain_filter: list[str] | None = None,
    min_citations: int = 10,
) -> tuple[bool, str]:
    """
    Returns (should_process, reason).
    reason: tier1 | tier2_domain_match | skip_irrelevant | skip_low_citation
    """

    topic_names = {
        str(topic.get("display_name") or "").lower().strip()
        for topic in work.get("topics", [])
        if isinstance(topic, dict)
    }
    cited_by_count = int(work.get("cited_by_count") or 0)

    if any(keyword in name for keyword in TIER_1_KEYWORDS for name in topic_names):
        if cited_by_count >= min_citations:
            return True, "tier1"
        return False, "skip_low_citation"

    if domain_filter:
        domain_lower = [d.lower() for d in domain_filter]
        if any(
            keyword in name and any(domain in name for domain in domain_lower)
            for keyword in TIER_2_KEYWORDS
            for name in topic_names
        ):
            if cited_by_count >= max(5, min_citations // 2):
                return True, "tier2_domain_match"

    return False, "skip_irrelevant"


__all__ = ["TIER_1_KEYWORDS", "TIER_2_KEYWORDS", "should_process"]
