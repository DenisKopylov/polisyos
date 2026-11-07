# Независимое содержательное readback causal v2

**Результат: принять пять предложенных packet revisions как спецификацию; новых блокирующих содержательных дефектов не обнаружено. Это НЕ приёмка реализации, native/scientific tests — NOT_RUN.** Общая сборка и aggregate integration mapping требуют отдельной frozen QA; настоящий документ их не заменяет.

## Прочитано и проверено

Полностью прочитаны revised MD CAU-03, CAU-04, FIT-01, DDM-02, SCM-02 и LANE-05/11. Все пять JSON полностью разобраны; проверены нормативные тексты/тесты, metadata, source/residual/remaining/preservation bindings, technical solution, compatibility и конечные решения. Изменения сопоставлены с baseline, включая удалённые требования и неизменённые тесты. Claims из `causal_statistics/findings.json` и `proposed_changes.json` — предмет проверки, не независимое доказательство.

Точные SHA-256 всех 12 revised файлов, baseline, claims и прочитанных source/test файлов находятся в `review_causal_v2.json`. Зафиксированы 35 REQ и 44 TEST в пяти пакетах: исходные 35 REQ/39 TEST сохранены; добавлены ровно пять stable TEST IDs. Все оригинальные residual/remaining/preservation bindings сохранены буквально. Нормативная сверка сохраняет арифметические `*`/`**`, меняя только пробелы и code backticks. Разобранный JSON не равен native execution.

Новый независимый `causal_v2_independent_algebra.py` использует только stdlib/Fraction/math. Он не импортирует продукт, NumPy/SciPy/sklearn/DoWhy и не вызывает авторский `independent_oracles.py`. Численные результаты сохранены рядом в JSON. Unified diff сохранён отдельно. Никаких изменений продукта/пакетов при этом readback не сделано.

## CAU-03 / CS-001: conventional kernel covariance

**Принять.** Actual `rdd.py:69–121` действительно вычисляет weighted residual scale и умножает её на inverse Gram. Это согласуется с inverse-variance WLS, но не становится правильным iid observation-error kernel covariance от нормировки координаты. Различие предпосылок подтверждает [Statsmodels WLS 0.14.6](https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.WLS.html).

Независимая Fraction-алгебра построила R, W, B, linear estimator map L и residual map I−RL. Для указанного n=12 triangular design получила:

- `Var(intercept)=sum(L[0,i]²)=127/286` при noise covariance I;
- `E[legacy variance]=63/220`;
- ratio `0.6448818897637796`.

Дополнительно на явном outcome `1+2u+(-1)^i` residual-HC0 равен `88910/224939`, а legacy plug-in `42/121`: это конкретный различающий witness, а не только комментарий о весах. Для независимых левой/правой сторон jump variances складываются; нельзя трактовать side value как jump variance. Proposed TEST-08 это различает.

Новая HC0 формула содержит **w²**, independent known-noise oracle не объявлен равным finite-sample residual estimator, HC0 unbiasedness не обещается. Economy factorization сохраняет linear-in-n design и единую rank policy; RBC p/q fits не объединены искусственно. Existing RBC sensitivity/removal/coverage tests сохранены. Новый профиль/default/reader naming отложен до конечного compatibility decision; исторические values не переписаны. Статистический bias, continuity/manipulation и эмпирическая applicability не выводятся из covariance algebra. Это достаточная правка ошибочного scientific contract без требования новой universal estimator library.

## CAU-04 / CS-002: independent OLS oracle

**Принять.** [DoWhy v0.14 source](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/linear_regression_estimator.html) прямо использует Statsmodels OLS и его CI/SE. Поэтому сохранённый old comparison — полезный adapter parity, но не независимая реализация. Worker `linear_ate` проверяет точный ATE0→1/.95/full-rank/binary profile; proposed eight-row design подходит этому контракту. Замена A на 1−A сохраняет поддержанные values {0,1}, а не требует неподдержанного request contrast1→2.

Независимое точное решение normal equations дало beta=[1,2,3], SSE=8, df=5, variance treatment coefficient=4/5, SE=0.8944271909999159. Подстановка `t=sqrt(5)tan(theta)` в t5 density даёт `8 cos(theta)^4/(3pi)`; её интеграл — именно предложенный CDF. Bisection даёт t=.975 quantile 2.570581835636312 и CI [−0.2991982904835937,4.299198290483593]. Знак/обратные endpoints при relabel верны. Этот exact finite-design test независим от Statsmodels и не выдаётся за iid Gaussian выборку/идентификацию. Existing 200-seed coverage остаётся отдельной.

Проверен важный environment distinction: parent lock содержит NumPy2.3.5/sklearn1.8.0/Statsmodels0.14.6; **worker lock содержит NumPy2.4.6/sklearn1.9.1/Statsmodels0.15.0/DoWhy0.14**. Proposed requirement правильно просит actual worker inventory, а не считает parent versions worker evidence. Linux/Python3.12 guard в source подтверждён; подготовленная среда и реальные subprocess jobs здесь не выполнялись.

## FIT-01 / CS-003: train-only outcome preprocessing

**Принять.** `tmle_core.py:889–890` обучает scaler на всём Y до folds; `_fit_crossfit_fold` передаёт этот scaled Y в arm fit и тем же scaler возвращает predictions в raw scale. `nuisance_layer.py:331–359` берёт mean/std всего переданного массива. Реальный ElasticNet branch задаёт alpha=.01,l1_ratio=.5, поэтому масштаб не просто обратимо отменяется.

Из [objective sklearn1.8 ElasticNet](https://scikit-learn.org/1.8/modules/generated/sklearn.linear_model.ElasticNet.html) независимо выведена положительная ветвь slope `(1−.005s)/1.005` для симметричного двухточечного train design. При heldout M0→30 и глобальном s raw slope меняется с .9909627035774741 на .9245488246737122, хотя training rows не менялись. Это algebraic subproblem, не исполненный native n≥80 fixture.

Новый test наблюдает **конкретный fold**, а не требует неизменности aggregate predictions всех repeats: в других folds изменённые Y могут быть training data. Final targeting/EIF/ATE законно зависят от heldout outcome и явно исключены из invariance. Fixed splits, actual selected backend, train-Y positive control, raw control и cache invalidation отличают repair от fixture-only freeze. Нужна fold-owned preprocessing provenance и согласованная materialization scaler metadata; это уже указано в REQ/solution. Existing immutable fit-core/current-view, complete fold plan, serial-inner и binary pilot сохранены. Новый scientific defect не превращён в необходимость второго cache/scheduler.

## DDM-02 / CS-004: holdout и truthful preparation method

**Принять.** Source `calibrate.py:118,123–182` задаёт MBB label по умолчанию, но helper вычисляет quantiles/holdout/Wilson уже переданных streams; CLI `429–435` действительно использует calibration slice как fallback holdout. Proposed contract исправляет происхождение и separation, не требует обязательно поместить bootstrap внутрь helper.

TEST-08 проверяет resolution IDs в immutable source artifact **и observation/time coordinates**: два названия одного наблюдения не создают независимость, одинаковые значения разных наблюдений не запрещены. Raw empirical computation остаётся полезной; externally prepared MBB с index lineage — valid positive route. Disjoint coordinates сами по себе не доказывают statistical independence при временной зависимости: документ этого и не обещает, сохраняя отдельную stationary/scientific qualification.

TEST-07 retained без незаметной замены: 100 windows, не 400 Bernoulli trials; Wilson upper=0.03699480747600191 независимо подтверждён. Это арифметика synthetic fixture, не field FP/ERT/FDR certificate. Один reused stream сам по себе не был назван доказанным successful gate bypass. Actual production finite-source veto, direct-builder regression, freshness, policy identity и отсутствие institutional authority сохранены.

## SCM-02 / CS-005: replica target и quantile

**Принять как усиление квалификации, не новый доказанный numerical bug.** Прочитанный `gcm_query.py:1069–1238` пересчитывает persisted interval тем же `_refit_interval_from_models`; исходный worker source-row verification в `gcm_fit.py:300–450` полезен, но не независим от target helper. Width shrink alone сохранялся бы при common offset/scaling и не является достаточным oracle.

Для каждой full-rank selected row sample независимые scalar sums дают правильные OLS intercept/slope. Поскольку fit включает intercept, empirical residual mean точно нулевой в exact algebra; поэтому `beta0+2beta1` совпадает с fixed-model intervention mean, а `3beta1` — do2−do(−1) contrast. Это не произвольное отбрасывание residual law. На исходных восьми rows independently получены beta0=29/28, beta1=27/14, do2=137/28 и contrast81/14; дополнительные явные row resamples дают иные values, а degenerate sample выявляется как rank-deficient. Linear quantile convention `j=(R−1)q` и sign-reversed interval корректны.

Source row indices, каждый target и complete denominator теперь обязательны; correct coefficients с неверной target aggregation не проходят. Existing real worker80 refits/shrink/predictive-distinction/negative provenance tests сохранены. Иллюстративные stdlib samples **не являются actual NumPy seed45 corpus**; его full-rank/success/mutant observations должны быть предъявлены будущим native job, а не предполагаться из этого readback. Отказы не выбрасываются и seed не подбирается после результата.

## Лейны, preservation и remaining acceptance

LANE-05 правильно разделяет parent/worker и SCM/FIT branches; 88 REQ/103 TEST согласуются с текущими 13 packets. LANE-11 явно удерживает finite-monitor utility при незакрытом production source. Kuzu archive подтверждён [upstream repository](https://github.com/kuzudb/kuzu/); proposed wording не превращает archive в security finding/обязательную миграцию. В parent lock rustworkx не обнаружен, optional import не квалифицирует backend.

Новых substantive open findings нет. Остались **неисполненные условия будущей приёмки**, а не скрытые PASS: actual locked worker/subprocess/CAS/fresh readback, реальный continuous fold leakage regression, source-backed holdout producer, all requested bootstrap replicas, numerical mutants и отдельные scientific campaigns. Root должен обновить aggregate requirement/test/scenario maps и hashes после завершения всех writers. Этот readback одобряет только зафиксированные bytes; последующее содержательное изменение требует delta re-review.
