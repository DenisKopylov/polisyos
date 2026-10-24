# DEB-04.catalog-absence — Проверить отсутствие catalog на границе runtime input

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-04](../../parents/DEB-04.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Removing the canonical catalog from an explicit fixture produces the same typed fail-closed result as the real production loader.

**Предпочтительное решение.** Reuse the production loader with an explicit temporary catalog fixture; remove the actual canonical artifact and exercise the real boundary.

**Граница владельца.** Catalog/discovery runtime owner; no repository-layout inference. Native exact-path lease family; paths unresolved until E02.

**Входы.** Canonical catalog identity and explicit fixture populated by the actual producer.

**Выход и consumer.** Typed missing-catalog refusal from the real loader and a source-qualified test receipt.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh production catalog loader/census consumer exercised by tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Removing the canonical catalog from an explicit fixture produces the same typed fail-closed result as the real production loader.

**Distinguishing negative.** Delete the canonical file while preserving markers/layout; loader must refuse rather than infer absence from directory shape.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Removing the canonical catalog from an explicit fixture produces the same typed fail-closed result as the real production loader.

**Граница контекста.** This validates actual catalog input absence, independent of GY-DEF22’s owner acceptance.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-04 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DEB-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — These fragments specify explicit catalog fixture deletion and real loader refusal.
  `solution.implementation_steps[2]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
