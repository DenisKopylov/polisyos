# Lex NormPack

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Owner: `@lex-owners`
Source of truth: `src/polisyos/lex/api.py`, `src/polisyos/lex/types.py`, `src/polisyos/lex/errors.py`, `src/polisyos/lex/normpack/diff.py`, `src/polisyos/lex/legal_evaluation/impact_diff.py`, compatibility facades under `src/polisyos/lex/simulator/`, and `tests/unit/lex/**`

This page covers the public Lex API for the stage flow `ingest -> structure -> version index ->
normpack -> legal evaluation`: ingest legal documents, structure provision anchors, resolve active
versions, assemble `NormPack` snapshots, and evaluate or simulate legal changes against those
snapshots.

## Pipeline Surface

| Layer                       | Main contracts                                                             |
| --------------------------- | -------------------------------------------------------------------------- |
| Source metadata and options | `LegalDocSource`, `LexIngestOptions`, `LexStructureOptions`                |
| Versioning                  | `LexVersionIndexOptions`, `ActiveVersionStrategy`, `ActiveVersionResult`   |
| NormPack assembly           | `NormPackBuildRequest`, `NormPackBuildResult`, `NormPackBudgets`           |
| Mutation and diff           | `MutationIntent`, `NormChange`, `NormDiff`, `diff_norm_packs`              |
| Impact analysis             | `NormImpactAnalyzer`, `NormImpactReport`, `ComplianceDelta`, `AffectedKPI` |
| Legality evaluation         | `LegalEvaluationRequest`, `LegalReportRef`, `ChangeProposalRef`            |

## Top-Level API

::: polisyos.lex.api

::: polisyos.lex.types

::: polisyos.lex.errors

## Mutation And Impact

::: polisyos.lex.simulator.mutator

::: polisyos.lex.normpack.diff

::: polisyos.lex.legal_evaluation.impact_diff

The former `polisyos.lex.simulator.diff`, `report`, and `engine` modules remain narrow
compatibility facades that re-export these canonical owners.
