# ADR-0033: JSON-Serializable Mechanism Families Only

## Status
Proposed

## Date
2026-02-28

## Context
Phase 10 GCM (Graphical Causal Model) fitting assigns functional mechanisms to
each node in a structural causal model. These mechanisms must be persistable as
CAS artifacts for reproducibility (Law H: every artifact must be content-addressed
and deterministically reproducible).

Pickle-based and closure-based mechanism serialization breaks reproducibility:
pickle is Python-version-dependent, non-deterministic, and opaque to auditing.
Closures capture mutable state that cannot be content-addressed.

## Decision
1. Only **JSON-serializable mechanism families** are allowed in GCM artifacts.
2. `NodeMechanism.family_params` must be a **flat dict of JSON primitives**
   (str, int, float, bool, None, and lists/dicts thereof).
3. Mechanism families are identified by a string `family_name` that maps to a
   deterministic reconstruction function in the method registry.
4. Fitted state (e.g., regression coefficients, kernel parameters) is stored
   as numeric arrays in `family_params`, not as opaque binary blobs.
5. The `gcm_fit` method validates JSON-serializability before persisting the
   `StructuralCausalModelSpec` artifact.

## Consequences
### Positive
- Deterministic mechanism persistence: same `family_name` + `family_params`
  always reconstructs the identical mechanism.
- CAS content-addressing works correctly since JSON serialization is stable.
- Mechanisms are human-readable and auditable in artifact inspection.

### Negative
- Cannot store complex fitted objects (e.g., sklearn pipelines, neural networks)
  directly; requires decomposition into parameter dictionaries.
- Custom mechanism families must implement a `to_params()` / `from_params()`
  protocol.
