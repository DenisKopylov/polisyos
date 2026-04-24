# Simulator (`polisyos.lex.simulator`)

`polisyos.lex.simulator` выполняет what-if анализ изменений `NormPack`: mutation,
diff и impact analysis до того, как изменения попадут в основной policy pipeline.
Это безопасный legal sandbox для сравнения baseline и proposed norm bundles.

## Роль в системе

- **Зависит от:** `polisyos.lex.normpack`, `polisyos.core.governance`, `polisyos.ir.norm_pack`
- **Используется в:** policy-design review, governance validation, explicit norm change analysis
- Пакет отделяет legal what-if analysis от production assembly/evaluation path.

## Ключевые концепции

- **Deterministic mutation** — `NormPackMutator` строит новый `pack_id` и mutation trace для reproducible sandbox runs.
- **Structured diff** — `diff_norm_packs()` вычисляет `added/removed/modified/unchanged` plus field-level deltas.
- **Impact analysis** — `NormImpactAnalyzer` запускает governance passes на old/new packs и агрегирует compliance transitions.
- **Persistence surface** — при `persist=True` публикуются `lex.norm_diff` и `lex.norm_impact_report`.
- **Report models** — `NormImpactReport`, `ComplianceDelta` и `AffectedKPI` задают human-facing result surface.

## Public API

| Type/Function                                                                | Description                                            |
| ---------------------------------------------------------------------------- | ------------------------------------------------------ |
| `NormPackMutator`                                                            | Deterministic mutation builder for baseline `NormPack` |
| `MutationIntent`                                                             | Structured description of requested norm changes       |
| `diff_norm_packs()`                                                          | Compute structured diff between old and new packs      |
| `NormDiff`, `NormChange`, `NormChangeType`                                   | Diff result contracts                                  |
| `NormImpactAnalyzer`                                                         | Run governance-based impact analysis over pack deltas  |
| `NormImpactReport`, `ComplianceDelta`, `ComplianceTransition`, `AffectedKPI` | Final impact-report models                             |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 6 Python files
- Exports: 12 symbols in `__init__.py`
- Notable delta: package remains stable, but README is now aligned with the shared template and explicit about diff/impact contracts
