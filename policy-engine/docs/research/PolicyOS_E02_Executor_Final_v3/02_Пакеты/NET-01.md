# NET-01 — Terminal cancellation без потери physical cleanup owner

**LANE-08 · CP2 · B87, B89, B90 · fix + current-test repair + native qualification.**

**Практическая цель:** Отмена не блокирует event loop и не выдаёт новую физическую ёмкость до подтверждённого закрытия старого handle.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/NET-01.md) · [остатки C102](../05_Основания/Аудит/01_Реестры/C102_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/NET-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Terminal cancellation busy loop confirmed bounded; production leak/overcommit frequency не установлены.

## 2. Сохранить работающий смысл
- Exact handle/owner/permit accounting
- Generation admission
- Absolute acquisition deadline and provider timeout identity
- Network outside metadata lock
- Retryable registry/private pool ownership
- Physical FD close confirmation before same-key reuse

Защищённые различения: исходные positive/negative boundaries выше. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C102-R01: fix** → REQ-NET-01-01. Distinguish done-cancelled task from active cleanup plus caller cancellation.
- **C102-G01: qualify** → REQ-NET-01-01, REQ-NET-01-02, REQ-NET-01-03. Native physical owner and supported selected transport qualification.
- **C102-G02: fix** → REQ-NET-01-04. Update stale test setup to current explicit contract, not production guard removal.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-NET-01-01
Terminal cancelled cleanup task должен завершать ownership settlement без busy loop; отмена caller при ещё активной cleanup не отменяет физическую очистку.

**TEST-NET-01-01 — native unit / integration; NOT_RUN.**
- Setup: Actual pool acquire→release, disconnect raises CancelledError; external watchdog child and heartbeat; separate caller cancellation while gated disconnect still active.
- Действие: Run _cleanup_pooled through public release/close, retry same owner after connector permits close.
- Точный oracle: Terminal task не shield-loop, heartbeat исполняется, отказ/отмена распространяется; pending owner/permit retained до confirmed close; retry закрывает exact FD и освобождает один slot. Caller-cancel active cleanup остаётся shielded.
- Doubles/границы: Не считать timeout-with-kill PASS; watchdog только ограничивает defective run.

### REQ-NET-01-02
Exact object/owner/generation/permit lifecycle сохраняется при lock/connect/health/close cancellation и pool close race, без physical overcommit.

**TEST-NET-01-02 — native unit / integration; NOT_RUN.**
- Setup: Pool1/2, mutated handle/clone, suppressing connect, late result, persistent disconnect failure; actual local FD.
- Действие: Acquire/release/close/retry and same logical key vs independent partition.
- Точный oracle: Clone не освобождает lease; unknown close не выдаёт replacement same key; sibling independent; fstat readable before close, EBADF after confirmed retirement; permit exactly once.
- Doubles/границы: Одних counters недостаточно; deletion physical close при сохранённых counters должен ломать oracle.

### REQ-NET-01-03
Network work остаётся вне metadata lock, absolute admission deadline покрывает permit/lock/connect/health без маскирования provider TimeoutError.

**TEST-NET-01-03 — native unit / integration; NOT_RUN.**
- Setup: Gated connect/health/disconnect, independent release, two concurrent connects max2, provider own TimeoutError.
- Действие: Controlled event ordering through actual pool.
- Точный oracle: Independent release proceeds; two connects start; late handle не published into closed/expired generation; original provider timeout identity preserved.
- Doubles/границы: Deadline admission не обещает мгновенный abort некооперативного physical cleanup; throughput отдельно измеряется.

### REQ-NET-01-04
Три stale finalizer tests приводятся к явному current lifecycle-only или source-owned profile и реально достигают injected failure. Native session/registry retry сохраняет primary error и cleanup notes.

**TEST-NET-01-04 — native unit / integration; NOT_RUN.**
- Setup: Checkpoint lookup/rewind/poll failures, subscribe failure; dedupe disabled/at_least_once только lifecycle tests, admitted owner для source tests.
- Действие: Actual StreamingSourceSession/process→registry retained private pool→retry→fresh consumer.
- Точный oracle: Target failure reached; primary object preserved with cleanup note; failed cleanup остаётся retryable и не blocks independent partition; current native suite assertions PASS, old audit FAIL не переименованы.
- Doubles/границы: Не удалить source owner gate и не weaken assertion ради green suite.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

В `src/polisyos/fabric/connectors/pool.py::_cleanup_pooled` except CancelledError обязан проверить cleanup_task.done()/cancelled(). Пока owned task активна, сохранять caller-cancel flag и продолжать shielded wait. Если task терминально cancelled, прекратить ожидание и перейти в единый settlement: cleaned=False, exact pending owner остаётся, completed failed task снимается только если всё ещё тот же task, permit не освобождается как при успехе. После settlement распространять cancellation, не возвращать True. Одновременно завершившийся successful task с caller cancellation также сначала settles correct physical result, затем распространяет caller cancellation.

Использовать existing lock и exact task identity checks; не sleep(0) как маскировку spin и не catch BaseException+release. `_close_connection` уже снимает closing при cancelled disconnect; retry создаст новую owned cleanup task. Остальные acquire/generation/physical owner mechanics сохранить.

В actual `tests/unit/fabric/data_plane/test_streaming_runtime.py` fixtures трёх finalizer cases явно выбрать lifecycle-only disabled dedupe/at_least_once либо предоставить настоящий finite owner, в зависимости от проверяемого смысла. Root issue — stale fixture admission, не source gate. NET-01 owns pool/session finalizer; ING-02/03 own other streaming.py sections.

## 6. Общая интеграция и порядок
**E02-I08-C**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- ING-02 depends on cleanup; streaming.py section mutex with ING-02/03
- E02-I08-C physical resources and useful fresh consumer

Owners/callers: `src/polisyos/fabric/connectors/pool.py`; `src/polisyos/fabric/data_plane/streaming.py`; `src/polisyos/fabric/connectors/_registry_lifecycle.py`; `src/polisyos/fabric/connectors/registry_core_parts.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Public cancellation остаётся cancellation. Pending cleanup не исчезает при diagnostics/cache eviction, same logical key fenced до physical close. Старые audit FAIL сохраняются историей; новые tests получают новые commands/commit evidence. Rollback не ослабляет physical capacity.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Небольшой shared lifecycle protocol полезен разным connectors; отдельные native driver contracts проверяются адресно. Не нужен новый pool framework или глобальная distributed exactly-once система.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/fabric/connectors/test_pool_e02.py`, `tests/unit/fabric/connectors/test_pool_admission_races.py`, `tests/unit/fabric/data_plane/test_stream_pool_physical_cleanup_oracle.py`, `tests/unit/fabric/data_plane/test_streaming_runtime.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
