# CYC-04 — Пригодная следующая альтернатива и настоящий ресурсный допуск

**LANE-01 · B10, B11 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CYC-04.md), [исходная карточка](../05_Основания/Аудит/05_Источники/CYC-04_исходные_строки.txt), строки 779–866.
**Практический результат:** После локального отказа первого кандидата система может выполнить уже предложенный пригодный второй; информативный шаг не теряется из-за денежной эвристики, но не обходится бюджет.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Post-grounding selection and complete blocker/history denominator.
- Existing owner constraints and candidate-occurrence result binding.
- Information gain may advance below ROI threshold.
- Budget/reserve/timeout controls and current producer owner.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C05_остатки:0 | REQ-CYC-04-01 | qualify: Связать настоящий numerical owner. |
| audit-residual:C05_остатки:1 | REQ-CYC-04-02 | fix: Типизированная фикстура. |
| audit-residual:C05_остатки:2 | REQ-CYC-04-03 | capability: Положительный переход к следующему пригодному кандидату. |
| audit-residual:C05_остатки:3 | REQ-CYC-04-04 | qualify: Существующий info route и budget controls. |
| audit-residual:C05_остатки:4 | REQ-CYC-04-05 | capability: Не выдавать current ledger за future per-call reserve. |
| audit-residual:C05_остатки:5 | REQ-CYC-04-06 | lifecycle: Конечный owner decision и configured guarantee test. |
| B10 | REQ-CYC-04-01, REQ-CYC-04-02, REQ-CYC-04-03 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B11 | REQ-CYC-04-04, REQ-CYC-04-05, REQ-CYC-04-06 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0024 | REQ-CYC-04-01 | qualify: Actual controller/N5/readback. |
| remaining:0025 | REQ-CYC-04-02 | fix: Исправить fixture, не guard. |
| remaining:0026 | REQ-CYC-04-03 | capability: Ограниченный late-local fallback. |
| remaining:0027 | REQ-CYC-04-04 | qualify: Information и actual spend вместе. |
| remaining:0028 | REQ-CYC-04-05 | capability: Единица/ценовое основание и existing reservation при требуемой гарантии. |
| remaining:0029 | REQ-CYC-04-06 | lifecycle: Явное решение реальной allocation policy, не claim по слову exploration. |

## 3. Нормативные REQ и конкретное решение

### REQ-CYC-04-01 — qualify
Post-grounding selector должен реально исполнять пригодного кандидата и сохранять полный набор summaries/blockers; численный результат относится только к выбранной occurrence.

**Решение на существующих владельцах.** Сохранить _ground_node→_grounded_candidate_for_evaluation: current_valid/grounded_shadow без acquisition requirement, VOI затем surrogate и stable tie. Не переписывать уже исправленный preliminary-max путь. Связать существующий selector с actual N5/store readback вместо sole _RecordingSimulation.
**Приёмка:** TEST-CYC-04-01.

### REQ-CYC-04-02 — fix
Тестовый state обязан содержать согласованный DesignProblem и настоящие required inputs; исправление fixture не ослабляет product type guard.

**Решение на существующих владельцах.** Заменить problem=object() в _grounded_two_candidate_state existing typed fixture или минимальным валидным DesignProblem, сохранив реальный путь _generate_node. Разделить flow-only recording-port тест и numerical acceptance из TEST-01.
**Приёмка:** TEST-CYC-04-02.

### REQ-CYC-04-03 — capability
После candidate-local N5/N8 failure N6 должен лениво выбрать следующую допустимую операцию среди уже произведённых кандидатов без повторной generation; global rights/budget/base failure не обходится сменой кандидата.

**Решение на существующих владельцах.** В _joint_value_node_impl организовать bounded ordered remainder над current grounded candidates, сохраняя существующий ranking/tie. Каждую attempted (occurrence, method/input basis, operation) учитывать один раз; сохранять отказ и actual cost. Ввести/использовать typed failure scope local-vs-shared у existing result/owner, не распознавать substring произвольной reason. Для нового кандидата заново _schedule_candidate_for_execution и canonical context/input binding; возвращать его точные simulation/value refs. N8-local absence не стирает полезный N5 первого.
**Приёмка:** TEST-CYC-04-03.

### REQ-CYC-04-04 — qualify
Положительный information gain может разрешить исследовательский шаг ниже ROI-порога только в пределах actual resource admission; unknown monetary value не выдаётся за измеренный ноль.

**Решение на существующих владельцах.** Сохранить SimpleVOIScheduler._recommended_action advance_by_information_value и prior budget/dominance/timeout checks. _schedule_candidate_for_execution передаёт owner-reconciled state. Не менять unknown на0 для доказательства universal utility: явный missing monetary proxy/ограничение остаётся видимым в ticket/report.
**Приёмка:** TEST-CYC-04-04.

### REQ-CYC-04-05 — capability
Стоимость и admission численной работы должны иметь явную единицу и основание; remaining allocation не называется per-call reservation, пока соответствующее резервирование не реализовано.

**Решение на существующих владельцах.** Existing ProducerBudgetObserver/ledger сохранить. Для выбранного supported N5 route определить проверяемый work unit (например bounded replica quota) и owner price/estimate origin либо explicit unknown. Если для запуска требуется гарантированное денежное резервирование — расширить существующий reservation middleware: reserve до физического шага, reconcile фактическую стоимость/освободить остаток, связать operation ID и retry-idempotency. Stage costs0.5/1.0 остаются эвристикой, не price proof; отдельного ledger не создавать.
**Приёмка:** TEST-CYC-04-05.

### REQ-CYC-04-06 — lifecycle
Если профиль обещает защищённую исследовательскую квоту, реальные counterevidence/diagnostic операции должны потреблять её в существующей allocation policy; без такой политики обещание явно отсутствует.

**Решение на существующих владельцах.** Зафиксировать у accountable resource owner конечный выбор: отдельная доля/лимит существующего бюджета для объявленного purpose либо отсутствие гарантии с честной projection. При выбранной гарантии reserve/reconcile те же owners TEST-05, не новый scheduler; обычные высокие priorities не могут израсходовать выделенную квоту. Не выводить это из calibration reserve уровня4 для N6 stage3 и не придумывать размер бюджета.
**Приёмка:** TEST-CYC-04-06.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-CYC-04-01 · NOT_RUN
- **Setup:** Тот же declared procurement/model profile, что в test_configured_candidate_simulation_served.py::test_served_configured_profile_runs_real_n4_through_candidate_n5_and_rejects_drift (его actual NCM, target baseline и materialization, не скопированный численный output). Два кандидата: высокий preliminary score blocked; второй grounded и owner-selected. Подключить этот profile к существующему test_cyc_04 route, не заменяя simulation recording-stub.
- **Действие:** Вызвать GenerationCycleController.run, разрешить persisted result.
- **Oracle:** Для этого неизменённого profile expected_effect = outcome_per_target_unit * (materialization.value - target_baseline) = 0.5 (algebraic assertion abs_tol=1e-12); все actual replication effects должны укладываться в уже установленный для этого NCM допуск 0.02. Допуск не переносится на другой model/profile. Физический N5 выполнен для второго; первый blocker и обе occurrences сохранены.
- **Positive / negative / boundary:** All-blocked сохраняет адресные причины, нет нулей для непроверенных и нет authority от порядка.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-04-02 · NOT_RUN
- **Setup:** Нынешний test_generation_cycle_executes_next_grounded_candidate_after_first_blocker и public_run selector.
- **Действие:** Исполнить repaired fixture через actual controller; отдельный object() negative.
- **Oracle:** Тест достигает проверяемого selector, а malformed problem по-прежнему generation_cycle_design_problem_untyped.
- **Positive / negative / boundary:** Не считать repair фикстуры реализацией позднего fallback.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-04-03 · NOT_RUN
- **Setup:** Два grounded candidates и реальные selected inputs: у первого адресно отсутствует local model/input, второй исполним. Отдельно local N8 limitation и общий истёкший budget/lease.
- **Действие:** Выполнить цепочку без дополнительного gateway generation, проверить all-blocked и повтор identical operation.
- **Oracle:** После локального отказа actual N5 второго вызван ровно один раз; первый failure сохранён; result bound ко второму; счётчик generation неизменен.
- **Positive / negative / boundary:** Global denial останавливает соответствующую работу; all-blocked конечен; exhaustion после первого запрещает второй; no fabricated fallback.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-04-04 · NOT_RUN
- **Setup:** Existing scheduler tests плюс tests/unit/runtime/quality/test_c49_n6_budget_binding.py; actual producer ledger и tiny NCM.
- **Действие:** Исполнить low ROI+positive information в бюджете, затем exhausted/reserved/timeout; actual spend между seeds.
- **Oracle:** Разрешённый информационный шаг выполняется; после первого seed exhaustion второй не идёт, persisted n5_current_budget_exhausted и выполненная работа сохранены.
- **Positive / negative / boundary:** Большая заявленная information не снимает lease/бюджет; score не публикуется денежной VOI или вероятностью.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-04-05 · NOT_RUN
- **Setup:** Один actual numerical route с разрешённой ценовой/вычислительной политикой; unknown price, known estimate и reported spend; сбой между reserve/execute/settle.
- **Действие:** Пройти positive bounded execution и recovery; попытаться увеличить work сверх принятой единицы.
- **Oracle:** Цена/единица/origin/лимит доступны reader, расходы и резервы согласованы; unknown не бесплатный unlimited, duplicate operation не doublecharge.
- **Positive / negative / boundary:** Поддержанный compute-quota путь допустим без выдуманного USD курса; денежная гарантия не утверждается при unknown price.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-04-06 · NOT_RUN
- **Setup:** Existing allocation policy и два work purposes: exploitation/counterevidence; explicit owner-authorized quota либо explicit no-guarantee profile.
- **Действие:** Исчерпать обычную allocation и предложить разрешённую диагностическую операцию; затем исчерпать её собственную квоту.
- **Oracle:** При configured quota диагностика реально исполняется и затем останавливается по её лимиту; no-guarantee profile не ложно сообщает protected exploration.
- **Positive / negative / boundary:** Новая normative budget величина задаётся полномочным owner, не ассистентом; не blanket платный расход.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-C, E02-X01**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- CYC-04 единственный owner late-candidate queue в N6; SIM-01 — альтернативные engine plans внутри одного N5 request, не дублировать эти уровни.
- ACQ-01 сохраняет data acquisition action; shared failure не превращать в обход через новую acquisition.
- Budget owner/middleware изменения согласовать с RES/ответственными integration lanes; CYC-04 owns consumer purpose/admission контракт.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

LLM предлагает содержательные альтернативы; bounded queue сохраняет возможность их проверить без новой генерации и не приписывает вычислительному порядку нормативный выбор.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:13562–13594](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L13562-L13594) — `def _joint_value_node_impl`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:18979–19011](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L18979-L19011) — `def _grounded_candidate_for_evaluation`.
- [policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py:890–922](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py#L890-L922) — `def _recommended_action`.
- [policy-engine/src/polisyos/scientist/orchestration/engine/producer_budget.py:122–154](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/producer_budget.py#L122-L154) — `class ProducerBudgetObserver`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0028 | REQ-CYC-04-01, REQ-CYC-04-03, TEST-CYC-04-01, TEST-CYC-04-03 | Post-grounding selection and complete blocker/history denominator. |
| preserve:0029 | REQ-CYC-04-01, REQ-CYC-04-03, REQ-CYC-04-05, TEST-CYC-04-01, TEST-CYC-04-03, TEST-CYC-04-05 | Existing owner constraints and candidate-occurrence result binding. |
| preserve:0030 | REQ-CYC-04-04, TEST-CYC-04-04 | Information gain may advance below ROI threshold. |
| preserve:0031 | REQ-CYC-04-04, REQ-CYC-04-05, REQ-CYC-04-06, TEST-CYC-04-04, TEST-CYC-04-05, TEST-CYC-04-06 | Budget/reserve/timeout controls and current producer owner. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/CYC-04.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
