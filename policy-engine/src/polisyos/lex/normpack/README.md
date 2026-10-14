# NormPack (`polisyos.lex.normpack`)

`polisyos.lex.normpack` собирает `NormPack` для заданных `jurisdiction`,
`as_of` и optional domain filters. Пакет умеет идти либо через provider path,
либо через локальный claims/provisions pipeline и всегда возвращает
`NormPackBuildResult` с provenance, warnings и детерминированным `pack_id`.

## Роль в системе

- **Зависит от:** `polisyos.data_forge.read_api.legal`, `polisyos.fabric.claims`, `polisyos.core.components`, `polisyos.ir.loading.norm_pack`
- **Используется в:** `polisyos.lex.legal_evaluation`, `polisyos.lex.simulator`, policy validation flows
- Пакет переводит corpus/provision evidence в executable legal rules для compliance и what-if analysis.

## Ключевые концепции

- **Provider vs pipeline path** — если доступен `NormPackProvider`, пакет может вернуть готовый pack; иначе запускается local assembly pipeline.
- **Source selection** — `select_sources.py` выбирает документы и активные версии через Data Forge corpus indexes либо temporal fallback из fact log.
- **Claim extraction** — `extract_norm_claims.py` строит `lex.norms.claim_set`, дедуплицирует claims и фиксирует degradation warnings.
- **Applicability windows** — `applicability.py` вычисляет `NormApplicability` по validity intervals claims.
- **Conflict resolution** — competing claims проходят через `fabric.claims.resolve_conflicts`, а не затираются локально.
- **Budgeted assembly** — `max_docs`, `max_provisions` и `max_claims` держат сборку в предсказуемых resource limits.
- **Legal authority requirements** — W7.B authority evaluation consumes
  `polisyos.legal_requirement.LegalAuthorityRequirementSpec`; broad
  jurisdiction/topic hits remain `context_only` until claim-level competence
  facets satisfy the compiled requirement.

## Public API

| Type/Function                                 | Description                                                    |
| --------------------------------------------- | -------------------------------------------------------------- |
| `assemble_norm_pack()`                        | Main provider-or-pipeline builder for `NormPack`               |
| `NormPackBuildRequest`, `NormPackBuildResult` | Input/output contracts for pack assembly                       |
| `NormPackBudgets`                             | Resource budgets for doc/provision/claim selection             |
| `select_sources.py`                           | Source and active-version selection logic                      |
| `legal_authority.py`                          | Claim-level authority adapter over compiled legal requirements |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Package files: follow the source tree at `src/polisyos/lex/normpack/`.
- Public exports: `src/polisyos/lex/normpack/__init__.py` is the canonical export list.
- The package-layout and export pointers were checked at source revision
  `36ac90f829b95e9874c5340fc2f1d0e595adf6d7` on 2026-10-14. The provider and
  runtime behavior described above was not executed or revalidated here; no
  deployment was observed.
- Historical note (2026-05-02): active-version selection was documented as
  going through `polisyos.data_forge.read_api.legal` plus fact-log fallback.
