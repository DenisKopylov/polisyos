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

## Docs lifecycle removed-reference scan

`check_docs_lifecycle.py` keeps the lifecycle checker and CLI surface. Its removed-stub reference scan is implemented by `docs_lifecycle_reference_scan.py`; the facade supplies the current repository enumerator, reader, selector, finding type, and path formatter through a typed dependency value. This preserves injected test enumerators without mutating scanner module globals. The scan receipt remains scoped to this one check. Excluded, opaque, or malformed inputs continue to produce partial or ambiguous coverage rather than a complete lifecycle-gate claim.

## Directory-health dashboard composition

`directory_health.py` remains the CLI and report facade. Its dashboard metrics and inventory
aggregation live in `directory_health_dashboard.py`; calls receive the active facade dependencies,
so report generation continues to use the same tracked-file, filesystem, contract, and finding
inputs as the CLI and imported API.

## Repository-structure inventory

`repository_structure_phase0.py` retains the CLI, gate composition, and compatibility facade. `repository_structure_phase0_inventory.py` owns the inventory scan; the facade passes its current helpers and policy constants as typed dependencies so existing callers and monkeypatch seams continue to work.
