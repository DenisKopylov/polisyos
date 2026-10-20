# AD-E02-03 — observational selection через ordinary HTTP

Disposition: **B selected as durable path; A selected only as explicit compatibility adapter**. Это конкретная граница реализации, не новый вопрос G. Source snapshot `11ff2421e04223fc961dd5a520768fd75bafe1e2`; приёмки кода/closures нет.

## Почему B и где остаётся A

Existing `ObservationMethodInputEnvelope` v1 умеет versioned target и payload; current HTEObservationalData — runtime DTO, не registered versioned artifact contract. Поэтому долгоживущий HTTP capability получает настоящий HTE target/materializer/producer у existing owners. Panel/Ukraine producer сохраняет свой purpose-specific scope и не переименовывается в universal HTE.

A нужен для уже существующего exact raw HTE input с `artifact_schema=null`. Его допускает только явный versioned compatibility protocol и candidate purpose. Canonical producer валидирует bytes и пишет **новый** versioned envelope с source lineage. Это инженерная нормализация, не переименование старого manifest и не source authenticity upgrade. B и A перестают конкурировать как два неявных parser fallbacks: wire protocol выбирается до чтения payload, effective typed input один.

## Public request: выбранные поля и truth table

Extend strict `core/contracts/control.py::WorkflowRunRequest` **одним** optional-by-absence, non-null-if-present объектом `observational_input`. Его strict DTO имеет protocol-discriminated branches с одинаковым набором selection fields:

| Поле | Контракт |
|---|---|
| `observational_input.protocol` | Обязателен: `method_input_envelope_v1` либо `legacy_hte_json_v1`; input protocol discriminator, не authority/status enum |
| `observational_input.source_ref` | Обязательный full ArtifactRef с selected manifest profile для каждого нового submission, включая explicit A |
| `observational_input.method.fqn` | Обязательный exact registered FQN; не prefix dispatch и не default synthetic control |
| `observational_input.method.version` | Optional-by-absence, non-null exact version if present; отсутствие выбирает server registration **один раз до durable acceptance**, resolved version сохраняется и видна в response/GET |
| `observational_input.method.params` | Optional object, absence → owner-resolved defaults **до durable acceptance**; present null запрещён; сохраняются submitted и canonical effective params |

`method` обязателен и non-null. Все уровни strict (`extra="forbid"`), включая branches. Конструкция делает selection атомарным значением API; не переносить новые поля в `params: dict[str, Any]`. Это **заменяет прежнее предложение четырёх новых top-level полей**: на исследованном source они ещё не были public contract. Existing `ExperimentState.observational_data_ref`, `causal_method_fqn` и `causal_method_params` остаются внутренними projections admitted intent. Не создавать второй публичный carrier ради похожих имён. Если coding source уже опубликовал предыдущую форму, сначала подтвердить actual consumers и применить явный versioned request adapter; нельзя молча сломать действующий API.

ExecutionProfile, manifest profile digest, payload schema/version, canonical serialization profile, method/version/build и observational protocol — **разные version axes**. `schema:null` не означает profile absence. `artifact_schema` и `canon` нельзя взаимозаменять.

| Request | Outcome |
|---|---|
| `observational_input` отсутствует | Существующий workflow contract сохраняется; causal source absent → existing skip/limited, без invented input; ambiguous selection aliases не разрешаются |
| `observational_input` явно null, `{}`, либо отсутствует required ref/protocol/method/fqn | Typed validation refusal; не absent |
| Любое присутствующее selection поле null, malformed, unknown protocol/version/field | Typed validation refusal; params внутри method могут отсутствовать, но не быть null |
| Новый объект и selection aliases в general `params` либо top-level одновременно | Conflict refusal, даже при равных значениях: ровно один carrier |
| Valid envelope protocol | Проверка exact envelope schema/target/manifest и registered method compatibility |
| Explicit legacy protocol | Exact legacy kind/media/profile и pinned parser; normalization → новый HTE envelope; legacy limitation сохраняется |
| B payload malformed/wrong target/missing body version | Refusal, никогда попытка raw parsing |
| Wrong kind/media/profile/content/tenant/method | Refusal; никогда fallback к data_source или другому методу |

`data_source` остаётся своим input role. Если конкретный workflow требует совпадения с observational source, сравнить полный ArtifactRef view и явно объявленную relation; не alias по artifact_id или имени. Existing callers, которые использовали general `params`, мигрируются одноразовым **явно versioned legacy request adapter** только для доказанного существующего request protocol. Он переводит selection в canonical object и удаляет legacy carrier перед admission; одновременный новый carrier — conflict. Для нового protocol никаких params fallbacks. Непривязанные старые jobs не получают новое method selection по догадке.

## Immutable requested intent и admitted intent

Runtime launch сохраняет **submitted selection** и **resolved execution intent** вместе с authenticated tenant context до подтверждения durable job. Resolved часть содержит exact method registration/version/ABI, ожидаемую immutable implementation/runtime boundary, canonical defaults/params, seed policy/seed, выбранные execution/input protocol/resource policy revisions. Resolver использует уже admitted/bootstrapped registry metadata; HTTP handler не импортирует ML backend и не сканирует всё окружение. Unknown method/params/profile или неразрешимый обязательный runtime pin дают typed refusal/unavailable до acceptance. Это собственная engineering работа по startup registry/runtime manifest, а не внешний institutional input.

Pin runtime означает проверяемую declared build boundary, не доказательство полной воспроизводимости всех transitive dependencies. Owner может разрешать candidate execution при явно limited replay assurance; selected registration и имеющиеся implementation bytes всё равно не подменяются `latest`. Непроверенная external provenance не повышается до `independently_reconciled`. Actual backend/fallback/dtype/environment фиксируются при execution и сверяются с разрешённой policy. Непредусмотренное изменение → refused attempt; выбрать новое исполнение можно только явно новым intent.

Структура strict/deep-frozen либо canonical immutable CAS payload; новые управляющие поля не живут только в mutable Python dict. Version `policyos.runtime.observational_run_intent.v1` — предлагаемая новая schema у существующего control/lifecycle owner, не новый registry/очередь. Submitted и resolved части не требуют двух отдельных artifact families. Response возвращает admitted request identity/resolved-selection digest; это acceptance запроса, **не** content admission observational bytes.

Под compute admission owner создаёт **content-admitted intent**: ref на сохранённый requested/resolved intent, effective envelope ref, source/raw parent refs, exact target contract ID/FQN (version encoded in ID), проверенную совместимость с pinned method, actual authorized selected view и outcome normalization. Он не заново выбирает method/defaults после ожидания. Этот результат пишется до dispatch и включается в owned attempt selection. Requested intent не перезаписывается effective ref. Resume читает сохранённый intent и pinned readers/build, а не registry latest. Revoked access или запрет действующей resource/security policy могут остановить попытку; это не повод silently заменить исходный intent.

- B: submitted ref обозначает versioned envelope. Если он уже соответствует выбранной canonical schema/profile/governance и полностью проверен owner, effective ref равен submitted ref. Если нужна допустимая нормализация representation, producer пишет **отдельный** canonical envelope с selected submitted-ref lineage и сохраняет оба refs. Смена target/method semantics не normalization, а refusal/new explicit selection. Никакого чтения B как raw.
- A: submitted ref обозначает raw source; effective ref — новый envelope, manifest lineage содержит полный selected raw InputRef. Связь recomputed normalizer, не caller assertion.
- `ExperimentState.observational_data_ref` становится **effective** input projection из admitted intent; requested source доступен через intent ref. Hydration проверяет согласованность, не overwrites произвольного state поля.
- Retry той же admitted попытки сохраняет input/method identity. Изменённый method registry/build/defaults требует compatible pinned runtime либо explicit new run/attempt policy, не silent latest rebinding.

Последовательность: resolve lightweight method/defaults/runtime pins → persist requested/resolved intent + durable job → refs-only queue AD02 → acquire worker slot → guarded source resolve/normalize → seal content-admitted intent → dispatch на том же resolved input → serialize/persist typed result под тем же slot → вернуть refs → fenced owned selection. Exact admitted-intent ref включается в existing execution-input basis и bundle input relation AD01 либо manifest canonical causal result. Guarded attempt commit выбирает result, связывающий этот intent; нельзя присоединить admitted intent к run только неподтверждённым state label.

Envelope producer формирует input contract, а не утверждение «наблюдения истинны». Допускается клиентский корректный envelope как candidate input; сервер всё равно проверяет/нормализует его. Producer name, kind label, payload hash и signed-looking fields не external attestation. Unknown calibration/currentness/custody сохраняются typed limitations, не блокируя допустимый candidate compute.

## Настоящий HTE target и producer

**Предлагаемый новый ID:** `foundry.causal.hte_observational_data.v1`; canonical target FQN — существующий `polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData`. Он не считается registered до реализации schema, target registration, producer и acceptance tests. Если repository ID convention требует другого написания, изменить ID согласованно до writer freeze; не выдавать старое `schema:null` за этот contract.

Wire payload schema v1 задаёт `outcome`, `treatment`, `covariates` и optional `confounders`, `feature_names`, `confounder_names`, `sample_ids`, `metadata`, реальные numeric shapes/finiteness/row alignment и method-owner restrictions. Совместимость с текущим `HTEObservationalData` обязательна: n≥40, binary treatment, outcome/treatment длины n, covariates n×p при p≥1, согласованные optional matrices/names/IDs. Это текущая execution precondition, **не научная достаточность 40 observations** и не универсальная causal grammar. Optional null semantics payload сохраняют существующий DTO там, где null разрешён; запрет null в request selection не переносится автоматически на данные. У NumPy runtime DTO остаётся свой representation. JSON schema и owner parser отвечают каждый за своё: `Any`→`np.asarray` само по себе недостаточно для versioned bounded wire contract. Source semantic roles/time/population unknown не изобретаются; если выбранный метод требует их для execution или claim, проверяется конкретное требование.

Extend existing `foundry/data_plane/bindings.py` registry и method acceptance mapping реальным HTE contract. Envelope `policyos.ir.observation.method_input_envelope.v1` сохраняется при совместимом расширении target registry. Existing target имеет `contract_id` и `contract_fqn`; версия target уже закодирована в ID, **отдельное поле target.version в envelope v1 не вводить**. Manifest `artifact_schema` обозначает outer envelope, target ID — inner payload contract. Для HTE envelope body discriminator обязателен в raw wire bytes: Pydantic default `schema_version` не доказывает, что он был передан. Manifest kind остаётся `ir.observation_method_input`, media — зарегистрированный JSON type.

Normalizer принадлежит существующему Foundry observation/data-plane owner: source resolution → guarded decode → registered HTE validation → canonical envelope write с lineage → effective ref. Он переиспользует Core decoder/canonical profile, включая tagged floats и presence/null semantics; raw `json.loads` не обходной decoder. Канонический writer задаёт явный schema ID/version и governance, reader больше не sniff-ит payload keys/FQN prefixes. Arbitrary import FQN, filesystem path или URL не input mechanism.

## Admission, privacy и память

1. HTTP до enqueue валидирует syntax/presence, exact registry names, selected view metadata и authenticated view access; фиксирует resolved execution intent по правилу выше. Method params проходят известный strict contract; нельзя использовать произвольный import path. Small metadata checks не дают права materialize arrays вне resource owner.
2. Durable queue хранит refs/intent, не input arrays. Под slot AD02 normalizer читает **один selected immutable view** с проверенным profile/hash/kind/media/schema. Разрешённый snapshot/stream передаётся дальше, default manifest второй раз не выбирается.
3. До полного JSON/NumPy allocation действуют actual-byte/depth/element bounds из selected resource policy; manifest declared size не заменяет observed stream bytes. Проверять shape/element count и expansion/copies, не только payload bytes. Duplicate full materialization в TMLE loader устраняется или явно учитывается. Если реализация сначала собирает giant dict, «проверили размер массива потом» не раннее ограничение.
4. Payload semantic invalid, обнаруженный worker после POST acceptance, сохраняется как typed refused/failed input outcome с reason и fresh GET. Это не успешный run и не source absence. Лишь syntax/access/known metadata errors гарантированно отказывают до enqueue.
5. Access проверяется до queue, при worker read и при выдаче surface по selected view и server tenant context. При revoked access stored candidate нельзя снова раскрыть из cache. Нет утверждения о доказанной текущей cross-tenant уязвимости; это invariant нового пути.
6. Derived envelope/outputs наследуют classification, tenant/audience restrictions, retention/encryption obligations источников согласно existing governance join. Default manifest classification `public` не допустимый fallback. Source privacy не ослабляется от слова candidate; fresh GET не возвращает arrays/sample IDs/private locators без соответствующего отдельного разрешения.

Logical slot cap не доказывает hard RSS ceiling. Ограничения byte/depth/elements и отсутствие дублирующих copies уменьшают известный риск; universal memory guarantee здесь не заявляется. Unsupported input size → typed resource refusal/backpressure по policy, не OOM как нормальная ветвь.

## Fresh GET и статус

Extend existing RunIndex/run-details projection, не новый serving subsystem. После ordinary authenticated POST → ControlWorker → RunLifecycle → Scientist/реальный TMLE → CAS → guarded owned attempt commit fresh reader GET показывает:

- requested source/protocol и effective envelope refs в доступном audience projection;
- exact selected method/version/build/params digest и input profile;
- persisted result refs, effective execution settings и candidate outcome;
- отдельные limitations: legacy source protocol, unknown scientific context/currentness/authority, unavailable outputs/unsupported replay;
- source observation epoch (если установлен), request/admission/execution/verification/read times как разные роли.

GET читается из persisted owned selection, не из POST response/state cache; не запускает normalizer/method повторно. Нет input — existing absent state; present invalid — persisted refusal; valid candidate ≠ authoritative/publication-approved. Reuse existing status composition, не вводить product `admissible` от одного source parse.

## Миграция и retirement

Server readers/normalizer/target сначала, затем writer, request propagation, свежий GET и официальная генерация OpenAPI/schema/Node/browser clients. Old clients могут omit новые поля; new clients не отправляют их old strict server без capability support. Old readers не разрешают new fields как extra-ignore. Migration guard запрещает silent field stripping при durable job/state round-trip.

Canonical new writes — versioned B. A new submissions отключаются versioned policy после: полного supported caller/source census, B producer+consumer parity/removal tests, перевода всех поддерживаемых raw writers и опубликованного retirement switch/profile. Никакого произвольного календарного срока и вечного implicit fallback. Исторический A reader остаётся pinned для воспроизводимости; неизвестный historical parser/build → limited/unavailable replay, не запуск под latest. Forward rollback отключает новые admissions/writes, сохраняя readers, jobs и refs.

Historical profileless records не разрешаются через today's default profile: только доказуемо pinned historical reader/context либо limited/unavailable. Replay build identifier обязан разрешаться в immutable executable/runtime identity выбранной boundary; красивой строки build недостаточно.

Minimum footprint: strict control DTO + launch mapping; durable intent/job schema; RunLifecycle/state hydration; registered HTE wire target/materializer; real producer; `run_causal_evaluation` parser/method binding; AD02 lazy admission; CAS lineage/governance; owned attempt commit; RunIndex/audience GET; public/generated companions из official inventory; meaningful HTTP/worker/reader tests.

Future acceptance: один ordinary POST→real worker→CAS→fresh GET positive для B, отдельный explicit A migration positive, old absent positive; минимум null/missing/params conflict, malformed envelope без discriminator, wrong target/kind/media/profile, same bytes different view, cross-run/profile swap, registry/defaults drift **между POST и первым dequeue**, drift on resume, after-validation backing alias replacement, resource expansion, revoked access и private→public derivation negatives. Mapping removal при сохранённых DTO markers должен сломать positive. Empty/repeated HTTP reads не запускают normalization/compute; generated clients сохраняют absence/null и atomic selection. Local synthetic observations допустимы для этого механизма; authentic evidence и production currentness требуют собственных inputs. Все проверки **UNRUN в этой архитектурной работе**.
