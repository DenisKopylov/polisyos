# DES-07.fresh-owner-readback — Прочитать новую редакцию после пересчёта

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DES-07](../../parents/DES-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Expected-base/CAS and affected dependency closure preserve concurrent/history semantics; a fresh reader shows which revised statements are supported, stale, proposed or unbound after native owner recomputation.

**Предпочтительное решение.** Use existing revision/CAS and LIF/currentness paths; branch on concurrent base changes, recompute only the affected dependency closure and regenerate linked materials without silently overwriting human text. Persist accepted mappings, unresolved edits, supersession and exact reader evidence.

**Граница владельца.** DES-07 owns document-route readback under write:artifact-document-route; native owners retain recomputation/status, DES-06 owns emitted document/schema, and LIF retains currentness/invalidation. Any shared document schema edit is coordinated with DES-06’s single writer. Exact path leases are E02-rebound.

**Входы.** semantic-patch-routing candidate patch and current expected base; actual native-owner recomputation/status outputs; exact rendered carrier/edition from DES-06.; Actual concurrent revision/CAS result and rights permitting fresh retrieval.

**Выход и consumer.** Persisted accepted/unresolved patch and supersession result plus fresh document reader refs showing changed/unbound semantics and recomputed owner evidence; earlier as-known edition remains interpretable.

**Что можно готовить независимо.** Readback and CAS cases can be prepared independently against agreed interfaces; no carrier instance or routed patch must arrive first. A supported/current result still requires actual native recompute output and reader; absence remains unresolved rather than stale green.

**Где результат соединяется с другими.** At actual readback, the fresh authorized document reader (and CNT-09 selected-case consumer where applicable) joins exact carrier identity, routed patch, native owner output and new rendition. No institutional submission/adoption is performed.

**Positive.** A changed threshold appears with its new trial/table; a concurrent edit branches instead of last-write-wins; older permitted edition remains readable without rewriting history.

**Distinguishing negative.** Hash/version labels without actual dependency closure, current parser defaults, stale projection or revised draft-as-adopted policy cannot establish the result.

**Matched removal.** Keep revision labels but remove actual closure or owner-bound recompute consumption; fresh reader detects the missing change or marks result unbound.

**Граница контекста.** This is the consumer checkpoint, not an independent document writer or institutional act. Shared DES-06/07 schema ownership and exact leases must be established from accepted source before implementation.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DES-06.private-policy-documents](../../cards/DES-06/private-policy-documents.md) | `direct:interface_agreement`: Consumes DES-06’s actual edition/shared schema for import and fresh rendition; DES-06 remains the sole shared schema/render writer.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DES-07.carrier-identity](../../cards/DES-07/carrier-identity.md) | Only for the selected same-scope composition described by this card: At actual readback, the fresh authorized document reader (and CNT-09 selected-case consumer where applicable) joins exact carrier identity, routed patch, native owner output and new rendition. No institutional submission/adoption is performed. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [DES-07.semantic-patch-routing](../../cards/DES-07/semantic-patch-routing.md) | Only for the selected same-scope composition described by this card: At actual readback, the fresh authorized document reader (and CNT-09 selected-case consumer where applicable) joins exact carrier identity, routed patch, native owner output and new rendition. No institutional submission/adoption is performed. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **join** — The private revision diff/surface is the final fresh consumer of carrier map, patches and actual owner results.
  `task.surface`
- **join** — R17 revision/edition clause 1 belongs to the fresh-owner-readback checkpoint; actual owner status and historical edition remain source-bound.
  `task.r17_extension.positive`
- **join** — R17 revision/edition clause 3 belongs to the fresh-owner-readback checkpoint; actual owner status and historical edition remain source-bound.
  `task.r17_extension.removal`
- **join** — R17 delivery and quality references concern real closure/current edition/fresh consumers; they are read back only from actual DES-06/07 and native-owner outputs.
  `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.delivery_slices[2]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.product_verification`
- **binding** — Expected-base/dependency closure proves whether changed spans can compose; shared DES-06 interface is a required supplier. The actual native owner recomputes its own result.
  `task.r19_extension.question_slices[1]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[1]`
- **execute** — Expected-base/CAS conflict and dependency closure govern actual joined recomputation and regenerated material without silent overwrite.
  `solution.implementation_steps[3]`
- **execute** — Persist accepted mappings/unresolved edits and show supported/stale/proposed/unbound results to a fresh reader.
  `solution.implementation_steps[4]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
