# Y0 temporal-boundary candidate — separate from B219

**Disposition:** source mismatch confirmed; consumer effect, production reachability, and all behavior are `UNRUN` / `not_established`. This is a separate optional-Y0 adapter candidate, not B219 closure evidence and not an E02 regression attribution.

## Property and source seam

A static Y0 identification call must not silently receive a positive-lag arrow as a contemporaneous directed edge. The bridge must use a time-aware owner or return a typed limited/unsupported result when the static consumer cannot preserve the lag role.

The read-only trace finds `_oracle_y0` builds `NxMixedGraph` from directed/bidirected endpoint marks without filtering positive lag. Native static ADMG owners explicitly exclude positive-lag edges; temporal bridges preserve lag separately. `_oracle_y0` also assigns `graph.to_networkx()` to a local that is not consumed. Therefore this is independent of B219's `CausalGraphModel.to_networkx()` parallel-edge overwrite.

The opt-in API path exists, but the repository search found no literal in-repository `oracle="y0"` selection; the default route uses `oracle="none"`. No Y0-backed run or returned identification expression was measured. Do not report a live false identification.

## Distinguishing case and probes

Candidate graph: PAG nodes `{X,Y,Z}`, with `X -> Y @ lag=1`, `X <-> Y @ lag=None`, `Y -> Z @ lag=None`, and `Z o-o X @ lag=None`; query `P(Y | do(X))`. The source audit predicts that flattening the lagged arrow can change the static graph from identifiable to non-identifiable, but this remains an unrun hypothesis until the real optional Y0 package and public `CausalEngine.identify(..., oracle="y0")` path are exercised.

- **Positive / control:** use the real Y0 public route with the exact graph and a contemporaneous-only counterpart; preserve typed temporal and PAG ambiguity semantics.
- **Negative:** a static Y0 adapter refuses or returns typed limited for positive-lag input; do not silently map the edge as instantaneous.
- **Removal probe:** retain graph/lag markers but remove the lag exclusion/refusal predicate; the served distinguishing case must turn red when its actual identification result is measured.
- **P41 whole-file candidates, all `UNRUN`:** `policy-engine/tests/unit/foundry/methods/catalog/causal/test_id_engine_extensions.py`, `test_id_engine_characterization.py`, `policy-engine/tests/unit/ir/test_causal_graph_contract.py`, `test_pag_completion.py`, and `test_interoperability_bridges.py`. Resolve four-base path presence and admit each whole file before edits. `test_symbolic_identify_y0.py` tests a separate backend and is not evidence for `_oracle_y0`.

## B219 separation and next step

B219 remains the simple-DiGraph parallel-edge export concern. `_oracle_y0`'s unused exporter result means fixing B219 alone does not fix this adapter seam. Before implementation, identify an actual production caller or explicit deployed profile for the optional Y0 route; if none exists, preserve this as a bounded dormant-API compatibility question rather than claiming served impact. Keep temporal edge semantics in the existing graph/temporal owners; do not create a second graph owner.

Source audit: `/Users/deniskopylov/.codex/scratch/e02-r2-b219-y0-lag-followup-v2-20260925.md@sha256:1d2f175c473b57a3adc6b63aeac63cff8df8a28a2364e9d05cd7502692cdb3cf`. Its proposed identification difference is not a measurement; production caller census and all P41 witnesses remain `UNRUN`.
