# SIM-01 — Полная применимость плана до выбора

**LANE-01 · B06, B07 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/SIM-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/SIM-01_исходные_строки.txt), строки 1091–1177.
**Практический результат:** Непригодный первый engine не лишает пользователя имеющегося подходящего второго; принятый результат связан с фактической физической спецификацией, а журнал отказов сохраняется.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Attempted-engine history remains complete
- Actual request-aware selected-result validation, seed/plan/atom matching
- Selected CAS view and explicit no-request provenance limitation
- Coupling/temporal/atom composition checks before selected return
- No-run when all candidates rejected
- Budget/access protections and useful optional defaults
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C08_остатки:0 | REQ-SIM-01-01 | fix: Согласовать preflight с реальным required-vector contract. |
| audit-residual:C08_остатки:1 | REQ-SIM-01-02, REQ-SIM-01-03 | qualify: Существующие сильные native tests сначала использовать. |
| audit-residual:C08_остатки:2 | REQ-SIM-01-04 | capability: Установить actual producer и связать supported alternate, не обещать automatic universal model choice. |
| B06 | REQ-SIM-01-02, REQ-SIM-01-03 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B07 | REQ-SIM-01-01, REQ-SIM-01-02, REQ-SIM-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0014 | REQ-SIM-01-02, REQ-SIM-01-03 | qualify: Native выбранный backend/adapter/CAS. |
| remaining:0015 | REQ-SIM-01-03 | qualify: Forged reissued receipt и same-triple changed plan. |
| remaining:0016 | REQ-SIM-01-01 | fix: Engine-owned required input preflight. |
| remaining:0017 | REQ-SIM-01-01 | qualify: Реальный viable second и controls. |
| remaining:0018 | REQ-SIM-01-04 | capability: Actual upstream multi-plan path, singleton сохранить. |

## 3. Нормативные REQ и конкретное решение

### REQ-SIM-01-01 — fix
Обязательные фактические coupled inputs должны проверяться bounded engine-owned preflight до selected; отсутствие/неверная форма initial_income отклоняет этот план, не весь допустимый список.

**Решение на существующих владельцах.** Выделить дешёвый общий input validation у coupled method owner и вызвать из _select_coupled_engine/существующего selection loop; runner использует тот же контракт. Проверять реальный coupled_state, не только наличие signature slot. Не запрещать отсутствующие initial_savings/is_employed/risk_aversion, когда method задаёт законный default. Preflight не выполняет симуляцию и не делает catch-all retry после расходов.
**Приёмка:** TEST-SIM-01-01.

### REQ-SIM-01-02 — qualify
Coupling, actual horizon и atom composition должны проверяться до окончательного выбора; unsupported history не запрещает корректный selected result.

**Решение на существующих владельцах.** Сохранить existing _select_engine порядок selector→coupling→temporal→composition→selected; request.horizon.steps определяет multi-period даже без caller-label. Result verifier не any(non_selected), а точное согласование выбранного плана. Нельзя подменить joint coupling суммой independent effects.
**Приёмка:** TEST-SIM-01-02.

### REQ-SIM-01-03 — qualify
Selected numerical result должен проверяться относительно actual request/plan/seed/model/atoms/outcomes; согласованно пересчитанный receipt не легализует чужую physical ref.

**Решение на существующих владельцах.** JointSimulationPort передаёт request в _joint_simulation_port_outcome/validate_selected_result, load_joint_simulation_result(expected_request=...) сохраняет selected manifest view. Полная plan.model_dump и runtime refs входят в physical identity; compare projection effects отдельно от raw work. Историческое чтение без request сохраняет n5_execution_request_provenance_not_established, не blanket отказ.
**Приёмка:** TEST-SIM-01-03.

### REQ-SIM-01-04 — capability
Поддержанный upstream producer альтернатив должен передавать несколько семантически сопоставимых планов существующему N5 без потери списка; singleton допустим при одном реальном варианте.

**Решение на существующих владельцах.** C08-G1 не доказывает отсутствие всех callers: сначала finite census factory/typed builders и actual served handoff. Для выбранного multi-method case расширить существующий typed request builder/profile так, чтобы admitted alternatives с same estimand/scope/horizon доходили в engine_plan; owner validates bindings каждого. LLM может предложить plans, но method registry/input preflight решают исполнимость. Не требовать всем запросам два метода и не создавать новый optimizer.
**Приёмка:** TEST-SIM-01-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-SIM-01-01 · NOT_RUN
- **Setup:** Настоящие WMR/registry/request с двумя coupled plans: первый missing/2D initial_income, второй корректный finite vector; actual backend counter.
- **Действие:** Запустить actual _select_engine→controller→adapter; затем оба bad, wrong domain, optional-default inputs и общий budget exhausted.
- **Oracle:** Первый producer не вызван, rejection reason сохранён; второй действительно считает и даёт читаемое число; all-bad no-run.
- **Positive / negative / boundary:** Global resource/access failure не обходится вторым engine; optional defaults сохраняются; known bad first не создаёт physical failed work.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-01-02 · NOT_RUN
- **Setup:** Существующий tests/unit/remediation/test_sim_01.py: NCM/coupling→coupled, static→stock-flow и both-unsupported paths, actual backend где предусмотрен.
- **Действие:** Исполнить эти малые native cases, сохранить engine decision history и actual chosen output.
- **Oracle:** Неподходящий первый оставляет причину, selected второй принимается в области; no-run сохраняет весь отказный denominator.
- **Positive / negative / boundary:** Не объявлять пять engine kinds проверенными по injected selector; unknown/system-wide coupling guards остаются.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-01-03 · NOT_RUN
- **Setup:** Actual finite result и CAS; existing forged-reference test и same engine/method/objective triple с изменённым variable map/seed/plan.
- **Действие:** Подменить ref и work facts, пересчитать валидный receipt; прочитать actual consumer с правильным и чужим request.
- **Oracle:** Foreign physical spec отвергается даже при корректном hash; unchanged positive readback содержит весь history; без request результат только limited candidate.
- **Positive / negative / boundary:** Нет снятия selected profile/tenant/model guard; один selected label не proof.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SIM-01-04 · NOT_RUN
- **Setup:** Один реальный upstream candidate с двумя supported compatible plans и один genuine singleton; не подавать Python-list вручную как доказательство server discovery.
- **Действие:** Пройти actual proposal/profile→builder→controller→consumer; заблокировать первый input и наблюдать второй.
- **Oracle:** Реальные alternatives дошли, второй численно полезен, подготовка/selection envelope раскрыты; singleton не становится error.
- **Positive / negative / boundary:** Несопоставимый outcome/estimand не удачный fallback; new compatible method resource подключается общим контрактом.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-A**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- SIM-01 owns engine-plan input preflight; CYC-04 owns кандидатные alternatives после локального N5/N8 отказа.
- SIM-02 owns resolved write paths/interruption reasons; SIM-03 comparator/replications/joint math.
- CYC-01 builder handoff и CYC-02 reader должны использовать один exact request/selected binding; shared horizon.py один writer.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Free-grow — новый совместимый method/plan проходит registry и общую применимость, а не hardcoded предпочтение второго имени.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:2455–2487](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L2455-L2487) — `def _select_coupled_engine`.
- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:2175–2207](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L2175-L2207) — `def _select_engine`.
- [policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py:2227–2259](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py#L2227-L2259) — `def validate_selected_result`.
- [policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py:33–65](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py#L33-L65) — `def _vector`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0016 | REQ-SIM-01-02, REQ-SIM-01-03, TEST-SIM-01-02, TEST-SIM-01-03 | Attempted-engine history remains complete |
| preserve:0017 | REQ-SIM-01-03, TEST-SIM-01-03 | Actual request-aware selected-result validation, seed/plan/atom matching |
| preserve:0018 | REQ-SIM-01-03, TEST-SIM-01-03 | Selected CAS view and explicit no-request provenance limitation |
| preserve:0019 | REQ-SIM-01-02, TEST-SIM-01-02 | Coupling/temporal/atom composition checks before selected return |
| preserve:0020 | REQ-SIM-01-01, REQ-SIM-01-02, TEST-SIM-01-01, TEST-SIM-01-02 | No-run when all candidates rejected |
| preserve:0021 | REQ-SIM-01-01, REQ-SIM-01-04, TEST-SIM-01-01, TEST-SIM-01-04 | Budget/access protections and useful optional defaults |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/SIM-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
