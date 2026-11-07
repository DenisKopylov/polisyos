# CYC-03 — Новая исследовательская основа без фиктивного нового кандидата

**LANE-01 · B09, B27, B28 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CYC-03.md), [исходная карточка](../05_Основания/Аудит/05_Источники/CYC-03_исходные_строки.txt), строки 508–616.
**Практический результат:** Пользователь видит новый содержательный расчёт при изменившемся основании, экономный reuse при полной эквивалентности и доступную историю ухудшений, а не только новый receipt.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Существующий acquisition dispatcher, полная эффективная quantity и retained evaluation.
- Актуальные grounding/value/VOI/requirement checks при численном reuse.
- Grammar guard для обычного grammar-driven advance.
- Stable subject и active problem basis; grammar-only rebind с domain/scope checks.
- Acquired data→native state/model→WMR/context producer и повторный owner read.
- Полные old/new refs и immutable old runs; сохранение occurrence identities.
- Текущий фронт выбирает новую occurrence даже при худшем результате.
- GET recomputes semantic identity и root-origin lineage; специальный continuation validator.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C03_C04_остатки:0 | REQ-CYC-03-01 | qualify: Actual A→B→B→B→C. |
| audit-residual:C03_C04_остатки:3 | REQ-CYC-03-06 | shared: ACQ-01 владеет общим profile expansion; CYC-03 — basis/occurrence. |
| audit-residual:C03_C04_остатки:4 | REQ-CYC-03-03 | capability: Не только запуск теста: поддержанный owner-bound новый transition. |
| audit-residual:C03_C04_остатки:5 | REQ-CYC-03-03 | capability: Не сливать равное число с независимостью наблюдения. |
| audit-residual:C03_C04_остатки:6 | REQ-CYC-03-05 | qualify: Actual consumers, не предположение по GET. |
| B09 | REQ-CYC-03-01, REQ-CYC-03-03, REQ-CYC-03-06 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B27 | REQ-CYC-03-02, REQ-CYC-03-03 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B28 | REQ-CYC-03-04, REQ-CYC-03-05 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0022 | REQ-CYC-03-01 | qualify: Существующий сильный sequential selector, не новый демонстрационный дубль. |
| remaining:0023 | REQ-CYC-03-03 | capability: Конечные transition profiles и реальный второй шаг. |
| remaining:0066 | REQ-CYC-03-02 | qualify: Раздельно grammar rebind и acquired world. |
| remaining:0067 | REQ-CYC-03-02, REQ-CYC-03-03 | capability: Содержательные изменения требуют своих owners, не служебных hints. |
| remaining:0068 | REQ-CYC-03-04, REQ-CYC-03-05 | qualify: Occurrence/removal controls и потребитель. |
| remaining:0069 | REQ-CYC-03-05 | qualify: Конечный surface census, GET не обобщается на UI/export. |

## 3. Нормативные REQ и конкретное решение

### REQ-CYC-03-01 — qualify
При equivalent эффективном input новое admission должно сохранить прежние numerical refs/bytes, но выполнить актуальные cheap grounding/value/VOI/requirement consequences; при different вызвать реальный повтор N5, при not_established не утверждать reuse.

**Решение на существующих владельцах.** Оставить AcquisitionEvaluationBasis/dispatcher единственными owners сравнения. Сравнивать сохранённое typed содержимое state/rules/NCM/request/model/configuration/implementation, не только scalar/hash. Existing equivalent-ветвь выполняет _current_cheap_continuation под native-writer fence; different вызывает bridge.resume. Новые audit timestamps/UUID не самостоятельная причина работы.
**Приёмка:** TEST-CYC-03-01.

### REQ-CYC-03-02 — qualify
Revision служебных grammar hints должна перевыпускать context существующим owner; смена предмета, модели, популяции или метода не должна идти через grammar-only rebind старого доказательства.

**Решение на существующих владельцах.** Сохранить stable design_problem_ref и active design_problem_basis_ref, _rebind_cycle_substrate_context_for_revision и acquisition materialization/readback. Вход rebind ограничить действительно разрешёнными hints; содержательные поля маршрутизировать к их настоящим model/data/context owners. Не удалять enforce_no_retry_without_new_grammar: он нужен обычному grammar advance.
**Приёмка:** TEST-CYC-03-02.

### REQ-CYC-03-03 — capability
Для model/method/constraint change и разрешённой независимой реплики должен быть задан исполняемый тип перехода с целью и полной dependency basis; новый независимый measurement равного значения не теряет independence/time/sample-size.

**Решение на существующих владельцах.** Расширять существующий basis/dispatch profile, а не общий research bypass. Составить конечную таблицу четырёх видов перехода: producer изменения, fields влияния, actual consumer, повторяемый шаг и разрешённый бюджет. Для поддержанного нового model/method и replica связать конкретный owner; если интерфейса нет, реализовать один typed transition в текущем owner с явным not_supported для остальных. Повторные технические attempts отделены от новых scientific samples.
**Приёмка:** TEST-CYC-03-03.

### REQ-CYC-03-04 — qualify
История должна сохранять все occurrences и old runs, а current frontier/потребитель выбирать последнюю валидную occurrence, включая ухудшение; promotion не привязывается только к candidate_id.

**Решение на существующих владельцах.** Использовать existing tuple(candidate_id, content_hash, cycle_index), _current_candidate_summaries/_derive_fronts и validate_acquisition_overlay_continuation. Не применять blind dedupe. Старый run/bytes неизменны, новая summary-проекция может менять currentness. origin_source_ref сохраняет root-origin, не принудительно immediate predecessor.
**Приёмка:** TEST-CYC-03-04.

### REQ-CYC-03-05 — qualify
Каждый реально используемый HTTP/export/UI consumer должен показывать выбранную current occurrence и происхождение numerical результата, не выдавая retained computation за новое исполнение.

**Решение на существующих владельцах.** Начать с routes/runs.py full semantic join; конечный census активных consumers по DTO/caller references. Для выбранного реального export/UI пройти его projection, сохранить exact selected refs/limits. Не обещать проверку всех UI на основании GET; если реальный потребитель отсутствует, назвать конкретный surface gap и добавить согласованную projection в существующем API/Atlas owner.
**Приёмка:** TEST-CYC-03-05.

### REQ-CYC-03-06 — capability
Второй содержательно иной поддержанный case должен проходить тот же acquisition/basis механизм с раскрытым объёмом специальной подготовки.

**Решение на существующих владельцах.** Общий owner расширения acquisition profile — ACQ-01; здесь проверить identity/continuation semantics. Выбрать существующий другой slot/resource, не rename первого; зависимости units/time/causal role фиксируются в typed profile. LLM может предложить постановку, но не подделывает actual basis.
**Приёмка:** TEST-CYC-03-06.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-CYC-03-01 · NOT_RUN
- **Setup:** Существующий tests/integration/core_runtime/test_acquisition_retained_sequential_served.py и его selector test_served_actual_acquisition_retains_equal_b_then_reenters_for_c; реальные N5/store, локальные разрешённые source bytes.
- **Действие:** Исполнить A→B→B→B→C с двумя новыми одинаковыми admissions и затем −17.1→−9.0.
- **Oracle:** Равные B сохраняют exact N4/context/input/execution/result refs и bytes, но имеют новые admission/current-continuation; C вызывает actual controller и меняет dependent input/result.
- **Positive / negative / boundary:** Unknown basis не equivalent; failure нового расчёта не возвращает старый success под новой датой; no fake grammar/ID-only retry.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-03-02 · NOT_RUN
- **Setup:** Настоящий DesignProblem и source-backed context; existing fence/context test test_fenced_nl_owner_reopens_same_store_candidate_world_and_refuses_without_fence.
- **Действие:** Раздельно изменить служебный hint, problem text при том же ID, population, model/method binding, снять execution fence.
- **Oracle:** Только разрешённый hint получает новый согласованный context; иной предмет не принимает old context; actual owner reread и правильный error code.
- **Positive / negative / boundary:** Допустимая revision положительна; foreign/stale/terminal lease отказывает до использования; grammar guard сохраняется.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-03-03 · NOT_RUN
- **Setup:** Один текущий compatible model/method resource и объявленный experimental replicate intent; два observations с равным числом, но разным independence/time; контроль того же occurrence.
- **Действие:** Пропустить объявленные изменения через actual continuation, сравнить basis и consumed request; выполнить новый sample с отдельным seed/measurement identity.
- **Oracle:** Meaningful declared change вызывает нужный owner ровно один раз; equal scalar с новой независимой информацией не сливается; технический replay идемпотентен.
- **Positive / negative / boundary:** Положительный полезный второй исследовательский шаг обязателен; неопределённый owner route даёт адресный непокрытый профиль, не универсальную поддержку.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-03-04 · NOT_RUN
- **Setup:** Два цикла того же stable candidate, первый research, второй quarantine/blocked; old/new N4/N5 и source lineage.
- **Действие:** Сохранить, открыть новый HTTP reader, затем отдельно подменить только occurrence cycle/hash и root origin.
- **Oracle:** Текущий front показывает второе худшее состояние; оба historical runs читаются; чужая occurrence/ref и inconsistent lineage отвергаются.
- **Positive / negative / boundary:** Дубликат exact occurrence запрещён; актуальный adverse result не заменяется удобным прошлым success.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-03-05 · NOT_RUN
- **Setup:** Persisted sequence TEST-01 и реальные активные readers; новый app/reader, для browser нужен отдельно разрешённый тестовый frontend.
- **Действие:** Открыть current и historical представления через actual consumers, заменить selected ref либо удалить bytes.
- **Oracle:** Current и historical метки, effect/basis и retained-versus-reexecuted различимы; missing не выглядит числом/успехом.
- **Positive / negative / boundary:** Полезный результат доступен consumer; отсутствие browser execution остаётся UNRUN, не скрывается screen snapshot.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-03-06 · NOT_RUN
- **Setup:** Совместный E02-I01-B с ACQ-01: другой осмысленный ресурс и явная model/input связь.
- **Действие:** Подключить ресурс через common adapter, пройти новый admission и subsequent evaluation.
- **Oracle:** Есть actual changed/retained decision на полной basis, таблица manual/server-derived preparation и новый полезный output.
- **Positive / negative / boundary:** Нет special-case switch по имени, invented units или требования нулевого нового кода при реально новой семантике.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-B, E02-X02**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- REQ-01 domain/construct contract → ACQ-01 actual admission/world → CYC-03 continuation/current occurrence.
- generation_cycle.py общий mutex с CYC-01/02/04/05; ACQ-01 writer общего world bridge, CYC-03 writer basis-transition/occurrence.
- Независимая реплика не создаёт empirical authority автоматически; SIM-03 владеет replication statistics.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Универсальность здесь — повторяемое расширение одного basis/dispatch механизма на обоснованный новый класс изменения, не разрешение бесконечного retry.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/runtime/quality/acquisition_evaluation_dispatch.py:851–883](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation_dispatch.py#L851-L883) — `if comparison == "equivalent" and prior is not None:`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:11928–11960](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L11928-L11960) — `def _rebind_cycle_substrate_context_for_revision`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:3296–3328](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L3296-L3328) — `def validate_acquisition_overlay_continuation`.
- [policy-engine/src/polisyos/runtime/http/routes/runs.py:843–875](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/routes/runs.py#L843-L875) — `origin_source_ref`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0025 | REQ-CYC-03-01, TEST-CYC-03-01 | Существующий acquisition dispatcher, полная эффективная quantity и retained evaluation. |
| preserve:0026 | REQ-CYC-03-01, TEST-CYC-03-01 | Актуальные grounding/value/VOI/requirement checks при численном reuse. |
| preserve:0027 | REQ-CYC-03-02, TEST-CYC-03-02 | Grammar guard для обычного grammar-driven advance. |
| preserve:0086 | REQ-CYC-03-02, TEST-CYC-03-02 | Stable subject и active problem basis; grammar-only rebind с domain/scope checks. |
| preserve:0087 | REQ-CYC-03-02, REQ-CYC-03-06, TEST-CYC-03-02, TEST-CYC-03-06 | Acquired data→native state/model→WMR/context producer и повторный owner read. |
| preserve:0088 | REQ-CYC-03-04, TEST-CYC-03-04 | Полные old/new refs и immutable old runs; сохранение occurrence identities. |
| preserve:0089 | REQ-CYC-03-04, TEST-CYC-03-04 | Текущий фронт выбирает новую occurrence даже при худшем результате. |
| preserve:0090 | REQ-CYC-03-04, REQ-CYC-03-05, TEST-CYC-03-04, TEST-CYC-03-05 | GET recomputes semantic identity и root-origin lineage; специальный continuation validator. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/CYC-03.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
