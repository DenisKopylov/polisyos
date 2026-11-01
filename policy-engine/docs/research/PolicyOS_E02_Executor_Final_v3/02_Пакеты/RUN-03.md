# RUN-03 — Одна retry-политика и чистый baseline каждой попытки

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B39, B96. Тип: known-cost cancellation fix + classification decision/native qualification.

Повтор начинает чистую ветвь и не стирает известную стоимость прошлой попытки; возврат и исключение эквивалентной причины имеют объяснимую retry policy.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/RUN-03.md), [все остатки](../05_Основания/Аудит/01_Реестры/C70_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/RUN-03_исходные_строки.txt), исходный объединённый план §RUN-03 (исторические строки 8221–8312).

## 2. Уже работает — сохранить

- Fresh declared-write branch внутри каждой retry-loop, чистые producing-copy nodes и max_retries0.
- retry_on, typed transient/validation precedence, IPC category/code; не class-name heuristic.
- Known completed-failure spend отдельно от ordinary writes.
- Existing attempt basis/outcome/trace owners; checkpoint continuation отдельный договор.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C70-R01 | fix: Cancellation переносит уже known failed_spend, не текущий unknown расход/dirty state. | REQ-RUN-03-02 |
| C70-G01 | capability: Нужен bounded classification contract actual return/raise, не прочтение details.category. | REQ-RUN-03-03 |
| C70-G02 | qualify: Native attempt/CAS/cost/consumer и continuation. | REQ-RUN-03-01, REQ-RUN-03-02, REQ-RUN-03-04 |

### Исходные обязанности, не только новые R

- B39 → REQ-RUN-03-03: empty retry filter уже исправлен; finite actual producer classification contract и unknown external effect no blind retry.
- B96 → REQ-RUN-03-01/-02/-04: fresh baseline, known cost terminal settlement, actual durable attempts и отдельный continuation.

## 4. Нормативный контракт

### REQ-RUN-03-01
Каждая permitted retry на sync/genuine-async/async→sync получает baseline x0/nested[]; mutate→fail→success даёт x1, только marker второй попытки. Ordinary failed writes не попадают в baseline; producing-copy и max_retries0 сохраняются.

Источник: B96; аудит: C70-G02; проверки: TEST-RUN-03-01.

### REQ-RUN-03-02
При cancellation после завершённой fail-попытки terminal baseline/settlement включает её уже известный failed_spend ровно один раз; baseline5 + known2 =7. Cancelled current attempt с unknown cost не добавляет выдуманную величину. CancelledError propagates, ordinary mutations не принимаются и success не публикуется.

Источник: B96; аудит: C70-R01, C70-G02; проверки: TEST-RUN-03-02.

### REQ-RUN-03-03
Для одного actual supported producer эквивалентные declared reason/code/category в return/raise дают одинаковое retry решение. Classification использует существующий owner и typed contract, не свободные details/message. Empty filter даёт один вызов; allowed transient bounded retry; permanent и unknown already-dispatched effect не слепо повторяются.

Источник: B39; аудит: C70-G01; проверки: TEST-RUN-03-03.

### REQ-RUN-03-04
Actual attempt input/implementation basis, outcome/error и known spend переживают persistence/fresh reader. Explicit checkpoint continuation проходит RES-01 contract, а не продолжает dirty retry state; поздний неизвестный effect требует reconciliation/idempotency, не новой UUID.

Источник: B39, B96; аудит: C70-G02; проверки: TEST-RUN-03-04.

## 5. Техническое решение и producer → consumer

В execute_with_retry_async CancelledError branch вызвать existing _merge_spend(state, failed_spend) или единый idempotent settlement helper, используемый deadline/terminal exits; выполнить до повторного raise и не переносить attempt_state. Проверить путь, где _finish_invocation_attempt_async сам отменён: known completed cost должен сохраниться в finally-safe terminal projection, но не дублировать durable owner settlement. Идентичность completed attempt берётся existing attempt ID.

G01: выписать producer code/category и текущий _should_retry/_exception classifier. Предпочтение нормализовать returned structured failure в существующий classifier; если NodeError не имеет typed category, выбрать совместимое additive typed field/enum либо code→category contract у owner. Не трактовать details.category как authority. Решение фиксируется с точными accepted/legacy cases; не переписывать произвольные exception classes.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/retry.py: _fresh_retry_state, _preserve_retry_spend, _merge_spend, execute_with_retry_async
- policy-engine/src/polisyos/scientist/orchestration/engine/runner/error_classifier.py: existing classification
- policy-engine/src/polisyos/scientist/orchestration/engine/protocol.py: NodeError
- policy-engine/src/polisyos/scientist/orchestration/engine/executor.py: persisted attempt basis/outcome

Нельзя reset total spend или merge full failed state. Новый classifier рядом с существующим и угадывание category из текста создают новый разрыв. Изменение returned-error schema отдельно от narrow cancellation fix.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-RUN-03-01
- Уровень: unit + targeted native integration.
- Setup: x0,nested[],spend5; first fail modifies x/list/spend2; second success cost1; three execution routes.
- Действие: Run return/raise failures и producing-copy/max_retries0 controls.
- Точный oracle: Final x1/list[second]/spend8; initial ordinary state clean. Second saw x0/list[]/baseline5; clean nodes unchanged.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RUN-03-02
- Уровень: unit + targeted native integration.
- Setup: First completed fail +2; second CancelledError, controlled cancellation during callback, separate first-attempt cancel/late unknown.
- Действие: Propagate cancel; inspect terminal state and durable owner.
- Точный oracle: Baseline spend7 exactly once and x0; first-cancel stays5; unknown current spend not fabricated; CancelledError retained, no success.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RUN-03-03
- Уровень: unit + targeted native integration.
- Setup: Actual same-cause producer both forms, declared category mapping; empty filter/permanent/transient/unknown effect.
- Действие: Run sync/async and IPC envelope through same classification.
- Точный oracle: Same declared cause same attempts; empty/permanent1, allowed transient2 in two-attempt fixture, unknown effect0 blind repeats. details/message-only category не принят как typed.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RUN-03-04
- Уровень: native persisted integration.
- Setup: Real RunContext/TraceRecord/CAS, attempt bindings and temporary budget ledger.
- Действие: Retry→cancel/exhaust/success→fresh read; RES-01 continuation distinct.
- Точный oracle: Exact started/completed attempts/costs bound to IDs, no double settlement; failed ordinary state absent; prior artifacts readable; continuation obeys original fingerprint.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_run_03.py`; `policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: small producer and controlled cancel only; unit cost arithmetic with actual Decimal owner. Запрещено: list event sink as durable evidence, unknown cost=0/known, fake receipt/idempotency.

## 7. Общая интеграция и порядок

RUN-03 owns baseline/classification/local cost projection; DUR-01 durable ledger identity, DUR-02 retry authority. Shared native wave tests one terminal reader and one continuation, не три независимые аттестации.

Точные общие сценарии: E02-I06-C, E02-I06-B из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: STA-01; RUN-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

If additive typed failure field chosen, absent legacy field retains documented code-only semantics until explicitly classified; no reinterpretation historical details. Cancellation cost fix preserves exception and immutable history. Rollback cannot erase completed known costs.

## 9. Free-grow и design direction

- policy-design-execution-topology.md §3–6: retry versus continuation, unknown effect requires next action.
- design_direction.md §4.9: failed work/history не исчезает; candidate retry не становится независимым научным экспериментом.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-RUN-03-01: выбрать load-bearing category representation у current NodeError/classifier по actual producer. Выход — таблица return/raise/IPC equivalence и legacy handling; если same-cause route отсутствует, ограничить claim, не объявить глобальный parity PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

