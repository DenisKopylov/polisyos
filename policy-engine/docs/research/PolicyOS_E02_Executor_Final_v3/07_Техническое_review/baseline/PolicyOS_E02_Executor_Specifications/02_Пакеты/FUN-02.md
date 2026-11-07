# FUN-02 — Честные fidelity, score и interval semantics

**LANE-02 · B157, B160, B162, B165 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/FUN-02.md), [исходная карточка](../05_Основания/Аудит/05_Источники/FUN-02_исходные_строки.txt), строки 2805–2932.
**Практический результат:** Получать полезный reduced/full результат без aliasing и ложной bootstrap certainty; empty/partial/zero остаются различимыми у настоящего consumer.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Пять small mapping copies, shared dataset/model/CAS handles.
- Прямая L4 и L3→L4 получают одинаковый input.
- None/NOT_EVALUATED для empty/capped.
- Zero и partial score retained без ложного full APPROVE.
- Typed missing/invalid/effect reasons.
- Huge-int conversion guard и true zero.
- Stage verdict отдельно; aggregate defer/reject не повышает полномочия.
- Score и stage result сохраняются.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C23_остатки:0 | REQ-FUN-02-03 | fix: Stable ratio с exact reference. |
| audit-residual:C23_остатки:1 | REQ-FUN-02-04 | fix: Heuristic не bootstrap. |
| audit-residual:C23_остатки:2 | REQ-FUN-02-01 | qualify: Actual work, не recording inputs alone. |
| audit-residual:C23_остатки:3 | REQ-FUN-02-02 | fix: Native runtime и согласование unit fixture. |
| audit-residual:C23_остатки:4 | REQ-FUN-02-02, REQ-FUN-02-04 | capability: Measured interval/zero actual chain. |
| B157 | REQ-FUN-02-01 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B160 | REQ-FUN-02-02 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B162 | REQ-FUN-02-03, REQ-FUN-02-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B165 | REQ-FUN-02-02 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0267 | REQ-FUN-02-01 | qualify: Native work/cost и nested ownership. |
| remaining:0272 | REQ-FUN-02-02 | qualify: Source-admitted zero. |
| remaining:0275 | REQ-FUN-02-03 | fix: Finite overflow и underflow controls. |
| remaining:0276 | REQ-FUN-02-04 | fix: Правдивый method/source label. |
| remaining:0282 | REQ-FUN-02-02, REQ-FUN-02-04 | qualify: Actual consumer migration и source validity. |

## 3. Нормативные REQ и конкретное решение

### REQ-FUN-02-01 — qualify
Квалифицировать actual effective L3/L4 config и physical work, сохраняя минимальные owned mapping copies.

**Решение на существующих владельцах.** Сохранить dict copies пяти конфигураций в _build_reduced_state и shared immutable dataset/model/CAS handles. Native engine должен принять effective fidelity/config digest, отдельно сообщить requested и действительно executed work. Если конкретный inner engine мутирует nested tuning, изолировать именно его owned subtree или прекратить mutation; не вводить blanket deepcopy. Direct L4 и L3→L4 используют один исходный full profile.
**Приёмка:** TEST-FUN-02-01.

### REQ-FUN-02-02 — qualify
Выполненный source-admitted zero, empty и partial сохраняют разные score/aggregate verdict у всех affected consumers.

**Решение на существующих владельцах.** Использовать existing _empty_result/_compatibility_result и score admission finalization. Actual zero подкрепить source metric/unit/selected result, не fixture admission. Перенести consumer с удобного stage APPROVE на declared aggregate field с version/migration; stage result/score оставить отдельно. Source/consumer census ограничить актуальными callers обоих funnel result/outcome полей.
**Приёмка:** TEST-FUN-02-02.

### REQ-FUN-02-03 — fix
Нормировка width/(2*abs(effect)) устойчива для всех finite диапазонов, включая subnormal; missing/invalid/zero остаются typed.

**Решение на существующих владельцах.** В statistical_uncertainty_from_ci_width после текущей validation вычислять ratio через масштабирование mantissa/exponent (frexp/ldexp или эквивалентный проверенный owner), чтобы не получить overflow 2*effect или underflow от предварительного 0.5*width. Clamp к1 делается по математическому ratio, не как лечение invalid. Сравнить с Fraction.from_float/as_integer_ratio oracle для exact входных float; при реально непредставимо малом результате допускается правильно округлённый0 с сохранённым source method, не fabricated certainty.
**Приёмка:** TEST-FUN-02-03.

### REQ-FUN-02-04 — capability
Метод uncertainty следует фактическому interval producer, а не имени bootstrap key/fidelity.

**Решение на существующих владельцах.** Расширить существующий uncertainty/source contract для heuristic_proxy и source_owned_interval с method/profile/input/unit binding. _build_policy_simulation_results_impl width0.1/0.12 при draw_execution_status=not_instrumented передаёт proxy, L4 не переименовывает его full_fidelity_bootstrap. Реальный interval producer предоставляет measured method/scale/refs; consumer проверяет binding перед bootstrap label. Сохранить raw result и useful routing, не повторять дорогую simulation ради исправления label.
**Приёмка:** TEST-FUN-02-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-FUN-02-01 · NOT_RUN
- **Setup:** Caller fraction1/bootstrap500/full SCM, L3 fraction0.2/bootstrap50/reduced; actual engine с instrumented work counters и dataset handles.
- **Действие:** Run direct full и reduced→full; сравнить input digests, output basis, физические calls/draws и costs.
- **Oracle:** Caller и full input неизменны; reduced реально использует свой меньший declared work, full не наследует overlay; handles не копируются без причины.
- **Positive / negative / boundary:** Requested500 не executed500. Если backend не умеет draws accounting, явно not_instrumented, без утверждения меньшей стоимости.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-02-02 · NOT_RUN
- **Setup:** Empty stages, cap исключает L4, actual valid zero objective, stage APPROVE + aggregate defer/reject, поле stage verdict присутствует/отсутствует.
- **Действие:** Actual stage/source→orchestrator→Stage B→blueprint persistence→fresh consumer.
- **Oracle:** Empty None/NOT_EVALUATED; zero0 сохранён; partial0 остаётся DEFER/partial, не full APPROVE; optional stage verdict не меняет aggregate.
- **Positive / negative / boundary:** Неверные/missing units не обойти для zero. Старый L4 fixture без units исправить по настоящему контракту, не ослабить admission.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-02-03 · NOT_RUN
- **Setup:** width=effect=1e308; оба равны минимальному positive subnormal; width0/effect2; width0.4/effect2; huge int10**400; bool/NaN/negative/missing.
- **Действие:** Вызвать actual helper и L3/L4 adapters, сравнить exact rational rounded oracle и typed reason.
- **Oracle:** Оба equal-scale extreme случая дают0.5; 0.4/4≈0.1 в ≤1ULP от rounded reference; настоящие zero cases сохраняются; invalid не bootstrap measurement.
- **Positive / negative / boundary:** Effect0 width>0→declared level1 proxy, both0→0; никакого произвольного clipping входов или универсального scientific CI вывода.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-02-04 · NOT_RUN
- **Setup:** Actual native producer heuristic width0.1, effect1 и not_instrumented; отдельно настоящий source-owned interval с известным method/input/units; tampered method/source.
- **Действие:** Producer→L4 envelope→persist→actual routing/display consumer.
- **Oracle:** Heuristic ratio0.05 остаётся proxy; только подтверждённый interval имеет свой реальный method; tamper не становится measured CI.
- **Positive / negative / boundary:** Нулевой interval не blanket запрещён; validity требует конкретного source method. Scientific uncertainty/current assessment остаётся FUN-03/UQS owner, а не scalar helper.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-C**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- FUN-01 владеет попытками/re-gating/reuse; общие orchestrator edits последовательны.
- FUN-03/UQS — source-traced current uncertainty, здесь interval origin и aggregate presentation.
- Actual engine owner подтверждает executed draws; диагностический label не назначает scientific authority.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/funnel/types.py:191–223](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/types.py#L191-L223) — `def statistical_uncertainty_from_ci_width(`.
- [policy-engine/src/polisyos/scientist/methods/search/funnel/level3_medium.py:250–282](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/level3_medium.py#L250-L282) — `    def _build_reduced_state(`.
- [policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_metrics.py:450–482](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_metrics.py#L450-L482) — `def _build_policy_simulation_results_impl(`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0395 | REQ-FUN-02-01, TEST-FUN-02-01 | Пять small mapping copies, shared dataset/model/CAS handles. |
| preserve:0396 | REQ-FUN-02-01, TEST-FUN-02-01 | Прямая L4 и L3→L4 получают одинаковый input. |
| preserve:0401 | REQ-FUN-02-02, TEST-FUN-02-02 | None/NOT_EVALUATED для empty/capped. |
| preserve:0402 | REQ-FUN-02-02, TEST-FUN-02-02 | Zero и partial score retained без ложного full APPROVE. |
| preserve:0405 | REQ-FUN-02-03, TEST-FUN-02-03 | Typed missing/invalid/effect reasons. |
| preserve:0406 | REQ-FUN-02-03, TEST-FUN-02-03 | Huge-int conversion guard и true zero. |
| preserve:0411 | REQ-FUN-02-02, TEST-FUN-02-02 | Stage verdict отдельно; aggregate defer/reject не повышает полномочия. |
| preserve:0412 | REQ-FUN-02-02, REQ-FUN-02-04, TEST-FUN-02-02, TEST-FUN-02-04 | Score и stage result сохраняются. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/FUN-02.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
