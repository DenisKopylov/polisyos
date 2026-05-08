# Benchmark Authority

Related references: [Scientist](index.md), [Frontier runtime](frontier-runtime.md), [Agent capability promotion](agent-capability-promotion.md), [Deep research evidence](deep-research-evidence.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/methods/search/benchmark_registry.py`, `src/polisyos/scientist/evals/**`, `tests/unit/scientist/evals/**`, `tests/unit/scientist/search/test_benchmark_registry.py`, `tests/unit/scientist/search/test_phase_d4_runtime_integration.py`, `tests/unit/scientist/search/test_frontier_runtime.py`, and `tools/ci/check_scientist_benchmark_authority.py`

Phase 1.5 keeps `BenchmarkRegistry` as the persistence authority for benchmark
refs. The new `BenchmarkAuthority` is a policy facade over that registry: it
answers what benchmark evidence is required before a claim family, capability,
workflow artifact or baseline replacement can advance readiness.

## Split Taxonomy

| Split or visibility | Meaning | Public export rule |
| --- | --- | --- |
| `public` | Safe-to-document public benchmark fixtures and example packs. | May appear in public docs. |
| `private` | Internal evaluation packs not intended for public artifacts. | Export only aggregate status. |
| `selection` | Visible selection/evaluation split used while iterating. | Refs may be internal; public exports use presence booleans. |
| `hidden_holdout` | Hidden promotion holdout evidence. | Artifact ids must never appear in public exports. |
| `rotating_challenge` | Time-limited challenge packs that refresh on schedule. | Export only counts/status. |
| `sentinel` | Regression/safety sentinel packs. | Export only counts/status unless explicitly public. |
| `adversarial` | Stress and challenge artifacts for adversarial behavior. | Export only counts/status unless explicitly public. |

## Authority Verdict

`PromotionEvidenceRequest` identifies the promotion target:

- `family`;
- `claim_mode`: `proof_only`, `bounds`, or `estimation`;
- optional readiness, query, estimator, capability, workflow, run and loop
  scope;
- `risk_tier`: `low`, `medium`, or `high`;
- optional typed `benchmark_pack_ref`.

Free-form benchmark refs are rejected when registry lookup is required. The
request model accepts `ArtifactRef`, not raw strings. If
`registry_lookup_required=true` and a typed `benchmark_pack_ref` is supplied,
the ref must already resolve through `BenchmarkRegistry`; otherwise the verdict
adds `registered_benchmark_pack_ref` and fails closed.

`BenchmarkAuthorityVerdict` contains the resolved `FrontierBenchmarkBundle`,
`missing`, `stale`, `leakage_warnings`, `default_enable_allowed`, and a
rationale. Internal verdicts may contain hidden refs because governance and
promotion code need to inspect them. Public exports must call
`verdict.public_export()` or `export_public_benchmark_authority_verdict(...)`;
those exports summarize hidden holdouts without serializing hidden artifact ids.

## Leakage And Contamination

Hidden benchmark refs are treated as internal-only tokens. Public exporters run
redaction before final leakage checks, and contamination helpers detect hidden
artifact ids or hidden suite ids in public/exportable payloads. A public export
that still contains hidden benchmark ids fails rather than silently publishing a
leaky report.

## Eval Families

Phase 1.5 registers grader metadata only; it does not implement large graders or
live LLM grading.

| Family | Purpose |
| --- | --- |
| `factuality` | Domain-local source-grounded short factuality checks. |
| `browsing_deep_research` | Frozen-web multi-hop deep research tasks. |
| `citation_faithfulness` | Claim-to-snippet and quote accuracy. |
| `causal_readiness` | Supported causal query classes versus blockers. |
| `policy_design` | Pareto, constraints, welfare, equity and legal feasibility. |
| `governance` | False-pass, false-block and escalation quality. |
| `tool_use` | Tool selection, argument precision and error recovery. |
| `human_review` | Reviewer burden, override correctness and explanation quality. |

## Staleness

`BenchmarkStalenessPolicy` applies split-aware TTLs:

- `rotating_challenge`: 30 days;
- `adversarial`: 60 days;
- `sentinel`: 90 days;
- `hidden_holdout` and `private`: 120 days;
- `selection` and `public`: 180 days.

Entries are stale when their TTL is exceeded, `metadata.expires_at` is in the
past, or `metadata.revision_status` is `stale`, `retired`, or `revoked`.
Stale evidence blocks default enablement.

## Promotion Rules

- `proof_only` does not require benchmark evidence by default.
- `estimation` requires selection and hidden holdout evidence.
- Non-core families also require `rotating_challenge` evidence.
- `bounds` requires selection and sentinel evidence; non-core bounds also
  require hidden holdout and rotating challenge evidence.
- High-risk non-proof promotions require sentinel refs.
- Missing or stale evidence fails closed.
- Hidden holdout refs are internal only and must not be serialized into public
  decision artifacts.

## Integrations

- `AgentCapabilityPromotionReport` can require a `BenchmarkAuthorityVerdict`
  before default enablement.
- `FrontierRuntimeConfig` can require benchmark authority approval before
  baseline replacement.
- Existing `BenchmarkRegistry.require_promotion_evidence(...)` remains the
  registry-level evidence resolver.

## Validation

```bash
uv run pytest tests/unit/scientist/evals -q
uv run pytest tests/unit/scientist/search/test_benchmark_registry.py tests/unit/scientist/search/test_frontier_runtime.py -q
uv run pytest tests/unit/scientist/search/test_phase_d4_runtime_integration.py -q
uv run python tools/ci/check_scientist_benchmark_authority.py --require-passing
```
