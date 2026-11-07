# Независимое содержательное readback common proposed v2

**Статус:** ACCEPT_PROPOSED_COMMON_SPEC_AT_RECORDED_HASHES_NATIVE_NOT_RUN. Product/native tests **NOT_RUN**.

Прочитаны все изменённые нормативные common clauses 17 файлов, все изменённые binding scopes и связанные актуальные локальные контракты; независимая проверка не принимает авторский validation report за доказательство. Полный дублированный1.3MB mapping JSON не заявлен как новый смысл. Exact baseline/proposed SHA, 159 binding render checks и области чтения — в соседнем JSON.

Из159bindings содержательно изменены 37; исходные IDs/edges сохраняются. 38+4 canonical scenarios. Статическая metadata freshness не смешивается с native execution.

## Полезный результат

Обнаружен и уже исправлен один реальный пропуск приёмки: общий PPO oracle обещал проверку value/entropy coefficients, а исходный новый unit ставил оба коэффициента в0. Такой unit пропускал удаление обоих слагаемых. Автор добавил actual-actor component controls с nonzero coefficients; независимое readback ниже принимает исправление только на уровне specification.

## FUN metrics / search / simulation

Принимаю bounded confusion-matrix qualification: TP/FP/FN/TN, denominator/cohort и missing labels фиксированы; observed zero не population bound. FUN fixture FOR1% и FNR100% различает прежнюю двусмысленность; пять независимых zero-event observations дают one-sided95% upper≈45.07%, не2%. OPT pending/completed effective-action dedup и exhaustion/census различаются; optional measured-only transfer не ослабляет fitted guard. SIM stochastic y=u+(2+u)*a с evidence{} проверяет actual paired effect2+u; integer comparator отдельно. Late PS-F08 переносит real NCM CI quantile из100000 ambient normal draws в deterministic qualified inverse-normal, но не выдаёт это за empirical coverage.

## RDD / DoWhy / FIT / SCM / DDM

Conventional HC0 B Xᵀdiag(w²e²)X B и known-noise variance B XᵀWΣWX B не смешаны с legacy inverse-Gram proxy и unchanged RBC. Actual DoWhy/Statsmodels parity и independent analytic oracle оба нужны; Linux Python3.12 worker — отдельный route, не все зависимости каждого repair. Selected FIT fold не зависит от heldout Y; это не обещание invariant final ATE/EIF. SCM bootstrap строит target каждого refit, interval width не coverage. DDM statistical unit —100 independent Bernoulli windows по4values, не400 independent outcomes. Подробная независимая Fraction/t5/algebra проверка уже в review_causal_v2.json; native NOT_RUN.

## PPO / calibration / sensitivity / numeric reuse

PPO policy clipping/sign/GAE unit не заменяет actual gradient→Optax→fresh artifact/action. Найденный мною пропуск nonzero value/entropy controls исправлен в TEST-PLG-03-02, см. COMMON-V2-01 и independent algebra. Native inactive-padding сравнивает same shape/key/active rows, не обещает append-padding RNG invariance. CAL mask-before-nonlinear-AD сохраняет active nonfinite guards и fixed train scaling; allcorpus no-fit отличён от masked target valid sibling. DOE full request управляет local-derived RNG/solver profile; 600×100,k5 provokes randomized PCA path, Morris2002×8 needs rank>15. Rank/gap preflight фиксирован до PCA; no retune after result; projectors/reconstruction instead of arbitrary signs/tied vectors. FED/UQS используют один existing CPython3.14 statistics.mean owner, independent Fraction/precision1200 Decimal oracle; no new rounded subgroup averaging. Finite overflow bucket rows не теряют denominators/trust; nonrepresentable residual отдельно.

## Runtime / registration / client

All three shared-Future async paths сохраняют private adapter, actual physical capacity ownership и external watchdog; no premature cancellation release. STA prior mapping value2,std_error.2, CI absent,multiplier3→μ2σ.6 before sampling; sampling mean не exact prior oracle. Warm-parent JAX/fork qualification не объявлена proven hang/forced spawn rewrite. MIG registration snapshot не arbitrary live closure freeze и не препятствует narrow rollback-exception fix; observer-family compatibility preserved. CLI Python actual HTTP response→generated decoder and generated request→actual service require one bidirectional bridge, не unrelated fake-JS/Python checks. Prototype-key fixtures need actual own key and optional absence guard, without unnecessary TSlib upgrade.

## Fabric / acquisition / index / legality

Off/smart miss does not permit inner resume, while policy-approved HTTP cache remains allowed. Async harvest finite stages={harvest} reuses current admission; smart route network0 and same-name changed config/source invalidation retained. Scalar UDF validates pre-coercion Python scalar so int>2**53 not rounded away, but cannot recover already-rounded floats. P-INDEX needs native >=3 non-tied vectors, k<N, independent cosine ground truth; not universal ANN quality. P-LEGAL-OWNED uses owned prequalified local model assets and actual encoder, no silent download/fake encoder. Heldout utility pre-adjudication is bounded evidence, not publisher repair; graph backend profile separate. Offline SCL policy validation may be DNS-free using retained facts; live fetch retains DNS pin/peer/redirect SSRF checks. Unknown required facts cannot become admission.

## Generalization / joint capacity / persisted invalidation

Freeze relevant generic code and selection/criterion before independent compatible transfer. Existing model/policy IR is configuration; arbitrary Python callback embedded in data is new code. New general semantics allowed, but begin fresh freeze/holdout; explicit constructors do not prove autonomous discovery. Cost table records real manual work/cardinality/construction/cold-warm IO/RSS, no invented SLA or mandatory index/framework. Conditional X04 requires actual existing resource owner+joint program+persisted consumer: demands4/4/4,capacity10 makes all pairs feasible/triple infeasible;12 makes triple feasible;8 subsets independent oracle. Max-benefit5/4/3 optimumAB9 only if owner really promises optimization. Missing owner is a capability gap, not mandatory new allocator. Source-change uses real persisted S→P,Q→R plus independentD and late old callbacks; standalone graph toy cannot prove system invalidation. Scientific monitoring does not silently update causal mechanism or grant permission.

## Binding preservation and evidence scope

Original38 lane scenarios+4stories and159 binding IDs retained. Five new analytic-test links cover precisely numerical/preprocessing/bootstrap/window qualification, not every requirement or scientific validity. Four REQs move from local-only to shared-plus-local without removing any local acceptance. Same-backend parity, analytic unit success, native integration, empirical coverage and authority are explicitly different claims. All future tests stay NOT_RUN. Source metadata readiness is checked separately from these semantic verdicts; after packet changes the source inventory must be regenerated before release.

## COMMON-V2-01: исправление проверено

При fixed returns[1,3], ν=0: MSE=(1+9)/2=5, derivative2*((−1)+(−3))/2=−4. Actual continuous entropy helper даёт H(ℓ)=.5*(1+log(2π))+ℓ при inactive clipping [−20,5]; ppo_loss использует cv*MSE−ce*H, без1/2. Поэтому total5cv−ceH0, dν−4cv, dℓ−ce. Шесть coefficient pairs включают isolated value, isolated entropy и combined controls; raw components/total/actual-field eager/JIT gradients проверяются. Это различает dropped/sign-flipped/ignored coefficient implementations. Original sign/clip, GAE, actual Optax update и artifact-consumer checks не удалены.

Accepted packet MD `e2ba11032528f972a7374e1a0d535b33a2dbf64d610cdf56ef021abac2844e43`; JSON `4557a131465925894ae03296d17f98cf33d0395a5a76fd94722e9e1c8e599a94`. Independent stdlib arithmetic/source range hashes: `common_v2_independent_algebra.json`. Никакого JAX/product execution не было.

## Оставшаяся граница

Открытых содержательных blockers после PPO correction нет. Два точечных уточнения формулировок согласованы с GEN author:100windows×4values означают100Bernoulli units; prior μ2σ.6 требует confidence_interval absent из фактического STA-02 TEST01. Обе строки теперь независимо перечитаны в final common MD/JSON и приняты; source inventory отражает corrected PLG JSON. Все17 common manifest hashes совпадают с actual files. Для PLG MD release-only header replacement отдельно проверен exact inverse-byte chain из release_editorial_deltas.json; peer нормативный текст не менялся. Ожидается только родительский global release freeze, не содержательная правка common. Final global structural QA выполняется отдельным независимым checker и не является native PASS.
