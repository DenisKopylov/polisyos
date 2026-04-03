# Lex
Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

`polisyos.lex` is the legal-text layer: it ingests source acts, resolves active
versions, assembles `NormPack` snapshots, builds a searchable knowledge graph,
and compiles legal interventions into policy-ready contracts.

## Page Map

| Page | Scope | Primary modules |
|------|-------|-----------------|
| [Batch Pipeline](batch-pipeline.md) | SPO extraction QC, amendment detection, hallucination checks, temporal resolution | `lex.batch.*` |
| [Knowledge](knowledge.md) | DuckDB/HNSW search surface and legal graph result types | `lex.knowledge.*` |
| [NormPack](normpack.md) | Ingest, structure, versioning, legality, diff, mutation, impact analysis | `lex.api`, `lex.types`, `lex.simulator.*` |
| [Interventions](interventions.md) | Provision mappings, knobs, temporal sequencing, policy bundle inputs | `lex.interventions`, `lex.intervention_artifacts` |

## Root Export Surface

The current root facade exports 58 public symbols from `polisyos.lex`.

| Group | Count | Representative exports |
|------|-------|------------------------|
| Errors | 7 | `LexError`, `LexValidationError`, `LexVersioningError` |
| Ingest and structure | 6 | `LexIngestOptions`, `LexStructureResult`, `ingest_legal_doc_bytes` |
| Versioning and active resolution | 6 | `ActiveVersionStrategy`, `ActiveVersionResult`, `resolve_active_version` |
| NormPack assembly | 4 | `NormPackBuildRequest`, `NormPackBudgets`, `assemble_norm_pack` |
| Mutation and impact analysis | 10 | `MutationIntent`, `NormDiff`, `NormImpactAnalyzer`, `AffectedKPI` |
| Legal evaluation | 6 | `LegalEvaluationRequest`, `LegalReportRef`, `evaluate_legality`, `propose_changes` |
| Knowledge | 1 | `LegalKnowledgeGraph` |
| Interventions and temporal policy search | 15 | `LexInterventionCompiler`, `LexProvisionDirective`, `TemporalInterventionSequencer`, `HierarchicalPolicySearchPlan`, `LexProvisionMappingRegistry` |
| Support types | 3 | `LegalDocSource`, `ChangeProposalRef`, `WorldEventRefLike` |

## Notes

- The historical plan counted 65 exports, but the current `polisyos.lex` facade
  exports 58 symbols.
- The intervention modules are now first-class public API and are documented on
  their own page instead of being hidden under general NormPack notes.
