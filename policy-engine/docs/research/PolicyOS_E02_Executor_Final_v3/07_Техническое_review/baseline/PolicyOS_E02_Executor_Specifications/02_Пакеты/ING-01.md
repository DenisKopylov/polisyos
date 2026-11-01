# ING-01 — Согласованные cursor progress и replay namespaces

**LANE-08 · CP2 · B79, B80, B88 · fix + native end-to-end qualification.**

**Практическая цель:** Полезная инкрементальная загрузка и дешёвое воспроизведение сохраняют точный состав и происхождение данных каждого источника.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/ING-01.md) · [остатки C99](../05_Основания/Аудит/01_Реестры/C99_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/ING-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 bounded multi-namespace completeness; no observed unauthorized network action. B79/B80 original defects superseded by current source-owned path.

## 2. Сохранить работающий смысл
- Joint cursor intake and advancement
- Typed/dict manifest normalization
- Whole finite source owner
- Persisted request/payload/provenance reconciliation
- Source-time not local-now watermark
- Conditional cursor predecessor
- Empty delta materializes whole source
- Partial evidence without complete snapshot
- Replay no ordinary/live fallback

Защищённые различения: исходные positive/negative boundaries выше. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C99-R01: fix** → REQ-ING-01-01. Deterministic declared namespace dispatch, early ambiguity refusal, no live fallback.
- **C99-G01: qualify** → REQ-ING-01-02, REQ-ING-01-03, REQ-ING-01-04. Whole native cursor/ingestion/replay provenance and useful finite source path.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-ING-01-01
Replay должен поддержать однозначный declared per-source session layout либо отказать неоднозначному layout до ingestion. Фикстура выбирается по exact canonical request identity и declared namespace, не поиском похожего ответа.

**TEST-ING-01-01 — native unit / integration; NOT_RUN.**
- Setup: Session с двумя namespaces и разными requests, individual controls; одинаковый request hash в двух namespaces; unknown manifest pair, missing/corrupt fixture.
- Действие: Actual run_replay_mode→APISimulator→persisted evidence; guard native egress и ordinary delegate.
- Точный oracle: Два однозначных requests дают свои recorded bytes; ambiguity отказывает до частичного исполнения; missing/corrupt не вызывает live/ordinary fallback. Mode/provenance replay остаются правдивыми.
- Doubles/границы: Не утверждать, что вся текущая record→replay пара сломана: current record маркирует первым namespace.

### REQ-ING-01-02
B79+B80 должны пройти native совместную цепочку approved cursor→actual fetch request→raw/transformed/PII payload→persisted graph/evidence→conditional promotion→fresh consumer.

**TEST-ING-01-02 — native unit / integration; NOT_RUN.**
- Setup: Finite actual source A8→A9 и failed B, typed/dict manifest, same dataset name у разных connectors, actual CAS/tenant/profile.
- Действие: Full batch incremental дважды, fresh CursorStore и downstream source collection/snapshot.
- Точный oracle: Только A продвигается; B unchanged; actual request versions None→8→9; empty delta материализует весь current A; partial evidence без complete snapshot.
- Doubles/границы: Source owner reader и ingestion delegate не подменять fixture для acceptance; fixture source остаётся declared replay/synthetic, не live authority.

### REQ-ING-01-03
Retained cursor требует полный current source proof и exact persisted request/payload/provenance; source time не local now, CAS write предшествует conditional index update.

**TEST-ING-01-03 — native unit / integration; NOT_RUN.**
- Setup: Удаление каждого proof member, wrong source/schema/partition, delayed source timestamp, save failure, stale predecessor; valid current control.
- Действие: Reopen/admit/fetch/promote actual owners.
- Точный oracle: Недостаточный legacy cursor full-fetch-only; source time сохранён; failed write и stale predecessor не продвигают index; valid complete proof допускает полезный incremental fetch.
- Doubles/границы: Не доверять completeness/header/version self-report или payload-hash как source identity.

### REQ-ING-01-04
Native replay success должен сохранить реальные produced provenance и served outcome; новая production source capability добавляется bounded adapter к existing owner-reader contract, не автоматически из finite fixture.

**TEST-ING-01-04 — native unit / integration; NOT_RUN.**
- Setup: Existing served catalog→HTTP→replay integration corpus и actual CAS; finite file I/O counters.
- Действие: Run existing full oracle и fresh evidence reader; сравнить actual source bytes/read count/outputs.
- Точный oracle: Recorded bytes и request binding прослеживаются до consumer; I/O savings заявляются только измеренные в конкретном source scope. Rights/currentness not_established явно не скрыты.
- Doubles/границы: Не требовать универсального deterministic inventor; source-specific owner extension только по реальной потребности и доказуемому contract.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/fabric/data_plane/modes.py::run_replay_mode` сейчас задаёт APISimulator первым dataset, тогда как `src/polisyos/fabric/data_plane/replay_store.py::ReplayStore.build_replay_fixture_dir` пишет каждый declared namespace. В existing replay intake построить конечную immutable dispatch map из загруженного RecordSession и допустимых manifest pairs: exact request_hash → единственный (connector_id,dataset_id). Повторный hash в разных namespaces — explicit unsupported ambiguity до запуска ingestion, даже если payload похож. Не искать по filesystem и не выбирать first match. Это выбранный bounded contract, не универсальная маршрутизация identical HTTP requests между источниками.

Добавить небольшой optional namespace resolver в existing `src/polisyos/fabric/connectors/testing/simulator.py::_fixture_path/_handle_request`, питаемый этой map. Single-namespace default совместим; current actual request hash вычисляется существующим canonicalizer и разрешается только в pre-admitted map. Unknown key остаётся MissingFixtureError. Для будущей поддержки одинаковых requests разных sources понадобится explicit request-scoped source identity на actual fetch boundary, не угадывание URL; здесь ambiguity честно отказана заранее.

B79/B80 existing `src/polisyos/fabric/ingestion/source_progress.py`, modes и CursorStore уже связаны. Native qualification использует actual `src/polisyos/fabric/ingestion/ingestion.py` cache/transform/PII/raw/persisted sinks и fresh consumers, не новую cursor service. Historical first-namespace record format отдельно квалифицируется; не переписывать старые recorded bytes под старым ID.

## 6. Общая интеграция и порядок
**E02-I08-C**, [канонический LANE-08](../03_Интеграция/LANE-08.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- ING-02 jointly preserves frontier; ING-03 schema/identity; E02-I08-C
- NET-01 lifecycle and NET-02 transport owners remain separate

Owners/callers: `src/polisyos/fabric/data_plane/modes.py`; `src/polisyos/fabric/data_plane/replay_store.py`; `src/polisyos/fabric/connectors/testing/simulator.py`; `src/polisyos/fabric/ingestion/source_progress.py`; `src/polisyos/fabric/ingestion/ingestion.py`; `src/polisyos/fabric/data_plane/cursor_store.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Legacy cursors без доказательства не становятся hints. Existing single-namespace sessions читаются как прежде; новая ambiguous session отказывает до side effects. Версия session меняется только если wire fields действительно расширены. Rollback не возвращает ordinary/live retry.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Один request/owner contract допускает реальные новые source adapters без branch в orchestration. Finite fixture — полезный bounded режим, но production source completeness требует собственного проверяемого owner, не универсального изобретателя семантики.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/fabric/data_plane/test_record_replay.py`, `tests/unit/fabric/data_plane/test_incremental.py`, `tests/unit/fabric/data_plane/test_cursor_source_admission.py`, `tests/unit/fabric/data_plane/test_e02_c_streaming_oracle.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
