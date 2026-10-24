# DES-10.document-fidelity — Проверить верность документа и повторное чтение

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DES-10](../../parents/DES-10.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Exact private document bytes and semantic edits preserve bound roles/content; material edits route to native owners and actual recomputation occurs before a fresh CNT-09 reader reuses the document.

**Предпочтительное решение.** Consume DES-06/07 private route and CNT-09. Test exact selected DOCX bytes, source/role/status refs, sidecar/revision and actual edit/readback; keep the real format reader distinct from HTML preview and the target-reader study.

**Граница владельца.** DES-10 owns the comparison recipe only. DES-06/07 own document producer/import-edit bridge; CNT-09 owns selected case consumer. No public recommendation text, enactment or publication authority; no duplicate document producer/schema writer.

**Входы.** Selected packet, bound source/role/status refs, exact DOCX carrier bytes/revision/sidecar, real material edits and actual native owner recomputation.; Authorized private audience and fresh CNT-09 reader result; DES-07/DES-06 exact schema agreement.

**Выход и consumer.** Carrier/semantic-fidelity and fresh-readback result with changed/unbound cells, affected claim recomputations and exact edition/output refs.

**Что можно готовить независимо.** Select material paragraphs/cells and edit mutations; bind expected roles and private audience before holdout. Exact output bytes and actual consumer join in shared FINAL-REPLAY.

**Где результат соединяется с другими.** Read actual DES-06/07 output through CNT-09 in the shared FINAL-REPLAY endpoint under FINAL-REVIEW’s actual immutable reviewed identity; reader cognition is measured separately by reader-comprehension.

**Positive.** Fresh consumer resolves exact carrier; material edit creates candidate delta and recomputes affected basis while preserving the old as-known edition.

**Distinguishing negative.** Changed text/cell, counterfeit DOCX, altered number, edit without owner recompute, proposal-as-enacted or HTML preview with changed exported action/status cannot pass.

**Matched removal.** Remove content/role binding or edit-to-recompute bridge but keep watermark/sidecar/headings; actual rendition/readback fidelity fails.

**Граница контекста.** R25 campaign 4 is mechanical semantic/document fidelity; it does not establish reader comprehension, accessibility certification or public release.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: Each selected campaign consumes FINAL-REVIEW’s actual final immutable reviewed identity when its campaign result is composed in the original single FINAL-REPLAY wave. This is the canonical acceptance dependency at composition; frozen cases, local oracles, protocol work and owner readiness may proceed independently, with no new ready/start blocker.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DES-10`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.



### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[12]` — Apply relevant document dimensions with exact-edition basis. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[19]` — Report document fidelity separately. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
