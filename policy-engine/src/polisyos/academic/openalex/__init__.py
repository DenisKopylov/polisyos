"""OpenAlex topic selection helpers for academic SKG ingestion."""

from polisyos.academic.openalex.client import OpenAlexClient, OpenAlexRequest
from polisyos.academic.openalex.priority_filter import should_process
from polisyos.academic.openalex.rate_limiter import OpenAlexRateLimiter
from polisyos.academic.openalex.selector import (
    SelectedTopicWork,
    select_all_topics,
    select_topic_works,
)
from polisyos.academic.openalex.topic_catalog import TopicEntry, discover_topic_files, load_topics

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
