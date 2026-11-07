# Финальное техническое ревью: Foundry, численные методы и проверяемые способности

**LANE-03, LANE-04, LANE-10 · 32 пакета · 2026-11-01**

## 1. Главное решение

Большая часть предложений технически разумна: правильные существующие владельцы, настоящее вычисление вместо fixture-ответа, useful limited results вместо тотального отказа, повторная проверка сохранённых источников. **Полный redesign этих трёх лейнов не обоснован.** Нужны шесть адресных результатов ревью: одна существенная ошибка порядка вычислений, два расширения численной/воспроизводимой способности, одна библиотечная оптимизация и два усиления training acceptance. Ниже явно различены defect, optimization и hypothesis; одинаковая серьёзность не означает одинаковую доказанность.

1. **FN-CAL-MASK:** маска fit после nonlinear float32 loss не изолирует extreme heldout; исправить до native acceptance.
2. **FN-BKT-RANGE:** finite residual1e308 может иметь representable RMSE/MAE при unavailable SSE; не выбрасывать полезную comparison row только из-за square.
3. **FN-UQS-STDLIB:** exact mean можно проще обслуживать common stdlib-backed helper. Это не ошибка предложенного exact алгоритма.
4. **FN-PLG-ORACLE:** ненулевой gradient/action delta допускает reversed PPO objective; нужен independent directional oracle.
5. **FN-PLG-INACTIVE:** обещанный inactive-padding профиль нуждается в конкретной native проверке; возможный NaN-путь виден в source, но runtime failure здесь не исполнен.
6. **FN-DOE-PCA-RNG:** locked sklearn PCA(auto,None) на600×100, k=5 использует global RNG; full-request seed contract должен охватывать preprocessing.

**Все product tests — NOT_RUN.** Это критическое ревью ТЗ/кода и план квалификации, не акт приёмки реализации. Продукт не импортировался и не запускался; packages не устанавливались, внешние сервисы не менялись. Единственное численное исполнение — маленькие независимые stdlib проверки на host CPython3.12.14, явно не целевой Python3.14/JAX runtime.

## 2. Метод, исходная база и честные пределы

Immutable repository HEAD `20d9009be21097bfbdc38a546a15cc60213b8ace`; delivered ZIP SHA `e08baa70c8acf92f8f2e5afd8ced38c94213355dea07c4b33b14a417aefdebf3`. `P` ниже — `e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications`. Кодовые пути без полного префикса относятся к `e02_repository/policy-engine/src/polisyos/`; пути `tests/...` — к корню product.

Прочитаны полные solutions и tests всех32 MD и соответствующее semantic JSON содержание, включая уникальные supplements; полный список IDs, hashes и ranges — `coverage.json`. Прочитаны три lane summaries, три integration contracts, practical extensibility, общие правила/owners, AGENTS/CONTRIBUTING. Assigned integration mapping и local-only обязательства рассмотрены содержательно. Два архитектурных документа прочитаны полностью (execution topology и causal grounding firewall); остальные18 не объявляются полностью перечитанными. Оригинальные audit/plan/residual документы использованы через source mappings и контекст, не выданы за новый независимый full audit.

Рассмотрены actual root causes и producer→persistence→fresh consumer, не только REQ↔TEST формальная связность. Для каждого пакета ниже указано, какой неверный implementation мог бы пройти слабую проверку. Source ranges и current primary library research перечислены отдельно; latest docs не равны locked runtime.

### Технологическая база и совместимость

Python `>=3.14,<3.15`; JAX/jaxlib0.8.2, Equinox0.13.2, Optax0.2.6, NumPy2.3.5, SciPy1.16.3, SALib1.5.2, sklearn1.8.0, statsmodels0.14.6, NetworkX3.6.1, arch8.0.0, ArviZ1.0.0, NumPyro0.20.1, pymoo0.6.1.6, CVXPY1.8.2, OR-Tools9.15.6755, Hypothesis6.151.2, Pydantic2.12.5 найдены в actual lock. Это **не** утверждение, что все являются base/direct runtime dependencies: sklearn относится к ml, SALib к sensitivity, arch к analytics; NetworkX не заявлен direct product runtime dependency. Использовать transitive lock presence как разрешение нового обязательного импорта нельзя. JAX/Equinox/Optax уже естественны для имеющихся differentiated owners.

Node22/pnpm10.33.2 присутствуют в actual frontend baseline, но не решают рассматриваемые численные проблемы. Native wheels, ABI и accelerator availability не проверялись; новая зависимость не предлагается как автоматически совместимая с Python3.14.

### Что означают вердикты

* `retain`: сохранить решение; перечисленные discriminating controls остаются частью обязательной приёмки, не вывод о PASS.
* `targeted revision`: адресно уточнить solution/requirement/test, не переписывать всю архитектуру.
* `bounded qualification`: решение перспективно и согласованно, но positive capability требует actual интеграционного доказательства в объявленном профиле.
* `redesign`: ни для одного из32 пакетов не требуется на найденных основаниях.

**Покрытие:** 32 пакета, 158 REQ, 151 TEST; вердикты {'retain': 23, 'bounded qualification': 3, 'targeted revision': 6}. Это census рассмотренных контрактов, не count успешных tests.

## 3. Адресные findings и точные изменения ТЗ

### FN-CAL-MASK — high · CAL-02

**Трассировка:** REQ-CAL-02-02, REQ-CAL-02-04, REQ-CAL-02-06, TEST-CAL-02-02, TEST-CAL-02-03, TEST-CAL-02-06, E02-I10-A.

**Тип доказательства.** verified_specification_defect

**Граница блокирования.** Не принимать CAL-02 split-isolation/native derivative claim и E02-I10-A до исправления порядка операций.

**Неточное положение.** §5: quality*fit_mask в measurement_support/_base_vec_from_traces считается достаточным исключением evaluation observations из training objective.

**Exact evidence:**
* P/02_Пакеты/CAL-02.md §5 и TEST02: mutation10→30 не затрагивает overflow regime.
* src/polisyos/foundry/calibration/loss.py:33–54 и70–85: float32 pointwise nonlinear loss и global finiteness до reduction.
* src/polisyos/foundry/calibration/calibrator.py:2806–2835: pointwise loss предшествует quality reducer.
* src/polisyos/foundry/execute/_internal/numeric/__init__.py:161–165: finite_loss_or_inf проверяет весь array.

**Контрпример.** Фиксировать train10, prediction[10,10], train-only scale10, fit mask[1,0]. Заменить только heldout10 на3e38. Это finite float32, но squared normalized residual≈9e74 не представим вfloat32. Late mask не отменяет inf/global guard; даже умножение inf*0 не0. Вfloat64 данный square представим: dtype существенно указан. Training support/model unchanged, fit обязано остаться finite и неизменным.

**Предпочтительное решение.** Одна effective fit-support closure для scale, base loss, GradNorm, обоих Hessian consumers и final report; inactive operands безопасны до square/Huber. Explicit model-finiteness check не маскируется. Evaluation diagnostics считаются отдельно с собственным range reason.

**Цена и компромиссы.** Небольшой дополнительный masked operand buffer; static shapes сохраняются. Обязательна явная политика nonfinite model vs excluded observations, иначе можно незаметно ослабить существующий guard.

**Предлагаемый replacement requirement.** При неизменных training support, parameters, scale и model outputs изменение только excluded evaluation observations, включая любые разрешённые конечные значения selected dtype, не меняет training primal, gradient, Hessian и optimizer update. Исключение выполняется до nonlinear primitives; nonfinite prediction обрабатывается отдельным прежним admission rule. Unsupported evaluation metric range не отравляет fit.

**Предлагаемый replacement test.** Расширить TEST02/06: actual compiler/splitter→Calibrator, float32 heldout10/3e38 при одинаковых train/model/keys; compare finite loss, gradients, физический Hessian и один native Optax update eager/JIT. Active train mutation остаётся различающим контролем. Полностью masked finite extreme target даёт0/zero derivatives только как contribution отдельной цели при наличии допустимого fit support другой цели; полностью пустой fit corpus остаётся no-fit/refusal, не successful zero-loss. Nonfinite prediction сохраняет declared отказ. Отдельно наблюдать evaluation range limitation. Не подменять forward/AD/optimizer.

**Рассмотренные альтернативы:**
* Existing loss owner: нейтрализовать excluded observed/residual operands до nonlinear primitive; отдельно сохранить nonfinite-prediction admission.
* Gather supported points при устойчивой static-shape policy; может усложнить JIT.
* where над уже computed loss: недостаточная AD гарантия.
* Глобальный x64: не решает support contract и меняет unrelated law.

**Общий владелец.** CAL-02 loss/base-vector owner; interfaces CAL-01/03/04/05, не новый numeric framework.

**Что нельзя сломать:** Не скрыть model NaN при zero quality.; Не изменить priority-after-sample reduction, penalty law, split role.; Не менять float32→float64 молча.

**План validation:** Native selected backend/dtype recorded; compare exact fit partition and frozen weights.; Independent analytic train-only quadratic oracle; old late-mask mutation must fail new test.; Report persistence/fresh consumer distinguishes fit and descriptive diagnostics.

**Неопределённость.** Source-level/specification counterexample confirmed; product/native execution NOT_RUN, exact runtime failure mode inf/NaN/rejection must be observed during implementation.

**Первичные источники:** [JAX-WHERE](https://docs.jax.dev/en/latest/faq.html#gradients-contain-nan-where-using-where), [JAX-DTYPE](https://docs.jax.dev/en/latest/101/default_dtypes.html). Подробные sections/version applicability — §6 и library_decisions.json.

### FN-BKT-RANGE — medium · BKT-02

**Трассировка:** REQ-BKT-02-01, REQ-BKT-02-02, TEST-BKT-02-01, TEST-BKT-02-02, TEST-BKT-02-05, TEST-BKT-02-07, E02-I03-C.

**Тип доказательства.** verified_specification_overrestriction

**Граница блокирования.** Пересмотреть BKT-02 row-admission/numerical-range acceptance; не блокирует прочие honest partial backtest paths.

**Неточное положение.** REQ01/§5 и TEST01 разрешают объявить individual row invalid только потому, что squared residual не представим; TEST01 закрепляет потерю второй useful row1e308.

**Exact evidence:**
* P/02_Пакеты/BKT-02.md:REQ01/02, §5, TEST01/02.
* src/polisyos/scientist/methods/backtesting/evaluator.py:98–104: abs_err**2 до append;139–149: OutcomeComparison хранит absolute_error, не square.
* src/polisyos/scientist/methods/backtesting/orchestrator.py:1378–1435: aggregate sufficient-stat calculations.

**Контрпример.** Одна finite ошибка1e308 имеет MAE=RMSE=1e308. Square/SSE переполняет binary64, но comparison row и обе основные метрики представимы. Для двух одинаковых ошибок ситуация та же. Это не случай max_float−(−max_float), где сам residual непредставим.

**Предпочтительное решение.** Отделить comparison validity от availability конкретной sufficient statistic. Общий numerical policy, независимый fresh row reconciliation; scaled RMS и устойчивое MAE, unavailable SSE с причиной. Не давать full trust там, где обязательная статистика недоступна.

**Цена и компромиссы.** Если persisted schema требует finite mandatory SSE, нужен узкий nullable/status versioning, не замена finite scalar наinf. Scale/ssq pair добавлять лишь при реальной потребности merge; row replay проще.

**Предлагаемый replacement requirement.** Finite representable residual/absolute_error остаётся полезной comparison row независимо от representability residual²/SSE. Все representable MAE/RMSE вычисляются устойчиво. Непредставимые derived statistics имеют отдельную unavailable reason; requested denominator не уменьшается и trust не усиливается. Непредставимый сам residual остаётся адресно invalid.

**Предлагаемый replacement test.** TEST01 сохранить обе rows для [1,1e308] versus[1,0]; single1e308 и pair[1e308,1e308] дают finite RMSE/MAE по analytic oracle, SSE unavailable. Отдельный subtraction overflow остаётся invalid. Actual serialization→fresh IR recomputes rows; техническое sharding сохраняет micro results/counts. Запретить0/inf substitutes и fraudulent eligible.

**Рассмотренные альтернативы:**
* Сохранять valid residual rows и separately unavailable SSE; scaled RMS из rows в existing evaluator/IR.
* Расширить sufficient stats на scale+sum-of-squares при доказанной необходимости incremental merge.
* Invalid entire row по square overflow — безопасно от fake trust, но ненужно сужает полезную способность.
* math.hypot/naive numpy.linalg.norm без scaling/n normalization не универсальны: norm может overflow при representable RMS.

**Общий владелец.** PredictionEvaluator + backtesting aggregate + existing IR row reconciler; shared exact mean FED только если нужен, без Foundry import.

**Что нельзя сломать:** Не смешать scientific unit pooling с numerical range.; Не назвать unavailable SSE нулевой ошибкой.; Не уронить requested denominator и provenance.

**План validation:** Analytic scaling oracle на actually representable floats.; Native owner→CAS/JSON→fresh IR positive/negative controls.; Versioned legacy limited read сохраняется.

**Неопределённость.** Это обоснованное устранение ненужного ограничения ТЗ, не утверждение что все extreme residuals обязаны стать trusted. Producttests NOT_RUN.

**Первичные источники:** [PY-MEAN](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py). Подробные sections/version applicability — §6 и library_decisions.json.

### FN-UQS-STDLIB — medium · UQS-01

**Трассировка:** REQ-UQS-01-02, TEST-UQS-01-02, E02-I10-B.

**Тип доказательства.** optimization_suggestion_not_correctness_defect

**Граница блокирования.** Не release blocker numerical correctness; пересмотреть обязательность самописного exact accumulator до реализации FED/UQS.

**Неточное положение.** §5 предписывает собственный exact integer accumulator для finite binary64 mean, хотя целевой stdlib уже реализует нужный порядок exact sum/division/conversion.

**Exact evidence:**
* P/02_Пакеты/UQS-01.md §5: exact finite mean shared owner FED-01.
* src/polisyos/foundry/uncertainty/aggregator.py:227–389: existing _widest mean/clamp and precision fusion; не предлагается переносить statistical fusion semantics в stdlib.
* CPythonv3.14.0 statistics.mean146–165/_sum1322–1373: exact ratios grouped by denominator, Fraction total divided byn before float conversion.

**Контрпример.** Проблема не ошибочность собственного exact algorithm. Это лишняя duplicate arithmetic surface: statistics.mean([max_float,max_float]) должен вернуть max_float там, где fsum затем /n может overflow. Cancellation с subnormal midpoint требует exact oracle. Host3.12 stdlib arithmetic было проверено отдельно; это не native3.14 acceptance.

**Предпочтительное решение.** Поведенческий requirement exact finite result оставить; implementation preference — common FED/Core helper поверх statistics.mean под pinned CPython3.14 qualification. Foundry и Fabric используют одного owner, не импортируют друг друга.

**Цена и компромиссы.** CPython implementation detail version-bound; performance exact rational reduction нужно измерить на bounded production summary lengths. Если иной Python runtime входит в scope — квалифицировать либо сохранять explicit fallback.

**Предлагаемый replacement requirement.** Общий finite-binary64 mean/midpoint сохраняет точный арифметический смысл и final rounding без intermediate overflow для representable result. Допускается квалифицированная stdlib statistics.mean; собственный accumulator не обязателен. Empty/nonfinite admission явно сохранён.

**Предлагаемый replacement test.** Native CPython3.14: max/max, opposite extremes+cancellation, subnormal midpoint, signed zero policy, permutation and repeated-concatenation metamorphisms (do not average rounded subgroup means) against separately constructed Fraction oracle plus Decimal.from_float precision1200 cross-check on bounded fixtures; no expected value computed by same helper; Fraction backend overlap with stdlib mean explicitly disclosed. Bounded length/time/memory measurement separate from numerical proof.

**Рассмотренные альтернативы:**
* Thin finite-validated common statistics.mean wrapper + mean((a,b)) midpoint.
* Оставить собственный exact integer accumulator после доказанной причины performance/contract.
* fmean/fsum/n либо statistics.median для even midpoint: неэквивалентные extreme guarantees.

**Общий владелец.** FED-01 common finite numeric helper, coordinated with Fabric reviewer; UQS owner owns summary law only.

**Что нельзя сломать:** Не подменить mean median/hull clamp.; Не переносить Python Fraction helper в JIT traced path.; Не изменить joint draw corpus и source independence requirements.

**План validation:** Freeze helper profile/version and finite boundary.; Run native exact-oracle matrix and existing summary persisted reconciliation.; Compare cost with custom accumulator only if measured sizes justify it.

**Неопределённость.** Optimization recommendation backed by pinned source; target runtime NOT_RUN. Existing proposed custom exact algorithm may be fully correct.

**Первичные источники:** [PY-MEAN](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py). Подробные sections/version applicability — §6 и library_decisions.json.

### FN-PLG-ORACLE — medium · PLG-03

**Трассировка:** REQ-PLG-03-02, REQ-PLG-03-04, TEST-PLG-03-02, E02-I04-C.

**Тип доказательства.** verified_acceptance_gap

**Граница блокирования.** Перед claim genuine PPO learning дополнить PLG-03 native update witness независимой loss/gradient semantics проверкой.

**Неточное положение.** Finite nonzero raw gradient + actual Optax + parameter/action delta относительно no-update считается достаточным oracle корректного PPO update.

**Exact evidence:**
* P/02_Пакеты/PLG-03.md REQ02/TEST02 требуют effect, но не направление/correct clipped objective.
* src/polisyos/foundry/agent_sim/rl.py:106–168: actual clipped-min policy loss имеет правильный вид; defect текущего знака НЕ заявляется.
* src/polisyos/foundry/agent_sim/jit_training.py:409–453: actual update route.
* src/polisyos/foundry/plugins/training_adapter.py:686–813: native effect/publication witness.

**Контрпример.** Заменить policy_loss на его отрицание, сохранить настоящие jax.grad/Optax и telemetry. Получится ненулевой finite gradient, parameter delta, next-action effect и same-seed replay; текущий эффект-only oracle допускает обучение в обратную сторону.

**Предпочтительное решение.** Проверять policy/value/entropy components отдельно, clip branches для обоих signs advantage и pre-Optax gradient direction. Old policy/advantages/returns являются fixed targets по chosen training contract. Затем original Optax и fresh policy artifact.

**Цена и компромиссы.** Небольшая unit matrix не доказывает RL convergence; сохраняется отдельная empirical evaluation. Native tiny update остаётся обязательным, analytic fixture не заменяет collector/executor.

**Предлагаемый replacement requirement.** Genuine PPO update должен соответствовать объявленному clipped surrogate, value/entropy weights и GAE termination/bootstrap convention. Nonzero action effect необходим, но недостаточен; independent analytic oracle обязан различать reversed sign, unclipped objective и incorrect target differentiation.

**Предлагаемый replacement test.** Добавить raw advantages[+1,−1], independent normalization включая declared epsilon, epsilon_clip=.2. Для ratios[1.3,.7] policy loss≈−.2 и clipped derivatives0 в открытых окрестностях; ratios[.9,1.1] loss≈.1 и derivatives по log ratios[−.45,+.55] с normalization factor. Проверить opposite bad-side clipping separately, isolate value/entropy coefficients, generic GAE tiny trajectory with terminal/bootstrap. Native profile terminal refusal сохраняется; original1–2updates и no-update control остаются.

**Рассмотренные альтернативы:**
* Добавить small independent analytic PPO/GAE oracle при сохранении native end-to-end update.
* Требовать welfare improvement после1–2updates — неверное scientific обещание.
* Подключить готовый RL framework — лишняя migration, не заменяет adapter law evidence.

**Общий владелец.** Existing agent_sim.rl numeric loss and training_adapter collector/Optax boundary; no duplicate RL framework.

**Что нельзя сломать:** Не потребовать монотонного welfare gain от stochastic PPO.; Не сравнить physical action gradient с unrelated network coordinate.; Не расширить HARD training без likelihood contract.

**План validation:** Analytic scalar computation independently from product helper, controlled inputs not precomputed product output.; Mutation test sign flip and clip removal must fail.; Native JAX/Equinox/Optax update and source-bound fresh load still required.

**Неопределённость.** Пропуск acceptance проверен; actual current PPO sign correct by source. Nativeexecution NOT_RUN.

**Первичные источники:** [PPO](https://arxiv.org/pdf/1707.06347), [OPTAX](https://optax.readthedocs.io/en/latest/getting_started.html). Подробные sections/version applicability — §6 и library_decisions.json.

### FN-PLG-INACTIVE — medium · PLG-03

**Трассировка:** REQ-PLG-03-02, TEST-PLG-03-02, E02-I04-C.

**Тип доказательства.** source_derived_runtime_hypothesis_and_test_gap

**Граница блокирования.** Квалификация обещанного inactive-padding native profile; не объявлять confirmed runtime bug до native witness.

**Неточное положение.** Общее “inactive padding allowed” в TEST02 без конкретного nonfinite inactive end-to-end witness может быть удовлетворено profile assessment/Gini тестом при unsafe native loss path.

**Exact evidence:**
* tests/unit/remediation/test_plg_03.py:973–997,1193–1219: inactive bad values проверяются через assessment/Gini, не данный actual optimizer trajectory.
* src/polisyos/foundry/plugins/training_adapter.py:566–578: inactive income copied.
* src/polisyos/foundry/agent_sim/temporal.py:42–51: unmasked observation features.
* src/polisyos/foundry/agent_sim/actor_critic.py:185–209: neural forward of row.
* src/polisyos/foundry/agent_sim/rl.py:139–155: multiplications by mask after advantage/nonlinear computations; source-derived NaN*0 concern.

**Контрпример.** Одинаковая shape/active index/key assignment, активные агенты полностью valid; изменить только income неактивной padding row finite→NaN. Profile допускает padding, но raw NaN может пройти в actor/GAE и mask multiplication отравить whole gradient. Shape не менять: это исключает легитимную смену PRNG draw arrangement.

**Предпочтительное решение.** Сначала native paired witness. Если подтвердится, нейтрализовать только вычислительный inactive view, не stored state; active guard и промежуточный terminal check сохранить. Same-shape same-key pair должен иметь одинаковую active behavior/update по declared tolerance.

**Цена и компромиссы.** Не обещать append-padding exact RNG invariance без per-agent key semantics. Inactive rows могут нести исторические данные, их нельзя destructive rewrite. Дополнительная masking matrix мала, но safety нужна доAD.

**Предлагаемый replacement requirement.** Разрешённый inactive padding не влияет на активную native training objective/gradient/update через payload, включая declared допустимые nonfinite inactive fields. Stored payload не переписывается. Active negative/nonfinite values и intermediate terminal violations по-прежнему отклоняются до update/publication.

**Предлагаемый replacement test.** TEST02: paired actual training runs с одинаковой shape, active indices, supplied seed, initial actor/optimizer; только inactive income finite/NaN различается. Реальные collector→executor→GAE→PPO→Optax1–2updates, finite metrics and same active action/update under predeclared tolerance. Active-row NaN — отказ; final recovery не скрывает intermediate failure. Observer only delegates original update.

**Рассмотренные альтернативы:**
* Sanitize/neutralize inactive computational observation/reward/target operands before nonlinear operations within native adapter/rl owner.
* Supported fixed active gather with explicit scattering/key contract.
* Reject any nonfinite stored row — сужает обещанный профиль и не является выполнением inactive support.

**Общий владелец.** training_adapter native projection + temporal observation + rl masks; coordinate PLG-03 only, no process-wide sanitization.

**Что нельзя сломать:** Не скрыть active model violations.; Не mutate persisted inactive state.; Не сравнить разные PRNG shape layouts как одно и то же испытание.

**План validation:** First demonstrate/native-refute source-derived path on locked stack.; If safe by another existing boundary, document exact source and retain discriminating acceptance; do not force redundant patch.; Fresh artifact same active inference with exact selected ref.

**Неопределённость.** Runtime hypothesis, NOT_RUN. Source path supports concern but no native failure claimed; finding primarily strengthens acceptance for already promised scope.

**Первичные источники:** [JAX-WHERE](https://docs.jax.dev/en/latest/faq.html#gradients-contain-nan-where-using-where). Подробные sections/version applicability — §6 и library_decisions.json.

### FN-DOE-PCA-RNG — medium · DOE-02, DOE-03

**Трассировка:** REQ-DOE-02-02, REQ-DOE-03-03, TEST-DOE-02-02, TEST-DOE-03-03, E02-I10-C.

**Тип доказательства.** verified_source_level_pipeline_omission

**Граница блокирования.** Не принимать DOE-02 full-request RNG isolation для multioutput и E02-I10-C до PCA-stage qualification.

**Неточное положение.** Full stage RNG contract охватывает sampler/analyzer/model/UQ, но solution/test fixtures не привязывают stochastic PCA stage; tiny3×5/6×5 matrices не активируют randomized solver.

**Exact evidence:**
* P/02_Пакеты/DOE-02.md REQ02/TEST02; DOE-03 TEST03.
* src/polisyos/scientist/methods/doe/multi_output.py:175–215, особенно190: PCA(n_components=n_components), default auto/random_state=None.
* Pinned sklearn1.8.0 _pca.py:479–491 auto threshold;661,682–693 randomized seed path.
* Pinned sklearn1.8.0 utils/validation.py:1324–1351: check_random_state(None) returns global NumPy singleton.
* tests/unit/remediation/test_doe_03.py:178–245: only small deterministic auto branches.

**Контрпример.** Supported two-parameter Morris200 trajectories с num_levels=8 для обеих axes дают600 rows;100 output columns, max_components5. Вlocked1.8.0:600<10*100, maxdim>500,5<.8*100 => randomized solver. None seed consumes ambient NumPy state; output can depend on unrelated request/global seed. Matrix с rank существенно больше oversampling избегает тривиальной exact-low-rank masking проблемы. Even if outputs happen close, external-state mutation already violates contract.

**Предпочтительное решение.** Один existing MultiOutputAnalyzer owns PCA profile/seed, domain-separated from sampling/analysis/model/UQ streams; сохранять resolved solver, backend version и derived seed в current source record. Preserve centered rank/subspace caveats.

**Цена и компромиссы.** Новый metadata field/profile version может требовать compatibility handling. Large randomized arithmetic stays approximate; tolerances/residual bounds не bitwise crossbackend promise. Input600×100 float64≈480KB, workspace отдельно.

**Предлагаемый replacement requirement.** Full-request reproducibility включает preprocessing/PCA. Каждый stochastic stage получает explicit local derived stream; ни один stage не читает/сбрасывает ambient NumPy RNG. Producer record содержит actual PCA backend/version/resolved solver/seed/profile; replay/new replica следуют declared identity.

**Предлагаемый replacement test.** Добавить bounded actual sklearn1.8.0 600×100, k=5 case: two-parameter Morris200 trajectories, num_levels=8 обеих axes; fixed deterministic compatible model output matrix с separated spectrum и проверенным centered rank>15. Не предполагать rank>15 для default4-level двухмерного deterministic grid (там максимум16unique points). Выполнить full PCA→Morris indices для A/B вAB/BA, replay и new replica; external NumPy state unchanged. Не monkeypatch PCA/randomized_svd. Независимый projector/reconstruction residual/reference SVD oracle с tolerance; eigenvector signs и tied partial eigenspaces не сравнивать. Save→fresh read checks actual solver/seed provenance. Small existing fixtures retained.

**Рассмотренные альтернативы:**
* Explicit full solver bounded small + randomized solver with independently derived local stage seed large.
* Always full SVD — deterministic but unnecessary large-data cost.
* Keep auto but always explicit random_state and persist resolved solver — acceptable if profile records threshold/backend version.
* Separate distributed PCA engine — unjustified.

**Общий владелец.** DOE-02 stream/profile owner + DOE-03 MultiOutputAnalyzer; one shared metadata/seed mechanism, not duplicated sampler RNG.

**Что нельзя сломать:** Не менять source matrix labels или silently force full SVD on large workloads.; Не требовать identical eigenvectors in tied spectra.; Не снимать seeded FAST pending по факту исправления PCA.

**План validation:** Locked native backend trace/metadata confirms solver choice.; Run external RNG state invariant even where PCA numeric output accidentally stable.; Two shapes around profile threshold and whole pipeline readback; cost recorded.

**Неопределённость.** Source-level control flow and ambient RNG dependence confirmed from pinned library. Actual numerical divergence/native timing not executed (NOT_RUN).

**Первичные источники:** [SK-PCA](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/decomposition/_pca.py), [SK-RNG](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/utils/validation.py). Подробные sections/version applicability — §6 и library_decisions.json.

## 4. Содержательный вердикт по каждому пакету

### LANE-03

#### EMP-01 — `retain`

**Итог:** Решение действительно устраняет unit-dependent admission и scope leakage; это не ещё один формат evidence.

**Алгоритм и contract fit.** Убрать rounding как numeric admission, проверять derived width до persistence, историческую width interpretation версионировать. Важнее второго знака после запятой — actual query entity/time/unit/regime и selected graph, а не region-only label. Current row grouping country/period недостаточен для promised measurement scope.

**Existing stack против альтернатив.** LIB-11: использовать существующий ObservationRecord/value_outer_set и owner query; новая causal inference библиотека не исправит неверно выбранные rows.

**Стоимость/совместимость.** Filter/pagination должны применяться до cap. Нельзя получить20001 строк чужой scope, отфильтровать и объявить свои данные отсутствующими. Unit normalization не должна менять raw source bytes/checksum.

**Достоверность проверки.** Полезны unit-rescaling и overflow controls, selected-graph counterexample. Wrong implementation: достоверно подписать metadata нового scope, но читать старый region-only query. Нужны соседние entities с одинаковым временем, другие units/regime и проверка exact source IDs fresh reader; changing identifier without numeric changes alone недостаточно.

**Capability/free-grow.** Positive scope-compatible данные дают useful outer set; неподдержанный режим — адресное limitation. Второй entity/единица через контракт, без branch по testID; это ограниченная наблюдательная опора, не causal permission.

**Source:** `core/contracts/value_outer_set.py:49–82,237–289,342–391`; `runtime/quality/generation_cycle.py:5999–6076,16154–16410,16538–16635,16970–17055`; `ir/observation/contracts.py:131–209`.

#### FRC-01 — `retain`

**Итог:** Counters и roles нужно исправлять от producer facts, а не заново интерпретировать badge.

**Алгоритм и contract fit.** 95/100 может быть passed по producer threshold,10/10 — failed по другой обязательной проверке. Нельзя свести status к numerator==denominator. Шесть source-defined roles и optional reference должны сохраняться от actual diagnostic; unknown не становится measured только из-за числа.

**Existing stack против альтернатив.** LIB-11: existing forecast bridge/continuous diagnostic; не новый forecast framework ради counters.

**Стоимость/совместимость.** Нормализация один раз на boundary. Historical aliases — конечный census/retirement, не вечное угадывание dict shapes; отсутствие optional ref не повод fabricated timestamps.

**Достоверность проверки.** Правильны разнонаправленные95/100 pass и10/10 fail, missing-ref и zero-denominator cases. Wrong implementation: hardcode один percent rule, оставаясь numeric-correct. Test должен сравнивать actual upstream diagnostic reason/threshold/role и downstream receipt, не ожидаемый label test fixture.

**Capability/free-grow.** Пропускает новый producer того же output contract без endpoint-specific logic. Корректный receipt ещё не доказывает forecasting skill; это основание следующего FRC-02.

**Source:** `calibration/forecast_bridge.py:1347–1478,1852–1859`; `calibration/diagnostics/continuous.py:25–100`; `runtime/quality/design_axes/outcome_prediction.py:590–649`.

#### PCL-01 — `retain`

**Итог:** Один typed output contract до merge/telemetry — разумнее нескольких consumer эвристик.

**Алгоритм и contract fit.** Backend dispatch сейчас получает broad output; следовательно output kind должен быть установлен owner-ом до receipt construction. Scalar/vector/structured роли не следует угадывать по первым ключам JSON. Compatibility aliases нормализуются один раз, не по всем consumers.

**Existing stack против альтернатив.** LIB-11: current contracts/dispatch owner; не добавлять IR→Foundry import или вторую normalization registry.

**Стоимость/совместимость.** O(payload) normalization и bounded alias census, без копирования больших trace arrays ради label. Legacy data readable с truthful limited role, не silent upgrade.

**Достоверность проверки.** Wrong implementation: receipt правильный, telemetry всё ещё считает serialized vector одним scalar success. Проверять actual returned payload, merged receipts и emitted telemetry для нескольких contracts; invalid output отказывает до positive publication. Exact numeric fixture alone не ловит semantic role.

**Capability/free-grow.** Новый backend того же typed output protocol подключается без case-name fork; новый output semantic kind требует общего contract extension, что не нарушает free-grow.

**Source:** `foundry/methods/backends/dispatch.py:274–415`.

#### FRC-02 — `bounded qualification`

**Итог:** Решение адресует реальную predictive calibration capability, но её нельзя закрыть только source-role/counter repairs.

**Алгоритм и contract fit.** Нужен actual observed prediction→outcome relation N4, новый observation record и source-bound model update, не copying same forecast into a new envelope. Existing predictive_calibration прямо оставляет relation not established; это конкретный gap, а не повод весь путь считать реализованным.

**Existing stack против альтернатив.** LIB-11: existing registered forecast/ETS owner, observation contracts и diagnostic bridge; замена forecast library до установления task/evaluation basis не обоснована.

**Стоимость/совместимость.** Маленький bounded train/holdout horizon, два source updates и exact artifact refs. History/replay отдельно; не перезапускать бесконтрольно ради нужного positive status.

**Достоверность проверки.** Wrong implementation: новый ref с прежними cached values выдаётся как recomputation. Добавить mutation actual observation и negative stale-source replay, current profile fingerprint, train cutoff controls; второй materially different series через тот же registry. Actual predictive error оценивается отдельно от relation presence.

**Capability/free-grow.** Useful scoped forecast+diagnostic+receipt должен пройти fresh consumer. Synthetic linear/seasonal fixture квалифицирует plumbing/model profile, но не population transport, real policy usefulness или permission.

**Source:** `scientist/methods/backtesting/forecast_owner.py:647–810`; `runtime/http/services/predictive_calibration.py:595–630,961–980`; `runtime/quality/generation_cycle.py:17173–17217`.

#### BKT-01 — `retain`

**Итог:** Существенное улучшение: as-of correctness всей feature basis и реальные replicate coordinates вместо scalar convenience.

**Алгоритм и contract fit.** Future target masking недостаточно, если derived feature рассчитана по full series. Cutoff применяется ко всем dependency features до model fit. Реальные n=1/n=7 replicas должны иметь declared coordinates и aggregate mean, не повторение готового single result. Current orchestrator содержит scalar/cohort fallback, который tests обязаны пересечь.

**Existing stack против альтернатив.** LIB-04/11: existing prefix mask/forecast registry; sklearn CV abstraction не знает domain as-of availability и не является drop-in.

**Стоимость/совместимость.** Bound folds×replicas×horizon заранее; реальные costs не source-count proxy. Derived feature prefix recomputation дороже naive mask, но необходима semantic correctness.

**Достоверность проверки.** Wrong implementation: правильно скрывает target, сохраняет full-series moving average. Holdout value perturbation и independently recomputed prefix feature oracle должны оставить train result неизменным. Negative scalar fallback must fail n7 coordinate test; не принимать fake replica supplier.

**Capability/free-grow.** Вторая series/feature law через registry подтверждает transfer; supported partial cohorts useful with counts. As-of simulation не равна реальному out-of-sample skill.

**Source:** `scientist/methods/backtesting/masking.py:1–161`; `scientist/methods/backtesting/orchestrator.py:661–780,925–1024`.

#### BKT-02 — `targeted revision`

**Итог:** Основной план правилен, но extreme square policy лишает полезных representable comparisons — FN-BKT-RANGE.

**Алгоритм и contract fit.** Различение requested/comparable/invalid cells, CI availability/conditional hits и micro/macro — сильная часть ТЗ. Reconciliation из actual rows важнее stored badge. Уточнить, что unavailable SSE не делает representable residual row invalid и не запрещает scaled RMSE.

**Existing stack против альтернатив.** LIB-01/04: общий finite mean если нужен, scaled RMS в existing evaluator; не generic WeightedScorer rewrite и не arbitrary precision всего pipeline.

**Стоимость/совместимость.** Row reconciliationO(n); signed/absolute units нельзя pooling без quantity contract. Legacy finite rows полезны без automatic trust. Version optional unavailable statistic вместо JSONinf.

**Достоверность проверки.** Новые controls FN-BKT-RANGE дополняют strong technical-sharding invariance и forged-summary tests. Wrong implementation: arithmetic mean per-scenario RMSE выглядит корректным на одинаковых n; unequal shard sizes/known residuals различают. Старые lambda_state stale envelopes не возвращать.

**Capability/free-grow.** Useful exact/partial point forecasts должны доходить до fresh decision packet с limitation, а always-refuse не проходит positive path. Exact fit не empirical coverage.

**Source:** `scientist/methods/backtesting/evaluator.py:1–209`; `scientist/methods/backtesting/orchestrator.py:1366–1435`; `tests/unit/remediation/test_bkt_02.py:331–398`.

Адресные изменения: FN-BKT-RANGE.

#### BKT-03 — `retain`

**Итог:** Общий signed-statistic helper и honest unknown p-value лучше локального знакового patch.

**Алгоритм и contract fit.** Bias — signed mean, не absolute error; near-zero/constant controls должны отделять finite arithmetic от разрешённости t inference. Native SciPy или explicit unavailable; отсутствие/degeneracy не p=0. Absolute variance floor требует unit/domain justification, а не magic default.

**Existing stack против альтернатив.** LIB-04: SciPy ttest_1samp уже доступен в appropriate extra; не писать собственную tCDF. Несколько forecast horizons зависимы, поэтому arithmetic t-stat qualification не снимает independence/multiple-comparison limitations.

**Стоимость/совместимость.** Linear pass plus SciPy call; exact finite mean может shared FED. Optional-backend missing path не ломает useful descriptive bias.

**Достоверность проверки.** Wrong implementation: abs(mean) проходит positive fixture и теряет direction. Negative symmetric/negative nearzero/constant cases и independent sample variance formula нужны. Контроль optional import failure даёт unknown, не significance. Fresh summary сохраняет n/units/method.

**Capability/free-grow.** Второй scale/unit с преобразованием всего residual basis проверяет отсутствие hidden fixture floor. Результат limited, если sampling assumptions не установлены; не blanket invalid всех rows.

**Source:** `scientist/methods/backtesting/orchestrator.py:1542–1725`.

#### BKT-04 — `retain`

**Итог:** Bounded lazy folds и generic statistic bootstrap — достаточное расширение existing API, не нужен новый experiment engine.

**Алгоритм и contract fit.** Не менять activation default скрытно. Выбор subsets до их materialization, callback inputs изолированы, statistic identifier связан с реальным callable. “Bootstrap RMSE” не может всегда возвращать mean только с другим label.

**Existing stack против альтернатив.** LIB-04: SciPy bootstrap полезен лишь при совпадающем percentile/paired/RNG profile; BCa default не silent replacement. arch block bootstrap — отдельный dependence law, не обязательный scope patch.

**Стоимость/совместимость.** Ограничение folds и B×n до вычисления; batching ограничивает memory. Copies нужны на callback boundary, не всего Cartesian universe. Seed локальный и disclosed.

**Достоверность проверки.** Wrong implementation: enumerate huge combinations then slice passes small fixture; sentinel iterator/large combinatorial input проверяет bounded consumption. Callback mutation не влияет на later folds/original source. Non-mean statistic oracle и deterministic percentile controls различают fake genericity.

**Capability/free-grow.** Новый statistic через callable contract, не named branches. Dependent time-series intervals не называются iid calibrated только потому, что bootstrap code запускается.

**Source:** `scientist/methods/backtesting/cv.py:1–160`; `scientist/methods/backtesting/bootstrap.py:90–246`.

### LANE-04

#### FRY-01 — `retain`

**Итог:** Derived registry view, stable RNG law и separate mechanism-family certificates — правильное разделение owner-ов.

**Алгоритм и contract fit.** Runtime view выводится из MethodRegistry, не новый authority catalog. Treasury legacy PRNG root behavior сохраняется; если нужен новый law, он versioned. IC/IR/budget mathematical properties относятся к family assumptions, не к наличию Python callable.

**Existing stack против альтернатив.** LIB-11: existing JAX keys/runtime_registry/families; никакой general mechanism-design engine для четырёх семей не нужен.

**Стоимость/совместимость.** View rebuild/cache invalidation по registry generation; bounded metadata enumeration. Не повторять deep mutable registry copies per execution.

**Достоверность проверки.** Wrong implementation: copied constant registry passes four known names, misses new registration. Register novel compatible method после initial read и проверить updated derived view/fresh compile. Family certificate oracle отдельно от catalog flags; aliases retirement finite and explicit.

**Capability/free-grow.** Новая compatible family member проходит как data/registration; fundamentally new economic property требует нового доказательства/semantics, а не automatic certificate.

**Source:** `foundry/methods/catalog/mechanism/runtime_registry.py:1–337`; `foundry/methods/catalog/mechanism/families.py:1–98`; `foundry/compile/randomization.py:1–61`.

#### FRY-03 — `retain`

**Итог:** Tax-base и precision law нужно сохранить при relocation; proposed distinction действительно предотвращает незаметную смену модели.

**Алгоритм и contract fit.** Native fiscal law использует reported income как base, меняет income/government; plugin wealth-tax law другой. Сходные имена не оправдывают объединение. Conservation проверяется на declared active population и taxbase, а не просто total changed.

**Existing stack против альтернатив.** LIB-11/02: current JAX fiscal primitives; x64 migration не часть mechanical relocation. Нет причины переносить их в сторонний finance package.

**Стоимость/совместимость.** Linear per-agent arrays, dtype explicit. Aliases сохраняют exact historical route; hidden casts могут изменить rounding/model.

**Достоверность проверки.** Wrong implementation: tax actual income вместо reported, проходит fixture где они равны. Нужны deliberately different reported/actual/wealth, inactive rows, zeros и cross-precision policy. Независимый ledger oracle по каждому changed field, не только sum.

**Capability/free-grow.** Произвольные valid rates/populations того же law проходят без fixture branch. Новая налоговая база требует named new law, что честнее fake universal mechanism.

**Source:** `foundry/execute/mechanisms/fiscal.py:1–149`; `foundry/plugins/economics/mechanisms.py:12–78`.

#### ECO-01 — `retain`

**Итог:** Две economic semantics и clock должны оставаться различимыми; normalized budget loss — не policy welfare objective.

**Алгоритм и contract fit.** Нельзя “исправить” normalized-income−1 только потому, что value отрицателен. Это named baseline с positive scaling invariance; его перенос не повод заменить полноценной utility function. Income-tax vs wealth-tax, tax/transfer order и time boundary явно квалифицируются.

**Existing stack против альтернатив.** LIB-11: current domain mechanisms/baselines, не новый agent framework.

**Стоимость/совместимость.** Linear agent updates; dtype и clock versioned. Existing compatibility alias не должен менять state law.

**Достоверность проверки.** Wrong implementation: один generic taxation function используется в обоих owners и совпадает на специально равных balances. Distinct wealth/income fixture, tax-before-transfer ledger и multiple time steps различают. Scale invariance test не заменяет welfare validation.

**Capability/free-grow.** Useful deterministic economic execution сохраняется. Для новой welfare definition — отдельный named contract/resource и scientific evaluation, не скрытая оптимизация loss ради позитивного score.

**Source:** `foundry/plugins/economics/mechanisms.py:12–78`; `foundry/plugins/economics/baselines.py:1–42`.

#### PLG-01 — `retain`

**Итог:** Локальная factory-product validation внутри per-source exception boundary лучше глобального discovery failure.

**Алгоритм и contract fit.** Ошибка может возникнуть после successful entry-point load: callable возвращает wrong object или metadata property сама throws. Diagnostic generation не должна повторно обращаться к небезопасному object и свалить discovery.

**Existing stack против альтернатив.** LIB-09: stdlib importlib.metadata и current loader достаточны; второй plugin framework повышает compatibility cost без нужной capability.

**Стоимость/совместимость.** Installed-source census конечный, optional imports remain optional. Ограничить side effects loader только существующим declared contract, не добавлять live installation/discovery.

**Достоверность проверки.** Wrong implementation: catch import error, но не factory/validation error; один bad plugin блокирует good sibling. Matrix malformed metadata/wrong type/factory raises plus one genuine valid plugin; реальные entry source identities preserved. Exception text не источник producer authority.

**Capability/free-grow.** Новый совместимый plugin подключается через entrypoint, не список известных имен. Broken one не превращает весь процесс в refusal machine.

**Source:** `foundry/plugins/discovery.py:1–238`.

#### PLG-02 — `retain`

**Итог:** Producer role обязан быть explicit: legacy constructor defaults сейчас действительно могут ложно выглядеть как trained.

**Алгоритм и contract fit.** TrainingResult three positional fields со status default trained — опасная compatibility ambiguity. Не infer PPO по list loss_history/artifact presence. Genuine in-memory training допустим без CAS, legacy evaluation не должен запускать training plot/publication.

**Existing stack против альтернатив.** LIB-09: narrow typed producer predicate/result role, не новый class hierarchy framework.

**Стоимость/совместимость.** Сохранять three-positional legacy calls readable; negative branch должен иметь zero writes/plots. No-artifact genuine positive не отклонять только из-за optional storage.

**Достоверность проверки.** Wrong implementation: require artifact to call trained — always-refuse genuine in-memory; alternatively default status trains legacy. Нужны обе разнонаправленные cases на public API→CLI, не лишь helper boolean test.

**Capability/free-grow.** Публичный смысл результата переносится вместе с source-defined role, а не угадывается downstream. Это полезная extensibility без подмены старого поведения.

**Source:** `foundry/plugins/api.py:395–418`; `foundry/plugins/training_adapter.py:686–813`.

#### PLG-03 — `targeted revision`

**Итог:** Positive native update/persisted policy нужен и хорошо задан; добавить independent PPO semantics и конкретный inactive-padding witness.

**Алгоритм и contract fit.** HARD collector sampling против mean execution — настоящая law mismatch. Временный адресный HARD-train refusal корректен только вместе с работающим fluid/relaxed native path и release note о narrowing. Не вечный запрет: future shared action/likelihood contract может расширить профиль.

**Existing stack против альтернатив.** LIB-02: JAX/Equinox/Optax already optimal fit; сторонний PPO framework не устраняет adapter law. FN-PLG-ORACLE/FN-PLG-INACTIVE дополняют, не заменяют actual native run.

**Стоимость/совместимость.** 1–2updates, tiny one-domain population; gradients/Hessians не требуются в масштабе neural net. Обязательны precise seed, reset/continue и previous-state preservation.

**Достоверность проверки.** Action delta alone допускает sign-flipped objective. Inactive NaN acceptance нуждается в paired same-shape actual collector→Optax, а не только assess/Gini. Tamper/missing weights/profile mismatch fresh strict loader и zero-store eval остаются обязательными.

**Capability/free-grow.** Узкая capability — реально обучить и восстановить policy, влияющую на action. Ни welfare gain, ни causal improvement из этого не следуют. Второй valid population/seed должен проходить без profile-ID hardcode.

**Source:** `foundry/agent_sim/rl.py:1–168`; `foundry/agent_sim/jit_training.py:243–333,409–453`; `foundry/agent_sim/temporal_mechanisms.py:1–127`; `foundry/plugins/training_adapter.py:550–601,686–813`.

Адресные изменения: FN-PLG-ORACLE, FN-PLG-INACTIVE.

#### CMP-01 — `bounded qualification`

**Итог:** Persisted recipe→fresh reconstructed effective chain — реальная capability, которую in-memory DAG tests не доказывают.

**Алгоритм и contract fit.** Authored node identity/parameter overrides и requires-only dependencies должны пережить persistence. Current composer добавляет requirement edges, compiler строит chain и dynamic payload отдельно; каждый этап должен использовать один frozen recipe basis.

**Existing stack против альтернатив.** LIB-03/05: current composer/compiler/registry; новый workflow engine не нужен. General graph library не владеет scoped parameter/default semantics.

**Стоимость/совместимость.** BuildO(nodes+edges) для DAG validation; actual compile cost separate. Static vs dynamic args отражаются в cache key без inappropriate recompilation.

**Достоверность проверки.** Wrong implementation: сохраняет original descriptor, а выполняет in-memory patched graph; fresh reader теряет requires-only edge или per-occurrence override. Тест40/60/120 должен заново получить recipe, registry и compiler в clean owner view; explicit consumer runtime values, не только graph ordering.

**Capability/free-grow.** Новый compatible authored chain через data contract, без ручного Python composition. Две разные dependency topologies/overrides подтверждают transfer; arbitrary code execution не обещается.

**Source:** `foundry/methods/components/composer.py:618–794`; `foundry/methods/compiler/__init__.py:847–918,1055–1111`.

#### CMP-02 — `retain`

**Итог:** Strict duplicate semantics и explicit merge лучше silent UUID-based ordering.

**Алгоритм и contract fit.** Duplicate outputs нельзя молча sum/overwrite; registered merge создаёт intended60, WARN остаётся limited с20/10, не притворяется merged semantics. Requires dependency относится к любой подходящей более ранней occurrence, не только непосредственно предыдущей.

**Existing stack против альтернатив.** LIB-05: существующий graph/merge owner, external DAG scheduler не заменяет domain conflict law.

**Стоимость/совместимость.** Conflict indexing linear-ish по slots вместо repeated allpairs где можно; stable occurrence identity сохраняется при persistence. No hidden UUID tie meaning.

**Достоверность проверки.** Wrong implementation: проверяет лишь соседнюю occurrence или last-writer wins, проходит линейную simple chain. Разнести requirement supplier и consumer дополнительной compatible node; reorder duplicate writers и явно отличить strict/WARN/merge outcomes. Test actual values, not just absence of exception.

**Capability/free-grow.** Сложные compatible recipes добавляются данными; неоднозначные compositions честно требуют explicit merge resource, не silent business choice.

**Source:** `foundry/methods/components/composer.py:618–794`; `foundry/methods/components/linker.py:317–450`.

#### CMP-03 — `retain`

**Итог:** Global max-cardinality then lexicographic preference — правильная цель; implementation choice не надо превращать в dogma.

**Алгоритм и contract fit.** Локальный augmenting path matching может обеспечить cardinality, но не заявленный total preference. Пять компонент и deterministic tie-break должны сравниваться глобально. Замена алгоритма обоснована; embedded stale source-name diagnostic отдельно сохраняет адресность.

**Existing stack против альтернатив.** LIB-05: NetworkX exact integer matching реальный вариант, но lock не direct dependency. Existing bounded exact owner тоже допустим. SciPy float assignment требует доказательства mixed-radix range; heavy solver не нужен.

**Стоимость/совместимость.** Нужен polynomial production solver, не exhaustive permutations. Exhaustive7293×3 None/A/B label cases (3^6) — малый independent test oracle, не все произвольные binary edge graphs; дополнительно bounded larger cost case.

**Достоверность проверки.** Wrong implementation: greedily берёт самый хороший edge и теряет лучшую сумму/кардинальность. Exhaustive oracle плюс weight/tie permutations и actual1020 composed execution различают. Не вычислять expected matching тем же production helper; graph-level успех не доказывает domain compatibility predicates.

**Capability/free-grow.** Новые slots и candidates через metadata получают matching без case-specific priorities. Сама matching preference не научное доказательство причинной совместимости.

**Source:** `foundry/methods/components/linker.py:317–450,603–693`.

#### JIT-01 — `retain`

**Итог:** Узкая get→claim race/default binding/shape-preparation правка у правильного owner; не надо заменять всё cache subsystem.

**Алгоритм и contract fit.** После leadership claim нужен повторный cache check и обязательное завершение flight даже при early hit. Immutable per-handle defaults отделить от shared compiled kernel. Shape preparation не должна делать huge np.empty или исполнять pure step для inference.

**Existing stack против альтернатив.** LIB-03: jax.jit/persistent cache дополняют, но не решают cancellation/generation/defaults. Latest JAX APIs нельзя blindly переносить в0.8.2.

**Стоимость/совместимость.** Разделить Python wrapper construction, tracing/XLA compile, host shape preparation, device execution. Actual .block_until_ready, cold/warm/transfer measurements, matched dtype; без fabricated speedups.

**Достоверность проверки.** Existing native test139–172 проверяет20/30, но сам по себе не счёт compile. Packet уже требует различить эти claims — сохранить. Race gate must target exact post-get/pre-claim window, failures/cancel/invalidation release all waiters, no double publication.

**Capability/free-grow.** Новый shape/dtype/static argument получает новую valid kernel, dynamic default — правильный handle без stale capture. Это system capability reusable execution, не benchmark-only optimization.

**Source:** `foundry/methods/compiler/__init__.py:580–758,945–1019`; `tests/unit/remediation/test_jit_01.py:139–259`.

#### RES-04 — `retain`

**Итог:** Commit-state distinction чинит повреждение данных после publication; storage replacement избыточен.

**Алгоритм и contract fit.** os.replace успешен, затем directory fsync падает: опубликованный JSON может уже ссылаться на sidecars. Общий except cleanup не должен удалять их как будто commit не состоялся. Publication и durability outcomes разные; history namespace/typed request restore не смешиваются с active state.

**Existing stack против альтернатив.** LIB-10: current atomic file owner+stdlib. SQLite/new store только при отдельной потребности transaction model, не ради этого race.

**Стоимость/совместимость.** Same-filesystem temp и platform support фиксируются. Нет честного универсального обещания power-loss durability без filesystem qualification; best-effort unsupported sync не false success.

**Достоверность проверки.** Wrong implementation: test только pre-rename write failure, post-rename cleanup остаётся destructive. Failure injection на каждом commit phase, затем fresh reader actual published path; предыдущий checkpoint/history и unrelated files остаются. Typed restore не unrestricted deserialization.

**Capability/free-grow.** Возобновление compatible run из real persisted state, а не in-memory copy. Новый request profile требует supported restore schema, unknown не должен исполняться.

**Source:** `foundry/methods/backends/checkpointing.py:189–244,1062–1095`.

#### CAL-05 — `retain`

**Итог:** Scalar lazy execution и explicit mapped refusal лучше eager where, если qualification включает реальные effects иAD.

**Алгоритм и contract fit.** Во время JAX tracing обе ветки могут быть traced; это не значит обе исполняются. Scalar cond поддерживает нужный schedule; batched predicate может стать select, поэтому refusal/policy для mapped case честен. Neutral patch должен соответствовать каждому actual emitted field, не generic guessed zero.

**Existing stack против альтернатив.** LIB-02: existing lax.cond/custom batching boundary; не universal scheduler layer. Backend semantics проверять locked0.8.2.

**Стоимость/совместимость.** Не считать tracing callbacks runtime side effects. Для cost/perf дождаться effects/device completion; bounded actual emission census прежде generic patch.

**Достоверность проверки.** Wrong implementation: считает Python calls during tracing и доказывает false laziness, либо zero result скрывает executed effect. Runtime counters/emitted resources, inactive model poison control и actual grad/Hessian должны различать; supported active sibling работает.

**Capability/free-grow.** Новая compatible schedule через data/contract; new emission kind требует explicit neutral semantics. Ограниченный scalar profile не выдаётся за universal vectorized lazy engine.

**Source:** `foundry/calibration/pure_executor.py:537–743`.

### LANE-10

#### CAL-02 — `targeted revision`

**Итог:** Shared objective architecture сильная; late-mask arithmetic должна быть исправлена прежде native acceptance.

**Алгоритм и contract fit.** Frozen train-only scale, exact shape checks, one base-vector для fit/GradNorm/Hessians/final report — правильный root-cause fix. Но multiply fit mask после pointwise loss не исключает extreme holdout, FN-CAL-MASK. Preserve explicit nonfinite model rule отдельно от eligible observations.

**Existing stack против альтернатив.** LIB-02: JAX current owner, scaled finite reduction вместо global x64 toggle. Mean/std scale oracle вычислять по actually representable float32 inputs в более точном reference.

**Стоимость/совместимость.** Linear observation reduction; dense Hessian только bounded parameter profile. Один shared closure снижает duplication, но не повторять fullforward ради каждого report field без actual dependency need.

**Достоверность проверки.** Quadratic fixture с physical vs optimizer-u gradients и penalties хорошо различает semantic mistakes, не подгонка. Дополнить extreme heldout3e38 и actual native derivatives/update; ordinary10→30 недостаточно. Не заменять actual compiler/ConstraintRegistry/forward готовым lossvector.

**Capability/free-grow.** Новый compatible target и placeholder dates не меняют старую training support; evaluation-only observations не проникают в fit. Реальная calibration capability остаётся model/measurement-scoped, не causal validity.

**Source:** `foundry/calibration/calibrator.py:716–762,2380–2668,2749–2960,2977–3046`; `foundry/calibration/loss.py:1–156`.

Адресные изменения: FN-CAL-MASK.

#### CAL-03 — `retain`

**Итог:** Единый finite admission selection и различение raw/repaired Hessian устраняют логическую неоднозначность, не просто формат.

**Алгоритм и contract fit.** Single-start должен пройти ту же selection policy, не обходить её через config branch. Finite ill-conditioned candidate может оставаться useful limited; repaired condition нельзя выдавать за raw evidence. OTel test должен видеть actual emitted attributes, не fake tracer dictionary.

**Existing stack против альтернатив.** LIB-02: existing selector/Hessian owner, не новый optimizer. FD fallback может дать limited estimate, не равен native Hessian confirmation.

**Стоимость/совместимость.** Dense HessianO(p²) memory; multistart attempts bounded. Не вычислять raw Hessian заново многократно ради badge, но selected state identity сохранить.

**Достоверность проверки.** Wrong implementation: all finite candidates accept, regardless infeasible/ill-conditioned roles; либо all badcondition refuse, уничтожая useful limited. Матрица single/multi, finite/nonfinite, raw/repaired, actual telemetry различает. Source inspection не заменяет native optional backend.

**Capability/free-grow.** Новый parameter vector того же model/profile проходит declared admission; uncertainty scope остаётся honestly limited. Не путать optimizer success с scientific adequacy.

**Source:** `foundry/calibration/multi_start.py:1–171`; `foundry/calibration/hessian.py:1–173`; `foundry/calibration/calibrator.py:3240–3305,3450–3610`; `tests/unit/remediation/test_cal_03.py:1–211`.

#### CAL-04 — `retain`

**Итог:** Exact evaluated-state binding — необходимая и достаточно узкая правка optimizer/report mismatch.

**Алгоритм и contract fit.** Нельзя reuse objective только по численному равенству loss: разные parameters/weights/support могут иметь одно значение. Last optimizer update должен реально оцениваться до выбора/report; old auxiliary data от предыдущего state не переносится. Candidate selection identity включает actual objective basis.

**Existing stack против альтернатив.** LIB-02: existing JAX/Optax loop, без нового optimizer/state tracker framework.

**Стоимость/совместимость.** Одно дополнительное finalforward оправдано, если новый state ещё не evaluated; если exact state/objective already evaluated, reuse допустим. Не blanket двойной forward every step.

**Достоверность проверки.** Wrong implementation: caches by loss scalar и возвращает stale gradients/Hessian. Test равных loss в разных points, final update vs last preupdate и changed weights/support. Existing tests содержат monkeypatch/jit=False routes: packet правильно требует actual native final state witness, его не убирать.

**Capability/free-grow.** Корректный persisted parameter/report pair пригоден fresh UQ consumer. На новом compatible objective reuse остаётся по identity, не fixture coincidence.

**Source:** `foundry/calibration/calibrator.py:3047–3240,3300–3455`; `tests/unit/remediation/test_cal_04.py:1–468`.

#### CAL-06 — `retain`

**Итог:** Scoped covariance block вместо all-or-nothing projection реально расширяет полезную capability без выдуманной certainty.

**Алгоритм и contract fit.** Известные uncertain A/B и point-only C должны сохранять свои роли. JΣJᵀ зависит от именованного parameter basis и correlation; tiedA=B не independent marginals. Legacy complete projection читается по versioned contract, unknown missing block не zero variance.

**Existing stack против альтернатив.** LIB-02: existing JAX derivative/covariance owner. NumPyro/ArviZ уже вlock не повод заменять локальный Gaussian/delta contract probabilistic programming framework.

**Стоимость/совместимость.** CovarianceO(p²), projectionO(mp²) для dense case; projected subset может уменьшить cost. PSD singular допускается, fake jitter нельзя молча менять law.

**Достоверность проверки.** Wrong implementation: fills omitted C with covariance0 и получает ложную точность; либо rejects whole report из-за C. A=B test через actual joint source, row/column reorder, unknown block mutation и fresh CAS propagation различают. JSON equality alone не доказывает uncertainty propagation.

**Capability/free-grow.** Новый compatible named parameter subset работает через contract без special-case names; limits переносятся downstream. Partial uncertainty не scientific fullcoverage.

**Source:** `foundry/calibration/report.py:230–376`; `foundry/calibration/calibrator.py:3450–3610`; `foundry/uncertainty/covariance.py:105–228`; `tests/unit/remediation/test_cal_06.py:1–143`.

#### UQS-01 — `targeted revision`

**Итог:** Statistical law/source semantics сильны; arithmetic implementation лучше упростить общей stdlib-backed boundary.

**Алгоритм и contract fit.** Caller-only decomposition не повышает authority primary result. Duplicated selected view не independent information; precision fusion требует одного estimand и justified independence/dependence. Mean вне equal-tail interval возможен, clamp меняет estimand. Raw joint draw corpus сохраняется.

**Existing stack против альтернатив.** LIB-01: FN-UQS-STDLIB, thin shared FED helper предпочтительнее mandatory custom exact accumulator. Это optimization, не дефект корректного exact algorithm; fusion decision остаётся domain-owned.

**Стоимость/совместимость.** Exact mean на bounded scalar lists, не traced arrays. Dedup/source-unit identity до fusion; нельзя дешевизну conservative hull выдавать за отсутствующий producer→consumer capability.

**Достоверность проверки.** Wrong implementation: каждый duplicate source уменьшает variance, raw rows переставляются independently peraxis, либо meanclamp выглядит “inside CI”. Duplicate/permutation/skewed mean-outside-interval controls и actual source-bound fresh read различают. Positive posterior propagation обязателен, не только отказ от fusion.

**Capability/free-grow.** Новые source-compatible views агрегируются без caseID; unknown dependence остаётся useful conservative result, не fake independent precision. Source-bound propagation gap не закрыть mere summary.

**Source:** `foundry/uncertainty/aggregator.py:227–389`; `foundry/uncertainty/covariance.py:105–228`.

Адресные изменения: FN-UQS-STDLIB.

#### UQP-01 — `retain`

**Итог:** Nominal point и delta derivative должны использовать полный invocation contract, а не отдельную упрощённую функцию.

**Алгоритм и contract fit.** Frozen constants/defaults и dtype coercion влияют на derivative; model2x должен дать point20, variance4 при declared source. Parameter nominal vector не весь callable contract. Derived source response basis нельзя подменять result scalar без parameters/axes.

**Existing stack против альтернатив.** LIB-02: existing JAX jacfwd/delta dispatcher; finite differences лишь qualified fallback. Не process-wide x64 mutation внутри helper.

**Стоимость/совместимость.** JacobianO(outputs×parameters) storage и forward/autodiff cost; tiny test не unlimited dense derivative guarantee. Static inputs frozen, mutable caller data не alias.

**Достоверность проверки.** Wrong implementation: differentiate f(theta) без constants/defaults, потом attach correct nominal label. Nonlinear/affine second fixture с nondefault constants, caller mutation after binding и named axis reorder различают. Compare actual forward and analytic derivative, not same helper for expected.

**Capability/free-grow.** Новый compatible model invocation проходит existing adapter, no special linear dispatch. Delta — local approximation, не global uncertainty truth или validated coverage.

**Source:** `foundry/uncertainty/delta.py:1–160`; `foundry/uncertainty/dispatcher.py:120–260`.

#### UQP-02 — `retain`

**Итог:** Point mass, empirical marginal и correlated joint law разделены правильно; это не excessive refusal.

**Алгоритм и contract fit.** Zero std означает deterministic point, не sigma1e-12. Empirical draws нельзя превращать в Gaussian с clipping; bounded law не clipped unbounded law. Singular covariance valid на lower-dimensional support. Collapsed finite CDF interval и positive but rare1e-12 probability — разные случаи.

**Existing stack против альтернатив.** LIB-08: existing SciPy/JAX transforms and named draw corpus; new arbitrary-precision sampler не обязателен. Unsupported numerical tail имеет reason, не silent law substitution.

**Стоимость/совместимость.** Bound rejection/attempts и full-row joint sampling; не независимая сортировка каждой marginal. Point-mass axes дешевле не sampling. Dtype profile обязателен.

**Достоверность проверки.** Wrong implementation: jitter singular covariance или independently resample a,b и получает plausible marginals, но a−b≠0. Exact joint constraint, empirical support, point mass and tail controls различают. Наблюдение нуля rare events не доказательство нулевой вероятности.

**Capability/free-grow.** Добавление compatible empirical/degenerate source через typed law без special fixture. Honest unsupported tails не уничтожают остальные valid outputs и не называются total capability.

**Source:** `foundry/uncertainty/monte_carlo.py:788–796,2572–2682`; `foundry/uncertainty/covariance.py:105–228`.

#### UQP-03 — `retain`

**Итог:** Разделение interval-width heuristic и MCSE, logical checkpoints и conditional failure measure предотвращает ложную точность.

**Алгоритм и contract fit.** Ширина outcome interval не standard error estimator. Переименование честнее подмены более сложным MCSE без модели. Stopping checkpoint100 не должен зависеть от batch50/60 при budget240; failed draws меняют observed conditional law и denominator, не превращаются вzero outputs.

**Existing stack против альтернатив.** LIB-08: retain bounded owner, proper MCSE как отдельное future profile. QMC не автоматическая замена iid/heuristic.

**Стоимость/совместимость.** Attempts budget отдельно successful outputs; retries bounded and same-input, cost source exact. Batch controls memory only, not statistical stopping identity.

**Достоверность проверки.** Wrong implementation: check stop only endbatch; для50 и60 разное sample count/result, smallbudget hides issue. checkpoint schedule independent ofbatch и conditional mean50/99 controls нужны. Retry2 uses same input not new random draw, otherwise scientific selection changes.

**Capability/free-grow.** Новые compatible distributions сохраняют declared measure и exact attempt accounting. Useful conditional result отдаётся limited; heuristic convergence не заявляется calibrated accuracy.

**Source:** `foundry/uncertainty/monte_carlo.py:1978–2004`.

#### DOE-01 — `retain`

**Итог:** Bounded lazy design consumption и честный adaptive cost более важны, чем генерация большого числа trial labels.

**Алгоритм и contract fit.** itertools.islice prefix ограничивает materialization, но grid prefix не uniform coverage. Constant axes canonicalized; adaptive uses actual previous result, no hidden rerun. Unknown cost нельзя считатьzero и оптимизировать budget по нему.

**Existing stack против альтернатив.** LIB-08: existing iterator/design owner; SciPy Sobol может стать отдельным declared design, не способ переименовать biased grid prefix.

**Стоимость/совместимость.** 12dimensions×3values дают531441grid points; first10 consumption bounded. Plan maxruns/attempts проверяется до costly execution, output artifacts current owner.

**Достоверность проверки.** Wrong implementation: list(product(...))[:10] проходит smallfixture и взрывает memory; sentinel iterator/counters различают. Adaptive spy на actual source attempt count и changed previous result ловит stale cached decision. Unknown-cost branch must stay useful limited or bounded by explicit cap, не fictional savings.

**Capability/free-grow.** Новый dimensionality/constant axis через plancontract без кода. First10grid не считается global sensitivity coverage; declared downstream usefulness отдельна.

**Source:** `scientist/methods/doe/sampling.py:1–109`; `scientist/methods/doe/adaptive.py:85–247`.

#### DOE-02 — `targeted revision`

**Итог:** Typed laws/source-matrix binding и local streams правильны; дописать stochastic preprocessing/PCA stage.

**Алгоритм и contract fit.** Canonical SALib problem один для sampling/analysis, physical bounds и declared distribution. Current-plan hash не доказывает происхождение already generated samples. Native source record должен связывать actual matrix/axes/backend/seed/replica. FN-DOE-PCA-RNG закрывает omitted stage.

**Existing stack против альтернатив.** LIB-06/07: SALib1.5.2 оставить; seeded FAST pending подтверждён именно analyzer global RNG, boundedLOGNORMAL не заменять unbounded. SciPy PPF reference — adapter comparison, не независимая реализация quantile.

**Стоимость/совместимость.** Local seeds по stage, profile version-bound; input copy если backend mutates. Bounded runs; only one PCA seed owner shared03. Нет blanket backend upgrade.

**Достоверность проверки.** AB/BA whole pipeline, external RNG state unchanged и original uniform design+normal plan swap хорошие controls. Добавить large-shape actual PCA path и analytic uniform/triangular/CDF profile checks. Small sampler-only repeat легко проходит с stochastic unseeded downstream.

**Capability/free-grow.** Новые compatible typed laws/replicas возможны данными; неподдержанный law адресно pending. Receipt не переносится на другую backendversion безqualification.

**Source:** `scientist/methods/doe/designs.py:1–401`; `scientist/methods/doe/sampling.py:1–109`; `scientist/methods/doe/analysis.py:1–290`; `scientist/methods/doe/multi_output.py:175–215`; `tests/unit/remediation/test_doe_02.py:1–367`.

Адресные изменения: FN-DOE-PCA-RNG.

#### DOE-03 — `targeted revision`

**Итог:** Failure/block/rank/units решения содержательно верны; tests добавить stochastic solver branch совместноDOE02.

**Алгоритм и contract fit.** Imputation не ordinary calibrated CI; whole Morris trajectories нельзя склеить из surviving rows. Centeredrank≤n−1 до solver selection; unmet variance threshold — useful limited, не scientific sufficiency. Normalized effect20 для y2x on[0,10] сохраняется при смене x units.

**Existing stack против альтернатив.** LIB-06/07: actual sklearn/NumPy/SALib reuse, not new PCA. Small analytical fullprojector oracle сильный; tied rank1 cap rightly avoids forced same vector. FN-DOE-PCA-RNG о другом shape/profile boundary.

**Стоимость/совместимость.** Failure filtering precedes PCA и retains original denominator. Dense output matrix budget, randomized solver explicit. Component count/variance threshold не достаточность empirical sensitivity.

**Достоверность проверки.** Wrong implementation: impute then drops failedcount, constructs plausible CI; or reorders retained trajectory rows. Persist original/retained IDs and source geometry, actual uncertainty owner verifies. Existing small3×5/6×5 tests do not exercise ambient RNG; new600×100 needed.

**Capability/free-grow.** Partial-output exploratory point useful with limitations; complete positive path still genuine. Novel outputbasis units through same pipeline, no hardcoded eigenvector/sign.

**Source:** `scientist/methods/doe/analysis.py:197–290`; `scientist/methods/doe/multi_output.py:40–239`; `tests/unit/remediation/test_doe_03.py:178–245`.

Адресные изменения: FN-DOE-PCA-RNG.

#### STR-01 — `bounded qualification`

**Итог:** Независимый objective intent и полная denominator accounting обязательны; scorer self-validation недостаточна для stress capability.

**Алгоритм и contract fit.** Utility/cost directions должны задаваться source objective один раз, а не вычисляться из удобного already-signed score. Topk/dedup не меняет original inspected set valid+invalid+unavailable. Finite sampled stress corpus не population risk estimate.

**Existing stack против альтернатив.** LIB-11: existing objective/scorer/report owner; новая multiobjective optimization framework не решает provenance/intent.

**Стоимость/совместимость.** Bound evaluated candidates и retained topk отдельно, no hidden full search. Count original attempts/unique scenarios/available outcomes по declared roles; source fresh reader re-evaluates required summary.

**Достоверность проверки.** Wrong implementation: product score используется как собственный oracle и подтверждает reversed cost sign. Hand objective intent fixture, duplicate invalid candidates, alternate ordering, fresh independent scorer и original denominators различают. Для second objective family semantics должны быть declared, не lookup bycaseID.

**Capability/free-grow.** Useful stress ranking для inspected scope; реальные policy resilience/population failure probabilities требуют независимых scenarios/distribution/evaluation, не принятия одного artifact.

**Source:** `scientist/methods/doe/stress_report.py:111–184,636–725`.

## 5. Улучшенный bounded end-to-end план квалификации лейнов

Это будущая приёмка, не исполненный сценарий. Один тяжёлый run может покрывать несколько packets только если manifest перечисляет actual inputs, exact claims и независимые outcomes; local-only matrices не исчезают. Реплика сохранённого JSON без реального producer не является positive end-to-end результатом.

### LANE-03

**Большая способность:** Получить предметно ограниченное empirical/forecast/backtest evidence из реально выбранных наблюдений, сохранить его происхождение и численные ограничения, передать свежему consumer без повышения силы утверждения.

**Оценка существующего плана:** Интеграционные контракты содержательно сильнее набора unit smoke tests: они требуют actual forecast/backtest producer и fresh receipt/decision reader. Однако исправленные counters, exact hashes и positive roundtrip не доказывают predictive skill, N4 update relation или переносимость population. Главный новый численный gap — FN-BKT-RANGE; положительную FRC-02 capability нельзя закрыть только FRC-01/PCL-01 repairs.

**Предпосылки:**
* Scoped ObservationRecord/compiler/query owner; actual entity/time/unit/regime contract, selected graph.
* Current source-bound ForecastOwner/ETS registered backend; реальные training/holdout roles и diagnostic producer.
* Current physical request/workflow/selected SimulationResult/PropagationReport/IR store, не stale lambda_state envelopes.
* Optional SciPy profile explicit; missing backend не positive significance.
* FRC-02 producer relation/N4 update binding must exist or remain named gap; integration runner не фабрикует его.

#### E02-I03-A

**Положительный путь.** Два entity/time/unit scope, реальный selected empirical producer→current ref→summary. Один scope даёт finite useful interval/conditional prediction; point-ID и nonzero width различимы; source limitations сохраняются.

**Adversarial controls.** Соседний entity с теми же датами, другой regime, unit-rescale, overflow derived width; query cap до чужого scope не должен обрезать нужную опору. Stored positive badge при failed source floor не восстанавливает PASS.

**Persisted state → fresh reader.** Записать exact selected rows/query contract/graph/profile в existing owner; новая reader instance без исходного object. Изменение source bytes/units/binding инвалидирует только затронутый claim.

**Независимость oracle.** Независимый перечень source row IDs + analytic unit conversion/width, не та же SQL/helper; equality summary bytes лишь transport evidence.

**Перенос/holdout.** Второй entity и новое metric/units combination поддержанного contract, новые IDs, иные времена/graph topology; no source-file edits.

**Ресурсная граница.** Небольшой synthetic scope fixture + отдельный bounded cap witness; счёт реально прочитанных/отфильтрованных rows, не требование huge dataset.

#### E02-I03-B

**Положительный путь.** Actual ETS train-prefix→holdout predictions→numeric diagnostic→report/receipt→fresh S10. По declared producer thresholds95/100 passed и10/10 failed могут сохраняться; real interval roles и optional selected refs.

**Adversarial controls.** Holdout labels в training не попадают; nominal95% не превращается в observed95 hits; wrongkind/foreign/tampered evidence, fractional counts/future temporal role и no-reference paths. Report-only nominal/rule mutation invalid; genuine new selected rule пересчитывает suitability.

**Persisted state → fresh reader.** Actual report/ref/profile persisted, fresh receipt consumer и S10 inspect exactly bound source. Cross-story E02-X04/FRC-02 отдельно: actual new observed outcome→N4 relation→fresh predictive update, old cached forecast with new ref запрещён.

**Независимость oracle.** Ручной hit/count на фиксированных heldout observations и independent role table; для model path analytical simple series плюс реально computed ETS, не model mock. Accuracy на fixture не population validation.

**Перенос/holdout.** Новая series с другим pattern/horizon в том же registered backend; temporal holdout не используется при tuning. Для empirical claim нужен отдельно замороженный реальный dataset/task.

**Ресурсная граница.** Bound trainlength/horizon/model fits;2small series, по одному actual update. Фиксировать backend/import/version, no live provider.

#### E02-I03-C

**Положительный путь.** Actual prefix feature ref→native n1/n7 forecast replicas→evaluator→micro summary→current persisted decision packet. Partial rows useful с full requested denominator; finite extreme row retained со separate unavailable SSE.

**Adversarial controls.** Future-value mutation, derived moving feature leakage, missing coordinate/selector typo, subtraction overflow, missing interval, constant signed residual, unavailable SciPy, cancelled work, forged aggregate. Unequal technical shards не меняют micro; scientific strata remain separate.

**Persisted state → fresh reader.** Fresh IR recomputes metrics/counts/interval availability from actual source rows and current physical request; invalid stale compute hash/candidate diagnostic не trusted.

**Независимость oracle.** Independent residual list/scaled RMS/signed mean; exact simple point prediction, analytic CI hits; CV/bootstrap expected from отдельно выписанных indices/statistic. Product scorer не oracle самого себя.

**Перенос/holdout.** Второй quantity/units stratum, новые cohort coordinates и иной split arrangement; declare pooling before observation. Callback statistic не только mean.

**Ресурсная граница.** Fold/replica/bootstrap caps before materialization; report expected model-call counts and source IO. Большой combinatorial bound тестировать iterator witness, не запуском exponential work.

**Граница силы вывода:** Repair acceptance подтверждает правильную численную и provenance механику. Scoped capability требует весь positive producer→fresh consumer path и transfer. Forecast skill/coverage/transport требуют independent empirical evaluation; ни один результат не permission или causal certification.

### LANE-04

**Большая способность:** Из авторского typed recipe получить reproducible effective execution, сохранить state/policy и восстановить их новым consumer; limited learning меняет настоящую policy при сохранении экономического и stochastic law.

**Оценка существующего плана:** Хорошо разделены authored graph, runtime registry, compiler cache, checkpoint и training role. Не требуется замена всей платформы. CMP-01 всё ещё нужно подтвердить через persisted fresh reconstruction. PLG-03 positive update witness важен, но без FN-PLG-ORACLE допускает wrong-direction learning; inactive payload safety остаётся native hypothesis. HARD refusal допустим как временный профиль, не окончательное доказательство universal learning.

**Предпосылки:**
* MethodRegistry/runtime views и merge/link compatibility owner; recipe persistence уже существует или его отсутствие адресно признано.
* Actual JAX0.8.2/Equinox0.13.2/Optax0.2.6 backend и declared dtype/device; build tools не подменены doubles.
* Tenant-owned CAS/policy strict loader; no default-view substitution.
* Checkpoint filesystem profile и restricted invocation/schema explicit.
* Existing economic law profiles/clock/RNG/CRRA active-population admission; supported training one-domain only.

#### E02-I04-A

**Положительный путь.** Авторовать recipe с nondefault static/dynamic params, requires-only edge, повторной occurrence и sibling; сохранить, закрыть owner view, fresh reconstruct/compile и actual sequential/async execute. Explicit merge даёт60; expected40/60/120 bindings проверяются по конкретному fixture.

**Adversarial controls.** Cycle и unresolved duplicate producer отклоняются до run; WARN limited сохраняет20/10, не merge. Rename/reorder IDs не меняют meaningful semantics. Global matching cardinality/lex preference проверяется отдельно.

**Persisted state → fresh reader.** Exact recipe/ref/schema и frozen effective graph; fresh registry/compiler не получают in-memory patched objects. Mutating args/recipe generation инвалидирует нужный cached execution.

**Независимость oracle.** Independent hand calculation actual chain outputs + exhaustive tiny matching enumeration, не same solver. DAG topology и actual numeric outcomes оба нужны.

**Перенос/holdout.** Вторая compatible topology с dependency не на ближайшую occurrence, novel slot names и иным dynamic parameter; отсутствие caseID веток inspectable.

**Ресурсная граница.** Small graphs; polynomial solver requirement, bounded larger smoke. Не exponential production matching. Cold/warm compile overhead отдельно.

#### E02-I04-B

**Положительный путь.** Cold/warm handles с разными dynamic defaults дают20/30 по текущему request; exact race window one compile/publication; saved checkpoint restores node outputs/seed/restricted request свежим reader.

**Adversarial controls.** get→claim race, invalidation-before-delivery, leader error, cancelled/deadline follower; все flights завершаются. Failure prewrite/prerename/postrename/dirsync не удаляет referenced committed sidecars/history. Changed params/input не reuse old checkpoint.

**Persisted state → fresh reader.** New cache/compiler/store instance; current namespace и generation, actual published manifest. Политика durability явно не обещает successful powerloss recovery на всехOS.

**Независимость oracle.** Exact output equations плюс event-order assertions/fresh on-disk reader; wrapper counter отдельно от actual XLA compile instrumentation. Platform failure injected at owner boundary, native serialization остаётся.

**Перенос/holdout.** Иной shape/dtype/static arg требует new valid compilation; unchanged dynamic shape не stale bindings. Second checkpoint namespace/history collision control.

**Ресурсная граница.** block_until_ready и effects barrier where relevant; separate preparation/cold/warm/device transfer, actual bytes allocated/written. Small bounded threads/timeouts, no throughput claim по одному sample.

#### E02-I04-C

**Положительный путь.** Actual fiscal/plugin economic laws с distinct reported-income/income/wealth→supported fluid/relaxed collector→1–2 real updates→policy artifact→fresh strict loader→next action. Обычный run и HARD evaluation сохраняются.

**Adversarial controls.** HARD train refuses before work/output при текущем boundedprofile; malformed plugin не блокирует valid sibling. Wrongsign PPO mutation fails analytic oracle. Same-shape inactive NaN pair проверяется native; active bad/intermediate terminal failure stops before optimizer/store, даже если final recovered.

**Persisted state → fresh reader.** Exact selected tenant refs/weights/optimizer metrics/schema1.1 profile; fresh skeleton/store loads action-equivalent policy. Tamper/missing/profile mismatch rejects; legacy1.0 readable без invented metadata; genuine in-memory positive безCAS permitted.

**Независимость oracle.** Independent economic ledger/action-law probability и analytic PPO clip/GAE gradients, original Optax delegation, same-seed no-update control. Next-action difference не welfare gain.

**Перенос/holdout.** Второй valid population/config/seed в том же one-domain profile, fixed active indices/keyassignment для padding metamorphism. Newdomain training не заявляется без нового contract.

**Ресурсная граница.** Tiny actors/population/horizon1–2updates; no full training campaign. Gradient effect threshold заранее, backend/version exact; record actual store writes0/2 по outcome contract.

#### E02-I04-D

**Положительный путь.** Real scalar scheduled mechanism through calibration pure executor, inactive branch produces neutral field-correct patch без runtime forward/emission; active scalar branch produces expected value and derivative.

**Adversarial controls.** Inactive poisonous computation/effect не выполняется; tracing counts не runtime calls. Unsupported mapped predicate gets precise refusal, active supported sibling не запрещается. New emission field без neutral contract не silently zeroed.

**Persisted state → fresh reader.** Schedule/recipe/profile binding сохраняется в calibration invocation/report; fresh consumer не переинтерпретирует scalar evidence как universal vectorized capability.

**Независимость oracle.** Actual runtime emissions/forward counters after effects completion, analytic simple value/gradient/Hessian. Traced Python callcount не oracle laziness.

**Перенос/holdout.** Второе расписание/compatible emission contract через ресурсы, active/inactive transitions в другом timestep; no special known method names.

**Ресурсная граница.** Bound steps/branches; measure no unwanted numerical work, not merely returned zeros. Full backend matrix не обязательна, заявленный supported device обязателен.

**Граница силы вывода:** Compile/restore correctness не доказывает корректность экономической модели. Tiny optimizer proof — настоящая ограниченная learning capability, но не scientific policy improvement. Permission boundary не повышается от successful execution/persisted artifact.

### LANE-10

**Большая способность:** Воспроизводимо подобрать параметры на declared training support, получить source-bound частичную/полную uncertainty правильного estimand и использовать сохранённый design для sensitivity/stress с честными единицами и потерями.

**Оценка существующего плана:** Большинство решений хорошо предпочитают useful limited result абсолютному отказу: partial covariance, failed-start sibling, exploratory imputation point, explicit rare-tail limitation. Два важных пропуска — CAL-02 masking до nonlinear AD и DOE whole pipeline PCA RNG. Нельзя считать small analytic fixtures статистической квалификацией CI/MCSE/causal impact.

**Предпосылки:**
* CAL-01/current ObservationRecord compiler/ConstraintRegistry/bijectors совместимы с shared training base-vector.
* Actual JAX/Optax forward, optional sklearn/SALib/SciPy versions pinned; fallback profiles записаны.
* Current CalibrationReport/PropagationReport source record and tenant/ref ownership, fresh IR consumer.
* Typed joint law/row identity/parameter basis; DOE actual design matrix and retained trajectory provenance.
* Scientific quantity/units/objective directions declared before inspecting result.

#### E02-I10-A

**Положительный путь.** Actual one-agent income_tax parameter r=.5, θ=r−.5, two targets1/9 and constant constraint penalty6. Weights9:1/1:9 yield96/736; physical derivatives−36/−164,H20; optimizer-u derivatives follow actual sigmoid,−9/−41,H1.25. Real one update, final chosen state/report and scoped covariance.

**Adversarial controls.** Heldout10→3e38 infloat32 does not poison fit; active train change does. Shape mismatch/no-effective support/nonfinite prediction guards; lastupdate/stale equal-loss point; one failed start plus useful finite sibling; unknownC covariance not guessedzero.

**Persisted state → fresh reader.** Store actual selected state/report/objective basis/weights/support/scale/parameter names; fresh propagation consumer checks exact selected ref. Changed basis/weights/source invalidates curvature reuse.

**Независимость oracle.** Independent analytic quadratic incl penalty and physical/u coordinate transformation; separate actual-forward finite difference with predeclared step. No mocked forward/gradient/Hessian/Optax. Scoped covariance tiedA=B verified algebraically.

**Перенос/holdout.** Second supported target/state/model parameter name and different split/placeholder axis; same objective owner, no caseID dispatch. Heldout labels never tune optimizer settings.

**Ресурсная граница.** Bound one/two parameters and steps for native acceptance; Hessian memoryO(p²) declared. Microfixture demonstrates semantics, не realdata convergence/general calibration.

#### E02-I10-B

**Положительный путь.** Actual named correlated input law + frozen constant→delta/MC→summary→persisted propagation→fresh consumer. Known linear2x example point20, variance4; singular a=b yields a−b=0. Empirical atoms/joint rows retained; duplicate selectedview не extra precision.

**Adversarial controls.** Zeroσ pointmass, asymmetric mean outsideequal-tailinterval, dependence duplication, absent output, filtered failures conditional mean50/99, retries2sameinput, collapsed CDF vs positive raretail. Same logical100checkpoint acrossbatch50/60budget240. Changed basis no stale curvature.

**Persisted state → fresh reader.** Persist source law/method/version/row IDs/seed/attemptcounts/limitations. Fresh reader recomputes required summary from preserved corpus and verifies exact source/profile; no default-view laundering.

**Независимость oracle.** Analytic affine mean/covariance and exactjointconstraint; independent finite mean/Fraction extremes. For stochastic marginals, predeclared distributional tolerance/multiple-run design if claiming empirical accuracy, not cherry-picked seed.

**Перенос/holdout.** Second affine/nonlinear compatible model, row reorder preserving joint identity, different requested output subset. Nonlinear delta result explicitly approximation; no universal coverage claim.

**Ресурсная граница.** Bound attempts and successful rows separately; batch memory cap and no hidden newdraw retries. Exact summary arithmeticcost measured separately; no arbitrary-precision MC engine required.

#### E02-I10-C

**Положительный путь.** Actual typed source-bound design→bounded model evaluations→sensitivity+stress→artifact→fresh analyzer/scorer. Uniform/normal/triangular law mapping; y=2x effect20 on[0,10] and unit transforms; complete Morris CI path plus exploratory imputed point.

**Adversarial controls.** Uniform source relabelled normal by currentplan rejected; source axes/units/replica/backend tamper. Failed wholeblocks retained/dropped correctly, originaldenominator survives.600×100PCA randomized stage explicit local seed/global state invariant. Reversed costdirection/top-k/dedup cannot improve false score.

**Persisted state → fresh reader.** Actual design matrix/block identities/seed law/backend/PCAprofile and retained outputs persisted in existing source owner. Fresh reader verifies originals, not currentplan fingerprint alone; missingowner remains precisegap.

**Независимость oracle.** Independent analytic effects/scaling, small exact PCA projector and larger reference residual/subspace with separated spectrum; hand objectiveintent not productscore. SciPy PPF is adapterreference only; analytic uniform/triangular or CDFerf controls add independence.

**Перенос/holdout.** Newaxes, reordered compatible outputs, unitrescale and different-law request; AB/BA two whole pipelines and newreplica.6×5tiedrank1case checksratio/status not arbitrary projector equality.

**Ресурсная граница.** Gridprefix max10 of12D×3 withoutmaterialization; bounded adaptivecalls;200two-paramMorris trajectories (num_levels=8)600rows×100outputs≈480KBinput plus reported workspace. Small PCA fixtures retained for cheap regression; one large-shapeprofilequalification, not every unit test.

**Граница силы вывода:** Repair and scoped algorithm qualification не доказательство empirical CI coverage, MCSE, missingness model, sensitivity transport or population stress risk. Эти claims требуют замороженного independent data/model/evaluation protocol; successful saved report не operational permission.

## 6. Библиотечные и технологические решения

Все внешние первичные источники проверены2026-11-01. Рекомендации ниже не означают install/upgrade. Приоритет: existing owner + stdlib/current dependency, затем новая зависимость только при доказанной выгоде.

### LIB-01 — UQS-01, BKT-02

**Решение:** Предпочесть thin common finite-binary64 statistics.mean wrapper; FED owner общий.

**Baseline:** CPython>=3.14<3.15; stdlib без новой зависимости.

**Почему:** Exact arithmetic уже в statistics.mean3.14; fmean/fsum может переполнить сумму, median even pair использует небезопасный midpoint. Собственный корректный accumulator не объявляется дефектным, но увеличивает surface сопровождения. Для scaled RMS mean недостаточен.

**Альтернативы:** Собственный exact integer accumulator; statistics.fmean/math.fsum затем /n; numpy.mean; Decimal/Fraction для production всего массива.

**Цена:** ПроходO(n), exact integer/Fraction arithmetic; оценить цену на реальных bounded summary sizes, не переносить на traced device arrays.

**Qualification:** Native3.14 extremes/cancellation/subnormal/permutation against independently accumulated Fraction oracle and Decimal.from_float precision1200 bounded cross-check; resource envelope; finite validation и empty policy прежние.

**Источники:** [PY-MEAN](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py).

### LIB-02 — CAL-02, CAL-03, CAL-04, CAL-05, CAL-06, UQP-01, PLG-03

**Решение:** Сохранить JAX/Equinox/Optax и текущие owner closures, исправить support semantics до AD.

**Baseline:** jax/jaxlib0.8.2, equinox0.13.2, optax0.2.6; base dependencies.

**Почему:** Ни смена framework, ни dtype не исправляют неверный estimand/support. Existing autodiff даёт единый objective для fit/Hessian. Нейтрализация входов перед nonlinear operation обязательна; scalar cond не обещает lazy vmapped ветки.

**Альтернативы:** SciPy finite differences как основной gradient; Новый PyTorch/RL stack; Глобальное включение x64; where над уже вычисленной invalid loss.

**Цена:** Compile upfront; dense HessianO(p²) storage, repeated forward cost; bounded tiny acceptance, не unlimited matrix obligation.

**Qualification:** Pinned native eager/JIT grad/Hessian, dtype explicit, no-forward mocks; actual updates и selected-state re-evaluation.

**Источники:** [JAX-WHERE](https://docs.jax.dev/en/latest/faq.html#gradients-contain-nan-where-using-where), [JAX-COND](https://docs.jax.dev/en/latest/_autosummary/jax.lax.cond.html), [JAX-DTYPE](https://docs.jax.dev/en/latest/101/default_dtypes.html), [OPTAX](https://optax.readthedocs.io/en/latest/getting_started.html).

### LIB-03 — JIT-01, CMP-01

**Решение:** Owner CompilationCache оставить; JAX compilation cache — только дополнение после измерения.

**Baseline:** Existing Python single-flight/default-binding owner + JAX0.8.2.

**Почему:** JAX не владеет domain defaults, cancellation, generation/invalidation; гонка get→claim должна закрываться в текущем owner. Persistent cache решает другую стоимость и требует trusted storage.

**Альтернативы:** Только jax.jit cache; JAX persistent cache вместо owner; Новая distributed cache/Ray framework.

**Цена:** Не повторять tracing/compile по wrapper count. Раздельно cold compilation, preparation allocation, warm execution и transfer; sync completion.

**Qualification:** Actual backend compile instrumentation + shape/dtype/static arg matrix; gated race, cancellation/errors; no stale publication.

**Источники:** [JAX-JIT](https://docs.jax.dev/en/latest/201/jit.html), [JAX-CACHE](https://docs.jax.dev/en/latest/persistent_compilation_cache.html), [JAX-BENCH](https://docs.jax.dev/en/latest/benchmarking.html).

### LIB-04 — BKT-03, BKT-04

**Решение:** Retain small shared signed-statistic/CV/bootstrap owner; SciPy применять по declared profile, не unconditional rewrite.

**Baseline:** SciPy1.16.3 optional analytics/sensitivity; NumPy2.3.5; existing scipy t-test path.

**Почему:** Native t-test лучше собственного p-value приближения; unavailable scipy не p=0. Generic statistic callback и bounded lazy CV полезнее нового framework. BCa не percentile, time dependence не iid.

**Альтернативы:** scipy.stats.bootstrap defaultBCa; arch block bootstrap; Собственный Student distribution implementation.

**Цена:** BootstrapO(Bn), SciPy batch controls memory; callbacks isolation and cost caps; arch adds model choice not free correctness.

**Qualification:** Signed near-zero/constant/negative fixtures; independent hand statistics; exact seed/profile; dependent forecast intervals separate qualification.

**Источники:** [SCIPY-T](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html), [SCIPY-BOOT](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html), [SCIPY-BOOT-PIN](https://raw.githubusercontent.com/scipy/scipy/v1.16.3/scipy/stats/_resampling.py), [ARCH](https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html).

### LIB-05 — CMP-03

**Решение:** Не требовать новую библиотеку автоматически; existing exact matching owner с независимым exhaustive oracle допустим.

**Baseline:** NetworkX3.6.1 есть lock, но не direct product runtime dependency; SciPy1.16.3 optional.

**Почему:** NetworkX снимает algorithm maintenance после явного dependency admission; exact lexicographic encoding/tie contract всё равно owner. SciPy float64 conversion может потерять low lexicographic digits. Heavy solver неоправдан для текущей задачи.

**Альтернативы:** NetworkX integer max_weight_matching(maxcardinality=True); SciPy linear_sum_assignment with dummies/range proof; Own exact bounded min-cost flow/augmenting paths; OR-Tools/CVXPY framework.

**Цена:** Existing small integer solver or NetworkXO(V³), bitwidth of lexicographic encoding учитывать. Exhaustive3×3 oracle только тестовый, production exponential search нельзя.

**Qualification:** 729 labelled3×3 None/A/B contract cases (3^6), not all binary edge graphs, plus independent weight/tie variants, reorder invariance, actual composed chain; larger bounded cost smoke.

**Источники:** [NX-MATCH](https://raw.githubusercontent.com/networkx/networkx/networkx-3.6.1/networkx/algorithms/matching.py), [SCIPY-ASSIGN](https://raw.githubusercontent.com/scipy/scipy/v1.16.3/scipy/optimize/_lsap.c).

### LIB-06 — DOE-02, DOE-03

**Решение:** Retain SALib1.5.2 typed adapter; поддержанные laws расширять отдельно, не снимать pending по sampler alone.

**Baseline:** SALib1.5.2 sensitivity extra, SciPy1.16.3, NumPy2.3.5.

**Почему:** FAST analyzer ambient RNG подтверждён; bounded LOGNORMAL не unbounded lognorm. SciPy PPF reference shares implementation with SALib, значит проверяет mapping, а independent analytic/CDF controls проверяют смысл.

**Альтернативы:** Uniform fallback; Unbounded lognorm вместо bounded law; Своя библиотека sensitivity analysis.

**Цена:** Canonical problem once per request; preserve input sample record (SALib transforms may mutate arrays/problem), local stage seeds; bounded trajectories.

**Qualification:** Native source matrix/axes/law/profile→fresh analyzer; AB/BA whole pipeline, analytic uniform/triangular and CDF inversion controls, no claim nominal coverage from tiny fixture.

**Источники:** [SALIB-LAWS](https://raw.githubusercontent.com/SALib/SALib/v1.5.2/src/SALib/util/__init__.py), [SALIB-FAST-SAMPLE](https://raw.githubusercontent.com/SALib/SALib/v1.5.2/src/SALib/sample/fast_sampler.py), [SALIB-FAST-ANALYZE](https://raw.githubusercontent.com/SALib/SALib/v1.5.2/src/SALib/analyze/fast.py).

### LIB-07 — DOE-02, DOE-03

**Решение:** Explicit PCA solver/profile и domain-separated local RNG в existing MultiOutputAnalyzer.

**Baseline:** scikit-learn1.8.0 ml extra; NumPy SVD fallback.

**Почему:** Auto переключается на randomized на поддержанных больших shapes; defaultNone использует global RNG. Full small + seeded randomized large сохраняют cost/meaning. Backend/solver должны быть записаны.

**Альтернативы:** PCA(auto,None) оставить; Always full SVD; Новая distributed PCA implementation.

**Цена:** 600×100 float64 input480000bytes; workspace отдельно. FullSVD roughlyO(np*min(n,p)), randomized bounded rank cheaper. Не universal full-SVD.

**Qualification:** Actual600×100 rank cap5 crosses locked auto threshold; AB/BA/global-state guard; independent projector/residual, spectrum separation; persist metadata.

**Источники:** [SK-PCA](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/decomposition/_pca.py), [SK-RNG](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/utils/validation.py).

### LIB-08 — UQP-02, UQP-03, DOE-01

**Решение:** Retain declared sampling laws/checkpoints; no arbitrary QMC upgrade or new probability framework.

**Baseline:** Existing JAX/NumPy/SciPy sampling owners.

**Почему:** Sobol useful only distinct declared design; truncated/bounded law and singular joint rows not replaceable by clipped Gaussian. MCSE is a different estimator; rename heuristic now, qualify MCSE separately if needed.

**Альтернативы:** SciPy Sobol QMC; Normal approximation for empirical law; Arbitrary precision rare-tail sampler; Replace interval-width heuristic by real MCSE.

**Цена:** Bound attempts, success denominator, fixed logical checkpoint schedule independent of batch; no Cartesian grid materialization.

**Qualification:** Point mass, exact joint a−b=0, conditional failures, tail collapse vs rare positive interval; same request repartitioned into batches.

**Источники:** [SCIPY-SOBOL](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html), [JAX-DTYPE](https://docs.jax.dev/en/latest/101/default_dtypes.html).

### LIB-09 — PLG-01, PLG-02

**Решение:** Existing stdlib entry-point loader + typed producer role; no second plugin framework.

**Baseline:** Python3.14 importlib.metadata; existing discovery/error owner.

**Почему:** Factory product validation belongs in per-source exception boundary; public label cannot be inferred from legacy default status. Existing contracts can express this without new registry.

**Альтернативы:** Pluggy-style new registration framework; Infer producer role from object shape; Catch only import errors.

**Цена:** Discovery enumeration bounded by installed entry points; diagnostics safe even malformed plugin metadata; optional imports remain optional.

**Qualification:** One valid plugin beside each broken factory; no producer mutation during read; API/CLI plot/publication branch controls.

**Источники:** [PY-ENTRY](https://docs.python.org/3.14/library/importlib.metadata.html#entry-points).

### LIB-10 — RES-04

**Решение:** Retain existing atomic file owner, split publication and durability outcomes explicitly.

**Baseline:** Python3.14 os.replace/fsync; current checkpoint sidecars.

**Почему:** After replace, deleting referenced sidecars on later fsync error can destroy published checkpoint. Commit-state tracking fixes owner boundary; new storage would multiply migration scope.

**Альтернативы:** SQLite/new transactional storage; Unconditional cleanup after any failure; Universal power-loss guarantee.

**Цена:** JSON+sidecar IO, same-filesystem temp, directory sync platform support; no blanket all-platform acceptance for this patch.

**Qualification:** Fault injection prewrite/prerename/postrename/dirsync; fresh reader and unrelated history survive; OS/filesystem evidence exact.

**Источники:** [PY-OS](https://docs.python.org/3.14/library/os.html).

### LIB-11 — FRY-01, FRY-03, ECO-01, FRC-01, FRC-02, EMP-01, PCL-01, STR-01

**Решение:** Existing domain registries, fiscal mechanisms, forecast owner и source-bound scorers предпочтительнее нового general engine.

**Baseline:** MethodRegistry/runtime view, current fiscal/plugin contracts, registered forecast adapter, existing observation/IR/CAS owners.

**Почему:** Library не решает taxbase, estimand, supported scope или независимость evidence. Сначала сохранить выбранный economic/statistical law и вывести новые cases через typed data/contracts. Новый semantic family законно требует общего кода и новой qualification.

**Альтернативы:** Новый универсальный mechanism/forecast/trust registry; Перенос float32 law в64 под видом refactor; Business heuristic по case ID.

**Цена:** Shared integration fixture costs amortized только при precise claim mapping; unrelated product systems не подключать ради маленького patch.

**Qualification:** Second materially different contract-compatible case, novel identifiers/axes/units, source mutation, actual fresh consumer; no causal/permission leap.

**Источники:** [JAX-DTYPE](https://docs.jax.dev/en/latest/101/default_dtypes.html).

### Версионные/доказательные оговорки источников

* [PY-MEAN](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py) — mean:146–165; _sum:1322–1373. Именно CPython3.14.0; source-level exact-ratio sum, деление до final float conversion. Native qualification установленного3.14 ещё требуется.

* [JAX-WHERE](https://docs.jax.dev/en/latest/faq.html#gradients-contain-nan-where-using-where) — Gradients contain NaN where using where. Принцип AD safety; current docs не разрешают использовать новые API без проверки locked0.8.2.

* [JAX-COND](https://docs.jax.dev/en/latest/_autosummary/jax.lax.cond.html) — cond semantics and vmap. Scalar conditional vs batched select; сохранять существующий narrow supported profile.

* [JAX-JIT](https://docs.jax.dev/en/latest/201/jit.html) — JIT caching, static arguments. Ключи/identity и recompilation; не substitute owner-level defaults/single-flight.

* [JAX-CACHE](https://docs.jax.dev/en/latest/persistent_compilation_cache.html) — Cache key and security considerations. Дополнение к wrapper cache, не новый authority owner; current guide, pinned0.8.2 qualification.

* [JAX-BENCH](https://docs.jax.dev/en/latest/benchmarking.html) — Benchmarking: compilation, asynchronous dispatch, dtype, device transfer. Измерять завершённое вычисление и раздельные cold/warm/transfer этапы; не performance claim настоящего review.

* [JAX-DTYPE](https://docs.jax.dev/en/latest/101/default_dtypes.html) — Default32 and X64 flag. Не менять процессный precision mode внутри доменного helper. Latest context-manager API не рекомендуется для locked0.8.2 без проверки.

* [PPO](https://arxiv.org/pdf/1707.06347) — Equations7,9,11,12; Algorithm1. Первичный математический oracle policy surrogate/GAE, не доказательство пользы конкретной политики.

* [OPTAX](https://optax.readthedocs.io/en/latest/getting_started.html) — Basic usage; Applying updates. update возвращает updates/state; apply_updates складывает. API already used by locked0.2.6; новых optimizer рекомендаций нет.

* [SALIB-LAWS](https://raw.githubusercontent.com/SALib/SALib/v1.5.2/src/SALib/util/__init__.py) — _nonuniform_scale_samples and scale_samples. Pinned1.5.2 transformations via SciPy; SciPy comparison проверяет adapter, не независимую численную реализацию самого quantile.

* [SALIB-FAST-SAMPLE](https://raw.githubusercontent.com/SALib/SALib/v1.5.2/src/SALib/sample/fast_sampler.py) — sample:local rng/handle_seed, sample size constraint. Pinned sampler уже local Generator; это не означает local RNG всей FAST pipeline.

* [SALIB-FAST-ANALYZE](https://raw.githubusercontent.com/SALib/SALib/v1.5.2/src/SALib/analyze/fast.py) — 63–64 and bootstrap111–135. Pinned analyzer использует np.random.seed/np.random.choice; current seeded FAST pending обоснован.

* [SK-PCA](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/decomposition/_pca.py) — 479–491 auto policy;661,682–693 randomized path. Именно locked1.8.0;600×100, k=5 выбирает randomized.

* [SK-RNG](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/utils/validation.py) — check_random_state1324–1351. None возвращает global RandomState singleton; нужен explicit derived local seed.

* [SCIPY-T](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html) — Definition, assumptions, statistic and df. Current docs; pinned1.16.3 API already used. Не заменяет declared sampling/near-zero policy.

* [SCIPY-BOOT](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) — method, paired, rng, batch. DefaultBCa не эквивалентен existing percentile. Optional dependency boundary и exact profile должны сохраниться.

* [SCIPY-BOOT-PIN](https://raw.githubusercontent.com/scipy/scipy/v1.16.3/scipy/stats/_resampling.py) — Pinned source availability for API qualification. Проверена доступность exact-version source; не полный audit реализации.

* [ARCH](https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html) — MovingBlock/CircularBlock/StationaryBootstrap. arch8.0.0 уже analytics option; другой estimand/dependence model, не drop-in iid замена.

* [SCIPY-ASSIGN](https://raw.githubusercontent.com/scipy/scipy/v1.16.3/scipy/optimize/_lsap.c) — 45–46 NPY_DOUBLE; rectangular assignment contract. Pinned1.16.3 converts costs to float64; exact mixed-radix lexicographic weights need range proof.

* [NX-MATCH](https://raw.githubusercontent.com/networkx/networkx/networkx-3.6.1/networkx/algorithms/matching.py) — max_weight_matching296–349. Pinned3.6.1: cardinality first, integer arithmetic, cubic complexity. Lock presence alone not direct runtime admission.

* [SCIPY-SOBOL](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html) — random_base2 vs random and balance warnings. Existing backend may supply low-discrepancy design; arbitrary bounded prefix must not claim balanced Sobol net.

* [PY-OS](https://docs.python.org/3.14/library/os.html) — os.replace1798–1806; fsync689–694. Atomic visibility is not durability. Filesystem/OS qualification explicit, no universal power-loss promise.

* [PY-ENTRY](https://docs.python.org/3.14/library/importlib.metadata.html#entry-points) — Entry points and distribution packages. Existing stdlib discovery; module/distribution identities not interchangeable; no second plugin framework needed.

## 7. Универсальность, free-grow и что не нужно переделывать

Free-grow здесь проверяется не числом поддержанных case IDs, а тем, что второй существенно иной совместимый случай проходит через **тот же** typed contract/owner: новая series/entity, другие units/axes, другой recipe topology, новые parameter names, иной output count, новая replica. Источник меняется как данные/ресурс, не как Python branch. Заменить имена при тех же числах — слишком слабый перенос; изменить все assumptions одновременно — не честный тест прежнего профиля.

Новые общие semantics закономерно требуют кода: новая economic law, новый neutral patch kind, новый joint distribution, новый likelihood contract для HARD training. Это не нарушение free-grow. Нарушение — специальный путь под один fixture, “универсальный” label поверх неподдержанного law, либо бесконечное накопление case-specific aliases без census/retirement.

Существующие решения правильно оставляют useful limited results: partial uncertainty, representable partial backtest rows, conditional failed-draw distribution, exploratory imputed Morris point, finite ill-conditioned fit и ordinary execution при unsupported training. Нельзя “усилить safety” до always-refuse и считать это исполненной capability. И наоборот, источник/подпись/receipt не дают научного смысла автоматически.

### Отклонённые ложные/необоснованные findings

* **Не требовать blanket снятия seeded FAST pending:** local RNG sampler не делает analyzer local; pinned analyzer использует global NumPy RNG. Проверено первичным source, LIB-06.
* **Не подменять bounded LOGNORMAL unbounded lognorm:** это другой law, а не недостающий import.
* **Не объявлять CAL-03 single-start config порядок дефектом без reachable path:** early single branch и final admission надо читать совместно.
* **Не объявлять normalized-income−1 ошибкой только из-за отрицательного loss:** ECO-01 explicitly named baseline; welfare definition — отдельное решение.
* **Не заставлять PCA tied rank1 vectors совпадать:** full retained subspace в separated-spectrum fixture — допустимый oracle; arbitrary basis orientation нет.
* **Не считать width heuristic MCSE:** UQP-03 уже правильно ограничивает claim; новая MCSE-модель — не обязательная часть rename/repair.
* **Не утверждать, что current PPO sign неверен:** source показывает правильный clipped-min вид; FN-PLG-ORACLE про acceptance mutation resistance.
* **Не настаивать на NetworkX только потому, что он в lock:** direct dependency admission и exact encoding всё равно нужны; current owned bounded exact algorithm допустим.
* **Не требовать нового storage/workflow/forecast/RL framework:** выявленные корни находятся в небольших existing owners и shared boundaries.

## 8. Порядок адресных изменений и критерий завершения

1. Уточнить CAL-02 support-before-nonlinearity, потом один shared native objective witness для CAL-03/04/06; не расходить closures.
2. Совместно DOE-02/03 добавить PCA stream/profile/metadata и один whole pipeline randomized-shape witness; FAST restriction не снимать попутно.
3. Для PLG-03 дополнить independent clipped PPO oracle и concrete native padding witness; на гипотезу не выпускать patch без проверки фактической guard chain.
4. Для BKT-02 отделить row validity/representable metrics от SSE availability, согласовать fresh IR reconciliation и schema compatibility.
5. FED/UQS согласовать common stdlib mean wrapper с Fabric owner; оставить behavioral contract, exact binary64/subnormal tests и bounded Decimal cross-check, а не mandatory custom accumulator.
6. Выполнить lane positive→persistence→fresh consumer и materially different transfer cases с current source records. Unrelated local-only matrices (aliases, actual OTel, registry census, historical width, iid/dependence, dtype/perf) не теряются при shared run.

Критерий будущего завершения — actual command/backend/input manifest, положительный и различающий негативный результат, independent oracle, exact saved refs и свежий reader. Исторический PASS, cached output, source-only arithmetic или фиктивный observer не повышаются до native PASS. Эмпирическая научная полезность и разрешение применения остаются отдельными решениями.

## 9. Приложения и статус

* `findings.json` — шесть полных findings со severity, scope, replacements, uncertainty.
* `library_decisions.json` —11 решений и23 первичных источника с version applicability.
* `coverage.json` —32 packet verdicts, все reviewed REQ/TEST IDs/hashes, actual code ranges,10 улучшенных lane scenarios, пределы покрытия.
* `independent_arithmetic.json` — host3.12 stdlib результаты: exact binary64 hex, Fraction и Decimal.from_float precision1200 для bounded fixtures; float32 residual-square representability проверена только независимым struct rounding. Это не product/native test.
* `source_reads.json`, `mapping_reads.json`, `json_semantic_supplements.json` — recoverable evidence logs; не заменяют findings/report.

Review work по назначенным32 пакетам завершена. Нет permission blocker. Продуктовые проверки намеренно NOT_RUN по контракту, а не ошибочно объявлены failed или passed. Адресные предложения к редакции v2 представлены отдельно; исходный комплект и репозиторий не изменялись.
