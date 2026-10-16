# tools/quality/validation

Validation ratchets for docs, benchmark contours, CI policies, and quality baselines.

Use the unified entry point:

```bash
polisyos-tools validation --help
```

## Dynamic import inventory

`architecture/imports/dynamic.toml` records source-owned dynamic import patterns. The
`decomposition_preflight.py` gate derives its expected rows from `collect_dynamic_imports`
and rejects missing, stale, or malformed inventory. The collector analyzes syntax and
source bindings without importing or executing the inventoried modules.

For an immutable source-owned `MappingProxyType` with fully known builtin literal keys,
exact .get(...) and subscription lookups follow Python's key equality and duplicate-key
behavior: only the effective value selected by an exact key contributes an importer target. The bounded lookup keys are builtin hashable literals and recursive tuples of those literals.
Mapping membership is a separate source-analysis path and is not broadened by this exact-lookup
change: existing string-membership and tuple-route controls remain unchanged, while the probed
exact-integer-membership guard followed by lookup remains fail-closed because that path has not
established the selected value. Dynamic or unresolved keys, unknown mapping unpack, unhashable
literals, and user-defined key behavior remain ambiguous and do not become an empty/default allowlist. A finite target list is derived
from the selected source-bound importer values; it does not issue or renew owner review
metadata in `dynamic.toml`.
