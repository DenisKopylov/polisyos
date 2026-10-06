## [candidate] - 2026-10-06

### Fixed
- `ir`: Isolate causal graph export rows from caller mutations: Cache immutable row preparations and return detached ordinary node and edge dictionaries so caller mutation cannot corrupt later graph exports.

## Compatibility Notes
- The public tuple-of-dictionaries value ABI and graph schema 1.0 are unchanged. Row mutations affect only the caller's detached values.

## Change Classes
- python-public-api

## Supported Surface Classification
- public_stable: polisyos.ir

## Migration Notes
- Keep mutations in the returned row values; use model_copy(update=...) to create a new published graph version.

## Structured Compatibility Changes
- `python-public-api` / `compatible` / public_stable: polisyos.ir.CausalGraphModel export row properties: Causal graph export readers retain tuple/plain-dict values and isolate caller mutations from cached row preparations. (owner: team-ir; version owner: team-ir; deprecation: not_applicable)
