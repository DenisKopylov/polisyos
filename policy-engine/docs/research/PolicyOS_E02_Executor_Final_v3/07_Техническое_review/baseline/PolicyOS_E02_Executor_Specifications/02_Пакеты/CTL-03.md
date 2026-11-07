# CTL-03 — Согласованные единицы работы, бюджета и пригодности

**LANE-02 · B120, B121, B123 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CTL-03.md), [исходная карточка](../05_Основания/Аудит/05_Источники/CTL-03_исходные_строки.txt), строки 1730–1849.
**Практический результат:** Sentinel расходует ресурс, но не загрязняет обучение; новые оценки не теряют квоту из-за warm history, а invalid typed result не становится лучшим по удобному scalar.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- owner/run/event reconciliation
- unknown not zero
- spent+reserved
- ordinary iteration semantics
- sentinels excluded from training/best
- presence status
- best/frontier guard
- legitimate optional scalar path
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C13_остатки:0 | REQ-CTL-03-01 | fix: Same-base sentinel StageB accounting. |
| audit-residual:C13_остатки:1 | REQ-CTL-03-02 | fix: Bound generic sentinel work. |
| audit-residual:C13_остатки:2 | REQ-CTL-03-03 | fix: Reject NaN cap. |
| audit-residual:C13_остатки:3 | REQ-CTL-03-04 | qualify: Actual evaluator admission, не generator-only scope. |
| audit-residual:C13_остатки:4 | REQ-CTL-03-05 | qualify: Реальный composite eligibility consumer. |
| B120 | REQ-CTL-03-03, REQ-CTL-03-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B121 | REQ-CTL-03-01, REQ-CTL-03-02 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B123 | REQ-CTL-03-05 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0199 | REQ-CTL-03-03 | fix: Finite configuration. |
| remaining:0200 | REQ-CTL-03-04 | qualify: Actual evaluator resource owner. |
| remaining:0201 | REQ-CTL-03-01 | fix: StageB denominator alignment. |
| remaining:0202 | REQ-CTL-03-02 | fix: Finite physical work cap. |
| remaining:0205 | REQ-CTL-03-05 | qualify: Scalar diagnostic не eligibility. |

## 3. Нормативные REQ и конкретное решение

### REQ-CTL-03-01 — fix
Scientific/non-sentinel StageB count должен вычитаться из той же StageB базы; ранний StageA-rejected sentinel не уменьшает обычные StageB.

**Решение на существующих владельцах.** У единственного SearchRunState хранить отдельно sentinel attempts и sentinel_stage_b_completed (либо explicit ordinary_stage_b counter), обновлять через shared transition fullrun/tell. scientific_evaluations обозначает выполненную non-sentinel StageB работу, не accepted evidence. Не лечить max(0) и не добавлять sentinel в ordinary history/best.
**Приёмка:** TEST-CTL-03-01.

### REQ-CTL-03-02 — fix
Generic sentinel-only профиль должен иметь конечный physical-work/attempt лимит либо обязательный независимый finite resource cap, сохраняя ordinary iteration semantics.

**Решение на существующих владельцах.** В существующих run-state/stopping задать отдельную единицу общего work cap и проверять до каждого actual evaluation/generation. Не повышать ordinary counter sentinel ради остановки. Штатный SentinelInjector, который не добавляет sentinel к empty, сохранить; custom generator без конечного cap не допускается к unlimited loop.
**Приёмка:** TEST-CTL-03-02.

### REQ-CTL-03-03 — fix
CostBudgetStopping должен отвергать bool/non-numeric/NaN/inf/nonpositive cap; допустимый конечный limit останавливает по фактическому owner snapshot.

**Решение на существующих владельцах.** В constructor/config boundary выполнить explicit numeric type+isfinite+positive validation до сохранения. Unlimited только отдельный явный профиль, не IEEE special value. Existing _read_source_budget_snapshot/owner reconciliation остаётся источником spent/reserved, не callercontext.
**Приёмка:** TEST-CTL-03-03.

### REQ-CTL-03-04 — qualify
Выбранный дорогой evaluator должен иметь собственный actual admission/reservation и price basis; post-spend search stopping не является его предварительным разрешением.

**Решение на существующих владельцах.** Связать существующий evaluator/budget middleware с тем же run owner, reserve до вызова где price policy это требует, settle/release по фактическому событию; генераторный TracedLLM budget не автоматически evaluator budget. Return snapshot reader проверяет exact identity/event totals. Не создавать search-side денежный ledger.
**Приёмка:** TEST-CTL-03-04.

### REQ-CTL-03-05 — qualify
Present malformed typed evaluation должен оставаться invalid до best/frontier/training/publication consumer; отдельное корректное scalar diagnostic может сохраняться без повышения eligibility.

**Решение на существующих владельцах.** Сохранить presence-aware _resolve_policy_evaluation_with_status и actual ObjectiveStack/source owner. Missing optional typed разрешает законный scalar; invalid/null/malformed не missing. Tell может хранить scalar AVAILABLE, но composite consumer всегда проверяет typed status/feasible/source. Не стирать полезное число ради одинаковости run/tell проекций.
**Приёмка:** TEST-CTL-03-05.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-CTL-03-01 · NOT_RUN
- **Setup:** Passing sentinel, StageA-rejected sentinel, ordinary StageB и malformed typed evaluation; обе APIs.
- **Действие:** Выполнить смешанную последовательность и roundtrip telemetry.
- **Oracle:** Rejected sentinel+ordinary→stageB1/scientific1, sentinelattempt1; passing sentinel отдельноStageB, ordinarytraining/best не меняется от sentinel.
- **Positive / negative / boundary:** Warm history не новые evaluations; resource counts и accepted evidence различны.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-03-02 · NOT_RUN
- **Setup:** Generator толькоsentinels, ordinaryhardlimit1, explicit worklimit3; stock injector ordinarymix; independent cost cap.
- **Действие:** Пройти full native driver и manual profile sharedSRV01, считать actual StageB и attempts.
- **Oracle:** После3разрешённых control work — адресный stop с partial output; ordinarycount0, обучение не загрязнено; normal injector работает.
- **Positive / negative / boundary:** Ни watchdog, ни отсутствие предложений не product stop proof; unknown resource не unlimited.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-03-03 · NOT_RUN
- **Setup:** capNaN,±inf,bool,0,−1,normal1; actual durable BudgetState/owner/run/events и settled0.
- **Действие:** Construct/check и actual generation spend→ledger→stopping→report, wrongowner/run/missingevents controls.
- **Oracle:** Invalid cap rejected до работы; actual committed cost и reserved видны,1порог работает, settled0 корректен.
- **Positive / negative / boundary:** Не выдавать локальный capfix за обход/замену durable admission; unknowncost не0.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-03-04 · NOT_RUN
- **Setup:** Actual test_autotune_runner_binds_real_provider_call_to_durable_budget_owner плюс реальный bounded evaluator route; fakeHTTPtransport допустим.
- **Действие:** Success,fail-after-dispatch,retry/cache,settledzero и unknownprice; прочитать spend+reserved и stop.
- **Oracle:** Один measurement расход виден всем consumers, нет doublecharge/cache суммирования, недопущенная новая работа не стартует.
- **Positive / negative / boundary:** Fixturecontextcost999 не истина; настоящий source/price profile явен, no live paid calls нужны.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-03-05 · NOT_RUN
- **Setup:** Actual PolicyEvaluationVector/ObjectiveStack, absent/None/extraField/list/bool, unverifiedsource и verifiedpositive; run иtell.
- **Действие:** Оценить, сохранить history, прочитать best/frontier/surrogate/действующий downstream, попытаться выбрать invalid scalar−100.
- **Oracle:** Invalid не best/train/promote; safe candidate сохраняется; absent legacypositive работает; valid owner-backed typed candidate полезно принимается.
- **Positive / negative / boundary:** Нельзя объявить source admission по VectorFixture; branch identity/limits видны после readback.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-A**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- CTL-03 owns counter semantics/finite monetary cap; CTL-01 failure attempt snapshot; SRV-01 shared split admission; SRV-03 actual consumer.
- OPT-01 source/coordinate contract governs usable objectives; scalar diagnostic не обходит его.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Различающие единицы сохраняют полезность warm start и sentinels одновременно. Budget предотвращает необоснованную новую работу, но tell уже сделанной работы не теряется только от позднего exhaustion.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/run_state.py:64–96](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/run_state.py#L64-L96) — `def scientific_evaluations`.
- [policy-engine/src/polisyos/scientist/methods/search/run_state.py:99–126](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/run_state.py#L99-L126) — `def apply_tell_transition`.
- [policy-engine/src/polisyos/scientist/methods/search/stopping.py:289–321](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stopping.py#L289-L321) — `class CostBudgetStopping`.
- [policy-engine/src/polisyos/scientist/methods/search/lifecycle.py:1299–1331](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lifecycle.py#L1299-L1331) — `def _resolve_policy_evaluation_with_status`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0315 | REQ-CTL-03-03, REQ-CTL-03-04, TEST-CTL-03-03, TEST-CTL-03-04 | owner/run/event reconciliation |
| preserve:0316 | REQ-CTL-03-03, TEST-CTL-03-03 | unknown not zero |
| preserve:0317 | REQ-CTL-03-03, REQ-CTL-03-04, TEST-CTL-03-03, TEST-CTL-03-04 | spent+reserved |
| preserve:0318 | REQ-CTL-03-01, REQ-CTL-03-02, TEST-CTL-03-01, TEST-CTL-03-02 | ordinary iteration semantics |
| preserve:0319 | REQ-CTL-03-01, REQ-CTL-03-02, TEST-CTL-03-01, TEST-CTL-03-02 | sentinels excluded from training/best |
| preserve:0322 | REQ-CTL-03-05, TEST-CTL-03-05 | presence status |
| preserve:0323 | REQ-CTL-03-05, TEST-CTL-03-05 | best/frontier guard |
| preserve:0324 | REQ-CTL-03-05, TEST-CTL-03-05 | legitimate optional scalar path |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/CTL-03.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
