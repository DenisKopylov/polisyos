# F graph source/consumer review

## Pins and scope

- Integration checkout at review: `83e7c0e934d0b40644dec8a24264a0602ef013e7`.
- F root under review: `cdf61b4500e355a27db14260e80ce673ddf8869e`, tree `a08083a193d4621a5d5c59bf31a94916e8323a0a`; published F graph intake slice `647f5d35362c2a5d7ad32283b804a5b03ea56e83`, tree `6b699cac11fb1fe5b317ed0ccfc76940e5958906`; installed graph test carrier `6f39b0edc48ec59db3731fa917c615b9f97e4dc0`, tree `bd4d4488cbd8121fed1c0983d2e3cc3d8fef49a5`.
- F source freeze `519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82` (tree `750d28da94f372848fe6b2db5f88db95b94cb57d`). Graph runtime/test paths are byte-identical at `519`, `647`, and `cdf`; the only later graph-path addition in `cdf` is the installed-consumer test and its release/docs companion. Current graph runtime blobs: `graph_reconciliation.py@6b148f720d7fb7aa978fb46bbca722615cf433cf`, node `reconcile_causal_graph.py@70ccfd46c42253861c31210ac176e22df3119e15`.
- Read only the graph source/test/release deltas from prior checkpoint `56e4513787773e6860b55163cd792062abe66a94`; no tests or builds were run in this review.

## Bounded property supported by source and receipts

The `GRF-03` current-content handoff at candidate `647` binds the changed runtime and tests to that exact tree. Its actual registered Numpy method producer serializes a synthetic typed graph, resolves a method result from CAS in `ReconcileCausalGraphNode`, recomputes the full request, persists the graph, and reopens it through a fresh `FileSystemCAS` reader. The node checks actual manifest kind/schema/body version, requires supplied graph and selected method-result content to agree, and only reuses a cached graph when the full graph and manifest input lineage agree. Composition replay resolves current fragments, graph refs, alignment and mapping; it recomputes the full producer certificate/failure-card body, then recomputes query caches.

The property oracle is meaningfully independent of implementation fields for the bounded cases: tests compare exact directed/reverse/bidirected endpoint relations after producer→node→CAS→fresh-reader; they mutate current producer direction and parameters; and they exercise malformed, absent, wrong-kind/schema/version, corrupted-cache, stale-composition, changed-alignment and operational-query-cache cases. Unsupported circle/tail-tail marks and nonzero input lags are rejected by the real method producer before it yields a method result, and direct node intake fails without persisting a graph. Exact candidate `647` native output is `79 passed`; the independent read-only reviewer on the same SHA/tree also reports `79 passed`, plus three original discriminators and 17 full certificate projection controls. Its source bindings match the candidate. The composition-property removal probe itself fails the expected assertion when the property is removed; this is a successful negative discriminator, not a candidate-suite failure. Baseline `072d45a` is separately characterized as unsafe (stale direction reuse, shaped missing ref, circle collapse and compact lag admission).

The graph-model installed-consumer proof is narrower. Candidate `6f39b0e` has no runtime source changes; author wheel and sdist runs, plus an independent wheel run, exercise detached `to_kuzu` parameter dictionaries, mutable consumer and base-dict controls, CSV output, exact multigraph edge identity, typed CAS persistence, and a fresh isolated child reader. Positive outputs pass two cases; removing row isolation makes both fail. The installed distribution is source `8236d9c`, not the current candidate. The exact `causal_graph.py` and `admg_ops.py` blobs in `8236d9c` equal current `cdf`, so evidence transfers only to those two modules. That older component receipt alone does not qualify the current producer/node. The later root de197 exact-source519 receipt does: 91 wheel and91 rebuilt-sdist PASS, including79 maintained graph and12 catalog cases. A separate c4dd wheel-only fresh-child receipt exercises registered producer→Node→selected CAS→different-PID reader. Current G-composed source is still a different unqualified tree; [F35 correction](../2026-10-07-F35-decision/README.md) supersedes the earlier broad installed-UNRUN statement. No live Kuzu database, optional DoWhy/EconML backend, empirical discovery validity, identification authority, or A-owned authority-gated consumer was tested. The A consumer edge remains with A.

## Blocker: M-graph type is admitted and erased by the new bidirected path

**HOLD the bounded profile claim until this boundary is either refused or made semantics-preserving.** This is the same static-profile admission class one level deeper (graph type, rather than edge mark/lag), not a new causal-authority finding.

`_validate_static_admg` checks only edge marks and lags; it does not reject `GraphType.MGRAPH` (method call at `graph_reconciliation.py:995-996`). `build_mgraph` constructs a typed M-graph with `metadata["mgraph"]` and permits bidirected edges (`ir/analytics/mgraph.py:305-310` and builder edge construction). The changed reconciler now emits `GraphType.ADMG` whenever any resolved edge is bidirected (`graph_reconciliation.py:1044-1052`), while carrying input metadata forward (`:1030-1041`). Thus a valid M-graph with a bidirected substantive edge passes the new static edge-profile check and is newly admitted as an ADMG; the M-graph metadata remains present but the graph-type identity is gone. The actual consumer `extract_mgraph_metadata` rejects every graph whose type is not `MGRAPH` (`ir/analytics/mgraph.py:124-139`). The current exact endpoint tests cover `GraphType.ADMG` bidirected relations but not `GraphType.MGRAPH`; there is no M-graph discriminator in the current-content suite. This was a source-derived consumer counterexample; the later scored-builder native witness now confirms the actual producer→Node→fresh-CAS reader failure. DAG/ADMG controls pass.

Small closure: at the canonical reconciliation boundary, either refuse `GraphType.MGRAPH` before the registered producer rewrites it, or preserve the full M-graph contract (type, metadata, required graph invariants) through the current producer and consumer. Add a focused real `build_mgraph`→registered producer→node→fresh-CAS-reader test with directed plus bidirected edges; assert typed refusal or successful `extract_mgraph_metadata` and unchanged missingness semantics. Do not tighten a shared ADMG helper globally without checking its other callers.

A further bounded limitation: successful direct `data_causal_graph` input without a method-result ref is still accepted. In that path `data_graph_ref` is `None`, so the persisted graph manifest has no `data_graph` `InputRef`; only the computed request digest remains. The current source-bound positive proof uses the method-result CAS path. Treat direct-parameter source lineage as not established, and do not infer authority from it.

## Finding scope and disposition

The `GRF-03` handoff records B214 as limited (arbitrary PAG/CPDAG completion and protected readiness remain out of scope) and B218's original storage/static-refusal recommendation as closed; full temporal inference/protected readiness stays unclaimed. Those are F handoff recommendations, not independent G ledger closure. The initially source-level MGraph counterexample is now a confirmed runtime blocker for the candidate profile boundary; G retains source acceptance HOLD until canonical repair and affected evidence. No conclusion is made about the unchanged A authority gate or overall F closure.

## Follow-up: M-graph admission trace

Initially source-derived; now confirmed by [exact native MGraph probe](../2026-10-07-F35-decision/native-MGraph/README.md). The original source analysis below remains its own evidence cut. There is no earlier graph-type guard in the registered producer input path: `GraphReconciliationData.data_graph` accepts `CausalGraphModel | dict` and its validator only coerces/validates that model (`protocols.py:836-857`). The Scientist loader validates the actual MethodResult manifest/schema and extracts its graph, but does not restrict `graph_type` (`reconcile_causal_graph.py:211-230`). `ReconcileCausalGraph.pure_step` then calls `_validate_static_admg` directly (`graph_reconciliation.py:995-996`), whose `CachedAdjacency` admission is edge-mark/lag based, before output selection changes any graph with an arrow-arrow edge to `GraphType.ADMG` (`:1044-1052`). The `MGRAPH` metadata is preserved, but its type is not. `extract_mgraph_metadata` requires `GraphType.MGRAPH` (`mgraph.py:124-139`).

The handoff's declared finite profile is explicitly “known contemporaneous directed/reverse/bidirected ADMG relations” (`graph-intake-current-content-20261007.json` → `property.finite_profile`); the docs phrase it as directed/bidirected relations but do not expand the supported typed graph classes. Therefore refusing `GraphType.MGRAPH` at this ADMG reconciliation boundary is the smallest correct repair and closes this unsupported-M-graph escape. Preserve MGRAPH only if reconciliation retains its graph type and metadata contract end to end.

Historical suggested probe (the later scored-builder native witness is now executed): add a test to `tests/unit/scientist/methods/causal/test_graph_intake_current_content.py` using its existing `context`/`produce`/`state_for` helpers:

```python
graph = build_mgraph(
    substantive_vars=["X", "Y"],
    directed_edges=[("X", "Y")],
    bidirected_edges=[("X", "Y")],
    missingness_map={"X": MissingnessKind.MCAR},
)
job, _ = produce(context, graph)
assert job.issues and job.method_result_ref is None  # desired typed refusal
```

If a method result is returned instead, continue through `ReconcileCausalGraphNode.execute`, fresh `FileSystemCAS`, and `extract_mgraph_metadata` to make the semantic loss fail visibly. Focused command after adding that test: `.venv/bin/python -m pytest tests/unit/scientist/methods/causal/test_graph_intake_current_content.py -k mgraph_admission -q -o addopts= --import-mode=importlib -p no:cacheprovider`. This remains the same P40 static-profile boundary class, one level deeper than marks/lags.
