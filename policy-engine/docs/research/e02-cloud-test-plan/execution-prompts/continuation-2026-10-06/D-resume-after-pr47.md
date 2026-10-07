Current criterion-scope correction: [B109/B111/B100 errata](../../integration/reviews/original-criteria-errata-2026-10-06.md). B109 is fast/direct comparator acceptance; the served provider is additional capability. B111 keeps invalid-state/partial-denominator/finite-or-unavailable semantics; schema-v3 migration and finite-positive underflow are separately scoped. Historical outcomes and status counts below are retained.

Current delta instructions: [latest D actions](../../integration/reviews/D-next-wave-2026-10-06.md). For E also use [PR38 r2 continuation](E-resume-after-pr38-r2.md). Apply historical tasks below only to the still-unresolved original criterion; do not repeat already-measured unchanged source.

# D — продолжить после PR47 до завершения собственных критериев

Ты — облачный оркестратор D. Продолжи существующую append-only работу; итог PR47 — промежуточный результат, не окончание задачи. Закрой доступные engineering/mechanism/consumer задачи, запроси минимальные реальные inputs у их canonical owners через committed handoffs и доведи каждый исходный criterion до честного решения. Не возвращай ещё один пакет `limited`, если собственный исправимый дефект или отсутствующий ordinary bridge остался без выполненной работы. Missing scientific law/authority не выдумывай; такие критерии сохраняют предметный held/input packet.

## Admission и чтение

Полностью прочитай root `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, [HANDOFF](../HANDOFF.md), execution-organization README, full result pack, [решения D](../../closure-decisions/D.md), [аудит G](../../integration/reviews/D-pr47-continuation-audit-2026-10-06.md). До использования результатов выполни `import_results.py --check`, прочитай `verification.json`, затем `query.py --unit D --failures-only --limit 30` и точечные запросы. Полные owners/cards/criterion occurrences бери из TSV и committed criterion accounting, не из query summary.

Выполни fetch origin, проверь attached branch/path/status и workspace admission до создания checkout. Возобновляй подходящий собственный checkout, не создавай пустую новую базу от main, теряя D history. Неожиданные HEAD/tree изменения не исправляй reset/rebase/switch. Зафиксируй свежий G checkpoint и собственный slice-base до нового кода.

Проверяемые исходные pins:

- Published branch `codex/e02-D-published-root`, [PR47](https://github.com/DenisKopylov/polisyos/pull/47), receipt head `cae5589aa7080b628e93d594eeb4ff7c2fc2414d`, tree `352f6a29da22ab09588fba0faaad66a1ff35005d`.
- Frozen implementation `3f38e7cbdc8ba544fe4d0c69d93dbb3a4a629973`, tree `e674e22edb8d94d47579326135a786c832402a15`, original base `198076863e143dea9f89f02734b13d50dae3eed5`.
- Источник передачи: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/published-final-closeout.json`, `published-final-criterion-accounting.json`, `published-closeout-final/README.md`, `published-closeout-final/G-local-production-inputs.json` на exact receipt head. Пути `/workspace/...` внутри исторических contexts — provenance, не требование наличия такого пути у следующего исполнителя.
- G checkpoint 10: record `6f869f39d04deaff7eda9b9047848912605beca5`, source `acdc3536f93f085d665a7b53460935525373d015`; fresh remote может быть новее. D source не принят в G. Shared ledger уже B 1.1, D старый 1.0 не накладывается поверх него.

## Полная очередь, без сокращения criteria

Пересчитай 17 bundles / 45 IDs / 46 occurrences; LA-015@CTL-01 — supplier companion, closure owner SRV-03. Сохрани исходное acceptance text/binding и добавь новый exact source, consumer, output, residual в каждый row. Исходное распределение: 35 limited, 7 held (B108/B131/B134/B137/B157/B161/B164), 3 open (B109/LA-014/LA-015), 0 closed. Нельзя заменить требование профилем, который проще сделать зелёным.

| Canonical bundles | Все связанные IDs | Очередь |
| --- | --- | --- |
| STR-01, STP-01 | B106, B107, B41, B122 | Scenario denominator, threshold, stopping unit/direction, реальный DOE consumer. |
| OPT-01 | B108–B111 | Точная геометрия/availability и A frontier provider/export; fiscal input отдельно. |
| OPT-02, OPT-03 | B112–B115, B127 | Effective action/corpus/GP state, NN restore, ordinary configured bridge. |
| OPT-04 | B116, B117 | Registry basis/pointer/CAS, real consumer/race и B→D edge. |
| CTL-01, CTL-02, CTL-03 | B118–B126, LA-015 companion | Ordinary lifecycle, RNG/Sobol/identity, B-ledger port, cost stopping. |
| TRN-01, TRN-02, TRN-03 | B128–B137 | Exact refs/native generation, local+transferred filters, temporal replay, issuer inputs. |
| FUN-01, FUN-02, FUN-03 | B156–B165 | Factory/split/owned prerequisite, sample port, status/calibration, typed permit boundary. |
| SRV-01, SRV-03 | LA-014, LA-015 | Served factory, persisted restore/resume, cutover/readers/rollback. |

Организуй полезные прямые subagents по независимым owners/проверкам, адаптивно до 20 при достаточной очереди: math/oracle; native cost+ledger dependency; transfer/state; stress/stopping+DOE; served factory/promotion; optional profiles/companions; independent reviews. Один writer на shared file; reviewers не авторы. Помощники не создают детей и не пишут в G integration. В облаке не вводи квоты CPU/processes/numerical threads/test workers; сериализуй только реально конфликтующий DB/cache/port/governed writer. Производство в cloud не переносить.

## 1. Исправить quantity и intake, которые уже можно закончить

**Hypervolume/availability (B111).** Откажись от bounding-box proxy в `scientist/methods/autotune/pareto.py` для >2 objectives. Front `(2,0,0),(0,2,0),(0,0,2)`, reference `(0,0,0)`, maximizing: текущая proxy=8, exact union=0. Оставь точную 1D/2D реализацию и независимый маленький O(n²)/box-union oracle. Предпочтительный adapter — уже имеющийся BoTorch partitioning; direction/reference/normalization и поддерживаемую размерность объявить явно, exact mode проверить по pinned version. [Официальный API](https://botorch.readthedocs.io/en/stable/utils.html). Не добавляй новый optimizer/GP/library без фактической нужды. Если exact backend/profile недоступен, вернуть typed unavailable вместо числа; не объявлять произвольную размерность точной.

Исправь также `MultiObjectiveStrategy.compute_hypervolume()` unavailable→0 и finite scalar admission `raw_value=10**400` → uncaught OverflowError. Reuse float-convert-then-finite boundary из `search/frontier.py`, сохраняя strict bool/type rules. Один numeric admission mechanism должен отказать malformed/overflow с row index/reason, не обрушить batch. Typed unavailable/reason провести через registry/indicator/stopping/frontier API; один producer fix без consumer недостаточен. Positive exact nonzero и computed zero; negatives unsupported backend, empty/unassessed basis, invalid reference/point, huge integer; marker-preserving removal и независимая 3D geometry.

**B110 отдельно.** Frontier, serialization/round-trip и `is_dominated` сохраняют одно отношение по полной coordinate identity metric+split+direction/unit/version. Display-label change не меняет решение, different splits не исчезают; duplicate full coordinate явно отказывает. Проверь реальный persisted/readback путь, не только helper.

**Cost decoder (B120).** Не повторяй dict-only underflow тест. Настоящий `GatewayLLMClient._post_json` делает `json.loads(raw_text)`; positive numeric token `1e-1000` превращается в zero до raw-cost guard. Сохрани lexeme/Decimal на каноническом JSON/intake seam: [`parse_float`](https://docs.python.org/3/library/json.html) — существующий стандартный механизм, но adapter обязан сохранить потребителей обычного payload. Проведи response-text fixture через actual decoder → enforcer/middleware → reopened B ledger. `1e-1000`/`-1e-1000`, invalid-present и conflicts refuse без ложного zero/release; literal zero допускается; обычная paid response списывает один раз. Bucket: тот же raw-cost класс глубже; widening seam один раз, не лестница helpers. Provider fixture не invoice truth.

## 2. Один бюджетный контракт и реальная factory

B DUR-01 canonical owner готовит совместимый additive successor единого B `spend_receipts`/unknown-ack ledger. D отдаёт typed requirements и consumer tests, не пишет параллельно shared ledger/middleware/Gateway owner. Нужны immutable event ID+payload digest, request/provider/run/stage/evaluation scope, reservation, distinct budget keys, amount/unit/source и cache lineage; settle/debit/release в одной durable transition. Exact retry возвращает первоначальный receipt; changed payload/scope с тем же ID отвергается без byte mutation. После ambiguous publish reservation остаётся pending, caller resolves/retries тот же ID, не создаёт новый и не сообщает zero. Schema version/migration назначает B; D-shaped 1.0 нельзя молча принять как B 1.0.

Портируй только D-owned enforcer/funnel consumers на новый receipt, сохрани attribution/source/limitations в результатах и costing snapshot до `CostBudgetStopping/SearchController`. Получи B-W09 обычную configured factory и A stage context producer: caller `_evaluation_id` остаётся correlation text до owner binding. Cache class name/module/flag не receipt; настоящий cache-owned content/context-bound reuse даёт нулевой *новый* charge с lineage, lookalike/tamper/missing receipt не допускают бесплатность по маркеру. Test factory → provider response → receipt → stopping/funnel → fresh reader; removal settlement при сохранённом trace cost обязан провалить проверку.

Multi-key settlement нужен только если реальные A/B producer и D consumer используют несколько budget keys; иначе сохранить canonical single-key поведение и самый малый additive receipt. Не создавать schema project ради optional attribution.

## 3. Сохранить сильную GP работу, закончить state/transfer

Не заменяй BoTorch/GPyTorch `SingleTaskGP` самописным GP или новым optimizer. GP26 уже содержит независимый fixed-parameter NumPy mean/full-covariance oracle и реальные CAS→GP 8/7-row fit/restore. Не прогоняй это заново без changed dependency; не выдавай model.posterior этого же model за независимый oracle.

Проверь ordinary `SearchConfig.transfer_manager` → configured bridge → exact CAS → GP fit: explicit injection positive уже есть, default configuration не established. Wire-existing bridge при предназначенном caller contract, с changed-ref/basis/direction/false outcome negatives до fit. NN `_warm_data` надо сохранить через existing state/checkpoint с content-bound refs/basis и восстановить fresh instance; same corpus/next proposal должны совпасть с uninterrupted поддерживаемым профилем. Не обещать cross-version/unsupported strategy profiles.

В lessons убери future evidence из past-as-of: creation/evidence anchor позже query time не имеет zero age и положительного confidence. Одна admission rule для local query, `query_with_transfer`, `materialize_transfer`; `last_accessed` только retention. Реальная revalidation/time authority остаётся owner input. Native vector generation готовится отдельно, валидируется/загружается, затем переключается одним immutable pointer; failure/tamper оставляет старую generation coherent. B CAS→TRN-02 нужен exact owner minref+combined receipt и second process, не второй ANN lookup вместо ArtifactRef.

Закрой optional-backend discovery класс одним supported marker/profile rule: minimal/runtime без Torch/HNSW extras собираются без import/collection errors; extras profile действительно исполняет GP/vector defining checks. Не преврати отсутствие backend в PASS численного свойства.

## 4. Stress/stopping и funnel не должны измерять proxy

B106 L5 partial/unknown repair присутствует и имеет bounded 57 PASS; сохраняй его. Два остатка: missing violation threshold может давать robust/score1; blueprint считает grouped issues вместо per-scenario denominator. Исправь общий producer→report→blueprint score basis: сохранённые attempt/scenario counts до grouping/top-k, отсутствие threshold → unavailable, observed finite fraction не population probability/model uncertainty. Негативы missing threshold, fixed stream с разным grouping/top-k, incomplete/unknown/empty. E DOE-01 должен получить exact D output и показать oversize refusal **до** exponential materialization, round count/direction и truthful fraction. В STP/convergence сохраняй units/tolerances/embedding version; missing basis не convergence.

B158/B159: уже есть full/split L3/L4 physical-event controls и owned reservation prerequisite recheck; не возвращай их как отсутствующую generic resume feature. Закончить default factory и actual resource producer, revalidate следующий edge на реальном изменении prerequisite. Unrelated spend/same ticket/stale basis не разрешают resume, повторный charge или terminal success. B160/B162/B163/B165 имеют полезные empty/width/tracker/final-action механизмы: reverify delta и ordinary consumer, не повторять уже исправленный code ради нового PASS.

Существующие selectors на D source: `tests/integration/scientist/methods/search/funnel/test_orchestrator.py::test_native_policy_callers_full_split_actual_events_and_fresh_reopen` и `::test_actual_spend_does_not_resume_but_released_owned_capacity_rechecks_remaining_work`. Их positive/recheck scope — bounded native callers; actual default factory/authoritative producer debit отдельно. На changed ledger/parser повторить именно affected consumers.

B157 native raw-sample/estimand port всё ещё отсутствует: Foundry 20/80-draw oracle не превращает native labels500/64/32 в реальные samples. B161 same-subject/value/input/rule/time supersession law отсутствует; не выбрать global min/last-write. E/F/input owners передают native report/samples/profile, B wires runtime factory, D consumes. Составь минимальный packet с typed producer/artifact/bridge/consumer и точной локальной recipe, не blanket production demand.

## 5. Открытые service задачи и held permit

LA-014/SRV-01: подключить существующий SearchService/runner к admitted ordinary served factory/caller; request→evaluation→persisted state/frontier→fresh API/readback, ask/tell compatibility и unknown/duplicate IDs. LA-015/SRV-03: persisted restore/public resume, reader-window/import retirement, controlled cutover и rollback на new/resumed/stopped/empty/evaluator-failure cases. CTL-01 только supplier. При отсутствии appointed served caller запиши точный owner/input packet, но закончи доступный persistence/consumer mechanism; не останавливай весь D.

B116/117: сохранить strict primitive admission/local pointer races; B CAS→OPT-04 combined owner source/input и under-lock pointer reread необходимы отдельно. Scientific evaluator/source/split rights и distributed/power-loss guarantees не следуют из local POSIX fixture.

B164: найти существующего issuer/verifier/write owner, не создавать authority subsystem. Нужен typed permit binding run/candidate/ticket generation/purpose/schema/rule/provenance/time/revocation; verify и effect сериализуются с revoke на existing commit boundary. Missing/fake/wrong issuer/purpose/scope/expired/stale/revoked — ноль effects; revoke между preflight/commit при bool=true — ноль; valid owner-issued positive — ровно один persisted effect/fresh readback. Нынешний bool/callback refusal и guard-removal2FAIL сохранить, valid positive пока UNRUN/bridge_missing. Фикстура D не appoint owner.

## Companions, verification и итог

Параллельно получить owner disposition для completed B04 state reads, B19 module budgets, B23 published links; schema/architecture/frontend incomplete остаются incomplete до complete outputs. Search/autotune public child claims сверить с inventory: либо реальные supported exports+generated companions, либо accurate internal classification. GP/RL/Pareto format refusal/migration требует structured compatibility там, где breaking contract. Static production-invocation AST — bounded diagnostic, runtime chain подтверждает actual integration witness.

Freeze source → все независимые reviews → один expensive wave для своего final changed denominator. До freeze targeted checks по changed contracts; старые 15 immutable lineages/617 executions не выдавать новым replay. На новый shared contract повторить affected consumer checks. P41 inherited только exact **slice-base** command + complete input zero-overlap; иначе not_established. G позже выполняет общий integration replay/data-dependent closeout на общем freeze, не после каждого merge.

Каждый законченный slice publish рано на собственной topic branch, сохранить оригинальную history, implementation commit/tree и отдельный committed HANDOFF JSON с full code/tests/companions, original criteria, actual runtime/independent oracle/negative, consumer/API, complete deciding outputs и limitations. Git — обязательный канал G, не предполагается автообмен чатами. Только G публикует integration; main не разрешён. Огромные derived/raw dumps не коммитить, tracked source не копировать.

Финальный ответ D: complete 45-ID/46-occurrence ledger и matched original criteria; отдельно code-ready/accepted G, closed proposals/limited/held/open, missing input/decision с appointed owner, skipped backend и remaining verification. Каждый исправимый собственный residual должен быть исправлен и испытан либо обоснован реально отсутствующей capability, не просто переименован `limited`. Pattern pass P01/P02/P05/P09/P10/P14/P27/P29/P32/P35/P37/P38/P40/P41. После second same-class escape — widen или bounded residual с falsifier, не endless ladder.

Production data остаётся локально read-only. Сохраняй код, документацию, unique inputs и deciding outputs; отработанные воспроизводимые fixtures/env/checkouts можно переносить только в штатную Корзину после publication/readback и inactive-user check. В cloud без Trash только точный перечень кандидатов; permanent deletion и очистка Корзины запрещены.
