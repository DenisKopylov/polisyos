# R16: технические основания расширяемой композиции и пересчёта

23 октября 2026. Исследование на `4633fc44df0aedeb3f9989b7a68036349cca2969`. Это static source review + primary literature, не benchmark, product acceptance или current E02 verdict. [R15](heterogeneous-model-execution.md) остаётся историческим source-bound dossier; следующие наблюдения перечитаны на новом pin. Concrete choices — [архитектура](../architecture/06-composition-and-reexecution.md), [delivery slices](../solutions/16-composed-execution-and-revisions.md).

## Ограниченное чтение native code

Пути относительно `policy-engine/src/polisyos/`; список — inspected selection, не полный repository census. После E02 rebind tracing охватывает actual callers/consumers/companions. Отсутствие возможности не выводится из поиска имени.

| Owner / symbol | Что видно на pin | Чего это не доказывает / где расширять |
|---|---|---|
| `runtime/quality/semantic_epoch.py`: `EpochResolutionQuery`, `SemanticEpochManifest`, `resolve_semantic_epoch`, `SemanticEpochService` | Owner-native coordinate evidence, complete registered boundary/facet denominators, semantic revisions и incomparable-history refusal | Это не simulation scheduler; использовать refs/qualified history как input semantics. Arbitrary scenario не становится authority epoch автоматически |
| `scientist/evidence/claims/head_index.py`: `ClaimLedgerOwnerPort`, `resolve_current_for_packet`, `advance_verified_batch`; `scientist/governance/continuous/lifecycle_bridge.py` | Packet-bound current reads и verified completed epoch-batch consumption | Не обещает запуск нового numerical trial; LIF-02 сохраняет head/currentness ownership |
| `scientist/validation/decision_validity.py`: `record_dependency_event`, `_register_dependencies`, `_apply_event_to_packet` | Event/dependency projection на сохранённый evaluation basis | Dirty/status propagation не selective model reexecution; enrollment/dedupe/actual dispatch проверяются отдельно |
| `ir/artifacts/lineage.py`: `ArtifactLineageGraph`; `core/artifacts/manifest.py` | Existing provenance/dependency representation | Не устанавливает автоматически dynamic read closure, absence-query dependencies, semantic equivalence или statistical independence |
| `foundry/compile/_graph.py`: `build_exec_order`, `_slot_dependency_edges` | Topological order; cycles rejected; часть зависимостей создаётся по пересечению slot names | Требуется typed semantic binding. SCC adapter не означает разрешить произвольные циклы в старом DAG |
| `foundry/execute/_internal/graph/__init__.py`: `execute_program_graph` | Потребляет `exec_plan.order` или node-list fallback, dispatch/patches/persist | Сам список не доказывает полный правильный order/active denominator; actual acceptance должен проверить это |
| `foundry/execute/api.py`, `foundry/feedback/fixed_point.py`, `foundry/feedback/diagnostics.py` | Existing feedback map invokes whole ExecPlan per evaluation, solve, final graph rerun, persisted convergence diagnostics | Whole-state purity, final observed residual и aggregate nested resource property нуждаются в actual witness; static risks не runtime FAIL |
| `foundry/methods/backends/chain_executor.py`: `_collect_node_inputs`, `_apply_binding_adapters`; `foundry/methods/backends/checkpointing.py`: `_compute_execution_digest`, checkpoint resume | Existing typed method chains, adapters и matching-execution resume | Prefix resume — не correction/retraction algorithm; dynamic provider/FX absence нужен в dependence. Header docstring не заменяет actual digest implementation |
| `scientist/orchestration/engine/idempotency.py`, `checkpoint.py` | Node result cache/mutation journals, run-scoped identity и workflow checkpoint seams | Run-local replay не arbitrary cross-run scientific cache; required code/source/scenario/use facets проверяются в owning profile |
| `scientist/methods/research_dag/replay.py` | Audit/pinned replay planning; live-fetch boundary | Не назначать исполнителем generic numerical reruns только из слова replay |
| `foundry/extensions/registry.py`, `foundry/methods/selection/registry.py`, `foundry/methods/backends/dispatch.py` | Extension/method discovery и backend dispatch | Unseen conforming model должен пройти actual bootstrap→caller→consumer; metadata entry не working extension |

Root отдельно перепроверил compiler/order fallback, semantic-epoch resolution, method execution-digest entry points и actual node-cache schema. Сводка не подменяет source-qualified verification; ограниченные numerical risks R15 остаются UNRUN.

## Что берём из других систем

| Primary source | Технический механизм | Применение и ограничение PolicyOS |
|---|---|---|
| [Bazel Skyframe](https://bazel.build/reference/skyframe) | Dependency requests, dynamic dependencies, invalidation и change pruning | Native read-set/negative dependency capture; equality pruning только для соответствующего полного consumer input. Build correctness не научная истинность и не право reuse |
| [Build systems à la carte](https://www.microsoft.com/en-us/research/publication/build-systems-la-carte/) | Разделение механизмов build systems и их свойств | Проектировать scheduling и decision-to-rebuild раздельно; не переносить новый build engine вместо existing Runtime |
| [Differential Dataflow updates](https://timelydataflow.github.io/differential-dataflow/chapter_3/chapter_3_3.html), [progress](https://timelydataflow.github.io/differential-dataflow/chapter_3/chapter_3_4.html) | Signed updates и explicit progress/finalization по logical time | Incremental insertion/retraction только для compatible method; progress — обещание producer, не отсутствие будущих исправлений во внешнем мире |
| [Apache Beam watermarks](https://beam.apache.org/documentation/programming-guide/#watermarks-and-late-data) | Source-derived watermark, late-data handling, trigger/window tradeoff | Разные cuts/time roles; correction создаёт новый result. Default late discard не универсальная политика evidence custody |
| [PostgreSQL logical decoding](https://www.postgresql.org/docs/18/logicaldecoding-explanation.html) | Per-database ordered changes, restart redelivery, retained slot resources | Source incarnation/position, idempotent effect и replay-floor contracts; ни distributed global snapshot, ни бесплатное бесконечное удержание history |
| [Temporal workflow definition](https://docs.temporal.io/workflow-definition) | Deterministic command-history replay и version-compatible workflows | Различать orchestration replay, activity retry и fresh scientific run; current ControlWorker остаётся первым reuse choice |
| [FMI 3.0.2](https://fmi-standard.org/docs/3.0.2/) | Model Exchange/Co-Simulation/Scheduled Execution и explicit state/event capabilities | Конкретный external adapter может использовать protocol. Standard не поставляет общий master, isolation или causal validity |
| [HELICS timing](https://docs.helics.org/en/latest/user-guide/fundamental_topics/timing_configuration.html) | Federate request/grant virtual time и exchange | Conditional independent-process clock adapter; grant не numerical convergence или validation модели |
| [BMI 2.0](https://bmi.csdms.io/en/latest/bmi.spec.html) | initialize/update/get-set/time/grid metadata | Adapter lifecycle; не general checkpoint/replay/coupling guarantee |
| [Pearl, Causality ch.3](https://web.cs.ucla.edu/~kaoru/CAUSALITY-REPRINTED-W-CORRECTIONS-2013/causality-ch3-june2013.pdf) | Intervention как операция над causal model, identification отдельно от observation | Различать observed conditioning, structural alternative и hypothetical forcing; выбранный cyclic computational profile сам не доказывает causal identification |
| [Kyllingstad, 2025 preprint](https://arxiv.org/abs/2512.13845) | Для определённых continuous co-simulations изменение шага может увеличить рассогласование интегральных состояний даже при уменьшении шага | Profile-specific step-change falsifier; не общий закон для всех моделей и не основание запрещать adaptive stepping |

Эти references обосновывают механизмы/опасности, не выбирают библиотеку автоматически. Рассмотренный alternative «один универсальный reactive platform для всего» отвергнут как duplicating ownership и лишняя migration. Alternative «любой change → полный глобальный replay» корректен только в ограниченном scope и дорог; targeted clean recompute остаётся fallback, incremental методы вводятся по доказанному выигрышу и correctness envelope.

## Численная и научная корректность — независимые обязательства

Малый residual может сочетаться с большой solution error: `T(x)=(1-epsilon)x+epsilon`, fixed point 1, residual в x=0 равен epsilon. Поэтому selected solver может заявлять residual-based convergence, но не accuracy-to-true-root без conditioning/error basis. Для co-simulation h/h2 comparison, conservation и tail-event checks диагностируют разные ошибки; один passed diagnostic не заменяет остальные selected promises.

Posterior update использует conditional likelihood genuinely new evidence. Same-data duplicate не увеличивает independent support; unavailable raw data может сделать exact retraction/refit невозможным. Вывод тогда ограничивается, а не сохраняет ложную current confidence. Simulation outputs и retrieved successful strategies остаются model/search influence, не новыми наблюдениями мира.

Разные модели могут быть вычислительно совместимы и научно несовместимы. Разрешённый результат — множество conditional alternatives, bounded comparison или abstention с research path; не silent average. Нужные domain rules (price basis, conservation, construct validity, transport, institutional effect) остаются source-qualified inputs, не hardcoded sector templates.

## Следующие исследования только по предъявленной потребности

Стартовый delivery проверяет native DAG + один явный existing coupling profile + bounded change/reuse path. Full asynchronous multi-clock execution, differentiable joint models, adjoint sensitivity, distributed differential inference и deterministic external FMU replay — conditional extensions по actual selected use. Для каждой сначала нужен native unmet property, объяснение cost/benefit, owner-specific protocol и independent oracle. Это не deferred blanket permission: claimed unsupported guarantee остаётся limitation, полезные supported compositions продолжаются.

Pattern pass: P02/P07/P08/P10/P13/P14/P17/P25/P27/P29/P31/P32/P35/P37/P38. Нет новых external services, downloaded runtimes, tests или production reads в исследовании.
