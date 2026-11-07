# Повторная source-led проверка Foundry, численных методов и calibration

**Итог:** 32 текущих пакета прочитаны целиком и получили по 70 dispositions (2240 всего). Новых подтверждённых дефектов формулировки не установлено. Это оценка достаточности ТЗ, не выполненных product tests: все native проверки остаются **NOT_RUN**.

## Основание и способ проверки

Использован замороженный каталог `8c8c77e13d9151349b7410b441f97f0f94fbfb7d097150f32c9872fe35a3cb59`: каждый критерий проверен с его условием применимости и ограничением. NASA/SEI и другие рекомендации не превращены в обязательство новой подсистемы, произвольного SLO или универсальной численной точности. Source IDs и точные source locators сохранены у criterion groups в `assessments.json`; полный источник и ограничения доступа — в `coverage.json`.

Прочитаны root MD и семантика всех companion JSON, общие правила и владельцы, LANE-03/04/10, I03/I04/I10, четыре истории, применимые integration bindings и local-only обязанности. Общий сценарий не заменяет локальные tests, один общий запуск не считается независимыми подтверждениями. Старые v1 findings не перенесены автоматически.

## Что важно сохранить

- Численные ограничения относятся к объявленным dtype/backend/input profiles: представимый residual не теряется от SSE overflow; collapsed CDF interval отказывается явно; tied PCA subspace не сравнивается по знаку eigenvector.
- Native replay отделён от независимого oracle. В v2 уже есть PPO/GAE и value/entropy controls, actual calibration derivative anchors, Fraction/Decimal mean reference и аналитический PCA projector/residual.
- Leakage проверяется на полном as-of view и до nonlinear AD; masked loss после уже вычисленного infinity не считается достаточным исправлением.
- Fresh consumer проверяет выбранные source/profile/units/time/row bindings. Partial и historical результаты полезны в своей области, но не получают новую authority.
- JIT single-flight и FS checkpoint проверяются как реальные локальные concurrent protocols, а не автоматически исключаются как «численные пакеты». Publication, fsync, cancellation и current authorization различены.
- Конечные решения по caller/fusion/source/intent owners законны: они не закрывают отсутствующую capability документным PASS и не блокируют независимый narrow repair.

## Пакетные вердикты

### LANE-03

#### EMP-01

Exact endpoint width и source-scope binding имеют реальные positive/negative controls, без универсальной unit-инвариантности при утрате представимости.

**Контракт/контроли.** ValueOuterSet single owner; selected graph/source/unit/profile и actual run basis доходят через native CAS к fresh N8; TEST-03/05/06/08 различают substitution. Equal-endpoint proxy, overflow width, wrong profile/context и unsupported subgroup отвергаются; point [2,2] и asymmetric CI [0,10] сохраняют разные роли.

**Граница.** DEC-NUMERIC выбирает versioned reader; DEC-SCOPE ограничивает фактические source coordinates. Country-only candidate не заменяет неизвестный subgroup.

**Основание:** [REQ-EMP-01-01…08; TEST-EMP-01-01…08](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/EMP-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### FRC-01

Summary наследует admitted floor, не выводит его из counts; 95/100 сохраняет правомерный pass, optional refs честно пусты.

**Контракт/контроли.** Один summary reducer; full ArtifactRefModel/profile сохраняется в service/reopened S10 совместно FRC-02/PCL-01; two sibling-profile directions проверяются. Limit 10/10 не повышается; genuine threshold .90/.95 pass не превращается в always-limit; raw map, unsupported temporal profile, чужой source/ref получают точную limitation.

**Граница.** DEC-TIME ограничен текущими six temporal roles; DEC-SUPPORT требует реальный producer и не фабрикует authority.

**Основание:** [REQ-FRC-01-01…07; TEST-FRC-01-01…06](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/FRC-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### PCL-01

Typed/serialized report имеет одинаковую ограничивающую силу на известном output boundary; generic binary/multiclass остаются самостоятельными.

**Контракт/контроли.** Одна normalisation до dispatcher merge/telemetry, IR не импортирует Foundry registry; actual DTO validation/source assurance и fresh receipt reconciliation; test method разрешён только для generic contract. Empty/partial inventory и malformed expected report не fall through к positive sidecar; explicit levels=[] не становится default; self-label continuous не даёт происхождение.

**Граница.** DEC-BOUNDARY конечный owner census; DEC-ALIAS default retain до подтверждённого окна, без invented retirement.

**Основание:** [REQ-PCL-01-01…07; TEST-PCL-01-01…07](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/PCL-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### FRC-02

Strict counters, actual holdout oracle и selected outcome relation разведены с scientific qualification.

**Контракт/контроли.** Actual ETS→report→canonical bridge→service/CAS→fresh S10 сохраняет source/model/rule/time/profile; relation target/snapshot/units/population строго связана. Same train/different holdout оставляет прогноз, меняет hits; bool/fraction/nonfinite counts invalid; relation mismatch блокирует outcome tier, но сохраняет series evidence; historical 1.0/1.1 не переиздаётся новым.

**Граница.** DEC-COUNTS ограничивает legacy grammar; relation owner и scoped experiment имеют конечный выход; отсутствующий corpus не блокирует независимый repair.

**Основание:** [REQ-FRC-02-01…08; TEST-FRC-02-01…08](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/FRC-02.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### BKT-01

Whole-view leakage, selected metrics profile, trajectory semantics и полезный ensemble описаны без подмены независимости seed-ами.

**Контракт/контроли.** Masker/source feature owner→exact persisted input view→Foundry replica→trajectory/uncertainty→report/fresh consumer; single orchestrator writer и LANE-06 budget owner. Contaminated derived prefix пересчитывается; known-ahead calendar разрешён явно; same-length ATE не trajectory; [1,3],[3,5],[5,7] даёт [3,5], failed requested replica не исчезает.

**Граница.** DEC-VIEW/PROJECTION/BUDGET требуют finite owner map и positive implementation; до него honest unsupported, не фиктивно закрытая capability.

**Основание:** [REQ-BKT-01-01…09; TEST-BKT-01-01…09](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/BKT-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### BKT-02

Представимый residual не теряется от square/SSE overflow; scaled RMSE и independent row reconciliation имеют адресные range limits.

**Контракт/контроли.** Evaluator/aggregate/IR reader используют объявленный range contract с independent recomputation; native source→CAS→fresh decision; nominal/type и requested/comparison counts сохраняются. Single/pair 1e308 и subtraction overflow различены; empty/partial не A; micro sqrt(200/3) partition-invariant, macro меняется явно; incompatible quantities отдельны.

**Граница.** DEC-RANGE выбирает unavailable sufficient statistics либо versioned scaled statistics; DEC-POOL требует предметную comparability до pooling.

**Основание:** [REQ-BKT-02-01…08; TEST-BKT-02-01…08](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/BKT-02.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### BKT-03

Cancellation repair не ослабляет source verification и не выдаёт иной statistic за SciPy; descriptive и inferential различены.

**Контракт/контроли.** Producer/IR/fresh C5b/full packet привязаны к одному source multiset и selected profile; direct SciPy — backend parity, не независимое доказательство t-law; numeric hand anchors отдельны. Все permutations [1e16,1,-1e16] дают 1/3; constant ±10 retains magnitude и pNone; backend unavailable/tampered p снимает только inference, сохраняет rows.

**Граница.** DEC-SCALE ограничивает floor/unit regime или выбирает versioned scale-aware predicate; DEC-SCOPE не выводит independence/orientation из residual sign.

**Основание:** [REQ-BKT-03-01…07; TEST-BKT-03-01…07](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/BKT-03.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### BKT-04

Уже работающие CV/selector repairs сохраняются; actual caller, metric denominator и sampling unit не изобретаются.

**Контракт/контроли.** Selected CV callback arrays изолированы; consumer adapter переиспользует completeness; bootstrap selector/declaration/basis/seed явно доставляются, callable имя не authenticity. 6 lists/1504 elements для выбранных 3folds; missing metric1/2 не full2; typo before RNG; mean3/median0/std√27 anchors исключают degenerate selector.

**Граница.** DEC-CALLER разрешает supported public-only qualification; DEC-SAMPLING требует justified iid либо explicit bounded dependent claim.

**Основание:** [REQ-BKT-04-01…07; TEST-BKT-04-01…07](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/BKT-04.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

### LANE-04

#### FRY-01

Перенос владельцев квалифицируется без повторного rewrite; versioned Treasury RNG и family certificates не обещают универсальный IC.

**Контракт/контроли.** Один canonical randomization/family owner, actual spec→IR→executable method; пять facade aliases сохраняют identity, новые slots без state_path остаются inventory-only. Seeds0/17/−3 и salts permutations/high words различают нулевой seed и потерянные соли; off-grid payment, unknown family и stale certificate не получают admission.

**Граница.** Marked treasury_salts_v1 обязан точной lineage; unmarked historical read сохраняет прежний профиль. Default31 slots не закрытая онтология; external alias consumers требуют конечного census.

**Основание:** [REQ-FRY-01-01…04; TEST-FRY-01-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/FRY-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### FRY-03

Native fiscal/labor laws, active∩target mask и явная precision delta сохранены; relocation не меняет модель.

**Контракт/контроли.** Canonical execute/mechanisms kernels→PatchMap→merge→actual FS/CAS→fresh state; old class aliases direct, treasury counteraccount и labor RNG split сохраняются. Tax reported[80,40,200,60] даёт [−20,0,0,−15] и gov+35; subsidy даёт [0,25,0,40]/gov−65; active firms0 отказывает до RNG. .1000000001×1e12→100000000100 при заявленном float64. 

**Граница.** Negative signed tax является математическим reverse transfer выбранной модели; запрет требует отдельного решения. Float64 profile лишь где поддержан, global x64 toggle не требуется.

**Основание:** [REQ-FRY-03-01…03; TEST-FRY-03-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/FRY-03.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### ECO-01

Два экономических ABI и закона не сливаются; normalized-income baseline имеет независимую формулу и честный finite guard.

**Контракт/контроли.** Native income debit/counteraccount и plugin income-base wealth-debit/no-counteraccount разделены таблицей units/clock/RNG/state; actual guard JIT/grad и consumers обязательны. Flat25%[100,200]→[25,50], progressive[25000,50000]→[3250,7700]; baseline positive−1/zero0/negative1/breach9; [1,−6,2]→1/3; nonfinite/empty/overflow→+inf.

**Граница.** Намеренный all-entry baseline, padding effect и constant −1 в положительном режиме не называются welfare improvement. Альтернативный welfare functional не включается без решения модели.

**Основание:** [REQ-ECO-01-01…03; TEST-ECO-01-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/ECO-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### PLG-01

Discovery изолирует malformed factory на границе кандидата и не маскирует неисправность всего registry; не sandbox.

**Контракт/контроли.** Core loading primitives reused, DomainPlugin ABI/group не Method ABI; common candidate validation внутри per-source try до register; успешный lifecycle get once, failed load не latch. object/None/bad metadata/import failure не мешают later-good и ранее valid; deterministic first duplicate; child-before-parent warning не выдаётся за topological discovery; BaseException не swallow.

**Граница.** Prefix scan и однопроходный dependency order сохраняются до конечного support census. Trusted fixture files квалифицируют discovery, не произвольный hostile code.

**Основание:** [REQ-PLG-01-01…03; TEST-PLG-01-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/PLG-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### PLG-02

Legacy TrainingResult не становится trained из default; unsupported train остаётся честным и не создаёт actor/output/store.

**Контракт/контроли.** Current producer должен явно поставить роль после фактического success; CLI trained iff current role+policy+no reason, rewardtrace не PPO loss; genuine in-memory training не требует CAS. Unsupported сохраняет prior state/policy, work0/write0/outputdir0; CLI1 vs usage2/internal error различены; ordinary run/eval не выполняют update.

**Граница.** Три positional fields сохраняются; role/version default unknown и old-layout object читаются как historical evaluation. Реальная learning capability принадлежит PLG-03.

**Основание:** [REQ-PLG-02-01…03; TEST-PLG-02-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/PLG-02.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### PLG-03

Реальный tiny PPO update отделён от математического oracle и model validity; HARD refusal, fixed-target GAE и inactive padding оговорены предметно.

**Контракт/контроли.** Actual ActorCritic/GAE/Optax→artifact1.1 supplied tenant store→fresh selected-profile skeleton action; old1.0 читается без переаттестации; loss/collector не заменяются shim. PPO ratios[1.3,.7]/[.9,1.1]/[.7,1.3] дают losses−.2/.1/.3 и μ gradients0/−1/−1; отдельные value/entropy coefficients и GAE terminal controls; active invalid и zero effective update запрещают publication.

**Граница.** Предпочтительный HARD train unsupported до работы сохраняет HARD eval; полный HARD train только отдельным action/likelihood contract. No welfare convergence claim; inactive NaN — qualification, не установленный runtime bug.

**Основание:** [REQ-PLG-03-01…04; TEST-PLG-03-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/PLG-03.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### CMP-01

Effective DAG и payload сохраняют authored static/dynamic значения через freeze и fresh recipe; sequential не зависит от optional Ray/JAX.

**Контракт/контроли.** Canonical composer→effective DAG→freeze→sync/async executor→FS/CAS fresh compiler хранит occurrence IDs/requires/params/mode/levels; dependency barriers actual. A7+5=12→B36, C independent parallel; cycles/missing fail dispatch0; static20 scale2/3→40/60,override30×4→120; implicit default7 даёт14/21 и ловится.

**Граница.** Если persisted executable recipe отсутствует, нужен минимальный versioned loader, не фиктивная документационная готовность. Internal import errors сохраняют cause, а не превращаются в backend absence.

**Основание:** [REQ-CMP-01-01…03; TEST-CMP-01-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CMP-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### CMP-02

STRICT collision, explicit merge и честный WARN различены; occurrence ordering не стирается повторным методом.

**Контракт/контроли.** Concrete target-slot owner и explicit merge едины для execution/checkpoint; requires применяются к occurrences, не уникальному FQN; neutral semantic tags не научная аттестация. STRICT dispatch0; explicit(10+20)×2=60 UUID invariant; WARN меняется явно; complete3-node checkpoint dispatch0, changed mode/context/request/prefix/history не reuse.

**Граница.** WARN остаётся order-sensitive20/10 и обязательно несёт diagnostics; это не универсальная semantic disambiguation. Checkpoint supplied live chain не самостоятельный executable recipe CMP-01.

**Основание:** [REQ-CMP-02-01…03; TEST-CMP-02-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CMP-02.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### CMP-03

Matching имеет полную lexicographic цель и независимую exhaustive tiny проверку; diagnostics описывает выбранный, не stale source.

**Контракт/контроли.** Auto/explicit routes используют один admissibility owner units/shapes/contracts; matching max-cardinality→lexsum5components→stable pairs, prefer_exact_names меняет лишь name component. right→right positive; two-source consumer100×left+right=1020 при обоих connect orders; 729 3×3 contracts exhaustive objective и score dominance для actual n; no arbitrary cap/exponential production solver.

**Граница.** Не обещается connect-order independence для произвольного ambiguous DAG. Contract semantic tags проверяют declared admissibility, не доказывают residualization/causality.

**Основание:** [REQ-CMP-03-01…03; TEST-CMP-03-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CMP-03.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### JIT-01

Per-handle dynamic binding, miss→claim recheck и generation-fenced publication закрывают локальную single-flight гонку без фиктивного XLA speedup.

**Контракт/контроли.** Immutable kernel cache shared two compilers; bound defaults принадлежат handle. Exact implementation/static/shape/dtype/backend key, cache-generation claim/publication owner один; old handle не mutable current defaults. old default2→20,warm/cold3→30,override4→40; leader завершился между miss и claim — recheck публикует existing kernel followers, не hanging return; error/BaseException/invalidation/timeout/cancel release independently.

**Граница.** Одна wrapper construction не означает одну XLA compile; scalar declared shape/native dtype квалифицируются отдельно. No arbitrary JAX global flags или hidden eval.

**Основание:** [REQ-JIT-01-01…03; TEST-JIT-01-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/JIT-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### RES-04

Checkpoint сохраняет exact request/history/restricted evidence; manifest publication и crash durability различены, uncertain rename не запускает destructive cleanup.

**Контракт/контроли.** Unique generations+flock+manifest owner связывают sidecar content/shape/dtype/hash; state/history namespaces injective, typed RestrictedMethodInvocationEvidence roundtrip fieldwise. Input3→multiply2/add1=7 history6/7seed7; fullresume0dispatch partial1; mismatch params/input/seed/prefix отказ. Postrename error сохраняет referenced newsidecars, prepublication preservesold; uncertain outcome сначала readmanifest underlock.

**Граница.** Это local FS checkpoint, не CoreCAS transaction replacement. Historical restricted evidence не current authorization; no RTO/RPO/general disaster recovery claim.

**Основание:** [REQ-RES-04-01…04; TEST-RES-04-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/RES-04.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### CAL-05

Conditional execution квалифицируется actual JAX derivatives и callback, без blanket vmap ban и без hidden inactive emitter.

**Контракт/контроли.** Actual compiler selector admission→lax.cond/neutral PatchMap→merge→Calibrator targetloss/report lifecycle; dtype/shape/records fixed по admitted registry contract. Inactivex0 log fixture value0grad1Hess0calls0; activex2 value2+ln2grad1.5Hess−.25; unknownselector отказывает даже inactive; dependency results[5,5],independentbase2→9; tax rows[100,200]/[100,180]/[100,200].

**Граница.** Mapped schedule unsupported даже когда значения равны; scalar sharedschedule state-vmap и scalar lax.map supported. Neutral contract census конечен, unsupported pytree не guessed.

**Основание:** [REQ-CAL-05-01…03; TEST-CAL-05-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CAL-05.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

### LANE-10

#### CAL-02

Scale, fit-support и derivatives имеют representable float32 profile; heldout extreme нейтрализуется до nonlinear AD, а не поздним нулевым весом.

**Контракт/контроли.** Single existing compiler/splitter frozen mask до measurement_support/basevector, shared objective weights после qualityreduction, actual tax→JAXgrad/Hess/Optax→report; historical observations неизменны. mean_abs3e38/std5e19 finite viahostfloat64; heldout10→3e38 не меняет fit/grad/Hess/update; allmasked target0 только с supported sibling; entireempty отказ; active modelNaN guard сохранён.

**Граница.** Training-only contract получает versioned input/policy binding; full-data profile лишь явным решением после caller census. Не требуется arbitrary dtype или scientific validity от tiny optimizer.

**Основание:** [REQ-CAL-02-01…07; TEST-CAL-02-01…06](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CAL-02.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### CAL-03

Finite admission одинаков для one/multistart; raw identifiability не повышается damping repair, exporter fault не стирает primary failure.

**Контракт/контроли.** Single select_best admission before projection; chosen state/loss/weights/history/Hess one record; native two-start OTel fresh context/spans отдельно от exporter/no-op. Allnonfinite fail exactdiagnostics; f0raw0conditioninf vs x²raw2condition1 distinguishes repaired inverse; loss.1 unqualified vs .5qualified выбирает.5; primaryexception survives telemetry failure.

**Граница.** Finite ill-conditioned result полезен с limitation; missing Hessian не равен observed infinite condition, lowest loss не globalminimum/scientific fit.

**Основание:** [REQ-CAL-03-01…04; TEST-CAL-03-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CAL-03.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### CAL-04

One exact selected state/objective feeds final projections; equal scalar loss не является identity и не разрешает stale Hessian reuse.

**Контракт/контроли.** Actual lastcandidate evaluates beforeselection; point/coordinates/weights/seed/numericpolicy key один; report projections используют actual chosenforward, без detached numerical reconstruction. Baseline0candidate2 equalquadraticloss сохраняет chosenstate0trace; .5loss.25 accepted,overshoot4/NaNnot; quarticH(.25)=.75/H(.5)=3, initial3Hreuse3 mismatch4.

**Граница.** Hessian reuse локальный exactkey, не globalcache; saved calls не заявляются walltime speedup. Budget exhaustion сохраняет checkedstate с причиной.

**Основание:** [REQ-CAL-04-01…05; TEST-CAL-04-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CAL-04.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### CAL-06

Scoped uncertainty не блокируется unrelated point-only field; tied covariance сохраняет rank и declared coordinate projection.

**Контракт/контроли.** Explicit uncertainty scope subset parameters+ordered coordinate basis/matrix; actual persistedreport→freshjointMC uses same projection/carrier; unrelated fields retained pointonly. A/B=.25 variance.0025 rank1 joint difference0 everydraw, C=.7 unknownnot0; removeC/renamegroup не меняетAB; sigma.05 remains underlevel.8/.95 and metadatasigma9.

**Граница.** Old2.0/2.1 complete semantics требуют newversion, не silent scope reinterpretation. Heuristic uncertainty flags nongating; missing typed sigma не восстанавливается из display metadata.

**Основание:** [REQ-CAL-06-01…05; TEST-CAL-06-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/CAL-06.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### UQS-01

Decomposition не усиливает authority; общий finite binary64 mean имеет independent exact-input oracle; duplicate evidence не независимый dataset.

**Контракт/контроли.** FED-01 единственный common/numeric_reductions owner, UQS thin consumer; exact selectedviews/sourcecorpus→actual CAS→fresh uncertaintyconsumer; profileidentity важнее sharedblob. [1e308,1e308]mean1e308/cancellation0/subnormal exactulp; Fraction+Decimal independentreference; fourduplicateSTD1 vs independentGaussianSTD.5;99zeros+100mean1 сCI[0,0] допустим.

**Граница.** Independent fusion требует source-bound independence/common estimand/prior treatment; owner absent остаётся точным capabilitygap, не always-refuse решение. CPython3.14 helper bounded, не arbitrary arithmetic platform.

**Основание:** [REQ-UQS-01-01…05; TEST-UQS-01-01…05](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/UQS-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### UQP-01

Все numerical routes используют один effective invocation; zero-baseline и absent output не подменяют друг друга.

**Контракт/контроли.** Nominal/probe/delta/random/QMC общий fixed/varying binding, actual execute/calibration source refs центры/units/roster→freshnode; callerhypothesis candidateonly. Omittedscale default7 !=explicit0,missingrequired доeval; x10σ1scale2 point20var4; affine x−2 at2 point0jac1var1 безMC; requestedmissingUNKNOWN vs real0; nondiff честный MCfallback.

**Граница.** Dtype/device profile задаётся явно; x100000001float32→1e8,y0 допустим и согласован с coercednominal, supportedx64→1. Нельзя обещать Pythonfloat precision всему JAX.

**Основание:** [REQ-UQP-01-01…05; TEST-UQP-01-01…05](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/UQP-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### UQP-02

Degenerate marginals и empirical inverse CDF сохраняют выбранный закон; collapsed floating CDF interval честно refused, не исчезающий атом.

**Контракт/контроли.** Namedaxes/singularcovariance одна analytical/random/QMC interpretation; empiricalpairedrows/sourceartifact сохраняются приfreshrepropagation, не independentmarginal shuffle. std0 deterministic доPRNG/ppf; atoms[-1,1],weights[1e-12,1−...] u0/5e-13→−1,boundary→1;positiveweight[1,1e-20]collapsedCDF refused доdraw/publication;invaliduNaNrefused.

**Граница.** Finite uniform lattice не обязана наблюдать rare atom в каждой выборке; arbitrary precision/approximate sampler не входят. Covariance не универсальный nonlinear jointlaw.

**Основание:** [REQ-UQP-02-01…05; TEST-UQP-02-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/UQP-02.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### UQP-03

Full relative output width не MCSE; partial law и bounded same-input retry сохраняют ledger и область conditional result.

**Контракт/контроли.** Existing adaptive batching/failureclassifier/ledger→actualstore→freshScience/normativeconsumer проверяет exactprofile/source/drawcounts; missing verifier не снимает safetycap. 99/101 width.02неpasses.015 приn200/10000,constantpasses;budget240checkpoint100batch50/60 stop100unattempted140; half-law50valuesmean50/99 не unconditional0; globalcause не rowfailure.

**Граница.** Legacy half_width сохраняет прежний fullwidth meaning сlabel; additional functional precision только при actualcaller/estimator/stoppingplan DEC, не universal sequential library.

**Основание:** [REQ-UQP-03-01…05; TEST-UQP-03-01…05](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/UQP-03.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### DOE-01

Bounded GRID и completed adaptive round не скрывают rerun/cost; final result связывается с фактическим design.

**Контракт/контроли.** Existing AdaptiveResult/designartifact source matrix/axes/seed/stream/round→fresh scientificconsumer; actual SALib smallroute вместо syntheticanalyzer; DOE02sameidentityowner. 12axes cap3 gives3×12float64nbytes288baseNone,10constantaxeslimited; rounds[6]or[6,12],falsepermission before12; failed2analysis preservesresult6observed18; partialevalunknownnot0.

**Граница.** Per-designcap не cumulativeglobalbudget. Missing productioncaller требует finiteownerdecision+minimaladapter, не invented source ref; ranking stability не scientific convergence.

**Основание:** [REQ-DOE-01-01…04; TEST-DOE-01-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/DOE-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### DOE-02

Full-request replay включает preprocessing/PCA local streams и actual solver/profile provenance; plan.seed alone недостаточен.

**Контракт/контроли.** Single typedlaw mappingowner sampling/analyzer; replica before stageseed derivation; sample/analysis/PCA/model/UQ streams separated. Existingdesignartifact binds actualmatrix/axes/law/backend/solver/cap/centering/seed. Uniformsource+currentNormalplan refuses relabel; AB/BA exactsource and declaredtolerance output with unchangedexternalNumPy state; auto/randomized activation actual600×100k5; changedsolver/seed atsamehash invalidatesreplay.

**Граница.** SALib1.5.2/sklearn1.8.0 pinnedprofile; FASTseeded и boundedLOGNORMAL compatibilitypending сохраняются. Seedsequence migration versioned, no perpetual bitwisestability.

**Основание:** [REQ-DOE-02-01…04; TEST-DOE-02-01…03](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/DOE-02.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### DOE-03

Imputation/selection остаются exploratory; PCA проверяется centered rank, независимым projector/residual и активированной randomized веткой.

**Контракт/контроли.** Shared preparation before scalar/multiPCA сохраняет original/retained blockIDs/counts; DOE02stream/sourceowner→actualSALibpoint/UQ→persistedfreshconsumer, exactsolverversion/seed/profile. Failures[1] or[1,4,5] retainwholeIDs[1,2,3]or[2,3]; Xrank2 ratios90/91,1/91/fullprojector; tiedcap1ratio.24unmet no rank1orientationcompare; normalizedy2xon[0,10]EE20 unitsinvariant.

**Граница.** Medianfilled trajectory не ordinaryCI без missingnessmodel. Componentcap/variancecoverage не samplesufficiency; named full/randomized profiles не forcedfullSVDforall.

**Основание:** [REQ-DOE-03-01…05; TEST-DOE-03-01…05](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/DOE-03.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

#### STR-01

Occurrence ledger исключает unavailable из valid, а selected objective intent приходит независимо от outcomes.

**Контракт/контроли.** Single badness/directionowner acrossdirect/adaptivesearch, existing selectedrequest/runstate→exactcandidate/plan/outcomeprofile→actualstore→freshLevel5resolver. Mixed3 valid1invalid1unavailable1 conservation; utilityworst−5/cost10; rawhistory8/−4 unchanged; tenviolations topk1/10 observed10unique1,emptyrobustNone; wrongdirection/threshold/ref refuses.

**Граница.** Finite inspectedfraction не populationprobability; missing adequateintentowner остаётся capabilitygap, diagnostics полезны. Новыйoptimizer и retired NegatedCompositeObjective не включены.

**Основание:** [REQ-STR-01-01…04; TEST-STR-01-01…04](../baseline/PolicyOS_E02_Review_and_Specs_v2/02_Пакеты/STR-01.md). Все 70 source-критериев — в машинной оценке; нового finding нет.

## Проверки самой проверки

Readback подтвердил 32 уникальных packet IDs, ровно 70 criterion IDs у каждого, существование evidence paths, неизменность записанных input hashes и разрешение применимых REQ→TEST edges. Малые независимые stdlib расчёты сверили CAL-02 physical/optimizer-coordinate anchors, PLG-03 GAE/clipped-loss anchors и UQP-03 conditional mean. Это арифметика спецификации, не исполнение продукта.

Дополнительно по запросу координатора проверен стык CAL-01: CAL-02/05 не дают общего основания требовать unique target timestamps. Actual preflight интерполирует отдельные target queries в исходном порядке; это не доказательство универсальной пригодности repeated model time. Узкое уточнение shared binding передано владельцу fabric-аудита и координатору, без дублирования finding здесь.

Никаких product/spec edits, installs, native runs или внешних записей не было. Новая редакция этих 32 ТЗ не предлагается только ради числа изменений.
