# NET-02 — Adaptive recovery через реальный provider success

**LANE-08 · CP2 · B91, B92, B93 · fix + native resilience qualification.**

**Практическая цель:** Rate limiter восстанавливает пропускную способность после успешных вызовов, не забывая quota/circuit protection.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/NET-02.md) · [остатки C103](../05_Основания/Аудит/01_Реестры/C103_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/NET-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 affects adaptive=True wrapper path, not all REST requests. Controlled clock proves state transitions, not production latency/SLA.

## 2. Сохранить работающий смысл
- Fractional refill/unit capacity
- Invalid rate and overweight refusal
- Generation-specific lease finalization
- Local admission origin distinction
- Mandatory cooldown/balance/pins
- Long-lived REST wrappers and numeric-key equivalence
- Neutral state reclamation

Защищённые различения: исходные positive/negative boundaries выше. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C103-R01: fix** → REQ-NET-02-01. Single common success feedback edge, no regulator reset.
- **C103-G01: qualify** → REQ-NET-02-02, REQ-NET-02-03, REQ-NET-02-04. Native telemetry/REST and scoped quota evidence.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-NET-02-01
Оба adaptive wrappers должны передать каждый successful provider completion существующему AdaptiveRateLimiter.record_success ровно один раз после result и до release registry lease.

**TEST-NET-02-01 — native unit / integration; NOT_RUN.**
- Setup: with_rate_limit и apply_resilience adaptive=True,429 rate1→0.5, затем 100 и 800 successes; plain limiter control, cancellation/provider failure.
- Действие: Actual public wrappers, controlled clock and provider result identity; registry cap1 pressure after recovery.
- Точный oracle: 100 successes дают 0.55,800 достигают 1 по текущему owner contract; success_count изменяется; cooldown/pacing соблюдены; neutral owner освобождается безопасно. Plain API не требует record_success; cancellation/error не recovery vote.
- Doubles/границы: Не direct-call limiter вместо wrappers, не reset owner/skip quiescent guard.

### REQ-NET-02-02
Fractional refill и unit capacity сохраняются, invalid rates/overweight отказывают до provider; actual long-lived REST wrapper разделяет правильный quota key.

**TEST-NET-02-02 — native unit / integration; NOT_RUN.**
- Setup: Rates0.1/0.2/1/2, capacity1, request weight2, NaN/inf/zero; pagination и subsequent fetch, same numeric key1/1.0, distinct domain.
- Действие: Actual GenericRESTConnector с controlled local provider; native telemetry profile.
- Точный oracle: 0.2: первый request допускается, следующий через 5 clock units; refill не округлён; invalid/overweight provider calls0; pages/fetches share owner, domains independent.
- Doubles/границы: Конкретный source start burst/quota scope подтверждается отдельно; default adaptive=False не объявлен affected R01.

### REQ-NET-02-03
Circuit завершает issued lease его поколения, сохраняя original provider result/error и distinguish local admission overload. Protected registry не теряет cooldown/balance/pins.

**TEST-NET-02-03 — native unit / integration; NOT_RUN.**
- Setup: Old CLOSED success/failure после OPEN→HALF_OPEN; stale half-open, foreign/double completion, cancellation; TTL/pressure while pinned/cooldown/depleted.
- Действие: Actual execute/registry lease paths и next current probe.
- Точный oracle: Stale result/error preserved без recovery vote; foreign/double diagnostic; local overload не provider failure; protected capacity отказ, neutral reclaim; active state не duplicated.
- Doubles/границы: Не swallow любой CircuitLeaseError, не unbounded second map или reset Retry-After.

### REQ-NET-02-04
Native telemetry/dependency graph и конкретный selected transport дают useful provider result без masking admission errors; measurement scope не distributed guarantee.

**TEST-NET-02-04 — native unit / integration; NOT_RUN.**
- Setup: Supported runtime с current telemetry dependencies и optional no-op profile; actual REST test transport, success/invalid rate/429.
- Действие: Existing suite плюс new success-feedback regression, full E02-I08-C consumer.
- Точный oracle: Correct result/error reached через actual wrappers; optional instrumentation не маскирует expected refusal. Команды/clock/seams/versions записаны, quotas scoped.
- Doubles/границы: Observed audit no-op SLO seam issue квалифицировать и исправить existing fallback owner при воспроизведении, не объявлять fixture workaround native PASS.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

В `src/polisyos/fabric/connectors/resilience/rate_limiter.py::_call_with_limiter` сохранить result = await func(...), затем только для existing AdaptiveRateLimiter вызвать record_success(), вернуть тот же result. Plain RateLimiter API не расширять обязательным callback. Typed RateLimitError branch остаётся единственным rate-limit feedback, другие provider errors/cancellation не success. Existing `with_rate_limit` и `src/polisyos/fabric/connectors/resilience/__init__.py::apply_resilience` уже используют helper под registry lease, поэтому исправление одно.

Callback находится вне provider-exception classification: собственная bookkeeping ошибка не должна повторно считаться provider failure/429. Если нынешний callback может отказать из-за invalid internal config, сохранить отдельный typed internal failure/diagnostic согласно existing owner contract и regression, не broad swallow. Для valid config result identity обязана сохраниться.

Registry quiescent guard уже правилен: уменьшенный adaptive rate не neutral. После реального success feedback восстановится rate, и expired cooldown/full bucket/zero active state позволит безопасное reclamation. Circuit generation и REST wrapper lifetime не переписывать. Native optional telemetry fallback проверить вместе с существующим core observability owner; no new telemetry framework.

## 6. Общая интеграция и порядок
**E02-I08-C**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- NET-01 owns physical pool independently; E02-I08-C
- Optional telemetry fallback coordinated with existing core observability owner

Owners/callers: `src/polisyos/fabric/connectors/resilience/rate_limiter.py`; `src/polisyos/fabric/connectors/resilience/__init__.py`; `src/polisyos/fabric/connectors/resilience/circuit_breaker.py`; `src/polisyos/fabric/connectors/resilience/_bounded_registry.py`; `src/polisyos/fabric/connectors/reference/rest_json.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Fractional rate defaults и key identity не меняются. Historical throttled owner не сбрасывать при patch: recovery идёт от последующих real successes. Никакой implied global quota между процессами; конкретный source contract определяет start balance/burst.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Полезная адаптация строится обратной связью producer→existing owner, не дополнительным registry. Новые transports используют общий wrapper contract; source semantics и scientific authority остаются отдельными.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/fabric/connectors/test_resilience.py`, `tests/unit/fabric/connectors/test_regulator_lifetime_e02.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
