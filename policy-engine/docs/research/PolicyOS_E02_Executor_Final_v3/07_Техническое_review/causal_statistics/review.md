# Финальное техническое ревью LANE-05 и LANE-11

**Дата: 01.11.2026. Scope: 17 пакетов. Срез: `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## Решение, которое полезно принять сейчас

В целом предложен **разумный адресный ремонт существующих владельцев**, а не новая универсальная платформа. Самые сильные части — endpoint-aware graph semantics, явный estimand staggered DiD, сохранение реального RBC, разделение fit-core/current-view, conditional joint-root law и отказ от подмены production evidence синтетикой. Переписывать эти подсистемы целиком оснований нет.

Но до окончательного принятия технических заданий нужны четыре содержательные поправки:

1. **CAU-03: нельзя закреплять inverse-variance WLS covariance как корректную covariance kernel-local regression.** Независимая точная алгебра показывает существенное расхождение уже на 12 точках: ожидаемая сохранённая оценка variance составляет **64,49%** истинной variance intercept при iid noise. Coordinate/SVD repair этого не устраняет. Нужен явный variance profile и compatibility decision, а не скрытая замена conventional на RBC. **CS-001**.
2. **CAU-04: Statsmodels OLS — underlying backend DoWhy0.14, а не независимая numerical реализация.** Существующее сравнение сохранить как adapter parity; добавить малый closed-form oracle и оставить отдельную DGP coverage. **CS-002**.
3. **FIT-01: фактический continuous cross-fit использует global outcome scaler, обученный на всех Y до folds.** При regularized ElasticNet held-out outcomes меняют fitted nuisance predictions. Это не дефект cache reuse, но важный пропуск scientific acceptance. Нужен fold-owned preprocessing и perturbation test; binary pilot не расширять задним числом. **CS-003**.
4. **DDM-02: actual CLI повторно использует calibration stream как holdout, если отдельного holdout нет; report называет raw quantile moving-block bootstrap без выполненного bootstrap.** Исправить producer/source ownership и truthful method identity; arithmetic smoke сохранить, production authority не ослаблять. **CS-004**.

Ещё две адресные квалификации: независимый target/quantile oracle для SCM refit (**CS-005**, усиление тестов, не обнаруженная numerical ошибка); точные native profiles и консервативное отношение к archived Kuzu (**CS-006**, не требование срочной миграции).

Полные тексты предлагаемых REQ/TEST, evidence, alternatives, риски и неопределённость находятся в `findings.json`; решения по 14 группам технологий — в `library_decisions.json`. Ни один product test в этом ревью **не запускался**. Выполнена только независимая stdlib арифметика и анализ документов/исходников. Исторические PASS исходного аудита не переаттестованы.

## 1. Как интерпретировать результат

`P` — immutable `baseline/PolicyOS_E02_Executor_Specifications`; пути `src/`, `tests/`, `workers/` ниже относительно `e02_repository/policy-engine`. Все 17 полных решений и тестов прочитаны; JSON проверены через полное чтение/parsing и сопоставление содержательных строк с MD, отдельные различающиеся формулировки прочитаны. Прочитаны оба lane и их integration contracts; рассмотрены все 21 relevant scenario binding и 25 local-only REQ. Exact hashes/ranges и ограничения чтения — `coverage.json`.

Разделяются четыре разных результата:

- **repair acceptance:** удалён названный дефект при сохранении совместимости;
- **bounded capability qualification:** actual owner проходит заданный класс запросов end-to-end;
- **empirical/scientific validation:** предпосылки и качество метода подтверждены на подходящем источнике/дизайне;
- **permission:** отдельное полномочие на использование/изменение мира.

Ни source review, ни content hash, ни correct synthetic answer не переводят автоматически из одного уровня в следующий. При этом полезный conditional result не должен исчезать только из-за отсутствия институционального разрешения. Это согласуется с `00_Общее/Архитектурное_направление_и_отступления.md`; архитектурный causal-grounding firewall также прямо признаёт зависимость гарантий от soundness/reference completeness и откладывает тяжёлые компоненты. Он не обосновывает второй общий solver ради каждого локального ремонта.

## 2. Вердикт по каждому пакету

### GRF-01 — retain + bounded qualification

**Почему решение подходит.** Endpoint-aware m-separation и perfect-do surgery — не обычная достижимость в DiGraph. `admg_ops.py:699–805` работает с состояниями endpoint-пути; collider ancestry имеет собственный смысл. Предложение сохранить этот owner и квалифицировать actual rule→ID/IDC→result→fresh reader правильнее, чем заменить всё graph library. Независимый test `test_admg_latent_oracle.py:1–164` разворачивает bidirected edges в latent DAG и использует ancestral moralization, то есть не просто повторяет production traversal.

**Сила и предел теста.** 200 трёхузловых ADMG, 2400 separation и 19200 surgery checks дают сильный finite mathematical corpus. Но fixed forward topological representations не заменяют reverse-mark/rename cases; они отдельно нужны и в пакете есть. Полная идентификация ID/IDC, большие districts и semantic source validity не доказываются этим corpus. Добавить небольшой независимый holdout 5–7 узлов с длинной collider-descendant цепью и несколькими bidirected districts: это качественный transfer, а не увеличение числа seeds того же шаблона. Always-refuse не пройдёт positive identified estimand; hardcoded truth table на трёх узлах не пройдёт holdout.

**Стоимость/библиотека.** Reuse adjacency и ancestor state полезен; не создавать новый causal graph engine. NetworkX d-separation допускает DAG, поэтому подходит как часть независимого latent-expanded oracle, не drop-in ADMG owner. [Официальный контракт NetworkX](https://networkx.org/documentation/stable/reference/algorithms/d_separation.html).

### GRF-02 — retain narrow repair; targeted profile qualification CS-006

`causal_graph.py:837–856` действительно MERGE-ит связи по endpoints; это не сохраняет multiset parallel relations. **Preflight всего входа до write**, simple-only rejection и действительный перевод mixed caller на уже существующий lossless bulk route — оптимальная первая мера. Один новый отказ без positive bulk consumer не реализует полезную способность. Occurrence-aware direct emitter оправдан только реальным caller need; его преждевременное добавление увеличит schema/migration surface.

`admg_ops.py:135–193,418–452,735–747` показывает repeated preparations и bounded cache. Private prepared representation внутри одного запроса сохраняет публичную revalidation; общий caller-owned mutable graph не должен проникнуть в кэш. 128 entries ограничивают число объектов, но не общий размер огромных графов; это не defect малого patch, а boundary будущего workload admission.

Multiset, marks, lag, metadata, duplicate occurrences и 120 edge-order permutations сильнее проверки количества ребер. Backend-independent canonical result нужен до и после fresh reopen. Backend counts не доказывают memory/runtime. Отдельно: official Kuzu repository archived 10.10.2025; это аргумент за минимальный compatibility repair, не доказательство несовместимости или срочного forced migration. Rustworkx отсутствует в parent lock и не может считаться qualified от optional import. [Kuzu maintenance status](https://github.com/kuzudb/kuzu/).

### GRF-03 — retain; bounded temporal capability, не arbitrary completion

`causal_graph.py:1078–1183` уже canonicalizes graph, сохраняет known reversed orientation/metadata и явно разворачивает bidirected edges в latent parents. Это правильная representational projection; projected latent DAG сам по себе не делает latent variables наблюдаемыми и не даёт fitter отсутствующие данные.

Finite temporal unrolling `(variable,time)` — подходящий reusable adapter при существующем temporal owner либо после его census. Лаг, horizon, history, initial conditions и source time alignment должны быть частью входного контракта; расширять до произвольного dynamic SCM здесь не нужно. Два variables, lag1, t0..t3 и второй lag2 case проверяют больше, чем просто отсутствие отказа. Дополнить transfer ненулевым start time и отсутствующей initial history: допустимый запрос даёт вычисленный результат, недостаточная history — конкретный missing-basis result, а не нулевая подстановка.

Важно сохранить separate native_hybrid vs selected Linux3.12 worker profiles. Polynomial/hybrid support не появляется в worker0.14 от того, что другой fitter успешно выполнился. Partial/PAG family остаётся conditional alternative set, а не произвольно выбранный DAG. Worst-case unrolled size O(T(V+E)) должен быть вычислен до allocation; не нужен cache/solver сверх этого без измерения.

### API-01 — retain; небольшая правка census, не facade redesign

Actual initializers `causal_engine/__init__.py:1–42`, `interference/__init__.py:1–67` уже explicit и сохраняют class identity. Public2/9 и direct-only compatibility5/3 не надо раздувать до всех 11 names sync helper. `identification.py:2163–2223` реально вызывает `_sync_public_algorithm_overrides` перед dispatch, поэтому monkeypatch+restore+no-op control проверяет поведение, а не только `__all__`.

`test_facade_consumers.py:167–212` содержит content-only prefilter и способен пропустить relative import без строк `causal_engine`/`interference`. Полный AST census конечного tracked denominator проще и надёжнее множества исключений; stdlib достаточно. Package-relative resolution и submodule fallback обязательны. Dynamic strings/external FQNs вне literal denominator — отдельный lifecycle census, не отрицательный вывод из отсутствия AST hit. Installed artifact test должен быть настоящим, но не требует нового disposable commit без отдельной авторизации.

Неверная реализация «правильный export list, старый hidden dispatch» должна падать на behavior test; «все external callers отсутствуют» не может пройти без доступного corpus. Сохранить честное ограничение, не удалять живые aliases ради чистого API.

### CAU-01 — retain targeted numeric repair

`did.py:197–265` объясняет реальный риск: cluster equality mask для NaN может потерять scores; integer-coded complete unit partition исправляет причину. Повторная проверка exactly-one label per unit до fitting полезнее обработчика exception после covariance. HC1 и **uncorrected CR0** намеренно разные; готовая библиотека по умолчанию может добавить small-sample correction. Statsmodels пригоден как отдельный differential reference только с `use_correction=False`. [Версия 0.14.6](https://www.statsmodels.org/v0.14.6/generated/statsmodels.stats.sandwich_covariance.cov_cluster.html).

Panel fixture ATT3.125, CR0SE.5659615711 и HC1SE.9042722673 проверяет число; unit relabel, row permutation и повторение единиц проверяют закон агрегации. Недостающие/mixed/NaN labels должны отказать адресно. t0=0 допустим в общем DTO, но не обязан стать валидным standard-DiD study — правильное разделение общего carrier и методного admission.

Lower-tail normal quantile устраняет rounding-to-one при confidence near1; numeric-range отказ при underflow лучше выдуманного finite CI. Point estimate, pretrend nonrejection, parallel-trends assumption и finite-cluster validity не смешаны. Возможная optimization при очень большом G: grouped indexed accumulation вместо O(nG) masks, но не prerequisite локального исправления и не новая статистика.

### CAU-02 — retain, хороший explicit estimand; empirical scope остаётся узким

Главное достоинство — **theta_sel задан формулой**, а не названием «staggered ATT»: среднее cells внутри cohort, затем estimated shares ever-treated с derivative share contribution. Unequal cohort/cell case41/6 против5.75 различает не тот estimand. `did.py:526–639,716–765,909–998` содержит actual target/influence/bootstrap; один Mammen multiplier per unit across all cells сохраняет совместную law. Независимые per-cell multipliers были бы другой covariance.

Finite-B plus-one inversion и endpoint/nextafter tests — сильная защита от несогласованных p и CI. При B399 p-resolution1/400; это ограничение реального метода, а не precision до machine epsilon. Anticipation g−1−a и controls timing>t+a должны проверяться на boundaries; no eligible cells нельзя молча выкинуть и назвать тот же target.

R `did::aggte` — содержательный reference для различных aggregation targets, но не drop-in для данного custom theta_sel и Python3.14. Не менять target ради совпадения популярной библиотеки. [Maintainer documentation](https://bcallaway11.github.io/did/reference/aggte.html). Campaign160 seeded n400, six periods, two cohorts, AR.6, null/alternative — bounded scientific evidence; не все panels/attrition/heterogeneous anticipation. Нужен held-out design с иным cohort-size ratio и фактической finite target формулой, а не только новый seed. No universal coverage claim в пакете уже правильно сформулирован.

### CAU-03 — targeted revision required, CS-001

Coordinate `u=(x−c)/h`, economy SVD/QR и общая rank/solve policy — оптимальный repair. Старый source `rdd.py:98–118` проверяет rank weighted design, но решает через Gram pseudoinverse с другим effective tolerance; small units способны потерять slope. Рефакторить узкий owner, а не заставлять пользователя включать RBC, чтобы ordinary point стал корректным.

Однако сохранение old covariance как научной нормы — ошибка. При kernel weights и iid observation errors variance содержит **W²**, не просто inverse Gram. Новое profile решение должно различать legacy inverse-variance WLS, conventional kernel sandwich и robust bias-corrected inference. Это изменение observable numerical contract: historical readback не переписывать и не скрывать migration. Exact counterexample и replacement REQ/TEST — CS-001.

RBC уже содержателен: corrected weights, q-residual variance, union h/b, actual removal mutants; `test_rdd_rbc_independent_oracle.py:55–162,198–264` строит finite sensitivity oracle через независимый WLS functional. Сохранить. Independent DGP400 принимается в заранее заданном band, не обязан повторить исторические371 hits. Ни он, ни rdrobust label не доказывает fuzzy/cluster/masspoint/data-selected-bandwidth support. External rdrobust может быть будущим reference с совпадающими parameters; его default NN и automatic bandwidth не являются reference для текущего fixed-HC0. [Maintainer implementation](https://github.com/rdpackages/rdrobust/blob/main/Python/rdrobust/src/rdrobust/rdbwselect.py).

### CAU-04 — targeted test revision CS-002; runtime architecture retain

Worker isolation и exact ATE/backdoor.linear_regression/binary0→1/targetATE/95%/fullrank admission соответствуют существующему implementation. `worker.py:69–150` реально identify+estimate; point-only должен оставаться полезным partial report, не успешным CI. Parent3.14 не должен пытаться выполнить worker через marker-conditioned old DoWhy dependency.

Same-backend OLS equality проверяет передачу колонок, treatment contrast, estimator class и формирование ответа, поэтому **его нужно сохранить**. Но DoWhy0.14 вызывает `sm.OLS(...).fit()` и берет CI/SE из того же result; independent label неверен. Добавить tiny rational balanced-design oracle и independent interval reference; DGP coverage против truth2 оставить отдельной. [Exact DoWhy0.14 source](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/linear_regression_estimator.html).

Whole request/response/source/graph/row inventory + CAS fresh reader отлично закрывает adapter custody, но не graph truth. Coherent substitution source+report особенно важен: сверка двух подменённых объектов друг с другом недостаточна, нужен selected owner source. Новый contrast, mediation/NIE или nonlinear estimator требует actual worker support и scientific profile, а не разблокировки string value.

### CAU-05 — retain lifecycle and shared owner

Dedicated standard/staggered routes и direct legacy slots решают разные задачи. Сохранить old adapter bool-slot semantics; не возрождать retired generic registry alias, который заново создаст неоднозначный method identity. Versioned historical reader допустим только для genuine supported frozen plans; отсутствие corpus не закрывать искусственно сериализованным объектом с прежним FQN.

Это правильный **единый владелец I05-B lifecycle**, но не всех covariance estimators. Numerical evidence остаётся CAU01/02/03/04; один целый report job может проверить materialization/storage/fresh consumer для нескольких methods только с отдельными inputs/claims. Старый flawed interval в historic report не должен «исправляться» при чтении без новой версии; current recomputation и historical bytes — разные outcomes.

Проверка generic route отсутствия нужна рядом с positive maintained route, иначе always-refuse retirement проходит. Пакет не требует нового compatibility framework и тем самым хорошо соответствует free-grow: новый compatible method payload использует существующий typed dispatcher, а не новый case-specific import branch.

### SCM-01 — retain proposed shared plan; qualified model-family scope

Actual twin source `twin_network_query.py:452–482` проверяет roots всего graph до relevant plan: unrelated missing root действительно способен заблокировать вопрос. Исправление closure должно включать оба arms, factual ancestors и joint-law dependencies. Простое ancestors(outcome) **не достаточно**: наблюдаемый неancestor Z может информировать W через aligned root rows. Пакет правильно делает этот случай явным.

Shared polynomial predictor вместо копий в fit/query/twin — разумная композиция: degree/powers/basis должны соответствовать fitted spec, никаких скрытых interaction terms или defaults при malformed mechanism. Source-row mechanism validation в `gcm_fit.py:300–450` полезно независимо проверяет коэффициенты и residual carrier.

Нельзя называть fully observed residual abduction общим nonlinear posterior. Invertible additive-noise модели дают восстановление noise; incomplete factual evidence и неизвестные nonlinear mechanisms требуют отдельного posterior method, а не добавления случайного Normal. [DoWhy0.14 counterfactual assumptions](https://www.pywhy.org/dowhy/v0.14/user_guide/causal_tasks/what_if/counterfactuals.html). Selected worker linearANM, native_hybrid polynomial и manual declared models квалифицировать раздельно. Irrelevant missing-root positive, necessary-root negative и observed joint-root dependency — сильная связка; удержать все три после оптимизации.

### SCM-02 — retain numerical/conditional-law repair; targeted oracle addition CS-005

`gcm_query.py:894–1014` использует covariance subtraction/pinv, абсолютные tolerances и `allclose(...atol=1e-12)` при draw. Поэтому tiny genuine posterior variance способна исчезнуть. Whitened-noise normalized SVD и сохранённый factor вместо jitter/absolute-zero collapse — правильный direction. Формулировка должна обещать scale-aware numerical rank с declared tolerance, **не exact symbolic rank произвольных почти сингулярных floating-point matrices**. Добавить anisotropic scales/near-dependence и incompatible-evidence residual, не только равномерное s→1e−7.

Finite root-law defect также реальный: `gcm_query.py:1426–1440` сначала выбирает unconditional aligned row, потом pin-ит observed root. Для rows(W,Z)={(0,0),(10,1)} factualZ1 требует W10; independent pin не тот conditional law. Joint row filtering по всем фактам, exact discrete matching и сохранение multiplicities — простое правильное решение. No matching rows означает unsupported empirical evidence, не fabricated independent draw.

Shared-U twin важен: при детерминированной разности counterfactual marginals могут иметь ненулевую variance, а ITE — нулевую. Нельзя проверять только difference mean. Refit в source действительно пересэмплирует полные aligned rows и refits worker; source-row OLS validation сильна. Но shrink ratios не независимый target oracle — CS-005. `fit_and_compute` в DoWhy не делает такую подмену автоматически лучше: он также требует реального retraining; frozen-query bootstrap имеет другой смысл. [DoWhy refit distinction](https://www.pywhy.org/dowhy/v0.14/user_guide/modeling_gcm/estimating_confidence_intervals.html).

### SCM-03 — retain shared admission/law/stream repair

Manual raw endpoint path должен проходить тот же canonical graph admission, что fitted input; иначе строковый src/dst меняет reverse/PAG semantics. Existing owner подходит, второй validator не нужен. Canonical order по логическим labels в joint Gaussian coordinates сохраняет seed-equivalent representation; переход к независимым per-node Gaussian streams ради воспроизводимости уничтожил бы posterior covariance.

Prepared intervention plan должен различать atomic/stochastic mechanism replacement и shifted/clipped natural-mechanism transformation. Hard-do вправе не вычислять заменённый natural mechanism; shift обязан его вычислить. Проверки call counts здесь семантические, не только performance: malformed unused natural mechanism не должен блокировать hard-do, но не должен молча пропасть при shift.

Truncated normal и clipped normal — разные laws; хвост8..9 делает rejection sampler плохим выбором. SciPy truncnorm уже в selected numerical stack, standardized bounds обязательны. Tail moment test через independent quadrature и boundary-atom check лучше сравнения с тем же rvs. [SciPy1.16 truncnorm](https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.stats.truncnorm.html). Одно parse/factorization на query полезно; новый cross-query cache без измеренной необходимости не нужен. Joint plan ownership совместно с SCM01/02 снижает drift.

### FIT-01 — retain architecture; add continuous anti-leakage CS-003

Immutable numeric bytes, reader-owned metadata, current diagnostic view и controlled precomputed resolution в `tmle_core.py:240–351,746–819` действительно решают cache ownership. Field-complete 32=17fit+15view matrix важнее списка нескольких известных параметров: новый field должен получить явную policy. Same caller label не должен обходить full data hash. Diagnostic threshold change48→100 не должен вызывать expensive refit.

All scientific folds/repeats остаются, inner execution serial, outer LocalWorkerPool содержит queue и finally-release (`local_pool.py:117–207`). Не писать второй scheduler. Actual worker budget1/2 и failure-release нужны; thread counters не означают BLAS/OpenMP boundedness. sklearn разделяет joblib, OpenMP и BLAS, поэтому measured resource profile должен проверять соответствующий уровень. [Официальное описание parallelism](https://scikit-learn.org/stable/computing/parallelism.html).

Новый finding — global target scaling до split, а не проблема fit cache. Пакет честно ограничивает pilot binary iid, но lane способность включает continuous nuisance regression. Fold-owned preprocessing и held-out-Y perturbation дают сильный дополнительный capability test с очень малой стоимостью. Не требовать final ATE invariance: targeting/EIF должен использовать heldout outcomes. EconML DML — возможный другой метод, но не замена TMLE с сохранением семантики.

### BER-01 — retain repair; bounded explanation capability strengthening

Strict persisted JSON и construction validation — разные входы. `validation_rules.py:105–129` использует permissive `model_validate`, тогда как `persistence.py:181–197` уже требует version/fields/strict JSON. Вынести существующий strict intake в нейтральный owner правильнее нового framework и предотвращает divergent acceptance. Pydantic различает strict JSON и Python input; нужно тестировать реальные bytes, а не только ready-made model. [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).

Effective alias dedup экономит real model calls, но aliases не становятся независимыми объясняющими methods. Requested IDs сохраняются; tree-first fallback должен честно указывать actual empirical algorithm, alias-only agreement — N/A/limited по explicit decision, не fabricated perfect agreement. Actual `shap_kernel.py:1–157` делает exact coalition enumeration только малого d; ScalarModel не предоставляет tree structure. TreeExplainer не универсальная замена, и его dependence/background law нужно выбирать явно. [SHAP contract](https://shap.readthedocs.io/en/stable/generated/shap.TreeExplainer.html).

Предлагаемый дополнительный numerical transfer: f=x1*x2+2*x1, background[(0,0),(2,2)], target(1,3), declared empirical coalition game имеет v(empty)=4,v({1})=3,v({2})=5,v(all)=5, phi=(-.5,1.5). Это независимый двухигроковый oracle, не product test result. Проверить actual alias cache, order/name permutation и persisted values. Wrong constant attributions либо linear-only fixture specialization не пройдут. Exact Shapley для этого finite game — не causal effect и не гарантированная heldout faithfulness. Увеличение d требует явного approximation/cost contract, а не снятия ограничителя10.

### DDM-01 — retain canonical ownership; native behavioral qualification

Сохранить canonical events/enums, lazy imports и old FQN identity; очередное перемещение классов не исправит applicability. Format keyword без активного validator не является проверкой даты, поэтому реальные invalid date/offset cases нужны. Actual monitor positive диагностического drift должен сохранить diagnostic-only semantics и R4, тогда как calibrated active shift способен изменить readiness; это сильнее import smoke.

No source/empirical claim о calibration от самого relocation. Genuine old-FQN artifacts — только доступный trusted corpus; newly manufactured pickle проверяет механизм, не историческую поддержку. Installed wheel/sdist/resource profile пересекается LANE12: переиспользовать его evidence identity, не повторять packaging framework. Нельзя требовать external deployment/retraining ради доказательства contract identity.

### DDM-02 — retain applicability/policy design; add producer qualification CS-004

`model_registry.py:128–230` строит identity binding в основном из last projections, тогда как source должен проверять каждый nested signal; единый neutral helper с monitor — оптимальный ремонт. Все supplied shifts/quality/degradation должны относиться к target model/version, независимо от списка/last pointer. Final finite-source guard уже ограничивает authority; finding о direct builder не надо преувеличивать до доказанного production bypass.

ReadinessPolicy сейчас effective в mapper (`readiness_mapper.py:84–148`), но не везде связан с registry rebind. Typed identity/projection лучше нового policy DSL. Сохранять exact veto/signoff matrix: signoff не нейтрализует failed certificate, foreign subject или R1/R0. Дополнительно semantic threshold ordering стоит проверять при admission policy, если проект разрешает произвольные values; это небольшое strengthening, не установленный gate exploit.

TEST07 корректно описывает100 windows, не400 independent observations, и synthetic status. Его zero-alert Wilson arithmetic полезна, но actual producer имеет два отдельные gaps CS-004. Новый test обязан проверять **source identities**, а не числовое неравенство двух arrays. Отсутствие production observation owner остаётся точным BLOCKED/NOT_ESTABLISHED только для сильного claim; monitoring/research result сохраняется. arch MBB — существующий optional инструмент resampling, не источник authority/стационарности. [arch8.0.0](https://bashtage.github.io/arch/bootstrap/generated/arch.bootstrap.MovingBlockBootstrap.html).

### LEX-01 — retain minimal structural repair; useful qualitative route

`impact_diff.py:647–663` соединяет path через '/', поэтому boundaries теряются; typed tuple segments решают коллизии и различают integer/string без новой библиотеки. Fingerprint `:683–697` имеет свой historical stringification contract: grouping fix не должен молча менять persisted identities/version. Сохранить multiset matching и severity transitions, а не сделать set-diff, теряющий multiplicity.

Actual norm comparison→LegalPass→selected1.1 report→CAS→fresh JSON/MD/CLI reader даёт полезную объяснимую legal-change view. Stub остаётся not-evaluated; historical1.0 читается без нового source-bound authority. Typed paths slash/intstr и перестановки должны менять только правильные transitions. Candidate topics — qualitative directions/unknowns и повод обратиться к существующему scientific evidence owner, не causal estimate/правовой мандат. Никакая causal library не решает jurisdiction/source coverage: это отдельный domain evidence. Такой ограниченный positive path отвечает free-grow лучше, чем всеобщий отказ или выдуманные количественные эффекты.

## 3. LANE-05: что именно должна уметь система end-to-end

**Claim lane:** данный граф/модель, данные, estimand и numerical profile приводят к корректному условному числу/закону или точной границе, сохранённой для свежего потребителя. Не claim «любая политика причинно валидирована» и не требование автоматического изобретения истинной SCM.

### Где нынешняя интеграция сильна и чего не хватает

I05-A/B/C хорошо отделены и требуют настоящих owners. Binding table не объявляет общий smoke заменой всех local tests — это правильно. Однако A преимущественно проверяет 3–5 node fixtures; B содержит mislabeled independent OLS и covariance preservation problem; C смешивает сильную custody qualification с более слабым refit width witness, а binary TMLE pilot не проверяет continuous leakage. Поэтому успешный общий job сам по себе ещё недостаточен для научной квалификации всей lane. Local-only temporal, historical, performance и scientific requirements нельзя потерять при объединении сценариев.

### Предлагаемый bounded acceptance plan — без нового harness framework

**A. Structural capability (GRF/API).**

1. Оставить exhaustive local200/2400/19200 и existing behavior tests в ближайших owners. В integration выбрать один 5-node ADMG с collider-descendant и district, сохранить source graph+query, выполнить actual public identify/rule route и canonical backend export/reopen.
2. Независимый reference — explicit latent expansion+ancestral moralization; positive identifiable query и negative hedge/nonidentifiable query. Проверить equivalent reverse-mark representation/rename/permutation, not just stable count/hash.
3. Mutants: collapse duplicate edge occurrence, stale cache, bypass canonical admission. Source mutation меняет только зависимый result; unrelated query остаётся доступным. Simple-only direct Kuzu collision не пишет частичный граф; supported bulk positive выполняется реально.
4. Transfer после freeze реализации: 7-node graph, другой district/conditioned descendant, новый variable vocabulary и finite temporal lag2 profile с explicit history. Только graph/data/model resources меняются, никаких branches по fixture IDs. Holdout фиксирует expected oracle до запуска, не подбирается после результата.
5. Cold/warm preparation counters и отдельное RSS/time measurement на выбранном finite size; не прогонять весь heavy benchmark на каждой permutation. NX, Kuzu и optional rustworkx — разные actual profiles, не одна строка PASS.

**B. Statistical capability (CAU).**

1. Shared I05-B job принадлежит CAU-05, numerical assertions — respective CAU owners. До job должны пройти unit label/quantile, staggered influence/inversion, corrected RD variance и DoWhy closed-form tests.
2. Native route: trusted input materializer→registered dedicated estimator→whole report/envelope→actual CAS→new reader process. Consumer сверяет estimate, SE/CI, estimand, contrast, control/cohort/anticipation, variance profile, input/window/graph and backend identities; not only summary JSON.
3. Independent DoWhy fixture (8 rows) уже конкретизирована в CS-002: A/X/Y=(0,-1,-3),(0,1,3),(0,-1,-1),(0,1,5),(1,-1,-1),(1,1,5),(1,-1,1),(1,1,7). Regression [1,A,X] даёт beta[1,2,3], SSE8, df5, SE(A)=sqrt(.8), CI[-.29919829048,4.29919829048]. Student-t quantile независимо найден из closed df5 CDF, без Statsmodels/DoWhy/SciPy. Это algebraic fixture, не empirical coverage.
4. Adversarial: NaN label, wrong cohort baseline, removed group-share influence, separate per-cell multipliers, wrong kernel covariance, swapped DoWhy columns, missing cutoff, coherent alternate source+report. Negative controls должны сохранять plausible metadata, чтобы именно numerical/source oracle их различал. Point-only path сохраняет число и limits; always-refuse fails positive.
5. Transfer — study с иными cohort proportions, nonzero RD cutoff/units, отрицательным treatment contrast и иными confounder coefficients. Case names и seeds меняются вместе с substantive design, expected values вычисляются независимым test algebra.
6. Scientific campaigns выполнить **однократно на метод**: CAU02 160 paired DGP, CAU03 400 fixed-design RBC, CAU04 200 Gaussian linear samples. Раздельные accepted/failed denominators, predeclared bands, no seed/tolerance tuning. Не суммировать их как независимые доказательства одной универсальной coverage. Новый conventional variance profile требует своей bounded variance/coverage qualification; старый RBC pilot не аттестует его автоматически.

**C. Model/query and fit capability (SCM/FIT).**

1. Real selected Linux3.12 fit worker обучает linear ANM на source-bound aligned rows; parent3.14 сохраняет selected spec1.2 и manifest. Fresh query/twin consumer использует exact selected spec, а не caller copy. Native_hybrid polynomial и temporal adapters — separate positive profiles.
2. Проверить три разных laws: Gaussian partial evidence с analytic posterior factor; finite correlated roots с conditional row selector; fully observed nonlinear/polynomial residual. SharedU marginals и contrast/ITE проверять совместно. Не считать совпадение marginal means доказательством joint law.
3. Hard-do replaces mechanism; natural/shift requires it; truncated and clipped laws distinguish boundary atoms. Changing factual evidence changes conditional posterior, changing irrelevant missing root does not refuse; joint-root nonancestor evidence does matter.
4. Adversarial: coefficient/source-row tamper, wrong active root closure, covariance collapse1e−14, independent-arm noises, dropped row multiplicity, graph raw-endpoint bypass, arbitrary covariance jitter, misleading no-override comparator. Fresh reader performs current source checks, не просто checksum producer output.
5. Actual refit uses frozen whole-row index plan and worker per replica. Independent small linear analytic target verifies **каждую** replica and quantile endpoints, then optional n400/800 shrink campaign stays diagnostic. Same samples need not shrink monotonically for arbitrary datasets; это не новый global invariant.
6. FIT branch проходит actual StudyNode/LocalWorkerPool budgets1/2, all folds/repeats, queue/failure release, immutable fit reuse, current-view update, full causal report+CAS. Continuous fold-Y perturbation проверяет отсутствие leakage; binary pilot120 remains independent bounded campaign.
7. Transfer — новые labels, asymmetric joint-root probabilities/multiplicities, shifted factual units, и другая polynomial degree в declared profile; ожидаемые moments/targets получены до запуска. Zero-code growth оценивается по diff: новые compatible resources, а не скрытое helper-кодирование fixture.

**Cost policy.** Один heavy native job за раз на исходном local profile; actual server capacity может задать другую очередь. Предварительный admission считает nodes×horizon, n×features, n×cells, replicas и expected memory. Gaussian factor reuse/serial-inner экономят работу без урезания scientific repetitions. При превышении бюджета вернуть bounded partial/proposal или явную границу, а не незаметно уменьшить B, число folds или support. Counterfactual predictive Monte Carlo и refit estimator interval имеют разные denominators/costs.

## 4. LANE-11: полезная диагностика без ложной authority

**Claim lane:** explanation faithfully represents declared model/game within its measured scope; monitoring выводит applicable current readiness из actual source/policy; legal comparison доставляет правильные структурные изменения и qualitative topics. Эти три ветви не обязаны превращаться в один причинный engine. Whole lane success требует настоящего positive consumer хотя бы на каждом заявленном профиле, не только отказов forged bundles.

### Улучшенный bounded I11 acceptance

**I11-A explanation.** Real ScalarModel+background→effective explanation algorithm→bundle writer→fresh strict selected reader→Phase5/display. Малый nonlinear two-player game из BER section имеет exact expected values. Три aliases одного effective method делают один actual computation; изменение background/model/input обязано инвалидировать reuse. Contribution multiset и requested IDs сохраняются. Adversarial bundle меняет numeric type/schema/version/nested field, numerical contribution или background identity. Неверные attributions не должны проходить только потому, что сумма совпала: проверять обе phi и game values. Для bounded faithfulness использовать distinct held-out perturbation source; producer не должен объявлять split='heldout' по одному label. Alias-only agreement остаётся N/A/limited. Transfer: второй interaction function и correlated background; не требовать causal SHAP claim из predictive model.

**I11-B monitoring/readiness.**

1. Existing synthetic100-window quantile/Wilson fixture остаётся дешёвым deterministic smoke, с windows100 и explicit no-empirical-stationarity claim.
2. Отдельный producer acceptance: source artifact+observation/time coordinates→calibration selection→separately selected holdout→method provenance→report→audit→current validity→monitor→registry persist→fresh rebind+gate. Если owner не найден, это exact unresolved source qualification, не fake finite token.
3. External MBB producer допустим: он может приготовить streams вне calibrate helper, если реальный source/index lineage связан с report. Нельзя требовать bootstrap внутри helper лишь ради названия метода. Raw empirical quantile имеет собственное truthful label.
4. Boundary: CLI один stream не переиспользует training в holdout. Разные trusted coordinates с одинаковыми значениями допустимы; те же source observations под новыми labels не независимы. Неполный/недоступный источник не трактуется observed-empty. Reused windows не увеличивают independent denominator.
5. Typed policy mutation меняет current result/identity; все nested subjects проверяются. Подмена middle shift, quality signal или degradation при неизменном last projection должна обнаружиться. R2 signoff route требует всех other predicates; failed certificate/foreign source/R1/R0 не обходятся signoff.
6. Transfer — иной detector/model version, horizon, observation delay и effect policy с тем же generic source API. Actual stationary scientific validation отдельно: time-ordered no-tuning holdout, явно сформулированная independence/dependence модель windows, block length choice вне holdout, detection-delay/ARL estimand и censoring. Нельзя выдумать production sample size/power без доступного источника. Первый qualifying run фиксирует этот finite design до результатов.
7. Cost: synthetic smoke не тяжелая recalibration; real bootstrap/retraining только после source/policy admission и отдельно измеренной capacity. Защитные monitoring outputs остаются доступны при unqualified FP certificate; никаких внешних deployment actions этим review не разрешено.

**I11-C legal comparison.** Two genuine typed norm packs→actual legal passes→structural diff with typed paths/multiplicity/severity→selected1.1 manifest/CAS→fresh JSON+MD+CLI. Independent fixture заранее перечисляет changed clauses and expected issue multiset. Slash-collision mutant и int/string conflation должны провалиться при unchanged display text; occurrence counts проверяются отдельно. Source/jurisdiction/version substitution не проходит selected reader. Transfer — новый norm vocabulary и иной structural nesting с тем же schema/adapter, без нового case routing. Missing legal pass остаётся not-evaluated; полезные qualitative topics сохраняются с unknown quantitative direction. Quantitative causal question передаётся existing scientific owner с явными missing assumptions, не получает выдуманный coefficient.

## 5. Общие технические решения и что НЕ следует делать

- **Один shared plan для SCM01/02/03**, один numerical owner каждой covariance, один CAU05 whole-report owner; не копировать repair в wrappers.
- **Не заменять custom semantics названием библиотеки.** NetworkX DAG не ADMG ID; EconML DML не TMLE; TreeSHAP не generic callable; SALib variance sensitivity не hidden-confounding evidence. [SALib workflow](https://salib.readthedocs.io/en/latest/user_guide/basics.html).
- **Не переезжать на JAX ради небольших NumPy solves.** Здесь нет measured GPU/autodiff bottleneck; precision/backend migration добавит qualification. Parent имеет JAX0.8.2, но это не причина смешивать RNG/dtype semantics с текущими worker profiles. Если появится JAX path, x64 и logical RNG law должны стать explicit profile, не предположение.
- **Не создавать «универсальный validator» для научной истинности.** Typed syntax, numerical correctness, measured calibration, source lineage и policy authority имеют разных owners и разные доказательства.
- **Не превращать unknown в тотальный отказ.** Candidate graph, point-only estimate, partial SCM, unqualified threshold и qualitative legal comparison полезны при честной границе. Сильный claim зависим от недостающего evidence, а не весь project.
- **Не выбирать тестовые thresholds после просмотра результатов.** Fixed seed полезен для reproducibility, но transfer должен менять substantive structure. Calibration/tuning/holdout lineage является частью входа; hash лишь фиксирует выбранный источник, не оправдывает его выбор.

## 6. Итоговая приёмочная позиция

**Нет оснований для полного redesign ни одного из 17 пакетов.** Четыре предметные поправки обязательны для соответствующих scientific/producer claims, два усиления квалификации ограничены и не мешают независимому локальному ремонту. Большинство решений должны остаться, включая scope refusals, если рядом сохранён содержательный positive path.

Следующая версия ТЗ должна быть проверена на сохранение old REQ/TEST/source/preservation mappings, а затем исполнена в действительно выбранных native profiles. Этот документ не сообщает о выполненном ремонте, empirically validated policy, разрешённой публикации или production readiness. `NOT_RUN` остаётся честным статусом всех product checks.
