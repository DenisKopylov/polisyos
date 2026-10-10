# Independent review: Twin EvidenceBundle versioning delta

Review target: `b2cd1fbb0c9aaa21a05cbf999330a2e07fe81f23` (tree `65c44e4872c0efb0772ee955c2b92351c2486892`, parent `00c200c2ec33786a80dd41209eca46a2539dac5c`) in the assigned candidate worktree. The review is read-only against committed source; this receipt is the only file written. No generated files were regenerated, and no historical wheel was executed or claimed.

## Result

The default version boundary works for both producer shapes: a reference-free EvidenceBundle remains exact schema 1.0 with the pre-Twin 21-field JSON shape, while a bundle carrying `TwinNetworkResultRef` is schema 1.1. The current reader negotiates both supported versions, refuses schema 1.0 payloads that smuggle the new field (including `null`), and validates the typed reference. Existing simulation-proof-bridge output remains on 1.0. A real `CausalEngine.run()` with a manually specified SCM persists the Twin result, links it through the proof trace, and a fresh process resolves and reads the result.

One bounded mismatch remains in the public persistence API: the writer accepts a custom `schema_name`, but the paired loader only accepts `ir.causal_evidence_bundle`. The same writer can therefore persist a ref that its loader cannot read. No current in-tree caller supplies a noncanonical name. This review does not adjudicate or close any E original-criterion proposal or establish G acceptance.

## P40 and gate classification

**P40 bucket: SAME class, one level deeper.** The class is the producer/reader schema-boundary invariant: the reader must accept only a schema/version that the producer and the compatibility registry can actually represent. The custom-name case is the sibling identity dimension below the reviewed version negotiation, so it is not a new class. The narrow class-level closure is for the writer to reject noncanonical `schema_name` before CAS I/O, matching the reader, or else to support custom names through the same registry. A local search found no production or test callsite using this override; the reproducer below falsifies the current writer/reader agreement directly.

**P38 property and implementation:** the property is “a successful persistence by this API yields a ref readable by its paired loader.” The writer turns on `schema_name` supplied by its caller and writes it; the loader turns on exact equality with `ir.causal_evidence_bundle`. The divergent case is a custom name: persistence succeeds, then load fails with `Missing or unsupported causal EvidenceBundle schema metadata`.

**P37 predicate:** supported-version compatibility is recomputed locally by `negotiate_schema_version()` against the registered 1.0/1.1 rules. The source schema name/version themselves come from the selected CAS manifest, which is producer/store-supplied metadata rather than an independent second source. Payload validation remains a separate strict Pydantic check; the manifest alone does not establish a Twin result.

## Source and behavior reviewed

- `src/polisyos/ir/analytics/evidence_bundle.py`: `EvidenceBundle` adds optional `twin_network_result_ref`; persistence chooses 1.0 without it and 1.1 with it, rejects explicit version mismatches, and excludes the field from 1.0 serialization. Loading reads the selected ref's manifest, checks the canonical schema name, negotiates against current 1.1, then validates the payload. A 1.0 payload containing the Twin key is rejected before model validation.
- `src/polisyos/ir/migrations/schema_registry.py`: 1.0 is strict and declares 1.1 writable; 1.1 is backward-readable from 1.0 and declares `twin_network_result_ref` an additive optional field. `ir.migrations` imports the registry and registers those default rules.
- Existing producers: `simulation_proof_bridge.py` persists a reference-free evidence bundle; the focused bridge test verifies manifest 1.0 and `twin_network_result_ref is None`. The causal engine's trace producer supplies `twin_network_result_ref` and an `InputRef` for the Twin result.
- Runtime boundary test: `test_counterfactual_run_persists_and_reads_typed_twin_network_result` invokes `CausalEngine.run()` with a manual SCM (`fit_method="manual"`, explicit training rows) and an ETT query. It resolves the actual persisted Twin result, checks source/query/SCM inputs and selected manifest profile hashes, resolves the proof bundle's trace, asserts the trace uses 1.1 and links the Twin ref, then launches a subprocess that follows proof bundle → trace → Twin result and compares the full serialized result with the producer output. This demonstrates the manual-SCM artifact path; it is not a native fit or worker-provenance claim.
- Legacy-reader evidence: `test_evidence_bundle.py` pins the pre-Twin 21-field set and a test-local strict `extra="forbid"` v1.0 parser. It proves the emitted 1.0 shape is accepted and a 1.1 payload is rejected by that parser. This is a model-shaped compatibility fixture, not execution of a historical package/wheel.

## Generated snapshot check

The committed `causal_evidence_bundle.schema.json` accepts both the exact reference-free v1.0 payload and the Twin-bearing v1.1 payload under `Draft202012Validator` (zero errors for each). The Twin field is nullable and optional, while the root remains `additionalProperties: false`; only `run_id` and `query_str` are required. `docs/reference/ir/schema-catalog.md` documents the optional typed ref. The IR model snapshot manifest has `schema_version: null` and `version_field: null` for this model because `EvidenceBundle` has no in-payload version field; the 1.0/1.1 version is carried by the CAS artifact manifest. No generator was run.

Exact committed SHA-256 values for the reviewed source and companion artifacts:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/ir/analytics/evidence_bundle.py` | `e4782562eadc95ed805aacba2a058bc1e367d3e437ae844103556bf99aa554b4` |
| `src/polisyos/ir/migrations/schema_registry.py` | `ded5e983f7c9863ae12c9e2eb60ab610d7bd3e9963d7f739652a833b820740c7` |
| `src/polisyos/foundry/methods/catalog/causal/causal_engine/artifacts.py` | `421bb85accfae77230fd91525f002ce35369a591d4e3955d8d1b736cca7dd50d` |
| `tests/unit/ir/analytics/test_evidence_bundle.py` | `f512213bee9b840cdb83bdef8d914ddee1488835e51cd9439404c9de4d92bd77` |
| `tests/unit/ir/analytics/test_simulation_proof_bridge.py` | `5b83e1d159a29b971706f459e89ef4622c2883a43dda4dc084554dd994ec64c5` |
| `tests/unit/foundry/methods/catalog/causal/test_id_star_algorithm.py` | `585e6af2b0e538e0dacd81f79ff3bb19dc996bb83f36c1405c1284a5a06bb85a` |
| `docs/reference/ir/schema-catalog.md` | `88208ff42a7f64eb7a21f237edb4d75beffe949b95d74e85139f1947c6429ae0` |
| `schemas/snapshots/ir/causal_evidence_bundle.schema.json` | `ee6b9b1888d2ac9dd7308b280264579a343dc5b8f4fb6b1eb7f98b31f3861a5b` |
| `schemas/snapshots/ir/_manifest.json` | `570df7bbcd0f636f0899003bd3040578c9b1883b51dc37aacdffecf625e57ddf` |
| `release-fragments/unreleased/2026-10-09-causal-engine-twin-result-persistence.toml` | `3ebfb29ae3de4bea54a123ce25fcb45daebe6a385f190cd743d8e62cf81d4975` |

## Verification receipts

Environment origin check:

```text
executable: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/bin/python
polisyos: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/src/polisyos/__init__.py
EvidenceBundle module: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/src/polisyos/ir/analytics/evidence_bundle.py
migrations module: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/src/polisyos/ir/migrations/__init__.py
```

Focused behavior command (exit 0):

```text
PYTHONPATH=src:. .venv/bin/pytest -q tests/unit/ir/analytics/test_evidence_bundle.py tests/unit/ir/analytics/test_simulation_proof_bridge.py::test_simulation_proof_bridge_defaults_to_scenario_without_causal_context tests/unit/foundry/methods/catalog/causal/test_id_star_algorithm.py::test_counterfactual_run_persists_and_reads_typed_twin_network_result
..........................                                               [100%]
```

Scoped Ruff command (exit 0):

```text
.venv/bin/python -m ruff check src/polisyos/ir/analytics/evidence_bundle.py src/polisyos/ir/migrations/schema_registry.py tests/unit/ir/analytics/test_evidence_bundle.py tests/unit/ir/analytics/test_simulation_proof_bridge.py tests/unit/foundry/methods/catalog/causal/test_id_star_algorithm.py
All checks passed!
```

Snapshot plus paired-writer reproduction command used a temporary CAS directory (no repository data writes). Output:

```text
snapshot validation errors no-Twin: 0
snapshot validation errors Twin 1.1: 0
snapshot schema_version: None version_field: None
Twin optional: True additionalProperties: False
catalog has Twin optional row: True
custom schema persisted as: custom.causal_evidence_bundle
canonical loader result: ValueError: Missing or unsupported causal EvidenceBundle schema metadata
```

Minimal custom-name reproduction:

```python
ref = persist_causal_evidence_bundle(
    store,
    EvidenceBundle(run_id="custom-name", query_str="Q"),
    schema_name="custom.causal_evidence_bundle",
)
load_causal_evidence_bundle(store, ref)
```

Expected class-level boundary: raise `ValueError` in persistence before CAS I/O for a noncanonical schema name (unless the schema registry and loader are deliberately generalized to support that name). Current behavior persists first and fails only at load.
