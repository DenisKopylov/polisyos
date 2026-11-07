# RES-03 — Сохранение частичного результата через последующий отказ

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B13. Тип: native qualification + bounded same-leaf capability decision.

Пользователь читает уже завершённый numerical result, scope и точную причину позднего отказа — как после sibling, так и после дальнейшей стадии того же leaf, без ложного success.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/RES-03.md), [все остатки](../05_Основания/Аудит/01_Реестры/C67_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/RES-03_исходные_строки.txt), исходный объединённый план §RES-03 (исторические строки 7885–7956).

## 2. Уже работает — сохранить

- Async successes merge перед AsyncChainExecutionError, exact errors и blocked future nodes.
- Recursive V3 content-bound partial: completed/pending/failed topology, root terminal=None.
- Public partial projection существует; нормативный consumer отказывает partial compiled run.
- Независимые N4/CAS записи не объявлять потерянными; не новый журнал или scheduler.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C67-G01 | qualify: Actual N5→CAS→compiled partial→scoped public reader и invalidation/reuse. | REQ-RES-03-01, REQ-RES-03-02 |
| C67-G02 | capability: Завершённый sibling не закрывает same-leaf partial representation; bounded trace/implementation decision с обязательным положительным результатом. | REQ-RES-03-03 |

### Исходные обязанности, не только новые R

- B13 → REQ-RES-03-01…-03: sibling partial уже имеет механизм; same-leaf late-stage граница требует конкретного positive witness и при отсутствии wiring — расширения existing owner.

## 4. Нормативный контракт

### REQ-RES-03-01
Если A/предыдущие уровни завершены, B падает, AsyncChainExecutionError сохраняет exact completed numerical results/scope и исходную ошибку B; failed B не node_result, зависимые будущие nodes не запускаются. В all-success control все результаты остаются доступны.

Источник: B13; аудит: C67-G01; проверки: TEST-RES-03-01.

### REQ-RES-03-02
После реального owner-bound N5 и sibling failure свежий scoped public reader возвращает exact simulation bytes/numbers, completed/pending/failure projection без terminal success. При изменении общего основания зависимая authority теряет current applicability, но независимый candidate artifact остаётся исторически доступным; normative partial publication отказана.

Источник: B13; аудит: C67-G01; проверки: TEST-RES-03-02.

### REQ-RES-03-03
Если actual N5 того же leaf уже завершён/сохранён, поздний независимый value/revision failure не делает его невидимым пользователю: existing source/checkpoint/reader предоставляет numerical result, declared scope, dependency refs и exact error. Если current native route уже это делает — сохранить; иначе расширить этот owner и его typed partial representation, не подменяя полный cycle completion и не повышая authority.

Источник: B13; аудит: C67-G02; проверки: TEST-RES-03-03.

## 5. Техническое решение и producer → consumer

Для existing AsyncChainExecutor не нужен новый repair: его execute уже merge-before-raise. Квалифицировать штатный dispatcher и reader. Для recursive sibling reuse existing real-leaf regression.

Same-leaf исследование ограничено одной штатной configured/generic N5 route: поставить контролируемый отказ в value/revision после actual simulation persistence; записать точные refs и вызвать существующий run reader. Если результат уже видим — no-code и evidence. Если пропадает только projection, довести ref/error через текущий generation_cycle source/checkpoint и run_lifecycle/public projection. Если error выходит до сохранения current partial link, добавить typed partial carrier у существующего cycle owner (completed simulation ref+problem/candidate/scope+failed stage/cause+blocked stages), записывая его в существующем run/source history до terminal failure. Не выдавать незавершённый leaf за canonical completed GenerationCycleRecord. SimpleLoopEngine generic exception wrapping выбирать только если несколько actual callers нуждаются в нём; иначе ловить в semantic owner, сохраняя original exception chain.

Producer N5→verified persisted simulation→same-run partial link→failed terminal record→scoped reader→пользователь; consumer не требует успешного следующего value.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py: execute, AsyncChainExecutionError
- policy-engine/src/polisyos/scientist/orchestration/workflows/engine_simple.py: SimpleLoopEngine.run_async
- policy-engine/src/polisyos/runtime/quality/generation_cycle.py: _run_cycle, _joint_value_node_impl
- policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py: V3 partial builder/predicates
- policy-engine/src/polisyos/runtime/http/routes/runs.py: partial checkpoint projection
- policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py: _normative_generation_sources

Не достаточно attached dict в synthetic exception: нужны persisted bytes и fresh reader. Не создавать второй history ledger; не менять terminal на success и не приписывать native потерю всех CAS данных до воспроизведения.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-RES-03-01
- Уровень: unit + targeted native integration.
- Setup: Compiled actual small chain A numerical producer, B exact exception, C dependent; prior level; all-success control.
- Действие: Execute native dispatcher и inspect partial.
- Точный oracle: Exact A output/scope и prior retained; same B cause/code/text, B absent from successes, C calls0/blocked; all-success all outputs.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-03-02
- Уровень: native end-to-end scoped persistence.
- Setup: Existing real-leaf route with actual selected CAS/profile and N5; controlled sibling failure.
- Действие: Persist→fresh process/read API; mutate shared epoch/dependency; normative consume.
- Точный oracle: Exact simulation WMR/atoms/outcomes retained; completed A, failed B, pending C/root; no promotion receipts. Changed basis only dependent authority invalid, candidate history retained; wrong tenant/profile refused.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-03-03
- Уровень: bounded investigation + mandatory native positive witness.
- Setup: One actual leaf N5 commits output; fault at subsequent value/revision before full cycle record.
- Действие: Read result through existing reader, then implement minimal missing link if necessary and repeat; normal success counterpart.
- Точный oracle: Числа/bytes/scope/ref и точная поздняя ошибка доступны fresh reader; terminal remains failed/partial, no completed-cycle forgery. Independent error не удаляет result; common-basis invalidation limits exactly dependent claim.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_res_03.py`; `policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: controlled value/revision exception и deterministic small input; N4 port only to select declared candidate. Запрещено: success-shaped N5/CAS/DTO/hash/reader при end-to-end acceptance; fake scope/authority markers.

## 7. Общая интеграция и порядок

RES-03 shares E02-I06-B persistence/readback, consumes CYC-02/CMP-01 actual producer. Same-leaf extension coordinate generation_cycle.py with LANE-01/04, not all LANE-06 barrier. CAS-01 owns publication; actual numeric method stays its existing lane.

Точные общие сценарии: E02-I06-B из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: CYC-02; CMP-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Existing V3 sibling partial и historical completed records не менять задним числом. Если нужен новый partial schema, old full/sibling readers остаются; unknown schema explicit refusal. Rollback сохраняет immutable simulation/history, не вычищает evidence ради несовместимого projection.

## 9. Free-grow и design direction

- policy-design-execution-topology.md §3–6: continuation after failed step использует actual artifacts, не success marker.
- policyos-identity-and-custody-boundary.md §3–6 и design_direction.md §2.1/§2.6: useful conditional output допустим без нормативного повышения.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-RES-03-01: после одной real same-leaf trace выбрать no-code existing reader, projection wiring или typed partial extension у existing cycle owner. Выход обязателен: exact ref→fresh public result/error; отсутствие supported N5 environment означает NOT_RUN именно этого witness, не закрытие G02.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

