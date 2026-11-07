# LANE-08: общий интеграционный контракт

**Цель:** Каталог, embeddings и streaming действительно доставляют текущий согласованный input, сохраняя поколения и ресурс после отмены.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: DFK-02, DFI-01, DFI-02, EMB-01, EMB-02, EMB-03, DFI-03, ING-01, ING-02, ING-03, NET-01, NET-02

- Reuse CAS witnesses LANE-06; source-progress contract подключается LANE-01 acquisition и LANE-07 observations.
- ING-02 historical prerequisites ING-01/NET-01, не завершение всех embeddings.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-DATA:** P-CORE with native selected pyarrow/Parquet, NumPy/NPZ, DuckDB/graph backend when claimed; ordinary JSON seam not Parquet qualification (основание: policy-engine/pyproject.toml; OBS-02/UDF-02/EMB audit reports)
- **P-INDEX:** P-CORE + selected vector-search extra hnswlib==0.8.0, actual native build/ABI, OS/arch/interpreter/lock and ef/index profile; fake index is wiring-only. No install implied by this specification. (основание: policy-engine/pyproject.toml [project.optional-dependencies].vector-search; uv.lock)
- **P-LEGAL-OWNED:** P-INDEX + selected rag-local extra, locked sentence-transformers==2.7.0 and compatible actual runtime inventory; verified already available local model/tokenizer assets with hashes. research/all does not by itself guarantee rag-local. Missing assets/profile NOT_QUALIFIED; no silent download, fake encoder or newer unsupported constructor API. (основание: policy-engine/pyproject.toml [project.optional-dependencies].rag-local; uv.lock; EMB-03 owned profile)

- Controlled local connector/transport, synthetic finite dataset; никакой fault injection в external user storage.
- Injected encoder годится для wiring, отдельный tiny native encoder/index только для заявляемой native способности.
- Source-bound receipt, real staged files/CAS/cursor и physical cleanup owner не подменяются.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I08-A — Catalog/API → canonical pipeline → selected generation

Покрываемая область: DFK-02, DFI-01, DFI-02, DFI-03

**Положительный oracle:** Declared catalog profile/empty/default различаются; scoped callers используют один real owner. Harvest/normalize/embed/graph resume связан с actual source/assets/rule bytes, а mtime-only change допускает reuse. Harvest-only qualification идёт через existing async finite stages={harvest} и тот же current admission, что full pipeline. Smart current hit делает network0; off/smart miss передаёт inner resume=False при сохранении отдельно разрешённого HTTP cache.

**Различающий негативный oracle:** Same-stat changed bytes, malformed receipt, missing inventory и changed loaded assets не перескакивают stage. Failure сохраняет old complete generation и source-specific причину. Coherent payload того же source.name со сменённым endpoint/config/registry не становится current hit; unsupported sync content-stage harvest route не используется как oracle.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I08-B — Shared embedding kernel → index/manifest → fresh reader

Покрываемая область: EMB-01, EMB-02, EMB-03

**Положительный oracle:** Малые тексты дают согласованные IDs/vectors/float32/profile; три legal projections и chunk/thermal/stats сохраняются; читатель выбирает текущий exact inventory. EMB-03 отдельно предъявляет supported owned producer/runtime material → selected generation → fresh served Legal query с текущим intent; generic candidate index не выдаётся за этот положительный served профиль. P-INDEX отдельно проверяет native HNSW на >=3 non-tied vectors,k<N и declared ef/native profile против независимого exact-cosine ground truth. P-LEGAL-OWNED отдельно требует locked local encoder/assets и actual serving. Только для claim полезности retrieval добавляются pre-adjudicated bounded corpus/queries, заранее выбранные recall@k/false-abstention criteria и frozen heldout compatible resource; known-seed recall/freshness evidence joins переиспользуют существующий GL/G5 pattern без legal authority.

**Различающий негативный oracle:** Encoder/model/tokenizer/rule/withdrawal drift инвалидирует reuse; typed empty остаётся empty; failed staged publish не выдаёт mixed-generation индекс. Drift runtime material/intent не обходит gate; недоступный owned профиль остаётся NOT_QUALIFIED, а не подменяется encoder fixture authority. Always-first-ID не проходит topology control; exact tiny witness не universal ANN guarantee. Fake encoder — wiring only, semantic utility NOT_QUALIFIED не проваливает publisher repair. До оптимизации измеряются cold/warm identity-hash/projection/encode/knn counts, time/RSS на declared workload ladder; не выдумываются SLA, новая vector DB или бессрочный identity lease.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I08-C — Connector/stream → chunk CAS → restart → actual consumer

Покрываемая область: ING-01, ING-02, ING-03, NET-01, NET-02

**Положительный oracle:** Непрерывный и rebatch/restart paths дают те же rows/windows/contributor refs; продвигается только завершённый source. Реальный physical FD освобождается перед fresh session; 0.2/s pacing соблюдает объявленный burst.

**Различающий негативный oracle:** Failure before publish/after chunk, missing replay fixture, malformed row и expired dedupe не меняют denominator в лучшую сторону. Cancel/late response не крадут permit и не лечат новое circuit generation; bounded cooldown не снимается. SPILL_TO_DISK без реализованного reader получает typed unsupported/capacity refusal с сохранённым frontier; положительный spill-путь требуется только для отдельно выбранного и реализованного профиля.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/data_forge/domains/catalog/batch/test__core_sources_ingest_contracts.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/data_forge/domains/catalog/batch/test__core_sources_ingest_contracts.py) — SHA256 `628e9f0809058bee8b4d385ee391bec6eef850cfff54fe309e8e5ad65553b08f`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_dfi_03.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_dfi_03.py) — SHA256 `f9829ac9c95e57f76ffd356933f2e4a5859c4871e45bc9390b81711b37f6b02e`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_emb_02.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_emb_02.py) — SHA256 `b830738c7656c015c5afc48c5c48076ceb4257139ee0f73aac2266ee9480ac9b`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/fabric/data_plane/test_e02_c_streaming_oracle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/fabric/data_plane/test_e02_c_streaming_oracle.py) — SHA256 `8283dd1fc531306d8f1dbd6550390e2d769dab622fa8dab2c33f9e59646f9a39`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/fabric/data_plane/test_stream_pool_physical_cleanup_oracle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/fabric/data_plane/test_stream_pool_physical_cleanup_oracle.py) — SHA256 `3bb2b8c5e3b413787685114dcca9fa4d469d5ba8688be87aaaab030f52cc9baf`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/fabric/connectors/test_regulator_lifetime_e02.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/fabric/connectors/test_regulator_lifetime_e02.py) — SHA256 `b15773b2fb88c8d237c84e5cc2e5e3b9574df40b7fec9739d36f2c223591b03a`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
