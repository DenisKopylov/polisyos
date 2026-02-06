# Migration Guide: TrinityBundle Only (Phase 4)

## Summary

Phase 4 removes legacy surface IR support from runtime code. Canonical IR is now only:

- `ProblemFrame`
- `PolicySpec`
- `ModelSpec`
- `TrinityBundle`

## Breaking Changes

- `polisyos.ir.surface` is removed from runtime code paths.
- `PolicySurfaceIR`/`PolicySemantic`/`PolicyAdvisory` are no longer supported.
- `CompileRequest.input_kind="surface"` is no longer accepted.
- `load_policy(..., as_trinity=...)` is removed. `load_policy()` always returns `TrinityBundle`.
- Legacy migration helpers for round-trip to surface IR are removed from runtime modules.

## Import Migrations

```python
# before
from polisyos.ir.surface import PolicySurfaceIR

# after
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.problem_frame import ProblemFrame
from polisyos.ir.policy_spec import PolicySpec
from polisyos.ir.model_spec import ModelSpec
```

```python
# before
from polisyos.foundry.compiler import compile_surface_policy

# after
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.core.contracts.foundry import CompileRequest
```

## Loader Migration

```python
# before
bundle = load_policy(payload, as_trinity=True)

# after
bundle = load_policy(payload)
```

## Compiler Migration

```python
request = CompileRequest(
    input_kind="trinity",
    policy_ref=trinity_bundle_ref,
    registry_bundle_ref=registry_bundle_ref,
)
result = compile_foundry(store, request)
```

## Operational Notes

- If you cached legacy class instances via pickle, clear long-lived caches after upgrade.
- JSON schema snapshots should be regenerated/checked after rollout.
