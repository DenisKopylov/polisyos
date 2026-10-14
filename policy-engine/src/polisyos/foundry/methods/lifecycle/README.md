# Foundry Method Lifecycle

`polisyos.foundry.methods.lifecycle` owns lifecycle state, compatibility,
deprecation, monitoring, and observability helpers for method execution.

## Home

- `__init__.py` owns `MethodLifecycle`, `LifecycleLog`, and transition rules.
- `compat.py` and `compat_matrix.py` own ABI compatibility checks.
- `deprecation.py` owns method deprecation and retirement helpers.
- `output_monitor.py`, `observability.py`, and `profiler.py` own operational
  instrumentation.

## Authoring Rules

- Lifecycle state must be deterministic and auditable from registry entries.
- Deprecation changes need a compatibility test and a documented removal path.
- Monitoring helpers must stay optional when telemetry dependencies are absent.

## Output validation contract

The dispatcher compares declared output names with normalized
`MethodResult.slot_outputs`. Supported raw aliases and diagnostic
sidecars are available in `MethodResult.output` and do not create slot-name errors.
Numeric NaN/Inf values in both representations retain typed `AnomalyFlag`
errors, warnings, and telemetry forwarding.

During standard dematerialization, the dispatcher traces the selected raw key to
the canonical slot: first the slot name, then aliases in canonical-normalizer
order. If the selected object reaches the slot without transformation, NaN/Inf
is checked once under the canonical name. This also applies to a bare output
for a single slot.
An independent raw diagnostic field is checked separately, even when it
contains the same object; an unselected alias also remains diagnostic when a
canonical key is present. Warnings and the OTel counter therefore count one
canonical anomaly and each separate diagnostic anomaly.

For a custom `dematerialize_output` that copies or wraps values, source
correspondence is not inferred from value equality or shared identity with
other fields. Both representations retain their checks; the guarantee of one
canonical counter applies to the standard dematerialization path that preserves
the selected object.

An empty Python list or tuple without a numeric dtype may represent an empty
diagnostic set. An explicitly typed empty array or empty sequence in a declared
vector/matrix/tensor slot retains `empty_array`. A missing declared slot and an
array with the wrong shape remain contract failures during dematerialization;
mismatched canonical keys remain monitor errors.
