# ING-03 — Точный bounded stream и schema membership

**LANE-08 · CP2 · B83, B84, B86 · fix + native resource/schema qualification.**

**Практическая цель:** Поток сохраняет состав допустимых строк и логические окна, не платя квадратичной сериализацией за контроль памяти.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/ING-03.md) · [остатки C101](../05_Основания/Аудит/01_Реестры/C101_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/ING-03_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 измерен как operation count, не production CPU/OOM. R02 ограничен existing CATEGORY allowlist, не exhaustive equivalence всех validators.

## 2. Сохранить работающий смысл
- Exact UTC horizon and scope
- No live-key eviction or identity hash fallback
- Disabled at-least-once semantics
- Pre-publication capacity guards
- At-cap logical window transitions
- Optional/required/null/type/finite validation
- Actual quarantine storage/readback

Защищённые различения: исходные positive/negative boundaries выше. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C101-R01: fix** → REQ-ING-03-01, REQ-ING-03-04. Owned exact incremental byte accounting with reference scan oracle.
- **C101-R02: fix** → REQ-ING-03-02. Existing CATEGORY restriction reaches actual row admission/quarantine.
- **C101-G01: qualify** → REQ-ING-03-01, REQ-ING-03-02, REQ-ING-03-03, REQ-ING-03-04. Native OS worker/CAS/consumer and separate resource measurements.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-ING-03-01
Exact retained-byte accounting должно быть incremental на existing accumulator owner, без повторной сериализации всего pending buffer при каждом admission. Restore/preview/eviction/flush сохраняют точный прежний serialization-size contract.

**TEST-ING-03-01 — native unit / integration; NOT_RUN.**
- Setup: Long unclosed SESSION20/40/80, COUNT/TUMBLING/count- и time-SLIDING, JSON roundtrip restart, same row object repeated; instrument estimator calls.
- Действие: Actual process and accumulator transitions; compare cached total с independent full scan after every transition.
- Точный oracle: Точные totals/cap decisions совпадают; buffered_bytes O(1); retained payload сериализуется один раз при owned admission/restore, не N² через repeated scans. Preview не меняет live accounting; flush/expiry освобождают соответствующий size.
- Doubles/границы: Это serialized payload bytes, не RSS. Отдельно измерить CPU/RSS/source allocation, без fabricated SLO/OOM.

### REQ-ING-03-02
CATEGORY.allowed_values применяется в row-local stream admission и actual quarantine; None означает отсутствие ограничения, empty set не равно None.

**TEST-ING-03-02 — native unit / integration; NOT_RUN.**
- Setup: Schema CATEGORY allowed={allowed}, empty set, None, optional missing/null и invalid type; batches1/3/8, same source set.
- Действие: Actual field_value_violation→sanitizer→CAS chunk/quarantine→fresh reader.
- Точный oracle: outside rejected с stable specific reason; allowed retained; empty set отвергает все present non-null category values, None не ограничивает; missing/null решает existing presence/nullable contract; batch membership одинаков.
- Doubles/границы: Не coercion в str, guessed enum или majority inference; sibling DataFrame contract comparison для CATEGORY, не claim all-schema equivalence.

### REQ-ING-03-03
Exact UTC first-accepted horizon и source event/version scope сохраняются на native separate-process restart; capacity не вытесняет живые keys и disabled остаётся at_least_once.

**TEST-ING-03-03 — native unit / integration; NOT_RUN.**
- Setup: Existing OS worker, UTC86399/86400, cap2 a,b,c,a затем cap3 retry; malformed/missing owner/event/version; same IDs different sources.
- Действие: Actual process→persisted CursorStore→new PID restore.
- Точный oracle: 86399 suppress,86400 admit; c при cap2 refusal без eviction, cap3 retry correct; disabled сохраняет все rows; unknown source identity не hash/position fallback.
- Doubles/границы: Finite/replay owner не production currentness; separate PID evidence обязателен для этого claim.

### REQ-ING-03-04
Input/operator/output capacity guards сохраняют window semantics и quarantine/consumer usefulness; честный unsupported spill не выдаётся за disk spill.

**TEST-ING-03-04 — native unit / integration; NOT_RUN.**
- Setup: 4 window strategies×backpressure profiles, restored/live over-cap и exact closing transition; oversized chunk до sanitizer; native CAS/tenant/profile.
- Действие: Full modes→real chunk/window/quarantine→fresh consumers, с removal controls guards.
- Точный oracle: Rejected transition не публикует input/frontier; at-cap legitimate close допускается; valid bounded corpus читается; optional coverage не CDC removal; bad finite/type rows quarantined.
- Doubles/границы: Не forced flush или silent row drop; allocation producer до возврата chunk измеряется отдельно от retained-state cap.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

В `src/polisyos/fabric/data_plane/streaming.py::StreamWindowAccumulator` добавить owned size accounting, а не memoization по одному id(dict). Row entry должен удерживать exact object identity и измеренный serialized size; row payload после admission считается immutable в existing transition contract. Если caller может mutate rows, owner делает bounded snapshot при admission либо явно отвергает mutation; silent stale size запрещён. Счётчик учитывает каждое retained occurrence в действующих buffers, а не unique ID, поэтому repeated references не занижают bytes.

Все append/remove/clear/expiry/restore переходы обновляют total; `buffered_bytes()` возвращает total. Preview копирует containers и accounting, не делит mutable counter/live entries. Restore заново вычисляет sizes из принятых rows один раз, не доверяет записанному произвольному total. Сопоставить независимому full-scan oracle на каждой из существующих window strategies, включая incomplete sliding tail. Existing row-ref pruning остаётся provenance owner; не заявлять устранение любой O(N²) работы всего loop по одной bytes оптимизации.

`src/polisyos/fabric/data_plane/schema_rows.py::field_value_violation`: после type membership проверить CATEGORY и field.allowed_values is not None, возвращая предложенный стабильный code `schema_allowed_values_violation` при value not in set. Null/missing остаются caller-owned. Использовать существующий quarantine producer; не новый schema engine. ING-02 first-frontier correction применить раньше shared native acceptance.

## 6. Общая интеграция и порядок
**E02-I08-C**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- ING-02 predecessor and shared streaming.py mutex
- E02-I08-C actual CAS/quarantine/fresh consumer

Owners/callers: `src/polisyos/fabric/data_plane/streaming.py`; `src/polisyos/fabric/data_plane/schema_rows.py`; `src/polisyos/fabric/data_plane/quarantine.py`; `src/polisyos/fabric/connectors/contracts/_schema_field.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Checkpoint representation не обязана хранить cached total; восстановление вычисляет его по существующим rows, сохраняя old state readability. Если вводится новый versioned field, старое отсутствие имеет deterministic rebuild path. Не менять horizon/window policy ради размера.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Общий row/schema/state owner расширяется один раз; source semantics задаёт bound contract. Реальный spill может быть дальнейшей полезной capability, но текущий honest bounded refusal допустим и не оправдывает ложное имя implemented spill.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/fabric/data_plane/test_e02_c_streaming_oracle.py`, `tests/unit/fabric/data_plane/test_streaming_runtime.py`, `tests/_helpers/source_progress_stream_worker.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
