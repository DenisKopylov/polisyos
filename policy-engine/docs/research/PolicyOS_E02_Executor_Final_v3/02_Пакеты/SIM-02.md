# SIM-02 — Адрес вмешательства, точная причина и реальное временное покрытие

**LANE-01 · B18, B20, B22 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/SIM-02.md), [исходная карточка](../05_Основания/Аудит/05_Источники/SIM-02_исходные_строки.txt), строки 1178–1288.
**Практический результат:** Вмешательство не меняет смысл из-за написания индекса; пользователь получает различимую причину missing/nonfinite и честную частичную траекторию вместо выдуманного нуля.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Присутствие исхода и finite/numeric проверка; ноль остаётся нулём
- Частично выполненная работа и failed-event
- Проверка полного write-set до producer
- Одинаковые совместимые присваивания и точные типы program parameters
- Partial coverage, missing/empty/full различение и hold_last=False
- Видимый dt mismatch и unestablished physical-time status
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C09_остатки:0 | REQ-SIM-02-01 | fix: Один resolved path contract у existing adapters. |
| audit-residual:C09_остатки:1 | REQ-SIM-02-02 | fix: Typed cause через retained projection. |
| audit-residual:C09_остатки:2 | REQ-SIM-02-03 | qualify: Обновить stale expectations без ослабления oracle. |
| audit-residual:C09_остатки:3 | REQ-SIM-02-04 | fix: Конечный temporal profile, не blanket запрет candidate. |
| audit-residual:C09_остатки:4 | REQ-SIM-02-05 | lifecycle: Разрешить осмысленные vectors, ограничить ambiguous aggregation. |
| B18 | REQ-SIM-02-02, REQ-SIM-02-03, REQ-SIM-02-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B20 | REQ-SIM-02-01 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B22 | REQ-SIM-02-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0046 | REQ-SIM-02-02 | fix: Persisted specific cause/outcome. |
| remaining:0047 | REQ-SIM-02-03, REQ-SIM-02-05 | qualify: Нынешние native tests и declared aggregation. |
| remaining:0050 | REQ-SIM-02-01 | fix: Resolved target identity. |
| remaining:0051 | REQ-SIM-02-01 | qualify: Оба sibling adapters. |
| remaining:0055 | REQ-SIM-02-04 | fix: Initial/final/time договор выбранного профиля. |
| remaining:0056 | REQ-SIM-02-02, REQ-SIM-02-04 | qualify: Partial readback с сохранённой причиной. |

## 3. Нормативные REQ и конкретное решение

### REQ-SIM-02-01 — fix
До physical producer simultaneous write-set должен сравнивать фактически разрешённые targets; aliases одного list/array элемента конфликтуют, distinct mapping keys не сливаются.

**Решение на существующих владельцах.** У existing state/path adapters resolve path относительно исходного container/slot в typed canonical target (mapping key vs normalized bounded index). Предпочесть разрешение отрицательных индексов относительно length; если профиль не поддерживает их — явный preflight отказ, не int surprise. Один проверенный write plan затем исполняется без повторного независимого parsing. Reuse _resolve_assignment_writes для exact/prefix conflicts, type-aware equal writes и сохранения source atoms. Registry sibling использует тот же shared resolver, не copy второй алгоритм.
**Приёмка:** TEST-SIM-02-01.

### REQ-SIM-02-02 — fix
Исходные typed cause code и безопасный outcome/slot context должны пережить physical interruption→persisted result→fresh reader; partial completed work сохраняется.

**Решение на существующих владельцах.** В _run_cached_replicates/current work-event projection перенести whitelist-safe structured cause поля из JointSimulationControllerError в existing error diagnostics, затем _PhysicalWorkInterruptedError/run retained projection. Не сериализовать произвольное exception object/secret string и не создавать второй error registry. Неведомое исключение сохраняет общий typed fallback без false specific diagnosis.
**Приёмка:** TEST-SIM-02-02.

### REQ-SIM-02-03 — qualify
Native regressions должны проверять нынешний retained-interruption контракт, а не требовать старый raises или принимать общий no_run; output presence/type/finite остаются строгими.

**Решение на существующих владельцах.** Обновить только устаревшие expectation в tests/unit/remediation/test_sim_02.py после TEST-02, ProgramGraph fake refs заменить compatible real artifact fixture. Существующие _ncm_outcomes/_selected_outcome_value guards не ослаблять. В тесте проверять persisted cause, выполненные/невыполненные роли и отсутствие invented numeric.
**Приёмка:** TEST-SIM-02-03.

### REQ-SIM-02-04 — fix
Для выбранного временного профиля initial rows, transitions и final summaries должны иметь однозначную роль/координаты; short/empty/surplus output не получает выдуманное полное покрытие.

**Решение на существующих владельцах.** У existing stock-flow/registry/coupled adapters закрепить declared row contract: initial snapshot отдельно, transition outputs с actual coordinate, final mass_balance отдельный summary либо явно endpoint role. Для one-point request не прикреплять post-transition scalar к initial label; выбрать existing-compatible initial или explicit final-summary profile. Surplus slicing допустим только по declared prefix/coordinates с emitted slice provenance/count. Сохранять hold_last=False и dt mismatch/not_established до реального time binding.
**Приёмка:** TEST-SIM-02-04.

### REQ-SIM-02-05 — lifecycle
Scalar aggregation численного массива допустима только в declared output contract; vector/population output не запрещается автоматически и не усредняется универсально без смысла.

**Решение на существующих владельцах.** Finite census actual callers _selected_outcome_value и method signatures: отметить scalar, population vector с explicit aggregation/weights/units и unsupported shapes. Сохранить legitimate mean profile, вынести rule/basis в существующую method/output projection; ambiguous array даёт limitation/typed refusal этой dependent effect, не fabricated scalar. Новая семантика агрегации реализуется у текущего producer/adapter, не глобальным mean.
**Приёмка:** TEST-SIM-02-05.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-SIM-02-01 · NOT_RUN
- **Setup:** Real system-dynamics и method-registry requests: .0/.00/+0, .-1/.1 при length2, dict keys "0"/"00", nested prefixes, equal values, bool/int/float parameters.
- **Действие:** Переставить atoms и отдельно поменять spelling aliases, затем вызвать actual producer с invocation counter.
- **Oracle:** Несовместимый resolved target отказан до producer в обоих adapters; distinct indices/keys и равные разрешённые writes дают одинаковый результат.
- **Positive / negative / boundary:** Simultaneous conflict не blanket запрет объявленной sequential program: её порядок должен быть явно в semantics/identity; missing/out-ofbounds адресны.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-02-02 · NOT_RUN
- **Setup:** Actual controller, сначала completed role, затем empty NCM envelope либо NaN selected outcome; temporary CAS и новый reader.
- **Действие:** Отдельно выполнить две причины, сохранить result и открыть вне исходного exception chain; отменить следующий callback.
- **Oracle:** ncm_world_summaries_missing и ncm_outcome_non_finite различимы с outcome/slot; общий n5_physical_work_failed допустим как enclosing code; предыдущая роль и failed event сохранены.
- **Positive / negative / boundary:** Missing не0, explicit0 сохраняется; partial failure не становится completed aggregate или opaque class-only cause.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-02-03 · NOT_RUN
- **Setup:** Пустой envelope, один отсутствующий из двух outcomes, null/bool,NaN/inf, explicit0; actual DTO/controller/store.
- **Действие:** Запустить существующий suite целевых selectors на поддержанном runtime; readback result, а preflight errors проверять по их actual contract.
- **Oracle:** Все причины различимы, явный0число; нет укороченного denominator или fake-ref bypass. Source/fixture correction отдельно от продукта.
- **Positive / negative / boundary:** Не объявлять весь suite broken по чтению; numerical mock в unit не заменяет actual consumer test.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-02-04 · NOT_RUN
- **Setup:** Actual stock-flow initial10,inflow1,zero flow matrix; labels[0,2,4], dt2/1, horizon one point; short/empty/4rowsfor3, coupled queue initial4→3.
- **Действие:** Выполнить real adapter, persist/read and inspect coordinates/roles/coverage; запросить missing tail.
- **Oracle:** Declared dt2 даёт10/12/14 в своём computational contract, dt1 mismatch виден; initial/final не смешаны, partial prefix доступен но не stable complete.
- **Positive / negative / boundary:** No hold-last by final_stocks; explicit supported reconstruction допускается только с source/rule/provenance и отдельным тестом, не требуется универсальный interpolator.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-02-05 · NOT_RUN
- **Setup:** Один реальный vector producer с declared population aggregate и scalar producer; 2×2 array, weights/missingness/empty/outcome units controls.
- **Действие:** Пройти actual selected outcome→result→consumer и независимый ручной aggregate.
- **Oracle:** Легитимный aggregate воспроизводим с denominator/units, scalar неизменен; ambiguous shape не ложный effect4 лишь потому что numpy.mean возможен.
- **Positive / negative / boundary:** Это bounded contract decision, не утверждение, что все arrays были багом; independent finite values и missingness остаются различимы.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-A**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- SIM-02 единственный owner common resolved-write и retained cause contract; SIM-03 использует этот cause для replication interruption.
- SIM-01 preflight не catch-all retry; CYC-02 actual conditional consumer принимает только qualified выбранный профиль.
- Temporal/aggregation profile согласовать с actual method owner, не менять units/estimand ради зелёной длины.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Точность причины открывает конкретное следующее исследование; она не заменяет полезную частичную работу blanket refusal. A01 требует проверенного chosen runner, не всех мировых моделей.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:3598–3630](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L3598-L3630) — `def _resolve_assignment_writes`.
- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:4224–4256](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L4224-L4256) — `def _assign_path_value`.
- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:1118–1150](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L1118-L1150) — `def _run_cached_replicates`.
- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:3835–3867](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L3835-L3867) — `def _selected_outcome_value`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0060 | REQ-SIM-02-02, REQ-SIM-02-03, REQ-SIM-02-05, TEST-SIM-02-02, TEST-SIM-02-03, TEST-SIM-02-05 | Присутствие исхода и finite/numeric проверка; ноль остаётся нулём |
| preserve:0061 | REQ-SIM-02-02, REQ-SIM-02-03, TEST-SIM-02-02, TEST-SIM-02-03 | Частично выполненная работа и failed-event |
| preserve:0065 | REQ-SIM-02-01, TEST-SIM-02-01 | Проверка полного write-set до producer |
| preserve:0066 | REQ-SIM-02-01, TEST-SIM-02-01 | Одинаковые совместимые присваивания и точные типы program parameters |
| preserve:0070 | REQ-SIM-02-04, TEST-SIM-02-04 | Partial coverage, missing/empty/full различение и hold_last=False |
| preserve:0071 | REQ-SIM-02-04, TEST-SIM-02-04 | Видимый dt mismatch и unestablished physical-time status |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/SIM-02.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
