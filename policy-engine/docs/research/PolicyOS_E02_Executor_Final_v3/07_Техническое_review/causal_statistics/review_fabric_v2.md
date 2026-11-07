# Независимое peer-review fabric/acquisition v2

**Вердикт: принять 17 проверенных изменений как PROPOSED specification corrections. Новых блокирующих дефектов в этих изменениях не найдено.** Это не подтверждение реализации: все product/native TEST остаются **NOT_RUN**, native platform/model qualification — **NOT_QUALIFIED** до исполнения.

Проверен именно итоговый manifest `fabric_acquisition/proposed_changes.json`, а не прежние промежуточные hashes. Контрольные текущие SHA: UDF-05.md `a8eea98a6047d03467982f59b7760a17f8f404ca413825fef6675f7755b80d40`, SCL-01.md `152f0a1f227dede5819998613030b8efb73ab6b49831a03ff60eb71dc689a749`. Полный перечень старых/новых SHA, source ranges и проверки находится в `review_fabric_v2.json`.

## Независимость и охват

- Полностью прочитаны семь изменённых packet Markdown: UDF-05, DFI-03, SCL-01, FED-01, EMB-01, EMB-02, EMB-03, включая все решения, 32 REQ и 33 TEST; три overview LANE-07/08/09. Все JSON parsed полностью; повторяющаяся нормативная проза сопоставлена с прочитанным Markdown, все отличающиеся поля и неповторяющиеся map/decision semantics рассмотрены отдельно.
- Прочитаны авторские `review.md`, `findings.json` и manifest как **claims**. Независимо рассмотрены baseline→proposal diff всех 17 файлов. Проверка не основана на авторском `proposal_validation.json`.
- Исследованы реальные owners и тесты pinned checkout `20d9009be21097bfbdc38a546a15cc60213b8ace` по указанным в JSON диапазонам. Это выборочные code ranges, не утверждение повторного полного аудита всех 25 fabric packets или всего репозитория.
- Все 17 baseline/proposed SHA совпали с manifest. В семи JSON сохранены source IDs, residual dispositions, obligation/preservation maps, protected distinctions и все исходные REQ/TEST IDs. Сохранность map не считается доказательством поведения.
- Библиотечные контракты независимо проверены по pinned primary sources 2026-11-01; отдельно прочитаны реальные extras/lock. Ничего не устанавливалось, repository modules не импортировались, product tests не запускались. Записаны только эти два review artifacts в собственной директории.

## FA-01 — raw integer identity: принять

Source подтверждает существенность порядка: `demography/__init__.py:197–211` делает `np.asarray` в before validator **раньше** `_validate_shapes:230–270`. Поэтому дополнительный integral/range guard только в after-validator сохранял бы округлённый ID. `source_inventory.py:917–933` использует обычный `json.loads`; raw JSON integers ещё доступны точно. Aggregate в `__init__.py:298–378` передаёт raw payload в DTO, а `static_aging.py:36–39` затем материализует int64.

V2 переносит admission перед inferred common float dtype и распространяет его на оба поля, включая standalone record. Положительные смешанные `[2**53+1,1.0]` и `[int64max,1.0]` различают соответственно silent corruption и false refusal; expected — Python integers, downstream comparison точный. Отрицательные out-of-range/fraction/NaN сохранены. Не вводится неоправданный запрет integral floats или отрицательных record IDs; уже испорченную до входа float identity не обещают восстановить.

Это универсальный boundary fix, а не ветка для трёх чисел. Второй compatible input и прежний useful Foundry route остаются обязательными. Стандартный [NumPy 2.3 `asarray`](https://numpy.org/doc/2.3/reference/generated/numpy.asarray.html) действительно выводит dtype из input при отсутствии явного dtype; новая числовая библиотека здесь не нужна.

## FA-02 — direct async harvest: принять

`pipeline.py:1240–1277` явно отвергает любой stage, кроме benchmark/qc/publish, и является synchronous function. Напротив, `pipeline.py:1346–1404` содержит настоящую async цепь с profile snapshot и ветвью harvest; CLI `cli.py:79–106` сейчас вызывает harvester напрямую. Inner resume в `harvester.py:1255–1278` выбирает existing payload; coherent hash после этого не связывает его с новым endpoint.

V2 выбирает существующий async owner либо небольшой общий dispatcher; сохраняет off **и** smart, completion receipt, отсутствие unrelated stage execution и самостоятельную transport-cache policy. Уточнение для исполнения: `stages={"harvest"}` — поле `DatasetBatchConfig`, **не новый keyword аргумент** `run_dataset_pipeline`; actual signature принимает config и thermal. Текст §5 следует читать именно как selected configuration, это не обнаруженный дефект v2.

Независимая проверка basis подтверждает пригодность owner: `pipeline.py:170–200` включает registry bytes, effective producer config и `asdict(spec)` selected sources; `:610–659` сравнивает current input/output basis. Thus endpoint mutation при прежнем name действительно должна приводить к miss, а не только менять декларацию config. Counted acquisition + receipt/fresh-reader oracle сильнее проверки `resume=False`. Старые malformed-count, full denominator, empty/None и noncacheable core/QC controls сохранены.

## FA-03 — offline admission до DNS: принять

`fetcher.py:42–45` делает `_resolve_fetch_target` до cache lookup; `security.py:76–116` включает `getaddrinfo`. Existing positive test `test_fetcher_security_cache.py:60–106` подменяет DNS успешным для обоих вызовов, поэтому не различает необходимую offline способность.

V2 не снимает безопасность ради availability: offline syntax/domain/port/literal-IP и saved initial/final/redirect/MIME/raw-size/profile admission остаются **до** cached выдачи. Только разрешённый fresh miss/refresh проходит прежний resolver и pinned peer/SNI/redirect transport. Current DNS не выдается за доказательство исторического peer. Неизвестные нужные факты дают ineligible/gap, а не fabricated permission; отсутствие полного совпадения несущественных profile fields не отключает всё reuse.

Producer put→JSON reload→DNS/socket/transport raise-on-call одновременно проверяет положительный offline hit и policy denial без сети. Native live negative controls остаются отдельными и не заменяются cache fixture. SCL-03 сохраняет единственный coordinated fetch-profile writer. Это bounded refactoring security owner, не новый HTTP stack и не вывод о найденном SSRF exploit.

## FA-04 — stdlib mean: принять как предпочтение, не доказанный speedup

`composer.py:1669–1727` уже классифицирует и приводит eligible numeric values к Python float; narrow binary64 helper подходит именно этому boundary. Текущий pandas mean/median заменяется без смены participant/exclusion/absence semantics. Scalar MEDIAN по-прежнему выбирает actual source cell; новый helper не создает synthetic producer.

Pinned [CPython 3.14 statistics source](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py) подтверждает: `mean` использует exact ratios и rational total/n перед conversion; `fmean` сначала `fsum`, а even `median` — сумму central values. Поэтому `fmean`/`median` не эквивалентны требуемому full finite-domain contract. V2 правильно предпочитает existing stdlib за общим API FED-owner/UQS-consumer, оставляя custom accumulator лишь по документированной причине.

Независимая stdlib арифметика на **host Python 3.12.14**, не product/target тест: `[1e308,1e308]→1e308`, `[10.,14.]→12`, `[1e308,-1e308,3*ulp(0)]→ulp(0)`, midpoint `[ulp(0),2*ulp(0)]→2*ulp(0)`. Все совпали с exact `Fraction.from_float` average. Это подтверждает конкретные expected values, не native 3.14 execution и не throughput claim. Expected нельзя вычислять production wrapper; Fraction oracle разделяет базовые runtime rational/conversion primitives с stdlib, поэтому hardcoded analytic boundary expectations также важны. V2 их сохраняет.

## FA-05 — measurement, без ослабления identity: принять

Catalog reader `store.py:301–345,428–476` перед reuse проверяет текущую полную text projection и selected generation. `embeddings.py:1250–1340` перечитывает/hashes inventory members и NPZ; cached HNSW object не устраняет этот объём. Следовательно, замечание о cost обосновано source, но SLA нарушение или линейная фактическая latency не измерены.

V2 оставляет именно bounded cold/warm breakdown, bytes/hash/projection/NPZ/load/encode/knn/RSS и workload goal. Нет обязательства внедрить новый lease/cache/vector DB; stat-only trust прямо запрещён. Любая будущая амортизация требует proven immutable lifetime и mutation/replace/withdrawal invalidation controls. Reader correctness и полезность старого поколения не обмениваются на speed. Baseline staged semantic admission, typed empty и postcommit copy distinction не урезаны.

## FA-06 — topology, semantic utility и GL/G5: принять с явной границей

Один existing ds-1 self-query (`test_emb_02.py:399–488`) проверяет wiring, но пропускает query-independent first-ID implementation. V2 topology fixture N≥3, k<N, non-tied vectors и заранее independent cosine ranks действительно различает этот механизм. [HNSW 0.8.0 API](https://raw.githubusercontent.com/nmslib/hnswlib/v0.8.0/README.md) подтверждает approximation и отдельный query ef, который требуется установить после load; source loader уже ставит ef=100. Нельзя распространить exact finite expected output на любой ANN corpus — v2 этого не делает.

Actual owned model qualification отделена от deterministic encoder: frozen relevance labels, distractors, held-out queries, заранее выбранные k/ef/criterion, новый resource через data/metadata и normal reissue/fresh public consumer. Без semantic witness utility остается NOT_QUALIFIED, но локальный preselection repair и механическая native serving qualification не блокируются. Это разумное разделение, не лазейка объявить пустой result достаточным positive serving.

Независимо прочитан `legal_mandate_search.py:1867–1990`: existing helper принимает **Layer3GLLegalSearchLedger**, проверяет known seeds и snapshot refs; test `:905–960` различает missed seed и permitted no-ground. V2 предлагает reuse **принципа evidence/currentness**, а не прямое преобразование embedding candidates в authoritative GL ledger. Typed schema и legal/source-relation границы сохранены. Конкретные utility threshold и corpus ещё должны быть заморожены до исполнения; их отсутствие сейчас — честная будущая qualification, не fabricated PASS.

## FA-07 — версии, extras, assets: принять

Независимый TOML read: parent Python `>=3.14,<3.15`; `vector-search` содержит hnswlib0.8.0, `rag-local` — отдельный optional extra. `research`/`all` не включают rag-local. Lock содержит hnswlib0.8.0 sdist без wheels, ST2.7.0, torch2.10.0, transformers4.57.6. Отсутствие wheel — не доказанная невозможность build, а наличие lock — не доказанная native совместимость.

`LegalRuntimeMaterialOwner.resolve_encoder:649–739` требует local snapshot, exact ST version, byte-bound assets/runtime и CPU dimension1024. [ST2.7 constructor/encode source](https://raw.githubusercontent.com/UKPLab/sentence-transformers/v2.7.0/sentence_transformers/SentenceTransformer.py) совместим с используемым local path/device; современные отсутствующие constructor keywords не навязаны. V2 правильно отделяет P-INDEX от P-LEGAL-OWNED, исключает нерелевантный GP prerequisite и не превращает tiny corpus в обещание tiny model memory.

Не выполнены build/import/runtime qualification на Python3.14, model inventory, actual encoding/serving или package installation. Нужен один реально поддержанный конечный профиль; нет требования всех OS и нет разрешения скачать assets. Общие `03_Интеграция` profiles согласует root; этот peer-review не считает ещё не завершённое общее согласование дефектом локальных 17 файлов.

## Остаточные условия принятия

1. Сохранить NOT_RUN/NOT_QUALIFIED, future numeric/native measurements и independent oracles при финальной сборке.
2. Root должен синхронизировать общие integration profiles/claims с packet/overview semantics; собственный review не редактировал shared files.
3. Перед implementation выбрать finite utility corpus/criterion и native platform/assets. Нельзя подменять missing prerequisites fake encoder или переносить performance/semantic claims с mechanical fixture.
4. Implementation review должен проверить actual raw validator ordering, async config.stages dispatch, offline/live split и общий numeric owner; этот document review не утверждает, что код уже исправлен.

**Новые findings: 0.** Вывод ограничен прочитанными 17 proposed files и перечисленными source contracts; никаких внешних или продуктовых mutations не выполнялось.
