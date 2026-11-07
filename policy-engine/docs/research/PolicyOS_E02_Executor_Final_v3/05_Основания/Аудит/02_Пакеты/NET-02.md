# NET-02 — редкая частота, поколения circuit и сохранение защиты
## C103 · LANE-08 · B91, B92, B93

**Решение: частично подтверждено, не закрыто.** Единичный запрос теперь помещается в bucket при 0.2 RPS без округления самой скорости. Поздний ответ учитывает поколение своего lease, а protected registry не стирает cooldown/active state ради TTL или LRU. Осталась содержательная недосвязка: adaptive wrappers сообщают limiter о429, но не о последующих успешных результатах.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **4 MATCH; 35 неизменённых existing test bodies /55 cases PASS** в finalrun04. Это bounded execution с controlled clock/provider и explicit telemetry fixtures, не native pytest. Ранние ошибки сохранены. **103/127**, далее SCL-01.

## 1. Две оси

**Исходный ремонт.** Rate capacity и refill разделены; невозможный weight и invalid rate отказывают до provider. Circuit completion связан с issued identity/generation; stale completion сохраняет собственный result/error, не голосует за новый HALF_OPEN. Registry pin начинается до первого await admission; cooldown, depleted tokens, half-open и active attempts остаются mandatory state.

**Содержательная способность.** Важна фактическая цепочка, а не наличие классов. Existing REST consumer сохраняет один request wrapper между pages и fetches, использует тот же rate/circuit owner после очистки diagnostic handle state и допускает отдельный domain отдельно. Local overload не объявляется отказом внешнего источника. Но successful provider→adaptive feedback edge отсутствует, поэтому заявленное восстановление скорости недостижимо через эти wrappers. Никакая из проверок не подтверждает научную истинность, полноту, актуальность или права на данные; LLM как semantic proposer этим не заменён.

## 2. Матрица исходных IDs

| ID | Подтверждённое поведение | Остаток |
|---|---|---|
| B91 | Default capacity=max(1,rate); при 0.2 первый запрос проходит, следующий ждёт5 по controlled clock. Проверены0.1/0.2/1/2, invalid/nonfinite, overweight, cooldown и cancellation. Actual REST pages/fetches сохраняют fractional budget. | C103-R01 касается adaptive recovery после 429, не отменяет исправление fractional admission. |
| B92 | Старые CLOSED success/failure и HALF_OPEN token не влияют на новое поколение. Current probe работает; foreign/double completion диагностируются, cancellation возвращает slot без recovery vote. | Native scheduling/telemetry corpus не исполнен; bounded state-machine evidence не обещает глобального circuit owner между процессами. |
| B93 | TTL/LRU не забывают Retry-After, depleted balance, pinned admission и OPEN/HALF_OPEN. При protected capacity честный local refusal; нейтральные записи освобождаются. | Adaptive owner не становится neutral через успешные wrapper calls из-за C103-R01. Сохранять guard, не лечить сбросом состояния. |

## 3. Actual producer→owner→consumer

1. `_call_with_limiter` получает token перед provider и направляет typed RateLimitError к тому же owner. `with_rate_limit` и `apply_resilience` lease-ят canonical key на весь вызов; numerically equal rates1/1.0 используют одно identity [S01: 456–542; S04: 267–288].
2. GenericRESTConnector создаёт `_page_request` один раз в constructor. Actual pagination и subsequent fetch повторно используют wrapper; same-key новый handle не получает свежий budget, а очищение diagnostic state не удаляет protection [S05: 242–251,411–580,629–639; S07: 168–218].
3. Registry pin и quiescent predicate находятся под одним lock. Активная попытка и неистёкший cooldown не вытесняются; нехватка protected capacity даёт owner-tagged refusal до provider. Circuit отличает это от ошибочного ответа provider, даже с тем же названием exception [S03; S02: 569–585].
4. Circuit проверяет issued lease, затем generation. Финализация удаляет active owner, ограничивает remembered IDs и не принимает stale vote. Sliding call/failure history истекает по времени; fixed-cardinality memory bound при произвольном throughput не заявлен [S02: 343–512].

## 4. Наблюдения

| ID | Фактически выполнено |
|---|---|
| P01 |17 unchanged bodies/27 cases PASS: rates/weights, cancellation, current/late generation, ownership и cooldown under pressure/TTL. |
| P02 |18 unchanged bodies/28 cases PASS: actual REST pages/fetches с in-memory provider seam, registry-installed zero-rate refusal, key equivalence, Retry-After, pre-admission pins, half-open protection и local-vs-provider exception origin. |
| P03 |Оба adaptive wrappers: 429 снижает1→0.5; 100 успешных результатов оставляют0.5 и success_count=0. Cooldown10 соблюдён, следующие интервалы2. После full bucket/expired cooldown new key приcap=1 отвергается. Direct feedback positive: 0.55 после 100,1 иneutral после 800. |
| P04 |Foreign/double completion отказ, half-open cancellation без vote, следующий valid42. После 200 calls finalized IDs≤16, active0; time-window history200→0 поexpiry. Neutral registry entries освобождаются, без безлимитной второй карты. |

[Диагностика](../04_Проверки/C103_NET02/bounded_diagnostics.json) · [команды](../04_Проверки/C103_NET02/commands.json) · [existing bodies](../04_Проверки/C103_NET02/probe_net02.py) · [adaptive feedback](../04_Проверки/C103_NET02/probe_adaptive_feedback.py) · [generation boundaries](../04_Проверки/C103_NET02/probe_generation_boundaries.py).

## 5. Подтверждённый остаток C103-R01

Общий helper возвращает `await func(...)` напрямую, а callback выполняет только для RateLimitError. `AdaptiveRateLimiter.record_success()` существует и реализует увеличение после 100 successes, но оба public wrappers не вызывают его [S01: 404–433,456–468; S04: 267–288].

P03 проходит через actual public wrappers, не вызывает limiter вместо них: provider действительно возвращает 100 результатов после 429, однако rate остаётся0.5 и `_success_count=0`. Отдельный direct positive показывает, что existing adaptive owner восстанавливается при доставленном feedback. После истёкшего cooldown и полного bucket уменьшенный rate по-прежнему влияет на admission, поэтому registry правильно не выбрасывает его. Наблюдаемый new-key refusal — следствие недовосстановленного состояния, а не основание ослабить защиту.

**Что осталось:** подключить successful provider completion к existing adaptive feedback в общей boundary, сохранив result/error identity, cancellation, plain limiter contract, cooldown и pin lifetime. Не создавать второй регулятор, не сбрасывать owner и не округлять rate. Native регрессия должна охватить оба wrappers и дальнейшее достижение neutral state. GenericREST default adaptive=False не объявлен пострадавшим; production prevalence не измерена.

## 6. Сохранить и доквалифицировать

Сохранить fractional refill, unit capacity, impossible-weight refusal, issued lease/generation, explicit local admission origin, exact provider error, TTL/cap protection и безопасное освобождение neutral state. Допуск нового ключа может честно отказать: это не повод незаметно сбросить Retry-After.

**C103-G01.** Native environment не соответствует baseline. Run01 — syntax typo audit harness,run02 — missing opentelemetry. Run03 с trace fixture дал54 PASS/1 FAIL: optional no-op metrics не имеет callable SLO method и маскирует ожидаемый invalid-rate error. Run04 явно добавляет no-op SLO callback и даёт55 PASS; это не исправление или аттестация native telemetry. Все версии/logs сохранены. Controlled clock и in-memory REST seam не являются HTTP integration, production latency или source authorization. Установок и изменений checkout нет.

[Исходная карточка](../05_Источники/NET-02_исходные_строки.txt) · [источники](../05_Источники/C103_источники.json) · [остатки](../01_Реестры/C103_остатки.json) · [точные границы](../04_Проверки/C103_NET02/Чтение_и_границы.md).

**103/127 — промежуточный аудит; следующий SCL-01. Фаза заданий исполнителю не начата.**
