# CYC-02 — Доступный N5 и честный положительный conditional N8

**LANE-01 · B04, B05, B08 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CYC-02.md), [исходная карточка](../05_Основания/Аудит/05_Источники/CYC-02_исходные_строки.txt), строки 867–979.
**Практический результат:** Настоящее сохранённое число достигает другого разрешённого процесса/потребителя как условный результат модели; исторические ограничения не блокируют чтение и не превращаются в authority.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Полный content-bound numerical payload и оригинальные historical bytes.
- Selected-profile CAS ref, tenant-owner, expected WMR/atoms/outcomes.
- Раздельные unavailable/integrity/binding исходы и честный persistence failure.
- K_sim остаётся доступным условным результатом, не K_world.
- Persisted full blockers и повторное currentness/source binding.
- No owner receipts, simulate_only и explicit low decision grade.
- Conditional численный результат не требует фиктивного treatment assignment.
- Candidate method-run artifact сохраняется без подмены production authority.
- LLM постановка допустима; её смысл и numerical result должны сохраниться.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C06_остатки:0 | REQ-CYC-02-01 | fix: Legacy projection/DTO согласование. |
| audit-residual:C06_остатки:1 | REQ-CYC-02-02 | fix: Fixture selected-view forwarding. |
| audit-residual:C06_остатки:2 | REQ-CYC-02-03 | qualify: Новый процесс, actual N5/CAS/N8. |
| audit-residual:C06_остатки:3 | REQ-CYC-02-05 | shared: SIM owns mathematical validity, CYC-02 propagation. |
| audit-residual:C06_остатки:4 | REQ-CYC-02-05 | qualify: Конечный consumer census и visible result. |
| B04 | REQ-CYC-02-02, REQ-CYC-02-03, REQ-CYC-02-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B05 | REQ-CYC-02-01, REQ-CYC-02-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B08 | REQ-CYC-02-03, REQ-CYC-02-04, REQ-CYC-02-05 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0009 | REQ-CYC-02-02 | fix: Точная fixture сигнатура. |
| remaining:0010 | REQ-CYC-02-03 | qualify: Реальный новый процесс и guards. |
| remaining:0011 | REQ-CYC-02-05 | shared: SIM mathematical owners + actual consumer. |
| remaining:0012 | REQ-CYC-02-01 | fix: Локальный контрпример проверяется native historical DTO. |
| remaining:0013 | REQ-CYC-02-01 | fix: Исторические bytes без contamination. |
| remaining:0019 | REQ-CYC-02-03, REQ-CYC-02-04 | qualify: Положительная настоящая цепочка. |
| remaining:0020 | REQ-CYC-02-04 | qualify: Не производить empirical authority из conditional. |
| remaining:0021 | REQ-CYC-02-05 | shared: Точечный consumer и SIM, не новый N8 engine. |

## 3. Нормативные REQ и конкретное решение

### REQ-CYC-02-01 — fix
Старый поддержанный N5 v1–v3 без позднего marker должен читаться в conditional N8 с явной unsupported interaction/sampling, не нарушая текущий DTO и не меняя signed bytes.

**Решение на существующих владельцах.** У existing _n8_sampling_uncertainty_limitations derive interaction_numeric_classification_unsupported при legacy numeric_interaction=unsupported, либо признать эквивалентное legacy ограничение в одном validator contract. Предпочесть additive текущую projection, не ослаблять ValuePortObservation authority shape. Проверить фактическую native reachability старого result, а не только helper transcription.
**Приёмка:** TEST-CYC-02-01.

### REQ-CYC-02-02 — fix
Fixture store должен поддерживать текущий put_json(return_selected_profile=True) и сохранять distinct generic/selected views.

**Решение на существующих владельцах.** Расширить _GenericDefaultN5Store.put_json совместимым параметром с точным forwarding к настоящему store; не удалять selected-profile request production writer. Отдельно проверять generic default view, выбранную N5 view и content-bound receipt.
**Приёмка:** TEST-CYC-02-02.

### REQ-CYC-02-03 — qualify
После завершения producer новый разрешённый процесс должен восстановить полный numerical payload и conditional N8 из exact selected CAS ref с исходными bindings.

**Решение на существующих владельцах.** Повторно использовать JointSimulationPort→persist_joint_simulation_result→load_joint_simulation_result→_DefaultSimulationBoundFoundryValuePort. Временный store/tenant и profile refs передать сериализованно; новая Python invocation не наследует объект памяти. Проверить WMR/atoms/outcomes/expected_request и typed reference, не artifact-id-alone shortcut.
**Приёмка:** TEST-CYC-02-03.

### REQ-CYC-02-04 — qualify
Conditional использование K_sim должно сохранять полный persisted blocker/currentness contract и не требовать synthetic treatment; эмпирическая authority остаётся отдельным путём.

**Решение на существующих владельцах.** Сохранить default conditional-before-Foundry routing, canonical source/context/profile/input/execution checks и no receipts. Candidate-fixture causal method artifact сохранять как candidate_fixture_value_run_not_authority. Не очищать blockers, не создавать treatment assignment и не подменять empirical owner, чтобы получить положительный статус.
**Приёмка:** TEST-CYC-02-04.

### REQ-CYC-02-05 — qualify
Actual API/Atlas consumer должен показывать точный выбранный numerical result и его basis/limits; математическая корректность выбранного профиля подтверждается отдельным независимым oracle.

**Решение на существующих владельцах.** Начать с действующего cycle enclosing N5 full ref и N8 value_ref, найти конечных readers по DTO/callers. Связать их на selected view, не считать строковый artifact ID standalone addressability. SIM-01/02/03 владеют missing/zero/comparator/replications/trajectory math; здесь единый small end-to-end до consumer, не повтор полного каталога.
**Приёмка:** TEST-CYC-02-05.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-CYC-02-01 · NOT_RUN
- **Setup:** Подлинная поддержанная historical форма v1/v2/v3 с валидным receipt/profile, без current-marker contamination; настоящий CAS/DTO. Current v4 positive.
- **Действие:** Сохранить старые bytes, загрузить load_joint_simulation_result→default conditional consumer и hash bytes повторно.
- **Oracle:** Получен value_conditional/simulate_only/low без owner receipts, legacy sampling/not-established и unsupported marker сохранены; старый SHA тот же.
- **Positive / negative / boundary:** Нельзя назначить high/value_ready, удалить другие blockers или назвать legacy interaction проверенной; malformed/unknown schema адресно отказана.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-02-02 · NOT_RUN
- **Setup:** tests/unit/remediation/test_cyc_02.py::_GenericDefaultN5Store; current actual persist/load functions.
- **Действие:** Вызвать нынешний writer, затем выбрать требуемый manifest profile и проверить другой profile/tampered bytes.
- **Oracle:** Нет unexpected keyword TypeError; actual selected ref имеет нужные kind/schema/digest, не случайный default.
- **Positive / negative / boundary:** Wrong view/blob/model сохраняет отказ; успешная фикстура не подставляет заранее готовый result.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-02-03 · NOT_RUN
- **Setup:** Existing _real_n5_observation использует actual NCM/controller; поддержанный Python3.14 и temporary CAS. Запуск нового subprocess разрешён исполнителю; здесь NOT_RUN.
- **Действие:** Произвести маленький реальный N5, завершить producer, отдельным процессом открыть store и вызвать canonical N8; затем missing/tamper/wrong model/tenant.
- **Oracle:** Совпадают numerical values/trajectory/units/model/limitations; fresh consumer получает полезный value_conditional; точные unavailable/integrity/binding исходы различимы.
- **Positive / negative / boundary:** Store отсутствует — отказ до работы; failed persistence после работы не становится доступным success по одному receipt hash.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-02-04 · NOT_RUN
- **Setup:** Real TEST-03 результат с допустимыми limitations; неизвестный blocker, stale/foreign source; empirical path без owner treatment.
- **Действие:** Пройти обе branches и сохранить их проекции.
- **Oracle:** Условное число положительно доступно при своих limits; эмпирический путь без основания остаётся treatment_assignment_not_owner_derived/ограниченным.
- **Positive / negative / boundary:** Unknown blocker не пропадает, K_sim не меняет K_world/N9; отсутствие empirical authority не удаляет полезное candidate число.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-02-05 · NOT_RUN
- **Setup:** Тот же declared procurement/model profile, что в test_configured_candidate_simulation_served.py::test_served_configured_profile_runs_real_n4_through_candidate_n5_and_rejects_drift (его actual NCM, target baseline и materialization, не скопированный численный output). Actual выбранный API/Atlas projection читает сохранённый результат shared E02-I01-A через новый reader process.
- **Действие:** Прочитать новый процесс TEST-03 результат через потребитель; изменить model/baseline/trajectory и неизвестный limitation по одному.
- **Oracle:** Для этого неизменённого profile expected_effect = outcome_per_target_unit * (materialization.value - target_baseline) = 0.5 (algebraic assertion abs_tol=1e-12); все actual replication effects должны укладываться в уже установленный для этого NCM допуск 0.02. Допуск не переносится на другой model/profile. Consumer показывает units/horizon/source/basis и ограничения; замена model/baseline/trajectory не даёт green result; degraded view доступен честно.
- **Positive / negative / boundary:** Равенство producer→reader само по себе не correctness; fresh GET не автоматически новый процесс; missing UI не объявлять проверенным.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-A, E02-X01**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- CYC-01 ordinary served entry; CYC-02 owns conditional projection/legacy fix/new-process reader.
- SIM-03 owns model-bound comparator и interaction math; CYC-05 authored child relationships не заменяет joint numerical semantics.
- Общий generation_cycle.py writer координируется с соседними CYC/ACQ; не создавать второй CAS/N8.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Positive capability здесь уже существует: квалифицировать её и исправить адресные стыки, а не заново проектировать N8. Не ждать empirical каталога ради честного conditional числа.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:6940–6972](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L6940-L6972) — `def _n8_interaction_qualification`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:6961–6993](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L6961-L6993) — `def _n8_sampling_uncertainty_limitations`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:7008–7040](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L7008-L7040) — `def _conditional_simulation_value_observation`.
- [policy-engine/tests/unit/remediation/test_cyc_02.py:829–861](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cyc_02.py#L829-L861) — `class _GenericDefaultN5Store`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0010 | REQ-CYC-02-01, REQ-CYC-02-03, TEST-CYC-02-01, TEST-CYC-02-03 | Полный content-bound numerical payload и оригинальные historical bytes. |
| preserve:0011 | REQ-CYC-02-02, REQ-CYC-02-03, TEST-CYC-02-02, TEST-CYC-02-03 | Selected-profile CAS ref, tenant-owner, expected WMR/atoms/outcomes. |
| preserve:0012 | REQ-CYC-02-03, TEST-CYC-02-03 | Раздельные unavailable/integrity/binding исходы и честный persistence failure. |
| preserve:0013 | REQ-CYC-02-04, TEST-CYC-02-04 | K_sim остаётся доступным условным результатом, не K_world. |
| preserve:0014 | REQ-CYC-02-01, REQ-CYC-02-04, TEST-CYC-02-01, TEST-CYC-02-04 | Persisted full blockers и повторное currentness/source binding. |
| preserve:0015 | REQ-CYC-02-04, TEST-CYC-02-04 | No owner receipts, simulate_only и explicit low decision grade. |
| preserve:0022 | REQ-CYC-02-04, TEST-CYC-02-04 | Conditional численный результат не требует фиктивного treatment assignment. |
| preserve:0023 | REQ-CYC-02-04, TEST-CYC-02-04 | Candidate method-run artifact сохраняется без подмены production authority. |
| preserve:0024 | REQ-CYC-02-05, TEST-CYC-02-05 | LLM постановка допустима; её смысл и numerical result должны сохраниться. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/CYC-02.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
