# UI-15.trust-docs-allocation — Записать владельцев Trust Center и Docs IA

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [UI-15](../../parents/UI-15.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The assigned owner-allocation work produces a recorded, content-bound competent-architect decision for the DS11 posture and existing Docs IA split; a missing internal Docs owner is resolved as absent/unallocated with a re-entry trigger, not left as an indefinite external hold.

**Предпочтительное решение.** Within UI-15, prepare the source-qualified proposal, route it through the competent architect’s actual allocation process, and record the decision. Locate/confirm an existing Docs owner as part of this assigned work; if none is appointed, record Docs IA absent/unallocated. Do not appoint a substitute or create a site/CMS.

**Граница владельца.** This card owns the allocation proposal, evidence of the genuine competent-architect decision, and the existing-owner lookup/route. It does not make the architect’s decision, infer DS11 ownership from the task ID, appoint an institutional or Docs owner, or create a Docs platform. Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Source-qualified unique-content split and existing DS11 posture/evidence source.; The competent architect’s actual recorded owner/scope decision, produced through this card’s assigned internal allocation work.; Existing Docs/marketing owner and rights to publish selected source artifacts, if present; owner absence is recorded as absent/unallocated, while genuine external publication rights remain a separate permission input.

**Выход и consumer.** Recorded content-bound architect allocation plus identified existing content owner and rights, or an explicit absent/unallocated Docs IA result with re-entry trigger; no substitute owner.

**Что можно готовить независимо.** Prepare the source-qualified recommendation and owner lookup independently. Keep the card active to obtain and record the competent architect decision; an unanswered internal allocation request is not an external-input hold. No Trust/Docs delivery precedes its required decision, owner and rights.

**Где результат соединяется с другими.** Only a recorded competent-architect decision authorizes the selected owner split. Trust posture may proceed through its own existing owner; Docs IA delivers through an appointed existing Docs owner, otherwise remains absent/unallocated. Genuine external rights remain separately conditional.

**Positive.** Recorded decision names owners, source, unique content and limits.

**Distinguishing negative.** Task ID, old plan or retained marketing text is not owner evidence.

**Matched removal.** Remove allocation but retain page copy: owner/semantic review fails.

**Граница контекста.** This is assigned internal allocation work, not a newly invented product gate or indefinite external blocker. The architect makes the genuine scope decision; the card records it and resolves the missing-owner branch without appointing a substitute.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-15`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Records unique DS11 evidence/download and Docs IA scopes for architect allocation. Source selectors: solution.implementation_steps[0].
  `solution.implementation_steps[0]`
- **execute** — Only a recorded competent architect decision authorizes dispatch. Source selectors: solution.implementation_steps[1].
  `solution.implementation_steps[1]`
- **execute** — Preserves absent/unallocated and re-entry trigger if Docs owner is not appointed. Source selectors: solution.implementation_steps[3].
  `solution.implementation_steps[3]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[1].
  `solution.composition_contracts[1]`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0].
  `solution.acceptance_discriminators[0]`
- **binding** — This source field contributes to trust-docs-allocation's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0], solution.deviation_triggers[1].
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.inputs_to_resolve[0], solution.inputs_to_resolve[1].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
