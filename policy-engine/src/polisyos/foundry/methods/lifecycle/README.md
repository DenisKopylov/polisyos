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

## Output Monitoring Contract

The dispatcher checks declared output names against the backend runner's
normalized `MethodResult.slot_outputs`. Supported raw aliases and diagnostic
sidecars remain available in `MethodResult.output` and do not create slot key
anomalies. Numeric NaN/Inf diagnostics in either view still produce typed
`AnomalyFlag` errors through the existing warning and telemetry routes.

An empty untyped Python list or tuple carries no numeric dtype, so it can
represent an empty diagnostic collection. An explicitly typed empty array
or an empty sequence in a declared vector/matrix/tensor slot still produces
`empty_array`. Missing declared slots and malformed array
shapes remain contract failures during dematerialization; inconsistent
canonical slot keys remain monitor anomalies.
