# PAG and lagged-pair identity: bounded contract decision packet

**Disposition:** no validator-key change is justified from the current contract. Preserve the existing `GraphType.PAG` one-adjacency-per-unordered-node-pair rule. A graph that combines a positive-lag edge and a contemporaneous edge for the same named pair needs an explicit temporal-PAG contract and consumers; that semantic choice is not established by the current IR, a Core artifact tag, or the Y0 candidate. Keep the static consumer's typed unsupported result. This is a research packet only: no source or test files were changed and no tests or product imports were run.

## Binding and question

Read-only source review used worktree `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`, HEAD `3e73f32f71e5fd15c538000a482da1b718a1737c`, tree `8843c2d3eab9d6fb9423d537c49f8c99390a458a`. Several source and test files are already dirty in this shared candidate. The hashes below pin the bytes read, not clean or committed paths. This note does not attribute or alter the existing work.

The branch later advanced to HEAD `af1f92c82be5ee8e268945b0ce6c77dac9086b8c`, tree `605f3cb26579373e5d2e08e46db69923c55b874c`; a readback confirmed the six primary IR/producer/static-consumer source hashes below were unchanged. The review remains bound to the captured bytes, not to a new source claim for that later commit.

| Current worktree file | SHA-256 |
| --- | --- |
| `src/polisyos/ir/analytics/causal_graph.py` | `270b6bdc2665256c4a28bc41a0597e19bee7c18dd14bbc434bfcf9091dad5f8a` |
| `tests/unit/ir/test_causal_graph_contract.py` | `832a932bf6f3d5164fc08a7fbfef3ae2c3b80a860a09ff15e921a21188fece8f` |
| `src/polisyos/ir/analytics/temporal_frontier.py` | `205221fd91b31775261e810e408ff827fede4532e56c85f128d32e4a5c45f391` |
| `src/polisyos/foundry/methods/catalog/causal/discovery_pipeline.py` | `dc8e5abd7bec042644cea99d8dbd7d9ddaddab91fc76b07a3c3b1671b65c9f87` |
| `src/polisyos/foundry/methods/catalog/causal/admg_ops.py` | `0f3ee0c59df8423c074432faf705ff46e45e30716277c5b15ba34e3e335c1542` |
| `src/polisyos/foundry/methods/catalog/causal/id_engine/core.py` | `54a919c33f3b0ba0720116d587590da5d86fa487f09a6c4d681bbc0cf84c6cef` |
| `src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py` | `20d053be981aab1270fd984d3810f73b7c5db91000c45d68ede39e2656b0f372` |
| `src/polisyos/ir/analytics/ecosystem_bridges.py` | `93acff425e799455563396c0164552f0cf272c69a3efc97753527066f34897ea` |
| `src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py` | `64604fe454e5c784212ac0928a4d7207f5c4946744a50ccdb6147d8b29c6a430` |
| `docs/plans/active/agent-packages/PolicyOS_E02R2/Y0_LAG_TASK.md` | `76e189b46db74967652e491f2560f459b7c1df8c23b8d430503423156230886d` |

The assigned original claim is B214, whose exact source block is `B_r19_original.md:5218–5229` (criterion-block SHA-256 `48c1311f230c5c8f4886013cf47fec75931cde810c20feee8889c9d820dcb1ad`; current source blob `d800082eebfc12eaf647b0c0257c4f06e135d25a`). It concerns a PAG/CPDAG projection reversing a known direction and creating a cycle. It does **not** specify temporal-PAG or same-pair multi-lag semantics. The current S1 entry records B214 as `partial / closed_bounded / not_adjudicated` and bounds supported work to existing DAG/ADMG behavior, typed limitations, and no claim of sound identification over every PAG completion (`LOCAL/s1-law-intakes/decision.md:33,82`).

## What the current contract says

`CausalEdge.lag` is an optional nonnegative integer (`causal_graph.py:148–152`). `CausalGraphModel` is the typed IR object, with `schema_version="1.0"` and `graph_type` (`:238–250`). For `GraphType.PAG`, validation calls `_ensure_pag_unique_adjacencies` (`:279–280`); `_pag_duplicate_adjacencies` keys only by sorted `(src,dst)`, independent of marks, lag, or metadata (`:309–329`). Thus the present IR rule refuses any second row for the same unordered named pair, including a row at a different lag. `model_copy` also rechecks this invariant (`:342–355` in the current file). The new test `lag-does-not-hide-pair-collision` covers two positive-lag directed rows (lag 1 and lag 2, stored in reverse directions); it does **not** exercise the Y0 candidate's mixed case `X→Y@lag=1` plus `X↔Y@lag=None`.

This is an IR rule, not a Core-only tag convention. `persist_causal_graph_model` writes `graph.model_dump()` as kind/schema `ir.causal_graph_model`/`1.0`, and `load_causal_graph_model` reconstructs and validates the typed model (`:567–594`). The current fresh-reader negative stores a raw duplicate payload and expects the typed loader to refuse it (`test_causal_graph_contract.py::test_causal_graph_pag_artifact_reader_refuses_persisted_duplicate_adjacencies`). No metadata tag or artifact kind changes the endpoint-keyed PAG rule.

The contract does **not** currently reject one positive-lag edge merely because its graph type is PAG. That makes the boundary narrower than “PAG is always contemporaneous”: a single lagged PAG row can be represented, but the static inference consumer refuses it. The important distinction is between (a) the enforced duplicate-row law, and (b) the unadjudicated meaning of a lag-bearing PAG. A Core tag, `discovery_method`, or `metadata` string cannot settle (b).

## Producer, consumer, and identity paths

- The current discovery producer already separates these roles. `_build_consensus_pag` documents and implements Phase 0: for `pcmci+`, positive-lag rows leave the consensus input and enter `temporal_edges`; lag `None`/0 rows go into the consensus graph (`discovery_pipeline.py:380–435`). The pipeline builds a separate `GraphType.DAG` `temporal_dag` from those lag rows and returns it beside `unified_pag` (`:1390–1442`). The existing `test_temporal_edges_segregated_from_pag` covers two lagged edges on separate pairs, not a contemporaneous-plus-lagged collision on one pair (`test_pag_completion.py:281–324`).
- The IR has a second, explicit temporal carrier: `TemporalDiscoveryFrontierReport` keeps `unified_graph` separate from `TemporalDiscoveryEdge` rows and keys those rows by `(src,dst,lag,source_method)` (`temporal_frontier.py:55–68,151–176`). That is evidence for a temporal report carrier, not a temporal PAG equivalence law.
- PAG operations remain endpoint-based. `extract_unshielded_triples` builds unordered adjacency from `(src,dst)` only; `apply_pag_orientation_rules` stores one edge under `(src,dst)`; both it and `validate_pag` defensively reject duplicate pairs before operating (`pag_completion.py:32–61,217–250,379–408`). Merely changing admission to key by lag would leave these consumers unable to distinguish two relations for one pair.
- Static causal inference has a shared refusal. `CachedAdjacency` raises `UnsupportedStaticADMGProfileError` for `edge.lag not in (None,0)` before building static endpoint sets (`admg_ops.py:61–80,128–141`). `id_algorithm` calls that guard before its PAG branch (`id_engine/core.py:554–580`); high-level `CausalEngine.identify` maps that typed exception to `ORACLE_NEEDED` with `limitation_code` `unsupported_static_admg_profile` (`causal_engine/identification.py:2414–2428`). That is a limitation, not an identified effect.
- The optional Y0 adapter itself creates a mixed graph from endpoint marks and does not pass lag (`id_engine/core.py:2025–2059`). However, `id_with_oracle_fallback` calls `id_algorithm` before Y0 (`:1322–1362`), and the typed static guard raises before it can produce a fallback result. The public path therefore does not demonstrate Y0 handling of a lagged PAG. The Y0 task calls its distinction prediction `UNRUN`/`not_established`, records no in-repository `oracle="y0"` selection, and requires a real public-path witness before any effect claim (`Y0_LAG_TASK.md:1–26`).
- Existing identity/export affordances are not uniform. `to_networkx` includes marks and lag in its multiedge key (`causal_graph.py:404–438`); `to_rustworkx` carries lag in each edge payload (`:388–402`); DOT includes a lag attribute but warns static backends may ignore it (`:362–385`). The IR→Tigramite bridge preserves directed lags, but maps `None` to 0 (`ecosystem_bridges.py:72–90,180–197`). CausalNex/pgmpy endpoint projections omit lag (`:93–178`). Kuzu row serialization includes lag, but `to_kuzu` merges relationships by endpoint pair before setting attributes (`causal_graph.py:454–500`), so it is not proof of same-pair multi-lag storage. Existing B219/B220 work addresses multiedge/export and immutable snapshot identity; do not treat it as PAG semantics.

A whole-source locator scan found `.lag` or `lag=` in 53 of 2,749 `src/polisyos/**/*.py` files. That lexical set is not a semantic caller census; the traced owners above are the paths relevant to this question. Any approved temporal-PAG scope must widen to the full set of real producers, static gates, exporters, and consumers, not stop at this test or the current model validator.

## Contract choice and P40 bucket

**P40: same class, one level deeper.** The existing issue is duplicate unordered PAG adjacency admission. The new input varies lag as well as marks; it asks whether the same pair-key invariant should treat lag as a second adjacency dimension. Do not add a one-off “different lags are okay” exception. The current static PAG implementation has one endpoint-keyed relation and its orientation consumers use that identity. A key change by itself is not a coherent temporal-PAG implementation.

Two scopes remain defensible, and the source does not choose between them:

| Scope | Contract and status effect | Migration / required companions |
| --- | --- | --- |
| Keep PAG static; keep temporal edges separate (recommended for current behavior) | One unordered node pair is one PAG adjacency; lag is not a duplicate bypass. Positive-lag relation facts use the existing temporal edge/`temporal_dag` carriers. Static causal consumers retain typed unsupported/limited outcomes until a temporal resolver is selected. | Preserve current `ir.causal_graph_model` 1.0 reader behavior. If G wants strict conformance, decide whether to reject all positive lags on a PAG or retain the current representational tolerance with mandatory downstream refusal. Historical 1.0 rows must not silently acquire new temporal meaning. Verify producer segregation and persisted limitation end to end. |
| Add temporal-PAG support | Define whether lag denotes a separate relation on the same variable nodes or time-indexed vertices, and define its equivalence-class/orientation law. Use a new explicit, versioned IR profile/type rather than changing static `GraphType.PAG` identity by implication. | Add producer/bridge, schema and compatibility rules, profile-aware PAG operations, temporal-aware identification or explicit typed refusal, and full-identity persistence/export. Old 1.0 artifacts remain under current semantics; no default upgrade from tag/metadata. This is a G choice. |

Do **not** adopt the tempting local fix “include `lag` in `_pag_duplicate_adjacencies`.” It would make the exact mixed-lag input pass IR admission while endpoint-based orientation maps overwrite/collapse it, static ADMG gates still reject it, some bridge projections drop lag, and Kuzu is endpoint-merged. Nor should Core artifact-family tags be treated as a substitute for a temporal relation law. A new versioned profile has migration and consumer consequences; no such version or temporal-PAG law is currently admitted.

This packet does not close B214, B218, B219, or B220. B214 remains the separate projection/all-completions boundary. B218's original criterion covers lag/self-lag representation/export and static refusal; `method-decisions.md:F-M9` recommends bounded closure only for that specific representation/export/refusal scope and leaves temporal readiness limited. B219 is graph multiedge export; B220 is topology/cache immutability. Do not infer a broader result from any of them.

## Smallest falsifier for the next frozen wave

The current test name is a marker of pair collision, not proof that a temporal-PAG profile exists. After source freeze, run these existing focused controls and add the exact mixed candidate to the same contract fixture (without changing the expected refusal before G chooses otherwise):

1. `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_model_validate_refuses_duplicate_pag_unordered_adjacencies` with `X→Y@lag=1` plus `X↔Y@lag=None`; reverse insertion order and endpoint storage. Preserve the valid one-edge PAG, valid ADMG bow, and valid reciprocal-lag DAG controls.
2. `tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_pag_artifact_reader_refuses_persisted_duplicate_adjacencies` and `::test_causal_graph_networkx_preserves_mixed_edge_identity`. The second currently tests ADMG; it does not authorize a PAG multirelation. If temporal support is selected, add a true producer→CAS→fresh-reader round trip asserting full `(src,dst,marks,lag,source/profile)` identity and order-independent result.
3. `tests/unit/foundry/methods/catalog/causal/test_pag_completion.py::test_temporal_edges_segregated_from_pag` plus `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py::test_static_profile_refuses_original_graph_before_surgery_rewrite_or_noop` for positive lag. Keep a direct `id_algorithm` and high-level `CausalEngine.identify` negative: typed unsupported/limited, never `IDENTIFIED`; do not count a Y0 label as a run.
4. If a temporal-PAG profile is proposed, rerun each actual exporter/consumer above with the exact same-pair/multiple-lag input. Remove only the relation-identity check while retaining graph type, lag markers, and producer labels; the persisted/served identity or consumer status must then change. A generic `MultiDiGraph` round trip alone is insufficient.

No test execution, Y0 runtime, production caller census, or scientific identification effect was measured here. The smallest missing capability for a positive temporal-PAG claim is an admitted versioned relation law plus a producer-to-fresh-consumer path that recomputes it; the current temporal report/DAG carrier does not supply a temporal PAG equivalence-class consumer. Until that exists, temporal-PAG support is `absent/unallocated`; the existing static inference boundary is `limited/typed unsupported` for positive lag.

## Pattern pass

- **P31/P32:** preserve the IR owner and actual typed validation; do not infer semantics from Core tags, metadata, or a serialized shape.
- **P38:** the guarded property is uniqueness of a static PAG adjacency; the implementation keys only unordered named endpoints. The divergent case is a genuinely time-indexed relation family with the same names at different lags. No admitted temporal-PAG consumer resolves that divergence today.
- **P40:** same collision class, deeper in the lag dimension; widen via a versioned temporal contract or record this bounded limitation, not a per-lag exception.
- **Capability labels:** static compact-lag rejection exists in the consumer. A temporal report and temporal-DAG representation exist. A temporal-PAG producer→artifact profile→bridge→consumer→verification chain is `absent/unallocated`; no semantic test can promote it.

