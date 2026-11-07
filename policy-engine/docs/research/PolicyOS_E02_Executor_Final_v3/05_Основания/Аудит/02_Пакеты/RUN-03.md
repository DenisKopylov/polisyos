# RUN-03 — свежая ветвь каждой попытки и ограниченная retry-политика
## C70 · 1 ноября 2026 года

**Порядок:** 70/127, LANE-06. **Исходные IDs:** B39, B96. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий разбор после внешнего сохранения C69.

## Решение

**Исходные механизмы B39/B96 ограниченно исправлены:** пустой `retry_on` больше не превращает raised error в три вызова; каждая разрешённая retry-попытка получает новую ветвь одного baseline. В bounded execution sync, genuine async и async→sync пути дают `x=1`, а не 2; nested mutations первой ошибки не переходят во вторую. Известные расходы обычного completed failure сохраняются: 5 + 2 + 1 = 8.

**Найден C70-R01, low:** отмена следующей попытки не переносит уже накопленный известный расход первой ошибки в terminal baseline. История при этом не исчезает. **G01:** полного единого семантического контракта return/raise не доказано. **G02:** native durable custody/cost/continuation остаётся UNRUN. **9 bounded MATCH, пять unchanged test bodies / шесть случаев; полного закрытия нет.**

## 1. Матрица исходных требований

| ID | Что подтверждено | Остаток |
|---|---|---|
| B39 | `retry_on=[]`: один вызов для return и raise; allowed transient: два; typed validation: один | G01: returned code и raised category не один контракт |
| B96 | Fresh declared-path branch на каждую попытку; nested baseline чист; producing-copy control сохранён | G02: native owner-bound workflow и checkpoint continuation |
| B96, расходы/история | Completed failed cost складывается с успешным; terminal raised failure переносит только стоимость, не грязную ветвь | R01: cancellation после уже известного failure cost; durable trace не исполнен |

Пакетный regression-файл действительно существует и прочитан полностью. Его native import и durable trace tests не объявлены пройденными из-за исполнения других изолированных тел. [S05:1–400](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_run_03.py#L1-L400)

## 2. Retry теперь уважает фильтр и typed причину

Returned `NodeError` проверяется по `code in retry_on`. Raised error сначала получает explicit `category`/`default_category`; validation/fatal запрещают повтор, transient допускает проверку кода. Только затем применяется существующий remote classifier. Поэтому typed transient `ValueError` не запрещён лишь из-за имени класса; typed validation `RuntimeError` не становится временным автоматически. IPC error envelope переносит category/code без восстановления произвольного exception class. [S01:1607–1773](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L1607-L1773) [S02:61–117](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/error_classifier.py#L61-L117)

**P01:** пять существующих тел / шесть cases исполнились изолированно: sync/async baseline, permanent return/raise, typed transient/validation, terminal spend projection. **P02:** 18 controlled wrapper cases на трёх маршрутах: empty filter и permanent controls — один вызов; разрешённый transient return/raise — два. **P06:** actual error envelope roundtrip сохраняет category/code четырёх типов. Это реальный ограниченный ремонт, не только наличие нового helper.

Но «одна политика» пока нельзя безоговорочно распространить на любую форму отказа. `NodeError` имеет code/message/details, без typed category. **P05:** одинаковый code `node.exception` с diagnostic `details.category=validation` повторяется трижды; explicit validation exception с тем же code — один раз. Свободное diagnostic поле не является контрактом, поэтому это **G01**, а не доказанный native same-cause bug. Нужен actual producer с эквивалентной причиной и явный выбор уже существующего classification owner. Не следует угадывать authority из текста ошибки. [S09:22–51](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/protocol.py#L22-L51)

## 3. Один baseline, а не продолжение грязной попытки

`_fresh_retry_state` вызывает existing `branch_state` с действительными `state_writes`. Обе wrapper-функции создают такую ветвь **внутри** retry-loop, а не единожды вокруг всей серии. Branching сохраняет существующее ограничение области и copy-on-write machinery; новый мировой snapshot store не нужен. Mutation guard проверяет допустимость записи, но сам по себе не заменяет новую ветвь следующей попытки. [S01:1613–1627](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L1613-L1627) [S01:2200–2227](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L2200-L2227) [S01:4048–4066](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L4048-L4066) [S03:310–367](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py#L310-L367) [S04:43–79](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/guards.py#L43-L79)

**P03:** начальное `x=0`, nested list пуст, prior spend 5. Первая попытка пишет `x=1`, добавляет marker 1 и расход 2, затем return/raise failure. Вторая снова видит `x=0`, пустой list и spend 5; её принятый результат — `x=1`, marker `[2]`, cumulative spend 8. Все шесть route/shape комбинаций совпали. Исходный baseline остаётся без ordinary mutations и с prior spend 5 при успешном возврате отдельной ветви.

**P08:** producing-copy node при `max_retries=0` и 1 сохраняет результат `x=1`, baseline `x=0` на всех трёх маршрутах. Это не требование переписать чистые узлы. **P07:** genuine async cancellation на первой попытке распространяется без второго запуска и без грязного baseline.

Checkpoint continuation — другая операция. Эта wrapper принимает переданный baseline, а не восстанавливает произвольный частичный алгоритм. Её fresh retry нельзя «исправить» возвратом к dirty state. Native continuation остаётся в G02 совместно с RES owners; нового результата о полном checkpoint пути здесь нет.

## 4. Изоляция не означает бесплатную неудачную работу

Actual spend owner вычисляет положительный delta полей `*_spent_usd`, накапливает completed failure cost отдельно и добавляет его к принятой ветви. `_preserve_retry_spend` переносит только стоимость в terminal fallback, не обычные failed writes. `NODE_RETRY` и dead-letter metrics содержат attempts/cost. [S01:1775–1934](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L1775-L1934)

**P03** сохраняет cost 8, а callback history содержит две попытки и их исходы; first failure event имеет cost 2. **P04:** две raised ошибки по 1 приводят к terminal baseline spend 7 при исходных 5, но `x` остаётся 0. Оба утверждения ограничены: два primitives snapshot/merge в probe принимают только finite Decimal fixtures, поскольку оригинальные exception clauses требуют Python 3.14. Actual delta, accumulation, metrics, callback routing и wrapper bodies исполняются без изменения. Error/coercion handling этих двух primitives не доказано исполнением.

Синтетическая ошибка провайдера и list sink не подтверждают реальное списание денег, научную валидность или durable CAS. Это проверка сохранения известной вычислительной стоимости в локальном договоре, не финансовый аудит.

## 5. C70-R01: ранее известная стоимость выпадает из cancellation baseline

В timeout branch accumulated failed_spend переносится в исходное state перед исключением. В `except asyncio.CancelledError` завершается attempt callback и исключение распространяется, но такого переноса нет. [S01:4135–4161](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/retry.py#L4135-L4161)

**P09:** первая попытка уже завершилась returned fail с cost +2 к baseline 5; actual owner сохранил callback с состоянием 7 и `NODE_RETRY` с cost 2. Вторая попытка поднимает `CancelledError`. После propagation исходный baseline всё ещё содержит 5, а не 7; ordinary `x` остался 0. Это bounded disagreement между terminal state projection и уже известной историей.

**Тяжесть низкая, граница узкая:** durable history и внешний budget ledger не объявлены потерянными. Callback/event control сохраняет первый расход; стоимость самой отменённой текущей работы неизвестна и не должна изобретаться. Native consumer этой terminal projection не исполнен. Остаток — согласовать settlement уже завершённых известных расходов с существующим owner при cancellation, не публикуя failed ordinary state и не превращая отмену в success. Соседний late/unknown native test прямо отделяет ещё не завершившийся расход; он прочитан и UNRUN. [S06:3518–3596](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py#L3518-L3596)

## 6. Producer → persisted attempt → consumer

Sync executor создаёт guarded branch, сохраняет exact attempt input и implementation identity, связывает context с attempt basis, вызывает retry и фиксирует outcome. При `RetryExhaustedError` и fail он использует `_preserve_retry_spend`, не принимает failed ветвь целиком. Async executor аналогично сохраняет attempt basis/outcome и передаёт current binding; после возврата проверяет workflow admission. [S07:1621–1793](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/executor.py#L1621-L1793) [S08:2026–2178](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L2026-L2178)

Это найденный реальный wiring, а не предложение построить второй attempt journal. Но probe заменяет persistence/context façades и event sink, поэтому native closure не заявлена. В existing tests уже есть actual RunContext/TraceRecord и real CAS known-spend settlement по разным маршрутам. **G02:** исполнить их в supported runtime, затем один общий LANE-06 integration для baseline, attempt history, cost, cancellation и readback. Не нужен тяжёлый одинаковый тест отдельно для RUN-01/02/03.

Ни memory rollback, ни fresh UUID не откатывают внешний эффект и не создают новый независимый научный эксперимент. Неизвестный external outcome требует своего evidence/idempotency договора; данный bounded probe его не проверяет и не разрешает слепой повтор.

## 7. Границы выполненного

Final: exit 0, **9 MATCH**; пять existing unchanged bodies / шесть cases. Семь initializer shells; context identity, dead-letter None и list/MagicMock sinks явно отмечены. Whole actual state_branching и classifier, actual Common bridge и unchanged retry owners использованы. 45 import identities сверены с pinned Git; это не полный human review всех зависимостей.

Attempt01 остановился до исполнения из-за ошибочного конца extraction range. Исправлен только внешний harness; первый source/log сохранён. Native pytest отсутствует, full retry import blocked на строке 258 Python 3.14 syntax. Текущие Python 3.12/Pydantic 2.13 не supported baseline; dependencies не устанавливались. Checkout чист. Старые утраченные C70 выводы не переаттестованы.

[Диагностика](../04_Проверки/C70_RUN03/bounded_diagnostics.json) · [Команды](../04_Проверки/C70_RUN03/commands.json) · [Границы](../04_Проверки/C70_RUN03/native_verification.json) · [Источники](../05_Источники/C70_источники.json) · [Остатки](../01_Реестры/C70_остатки.json).

**70/127 пакетов рассмотрены ограниченно. Следующий — DUR-01. Полного закрытия нет; фаза 2 не начата.**
