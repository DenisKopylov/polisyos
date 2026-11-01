# DFI-03 — содержательное основание batch resume
## C98 · LANE-08 · LA-041

**Решение: частично подтверждено, не закрыто.** Selected pipeline больше не принимает только stat-fingerprint и существование directory: сравнивает текущие input basis и обязательный output inventory, а embed связывает с выбранным поколением и encoder assets. Сохранены formatter и atomic owner. Найдены два узких остатка: malformed numeric receipt прерывает recovery, а standalone harvest CLI игнорирует `resume_mode=off`, когда `resume=True`.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **5 MATCH; 13 неизменённых existing bodies / 14 cases PASS**, bounded, не native pytest. MATCH включает воспроизведение двух дефектов. 98/127 пакетов рассмотрены; следующий ING-01. Полного закрытия LA-041 или научной способности не заявлено.

## 1. Две независимые оси

**Исходный ремонт.** Оба основания реально подключены к selected consumer, не просто существуют рядом. Legacy helper остаётся слабым по умолчанию, но actual tracked selected caller требует strict basis/inventory. Explicit `required_outputs=[]` теперь намеренно отказывает; `None` сохраняет recorded-path semantics. Это объявленный behavior delta, не случайная подмена formatter/API.

**Содержательная способность.** Actual harvest producer пишет payload, raw manifest, checkpoint и stage outcomes; consumer сверяет выбранные source names, complete statuses, hashes, paths и row counts. Полная pipeline при outer miss отключает inner legacy cache. Но direct CLI обходит эту policy, а неправильный numeric receipt не деградирует в cache miss. Ни checksum, ни право пропустить вычисление не удостоверяют научную пригодность данных или финальное право публикации.

## 2. Матрица исходного ID

| ID / требование | Actual evidence | Вывод |
|---|---|---|
| LA-041: input bytes, config/rule и output integrity отдельно | S01–S03; P01/P02 | Same-stat input change отказывает; mtime-only не мешает reuse; changed output/config/rule отказывает |
| Embed first, complete и declared empty generation | S02:428–474,596–659; S03; P01/P05 | Нужны established current encoder identity и selected complete/empty inventory; empty не запускает encode |
| Harvest/normalize на фактическом маршруте | S02,S06,S07; P03/P04 | Actual harvest receipt проходит; checksum-free отказывает. Normalize predicate проверен с receipt fixture, producer source-only; direct CLI остаётся R02 |
| Malformed/interrupted/legacy recovery | P01/P03; S01:21–29,131–204 | Malformed stage JSON и wrong entry shape → rerun с сохранением current generation; numeric receipt shape → R01 |
| Explicit [] против None; old JSON bytes | S01:32–40,160–204; P01/P02 | Различие объявлено и проверено; formatter indent=2/sort_keys=True сохранён поверх atomic_write_text |
| LK20: hash не authority и не полнота denominator | S02:492–659; P03/P05 | Полный выбранный source set и hash обязателен; excluded private profile inputs не дают skip. Actual profile capture UNRUN |

[Полный исходный текст](../05_Источники/DFI-03_исходные_строки.txt) · [Pinned source index](../05_Источники/C98_источники.json).

## 3. Реальная цепочка owner → запись → consumer

`checkpoints` описывает только caller-selected inputs/outputs, не сканирует весь repository. Content records для файлов содержат hash; directory output inventory включает членов и hashes. Pipeline задаёт stage-specific rule, effective config, inputs и mandatory outputs. При completion сохраняет basis и inventory, при skip вычисляет их заново и сравнивает с recorded (`S01:67–204`, `S02:170–474,1285–1343`).

Для embed basis получает DB и текущую identity загруженных local-only encoder assets, не одно имя модели. Output inventory разрешается через selected generation manifest: complete members или declared empty, а не historical flat pair. Same-label asset change отказывает. Эта связь использует common publisher из EMB-02; общий semantic preselection остаток [C96-R01](EMB-02.md) не исчезает от добавления resume и не считается здесь второй раз (`S03`, `S02:428–474`).

Harvest receipt сверяет полный selected registry denominator, успешные outcomes без failed sources, confinement payload/manifest внутри source root, digest в трёх местах и count с реальными строками. Checksum-free historical raw manifest не допускается. Normalize требует этот receipt, затем свой content inventory. При cache miss full pipeline передаёт `replace(config, resume=False)` в harvest/normalize, поэтому их inner прежний cache не отменяет outer decision. Core ingest и QC намеренно rerun: внешние inputs/live-readiness не имеют достаточного complete receipt. Это честная limitation, не ошибка эффективности сама по себе (`S02:492–659,1280–1282,1358–1463`; `S06–S07`).

`current_content_stage_receipt` служит отдельным downstream readback: проверяет текущие basis/inventory/selected generation, а не верит одному status. Whole benchmark/QC/publish helpers и final admission здесь не квалифицированы. Source-only producer profile capture содержит отдельный coverage contract; исполнен лишь его classifier с controlled states, а не реальные private inputs (`S02:662–712`, `S04:434–713`).

## 4. Различающие проверки

1. **P01: 14 cases, 13 bodies.** Same-stat changed input, mtime-only, changed merge output, legacy directory без inventory, empty normalize directory, explicit [] и None, selected empty без encode, config/rule/output changes, same-label encoder asset drift, interrupted state и retry; malformed JSON/wrong entry shape (две параметризации) восстанавливают actual current empty generation через sync/async pipeline. Fixtures перечислены ниже; это не вся existing suite.
2. **P02: совместимость отделена от strict policy.** Legacy default helper всё ещё принимает изменённые output bytes; selected caller использует strict kwargs. Formatter сравнен с прежними exact bytes; input None не тождественен пустому списку. Слабый helper default не объявлен текущим bypass без caller evidence.
3. **P03: actual harvest producer/consumer.** Записанный producer receipt позволяет skip и даёт current readback. Удаление обязательного sha256 отказывает. После восстановления замена count на `not-an-integer` вызывает ValueError; возвращение исходных bytes снова разрешает skip. Никакого ложного success не получено.
4. **P04: public parser и два dispatcher маршрута.** После первого harvest команда `harvest --resume --resume-mode off` не вызывает transport повторно и сохраняет старый payload. `run --stages harvest --resume --resume-mode off` вызывает один новый fetch и меняет payload. Config constructor fixture сохранён явно; actual constructor/validator source не сбрасывает resume при off.
5. **P05: coverage не inventory.** Current empty generation с установленным fixture profile coverage reusable; `excluded_present` делает skip=False; возврат coverage восстанавливает True. Actual classifier исполняется, actual private profile capture — нет.

## 5. Остатки и что сохранить

**C98-R01, low — malformed receipt recovery.** В [actual reconciler](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py#L552-L564) три `int(...)` выполняются без shape/type admission. Controlled wrong count выбрасывает ValueError до cache-miss решения. Исправлять existing reconciler: typed invalid receipt → адресный rerun/unavailable, не широкое подавление всех ошибок и не ослабление hash/count checks. Это ограниченная availability/recovery проблема, не authority bypass и не доказательство частоты повреждений.

**C98-R02, low — direct CLI policy не подключена.** [Dispatcher](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/catalog/batch/cli.py#L96-L109) вызывает harvester напрямую; [inner cache](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/catalog/batch/harvester.py#L1256-L1280) проверяет только resume. Связать existing policy/uncached config с этим маршрутом или явно реализовать off у owner, не писать второй resume framework. Сохранить полезный smart resume. Подтверждены parser/branch и bytes под transport/config fixtures; native network, final publication и все direct команды не исследованы.

**C98-G01 — native scope и стоимость.** Требуется связанный малый native corpus для actual config/profile capture → harvest/normalize → embed → resume/readback, с настоящими DuckDB/HNSW и existing tests. Использовать общую lane-проверку C95–C98, не четыре дублированных тяжёлых suite. Actual normalizer сейчас только прочитан. Native all-stage pipeline, scientific validity, final closeout и большой DB performance не измерены. Helper принимает trusted immutable receipt, но current tracked source `trusted_inputs=` caller не найден; нельзя объявить optimization подключённой или stat trust активным обходом. Не устранять hashing ценой недоказанной immutability.

**Сохранить:** strict разделение input/output; full selected-source denominator и checksum requirement; current encoder assets; complete/typed empty distinction; current receipt consumer; retry после malformed/interrupted stage; formatter bytes/atomic transport; legacy readable state без автоматического strict admission; declared excluded-profile refusal; intentionally non-cacheable external/live stages. Не требовать universal deterministic model inventor и не превращать reuse receipt в научное доказательство.

## 6. Воспроизводимость

[Команды](../04_Проверки/C98_DFI03/commands.json) · [Диагностика](../04_Проверки/C98_DFI03/bounded_diagnostics.json) · [Selected source identity/adaptation](../04_Проверки/C98_DFI03/selected_source_identity.json) · [Receipt fault](../04_Проверки/C98_DFI03/run03/harvest_receipt_fault.json) · [CLI trace](../04_Проверки/C98_DFI03/run03/CLI_resume_mode_trace.json) · [Native status](../04_Проверки/C98_DFI03/native_verification.json) · [Fixtures](../04_Проверки/C98_DFI03/fixture_authority_limits.json) · [Чтение](../04_Проверки/C98_DFI03/Чтение_и_границы.md) · [Остатки](../01_Реестры/C98_остатки.json).

Run01 exit1 до observations: transitive unsupported syntax. Run02 exit1: неполный fixture config, 2 PASS/11 FAIL, четыре ERROR/один MATCH; ошибки сохранены, не названы product defects. Run03 exit0: 5 MATCH/14 PASS, без суммирования прошлых запусков. Actual selected pipeline clause468 имеет только syntax parenthesization для3.12; clause1233 изменён лишь для parsing и не исполняется. Harvester selected nodes unchanged. Whole checkpoint/embed kernel, files, hashes, NumPy/NPZ и atomic writes реальны. Config/profile/selection, SQL/encoder/transport и JSON `.hnsw` — fixtures, не native инфраструктура.

Native pipeline/checkpoint/CLI imports BLOCKED на transitive `core/artifacts/store.py:2118` Python3.14 syntax в3.12.14; pytest/DuckDB/HNSW отсутствуют. Checkout и зависимости не менялись; внешние запросы не выполнялись. Отсутствие среды не product defect. **98/127 — промежуточный результат, фаза заданий исполнителю не начата.**
