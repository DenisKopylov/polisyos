# CYC-04 — пригодные альтернативы и исследовательский бюджет

**Проход C05 · v003 · 31 октября 2026 · B10/B11 · read-only audit**  
Код: `20d9009be21097bfbdc38a546a15cc60213b8ace`. Исходный E02 — [полный сохранённый пакет](../05_Источники/CYC-04_исходные_строки.txt). Продуктовый код и тесты не менялись. Независимая приёмка не заявлена.

## Итог

**Два исходных механизма уже изменены в нужную сторону.** N6 пересматривает предварительный выбор после grounding и сохраняет непрошедших кандидатов с причинами. SimpleVOIScheduler больше не отклоняет положительно информативную работу только из-за низкого value-proxy/ROI. Это существующие механизмы, которые следует сохранить, а не создавать повторно. [C05-S01, C05-S02]

Полного закрытия CYC-04 нет. У текущего узла N5/N8 по-прежнему один выбранный кандидат: поздний локальный отказ исполнения не вызывает перехода к следующему уже созданному варианту. Верификация также нуждается в ремонте одной устаревшей фикстуры и в настоящем связанном N5-прогоне. Для бюджета важно не спутать установленную защиту текущего USD-учёта с пока не установленной ценой всего будущего численного расчёта. [C05-S01, C05-S04–S06]

Рабочая установка о содержательном выборе через LLM принята [отдельным дополнением](../03_Основания/Рабочая_установка_LLM_2026-10-31.md). Этот проход не требует нового универсального алгоритма гипотез и не начинает его реализацию.

## 1. Исходная способность, а не буквальное повторение ремонта

B10 требует, чтобы первая высоко ранжированная, но неисполняемая альтернатива не заслоняла вторую исполнимую. Исходная причина отказа, состав уже произведённых кандидатов, общий бюджет и разнообразие должны сохраниться; неисследованный вариант не получает выдуманный численный результат.

B11 требует, чтобы информативную разрешённую проверку можно было выполнить при неопределённой денежной выгоде. Это не право на неограниченные расходы. Порядок исследования, экономическая эвристика и действительный допуск к ресурсу — разные решения. E02 не предписывает заново создавать MCTS, acquisition runtime или другой ledger.

## 2. B10: что работает в текущем коде

### 2.1. Предварительный максимум больше не окончательный

`_generate_node` по-прежнему делает предварительный `max` по surrogate-score. Но `_ground_node` затем проходит весь полученный набор, получает grounding каждой альтернативы и вызывает `_grounded_candidate_for_evaluation`. Пригодность этого селектора — `current_valid` либо `grounded_shadow` без текущего `acquisition_requirement`. Из пригодных выбирается сначала максимальный VOI-ориентир, затем surrogate-score, а при равенстве сохраняется исходный порядок. [C05-S01]

Таким образом, исходный контрпример «первый не имеет нужного входа, второй имеет, но первый навсегда выбран» больше не следует из одного предварительного `max`. В изолированном воспроизведении тела узла первый заблокирован, второй выбран, записывающий порт симуляции вызван только для второго. Это проверка порядка вызовов на явных фикстурах, не результат настоящей численной симуляции.

### 2.2. Заблокированные варианты не удаляются

Для каждого кандидата сохраняется `CandidateSummary`: идентификатор и хэш, номер цикла, grounding-status, issue codes, report ref, score и принадлежность исследовательскому/карантинному представлению. Второй кандидат не заменяет первое наблюдение в истории. Если пригодных альтернатив нет, селектор возвращает исходно выбранную: сохраняется его адресный blocker вместо выдуманного «успеха пустого множества». Это не означает blanket-запрет любого условного N5 при неизвестном grounding: дальнейшие режимы имеют свои правила. [C05-S01]

Нормальный N4 отдельно валидирует знаменатель rankings. Частное поведение helper при отсутствующих rankings нельзя выдавать за допуск отсутствующего рейтинга во всех обычных входах; настроенный unranked candidate-scenario является отдельным ограниченным маршрутом.

### 2.3. Что сохранять

Сохраняются post-grounding reselection, полный набор summaries, различие кандидата и его появления, отсутствие присвоения чужого N5-результата невыбранным вариантам и детерминированный tie-break. Порядок вычислений не является нормативным предпочтением или сертификацией рекомендации. Существующий helper не нужно заменять новым общим оптимизатором только ради выполнения формулировки сентября.

## 3. B10: точный остаток — после grounding

`_joint_value_node_impl` берёт один `selected_candidate`, запрашивает его schedule и вызывает соответствующую ветвь N5/N8. Внутри прочитанного тела нет очереди оставшихся вариантов и возврата к ним после локального отказа. Configured и generic ветви также возвращают результат выбранного кандидата. [C05-S01]

Различающий сценарий: оба кандидата прошли grounding; первый выбран по информационному ориентиру; только его N5 сообщает об отсутствующей модели либо N8 сообщает о недоступном входе; второй имел бы пригодный вход. В изолированной композиции исходных тел вызван только первый. Второй не исследуется в этом узле. Две диагностические проверки фиксируют эту границу отдельно для N5 и N8. Это не доказательство частоты проблемы на production и не утверждение об отсутствии любых альтернатив в других контроллерах.

**Экономный следующий шаг:** у действующего N6 поддержать ограниченный набор следующих исполнимых операций над уже произведёнными кандидатами. Не генерировать весь batch повторно лишь потому, что один план не исполнился. Отказ метода/входа одного кандидата может открыть проверку другого. Общий отказ прав, исчерпание общего ресурса или отсутствие общего основания не разрешает автоматически обходить запрет сменой кандидата. Для иной более дешёвой операции нужен действительный план и новый допуск её ресурса, не случайное уменьшение заявленной цены.

Минимальный критерий расширения: first passes grounding→candidate-local N5 failure→second actually executes; first failure retained; no extra generation; exact result bound to second occurrence. Отдельно нужны all-blocked, exhausted-budget и repeated-identical-operation controls. Само наличие такой очереди не требует LLM заменить дешёвую детерминированную фильтрацию. LLM может предложить следующую гипотезу, а очередь исполняет допустимые уже сформулированные операции.

## 4. Тесты B10: полезное существующее покрытие и одна устаревшая фикстура

В `tests/unit/remediation/test_cyc_04.py` есть нужные тесты самого selector/history-поведения. Публичный `test_public_run_retains_blocked_first_reason_after_executing_second` содержит сборку `DesignProblem` и вызов `GenerationCycleController.run`, требует вызова записывающего simulation-порта для второго и сохранения первого blocker. Это полноценная идея проверки controller flow, но сам `_RecordingSimulation` вручную возвращает `joint_simulated`; он не выполняет численную модель и не подтверждает CAS-readback. [C05-S05]

Другой тест — `test_generation_cycle_executes_next_grounded_candidate_after_first_blocker` — использует `_grounded_two_candidate_state`, где `problem=object()`. Текущий `_generate_node` сначала требует `isinstance(problem, DesignProblem)`. Следовательно, при достижении этого guard тест остановится с `generation_cycle_design_problem_untyped` до проверяемого выбора. Пролог воспроизведён отдельно; сам pytest-проход проекта здесь не запускался. [C05-S01, C05-S05]

Ремонт относится к фикстуре: передать согласованный действительный `DesignProblem`, а не снять type guard в продукте. Затем запустить существующие тесты и отдельный малый owner-backed N5-контроль. Упоминание теста в реестре или старое зелёное сообщение не заменяет результата на нынешней форме входа.

## 5. B11: низкий ROI больше не уничтожает информационную ценность

У `SimpleVOIScheduler._recommended_action` теперь есть ветвь: если ROI ниже порога, но `expected_information_gain > 0`, действие остаётся `advance`, причина — `advance_by_information_value`. Если нет и value-, и information-основания, сохраняется `reject / roi_below_threshold`. Информационный бонус участвует в приоритете отдельно от этого решения. [C05-S02]

До этой ветви проверяются применимые ограничения: dominated-позиция, достаточность текущего бюджета, резерв калибровки для уровня 4 и выше, риск timeout. Изолированные контроли показывают, что даже очень большой информационный сигнал не отменяет исчерпание бюджета или `retry_cheaper`. Следовательно, старую ROI-ветвь повторно «исправлять» не требуется.

В настроенном candidate-only режиме существует отдельное разрешение выполнить N5 при `reject / roi_below_threshold`. Оно не распространяется на `defer / budget_exhausted_for_next_level`. Такой маршрут нельзя считать общим обходом ресурсного контроля; его назначение связано с отдельным unranked candidate-scenario. [C05-S01]

### 5.1. Положительное решение scheduler не равно разрешению любого следующего действия

N6 получает schedule через `_schedule_candidate_for_execution`; при наличии reconciler сначала обновляет текущее бюджетное состояние. Далее `decide_next_action` учитывает terminal: acquisition/human-decision/spec-gap требуют эскалации, завершённые терминалы останавливают цикл. Положительный информационный ориентир сам не закрывает дефицит данных и не делает N9 допустимым. [C05-S01]

### 5.2. Исследовательская квота ещё не следует из слова exploration

Рассмотренный N6 создаёт ticket с `current_level=2`, `next_level=3`, пустыми feedback/context и новым `ParetoSnapshot`. Его default stage-costs — 0.5 и 1.0 USD; это заданная эвристика стадий, не измеренная стоимость конкретного N5. Резерв калибровки проверяется начиная с уровня 4, поэтому данный stage-3 маршрут сам по себе не подтверждает защищённую квоту на опровержения. [C05-S01, C05-S02]

Это не основание заводить новый бюджетный сервис. Если нужна гарантия, что высокие эксплуатационные priorities не вытеснят исследовательские проверки, следует определить её в существующей политике распределения и подтвердить действительным резервированием. Один положительный `information_gain` такого свойства не обеспечивает. Значение 0, используемое в existing «unknown monetary proxy» тесте, также не доказывает полноценного различения отсутствующего значения и реально оценённого нуля. [C05-S05]

## 6. Фактический учёт уже связан с N6 — сохранять

`BudgetState.remaining` вычитает и `spent`, и `reserved`. Более важен имеющийся `ProducerBudgetObserver`: он перечитывает durable ledger, проверяет владельца, точную run-binding, завершённость финансовых событий, происхождение стоимости и условия reuse. Неустановленное положительное бюджетное основание не превращается в бесплатный ресурс. Контроллер проверяет привязку canonical N5-порта к тому же владельцу. [C05-S01, C05-S03, C05-S04]

В существующем `test_c49_n6_budget_binding.py` проверяется особенно полезная композиция: настоящий NCM выполняет первую реплику, затем producer-расход исчерпывает лимит; вторая реплика не запускается, а сохранённый результат содержит `n5_current_budget_exhausted` и одно наблюдение физической работы. Проверяются default и supplied canonical port, чужой owner, detached state и изменение владельца до generation. Этот тест прочитан, **не исполнен в данном аудите**. [C05-S06]

Сам owner прямо сохраняет ограничения `n5_usd_price_not_established` и `remaining_allocation_is_not_a_per_call_cost_reservation`. Поэтому установленная связь с актуальными расходами не означает ни измеренной цены N5, ни гарантии, что все будущие численные вызовы заранее обеспечены денежным резервом. Корректный остаток — установить стоимость/единицу и admission нужного вида работы у существующих владельцев, а не объявлять весь бюджет отсутствующим.

## 7. Что исполнено здесь

Выполнены **34 изолированные проверки, 34 MATCH, 0 MISMATCH**. В это число входят 24 выбранных source-predicate/budget characterizations, 4 композиции исходных тел с записывающими портами, 2 characterization текущего позднего отказа, 2 проверки type-guard-пролога и 2 property-removal controls. Ожидаемое совпадение с текущим ограничением не является положительным capability PASS.

Исполнялись переписанные по прочитанным исходникам тела отдельных функций и выбранные методы `BudgetState`; Python и Pydantic реальные. Controller constructor, product DTOs для candidates/observations, численный N5, CAS, текущий ledger, HTTP и весь package import не исполнялись. Для этих границ использованы явно описанные фикстуры. Код репозитория не редактировался; mutation controls меняли только отдельное пространство имён аудита.

Контроль удаления post-grounding reselection возвращает исполнение первого кандидата и обнаруживается. Контроль возврата безусловного ROI-veto отменяет информационное продолжение и также обнаруживается. Это показывает различающую способность малых проверок, но не заменяет native regression.

[Результаты и точные ограничения](../04_Проверки/C05_CYC04/bounded_diagnostics.json) · [исполняемый harness](../04_Проверки/C05_CYC04/run_bounded_diagnostics.py) · [тела фрагментов](../04_Проверки/C05_CYC04/source_excerpts.py).

## 8. Решение по исходному пакету

| ID | Подтверждённое чтением/ограниченными probes | Остаток и класс |
|---|---|---|
| B10 | Выбор после grounding; первый blocker и весь набор сохранены | Native проверка; устаревшая фикстура; расширение на поздние candidate-local N5/N8 отказы |
| B11 | Информационная ценность не подавляется низким ROI; ресурсные ветви предшествуют ей | Native owner-connected проверка; цена/резерв численной работы; при необходимости политика защищённой исследовательской квоты |

Оба ID получают `partially_assessed`, без полного закрытия. Первоначальные механизмы изменены; это не значит, что все более широкие пожелания E02 реализованы. Не следует закрывать B10/B11 на основании другой проверки согласованности blocked-disposition (R11): исторический audit ledger отдельно предупреждал о неверной привязке этих классов. [C05-S08; документальный контекст, не новый runtime-результат]

Следующая приёмка адресная: восстановить валидный вход первой фикстуры; выполнить существующие selector/history/info/budget tests; один actual N5 для второй альтернативы; один late-local-failure discriminator и глобальный budget negative; существующий owner-binding/between-seeds test. Никаких paid LLM/live acquisition для этих проверок не нужно. Широкий pytest и новый scheduler не требуются только ради этой карточки.

Следующий пакет исходного порядка — **CYC-02**. Его положительный численный N8 рассматривается вместе с declared SIM-зависимостями; порядок чтения не означает снятия activation-условий.

## Источники

Все продуктовые ссылки закреплены за одним commit; source read и test execution различены в [машинном индексе](../05_Источники/C05_источники.json).

**C05-S01** — [policy-engine/src/polisyos/runtime/quality/generation_cycle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L7860-L8220). N6 generation type guard, provisional selection, post-grounding reselection, one selected N5/N8, scheduler, configured ROI exception. Статус: pinned source read; selected transcribed bodies executed with explicit fixtures; not full-module import.

**C05-S02** — [policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py#L1-L350). SimpleVOIScheduler priority versus action, information override, resource controls, Predictive class existence. Статус: pinned source read; selected Simple decision methods executed; predictive training UNRUN.

**C05-S03** — [policy-engine/src/polisyos/scientist/orchestration/engine/budget.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/budget.py#L1-L330). BudgetState remaining, spent and reserved; no limit is None. Статус: full source read; selected class fields/methods transcribed and executed with real Pydantic.

**C05-S04** — [policy-engine/src/polisyos/scientist/orchestration/engine/producer_budget.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/producer_budget.py#L1-L350). Fresh producer owner reconciliation, exact run binding, unknown-cost refusal, N5 price limitations. Статус: source read only; ledger/middleware/admit UNRUN.

**C05-S05** — [policy-engine/tests/unit/remediation/test_cyc_04.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cyc_04.py). Existing selector/history/info/budget tests; object() fixture now conflicts with DesignProblem guard. Статус: full test source read, native pytest UNRUN; guard conflict characterized separately.

**C05-S06** — [policy-engine/tests/unit/runtime/quality/test_c49_n6_budget_binding.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/runtime/quality/test_c49_n6_budget_binding.py#L1-L360). Canonical owner binding and actual NCM interruption between seeds after producer spend. Статус: full test source read; no fresh result receipt and no native execution.

**C05-S07** — [policy-engine/tests/unit/scientist/search/test_voi_scheduler.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/test_voi_scheduler.py#L1-L330). Insufficient budget, dominance, unassessed/legacy frontiers, timeout test design. Статус: bounded test-source read; native pytest UNRUN.

**C05-S08** — [policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/LEDGER_DELTA_AUDIT_D58.md](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/LEDGER_DELTA_AUDIT_D58.md). Historical warning not to conflate B10/B11 with R11 blocked-disposition class. Статус: document read; historical audit, not current behavior evidence.

**C05-S09** — [policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/task-status-detailed-20261027/tasks.json](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/task-status-detailed-20261027/tasks.json). R3-2 requests actual selector discriminator and original-selection mutation control. Статус: search excerpt only; not complete task or closure receipt.
