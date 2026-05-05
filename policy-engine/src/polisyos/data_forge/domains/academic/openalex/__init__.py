"""OpenAlex topic selection helpers for academic SKG ingestion."""

from polisyos.data_forge.domains.academic.openalex.client import OpenAlexClient, OpenAlexRequest
from polisyos.data_forge.domains.academic.openalex.priority_filter import should_process
from polisyos.data_forge.domains.academic.openalex.rate_limiter import OpenAlexRateLimiter
from polisyos.data_forge.domains.academic.openalex.selector import (
    SelectedTopicWork,
    select_all_topics,
    select_topic_works,
)
from polisyos.data_forge.domains.academic.openalex.topic_catalog import (
    TopicEntry,
    discover_topic_files,
    load_topics,
)

__all__ = [
    "OpenAlexClient",
    "OpenAlexRateLimiter",
    "OpenAlexRequest",
    "SelectedTopicWork",
    "TopicEntry",
    "discover_topic_files",
    "load_topics",
    "select_all_topics",
    "select_topic_works",
    "should_process",
]
