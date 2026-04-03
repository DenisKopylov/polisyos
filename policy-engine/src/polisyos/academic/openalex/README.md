# Academic OpenAlex (`polisyos.academic.openalex`)

`polisyos.academic.openalex` is the OpenAlex integration layer used by the academic batch pipeline.
It handles topic catalog loading, retry-safe work retrieval, topic selection, and the lightweight
policy filter that decides whether a work should be processed.

## Role in System

- **Depends on:** `AcademicBatchConfig` and the local topic catalog files.
- **Used by:** `topic_select` and `resolve_extract` inside `polisyos.academic.batch`.
- **Boundary function:** keeps OpenAlex-specific HTTP and selection logic away from the main pipeline.

## Key Concepts

- **Topic catalog** - `topic_catalog.py` parses `relevant_topics_*.csv` into `TopicEntry` objects.
- **Async client** - `client.py` handles OpenAlex `/works` requests with retries.
- **Rate limiting** - `rate_limiter.py` keeps requests within safe concurrency and RPS bounds.
- **Selection** - `selector.py` implements topic-based candidate ranking and diversification.
- **Priority filter** - `priority_filter.py` screens works before expensive extraction.

## Public API

- `OpenAlexClient`
- `OpenAlexRequest`
- `OpenAlexRateLimiter`
- `SelectedTopicWork`
- `TopicEntry`
- `discover_topic_files`
- `load_topics`
- `select_all_topics`
- `select_topic_works`
- `should_process`

## Current State

- Last updated: 2026-04-03
- The package continues to export the same topic-selection facade, with the OpenAlex client and rate limiter remaining the key runtime pieces.
- `priority_filter.py` is still used as an early cutoff before batch extraction work begins.
