# ACQ-01 — Явное требование → принятие источника → реальный зависимый расчёт

**LANE-01 · B12, LA-046 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/ACQ-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/ACQ-01_исходные_строки.txt), строки 617–778.
**Практический результат:** Приобретённое разрешённое основание доходит до настоящего state/model/N5; одинаковый вход экономно переиспользуется, а новая информация меняет результат с сохранёнными ограничениями.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Compiler/planner persisted readback до action.
- Настоящие existing acquisition, epoch, Data Forge/Fabric/Foundry/context/N5 owners.
- Local contract-testing receipt не заменяет native admission.
- Сохранение актуальных ограничений при retained result и при failed new evaluation.
- Необходимость source-backed compiler/planner readback и реальные consumers.
- Ограниченный controlled refresh не выдаётся за универсальную NLP/discovery способность.
- Защищённые различения: LK24, LK31. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C03_C04_остатки:1 | REQ-ACQ-01-02, REQ-ACQ-01-03 | qualify: Actual missing-bytes и state/NCM controls. |
| audit-residual:C03_C04_остатки:2 | REQ-ACQ-01-01 | shared: REQ-01 — единственный writer normalizer. |
| audit-residual:C03_C04_остатки:3 | REQ-ACQ-01-05 | capability: ACQ-01 — общий profile expansion; CYC-03 проверяет continuation. |
| audit-residual:C03_C04_остатки:7 | REQ-ACQ-01-04 | qualify: Recovery/concurrency на том же admitted profile. |
| B12 | REQ-ACQ-01-02, REQ-ACQ-01-03, REQ-ACQ-01-04, REQ-ACQ-01-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| LA-046 | REQ-ACQ-01-01, REQ-ACQ-01-05, REQ-ACQ-01-06 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0030 | REQ-ACQ-01-02, REQ-ACQ-01-03 | qualify: Existing bounded route сохраняется. |
| remaining:0031 | REQ-ACQ-01-05 | capability: Второй meaningful input и явная агрегация, если нужна. |
| remaining:0032 | REQ-ACQ-01-06 | shared: Полный LA-046 только REQ-01+ACQ-01; N8/N9 не выводится. |
| remaining:0463 | REQ-ACQ-01-01 | shared: Domain implementation REQ-01; ACQ actual consumer. |
| remaining:0464 | REQ-ACQ-01-01, REQ-ACQ-01-05, REQ-ACQ-01-06 | capability: Две области через реальный resolver/consumer. |
| remaining:0465 | REQ-ACQ-01-03 | shared: Sequential orchestration CYC-03, actual acquisition здесь. |

## 3. Нормативные REQ и конкретное решение

### REQ-ACQ-01-01 — fix
Actual N7 должен передавать полный text/domain/scope/explicit constructs и обязательный resolver; пустой/unbound denominator не трактуется как отсутствие потребности или successful acquisition.

**Решение на существующих владельцах.** Сохранить _n7_data_requirement_basis_with_report→DataRequirementCompiler(capability_resolver=...) и report readback. Domain normalizer единолично REQ-01; здесь перевод его existing typed input error (новый тип только при доказанной необходимости) в адресный GenerationCycleError/continuation limitation. Сентябрьское explicit specs precedence не восстанавливает arbitrary raw data_requirement_specs: текущие inputs помечаются unbound, typed gap только маршрутизирует compiler-owned denominator.
**Приёмка:** TEST-ACQ-01-01.

### REQ-ACQ-01-02 — qualify
Typed planner plan должен передавать exact compiler/planner report refs фактическому executor; consumer обязан перечитать bytes до разрешённого действия.

**Решение на существующих владельцах.** Existing run plan-ветвь уже вызывает _run_n7_acquisition_if_requested: не восстанавливать старое else и не строить второй runtime. Сверить input hash, MeasurementRoot/specs/capability resolutions, planner route и gateway; missing report/readback даёт текущие адресные ошибки до run_acquisition_closed_loop.
**Приёмка:** TEST-ACQ-01-02.

### REQ-ACQ-01-03 — qualify
Принятые observation bytes должны материализовать действительный world/state/model/context и попасть в N5; новое receipt имя само по себе не world growth.

**Решение на существующих владельцах.** Сохранить AcquisitionWorldGrowthBridge и _prepare_candidate_world_context/_candidate_world_context_handoff: route/action/lease → verified passport/epoch/projection → Data Forge → Fabric/Foundry state/rules → WMR/model/context persist/readback → bridge.resume. Local authority_scope=contract_testing receipt не заменяет native admission. Полная equality сверяет все существенные state/rule/NCM/request поля, не только target scalar.
**Приёмка:** TEST-ACQ-01-03.

### REQ-ACQ-01-04 — qualify
Recovery и concurrent frontier updates не должны публиковать результат под устаревшей route/admission/basis; повтор принятого operation не удваивает эффект.

**Решение на существующих владельцах.** Использовать existing operation lock/recovery pointers и post-N5 revalidation, не держать глобальный writer fence весь async расчёт. Перед terminal receipt перечитать current growth/admission/projection и route selection; stale computation сохранить как ограниченное диагностическое свидетельство, но не новый current selection. Recovery продолжает owner-defined idempotent шаг, не invent success.
**Приёмка:** TEST-ACQ-01-04.

### REQ-ACQ-01-05 — capability
Второй содержательный input/profile должен связываться существующим общим механизмом; многорядное/новое измерение требует явной units/time/population/aggregation semantics, не скрытой подстановки первой строки.

**Решение на существующих владельцах.** Current _prepare_candidate_world_context требует ровно одну строку. Выбрать реальный compatible иной slot/resource. При необходимости расширить один typed profile и его owner-owned transform/aggregation, хранить полный вход и потерю/aggregation rule; при неизвестном mapping запрашивать точное недостающее основание. Не создавать второй world store или case-name switch; data не заменяет causal model, license или authority.
**Приёмка:** TEST-ACQ-01-05.

### REQ-ACQ-01-06 — qualify
Полное LA-046 closure требует одновременно принятого REQ-01 generic contract и actual acquisition/reentry consumer в двух смысловых областях; conditional результат не закрывает N8/N9 authority.

**Решение на существующих владельцах.** ACQ-01 accountable owner общей closure. Свести evidence двух shared E02-I01-B ветвей: REQ domain/scope/resolver и producer→world→selected evaluation. Проверить новый consumer readback; не дублировать REQ compiler fix. Удержать LK24/LK31: active compiler, mandatory resolver guards и useful explicit semantics, retired family heuristic не возвращается.
**Приёмка:** TEST-ACQ-01-06.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-ACQ-01-01 · NOT_RUN
- **Setup:** Два различных generic statements/domain и explicit scopes, actual compiler/injected resolver; отдельные malformed/unknown, optional/required resolver и raw-spec inputs.
- **Действие:** Пройти реальный N7, сохранить report/specs/query; выполнить supported typed any-of route и сырой specs override negative.
- **Oracle:** Разные семантические запросы не превращаются в общий fiscal/annual; owner-backed declared requirement доходит до resolver; unbound override не инициирует acquisition.
- **Positive / negative / boundary:** Положительный explicit construct и unknown-with-limitation работают по REQ-01 contract; no need и not-derived различимы.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-ACQ-01-02 · NOT_RUN
- **Setup:** Существующий tests/integration/core_runtime/test_acquisition_authority_served.py selector test_served_acquisition_binds_n7_compiler_and_planner_cas_before_reentry; локальный допустимый source.
- **Действие:** Запустить positive; затем удалить только compiler CAS bytes, отдельно planner bytes, сохранив inline-shaped поля и refs.
- **Oracle:** Positive реально вызывает permitted gateway; negatives дают n7_compiler_report_readback_failed / acquisition_planner_report_readback_failed, без действия по недоступному основанию.
- **Positive / negative / boundary:** План/URL не receipt принятого источника; отказ permissions/budget остаётся, live/paid provider не требуется.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-ACQ-01-03 · NOT_RUN
- **Setup:** Actual source admission fixture и настоящие Data Forge/Fabric/Foundry/context/N5 owners, один выбранный observation row по текущему профилю.
- **Действие:** Пройти positive и по одному заменить non-target state component, source_path, baseline и NCM при той же declaration.
- **Oracle:** Positive numerical output потребляет изменённое значение; каждый foreign constituent отказывает до falsely current receipt. Исторические bytes остаются.
- **Positive / negative / boundary:** Новый admission с equivalent полной basis может retained result по CYC-03; failed new N5 не выдаёт прежний success.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-ACQ-01-04 · NOT_RUN
- **Setup:** Один bounded acquisition, controlled barrier перед async N5 завершением; второй разрешённый actor обновляет выбранную projection/route.
- **Действие:** В первой ветви прервать и возобновить в каждой persisted boundary; во второй сменить frontier во время N5 и завершить старую работу.
- **Oracle:** Ровно один terminal admitted current outcome на согласованной basis; stale route не promoted; partial bytes доступны, old success не замещён ложным новым.
- **Positive / negative / boundary:** Одинаковый operation повторно идемпотентен; чужой scope/lease rejected; concurrency test не утверждает freeze всего мира.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-ACQ-01-05 · NOT_RUN
- **Setup:** Другой реальный поддержанный source/resource, чем controlled original; если rows>1 — объявленное правило, denominator и независимый простой oracle.
- **Действие:** Через common resolver/profile admission материализовать новый input и сравнить dependent output; перестановка rows/units/time controls.
- **Oracle:** Второй полезный result проходит тот же chain; manual/server-derived preparation явно измерена; неизвестность не становится нулём.
- **Positive / negative / boundary:** Неподдержанная агрегация не маскируется single-row; compatible added resource обнаруживается без новой ветки по его ID.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-ACQ-01-06 · NOT_RUN
- **Setup:** Artifacts TEST-01–05, REQ-01 domain regressions и CYC-03 sequential readback.
- **Действие:** Сверить exact source IDs, фактические queries/consumer refs и отрицательный missing-requirement outcome.
- **Oracle:** Обе области имеют различимый смысл и реальное потребление, no silent legacy fallback; closure сообщает точный envelope и оставшиеся authority/capability пределы.
- **Positive / negative / boundary:** Отсутствие native execution или только RecordingCompiler не принимается за closure; полезная candidate работа не ждёт полного empirical каталога.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-B, E02-X02**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- REQ-01 normalizer/report contract перед ACQ full closure; CYC-03 owns basis/occurrence and reuse semantics.
- Shared generation_cycle.py mutations выполняет один writer по agreed patch order; no independent duplicated compiler adapter.
- Source trust/acquisition owners других lanes остаются настоящими boundaries; fixture network допустим, admission/consumer не подменять.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Практическая польза — не получение красивого плана, а изменение потребляемого model input либо обоснованная экономия N5. Free-grow расширяет typed resource/profile, не превращает всякий knowledge gap в нехватку строк.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:9937–9969](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9937-L9969) — `def _n7_data_requirement_basis_with_report`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:9542–9574](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9542-L9574) — `def _run_n7_acquisition_if_requested`.
- [policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py:2274–2306](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2274-L2306) — `def _prepare_candidate_world_context`.
- [policy-engine/src/polisyos/runtime/quality/acquisition_evaluation_dispatch.py:851–883](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation_dispatch.py#L851-L883) — `if comparison == "equivalent" and prior is not None:`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0032 | REQ-ACQ-01-02, TEST-ACQ-01-02 | Compiler/planner persisted readback до action. |
| preserve:0033 | REQ-ACQ-01-03, TEST-ACQ-01-03 | Настоящие existing acquisition, epoch, Data Forge/Fabric/Foundry/context/N5 owners. |
| preserve:0034 | REQ-ACQ-01-03, TEST-ACQ-01-03 | Local contract-testing receipt не заменяет native admission. |
| preserve:0035 | REQ-ACQ-01-03, REQ-ACQ-01-04, TEST-ACQ-01-03, TEST-ACQ-01-04 | Сохранение актуальных ограничений при retained result и при failed new evaluation. |
| preserve:0762 | REQ-ACQ-01-01, REQ-ACQ-01-02, TEST-ACQ-01-01, TEST-ACQ-01-02 | Необходимость source-backed compiler/planner readback и реальные consumers. |
| preserve:0763 | REQ-ACQ-01-05, REQ-ACQ-01-06, TEST-ACQ-01-05, TEST-ACQ-01-06 | Ограниченный controlled refresh не выдаётся за универсальную NLP/discovery способность. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/ACQ-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
