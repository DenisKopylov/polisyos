# UI-15.docs-ia — Организовать Docs IA по user needs

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [UI-15](../../parents/UI-15.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Existing Docs owner organizes explanatory landing/article IA and canonical links without authoring claim status.

**Предпочтительное решение.** Reuse only an appointed Docs/marketing surface; if absent, stay absent/unallocated; no CMS/second evidence register.

**Граница владельца.** Existing Docs owner writes after allocation and cannot elevate DS11 claims; no new owner assigned.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Recorded allocation, appointed Docs owner, allowed explanatory text and DS11 canonical link/status.

**Выход и consumer.** Approved navigation/copy links to fresh DS11 posture and preserves its meaning/limits.

**Что можно готовить независимо.** Prepare the IA outline independently; actual delivery waits for the recorded allocation decision, an appointed existing Docs owner, and any applicable rights.

**Где результат соединяется с другими.** Join live DS11 status; rendered copy agrees on source/date/limits.

**Positive.** User-needs content helps find evidence without changing claim meaning.

**Distinguishing negative.** Contradictory duplicate, unsupported certification or private evidence is refused.

**Matched removal.** Remove status/link binding with copy intact: audience review detects divergence.

**Граница контекста.** Explanation/navigation, not authority-bearing claim support. Direct source U023 (solution.implementation_steps[2]) assigns the existing Docs surface to present explanatory IA from canonical DS11 posture/status/source/version/date; this card owns the Docs IA/link output and consumes trust-posture, without rendering or authoring Trust claim status.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [UI-15.trust-docs-allocation](../../cards/UI-15/trust-docs-allocation.md) | Only when explanatory Docs delivery is allocated to the existing owner. |
| Composition output (не start gate) [UI-15.trust-posture](../../cards/UI-15/trust-posture.md) | For any evidence/status explanation or canonical link in the selected Docs output; Docs cannot author status. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-15`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This implementation step assigns the explanatory Docs IA/link output to the existing Docs owner; it consumes trust-posture’s canonical DS11 claim/status/source/version/date and cannot author or strengthen that status. Source selectors: solution.implementation_steps[2].
  `solution.implementation_steps[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
