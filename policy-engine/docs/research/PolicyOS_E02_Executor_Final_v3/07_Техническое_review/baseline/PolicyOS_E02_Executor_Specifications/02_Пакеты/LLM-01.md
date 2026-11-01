# LLM-01 — Ответ и обязательный учёт переживают отказ optional telemetry

**Лейн:** LANE-09 · **Окно:** CP2 · **Основания:** B64, B65, B66 · **Тип:** fix + preserve + lifecycle qualification.

**Практический результат.** Сохранить полезный provider response и точный расход даже при отказе необязательной наблюдаемости; не расходовать повторно из-за экспортного сбоя.

**Статус:** исполнительское ТЗ. Это не выполненный ремонт; все новые TEST ниже — **NOT_RUN**. Исходный аудит выполнен на `20d9009be21097bfbdc38a546a15cc60213b8ace`; его полнота не означает закрытия остатков.

## 1. Основание и границы
[Аудит LLM-01](../05_Основания/Аудит/02_Пакеты/LLM-01.md), [остатки C106](../05_Основания/Аудит/01_Реестры/C106_остатки.json), [полная исходная карточка](../05_Основания/Аудит/05_Источники/LLM-01_исходные_строки.txt). B64/B66 уже исправлены на bounded цепочке; обязательны preserve/qualification, не искусственная переделка. R01/R02 ограничены optional sink failures, не доказанная потеря durable charges или production frequency. Full probes доступны в отдельно доставленном phase1 ZIP; historical bounded counts не являются свежей native приёмкой.

## 2. Сохранить
Prompt ABI, Core proof, original usage/current increment, unique receipts, expiry и unknown. Нельзя глотать mandatory budget/security audit под именем optional observability.

## 3. Полная disposition остатков

- **C106-R01 — fix** → REQ-LLM-01-01. Изолировать optional export и сохранить обязательный post-record в sync/async.
- **C106-R02 — fix** → REQ-LLM-01-02. Safe span boundary сохраняет response и primary mandatory/provider error.
- **C106-G01 — qualify** → REQ-LLM-01-03, REQ-LLM-01-04, REQ-LLM-01-06. Native supported backend/interface и actual unresolved-outcome→admission lifecycle. Shared fallback repair C107-G02 также принадлежит LLM-01, не двойной writer.

Исходные обязанности и сохранения lossless inventory связаны отдельно в companion JSON (`obligation_dispositions`, `preservation_bindings`); номера residual не заменяют исходные обязанности.

## 4. Нормативные требования

### REQ-LLM-01-01
Optional latency/cost histogram failure в LLMBudgetEnforcer не должен скрывать успешно полученный response, препятствовать обязательному post_record или запускать повторный provider. Async generate и sync invoke должны сохранить actual settlement и local budget projection; optional degradation наблюдаема отдельно.

Основание: B65; аудит: C106-R01. Проверка: TEST-LLM-01-01.

### REQ-LLM-01-02
Optional span attribute/status/record_exception/context-manager failure не должен менять success response или верхний тип mandatory accounting/security/settlement ошибки. LLMAccountingError должен сохранить response и original cause; отказ только telemetry не переобозначается как provider failure.

Основание: B65; аудит: C106-R02. Проверка: TEST-LLM-01-02.

### REQ-LLM-01-03
Обязательный accounting отказ либо unknown amount остаётся различимым от отсутствовавшего provider call; actual runtime spending owner должен удержать следующий расход согласно текущему unresolved-outcome правилу до reconciliation, не превращая unknown в zero или проглатывая ошибку.

Основание: B65, B66; аудит: C106-G01. Проверка: TEST-LLM-01-03.

### REQ-LLM-01-04
Поддержанные named/positional prompt нормализуются один раз; совместимый дубль не дублируется, конфликт отказывает до transport. User/system/messages и действующий sanitizer contract сохраняются; неподдержанная форма не переинтерпретируется в новый смысл.

Основание: B64; аудит: C106-G01. Проверка: TEST-LLM-01-04.

### REQ-LLM-01-05
Actual factory miss+2hits должны дать один physical event и отдельные consumer reuse events/receipts с original usage и нулевым provider increment для hits. Expiry создаёт новый charge; forged marker/invalid origin proof не создаёт committed reuse, а missing usage сохраняет unknown.

Основание: B66. Проверка: TEST-LLM-01-05.

### REQ-LLM-01-06
Штатный fallback PolicyOSTracer при supported no-OTel profile должен принимать те же используемые start_as_current_span keywords, что основной tracer, включая kind/record_exception/set_status_on_exception, и не требовать тестового shim. Native configured observability и fallback проверяются раздельно; detailed scope/concurrency остаётся LLM-02.

Основание: B65; аудит: C106-G01, C107-G02. Проверка: TEST-LLM-01-06.

## 5. Решение на текущих owners
Все code paths ниже repo-relative от `policy-engine/` на pinned commit.

1. `src/polisyos/scientist/orchestration/llm/budget_enforcer.py::generate/invoke`: response получить один раз; `_post_record` должен исполняться независимо от `_record_latency`. Оградить именно optional export boundary, не весь post_record. `_post_record` содержит mandatory audit и local spend mutation, а `_emit_cost_metrics` — optional tail: изоляция хвоста не должна проглатывать audit_log.append failure. Existing `emit_degraded_path` использовать с безопасным diagnostic sink; его отказ не запускает рекурсию/повтор transport. Reservation release остаётся exactly once. Local projection не заменяет durable ledger.
2. `src/polisyos/core/llm/traced_client.py::_record_tokens/generate` и sync analog: существующую tracing boundary расширить безопасной публикацией span attrs/status/exception. При создании/enter/exit optional span различать exception самого exporter и exception тела: context manager не может подавить body failure. Сначала сохранять обязательный settlement; primary response/error держать вне optional callbacks, затем best-effort telemetry. Не ловить одним blanket except всё исполнение provider/ledger. Никакой retry provider по sink error.
3. Shared no-OTel fix: `src/polisyos/core/observability/__init__.py::PolicyOSTracer.start_as_current_span` привести к используемому keyword API `src/polisyos/core/observability/tracer.py` (attributes,kind,record_exception,set_status_on_exception); noop не имитирует реальные traces. LLM-01 единственный owner; LLM-02 потребляет.
4. B64/B66 owners — existing `src/polisyos/core/llm/response.py`, `src/polisyos/core/llm/traced_client.py`, `src/polisyos/scientist/orchestration/llm/factory.py`, `src/polisyos/scientist/orchestration/llm/prompt_cache.py`: preserve known repairs. Для G01 проследить actual `src/polisyos/runtime/http/services/control/job_nl_execution.py` owner guard и BudgetMiddleware/FileBudgetLedger after unknown/mandatory failure; не сочинять новый financial subsystem. Если missing integration обнаружится, подключить существующий unresolved settlement gate, не просто добавить «unknown» поле.
5. Test placement: `tests/unit/scientist/orchestration/llm/test_factory_cache_composition.py`, `tests/unit/scientist/orchestration/llm/test_prompt_cache.py` существуют; targeted tracing/budget tests выбрать по фактическим владельцам после чтения. Original предложенный `tests/unit/remediation/test_llm_01.py` не объявляется существующим. Native 3.14 suite без AST runner/telemetry shim.

## 6. Локальные различающие проверки

Все TEST — будущие спецификации проверок, не заявления о существующих тестовых функциях. Сначала расширять перечисленные реальные test owners; новый файл — только при отсутствии подходящего owner.

### TEST-LLM-01-01 — native unit + actual wrapper composition / NOT_RUN
- **Setup:** Real LLMBudgetEnforcer с actual inner traced client и FileBudgetLedger; controlled provider cost0.02; отдельно throwing latency и cost sinks.
- **Действие:** Выполнить async generate и sync invoke; повторить без sink failure.
- **Oracle:** 1 provider, ответ доступен; durable ledger и local spent=0.02, reservation released; degraded diagnostic; нет second dispatch. Mandatory audit failure не swallowed.
- **Ожидаемый исход:** Positive полезный ответ при optional sink fault; старый code скрывает return.
- **Doubles / граница:** Provider/sinks doubles разрешены; реальны wrapper/accounting/ledger. Нельзя заменить _post_record или судить только по inner charge.
- **REQ:** REQ-LLM-01-01.

### TEST-LLM-01-02 — native tracing boundaries / NOT_RUN
- **Setup:** Configured tracer поочерёдно throws on attribute, status, record_exception, enter/exit; provider success/error и mandatory callback error.
- **Действие:** Вызвать real TracedLLMClient и проверить результат/exception.
- **Oracle:** Success response сохранён; accounting ошибка остаётся LLMAccountingError с тем же response/cause; provider ValueError остаётся primary. Optional span faults только degraded. Обязательная failure не исчезает из-за safe-span handling.
- **Ожидаемый исход:** Positive и negative сохранение семантики; старый attribute/status reproducer различающий.
- **Doubles / граница:** Failing tracer допустим и явно не production-frequency claim; не подменять клиент или mandatory callback success.
- **REQ:** REQ-LLM-01-02.

### TEST-LLM-01-03 — native runtime owner / ledger lifecycle / NOT_RUN
- **Setup:** Actual scoped producer admission, settlement store и budget owner; provider получил ответ, required accounting падает/amount unknown; сохранённое намерение и record.
- **Действие:** Попытаться начать следующую генерацию тем же run до reconciliation, затем выполнить existing reconciliation/replay и разрешённый retry.
- **Oracle:** До разрешённого settlement owner не выдаёт uncontrolled spend; response/cause/unknown record сохранены, не synthetic zero. После корректного reconciliation допуск восстанавливается один раз без double charge.
- **Ожидаемый исход:** Lifecycle qualification с positive recovery; product repair только если real path не соответствует правилу.
- **Doubles / граница:** Transport fake разрешён; gate/store/reconciliation реальные. Нельзя ограничиться DTO unknown или handwritten gate.
- **REQ:** REQ-LLM-01-03.

### TEST-LLM-01-04 — native interface/sanitizer characterization / NOT_RUN
- **Setup:** Prompt-capable provider и actual Gateway preparation; named/positional/equal duplicate/conflict/user/system/messages; sanitizer on/off fixtures без секретов.
- **Действие:** Вызвать реальные normalization+transport boundaries.
- **Oracle:** Supported prompt передан один раз; conflict0calls; user/system/messages сохраняют declared transformation; sanitizer change не выдаётся equivalent.
- **Ожидаемый исход:** Positive supported inputs и explicit rejection unsupported.
- **Doubles / граница:** Provider spy allowed; не arbitrary kwargs acceptance и не новый interface для всех providers.
- **REQ:** REQ-LLM-01-04.

### TEST-LLM-01-05 — native factory→real ledger integration / NOT_RUN
- **Setup:** Actual create_traced_gateway_client/cache/normalizer/tracer/FileBudgetLedger; single controlled endpoint и deterministic reply.
- **Действие:** Miss+2hits, expiry+miss, raw=None/missing usage и damaged origin/proof variants.
- **Oracle:** 1call и 3unique events на первой серии, billable increments0.02/0/0; expiry total0.04. Original tokens/request_id retained как provenance. Damaged authority не committed; unknown не нулевая сеть.
- **Ожидаемый исход:** Полезный cached response и корректный учёт; fixed provider price synthetic.
- **Doubles / граница:** Fake _post_json разрешён; factory/CAS or filesystem ledger/cache/Core proofs реальные. Sanitizer configuration зафиксировать.
- **REQ:** REQ-LLM-01-05.

### TEST-LLM-01-06 — native profile qualification / NOT_RUN
- **Setup:** Supported Python3.14 и declared dependencies; standard optional OTel profile, отдельно no-OTel fallback import.
- **Действие:** Запустить actual factory/traced path с используемыми keywords; existing cache/accounting suites плюс LLM-02 consumption.
- **Oracle:** Нет pre-assertion TypeError(kind); body assertions реально выполнены. Configured backend error не маскирует result; оба profiles честно отмечены RUN/BLOCKED/N/A.
- **Ожидаемый исход:** Shared compatibility repair положительно потребляется LLM-02.
- **Doubles / граница:** Не install/monkeypatch tracer signature; actual fallback owner, optional exporter can be local controlled sink.
- **REQ:** REQ-LLM-01-06.

## 7. Общий сценарий, зависимости и ownership
**E02-I09-B**: actual factory→cache/singleflight→trace ledger. LLM-01 владеет optional telemetry/fallback, LLM-02 — согласованным reuse/flight delta; один writer на общие файлы, последовательная интеграция. Не дублировать ledger harness. [Канонический сценарий LANE-09](../03_Интеграция/LANE-09.md). CP2 — окно связанной приёмки, не новый runtime gate.

## 8. Совместимость, история и rollback
Ledger/history не переписываются. Existing exception classes/accounting origin сохраняются. Optional sink теперь degraded вместо ложного provider failure — intentional delta. Rollback отключает неисправный optional exporter, не mandatory accounting и не контроль расходов; already received response не генерируется заново.

## 9. Free-grow/design alignment
[Vision §3,§6–§7](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) требует реального connected consumer и единого owner. [Honest diagnostics substrate](../05_Основания/Архитектура/honest-diagnostics-substrate.md) отделяет диагностическое утверждение от основания. Малый sink repair не оправдывает новый telemetry/финансовый framework. LLM ответ остаётся proposal; технический receipt не scientific truth.

## 10. Приёмка и пределы PASS
Показать R01/R02 before/after, sync и async, actual factory→filesystem ledger и actual gate recovery; один общий E02-I09-B evidence set. Не выдавать native imports за suite, injected failing tracer за измеренную production частоту, synthetic0.02 за invoice, exception context за доступный обычный return. C107-G02 fallback work прослеживается из LLM-02 сюда.

Для каждого TEST: actual command/runtime/commit, exit/log, input hashes, assertions и список doubles. Новые tests NOT_RUN до исполнения. Адаптируемый шаблон `<supported-python> -m pytest <verified test paths>` из `policy-engine/`; runner/dependencies здесь не объявлены доступными. Не устанавливать зависимости как часть этого задания на документы.

