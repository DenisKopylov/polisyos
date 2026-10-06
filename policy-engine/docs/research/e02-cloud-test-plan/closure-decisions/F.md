# F — текущие научные критерии, consumers и отдельная приёмка

Читать вместе с [методами](method-decisions.md#methods-f) и [runtime-профилями](runtime-profiles.md#f-current-runtime). Это reconciliation опубликованных source-bound receipts, а не новый численный прогон, приёмка G или разрешение публикации причинного вывода. `closed` ниже — техническая рекомендация по указанному оригинальному критерию; authority, интеграция и полный production run принимаются отдельно. Незаконченные API/TMLE continuation packets не повышаются до PASS.

## Исторический G97 и текущая граница

G97 `97c85fae2d4505ec8248540d98b9556296244208`, tree `e77c0741d3b19acb43e07a0de2bdb97c8fa98ee3`, имел 34 `partial` и B219 `held`; checkpoints 03/05/06 принимали bounded slices с `finding_closure=false`. Прежний аудит и его планы сохранены в Git: `closure-decisions/F.md@d9c48853c5ab9ad7473df204bf3a7a1995a32057`. Тогда отсутствовавшие worker/RBC/exporter witnesses не являются описанием более поздних кандидатов. Прежний read-only аудит не исполнял предложенные команды.

Текущий исходный знаменатель — полный `finding-owners.tsv@198076863e143dea9f89f02734b13d50dae3eed5`: **35 IDs, 17 bundles, 36 coverage bindings к 35 различным original source blocks**. Две записи LA-016 указывают на один и тот же блок LA_r09:513–539. Exact ranges/bytes/hashes находятся в [coverage.json](coverage.json); исходные B_r19/LA_r09 cards не заменяются пересказами.

Сверка использует полный independent `original35-reconciliation.json` (235804 bytes, SHA-256 `95f728b758fde25591b0124bc0a2cd8b6c0acd86a61deb6d13bc07e99c4ba2a7`) и его selection/Markdown. Frozen421 `421f1dd977b237307394c68820caab4156716eb2` остаётся историческим transfer; G audit `363e7ae0cb2929a92d9667334fdc0ac3087daf5e` не переписывается задним числом. Current source supplements перечислены ниже; это не новый composed-source runtime PASS.

## 35 оригинальных критериев

Полная scratch proposal различает technical original criterion и current continuation: **26 closed / 8 limited / 1 held** против **21 closed / 13 limited / 1 held**. Числа относятся к полному указанному набору и не являются формальным ledger G. Для всех 35 `G_acceptance=UNRUN`. Pending API/TMLE packets требуют нового source-bound решения; сохранённые scientific waves не перезапускались.

| ID | Оригинальное свойство / current continuation recommendation | Deciding source и отдельный остаток |
| --- | --- | --- |
| B204 | Estimable standard DiD и честный pretrend; closed | DID + DIAGNOSTICS; отсутствие pretest ≠ passed, nonrejection ≠ parallel trends. |
| B205 | Actual HC1 / unit-cluster CR0; closed | DID; совпадение covariance algebra не доказывает small-cluster coverage. |
| B206 | Requested level меняет DiD И RDD bounds; closed | DID + RDD checks0/5/12; actual .8/.95/.99, не выдуманный новый .90 run. |
| B207 | Fixed θ_sel / estimated-share IF / unit multiplier; limited | DID; original finite scientific criterion closed, admitted production sampling/authority отдельно. |
| B208 | Centered null и тот же closed finite-B inversion; limited | DID; 160-DGP witness, endpoints/nextafter controls; не simultaneous/small-G guarantee. |
| B209 | Anticipation-safe full eligible horizon; limited | DID; support failure не меняет target; реальное anticipation assumption не установлено. |
| B210 | Actual sharp CCT RBC; closed | RDD; native clean-room weights/HC0 и real external oracle; real cutoff design отдельно. |
| B211 | O(np) weighted structures, kernels/order/SE; closed | RDD; diagonal-WLS oracle и permutation; нет измеренного whole-method speedup. |
| B212 | Point-only backend без изготовленного CI; limited | DoWhy423 + historical installed5cd; выбранный backend реально выполнен, latest composition/authority отдельно. |
| B213 | Actual estimand/contrast/target binding; limited | DoWhy423; selected linear ATE, не label-only универсальная mediation capability. |
| B214 | Known reverse и explicit unresolved/cycle refusal; limited | STATIC518 + intake632; default normalizes known reverse; Scientist node canonical DAG profile, не all PAG/CPDAG types. |
| B215 | Conditional Gaussian abduction / complete residual inverse; closed | SCM6d; posterior credible law не sampling CI, nonlinear partial posterior limited. |
| B216 | Endpoint m-separation и actual do/sigma/IDC entries; closed | STATIC518; 57 static causal entries, unknown marks/compact lag refuse before rewrite. |
| B217 | Perfect do incoming directed/latent surgery; closed | SCM6d + STATIC518; outgoing paths и независимый latent-DAG oracle сохранены. |
| B218 | Lag/self-lag representation/export и static refusal; limited | SCM6d + STATIC518/intake632; time-unrolled inference не заявляется и не подменяет original export criterion. |
| B219 | Complete keyed mixed multiedge export; closed | SCM6d actual NetworkX3.6.1; историческое missing-wheel UNRUN superseded только этим exporter witness. |
| B220 | Deep cache immutability / detached rows / copy freshness; closed | CACHE213; preceding mutable-row FAIL сохранён; no live Kuzu claim. |
| B221 | Observed root/joint-row law through real fit; closed | SCM6d actual selected worker + VERSIONeaf9; unknown law limited. |
| B222 | Declared fitted additive polynomial law; closed | POLY6f; helper→CAS→query/twin, quadratic4 vs OLS1.36, independent cubic8; no new fitter prerequisite. |
| B223 | Explicit comparator and same-U contrast; closed | SCM6d + ROOT3afb; model/ITE distributions не estimator CI. |
| B224 | Replaced mechanism bypass / safe pruning; closed | SCM6d; relevant factual ancestors/shared noise не удаляются. |
| B225 | Declared stochastic laws / stable tails; closed | SCM6d independent math.erfc, positive-tail SF differences; no same-SciPy-CDF independence claim. |
| B54 | Fit identity / current diagnostics / immutable readers; closed | TMLE55d2; original cache criterion measured; new native report continuation pending separately. |
| B56 | Study-wide admitted fold resource accounting; limited | Historical TMLE55d2; latest broker/study packet pending, no omitted folds or metadata cap as evidence. |
| LA-001 | Treasury relocation / IDs / seeds / actual RNG; closed | Treasury03bb/63425; retained versioned v1/historical law, no unrequested new time innovation. |
| LA-002 | Family catalog / IC certificates / reexports / supported loading; closed | FAMILY7f; real four-family service/CAS and runtime loading. Four new family→state mappings не prerequisite. |
| LA-003 | Fiscal/labor relocation, PatchMap/masks/key/spec/compiler/replay; limited | ECO412 checks0/4/6/10/11; real relocation passes, .10 budget precision remains FAIL. |
| LA-004 | DISTINCT economic models, paired regimes and deliberate divergence; closed | ECO412 checks0/4/6/8; state/units/step/taxbase/RNG/budget/outputs. Welfare norm не prerequisite. |
| LA-007 | Exact empty id_engine.py absent, package/loaders preserved; limited | Already absent base198; API supported loader/install reconciliation pending; no new deletion claimed. |
| LA-016 | Dedicated metadata/callers/flags/slots, default retirement; closed | DIAGNOSTICS0b; maintained request→registry/dispatcher/CAS, historical import explicit; same original block twice. |
| LA-017 | Norm diff/issues/pass config/report/topic consumer migration; limited | Lex00a6 finite plan/duplicate/CAS/CLI property; full supported migration packet distinct from real-law authority. |
| LA-019 | Exact empty causal_engine.py/interference.py absent; limited | Already absent base198; preserve nonempty packages; pending finite filename/loader/docs/install packet. |
| LA-020 | Supported facade identity/FQN/patch/docs/install ABI; limited | API729 historical actual census/wheel/sdist; latest generic-guard packet pending, not every possible external computed importer. |
| LA-035 | Named normalized-income/budget historical baseline; held | ECO412 check15 owner packet; formula/aliases/native/JIT/grad/guards pass. Named optimizer and units/population/time/sign intent absent. |
| LA-037 | One native IR slot owner/direct compiler/docs/install; closed | FAMILY7f + docs3e181; five identities/native patches/CAS/page; byte-identical installed owners only. |

## Все 17 bundles и consumer boundaries

| Bundle | Current bounded path | Отдельное условие |
| --- | --- | --- |
| <a id="bundle-api-01"></a> API-01 | Historical API729 canonical facade/census/wheel/sdist; latest owner continuation pending. | LA-020 ABI ≠ absence of reflection; LA-007/019 exact already-absent siblings ≠ package removal. |
| <a id="bundle-cau-01"></a> CAU-01 | Native standard DiD → report/CAS; DIAGNOSTICS producer + ROOT current typed-view/diagnostic readers. | B204/205/206 distinct; recomputed pretrend is not identification authority. |
| <a id="bundle-cau-02"></a> CAU-02 | Fixed θ_sel/share IF/unit Mammen/null inversion on DID. | 160 known-DGP replicates each arm; exact retained source, no real-data/small-G guarantee. |
| <a id="bundle-cau-03"></a> CAU-03 | Native clean-room CCT RBC → dispatcher/report/CAS/canonical fresh reader. | GPL external development oracle not product dependency; no fuzzy/selector/cluster claim. |
| <a id="bundle-cau-04"></a> CAU-04 | Real configured Python3.12/DoWhy0.14 worker → validated Python3.14 parent/report/CAS. | Python3.14 markers remain excluded; selected ATE only, authority separate. |
| <a id="bundle-cau-05"></a> CAU-05 | Dedicated maintained Standard route, registry/slot/flags and historical replay. | Original two LA-016 bindings refer to one card. |
| <a id="bundle-eco-01"></a> ECO-01 | Distinct real native/plugin profiles; canonical current Gini/domain; preserved normalized baseline. | LA-004 closed finite inequivalence; LA-035 held intent, not a common Gini hold. |
| <a id="bundle-fit-01"></a> FIT-01 | Original native fit-core/cache/reader evidence. | Latest study-wide resources/native-report continuation pending; no automatic B56 promotion. |
| <a id="bundle-fry-01"></a> FRY-01 | Real Treasury RNG; FAMILY catalog→IC certificate CAS; IR layout→compiler/patch/state/docs/install. | LA-002/037 original migration complete; no invented certificate→new kernel gate. |
| <a id="bundle-fry-03"></a> FRY-03 | Registry spec/compiler/replay native fiscal/labor → complete PatchMap/state/CAS. | Decimal fiscal precision red visible; law/fingerprint unchanged, LA-003 limited. |
| <a id="bundle-grf-01"></a> GRF-01 | Shared static endpoint/lag admission before native separation/surgery/ID consumers. | Original unresolved CPDAG escape and malformed sibling fixture failures preserved. |
| <a id="bundle-grf-02"></a> GRF-02 | Actual NetworkX multiedges; deeply immutable cache JSON tuples/fresh plain rows. | No live Kuzu backend or global graph completeness claim. |
| <a id="bundle-grf-03"></a> GRF-03 | Known reverse normalization, lag-preserving export; declared static refusal. | Canonical DAG Node profile is narrower than general PAG/CPDAG completion/temporal inference. |
| <a id="bundle-lex-01"></a> LEX-01 | Frozen pass-plan/real expr AST/CAS/CLI witness. | Topic similarity not causal effect; finite migration residual not identical to absent legal authority. |
| <a id="bundle-scm-01"></a> SCM-01 | Real root-fit/source law; POLY helper→CAS→query/twin; VERSION1.1/legacy1.0. | No new default nonlinear fitter or general partial posterior. |
| <a id="bundle-scm-02"></a> SCM-02 | Analytic Gaussian posterior/shared-U comparator, typed distributions/CAS readers. | Outcome/ITE/credible distributions not estimator confidence intervals. |
| <a id="bundle-scm-03"></a> SCM-03 | Exact surgery/pruning and declared stochastic laws. | Independent math.erfc tail oracle; temporal/unknown law refusal. |

## Property, proxy и классификация остатков

F-M5 использует один фиксированный θ_sel, influence от estimated cohort shares, один iid Mammen multiplier на unit и тот же closed effect-scale test/CI inversion. В DID known DGP true0 и true1.5 дали **154/160 coverage** каждый; null **6/160 rejects**, alternative **160/160 rejects**. Это проверка данного synthetic DGP с binomial bounds, не вывод о real panel и не новый прогон на DIAGNOSTICS0b. Сам diagnostic basis и selected CAS view проверяются отдельно ROOT3afb.

F-M6 уже выполняет CCT sharp RBC: 4036 external differential cases, maximum CI difference `3.658229275060876e-11`; coverage true0 `1879/2000`, true3 `1877/2000`. Accepted criterion — 99% Clopper–Pearson interval содержит .95 и observed coverage в [.925,.975]. No-property RBC removal оставляет markers, но **12108 numerical differences** и coverage **84.35%/83.80%**. Native .8/.95/.99 bounds и invalid-level refusal относятся к B206; local weighted structures к B211.

B225 independent oracle находится в `test_scm_result_semantics.py@6dcb792b6f8c2d2dcfc04a5e04ea33135a2ad181`: `math.erfc` Normal CDF и survival-function differences для положительного tail, включая [8,9] и [-12,-10]. Это независимая логика от sampler SciPy; прежняя формулировка «independent scipy CDF» была неверна.

P40 buckets следуют свойствам, а не package names: covariance/interval; share resampling/null inversion/anticipation; separation/surgery/export/cache/profile; abduction/root law/polynomial/comparator/pruning/sampler; distinct models/current metric/optimizer intent. P37/P38: typed manifest с теми же physical bytes не является default manifest; свежий diagnostic digest/typed tests нельзя заменить статусом; finite stale Gini не характеризует changed current population. Removal controls сохраняют markers и удаляют свойство.

P41 не установлен для глобальных inherited-red ярлыков без exact pre-slice command replay **и** полного zero-overlap input denominator. ECO mixed97 на slice base и source964 дал 93PASS/3FAIL/1SKIP; совпадение красного само по себе не P41. C003 forward numeric carry companion имеет собственные 37PASS/independent37PASS и не превращает fiscal precision/Plotly SKIP в PASS. Whole architecture/docs/compatibility/static diagnostics сохраняют FAIL/ERROR/UNRUN на своих SHA; их source/check identity не переносится на текущую документацию.

<a id="receipts"></a>

## Source receipts и точные ссылки

Ниже `F/` означает `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/`. Каждый Git ref — **carrier**, source/tree берутся из JSON; `/checks/n` содержит уже исполненную команду, среду, inputs, outcome и полный output ref. Этот doc update только читал receipts; научные команды не запускались заново.

- **ECO412**: `F/economics-continuation-20261006.json@d9c48853c5ab9ad7473df204bf3a7a1995a32057`; 127652 bytes, SHA-256 `ced279a2a9ce169c271c4dedbb2ac18a27193de75dd7cd2cf80375fb633c4162`. Implementation `4128879c3cec37dcb2bd1e7f91a1da5e4f51d2d3`, tree `134aca5ad6bac87da8d2f3d18a4be0ab20652251`.
- **CARRYc003**: `F/economic-training-dtype-continuation-20261006.json@d9c48853c5ab9ad7473df204bf3a7a1995a32057`; 58922 bytes, SHA-256 `cb9efb8452c6446d78d19225dcae4c69dadaa817810e16fcc9c8741dee8ad6c7`. Implementation `c003bd673fd672726db18773bf888357a468d901`, tree `16927b18be300fc6c1723c2af4bb8a421ccac357`.
- **FAMILY7f/docs3e181**: `F/family-layout-consumers-20261006.json@e00dd3799cf2cdd14baf4b26e175ba1e848c3a6a`; 97248 bytes, SHA-256 `04fba06be549c934631ea496ae1cbf6b3698e2f235a94b61880ba540308f2cbf`. Implementation `3e1819173f0593ce93d257c3c62cdb2fa627e426`, tree `45852a68bb786a96d6d23c52cea790f13d3489d3`.
- **VERSIONeaf9/docs e94**: `F/scm-schema-version-20261006.json@3ad29e43aaa16d2ce320d4b850f8b84f9abdd1e0`; 131648 bytes, SHA-256 `0aef8daff10c6a047fd5104910bdf79bfc06f58a2cd0c7ef3ba80c2406292570`. Implementation `e94a40e78416b7392edf96f1f24c7846a808c8d0`, tree `8fcab970c187cb6f15f4b3a7cb368b9f929db2fd`.
- **STATIC518**: `F/static-admg-profile-20261006.json@3ad29e43aaa16d2ce320d4b850f8b84f9abdd1e0`; 50088 bytes, SHA-256 `d71112938c6ee404c4436979df7139a2b6c7948d34fea1597de48ec2d0704818`. Implementation `5182825c190aa403bee765e339a119bb53e805e0`, tree `87e2bc0e426a2e1cc41fdb3adb340a70ed0c8b1e`.
- **POLY6f**: `F/polynomial-helper-cas-20261006.json@3ad29e43aaa16d2ce320d4b850f8b84f9abdd1e0`; 44860 bytes, SHA-256 `2aa65d305f67d094489b849ee64cff927db717bd866acb51484e99ed051f91f4`. Implementation `6f95f55ca7d9c5cd9489256a354a27da058b46b9`, tree `1481e08664a271f12e77807f2468906efd7e40c5`.
- **DIAGNOSTICS0b**: `F/did-diagnostic-basis-20261006.json@f88c98a190c336ef414361a236276ed7ea6d3d62`; 162688 bytes, SHA-256 `ba2405cc2cafdb42b2bcfaab0606aacb60056cdffe9fc4f304f854c1283e62dc`. Implementation `0b522ed173730b4ec744253bb75b6ee260bfcebb`, tree `a402720194c41d0b6c5bb93cceb326cd4699df72`.
- **DIDcebe**: `F/did-selected-cohort-20261006.json@4c5a11ff8050c6108f6753177b96e6714cef401f`; 216928 bytes, SHA-256 `bfbe2d38cc248e6c6a4ae5ab762bc751109007822ada68b707de3a3abdc00e73`. Implementation `cebe94d8134a4652bbfc1ae4d74ec6403940ced5`, tree `a2ed0a07151263cd747cff5ec410643e326620a9`.
- **RDDfb**: `F/rdd-sharp-rbc-20261006.json@15a04c4400497374416e167a5f61ebc12f61b8e4`; 68616 bytes, SHA-256 `99a51663ca672ad1809a04dfbdca89bcf65c65f964b43a5bd9305b33dd5cae60`. Implementation `fb022aa12599ee1617f83d154cd9a8027b2a58b8`, tree `bee112b9284e11b78c96d2f91660f330d68b26c7`.
- **ROOT3afb**: `F/causal-consumer-boundaries-continuation-20261006.json@4a0c831ce1088c4e2fe1587b6c5a2eb1fb85b75c`; 13477 bytes, SHA-256 `0ec2f8e09b0dfc2be368d6aa30dd1160ffc4c0d2e3fc9bf1f9f1bdcc398d0927`. Implementation `3afb3ea5f26ad429ac45be78bd2cbd180fcc5a77`, tree `508884be8ea79e5b87844030ea4122c8e74d610a`.

Дополнительные неизменённые primary receipts: `F/scm-source-bound-20261006.json@bf335dd687c313fda9001fa3bb1365df6bc5ae1f` source6d; `F/graph-cache-immutability-20261006.json` на том же carrier source213; `F/treasury-execution-20261006.json@f4fa51e6dd247cfd967450263579d67233a743d6` source03bb/63425; `F/dowhy-worker-20261006.json@c8c2319d6c48f23f90103322da8cd63bc959da6f` source423; `F/tmle-20261006.json@f460bd81b8124be58f890f59a53e2aba9e7ceb76` source55d2; `F/api-20261006.json@449d32909928caf39382f4ff02ac74b0adf277eb` source729; `F/lex-pass-plan-20261006.json@77166daa0ff8b9659e3978447f9016c691694266` source00a6. Exact prior bytes/tree/check pointers находятся в immutable frozen421 full audit, а новые владельцы должны приложить отдельный current receipt. Installed5cd outputs читаются по explicit `output_git_sha=3dde887e22592cdd7c1fe8865707afdfd72dc6fb`; FAMILY не выдаёт их за freshly built7f source.

G получает код и deciding bytes через fetch/PR. Full production inputs остаются локально; точный data-dependent run относится к composed candidate SHA и canonical evaluator/rights/appointment/revision packet. Никакой synthetic oracle, resource receipt, imported backend или эта рекомендация не выдаёт authority и не заменяет G acceptance.
