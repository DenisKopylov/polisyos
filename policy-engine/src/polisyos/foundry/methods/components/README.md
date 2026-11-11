# Foundry Method Components

`polisyos.foundry.methods.components` owns chain composition, component-backed
method promotion, and input/output materialization helpers.

## Home

- `composer.py` builds method DAGs and compiled chains.
- `bridge.py` promotes component-registry entries into method registrations.
- `consensus.py` owns cross-method consistency and misspecification diagnostics.
- `io.py` materializes bound inputs and dematerializes method outputs.
- `linker.py` resolves slot bindings and compatibility diagnostics.
- `merge_engine.py` owns deterministic state-delta merge helpers.
- `representation.py` binds registered representation profiles to native method
  inputs and outputs observed at the NumPy execution endpoints.
- `semantic_validator.py` validates cross-method chain semantics.
- `slot_schema.py` owns semantic slot labels and compatibility registration.

Automatic slot linking maximizes admissible target coverage first, then the
lexicographic sum of the existing name/unit/type/shape/warning scores, then
sorted `(target, source)` ties. Residual augmenting paths may move an earlier
pair; diagnostics always describe the final selected binding. Exact-name
preference cannot sacrifice coverage, and unknown slot names remain
unconstrained rather than semantically attested.

## Registration Boundary

`bridge.py` may call `selection.registry.MethodRegistry.register_lazy()` for
component-backed methods. Catalog family registration remains in
`catalog/*/_registry_boot.py`.

Representation support is declared by typed method profiles and reconciled with
the actual registered callable, input preconditions and native output contract.
The initial Bounds profile covers only its finite binary-data base bounds;
optional tightening and other scientific forms have no implied support.
Neither an expectation dictionary nor a serialized audit summary establishes
live mode compatibility. Endpoint compatibility is separate from scientific
identification, calibration, execution-through-use custody and publication
authority. Stable ABI identity and representation-profile identity are distinct.

## Composition and checkpoint custody

The composer checks edge compatibility while building, then the existing linker
checks the union of incoming bindings per concrete target occurrence. Strict
public pairwise `SlotLinker.link()` keeps its original completeness contract.
Strict builder edges defer completeness until finalization; no type, unit,
shape, output-contract or named-semantic check is deferred. Input `SlotSpec`
currently has no optional/default/input-alias declaration. For strict linking,
all declared slots on a target with incoming data edges are therefore required;
root inputs remain external. Do not infer a default or alias from a method body.

A compiled plan records linker configuration and the explicit/automatic edge
route. `reconcile_validation_context()` replays the same compiler and regenerates
bindings and diagnostics from typed signatures before an owned plan executes.
It validates current checks; it does not authenticate a historical issuer. OFF
remains a visible limitation. Unknown rule/schema/mode and inconsistent graph,
bindings or warnings refuse rather than acquiring compiler provenance from a
self-computed hash. Existing heuristic semantic rules remain candidate mechanics,
not proof of scientific or policy admissibility.

The checkpoint owner persists context, aggregate composition warnings and each
completed result's slot outputs/history. A fresh resume uses the shared input
collector, including aliases established by explicit slot bindings, conversions
and validation, rather than substituting ambient state. Missing execution or
validation identity and missing completed slot-output history refuse safely;
there is no invented legacy clean-context migration. Runtime seeds remain on the
runner seed route rather than being injected as an undeclared user parameter.

`ValidationIssue.target_node_id` and `target_index` identify the actual offending
ordering occurrence. The fields are additive; FQN identity remains available.
The public result carries a typed `ValidationContext` separately from per-node
`MethodResult.warnings`.
