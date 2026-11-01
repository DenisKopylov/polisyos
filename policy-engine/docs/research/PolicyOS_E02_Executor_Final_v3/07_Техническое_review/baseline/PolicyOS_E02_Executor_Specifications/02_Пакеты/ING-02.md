# ING-02 — Возобновимая пустая граница и полная оконная lineage

**LANE-08 · CP2 · B81, B82, B85 · fix + native recovery qualification.**

**Практическая цель:** Transient ошибка до первого commit не блокирует повтор; восстановленные окна сохраняют тот же состав и зависимости.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/ING-02.md) · [остатки C100](../05_Основания/Аудит/01_Реестры/C100_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/ING-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 availability/recovery failure, не доказанная потеря строк. Missing clock confirmed; missing witness следующий guard source-proven, не отдельно исполненный defect.

## 2. Сохранить работающий смысл
- Observed versus committed frontier
- Explicit empty frontier
- Versioned pending operator/order state
- Policy and owner binding
- Concrete contributor refs
- Paired intent/readback/conditional compensation
- Honest replay/at-least-once limits

Защищённые различения: исходные positive/negative boundaries выше. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C100-R01: fix** → REQ-ING-02-01. Initial error metadata derives stable admitted identity, not observed state.
- **C100-G01: qualify** → REQ-ING-02-02, REQ-ING-02-03, REQ-ING-02-04. Native frontier/revalidation/consumer and scoped physical crash evidence.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-ING-02-01
First-frontier ordinary error checkpoint должен быть возобновимым с тем же admitted source/clock и оставаться пустой committed boundary, не observed progress.

**TEST-ING-02-01 — native unit / integration; NOT_RUN.**
- Setup: RuntimeError после poll/dedupe перед raw, после raw, после window до первого commit; source with current owner; fresh CursorStore reopen.
- Действие: Actual process_stream_dataset→save diagnostic→restart.
- Точный oracle: Повтор начинается с chunk0, все rows/windows/refs совпадают непрерывному проходу; cursor не продвинут на failure. Changed owner/clock/schema по-прежнему отказ до poll.
- Doubles/границы: Не manual patch checkpoint и не отключение restart guards.

### REQ-ING-02-02
Все window strategies сохраняют versioned pending state/order/ordinal/policy и paired frontier intent/readback/conditional compensation.

**TEST-ING-02-02 — native unit / integration; NOT_RUN.**
- Setup: COUNT/SESSION/SLIDING/TUMBLING,41 rows, interruption19; failures raw/window/index/commit/readback, cancellation и separate process kill где supported.
- Действие: Continuous vs restart actual CAS/CursorStore; replay native source token implementation отдельно.
- Точный oracle: Точные logical windows/time bounds/rows/ordinal одинаковы; pending dedupe не suppress recovery; old predecessor сохранён при failed transition; no forced flush.
- Doubles/границы: BaseException injection не OS kill; external connector guarantees заявляются только для tested token contract.

### REQ-ING-02-03
Каждое emitted window несёт все concrete contributor refs; withdrawal A должен инвалидировать зависимое A+B окно через штатный consumer/revalidation, не скрываться valid B.

**TEST-ING-02-03 — native unit / integration; NOT_RUN.**
- Setup: Два raw chunks A/B, bucket trigger из C, final flush/restart; actual CAS graph, independent valid D.
- Действие: Publish→fresh consumer→revoke/remove A→existing targeted revalidation/read.
- Точный oracle: Payload-contributor exact match; C не вымышленный data input; affected window недоступно как current, independent D остаётся полезным; восстановление valid A basis даёт controlled rerun.
- Doubles/границы: Не только assert InputRef list; нужен реальный consumer refusal/revalidation witness.

### REQ-ING-02-04
Native modes/evidence/served consumer квалифицирует output и partial guarantees без global exactly-once claim.

**TEST-ING-02-04 — native unit / integration; NOT_RUN.**
- Setup: Actual selected tenant/profile/input closure, source-owned finite JSONL, successful и interrupted run.
- Действие: Whole mode→snapshot/evidence→fresh source collection/public consumer.
- Точный oracle: Полезные complete outputs реально читаются; replay/synthetic limitations явны; schema/owner mismatch не создаёт artifacts или positive cursor.
- Doubles/границы: Не source-only/fixture CAS PASS; shared E02-I08-C evidence не дублировать.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

В `src/polisyos/fabric/data_plane/streaming.py::process_stream_dataset` first-frontier except branch создаёт frontier_metadata={} и пропускает ingestion_clock_profile/source_progress_witness_ref. Сформировать initial empty-boundary metadata из уже admitted clock_profile, schema_binding, source_progress_ref и empty operator/dedupe state. Общие identity поля выделить из existing `_stream_checkpoint_metadata` в маленький helper либо явно переиспользовать тот же owner; не брать текущий mutated accumulator/result как committed state.

`frontier_committed=False`, empty offset/token и zero committed counters остаются. Observed offset/error — только diagnostics. Retained witness при restart проверяется тем же `progress_frame.retained_witness_is_current`; owner/clock mismatch сохраняет refusal. Ошибка после существующего commit по-прежнему копирует именно committed metadata. Если witness невозможно сохранить/проверить, не публиковать такой diagnostic как resumable latest: сохранить отдельную диагностику и прежнюю resume boundary.

ING-02 owns checkpoint/error metadata и contributor consumer qualification; ING-03 owns accumulator accounting/schema checks, NET-01 session finalizer. Shared streaming.py patches последовательно. Native withdrawal witness использует текущий CAS/revalidation owner, не новый storage engine.

## 6. Общая интеграция и порядок
**E02-I08-C**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- ING-01 and NET-01 predecessors; ING-03 shared streaming writer
- E02-I08-C; CAS/revalidation owner review for withdrawal test

Owners/callers: `src/polisyos/fabric/data_plane/streaming.py`; `src/polisyos/fabric/data_plane/cursor_store.py`; `src/polisyos/core/artifacts/store.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Исторический incomplete diagnostic не объявлять валидным автоматически: безопасный repair должен вернуться к доказанной empty/committed boundary с re-admission, не guess offset. Versioned state mismatch остаётся typed repair/refusal. Rollback не продвигает observed chunk.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Восстановление не меняет научную выборку или окно. Новые source token profiles квалифицируются адресно; общий state contract не требует одинаковой offset semantics для всех connectors.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/fabric/data_plane/test_e02_c_streaming_oracle.py`, `tests/unit/fabric/data_plane/test_streaming_runtime.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
