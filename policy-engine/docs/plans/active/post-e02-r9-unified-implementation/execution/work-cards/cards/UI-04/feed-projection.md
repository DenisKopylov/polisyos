# UI-04.feed-projection — Проецировать общий DS13 feed/history

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [UI-04](../../parents/UI-04.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Fresh browser/API/client/CLI/MACHINE/audit readers строят одну ordered lineage из persisted events и UI-03 identity, включая “this case” versus “new evidence”.

**Предпочтительное решение.** Переиспользовать governed-projection waist и общий event source; regulator feed — отдельное условие.

**Граница владельца.** UI-04 owns generic DS13 feed/history consumer; generated/client/locale/accessibility owners остаются native owners.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Persisted UI-04 events, UI-03 index, accepted locale/audience rules.

**Выход и consumer.** Fresh read-only feed с exact parent, supersession/revocation/learning, ordered times и reconstructable MACHINE refs.

**Что можно готовить независимо.** Prepare the consumer against the agreed event contract independently; actual feed composition joins event-history output and selected rights/currentness at the serving effect.

**Где результат соединяется с другими.** Ждёт event source; joins selected rights/currentness result. Regulator parity не заменяет generic feed.

**Positive.** Свежий feed показывает тот же event/parent/authority/time meaning на commissioned surfaces; accessibility review оценивает реальный текст.

**Distinguishing negative.** Stale feed, omitted learning, meaning-changing translation, inaccessible controls или hidden lineage не проходит.

**Matched removal.** Удалить event-to-feed join при intact labels: producer→persisted event→consumer witness fails.

**Граница контекста.** Один feed across transports; bind en primary/uk translation/ru legacy-frozen по принятому locale contract.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [UI-03.canonical-case-index](../../cards/UI-03/canonical-case-index.md) | `direct:interface_agreement; acceptance:composition`: Canonical case identity/snapshot for generic DS13 feed.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [UI-04.event-history](../../cards/UI-04/event-history.md) | Consume only for the exact composition described here: Ждёт event source; joins selected rights/currentness result. Regulator parity не заменяет generic feed. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [UI-04.placement-currentness](../../cards/UI-04/placement-currentness.md) | Consume only for the exact composition described here: Ждёт event source; joins selected rights/currentness result. Regulator parity не заменяет generic feed. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Enumerated surfaces are readers of one canonical card result, not separate transport owners. Source selectors: task.surface[0], task.surface[1], task.surface[2], task.surface[3].
  `task.surface[0]`; `task.surface[1]`; `task.surface[2]`; `task.surface[3]`
- **binding** — This source field contributes to feed-projection's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: task.locale_scope_reconciliation.authority, task.locale_scope_reconciliation.governing_contract, task.locale_scope_reconciliation.original, task.locale_scope_reconciliation.required_action, task.retained_criteria_dispositions[2].property.
  `task.retained_criteria_dispositions[2].property`; `task.locale_scope_reconciliation.original`; `task.locale_scope_reconciliation.governing_contract`; `task.locale_scope_reconciliation.required_action`; `task.locale_scope_reconciliation.authority`
- **execute** — Renders same event lineage and checks real accessibility/locale semantics on fresh feed/history reader. Source selectors: solution.implementation_steps[3], solution.implementation_steps[4], solution.implementation_steps[5].
  `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.implementation_steps[5]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[3].
  `solution.composition_contracts[3]`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[3], solution.acceptance_discriminators[4], solution.acceptance_discriminators[5].
  `solution.acceptance_discriminators[3]`; `solution.acceptance_discriminators[4]`; `solution.acceptance_discriminators[5]`
- **binding** — tasks.json#UI-04.task.r19_extension.question_slices[0] value-matches question_ids[0]. Current destination/role are correct: feed-projection's existing implementation steps 3..5 render the selected locale/history reader, while this slice binds that read to the exact edition/rendition lineage and forbids semantic-parity-by-locale-badge.
  `task.r19_extension.question_slices[0]` (`R18-D12-Q04`); `task.r19_extension.question_ids[0]` (`R18-D12-Q04`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[1]` — Fresh history/feed read renders the persisted event and distinguishes it from the current claim state. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Apply the same allowed/withheld outcome on the actual selected history/API/audit event projection readers. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[3]` — Fresh history reader resolves the addressed edition and correction while leaving old bytes immutable; receipt is not adoption. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — Render the linked events only to the authorized audience with checked/disputed status distinct. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[5]` — Project the attributed correction/supersession against the old policy edition on the fresh history reader. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
