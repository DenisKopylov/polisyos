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

