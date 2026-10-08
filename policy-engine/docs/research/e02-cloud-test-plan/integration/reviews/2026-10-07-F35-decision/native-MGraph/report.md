# Native M-graph boundary probe

Verdict: CONFIRMED_ADMITTED_TYPE_ERASURE. The registered reconciliation producer accepted a valid M-graph, preserved its metadata and edges, then changed its graph type to ADMG. The actual M-graph metadata reader rejected both the producer result and fresh-CAS result because the type was no longer MGRAPH.

## Target and isolation

- F candidate 25cdea9064ddea2c3a812fd68670076bd4b088cb (tree ed4a4fd6864e8b60cb45124fb8e6fa9b7c503b66); source freeze 519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82. Critical graph/runtime source blobs match the freeze. Candidate is not an ancestor of integration checkpoint c75eb7125ae0b4b296fc469b13bba9653f1dd42d; only isolated candidate source was imported.
- Exact archive: 2914 tracked source files (54,939,306 bytes); all paths, modes and Git blob IDs verified. Five additional tracked files read by runtime import checks (three owner registries, pyproject.toml, uv.lock; 839,680 bytes) were pinned and verified. No .git, copied venv, dependency install or production data.
- Python 3.14.3, Pydantic 2.12.5, NumPy 2.3.5. All 970 loaded Polisyos modules originated in the exact archive and matched Git blobs. Source and working assets were unchanged before and after.

## Observed chain

The input used build_mgraph to construct X -> Y, X <-> Y, and R_X -> X_star with MCAR metadata. The builder’s edges were assigned synthetic DATA confidence 0.9 and revalidated as a public CausalGraphModel so the normal reconciliation threshold retained the structural discriminator. Input extract_mgraph_metadata passed.

The registered ReconcileCausalGraph method result was ADMG, retaining all three edge relations and the original metadata["mgraph"]. Calling extract_mgraph_metadata on that producer result raised: ValueError: extract_mgraph_metadata requires graph_type=MGRAPH, got GraphType.ADMG. ReconcileCausalGraphNode accepted the result, persisted a graph, and a new FileSystemCAS reader returned the same ADMG, edges and metadata; the same MGraph reader failed again.

The normal DAG and ADMG controls passed through the same producer/node/CAS path. DAG stayed DAG with X -> Y. ADMG stayed ADMG with X -> Y and X <-> Y. This rules out a generic producer or CAS failure.

## Execution and scope

Command: /Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/.venv/bin/python -B -B; PYTHONPATH points to isolated candidate source, bytecode and user site disabled, numerical thread variables set to one. Wall time 8.129s against a 90s cap; child runtime 7.406s; raw ru_maxrss 588,562,432 platform units. Full stdout/stderr, execution context, JSON results, source/asset manifests, native inputs, producer/consumer outputs and CAS data are retained under this ignored directory.

The first builder-only fixture was inconclusive because default builder edges have no confidence and the reconciler filtered them. Full outputs are preserved in attempt1-builder-unscored/. An earlier source-only import setup failed on one missing tracked registry asset. Its original raw bytes were overwritten by the next wrapper invocation before preservation; the captured hashes and cause are transcript-bound and explicitly not represented as a complete file receipt.

This confirms the same static-profile admission class at graph-type identity depth; it does not establish causal identification or overall F closure. The bounded owner action is to issue a typed MGRAPH refusal at the ADMG reconciliation boundary, or preserve MGRAPH identity and its consumer contract end to end. No source, tests, refs, integration history or tracked files changed.

Machine receipt: policy-engine/_build/e02-g-continuation-20261006/R/F35-decision-20261007/Mgraph-local/receipt.json
Full deciding runtime JSON: policy-engine/_build/e02-g-continuation-20261006/R/F35-decision-20261007/Mgraph-local/attempt2-confidence-annotated/probe-results.json
