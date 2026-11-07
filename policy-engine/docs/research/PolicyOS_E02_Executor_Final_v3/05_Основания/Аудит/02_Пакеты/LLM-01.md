# LLM-01 — обёртка, optional telemetry и стоимость reuse

**C106 · LANE-09 · B64, B65, B66 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Исходный duplicate-prompt дефект устранён на проверенных формах. Cache hit больше не выдаётся за повторную оплаченную генерацию: provenance сохраняет исходное usage, текущий reuse получает отдельный event и нулевой provider increment. Это подтверждено не только DTO: actual factory, cache, normalizer, tracing, budget middleware и **настоящий filesystem ledger** прошли локальную цепочку с фикстурным transport.

Защита `metrics.record_llm_call` в TracedLLMClient действует, включая error metric. Но optional observability ещё не изолирована целиком: внешний budget wrapper теряет полученный ответ при отказе histogram; injected tracer может скрыть return или верхний тип accounting error. **C106-R01/R02** — ограниченные остатки, не утверждение частых production сбоев. Полного закрытия пакета нет.

**6 MATCH; 10 неизменённых test bodies /15 cases PASS.** MATCH включает воспроизведённые дефекты. Выбранные project modules импортируются нативно без shim; это не native pytest и не подтверждение всей поддерживаемой среды.

## 2. Матрица исходных оснований

| Основание | Исходный ремонт | Фактическая producer→consumer способность | Остаток |
|---|---|---|---|
| B64 | Prompt удаляется из копии tracing kwargs; одинаковый positional/named дубль сводится к одному, конфликт отказывается до provider. Gateway переводит prompt в user согласно своему интерфейсу. | Existing named/duplicate/Gateway cases PASS; user/system/messages сохранены в P02. Actual factory P05 передаёт один system/user payload; prompt+user отказывает без нового transport call. | Privacy sanitizer и все внешние client interfaces не квалифицированы; G01. Не требуется превращать произвольный неподдержанный ввод в другой смысл. |
| B65 | Optional call/error metrics защищены; обязательный accounting callback не проглатывается, LLMAccountingError удерживает response. | P02 возвращает answer при degraded metrics, primary provider error остаётся исходным. P03/P04 различают actual durable charge, local budget projection и утраченный return. | R01: внешний histogram. R02: injected span. G01: full runtime admission/reconciliation после обязательного отказа. |
| B66 | Normalizer различает original usage и billable increment; raw=None получает cache marker, но marker сам по себе не authority. | Miss+2hits дают 1 provider и 3 event IDs/receipts при сумме 0.02. Expiry даёт новый provider event и суммарно 0.04. Damaged origin/receipt не получает committed acknowledgment; unmanaged не становится paid. | Full reuse authorization/concurrency — следующий LLM-02. Native deployment/financial/scientific validity не следует из локальных fixtures; G01. |

## 3. Actual ownership и выполненные проверки

Factory создаёт Gateway→CachingLLMClient→TracedLLMClient [S04:425–519]. Gateway готовит immutable payload/transport identity; cache хранит detached response projection, Core владеет exact session и response-bound proof. Normalizer получает этот session, а не доверяет произвольному `raw._polisyos_cache`. Tracing отделяет physical provider event от каждого reuse event. BudgetMiddleware передаёт immutable event в FileBudgetLedger, который связывает settlement с точным receipt и origin.

P05 использует **саму фабрику**, не самостоятельно собранный её аналог: explicit config, один endpoint, sanitizer явно выключен. Только `_post_json` заменён конечным fixture, подтверждающим успешную prepared identity. P01 использует существующие project composition tests с локальным provider spy. Ledger writes/readback настоящие, HTTP/model execution отсутствует.

| Проверка | Результат и граница |
|---|---|
| P01 | 10 existing bodies /15 cases PASS: duplicate/conflicting prompt, Gateway mapping, optional/mandatory accounting, forged marker, miss/hits, expiry, 6 повреждений origin custody и unmanaged origin. AST тела неизменны; pytest adapter вместо отсутствующего pytest. |
| P02 | User/system/messages не изменены. Failed optional metrics дают response и observer metrics_status=degraded. Failed error metrics не заменяют исходный ValueError provider. |
| P03 | Actual LLMBudgetEnforcer с рабочим, failing latency и failing cost sink. Provider 1 раз, inner durable spend 0.02 во всех случаях. Latency failure оставляет outer spent 0, cost failure — 0.02; оба не возвращают response. |
| P04 | Configured failing span после ответа скрывает return; durable spend 0.02 остаётся. Failing error-status заменяет LLMAccountingError верхним RuntimeError, но исходный response остаётся в exception context. |
| P05 | Actual factory miss+2hits: 1 fake transport, provider/reuse/reuse, 3 уникальных IDs, 3 committed receipts, metric increments 0.02/0/0. Исходные tokens и request_id сохраняются как provenance, не независимый новый эксперимент. |
| P06 | Missing usage и raw=None дают amount=None, cost_origin=unknown, ledger status=unknown, 0 receipts. Нулевая receipt сумма не означает бесплатную сеть. Дальнейший full-runtime gate не исполнялся. |

[Диагностика](../04_Проверки/C106_LLM01/bounded_diagnostics.json) · [команды и exit codes](../04_Проверки/C106_LLM01/commands.json) · [existing-test runner](../04_Проверки/C106_LLM01/probe_llm01.py) · [boundary probes](../04_Проверки/C106_LLM01/probe_boundaries.py).

## 4. Подтверждённые остатки

### C106-R01 — optional histogram снова становится причиной failed call во внешнем wrapper

После `await client.generate` wrapper вызывает latency histogram **перед** обязательным `_post_record` [S07:424–446](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/llm/budget_enforcer.py#L424-L446). Сам histogram вызван без optional guard [S07:394–412](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/llm/budget_enforcer.py#L394-L412). Cost metrics вызываются уже после local spend mutation, но тоже могут сорвать return.

В P03 failing latency даёт RuntimeError без response, outer spent=0/reserved=0; failing cost даёт RuntimeError при outer spent=0.02. В обоих случаях provider выполнен ровно один раз, а **inner FileBudgetLedger сохраняет расход 0.02 и receipt**. Поэтому вывод — потеря return и, в latency ветке, local projection, а не потеря durable учёта или доказанный повторный денежный платёж.

Это не мёртвый helper: source-only consumer trace показывает подключение wrapper в translator/adversary при budget_state [S14:187–233; S15:117–167]. Их full execution здесь не запускался; автоматический retry не воспроизводился. Аналогичный sync invoke прочитан, но не исполнен.

**Оставшаяся работа:** распространить existing optional-observability isolation на этот wrapper, сохранять полученный response/settlement и выполнить обязательный учёт независимо от экспортных histogram. Не глотать audit/ledger ошибки, не переобозначать provider event, не компенсировать observability failure повторной генерацией. Проверить async и sync boundary отдельно.

### C106-R02 — необязательный span не защищён как metrics sink

`_record_tokens` вызывает span attributes после обязательного accounting callback без guard [S01:1325–1358](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/llm/traced_client.py#L1325-L1358). Accounting-error handler сам вызывает `set_status/record_exception` [S01:1598–1617](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/llm/traced_client.py#L1598-L1617).

P04 с явно configured failing tracer подтверждает два ограниченных исхода: attribute failure скрывает response при уже сохранённом durable расходе; error-status failure заменяет верхний LLMAccountingError на RuntimeError. Исходная accounting exception и response **остаются в `__context__`** — полной утраты exception chain нет. Обычный OTel SDK/exporter не установлен, его реальная семантика и частота отказов не измерены; поэтому severity low, без extrapolation на production.

**Оставшаяся работа:** оградить optional span publication существующей tracing boundary, сохраняя typed mandatory failure, response и original cause. Не ослаблять security/settlement guards и не создавать новую подсистему ради локального ремонта.

## 5. Сохранить и доквалифицировать

Сохранить current prompt interfaces, явный conflict-before-provider, mandatory accounting distinction, exact Core cache session/proof, original usage, unique consumption IDs, expiry charges, unknown amount и origin/receipt readback. Кэшированный ответ не новый независимый эксперимент; условные 0.02 не реальный invoice. Наличие логов, receipt или ответа LLM не подтверждает научную корректность.

**C106-G01.** Actual selected module imports PASS без project shims и без AST extraction. Но Python3.12.14/Pydantic2.13.4 отличаются от declared Python3.14/Pydantic<2.13; pytest отсутствует, настоящий OTel backend не запускался. Начальная ошибка нашего harness сохранена отдельно: run01 остановлен до тестов; run02 действительно выполнил 15 cases.

Нужно квалифицировать supported-runtime suite, optional backend integrations, sync entry и actual runtime stop/reconciliation при mandatory/unknown outcome. P06 доказывает сохранение unknown, но не всю политику последующего допуска. Ни отсутствие зависимостей, ни неисполненная ветка не названы product defect. Concurrency, cancellation, scope и freshness reuse рассматриваются в следующем **LLM-02**, не считаются закрытыми этим проходом.

[Исходная карточка](../05_Источники/LLM-01_исходные_строки.txt) · [pinned источники](../05_Источники/C106_источники.json) · [реестр остатков](../01_Реестры/C106_остатки.json) · [точные границы](../04_Проверки/C106_LLM01/Чтение_и_границы.md).

**106/127 — промежуточный аудит. Следующий LLM-02. Фаза заданий исполнителю не начата.**
