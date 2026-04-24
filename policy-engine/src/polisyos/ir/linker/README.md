# Linker (`polisyos.ir.linker`)

`polisyos.ir.linker` связывает `TrinityBundle` с registry surface и превращает
декларативный policy payload в `LinkedTrinityBundle` с binding diagnostics,
canonical digests и typed issue report. Это последняя контрактная стадия перед
compile/execute в `foundry` и перед governance preflight в `scientist`.

## Роль в системе

- **Зависит от:** `polisyos.ir.trinity`, `polisyos.ir.kernel`, `polisyos.ir.governance`
- **Используется в:** `polisyos.core.compiler`, `polisyos.foundry`, `polisyos.scientist`
- Linker превращает static IR contracts в runtime-ready bindings, не исполняя сами механизмы.

## Ключевые концепции

- **Linked bundle** — `LinkedTrinityBundle` сохраняет исходный bundle, bindings и digests.
- **Typed diagnostics** — `LinkReport` и `LinkIssue` отделяют errors, warnings и info notes.
- **Registry validation** — linker проверяет mechanism ids, params, slots, metrics, constraints и selector fields.
- **Canonical digests** — report включает registry and bundle hashes, если канонизация возможна.
- **Applicability refs** — helper из `types.py` проверяет actor/concept/jurisdiction references.

## Public API

| Type/Function                                | Description                                                          |
| -------------------------------------------- | -------------------------------------------------------------------- |
| `link_trinity()`                             | Основная функция линковки Trinity bundle against registries          |
| `LinkedIntervention`                         | Нормализованный linked view одного intervention                      |
| `TrinityBindings`                            | Aggregated bindings for slots, params and mechanisms                 |
| `LinkedTrinityBundle`                        | Result object для downstream compile/runtime use                     |
| `LinkIssue`, `LinkIssueCode`, `LinkSeverity` | Typed issue protocol                                                 |
| `LinkReport`                                 | Сводка validation outcome и digests                                  |
| `validate_norm_applicability_refs()`         | Проверка norm applicability references вне основного linker pipeline |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 9 Python files
- Exports: 9 public names in `__init__.py`
- Delta status: код линкера стабилен; README обновлен под текущий registry/observation-aware Trinity surface
