# ADR-0124: LLM Idempotency and Prompt Versioning

## Status
Proposed

## Date
2026-04-18

## Context

Data Forge and Lex already call LLMs for claim extraction, structuring, and
screening. Current failure modes seen in benchmarks:

- Retry-storms silently re-bill the same semantic call because cache keys miss
  the model temperature or schema version.
- Prompt edits ship without a pinned version, so historical artifacts cannot
  be reproduced.
- Failed calls land as `ValueError` deep inside pipelines instead of in a DLQ
  with replay metadata.
- Two calls differing only by whitespace in the prompt pay twice.

SOTA: every LLM call must be deterministic, versioned, idempotent, replayable,
and costable.

## Decision

1. Every LLM call goes through `polisyos.data_forge.kernel.llm.call(...)`.
2. The cache key is a canonical hash over:
   - `messages` (canonicalised: JSON-normalized, whitespace-trimmed),
   - `model_id`,
   - `temperature`, `top_p`, `seed`,
   - `response_schema_id`, `response_schema_version`,
   - `prompt_id`, `prompt_version`,
   - `provider`, `provider_api_version`.
3. Prompts are addressable objects in `data_forge/prompts/<prompt_id>.v<N>.md`
   with front-matter `{prompt_id, version, owner, model_family, last_reviewed}`.
4. Responses are persisted with provenance: request hash, response hash,
   tokens, cost, `trace_id`, and the prompt + schema pair used.
5. Failures route to a structured DLQ (`runs/<run_id>/llm_dlq/*.jsonl`) with
   original request hash, category (`timeout | schema_violation | quota |
   upstream_5xx | other`), attempt count, and last error.
6. Replays read from DLQ; semantic reruns require a new `prompt_version` or
   a new `provider_api_version`.
7. Schema-constrained responses must pass JSON Schema validation against the
   registered schema (ADR-0114) before entering cache.

## Consequences

- Cache hit rate becomes measurable (SLO `llm_cache_hit_rate > 0.6`).
- Reproducibility of historical artifacts is guaranteed at the prompt layer.
- Prompt edits become an explicit governance event.
- DLQ gives operators a queryable backlog instead of lost runs.

## Related Decisions

- Extends: ADR-0032 (LLM as context interpreter), ADR-0035 (two-step screening
  Haiku-Sonnet).
- Depends on: ADR-0114 (schema registry), ADR-0116 (OTel observability),
  ADR-0123 (ArtifactRef governance).
- Related: ADR-0097 (runtime rate limiting and idempotency).
