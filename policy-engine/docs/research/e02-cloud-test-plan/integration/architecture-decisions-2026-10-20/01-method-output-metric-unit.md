# AD-E02-01 — actual method output → policy metric / unit

Disposition: **selected for implementation**. Code acceptance и formal closure отсутствуют. Пути source ниже относительно `policy-engine/src/polisyos/`, snapshot `11ff2421e04223fc961dd5a520768fd75bafe1e2`.

## Выбор и его предел

Extend существующие compiler/ProgramGraph/ExecPlan, MethodDispatcher, CAS, EnvironmentManifest, Foundry source admission и IR Metric/Units owners. Новый механизм состоит из compiled binding и одного execution bundle index; отдельный execution engine, provenance database или quantity algebra не нужны. Existing `ExecuteArtifacts.derived_artifacts` — carrier, а не повод создать параллельную transport систему.

Разделить три проверяемых отношения:

1. **Execution origin:** выбранная owned попытка действительно вернула эти slot bytes при этих inputs/build/backend.
2. **Metric meaning:** выбранный producer contract или исполняемый закон связывает output с конкретным objective/metric, population, denominator, time и quantity role.
3. **Representation:** exact adapter или закон переводит установленную величину в требуемое представление unit.

Ни одно отношение не заменяет другие. Даже все три вместе не устанавливают causal identification, calibration, empirical adequacy, внешний закон или право публикации. B31 требует ещё исходный same-estimand uncertainty join; B108 — конкретный fiscal alias/sign/unit law.

## Наблюдаемый разрыв

`foundry/execute/_internal/graph/__init__.py:510–541` получает `MethodResult`, но проводит дальше patch records, теряя `slot_outputs` и artifacts. `core/contracts/foundry.py` содержит строгие ProgramGraph 0.2.0 / ExecPlan 0.2.0 и SimulationResult 1.3/1.4. `foundry/execute/api.py` уже сверяет selected graph/plan/candidate/registry/basis; это существующая точка расширения, а не отсутствующая admission система.

`ir/kernel/metrics.py` не определяет typed смысл metric одной строкой description. `foundry/methods/base.py` различает slots/ABI и units, но ABI не равен executable identity. `NativeValueEstimandBinding` в `ir/analytics/uncertainty.py` — полезная semantic shape, явно `contract_only_nonproduction`; её caller labels не становятся provenance. `_persist_environment_manifest` в graph executor теряет selected profile — исправить этот существующий ref projection.

## Контракты, владельцы, версии

Ниже **новые предлагаемые schema IDs**, а не утверждение об уже существующих contracts. Зарегистрировать их через штатный schema/public-surface inventory; имена Python типов допускают местную конвенцию, смысл и версия обязательны.

| Contract / version | Owner | Обязательное содержание |
|---|---|---|
| `policyos.foundry.method_metric_binding_set.v1` | Existing compiler + IR metric owner | Exact graph ref; selected candidate/problem-frame/objective/metric/units refs; binding entries и selected law/adapter versions |
| Binding entry внутри set | Те же owners | Unique binding ID; graph node ID; exact method FQN/version/ABI и slot; typed metric definition / derivation; expected output type/shape/axes; quantity kind/role; target IR unit; scope/source selectors |
| `policyos.foundry.method_execution_bundle.v1` | Existing graph execution owner | Exact plan/basis/binding/environment refs; run/attempt opaque IDs; полный ordered occurrence inventory и captured output refs; actual backend/build/RNG; outcomes и times |
| Guarded committed execution selection | Existing Runtime run/attempt owner; extend его persisted record | Atomic winning attempt tuple, terminal/partial outcome и exact selected SimulationResult + bundle refs. Не отдельный ledger |
| Owner metric projection | `foundry/execute/api.py` → existing Scientist metric owner | Persisted typed observation в existing PolicyEvaluationVector с version bump 1.1→1.2; exact binding/output/run selection, law/verifier context, value/unit и limitations. Deep-immutable primitives, не mutable caller maps |

Binding semantic definition использует D04 EstimandAST/существующие quantity/uncertainty contracts, где они действительно выражают нужное свойство. Если их недостаточно — smallest typed extension у того же owner: операция, typed input roles, subject/population/filter, axes/alignment, denominator, condition/exposure, horizon/source epoch, quantity kind и level/delta/stock/flow role. Это candidate policy intent, не реальный causal law. Свободный текст или новое поле `semantic_kind="employment"` не являются исполнением определения.

Исполняемый derivation handler выбирается по exact registered ID/version/code digest из compiler-owned rules, а не import string/LLM formula/caller lambda. Он получает только content-bound typed inputs, проверяет их реальные axes/row alignment/units/time scopes и вычисляет output. Unsupported expression получает typed unavailable, а не произвольный `eval`. Существующий producer, уже выдающий точно такой metric contract, может использовать identity law; контракт всё равно должен разрешаться и соответствовать реальным output/input semantics.

## Ациклическая CAS модель

Порядок записи фиксирован:

`graph + selected registries/candidate → binding_set → ExecPlan manifest → execution basis → method output payloads → execution_bundle → SimulationResult manifest → owned run selection`.

- BindingSet ссылается на graph, **не на ExecPlan**. ExecPlan selected manifest имеет единственную роль `method_metric_bindings` со ссылкой на set. Не добавлять обратную ссылку из graph на set, содержащий graph ref.
- Bundle ссылается на уже существующие plan/basis/binding/environment и output payloads. Он не содержит ref будущего SimulationResult или будущего run commit.
- Если execution использует observational selection AD03, existing execution-input basis получает selected input role `admitted_observational_intent`; bundle связывает тот же exact admitted-intent ref через basis и проверяемую input relation. Не копировать intent payload. Для route без observational selection эта роль отсутствует и не изобретается. Для causal route с другим canonical result его result manifest связывает тот же intent; навязывать SimulationResult этому route не нужно.
- SimulationResult selected manifest имеет одну роль `method_execution` → bundle. Guarded run selection записывается последним и указывает оба selected refs. Run/attempt IDs в bundle — opaque correlation IDs; не self-attesting доказательство run origin.
- Сохраняем JSON SimulationResult 1.4 и legacy numeric Metrics без переинтерпретации. Новые selected InputRefs требуют manifest schema v2+ по существующим правилам. Если меняется payload SimulationResult или ExecPlan, version bump обязателен: additive manifest edge не разрешает добавлять скрытые payload поля.
- Содержимое CAS пишется прежде owned pointer. Crash оставляет unselected CAS objects, не частично принятый run. Не требовать распределённой атомарной транзакции между CAS и control store.

**Atomic owned tuple:** `(run_id, attempt_id, current_fence, run_outcome, exact SimulationResult view, exact method_execution view)`. Compare-and-set по действующему attempt/fence; idempotent повтор только при том же полном tuple. Раздельные updates refs запрещены. Stale attempt сохраняет diagnostic bytes, но не меняет current pointer. Fresh reader проверяет tuple и manifest relation, а не caller-created run label.

Partial aggregate не уничтожает успешную работу: existing status calculus определяет eligible committed producer occurrences в partial результате. Их candidate evidence может сохраняться. Failed/skipped/cancelled occurrence не выдаёт fabricated output, а superseded attempt не считается текущим. Выбор historical attempt должен быть явным и показывать historical/partial status; GET current никогда не подменяет его старым успехом.

## Захват и проверка

Graph validator отвергает duplicate node IDs, невалидный plan order, неоднозначные selected roles и bindings. Feedback/repeated execution различается `(node_id, iteration/occurrence_id)`, а не last-write-wins dictionary.

В точке фактического dispatch записываются resolved signature, canonical parameters/defaults, input refs/pre-state identity, actual seed/RNG, requested и actual backend/fallback, start/end/outcome. Inventory содержит **все planned и actual occurrences**: success/failure/skip и причину различия. Для успешного occurrence generic inventory включает все реально возвращённые slots, type/shape/codec и capture state. Для выбранных/обязательных outputs сохраняются actual bytes один раз; существующий typed CAS output переиспользуется после проверки. Незатронутые тяжёлые outputs могут быть `not_retained`, unsupported Python value — `unsupported_codec`; ни то ни другое нельзя выбрать доступным metric. Не pickle/repr/stringify arbitrary objects. Полный inventory не означает копирование всех tensor payloads.

Source admission получает exact selected refs **и owned run context** для run-origin claim. В standalone режиме `admit_execution_source(store, ref)` может подтвердить внутреннюю CAS consistency, но не утверждать, что этот артефакт — результат конкретного принятого Runtime run. Consumer не может обойти этот режим собственного назначения run_id.

Fresh **admission worker** проверяет hash/profile/kind/media/schema, связи с выбранными registries и program, occurrence coverage, controlled run selection, исполняет metric law и unit relation на captured bytes. Это compute operation под AD02, не HTTP reader. Existing producer records — evidence происхождения в доверенной границе Runtime, не независимый научный oracle. Проверка captured value/derivation не требует заново исполнять весь graph.

### Persisted admission и дешёвый fresh reader

Одного in-memory cache недостаточно: cold GET после restart иначе снова декодирует arrays и исполняет law. Reuse existing `scientist.policy_evaluation_vector` и writer `_persist_policy_evaluation_vector_to_store_impl` в `scientist/nodes/builtins/decide/policy_runtime_artifacts.py:178–206`. Он уже сохраняет vector и selected source edges. **Расширение:** typed optional-by-absence `method_metric_observations` в payload, schema version **1.2**; old 1.1 остаётся отдельным читаемым limited contract. Это предлагаемый новый version, не уже опубликованный.

Observation содержит unique binding/metric ID, finite value или explicit unavailable, exact unit/quantity role, source bundle/result/selected output refs, law/adapter/verifier versions, checked build/context, predicate evidence и limitations. Set generic по compiled bindings, без government/employment-specific списка. Existing `SourceMetricObservation` 1.0 в `scientist/methods/search/objective.py:25–88` имеет Literal government-balance semantics: его **не** переименовывать в generic observation и не менять исторический смысл. Новый nested typed record у того же owner не становится отдельным provenance subsystem или unchecked metadata bag. Legacy values могут оставаться в vector, но новый qualified consumer принимает только bound observation; отсутствие/invalid не заполняется alias/default/channel score.

Верifier сохраняет projection в CAS и привязывает её через existing owned run/evaluation record к exact source selection. Binding обновляется атомарно по expected `(run, attempt, fence, source result view, bundle view)` и выбранной verifier/rule revision. Caller-provided projection ref или `predicate_status="recomputed"` этого не заменяют. Можно подготовить projection до первого run commit и выбрать её в той же transaction; поздняя verification/reverification добавляет новую controlled projection revision только при совпадающей source selection. Исторические revisions сохраняются; изменение current source делает старую projection ineligible для current claim. Циклов CAS нет: projection ссылается на уже записанный source, control record — на source и projection.

GET/L3/L4 через общий admitted reader проверяют owned projection selection, небольшие selected manifests/payload, verifier compatibility и current access/purpose. Они **не** заново загружают весь bundle inventory/output arrays и не исполняют law. Полная source verification уже записана trusted owner; целостность CAS и provenance этого admission остаются обязательными. При отсутствующей/устаревшей projection reader возвращает existing `verification_missing`/limited, refs и причину, без запуска тяжёлой работы из GET. Lifecycle может независимо поставить ровно одну идемпотентную verification task по source+rule key через существующий owner. Raw execution result сохраняется и при verification failure; metric-qualified result остаётся unavailable. Непроверенный generic vector нельзя принять за authenticated verifier output.

## Units: выбран точный adapter плюс законы преобразования

Adapter v1 — versioned compilation rule у existing IR unit owner, не новый изменяемый registry. Pin ID/version/implementation digest и exact selected UnitsRegistry. Матчится полный Foundry `Unit(dimension,symbol,scale)` и IR UnitSpec **после** установления одинакового quantity kind/role.

| Отношение | Решение v1 |
|---|---|
| Exact representation / same quantity | Identity adapter, factor 1 |
| Ratio ↔ percent для той же установленной величины/role | Только явно зарегистрированная exact rational пара 1/100 или 100; factor вычисляет handler, caller scale не authority |
| Иные representations | Unsupported до versioned extension либо explicit derivation law; не автоматически весь UCUM/Pint |
| Vector → scalar, weighted mean, numerator/denominator, relative change, level→delta | Compiled executable derivation law с row/population/time alignment, denominator и missingness rules |
| Currency change, nominal↔real prices | Закон с выбранными FX/deflator/source/time inputs; dimension `currency` не достаточна |
| Calendar conversion, stock/flow, affine/logarithmic scales | Нет generic scale conversion; требуется representable typed law/scale и контекст либо unavailable |

USD и UAH с одинаковой dimension/scale не identity; `ratio` DRE weights не employment rate. Missing price year/base — unknown, не wildcard. Count labels persons/households не преобразуются коэффициентом без закона. Не смешивать rate level, percentage-point difference и relative percentage change. При отсутствии IR модели для нужного denominator/time/scale расширяется этот owner или значение остаётся unqualified.

«Exact rational adapter» означает точный закон коэффициента, а не обещание точного IEEE-754 результата. Handler фиксирует numeric representation/rounding и propagation error по существующему canonical numeric contract. Не вводить Decimal/Fraction по всему runtime. Non-finite/bool-as-number и неизвестный rounding/error budget у чувствительной threshold decision не маскируются unit match; predicate остаётся limited до соответствующей numeric проверки.

## Executable identity, replay и cache

Сохранять exact selected EnvironmentManifestRef, исправив потерю profile. Существующий environment owner расширяется actual loaded method implementation/build/dependency identity, backend/version/device/dtype/fallback, RNG algorithm/seed и replay policy. Подписанный build provenance может быть входом проверки; ABI, Git SHA, module hash, seed или container label в одиночку не доказывают все исполняемые bytes. Не строить бесконечный transitive-source crawler: выбранная поддерживаемая build/runtime boundary и её limitation должны быть явны.

Три разных действия: read consistency; replay согласованности при том же build/profile; independent scientific verification. Same-code replay не доказывает научную корректность. Unsupported historical build/fallback сохраняет output provenance с limitation, но не утверждает replay equivalence. Replay допускается лишь для объявленного replay-safe method/profile, вне GET и без повторения внешних side effects.

Cache — необязательное ускорение **persisted** immutable admitted projection. Key включает owned committed selection, все selected views, binding/law/adapter/verifier versions и build/backend/context. При изменении ключа нужна новая admission revision; cold GET не выполняет её сам. Volatile permission, revocation, source currentness и публикационная допустимость проверяются при protected use; исторический cache не сохраняет их навсегда. Точность refs/status/units/roles — exact. Численный replay tolerance заранее задан backend/dtype/error budget; captured bytes не заменяются «почти теми же». Если интервал пересекает decision threshold, итог не превращается в доказанный положительный вывод.

## Migration, surface и приёмочный сигнал

Readers first; затем writer/capture; затем source admission; затем consumer. Historical numeric-only results остаются readable limited/unit-unknown. Отсутствующий legacy edge не malformed; present-invalid edge/binding — typed refusal, без numeric fallback. Old readers/writers допускаются только если доказано safe limited reading / lossless edge preservation; иначе capability refusal, не drop-and-rewrite. Forward-disable новых writes сохраняет readers и все старые views.

Minimum footprint: compiler/graph validator; dispatch capture; strict schemas + CAS manifest roles; existing environment projection; Runtime run commit; source admission; IR metric/units; Scientist policy-runtime metrics/objective/L3/L4; authenticated audit/GET evidence projection; official schema/OpenAPI/client companions по действительному public inventory. Нельзя считать Foundry-only test готовой capability.

Future acceptance: real compiled ProgramGraph→dispatch→persisted SimulationResult→discard producer objects→fresh admission worker с law/unit recomputation→persisted projection→restart/cold L3/L4/GET. Независимый ручной oracle на малом fixture вычисляет expected arithmetic без вызова production derivation handler; replay отдельно проверяет согласованность. Обязательны: edge removal при сохранённых markers; correctly rehashed forged bundle с caller run_id; stale winning-attempt race; partial sibling failure; duplicate node/slot/iteration; swapped candidate/registry/profile; same-ABI changed build; semantically changed equal-shape vectors; USD/UAH; ratio weights/employment; missing/unsupported output; legacy absent против invalid-present; mutation cached projection; permission/currentness changes; forged projection с честными hashes, но без owner admission; old-source projection после нового winning attempt; cold GET при запрещённой materialization/dispatch/law execution. Эти проверки **не запускались**.

Внешние inputs остаются genuine только для соответствующих утверждений: научная identification/calibration, fiscal convention/FX/deflator, certified provenance/permissions/currentness. Кодировщик, compiled law для объявленного candidate metric и run-origin binding — собственная engineering работа, не внешний blocker.
