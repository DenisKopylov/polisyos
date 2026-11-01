# UDF-02 — IO и diagnostic bindings: native accountable closure LA-031

**LANE-07 · CP2 · LA-031 · preserve + native/consumer qualification + lifecycle.**

**Практическая цель:** Существующие stages сохраняют output meaning и форматы, а synthetic runtime seed действительно доходит до bindings consumer без ложной эмпирической authority.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/UDF-02.md) · [остатки C85](../05_Основания/Аудит/01_Реестры/C85_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/UDF-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Нового доказанного R нет; G02 не называется misuse, но требует реального положительного потребления.

## 2. Сохранить работающий смысл
- Canonical coherent owners
- Legacy JSON serializer и kernel atomic boundary
- Diagnostic warnings/synthetic purpose
- Sequential scheduler
- Narrow compatibility aliases и защищённые контракты

Защищённые различения: LK10, LK11, LK12. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C85-G01: qualify** → REQ-UDF-02-01. Native output profiles/activation, не повторный move.
- **C85-G02: qualify** → REQ-UDF-02-02, REQ-UDF-02-04. Actual consumer validation positive path и purpose; если missing wire, bounded repair of existing owner.
- **C85-G03: lifecycle** → REQ-UDF-02-03. Caller/aliases/phase closure и protected contracts; shared C83-R01 не дублировать.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-UDF-02-01
Выбранные native stage outputs должны сохранить доменные JSON bytes, NPZ arrays/metadata и Parquet semantic profile, errors/warnings и registry activation; JSON formatter не подменяется другой kernel JSON функцией.

**TEST-UDF-02-01 — native unit / integration; NOT_RUN.**
- Setup: Unicode/NumPy/date/Path/DTO fixtures, adjacency NPZ, real Parquet. Раздельные controlled failures: до successful replace (write/file fsync/replace refusal) и directory fsync после successful replace; собственный temp/target и наблюдаемая фаза отказа.
- Действие: Actual IO helpers и selected stage producer→manifest→native CAS reader.
- Точный oracle: JSON exact legacy bytes, NPZ arrays/nnz/hashsize, Parquet rows/schema/index=False. Отказ до успешного replace сохраняет prior file и удаляет собственный оставшийся temp. Если replace уже успешен, новые bytes видимы; ошибка directory fsync не доказывает durability и не обещает восстановление prior file; фаза/исход различимы в existing error/reporting evidence. No output PASS до reader.
- Doubles/границы: Real formats/CAS/atomic writer; compressed NPZ historical byte equivalence не выводить из decoded arrays.

### REQ-UDF-02-02
Synthetic runtime seed должен пройти actual selected-snapshot→Foundry bindings consumer с явным diagnostic purpose; consumer_required не считается выполненной validation. Valid synthetic input допускает полезный bounded consumer, но не становится empirical observations.

**TEST-UDF-02-02 — native unit / integration; NOT_RUN.**
- Setup: RuntimeBundleManifest с synthetic payload/selected DataSnapshotRef; actual D0→D3 tiny intake fixtures и Foundry contracts; bad profile/missing validation controls.
- Действие: load_ukraine_foundry_intake затем actual prepare/build_input_bindings и конкретный consumer; inspect receipt.
- Точный oracle: Real binding receipt связан с selected snapshot и source profile; diagnostic/synthetic meaning сохранён. Missing required contract/validation не accepted как empirical; valid fixture reaches consumer.
- Doubles/границы: No fake Foundry bindings/CAS; fixture data explicit, not empirical. Если связка отсутствует — implement narrow existing owner wiring, не закончить документацией consumer_required.

### REQ-UDF-02-03
Canonical IO/bindings owners, explicit imports и narrow aliases должны сохранять actual callers, sequential memory scheduler и protected materialize/academic shadow/readAPI. Shared import isolation owner UDF-01; LA031 closure собирает все 3 phases, не удаляет common по имени.

**TEST-UDF-02-03 — native unit / integration; NOT_RUN.**
- Setup: Census actual imports/callers, scheduler tasks/budget, academic read-only fixture и protected DAG controls.
- Действие: Fresh activation, alias identity, selected callers and scheduler; подтверждённые external serialization calls.
- Точный oracle: No wildcard/domain→tools; scheduler order/budget unchanged; aliases resolve one owner. Academic currentness/schema and read-only contract сохраняется. До retirement нет unqualified callers.
- Doubles/границы: Census не semantic proof всех stage bodies; DuckDB native only для read-only claim.

### REQ-UDF-02-04
Bindings diagnostics должны сохранять identity coverage/subset warnings, nonmutation и synthetic fallback distinctions; env-limited sample не выдаётся full population observation.

**TEST-UDF-02-04 — native unit / integration; NOT_RUN.**
- Setup: Absent/empty/nonempty procurement proxy; duplicated participants; bounded subset/env limits; empty runtime fixture.
- Действие: Actual _select_procurement_frame/_validation_subset/_build_synthetic_multiscale_payload.
- Точный oracle: Preferred nonempty proxy выбран; empty warning+required fallback; missing required refusal; source unchanged; synthetic payload не имеет observations/observation IDs; finite diagnostic serialization.
- Doubles/границы: Frame fixtures allowed для unit; native Parquet selection отдельно REQ01.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/ukraine/builders/io.py` уже выполняет sorted ASCII indent2 JSON → atomic_write_text; NPZ → atomic_write_bytes; Parquet frame.to_parquet(index=False). Characterize эти owners, не менять serializer ради унификации. `src/polisyos/data_forge/domains/ukraine/builders/bindings_validation.py` владеет subsets/identity coverage/synthetic payload; common.py всё ещё полезен scheduler/helpers.

В `src/polisyos/data_forge/domains/ukraine/builders/sources.py` D0 tail формирует fabric.synthetic_multiscale_payload, DataSnapshot с selected profile и RuntimeBundleManifest с input_bindings_artifact_id=None,validation=[],foundry_input_bindings=consumer_required. Это не готовая validation. Пройти existing `src/polisyos/foundry/data_plane/bindings.py::load_ukraine_foundry_intake` (D0–D3 receipts, typed contracts, selected snapshot), затем `prepare_input_bindings/build_input_bindings` по actual caller. При отсутствующей wiring подключить эту цепочку в существующем consumer; не добавлять producer self-certification. Required output — actual receipt/input basis и successful bounded method consumer плюс missing contract control. Не требовать эмпирической пригодности synthetic fixture.

LA031 accounted один раз UDF02: собрать UDF-01 contracts/lazy facade, OBS-01 calendar и текущие IO/bindings. Нет повода удалять работающие scheduler/materialize/shadow или readAPI.

## 6. Общая интеграция и порядок
**E02-I07-A**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- UDF-01 и OBS-01 prerequisites; UDF02 accountable LA-031
- Foundry binding owner co-review; OBS02 shared sources writer

Owners/callers: `src/polisyos/data_forge/domains/ukraine/builders/io.py`; `src/polisyos/data_forge/domains/ukraine/builders/bindings_validation.py`; `src/polisyos/data_forge/domains/ukraine/builders/common.py`; `src/polisyos/data_forge/domains/ukraine/builders/sources.py`; `src/polisyos/foundry/data_plane/bindings.py::load_ukraine_foundry_intake`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Original JSON/NPZ/Parquet/artifact IDs не rewrite. Intentional new validation/wiring отдельно equivalent moves. Unknown external aliases retained; rollback не включает wildcard и не объявляет synthetic empirical. Невалидная bindings ветка ограничивается, valid independent outputs сохраняются.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Новая semantics может потребовать общий binding adapter; проверенный typed contract, а не bespoke branch на каждый dataset. Не создавать universal model inventor и не запрещать diagnostic/candidate work из-за отсутствия empirical authority.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_udf_02.py`, `tests/unit/data_forge/domains/ukraine/test_builders.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
