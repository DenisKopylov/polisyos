# UI-15.trust-posture — Проецировать DS11 evidence posture

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [UI-15](../../parents/UI-15.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Authority-bearing Trust claims/downloads resolve from existing DS11 typed posture/bound evidence; explanation cannot strengthen status.

**Предпочтительное решение.** Reuse DS11 Trust/MACHINE posture and approved projection; no second claim register/publisher/history/CMS.

**Граница владельца.** DS11 claim owner controls status; UI-15 projects only after allocation and publication rights.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Recorded allocation, DS11 typed posture/MACHINE artifact, evidence/status/source/version/date and rights.

**Выход и consumer.** Fresh public Trust projection/download with supported/planned/blocked posture, date/source and canonical Docs link.

**Что можно готовить независимо.** Prepare the reader contract independently; actual rendering waits for owner allocation and rights binding.

**Где результат соединяется с другими.** Joins allocation and DOCS link; both display the same live DS11 posture/source.

**Positive.** Every claim has bound evidence or explicit planned/blocked posture with source/version/date.

**Distinguishing negative.** Unsupported certification, stale copy, signature-as-policy-authority or private evidence is never supported.

**Matched removal.** Remove status binding with copy intact: live evidence/semantic review rejects.

**Граница контекста.** Projection cannot sign or upgrade authority.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [UI-15.trust-docs-allocation](../../cards/UI-15/trust-docs-allocation.md) | Actual delivery requires its competent native scope allocation; independent reader preparation may precede it. Docs IA absence does not suppress supported DS11 posture. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `UI-15`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.inputs_to_resolve[2].
  `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
