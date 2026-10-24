# UI-02.public-record — Выпустить один точный data-only record

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [UI-02](../../parents/UI-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Разрешённый data-only record или typed refusal создаётся из одной exact CAS view; authority остаётся typed-empty без signer predicate, а четыре аудитории читают ту же edition согласно permissions.

**Предпочтительное решение.** Связать public_export → ArtifactRef/CAS → issue event/accepted verifier → фактические readers; переиспользовать закрытый verifier и store.

**Граница владельца.** UI-02 владеет production/projection route; signer appointment и audience/tenant/public-use rights подтверждают native owners. UI-05 Clerk не заменяет DS12.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** GY-PR1a реальный record evidence (GYD-01), exact ArtifactRef/profile, signer policy только для signature band, owner-issued read permissions.

**Выход и consumer.** Typed refusal chronology либо persisted exact-view record с source/authority/audit refs, rule/schema, audience, issue/status times и limits.

**Что можно готовить независимо.** Подготовить refusal route и page checks независимо от signer appointment; bind actual readers на P0.

**Где результат соединяется с другими.** Issue только после applicable PR1a и exact-view/rights gates; PR1b + actual signer mandate требуются только для pilot/signature claim.

**Positive.** До PR1a — refusal chronology; после — permitted exact edition без изобретённой authority.

**Distinguishing negative.** Candidate, wrong view/tenant, pending intent, lost rights, bad signature, absent refs или audience escalation не дают public bytes.

**Matched removal.** Удалить view/owner/audience gate при labels: fresh reader обнаруживает wrong/unauthorized edition.

**Граница контекста.** PUBLIC/REVIEWER/EXPERT/MACHINE — отдельные audiences поверх одной edition; транспорт не создаёт новый owner.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [UI-02.private-egress](../../cards/UI-02/private-egress.md) | Consume only for the exact composition described here: Issue только после applicable PR1a и exact-view/rights gates; PR1b + actual signer mandate требуются только для pilot/signature claim. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [UI-02.placement-rights](../../cards/UI-02/placement-rights.md) | Consume only for the exact composition described here: Issue только после applicable PR1a и exact-view/rights gates; PR1b + actual signer mandate требуются только для pilot/signature claim. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [UI-04.event-history](../../cards/UI-04/event-history.md) | Only for the selected managed-correction/current-status path: consume the exact persisted event/history output; it is not a prerequisite for unrelated PR1a/refusal preparation. |
| Composition output (не start gate) [UI-04.feed-projection](../../cards/UI-04/feed-projection.md) | Selected correction/current-status surface reads the same-generation event/feed with audience/currentness constraints; no global UI-04 completion gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Enumerated surfaces are readers of one canonical card result, not separate transport owners. Source selectors: task.surface[0], task.surface[1], task.surface[2], task.surface[3], task.surface[4], task.surface[5].
  `task.surface[0]`; `task.surface[1]`; `task.surface[2]`; `task.surface[3]`; `task.surface[4]`; `task.surface[5]`
- **binding** — This source field contributes to public-record's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0], solution.deviation_triggers[1], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, task.r14_extension.detail, task.r14_extension.product_verification, task.r14_extension.quality_ref, task.r14_extension.requirement.
  `task.r14_extension.requirement`; `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **execute** — Advances the same native owner result; exact path/lease resolves at P0. Source selectors: solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[4], solution.implementation_steps[5], solution.implementation_steps[6].
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[4]`; `solution.implementation_steps[5]`; `solution.implementation_steps[6]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[3], solution.composition_contracts[4].
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[3]`; `solution.composition_contracts[4]`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0], solution.acceptance_discriminators[3], solution.acceptance_discriminators[4], solution.acceptance_discriminators[5], solution.acceptance_discriminators[6], solution.acceptance_discriminators[7].
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[3]`; `solution.acceptance_discriminators[4]`; `solution.acceptance_discriminators[5]`; `solution.acceptance_discriminators[6]`; `solution.acceptance_discriminators[7]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.inputs_to_resolve[0], solution.inputs_to_resolve[1].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`
- **binding** — tasks.json#UI-02.task.r19_extension.question_slices[0] value-matches question_ids[0]. Public-record applies this constraint in the existing exact-record projection at preferred-solutions implementation_steps[1..2,5]. Keep one edition across the four actual authorized audience readers; do not substitute UI-05 Clerk or transport parity for audience projection.
  `task.r19_extension.question_slices[0]` (`R18-D12-Q04`); `task.r19_extension.question_ids[0]` (`R18-D12-Q04`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[1]` — Keep the exact prior issue and its audience-specific rendition as the historical edition while displaying a separate current-status link. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Apply the selected PUBLIC/MACHINE audience projection to the same issued record on each enumerated export/prior-projection reader. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[3]` — Preserve the exact issued bytes/edition and audience view as historical while linking a distinct derivative or correction status. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — The old public view retains its exact permitted edition, links the authorized correction, and states only known copy-control limits. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
