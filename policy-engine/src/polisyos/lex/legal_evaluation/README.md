# Legal Evaluation (`polisyos.lex.legal_evaluation`)

`polisyos.lex.legal_evaluation` compares policy/simulation output with a `NormPack`,
builds `lex.legal_report`, produces change proposals, and provides the bridge
between legal constraints and causal transportability constraints.

## Role in the system

- **Depends on:** `polisyos.lex.normpack`, `polisyos.core.contracts.lex`, `polisyos.ir`, `polisyos.fabric.world`
- **Used by:** policy validation, governance passes, transportability gating, and change-proposal flows
- The package turns norms and observed values into explicit compliance verdicts instead of ad hoc post hoc reasoning.

## Key concepts

- **Evaluator registry** — `LexEvaluatorRegistry` loads built-in and external evaluators by `eval_policy_id`.
- **Context normalization** — `evaluate_legality_impl()` extracts policy source, metrics, and norm context into a unified `LegalContext`.
- **Rule observations** — `context_builder.py` resolves observed values from metrics and policy parameters, with explicit `quality_issues`.
- **Change proposals** — `propose_changes_impl()` generates `policy_patch` or `add_metric` actions for actionable failures.
- **Transport constraints** — `LegalConstraintBridge` and `is_transport_blocked()` connect legal limits to causal-graph/transportability checks.
- **Norm comparison** — `impact_diff.NormImpactAnalyzer` compares two `NormPack` objects,
  runs the selected built-in `legal`/`safety` passes, and persists the diff/report in CAS.
  Each run takes its norms from the compared pack; a same-named key in the
  additional context does not replace them. `passes=None` selects both passes,
  while `passes=()` keeps only the norm diff; unknown pass IDs are rejected.
  The historical schema `1.0` field `affected_kpis` contains candidate impact topics,
  without a measured magnitude or established effect direction. Legacy
  `polisyos.lex.simulator` imports and CLI use this same canonical owner. Reports
  record the configured legal backend and the limit of its evaluated scope in
  `metadata`; these producer records are not verifier-provenance or authority.
  Omitted backend uses the historical stub: its not-implemented
  results do not establish rule compliance. The CLI accepts
  `--legal-backend expr_ast` to evaluate supplied rules assigned to that backend.
  This does not authenticate source law or establish coverage of all rules.
  The current report does not bind the complete comparison context; it remains
  `not_established`, even when a configured backend evaluated a supplied fixture.
  Historical reports without backend metadata remain readable, with backend
  and evaluation scope not established. The omitted writer option retains
  limited 1.0 output, and explicit opt-in 1.1 carries full issued diff and
  report references after readers are upgraded. The canonical
  `load_norm_impact_report()` reader verifies the selected report and its
  `norm_diff` edge, then recomputes the embedded diff and reported issue deltas.
  It cannot establish completeness or authenticity of the originating packs,
  legal issues, or comparison context. Legacy 1.0 ID-only diff references
  remain readable with their issued profile unbound. Newly written reports
  record both producer-declared jurisdictions; 1.1 refuses differing scopes,
  while 1.0 preserves the comparison with an explicit limitation. See
  [the migration guide](../../../../docs/how-to/lex-impact-report-migration.md).

## Public API

| Type/Function                                  | Description                                                      |
| ---------------------------------------------- | ---------------------------------------------------------------- |
| `evaluate_legality_impl()`                     | Main legality evaluation orchestrator                            |
| `propose_changes_impl()`                       | Generate change proposals from evaluation failures               |
| `LegalConstraintBridge`                        | Resolve legal constraints for transportability and causal checks |
| `LegalConstraint`, `LegalConstraintSet`        | Typed legal-constraint models                                    |
| `LegalToDAGMapping`, `LegalToDAGMappingType`   | Mapping contracts from legal constraints to DAG semantics        |
| `ConstraintSeverity`, `is_transport_blocked()` | Severity and fast hard-block helpers                             |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-10-14
- Files: 9 Python files under this package tree
- Exports: 9 symbols in `__init__.py`
- Notable delta: transport-constraint bridge remains a first-class part of the package surface, not just an internal helper
