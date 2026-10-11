# Independent review: IR lag/PAG temporal-segregation test proposal

**Verdict: GO as a narrowly scoped test-only companion; LIMIT as evidence for B218–B220.** The patch is well bounded and exercises real report production, persistence, reload, and static-consumer refusal. It does not establish a temporal-PAG law, and it does not complete the three original criteria. Execution remains UNRUN in this review.

## Binding and reviewed surface

- Product checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`.
- Current shared checkout: HEAD `fd5feb3714fe0395157940027259fe10180db4e0`, tree `5cde4060cd0cf9f13033a9b54ab460adeaf46a26`. The proposal note records an earlier HEAD (`8c37b74e…`, tree `2c6c1215…`); treat that note as a prior snapshot. Both target-test preimages still match its recorded SHA-256 values.
- Virtual patch: `LOCAL/raw/ir-pag-lag-controls-20261011/ir-pag-lag-controls-20261011.patch`, SHA-256 `09c9edc0e91f89cea2f4dbcbe3be169d33b67c83734c2651056863d7cc64a8be`.
- Proposal note: `LOCAL/decisions/ir-pag-lag-temporal-segregation-falsifier-20261011.md`, SHA-256 `a70bb2e23f08f8c4c38f2b4cf383d4e5e66cceead6f9d7b8dcf0b7d4b8176fff`.
- `git apply --check <patch>` from the product root exited 0. The patch changes only these two test files; no source, schema, or public law is added:

| Test path | Current preimage SHA-256 | Proposed postimage SHA-256 |
| --- | --- | --- |
| `tests/unit/ir/test_causal_graph_contract.py` | `832a932bf6f3d5164fc08a7fbfef3ae2c3b80a860a09ff15e921a21188fece8f` | `ef692a674e5a934674e8d980975d79368c8a90a8a947e9fa3f0cf3022320d360` |
| `tests/unit/foundry/methods/catalog/causal/test_discovery_reconciliation_limitations.py` | `fe825595f5e6cdceaafe2bd86a4fc5ec54fb432a025d2ba63bb4c2a93aaf46fd` | `6b9ff8b8fa2293e40b312c0e18525449cea71b9bceb91975dd07cb0e988424de` |

The first file has unrelated shared-worktree dirt; the exact preimage above is the one accepted by the patch check. `src/polisyos/ir/analytics/causal_graph.py` also has an uncommitted 27-line addition implementing the duplicate-PAG guard (current file SHA-256 `270b6bdc2665256c4a28bc41a0597e19bee7c18dd14bbc434bfcf9091dad5f8a`). That source change is not part of this patch. The pair-collision test depends on that guard being included in the composed candidate; the test patch alone is not a fix.

No tests, imports, lints, or numerical executions were run.

## Property and test quality

The first test addition extends the existing PAG duplicate-adjacency validation parameterization with both storage orders for a lag-1 directed row and a contemporaneous bidirected row on the same unordered pair. This is a meaningful remove-the-lag-dimension falsifier for the current source rule: `CausalGraphModel._pag_duplicate_adjacencies()` keys only on the unordered endpoint pair (`src/polisyos/ir/analytics/causal_graph.py:309–329`), and `_validate_graph()` invokes it for PAGs (`:279–280`). It tests preservation of the current one-adjacency-per-pair contract; it does not argue that a time-indexed PAG should or should not permit parallel lagged relations.

The integration addition is more than a marker test. It builds a seeded VAR(1) input, writes the input to CAS, calls actual `run_job` for `UnifiedCausalDiscovery` with PCMCI and PC, reloads the result through a new `FileSystemCAS`/IR artifact reader, validates `DiscoveryPipelineReport`, checks the actual PCMCI lag-1 and PC pair outputs, checks the split report fields, then sends the temporal DAG to actual `id_algorithm`. The latter reaches `_validate_static_admg()` and the `CachedAdjacency` lag guard (`src/polisyos/foundry/methods/catalog/causal/id_engine/core.py:579` and `src/polisyos/foundry/methods/catalog/causal/admg_ops.py:61–77`), which raises `UnsupportedStaticADMGProfileError`. This is a useful producer → persisted report → fresh reader → static consumer witness if it passes.

There is one fixture-interpretation limit: the supplied VAR equation makes `Y[t]` depend on `X[t-1]` and `Y[t-1]`, but contains no contemporaneous `X[t]` effect. The PC runner receives the rows as tabular observations while the observations are autocorrelated. Therefore its X/Y adjacency is an observed PC output for the report-path check, not evidence of a true contemporaneous causal relation. Keep this test described as a structural routing/report witness. If the test is meant to assert that both relations are present in the generating process, amend the DGP to include a declared same-time effect while retaining the lagged effect; do not infer a zero-lag causal law from the PC edge alone.

The integration witness is correctly gated by `pytest.importorskip("tigramite")`; the configured PC conditional-independence backend is `numpy`. A skip is not a pass, and this review has no selected environment or execution receipt. The exact focused selector proposed in the decision note should be run only after the composed source/test snapshot is frozen.

## Original-criterion boundary

The pinned source is `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md`:

- **B218**, lines 5361–5374, source SHA-256 `8ce1868ddb2663580547f475288d03502e03ae6a4bc38923313bc069efb0a40a`: requires lag-1/lag-2 round-trip and causal-time preservation, unchanged known-static-DAG behavior, and temporal self-lag versus ordinary static self-loop refusal. This proposal witnesses a lag-1 report split and typed static refusal only. It does not cover lag-2 export/round-trip, `to_dot`/other exports, static-DAG unchanged controls, or the self-lag/static-self-loop pair. B218 therefore remains partial/unverified.
- **B219**, lines 5375–5388, source SHA-256 `c3c2613bd397c8dd5d252ccb15562a6aa2f4bee46e36fa86eff1b12bf7c30009`: concerns the named `CausalGraphModel.to_networkx` conversion, mixed/lagged parallel-edge retention, and order-independent round-trip on the actual exporter. The proposal never calls that exporter and does not cover its backend. No B219 evidence is added.
- **B220**, lines 5389–5402, source SHA-256 `d0c39288b089bc7e1a85c4eec40ffd1c4fa3273293734b758729b4bb7dc54b71`: concerns deep topology immutability, mutation refusal, copy/update after warmed derived properties, serialization/ancestor/export agreement, and old cache-entry cleanup. Neither new test exercises these behaviors. No B220 evidence is added.

Source already separates PCMCI positive-lag edges from contemporaneous input to the consensus builder (`src/polisyos/foundry/methods/catalog/causal/discovery_pipeline.py:409–438`) and emits a `temporal_dag` beside `unified_pag` (`:1395–1445`). Static ADMG intake explicitly refuses positive lag rather than silently flattening it. These facts support the proposal’s narrow software boundary; they do not establish a temporal-PAG schema, equivalence-class/orientation rule, temporal identification semantics, or an external scientific result. Keep temporal-PAG support `absent/unallocated` until such a versioned law and its consumers are supplied.

## Pattern pass and next check

- **P29/P33:** good shape for a real producer/CAS/fresh-reader test, with direct output assertions rather than constructed report markers. The actual run is still required.
- **P31/P32/P38:** exercise the existing canonical pair-identity guard and exact lag refusal; do not weaken the static guard to make the mixed pair valid.
- **P40:** same pair-identity class, deeper lag dimension—not a new class. The proposal correctly tests both row orders and does not add one-off lag exemptions.
- Acceptance after freeze: run the exact focused pytest command in the proposal with full stdout/JUnit and selected profile; report skip/fail separately. Then assess only the B218 portion actually covered. B219/B220 require their own exporter and mutation/cache-consistency witnesses.
