# NormPack (`polisyos.lex.normpack`)

`polisyos.lex.normpack` собирает `NormPack` для заданных `jurisdiction`,
`as_of` и optional domain filters. Пакет умеет идти либо через provider path,
либо через локальный claims/provisions pipeline и всегда возвращает
`NormPackBuildResult` с provenance, warnings и детерминированным `pack_id`.

## Роль в системе

- **Зависит от:** `polisyos.lex.corpus`, `polisyos.fabric.claims`, `polisyos.core.components`, `polisyos.ir.norm_pack`
- **Используется в:** `polisyos.lex.legal_evaluation`, `polisyos.lex.simulator`, policy validation flows
- Пакет переводит corpus/provision evidence в executable legal rules для compliance и what-if analysis.

## Ключевые концепции

- **Provider vs pipeline path** — если доступен `NormPackProvider`, пакет может вернуть готовый pack; иначе запускается local assembly pipeline.
- **Source selection** — `select_sources.py` выбирает документы и активные версии через corpus indexes либо temporal fallback из fact log.
- **Claim extraction** — `extract_norm_claims.py` строит `lex.norms.claim_set`, дедуплицирует claims и фиксирует degradation warnings.
- **Applicability windows** — `applicability.py` вычисляет `NormApplicability` по validity intervals claims.
- **Conflict resolution** — competing claims проходят через `fabric.claims.resolve_conflicts`, а не затираются локально.
- **Budgeted assembly** — `max_docs`, `max_provisions` и `max_claims` держат сборку в предсказуемых resource limits.

## Public API

| Type/Function | Description |
|---|---|
| `assemble_norm_pack()` | Main provider-or-pipeline builder for `NormPack` |
| `NormPackBuildRequest`, `NormPackBuildResult` | Input/output contracts for pack assembly |
| `NormPackBudgets` | Resource budgets for doc/provision/claim selection |
| `select_sources.py` | Source and active-version selection logic |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 7 Python files
- Exports: 4 symbols in `__init__.py`
- Notable delta: active-version selection now explicitly documents the `resolve_active_version()` primary path plus fact-log fallback
