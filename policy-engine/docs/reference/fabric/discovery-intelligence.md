# Fabric Discovery And Entity Intelligence

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `c35222b3dcf103338175cf300c5fe9487e6416f3`
Source of truth: `src/polisyos/fabric/catalog/discovery.py`, `src/polisyos/fabric/entity_resolution/`, `src/polisyos/fabric/world/query.py`, `src/polisyos/fabric/world/materialize/kuzu.py`, `tools/quality/validation/fabric_discovery_intelligence.py`, `tests/_data/fabric/discovery_eval.json`, `tests/unit/fabric/test_discovery_intelligence.py`, and `tests/unit/fabric/test_entity_resolution.py`
Evidence level: implementation and named test behavior inspected at the source pin. Tests were not run in this documentation pass; offline ranking and graph-helper behavior do not establish live-source readiness or a source-to-world workflow.
Test status: cited tests were inspected but not run in this documentation pass.

Related plan evidence path: `docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md`.
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md).
Inventory scope: code counts reflect statically resolved source declarations;
they do not prove runtime or deployment readiness. Dynamic or unresolved
declarations remain partial/unknown rather than being silently treated as absent.

Phase 9 keeps discovery explainable, reversible, stale-aware, and contract-bound.
The implementation is offline-first: no LLM calls are made by the validator or
tests. Future LLM/embedding providers can plug in behind the same evidence
contract after separate review.

## Semantic Catalog

`SemanticDatasetCatalog` builds one catalog document per production
`SourceContract` v2 record. Each ranked candidate carries:

| Evidence | Source |
| -------- | ------ |
| Source contract id/version | `SourceContract.id`, `SourceContract.version` |
| Profile id/status | `SourceProfileRegistry` |
| Quality contract | `SourceContract.quality.contract_ref` |
| Access state | `SourceContract.security.classification`, `pii_tier` |
| Source trust | `SourceContract.source_trust` |
| Owner/reviewer | `SourceContract.owner`, `reviewer` |
| Vector fingerprint | canonical source contract plus profile payload |

The default embedding model is `hashing-bow-dataset-v1`, a deterministic local
vectorizer. Search combines offline vector rank, token coverage, and lexical
fallback, and every plan records `llm_calls=0`.

The candidate's trust, access, quality, and owner fields are copied from the
declared source contract and profile; discovery does not independently verify
the upstream content. A `DatasetResolutionPlan` also has no automatic fetch and
world-materialization consumer at this source pin, so that handoff is
`bridge_missing` and the full discovery-to-source-to-world semantic chain is
`semantic_test_missing`. See the [data-plane reference](data-plane.md) for the
separate connector and world-store paths.

## Stale Invalidation

Catalog vectors are fingerprinted from source contract, schema/metadata,
quality/access/trust fields, and profile payload. `refresh()` returns invalidated
source-contract ids when any of those inputs change. Operators can also mark an
entry stale; stale entries are filtered by default and only returned when a
caller explicitly sets `allow_stale=True`, in which case the candidate evidence
is labelled stale with reasons.

## Dataset Resolution

Natural-language resolution returns a `DatasetResolutionPlan` with ranked
`DatasetDiscoveryCandidate` rows. Plans expose route, score breakdown,
supporting tokens, stale-filter counts, and the evidence block above. This is
the contract future AI-assisted discovery must preserve.

## Entity Resolution

`ProbabilisticEntityResolver` emits explainable candidate matches with name,
identifier, and attribute evidence. `EntityMatchStore` persists candidates and
append-only override envelopes. Accepted overrides require actor, reason,
provenance, and merge-governance evidence; they do not overwrite canonical world
facts.

## Graph Reasoning

Fabric world graph helpers answer the Phase 9 questions in memory and through
Kuzu traversal helpers:

| Question | Helper |
| -------- | ------ |
| Origin | `query_world_origin_trace()`, `query_world_kuzu_origin_trace()` |
| Source overlap | `query_world_source_overlap()`, `query_world_kuzu_source_overlap()` |
| Conflict neighborhood | `query_world_conflict_neighborhood()`, `query_world_kuzu_conflict_neighborhood()` |
| Downstream impact | `query_world_policy_impact()`, `query_world_kuzu_policy_impact()` |
| Entity neighborhood | `query_world_entity_neighborhood()`, `query_world_kuzu_entity_neighborhood()` |

## Evaluation

The relevance and false-positive pack lives at
`tests/_data/fabric/discovery_eval.json`. It covers dataset relevance and a
negative query that should not produce an overconfident source match.

Validation:

```bash
uv run python tools/quality/validation/fabric_discovery_intelligence.py --check
uv run pytest tests/unit/fabric/test_discovery_intelligence.py tests/unit/fabric/test_entity_resolution.py -q
```
