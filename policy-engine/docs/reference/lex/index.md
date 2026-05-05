# Lex

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Owner: `@lex-owners`
Source of truth: `src/polisyos/lex/**`, `src/polisyos/lex/__init__.py`, `src/polisyos/lex/README.md`, and `tests/unit/lex/**`

`polisyos.lex` is the runtime legal layer for NormPack assembly, legal
evaluation, read-only legal knowledge graph access, and intervention
compilation. Offline corpus preprocessing, SPO extraction, QC, benchmark, and
publish flows are owned by Data Forge legal modules.

## Page Map

| Page                                | Scope                                                                                 | Primary modules                                   |
| ----------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------- |
| [Legal Batch Pipeline](batch-pipeline.md) | Offline SPO extraction, amendment handling, QC, publish flow | `data_forge.domains.legal.batch.*`               |
| [Knowledge](knowledge.md)           | DuckDB/HNSW search surface and legal graph result types                               | `lex.knowledge.*`                                 |
| [NormPack](normpack.md)             | Version-aware reads, legality, diff, mutation, impact analysis                        | `lex.api`, `lex.types`, `lex.simulator.*`         |
| [Interventions](interventions.md)   | Provision mappings, knobs, temporal sequencing, policy bundle inputs                  | `lex.interventions`, `lex.intervention_artifacts` |

## Root Export Surface

The current root facade exports 50 public symbols from `polisyos.lex`.

| Group                                    | Count | Representative exports                                                                                                                             |
| ---------------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Errors                                   | 7     | `LexError`, `LexValidationError`, `LexVersioningError`                                                                                             |
| Versioning and active resolution         | 3     | `ActiveVersionStrategy`, `ActiveVersionResult`, `resolve_active_version`                                                                           |
| NormPack assembly                        | 4     | `NormPackBuildRequest`, `NormPackBudgets`, `assemble_norm_pack`                                                                                    |
| Mutation and impact analysis             | 10    | `MutationIntent`, `NormDiff`, `NormImpactAnalyzer`, `AffectedKPI`                                                                                  |
| Legal evaluation                         | 6     | `LegalEvaluationRequest`, `LegalReportRef`, `evaluate_legality`, `propose_changes`                                                                 |
| Knowledge                                | 1     | `LegalKnowledgeGraph`                                                                                                                              |
| Interventions and temporal policy search | 15    | `LexInterventionCompiler`, `LexProvisionDirective`, `TemporalInterventionSequencer`, `HierarchicalPolicySearchPlan`, `LexProvisionMappingRegistry` |
| Support and provenance                   | 4     | `ChangeProposalRef`, `WorldEventRefLike`, `LexFabricEvidencePath`, `lex_evidence_from_fabric_decision_data`                                        |

## Notes

- The historical plan counted offline build symbols in Lex. Those build symbols
  now live under `polisyos.data_forge.domains.legal`.

- The intervention modules are now first-class public API and are documented on
  their own page instead of being hidden under general NormPack notes.
