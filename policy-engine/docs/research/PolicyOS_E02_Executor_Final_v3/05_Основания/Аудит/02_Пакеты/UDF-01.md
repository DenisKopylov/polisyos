# UDF-01 — D4 governance handoff и явные builder contracts

## 1. Решение

**Ограниченно оценён, не закрыт.** Canonical D4 producer уже находится в `governance_handoff.py`; старый calibration адрес — узкий alias. D4 сохраняет filename, schema, required-stage mapping, четыре запрета downstream использования и `producer_handoff_ready`. Это полезный handoff, не забытая калибровка.

**C83-R01:** контракт-only import всё ещё запускает eager `builders/__init__` и unrelated siblings. Сам `contracts.py` выделен, но обещанная import isolation не достигнута. Severity low; время и память не измерялись.

Свежий результат: **6 bounded MATCH;3 selected unchanged bodies /3 cases PASS**. Producer/DTO/I/O/read API настоящие; storage в bounded chain — **fixture CAS**, Scientist — только actual request parser. Native full facade/CAS/selected-profile/governance execution не заявлены.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/UDF-01_исходные_строки.txt) · [Pinned sources](../05_Источники/C83_источники.json).

## 2. Матрица исходных IDs

| ID | Проверенный результат | Остаток |
|---|---|---|
| LA-030 | Реальный canonical owner, old alias, exact D4 bytes/hash/size/filename/schema и4 denials; registry source mapping обновлён | Native facade/orchestration/selected-profile chain G01; alias lifecycle G02 |
| LA-031, только текущая фаза | StageBuildResult в contracts, explicit D4 imports, incidental common symbol не протекает | R01 contract import coupling; OBS-01 и UDF-02 остаются отдельными фазами |
| LK10 | Реальные AssetDefinition/decorator/planner сохранены, прочитаны | Не исполнялись здесь; не объявлены пустышкой/распределённым executor |
| LK12 | Actual read API проверяет path/hash/size/status и сохраняет ограничения receipt | Fixture storage не закрывает native CAS/selected profile; нельзя обходить reader plain-file чтением |

Current `StageBuildResult` имеет полезный дополнительный `inputs` в конце и `validate_inputs()`. Первые5 positional fields сохранены, orchestrator повторно валидирует returned inputs и объединяет их с own source inputs. Это **отдельное current behavioural extension**, не утверждение, что класс остался буквально неизменным после переноса. Оно не классифицируется как дефект только потому, что исходный move просил не менять поля.

## 3. Реальная цепочка и её исполненная часть

Producer выбирает прежний `calibration/d4` output path, пишет тот же deterministic domain JSON через actual kernel atomic writer и создаёт настоящий `ArtifactRecord.from_path` с hash/size. Result содержит только readiness metric и request artifact, не governance verdict (`S01`, `S07`–`S13`). Старое имя директории/filename не меняется ради Python relocation.

`STAGE_BUILDERS` указывает на imported canonical `build_d4_stage`. Actual orchestrator вызывает builder, revalidates inputs, собирает outputs/findings/metrics и пишет completed/failed BuildRunManifest (`S04`, `S14`). **Эта orchestration activation прочитана, но не исполнена**: серверные guards не обходились.

Read API сначала validates completed exact stage, allowed root, unique output basenames, declared/recomputed hashes и sizes, required outputs; только после этого snapshot-ит exact bytes. Byte getter использует admitted reference, не повторно открывает producer path. Receipt ограничен producer identity/content binding, не governance/release (`S15`). Эти guards действительно исполнялись над собственными fixtures.

Current Scientist bridge читает D4 через `load_verified_stage_json_output(...).value_for_candidate()`, затем narrow request parser и separately проверяет D0/D2/D3 producer receipts (`S16`). В C83 выполнен parser и исторический existing byte-reader chain, **но не новый selected-profile route, не native CAS и не весь Scientist runner**.

## 4. Свежие проверки

1. **P01:** fresh native запрос `builders.contracts` фактически вошёл в `builders → bindings_validation → common` до загрузки contracts. Recorder лишь наблюдал native loader, возвращая None. Позднее import заблокирован Python3.14 syntax в Core store на доступном Python3.12. Этот environment blocker не объявлен product defect; eager dependency topology подтверждена отдельно.
2. **P02:**3 unchanged existing bodies PASS: exact expected bytes independent json.dumps, actual ArtifactRecord/hash/size/result fields; narrow namespaces; actual read API → fixture CAS → actual selected Scientist parser. Четвёртый facade identity body исключён, чтобы не считать fixture parent binding доказательством native activation.
3. **P03:** actual reader отвергает wrong stage, failed status, missing output, duplicate basename, wrong size и source hash без новых storage puts. После successful admission изменение source не меняет stored copy; tampered fixture bytes отвергаются getter. Это исполнение настоящих guards, не fake verifier, но storage backend не native Core.
4. **P04:** настоящий calibration alias тождественен canonical function до reload; incidental common symbol не появляется при reload handoff. STAGE_BUILDERS mapping проверен source-only. Full facade не объявлен выполненным.
5. **P05:** old5 positional constructor arguments работают; default lists независимы; new input type/empty hash/duplicate/overlap отказывают, post-return duplicate ловится повторным validate_inputs. Это metadata contract, не доказательство фактической source authority.
6. **P06:** actual narrow parser отвергает wrong schema, purpose, отсутствие governance denial, wrong required mapping и extra permission field. Positive producer содержит все4 denials. Parser не создаёт решения о governance или разрешения на публикацию.

## 5. Подтверждённый остаток и сохранение полезного

### C83-R01 — выделенный contract остаётся зависимым от eager sibling activation

**Low, high confidence.** Python загружает parent package перед submodule. `builders/__init__.py:7–24` eagerly импортирует bindings/common/demography/io/observation/sources/release. Уже первый sibling идёт в common и его NumPy/pandas/adapters stack. Следовательно, ordinary contract-only import не получает заявленной изоляции (`S04`–`S06`, native trace).

Минимальное направление: сделать существующую facade activation явной/ленивой, сохранив current aliases и registry mapping. В Ukraine domain уже есть lazy-export pattern (`S18`), новый global import framework не нужен. Fresh-process test должен отдельно доказать отсутствие unrelated builder imports и последующую правильную activation. Не удалять working scheduler, diagnostic bindings payload или real materialization planner ради меньшего числа импортов.

**Сохранить:** exact D4 artifact IDs/bytes/formatter/path/schema; producer readiness и4 denials; canonical owner/узкий old alias; actual hash record; read API guards; current input contract/revalidation. Не добавлять Foundry calibration или Scientist decision внутрь D4 producer ради исторического имени calibration.

## 6. Qualification gaps

**C83-G01:** supported native facade/orchestrator/CAS/selected-profile request chain с corruption/absence controls. Общий LANE-07 integration corpus может обслуживать несколько пакетов. Fixture CAS использует actual typed refs с synthetic profile token; это не доказательство Core custody, immutable publication, profile selection или governance admission. Real-data scientific validity здесь также не установлена.

**C83-G02:** class/alias lifecycle. Дополнительный inputs field и его consumer должны оставаться явно отделённым behavioural delta. External introspection/serialization/old callers не перечислены полностью; перед retirement alias нужна квалификация. LA-031 не закрыта: календарные helpers идут в OBS-01, остальной IO/bindings/facade — UDF-02.

## 7. Воспроизводимость

[Commands/exit/logs](../04_Проверки/C83_UDF01/commands.json) · [Diagnostics](../04_Проверки/C83_UDF01/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C83_UDF01/native_verification.json) · [Остатки](../01_Реестры/C83_остатки.json).

Bounded run01 exit0:6 MATCH,3/3 selected cases. Native models import PASS; contracts/manifests native imports BLOCKED на Core store syntax; native pytest отсутствует. Core/builders initializers заменены package shells только в bounded probe; actual producer/config/manifest/read API modules не заменены. Scientist function1648–1680 выбрана неизменённым AST; actual full runner UNRUN. Full native CAS вместо собственного fixture storage не утверждается.

Один intentional invalid JSON после tamper сохранён losslessly как .invalid-snapshot.bin с SHA map. Checkout чист; source/tests/config/dependencies не менялись, реальные серверы/datasets не использованы.

**83/127 рассмотрены ограниченно. Следующий — OBS-01. Фаза 2 не начата.**
