# Foundry Method Artifacts

`polisyos.foundry.methods.artifacts` owns immutable provenance records for
method, chain, and execution evidence.

## Home

- `parts.py` exposes the public artifact functions and dataclasses.
- `_chain.py`, `_method.py`, `_evidence.py`, `_fingerprint.py`, and
  `_records.py` are private implementation slices.
- Public callers should import from `polisyos.foundry.methods.artifacts`.

## Executable chain recipes

`ChainArtifact.from_chain` emits the 1.1 recipe from a currently reconciled
`CompiledMethodChain`. It binds each occurrence and authored static/dynamic
parameter, full signature ABI (including `requires`), link route, validation
mode/configuration and effective predecessor set. The recipe is an immutable
canonical byte snapshot; it does not serialize Python functions or closures.

Persist method artifacts first, then call `store_chain_artifact` with their
selected `method_refs` and `return_selected_profile=True`. Omitting `method_refs`
resolves and binds the current actual method manifest views in that store.
`load_compiled_chain(cas, selected_ref, registry=...)` reopens those exact views,
checks method source/module bytes and full ABI against the current registered
implementations, and rebuilds through `MethodComposer`. A complete canonical
re-emission must agree before the caller can execute the returned chain.
Stored ordering alone cannot stand in for requires-only dependencies.

Executable reconstruction declares `ordinary-class-source-v1`: an operation's
live code must equal the class's own `pure_step` definition compiled from its
actual module bytes, without running module statements. Decorated/native
callables, inherited/aliased operations, captured live closures and
runtime-default-bound functions are unavailable in this source-bound profile;
their ordinary dispatch and legacy provenance inspection remain unchanged.
The check does not attest external module state or scientific validity.
The loaded chain also retains the existing process-local executable identities.
Shared plan admission and actual node-input admission reconcile the selected
registry/class/code before execution, so a later registry override or operation
change cannot silently substitute another implementation. These process-local
bindings are rebuilt from verified source on each fresh load, never serialized.

Executable recipe 1.1 uses Core CAN.2 finite floats with `exclude_none=False`,
recorded in both the payload and manifest. Recipe-only numeric chain records
and `ExecutionEvidence` use 1.1 with the explicit finite-float, legacy-field/null
profile (`exclude_none=True`); dictionary null fields remain present, and the
optional per-method JIT timing remains omitted when unavailable. Conversion
factors and timings must be finite real numbers, never numeric strings or bools.
The Core default continues to forbid floats.

Valid nonnumeric recipe-only 1.0 bytes and content IDs are preserved exactly.
`ChainArtifact.from_canonical_bytes` reads those records and new 1.1 records;
only `load_compiled_chain` reconstructs an executable recipe. Historic numeric
1.0 records using reserved `float_hex` aliases are not canonical fixed points
under CAN.2 and cannot be promoted to verified records. Their original CAS bytes
remain immutable inspection data. Reissue from available typed composition or
execution inputs into 1.1; do not rewrite their bytes or reinterpret an old
manifest's profile. Missing original inputs make reissue unavailable.

`store_execution_evidence(..., return_selected_profile=True)` returns the exact
written view. `load_execution_evidence` checks selected kind/schema/canonical
profile, strict typed fields, complete canonical re-emission and the manifest's
chain/input/output/parameter/RNG lineage. It records declared provenance; it does
not independently attest that the asserted computation or scientific effect
occurred. Nested library-version mappings are snapshotted before hashing.

The canonical-owner numeric census covers all three artifact classes:
`MethodArtifact` 1.0 persists hashes, source facts and integer/string/boolean
specialization fields, not raw parameter bounds/static values, so its valid
bytes need no numeric migration. Full signature ABI (including bounds/requires)
and authored values are checked in the 1.1 chain recipe. `ChainArtifact` contains
conversion factors; `ExecutionEvidence` contains total/per-method/JIT timings.
Their new finite-float writers and selected manifest profiles agree; direct
legacy record `to_dict()` helpers retain their historic projection.

Recipe-only records remain unavailable for executable loading, which refuses
them rather than inventing missing parameters or a performed mode.
New 1.1 identities intentionally bind occurrence UUIDs and diagnostic context;
the existing numeric explicit-merge result remains UUID-invariant. Historical
specialization/backend metadata is provenance, not a claim that a different
current backend reproduces old numerical behavior or scientific authority.

## Authoring Rules

- Keep artifact payloads deterministic and content-addressable.
- Add schema-version changes beside compatibility tests.
- Do not add backend execution logic here; backend receipts are passed in from
  `backends/` and persisted here.

