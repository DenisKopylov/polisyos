# IR PAG lag boundary: executable producer/CAS falsifier

**Disposition:** preserve the current PAG one-adjacency-per-unordered-pair guard and the existing temporal/static split. This packet proposes only two test additions; it does not establish a temporal-PAG law or change any source contract. The exact mixed-lag IR input remains a typed validation refusal. A real PCMCI+PC producer run should keep same-endpoint relations in the separate `temporal_dag` and `unified_pag` fields, persist the report through the existing method/CAS route, and retain static identification's typed refusal on the lagged graph.

## Binding and immutable prior decision

The worktree is `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`, HEAD `8c37b74e68fdbafeca83bf77573fb8c565fbc7a9`, tree `2c6c1215b7ca94c789838bd6c29abfc7fba03b68`. The preceding decision `LOCAL/decisions/pag-lag-pair-identity-contract-choice-20261011.md` is unchanged at SHA-256 `c1c87b1d6bea3860ceda91b4599af9c5436215c7f347f16ac7c0168cecdccad1`.

The virtual test patch is `LOCAL/raw/ir-pag-lag-controls-20261011/ir-pag-lag-controls-20261011.patch`, SHA-256 `09c9edc0e91f89cea2f4dbcbe3be169d33b67c83734c2651056863d7cc64a8be`, 5,120 bytes. It touches two test files and no product sources:

| Test file | Current preimage SHA-256 | Proposed postimage SHA-256 |
| --- | --- | --- |
| `tests/unit/ir/test_causal_graph_contract.py` | `832a932bf6f3d5164fc08a7fbfef3ae2c3b80a860a09ff15e921a21188fece8f` | `ef692a674e5a934674e8d980975d79368c8a90a8a947e9fa3f0cf3022320d360` |
| `tests/unit/foundry/methods/catalog/causal/test_discovery_reconciliation_limitations.py` | `fe825595f5e6cdceaafe2bd86a4fc5ec54fb432a025d2ba63bb4c2a93aaf46fd` | `6b9ff8b8fa2293e40b312c0e18525449cea71b9bceb91975dd07cb0e988424de` |

The first file is already dirty in this shared worktree; its patch preimage includes that exact current content. Apply only against the pinned preimages or regenerate against the post-freeze test bytes. `git apply --check` accepted the virtual patch against this snapshot. No product import or test was run.

## Why these are the right falsifiers

`CausalGraphModel` invokes `_ensure_pag_unique_adjacencies` for `GraphType.PAG` (`src/polisyos/ir/analytics/causal_graph.py:279–280`). Its duplicate key is the unordered `(src, dst)` pair, independent of endpoint marks and `lag` (`:309–329`). The existing parameter `lag-does-not-hide-pair-collision` uses two positive-lag rows; it does not cover the Y0-shaped input `X→Y@lag=1` plus `X↔Y@lag=None`. The patch adds that exact mixed case in both insertion/storage directions and keeps the same validation refusal.

The existing producer already provides a real separation path. `UnifiedCausalDiscovery` dispatches PCMCI+ for time-series data and passes other requested algorithms through their actual discovery runners (`src/polisyos/foundry/methods/catalog/causal/discovery_pipeline.py:216–273`). `_build_consensus_pag` moves positive-lag PCMCI+ edges out of consensus and keeps `None`/0 edges in the contemporaneous input (`:409–435`); the report builder stores the positive-lag rows as a `GraphType.DAG` `temporal_dag` beside `unified_pag` (`:1390–1444`). The added integration test forces actual `pcmci,pc` runs on the deterministic VAR(1) fixture, so the same X/Y pair must be evidenced by the PCMCI lag edge and the PC contemporaneous edge before asserting their distinct report fields. It persists through `run_job` and reads the result using a new `FileSystemCAS` instance and `DiscoveryPipelineReport.model_validate`, matching the existing test module's real method/CAS pattern.

The same fresh report's temporal DAG is sent to the actual low-level `id_algorithm`. `CachedAdjacency` rejects any `lag` outside `(None, 0)` before it builds static adjacency (`src/polisyos/foundry/methods/catalog/causal/admg_ops.py:61–77`); the test requires `UnsupportedStaticADMGProfileError`, never an identified result. This is an executable check that the pipeline's temporal carrier does not silently enter a static inference consumer.

The integration witness is dependency-gated with `pytest.importorskip("tigramite")`; it uses `ci_backend="numpy"` and no bootstrap draws. If Tigramite is absent, that witness is `SKIPPED`/unrun in that environment, not a producer-to-CAS closure. The direct IR negative remains runnable without that optional dependency. Do not replace either real algorithm with a hand-built `CausalDiscoveryReport`, marker metadata, or a mocked `_build_consensus_pag`.

## Exact focused execution after source freeze

```text
.venv/bin/python -m pytest -q tests/unit/ir/test_causal_graph_contract.py::test_causal_graph_model_validate_refuses_duplicate_pag_unordered_adjacencies tests/unit/foundry/methods/catalog/causal/test_discovery_reconciliation_limitations.py::test_temporal_and_static_same_pair_are_separated_in_persisted_discovery_report
```

Retain the actual run output. The positive producer test must show both algorithm outputs contain the same pair with their respective lag semantics, the persisted reader retains a static pair only in `unified_pag` and a positive-lag pair in `temporal_dag`, and static ID refuses the latter. If the PC contemporaneous pair or PCMCI lag-1 edge is absent, treat the test as a failed witness and adjust the deterministic fixture—not the assertions or production law.

## Contract choice, P40, and boundaries

**P40: same class, deeper dimension.** The collision question is still whether a PAG may hold multiple relations for the same unordered named pair; lag is the additional identity dimension. No per-lag exception is proposed. The current code already has the producer separation and static refusal; the test patch makes their end-to-end boundary falsifiable.

The source supports a temporal edge/report carrier and a static PAG identity. It does not define how PAG equivalence, orientation rules, exports, or identification should treat a time-indexed relation family on repeated variable names. A temporal-PAG schema/profile and its consumers remain `absent/unallocated`; positive temporal edges entering static inference remain `limited/typed unsupported`. If G chooses to support temporal-PAG later, that needs an explicit versioned relation law and profile-aware consumer/export path; changing `_pag_duplicate_adjacencies` to include `lag` is still insufficient.

This is distinct from B214's projection/all-completions criterion. It adds no B214 closure claim and does not adjudicate Y0. A Core artifact tag, metadata string, or test fixture cannot create temporal-PAG authority. Keep the earlier decision packet immutable and use this test-only proposal as its executable follow-up.

## Pattern pass

- **P31/P32/P38:** keep one IR admission rule, then test exact mixed input; a marker or data-source label cannot distinguish a temporal relation from a static adjacency.
- **P29/P33:** execute actual PCMCI and PC producers through the real method result/CAS reader; do not build reports by hand or turn a skipped optional backend into a pass.
- **P40:** classify as the same pair-identity class; retain the static key, widen the falsifier to mixed lag/marks and the producer-consumer quantity.
- **Capability:** producer segregation and typed static refusal exist in source; the proposed semantic integration test is `verification_missing` until executed. Temporal-PAG profile/consumer support is `absent/unallocated`.
