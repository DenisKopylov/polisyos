# CAP-05.legal-applicability — Resolve legal competence, scope, and time

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CAP-05](../../parents/CAP-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Legal force is limited to a competent issuer, exact jurisdiction/parties/provision and supported effective/transition scope.

**Предпочтительное решение.** Pass the verified relation and actual issuer/delegation/notice/recipient evidence to the existing Lex applicability owner, resolving only the selected jurisdiction, parties, provision and publication/effective/transition times. Keep unsupported applicability explicit; do not create another legal-authority service. Anchors: lex/normpack/applicability.py; data_forge/domains/legal/source_relation.py:require_legal_source_relation_verification.

**Граница владельца.** Existing Lex applicability and actual-act owner; CNT-04 supplies human/institutional determinations. Parent native lease family: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** CAP-05.official-source exact artifact/root/version-bound verified source relation, original-language/translation occurrence and citation; actual issuer/delegation and act/notice/recipient evidence only where the selected legal-effect claim requires them; publication/effective/known times.

**Выход и consumer.** Versioned legal applicability/actual-act evidence with partial scope and uncertainty.

**Что можно готовить независимо.** CNT-04 obtains the actual act, notice, recipient, competence and legal review; no CAP code invents them.

**Где результат соединяется с другими.** Consume official-source relation and claim-type grounds at the native applicability owner, producing the exact scope/time/competence premise for legal-consumer. Join CAP-04/LIF-02 only when current law/change tracking is claimed; a source-text claim does not invent a legal-effect premise.

**Positive.** Partial commencement or saving clause changes only the verified cohort and time.

**Distinguishing negative.** Draft, signature-only, latest-arrival, wrong recipient or unknown jurisdiction does not establish effect.

**Matched removal.** Remove competence/content/applicability check while labels remain; fresh protected reader refuses.

**Граница контекста.** Keep one jurisdiction-specific legal relation vertical: the R14/R17/R19 cases are variants of exact source relation, competence/applicability, and time-scoped consumer meaning. Sequencing reduces simultaneous legal contexts while preserving one native Lex relation owner and the full composed legal proof. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/jurisdiction rebind where relevant; no new start gate.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-04](../../parents/CNT-04.md) | `conditional_acceptance_requirements:composition`: When legal source use is claimed, consume CNT-04’s selected jurisdiction/source and source-qualified law/version/effect/applicability premises: bind the official relation, resolve competent act/scope/time, then pass only the supported premise to the selected consumer. Missing premises remain explicit.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: legal source use is claimed |
| Composition output (не start gate) [CAP-05.official-source](../../cards/CAP-05/official-source.md) | For the selected law/applicability use, consume the exact verified official-source relation and artifact/version/language/citation binding. Relation authenticity alone cannot establish competence or applicability; preparation against the interface remains independent. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Competent act, issuer/jurisdiction/party scope and effective/transition/correction times remain with existing legal/institutional owners.
  `task.migration`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `solution.implementation_steps[2]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`
- **execute** — Current route remains primary for party/jurisdiction/provision/act applicability; bind the exact source relation first and limit Party A evidence to Party A.
  `task.r19_extension.question_slices[0]` (`R18-D04-Q01`); `task.r19_extension.question_ids[0]` (`R18-D04-Q01`)
- **execute** — Current route remains primary for actual order/status, competence, addressee, proceeding, and stay scope; only the named case scope can change.
  `task.r19_extension.question_slices[2]` (`R18-D04-Q03`); `task.r19_extension.question_ids[2]` (`R18-D04-Q03`)
- **execute** — Current route matches: distinguish original act, notice, recipient service, and delegation evidence before assigning legal effect.
  `task.r19_extension.question_slices[3]` (`R18-D04-Q04`); `task.r19_extension.question_ids[3]` (`R18-D04-Q04`)
- **execute** — Current route remains primary for party/reservation/implementation status and resulting treaty applicability; bind the exact official text/version/source family as a distinct input, and never infer force from source_type.
  `task.r19_extension.question_slices[4]` (`R18-D04-Q05`); `task.r19_extension.question_ids[4]` (`R18-D04-Q05`)
- **execute** — Current route matches: resolve authenticated correction/repeal/act effect, interval, saving scope, and receipt timeline without applying drafts or arrival order globally.
  `task.r19_extension.question_slices[5]` (`R18-D04-Q06`); `task.r19_extension.question_ids[5]` (`R18-D04-Q06`)
- **execute** — Current route matches: verify actual act content, issuer competence, jurisdiction, and effective scope; publication/signature/arrival time is not legal effect.
  `task.r19_extension.question_slices[6]` (`R18-D22-Q01`); `task.r19_extension.question_ids[10]` (`R18-D22-Q01`)
- **execute** — Current route matches: resolve source-specific competence and overlapping legal scope; partial effective scope preserves only the verified subset.
  `task.r19_extension.question_slices[9]` (`R18-D18-Q02`); `task.r19_extension.question_ids[7]` (`R18-D18-Q02`)
- **execute** — Current route matches: verify foreign-law source, act/version, local jurisdictional scope, and effective time; origin publication alone does not prove local commencement.
  `task.r19_extension.question_slices[11]` (`R18-D18-Q04`); `task.r19_extension.question_ids[9]` (`R18-D18-Q04`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[1]` — For a selected legal-effect claim, resolve applicability from the verified original/translation relation and keep translation uncertainty explicit; source authenticity alone does not prove effect. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[7]` — Only for that selected authority premise, resolve the admitted act’s competence and institution/role/scope/time; pass a bounded premise to the consumer. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[8]` — For legal-effect/applicability claims, resolve competence and exact scope/time; source labels alone cannot support the claim. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[10]` — Resolve competent issuer/jurisdiction/effective scope only when the claim asserts legal force; retain scientific and measurement grounds on their own evidence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
