# CAP-05.official-source — Bind exact official source and candidate relation

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CAP-05](../../parents/CAP-05.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The cited legal text/version/span/language is the resolved artifact, while extraction or translation remains candidate evidence.

**Предпочтительное решение.** Bind the selected jurisdiction’s exact official artifact/version/span/language to the CAP-02 root and CAP-03/LIF-01 relation admission; use require_legal_source_relation_verification plus the existing CitationRef/DocMeta readers. Keep parser, URL, signature and translation results candidate until issuer/source identity is resolved. Anchors: data_forge/domains/legal/source_relation.py; ir/loading/citations.py:CitationRef; ir/world/doc.py:DocMeta/DocFragment.

**Граница владельца.** CAP-05 source relation adapter over CAP-02 root; existing Lex/legal source owner. Parent native lease family: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** CNT-04 selected jurisdiction/source, CAP-02 exact root, original text/version/span and translation relation.

**Выход и consumer.** Persisted source-bound candidate relation with unresolved premises explicit.

**Что можно готовить независимо.** Select the actual jurisdiction, official publisher, authentic representation and verifier.

**Где результат соединяется с другими.** LIF-01/CAP-03 admit exact use only after source binding.

**Positive.** Consumer resolves the matching official text and exact language/version; translation uncertainty stays visible.

**Distinguishing negative.** URL/hash/LLM paraphrase or stale mirror cannot establish legal meaning.

**Matched removal.** Remove source/span/translation bind but keep citation/verified labels; legal reader limits.

**Граница контекста.** Keep one jurisdiction-specific legal relation vertical: the R14/R17/R19 cases are variants of exact source relation, competence/applicability, and time-scoped consumer meaning. Sequencing reduces simultaneous legal contexts while preserving one native Lex relation owner and the full composed legal proof. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/jurisdiction rebind where relevant; no new start gate.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:interface_agreement; acceptance:composition`: Consume exact retained legal source root or preserve unavailable.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume content/use admission at relation and selected consumer; applicability remains competent owner.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-04](../../parents/CNT-04.md) | `conditional_acceptance_requirements:composition`: When legal source use is claimed, consume CNT-04’s selected jurisdiction/source and source-qualified law/version/effect/applicability premises: bind the official relation, resolve competent act/scope/time, then pass only the supported premise to the selected consumer. Missing premises remain explicit.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: legal source use is claimed |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bind exact official artifact/version/span/language and candidate legal relation; URL/signature/extraction/translation alone do not prove meaning.
  `task.r14_extension.requirement`; `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[2]`
- **execute** — bind exact official span, original language, translation relation, and candidate extraction; authentic text does not make the translation authoritative.
  `task.r19_extension.question_slices[1]` (`R18-D04-Q02`); `task.r19_extension.question_ids[1]` (`R18-D04-Q02`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — Supply the exact official artifact/version/span and source relation that applicability resolves; URL/hash alone does not establish the party/scope relation. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Bind the exact official order/status text, source/version, addressees, proceeding, and source cut used by applicability. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[3]` — Bind the original official acts/notices and exact source/version separately from recipient receipt and delegation evidence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[5]` — Bind the exact official correction/repeal/act and version/span used to establish its effect. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[6]` — Supply the exact official act text/version/provision and issuer/source relation for the applicability check. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[7]` — When the selected claim relies on the act, bind its exact official source/version and issuer evidence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[8]` — Provide the exact official version/citation/source relation supporting the selected legal use. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[9]` — Bind the exact official source relation/version that applicability is resolving. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[10]` — For a legal premise, consume the exact official artifact/source relation rather than treating a valid digest as authority. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[11]` — Bind the exact official foreign-law artifact/version/source relation used by the local-applicability check. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
