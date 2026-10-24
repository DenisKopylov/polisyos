# UI-01.currentness-projection — Проецировать только owner-confirmed currentness

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [UI-01](../../parents/UI-01.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** После выбранной material correction свежий ответ показывает scoped LIF-02 reaction с as-of time/reason; historical signature остаётся отдельным фактом.

**Предпочтительное решение.** Прочитать действующий LIF-02 reaction в существующем consumer route; currentness нельзя выводить из signature, digest или badge.

**Граница владельца.** UI-01 только читает LIF-02 output; LIF-02 владеет enrollment/replay/fence/reaction.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Условный LIF-02 evaluation/reaction для affected claim/use, event/as-of time и reason.

**Выход и consumer.** Свежая selected verification response связывает owner reaction с affected claim; unrelated claims остаются current.

**Что можно готовить независимо.** Consumer можно подготовить по agreed interface; Q05 positive остаётся условным до реального LIF-02 output.

**Где результат соединяется с другими.** Собрать с auth-projection только если R18-D12-Q05 выбран; base acceptance возможен с currentness not_established.

**Positive.** После enrolled correction affected claim ограничен с owner reason; unrelated claim current.

**Distinguishing negative.** Старый authentic record не выдаётся за current; hash/caller label/badge не заменяют LIF-02.

**Matched removal.** Убрать fresh currentness read при валидной подписи: stale-current probe проваливается.

**Граница контекста.** Отдельное Q05 свойство, не деление по транспорту; не становится blanket gate для base authentication.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `conditional_acceptance_requirements:composition`: Conditional Q05: actual enrolled-dependency evaluation and scoped reaction with event/as-of time/reason; unrelated claims remain current.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: The R19 R18-D12-Q05 currentness extension is selected for UI-01, and UI-01 claims a fresh current status after a material enrolled correction |
| Composition output (не start gate) [UI-01.auth-projection](../../cards/UI-01/auth-projection.md) | Consume only for the exact composition described here: Собрать с auth-projection только если R18-D12-Q05 выбран; base acceptance возможен с currentness not_established. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[3].
  `solution.composition_contracts[3]`
- **execute** — tasks.json#UI-01.task.r19_extension.question_slices[0] (R18-D12-Q05) value-matches question_ids[0]. Current coverage sends both selectors to this card as binding, but UI-01 preferred-solutions implementation_steps[0..3] cover only authentication/read wiring and do not execute the LIF-02 currentness read; this card owns the fresh selected consumer, so route the missing consumer work as execute. Keep the source condition that base authentication can remain independently acceptable with currentness not_established.
  `task.r19_extension.question_slices[0]` (`R18-D12-Q05`); `task.r19_extension.question_ids[0]` (`R18-D12-Q05`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
