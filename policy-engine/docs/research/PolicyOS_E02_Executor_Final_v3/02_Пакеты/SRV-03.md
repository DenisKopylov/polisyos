# SRV-03 — Реальный autotune consumer и завершённый search cutover

**LANE-02 · LA-015 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/SRV-03.md), [исходная карточка](../05_Основания/Аудит/05_Источники/SRV-03_исходные_строки.txt), строки 1945–2044.
**Практический результат:** Обычный кандидат и контрольный sentinel реально проходят codec/benchmark/reader, partial run переживает сбой; LA-015 принимается по реальному consumer, не новому имени класса.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- single native driver/lifecycle/state owner
- actual runner direct construction, typed codecs, source/promotion boundaries
- independent run snapshots, bounded empty, source-budget binding scope
- supported compatibility addresses and historical semantics
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C15_остатки:0 | REQ-SRV-03-01 | fix: Typed role bridge, не просто pop. |
| audit-residual:C15_остатки:1 | REQ-SRV-03-02 | shared: Один CTL-01 interruption mechanism, actual runner delivery здесь. |
| audit-residual:C15_остатки:2 | REQ-SRV-03-03 | fix: Source-qualified warm fixture. |
| audit-residual:C15_остатки:3 | REQ-SRV-03-04 | qualify: Actual complex consumer/RNGcompatibility. |
| audit-residual:C15_остатки:4 | REQ-SRV-03-03 | lifecycle: Конечный reserved field contract и реальные схемы. |
| LA-015 | REQ-SRV-03-01, REQ-SRV-03-02, REQ-SRV-03-03, REQ-SRV-03-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0382 | REQ-SRV-03-01 | fix: Control role до actual benchmark/registry. |
| remaining:0383 | REQ-SRV-03-02 | shared: CTL-01 owns finalization, SRV-03 actual persist/recoveryconsumer. |
| remaining:0384 | REQ-SRV-03-04 | shared: CTL-03 counters и SRV-01 atomic/runaffinity reused. |
| remaining:0385 | REQ-SRV-03-04 | qualify: Nativeconsumer/census/history. |
| remaining:0386 | REQ-SRV-03-04 | superseded: Фраза companions not reviewed историческая: CTL-02/STP-01 audit/spec готовы, их приёмка по-прежнему обязательна. |

## 3. Нормативные REQ и конкретное решение

### REQ-SRV-03-01 — fix
Sentinel role должна оставаться организационной metadata до benchmark/registry/history, не входить как неизвестное поле mutation и не исчезать перед promotion.

**Решение на существующих владельцах.** В SearchLoopRunner evaluation bridge использовать existing typed CandidateProposal/service envelope: отделить именно известную __sentinel__ роль от subject до PydanticMutationCodec, передать роль evaluator/registry policy и lifecycle transition. Сохранять строгий extra=forbid для неизвестных subject keys; не pop всех underscore. ChampionRegistry не рассматривает sentinel как обычное promotion независимо от callback порядка. Предмет decode должен совпасть с source identity, role записывается отдельно.
**Приёмка:** TEST-SRV-03-01.

### REQ-SRV-03-02 — capability
Interrupted actual runner должен предоставлять сохранённый partial run/ref и явное разрешённое продолжение без повторения уже завершённого work и без нового run-affinity обхода.

**Решение на существующих владельцах.** Потребить CTL-01 failure-finalization contract в SearchLoopRunner: persist completed candidates/evaluations уже существующим store, связать run snapshot/error и budget/strategy checkpoint. Resume принимает exact run/basis и совместимый CTL-02 state, не просто имя candidate=resumed; late tells через SRV-01 admission. Original exception/cancel remains; lock/binding scope release гарантирован.
**Приёмка:** TEST-SRV-03-02.

### REQ-SRV-03-03 — fix
Warm history и reserved semantic/strategy fields должны иметь явный source-qualified contract; тест не требует training credit от unbound scalar.

**Решение на существующих владельцах.** Исправить stale warm trace fixture: либо actual compatible source-results/assessment→AVAILABLE, либо ожидать diagnostic historical row/training0. Warm-start delivery generator не lifecycle initial_evaluations и не proof GP conditioning (OPT/TRN). Finite census custom mutation schemas/aliases для semantic/_strategy_metadata: поддержанный subject field сохранять; зарезервированную transport роль декларировать в envelope/version и отвергать conflicting meaning, не молча default subject.
**Приёмка:** TEST-SRV-03-03.

### REQ-SRV-03-04 — qualify
LA-015 closure требует native actual runner traces, корректных RNG/stopping/counters и конечного совместимого retirement census; working facade не удаляется без основания.

**Решение на существующих владельцах.** Сохранить прямое создание _SearchLifecycleOwner/_NativeSearchServiceDriver — cutover уже есть. Использовать test_current_autotune_runner_characterizes_real_cas_consumer_path с запретом SearchController ctor/run, actual CAS/registry; добавить complex actual runner warm→sentinel→empty→exception→persisted resume, не REJECT переименованный error. CTL-02/STP-01 являются current spec dependencies, старое «нерассмотрены» superseded. Census python/import/string/serialized readers конечный; alias retirement только при migrating all supported callers.
**Приёмка:** TEST-SRV-03-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-SRV-03-01 · NOT_RUN
- **Setup:** Штатный SentinelInjector + строгий MutationArtifact subclass(value), actual Pydantic codec, benchmark, CAS/ChampionRegistry; ordinary same payload и malformed unknown field.
- **Действие:** Пройти actual SearchLoopRunner, inject sentinel после двух ordinary; fresh reader результата/registry.
- **Oracle:** Sentinel benchmark реально вызван, numerical контроль доступен, sentinel count/resource учтены; ordinary history/best/champion от него не улучшаются; ordinary positive проходит.
- **Positive / negative / boundary:** Удаление роли до lifecycle или одним pop перед codec недостаточно; неизвестный предметный key всё ещё rejected.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SRV-03-02 · NOT_RUN
- **Setup:** Actual runner good benchmark→exception/cancel after settlement; temporary store/registry и strategy checkpoint; fresh-process reader.
- **Действие:** Прервать, открыть partial, затем explicit resume с теми же accepted refs; изменённый source/run/strategy negative.
- **Oracle:** Предыдущий useful output доступен, расходы/attempts не исчезли, completed work не повторяется вслепую, continuation сохраняет subject и run ownership.
- **Positive / negative / boundary:** Не заявлять erased CAS из отсутствия SearchResult; не возвращать обычный success вместо ошибки и не запускать paid retry автоматически.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SRV-03-03 · NOT_RUN
- **Setup:** Existing test_srv_03 warm trace, source-bound/unbound rows, contextual warm_start_for_context, custom schema с явным semantic и reserved alias.
- **Действие:** Пройти actual codec/materialization/benchmark и проверить actual training consumer/subject hash.
- **Oracle:** Правомерная warm информация реально используется своим consumer; unbound не train; decoded subject соответствует persisted identity; не исчезают substantive поля.
- **Positive / negative / boundary:** Не объявлять все custom schemas сломаны по fixture; не ослаблять source guards ради старого training count 1.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SRV-03-04 · NOT_RUN
- **Setup:** Existing test_srv_03/test_srv_01/test_contracts; actual MethodJob route shared OPT-02, conditional tiny evaluator, supported Python3.14.
- **Действие:** Обычный и complex consumer trace, new-process readback, compare final/history/frontier/effective subject/costs/RNG; legacy addresses отдельно.
- **Oracle:** Один state owner, no old full-loop construction; изменены только намеренные bugs, не требовать parity с ошибкой. Каждый supported caller/reader disposition записан.
- **Positive / negative / boundary:** NOT_RUN остаётся NOT_RUN; нет blanket rm methods/search; snapshot reopen same process не independent restart.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-A, E02-I02-B**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- CTL01run/partial; CTL03counts/cost; SRV01acceptance; CTL02RNG; STP01stop — обязательные общие contracts.
- SRV-03 accountable LA-015 closure; CTL-01 phase 1 не закрывает целое. OPT-02 owns MethodJob binding; OPT-04 promotion atomicity, здесь sentinel role consumer.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Содержательная контрольная проверка должна реально выполняться, а не быть запрещена строгим codec или превращена в лучшего обычного кандидата. Настоящий partialresume повышает полезность без нового framework.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/autotune/runtime.py:1796–1828](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/runtime.py#L1796-L1828) — `class SearchLoopRunner`.
- [policy-engine/src/polisyos/scientist/methods/autotune/runtime.py:1938–1970](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/runtime.py#L1938-L1970) — `def _evaluate_candidate`.
- [policy-engine/src/polisyos/scientist/methods/autotune/models.py:728–760](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/models.py#L728-L760) — `class PydanticMutationCodec`.
- [policy-engine/src/polisyos/scientist/methods/search/sentinels.py:219–244](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/sentinels.py#L219-L244) — `def _decorated_sentinel`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0618 | REQ-SRV-03-04, TEST-SRV-03-04 | single native driver/lifecycle/state owner |
| preserve:0619 | REQ-SRV-03-01, REQ-SRV-03-04, TEST-SRV-03-01, TEST-SRV-03-04 | actual runner direct construction, typed codecs, source/promotion boundaries |
| preserve:0620 | REQ-SRV-03-02, REQ-SRV-03-04, TEST-SRV-03-02, TEST-SRV-03-04 | independent run snapshots, bounded empty, source-budget binding scope |
| preserve:0621 | REQ-SRV-03-03, REQ-SRV-03-04, TEST-SRV-03-03, TEST-SRV-03-04 | supported compatibility addresses and historical semantics |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/SRV-03.json). Аудит охватил 127/127; это не означает выполненных 127 ремонтов.
