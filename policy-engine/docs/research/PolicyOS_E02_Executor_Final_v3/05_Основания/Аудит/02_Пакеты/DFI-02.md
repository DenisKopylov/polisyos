# DFI-02 — canonical API cutover без обратной синхронизации globals

## 1. Решение

**Ограниченно оценён, LA-038 целиком не закрыт.** Canonical pipeline действительно направлен в `core_sources.api`, а не в legacy facade. Remaining leaves имеют конечные owner bindings; facade больше не раздаёт произвольные globals. Контролируемые concurrent A/B invocations сохраняют собственные substitutions и записывают раздельные manifests. Эти полезные изменения следует сохранить.

Свежий результат: **6 MATCH; 12 unchanged existing bodies / 12 cases PASS**. Обнаружены два low residuals: **empty_shards теряется на outer API merge** и **восстановление старого generated facade delegate после повторного lookup вызывает рекурсию**. Full native ingestion и profile/DB receipt chain не квалифицированы.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Полная карточка](../05_Источники/DFI-02_исходные_строки.txt) · [Pinned источники](../05_Источники/C94_источники.json).

## 2. Матрица исходных IDs

| ID | Подтверждено | Остаток |
|---|---|---|
| LA-038 / M, этап 2/2, accountable | Remaining finite dependency declarations, actual canonical caller, scoped facade, sync runner/context, controlled leases/budgets, persisted stage metrics | C94-R01/R02 и C94-G01; C93-G01 не погашен synthetic tests |
| LK19 | Fabric request/lease/profile boundaries остаются у existing owners; batch orchestration отделена | Полная network equivalence не проверена, transport ownership не переносится |

Предшествующий DFI-01 сохранён. Повторное LA-038 не увеличивает число уникальных IDs. Название accountable не означает автоматическое закрытие.

## 3. Producer → consumer

Registry строит ObservationPlan из фактического CatalogTransportDataset и alignment: сохраняет connector/profile/request ID, default filters, watermark/version, применяет source/preflight/confidence constraints и existing plan limiter. Transformer нормализует country filters, не выбрасывая прочие dimensions. API imports сохраняют существующие Fabric contracts/profile resolution и session-cache owners (`S01–S03`). Это разделение обязанностей, а не новый acquisition transport.

Actual pipeline function импортирует canonical API внутри invocation и переносит семь ingest counters в metrics. Public API scope → `_run_core_sources_ingest_stage` → internal ingest → actual checkpoint/receipt reconciliation → stage manifest → progress. При отсутствии допустимого output receipt итог **warning**, даже если отдельные counters положительные. При успешном внутреннем catalog ingest outer merge переносит многие поля, но пропускает empty_shards (`S01:867–1132`, `S05:1346–1561`).

Facade имеет explicit bindings, scoped snapshot и no-op `_sync_implementation_globals`. Default wrappers различаются по identity; таблица exemption хранит только последний wrapper каждого binding. Это убирает прежний broadcast, но оставляет узкий save/restore lifecycle residual. No-growth запись уже описывает explicit bounded bindings и scoped test overrides; её прежняя семантика про общий mutable namespace не сохранена (`S04`, `S19`).

## 4. Свежие различающие проверки

1. **P01:** пять existing bodies до legacy import: настоящий pipeline function потребляет existing fake-ingest seam и переносит семь counters; sequential owner substitutions FIRST→SECOND не затираются; canonical ILO filters сохраняют sex=T и переводят UA→UKR/REF_AREA; registry limiter и transport-source overrides имеют явный адрес. Config/alignment — явно fixture objects, не native constructors.
2. **P02:** семь existing bodies: отсутствие broadcast, scoped loader override, concurrent A/B full facade entrypoints, scalar substitution, API entrypoints и sync worker-thread context. Настоящий API stage writer сохраняет manifests с observations1 и2; выход A не снимает scope живого B. Whole actual common runner копирует context в worker. DB receipt здесь None fixture, поэтому stage manifests warning, а не доказательство публикации.
3. **P03:** complete AST remaining group: registry **21 proxies / 4 literal resolver calls**, transformers **3/10**, API **78/48**. Targets существуют, wildcard imports нет. Это структурный denominator, не полный semantic/native PASS всех шести leaves.
4. **P04 / R01:** actual outer merge получает typed inner stats `empty_shards=4`, `completed_shards=5`, `observations=6`. Возвращает empty=0 и записывает именно0 в настоящий stage JSON; другие два counters сохраняются. Source inner producer действительно увеличивает empty counter на complete_empty. Controlled result и DB seams синтетические, но потеря поля происходит в unchanged real merge и manifest consumer. Missing receipt остаётся warning.
5. **P05:** actual request и lease проходят bounded connector: handle/request identity сохранены, direct fetch сообщает12 bytes; async lease создаётся, сериализуется, poll завершается40 bytes; persisted lease повторно не отправляется. Budget резервирует5 slots, включая ошибочный fetch; ValueError не проглатывается. Trace records сохранены. Мы **не** объявляем внутренний request_count доказанно равным числу реальных HTTP calls: transport здесь fixture.
6. **P06 / R02:** текущий generated delegate можно восстановить и вызвать. Но save d1 → второй lookup d2 → restore attr=d1 → call приводит к RecursionError. После удаления restored attr и direct owner, и свежий facade снова работают. Это реальный механизм bounded compatibility surface, не наблюдавшийся production incident.

## 5. Остатки

**C94-R01 — low, высокая уверенность: потеря empty-shard metric.** [Outer merge](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/api.py#L1094-L1132) не переносит поле, которое [stage manifest](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/api.py#L969-L1009) публикует. Перенести existing counter через existing aggregate, проверить совместно с completed/failed/deferred и persisted consumer. Не менять смысл complete_empty и не ослаблять receipt guard. Потеря rows, checkpoint ledger и ложная publication authority не установлены; native частота неизвестна.

**C94-R02 — low, высокая уверенность: recency-dependent wrapper exemption.** [Facade scope и delegates](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py#L121-L183) принимают older generated wrapper за реальную substitution, и он получает себя как scoped target. Различать свои wrappers независимо от последнего lookup, сохранив актуального owner и легитимные developer overrides. Не исправлять это возвращением broadcast или безусловным кэшированием устаревшего owner. Regression: repeated lookup / saved restore / current restore / normal custom override / scoped cleanup. **Не утверждается**, что любой pytest monkeypatch restore ломается; такой production caller не найден, canonical pipeline этим facade не пользуется.

**C94-G01 — native совместная квалификация.** Один согласованный LANE-08 witness должен покрыть обе DFI-группы, DFK-02 rich filters, actual DatasetBatchConfig/profile snapshot, настоящую малую DB, successful/empty/error source results, leases/budgets/bytes/counters, current output receipt и fresh consumer. Existing architecture/no-growth checks также не запускались. Нынешние config/profile/DB/checkpoint seams не могут закрыть этот разрыв. Не строить новую платформу для отчётов или второй transport; расширить existing tests/owners.

**Сохранить:** finite dependency maps, canonical caller, actual owner lookup, ContextVar scope/reset, asynchronous isolation и sync bridge, DTO ownership, meaningful warning при missing receipt, реальный Fabric reuse, source filters и provenance. Полезная реализация уже есть; не откатывать её из-за двух локальных остатков. Typed metadata и synthetic rows не являются научной авторитетностью.

## 6. Воспроизводимость

[Команды / exit / logs](../04_Проверки/C94_DFI02/commands.json) · [Diagnostics](../04_Проверки/C94_DFI02/bounded_diagnostics.json) · [Empty-counter trace](../04_Проверки/C94_DFI02/run04/empty_counter_trace.json) · [Budget/lease trace](../04_Проверки/C94_DFI02/run04/budget_lease_trace.json) · [AST census](../04_Проверки/C94_DFI02/run04/remaining_group_AST_inventory.json) · [Native status](../04_Проверки/C94_DFI02/native_verification.json) · [Границы](../04_Проверки/C94_DFI02/Чтение_и_границы.md) · [Остатки](../01_Реестры/C94_остатки.json).

Run04 exit0, 6 MATCH / 12 PASS. Run01 blocked whole-file syntax и run02 наша off-by-one extraction error сохранены. Run03 уже имел те же12 PASS; повторные cases не суммируются. Whole facade/contracts/common runner/kernel writers и selected API/pipeline bodies настоящие; config/alignment/profile/DB/checkpoint/connector/result fixtures перечислены отдельно. Native API import BLOCKED на Core store:2118; pytest/DuckDB отсутствуют. PEP695 поддерживается и реально исполнен. Полный ingest scheduler, network, published receipt/currentness и scientific validation — UNRUN. Checkout не менялся.

**94/127 рассмотрены ограниченно; 202 уникальных B/LA. Следующий — EMB-01. Фаза 2 не начата.**
