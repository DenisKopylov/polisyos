# TRN-02 — точные snapshots и согласованное поколение vector memory
## C26 · 31 октября 2026 года

**Исходные IDs:** B129, B133, B134. **Порядок:** 26/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; следующий — TRN-03.

## Решение

**Все три исходных механизма существенно отремонтированы.** Найденный run сохраняет exact history ref/profile; известный ключ читается через `lookup_metadata`, не нулевой ANN. Cache адресован полным snapshot identity и хранит ограниченные immutable bytes с повторной проверкой. Vector memory защищает единое поколение lock-ом, сохраняет snapshot перед native mutation, восстанавливает индекс при частичной ошибке и полностью блокирует поколение, если rollback не удался. Load строит отдельный candidate index до публикации; metadata принадлежат store, а не вызывающему коду.

Подтверждён более узкий **C26-R01:** discovery ограничивает ANN до `2 * top_k` **до** compatibility filtering, поэтому доступный совместимый третий результат скрывается за двумя несовместимыми при top_k=1. Это не прежняя потеря уже найденной ссылки: exact replay исправен. Полное закрытие также требует native HNSW/CAS и source-owner квалификации, а не возврата небезопасной загрузки произвольного native graph.

Итог решающего повторного запуска: **24 MATCH, 0 ERROR**, exit 0. Actual transfer/vector owner definitions, реальные DTO, реальные локальные файлы и Python thread locks; HNSW interface, CAS и source replay — **явные фикстуры**. Native hnswlib и pytest отсутствуют; tiny native test **UNRUN**, зависимости не устанавливались.

## 1. Исходные требования и сохранённая работа

[Полная карточка TRN-02](../05_Источники/TRN-02_исходные_строки.txt) требует сохранять оплаченный опыт и не связывать старые векторы с новыми именами после ошибки. Увеличение ANN top_k или только откат Python metadata не являются достаточными ремонтами.

| ID | Исправленный исходный механизм | Остаток / граница |
|---|---|---|
| B129 | `RunFingerprint.history_ref`; exact profile-qualified read; key lookup без ANN; corruption не превращается в empty | C26-R01 касается полноты discovery до получения ref. Native access/custody не доказывается fixtures |
| B133 | Полный ref + run identity в cache key; bytes, fresh decode, source/profile recheck; LRU 128 и 32 MiB | Измерить native стоимость/ошибки store; byte budget не обещает RSS ceiling. Старый snapshot остаётся адресуемым |
| B134 | Whole generation; lock; prechecks; snapshot/restore; poison after failed rollback; отдельный candidate load; owned JSON | Tiny native ABI/failure/fresh-process tests не выполнены; portable producer→persisted ref→runtime consumer требует полного qualification |

Это две независимые оси. Исправленная storage-механика делает reuse доступным, но не устанавливает причинную сопоставимость измерений, source authority или право использовать hidden holdout. Эти границы сохраняются из TRN-01 и настоящих downstream consumers.

## 2. B129/B133: от discovery до повторного чтения конкретных bytes

`find_similar_runs` возвращает полный ArtifactRef с выбранным manifest profile. `_load_run_evaluations` использует его непосредственно; если caller знает только run ID, он делает exact `lookup_metadata`. Отсутствующий ключ возвращает [], а неподходящий ref, malformed header или повреждение вызывают адресную ошибку. Они не заменяются ближайшим соседом. [S01:182–281,480–497,739–808]

`_history_cache_key` связывает full ref identity и complete run fingerprint. `_remember_history_bytes` принимает только exact bytes; LRU ограничен 128 entries и суммой retained payload bytes 32 MiB. Oversized artifact читается без caching; eviction не удаляет CAS history. На hit вновь вызывается `_read_history`, проверяется selected Core view, затем создаются новые decoded rows. [S01:447–478,810–919]

**Реальная граница store:** `read_core_json_artifact` сначала читает typed/raw manifest profile, проверяет selected profile и digest даже при переданных cached bytes. `FileSystemCAS.get_bytes/get_manifest` вызывает owner checks для blob и selected/default manifest view, затем проверяет identity. Это source trace, не выполненная нами авторизация. Cache экономит payload reads, но не должен превращаться в обход актуальной manifest custody. [S07; S08]

### Исполненные различающие контроли

* **P01:** после discovery fixture catalog расширен до 1002 записей; selected history читается, ANN calls остаётся 1. Это не измерение геометрии HNSW.
* **P02:** известный key без history ref — 1 exact lookup, 0 ANN calls.
* **P03:** один run alias, old/new snapshots: последовательность scalar **1, 9, 1, 9, 9** для old, new, old replay, current alias, fresh manager. Никакой warm/cold stale-cache разницы в этой механике.
* **P04:** consumer меняет params/source/metadata; следующий hit сохраняет исходный valid record; payload прочитан один раз, profile boundary вызывается снова.
* **P05:** cached bytes повреждены — refusal, cache discard, следующее чтение вновь получает источник. Это контролируемая порча private cache, не пользовательская операция.
* **P06/P07:** LRU порядок и сумма bytes согласованы; oversized history не cached, но адресуемая запись остаётся.
* **P08:** exact selected artifact с другим run ID отвергнут без fallback/ANN.

В P01–P08 actual history/header/cache functions исполняются полностью, но Core reader/manifest owner заменён explicit fixture с digest и selected-ref проверкой. Поэтому результат не называется native CAS acceptance либо independent scientific replay.

## 3. C26-R01 — compatible discovery обрезается до применения фильтра

**Важность:** средняя для доступности полезного опыта; не нарушение numerical admission.

[Actual discovery](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py#L194-L219) вызывает `query(..., top_k=top_k * 2)`, а затем применяет `_binding_matches`. Если ближайшие результаты принадлежат другому tenant/split/space, бюджет уже исчерпан до подходящего source.

**P09:** deterministic index содержит по порядку два несовместимых результата и один совместимый. При top_k=1 ANN возвращает только первые 2, итог discovery=[]; при top_k=2 ANN budget=4 и тот же совместимый run найден. Exact known ref в обоих случаях читается. Source fingerprint и содержимое не менялись.

Это не требование превратить ANN в exhaustive search и не повод снять tenant/split filters. Остаток — применить compatible filtering у существующего index owner либо разрешённый bounded refill/continuation с явным статусом исчерпанного discovery budget. Нельзя описывать bounded пустой результат как доказанное отсутствие совместимого опыта. Полезный exact lookup и ограничения численного reuse сохранить.

## 4. B134: публикация не оставляет полупоколение

`_Generation` связывает native index, config, tuple keys/metadata, key map и binding status. `add` заранее проверяет размер, конечность, capacity и owned JSON, готовит новые Python tables, сохраняет index bytes, затем **до native mutation** устанавливает `_generation=None`. Всё выполняется под RLock. После успеха публикуется новое целое поколение; после исключения восстанавливается новый index из старого snapshot. Если восстановление тоже падает, poison остаётся. [S02:271–425]

`query`, exact lookup и capture для save используют тот же lock. Metadata глубоко копируются только как exact встроенные JSON values, без arbitrary `__deepcopy__` callbacks; запрещены cycles, custom objects, non-string keys, reserved `_type` и nonfinite values. `_owned_vector` масштабирует finite inputs до нормализации, не переполняя сумму квадратов на больших finite values. [S02:133–178,426–627]

### Наблюдения

| Наблюдения | Фактический результат |
|---|---|
| P10 | Normal add/query: имена, расстояния fixture и metadata согласованы |
| P11/P12 | Capacity и wrong dimension отвергаются до изменения bytes или metadata |
| P13 | Fixture index сначала действительно изменяется, затем бросает exception; snapshot restore возвращает старые bytes и metadata |
| P14 | При отказе rollback query/add/length/lookup все отказывают; смешанное состояние не выдаётся |
| P15/P16 | Caller mutation после write/read не меняет store; 4 недопустимых metadata формы не трогают старое поколение |
| P17 | Actual save/load v2 bodies и actual Pydantic refs сохраняют выбранное поколение в fixture store |
| P18–P20 | Candidate native-interface exception, duplicate keys и несовместимая dimension оставляют старое поколение целым |
| P21 | Actual binary record-shape validator принимает правильный fixture layout и отвергает truncated links |
| P23 | Реальный concurrent query ждёт publication lock во время частично изменённого fixture index и затем получает только новые согласованные metadata |
| P24 | Два query и exact lookup не сохраняют/не перестраивают весь индекс; один add создаёт один snapshot |

В P13 используется partial mutation, а не просто ошибка до вызова native backend: это различает настоящий rollback от отката только Python-list. В P23 реальны threads и RLock, но backend — сохранённый `_PortableIndex` из существующего test fixture. **Это не native exception/stress или distributed transaction proof.** Полные snapshot bytes на каждом add имеют стоимость; P24 считает вызовы, не измеряет native throughput/RSS.

## 5. Source capability: portable rows вместо неподтверждённого внешнего graph

Load сначала собирает candidate config/keys/metadata/index, проверяет shape/labels/capacity, затем под lock заменяет единственную `_generation`. До этого прежнее поколение продолжает существовать. Для native v2 сохранены exact member ref/profile и lineage edge; legacy default-at-read явно помечен ограниченным. [S02:637–959]

Default load **не принимает** native legacy/v2 без explicit trust opt-in, даже при синтаксически корректном ref. **P22** подтверждает actual `legacy_native_index_not_admitted`, старое поколение сохранено. Это полезная intentional boundary, не регрессия, которую следует исправлять включением bool по умолчанию. `_validate_native_index_bytes` сам предупреждает: shape validator не устанавливает adversarial topology или producer origin; наш ABI gate заменён fixture, настоящий HNSW 0.8.0 не запускался.

Есть штатный portable rows v3: bounded JSON и selected NPZ member, exact lineage, dimensions/count/capacity/work limits, numeric dtype/finite checks, затем rebuild без загрузки внешнего graph. `from_portable_artifact` позволяет начать без предварительной native allocation. Реальный candidate-only runtime loader использует именно его. [S02:317–323,491–579,670–726,837–887; S09]

**C26-G01:** положительный native 0.8.0 read/rebuild, actual Core store/owner/profile и fresh-process replay ещё нужны. Существующие native custody tests прочитаны целиком; они действительно содержат isolated subprocess проверки, а не только DTO assertions. Не считать их выполнение состоявшимся в этой среде. В inspected runtime путь получает caller-supplied index_ref; автоматический producer portable index в этом пути не установлен. Есть working API для записи; отсутствие здесь полностью проверенного orchestration bridge не означает отсутствия всего transfer.

**C26-G02:** измерить стоимость snapshot-per-add, recovery и portable rebuild в поддерживаемом tiny native профиле, не менять bounds ради throughput и не требовать полного rebuild на обычном чтении. Сумма cache payload bytes не равна общей памяти процесса.

## 6. Существующие тесты и честность audit следов

`test_trn_02.py` прочитан полностью, 814 строк: exact discovery, cache, capacity, native round trip, controlled load failure и malformed/truncated bundles. Дополнительно прочитаны complete native custody tests (198 строк) и конкретные содержательные блоки snapshot-consistency tests, перечисленные в source index; остальные 1266 строк не объявлены прочитанными целиком.

**C26-G03:** один inherited cache test обращается к `stage_b_result['metrics']['coverage']`, хотя его `_stored_eval` теперь создаёт score/metric_units без coverage. Это source-level fixture inconsistency, не выполненный pytest failure. Не объявлять всю suite зелёной по нашим bounded probes.

Первоначальная audit-обвязка вызвала P17 до объявления helper, затем сама удалила ERROR и повторила observation. Такой лог не использован как решающее доказательство. Исходный script snapshot, первоначальный вывод и явное объяснение сохранены. Обвязка исправлена на единственный вызов **после** определения, весь harness запущен заново с нуля без удаления observations: **24 MATCH / 0 ERROR**. Ни product source, ни tests не менялись.

Отдельная citation-поправка к предыдущему C25 сохранена в истории: deciding `bool(stage_a_passed)` находится на строке 621, поэтому узкий диапазон следует читать как 615–629. Source-index уже содержит полный transfer.py; report и execution evidence C25 не переписаны и не переаттестованы. [Поправка](../06_История/Поправка_цитаты_C25_при_C26.md)

[Диагностика](../04_Проверки/C26_TRN02/bounded_diagnostics.json) · [команды](../04_Проверки/C26_TRN02/commands.json) · [границы](../04_Проверки/C26_TRN02/Чтение_и_границы.md) · [источники](../05_Источники/C26_источники.json) · [остатки](../01_Реестры/C26_остатки.json).

**26/127 пакетов рассмотрены ограниченно; 70 уникальных B/LA частично оценены; полного закрытия нет.** Следующий — **TRN-03 / B135, B136, B137**.
