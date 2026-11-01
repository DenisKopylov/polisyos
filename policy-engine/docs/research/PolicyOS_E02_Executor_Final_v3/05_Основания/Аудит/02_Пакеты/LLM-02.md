# LLM-02 — разрешённый immutable reuse и single-flight

**C107 · LANE-09 · B67, B68 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

В существующей обёртке действительно есть owner-bound reuse, общий single-flight, bounded retention, защита mutable projection и явный lifecycle. Это не только lock вокруг словаря: четыре допустимых запроса разделяют одну physical работу, follower cancellation не отменяет остальных, error/deadline освобождают flight, а actual ledger различает provider и reuse. Scoped factory после закрытия не разрешает retained client выполнять новые действия; уже начатый producer сохраняет исходную attribution.

**Остаётся C107-R01:** publication между admission и claim безопасно уводит consumer в новый physical call даже при уже доступном допустимом результате. Это low-severity потеря экономии, не ложный reuse. **B67 не закрыт полностью:** authorized non-strict путь reuse-ит frozen URL, но strict runtime-style путь оставляет lexical freshness barrier. Его нельзя просто снять без действительного trusted binding всех чувствительных inputs.

**7 MATCH + 1 PARTIAL. 41 неизменённое тело теста / 80 cases: 79 PASS, 1 FAIL** после явного optional-tracer fixture. Original run без этой подстановки сохранён; native suite не объявлена зелёной.

## 2. Матрица исходных оснований

| Основание | Исходный ремонт | Фактическая способность | Остаток |
|---|---|---|---|
| B67 | Snapshot bytes/hash/version + principal/model/request digest и текущий authorizer участвуют в key/admission; URI не authority. Live URL без valid context не reuse-ится. | P03 читает настоящие fixture bytes: одинаковый frozen URL даёт1 physical call, смена epoch, отзыв grant и смена bytes требуют новую работу. P04 plain strict request reuse-ится; seeded strict calls остаются отдельными. | G01: strict URL/uncertainty input отказывается до authorizer, поэтому generic frozen path не равен active runtime qualification. Native CAS/permissions G02. |
| B68 | Общие flight/Future на exact cache, per-request registrations, shielded waiter, timeout/cleanup, detached flight snapshot и per-consumption proof. | Existing 4-way/two-loop/cancellation/owner lifecycle tests и P05/P06 исполнены. P05:4 waiters,1 cancel,1 provider,3 successful consumers,3 receipts,spent 0.02. | R01: admission→publication→claim duplicate. G02: supported runtime/CAS/HTTP execution не выполнены. |

## 3. Owner→producer→consumer, а не наличие файлов

Runtime snapshot binding читает actual CAS bytes и selected profile, связывает tenant/cell/actor; configured owner должен независимо разрешить текущий scope [S14:222–296]. Job execution входит в producer binding и `_gateway_cache_reuse_scope` с current admission проверками [S13:149–350]. Это source-only trace, не доказательство configured deployment authority.

Factory принудительно выбирает строгий режим внутри job scope. Cache готовит immutable provider dispatch до выбора key, проверяет eligibility и authorizer, затем либо выдаёт authenticated reuse, либо регистрирует/join-ит один shared flight. Core owns exact response/session proof. Follower получает frozen projection именно своего flight, а не более поздний cache head. Actual ledger связывает каждый reuse с physical origin и отдельным receipt. Закрытие factory scope не ждёт заблокированный worker, но запрещает late dispatch; already-started outcome доучитывается исходным owner.

Ни `temperature=0`, ни `cacheable=True`, ни строка hash сами по себе не разрешают объединение независимых экспериментов. Сохранены tool/stream/freshness/independent-seed guards, provider route/tenant/epoch identities и физический путь для opaque Python values.

## 4. Что исполнено

| Проверка | Наблюдение |
|---|---|
| P01 | 30 unchanged prompt-cache bodies / 43 cases PASS: keys, cloning, TTL/LRU, 4-way flight, follower cancel, error cleanup, два event loops, shared wrapper lifetime, provider route и opaque values. PI body не запускался. |
| P02 | 11 unchanged owner-admission bodies / 37 cases: 36 PASS / 1 FAIL с explicit tracer fixture. Proof poisoning, current fence, closed scope, overlapping principals, 9 started-producer scope/outcome combinations и late begin проверены. NaN expectation остаётся FAIL. |
| P03 | Authorized non-strict frozen URL reuse с independently read local file bytes. Каждый hit сверяет current owner; epoch/revocation/changed bytes не переиспользуют старый результат. Owner — fixture, не native CAS authority. |
| P04 | В strict mode два одинаковых frozen URL inputs дают2 provider calls и0 authorizer calls из-за freshness guard. Plain strict control даёт1 provider на2 consumers. Explicit seed сохраняет независимые вызовы. |
| P05 | Четыре admitted waiters, один follower cancelled:1 provider,3 successful consumers, provider/reuse/reuse,3actual ledger receipts, сумма 0.02. Flight очищен. |
| P06 | Error и deadline каждого shared producer получают4 consumers; flight/cache очищены, следующий запрос выполняет одну свежую работу. |
| P07 | Controlled admission/publication race: другой wrapper успел опубликовать и независимо прочитать тот же admissible результат; paused consumer после release всё равно создаёт второй physical call. |
| P08 | Opaque Python NaN сохраняет original object, делает2 physical calls и0 cache entries. Actual Gateway отвергает nonfinite JSON до transport. Это отдельный current-contract control, не PASS старого теста. |

[Диагностика](../04_Проверки/C107_LLM02/bounded_diagnostics.json) · [команды](../04_Проверки/C107_LLM02/commands.json) · [existing runner](../04_Проверки/C107_LLM02/probe_existing.py) · [boundary probes](../04_Проверки/C107_LLM02/probe_boundaries.py) · [NaN control](../04_Проверки/C107_LLM02/probe_nonfinite.py).

## 5. C107-R01 — безопасный revision fallback теряет уже доступную экономию

После actual admission код проверяет publication revision [S01:806–819](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/llm/prompt_cache.py#L806-L819). Изменение head поднимает ValueError и попадает в `_generate_uncached` [S01:859–868](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/llm/prompt_cache.py#L859-L868), без повторной current lookup.

P07 использует два actual wrappers и два event loops на одной cache/identity/current grant. Первый paused **после настоящего miss admission**, не вместо него. Второй делает единственный physical provider call и публикует ответ. Отдельный sequential control успешно читает этот ответ как hit без нового provider. Затем первый возобновляется, видит revision change и делает второй physical call. Итоговые ответы согласованы; permission/proof не обойдены.

**Оставшаяся работа:** сохранить revision и owner guards, но рассмотреть ограниченное повторение actual admission/lookup при изменении head, когда текущий owner допускает уже опубликованный результат. Нельзя использовать старое разрешение, доверять одному marker, снимать tenant/epoch проверки или добавлять distributed-lock сервис. Масштаб потерь в production и реальная денежная экономия не измерены.

## 6. Сохранить и доквалифицировать

**C107-G01 — strict frozen capability.** Lexical guard действует при strict reuse даже при valid context [S01:1312–1335](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/llm/prompt_cache.py#L1312-L1335). P04 подтверждает отсутствие authorizer call, а actual runtime scope включает strict mode. Поэтому non-strict fixture success нельзя объявить завершённым B67 для активного runtime.

Это безопасная capability limitation, не false authorization. Snapshot одного data source ещё не автоматически фиксирует все внешние ссылки в prompt. Нужно квалифицировать достаточный existing trusted descriptor/owner binding и лишь затем расширять допуск. Не удалять URL/uncertainty_notes, не подменять authority словами агента, не разблокировать tool/stream/independent replica только по temperature. Missing injected production owner сам по себе не новый дефект.

**C107-G02 — исполнимость и tests.** Original run01: 54 PASS / 26 FAIL. 25 cases остановлены до целевых assertions из-за no-OTel fallback: его `start_as_current_span` не принимает `kind`, в отличие от настоящего tracer [S16:600–605; S17:327–350]. Secondary timeouts и pending-task warnings сохранены. Отсутствие required dependencies в текущей неподдерживаемой среде не объявлено 25 product defects.

Run02 использует только явно подставленный optional default tracer; project bodies и ledger настоящие.79 PASS / 1 FAIL не native suite. Metrics fallback не подменён и его ошибки безопасно деградируют. Оставшийся existing NaN FAIL противоречит новому explicit opaque-input contract: P08 отдельно показывает отсутствие reuse и строгий Gateway wire refusal. Старый тест не переписан и не перекрашен.

Native cache/factory imports PASS; native CAS/PI/runtime BLOCKED на Python3.14-only exception syntax в Python3.12.14; pytest отсутствует. Existing CAS scope и full factory/CAS/HTTP tests полностью прочитаны, но не выполнялись. Старый CAS cleanup witness ожидает shield самого flight.task, тогда как текущий код ждёт wrap_future; новый factory test уже наблюдает Core join. Это qualification/test-maintenance остаток, не заявленный execution failure невыполненного теста.

Сохранить current scope lifecycle, retained producer attribution, exact projection proof и existing budget ledger. Поддерживаемый native suite должен квалифицировать эти связи вместе, включая R01, без отдельного искусственного integration test для каждого слоя. Synthetic simulator и cached response не эмпирическая authority и не новый независимый эксперимент.

[Исходная карточка](../05_Источники/LLM-02_исходные_строки.txt) · [pinned источники](../05_Источники/C107_источники.json) · [остатки](../01_Реестры/C107_остатки.json) · [границы](../04_Проверки/C107_LLM02/Чтение_и_границы.md).

**107/127 — промежуточный аудит. Следующий CAL-02. Фаза заданий исполнителю не начата.**
