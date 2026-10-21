# E02: актуальные архитектурные вопросы для G, 20 октября 2026

Авторский пакет выбора контракта. Это не приёмка кода и не adjudication findings. `G_acceptance=false`, `closure_ids=[]`. Исходный candidate: `codex/e02-unified-local-20261009`, commit `fe046fefbb06fc3dcaf259766f048a6defed58ea`, tree `c664005a5a930f91a7e05bc25e13c376dccdeabb`, parent `76ea932f6c2188980ae506f6855e14e77005dd0f`. Global source/input/backend freeze ещё не выполнен.

Этот пакет выделяет подготовленные вопросы, над которыми G может работать параллельно с engineering. Он не переоткрывает уже выбранные D01–D08 исходного connected plan и не превращает каждую запись каталога `decisions/` в новую архитектурную развилку. Устаревшие UNRUN в ранних исходных записках ниже уточняются свежими, точно ограниченными результатами этого индекса.

## Обновление 21 октября: принятые решения и оставшиеся предложения

G опубликовал выбор AD01–03 в commit `b7adafe89423bc6906a5fb86c38e579a381ad2ee` (tree `3cf103b6e1b9a395bcb7f3f5803346f90ddc1370`); пакет включён обычным merge в candidate. [Финальные решения](../../../integration/architecture-decisions-2026-10-20/06-final-decisions-and-solo-review.md) и [порядок реализации](../../../integration/architecture-decisions-2026-10-20/04-implementation-and-verification.md) задают действующий контракт. Разделы AD-E02-01–03 ниже сохраняют исходные вопросы и прежние результаты как историю; они не являются повторным запросом выбора. Принятие архитектурного варианта не означает приёмку текущего авторского кода или formal closure. Реализация и composed verification продолжаются.

HTE outcome/inference, CAN profile/law и B161 остаются отдельными предложениями в указанных пакетах. DS17 ниже — условный непринятый вопрос; обычное исправление source identity не ожидает его решения.

## AD-E02-01. Реальный выход метода → policy metric и unit

**Нужное решение.** Как selected compiled program связывает точный method node/output slot с ObjectiveSpec/MetricSpec, единицей и допустимым преобразованием? Отдельно выбрать: узкий versioned adapter для точного соответствия Foundry Unit и IR Unit либо обязательный явный derivation law в compiled source для каждого преобразования. Совпадение имён и caller `metric_units` таким контрактом не являются.

**Разрыв сейчас.** MethodDispatcher возвращает slot_outputs, но graph execution не сохраняет их как полный source для policy metrics. SimulationResult/source admission не связывает такой output с выбранной метрикой. Runtime оставляет unit неизвестной; это честное ограничение, а не повод назначить unit по имени. Related criteria: B31 и fiscal B108; это связи исследования, не closure proposals по этим ID.

**Варианты.** (A) Оставить текущие refs/registries как есть: оценка unit-qualified остаётся unavailable. (B, рекомендуется) Extend существующие ProgramGraph/ExecPlan, MethodSignature/Dispatcher, CAS, SimulationResult source admission и IR registries одним compiled output binding и owner-recomputed relation. (C) Свести все numeric dictionaries к QuantityValue: отложить, потому что сама форма value/unit не связывает producer/run/derivation. (D) Новый самостоятельный algebra/evidence subsystem: не рекомендуется, дублирует существующих owners.

**Что ратифицировать G.** Поля/owner/version binding; источник executable identity и replay-equivalence для выбранного backend; допустимые exact unit adapters и derivation laws; manifest edges к SimulationResult или новая payload/schema version; legacy numeric-only migration; producer/receiver/public surfaces. Рекомендация: additive manifest edges при неизменном старом JSON, exact selected input/candidate/registry refs, без переинтерпретации старых Metrics. Для отсутствующей или некорректной связи — typed limitation/refusal; размерность не означает causal calibration, эмпирическую достаточность или authority.

**Прототип и текущая проверка.** Подготовлен generic registered-method/CAS replay prototype, с намеренно узкой DRE weights→ratio projection. Его первый реальный RAW replay на fe046fef выполнил все 4 случая, 4 FAIL: центральный reader прочитал Core tagged floats через raw json.loads, и настоящий DRE отказал на dict вместо float. Exact RAW origin подтверждён. Это внутренний codec defect, исправляется независимо; положительного prototype receipt пока нет. Ни один MethodDispatcher-only результат не заменяет будущий ProgramGraph→SimulationResult→fresh owner→L3/L4 falsifier. Method ABI не является executable identity.

**Подробности.** `20261020-method-output-metric-unit-g-question.json` рядом с этим индексом содержит reuse/extend/consolidate/build, полный footprint, migration/status/authority/time и минимальный falsifier. Исходник: `LOCAL/raw/measured-output-owner-prototype-20261020-r2/decision-r2.json@8ee914b3e6c843ad4fdbeccf9039abfa9cdbdb989cc8dd99370f53b3f63d652c`. Actual RAW result: `LOCAL/raw/root-measured-output-controlled-raw-r4-fe046fef-20261020-r1/actual/result.json@7ef2d078ca737305eff5dfd2b9c14e867c929c3fbbad325cda3cf53f88659852`.

## AD-E02-02. Shared budget: competing jobs и вложенные folds

**Вопрос о границе, а не доказанный новый scheduler requirement.** Подтвердить, удовлетворяет ли исходному B56 существующий общий Runtime/study permit при последовательных folds внутри каждого admitted job. Если criterion требует именно вложенного parallel fold execution — определить, как folds получают permits того же owner: cap unit/weights, reentrancy, очередь, cancellation/release, deadlock и accounting. Денежный ledger не является compute permit.

**Что реально проверено.** Internal Runtime/worker/native-TMLE route с cap 1/2 и bridge-removal прошёл. Whole command: 56 случаев = 52 PASS / 3 FAIL / 1 intentional child SKIP; все вызовы завершены, source unchanged, cap не превышен. R4 integration — 3 PASS / 1 SKIP; соседний TMLE worker-pool module — 49 PASS / 3 FAIL, где выявлен retry-view composition defect. Это не inherited red и не общий native green. Requested `parallel_folds=true,max_parallel_folds=0` сохранён; фактические folds serial. Witness использует internal `_enqueue_job`/manual dispatch и fresh CAS/control-store reader, а не ordinary HTTP POST/fresh GET; safety blockers в candidate fixture отключены явно. Внешний qualifying production workload не установлен.

**Рекомендация.** Reuse уже выбранный D03 outer owner и стабильные serial folds как строго ограниченную основу. G оценивает её по исходному criterion; это не разрешение сузить criterion. Если нужен inner-fold fanout — extend тот же permit owner, не создавать второй scheduler, и закрепить отдельный contract/acceptance signal. Не блокировать accounting, worker-composition repair и HTTP input design ожиданием этого решения.

**Подробности.** Уже tracked `20261020-shared-runtime-admission-scope.md` рядом. Actual: `LOCAL/raw/root-r4-requested-native-whole-4gib-76ea932f-20261020-r2/actual/result.json@2ba7f614a44bc59b6986f7789074c7f8ec3e1cc227113eca80c6a1194fae76f1`; три child profiles лежат в его `r4-child-receipts/`. Нужные внешние L01 F-B56 inputs: named workload, active profile, common permit identity/cap unit, complete competing roster, recipe и result reader; G-choice их не создаёт.

## AD-E02-03. Универсальный observational input через обычный HTTP

**Нужное решение.** Как выбрать method observational source в WorkflowRunRequest и донести immutable selection до ExperimentState/реального method owner? Сейчас публичный POST этого root не передаёт. R4 raw source имеет exact kind/media/profile, но `artifact_schema=null`; HTEObservationalData — runtime DTO без artifact contract ID/version. Существующий versioned ObservationMethodInputEnvelope нельзя объявить HTE producer одним новым label.

**Варианты.** (A) Typed selected ArtifactRef → существующий method-owner parser, только с явно принятой legacy/unversioned candidate границей. (B) Extend существующий versioned envelope настоящим HTE target/producer и reader migration. (C) Ukraine/panel binder: сохранить для его purpose-specific scope, не использовать как универсальное решение.

**Что выбрать G.** A или B; legacy window/retirement condition; canonical immutable source/method intent и его owner; selected-profile requirement; absence versus explicit-null/malformed/wrong-kind/profile/method typed refusal; public fresh GET evidence surface. Рекомендация A лишь при ратифицированной candidate-only границе; иначе B. Нельзя выдумать schema, закон, идентификацию, custody или currentness.

**После решения.** Один настоящий ordinary POST→ControlWorker→RunLifecycle→Scientist/TMLE→CAS→fresh HTTP GET, cap 1/2 и removal/refusal controls. DTO/intake/OpenAPI/generated clients/browser companions входят в scope. До этого такой HTTP positive — UNRUN.

**Подробности.** `20261020-observational-http-input-g-question.md` и `.json` рядом — source-bound варианты, точные method/parser pins и вопросы G. Исходники: `LOCAL/raw/r4-http-readiness-76ea932f-20261020-r1/g-observational-http-input-architecture-question-20261020-r1.md@e0838cb15d5d9d206161acc484e3ea7c8e96bf074b50bfb3617bb6c08e96d310` и `.json@0c06cd45cff8b00d1e072186ad270eac36b8ec8491a6656ca73f7935f91809aa`.

## AD-E02-04. HTE point estimate without supported population-ATE inference

**Decision needed.** For the shared EconML HTE result family (CATE, DML, selected S/T/X, and ForestDR), choose whether a valid fitted point with no supported population-ATE interval becomes (A) a versioned `limited/inference_unavailable` point-only candidate with no ATE bounds and a typed content-bound inference-basis reference required for finite-interval success (recommended), (B) a typed refusal, or (C) a finite interval only for a named method/profile whose owner supplies and G accepts the inference law and scope. Cross-row CATE dispersion, finite fields, method names, warnings, and confidence-level labels do not establish a supported ATE interval.

**Reuse and boundary.** Extend the existing *candidate* HTE Estimate/Refusal union with `EstimateLimited` and a content-bound inference-basis reference; give it a new HTE identity and preserve historical HTEResult v1 bytes/replay. Current CausalEffectReport cannot mean `inference_unavailable` without misusing its generic non-success statuses, and cannot satisfy the required HTE output slot alone. The decision covers four final shared-extractor producers, not the candidate-only scoring call. The real ForestDR witness is a real-backend synthetic-fixture adapter failure, not a no-inference runtime or production claim. B31 remains held; V4/V7 remain predictive-calibration routes.

**Decision packet.** `g-choice-hte-ate-inference-unavailable-20261021.md` contains the source-bound B31 citation, HTE schema/caller crosswalk, reuse options, versioned inference-basis proposal, legacy interval-guard residual, migration, authority/time semantics, and falsifiers. G acceptance is false; this index entry closes no finding.

## Условный резерв: paged K_ref

Пока не требуется выбирать новую representation. Сначала extend существующие DataForge/SKG/L3 owner readers до полного streaming с неизменными row/time/profile/hash semantics. Первый 19-path candidate находится на independent HOLD по отсутствующей composed parity/removal/source-replacement проверке и двум public-artifact companions; это engineering queue, не новая semantics. Старый actual served abort на 3 GiB не доказывает OOM и не доказывает, что полный map не помещается. Если после исправления и измерения остаётся именно floor полного immutable map/copy, тогда отдельный G choice: bounded eager budget либо paged immutable CAS view с новым consumer/iteration/hash/migration контрактом. Сейчас не выбирать pagination авансом.

## Что не передаётся G как архитектурная развилка

CAN DTO null preservation, Core decoder, work-packet profile/presence, worker retry-view composition, source-census companions, producer/GET wiring в уже заданном контракте, resource resolution и native gates исправляются по существующим owners. G независимо принимает код; мы не просим заново выбирать их архитектуру. Внешние law/refinement/conditional law/calibration, issuer/permission/custody/currentness и authentic workload требуют настоящих inputs и provenance, а не waiver. Historical closures, включая B198, не переоткрываются и не увеличиваются этим пакетом.

## Формат ответа G

Для каждого AD ID: выбранный вариант и rejected alternatives; точный contract/owner/schema/rule version; allowed/forbidden scope; status/authority/time semantics; migration/legacy window; minimum producer/consumer/public-surface footprint; acceptance + adversarial/removal signal; remaining genuine external inputs; integration/adjudication boundary. Это даст исполнителю достаточно конкретное решение для реализации без нового абстрактного круга вопросов.

Pattern pass: P01/P02/P04/P05/P07/P08/P10/P29/P31/P32/P37/P38/P40. Target: один source-bound producer→artifact→bridge→consumer с проверяемым admission; незамкнутые policy metric и HTTP paths остаются `bridge_missing`/`verification_missing`/`surface_missing` в названной границе. Никакая строка этого decision packet не является formal closure.

## B161 follow-up to the existing R8 question (same decision class)

**Decision requested:** choose whether this route stays historical-max-only (B161 remains limited/held) or exposes a separate candidate current projection that may refine only through a real owner-produced, content-bound same-scope relation. Recommendation: retain history and independent risk; extend the existing uncertainty owner with a separate current projection only after the permitted profile/relation is supplied and the fresh consumer recomputes subject, value/estimand, inputs, procedure/profile, rule/version, and valid-time/currentness. This is a runtime/status choice; G does not invent the scientific law, independence, issuer, or currentness fact.

Evidence: original B161 criterion `B_r19_original.md@9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5` lines 4165–4176; D04 `02-decisions.md@6c736256699df2d5283d4fca939a4d81f12a6af3a3a08c190eec08c2bc998701` lines 39–53; current routing-only evidence and falsifier are in [the B161 follow-up packet](b161-current-scoped-refinement-followup-20261021.md). The older R8 packet is local/untracked and absent from inspected G commit b7adafe; repository state cannot establish G received it. Append/resolve this one existing B161 question only if G has not already received/disposed it. Preserve B198; AD01–03 and pending CAN/HTE questions are unchanged. `G_acceptance=false`; no closure IDs.

## Conditional DS17 source-identity/import-purity clarification (unassigned proposal)

**Question only if supported by a cited ratified contract:** Does the DS17 owner require whole selected-module import purity as an authority property beyond its currently evidenced source-bound identity and declared-route contract? No reviewed DS17 source establishes that requirement. If no supporting citation is produced, mark this conditional clarification not required and continue the narrower source-identity repair as ordinary owner engineering.

Proposal: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/ds17-source-binding-vs-import-purity-proposal-20261021.md` (postimage SHA-256 `43dd342007fccaaa7c2b62cd3c368b5505f81c548613425f2d8242b32f0d9af9`). It recommends parsing route and summary expectations from exact selected source bytes, then comparing loaded maps, tuple rows/class/facade/module origins; the paired map-plus-tuple joint-mutation falsifier must refuse. Whole-module purity, if supported by a ratified requirement, is a separate higher-cost contract with its own complete selected-source denominator and adversarial effect grammar.

This is unaccepted and non-blocking: owner engineering continues; no decision owner is inferred, no release gate is created, `G_acceptance=false`; no closure IDs.
