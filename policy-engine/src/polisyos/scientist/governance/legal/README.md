# Legal validation backends

This package hosts pluggable rule evaluation backends for the legal validation pass.

- `RuleBackend` defines the protocol contract for evaluators.
- `StubBackend` is a Phase 10 reference implementation that returns
  INFO-level "not implemented" issues for all norms.

Future phases will add AST/LLM-based evaluators without changing the pass.
