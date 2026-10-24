# CAP-05.legal-applicability — Resolve legal competence, scope, and time

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CAP-05](../../parents/CAP-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Legal force is limited to a competent issuer, exact jurisdiction/parties/provision and supported effective/transition scope.

**Предпочтительное решение.** Pass the verified relation and actual issuer/delegation/notice/recipient evidence to the existing Lex applicability owner, resolving only the selected jurisdiction, parties, provision and publication/effective/transition times. Keep unsupported applicability explicit; do not create another legal-authority service. Anchors: lex/normpack/applicability.py; data_forge/domains/legal/source_relation.py:require_legal_source_relation_verification.

**Граница владельца.** Existing Lex applicability and actual-act owner; CNT-04 supplies human/institutional determinations. Parent native lease family: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Checkpoint-1 relation, authentic act/notice/recipient, issuer/delegation evidence, publication/effective/known times.

**Выход и consumer.** Versioned legal applicability/actual-act evidence with partial scope and uncertainty.

**Что можно готовить независимо.** CNT-04 obtains the actual act, notice, recipient, competence and legal review; no CAP code invents them.

**Где результат соединяется с другими.** Join CAP-04/LIF-02 only when current law/change tracking is claimed.

**Positive.** Partial commencement or saving clause changes only the verified cohort and time.

**Distinguishing negative.** Draft, signature-only, latest-arrival, wrong recipient or unknown jurisdiction does not establish effect.

**Matched removal.** Remove competence/content/applicability check while labels remain; fresh protected reader refuses.

**Граница контекста.** Keep one jurisdiction-specific legal relation vertical: the R14/R17/R19 cases are variants of exact source relation, competence/applicability, and time-scoped consumer meaning. Sequencing reduces simultaneous legal contexts while preserving one native Lex relation owner and the full composed legal proof. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/jurisdiction rebind where relevant; no new start gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-04](../../parents/CNT-04.md) | `conditional_acceptance_requirements:composition`: When legal source use is claimed, consume CNT-04’s selected jurisdiction/source and source-qualified law/version/effect/applicability premises: bind the official relation, resolve competent act/scope/time, then pass only the supported premise to the selected consumer. Missing premises remain explicit.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: legal source use is claimed |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-05`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Competent act, issuer/jurisdiction/party scope and effective/transition/correction times remain with existing legal/institutional owners.
  `task.migration`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[5]`; `task.r19_extension.question_slices[6]`; `task.r19_extension.question_slices[7]`; `task.r19_extension.question_slices[9]`; `task.r19_extension.question_slices[11]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`; `task.r19_extension.question_ids[10]`; `task.r19_extension.question_ids[11]`; `solution.implementation_steps[2]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
