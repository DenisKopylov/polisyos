# CAP-05.legal-consumer — Apply relation to the selected legal consumer

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [CAP-05](../../parents/CAP-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only the exact supported legal premise affects the selected recommendation, with unresolved law left limited/contested.

**Предпочтительное решение.** Feed the exact supported law/version/applicability premise and currentness outcome, when selected, to the native CNT-09/DES-05 legal consumer; preserve claim-type grounds, translation challenges and unresolved limits at the fresh audit/projection. Causal/measurement grounds remain their own evidence. Anchors: lex/normpack/applicability.py; ir/loading/citations.py:CitationRef; scientist/validation/decision_validity.py:read_current_projection.

**Граница владельца.** DES-05 generic interpretation composition and CNT-09 selected case consumer. Parent native lease family: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Verified CAP-05 relation, selected claim/lever, legal as-of cut, and CAP-04 currentness outcome where applicable.

**Выход и consumer.** Fresh consumer decision and authorized audit/public projection with status/time basis.

**Что можно готовить независимо.** Agree consumer interface and claim type; scientific/causal claims retain their own evidence grounds.

**Где результат соединяется с другими.** Compose legal source, actual act, and currentness receipts at a fresh consumer; no legal-authority-by-adjacency.

**Positive.** Only supported jurisdiction/time premises change the selected branch.

**Distinguishing negative.** Late correction, wrong scope, or legal-source metadata used for causal evidence limits/refuses.

**Matched removal.** Remove relation/currentness input but retain recommendation markers; selected consumer cannot pass.

**Граница контекста.** Keep one jurisdiction-specific legal relation vertical: the R14/R17/R19 cases are variants of exact source relation, competence/applicability, and time-scoped consumer meaning. Sequencing reduces simultaneous legal contexts while preserving one native Lex relation owner and the full composed legal proof. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/jurisdiction rebind where relevant; no new start gate.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume content/use admission at relation and selected consumer; applicability remains competent owner.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-04](../../parents/CAP-04.md) | `acceptance:composition`: Only when the selected legal claim asserts current law/change tracking: consume the qualified CAP-04/LIF-02 currentness outcome at the fresh legal consumer. An as-of-only relation stays explicitly scoped and does not acquire an event-chain gate.<br>Source: `task.acceptance_dependencies[2]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-04](../../parents/CNT-04.md) | `conditional_acceptance_requirements:composition`: When legal source use is claimed, consume CNT-04’s selected jurisdiction/source and source-qualified law/version/effect/applicability premises: bind the official relation, resolve competent act/scope/time, then pass only the supported premise to the selected consumer. Missing premises remain explicit.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: legal source use is claimed |
| Composition output (не start gate) [CAP-05.legal-applicability](../../cards/CAP-05/legal-applicability.md) | For a selected legal-effect/applicability claim, consume this exact scope/time/competence result, including limited/contested premises. A source-text/citation-only use retains its narrower grounds and does not require an inapplicable legal-effect decision. |
| Composition output (не start gate) [CAP-05.official-source](../../cards/CAP-05/official-source.md) | Consume the selected verified source relation, exact artifact/version/citation and original/translation occurrence supporting this legal use; legal-effect claims additionally consume legal-applicability. No unverified relation is promoted by a consumer. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — DES-05/CNT-09 selected consumer applies only supported premise; law does not replace causal/measurement grounds.
  `solution.implementation_steps[3]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[3]`
- **execute** — Current route is legal-applicability, but the slice’s controlling condition is consumer-side: verify mandate only when authority is actually a premise of the selected claim, never as a blanket gate.
  `task.r19_extension.question_slices[7]` (`R18-D22-Q04`); `task.r19_extension.question_ids[11]` (`R18-D22-Q04`)
- **execute** — Current route matches: keep legal-source meaning/applicability distinct from citation metadata and apply only the supported exact version/scope to the selected claim.
  `task.r19_extension.question_slices[8]` (`R18-D18-Q01`); `task.r19_extension.question_ids[6]` (`R18-D18-Q01`)
- **execute** — Current route matches: this is a consumer boundary—require legal competence/applicability for legal premises only and do not generalize that rule to scientific evidence.
  `task.r19_extension.question_slices[10]` (`R18-D18-Q03`); `task.r19_extension.question_ids[8]` (`R18-D18-Q03`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — For a selected legal-use claim, apply only the supported Party A premise; leave unmatched parties limited rather than widening the recommendation. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[1]` — When the selected claim relies on translated text, carry translation uncertainty into the fresh consumer and do not promote candidate extraction to a legal premise. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Apply a stay only to the named supported case/scope; appeal or referral without a qualifying order/effect rule cannot change the selected claim. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[3]` — For a selected legal-effect claim, consume only the supported publication/recipient/delegation relation; signature alone cannot support the use. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — Only the resulting supported party/relation premise may affect the selected legal claim; otherwise preserve limited status. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[5]` — A supported retroactive correction changes only the covered provision/cohort and effective interval in the selected fresh claim. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[6]` — Only the act-supported institution/role/scope/time may update the selected legal claim. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[9]` — Apply the partial supported scope only to the matching selected claim; draft/arrival order cannot choose its law. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[11]` — Only the partially verified local jurisdiction/time premise may affect the matching selected claim. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
