# UDF-02 — доменный I/O, bindings diagnostics и явные exports

## 1. Решение

**Ограниченно оценён, не закрыт. Новый подтверждённый product defect не установлен.** Связные canonical owners `io.py` и `bindings_validation.py` действительно отделены; старый широкий wildcard namespace заменён явными imports и узкими compatibility aliases. JSON сохраняет прежний serializer поверх настоящего kernel atomic writer; scheduler намеренно последовательный.

Свежий результат: **5 bounded MATCH; 10 unchanged test bodies PASS; 2 Parquet bodies BLOCKED**. Full facade alias body не выполнялся. Actual whole I/O/common/bindings modules исполнены за двумя initializer shells; это не native full stage/CAS qualification. Shared **C83-R01** остаётся, не размножается новым finding.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/UDF-02_исходные_строки.txt) · [Pinned sources](../05_Источники/C85_источники.json).

## 2. Матрица исходных IDs

| ID | Проверенный результат | Остаток |
|---|---|---|
| LA-031, UDF-02 accountable phase | Coherent I/O/bindings owners; explicit imports в12 builder files;28 actual common aliases; bounded serialization/warnings/synthetic/scheduler preservation | G01 native activation/output profiles; G02 consumer validation/purpose; G03 lifecycle и shared C83-R01 |
| LK10 | Настоящие asset binding и dependency planner сохранены | Source-only в этом пакете; не distributed executor |
| LK11 | Academic loader проверяет schema/currentness; SKG читает DuckDB read-only | Native DuckDB UNRUN; не удалять по имени shadow |
| LK12 | Content-bound read API и purpose ограничения сохраняются | Plain-file diagnostics не считаются admitted receipts |

Accountable closure не означает автоматическое закрытие LA-031: UDF-01 и OBS-01 обязательны и содержат собственные остатки. LA-031 учитывается один раз в unique-ID count, прежние phase assessments сохранены в истории. Это current-state audit, не доказательство отдельных исторических move/fix commits.

## 3. Actual producer → consumer

`io.py` сохраняет sorted ASCII JSON с indent2 и прежним conversion для NumPy/date/Path/Pydantic. Готовый текст передаётся `atomic_write_text`, NPZ bytes — `atomic_write_bytes`; `ArtifactRecord` вычисляет настоящий hash/size. Parquet по-прежнему пишет frame без index. Выбор procurement source сохраняет preferred nonempty proxy, предупреждение об empty proxy и fallback к required Prozorro (`S01`, `S13`, `S14`). Не заменять serializer другой kernel JSON функцией, у которой иной byte profile.

`bindings_validation.py` владеет identity/coverage diagnostics, env-limited subsets и synthetic multiscale payload. Actual D0 caller переносит sampling warnings, освобождает тяжёлые frames, формирует synthetic payload и сохраняет его с kind `fabric.synthetic_multiscale_payload`. Snapshot сохраняет lineage и selected-profile requirement. Runtime bundle явно имеет `input_bindings_artifact_id=None`, `validation=[]` и `foundry_input_bindings="consumer_required"` (`S02`, `S04:676–764`).

**Это полезный diagnostic runtime seed, не уже выполненная Foundry bindings validation и не empirical observation.** Current source отличается от старого описания caller: consumer обязан выполнить нужную проверку позже. Downstream misuse не доказано; не превращаем synthetic fallback в обвинение в подмене данных, но и не объявляем полноценную consumer capability на основании наличия payload.

`common.py` не пустой остаток: здесь остаются scheduler, graph/numeric helpers и narrow lazy aliases. `__all__` больше не экспортирует всё подряд. Реальные sources/release/demography imports явны; facade registry mapping сохранён. Eager parent activation из C83 не исчезает только потому, что wildcard удалён (`S03`–`S12`).

## 4. Свежие проверки

1. **P01:** 4 selected UDF-02 regression bodies PASS: exact JSON bytes, NPZ arrays/nnz, atomic error propagation, synthetic-only shape. Ещё6 existing bodies PASS: scheduler order/budget, normalized identity lookup, unique participant coverage, subset warnings и huge-metric sanitization. Два Parquet bodies действительно попытались выполнить `to_parquet`, но BLOCKED до assertions: отсутствуют PyArrow/fastparquet. Один full facade alias body сознательно UNRUN.
2. **P02:** все14 I/O и14 bindings aliases настоящего common указывают на actual canonical functions; неизвестные имена отвергаются. AST census всех12 builder files не обнаружил wildcard или tools imports. Полный denominator и hashes сохранены. Это topology check, не blanket semantic closure всех stage bodies и не import-budget measurement.
3. **P03:** complex JSON fixture с Unicode, NumPy, dates, Path и DTO совпал с независимым ожидаемым legacy JSON. Actual ArtifactRecord hash/size проверены. Инъекции fsync до replace и replace error оставляют прежний target и не оставляют temp files. Actual adjacency NPZ возвращает ожидаемые arrays/nnz/hash. Power-loss и историческая compressed-byte equivalence не проверялись.
4. **P04:** actual source-selection функции за явно заменённым frame reader проверены на absent/empty/nonempty proxy, точные warnings, selected columns и required-missing refusal. Это не успешный native Parquet test; отдельные blocked existing bodies не переклассифицированы в PASS.
5. **P05:** actual subset/synthetic functions сохраняют input, sampling warnings и конечный сериализуемый diagnostic payload; empty input даёт synthetic fallback. Payload не содержит observations/observation IDs. Это не доказательство научной пригодности придуманных age/income/employer значений.

## 5. Сохранить и доработать

**Сохранить:** предметные owners, старые JSON bytes, kernel atomic boundary, hash/size metadata, явные imports, narrow aliases, diagnostic warnings/synthetic distinction и последовательный scheduler. Не удалять common целиком и не вводить domain→tools dependency. Полезные materialize, academic shadow и content-bound read API остаются защищёнными контрактами.

**C85-G01 — native closure.** В supported environment проверить whole facade/registry/stage callers с real Parquet и CAS, выбранные stage output profiles и негативные сценарии. Использовать общий LANE-07 integration для UDF-01/OBS-01/UDF-02/OBS-02, а не отдельную тяжёлую инфраструктуру на каждый пакет. Shared C83-R01 — один import-isolation остаток.

**C85-G02 — purpose и consumer activation.** Проследить actual consumer runtime bundle до требуемой bindings validation и receipt. Сохранить различие synthetic diagnostic seed и empirical observations. Здесь producer tail прочитан, а producer/CAS/Foundry consumer целиком не исполнялись. Не доказаны ни нарушение authority, ни полная activation.

**C85-G03 — compatibility lifecycle.** Проверить подтверждённые callers прежде снятия private aliases; учесть UDF-01/OBS-01 остатки.12-file import census не оправдывает удаление непрочитанных stage algorithms. Сохранить StageBuildResult inputs extension и полезные защищённые контракты; текущий перенос не требует восстановления широкого wildcard или удаления новой validation.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C85_UDF02/commands.json) · [Diagnostics](../04_Проверки/C85_UDF02/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C85_UDF02/native_verification.json) · [Остатки](../01_Реестры/C85_остатки.json).

Run04 exit0:5 MATCH,10 PASS,2 BLOCKED. Run01/02 содержат ошибки внешнего harness, run03 — неполную собственную cell fixture; все исходные scripts/logs сохранены. Исправлялись только внешние fixture/harness, не repository. Повторные runs не увеличивают число тестов.

Whole actual modules за Core artifacts/builders shells; CAS sentinel запрещает исполнение. Native ordinary import снова blocked на parent/Core Python3.14 syntax в Python3.12. Native pytest/Parquet/DuckDB отсутствуют; Pydantic также вне declared project range. Ни full stage/native CAS, ни power-loss, ни import RSS/latency, ни реальные datasets не измерены. Lack of dependencies не product defect.

Checkout чист; source/tests/config/dependencies не менялись. Полное закрытие LA-031 и scientific validity не заявлены.

**85/127 рассмотрены ограниченно. Следующий — OBS-02. Фаза 2 не начата.**
