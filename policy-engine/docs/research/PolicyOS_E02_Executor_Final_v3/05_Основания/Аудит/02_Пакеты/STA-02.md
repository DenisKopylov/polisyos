# STA-02 — точные основания reuse и пригодность bundle
## C62 · 1 ноября 2026 года

**Порядок:** 62/127, LANE-06. **Исходные ID:** B60, B61, B62. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий проход после внешнего сохранения C61, не восстановление утраченной старой аттестации.

## Решение

Исходный `exists → ok` существенно ограничен: actual loader/matcher проверяет контекст, domain, покрытие параметров, selected graph/profile и source binding. Source owner связывает key с полными bytes и удерживает тот же reader для работы. Actual key v2 сохраняет presence/null и не объединяет все falsy значения.

**9 bounded MATCH; 4 unchanged test bodies PASS изолированно. C62-R01:** в оставшемся source-unbound compatibility shortcut пригодный bundle возвращается без обновления зависимого runtime payload. Корректный новый key для128draws/seed9 всё равно получает прежние32draws; imported bundle без derived fields также даёт ok. Native CAS/DuckDB/WorkflowExecutor остаются UNRUN. Это не обвинение selected source-bound route.

## 1. Матрица исходных ID

| ID | Требование | Свежая проверка | Остаток |
|---|---|---|---|
| B60 | Bundle как проверенный кандидат, а не имя ссылки | P01 changed context/domain/required/graph/profile и missing loader отказаны; P07 source join | R01 runtime outputs; G01 native custody; G02 scientific applicability |
| B61 | Key и actual read привязаны к той же версии | P08 actual prepare/hash/tracker/key; changed bytes различены, stable reusable; P09 mutation/WAL отказаны | G01 real DuckDB/CAS/executor; G02 measured I/O |
| B62 | Missing/null/false/zero/list по consumer contract | P05 actual canonical key v2:5 разных; nested missing не leaf-null; P06 только known gate default | G01 native cache corpus |

Карточка7366–7479 прочитана полностью; proposed `test_sta_02.py` не подменяет actual existing tests.

## 2. Bundle applicability и custody — разные уровни

Один `_bundle_matches_request` обслуживает internal reuse и external cache validation. Сначала вызываются typed bundle loader и manifest reader. Проверяются kind/schema, версии1.0/1.1/1.2; для active request нужны target/required/graph, exact context/domain, покрытие requested names через parameters или явно unsupported, graph role и exact manifest profile. Optional cross-profile absence тоже хранится и сравнивается; same payload ID не означает same selected profile. [S01:179–209](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py#L179-L209) [S01:480–613](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py#L480-L613)

**P01:** same V1.1 request принят; changed context, domain, required delta, graph ID, graph manifest profile и optional profile отказаны. Missing bundle loader отказан, а не превращён в ok по наличию ref. Использованы actual DTO/matcher, но store/manifest/profile resolver — явные fixtures. Полный native owner имеет дополнительно representation admission и lineage; он прочитан, но fixture не подтверждает его custody. [S08:381–435](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/parameters.py#L381-L435)

**P07:** actual V1.2 binding принимает совпавшие descriptor/digest/schema/query/version; иной digest/query/schema, failed generation и иной selected descriptor profile отказаны. Даже historical no-request path не обходит выбранный source. Native source-bound route получает тот же prepared reader, проверяет generation/version до и после selection, удерживает retained descriptor и создаёт V1.2 с source role. Это полезная связка, которую нельзя удалять ради возврата старого безусловного reuse. [S01:303–410](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py#L303-L410) [S01:512–552](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py#L512-L552)

**P02:** четыре unchanged existing skip bodies действительно выполнены с real state/context/outcome и fixture execution context. Existing CAS same-request/changed-domain/graph-profile tests прочитаны, но не заявлены пройденными.

## 3. C62-R01: пригодность bundle не гарантирует актуальность его производных outputs

State reads уже включают `phase15_runtime_backend/draws/seed`. Однако source-unbound reuse возвращает исходный state до ParameterTransfer. Bundle содержит selected parameters/applicability, но не binding runtime draws/seed и не обязательные state outputs. Проверка bundle не заменяет материализацию его нынешнего numerical payload. [S01:85–108](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py#L85-L108) [S01:232–254](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py#L232-L254) [S01:419–443](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py#L419-L443)

**P03:** actual V1.1 bundle beta=2,std_error=.2, target/domain/graph совпадают; нет configured SKG path, selected snapshot или prepared read. Actual NumPy ParameterTransfer создаёт32draws/seed1. Затем request меняется на128draws/seed9. Actual canonical keys различны, но actual ResolveParameters.execute возвращает **ok, тот же state,0bridge calls**, interval всё ещё содержит32draws. Прямой вызов того же actual bridge с текущими params даёт128draws и иные mean/CI. Старый runtime payload не стал допустимым из-за верного bundle.

**P04:** тот же допустимый bundle, но без `literature_priors`/`phase15_runtime_ready` в state: shortcut опять ok, outputs отсутствуют, хотя direct bridge ready=True. Это одна и та же bounded проблема materialization, не второй независимый дефект.

**Severity medium, confidence high bounded.** Store и manifest в этой пробе fixtures; настоящий CAS и downstream invocation не выполнены. Source-bound live/retained branch не попадает в данный shortcut. Не утверждается неправильная production policy, потеря evidence bytes или invalid scientific prior.

Минимальное направление — разделить reuse выбранного bundle и derivation runtime fields: существующий ParameterTransfer должен материализовать/валидировать outputs для текущих backend/draws/seed. Не нужно заново вызывать дорогой selector или удалять исторический bundle; unchanged request может сохранять полезный reuse.

## 4. B61: одна source identity до key и до потребления

Actual prepare_read требует стабильный файл без WAL, вычисляет полный SHA256, сверяет file identity до/после, открывает read-only transaction, снова проверяет identity и оставляет connection у query. PreparedSKGRead.cache_binding содержит source-binding schema, query version, selector version, source ref и digest; не весь ExperimentState. [S05:132–184](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_query.py#L132-L184) [S05:445–526](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_query.py#L445-L526) [S05:3286–3360](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_query.py#L3286-L3360)

**P08:** actual prepare/hash/stat/tracked connection/cache binding bodies исполняются над controlled temporary bytes; DuckDB connection/rows явно stub. По одному пути version-one→version-two сохраняет логическое имяref, но меняет digest и actual key. Следующее чтение неизменённых bytes даёт тот же digest/key. Actual query tracker использует тот же connection object, один SELECT создаёт один fingerprint; close дважды закрывает underlying connection один раз. **P09:** изменение bytes во время BEGIN отказано и connection закрыт; WAL отказан до admission. Это проверка owner plumbing, **не транзакционная проверка настоящего DuckDB**.

Source-only executor готовит read до key, кладёт binding в bind_params и тот же объект в node context; ExitStack владеет close. Если live generation успела смениться, он rebind один раз и отключает старый key; selected retained replay не переводится молча на live fallback. Retained source materializer проверяет descriptor/member/hash/size и не объявляет один source path immutable authority. [S03:1241–1395](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/executor.py#L1241-L1395) [S04:193–394](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/skg_snapshot.py#L193-L394)

Полный existing native regression читает реальную базу1.25, заменяет bytes по тому же пути на9.75, затем создаёт unrelated database. Он требует changed→newkey/value, stable→hit, same prepared reader и exactly-once close. Тест прочитан полностью, но **UNRUN**, так как pytest/DuckDB отсутствуют. Наш row stub не заменяет его acceptance. [S16:1441–1675](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py#L1441-L1675)

Full-file hash здесь сознательно проверяет file-owned boundary. Не измерено, насколько повторное hashing/materialization дорого при retained owner-ref; это G02 performance qualification, не доказанный функциональный дефект. Ослаблять verification до mtime ради скорости нельзя.

## 5. B62: presence и effective default

Actual `_MISSING` отличен от None, snapshot явно кодирует presence. Contract version2.0 входит в canonical key. **P05:** missing,null,0,false,[] дают **5 разных ключей** настоящими serializer/canonical functions; missing intermediate и missing leaf совпадают как отсутствие читаемого leaf, но leaf-null отличается. [S02:51–65](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L51-L65) [S02:239–331](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L239-L331)

**P06:** только exact DataPlaneGate node ID и `params.tenant_tier` нормализуют missing в shared, что соответствует реальному consumer `get(...,"shared")`. Другой node сохраняет различие; null,0,false,[] не сливаются. В пробе использован actual NodeSpec с fixture metadata ID, не весь native gate. Historical cache proof/version qualification C61 не переаттестовывается C62. [S19:84–113](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py#L84-L113) [S19:179–190](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py#L179-L190)

## 6. Producer → consumer и границы содержательной способности

ParameterTransfer принимает typed bundle, переносит scalar mean, std/CI и applicability multiplier в literature_priors/runtime intervals. SCMFitData принимает этот explicit payload; causal engine builder переносит поле, когда оно передано. Manual fit различает data/hybrid/literature/default, а selected GCM прямо отказывает literature-prior fitting. Поэтому наличие bridge не доказывает автоматическое Scientist-state→fit wiring или универсальную переносимость priors. [S12:95–175](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/parameter_transfer.py#L95-L175) [S13:499–563](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py#L499-L563) [S21:460–475](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L460-L475) [S21:665–688](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L665-L688) [S22:1907–1917](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/artifacts.py#L1907-L1917)

Synthetic beta и generated normal intervals не становятся empirical authority. Query fingerprint доказывает исполненный SELECT/WITH на bound connection, не output dependence; actual executor так и маркирует. Semantic proposer может предлагать параметры/гипотезы, но binding, evidence provenance, transport validity и admission должны оставаться честными. Не требуется новый deterministic inventor или отдельная paperwork architecture. [S03:1855–1901](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/executor.py#L1855-L1901)

**G01:** public import блокируется Python3.14 syntax при Python3.12.14; pytest/DuckDB нет, Pydantic2.13.4 вне pinned<2.13. **G02:** научная applicability, automatic downstream route и representative I/O cost не квалифицированы. Сохранить useful exact-source/request/presence work; исправить R01 через existing bridge и затем выполнить native chain на штатном runtime.

Четыре неуспешные harness-попытки сохранены с полными исходниками/log/exit; финальный полный run exit0. Repo чист, installs/source edits отсутствуют. MATCH остатка не означает PASS продукта.

[Диагностика](../04_Проверки/C62_STA02/bounded_diagnostics.json) · [Команды](../04_Проверки/C62_STA02/commands.json) · [Границы](../04_Проверки/C62_STA02/native_verification.json) · [Источники](../05_Источники/C62_источники.json) · [Остатки](../01_Реестры/C62_остатки.json).

**62/127 пакетов рассмотрены ограниченно;146 уникальных B/LA частично оценены. Следующий — EXE-01. Полного закрытия нет; фаза2 не начата.**
