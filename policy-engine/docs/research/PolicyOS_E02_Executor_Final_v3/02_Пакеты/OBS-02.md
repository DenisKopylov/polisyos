# OBS-02 — Native resume и lifecycle незавершённой D2 generation

**LANE-07 · CP2 · B147 · preserve + native/lifecycle qualification.**

**Практическая цель:** Полезная observation generation не теряет и не дублирует наблюдения после reader failure; partial результаты учитываются честно и не публикуются как completed.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/OBS-02.md) · [остатки C86](../05_Основания/Аудит/01_Реестры/C86_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/OBS-02_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. Новый defect не установлен. 18 исторических cases BLOCKED, не native PASS.

## 2. Сохранить работающий смысл
- Captured immutable snapshot и disk/hash admission
- Phase-aware retry/refusal
- No unbounded full read
- Equal values preserved with row IDs
- Incomplete counters и completed receipt gate

Защищённые различения: LK12. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C86-G01: qualify** → REQ-OBS-02-01, REQ-OBS-02-02. Настоящий Arrow/DuckDB/CAS success и failure chain вместо JSON интерфейсных fixtures.
- **C86-G02: lifecycle** → REQ-OBS-02-03. Bounded resource/public-rerun квалификация, retained scratch не объявляется authority leak.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-OBS-02-01
Observation reader должен повторять чтение только того же captured snapshot с confirmed cursor; valid retry не повторяет префикс и не удаляет равные значения. Conversion/mapper/permission failures не должны переключаться в reader fallback; unbounded full read до первого yield запрещён.

**TEST-OBS-02-01 — native unit / integration; NOT_RUN.**
- Setup: Real Parquet, два blocks и две metrics; failure после блока, до первого yield, между metrics; restart batches2+2/3+1/1+3/4.
- Действие: Actual _iter_observation_metric_frames через D2 consumer; изменить live source при сохранённых size/mtime.
- Точный oracle: Успешный retry даёт один полный набор row-based observation IDs и исходные значения, captured digest один. Semantic/inter-metric failure заканчивает generation incomplete, не повторяет partial prefix как completed. Preyield refusal typed; no giant read.
- Doubles/границы: Разрешён injected reader fault над настоящим Arrow reader; не JSON-backed .parquet и не mapper copy.

### REQ-OBS-02-02
Successful native D2 materialization должна согласовать shards, merged panel IDs/rows, final counters и completed selected-profile receipt. Terminal failure сохраняет confirmed partial counters, failed outputs=[] и read API refusal; scratch не authoritative output.

**TEST-OBS-02-02 — native unit / integration; NOT_RUN.**
- Setup: Tiny Arrow/DuckDB source, actual shard writer/merge/orchestrator/native CAS; terminal retry и mapper failures.
- Действие: Пройти stage tracking→persisted manifest→read API; fresh reader успешной generation.
- Точный oracle: Success expected rows/IDs/counts одинаковы во всех слоях; failure counts равны реально записанным shards, incomplete/not_established, no CAS publication по failed receipt.
- Doubles/границы: Настоящие форматы/merge/CAS; нельзя остановиться capture sentinel до successful downstream.

### REQ-OBS-02-03
Disk-backed snapshot должен сохранять size/hash/resource admission и release handles при completion/cancel. Public rerun после incomplete scratch не смешивает generations и даёт либо полный новый result, либо честный новый failure.

**TEST-OBS-02-03 — native unit / integration; NOT_RUN.**
- Setup: Controlled corpus с заявленным размером и budget; disk hint0/NaN/insufficient, growth/shrink/same-size mutation; retained failed scratch.
- Действие: Snapshot capture/consumer close, затем actual public D2 rerun в отдельной идентифицированной попытке.
- Точный oracle: Invalid admission до yield; handles закрыты; bounded copy не превышает исходный size. Rerun consumer использует новый completed receipt, не остаточные shards; forensic предыдущего failure сохранён в evidence до штатного cleanup.
- Doubles/границы: Не production disk exhaustion/powerloss. Workload scope/peak/disk metrics предъявить; одно tiny fixture не universal scale proof.

### REQ-OBS-02-04
Shared facade activation должна потреблять единственный C83-R01 fix UDF-01; content-bound read API и календарная OBS-01 семантика остаются на actual пути OBS-02.

**TEST-OBS-02-04 — native unit / integration; NOT_RUN.**
- Setup: Общий E02-I07-A native fixture, reordered periods и explicit stage activation.
- Действие: Запустить reader и selected consumer без package shells.
- Точный oracle: Shared import evidence использовано один раз; calendar/receipt semantics preserved, ordinary valid rows доходят до consumer.
- Doubles/границы: Не создавать второй import framework или второй read API.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/ukraine/builders/sources.py::_verified_observation_snapshot` уже копирует initial-size bytes во временный file, проверяет disk/free-space reserve и hash; `_iter_observation_metric_frames` уже различает reader/conversion/mapper и retry по тому же handle. Реализованный cursor учитывает confirmed row_offset и emitted_metric_ids; не возвращать исторический full-read fallback. Исполнитель сначала квалифицирует current code, меняет только воспроизведённое несоответствие.

`build_d2_stage` сохраняет shard до изменения counters; `ObservationStagePartialError` и orchestrator tracking фиксируют incomplete/failed. Для успеха проверить настоящее Parquet→DuckDB merge→manifest→`src/polisyos/data_forge/read_api/ukraine.py`→fresh consumer, не только negative receipt gate. Для failure сохранять обе причины retry failure и confirmed rows/shards/families. При public rerun учитывать existing удаление shard directory: сначала сохранить diagnostic evidence предыдущей attempt, затем проверить actual run identity и отсутствие смешения. Не вводить distributed generation service ради локальной квалификации.

Existing `tests/unit/remediation/test_obs_02.py` и `tests/unit/data_forge/domains/ukraine/test_orchestrator.py` содержат native tests, которые в аудите BLOCKED до assertions. Исполнить их в supported environment, не считать прежний BLOCKED продуктовым FAIL.

## 6. Общая интеграция и порядок
**E02-I07-A**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- UDF-02 predecessor; UDF-01 shared import fix; OBS-01 periods
- Один writer sources.py; общий E02-I07-A

Owners/callers: `src/polisyos/data_forge/domains/ukraine/builders/sources.py::_verified_observation_snapshot`; `src/polisyos/data_forge/domains/ukraine/builders/sources.py::_iter_observation_metric_frames`; `src/polisyos/data_forge/domains/ukraine/builders/sources.py::build_d2_stage`; `src/polisyos/data_forge/domains/ukraine/orchestrator.py`; `src/polisyos/data_forge/read_api/ukraine.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Historical failed receipts остаются failed; scratch не превращается в output и не удаляется только для зелёного вида. Новый run даёт собственный manifest. Rollback не включает duplicate-prefix fallback; допустим честный typed stop affected generation с сохранением остальных completed результатов.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Resume — общий snapshot/cursor механизм, не branch по source ID. На semantic failure допустима честная отмена affected generation; требование полезного positive path не означает скрыть ошибки или изобрести данные.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_obs_02.py`, `tests/unit/data_forge/domains/ukraine/test_orchestrator.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
