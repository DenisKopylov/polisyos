# CAP-06.private-input — Bind selected private/federated inputs and participant coverage

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [CAP-06](../../parents/CAP-06.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A private result is bound to actual inputs, roster/omissions, alignment, executable and allowed recipient; aggregation alone does not establish inference or independence.

**Предпочтительное решение.** For the selected private/federated profile, use AccessScope/classification_allowed only as local inputs, require source/custodian grant through LIF-01/LIF-05, and bind exact roots, roster/omissions, alignment and executable into the existing PartitionedIngestionPlan path. Do not infer permission, completeness or independence from labels or successful aggregation. Anchors: core/security/access_scope.py:AccessScope; fabric/security/access_control.py:classification_allowed; fabric/data_plane/orchestrator.py:PartitionedIngestionPlan.

**Граница владельца.** CAP-06 capture/result-intake contract; CNT-06 qualifies population/inference; OPS-09 consumes the selected deployment cell. Parent native lease family: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Source/custodian grant, exact roots, site roster/omissions, input/executable identity, alignment and aggregation rule.

**Выход и consumer.** Persisted private result receipt with participant coverage and scope limitation.

**Что можно готовить независимо.** Choose an actual federated/private profile and obtain external owner evidence.

**Где результат соединяется с другими.** Join CNT-06's separate inferential qualification and OPS-09's deployment proof at selected consumers.

**Positive.** Permitted result reaches a qualified consumer with complete declared roster; approved dropout changes the scope honestly.

**Distinguishing negative.** Poisoned/misaligned result, duplicate site, nonrandom dropout or overlap hash cannot support the original global claim.

**Matched removal.** Remove roster/input/source binding while retaining encrypted/aggregate markers; CNT-06 consumer rejects.

**Граница контекста.** The card combines private/federated evidence qualification, durable remote effects/retries, and output-rights/sink enforcement. R15/R16/R17/R19 explicitly assign these to separate native owners; a single implementer otherwise holds statistical, provider, and custody contexts at once. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted provider/source rebind where relevant; parent stage remains.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:interface_agreement; acceptance:composition`: Consume exact selected input roots at private/provider/effectful solver calls.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume exact admitted roots/current-use identity at input, dispatch, call and output admission.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:interface_agreement; acceptance:composition`: Consume shared rights/AP07 outcome at input, dispatch, calls, resume and sinks.<br>Source: `task.depends_on[4]`; `task.acceptance_dependencies[3]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-04](../../parents/CAP-04.md) | `conditional_acceptance_requirements:composition`: Only when a selected restricted-source profile claims ongoing source-change/revocation handling: consume the exact CAP-04 event/lookup through LIF-02 before admitting the selected source-custody inputs. Absence blocks that custody claim, not independent controlled-query preparation.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: The selected restricted-source profile claims ongoing source change/revocation event handling |
| Composition output (не start gate) [CAP-06.rights-and-output-sinks](../../cards/CAP-06/rights-and-output-sinks.md) | Consume only for the exact composition described here: Join CNT-06's separate inferential qualification and OPS-09's deployment proof at selected consumers. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bind actual private roster/omissions, producer trust and cross-instance scope; CNT-06 owns inference/independence, OPS-09 chooses deployment cell.
  `task.r15_extension.requirement`
- **binding** — R15 adaptive-trajectory extension constrains selected private/federated participant and input coverage; it does not appoint a second inference owner.
  `task.r15_extension.detail`
- **binding** — R15 adaptive-method quality reference constrains the selected private-input profile and uncertainty handling; CNT-06 retains inferential qualification.
  `task.r15_extension.quality_ref`
- **binding** — TP07 technical-method profile constrains the selected input/executable relation; no new method or provider owner is implied.
  `task.r15_extension.technical_profiles[0]`

### Обязанности внутри составных fragments

- `task.r15_extension.adversarial` — Poisoned or misaligned results, duplicate sites, nonrandom dropout or revoked rights cannot preserve the original global claim merely because aggregation succeeded. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[0]` — Only if the selected profile is private/federated, bind actual input overlap/roster and omissions; this does not qualify independence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[1]` — Only when the selected transform uses a private/federated profile, bind its actual roster/input coverage; ordinary public/local inputs do not require a private receipt. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — Only for the selected private/federated profile, bind the actual input/roster/omissions; do not require this receipt for public/local profiles. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[6]` — Only for the selected private/federated call, bind exact private inputs/roster/omissions and scope; a successful aggregate does not prove completeness or independence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
