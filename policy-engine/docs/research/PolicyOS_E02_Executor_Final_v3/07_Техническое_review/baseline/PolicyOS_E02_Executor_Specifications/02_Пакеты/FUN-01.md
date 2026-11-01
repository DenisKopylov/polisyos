# FUN-01 — Сохранное продолжение и свежие gates

**LANE-02 · B156, B158, B159 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/FUN-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/FUN-01_исходные_строки.txt), строки 2697–2804.
**Практический результат:** После разрешённого изменения основания продолжить нужную работу, не переплачивая за уже пригодный immutable source и не переиспользуя старый допуск.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Strict candidate/proposal subject binding.
- Свежие current gates и неизменность обычной sentinel истории.
- Перед L3 проверяется pending L2 edge.
- Bound split не обходит defer и не скрывает repeated cost.
- Direct terminal не тратит новую работу.
- Freeze/reject остаются; prior attempts/costs retained.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C22_остатки:0 | REQ-FUN-01-01, REQ-FUN-01-02 | capability: Новый допустимый successor с адресным reuse. |
| audit-residual:C22_остатки:1 | REQ-FUN-01-03 | fix: Lineage не зависит от reuse kind. |
| audit-residual:C22_остатки:2 | REQ-FUN-01-04 | qualify: Actual source и mutable owners. |
| audit-residual:C22_остатки:3 | REQ-FUN-01-04 | fix: Примирить tests по предметной семантике. |
| audit-residual:C22_остатки:4 | REQ-FUN-01-01, REQ-FUN-01-04 | capability: Source identity и реальная независимость. |
| B156 | REQ-FUN-01-01, REQ-FUN-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B158 | REQ-FUN-01-01, REQ-FUN-01-02, REQ-FUN-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B159 | REQ-FUN-01-02, REQ-FUN-01-03, REQ-FUN-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0265 | REQ-FUN-01-01, REQ-FUN-01-04 | capability: Actual immutable reuse и replicate independence. |
| remaining:0266 | REQ-FUN-01-04 | fix: Обновить stale assertions, не вернуть whole cache. |
| remaining:0268 | REQ-FUN-01-01 | capability: Gates отдельно от source computation. |
| remaining:0269 | REQ-FUN-01-04 | qualify: Native work/cost equivalence. |
| remaining:0270 | REQ-FUN-01-02 | capability: Owner-valid successor. |
| remaining:0271 | REQ-FUN-01-03 | fix: Общая lineage projection. |

## 3. Нормативные REQ и конкретное решение

### REQ-FUN-01-01 — capability
Разделить fresh организационную попытку, текущие gates и reuse неизменной source-owned численной работы.

**Решение на существующих владельцах.** Сохранить отсутствие whole-ticket cache. У stage.evaluate выделить/переиспользовать существующий source computation interface с immutable input/model/data/procedure/seed refs и отдельную current admission/re-gating projection. Bound A/B переносит только проверенные source refs; lessons/correlation/access/budget проверяются заново. Не подключать старые _carry_forward helpers без modern owner checks. Sentinel получает отдельную роль/attempt, а независимость определяется источником и replicate, не UUID.
**Приёмка:** TEST-FUN-01-01.

### REQ-FUN-01-02 — capability
Continuation требует явного new-basis successor, сохраняя неизменный terminal и постоянные blockers.

**Решение на существующих владельцах.** В submit/advance добавить явный continuation request с parent attempt, прежним terminal_basis и событием действительного owner change. Проверить изменившийся budget/freeze/data/permit; при допустимом изменении создать linked successor и остаточный plan. У того же terminal без new basis не очищать results/is_terminal. retry_cheaper связывает другой разрешённый plan/ref, а не бесконечный reset. Не выводить новое разрешение из caller changed JSON.
**Приёмка:** TEST-FUN-01-02.

### REQ-FUN-01-03 — fix
Parent, lineage и continuation_reason сериализуются для всех применимых attempts, не только result reuse.

**Решение на существующих владельцах.** В policy_blueprint_runtime_reporting._serialize_funnel_outcome вынести существующие fields из условия result_reuse_source_ticket_id. При отсутствии не выдумывать relation; versioned projection различает linked attempt и actual result reuse. Blueprint state params и fresh reader сохраняют prior_attempt_history вместе с общей lineage/reason.
**Приёмка:** TEST-FUN-01-03.

### REQ-FUN-01-04 — qualify
Согласовать старые cache/continuation tests с современными fresh-gate контрактами и квалифицировать native full/split work.

**Решение на существующих владельцах.** В existing subject_identity, transition_accounting_semantics и stage-B tests заменить только устаревшее ожидание implicit whole-outcome reuse. Сохранить его содержательную цель новым test source work reuse + fresh gates + bound successor. Actual source-score/VOI/uncertainty/lessons/correlation owners выполнять, не scoreless fixture. Отдельно записать стоимость re-gating и physical evaluation, не равнять их по числу stage.evaluate.
**Приёмка:** TEST-FUN-01-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-FUN-01-01 · NOT_RUN
- **Setup:** Один strict candidate/proposal, тот же source, затем dataset v2 и изменённые lessons; normal и sentinel роли; actual immutable source owner с physical call counter.
- **Действие:** Full против owner-bound A/B; повтор independent request; source reuse через actual owner и свежие gates.
- **Oracle:** При одной basis численное source work1, gates актуальны в обоих API; dataset v2 вызывает новую нужную работу; history normal не меняется sentinel.
- **Positive / negative / boundary:** Новый UUID не новая независимая калибровка; opaque context допускает fresh work без ложного reuse; rejected source не используется.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-01-02 · NOT_RUN
- **Setup:** Terminal defer после L2, unchanged budget, затем owner-issued new budget; freeze on/off; permanent reject; alternate cheaper plan.
- **Действие:** Явно запросить resume для каждого состояния, пройти реальный scheduler/resource owner и actual source reuse из REQ01.
- **Oracle:** Unchanged не тратит физический ресурс; changed admissible basis rechecks L2→L3 и выполняет остаток; prior costs/traces retained; permanent reject не исчезает.
- **Positive / negative / boundary:** Full/direct split/bound split имеют одинаковое transition решение на одной basis, не двойное списание; freeze нельзя обойти новым ID.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-01-03 · NOT_RUN
- **Setup:** Explicit-linked attempt с parent и lineage2, reuse_ref=None, prior trace; отдельный source-reuse attempt.
- **Действие:** Actual serializer→JSON/CAS/state→fresh blueprint consumer.
- **Oracle:** Оба типа связи видимы с точным reason; parent/lineage не исчезают у live_split_gates_rechecked; prior cost history не дублируется.
- **Positive / negative / boundary:** Нет новой параллельной ledger; legacy отсутствие полей не интерпретируется как доказанное отсутствие предшественника.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-01-04 · NOT_RUN
- **Setup:** Один source-admitted tiny objective с единицами, full/A-B paths, capped/defer/changed-basis variants; supported native runtime.
- **Действие:** Пройти actual lifecycle и readback, сравнить work IDs, admission decisions, consumed budget и scopes.
- **Oracle:** На одинаковой basis тот же разрешённый набор source computations, costs и stop reasons; любое дополнительное re-gating объяснено; score не повышен отсутствующим admission.
- **Positive / negative / boundary:** Историческое source-only test contradiction не называется прежним native failure; skip остаётся видимым.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-C**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- FUN-01 — orchestration/continuation owner; FUN-02 — fidelity/aggregate projection; FUN-03 — current knowledge/calibration/protected action.
- CTL-03 владеет actual resource admission; bound continuation не создаёт второй budget owner.
- Источник immutable numerical work остаётся у existing Foundry/AD01 owner; не общий ticket-cache.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py:471–503](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py#L471-L503) — `    def submit(`.
- [policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py:648–680](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py#L648-L680) — `    def advance(`.
- [policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_reporting.py:574–606](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_reporting.py#L574-L606) — `def _serialize_funnel_outcome(`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0393 | REQ-FUN-01-01, TEST-FUN-01-01 | Strict candidate/proposal subject binding. |
| preserve:0394 | REQ-FUN-01-01, REQ-FUN-01-04, TEST-FUN-01-01, TEST-FUN-01-04 | Свежие current gates и неизменность обычной sentinel истории. |
| preserve:0397 | REQ-FUN-01-02, REQ-FUN-01-04, TEST-FUN-01-02, TEST-FUN-01-04 | Перед L3 проверяется pending L2 edge. |
| preserve:0398 | REQ-FUN-01-02, REQ-FUN-01-04, TEST-FUN-01-02, TEST-FUN-01-04 | Bound split не обходит defer и не скрывает repeated cost. |
| preserve:0399 | REQ-FUN-01-02, TEST-FUN-01-02 | Direct terminal не тратит новую работу. |
| preserve:0400 | REQ-FUN-01-02, REQ-FUN-01-03, TEST-FUN-01-02, TEST-FUN-01-03 | Freeze/reject остаются; prior attempts/costs retained. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/FUN-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
