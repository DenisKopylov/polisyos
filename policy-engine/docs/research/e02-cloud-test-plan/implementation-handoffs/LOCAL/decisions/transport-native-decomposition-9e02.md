# Transportability source decomposition

## Decision and scope

This is a behavior-preserving source-organization change against slice base
`9e02a9f49c8b01026327a9f7c7e18711b13a96f2` (tree
`881a950dccb7cdefacc636515aa7dd2bceadf928`; original canonical source SHA-256
`594d6e5d0f873d2e2641532ee1cdfe8d1e79ae63e705230081e87b4c413f850c`). The canonical
transportability node and resolution loop remain in `resolve_transport.py`; input/context and
result/lineage implementation are grouped in two domain-named adjacent modules. No scientific
evidence, result currentness, or adequacy claim is added.

The disposition is `NEW_CLASS` for this slice: the task is a whole-module organization and
complexity-boundary change, separate from the earlier custody and monetary mechanisms. It moves
the complete canonical implementation into cohesive input and output responsibility groups while
retaining the public facade and its integration seams. No deeper same-class escape has been
identified in this slice. If a later review identifies one, apply P40 to the whole source-boundary
mechanism or record a bounded residual; do not add another site-by-site extraction.

## Structural result

- `src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py` retains
  `ResolutionState`, `TransportabilityResolutionLoop`, `RunTransportabilityNode`, the query
  construction adapter, and runtime/producer/test patch seams.
- `transport_resolution_inputs.py` groups context, registry, configuration, graph/PAG,
  capability, resolver, and query-selection helpers.
- `transport_resolution_results.py` groups result construction, alignment, partial-ID fallback,
  lineage, legal mapping, proxy/GAP projection, and privacy finalization.
- The canonical query adapter supplies its own `SKGQuery` dependency to the helper, and result
  helpers receive canonical proxy/confidence callbacks. This preserves module-level monkeypatch
  behavior instead of creating parallel producer implementations.
- Measured logical LOC (nonblank, non-comment lines) is 982 / 356 / 537 respectively; physical
  lines are 1,062 / 417 / 585. The canonical module is below the 1,000 logical-LOC boundary.

## Compatibility evidence

The generated before/after API census is byte-identical after parsing: both JSON files have
SHA-256 `83e72764b8d418604d277500a7901d5e8ce7584a391dac3e8a57466b1749c197`. The comparison
receipt is `raw/transport-native-decomposition-9e02/final-api-compare.log` with SHA-256
`cf578947890821ed427eb7143cb6fd7f7e3dc81ea36a6b5b7e5aab81b17f44bd` and reports PASS. The
census covers the three public class FQNs, `__all__`, constructor/resolve/execute/prepare
signatures, `ResolutionState` fields, and package-lazy class identity. A characterization test
pins these properties. Existing tests continue to exercise the canonical `_build_skg_query` seam
and error propagation.

The source SHA-256 values at this readback are:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py` | `4696f3c37f1edb287527776d1579fd98ae0d94b8d4d513c9571328bf1e0d51cc` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_inputs.py` | `0d9601de272f6067b2384111fb09d783d8cbfffa46500ed2bd0dba21ee717703` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_results.py` | `c607b069be5fcd8d537e7ce53a92e3321ccaa1904007581a40276a81b8074cfa` |
| `tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py` | `a364e1c9969b8ae785951140367eca549b572f4dc9b61fa4b06ab0da3d3b4a95` |
| `release-fragments/unreleased/2026-10-09-e02-causal-transport-module-decomposition.toml` | `c92dbd5e842cdef53b494273bf29e32046fc802c893e7962644c276125d20a96` |

## Verification

The focused baseline suite on the original source passed 28 tests with one environment-conditional
skip. The same focused suite after the refactor passed 29 tests with one skip; the additional test
is the public-API characterization. The skipped bounds-fallback case is intentionally unavailable
because `y0` is installed and symbolic identification succeeds.

Final receipts under `raw/transport-native-decomposition-9e02/`:

- `final-focused.log` (`a2945966c1638ea49339aedcbe9bb037c129b14fff2c19ffcce6aa003e39ea39`):
  focused node, method, and cache tests; 29 passed, 1 skipped.
- `final-ruff.log` and `final-c901.log` (both
  `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`): Ruff and C901 checks
  passed on the four changed Python files.
- `final-format.log` (`177f260a5645724013185e4b140c7045cc39e56c0c97b120f5cb23599f85f0de`): all four
  Python files already formatted.
- `final-compileall.log` and `final-diff-check.log` (both empty-output SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`): compile and whitespace
  checks completed without diagnostics.
- `baseline-causal-transport-tests.log`
  (`52cdf2b6b365cff884c5af059f98eb210e0bb49f2ffa37ef055b884402722331`): original-source
  focused baseline.

The release fragment parses as TOML and describes the change as internal. No commit or staging
operation was performed by this worker.

## Pattern and companion record

P27 is addressed by keeping the canonical owner and naming helpers by domain responsibility; no
parallel node, engine, or producer is introduced. P06 is guarded by preserving canonical class
FQNs and package-lazy identity. P13 is addressed by measuring the whole changed module against the
complexity boundary. P31 is addressed structurally by splitting cohesive responsibility groups,
not by routing selected call sites through new wrappers. P40 is classified above before any
possible later finding.

The nearest-parent README is shared with the root documentation owner and was not edited here, as
directed. Proposed paragraph sent to that owner:

> The transportability node remains registered from its canonical
> `builtins/causal/resolve_transport.py` module. That facade retains the public node classes and
> module-level integration seams; `transport_resolution_inputs.py` groups context, registry,
> configuration, and query selection, while `transport_resolution_results.py` groups private
> result, lineage, and projection helpers. The split changes source organization only; node
> identity, persisted schemas, and runtime behavior remain unchanged.

The complexity exception registry is also outside this worker's lease and was not edited. This
refactor does not claim to complete the empirical transportability capability chain; that
scientific/product question remains outside this source-organization change.
