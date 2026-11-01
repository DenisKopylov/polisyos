# Финальное техническое ревью LANE-07/08/09 — 25 пакетов

**Главный вывод:** архитектуру этих лейнов не нужно переписывать. Найдены три адресные ошибки/неполноты технических инструкций: UDF-05 проверяет ID после возможной потери точности; DFI-03 предлагает неподдержанный sync harvest helper и неполный off-only обход; SCL-01 недостаточно явно отделяет offline cache от live DNS. Они исправляются на существующих owners. Exact mean можно упростить через stdlib3.14. Остальное — точная native/полезностная квалификация, а не выдуманные дефекты.

**Статус:** все product tests **NOT_RUN**. Это новое source/spec/library review на `20d9009be21097bfbdc38a546a15cc60213b8ace`, не подтверждение исторических PASS. Ни baseline, ни product code не изменялись. Полностью рассмотрены все25 solutions и TEST; выборочные exact source/test ranges и hashes — `coverage.json`. Машиночитаемые решения — `findings.json`, `library_decisions.json`; per-packet data — `packet_reviews.json`.

Обозначения путей: `P/` = `e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications/`; `src/` и `tests/` — относительно `e02_repository/policy-engine/`.

## Приоритет решений

- **До исполнения соответствующего ремонта:** FA-01, FA-02, FA-03 — уточнить инструкции и различающие тесты.
- **Предпочтение, а не correctness blocker:** FA-04 — stdlib exact mean за common API, target/cost qualification обязательна.
- **Только measurement-first:** FA-05 — warm index validation может оставаться O(total bytes/text); SLO нарушения не измерены, нового lease framework не требуется.
- **Только для stronger retrieval claim:** FA-06 — separate index topology и semantic relevance holdout; не блокировать локальный semantic publisher fix.
- **Профили native execution:** FA-07 — HNSW отдельно от owned ST assets; GP dependency не нужна LANE08.

Общий критерий free-grow здесь практический: новый совместимый ресурс/данные должны проходить текущий contract и actual consumer без новой case-specific ветки. Новая семантика, модель или live role может законно требовать reusable code/contract extension. Нельзя требовать deterministic universal truth engine; нельзя и объявлять «полезность» по одному green receipt.

## Находки и точные корректировки

### FA-01 — verified_specification_defect / medium

**Пакеты/приёмка:** UDF-05; REQ-UDF-05-02, TEST-UDF-05-02, E02-I07-B-B01.

**Проблемное предписание:** §5.3 помещает exact-integer validation в model _validate_shapes как будто до него не было lossy coercion.

**Доказательство:** P/02_Пакеты/UDF-05.md:63; src/polisyos/data_forge/domains/ukraine/demography/__init__.py:197–211 (_coerce_numpy before validator); same:230–270 (_validate_shapes/int64 casts); src/polisyos/data_forge/domains/ukraine/static_aging.py:36–39.

**Контрпример:** donor_record_index=[9007199254740993,1.0] ещё до after-validator становится общим float array; первый ID округляется к9007199254740992, оставаясь integral/int64-representable. [9223372036854775807,1.0] округляет valid max к2**63 и может дать false refusal. Homogeneous max tests этого не различают.

**Предпочтительное решение:** Разделить числовые arrays и index fields в before coercion; exact source scalar validation без float(int), далее canonical int64 и существующие pair/shape/state-domain guards. Для уже float-array доступная identity — его actual float, не выдуманное исходное integer значение.

**Замена REQ/decision:** REQ-UDF-05-02 дополнить: «Дискретные индексы проверяются на исходных scalar values ДО любого inferred/common float dtype. Смешанные допустимые integer/integral-float последовательности сохраняют каждый int64 ID точно; дальнейший dtype materialization не изменяет идентичность».

**Различающий TEST:** TEST-UDF-05-02 добавить record mixed [2**53+1,1.0], [int64max,1.0], [int64min,-1.0] через raw JSON→historical reader, candidate reader и direct DTO; expected IDs заданы Python ints. Negative соседние2**63/-2**63-1, fractions/NaN и standalone record. Downstream state equality точная, не allclose.

**Owner:** UDF-05 demography DTO/assembler; UDF-01 не второй writer.

**Что сохранить:** Сохранить signed record domain, integer-valued floats, optional donor и typed error translation. Не пытаться восстановить точность уже float input.

**Проверка:** Native3.14 NumPy2.3.5/Pydantic2.12.5; failing-before mixed-ID witness + homogeneous matrix; product tests NOT_RUN.

**Неопределённость:** Verified source/spec placement mismatch. Binary64 rounding reproduced stdlib independently; actual NumPy/Pydantic paths not executed.

**Альтернативы:** Только после np.asarray проверять finite/integral/range — недостаточно; Отвергать все integral floats — нарушает сохранение; Original scalar validation в dedicated before field validator либо bounded object-preserving staging, затем int64.

**Первоисточники:** [dtype parameter / inferred from input](https://numpy.org/doc/2.3/reference/generated/numpy.asarray.html).

### FA-02 — verified_specification_defect / medium

**Пакеты/приёмка:** DFI-03; REQ-DFI-03-02, TEST-DFI-03-02, E02-I08-A-B03.

**Проблемное предписание:** §5 предлагает существующий run_content_stage_with_receipt для harvest; запасной off-only config change не закрывает normative direct-smart currentness.

**Доказательство:** P/02_Пакеты/DFI-03.md:75; src/polisyos/data_forge/domains/catalog/batch/pipeline.py:1240–1277 (sync, benchmark/qc/publish only); same:1392–1404 (actual async harvest policy); src/polisyos/data_forge/domains/catalog/batch/cli.py:79–106; src/polisyos/data_forge/domains/catalog/batch/harvester.py:1075–1134,1255–1278.

**Контрпример:** Буквальный helper(config,"harvest") всегда ValueError. Если выбрать только off patch, smart при том же source.name, coherent previous payload/hash и изменившемся endpoint/profile может выполнить inner existence-based resume без current input-basis admission. Post-read checks доказывают payload integrity, не соответствие новому request.

**Предпочтительное решение:** Явно выбрать existing async finite-stage route. На smart hit current content receipt разрешает reuse; на off/miss отключить внутренний stat/existence checkpoint и реально harvest; сохранить single-stage ABI. Если используется factor helper, он принадлежит pipeline и вызывается обоими routes.

**Замена REQ/decision:** REQ-DFI-03-02 дополнить: «Direct single-stage harvest использует тот же current input/output-basis admission и completion writer, что full pipeline. На off либо smart miss inner resume=False. run_content_stage_with_receipt не используется для неподдержанного harvest».

**Различающий TEST:** TEST-DFI-03-02: initial valid→smart current hit network0; изменить только endpoint/config/registry bytes при прежнем source.name и coherent old payload→fresh counted acquisition. Off --resume всё равно fresh. Missing/malformed receipt→fresh. Actual new receipt+fresh reader, не одно observed config поле.

**Owner:** DFI-03 owns harvest dispatch/receipt. DFI-02 counters и EMB-02 publisher freeze before shared pipeline edit.

**Что сохранить:** Не выключить отдельно разрешённый HTTP cache; не запускать unrelated pipeline stages; сохранить errors/results/CLI contract и old complete generation.

**Проверка:** Native parser→config→actual async stage, local allowed connector; compare full/direct outcomes and receipts. NOT_RUN.

**Неопределённость:** Current source path verified; endpoint/profile scenario is source-derived counterexample, not executed production incident. Minimal helper extraction may require caller-owner review.

**Альтернативы:** Расширять sync content helper для async acquisition — лишний API/semantics риск; Только off resumeFalse — частичный ремонт; Existing async pipeline с stages={harvest}, либо узкий общий harvest dispatcher, использующий тот же admission.


### FA-03 — verified_specification_ambiguity / medium

**Пакеты/приёмка:** SCL-01, SCL-03; REQ-SCL-01-01, TEST-SCL-01-01, TEST-SCL-01-02, E02-I09-A-B02.

**Проблемное предписание:** SCL-01 §5.1 говорит добавить offline cached admission «после initial guard», не устраняя live resolution перед cache lookup.

**Доказательство:** P/02_Пакеты/SCL-01.md:53 (solution point1); src/polisyos/scholar/search/fetcher.py:42–45; src/polisyos/scholar/search/security.py:76–116; tests/unit/scholar/search/test_fetcher_security_cache.py:60–106 fixes successful DNS for both calls.

**Контрпример:** Persisted permitted page с достаточными exact raw/profile facts; DNS сейчас unavailable либо endpoint более не существует. Existing _resolve_fetch_target raises до cache.get, поэтому законное offline reuse не выполняется. Existing positive cache test фиксирует successful DNS и пропускает такую неверную реализацию.

**Предпочтительное решение:** Порядок: offline initial URL admission→cache lookup/current saved-chain MIME/size/profile admission→return eligible cached; только при permitted fresh fetch выполнять live DNS→pinned transport. Pure policy checks literal private IP, syntax/domain/port without DNS; access policy продолжает действовать.

**Замена REQ/decision:** REQ-SCL-01-01 уточнить: «Проверка пригодного saved snapshot не зависит от нового DNS/network access; current offline URL/domain/literal-IP/MIME/size/reuse policy применяется до выдачи. Live resolver вызывается только на разрешённом fresh fetch».

**Различающий TEST:** Persist cache через actual producer/reload; DNS/socket/transport callbacks затем raise-on-call. Unchanged permitted page returns cached exact text/rawref и network0. Изменённая domain/MIME/size policy отказывает тоже network0. Miss/explicit refresh сохраняют live DNS/peer/redirect negative controls.

**Owner:** SCL-01 security/admission, SCL-03 sole coordinated fetch_profile writer.

**Что сохранить:** Не использовать DNS today как historical peer proof; не разрешать live private fetch; не стирать весь cache по одному unusable entry. Public-web label не rights.

**Проверка:** Native async public fetch/find + real persisted cache; separate allowed local TLS qualification. NOT_RUN.

**Неопределённость:** Intent пакета уже верен; finding об incomplete placement instruction. Не заявляется SSRF exploit или обязанность автоматически fetch при cache gap.

**Альтернативы:** Сохранить live DNS на cached reads — availability/dependency regression; Пропустить все checks на hit — запрещённый bypass; Разделить pure URL policy и live target resolution в existing security owner.

**Первоисточники:** [HTTP transport / custom transports / retries](https://www.python-httpx.org/advanced/transports/).

### FA-04 — optimization_suggestion / low

**Пакеты/приёмка:** FED-01, UQS-01; FED-01 §5, DEC-FED-01-01, E02-I07-B-B02.

**Проблемное предписание:** Custom exact binary-rational production accumulator выбран без явного сравнения с подходящим statistics.mean в locked Python.

**Доказательство:** P/02_Пакеты/FED-01.md:80–82,110; src/polisyos/fabric/connectors/federation/composer.py:1715–1727; src/polisyos/fabric/connectors/federation/resolver.py:323–365; CPython v3.14.0 statistics source cited in LIB-FA-01.

**Контрпример:** Не дефект результата предложенного exact algorithm: тот корректен при реализации. Но новый integer rounding/normalization код может повторить существующую stdlib, создать ownership/test burden и второй numerical implementation.

**Предпочтительное решение:** Common finite_binary64_mean валидирует допустимые конечные Python float значения и использует statistics.mean; midpoint тот же owner на двух central floats. Keep independent rational oracle (не statistics.mean в expected). Custom algorithm оставить лишь при измеренном выгодном tradeoff+equivalence.

**Замена REQ/decision:** DEC-FED-01-01: «Сначала квалифицировать CPython3.14 statistics.mean для narrow finite-binary64 API. Собственный accumulator допускается при документированной correctness/performance причине; API/owner/consumer semantics остаются прежними».

**Различающий TEST:** Existing TEST-FED-01-01 numeric matrix дополнить stdlib-vs-independent rational comparison, permutations и group-size timing/allocations; reject nonfinite before library; no underflow zero hidden by finite-only fallback.

**Owner:** FED-01 sole common/numeric_reductions.py writer; independently coordinated with foundry_numeric reviewer for UQS.

**Что сохранить:** statistics.median и fmean не substitute; preserve absence/categorical/cell lineage and scalar MEDIAN selection rather than synthesized source.

**Проверка:** Independent host3.12 calculator saved; target3.14 native test and performance pending. No new dependency.

**Неопределённость:** Recommendation, not blocker. Cost superiority not measured; Python implementation-specific exact behavior must remain pinned/tested.

**Альтернативы:** Custom scaled numerator accumulator; Fraction per row reference; statistics.mean behind finite float wrapper; numpy mean/scaled fsum/fmean — не full-domain replacement.

**Первоисточники:** [mean146–165; fmean168–205; median304–324; _sum1322–1373](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py).

### FA-05 — optimization_qualification / low

**Пакеты/приёмка:** EMB-01, EMB-02, EMB-03, DFI-03; REQ-EMB-02-03, REQ-DFI-03-04, E02-I08-B.

**Проблемное предписание:** Native warm selected-query acceptance не требует разделить semantic correctness от стоимости full content revalidation; нельзя выводить scalable free-grow только из cached index.

**Доказательство:** src/polisyos/data_forge/domains/catalog/knowledge/store.py:301–345,428–476,637–660; src/polisyos/data_forge/kernel/embeddings.py:1217–1236,1250–1340; src/polisyos/data_forge/domains/legal/runtime_material.py:271–301,649–739.

**Контрпример:** Warm _dataset_index is reused лишь после whole catalog text projection и selected-generation file hashes/NPZ work. При растущем N query может иметь линейную validation cost даже если ANN быстрое. Это code-derived cost bound, не измеренный SLA breach.

**Предпочтительное решение:** Только measurement-first: снять cold/warm breakdown IO/hash/projection/encode/knn на workload ladder. Никакого нового lease implementation mandate. При установленной performance цели отдельно оценить существующий immutable owned opened-generation/read-session lifetime; если immutability не доказана, оставить полные content checks.

**Замена REQ/decision:** Дополнение к cost qualification: «Публиковать cold/warm costs и bytes read, отдельно identity revalidation и ANN. Ускорение не заменяет content-bound identity на stat-only; выбранный trusted immutable lifetime и invalidators должны быть явными».

**Различающий TEST:** Same query repeated at N,2N,4N; cold process and warm handle; read-byte/hash-call counters+RSS/wall. Same-stat replace, in-place mutation, delete/withdrawal, selector swap during query still denied/renewed; unrelated stable generation remains useful.

**Owner:** EMB-02 common reader/publisher; DFI-03 receipt cost; Legal runtime owner сохраняет свой более узкий trusted-process scope.

**Что сохранить:** Не скрывать freshness checks в memoization; не увеличивать capability claim из-за speed. No unmeasured SLO/automatic redesign.

**Проверка:** Future controlled benchmark native3.14 only; no benchmark executed. Operation count evidence separate from actual throughput.

**Неопределённость:** Observed algorithmic work, empirical severity unknown. Existing read guard implementation may enable safe amortization, must inspect exact lease guarantee before change.

**Альтернативы:** Сохранить текущую полную revalidation; mtime/size-only hash cache — неприемлемо для данного threat model; Immutable owned opened-generation lease/read session с bounded trusted lifetime; Переход на другой vector database — не устраняет identity obligation.

**Первоисточники:** [Python API: set_ef; get_items cosine normalized; thread safety; M/ef_construction](https://github.com/nmslib/hnswlib), [Few searches; exact Flat; HNSW memory/accuracy tradeoff](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index).

### FA-06 — capability_acceptance_gap / medium_for_stronger_retrieval_claim_not_repair

**Пакеты/приёмка:** EMB-01, EMB-02, EMB-03; TEST-EMB-01-01, TEST-EMB-02-03, TEST-EMB-03-02, E02-I08-B.

**Проблемное предписание:** «Полезные search_candidate results» в owned serving witness не имеет finite relevance oracle; native vector correspondence и один self-query не доказывают search capability на новых compatible ресурсах.

**Доказательство:** P/02_Пакеты/EMB-01.md:32–40 explicitly excludes ANN recall/model quality; P/02_Пакеты/EMB-03.md:40–46; tests/unit/remediation/test_emb_02.py:399–488 single ds-1 self-query; Vision §8.2 T7 and §5 Rule12.

**Контрпример:** Всегда возвращать первый admitted ID или выбирать только lexical overlap: одноэлементный corpus и статус search_candidate проходят, но новый релевантный resource не находится. Correct stored vectors также не исключают query-independent routing/top-k bug.

**Предпочтительное решение:** Два уровня: (a) deterministic non-tied vectors с независимым exact dot/cosine expected ranking через actual binary HNSW/public reader; (b) маленький заранее размеченный actual-model corpus с distractors, paraphrases, multilingual/long-text cases внутри declared profile, frozen holdout. Новый compatible resource добавляется только data+metadata, без case-ID code. Exact cosine является ground-truth reference; конкретный expected HNSW result принимается лишь для finite non-tied corpus≥3, k<N и объявленного ef/native profile, не как universal exact ANN guarantee. Reuse existing GL/G5 recall/freshness evidence pattern (legal_mandate_search.py:1867–1990; tests:905–960) и E02-X03/X04 join where contract supports; не создавать GL legal ledger из embedding output. Это не gate для локального publisher repair.

**Замена REQ/decision:** E02-I08-B дополнить: «Native index integrity принимается отдельно от retrieval utility. Для utility объявить corpus/query scope, заранее fixed relevance labels и threshold, держать holdout вне настройки. Отказ known-groundable seed учитывается как missed retrieval, не доказательство отсутствия знания».

**Различающий TEST:** Three+ docs, nontrivial order with k<N; insert new relevant doc after build via normal reissue and fresh consumer finds it. Independent exact top-k oracle for synthetic vectors. Actual-model known-answer labels set before run; perturb irrelevant IDs/order; record recall@k, false abstention, latency. Withdrawal removes only dependent hit, text fallback still exercised.

**Owner:** EMB-01 compute, EMB-02 reader, EMB-03 owned legal serving; shared E02-I08-B avoids three model loads.

**Что сохранить:** Не превращать semantic proximity в verified legal relation; no all-model/all-domain gate for local publisher fix. Existing explicit exclusion remains honest if no quality witness available.

**Проверка:** Mechanism tests native; semantic qualification with provided local assets and authorized corpus only. Both NOT_RUN; no proposed arbitrary universal numeric threshold.

**Неопределённость:** Packet explicitly bounds recall claim; this is stronger capability evidence gap, not concealed breach of current repair acceptance.

**Альтернативы:** Ограничить claim только index wiring/custody; Добавить независимый exact cosine topology witness + finite semantic retrieval qualification; Требовать универсальное legal understanding — несоразмерно.

**Первоисточники:** [Python API: set_ef; get_items cosine normalized; thread safety; M/ef_construction](https://github.com/nmslib/hnswlib), [Few searches; exact Flat; HNSW memory/accuracy tradeoff](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index), [constructor46–85; encode normalize_embeddings; get_max_seq_length530–537](https://raw.githubusercontent.com/UKPLab/sentence-transformers/v2.7.0/sentence_transformers/SentenceTransformer.py).

### FA-07 — profile_qualification_correction / low

**Пакеты/приёмка:** EMB-01, EMB-02, EMB-03; LANE-08 P-SEARCH, E02-I08-B.

**Проблемное предписание:** LANE-08 P-SEARCH упоминает GP backend/test_gp_resume_witness, но native embedding profile требует HNSW и отдельно rag-local/model assets; общий research/all не гарантирует последний.

**Доказательство:** P/03_Интеграция/LANE-08.md:18; policy-engine/pyproject.toml optional vector-search/rag-local/research/all; policy-engine/uv.lock hnswlib0.8.0 sdist, sentence-transformers2.7.0; src/polisyos/data_forge/domains/legal/runtime_material.py:655–706.

**Контрпример:** Runner с P-CORE+research может иметь hnswlib, но не ST2.7/локальные assets; GP backend не делает legal encoder available. Такой missing environment не должен выглядеть как behavioral FAIL или silently replaced fake encoder.

**Предпочтительное решение:** Уточнить profile manifest без установки: P-INDEX native hnswlib0.8 build ABI/platform; P-LEGAL-OWNED adds rag-local exact runtime+local model inventory. GP удалить из lane8 prerequisites если ни одна выбранная проверка его не использует.

**Замена REQ/decision:** Profile requirement: «Записывать фактические lock groups/native backend versions/platform; owned Legal witness требует заранее доступные проверенные local assets. Missing prerequisite→NOT_QUALIFIED, не PASS fixture и не product defect».

**Различающий TEST:** Preflight read-only inventory actual imports/runtime files plus native tests later; fake encoder qualifies only compute wiring. At least one separately declared supported3.14 native environment.

**Owner:** Lane8 integrator; EMB-03 runtime material owner; packaging owner for native ABI if required.

**Что сохранить:** Не навязывать все platforms/OS или install/download; не считать отсутствие wheel доказательством несовместимости.

**Проверка:** Read-only package/asset provenance preflight; execution not authorized in this review.

**Неопределённость:** Lock parsed; native build compatibility not tested; exact environment may already be provisioned elsewhere.

**Альтернативы:** Один универсальный P-SEARCH со всеми extras; Отдельные finite P-INDEX/P-LEGAL-OWNED profiles.

**Первоисточники:** [constructor46–85; encode normalize_embeddings; get_max_seq_length530–537](https://raw.githubusercontent.com/UKPLab/sentence-transformers/v2.7.0/sentence_transformers/SentenceTransformer.py), [Python API: set_ef; get_items cosine normalized; thread safety; M/ef_construction](https://github.com/nmslib/hnswlib).

## Вердикт каждого пакета

Здесь пути от `policy-engine/`; сокращённые исторические references P означают immutable executor baseline. Ни retain, ни bounded qualification не означает продуктовый PASS.

### UDF-01 · LANE-07 · retain

**Техническое решение:** Lazy facade вместо очередного relocation — правильный локальный ремонт: contract-only import не должен активировать все stages. Dynamic activation должен возвращать canonical functions, а не copied wrappers. D4 exact deny bytes и первые5 positional полей StageBuildResult — реальные ABI, inputs extension не основание ломать callers.

**Достоверность проверки:** Cold subprocess важнее sys.modules assertion после warmed import. Existing D4 test производит payload и вручную complete manifest: он полезен для parser/CAS seam, но не полный admitted orchestration. Packet правильно требует actual stage→binding consumer; не заменять expected byte literal production formatter.

**Перенос/free-grow:** Второй builder активируется тем же facade механизмом без case-ID ветки. Здесь не нужен второй предметный проект ради lazy import; существенный consumer transfer общий I07-A.

**Стоимость/совместимость:** PEP562/existing lazy pattern без dependency; измерять cold import dependency closure, не только import elapsed. Поддержать introspection/explicit aliases и failed first import retry.

**Граница:** Qualification-only части не разрешают удалять wrappers по историческому имени.

**Код/тесты:** `src/polisyos/data_forge/domains/ukraine/builders/__init__.py:1–88`; `src/polisyos/data_forge/domains/ukraine/builders/governance_handoff.py:1–52`; `tests/unit/remediation/test_udf_01.py:133–164`.

### OBS-01 · LANE-07 · retain

**Техническое решение:** Calendar.monthrange и source-owned period parsing соответствуют календарной задаче; не заменять общим fuzzy date parser, способным угадывать missing дату. Inclusive bounds, coarse/fine precision и positional duplicate index semantics важнее pandas index labels.

**Достоверность проверки:** Leap2024/ordinary2023/Q2/year — аналитические independent expected dates; malformed/None и duplicate rows distinct. Missing не measured zero. Historical reevaluation обязана предъявить finite actual inventory, а не произвольный сегодняшней fixture. Хорошо, что пакет не объявляет реконструкцию без periodID.

**Перенос/free-grow:** Новые корректные period strings в уже объявленной grammar проходят без dictionary per date. Transfer irregular fiscal calendar — новая семантика и отдельный owner/profile, не обязанность этого patch.

**Стоимость/совместимость:** Unique-period precompute сохраняет O(U) parsing+O(N) placement; нет смысла добавлять dateutil ради finite grammar.

**Граница:** Calendar correctness не source authenticity; native Parquet/gate I07-A остаётся обязательным.

**Код/тесты:** `src/polisyos/data_forge/domains/ukraine/builders/observation.py:96–275`; `tests/unit/remediation/test_obs_01.py:43–125`.

### UDF-02 · LANE-07 · bounded qualification

**Техническое решение:** Existing IO/bindings extraction уже есть; повторная архитектурная перестройка не оправдана. Exact legacy JSON bytes, NPZ/Parquet semantic reader и D0–D3 prepared input bindings нужно квалифицировать на реальном producer/consumer.

**Достоверность проверки:** Formatter unit and synthetic payload shape недостаточны. Actual FileSystemCAS+prepare_input_bindings/build consumer должны связать selected refs, а не only expected mapping. Existing mocked atomic writer failure доказывает propagation, не old-file durability: native fail-before-replace если заявляется атомарность.

**Перенос/free-grow:** Добавить второй compatible D0–D3 source manifest с новым schema/data и explicit declared binding, без special country/source branch. Не превращать synthetic input в empirical observation.

**Стоимость/совместимость:** JSON+NPZ existing writer достаточен; Parquet current writer не следует автоматически объявлять atomic как JSON. No new serialization framework.

**Граница:** Нужно назвать конкретный принимающий consumer/config в execution manifest; whole Scientist/Foundry реализованность из IO roundtrip не следует.

**Код/тесты:** `src/polisyos/data_forge/domains/ukraine/builders/io.py:40–96`; `src/polisyos/foundry/data_plane/bindings.py:1373–1515,1943–2075`; `tests/unit/remediation/test_udf_02.py:63–161`.

### OBS-02 · LANE-07 · retain

**Техническое решение:** Disk-captured immutable read + bounded Arrow batch + prefix accounting соответствует replay при mutation/rebatch. Копия на диск дороже прямого parquet scan, но необходима для выбранного неизменного источника; mapper failures не должны провоцировать reader fallback и дублирование accepted prefix.

**Достоверность проверки:** Сильные controls уже предусмотрены: exact row IDs, same-size restoredmtime/ABA, confirmed vs pending counters и actual reader fault. Wrong implementation «dedupe по value» проходит sum/count-only oracle, но ломается distinct IDs with equal values; это следует сохранить.

**Перенос/free-grow:** Transfer меняет batch/rowgroup boundaries и duplicate index layout, а не только seed. Второй compatible table с nullable numeric и variable-width strings испытывает тот же snapshot owner.

**Стоимость/совместимость:** Arrow22 iter_batches не whole-file pandas; O(file) temporary storage/free-space admission, peak batch memory и prefix reread measurable. DuckDB Arrow handoff — optional future measured optimization, не нынешний prerequisite.

**Граница:** No global exactly-once/no power-loss durability из одного retry. Disk full должен оставить old output и close captured handles.

**Код/тесты:** `src/polisyos/data_forge/domains/ukraine/builders/sources.py:1420–1593`; `tests/unit/remediation/test_obs_02.py:248–379`.

### UDF-04 · LANE-07 · retain

**Техническое решение:** Preflight unavailable до server guard разумен: absence checkout — structural capability, не попытка обойти запрещённый action. Workspace root и artifact root отдельны; callbacks принадлежат Ops. Installed C7 receipt требует real same-child collection/setup/call/teardown, не stdout passed.

**Достоверность проверки:** Подходящий positive fixture с actual callback рядом с missing-root denial предотвращает always-unavailable. Installed console/import proof отдельно от rendered shell command. Fake runner допустим для cwd/env composition, но не для receipt lifecycle.

**Перенос/free-grow:** Transfer checkout vs installed/no-checkout forms имеет смысл; не требовать реального provisioning всех окружений для diagnostic fix.

**Стоимость/совместимость:** Existing pathlib/packaging composition enough. Не вычислять repo через parents[N], не добавлять runtime registry.

**Граница:** Actual deployment requires отдельное разрешение и target evidence. Review ничего не запускает.

**Код/тесты:** `src/polisyos/data_forge/domains/ukraine/orchestrator.py:442–475`; `src/polisyos/data_forge/domains/ukraine/server.py:57–137`; `tests/unit/remediation/test_udf_04.py:361–413`.

### UDF-05 · LANE-07 · targeted revision

**Техническое решение:** Role-aware assembler выбран правильно: scalar/aggregate согласованность, equal legacy duplicate vs conflicting value, metadata preservation и reserved evidence last. Но exact index validator поставлен после before np.asarray — FA-01. Исправление должно захватить raw scalar identity.

**Достоверность проверки:** Mixed big int/integral float discriminator обязателен. Existing TEST02 homogeneous extrema недостаточны; full public DTO+historical+candidate covers error translation. Candidate helper патчит unrelated gates — его нельзя выдавать за admitted full orchestration; пакет честно отмечает это.

**Перенос/free-grow:** Два state axes разного размера и materialized entrants/donor дают reusable pure aging. Изменить не только labels: разные positive flow/zero entrant structure и optional donor disposition.

**Стоимость/совместимость:** Никакой новой unit/index library. O(N) source admission+canonical int64. Signed record IDs сохраняются; state IDs range ограничен.

**Граница:** Inventory receipt доказывает captured inputs, не научную пригодность. Прогноз/калибровка на synthetic fixture остаются conditional.

**Код/тесты:** `src/polisyos/data_forge/domains/ukraine/demography/__init__.py:176–380`; `src/polisyos/data_forge/domains/ukraine/static_aging.py:14–49`; `P/02_Пакеты/UDF-05.md §5.3`.

### FED-01 · LANE-07 · targeted revision

**Техническое решение:** Numeric contract сильный: finite extremes/subnormal/cancellation, MEDIAN validation до singleton, distinction arithmetic point vs actual source selection. Предпочтительнее existing statistics.mean за common wrapper, чем новая arithmetic implementation (FA-04). Custom exact algorithm сам по себе не ошибочен.

**Достоверность проверки:** Expected exact rational result независим; вычисление expected тем же helper запрещено. Три sources/second JOIN/persisted fresh reader проверяют cell lineage, repeated keys, null/cardinality. Wrong shared producer attribution проходит numeric-only asserts, но не cell-origin matrix.

**Перенос/free-grow:** Поменять primary priority, secondary overlap и missingness, не только values; holdout с source names вне fixtures и одними контрактами. Candidate composition не зависит от эмпирической source independence.

**Стоимость/совместимость:** Common stdlib3.14 wrapper, group cost измерить; mean streamable, median требует central selection. Bounded audit не означает full composition O(1) memory.

**Граница:** Scalar MEDIAN выбирает действительный admitted cell, не synthetic median source. Не менять tolerance/tie policy под numeric test.

**Код/тесты:** `src/polisyos/fabric/connectors/federation/resolver.py:95–145,323–365`; `src/polisyos/fabric/connectors/federation/composer.py:1612–1778`.

### FED-02 · LANE-07 · retain

**Техническое решение:** Schema-first typed empty UNION и one bounded audit collector решают реальные дефекты без новой relational engine. Declared nullable schema-only column должна создаваться до pd.concat templates; no-sources отличается от lawful empty sources.

**Достоверность проверки:** Full typed schema through SQL fresh reader + summary/full/none equal results и full conflict counts сильнее len0/count-only. Heap tiebreaker stable sequence не должен сравнивать MergeLog payload. Transient allocation census полезен, но не RSS/latency proof.

**Перенос/free-grow:** Transfer repeated keys+secondaries with different priority and unused source; index once per used secondary. Новый declared field без rows — решающий schema transfer.

**Стоимость/совместимость:** Сохранить pandas2.3 current ABI; DuckDB rewrite только по measured need. Per-composition lazy indexes не global mutable cache.

**Граница:** Schema authority не утверждается inferred pandas dtype; no-source refusal не считается lawful empty positive.

**Код/тесты:** `src/polisyos/fabric/connectors/federation/composer.py:634–775`; `tests/unit/remediation/test_fed_02.py:115–205,661–785`.

### CAL-01 · LANE-07 · retain

**Техническое решение:** Normalize paired source axis до inferred linspace и equal-length shortcut — правильное место; np.interp сам не валидирует domain invariants. Unit/interval compatibility всей selected series, не unit первого record. Не навязывать Pint/global conversion: upstream declared conversion owner достаточен.

**Достоверность проверки:** Local _resample explicit target test уже может быть green при broken prepare_targets inferred branch: будущая suite правильно должна пройти public prepare_targets equal-length/inferred и compiler→optimizer. Oracle line y=2t+1 аналитичен; masks/IDs отдельны. Empty support/zero/fill различаются.

**Перенос/free-grow:** Transfer нерегулярная сетка, перестановка+переименование IDs, explicit reversed requested grid, другой unit объявленный upstream conversion. Не требовать generic model invention.

**Стоимость/совместимость:** Stable O(nlogn) sort и existing NumPy/JAX. Measurement compiler explicitlyfloat32, native profile tolerance/report должны быть dtype-aware; не утверждать binary64 precision всего model path.

**Граница:** Передача CAL-02 в I10-A нужна для optimizer/report sensitivity; target correctness не empirical model validity.

**Код/тесты:** `src/polisyos/foundry/calibration/preflight.py:63–109,230–308`; `src/polisyos/foundry/calibration/measurement.py:247–338`; `tests/unit/remediation/test_cal_01.py:196–248`.

### DFK-02 · LANE-08 · retain

**Техническое решение:** Catalog visibility не должна проходить executable connector projection. Исправить predicate через current selection owner, сохранив governed source config semantics; не отождествлять catalog-only с callable source.

**Достоверность проверки:** Explicit default vs [] vs None, seed closure и same-stat policy bytes контролируют реальные meanings. Wrong predicate alwaysTrue проходит один legal source, но должен сломаться excluded private/catalog-only/control source.

**Перенос/free-grow:** Второй catalog-only entry с иной source family добавляется data/profile без connector stub. Policy denied executable всё ещё denied; free-grow не значит обход access.

**Стоимость/совместимость:** Existing typed YAML registry достаточен; no second parser/list. Lazy YAML import и compatibility exports сохранить.

**Граница:** Catalog listing показывает discoverable, не executable/authority.

**Код/тесты:** `src/polisyos/data_forge/domains/catalog/registry.py:50–115`; `P/02_Пакеты/DFK-02.md all solution/tests`.

### DFI-01 · LANE-08 · bounded qualification

**Техническое решение:** Existing finite binding/context extraction уже выполнен, поэтому retain owners и квалифицировать actual three leaf groups. ContextVar правильнее module global overrides; scope restoration в finally нужно проверять при exceptions/cancellation.

**Достоверность проверки:** AST/import architecture tests не проверяют SQL write/manifests. Actual canonical caller с native DB и two concurrent bindings обязан выдавать раздельные outputs; second invocation after exception проверяет reset, а не только successful path.

**Перенос/free-grow:** Compatible source через finite existing bindings без добавления нового global alias. New unsupported semantics legitimate code extension, не бесконечный injection registry.

**Стоимость/совместимость:** MappingProxyType shallow — caller-owned mutable values надо использовать по объявленной lifecycle, не считать deep immutability. Не вводить heavyweight DI framework.

**Граница:** Нет нового root-cause fix без найденного mismatch; full LA038 closure включает callers and actual manifests.

**Код/тесты:** `src/polisyos/data_forge/domains/catalog/batch/_core_sources_ingest_contracts.py:1–210,289–370`; `P/02_Пакеты/DFI-01.md`.

### DFI-02 · LANE-08 · retain

**Техническое решение:** Потерянный empty_shards counter протянуть через actual aggregate. Facade stale delegate решается small weak identity bookkeeping либо stable forwarding with current owner lookup; не broad monkeypatch broadcast и не дублирование API функций.

**Достоверность проверки:** Counter test должен получить actual complete-empty shard а не fake returned dictionary; existing unit mocks useful wiring only. Два сохранённых wrapper handles до и после owner change различают stale closure, один latest wrapper — нет.

**Перенос/free-grow:** Transfer explicit binding, default binding и concurrent scope with cancellation. Не поддерживать произвольное reflective private symbol patching ради теста.

**Стоимость/совместимость:** Weak refs избегают unbounded retained wrapper list; stable dynamic lookup дешевле, но preserve exact dispatch/exception identity.

**Граница:** empty_shards — metric, не completeness evidence без selected denominator. Canonical writers unchanged.

**Код/тесты:** `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py:1–197`; `src/polisyos/data_forge/domains/catalog/batch/core_sources/api.py:1096–1139`; `tests/unit/remediation/test_dfi_02.py:1–178`.

### DFI-03 · LANE-08 · targeted revision

**Техническое решение:** Strict nonnegative integer counts (not bool/coercion) и content-bound resume правильны. §5 содержит неподдержанный sync helper; off-only alternative не покрывает smart direct admission. FA-02: existing async finite-stage route предпочтителен.

**Достоверность проверки:** Endpoint/profile mutation при прежнем source.name и coherent old payload must force acquisition. Only config.resume assertion не проверяет stage work; TEST02 требует counted connector+fresh receipt. [] required outputs vs None — реальный all([]) adversary.

**Перенос/free-grow:** Два источника с complete_empty/nonempty; same bytes/newmtime reuse, same stat/newbytes miss. Transfer через новые source metadata, не fixture filename.

**Стоимость/совместимость:** Whole selected hashing costly but preserves threat model; measure separately, immutable lease only if proved. Core/QC remain live noncacheable.

**Граница:** Off не означает запрет независимого lawful transport cache. Native build not run.

**Код/тесты:** `src/polisyos/data_forge/domains/catalog/batch/pipeline.py:492–616,1240–1283,1392–1425`; `src/polisyos/data_forge/domains/catalog/batch/harvester.py:1069–1174,1255–1278`; `src/polisyos/data_forge/domains/catalog/batch/cli.py:79–106`.

### EMB-01 · LANE-08 · bounded qualification

**Техническое решение:** Existing shared encode kernel хороший reuse: разные Academic/Catalog text projections остаются domain-owned, matrix/index normalization и dtype общие. Re-extract no need. Dimension from actual encoder4 vs fallback99 полезно отличает silent pad.

**Достоверность проверки:** Настоящие DuckDB/NumPy/HNSW нужны вместо JSON recorder; deterministic encoder допустим только wiring. Пакет честно не доказывает model quality/ANN recall. Дополнительный topology query oracle делает search wiring более различающим, но scientific quality отдельно.

**Перенос/free-grow:** Text preparation profiles и ID collision controls существеннее другого seed. Добавить compatible corpus без domain routing в kernel; retain separate SQL truncations.

**Стоимость/совместимость:** M16/ef_construction200 preserved; set_ef100 after load exists. vector-search native build3.14 отдельно; не ставить latest library ради ремонта.

**Граница:** Current selected ordering сознательно canonical, legacy byte order иной. Unbound encoder может produce candidate, не reuse authority.

**Код/тесты:** `src/polisyos/data_forge/kernel/embeddings.py:349–463,1118–1182`; `P/02_Пакеты/EMB-01.md:32–76`.

### EMB-02 · LANE-08 · retain

**Техническое решение:** Перед selector switch вызвать существующую semantic admission — оптимальный небольшой fix. Hashes не видят coherent but wrong index vectors; common staged validator нужен, selected flag forge не нужен. Postcommit projection error не rollback уже committed selector.

**Достоверность проверки:** Coherent inventory wrong vector до commit — сильный counterexample, лучше простой tamper checksum. Fresh reader after each failure phase и valid replacement исключают always-reject. Both warm/fresh effective-text mutation and beyond-truncation positive keep exact model-input semantics.

**Перенос/free-grow:** Перестановка IDs/добавление/withdrawal и второй domain reader показывают shared publisher. Не общий третий generation framework.

**Стоимость/совместимость:** Warm revalidation cost FA-05; не ослаблять currentness ради speed. HNSW stored normalized cosine vectors correspondence requires tolerance, not arbitrary byte identity.

**Граница:** No fsync/powerloss claim from os.replace; readiness/QC distinct from valid index.

**Код/тесты:** `src/polisyos/data_forge/kernel/embeddings.py:349–463,1118–1182,1217–1412`; `src/polisyos/data_forge/domains/catalog/knowledge/store.py:301–378,428–476`; `tests/unit/remediation/test_emb_02.py:95–127,399–488`.

### EMB-03 · LANE-08 · bounded qualification

**Техническое решение:** Legal incremental per-record text/assets/tokenizer identity следует сохранить, а не менять на Academic full rebuild или ID-only cache. Owned runtime positive served query действительно добавляет способность; source-owned finite CPU1024/ST2.7 profile допустим старт, не вечный hardcoded universe.

**Достоверность проверки:** Three tables, append/change/withdrawal/revision invalidators и actual owned model без mocked gate сильны. Но «полезный» результат требует relevance target/holdout, FA-06. Runtime owner trusted-process assumption не доказывает защиту от hostile concurrent mutation всех globals.

**Перенос/free-grow:** Второй corpus с иными legal entities/facts/provisions и paraphrase query через тот же профиль. Новый model backend — новая semantic/runtime qualification, не обязан автоматически пройти.

**Стоимость/совместимость:** Optional rag-local и provided assets обязательны; tiny corpus still full model load/RSS. Long text truncation query adversary может выявить false abstention. No downloads in review.

**Граница:** Candidate similarity не verified source relation; text fallback остаётся полезным, но не заменяет требуемый owned-vector positive.

**Код/тесты:** `src/polisyos/data_forge/domains/legal/runtime_material.py:568–577,649–739`; `P/02_Пакеты/EMB-03.md:31–75`; `src/polisyos/data_forge/kernel/embeddings.py:349–463,1118–1182`.

### ING-01 · LANE-08 · retain

**Техническое решение:** Finite pre-admitted request_hash→unique namespace map устраняет first namespace selection без filesystem guessing. Identical HTTP request across two sources действительно неоднозначен без request-scoped identity; bounded upfront unsupported честнее случайного routing.

**Достоверность проверки:** Два real namespaces, unknown request, ambiguity до ingestion и no live fallback обязательны. Различать successful fetch count и actual persisted transform/PII/graph consumer. Replaying recorded bytes не доказывает fresh provider computation.

**Перенос/free-grow:** Второй source namespace с иной request method/body/schema; compatible manifests data-only. Для одинаковых requests нужен новый typed source boundary, не ad-hoc URL suffix.

**Стоимость/совместимость:** Map O(fixtures), no network service/new router. Content canonicalization owner existing; payload historical bytes не переписывать под old ID.

**Граница:** Finite approved adapter scope only; no arbitrary production access or global exactly-once.

**Код/тесты:** `src/polisyos/fabric/data_plane/modes.py:1124–1204`; `src/polisyos/fabric/data_plane/replay_store.py:96–114`; `src/polisyos/fabric/connectors/testing/simulator.py:344–405`.

### ING-02 · LANE-08 · retain

**Техническое решение:** Initial failure checkpoint должен иметь admitted source/clock/schema identities и empty operator state, а не mutated observed progress. Малый helper identity fields корректнее клонирования live accumulator. Actual committed frontier остаётся единственным resume basis.

**Достоверность проверки:** Independent raw byte/window oracle и actual CAS writes хороши; BaseException injection не OS process death, поэтому separate worker-kill required только для declared crash recovery. First-before-commit failure плюс actual fresh reader решает конкретный gap, not only state DTO.

**Перенос/free-grow:** Count/tumbling/sliding/session и uneven rebatching должны сохранять window memberships/contributor refs; new dataset/source identity через contracts. Withdrawal affected contributor invalidates dependent window, independent retained.

**Стоимость/совместимость:** Checkpoint snapshot O(retained state) memory+IO, horizon bounds declared. No parallel journal/recovery service.

**Граница:** Source witness identity не сама causal authority; timed event clocks require same admitted semantic profile.

**Код/тесты:** `src/polisyos/fabric/data_plane/streaming.py:1540–1588,3049–3113`; `tests/unit/fabric/data_plane/test_e02_c_streaming_oracle.py:805–945`.

### ING-03 · LANE-08 · retain

**Техническое решение:** Owned per-occurrence serialized byte accounting правильно заменяет repeated full sum; id(dict)-only memoization неверна при reuse/mutation. CATEGORY allowed_values is not None отличает empty allowed set от unconstrained; existing quarantine owner достаточен.

**Достоверность проверки:** Exact cap+one byte, repeated identical object occurrences, mutate-after-admit, preview abort, restored state counter independently recomputed. Wrong one-size-per-unique-ID cache проходит unique-row fixtures; explicit repeated reference distinguishes. Window-closing transition must remain admitted without arbitrary forced flush.

**Перенос/free-grow:** Разные window types/variable-width Unicode fields, category[]=denyall vs None=any, UTC expiry after restart. Новая data value не новый branch.

**Стоимость/совместимость:** O(1) buffered_bytes не full loop O(N): _prune_row_refs scans buffer, preview copies containers. Не предлагать eviction cache для semantic live rows; no unimplemented spill success.

**Граница:** Operator serialized budget не process RSS. Counter/index metadata overhead отдельно measured; capacity refusal preserves frontier.

**Код/тесты:** `src/polisyos/fabric/data_plane/streaming.py:954–1054,1237–1270`; `src/polisyos/fabric/data_plane/schema_rows.py:23–115`.

### NET-01 · LANE-08 · retain

**Техническое решение:** Terminal cleanup task cancelled нельзя shield-await forever: inspect done/cancelled and unified settlement retaining owner/permit until real close. Caller cancellation after success сначала settles physical result, then propagates. Design uses existing lifecycle, not new cancellation framework.

**Достоверность проверки:** Watchdog timeout сам по себе не PASS: heartbeat progress, fd remains readable while pending, os.fstat closed after retry, new session acquisition then works. Fixtures must pass legitimate dedupe/source admission before reaching cleanup; removing gate ради finalizer недопустимо.

**Перенос/free-grow:** Two cancellation origins (caller vs owned task), same-session-key replacement and independent pending owners transfer mechanism, no source-specific cleanup branch.

**Стоимость/совместимость:** Python asyncio primitives adequate. Lock protects metadata, never physical disconnect await. No finite timeout can pretend actual FD close.

**Граница:** Primary provider/sanitizer error identity preserved; cleanup degradation separate, pending ownership explicit.

**Код/тесты:** `src/polisyos/fabric/connectors/pool.py:833–900`; `src/polisyos/fabric/data_plane/streaming.py:3114–3120`; `tests/unit/fabric/data_plane/test_stream_pool_physical_cleanup_oracle.py:146–260`.

### NET-02 · LANE-08 · retain

**Техническое решение:** Successful result feeds AdaptiveRateLimiter once after actual provider completion. Plain RateLimiter protocol не расширять обязательным callback. Success feedback exception нельзя перехватить как provider RateLimitError и повторить physical call.

**Достоверность проверки:** Actual wrapper+controlled clock matrix: 429 cooldown→success recovery, exception/cancel no success, fractional0.2/s and declared burst, stale circuit generation ignored. Mere call count misses recovered state; next admitted request time distinguishes.

**Перенос/free-grow:** Different connector IDs/tenants sharing intended owner vs isolated profile; registry eviction with pinned leases and late completion. No distributed quota claim.

**Стоимость/совместимость:** Existing limiter+registry sufficient; tenacity retry cannot replace feedback/generation semantics. Relative sleep sums не absolute deadline.

**Граница:** Provider result/accounting remains primary; adaptive policy unchanged except missing successful feedback.

**Код/тесты:** `src/polisyos/fabric/connectors/resilience/rate_limiter.py:380–468`; `P/02_Пакеты/NET-02.md full local tests`.

### SCL-01 · LANE-09 · targeted revision

**Техническое решение:** Current cached admission и per-attempt deadline — нужный ремонт, но offline ordering явно исправить FA-03. Общий raw transport сохраняет numeric destination/peer/hostname SNI; rewrite HTTP stack без причины не оправдан.

**Достоверность проверки:** Positive legal cached reuse+prohibited final/redirect/MIME/size рядом. Offline DNS-failure control missing in text; add. Deadline injected clock first ends t2 budget1 excludes second; positive failover within budget excludes always-stop. Async cancellation physical worker distinct.

**Перенос/free-grow:** Second compatible profile with different MIME/domain/limits and third-party legacy list provider — не просто another URL. Unknown legacy cache fact explicitly gap/allowed refresh.

**Стоимость/совместимость:** HTTPX phase timeouts no wall guarantee; outer monotonic async deadline plus existing retained worker owner. No live network in review.

**Граница:** Candidate schema1.1 remains decision, not implied migration; snippet availability not source permission.

**Код/тесты:** `src/polisyos/scholar/search/fetcher.py:31–103`; `src/polisyos/scholar/search/security.py:76–180`; `src/polisyos/scholar/search/providers.py:118–218`; `tests/unit/scholar/search/test_fetcher_security_cache.py:60–106`.

### SCL-03 · LANE-09 · retain

**Техническое решение:** Carry existing typed raw ArtifactRef through manual bytes normalization activates existing acquire recheck; второй CAS/SourceSpec type не нужен. Fetch profile must come from actual applied transport arguments on cache and no-cache routes, not populated test DTO.

**Достоверность проверки:** Native API→CAS→docs/fragments/claims→fresh reader решительно лучше sentinel before publication. v1 then URLv2 without refetch and explicit refresh lineage distinguish cache from accidental fresh retrieval. Corrupt/missing blob must not reconstruct from snippets.

**Перенос/free-grow:** Два документа с повторяющимися фразами и Unicode normalization + multiple snippets; второй applied profile no code branch. Span coordinate system должен быть extracted text, не naive raw-byte offset.

**Стоимость/совместимость:** Store full raw bytes once; exact profile metadata inexpensive. Native parser/backend qualification separate for HTML/PDF, не promise arbitrary MIME.

**Граница:** Fragment substring proves extraction fidelity, not truth/entailment/copyright rights. Source-bound non-URL manual bytes remain functional.

**Код/тесты:** `src/polisyos/scholar/search/fetcher.py:70–93`; `P/02_Пакеты/SCL-03.md §5`; `src/polisyos/scholar/discover/http_fetch.py:46–137`.

### LLM-01 · LANE-09 · retain

**Техническое решение:** Optional metrics/traces не могут скрыть response/mandatory post_record. Нужен safe optional context boundary preserving body exception, не blanket suppress. Existing ledger/accounting owner retain; no new money subsystem.

**Достоверность проверки:** Current native-style composition real FileBudgetLedger/local gateway useful, но _Tracer double не no-OTel fallback proof. Fault matrix enter/exit/attributes/status and mandatory audit failure must verify response/cause+next-spend gate, not only ledger already charged.

**Перенос/free-grow:** Async generate и sync invoke separate routes; normal/fallback tracer profile; missing usage unknown→reconciliation→positive next call. Другой controlled provider reply tests no constant fallback.

**Стоимость/совместимость:** OTel principle supports optional isolation, но core default includes SDK. Deliberately reduced fallback environment explicit. No external bill/invoice claim.

**Граница:** Unknown cost не zero; consumer reuse events не physical invoice. Body cancellation и mandatory error должны распространяться.

**Код/тесты:** `src/polisyos/scientist/orchestration/llm/budget_enforcer.py:221–291,424–471`; `src/polisyos/core/llm/traced_client.py:1301–1365`; `tests/unit/scientist/orchestration/llm/test_factory_cache_composition.py:229–329`.

### LLM-02 · LANE-09 · retain

**Техническое решение:** Finite six-role translator closure — обоснованное новое общее contract extension; не regex whitelist и не universal NL semantics. Exact prepared request binding + current owner/epoch per hit and once bounded revision re-admission avoids needless physical duplicate. Existing coordinator sufficient.

**Достоверность проверки:** One role at a time drift/absence/request/scope must force miss; unchanged literal URL/uncertainty content still hit. Provider fixture should parse actual serialized six-role payload and return role-sensitive valid brief, not constant answer; otherwise consumer wiring can ignore changed material. Cross-loop shared concurrent Future already meaningful.

**Перенос/free-grow:** Два materially different bundles (например fiscal transfer vs service provision) через same translator profile, no dossierID routing. New seventh live role remains unsupported until explicit contract extension; это честная граница, не free-grow дефект.

**Стоимость/совместимость:** One retry only; no locks around async provider/IO. Capture immutable payload bytes before dispatch; bind selectedCAS facts by current owner. No new distributed cache service. DefaultT0.1 stays; explicitT0/fallbackFalse qualifies reusable route.

**Граница:** T0/cache reuse не гарантирует cloud-model mathematical determinism или policy quality. Tool-calling NL request builder не покрыт. LLM-01 shared files sequential writer.

**Код/тесты:** `src/polisyos/scientist/orchestration/llm/prompt_cache.py:674–910`; `src/polisyos/scientist/policy_design/translator.py:48–61,188–233`; `src/polisyos/runtime/http/services/control/nl_pipeline.py:222–296`; `tests/unit/scientist/orchestration/llm/test_factory_cache_composition.py:330–430`.

## Сквозная способность LANE-07: источник → измерение/композиция → численный потребитель

**Вердикт:** убедительная архитектура ограниченной data capability; не доказанная эмпирическая модель. I07-A/B/C покрывают не один pipeline, а три связанных перехода. Их допустимо запускать отдельно, сохраняя exact shared generation. Не нужно превращать календарный fix в обязательный государственный production deployment.

**Что уже хорошо.** В mapping I07-A-B01..04 различены D4 handoff, календарь, captured reader и server admission. I07-B отдельно принимает demographic role/ID и federation cell producer. I07-C передаёт CAL-01 в CAL-02/реальный optimizer. Local-only import/historical/deployment matrices намеренно не считаются покрытыми одним shared TEST. Эти границы сохранить.

**Оставшийся разрыв:** слова actual consumer и usable measurements должны превратиться в named вызов, values и output effect. Обязательная source-bound цепь сама по себе допускает ошибочный consumer, который читает artifact, но игнорирует значения. Для UDF-05 есть FA-01; для numerical reduction — более простой библиотечный owner FA-04. Ни schema, ни hash не проверяет единицы/действительное наблюдение.

### Ограниченный улучшенный план приёмки

1. **Frozen вход и independent oracle.** Два маленьких synthetic source tables: monthly population stock и quarterly service-flow; они явно не реальные ведомственные данные. Даты/period bounds считать независимым calendar arithmetic, строки сверять по `(source, row ordinal, measure)` с сохранением двух одинаковых values. Для federation заранее вручную задать expected cell-producer matrix и rational arithmetic; для демографии — небольшой 2-state mass-balance и независимые expected entrant donor IDs. Не импортировать production reducer/resampler в expected.
2. **A — producer→snapshot→shards→merged panel.** Actual approved local raw fixture→Arrow Parquet→existing builder capture→mapper→DuckDB shards→manifest/receipt→fresh verified reader. Подменять можно только acquisition boundary; writer, hash, mapper, snapshot и merge нельзя. Для D4 отдельно actual builder emits exact payload, actual parser и binding consumer, explicit synthetic deny flags неизменны. UDF04 negative public route не выполняет subprocess; permitted structural route получает actual composed callback без deployment claim.
3. **B — values реально потребляются.** Current demographic inventory→captured public readers→build_static_aging_state→StaticAgingSimulationEstimator.pure_step; изменить один target/entrant value и проверить predicted finite expected output delta, не только source identity. Federation three sources→persisted composed artifact→новый registry/SQL reader→second JOIN. Сверить полную numeric/null/cardinality и producer matrix. Empty UNION с объявленным новым nullable column проходит тот же SQL readback.
4. **C — target к calibration.** Bundle→prepare_targets→существующий I10-A Calibrator и report. Аналитическая линия `y=2t+1`, irregular source order, explicit requested grid и mask; expected aligned targets из ручной формулы. Проверить objective/report меняется при допустимом data delta, а не лишь array shape. dtype/JAX64 capability записать; measurement compiler float32 не выдавать за binary64 exactness. CAL-02 owner отвечает за fitting semantics.
5. **Adversarial pairs.** Same-stat overwrite/ABA между batches; exception после confirmed prefix; mapper error отдельно от reader ImportError/OSError; period invalid vs absent; conflicting priors role; mixed big-int record ID; duplicate source times; mixed unit/interval; coherent manifest с неправильным actual member. Во всех случаях заранее указать affected result и сохранить независимый полезный output. Native failure-before-switch не уничтожает old generation.
6. **Transfer/holdout.** После фиксации implementation и параметров добавить не просто другой seed: второй source layout с reordered columns, variable-width strings, иной valid frequency, большим state axis и другим missingness pattern. Только fixture/schema/profile/data changes; сохранить diff ручной работы. Holdout IDs/values недоступны ветвлению production кода. Для новых unsupported calendar/unit semantics требуется честный declared conversion/profile, не молчаливый guess.
7. **Стоимость и повторное чтение.** Записать bytes captured/read, tmp disk peak, batch peak/RSS, row counts, parsing calls, audit live-object cap и group-size mean cost; 1×/2×/4× bounded synthetic N, без выдуманного универсального SLA. Закрыть producer objects; fresh process/readers читают output refs. Retry/rebatch equivalence сравнить с exact reference, не production uninterrupted run как единственным oracle.

**Что принимается:** finite source custody, correct observation/role/cell/time semantics, полезный conditional numerical consumer и data-only перенос в объявленном envelope. **Что не принимается:** достоверность population/source, причинная идентификация, универсальная научная пригодность, институциональное право, все historical layouts одним прогоном.

## Сквозная способность LANE-08: discoverable resource → usable indexed/streamed input

**Вердикт:** механизмы имеют правильные owner boundaries; native qualification ещё не выполнена. Free-grow можно показать без новых routing branches, но хорошие receipts не гарантируют, что новый релевантный ресурс будет найден. Отдельны catalog visibility, executable connector, admitted source, vector identity, semantic retrieval и stream processing.

**Уже сильные элементы:** I08-A различает selected sources и input/output basis; I08-B связывает semantic staged admission→single selector→fresh consumer, а EMB-03 требует реальную положительную owned query; I08-C не заявляет global exactly-once и не имитирует несуществующий spill. NET01 требует physical FD, а не mock close. Это гораздо больше structural QA. DFI03 direct dispatch и native profiles требуют точечной коррекции FA-02/07.

### Ограниченный улучшенный план приёмки

1. **Конечные профили.** P-DATA: Python3.14/lock/native Arrow/DuckDB. P-INDEX: дополнительно hnswlib0.8.0 и зафиксированный build/OS/ABI; GP backend не нужен. P-LEGAL-OWNED: дополнительно rag-local/ST2.7/actual locked runtime и заранее предоставленные local CPU1024 assets. Отсутствие prerequisites — NOT_QUALIFIED, не fake green encoder. Никаких установок/загрузок по этому ревью.
2. **Catalog route.** Два selected источника, один complete_empty, второй полезный; один catalog-only entry и excluded private entry. Actual registry/CLI→async selected harvest→normalize/merge→DuckDB→generation/readiness receipt→fresh DatasetCatalogStore. Проверять expected IDs/field values и downstream source binding. Smart и off direct/full routes дают согласованные content policy outcomes; changed endpoint/profile с прежним name и coherent old payload всё равно fresh miss. New compatible source затем добавляется только YAML/data.
3. **Index correctness oracle, не universal exact ANN.** Отдельный finite fixture минимум3 документов, k<N, normalized non-tied vectors с заранее вычисленными независимыми exact cosine ranks. Реальные HNSW build/load/query и обе domain preparation surfaces. Для выбранного малого corpus/ef profile проверить конкретный expected result; exact cosine — ground-truth reference, а не гарантия равенства любой approximate выдачи всех корпусов. Label permutation, changed vector with coherent hashes, typed empty и failed preselector должны различаться; valid replacement обязательно проходит.
4. **Retrieval utility qualification отдельно от publisher repair.** Если требуется stronger useful search claim, на предоставленном actual model выполнить маленький frozen релевантностный corpus: заранее adjudicated queries, expected relevant resource IDs, distractors, paraphrase, длинный документ с relevant passage в конце, и multilingual вариант только внутри заявленного profile. k/ef/threshold выбираются до holdout. Измерять recall@k и false abstention отдельно от exact-ANN agreement; threshold обусловлен конкретной задачей, не выдуман универсально. Holdout new compatible resource должен быть обнаружен actual public query после normal generation reissue. Не считать authoritative legal claim из proximity.
5. **Reuse existing health owners.** У `runtime/quality/proving_ground/legal_mandate_search.py:1867–1990` уже есть current-snapshot/known-seed pattern; tests `test_proving_ground_legal_mandate_search.py:905–960` различают missed seed и honest no-ground. Использовать этот принцип и существующий evidence join к E02-X03/X04/health, если поддерживает contract; НЕ фабриковать GL legal ledgers для embedding output и НЕ вводить ещё retrieval framework. E02-I08-B остаётся владельцем embedding qualification.
6. **Streaming reference.** Immutable raw JSONL с independent byte spans, source→expected accepted rows→window membership written outside StreamWindowAccumulator. Count, tumbling, sliding и session на небольшой конечной матрице; duplicate IDs/versions, event-time/order и ingestion UTC отдельно. Actual record→multi-namespace replay→transform/PII→chunk CAS→window→frontier→fresh downstream consumer. Vary batching/reset/crash boundary with same semantic input. Resume не означает заново physical fetched result.
7. **Failure/resource.** Initial precommit failure сохраняет source/clock/empty operator; malformed category quarantines exact row; repeated row-object occurrence counts twice; caller mutation cannot undercount. Process kill квалифицировать отдельно от BaseException injection. Contributor withdrawal отзывает только зависимые outputs. Actual FD remains readable while pending cleanup, then closes before fresh session; cancelled cleanup task heartbeat continues, watchdog distinguishes hang. Adaptive limiter completed success restores rate once, stale circuit completion not new recovery vote.
8. **Стоимость.** N ladder замеряет cold build, cold open, warm currentness/SQL/hash/NPZ/encoder/knn separately; encode count для incremental changed records; RSS/file reads и bytes retained. No FA-05 lease implementation mandate: только measurement-first. Оптимизацию можно обсуждать отдельно, если цель и ownership lifetime доказаны. Stream O(1) byte counter не full-loop complexity; operator/state/output-reference limits отдельно от process RSS. Native batch model profiling не оплаченный production load test.

**Принимается:** index/stream/connector действительно поставляет нужный finite compatible input со state/currentness/resource guarantees. **Не принимается автоматически:** all-source network support, distributed quota, scalable search SLA, empirical relevance во всех доменах, legal verification, arbitrary source namespace ambiguity resolution.

## Сквозная способность LANE-09: raw-backed discovery и полезный controlled LLM consumer

**Вердикт:** предложенный six-role materialization профиль — содержательное capability extension, а не cache-allowlist под fixtures. Scholar snapshot handoff правильно сохраняет факт, какой документ прочитан. Но два integration scenarios сами по себе ещё не доказывают целый autonomous research cycle; их linking с acquisition/NL owners нужно предъявлять только если тот фактически выполнен.

### Ограниченный улучшенный план приёмки

1. **Scholar positive.** Controlled local allowed source produces rawv1 HTML с repeated passages/Unicode и второй permitted MIME. Actual search provider empty/error→next provider hit; shared transport→raw CAS/cache→SourceMetadata→public API seed→manual normalization→_acquire_bytes selected recheck→docs/fragments/claims. Закрыть store/service objects, fresh consumer читает exact document lineage. Фрагменты сверять с независимым expected extracted-text substring; не смешивать UTF8 byte offsets и Unicode character offsets.
2. **Saved vs fresh.** После v1 изменить server content наv2. Повторный enrich выбранногоv1 и permitted cache читаетv1 без URL fetch; DNS/transport raise-on-call должны не мешать разрешённому offline reuse. Explicit refresh createsv2 with parent relation, v1 доступен. Current domain/MIME/size prohibition или unknown necessary profile не даёт cached text/snippets. No missing-blob reconstruction из snippets и no hidden live fallback.
3. **Deadline и physical boundary.** Inject monotonic clock для exact remaining/per-attempt start semantics; positive failover within budget, first completion after deadline excludes next. Реальный local drip transport отдельным native test проверяет outer wait deadline vs phase timeout; running shared worker retains slot until actual physical completion. Provider cancellation не обычная пустота. Не обещать hard-kill из asyncio timeout.
4. **LLM controlled semantic consumer.** Actual PolicyTranslatorWorker с explicitT0/fallbackFalse и двумя materially different valid bundles (например transfer policy и service provision), each six roles plus optional absence. Owner freezes actual payload bytes и selected CAS profiles, actual prepared request и scoped factory. Deterministic local provider разрешён, но он должен извлекать deciding dossier/constraint/uncertainty fields из wire request и выдавать соответствующий valid PolicyBrief; constant fixture answer не проверяет materialization. Проверять brief fields и change sensitivity, а не только provider count.
5. **Closure/miss/hit accounting.** Miss+2hits: один physical provider event,3 distinct consumer receipts, original usage и0 new provider increment наhits; actual FileBudgetLedger reopen сверяет totals/origin links. One-role-at-a-time byte/profile/absence/request/scope/epoch change invalidates only affected reuse. Literal URL/uncertainty text с полной closure остаются reusable; actual unresolved/live/tool role physical-only. Не менять defaultT0.1 или tool calling ради green test.
6. **Concurrency/fault pairs.** Two wrappers/shared cache/separate loops, barrier before claim, publication revision race → одна current full re-admission. Repeated conflict bounded physical path с новым admission, не stale grant. Follower cancellation не убивает остальных, owner failure resolves all and removes stale flight. Detached result identity must prevent one caller mutation affecting others. Optional span/metric fault preserves successful response; mandatory audit failure/unknown blocks uncontrolled next spend, recovery reconciliation permits exactly one legitimate retry без duplicate charge.
7. **Transfer и независимость.** Holdout bundle отличается структурой ограничений/optional role/uncertainty, не одним ID. Новый compatible document/resource проходит data/contracts; новую live role нужно versioned materializer semantics. Frozen known-groundable retrieval set отдельно оценивает поиск; LLM response consistency fixture не измеряет language/model quality. Acquisition→new brief/candidate link берётся из existing I01/X stories, не invented all-in-one coordinator.
8. **Cost.** Записать physical provider requests, wire bytes, per-consumer events, cache admission/CAS read cost, deadline starts, peak outstanding workers/flights, settled/unknown charges. Controlled0.02 — test amount, не real invoice или provider pricing. Pinned model assets/network/auth profiles и current permission не выводятся из hash.

**Принимается:** coherent raw source version reaches actual docs consumer; current authorized closed completion reuse не теряет response/accounting и переносится на второй materialized bundle. **Не принимается:** истинность цитируемого утверждения, entailment каждого claim, качество policy advice, права доступа по label, whole NL tool pipeline или универсальность любых natural-language dependencies.

## Библиотеки: решения, а не список модных технологий

Проверено по первичным источникам 2026-11-01. Пин project lock важнее newest API. Ни одна рекомендация не требует install в рамках ревью.

### LIB-FA-01 · FED-01, FED-02, UQS-01

**Выбор:** Предпочесть statistics.mean за narrow common finite-binary64 wrapper; midpoint через mean двух чисел. Не менять provenance policy.

**Lock:** Python3.14; NumPy2.3.5/pandas2.3.3 имеются.

**Почему:** CPython mean уже группирует exact integer ratios по denominator, суммирует рационально и округляет после total/n. fmean и even median не дают нужной overflow/subnormal семантики. Нужен finite/type wrapper, а не смешанные Decimal/NumPy types.

**Альтернативы:** Новый exact integer accumulator; Fraction per input; numpy/pandas mean; scaled fsum; statistics.fmean/median.

**Цена/границы:** O(n) conversion, bounded binary64 denominator buckets; big integers растут с log n. Не бесплатно и не vectorized. Большой group-cost измерить; optimized fallback только при доказанном сохранении точности.

**Квалификация:** Target3.14 independent Fraction oracle: extremes, signed cancellation, subnormal ties, permutations, empty/singleton, n scaling. FED sole writer; UQS contract tests.

**Первичные источники:** [mean146–165; fmean168–205; median304–324; _sum1322–1373](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py) — Точная CPython3.14.0 implementation; target project Python>=3.14,<3.15. Source inspection, not target runtime execution..

### LIB-FA-02 · OBS-02, UDF-02

**Выбор:** Сохранить Arrow streaming + existing snapshot owner; DuckDB/Arrow handoff оптимизировать только после профиля.

**Lock:** PyArrow22.0.0 + DuckDB1.4.3 already core.

**Почему:** iter_batches и column projection решают bounded reading; file-like input позволяет читать captured snapshot. DuckDB читает Arrow reader и умеет pushdown, но сам не заменяет source capture/retry/row ordinal contract.

**Альтернативы:** Full pandas.read_parquet; DuckDB direct scan вместо capture; Arrow RecordBatchReader→DuckDB вместо per-batch pandas conversion; Новая streaming platform.

**Цена/границы:** Нынешний capture: O(file bytes) disk+hash/copy и O(batch) dataframe; fallback повторно сканирует prefix. Direct scan может сократить copies, но обязан сохранить immutable basis и exactly accepted prefix.

**Квалификация:** Batch1/odd sizes/rowgroup changes, duplicate-valued distinct rows, failure afteryield, same-stat ABA mutation, tmp free space/peak RSS/read bytes. Нет утверждения zero-copy во всём пути.

**Первичные источники:** [ParquetFile source file-like193–200; iter_batches492–542](https://raw.githubusercontent.com/apache/arrow/apache-arrow-22.0.0/python/pyarrow/parquet/core.py) — Exact locked22.0.0. Versioned documentation URL unavailable; used immutable maintainer source instead.; [Arrow Datasets/Scanners/RecordBatchReaders](https://duckdb.org/docs/1.4/guides/python/sql_on_arrow) — DuckDB1.4.3 lock;1.4 LTS docs. No claim newest2.0 features available..

### LIB-FA-03 · FED-02

**Выбор:** Оставить pandas composition и явную schema-first typed empty branch.

**Lock:** pandas2.3.3, DuckDB1.4.3.

**Почему:** Уже существующие lineage/conflict/cardinality semantics важнее смены backend; concat сам не создаёт объявленный schema-only column. Для empty schema dtype создаётся из контрактного declaration до inference.

**Альтернативы:** Inference из concat empty templates; Перенос всей composition в DuckDB; Новая dataframe library.

**Цена/границы:** Index-once per composition полезнее повторного row lookup. SQL pushdown оправдан только measured large-group work и полным equivalence корпусом null/join/lineage.

**Квалификация:** Full typed empty schema→SQL fresh read; nullable z; all audit modes identical values/counts; precise dtype/metadata tests.

**Первичные источники:** [Parameters/Notes/outer join missing columns](https://pandas.pydata.org/pandas-docs/version/2.3/reference/api/pandas.concat.html) — 2.3.3 docs match lock.; [Arrow Datasets/Scanners/RecordBatchReaders](https://duckdb.org/docs/1.4/guides/python/sql_on_arrow) — DuckDB1.4.3 lock;1.4 LTS docs. No claim newest2.0 features available..

### LIB-FA-04 · UDF-05, CAL-01

**Выбор:** Сохранить NumPy/Pydantic; исправить admission order, не вводить численную платформу.

**Lock:** NumPy2.3.5; Pydantic2.12.5; JAX0.8.2.

**Почему:** asarray infers common dtype; exact IDs проверять до него. np.interp требует increasing source axis и не проверяет все domain invariants. Stable paired normalization и domain unit/interval policy достаточно.

**Альтернативы:** Blind np.asarray then validate; New generic units/axis engine; SciPy interpolation migration.

**Цена/границы:** Prevalidation O(n), сортировка time O(nlog n); explicit target order сохраняется. JAX dtype/report profile фиксировать; measurement.py explicitly float32, поэтому нельзя считать весь pipeline binary64.

**Квалификация:** Mixed large-int/integral-float record IDs; axis permutations/equal-length/inferred-grid; unit mismatch; native calibration target consumer.

**Первичные источники:** [dtype parameter / inferred from input](https://numpy.org/doc/2.3/reference/generated/numpy.asarray.html) — NumPy2.3.5 lock; same2.3 API.; [xp increasing / Warning / left,right](https://numpy.org/doc/2.3/reference/generated/numpy.interp.html) — NumPy2.3.5; does not define domain units or duplicate observation policy..

### LIB-FA-05 · EMB-01, EMB-02, EMB-03

**Выбор:** Сохранить hnswlib; добавить exact small-corpus oracle и measured quality/cost qualification.

**Lock:** hnswlib0.8.0 optional vector-search; lock entry sdist without wheels; NumPy available.

**Почему:** Native index admission принадлежит existing shared owner. HNSW set_ef после load важен и уже есть=100; stored-vector equality не доказывает retrieval recall. FAISS предлагает exact baseline/quantization, но migration сейчас не оправдана.

**Альтернативы:** NumPy exact cosine/flat retrieval для small N; FAISS Flat/HNSW/PQ; External vector database.

**Цена/границы:** HNSW строится и держит graph memory. При редких query exact scan может быть проще; warm validation читает whole artifacts/text. Сначала measurements, затем bounded immutable-generation lease, не stat-only cache.

**Квалификация:** Cold/warm query at N ladder, exact cosine no-tie fixtures, recall@k on frozen query holdout, provenance and withdrawal; native build availability3.14 qualification before stronger claim.

**Первичные источники:** [Python API: set_ef; get_items cosine normalized; thread safety; M/ef_construction](https://github.com/nmslib/hnswlib) — Project hnswlib0.8.0 optional vector-search; current maintainer API requires native qualification on lock.; [Few searches; exact Flat; HNSW memory/accuracy tradeoff](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index) — Alternative only, not existing approved dependency. No recommendation to install/upgrade..

### LIB-FA-06 · EMB-03

**Выбор:** Оставить первый owned local ST2.7 CPU1024 профиль как bounded capability, не выдать его за универсальную модель.

**Lock:** sentence-transformers2.7.0 rag-local; torch2.10.0; transformers4.57.6; research/all extra не включает rag-local.

**Почему:** 2.7 constructor supports local path/revision/device; owner уже snapshot_download(local_files_only=True), exact assets и dimension. Generic text encoder полезен candidate, не заменяет owned served witness.

**Альтернативы:** Generic encoder fixture; Latest ST backend API; Новая модель/сервис.

**Цена/границы:** Tiny corpus не делает саму модель tiny. Отдельно cold load/RSS, encode batches, runtime hashing. Tokenizer truncation может скрыть релевантный конец текста; обязательна adversarial retrieval qualification, не обещание всех языков.

**Квалификация:** Заранее предоставленные local assets; actual model+index+fresh public query, no admission mock; second content corpus with frozen holdout. No downloads/install authorized.

**Первичные источники:** [constructor46–85; encode normalize_embeddings; get_max_seq_length530–537](https://raw.githubusercontent.com/UKPLab/sentence-transformers/v2.7.0/sentence_transformers/SentenceTransformer.py) — Exact locked2.7.0 optional rag-local; do not prescribe modern backend/local_files_only constructor keywords absent in this version..

### LIB-FA-07 · ING-02, ING-03, NET-01, NET-02

**Выбор:** Сохранить domain stream/frontier и stdlib asyncio/deque/locks; не переносить в Flink/Kafka ради локального ремонта.

**Lock:** Python3.14 asyncio, aiohttp3.13.3; existing CAS/cursor/pool/rate limiter.

**Почему:** Shield не делает independently-cancelled task живой: terminal state обязан settle. Operator byte budget — не eviction cache; live keys нельзя выбрасывать ради capacity. Callback success belongs completed provider outcome, not attempted request.

**Альтернативы:** TaskGroup вместо lifecycle owner; Generic retry decorator; External streaming framework.

**Цена/границы:** O(1) byte counter не устраняет O(buffer) _prune_row_refs/preview copies. Explicit process resources remain until physical close; cancellation deadline not FD evidence.

**Квалификация:** Barrier-driven cancellation, watchdog+heartbeat, os.fstat/pread and fresh session, independent row/window oracle, UTC restart. Custom limiter local, no distributed quota claim.

**Первичные источники:** [Shielding; timeout_at; Task cancellation](https://docs.python.org/3.14/library/asyncio-task.html) — 3.14 docs; cancellation is cooperative, physical worker lifecycle remains application owned..

### LIB-FA-08 · SCL-01, SCL-03

**Выбор:** Сохранить общий pinned raw transport; stdlib absolute async deadline в существующем owner.

**Lock:** urllib custom raw owner; HTTPX0.28.1 already used in search adapters; common bounded executor.

**Почему:** HTTPX timeouts не total deadline. Custom transports дают extension seam, но не автоматически peer/SNI/redirect policy. Offline saved-byte admission отделить от live DNS. Shared raw owner already implemented; переписывание добавит риск.

**Альтернативы:** Replace all transport with requests/httpx; HTTPX per-phase timeout only; TTL cache permission.

**Цена/границы:** Outer cancellation прекращает ожидание, не гарантирует уничтожение running blocking thread. Current shared executor сохраняет physical slot; измерять exit/resource separately. DNS before cache запрещает offline reuse.

**Квалификация:** Persisted offline cache network0, real local TLS/SNI redirects on allowed fixture, drip response vs absolute budget, all failover attempt starts. Не ослаблять rawbytes/MIME/maxbytes.

**Первичные источники:** [Fine tuning: connect/read/write/pool](https://www.python-httpx.org/advanced/timeouts/) — HTTPX0.28.1 in lock. Timeout read is per chunk, not total wall budget.; [HTTP transport / custom transports / retries](https://www.python-httpx.org/advanced/transports/) — Current primary docs; generic client not drop-in proof of project DNS-pinned peer/SNI contract.; [Shielding; timeout_at; Task cancellation](https://docs.python.org/3.14/library/asyncio-task.html) — 3.14 docs; cancellation is cooperative, physical worker lifecycle remains application owned..

### LIB-FA-09 · LLM-01

**Выбор:** Оставить OTel и узкий best-effort optional boundary; mandatory budget/audit вне неё.

**Lock:** OTel API/SDK1.39.1 core; declared no-OTel fallback distinct environment.

**Почему:** OTel principle предпочитает потерю telemetry изменению business logic; injection useful even if normal SDK handles exporter errors. Existing _post_record mutates mandatory projection; optional tail isolate only.

**Альтернативы:** Blanket except around provider/ledger; Remove tracing entirely; Async telemetry queue rewrite.

**Цена/границы:** Safe callbacks add small overhead; не создавать recursive diagnostic failure. Fallback profile не равен ordinary core install with OTel; проверить ABI independently.

**Квалификация:** Enter/exit/attribute/status fault matrix, body exception cannot be suppressed, response/ledger persist, provider count1, unknown owner blocks spend then recovers.

**Первичные источники:** [Basic principles124–137](https://opentelemetry.io/docs/specs/otel/error-handling/) — General normative design guidance, not evidence locked Python SDK1.39.1 never throws injected callback exceptions..

### LIB-FA-10 · LLM-02, DFI-03, SCL-01

**Выбор:** Сохранить domain content-bound owners; cachetools/TTL лишь storage primitive, не permission/proof/single-flight framework.

**Lock:** cachetools6.2.4 existing; custom PromptCache owns proofs/settlement and shared Future state.

**Почему:** TTL/memoization не кодирует current actor/epoch/selected CAS/profile/prepared wire bytes. Frozen six-role translator closure минимальна и переносима на данные, а произвольные live/tool requests остаются physical-only.

**Альтернативы:** functools.lru_cache; cachetools.TTLCache wrapper; Redis/distributed locks; Regex whitelist cacheable prompts.

**Цена/границы:** Public docs newer than lock used only generic comparison. Extra binding adds hashes+CAS reads, но решает semantic ownership; per-key revision optimization не нужна для one-retry correction.

**Квалификация:** Two actual translator bundles, one-role mutation matrix, explicit optional absence, no stale grant, separate loops/follower cancellation, physical ledger readback. Exact response-content holdout prevents constant fixture becoming semantic proof.

**Первичные источники:** [Cache mutable mapping/getsizeof/thread safety; TTLCache](https://cachetools.readthedocs.io/en/latest/) — Current docs7.2.8, lock6.2.4. Exact version URL unavailable; general comparison only, no new6.2.4 API recommendation.; [Shielding; timeout_at; Task cancellation](https://docs.python.org/3.14/library/asyncio-task.html) — 3.14 docs; cancellation is cooperative, physical worker lifecycle remains application owned..

## Метод, охват и ограничения

- Прочитаны полные25 packet Markdown, 112 REQ и 115 TEST; companion JSON полностью parsed, повторяющаяся нормативная проза сверена с Markdown, unique maps/decisions inspected. Все8 I07/I08/I09 сценариев и их explicit concrete binding blocks прочитаны. Это не повторная форматная QA вместо содержания.
- Repository code/tests читались по ranges, а не запускались. `coverage.json` явно отличает whole document от selected source range. Два архитектурных документа прочитаны в релевантных разделах; остальные18 и весь прежний audit не выдаются за повторно прочитанные этим reviewer. Root ведёт общую synthesis.
- Python3.14 requirement и lock inspected. Host independent arithmetic — Python3.12.14, только `statistics`/`Fraction` и exact integer→float examples; `independent_arithmetic.json` не product test и не native3.14 qualification.
- Нативные зависимости, model assets, source quality, throughput/RSS, cancellation/process death и installed distribution остаются NOT_RUN/NOT_QUALIFIED до разрешённого actual execution. Нет установок, live providers, product edits, commits или внешних mutations.
- Не установлен широкий security exploit, production data corruption или измеренное SLO нарушение. FA-01..03 — ошибки/неполноты предложенного способа; FA-04..07 — оптимальность/приёмка/профили с разными блокирующими областями.

## Рекомендуемая последовательность

1. Уточнить FA-01/02/03 в пакетах, сохранив исходные IDs/maps.
2. Согласовать FED/UQS stdlib choice с одним common writer; не делать два reducers.
3. Исполнить local discriminators на named native profile, затем один shared evidence set каждого применимого I07/I08/I09 scenario.
4. Дополнить FA-06 existing I08-B/GL-G5 pattern только при stronger retrieval claim; holdout выбирается до параметров.
5. По FA-05 сначала получить cost evidence; решение об оптимизации отдельно. Не заменять content binding на stat cache.
