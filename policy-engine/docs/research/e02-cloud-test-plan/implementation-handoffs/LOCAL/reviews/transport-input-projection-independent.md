# Independent transport input and projection review

## Scope and binding

Reviewed candidate `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a` (tree
`741784521d909f775d50863a29deec63cde300cd`). This is a WIP source review, not a final
source freeze or formal closure. The criteria/source packet is
`LOCAL/decisions/transport-input-and-legal-mapping.md@sha256:5d4c47ce350bfc37910b06ae89535d6ea86be8df9eb040731bf072078089a9b8`.
It explicitly leaves null-versus-absent alias semantics `not_established` and legal target
semantics as a G choice; this review preserves both limits.

## Input boundary

The common boundary now rejects wrong-type or unsupported non-null query names, contexts,
policy specs, privacy candidates, solver modes, PAG policy values, and seed values before
backend selection. It preserves the current `None` omission/default behavior and records the
existing PAG range clamps in result warnings. `_resolve_pag_seed` accepts the exact unsigned
32-bit range consumed by `numpy.random.RandomState`; a direct lightweight probe accepted both
`0` and `2**32 - 1`.

One same-class escape remains. `_coerce_path` in
`src/polisyos/scientist/nodes/builtins/causal/transport_resolution_inputs.py:531` returns
`None` for a present whitespace-only string, exactly as it does for actual `None`. The direct
probe confirms that `_build_dataset_registry("   ")` selects `_NullDatasetRegistry` and
`build_skg_query("   ", "   ")` selects `_NullSKG`. The node preflights the four path fields with
this helper, then adapters use it again; a blank `dataset_registry_db_path`, `legal_kg_db_path`,
`skg_db_path`, or `skg_index_dir` can therefore take an omission/degraded-source path rather
than fail as malformed-present input. This is the same input-normalization class already
described in the packet, one level deeper, not a new class. Under P40, the next repair must
widen the shared path-input boundary so present blank values and omitted/`None` values are
distinguished consistently across all four fields, or record a bounded residual with a
falsifier; a one-field patch would leave sibling paths open. The falsifier should run each
blank path at the node boundary and prove it returns `ERROR_INVALID_STATE` before selecting a
null adapter, while missing/`None` retain the declared omission behavior and a valid path still
selects its configured adapter.

The `policy_spec` alias case remains correctly unadjudicated: the packet has no request schema
that distinguishes a missing alias from an explicit JSON null. `_resolve_treatment_value` skips
`None` aliases and continues to the next alias, so the pair `{"dose": 3}` and
`{"value": null, "dose": 3}` currently resolves the same way. Do not call this malformed-input
closure until the request contract defines presence/null semantics.

## Test replay

Ran one-thread focused replay from `policy-engine`:

```text
.venv/bin/python -m pytest -n 0 \
  tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py \
  tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_inputs.py \
  tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_results.py
```

Result: **13 passed, 12 failed** in 8.034 seconds. Complete stdout, stderr, command, and
before/after source hashes are retained under
`LOCAL/raw/transport-input-projection-review/`; stdout SHA-256 is
`e014a6f6335512641f18cc74ddb0b56c70bff23b5e07b3317265b75b78f5f407`, stderr is empty
(`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). The direct boundary
probes are in `behavior-probes.json@sha256:43b3e41b7c8b173ae8ad50bbd5502e2e1a6209e4df6a0ff20c48243ec49ef8f7`.
All six scoped source/test hashes were identical before and after the replay.

The failures are not evidence that all tested malformed values escaped. In the parameterized
input test, the node-boundary assertions pass for the malformed cases, then shared PAG default,
clamp, and seed assertions run inside that parameterized function. Nine cases fail repeatedly
at the nested assertion that `optimistic` should be invalid, but `PAGIdentificationPolicy` in
`src/polisyos/ir/analytics/causal_graph.py:29` explicitly defines `optimistic` as a valid enum
member. The remaining PAG-policy case itself expects the node to fail on that valid value and
instead receives `ok`. Use a genuinely unsupported token for the invalid case and move the
common helper assertions outside the parameterized function; add explicit acceptance checks for
seed endpoints. The branch-state test supplies `MagicMock()` as a causal report; the new strict
name parser sees mock-valued `method_params` and returns `fail` where this fixture expects
`skip`. Use a valid report fixture or assert the intended malformed-report outcome. The result
mirror confirms unresolved review state but still searches for the former text
`mechanism_target_not_in_graph`; the current reason is
`mechanism_target_not_present_in_current_graph`. Update the expected reason to the current
typed diagnostic.

## Legal projection boundary

`_candidate_legal_target_variable` in
`src/polisyos/scientist/nodes/builtins/causal/transport_resolution_results.py:577` now refuses
unsupported or ambiguous shapes and carries unresolved reasons into the result's
`requires_expert_review`/`expert_review_reasons`. The mirror exercises an in-graph mechanism
name, a one-edge effect-modifier shape, absent mechanism target, mixed edge/name shape, invalid
or multiple edges, and intervention redefinition. The loop test confirms the unresolved state
reaches the result; its failed assertion is only the renamed reason noted above.

This remains a review-required projection prototype, not a legal rule or authority decision.
The producer currently copies every graph edge into each mapping, so one valid edge does not
establish a selected edge. `SNode` cannot encode edge identity/slope or a proposed new mediator
slot, and an absent mechanism name cannot distinguish a proposed graph addition from a stale
target. Existing decision-packet and validity code can project a transport review signal, but
this source/test set does not prove that every such result creates a governance request or that
a review decision is completed and bound to the mapping and graph version. Keep this G choice
open; the packet's issuer-backed mapping plus fresh graph readback and exact edge-identity
witness remain the relevant discriminator. No legal rule, issuer fact, semantic approval, or G
closure is claimed here.

## Source and test fingerprints

| File | SHA-256 |
| --- | --- |
| `src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py` | `c675be08d419f6b81dfe8ef76ffc669672ef453c5bac37ea49165ee5b39d7bb9` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_inputs.py` | `cd3caca3ba2b8f244c62b00c3d25fcd1332fed7147fff66fc3c3ad2b28323e51` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_results.py` | `af895ed6cd2b16e52873a76dea1d7efc4bb48bf577d6abadd04eb291218eb76b` |
| `tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py` | `a364e1c9969b8ae785951140367eca549b572f4dc9b61fa4b06ab0da3d3b4a95` |
| `tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_inputs.py` | `c74c6fcd91c21fd2c9b4e804bc46fa0c0a9f48dd922a627f583738a3fe1be3a3` |
| `tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_results.py` | `0f79373c47679bd26c67d63f9cfcdafbaf1c16a66cb5fee16d202174a952c864` |
