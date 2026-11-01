# RES-01 — повторное продолжение без смены исходной задачи
## C65 · 1 ноября 2026 года

**Порядок:** 65/127, LANE-06. **Исходные IDs:** B63, B70, B71. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий проход после внешнего сохранения C64; утраченное прежнее C65 не используется как доказательство.

## Решение

Основные адресные исправления существуют и связаны с потребителем: original fingerprint хранится отдельно от остаточного workflow; достаточность состояния не подменяется числом cache refs; allow_replay действительно возвращает исходный план; успешные точные refs не читаются заново при последовательном восстановлении одного индекса.

**11 bounded MATCH. Новый подтверждённый продуктовый R не установлен.** Полный unchanged resume control flow и cache owner исполнены с явными storage/runner fixtures. Это существенное локальное свидетельство, но **не native durable double-resume и не полное закрытие**. Native tests прочитаны, не выполнены.

## 1. Матрица исходных оснований

| ID | Требование и наблюдение | Сохраняемый остаток |
|---|---|---|
| B63 | P01–P05, P11: точные успешные refs совместно dedupe по trace/checkpoint; failed load повторяем; конфликт одного key не заменяет первый результат | G01 native custody; G02 реальные I/O и tail |
| B70 | P06: исходный fingerprint сохраняется, остатки B→C и C различны; A/B повторно не вызываются. P07: changed functional input отказан, completed reopen без node lookup | G01 actual durable restart |
| B71 | P06: достаточное state без refs продолжает. P08: два refsA не заменяют отсутствующий params.b; allow_replay запускает A,B,C | G01 external artifacts; G03 полнота declarations |

Полная исходная карточка7666–7785 и existing remediation файл539 строк прочитаны. Старые source facts сверены с текущими владельцами, а не приняты за нынешний статус.

## 2. Дешёвый индекс без ослабления replay proof

`_cache_ref_identity` использует четыре компонента: artifact ID, kind, media type и selected manifest profile. `load_entry` пропускает только уже успешно проверенный exact ref, который ещё присутствует в индексе. После failed read memo не создаётся; eviction/discard/clear согласуют memo с индексом. Разные refs одного key читаются отдельно; при конфликте сохраняется первый проверенный результат. [S01:100–103](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L100-L103) [S01:453–505](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L453-L505) [S01:864–924](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L864-L924) [S11:303–317](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/artifacts/manifest.py#L303-L317)

**P01:** 100 trace occurrences A и checkpoint refs A×100+B проходят через один actual NodeResultCache: два admissions и два fixture payload reads. Первый actual get(A) добавляет третье чтение и возвращает first. **P02:** transient failed load→0, повтор→1, ещё100дублей→0; всего два чтения. **P03:** конфликтующий exact ref того же key действительно прочитан, но не подменяет first; altered selected-profile identity не считается тем же ref. Native выбор manifest не заявлен: в fixture отсутствующий exact selector даёт FileNotFoundError.

**P04:** wrong run и unknown replay epoch дают0admissions; unbound payload на tenant-bound owner отвергается. Здесь работают настоящие proof/run/scope predicates, но ambient scope и manifest provider — явные fixtures. **P05:** LRU capacity1, A→B→A требует три проверки, discardA→A — четвёртую: memo не удерживает утраченную admission.

**P11:** 100 действительно разных refs дают100payloadreads. Текущий v2 содержит outcome внутри entry; нельзя механически повторять исходную счётную модель v1 «entry+outcome=200» и приписывать дополнительную экономию dedupe. Схемы и обязательная проверка результата сохранены. [S01:125–151](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L125-L151) [S01:563–696](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L563-L696)

Sync executor и async recovery действительно вызывают trace seed, затем checkpoint seed на **одном** instance. Async делает это off-loop под одним deadline/read budget. Это существующий activation bridge, а не неиспользуемый helper. [S03:1082–1086](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/executor.py#L1082-L1086) [S04:1600–1643](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1600-L1643)

## 3. Исходная идентичность и остаточный план теперь различены

Metadata хранит `workflow_fingerprint` текущего execution plan и `origin_workflow_fingerprint`. Hook init получает прежний origin; оба writer paths сохраняют его, даже если новый fingerprint относится к остаточному графу. Resume сравнивает исходный workflow с origin, проверяет completed aliases в исходном графе и только затем выводит остаток. Functional params остаются в canonical fingerprint; retry/timeout исключены как operational настройки. [S02:338–376](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L338-L376) [S02:834–1036](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L834-L1036) [S02:1524–1551](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L1524-L1551) [S02:1631–1643](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L1631-L1643) [S02:2537–2550](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L2537-L2550)

**P06:** фактические unchanged resume_from_checkpoint и sync/async hook writers работают на typed WorkflowSpec/ExperimentState с реальной canonical сериализацией. InitialA записан; first resume отдаёт fixture runner B,C и останавливается передC; second resume отдаёт толькоC. Calls a=1,b=1,c=1; finalstate{a:1,b:1,c:1}; cache refs пусты. Mid completed=[a,b], current fingerprint уже иной, origin неизменён. Scope этого результата — control flow и writer metadata, **не реальный CAS/head/history или actual executor**.

**P07:** fully completed reopen возвращает пустой report.nodes без registry lookup и без нового runner plan. Изменение functional params даёт WorkflowMismatchError; timeout-only change сохраняет fingerprint. Lock-release fixture наблюдает finally, но OS locking здесь не квалифицирован. Не требуется выключать guards ради второго resume.

## 4. Достаточное состояние, а не кардинальность cache refs

`_missing_completed_state_paths` сопоставляет declared writes завершённых узлов с declared reads остатка. Нужный typed ArtifactRef требует verify **и** readable bytes по целому selector; произвольный похожий JSON не превращается в доверенную ссылку. Полный материализованный state и фактическая доступность внешних объектов — разные условия. [S02:1553–1628](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L1553-L1628) [S08:23–81](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state.py#L23-L81)

**P08:** completed=[a,b], state содержитa, но неb; даже два refsA не помогают: strict resume отказывает по params.b до runner. При allow_replay actual branch выбирает **workflow_spec**, а не residual, и выдаёт явное degraded событие; runner получает [a,b,c]. Это действительно разрешённый повтор, а не прежняя пустая этикетка. [S02:2551–2603](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L2551-L2603)

**P09:** present typed ref с verify/read допускается, read-denied ref отвергается; обычный JSON shape не интерпретируется как ArtifactRef. Native protected store и selected-owner decoding не исполнены, поэтому результат не доказывает разрешение доступа или совместимость всего checkpoint wire.

**P10 / G03:** path `params.items.0` не проходит resume accessor, хотя список содержит7. Это зафиксированная граница dot-path grammar; idempotency read owner тоже не обходит list segments. Поддерживаемый native consumer такого read path не установлен, поэтому наблюдение **не повышено до R**. Важно согласовать контракт existing owners, а не объявить любые string paths уже поддержанными либо переписать dict keys в integer.

## 5. Producer → persist → resume → consumer: что ещё не доказано

Actual local runner передаёт checkpoint hook/cache refs в AsyncWorkflowExecutor. Actual resolution сверяет run/sequence/head metadata, selected artifact view, scope и materialized incremental chain. Эти части прочитаны, но probe намеренно заменяет storage/lock/resolution/context/bootstrap/runner boundary. [S05:43–77](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/local_runner.py#L43-L77) [S02:2218–2346](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L2218-L2346)

**G01:** нужны native existing tests на поддерживаемом Python3.14/Pydantic<2.13: два останова, completed reopen, changed input, selected profile, tenant/cell, missing/corrupt external blob, read denial, successful frontier и настоящее сохранение результата. Current environment Python3.12.14/Pydantic2.13.4, pytest отсутствует; public import останавливается на Corestore2118syntax. Это ограничение среды, не дефект продукта и не разрешение обходить custody.

**G02:** trace всё ещё читается от начала; get заново проверяет entry/outcome перед использованием. Это не само по себе баг: восстановленная cache admission не заменяет действующую проверку использования. Workload bytes/latency и доля повторов не измерены. Если потребуется checkpoint-tail, граница должна быть привязана к подлинной истории и текущей попытке; произвольный offset недопустим.

**G03:** достаточность основана на полноте declarations. Missing external/hidden inputs, consumer-specific meaningful null и более широкая грамматика путей требуют actual consumer cases; JSON-полнота сама по себе не эмпирическая достаточность. Результат маленького a/b/c witness не подтверждает научную истинность или общую надёжность всех методов.

## 6. Сохранить и продолжить

Сохранить immutable origin binding, точные selected refs, успешный memo с invalidation, отказ конфликтующего same-key content, strict state availability и observable full replay. Продолжить существующие owners и общий integration набор LANE-06; новый cache service, новый planner или универсальный deterministic model inventor здесь не нужны.

Attempt01 blocked на retry.py258syntax; затем exact RetryPolicy DTO извлечён без изменения тела. Attempt02 имел10успешныхassertions, но mutable observation dataP06 позднее изменились; лог сохранён, как финальная аттестация не используется. Finalrun делает snapshots и содержит11MATCH, exit0. Expected conflicting-key warning сохранён.50 imported module identities сверены с Git; это не полное human review50files. Repo чист, installs/source edits нет.

[Диагностика](../04_Проверки/C65_RES01/bounded_diagnostics.json) · [Команды](../04_Проверки/C65_RES01/commands.json) · [Границы](../04_Проверки/C65_RES01/native_verification.json) · [Источники](../05_Источники/C65_источники.json) · [Остатки](../01_Реестры/C65_остатки.json).

**65/127 пакетов рассмотрены ограниченно;153 уникальных B/LA частично оценены. Следующий — RES-02. Полного закрытия нет; фаза2 не начата.**
