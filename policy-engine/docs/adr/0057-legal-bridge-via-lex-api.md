# ADR-0057: Legal bridge via lex/api.py, not separate legal_graph/ module

## Status
Proposed

## Date
2026-02-28

## Context
The scientist workflow requires legal constraint information (e.g., jurisdiction
applicability, regulatory restrictions) when evaluating policy interventions.
Early prototypes placed this logic in a standalone `legal_graph/` module with its
own data model. This created a parallel abstraction that duplicated routing,
serialisation, and error-handling already present in the `lex` subsystem. The
`lex/api.py` module already exposes a stable interface for legal evaluations and
transport constraints.

## Decision
1. Expose all legal bridge functionality through `lex/api.py` endpoints and
   helper functions rather than introducing a separate `legal_graph/` module.
2. Add a `transport_constraints` sub-module under `lex/legal_evaluation/` for
   jurisdiction-specific transport feasibility checks.
3. Scientist nodes that need legal information must import from `polisyos.lex`
   only, never from an ad-hoc legal module.

## Consequences
### Positive
- Single source of truth for legal evaluation logic reduces the risk of
  divergent legal interpretations across modules.
- Leverages the existing lex API's authentication, caching, and error handling
  without reimplementation.

### Negative
- The lex module becomes a wider dependency, and changes to its API surface may
  have broader blast radius across scientist and governance passes.
- Legal graph queries that could benefit from a dedicated graph store must now be
  routed through lex, adding an indirection layer.
