# OBS-02 — непрерывность observation reader после partial yield

## 1. Решение

**Ограниченно оценён, не закрыт. Новый подтверждённый product defect не установлен.** Исходный B147 механизм — повторная выдача всего префикса через full-read fallback — отсутствует в проверенном actual-function corpus. Reader повторно открывает один captured snapshot и пропускает подтверждённые строки; conversion/mapper failures не маскируются как reader errors. До первой выдачи unbounded full read отвергается, а не обходит memory budget.

Свежий результат: **6 bounded MATCH;12 existing native bodies /18 cases BLOCKED,0 native PASS**. Actual snapshot/iterator/mapper/D2/tracking functions исполнены; reader и shard writer — явно обозначенные JSON-backed fixtures. Native successful Parquet/DuckDB/CAS chain не заявлен.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/OBS-02_исходные_строки.txt) · [Pinned sources](../05_Источники/C86_источники.json).

## 2. Матрица исходных IDs

| ID | Проверенный результат | Остаток |
|---|---|---|
| B147 | Same-snapshot retry без повторного prefix, phase-aware refusal между metrics, no full-read fallback; actual incomplete shard/row accounting | G01 native reader/merge/read/CAS; G02 real workload/public rerun lifecycle |
| LK12 | Actual content-bound read API отвергает failed receipt до CAS writes | Successful native admission и весь downstream не выполнялись |

B147 не сводится к локальному offset: current retry связан с private captured bytes. Equal values не удаляются как duplicates. Семантическая ошибка после первого metric допускает честную остановку всей незавершённой generation; это не успешное продолжение без потерь.

## 3. Producer → snapshot → shards → receipt

`_verified_observation_snapshot` открывает regular source, фиксирует initial size, проверяет disk hint и actual free space с reserve, копирует не более исходного размера в temporary file и сверяет SHA256. Рост, усечение и hash mismatch отвергаются до yield; handle закрывается с выходом context (`S01:1420–1467`, `S08`). Это bounded disk-backed capture, не гарантия отсутствия concurrent exhaustion или power-loss.

Iterator различает `reader`, `conversion`, `mapper`. Permission/FileNotFound и non-reader errors не переключают backend. До первого yield нет доказанного decoded-memory bound, поэтому выдаётся `ObservationFullReadBudgetUnavailableError`. После reader failure один повтор читает тот же captured handle, пропускает confirmed prefix и умеет срезать частичный restart batch. Реальные повторные значения сохраняют разные observation IDs (`S01:1470–1591`).

Actual D2 consumer сохраняет shard, затем увеличивает counters. При ошибке он не возвращает completed output: `ObservationStagePartialError` несёт confirmed rows/shards/family counts, `status=incomplete` и `scratch_integrity=not_established`. Tracking сохраняет `failed`, пустые outputs и partial metrics; scratch остаётся диагностическим. Existing read API требует completed status и отвергает такой receipt до CAS publication (`S01:2004–2075`, `S05`, `S09`).

Таким образом, retained scratch не объявлен ни готовым panel, ни empirical authority. Обход read API прямым чтением временных файлов не является допустимым доказательством consumer capability. Полная successful D2 materialization/contract generation/CAS chain здесь source-traced, не исполнена.

## 4. Свежие проверки

1. **P01:** все12 existing OBS-02 bodies /18 parameterized cases вызваны unchanged. Каждый остановился на отсутствии PyArrow до deciding assertions. Это BLOCKED, не PASS/FAIL продукта. Пять вариантов отдельного orchestrator regression прочитаны, но native execution UNRUN.
2. **P02:** actual iterator/mapper/snapshot с4 вариантами retry batch sizes:2+2,3+1,1+3,4. Во всех случаях8 rows/8 unique IDs, одинаковые значения не удалены. Live source изменён с сохранением size/mtime; оба reader attempts получили прежний captured SHA256. Temporary handle после завершения закрыт.
3. **P03:** pre-yield OSError даёт typed budget refusal без full read; PermissionError/FileNotFoundError/ValueError не скрыты. Conversion и inter-metric mapper OSError не запускают retry. Слишком короткий restart относительно confirmed cursor отвергается. Между metrics первая частичная выдача остаётся диагностическим prefix, не completed generation.
4. **P04:** настоящий OS snapshot copy проверен на zero/negative/nonfinite/insufficient disk budget и zero free space до copy. Same-size mutation, growth и shrink отказаны до yield; temp handles закрыты. Consumer `close()` после первого frame освобождает snapshot. Это bounded controls, не concurrent disk stress/power-loss proof.
5. **P05:** actual complete D2 function и tracking method исполнены по двум failure routes. После recover-first-batch и terminal retry error сохранены4 distinct shard paths/8 unique rows, counts совпали; после inter-metric stop —1 shard/2 rows. Actual persisted BuildRunManifest имеет failed, outputs=[] и incomplete/not_established metrics, включая обе причины retry failure. Writer явно сохранял JSON fixture, не Parquet.
6. **P06:** actual whole read API отказал обоим persisted failed receipts до вызова store.put_bytes. Никакой native CAS write не имитировался успешным результатом.

## 5. Что сохранить и что осталось

**Сохранить:** snapshot-bound cursor, actual hash/size/disk admission, phase distinction, отказ от giant full-read, уникальность row-based IDs без value dedup, partial accounting и strict completed-status read gate. Не возвращать старый fallback ради availability и не превращать synthetic diagnostic rows в empirical evidence.

**C86-G01 — native chain.** В supported environment исполнить имеющиеся12 bodies/18 cases и5-variant orchestrator regression. Проверить real Parquet column/schema behavior, two-block/two-metric shards, merged panel IDs/counts, persisted final counters и content-bound CAS read. Shared LANE-07 test может обслуживать предыдущие UDF/OBS пакеты. Current JSON interface checks не заменяют этот результат; shared C83-R01 import limitation остаётся отдельным finding.

**C86-G02 — workload/lifecycle.** Проверить representative resource behavior, public rerun после retained incomplete scratch и применение completed receipts реальными consumers. Current code удаляет прежний shard directory при новом D2 run; это не аттестовано как вся lifecycle/concurrency semantics. Не удалять diagnostic scratch просто ради вида чистой папки и не объявлять его наличие authority leak: actual selected failed receipt и read refusal уже подтверждены. All historical outputs и внешние consumers не оценены.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C86_OBS02/commands.json) · [Diagnostics](../04_Проверки/C86_OBS02/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C86_OBS02/native_verification.json) · [Fixture formats](../04_Проверки/C86_OBS02/fixture_format_index.json) · [Остатки](../01_Реестры/C86_остатки.json).

Run03 exit0:6 MATCH,18 native cases BLOCKED,0 native PASS. Initial run01 syntax error внешнего probe сохранён; run02 пройден, run03 добавил actual read refusal. Test bodies и algorithms не переписаны; selected product nodes извлечены целиком unchanged AST. Core/builders initializers заменены shells; tracking self adapter опускает telemetry composition. JSON fixture files под actual .parquet naming явно перечислены, не выданы за Parquet.

Native ordinary import blocked в eager parent/Core Python3.14 syntax stack; pytest/PyArrow/DuckDB отсутствуют, supported baseline не достигнут. Полная native успешная цепь, production data, performance/scientific validity не заявлены. Checkout чист; source/tests/config/dependencies не менялись.

**86/127 рассмотрены ограниченно. Следующий — UDF-04. Фаза 2 не начата.**
