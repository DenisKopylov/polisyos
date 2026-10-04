# Каталог проверок 127 пакетов E02

Исходные требования и IDs взяты полным обходом `bundle_manifest.json@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`. Тестовые пути дополнительно проверены на этом SHA корневым агентом. Карта поведения и дополнительные пробы — кандидаты из 20 исследовательских отчётов; выполнение и достаточность требований ими не аттестуются. Перечень путей пакета не является точным finding → collected node отображением.

Команды ниже — диагностические целые файлы на research SHA, `cwd=<checkout>/policy-engine`. Уже полученные Q/C-результаты использовать в пределах их собственного cut; весь каталог подряд не прогонять. Файлы за пределами назначенного mode-roster получают отдельную дельту. Каждый запуск требует своего basetemp/output, frozen environment и receipts по README. Предложенные пробы сначала реализуются локально, затем тестируются в облаке. Технические детали дополнительных проб сохранены на языке исследовательских отчётов.

Исторические локальные ресурсные ограничения в отчётах не переносились как облачная аттестация. На Pro VM применяется общий контракт README: один pytest-процесс, численные threads=1, отдельные CAS/DuckDB/scratch roots; дополнительные сервисы и native dependencies устанавливаются только в выбранном profile.

<a id="acq-01"></a>

## ACQ-01 — N7: типизированное требование → acquisition → re-entry

**Записи:** B12, LA-046. **Реестр:** B12=partial, LA-046=partial.
**Маршрут:** первый сбор Q01, Q07, Q08; historical C03, C05, C18; дополнительно D02, D04. **Checkpoint:** CP1. **Исследователь:** e02_01.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/ACQ-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: REQ-01, CYC-03. Protected controls: LK24, LK31.

**Дискриминатор из owner-пакета:** Два разных problem statements доходят до resolver как разные запросы; отсутствие resolver/empty specs не считается отсутствием потребности или выполненным acquisition. Explicit specs и typed any-of gap не перезаписываются. Один разрешённый local fixture-source через настоящие contracts даёт receipt и повтор зависимого расчёта; отказ прав/бюджета сохранён.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_acq_01.py` → Q07 / C05
- `policy-engine/tests/unit/data_requirement/test_compiler.py` → Q08 / C18
- `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py` → Q01 / C03

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_acq_01.py tests/unit/data_requirement/test_compiler.py tests/unit/runtime/quality/test_generation_cycle.py
```

**Profile и доступность:** test; runtime.
**Карта поведения из статического исследования:** Behavioral compiler/caller/consumer tests. Dedicated N7 tests check precedence, typed gap, two distinct statement/domain/scope inputs, resolver forwarding, missing-resolver/empty-spec fail-closed behavior, local recorded-owner write and N5/N8 re-entry; adjacent compiler and generation-cycle tests cover the owner and same-cycle route.

**Дополнительные пробы / границы:**
- Add explicit denied-rights and over-budget negative coverage proving there is no accepted source, receipt, or dependent re-entry. Existing fixture route evidence is zero-cost/positive-budget; contract-test-only scope refusal does not establish budget/rights denial.
- If closure requires one integrated real resolver proof, feed both distinct N7 statements through the actual DataRequirementCompiler/resolver and compare produced query objects. The dual-input caller test uses a RecordingCompiler stub; resolver-owner tests are separate.
- Ограничение: No denied-rights/over-budget negative was found among the mapped acceptance tests.
- Ограничение: No test execution/pass status established; collection only.

<a id="api-01"></a>

## API-01 — Причинные фасады: explicit surface вместо отражающих globals

**Записи:** LA-020. **Реестр:** LA-020=partial.
**Маршрут:** первый сбор Q20; historical C11; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_01.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/API-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK05, LK13.

**Дискриминатор из owner-пакета:** Public/star/underscore exports, docs/monkeypatch/FQN, unknown name, incidental new internal import не расширяет API. Реальные causal_engine/interference пакетные imports сохраняются независимо от удалённых sibling файлов.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_api_01.py` → Q20 / C11
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test__causal_engine_contracts.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test__interference_contracts.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_api_01.py tests/unit/foundry/methods/catalog/causal/test__causal_engine_contracts.py tests/unit/foundry/methods/catalog/causal/test__interference_contracts.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral package-facade tests for real imports, leaf identity, stable __all__, star import, unknown names, incidental imports, monkeypatch bindings and reload cleanup.

**Дополнительные пробы / границы:**
- Run a complete import/FQN/string/monkeypatch/docs client census for both packages, with full source/test/docs and file-type denominators.
- If sibling deletion compatibility is part of closure, add an isolated-import/deletion probe; current tests prove identity with sibling modules present.
- Ограничение: Docs/FQN/dynamic client census is not demonstrated by the focused tests.
- Ограничение: No test execution/pass status established; collection only.

<a id="ber-01"></a>

## BER-01 — BERL: schema profile и действительная identity объяснителя

**Записи:** LA-034, LA-036. **Реестр:** LA-034=partial, LA-036=partial.
**Маршрут:** первый сбор Q02; historical C12; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_01.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BER-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK13.

**Дискриминатор из owner-пакета:** Full bundle, empty nested objects, extra fields, version9.9.9 и omitted defaults по обоим объявленным profiles; content drift test, не только $id. На двухпризнаковой модели: два alias, changed background/model/parameters, unsupported request и explicit fallback; число реальных model calls и effective identity. Feature-count/empty-background guards сохранены, source raw data не меняются.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_ber_01.py` → Q02 / C12
- `policy-engine/tests/unit/berl/test_contracts.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/berl/test_service.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_ber_01.py tests/unit/berl/test_contracts.py tests/unit/berl/test_service.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral schema/artifact and producer coverage for construction/persisted profiles, content-drift equality, nested empty/extra rejection, version handling, effective request identity, alias dedup/model-call count, unavailable diagnostic and explicit TreeSHAP fallback.

**Дополнительные пробы / границы:**
- Дополнительный discriminator по статическому исследованию не выделен; это не PASS.
- Ограничение: No test execution/pass status established; collection only.

<a id="bkt-01"></a>

## BKT-01 — Фактический historical view, тип прогноза и реплики

**Записи:** B166, B169, B170. **Реестр:** B166=partial, B169=partial, B170=partial.
**Маршрут:** первый сбор Q11, Q18; historical C11, C14; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_01.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Для[1,2,900,901]/cutoff=2 runner реально получает префикс. Scalar ATE=7 не размножается в forecast/CI без контракта; явный constant profile работает. n=1/n=7 меняют действительный план либо дают capability-result. PROVIDED не запускает лишних симуляций.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/methods/backtesting/test_backtesting.py` → Q11 / C11
- `policy-engine/tests/unit/scientist/methods/backtesting/test_masking.py` → Q18 / C14

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_bkt_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/methods/backtesting/test_backtesting.py tests/unit/scientist/methods/backtesting/test_masking.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral backend-boundary/local-artifact coverage for actual pre-cutoff bytes, scalar and CI trajectory status, explicit constant profiles, horizon mismatch, n_simulation_runs dispatch, and PROVIDED no-dispatch.

**Дополнительные пробы / границы:**
- The current n_simulation_runs test captures mocked run_experiment state for n=7 only. Add paired n=1/n=7 or real backend-plan evidence that the consumer uses the count or returns typed unsupported; a populated field is a P38 proxy for executed repeats.
- Add a derived-feature leakage test if derived features occur in the historical input; current masked-view test checks raw metric/time_index prefix only.
- Ограничение: Dedicated test_bkt_01.py is absent; existing native tests cover most listed behavior.
- Ограничение: No test execution/pass status established; collection only.

<a id="bkt-02"></a>

## BKT-02 — Полнота сравнения, nominal coverage и micro/macro

**Записи:** B167, B168, B171. **Реестр:** B167=partial, B168=partial, B171=partial.
**Маршрут:** первый сбор Q01; historical C06; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_01.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: BKT-01. Protected controls: LK01, LK29, LK30.

**Дискриминатор из owner-пакета:** Wrong-key/zero comparisons не дают gradeA. Удаление трудного prediction не улучшает completeness. Один доступный попавший CI из двух точек показывает availability=1/2 и hit=1/1 на доступных. Разное разбиение[0,10,10] сохраняет micro RMSE; macro описан отдельно.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_bkt_02.py` → Q01 / C06

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_bkt_02.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral evaluator/orchestrator/persisted-report checks for requested/compared/missing/invalid denominators, empty/wrong-key refusal, CI availability versus hit denominator, nominal level, micro invariance and explicit macro policy; includes exact-comparison positive control.

**Дополнительные пробы / границы:**
- Дополнительный discriminator по статическому исследованию не выделен; это не PASS.
- Ограничение: Shared write/test surface with BKT-01 and BKT-03 is orchestrator.py/test_backtesting.py; serialize source mutation and accepted-SHA consumer checks.
- Ограничение: No test execution/pass status established; collection only.

<a id="bkt-03"></a>

## BKT-03 — Описательное смещение и честный статистический backend

**Записи:** B172, B173. **Реестр:** B172=partial, B173=partial.
**Маршрут:** первый сбор Q03; historical C17; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_01.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: BKT-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Residuals10,10,10 имеют bias magnitude без выдуманного p=0;0,0,0 — отдельный контроль. Для 0.5,1.5,2.5 normal approximation не называется t-test. Настоящий scipy ttest_1samp даёт маленький reference; coverage campaign не запускается.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_bkt_03.py` → Q03 / C17

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_bkt_03.py
```

**Profile и доступность:** test; analytics.
**Карта поведения из статического исследования:** Behavioral report/trust checks for constant nonzero and zero residual distinction, uncomputable small-n test status, SciPy reference, and simulated SciPy absence while preserving metrics and withholding trust.

**Дополнительные пробы / границы:**
- Provision the analytics extra for the cloud run: test_small_sample_ttest_matches_scipy_reference uses pytest.importorskip('scipy.stats'), so without SciPy the true reference case can skip.
- Ограничение: Dedicated test_bkt_03.py is present at the pin; no run/pass status established.
- Ограничение: No test execution/pass status established; collection only.

<a id="bkt-04"></a>

## BKT-04 — Только выбранные CV-разбиения и разрешённая bootstrap-статистика

**Записи:** B174, B175. **Реестр:** B174=partial, B175=partial.
**Маршрут:** первый сбор Q08, Q14; historical C06, C11; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_01.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** n=1000/max_folds3 создаёт нужные 6 списков без подготовки 1996. Step=0/negative отвергается до loop. Medain не заменяется mean под подписью median; для[0,0,9] median=0 и mean=3 различаются. Non-finite не становится обычным CI, seed воспроизводим.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/methods/backtesting/test_cv.py` → Q14 / C11
- `policy-engine/tests/unit/scientist/methods/backtesting/test_bootstrap.py` → Q08 / C06

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_bkt_04.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/methods/backtesting/test_cv.py tests/unit/scientist/methods/backtesting/test_bootstrap.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral pure-unit coverage for max_folds-bounded materialization, invalid CV progress values before the loop, actual median versus mean, unknown statistic rejection before draws, non-finite input/output rejection and seeded reproducibility.

**Дополнительные пробы / границы:**
- Дополнительный discriminator по статическому исследованию не выделен; это не PASS.
- Ограничение: Dedicated test_bkt_04.py is absent; existing native tests cover the listed behavior.
- Ограничение: No test execution/pass status established; collection only.

<a id="cal-01"></a>

## CAL-01 — Наблюдения, календарная ось и заполнение без фиктивной опоры

**Записи:** B176, B177, B178. **Реестр:** B176=partial, B177=partial, B178=partial.
**Маршрут:** первый сбор Q11; historical C16; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK01.

**Дискриминатор из owner-пакета:** Переименование observation ID не выбирает 10 вместо 20. Перестановка пар времени/значения сохраняет разрешённую интерполяцию; отсутствующий запрошенный time_column не становится позиционной осью. Integer/float при fill=0.5 дают одинаковое заполнение; empty+steps=3 не выглядит наблюдаемым рядом из нулей.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cal_01.py` → Q11 / C16
- `policy-engine/tests/unit/foundry/calibration/test_measurement.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/calibration/test_preflight.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cal_01.py tests/unit/foundry/calibration/test_measurement.py tests/unit/foundry/calibration/test_preflight.py
```

**Profile и доступность:** pytest requires the project test extra; command uses uv run --extra test.; JAX/JAXLIB, NumPy, pandas, and OpenTelemetry are declared in the project base dependencies; no research, ML, or Apple Metal extra is indicated for these selectors.; Project Python range is >=3.14,<3.15. Linux/cloud execution should use CPU JAX; a macOS Metal result would not substitute for a Linux receipt..
**Карта поведения из статического исследования:** Direct test-first behavioral witnesses in the real compiler/preflight owners, plus neighboring mask, measurement-loss, raw-target normalization, padding, and endpoint-fill unit tests. No command was executed for this report; these are available checks, not pass receipts.

**Дополнительные пробы / границы:**
- B176: the direct ID-renaming and conflicting-source tests cover non-selection of a technical ID; retain an assertion that every accepted same-period observation remains represented with its own source/unit lineage or has an explicit owner aggregation. Current fixtures do not exercise a multi-source aggregate with complete lineage.
- B177: add one raw alignment case where time, values, masks, and metadata are all permuted together and assert the aligned outputs remain paired; current compiler reorder test checks metadata pairing and the raw resampling test checks values/time separately. Add non-finite and repeated-time inputs to pin the declared time-axis policy.
- B178: pair the empty-target rejection with a downstream fit/report assertion that no-support cannot be presented as calibrated zero. The current direct test asserts preparation raises; the native finite-gradient/loss tests do not produce a positive full CalibrationReport.
- Preserve the positive endpoint-fill control; do not make every boundary fill invalid. The current endpoint-fill test is that control.
- Ограничение: No test run or exact output was captured, so current pass/fail and timing are not established.
- Ограничение: The tests establish local transformations on synthetic fixtures; they do not by themselves establish the provenance or semantic validity of external observations.

<a id="cal-02"></a>

## CAL-02 — Один effective loss: оси, два уровня весов и masked scale

**Записи:** B179, B180, B181, B182. **Реестр:** B179=partial, B180=partial, B181=partial, B182=partial.
**Маршрут:** первый сбор Q19; historical C12; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAL-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Вектор и столбец не образуют N×N пар без явного контракта. Веса 9:1 и 1:9 меняют общую цель. Полностью masked target имеет конечные primal/gradient, но статус отсутствия опоры. Добавление дат другого target не меняет loss первого. Tiny JAX grad/JIT проверяется по одному слоту N, не полным fit.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cal_02.py` → Q19 / C12
- `policy-engine/tests/unit/foundry/calibration/test_loss.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/calibration/test_measurement.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/calibration/test_calibrator_mvp.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cal_02.py tests/unit/foundry/calibration/test_loss.py tests/unit/foundry/calibration/test_measurement.py tests/unit/foundry/calibration/test_calibrator_mvp.py
```

**Profile и доступность:** pytest test extra only beyond the base project runtime for the named paths.; JAX/JAXLIB and NumPy are base dependencies. No GPU, Apple Metal, Bayesian, or broader research extra is required by the listed tests.; Linux CPU JAX is the portable target; no test result from an accelerator-specific backend should replace it..
**Карта поведения из статического исследования:** Direct tests cover shape rejection, effective sample-quality weights, inter-target objective weights, zero-support primal/gradient/JIT and observed-training-mask scale. The second command is a narrower downstream trainer/GradNorm/Hessian consumer check, not a full fit/report consistency proof. None was run here.

**Дополнительные пробы / границы:**
- B179: test_cal_02.py rejects (N,1) versus (N) broadcasting; add positive explicit-shape controls for scalar and equal-shaped axes and retain the pre-JIT failure assertion.
- B180: the 9:1 versus 1:9 objective test directly proves target priority affects the sum, while the sample-quality test proves within-target normalization. Add one composed two-target fixture through the calibrator's actual objective to prove the same weight placement reaches optimizer, GradNorm, report, and Hessian consumers.
- B181: finite primal/gradient/JIT plus has_effective_support=False distinguishes no support from a valid zero fit at the helper boundary. Add an end-to-end no-support status/report assertion so finite zero cannot be promoted downstream.
- B182: direct _compute_scale_local test excludes placeholder dates; add a training-slice consumer test proving other-target dates cannot alter target A's fitted scale/report/Hessian on the same tiny calibration run.
- Ограничение: No run receipt exists; JIT compilation time is only estimated.
- Ограничение: Helper-level tests are not evidence that every consumer uses one effective objective. The selected trainer tests are useful downstream signals but do not assert exact equality across fit, GradNorm, report, and Hessian.
- Ограничение: No positive full-fit test currently couples the no-support status to a non-publishable calibration outcome in the listed path set.

<a id="cal-03"></a>

## CAL-03 — Несколько стартов: span lifecycle и пригодность выбора

**Записи:** B183, B195. **Реестр:** B183=partial, B195=partial.
**Маршрут:** первый сбор Q04; historical C05; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAL-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Два старта с OTel и без него проходят; повтор одноразового context manager отсутствует. NaN-loss не выигрывает из-за порядка списка. condition=inf не считается отсутствием диагностики, finite-large и unknown имеют свои результаты. Проверка выбора на таблице кандидатов; один маленький настоящий Hessian в K4.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cal_03.py` → Q04 / C05
- `policy-engine/tests/unit/foundry/calibration/test_multi_start.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/calibration/test_hessian.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cal_03.py tests/unit/foundry/calibration/test_multi_start.py tests/unit/foundry/calibration/test_hessian.py
```

**Profile и доступность:** pytest test extra; NumPy/JAX/JAXLIB and OpenTelemetry API are in base dependencies.; No external telemetry service is needed for the helper tests; the fake tracer is local. A Linux/cloud receipt should use CPU and the real installed OTel API for the added orchestration check..
**Карта поведения из статического исследования:** Selection has direct negative and mixed-outcome tests for NaN/non-numeric loss, missing versus infinite Hessian, finite-large condition, fallback, and tie order. Span tests call the production span-context helper with a one-shot fake tracer. Native tests separately exercise selection and low-dimensional Hessian math. No tests were run.

**Дополнительные пробы / границы:**
- B183: the fresh-context tests call _calibration_span_context twice, but do not run the actual multi-start optimizer loop with an OTel tracer. Add a tiny two-start orchestration test that records two distinct spans, verifies start_index attributes, and checks cleanup when one start raises.
- B195: current tests distinguish hessian_result=None from condition_number=inf and finite-large, and cover all-diagnostics-limited fallback. Add a tiny real K=4 calibration selection case so the actual Hessian producer and selector are exercised together; current unit selection fixtures construct HessianResult values directly.
- Retain an honest limited candidate as limited in the returned result/report while confirming it does not satisfy the acceptable-selection filter. Current all-limited test checks fallback reason and finite loss, but not the full report's limited status.
- Ограничение: No pass/fail or duration receipt exists.
- Ограничение: The OTel witness exercises a helper boundary, not the multi-start orchestration consumer; this is the main P38 divergence to close.
- Ограничение: The selector tests are fixture-driven; they do not demonstrate the whole optimizer-to-Hessian-to-selected-report bridge.

<a id="cal-04"></a>

## CAL-04 — Последний итерат, единый финальный forward и Hessian reuse

**Записи:** B184, B196, B203. **Реестр:** B184=partial, B196=partial, B203=partial.
**Маршрут:** первый сбор Q03; historical C17; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAL-03. Protected controls: нет.

**Дискриминатор из owner-пакета:** f(x)=(x−1)^2: один шаг из 0 к 0.5 может вернуть улучшенный результат; чрезмерный шаг к 4 не вытесняет лучший 0. Финализация не выполняет три одинаковых scan. При N стартах нет N+1 одинакового Hessian; изменение выбранной точки требует нового расчёта. Счётчики и небольшой настоящий JAX-контроль.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cal_04.py` → Q03 / C17
- `policy-engine/tests/unit/foundry/calibration/test_multi_start.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/calibration/test_hessian.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cal_04.py tests/unit/foundry/calibration/test_multi_start.py tests/unit/foundry/calibration/test_hessian.py
```

**Profile и доступность:** Use the provisioned Python >=3.14,<3.15 environment and pytest test extra (`uv run --extra test`). JAX/JAXLIB and NumPy are base dependencies; the listed tests use CPU and no research/ML/Metal extra.; Linux/cloud portability is expected for CPU JAX but not established here; keep the same dtype/backend policy and a unique local temp root..
**Карта поведения из статического исследования:** test_cal_04.py drives the real Calibrator.run orchestration with a controlled synthetic, parameter-connected JAX scan: better and overshooting final iterates are selected by evaluated loss; one final scan supplies total/per-target/report projections; nonfinite gradients retain the last checked state; step-varying and fixed-seed candidate checks use comparable final replicas. Its multi-start cases assert N Hessians rather than N+1 and force recomputation when reuse identity differs, with real JAX Hessian calculations. Native multi_start.py and hessian.py add selection/math controls. These are behavioral candidates, not a run receipt in this report. E02-R2 records B184, B196, and B203 as partial due to missing finding-specific selector/receipt reconciliation, explicitly not as behavior failures.

**Дополнительные пробы / границы:**
- B184: current tests cover a single final forward and same-replica controls. The R2 row asks for unchanged-input replay plus an explicit independently requested stochastic-replica control; reconcile an exact selector/result to that discriminator rather than inferring row closure from a bundle run.
- B196: current tests exercise improving, overshooting, and nonfinite updates. The inspected set has no explicit exhausted-resource/no-budget-for-final-evaluation branch; add a bounded case that retains the last checked state and asserts evaluation counts if that branch is in scope. The R2 row still lacks an accepted finding-specific selector receipt.
- B203: current tests cover N versus N+1 and identity-mismatch recomputation. To meet the R2 discriminator, add or identify a case where a prior diagnostic miss/error cannot hide or bless a changed matrix, and compare matrix/fields/constraints as well as call count. Link exact selectors and results to B203; the current R2 partial status is an evidence-link gap, not a reported defect.
- Ограничение: No test command or timing was executed in this planning pass. A test’s presence or a whole-bundle receipt does not resolve the row-specific R2 evidence gap.
- Ограничение: The controlled scan is synthetic; it verifies real Calibrator/JAX orchestration paths but does not establish every configured production model or downstream publication capability.

<a id="cal-05"></a>

## CAL-05 — Неактивный механизм не вычисляется как активный

**Записи:** B185. **Реестр:** B185=partial.
**Маршрут:** первый сбор Q10; historical C03, C15; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-05.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Отложенный log(x) при x=0 не портит доступный префикс и градиент; активный режим сохраняет реальный отказ на недопустимом входе. Проверить eager, JIT и применимый vmap на маленьком механизме; обе ветви имеют согласованные формы. Счётчик emitter отличает tracing от численного исполнения.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/foundry/calibration/test_pure_executor_semantics.py` → Q10 / C15
- `policy-engine/tests/unit/foundry/calibration/test_pure_executor.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/analysis/test_merge_engine_regressions.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/analysis/test_merge_determinism.py` → Q10 / C03

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_cal_05.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/foundry/calibration/test_pure_executor_semantics.py tests/unit/foundry/calibration/test_pure_executor.py tests/unit/foundry/analysis/test_merge_engine_regressions.py tests/unit/foundry/analysis/test_merge_determinism.py
```

**Profile и доступность:** Python >=3.14,<3.15 and pytest test extra; JAX/JAXLIB, NumPy, and implementation dependencies are in project base dependencies. CPU JAX is sufficient.; No GPU/Apple Metal or telemetry service is required by the inspected selectors. Linux/cloud runtime is unverified in this research pass..
**Карта поведения из статического исследования:** The proposed remediation path tests/unit/remediation/test_cal_05.py is absent at the pinned source; existing native tests already execute apply_nodes/run_pure_scan and cover the main inactive-path property. test_pure_executor_semantics.py instruments a fake log emitter: inactive execution does not call it, preserves state and PRNG key, keeps finite identity gradients, while the active path runs and differentiates correctly; it also exercises dynamic JIT/lax.cond, eval_shape/vmap with homogeneous schedules, active invalid-input refusal, and inactive scan integration. Merge companion tests cover dependency flush, batched merge, conflicts, determinism, and merge rules. Current E02-R2 records the exact inactive scan witness as 3/3 bounded evidence; its remaining B185 residual is mixed active/inactive rows with different per-row schedules, which the current vmap test explicitly excludes. This report did not rerun that evidence.

**Дополнительные пробы / границы:**
- Do not treat the absent proposed test_cal_05.py as missing behavioral coverage: the existing native path exercises the inactive emitter/gradient behavior and the R2 ledger retains a bounded 3/3 witness for test_run_pure_scan_preserves_inactive_gradient_path.
- Only if heterogeneous per-row schedules are required, add a mixed active/inactive batch through the consuming calibration path and compare the active row with its single-row gradient control while proving the inactive row has no runtime emission or gradient contribution. Otherwise retain the explicit bounded limitation: mixed per-row schedules are unsupported; the existing vmap witness is homogeneous.
- Ограничение: No test command or timing was executed here. The existing active/inactive tests use synthetic mechanisms, not every registered production mechanism.
- Ограничение: The current vectorized witness deliberately uses one scalar schedule for the batch; do not infer heterogeneous schedule support or general execution savings from it.

<a id="cal-06"></a>

## CAL-06 — Tied-параметры и неизменный масштаб условного закона

**Записи:** B197, B198. **Реестр:** B197=held, B198=closed.
**Маршрут:** первый сбор Q02, Q06, Q07; historical C10, C15, C19; дополнительно по готовности новых проб. **Checkpoint:** CP4. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-06.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAL-04, UQP-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Два поля одной tied-группы имеют дисперсии и cross-covariance=0.0025, оставаясь одной степенью свободы. Переименование группы не теряет envelopes. Отображение уровня 0.8/0.95 не меняет исходный STD=1; heuristic/gate prohibition остаётся. Untied и unknown-STD контроли сохранены.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cal_06.py` → Q02 / C19
- `policy-engine/tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py` → Q07 / C15
- `policy-engine/tests/unit/foundry/uncertainty/test_covariance.py` → Q06 / C10

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cal_06.py tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py tests/unit/foundry/uncertainty/test_covariance.py
```

**Profile и доступность:** Python >=3.14,<3.15 with pytest test extra; JAX/NumPy dependencies are base, but these selected adapter/covariance tests are CPU and no accelerator is required.; No external data or cloud service is required by the selectors. Linux/cloud portability is expected at CPU level but unverified here..
**Карта поведения из статического исследования:** test_cal_06.py exercises typed Normal(mean,std) payload preservation at display levels 0.8/0.95, unchanged extract_std, heuristic/non-gate-eligible status, typed carrier precedence over mutable metadata, fail-closed incomplete Normal, declared Uniform support, and missing Hessian STD. The native adapter tests map one tied coordinate onto A.rate/B.rate with the full singular covariance row, preserve name-renaming invariance, reject incomplete projection, and retain the V1 wire shape on persisted round-trip; covariance tests preserve the tied nullspace. Reconcile with R2: B197 has a separate bounded 58/58 internal Calibrator→persisted v2 report→reopen→welfare witness but remains held for a configured/served producer with independently admitted provenance and consumer-specific kind/schema admission. B198 is closed bounded for the persisted typed-scale and Phase3 discriminator with removal-probe/P41 receipts. Neither ledger evidence nor a passing run is produced by this report.

**Дополнительные пробы / границы:**
- B197: do not repeat the bounded tied-projection/persist-reopen case as an unclosed requirement. The current held residual is the configured/served Calibrator producer, independently admitted source/graph/plan provenance, and consumer-specific typed intake resolving stored kind/schema; marker-removal, served sibling consumer, and production-scale evidence are also not established. Any next probe should target that bridge and keep authority claims scoped.
- B198: the current R2 row already records bounded closure for the exact source-card discriminator, including persisted ParametricFitCarrier Normal std=1.0, fixed-seed welfare behavior at 0.8/0.95, Phase3 eligibility, removal probes, and a whole-file replay. Do not reopen it because this local suite is unit-level. Adjacent GE-entry-only references, GE matrix admission, and CREDIBLE law/provenance are separate residuals, not B198 gaps.
- Ограничение: No test command or duration was observed in this planning pass. The R2 B197/B198 receipts have their own source snapshots and must not be presented as this pinned worktree’s run receipt.
- Ограничение: B197’s remaining served-producer bridge is not established by the listed unit tests; that held capability is distinct from the local tied-coordinate property.

<a id="can-01"></a>

## CAN-01 — Strict canon: один primitive, явные Core/IR профили

**Записи:** LA-021. **Реестр:** LA-021=closed.
**Маршрут:** первый сбор Q10; historical C15; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAN-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK07, LK20.

**Дискриминатор из owner-пакета:** Decimal/date/bytes/null/numeric/depth/tags, float_hex/bytes_hex/array_digest, malformed input, old read/write/hash identity. Идентичные исторические payloads не меняют digest. IR не импортирует Core; runtime JsonDataVisitor/WIRE-01 остаются отдельными contracts.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_can_01.py` → Q10 / C15
- `policy-engine/tests/unit/ir/test_canon_hash_parity.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/ir/test_canon_hardening.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/ir/test_semantic_group_imports.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/core/phase0/test_canon_json.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/core/test_hashing.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_can_01.py tests/unit/ir/test_canon_hash_parity.py tests/unit/ir/test_canon_hardening.py tests/unit/ir/test_semantic_group_imports.py tests/unit/core/phase0/test_canon_json.py tests/unit/core/test_hashing.py
```

**Profile и доступность:** pytest test extra only for the named tests; canonical codecs use standard-library and base project dependencies.; Project Python >=3.14,<3.15. No JAX accelerator or research extra is needed for this bundle's tests.; Run the architecture guardrail from a provisioned checkout after any common/canonical.py owner move; it is a separate boundary check, not a test receipt for codec parity..
**Карта поведения из статического исследования:** The listed files are executable characterization/compatibility tests for ordinary canonical bytes and hashes, Core/IR typed-tag differences, malformed/depth behavior, and public owner/facade boundaries. Reconcile them with the current E02-R2 residual ledger: LA-021 is closed bounded for the measured 7,762-record tracked current/main JSON path/blob plus shared JSONL corpus and exercised Core/IR owner contract (zero unexpected differences; historical owner tests 43/43 current/Phase-0 and 24/24 shared-main). This is prior ledger evidence, not a run in this report or proof beyond that bounded profile.

**Дополнительные пробы / границы:**
- Do not repeat the broad tracked-corpus census as an open missing-test claim: the current E02-R2 LA-021 row records the bounded 7,762-record measurement and owner-contract results. If the plan explicitly extends beyond that closure, the remaining ledger probes are the exact historical architect 418-input selector and the 140 shared caller-file four-base replay; both remain UNRUN. Keep CAS objects, runtime-generated values, production_data, non-JSON formats, and alternate environments explicitly outside the existing closure unless a new scope is admitted.
- A fresh run of the listed selectors may confirm their state at the pinned 69780761ae091d8fcc6ab8778c7f5f7227eeef0b source, but would not replace the distinct 418-input or 140-file receipts. Do not interpret the ledger’s bounded closure as full historical or external equivalence.
- Ограничение: This research pass did not execute tests or validate the historical receipts. The ledger supports bounded closure only; it does not establish parity for the exact unrecovered selector, the full 140-caller replay, dynamic/runtime-generated data, or excluded deployment environments.
- Ограничение: The E02-R2 gap is evidence scope, not a claim that the measured corpus or the listed regression tests fail.

<a id="cas-01"></a>

## CAS-01 — First-writer, честная ref и bounded lock ownership

**Записи:** B150, B151, B153. **Реестр:** B150=closed, B151=partial, B153=closed.
**Маршрут:** первый сбор Q04, Q06, Q10, Q11, Q12, Q20; historical C05, C07, C13, C16, C18; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_02.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAS-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK20.

**Дискриминатор из owner-пакета:** Повтор bytesA с profileB не выдаёт refB при сохранённом manifestA. Existing corrupt blob не подтверждается как successful put. Два управляемых writer сохраняют first-writer semantics. Малое число ключей и искусственный cap проверяют bound без массовых файлов.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cas_01.py` → Q04 / C13
- `policy-engine/tests/unit/core/phase0/test_artifact_store.py` → Q10 / C16
- `policy-engine/tests/unit/core/artifacts/test_artifact_store_protocol.py` → Q11 / C13
- `policy-engine/tests/unit/core/artifacts/test_manifest_serialization_schema.py` → Q06 / C05
- `policy-engine/tests/unit/core/artifacts/test_manifest_lineage_input_normalization.py` → Q20 / C07
- `policy-engine/tests/unit/core/artifacts/test_cas_integrity_report.py` → Q12 / C18

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cas_01.py tests/unit/core/phase0/test_artifact_store.py tests/unit/core/artifacts/test_artifact_store_protocol.py tests/unit/core/artifacts/test_manifest_serialization_schema.py tests/unit/core/artifacts/test_manifest_lineage_input_normalization.py tests/unit/core/artifacts/test_cas_integrity_report.py
```

**Profile и доступность:** pytest test extra only beyond project base dependencies; cryptography, Pydantic and the local filesystem CAS are base dependencies.; Project Python >=3.14,<3.15. Test design uses pathlib/tmp_path, threading Events and Ed25519; no macOS-only API or external cloud service is apparent.; For cloud/Linux portability use a local container scratch filesystem with hard-link support; overlay/NFS semantics and runner-specific filesystem behavior remain unmeasured..
**Карта поведения из статического исследования:** Direct store tests read back actual refs/manifests/bytes, inject blob corruption and assert failure or verified repair, orchestrate two same-ID writers, and pressure a bounded lock pool while a same-ID waiter is live. The test file also has opt-in mutation/removal probes. Adjacent tests cover historical manifest bytes, store integrity, lineage/profile normalization and report behavior. No command was executed; the opt-in removal probe is expected-red evidence and must not be counted as a normal passing test.

**Дополнительные пробы / границы:**
- B150: current tests compare returned references with persisted manifests and exercise repeated same-profile plus concurrent writers. Preserve a direct different-profile retry case that asserts the returned reference resolves to exactly the manifest/profile it claims; keep physical blob dedup separate from provenance identity.
- B151: the corruption retry test accepts either fail-closed or a successful retry whose bytes and verify result are correct. Add assertions for quarantine/repair-event custody and for the atomicity of a concurrent read/retry; current acceptance does not require proof that a quarantined copy and repair event remain available.
- B153: the main lock test generates 3000 IDs, checks the fixed pool size, and keeps a same-ID waiter behind an active holder; the colliding-stripe test keeps different CAS bytes/manifests distinct. Run both normal behavior and the existing opt-in removal probes as separately labeled expected-red checks.
- Keep process-lock scope explicit: these tests prove in-process thread ownership only, not cross-process or distributed mutual exclusion; the card does not require a distributed lock service.
- Ограничение: No test, mutation probe, or Linux filesystem was exercised in this research pass; pass/fail and timings are not established.
- Ограничение: The corrupt-retry test does not assert a retained quarantine artifact or auditable repair event, and does not establish concurrent recovery semantics.
- Ограничение: The lock tests deliberately prove one-process thread semantics; inter-process exclusion is outside the assigned finding and must not be inferred.

<a id="cas-02"></a>

## CAS-02 — Сначала проверенный transfer, затем публикация inventory

**Записи:** B148, B149. **Реестр:** B148=partial, B149=partial.
**Маршрут:** первый сбор Q14; historical C15; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAS-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAS-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Bad import не повреждает доступный старый blob/manifest. ExportA затем B не включает остатки A в B. Сбой до публикации оставляет старое valid поколение. Несколько маленьких файлов/tar заменяют массовое копирование CAS.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cas_02.py` → Q14 / C15

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cas_02.py
```

**Profile и доступность:** Python 3.14.x; uv extra test (pytest/runtime-http). No research extra identified..
**Карта поведения из статического исследования:** Existing behavioral tests use real FileSystemCAS import/export and assert old bytes/manifest survive bad import, exact A-then-B inventory, and publication rollback. Static inspection only; not executed.

**Дополнительные пробы / границы:**
- No extra B148/B149 probe identified statically; execute the whole file and retain complete output (P29).
- Ограничение: No test status claimed; command was not run.

<a id="cas-03"></a>

## CAS-03 — Одна проверка bytes и bounded batch verification

**Записи:** B152, B154, B155. **Реестр:** B152=partial, B154=partial, B155=partial.
**Маршрут:** первый сбор Q06; historical C09; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAS-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAS-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Hash/read counters показывают одну пригодную подготовку без доверия чужой версии. Corrupt item не уничтожает уже готовые результаты остальных. Iterable из десятков entries имеет малый pending cap. Отмена останавливает новую работу и сохраняет фактические результаты.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cas_03.py` → Q06 / C09

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cas_03.py
```

**Profile и доступность:** Python 3.14.x; uv extra test..
**Карта поведения из статического исследования:** Existing behavioral tests run real CAS integrity/signature/batch paths with counters and controlled iterables/threads. They prove snapshot reuse, local errors, bounded pending window, cancellation; they do not measure throughput or RSS. Not executed.

**Дополнительные пробы / границы:**
- No extra B152/B154/B155 probe identified statically; preserve bounded claim that an N-row report can itself scale with N.
- Retain full pytest output on execution (P29).
- Ограничение: No performance/RSS claim is established by counters; command not run.

<a id="cau-01"></a>

## CAU-01 — Standard DiD: допустимый дизайн, covariance и уровни CI

**Записи:** B204, B205, B206, LA-016. **Реестр:** B204=partial, B205=partial, B206=partial, LA-016=partial.
**Маршрут:** первый сбор Q01, Q14; historical C13, C17; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAU-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK05.

**Дискриминатор из owner-пакета:** Known ATT=3 сохраняется; t0=0 не даёт идентифицированный DiD-effect. Unit-cluster контроль не получает новую информацию от технического повторения периодов. Уровни 80/99% меняют границы при положительном SE;95% сохраняет допустимый прежний профиль. Малые панели и независимый statsmodels-reference, без утверждения о population coverage. Old/dedicated wrappers на одном effective request дают одинаковые значения/warnings после bugfix; старая обёртка не остаётся владельцем metadata. Снятие registration проверяет CAU-05.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cau_01.py` → Q14 / C17
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_did.py` → Q01 / C13

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cau_01.py tests/unit/foundry/methods/catalog/causal/test_did.py
```

**Profile и доступность:** Python 3.14.x; uv extras test + research (research supplies analytics/statsmodels)..
**Карта поведения из статического исследования:** Real standard DiD/RDD estimator and dispatcher tests, with independent statsmodels covariance reference, duplicate-period counterexample, confidence-level changes, known-ATT control, and old/dedicated metadata checks. No population-coverage claim. Not executed.

**Дополнительные пробы / границы:**
- No additional B204/B205/B206 or CAU-01 phase-1 LA probe identified statically; LA-016 closure remains CAU-05.
- Ограничение: Small panels do not attest CI population coverage; command not run.

<a id="cau-02"></a>

## CAU-02 — Staggered DiD: единицы, H0 и anticipation

**Записи:** B207, B208, B209. **Реестр:** B207=partial, B208=partial, B209=partial.
**Маршрут:** первый сбор Q01, Q19; historical C03, C13; дополнительно по готовности новых проб. **Checkpoint:** CP5. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAU-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAU-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Одна ATT(g, t) ячейка с варьирующими единицами не имеет искусственно точный[5,5]. Корректный нулевой тест отделён от доли |boot|>=|att|. При anticipation=1 уже затронутая когорта не используется как чистый control; a=0 сохраняет нормальный путь. Механические unit-тесты малы; bounded независимый null/coverage smoke только K5.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cau_02.py` → Q19 / C03
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_did.py` → Q01 / C13

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cau_02.py tests/unit/foundry/methods/catalog/causal/test_did.py
```

**Profile и доступность:** Python 3.14.x; uv extra test; NumPy is base dependency..
**Карта поведения из статического исследования:** Tests dispatch through real registered staggered estimator with deterministic panels/seeds; check unit resampling posture, not-established inference and anticipation/control eligibility. No calibrated CI/p-value claim. Not executed.

**Дополнительные пробы / границы:**
- If product claims calibrated CI/p-values, add the bundle's independent null/coverage K5 via real estimator. Current point-only/not-established behavior is the honest bounded result.
- Ограничение: Inference calibration/coverage remains unestablished by design; command not run.

<a id="cau-03"></a>

## CAU-03 — RDD: честная RBC capability и линейная память WLS

**Записи:** B210, B211. **Реестр:** B210=partial, B211=partial.
**Маршрут:** первый сбор Q17; historical C02; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAU-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAU-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Curved data с requested correction не даёт прежний uncorrected результат под флагом True. Uncorrected допустим отдельно. На 400 точках weighted-vector formula сохраняет point/SE и не создаёт 400×400. Kernel/order/rank и nonpositive-bandwidth контроли. Настоящий RBC-профиль — ограниченный K5, не повторные установки библиотек каждым агентом.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cau_03.py` → Q17 / C02
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cau_03.py tests/unit/foundry/methods/catalog/causal/test_rdd.py
```

**Profile и доступность:** Python 3.14.x; uv extra test; NumPy base dependency..
**Карта поведения из статического исследования:** Pure_step fail-closed/RBC-profile and known-jump tests use real estimator. The 400-point independent WLS reference and no-diagonal/pinv-count test call the private fit helper directly. Not executed.

**Дополнительные пробы / границы:**
- P29/P38: add bounded 400/800-point memory witness through RegressionDiscontinuity.pure_step; helper-only test could stay green if the estimator stopped calling the helper.
- RBC is honestly unsupported/fail-closed; a real RBC reference is required only before claiming RBC capability.
- Ограничение: Full estimator path is not the current memory test subject; RBC procedure not attested; command not run.

<a id="cau-04"></a>

## CAU-04 — DoWhy: реальный estimand и point-only результат

**Записи:** B212, B213. **Реестр:** B212=partial, B213=partial.
**Маршрут:** первый сбор Q07; historical C02; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAU-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Recorder point=7 без CI не создаёт 7±epsilon. Настоящий interval[5,9] сохраняется. NIE-request не выдаёт backend-defaultATE под новой подписью; unsupported profile — точный capability-result. Native DTO тест обязателен; один действительный DoWhy smoke на K5. Proceed_when_unidentifiable=False остаётся.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cau_04.py` → Q07 / C02
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_identify_estimate.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cau_04.py tests/unit/foundry/methods/catalog/causal/test_dowhy_identify_estimate.py
```

**Profile и доступность:** Python 3.14.x; uv extra test; research does not install DoWhy for >=3.13; real backend requires pre-provisioned <=3.12 causal-dowhy environment (not installed here)..
**Карта поведения из статического исследования:** Recorder tests exercise real adapter entry point while replacing only DoWhy loader: they prove point/CI and argument/estimand binding, not external DoWhy inference. Native real-backend tests importorskip DoWhy. Not executed.

**Дополнительные пробы / границы:**
- Real DoWhy K5 confounding/estimand smoke is needed for external backend claim; unavailable in supported Python 3.14 profile because causal-dowhy markers are python_version < 3.13. importorskip is skipped, never a real-backend green receipt.
- Keep unsupported estimand fail-closed; recorder does not prove backend behavior.
- Ограничение: Supported 3.14 profile cannot establish external DoWhy/estimand behavior; command not run.

<a id="cau-05"></a>

## CAU-05 — DiD: dedicated planning, old-slot replay и retirement umbrella

**Записи:** LA-016. **Реестр:** LA-016=partial.
**Маршрут:** первый сбор Q01, Q06; historical C05, C13; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAU-05.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CAU-01, CAU-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Old/dedicated equivalent inputs совпадают после CAU-01/02, shared assumptions/equations доступны без deprecated metadata owner. Unsupported slot/mode не превращается в другой estimator. Registry больше не предлагает retired generic для новых plans; supported historical replay сохранён.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cau_05.py` → Q06 / C05
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_registration.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_did.py` → Q01 / C13

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cau_05.py tests/unit/foundry/methods/catalog/causal/test_registration.py tests/unit/foundry/methods/catalog/causal/test_did.py
```

**Profile и доступность:** Python 3.14.x; uv extras test + research for causal registry bootstrap..
**Карта поведения из статического исследования:** Direct legacy slot/flag adapter comparisons and dedicated dispatcher tests use real methods. Registry test asserts exact causal.inference names plus dedicated did namespace. Not executed.

**Дополнительные пробы / границы:**
- Add a real frozen-plan/versioned replay probe for old FQN/old slots through canonical planning/resolution bridge; direct compatibility-class calls do not prove persisted-plan resolution.
- Preserve registry negative assertion and verify no alternate registration path accepts generic FQN.
- Ограничение: No frozen historical-plan bridge test identified in the full tracked Python census; command not run.

<a id="cli-01"></a>

## CLI-01 — Runtime client: package-owned генерация и снятие raw committed surface

**Записи:** LA-043, LA-044. **Реестр:** LA-043=partial, LA-044=partial.
**Маршрут:** первый сбор Q07, Q15; historical C01, C17; дополнительно D04. **Checkpoint:** CP6. **Исследователь:** e02_03.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CLI-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK16, LK21, LK22, LK23.

**Дискриминатор из owner-пакета:** Один bounded frozen install при реальной необходимости и одна full-family регенерация в N/CP6. Public operation/type surface, binary response/exposure headers, query/path/body/errors, discriminated aliases; corruption/missing/extra каждого supported output, custom OpenAPI и UNRUN. Isolated output root, canonicalizer idempotency/collision guard; consumer без dashboard runtime. Не считать byte equality исполнением всех endpoints.

**Существующие пути на research SHA:**
- `policy-engine/packages/runtime-api-client/remediation.test.mjs` → отдельная дельта, вне исторической матрицы
- `policy-engine/packages/runtime-api-client/runtimeApiClient.test.mjs` → отдельная дельта, вне исторической матрицы
- `policy-engine/packages/runtime-api-client/scripts/canonicalize-runtime-client.test.mjs` → отдельная дельта, вне исторической матрицы
- `policy-engine/packages/runtime-api-client/scripts/normalize-recursive-openapi-types.test.mjs` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/repo_quality/tools/test_runtime_contract_measurement.py` → Q07 / C01
- `policy-engine/tests/repo_quality/tools/test_generated_client_station.py` → Q15 / C17

```bash
.venv/bin/python -m pytest -c pytest.ini tests/repo_quality/tools/test_runtime_contract_measurement.py tests/repo_quality/tools/test_generated_client_station.py
```

**Другие native-команды (кандидаты, проверить profile):**
- cd policy-engine && corepack pnpm --filter @polisyos/runtime-api-client run test
- cd policy-engine && corepack pnpm --filter @polisyos/runtime-api-client run test:remediation
- cd policy-engine && corepack pnpm --filter @polisyos/runtime-api-client run check:architecture

**Profile и доступность:** Node >=22 <23, Corepack/pnpm workspace dev dependencies; Fresh checkout prerequisite: corepack pnpm install --frozen-lockfile (not run); Python contract checker: uv extras runtime + ml; node_modules and .venv directories present at inspected SHA..
**Карта поведения из статического исследования:** Node cases exercise canonical client request behavior, canonicalizer/recursive schemas, custom --openapi with isolated output root, and no raw committed twins. Real Python freshness checker invokes actual generator into temp root and checks exact output set/bytes; checker unit tests mock producer, so use live command for deciding receipt. Not all endpoints are semantically exercised. Not executed.

**Дополнительные пробы / границы:**
- P29/P35/P37: reconcile generated_artifacts.toml outputs, checker expected_outputs, and actual output set. Pinned SHA lists exactly types.ts, canonicalRuntimeApiClient.ts/js, but checker holds a code-owned tuple.
- Add isolated negative family witnesses: each of 3 outputs missing/corrupt, plus unexpected output; assert real checker fails or reports UNRUN. Current mocked checker tests cover pass/byte drift, not full matrix.
- P38 divergence: byte equality may pass with semantically wrong endpoint; retain actual client behavior tests and bound freshness claim to freshness only.
- No install/build/full-family generation was run in this research pass.
- Ограничение: Full per-output missing/extra/corruption adversarial test matrix absent from listed tests.
- Ограничение: Byte parity does not prove all endpoints; command set was not run.

<a id="cmp-01"></a>

## CMP-01 — Импорт, effective DAG и единый payload исполнителей

**Записи:** B42, B43, B44. **Реестр:** B42=partial, B43=partial, B44=partial.
**Маршрут:** первый сбор Q20; historical C06; дополнительно D04. **Checkpoint:** CP1. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CMP-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Два свежих процесса с обратным порядком импорта получают рабочий wrapper. Build→freeze→execute: B.requires(A) соблюдается без data-flow ребра; независимый сосед параллелен. window=20 доходит в async без ручного повторного override; cycle выявлен до исполнения.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cmp_01.py` → Q20 / C06
- `policy-engine/tests/unit/foundry/methods/test_composer.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cmp_01.py tests/unit/foundry/methods/test_composer.py
```

**Profile и доступность:** Pre-provisioned test environment; no new extra justified for these focused unit selectors..
**Карта поведения из статического исследования:** Direct CMP regression source is present and tracked at the pin, but unexecuted. The adjacent composer suite covers build/order basics; neither source presence nor an eventual pass establishes full runtime closure.

**Дополнительные пробы / границы:**
- B42: inject an internal module-initialization failure and prove the common wrapper propagates it distinctly from a genuinely missing optional dependency; current subprocess cases exercise both import orders only.
- B43: drive an actual async composition with an independent sibling and a synchronization barrier to prove overlap; the current level assertion proves the sibling is eligible for the same level, not that execution overlaps. Also retain a failure case against silent sequential fallback if that fallback remains reachable.
- B44: add an adversarial unknown override / invalid seed control if the parameter builder contract is widened; current test covers static window=20, dynamic scale, and an allowed per-call override.
- Ограничение: The assignment card says the regression destination is proposed, but test_cmp_01.py is already tracked at the source pin. No test result, process log, or full async concurrency evidence was collected.

<a id="cmp-02"></a>

## CMP-02 — Однозначные slots и ordering по occurrence

**Записи:** B45, B46. **Реестр:** B45=partial, B46=partial.
**Маршрут:** первый сбор Q15; historical C17; дополнительно D04. **Checkpoint:** CP1. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CMP-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CMP-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Два источника одного scalar-slot не зависят от UUID; разные slots работают. estimate1→sensitivity→estimate2 не отвергается; sensitivity1→estimate→sensitivity2 не скрывает раннее нарушение. Проверить strict/warning режимы и явный merge.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cmp_02.py` → Q15 / C17
- `policy-engine/tests/unit/foundry/methods/test_composer.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/methods/test_semantic_validator.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cmp_02.py tests/unit/foundry/methods/test_composer.py tests/unit/foundry/methods/test_semantic_validator.py
```

**Profile и доступность:** Pre-provisioned test environment; no new extra justified for these focused unit selectors..
**Карта поведения из статического исследования:** Direct CMP regression source is present and tracked at the pin, but unexecuted. It covers warn/strict producer conflicts and repeated-FQN ordering examples.

**Дополнительные пробы / границы:**
- B45: permute producer insertion order and UUIDs while assigning distinct values, then exercise the real consumer to prove no last-wins result depends on UUID/order. Current conflict tests assert warn/strict diagnostics, not value selection under permutations.
- B45: make the explicit merge control execute and assert both source values are consumed; current test validates its graph shape and absence of duplicate-producer warnings.
- B46: add a MethodComposer-built chain with repeated method occurrences and run the validator on the compiled chain; the current repeated-FQN cases use a minimal SimpleNamespace chain protocol.
- Ограничение: The assignment card says the regression destination is proposed, but test_cmp_02.py is already tracked at the source pin. UUID/order-invariant value behavior and a built-chain validator path remain unestablished by the inspected tests.

<a id="cmp-03"></a>

## CMP-03 — Полное и семантически одинаковое ручное/автоматическое связывание

**Записи:** B47, B48. **Реестр:** B47=partial, B48=partial.
**Маршрут:** первый сбор Q15; historical C08; дополнительно D04. **Checkpoint:** CP1. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CMP-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CMP-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Flexible source связывается со вторым обязательным входом, fixed — с первым; полное решение найдено. Переименование нейтральных slots не меняет существование решения. Auto и explicit одинаково отвергают запрещённую семантику и неполноту.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cmp_03.py` → Q15 / C08
- `policy-engine/tests/unit/foundry/methods/test_linker.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/methods/test_semantic_validator.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cmp_03.py tests/unit/foundry/methods/test_linker.py tests/unit/foundry/methods/test_semantic_validator.py
```

**Profile и доступность:** Pre-provisioned test environment; no new extra justified for these focused unit selectors..
**Карта поведения из статического исследования:** Direct CMP regression source is present and tracked at the pin, but unexecuted. Matching, semantic parity, completeness, and unit/shape/contract controls are directly represented.

**Дополнительные пробы / границы:**
- B47: test source/target permutation and an ambiguous multiple-complete-match case; leave semantically ambiguous choices unresolved instead of selecting an arbitrary complete matching.
- B48: add more than one forbidden semantic class and a partial-link case to show the shared auto/explicit rule generalizes beyond the current outcome-to-treatment mismatch and incomplete assignment.
- Exercise the final composed DAG after successful repair and rejection, so a locally valid edge set cannot leave a globally invalid graph.
- Ограничение: The assignment card says the regression destination is proposed, but test_cmp_03.py is already tracked at the source pin. The tests do not establish runtime behavior until executed, and matching ambiguity / permutation cases remain untested.

<a id="ctl-01"></a>

## CTL-01 — Search run-state: исправление fresh/empty и извлечение владельца состояния

**Записи:** B118, B119, LA-015. **Реестр:** B118=partial, B119=partial, LA-015=partial.
**Маршрут:** первый сбор Q05, Q06, Q11, Q17; historical C01, C03, C05, C08; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CTL-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: OPT-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Два независимых run эквивалентны двум свежим владельцам, прежняя история неизменна. Persistent empty завершается адресно; transient empty→candidate работает. На relocation-коммите прежние traces совпадают; на bugfix-коммите меняются ровно fresh/empty контрпримеры.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/search/test_search_loop.py` → Q05 / C08
- `policy-engine/tests/unit/scientist/search/strategies/test_controller_batch.py` → Q11 / C01
- `policy-engine/tests/unit/remediation/test_srv_01.py` → Q17 / C05
- `policy-engine/tests/unit/remediation/test_srv_03.py` → Q06 / C03

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ctl_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/search/test_search_loop.py tests/unit/scientist/search/strategies/test_controller_batch.py tests/unit/remediation/test_srv_01.py tests/unit/remediation/test_srv_03.py
```

**Profile и доступность:** Pre-provisioned test environment; test extra. The selected controller/strategy tests are local and need no cloud client..
**Карта поведения из статического исследования:** No test_ctl_01.py exists at the pin. Existing canonical methods/search tests directly exercise repeated fresh runs, stable prior results, empty generation transitions, and ask/tell; LA-015 remains a multi-stage migration and CTL-01 covers only its state/transition stage.

**Дополнительные пробы / границы:**
- B118: rerun two different requests through the production caller and prove prior result/history/frontier snapshots remain byte-stable after the second run and after caller mutation.
- B119: preserve cancellation/generator-error reason after an empty attempt; current direct tests cover transient empty-to-candidate and bounded persistent-empty exhaustion, not the full cancellation/error combination.
- LA-015: census all production callers and old serialized-history/import consumers, prove the actual caller cutover to the native service, and verify the predecessor cannot remain the default. Do not mark LA-015 closed from protocol presence or CTL-01 alone.
- Ограничение: No bundle-named regression file exists. LA-015 explicitly assigns full caller cutover/retirement to SRV-03; full closure is not established by this bundle or these unexecuted tests.

<a id="ctl-02"></a>

## CTL-02 — Содержательные даты и воспроизводимый RNG/checkpoint

**Записи:** B124, B125, B126. **Реестр:** B124=partial, B125=partial, B126=partial.
**Маршрут:** первый сбор Q05, Q06, Q15; historical C03, C04, C10; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CTL-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: OPT-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Разные starts_at в содержательном кандидате дают разные identities; audit timestamp не меняет предмет. JSON round-trip восстанавливает Random sequence. Один batch и несколько batches после restore дают один Sobol-префикс; несовместимый legacy checkpoint имеет точный исход.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/search/test_frontier.py` → Q06 / C04
- `policy-engine/tests/unit/scientist/search/strategies/test_random_grid.py` → Q15 / C10
- `policy-engine/tests/unit/scientist/search/strategies/test_space_codec.py` → Q05 / C03

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ctl_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/search/test_frontier.py tests/unit/scientist/search/strategies/test_random_grid.py tests/unit/scientist/search/strategies/test_space_codec.py
```

**Profile и доступность:** Pre-provisioned test environment; test extra. No cloud service is involved..
**Карта поведения из статического исследования:** No test_ctl_02.py exists at the pin. Existing tests directly cover semantic starts_at identity, JSON Python-RNG round-trip, Sobol batch/checkpoint prefix stability, and legacy checkpoint rejection; unexecuted.

**Дополнительные пробы / границы:**
- B124: test other semantic time roles and nested/multiple interventions, while changing audit/generated timestamps independently; current semantic-date case is one starts_at field.
- B125: keep the positive next-value equality across a fresh process boundary and exercise malformed/truncated RNG state in addition to version mismatch.
- B126: verify the public suggest/batch API gives identical Sobol prefixes for one batch, split batches, cache reordering, and restore; current test calls the internal candidate helper for its stream assertions.
- Ограничение: No bundle-named regression file exists. Current tests are targeted but do not cover the broader temporal-field set or an external fresh-process restore.

<a id="ctl-03"></a>

## CTL-03 — Search transition: стоимость, счётчики и typed eligibility

**Записи:** B120, B121, B123. **Реестр:** B120=partial, B121=partial, B123=partial.
**Маршрут:** первый сбор Q05, Q11, Q17, Q19, Q20; historical C01, C05, C08, C13; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CTL-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CTL-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Cost виден stopping и report; warm history не съедает бюджет новых оцениваний в таком профиле; sentinel расходует ресурс, не обучает surrogate. Malformed present typed vector не выбирает legacy scalar fallback; законный legacy without typed остаётся рабочим.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/search/test_search_loop.py` → Q05 / C08
- `policy-engine/tests/unit/scientist/search/test_cost_stopping.py` → Q19 / C13
- `policy-engine/tests/unit/scientist/search/test_sentinels.py` → Q20 / C08
- `policy-engine/tests/unit/scientist/search/strategies/test_controller_batch.py` → Q11 / C01
- `policy-engine/tests/unit/remediation/test_srv_01.py` → Q17 / C05

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ctl_03.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/search/test_search_loop.py tests/unit/scientist/search/test_cost_stopping.py tests/unit/scientist/search/test_sentinels.py tests/unit/scientist/search/strategies/test_controller_batch.py tests/unit/remediation/test_srv_01.py
```

**Profile и доступность:** Pre-provisioned test environment; test extra. No cloud service is involved..
**Карта поведения из статического исследования:** No test_ctl_03.py exists at the pin. Adjacent controller and service tests directly exercise cost snapshots, warm-history counters, sentinel exclusion, and malformed typed feedback; unexecuted.

**Дополнительные пробы / границы:**
- B120: assert one measured owner spend is the same value seen by the stopping decision and final report, including unavailable/malformed cost inputs; direct source has a positive spend/report case and component missing-cost case.
- B121: combine a warm history and sentinel with a real cost-bearing evaluator; assert the sentinel consumes the cost/resource budget, does not enter ordinary history or surrogate training, and warm history does not count against new-evaluation budget.
- B123: mutate a present typed vector into wrong shape/version/foreign binding while keeping a valid legacy scalar; prove fail-closed and contrast with the genuinely absent typed field legacy path.
- Ограничение: No bundle-named regression file exists. The main missing integration is the sentinel-cost/warm-history composition with the actual budget owner; per-card 'cost is visible in stopping and report' is only covered for ordinary evaluator spend in the inspected case.

<a id="cyc-01"></a>

## CYC-01 — Штатный вход и связанные контексты N4/N5

**Записи:** B01, B02, B03. **Реестр:** B01=partial, B02=partial, B03=partial.
**Маршрут:** первый сбор Q01, Q09, Q10; historical C03, C06, C15; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK02, LK17.

**Дискриминатор из owner-пакета:** Штатный вход без вручную собранного Python-context доходит до настоящего разрешённого N5. Изменение problem/model/catalog binding отвергается. Отсутствующие параметры не становятся нулями. В локальном тесте использовать настоящий builder/DTO и захват границы вызова; численный результат и CAS-readback проверяет K1.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py` → Q09 / C15
- `policy-engine/tests/unit/runtime/http/test_control_service_di.py` → Q10 / C06
- `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py` → Q01 / C03

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_cyc_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py tests/unit/runtime/http/test_control_service_di.py tests/unit/runtime/quality/test_generation_cycle.py
```

**Profile и доступность:** Pre-provisioned test + runtime test environment (test extra includes runtime-http); no live cloud/model/API dependency is demonstrated or required by the inspected fixtures..
**Карта поведения из статического исследования:** No test_cyc_01.py exists at the pin. Existing tests provide a useful served-route/context handoff and N5 DTO/request capture under a controlled synthetic profile, plus a contextless fail-before-N4 negative; this is partial and unexecuted.

**Дополнительные пробы / границы:**
- B01: exercise the ordinary user-facing input route without a manually supplied Python context, preserve early access control, and show the compiled DesignProblem is bound before N4/N5.
- B02: compare the persisted CycleSubstrateContext artifact/ref and its job/run/problem/model/catalog bindings at HTTP admission, recursive owner, N6, and N5; tamper each binding one at a time and assert refusal before engine execution.
- B03: capture the actual CandidateSimulationN5InputV5 builder output and downstream request with required horizon/resource fields omitted; prove absence stays typed/unavailable and never silently becomes numeric zero. Existing served fixture captures DTO and selected refs but does not show this missing-parameter falsifier.
- Keep fixture bundle, synthetic model, and contract-testing profile explicitly limited; a local test must not be described as accessible empirical data or production authorization.
- Ограничение: The assigned proposed test path is absent. Current tests demonstrate a controlled synthetic-profile seam, not full ordinary production input, all binding mutations, or omitted-parameter semantics; no test output or runtime event was collected.

<a id="cyc-02"></a>

## CYC-02 — Читаемый численный результат и положительный условный N8

**Записи:** B04, B05, B08. **Реестр:** B04=partial, B05=partial, B08=partial.
**Маршрут:** первый сбор Q01, Q14, Q17; historical C03, C13, C20; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_04.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CYC-01, SIM-01, SIM-02, SIM-03. Protected controls: нет.

**Дискриминатор из owner-пакета:** Настоящий N5→adapter→N8 возвращает условный численный результат; readback в новом процессе сохраняет модель/ограничения. Повреждённый blob, чужая модель и недоступная ref отвергаются. Этот же K_sim не становится K_world или разрешением действия. Для этого пакета маленький native end-to-end выполняется до принятия, не откладывается только на финал.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cyc_02.py` → Q14 / C20
- `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py` → Q01 / C03
- `policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py` → Q17 / C13

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cyc_02.py tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_joint_simulation_horizon.py
```

**Profile и доступность:** Pre-provisioned test + runtime test environment; selected checks use local numerical execution and temp/local CAS. Do not add the broad research extra without evidence it is needed..
**Карта поведения из статического исследования:** Direct CYC-02 regression source is present and tracked at the pin; local N5-to-N8 conditional numeric result and CAS-integrity/readback cases are represented, but unexecuted. Fixtures explicitly remain synthetic/contract-testing and cannot establish empirical authority.

**Дополнительные пробы / границы:**
- B04: reopen the content-bound result from a fresh process/store view and compare model, atom, trajectory, and limitation fields; current CAS readback is exercised within a process.
- B05: retain K_sim as a usable simulation input while attempting each downstream authority/promotion/action consumer; assert the same simulation-only blocker remains and no K_world or action authority is minted.
- B08: preserve the positive conditional N8 number and add independent negative controls for missing/zero/comparator/replication/trajectory semantics, foreign model/catalog binding, malformed/absent ref, and altered result bytes. Current test already covers several ref/blob/WMR/atom failures, but not each N8 comparator/replication case in this focused file.
- Record the native numerical command's full output, selected model/catalog identity, content-bound CAS ref and fresh readback; do not infer this evidence from constructor or fixture-only tests.
- Ограничение: The assignment card says the regression destination is proposed, but test_cyc_02.py is already tracked at the source pin. Fresh-process readback and the complete authority/promotion refusal chain remain unproved by the tests inspected here; no native command receipt exists in this research.

<a id="cyc-03"></a>

## CYC-03 — Идентичность содержательной второй итерации

**Записи:** B09, B27, B28. **Реестр:** B09=open, B27=partial, B28=partial.
**Маршрут:** первый сбор Q01, Q09; historical C03, C15; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CYC-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Тот же кандидат на новой версии данных переоценивается и имеет новый occurrence; прежняя попытка остаётся читаемой. Новый UUID при тех же inputs не создаёт бесконечное исследование. Изменённая популяция/модель не использует старое основание. В K1 проверить T2 на настоящем входе.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py` → Q01 / C03
- `policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py` → Q09 / C15

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_cyc_03.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py
```

**Profile и доступность:** {"expected_artifacts": ["GenerationCycleRun.candidate_summaries contains two occurrences for the same candidate_id with distinct content_hash and cycle_index.", "Run cycles retain design_problem_ref history; changed population/model produces a different binding ref/hash and candidate_occurrence_ref.", "UUID/timestamp-only retry ends blocked with no_retry_without_new_grammar."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Behavioral controller/unit tests plus in-memory CAS promotion-context test; synthetic generator, not domain T2.

**Дополнительные пробы / границы:**
- B09: run T2 on a real input where data/model/method basis changes without grammar expansion; retain old attempt and show same inputs under a new UUID/timestamp are blocked.
- B27: change the revised task/population/model in a recursive second cycle and prove each downstream binding resolves to the matching task version.
- B28: for one candidate_id with two content versions, assert history keeps both while the current front and downstream consumer resolve specifically to the newest candidate_occurrence_ref.
- Ограничение: Proposed tests/unit/remediation/test_cyc_03.py does not exist at this SHA.
- Ограничение: The same-candidate test asserts one front candidate_id, not that the front/promotion consumer resolves to the second occurrence.
- Ограничение: B27 source card says the full second-cycle scenario was not previously run; current recursive leaf test uses contract-testing generator fixtures, not T2 production input.

<a id="cyc-04"></a>

## CYC-04 — Пригодные альтернативы и исследовательский бюджет

**Записи:** B10, B11. **Реестр:** B10=partial, B11=partial.
**Маршрут:** первый сбор Q01, Q04, Q18; historical C09, C19; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CYC-03. Protected controls: нет.

**Дискриминатор из owner-пакета:** Первый кандидат blocked, второй пригоден — исполняется второй; исходный blocker сохранён. Разрешённая информативная проверка не отклоняется только по неопределённой денежной VOI; исчерпание действительного бюджета останавливает новую работу.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cyc_04.py` → Q01 / C19
- `policy-engine/tests/unit/scientist/search/test_voi_scheduler.py` → Q04 / C19
- `policy-engine/tests/unit/scientist/orchestration/engine/test_budget_middleware.py` → Q18 / C09

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cyc_04.py tests/unit/scientist/search/test_voi_scheduler.py tests/unit/scientist/orchestration/engine/test_budget_middleware.py
```

**Profile и доступность:** {"expected_artifacts": ["Public GenerationCycleRun selects usable-second, preserves blocked-first in candidate_summaries with issue codes/report_ref, and simulation is for usable-second.", "VOI decision records scheduler_action/reason; budget exhaustion yields simulation_blocked and budget_exhausted_for_next_level."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Behavioral candidate-selection tests, scheduler unit tests, and budget-owner unit tests; no live acquisition.

**Дополнительные пробы / границы:**
- B10: keep first candidate blocked with a typed reason, run the next grounded candidate, and retain the blocker in the public run artifact.
- B11: exercise SimpleVOIScheduler with expected improvement below min_roi_threshold and positive expected_information_gain; assert advance_by_information_value, while zero information gain rejects and insufficient real budget defers.
- Ограничение: The CYC-04 suite tests the generation-cycle scheduler, not the target SimpleVOIScheduler low-ROI/positive-information branch in scientist/methods/search/voi_scheduler.py.
- Ограничение: BudgetMiddleware and ledger tests are separate from candidate scheduling; no test proves the shared lifecycle budget owner is the budget consumed by this alternative path.

<a id="cyc-05"></a>

## CYC-05 — Правдивые лимиты, завершение и структурная проверка

**Записи:** B15, B29, B30. **Реестр:** B15=partial, B29=partial, B30=partial.
**Маршрут:** первый сбор Q01, Q03; historical C03, C17; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-05.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CYC-02, CYC-03. Protected controls: нет.

**Дискриминатор из owner-пакета:** Два содержательных дочерних узла сохраняют отношения и результат. Stop стабильного фронта не становится abstained в соседней проекции. Нет src — нет положительного structural evidence. Неизменная сборка не сканируется повторно; значимое изменение не переиспользует старое свидетельство.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_cyc_05.py` → Q03 / C17
- `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py` → Q01 / C03

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_cyc_05.py tests/unit/runtime/quality/test_generation_cycle.py
```

**Profile и доступность:** {"expected_artifacts": ["HTTP progress reports requested_max_iterations=7, effective_max_iterations=3, typed RecursiveCycleBudget, clamp_reason, and recursive_budget_application_status.", "Recursive graph contains two parent_child_edges; output includes joint_simulation_ref and composition certificate/readback.", "StrangleReceipt.status/source_state/content hash/parse_errors distinguish not_established, parse_error, drift, and strangled.", "Cycle terminal_kind, refinement decision, and search_iteration.status keep stop distinct from abstention."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Behavioral HTTP progress, recursive graph/N5 fixture integration, terminal projection, and source-census/removal probes.

**Дополнительные пробы / границы:**
- B15: preserve requested/effective limits and execute a small two-child decomposition through the real graph/N5 path.
- B29: retain distinct frontier_stable, grounded_admissible, budget_exhausted, and grounded_abstention semantics across terminal/refinement/search projections.
- B30: distinguish missing source, syntax error, and direct prohibited caller; prove unchanged source reuse/currentness and changed-source invalidation.
- Ограничение: HTTP test explicitly records not_applied_n4_proposal_only; the two-child test consumes fixture-created children, so there is no single end-to-end request-to-generated-recursion proof.
- Ограничение: The receipt is a direct AST census over src/polisyos, not deployed-build/runtime reachability; code declares build_identity_unavailable, deployment_identity_unavailable, and alias_and_dynamic_calls_not_established. Example P38 divergence: aliasing loop.run_fixture then calling the alias may evade a direct-symbol census.

<a id="ddm-01"></a>

## DDM-01 — DDM: один event/budget owner и lazy parent facade

**Записи:** LA-056. **Реестр:** LA-056=partial.
**Маршрут:** первый сбор Q12, Q17; historical C04, C08; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DDM-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK01, LK14, LK33, LK34, LK35.

**Дискриминатор из owner-пакета:** Contract-only import с monitor trap не загружает orchestration; root API, все enum/classes, native model validation и JSON forms сохраняются. Проверить __module__/FQN/pickle/schema introspection, когда реально используются. Ручной Shift schema anyOf по p/e/ert сохраняется: generic generated schema не полная замена; reversed window остаётся runtime-check.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/ddm/test_facade.py` → Q12 / C04
- `policy-engine/tests/unit/ddm/test_readiness_mapping.py` → Q17 / C08
- `policy-engine/tests/unit/ddm/mirror_contracts/test_events.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ddm_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/ddm/test_facade.py tests/unit/ddm/test_readiness_mapping.py tests/unit/ddm/mirror_contracts/test_events.py
```

**Profile и доступность:** {"expected_artifacts": ["Canonical event DTOs live in ddm/contracts/events.py; MetricBudgetPolicy lives in ddm/contracts/metric_budget.py.", "Root and integration facades lazily expose orchestration and forward the same contract class objects.", "Contract probe prints contract-only and confirms monitor/incident/model_registry were not loaded."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Fresh-process import-boundary probe, facade identity/validator checks, and canonical budget-owner unit test.

**Дополнительные пробы / границы:**
- LA-056: verify contract-only import with orchestration import trapped; root/integration compatibility aliases are the same class objects; preserve event validators, aliases, and hand-maintained schema semantics.
- LA-056: inventory actual serialized FQNs/pickle/schema consumers before deciding whether class __module__ migration needs compatibility work.
- Ограничение: No current remediation/test_ddm_01.py.
- Ограничение: Facade tests cover selected event classes, not class FQN/pickle compatibility for DTOs or generated-schema parity with shift_event.schema.json's manual anyOf requirement.
- Ограничение: Import trap asserts a bounded set of orchestration modules, not every possible runtime dependency.

<a id="ddm-02"></a>

## DDM-02 — DDM: актуальное основание и единый gate с R2 override

**Записи:** LA-054, LA-055. **Реестр:** LA-054=partial, LA-055=partial.
**Маршрут:** первый сбор Q09, Q14, Q17; historical C08, C17, C20; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DDM-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: DDM-01. Protected controls: LK01, LK14, LK33, LK34, LK35.

**Дискриминатор из owner-пакета:** Before/after expiry; model-change trigger; чужая model/regime/calibration/metric budget; позднее событие в разрешённом окне; unavailable feed против observed empty-alert window. Матрица: R4/R3 с veto не разрешены; R2 только с допустимым signoff; R1/R0 и failed certificate не разрешены даже с signoff. Проверить причины/сроки/версию policy и действительные native models, не fixture verdict. Реальный deployment не вызывается.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/ddm/test_full_acceptance.py` → Q09 / C20
- `policy-engine/tests/unit/ddm/test_stationary_replay.py` → Q14 / C17
- `policy-engine/tests/unit/ddm/test_readiness_mapping.py` → Q17 / C08

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ddm_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/ddm/test_full_acceptance.py tests/unit/ddm/test_stationary_replay.py tests/unit/ddm/test_readiness_mapping.py
```

**Profile и доступность:** {"expected_artifacts": ["CalibrationValidityProjection carries report_digest, verifier_id/version, effective_at, valid_until, configured/observed triggers, status, reasons.", "ModelRegistryReadinessRecord round-trip loses private checker authority and fails closed until exact report/audit/time/trigger rebind; RegistryGateDecision reports reason and required_actions.", "R4/R3 persisted veto remains binding; R2 signoff is a limited exception; R1/R0 and failed FP certificate remain blocked."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Behavioral calibration validity, identity-binding, serialized readback/rebind, and readiness-gate unit tests on synthetic streams/models.

**Дополнительные пробы / границы:**
- LA-054: independently reconcile trigger-feed completeness/arrival against the declared observed-trigger list; falsify an empty-list declaration while leaving it intact and confirm an authority-grade gate cannot go green.
- LA-054/055: exercise late event inside the declared permitted window and unavailable feed versus independently observed empty window through the real registry consumer.
- LA-055: bind policy identity/version into the decision/readback; classify owner_signoff provenance before treating caller-supplied bool as any authority evidence.
- Ограничение: Tests use synthetic calibration/model records; they do not run native deployed models, an external registry persistence service, or deployment actions.
- Ограничение: P37: observed_invalidation_triggers=[] is classified observed based on argument presence; source/feed completeness is caller-supplied and not independently reconciled. owner_signoff is also a bool with no verifier provenance.
- Ограничение: Readiness policy YAML is not an executable/version-bound decision artifact; record/gate do not carry its policy version.
- Ограничение: No explicit registry-gate test for late-arriving event within an allowed window was found; delayed-label replay tests cover a separate label path.

<a id="dfi-01"></a>

## DFI-01 — Core sources: самостоятельные writer/validator/loader dependencies

**Записи:** LA-038. **Реестр:** LA-038=partial.
**Маршрут:** первый сбор Q05, Q07, Q18, Q19; historical C11, C15, C17, C18; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DFI-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK19.

**Дискриминатор из owner-пакета:** Canonical leaf-вызов работает без старого facade bootstrap; две зависимости с одинаковым именем не перезаписываются соседним вызовом. Реальные source profiles, запросы, bytes, ошибки и counts сохраняются на малых fixtures. Sync/async signature и тестовые substitutions получают явный адрес; отдельный negative доказывает отсутствие global broadcast для группы.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/data_forge/domains/catalog/batch/core_sources/test_loaders.py` → Q07 / C18
- `policy-engine/tests/unit/data_forge/domains/catalog/batch/core_sources/test_writers.py` → Q05 / C15
- `policy-engine/tests/unit/data_forge/domains/catalog/batch/core_sources/test_validators.py` → Q18 / C17
- `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py` → Q19 / C11

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_dfi_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/data_forge/domains/catalog/batch/core_sources/test_loaders.py tests/unit/data_forge/domains/catalog/batch/core_sources/test_writers.py tests/unit/data_forge/domains/catalog/batch/core_sources/test_validators.py tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py
```

**Profile и доступность:** {"expected_artifacts": ["Facade _sync_implementation_globals is a no-op; test marker remains absent from loaders/validators/writers.", "Standalone loaders/writers/validators resolve transformer dependency without facade bootstrap.", "Synthetic ingest writes ds_registry_datasets, ds_variable_alignments, ds_observations and returns positive stats."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Leaf dependency/compatibility unit tests plus synthetic DuckDB persistence test.

**Дополнительные пробы / границы:**
- LA-038: complete the actual cross-leaf dependency and monkeypatch-target inventory before retiring compatibility bindings; prove no sibling call can overwrite a leaf dependency.
- LA-038: preserve source request/filter/profile, sync/async behavior, writes, errors, and counts for the chosen leaf group.
- Ограничение: No current remediation/test_dfi_01.py.
- Ограничение: Behavioral isolation tests cover the writer/validator/loader group, not a complete independently enumerated cross-leaf inventory for all six modules.
- Ограничение: Persistence test uses synthetic responses and temporary DuckDB; it does not verify live source requests.

<a id="dfi-02"></a>

## DFI-02 — Core sources: API cutover без обратной синхронизации globals

**Записи:** LA-038. **Реестр:** LA-038=partial.
**Маршрут:** первый сбор Q18, Q19; historical C01, C11; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DFI-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: DFI-01. Protected controls: LK19.

**Дискриминатор из owner-пакета:** Один настоящий batch consumer без предварительного legacy import; sync/async, budget/lease/profile handoff, ошибок и counters parity. Добавленный атрибут фасада не попадает в leaves; изменение leaf dependency не стирается следующим вызовом. Два контролируемых вызова с разными зависимостями изолированы. Source-selection DFK-02 не теряет filters при совместной приёмке.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_dfi_02.py` → Q18 / C01
- `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py` → Q19 / C11
- `policy-engine/tests/unit/data_forge/domains/catalog/batch/core_sources/test_api.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_dfi_02.py tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py tests/unit/data_forge/domains/catalog/batch/core_sources/test_api.py
```

**Profile и доступность:** {"expected_artifacts": ["PipelineStats.metrics retains registry/alignment/observation counts and failure counts from CoreSourcesIngestStats.", "Facade override affects only its named supported leaf binding and is restored after call.", "Canonical transformer keeps ILO geo/sex filters as REF_AREA=UKR and sex=T."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Pipeline-to-canonical-API behavioral test, dependency-isolation probes, filter-preservation probe, and synthetic ingest persistence.

**Дополнительные пробы / границы:**
- LA-038: verify all remaining leaves and real pipeline callers against final dependency inventory; exercise sync/async, budget/lease/profile handoff, errors/counters, and two calls with different dependencies.
- LA-038: retain no-growth compatibility and test seams while proving a fresh pipeline consumer does not require legacy facade initialization.
- Ограничение: No full per-leaf budget/lease/profile and error-parity matrix across remaining API/registry/transformer leaves.
- Ограничение: Current direct pipeline test monkeypatches canonical API and verifies metrics; it is not a fresh-process proof that every entrypoint works without any prior legacy import.

<a id="dfi-03"></a>

## DFI-03 — Batch resume: input basis и обязательный output inventory

**Записи:** LA-041. **Реестр:** LA-041=partial.
**Маршрут:** первый сбор Q15, Q16; historical C02, C13; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_05.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DFI-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: EMB-02. Protected controls: LK20.

**Дискриминатор из owner-пакета:** Same stat/changed bytes, mtime-only change, corrupted output, empty directory, missing required member/hash, malformed old state, interrupted stage, changed config и allowed empty-generation. all([]) не означает complete; explicit [] против None трактуется объявленно. Неизменный snapshot действительно skip без нового encode, неподтверждённый — rerun/historical-only с причиной.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_dfi_03.py` → Q16 / C13
- `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_pipeline.py` → Q15 / C02
- `policy-engine/tests/unit/data_forge/kernel/io/test_generation_basis.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_dfi_03.py tests/unit/data_forge/domains/catalog/batch/test_pipeline.py tests/unit/data_forge/kernel/io/test_generation_basis.py
```

**Profile и доступность:** {"expected_artifacts": ["Content-bound stage state includes input_basis and output_inventory beside status/input_fingerprint/outputs.", "Changed manifest bytes with same stat and changed output bytes reject skip; mtime-only input change remains reusable.", "Empty normalize output is not reusable; selected empty embed generation can skip without re-encoding; missing selected embedding member rejects skip."], "estimate_label": "estimated", "estimate_basis": "Research/implementation sizing only; no elapsed-time receipt."}.
**Карта поведения из статического исследования:** Behavioral batch-stage resume tests plus kernel basis utility tests; local files only.

**Дополнительные пробы / границы:**
- LA-041: cover harvest-stage basis/output inventory, malformed state, normalize config/rule changes, and explicit None versus [] required-output behavior.
- LA-041: prove unchanged snapshot skips without encode, but changed inputs/outputs rerun and report an addressable reason; preserve the prior JSON bytes/formatter.
- Ограничение: No direct harvest-stage resume test, despite harvest being in the content-bound stage set.
- Ограничение: No explicit malformed JSON state test or None-versus-empty output pair; explicit [] is covered, None fallback is not directly compared.
- Ограничение: Config/rule drift is tested for embed only; stage JSON byte compatibility is described in code but not asserted by a byte-for-byte regression.

<a id="dfk-01"></a>

## DFK-01 — Точные остатки Foundry/Data Forge schemas без удаления владельцев

**Записи:** LA-005, LA-006, LA-026, LA-027. **Реестр:** LA-005=held, LA-006=partial, LA-026=held, LA-027=held.
**Маршрут:** первый сбор Q02, Q05; historical C10, C17; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DFK-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK03, LK10, LK25.

**Дискриминатор из owner-пакета:** Проверить AgentType/RegionProfile/SimulationConfig, GeneratedSchemaModule и три schema aliases, relative/string/generated consumers. Canonical classes identity и schema evolution/migrations работают; retired reexports не возвращаются. Нативные выбранные schema tests сейчас, объединённый wheel/sdist inventory в CP6. Неизвестный внешний consumer означает compatibility_pending конкретного имени, не блок всего ремонта.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_dfk_01.py` → Q05 / C10
- `policy-engine/tests/unit/foundry/hygiene/test_no_compat_facade_imports.py` → Q02 / C17
- `policy-engine/tests/unit/foundry/hygiene/test_no_foundry_domain_imports.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/data_forge/mirror_contracts/test_schemas.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/mirror_contracts/test_schema.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_dfk_01.py tests/unit/foundry/hygiene/test_no_compat_facade_imports.py tests/unit/foundry/hygiene/test_no_foundry_domain_imports.py tests/unit/data_forge/mirror_contracts/test_schemas.py tests/unit/foundry/mirror_contracts/test_schema.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Existing mixed semantic and static coverage. Tombstone absence is already tested; three other legacy FQNs are deliberately required to import, so the current suite is a compatibility-pending guard and must be revised only after the card's complete census/decision.

**Дополнительные пробы / границы:**
- Before retiring AgentType/RegionProfile/SimulationConfig, GeneratedSchemaModule, or pipeline schema aliases, enumerate canonical and relative imports, string-based imports/loaders, generated/config references, persisted payloads, and package data across the complete checkout; test each discovered consumer or keep that exact name compatibility_pending.
- After the owner decision, add negative tests for each retired FQN and retain identity/evolution/migration tests for canonical schemas; update test_dfk_01_compatibility_pending_surfaces_remain_importable and test_dfk_01_compatibility_pending_surfaces_preserve_current_identity so they do not require retired surfaces.
- Distribution wheel/sdist inventory is explicitly deferred to CP6; local unit selectors do not prove it.
- Ограничение: Do not treat the existing compatibility-pending import test as proof those public names are safe to delete; it currently constrains deletion.
- Ограничение: No current unit test establishes absence of string/generated/external FQN consumers or wheel/sdist contents.

<a id="dfk-02"></a>

## DFK-02 — Source catalog: одно определение и единая seed-selection policy

**Записи:** LA-028. **Реестр:** LA-028=partial.
**Маршрут:** первый сбор Q08, Q11, Q19; historical C09, C16, C18; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DFK-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK19, LK20.

**Дискриминатор из owner-пакета:** Enabled seed, disabled mandatory seed, missing/cyclic dependencies, empty tuple против None, custom registry, порядок и 35 штатных записей существующего equality-test. Нельзя молча включить disabled или запустить exec без обязательного seed. Contract-only import не выполняет тяжёлый I/O; реальные Fabric consumers читают ту же разрешённую проекцию.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_dfk_02.py` → Q08 / C18
- `policy-engine/tests/unit/data_forge/test_phase3_catalog_completion.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/fabric/test_retrieval_service_catalog.py` → Q19 / C16
- `policy-engine/tests/integration/data_forge_runtime/test_catalog_to_runtime_bridge.py` → Q11 / C09

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_dfk_02.py tests/unit/data_forge/test_phase3_catalog_completion.py tests/unit/fabric/test_retrieval_service_catalog.py tests/integration/data_forge_runtime/test_catalog_to_runtime_bridge.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral unit coverage plus consumer/bridge checks. The existing 35-entry equality contract is useful, but equality alone does not prove YAML is the sole source and Python is a derived view.

**Дополнительные пробы / границы:**
- Change one canonical YAML entry in an isolated temporary registry and prove the derived Python projection and Fabric consumer change together; this distinguishes generated view from two manually synchronized authorities.
- Keep disabled mandatory seeds from reaching the execution/fetch call, not only from selection; current tests prove typed selection failure and exercise RetrievalService for a selected source.
- Confirm contract-only imports do not trigger catalog asset/file I/O; test this at the public import boundary if no existing test does so.
- Ограничение: The proposed source-of-truth transition needs a consumer-level mutation/corruption probe; matching two views is not sufficient evidence that one is derived.
- Ограничение: No test currently demonstrates a disabled source cannot be fetched/executed after selection failure.

<a id="doe-01"></a>

## DOE-01 — Ограниченная генерация и только объявленные раунды

**Записи:** B97, B98, B99. **Реестр:** B97=partial, B98=partial, B99=partial.
**Маршрут:** первый сбор Q16; historical C02; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DOE-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** 12 параметров/max=3 перечисляют 3, не 4096 комбинаций, сохраняя прежний префикс. Один/два раунда имеют ровно объявленные evaluator calls; ошибка следующей операции не теряет готовое. False остаётся False; oversized план не достигает evaluator.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_doe_01.py` → Q16 / C02
- `policy-engine/tests/unit/scientist/methods/doe/test_sampling.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/methods/doe/test_adaptive.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/methods/doe/test_sensitivity_plan.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_doe_01.py tests/unit/scientist/methods/doe/test_sampling.py tests/unit/scientist/methods/doe/test_adaptive.py tests/unit/scientist/methods/doe/test_sensitivity_plan.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral regression witnesses for B97-B99; no full stress-coverage or production-scale simulation claim.

**Дополнительные пробы / границы:**
- For B99, prove both sides: false remains false in every copied/derived plan and explicit true still admits a bounded follow-up; the remediation test covers denial, while native plan tests cover direct override rather than the adaptive path with true.
- Keep the B97 prefix-equality test separate from the laziness/memory witness; the short prefix is not scientific stress coverage.
- Ограничение: There is no adaptive-path positive test proving explicit large-run permission stays effective while an allowed resource budget is respected.

<a id="doe-02"></a>

## DOE-02 — Один дизайн распределений и локальные RNG

**Записи:** B100, B101. **Реестр:** B100=partial, B101=partial.
**Маршрут:** первый сбор Q06, Q10; historical C01; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DOE-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: DOE-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Корректно заданные UNIFORM/NORMAL действительно меняют sample support/квантили. Одинаковый seed повторяет малую выборку; порядок независимых задач не меняет inputs; внешний RNG не сбрасывается. Один маленький настоящий SALib/SciPy путь выполняется в слоте N.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_doe_02.py` → Q06 / C01
- `policy-engine/tests/unit/scientist/methods/doe/test_analysis_enhanced.py` → Q10 / C01

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_doe_02.py tests/unit/scientist/methods/doe/test_analysis_enhanced.py
```

**Profile и доступность:** test; sensitivity.
**Карта поведения из статического исследования:** Behavioral tests, including real SALib/SciPy paths and mocked backend-call witnesses. This module-level importorskip makes sensitivity an essential extra; without it the entire remediation module can skip rather than verify behavior.

**Дополнительные пробы / границы:**
- Preserve explicit evidence for each backend version's accepted seed/Generator API; current tests assert SALib@1.5.2 in analysis metadata and the lock must remain aligned.
- Include an actual small SALib sampling plus matching analyzer round-trip under the locked backend; distinguish this from monkeypatch-only seed-forwarding tests.
- Add an uncertainty/bootstrap substream order-independence case if that stage consumes RNG separately from sampling and analysis.
- Ограничение: Running the command without sensitivity is a silent skip risk.
- Ограничение: Boundary-spy tests alone do not show the installed backend consumes the seed as intended; the real same-seed sample test is the distinct witness.

<a id="doe-03"></a>

## DOE-03 — Целые блоки, failure-policy, PCA и шкала Morris

**Записи:** B102, B103, B104, B105. **Реестр:** B102=partial, B103=partial, B104=partial, B105=partial.
**Маршрут:** первый сбор Q02; historical C19; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DOE-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: DOE-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Удаление 1 или 3 внутренних точек не склеивает разные Morris trajectories. FAIL_FAST и min_success_rate не исчезают после PCA. Матрица 3×5 имеет согласованный sklearn/SVD путь. y=2x на[0,10] сохраняет шкалу point/UQ при смене единиц. Малый native SALib тест не является coverage campaign.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_doe_03.py` → Q02 / C19
- `policy-engine/tests/unit/scientist/methods/doe/test_multi_output.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/methods/doe/test_uncertainty.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_doe_03.py tests/unit/scientist/methods/doe/test_multi_output.py tests/unit/scientist/methods/doe/test_uncertainty.py
```

**Profile и доступность:** test; sensitivity; ml.
**Карта поведения из статического исследования:** Behavioral numerical probes, not a Morris/Sobol statistical coverage campaign. Sensitivity is required because the module-level importorskip skips all witnesses otherwise; ml selects the real sklearn PCA path while a test forces the NumPy fallback.

**Дополнительные пробы / границы:**
- For B103, add paired scalar and multi-output tests for the same FAIL_FAST, minimum-success, and imputation inputs; current remediation directly exercises policies mainly through MultiOutputAnalyzer.
- For B105, test an equivalent linear model after changing input units/range and assert point and uncertainty estimates transform under the declared coordinate contract; the current y=2x on [0,10] is one witness only.
- Keep a known trajectory/block identity when an interior row is removed and add malformed/non-divisible block layouts; current whole-trajectory tests cover selected internal failures, not every design-shape failure.
- Ограничение: A successful collection without sensitivity is not meaningful because the module skips at import.
- Ограничение: One scale witness cannot establish invariant coordinate behavior across units or input transforms.

<a id="dur-01"></a>

## DUR-01 — Аварийно-устойчивый бюджетный snapshot

**Записи:** B37. **Реестр:** B37=partial.
**Маршрут:** первый сбор нет в Q; historical нет в C; дополнительно D04, D01. **Checkpoint:** CP2. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DUR-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Пауза writer после начала записи не даёт читателю blank=no-limits. Обрыв JSON и controlled crash между temp/write/replace оставляют valid old/new либо адресное восстановление, не обнуление расходов. Повтор чтения не списывает новую работу.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/mirror_contracts/test_budget_ledger.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_dur_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/mirror_contracts/test_budget_ledger.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Current behavioral coverage is missing. The first command is only a static mirror check; the second becomes valid after the proposed semantic regression test is created.

**Дополнительные пробы / границы:**
- Use the real FileBudgetLedger on a tmp_path with a barrier around publication; while writer A is paused, reader B must block or observe the complete prior snapshot, never an empty/unlimited BudgetState.
- Inject write/fsync/replace failures at the publication boundary and assert a complete valid old or new snapshot remains, revision/spend is preserved, and partial temporary artifacts are cleaned.
- Differentiate an absent new ledger (allowed bootstrap) from an existing empty/truncated/malformed ledger (must raise or enter explicit recovery; must not reset limits/spend).
- Exercise the same persisted ledger through BudgetMiddleware/pre_check after concurrent read/write. Keep duplicate operation idempotency as a separate property: B37 says it is not established by this audit.
- Ограничение: The current source appears to already contain the core B37 repair, but that state is not behaviorally verified by an existing test; assignment output should treat this as verification_missing, not assume bug still reproduces.
- Ограничение: No current test guards concurrent load during replacement or recovery behavior on interrupted/corrupt files.

<a id="dur-02"></a>

## DUR-02 — Поколение worker и безопасный backend handover

**Записи:** B38, B78. **Реестр:** B38=partial, B78=partial.
**Маршрут:** первый сбор Q11, Q13, Q17, Q19; historical C03, C08, C09, C13; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DUR-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: RUN-03, RES-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Stale worker A не портит running/completed attemptB; актуальный B завершает. Primary создал тестовый эффект и потерял ответ — local не повторяет его вслепую. Unhealthy/probe-network-error до старта допускает только разрешённый fallback; access/contract failure не даёт нового права.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_dur_02.py` → Q11 / C09
- `policy-engine/tests/unit/runtime/http/test_control_plane_store.py` → Q13 / C13
- `policy-engine/tests/unit/runtime/http/test_acquisition_control_worker.py` → Q19 / C03
- `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_fallback_runner.py` → Q17 / C08

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_dur_02.py tests/unit/runtime/http/test_control_plane_store.py tests/unit/runtime/http/test_acquisition_control_worker.py tests/unit/scientist/orchestration/engine/runner/test_fallback_runner.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Existing semantic regression file plus store and runner integration-style unit tests. The post-dispatch failure witness is stronger than a generic fallback test because it records the effect then proves fallback is not called.

**Дополнительные пробы / границы:**
- Extend stale-generation tests across fail and progress writes as well as complete; B38 names all three mutations, while the remediation test directly drives stale complete plus a transaction failure case.
- Add the primary-effect/lost-ack case with a persisted operation/evidence receipt and reconciliation proving fallback resumes only verified unfinished work; current test proves no blind duplicate but not reconciliation/resumption.
- Review TestFallbackRunner::test_primary_execution_error_falls_back: it constructs a runner and asserts no call without executing the runner, so it is not a semantic witness and should be replaced or explicitly kept as constructor characterization.
- Ограничение: The suite distinguishes failover authority from unknown outcome but does not yet demonstrate readback/reconciliation and safe continuation of unfinished operations.
- Ограничение: The package's exactly-once caveat remains material: SQL fencing does not prove external side effects were not duplicated.

<a id="eco-01"></a>

## ECO-01 — Два economic профиля и предметный baseline objective

**Записи:** LA-004, LA-035. **Реестр:** LA-004=partial, LA-035=partial.
**Маршрут:** первый сбор Q13; historical C14; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_06.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/ECO-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: FRY-03. Protected controls: LK04, LK06, LK08.

**Дискриминатор из owner-пакета:** Threshold employment не выдаётся за transition employment; wealth tax не за income tax. Старый loss positive/scaled/zero/negative/breach/nonfinite и JIT/grad сохраняет свой определённый профиль. Constant -1 в positive regime документируется, не исправляется скрыто новым welfare objective. Native guard остаётся настоящим.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_eco_01.py` → Q13 / C14
- `policy-engine/tests/unit/foundry/mechanisms/test_fiscal.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/mechanisms/test_labor.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/analysis/test_loss_numeric.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_eco_01.py tests/unit/foundry/mechanisms/test_fiscal.py tests/unit/foundry/mechanisms/test_labor.py tests/unit/foundry/analysis/test_loss_numeric.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral numerical characterization with actual GlobalState, EconomicState, JAX jit/grad, fiscal and labor producers. Existing test names identify both non-equivalent profiles rather than asserting equivalence by class name.

**Дополнительные пробы / границы:**
- For the legacy normalized-income objective, assert the positive-income gradient behavior described by LA-035 (scale-normalized positive regime can be constant -1); current JIT/gradient test uses mixed negative/positive values and only asserts finite gradient.
- Keep the equivalent relocation test separate from any intentional new welfare/objective semantics; do not rename the expected ranking silently.
- Check other state dimensions enumerated in LA-004's mapping table (units, timestep, RNG, balances and PatchMap/EconomicState fields) before any mechanism consolidation; current remediation differentiates representative tax and labor cases, not the full state crosswalk.
- Ограничение: No positive-regime gradient assertion records the constant-loss limitation; finite gradient is weaker than the semantic characterization.
- Ограничение: The LA-004 state/unit/timestep/RNG/balance crosswalk is not covered end to end by the selected test nodes.

<a id="emb-01"></a>

## EMB-01 — Academic/Catalog: общий encode/index primitive, разные text profiles

**Записи:** LA-039. **Реестр:** LA-039=partial.
**Маршрут:** первый сбор Q09; historical C18; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/EMB-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK20.

**Дискриминатор из owner-пакета:** Одинаковые effective texts дают тот же input модели, normalization/dtype/labels/M/ef settings; Catalog500 и Academic1200 остаются разными. Малый реальный NumPy/HNSW path без загрузки большой SentenceTransformer; fake encoder допустим для wiring, но не объявляется тестом модели. Counts/profile/device/thermal pause hooks сохранены.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/data_forge/kernel/test_embeddings.py` → Q09 / C18
- `policy-engine/tests/unit/data_forge/kernel/io/test_generation_basis.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_emb_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/data_forge/kernel/test_embeddings.py tests/unit/data_forge/kernel/io/test_generation_basis.py
```

**Profile и доступность:** pytest/pytest-asyncio from the test extra.; vector-search extra (hnswlib) is required for the real HNSW assertions.; rag-local / sentence-transformers is not needed by these tests because SentenceTransformer is replaced with a deterministic fake; no model download..
**Карта поведения из статического исследования:** Direct dynamic kernel/domain coverage. The shared primitive and distinct domain wrappers are exercised; model quality, real SentenceTransformer inference, ANN recall and accelerator execution are not.

**Дополнительные пробы / границы:**
- No additional semantic probe is required for this phase's narrow encode/index primitive based on the existing assertions. Keep real-model quality and hardware claims explicitly out of scope.
- The new test_emb_01.py filename in the card is not present; the existing kernel test is the canonical owner test.
- Ограничение: This test demonstrates the encode/index primitive, not an end-to-end persisted generation or consumer; that closure belongs to EMB-02.

<a id="emb-02"></a>

## EMB-02 — Индексное поколение: NPZ/HNSW/basis публикуются согласованно

**Записи:** LA-039. **Реестр:** LA-039=partial.
**Маршрут:** первый сбор Q13; historical C09; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/EMB-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: EMB-01. Protected controls: LK20.

**Дискриминатор из owner-пакета:** Малый native индекс: empty/nonempty, две model revisions, failure между NPZ/HNSW, missing/corrupt member, rows permutation и old supported generation. Reader не смешивает IDs/vectors/HNSW/basis; при провале новый stage не complete, старый snapshot не уничтожен. Байтовая reproducibility HNSW не обещается без фактического основания.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_emb_02.py` → Q13 / C09
- `policy-engine/tests/unit/data_forge/kernel/io/test_generation_basis.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_emb_02.py tests/unit/data_forge/kernel/io/test_generation_basis.py
```

**Profile и доступность:** pytest/pytest-asyncio from the test extra.; vector-search extra (hnswlib) is required for nonempty generation cases.; rag-local / sentence-transformers is not needed because the tests install a fake encoder..
**Карта поведения из статического исследования:** Strong dynamic publisher-to-persisted-artifact-to-reader coverage for the tested Academic/Catalog paths; native HNSW is real and encoder is fake. Fails before selector commit without replacing the last selected generation.

**Дополнительные пробы / границы:**
- LK20/P37: demonstrate source-membership completeness separately from hashes of the offered inventory. A self-consistent selector/inventory can prove its members' bytes, but not that the caller supplied every current source row. Add a producer-side omission probe or record this as a bounded limitation.
- The new test_emb_02.py destination is present despite the card's historical wording that it was proposed. The existing previous-selected-generation tests do not establish historical flat-file NPZ fallback compatibility as a separate reader contract.
- Ограничение: The source-of-truth completeness premise is not independently reconciled by a content hash; do not call the inventory complete solely because its digest verifies.

<a id="emb-03"></a>

## EMB-03 — Legal embeddings: content-bound incremental и честный старый backend API

**Записи:** LA-040, LA-042. **Реестр:** LA-040=partial, LA-042=partial.
**Маршрут:** первый сбор Q16; historical C17; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/EMB-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: EMB-02. Protected controls: LK20.

**Дискриминатор из owner-пакета:** Unchanged append; changed text same ID; withdrawal; model change same dimension и different dimension; projection-rule change; corrupt/missing sidecar; full rebuild и historical NPZ. Сохраняются три legal projections и chunking. Old backend trap получает явную несовместимость, не silent local default; canonical model/device/chunk forwarding и result identity проверены.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_emb_03.py` → Q16 / C17
- `policy-engine/tests/unit/data_forge/legal_batch/test_embed_local.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_emb_03.py tests/unit/data_forge/legal_batch/test_embed_local.py
```

**Profile и доступность:** pytest/pytest-asyncio from the test extra.; vector-search extra (hnswlib) is required for generation-building tests.; rag-local is not required by tests; no model download. Real encoder quality remains untested..
**Карта поведения из статического исследования:** Dynamic legal producer and legacy wrapper tests; real DB/NPZ/HNSW path with synthetic encoder and tiny tables. Current incremental semantic cases populate entities only.

**Дополнительные пробы / границы:**
- Separate a same-dimension encoder revision change from the currently combined model-and-dimension change; same dimension is the LA-040 failure case.
- Populate facts and provisions and exercise changed text, withdrawal and reuse for all three legal projections; the remediation helper currently leaves those tables empty.
- Add historical flat NPZ/full-rebuild reader coverage before claiming that legacy caches remain safely readable; test_embed_local only proves fresh output creation.
- LA-042 wrapper behavior is covered, but the card's FQN/config/notebook/external-caller census and retirement decision are not.
- Ограничение: Same-dimension model change and content-bound incremental coverage for facts/provisions are not demonstrated by the current tests.

<a id="emp-01"></a>

## EMP-01 — Область эмпирических данных, ValueOuterSet и selection diagram

**Записи:** B16, B31, B33. **Реестр:** B16=partial, B31=held, B33=partial.
**Маршрут:** первый сбор Q07; historical C14; дополнительно D02, D04. **Checkpoint:** CP1. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/EMP-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CYC-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Scope фильтруется до LIMIT; несовместимые единицы не усредняются. Асимметричный CI не сужается при value projection; point identification не означает нулевую общую uncertainty. Разные причинные структуры не получают одинаковое основание из одних имён переменных.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_emp_01.py` → Q07 / C14
- `policy-engine/tests/unit/core/contracts/test_value_outer_set.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_emp_01.py tests/unit/core/contracts/test_value_outer_set.py
```

**Profile и доступность:** pytest/pytest-asyncio from the test extra.; No bundle-specific optional extra found; numpy, pandas and DuckDB are base dependencies for adjacent product surfaces..
**Карта поведения из статического исследования:** Direct dynamic owner tests for scope/error decisions and ValueOuterSet projection, but scope SQL is a mock and positive graph-artifact consumption is not implemented/tested.

**Дополнительные пробы / границы:**
- P38/B16: add a small real DuckDB fixture with in-scope and foreign rows ordered so an unscoped LIMIT would exclude target rows; assert actual returned rows. Current fake connection filters on the presence of a SQL substring and one assertion compares SQL token positions.
- P33/P38/B33: the two tests only prove raw/unverified graph inputs are refused. No positive verified CausalGraphModelRef/artifact bridge or differing graph topologies with identical variable names are exercised; the current generation-cycle boundary has no such verifier bridge.
- B31: add unit-rescaling/same-estimand cases if claiming interval semantics are invariant beyond preservation of one asymmetric CI.
- Ограничение: B33 is currently a fail-closed contract without a verified causal-graph artifact consumer bridge, so the bundle does not demonstrate admitted graph-derived diagrams.

<a id="exe-01"></a>

## EXE-01 — Допуск cache read, неблокирующий I/O и fail-fast

**Записи:** B51, B52, B55. **Реестр:** B51=partial, B52=partial, B55=partial.
**Маршрут:** первый сбор Q06, Q16; historical C07, C12; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/EXE-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: STA-01, RUN-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Hit при нулевом compute-budget читается только при разрешённом read-budget; miss не запускает producer. Медленный local store не блокирует соседнюю coroutine. Parallelism=1 и fail первого из четырёх не запускает остальных при fail_fast, но continue выполняет их.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor.py` → Q06 / C07
- `policy-engine/tests/unit/core/artifacts/test_async_store.py` → Q16 / C12

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_exe_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/orchestration/engine/test_async_executor.py tests/unit/core/artifacts/test_async_store.py
```

**Profile и доступность:** pytest and pytest-asyncio from the test extra.; No runtime, DB, browser or model extra found for the focused tests..
**Карта поведения из статического исследования:** Strong dynamic cache/budget/tier coverage on AsyncWorkflowExecutor; local ArtifactStore is real under tmp_path, with deterministic fake node and injected slow/failing I/O. Does not exercise remote CAS or an external storage service.

**Дополнительные пробы / границы:**
- B55: current failure witness has three nodes total and uses a 40ms sleep to let waiters queue; make queued admission deterministic with Events and include the card's continue-mode failure control.
- B52: slow local I/O and failed pre-publication are covered; test cancellation/deadline while an underlying write is still in progress and readback after recovery if making the stronger cancellation guarantee.
- The bundle's test_exe_01.py file is absent; canonical owner tests already cover most stated semantics.
- Ограничение: The `continue` counter-control is not in the same queued-after-failure scenario; current second test under TestAsyncFailFastAdmission covers slot release after telemetry failure instead.

<a id="exe-02"></a>

## EXE-02 — Готовность зависимостей вместо лишнего tier-ожидания

**Записи:** B77. **Реестр:** B77=partial.
**Маршрут:** первый сбор Q08; historical C19; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/EXE-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: RES-02, RES-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Управляемые события A и независимого B: C(A) стартует после A, не дожидаясь B; после добавления настоящего B→C ожидает обоих. Число методов, входы, seeds, provenance и checkpoint остаются прежними. Это тест расписания на крошечном DAG, не нагрузочный тест.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_exe_02.py` → Q08 / C19

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_exe_02.py
```

**Profile и доступность:** pytest and pytest-asyncio from the test extra..
**Карта поведения из статического исследования:** Direct dynamic scheduler and state-journal semantics; controlled test-only workflow, not load/performance testing.

**Дополнительные пробы / границы:**
- Connect the readiness behavior to one actual production workflow/DAG whose declared read/write set permits the reordering; current witness builds its own nodes and stubs persistence.
- The packet names preserved method count, seeds, provenance and checkpoint behavior; current tests do not inspect a persisted workflow/report/checkpoint because the persistence helpers return synthetic refs.
- Ограничение: The dynamic proof is on a synthetic workflow; production caller/lifecycle and persisted checkpoint continuity remain unverified.

<a id="fed-01"></a>

## FED-01 — Grain, cell lineage, внутренние имена и CONSENSUS

**Записи:** B138, B140, B141, B145. **Реестр:** B138=partial, B140=partial, B141=partial, B145=partial.
**Маршрут:** первый сбор Q12; historical C07; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FED-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK04.

**Дискриминатор из owner-пакета:** Смешанный столбец 10/20 не становится 10/200 из-за column metadata. Необъявленный many-to-many не удваивает сумму; разрешённый m2m работает. Реальные __source_id/_left не перезаписываются. Invalid/inf участник не получает вымышленный голос в consensus.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/fabric/connectors/test_federation.py` → Q12 / C07

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_fed_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/fabric/connectors/test_federation.py
```

**Profile и доступность:** pytest from the test extra; pandas is a base project dependency..
**Карта поведения из статического исследования:** Direct dynamic composer semantics over in-memory pandas frames; no connector-network fetch or persisted-result replay in these witnesses.

**Дополнительные пробы / границы:**
- B138: round-trip a mixed-lineage result through the actual supported persistence/read path; current test verifies only one in-memory A→B→C join.
- B140: add a permitted declared many-to-many positive control with an explicit resource bound; existing coverage is negative rejection plus null-key separation.
- B141: exercise reserved-name preservation across remaining composition strategies and persisted reread; present witnesses cover UNION `__source_id` and JOIN suffix-like field.
- B145: assert counts/identities and reasons for invalid, excluded, null and finite CONSENSUS participants; current tests prove strict refusal for inf and a bad numeric string only.
- Ограничение: test_fed_01.py is absent; existing canonical owner tests already cover the primary negative cases but leave explicit positive/replay scenarios open.

<a id="fed-02"></a>

## FED-02 — Устойчивый bounded audit, typed-empty и один indexing

**Записи:** B139, B142, B143, B144. **Реестр:** B139=partial, B142=partial, B143=partial, B144=partial.
**Маршрут:** первый сбор Q10; historical C20; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_07.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FED-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: FED-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Обычный повтор ключа не падает.80 событий/cap=1 дают ограниченный пример и полный count. Empty valid UNION сохраняет columns/dtype. OVERLAY трёх столбцов не повторяет set_index трижды; NONE не создаёт лишних audit payload.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_fed_02.py` → Q10 / C20

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_fed_02.py
```

**Profile и доступность:** pytest from the test extra; pandas is a base project dependency..
**Карта поведения из статического исследования:** Direct dynamic bounded collector/compose coverage with pandas artifacts in memory; not a peak-memory benchmark.

**Дополнительные пробы / границы:**
- P38/B143: current test asserts `_union` return locals omit the name `merge_log`; an alternate alias/list retaining all MergeLogEntry objects would satisfy that check. Add an object-lifetime/reference census or a bounded-memory probe over captured payloads, while retaining full conflict counts.
- Keep performance claims bounded: present 80-row case establishes sample/count behavior and operation counts, not a real-size memory/time improvement or constant-memory UNION.
- Ограничение: The B143 hidden-memory claim is guarded by a local variable name check (P38 proxy), not direct retention measurement.

<a id="fit-01"></a>

## FIT-01 — Nuisance fit-core, актуальная диагностика и ограниченные folds

**Записи:** B54, B56. **Реестр:** B54=partial, B56=partial.
**Маршрут:** первый сбор Q14, Q18; historical C07, C09; дополнительно по готовности новых проб. **Checkpoint:** CP4. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FIT-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Изменение порога 48→100 не меняет fit, но меняет diagnostics; изменение данных/seed требует новой оценки. Потребитель не мутирует следующий hit. Два внешних fit с cap=1 выполняют тот же научный план, что разрешённый одиночный fit; контроль числа задач без тяжёлого обучения, один bounded native fit в K4.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_fit_01.py` → Q14 / C07
- `policy-engine/tests/unit/scientist/orchestration/engine/test_budget_middleware.py` → Q18 / C09

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_fit_01.py tests/unit/scientist/orchestration/engine/test_budget_middleware.py
```

**Profile и доступность:** test for all selectors; ml for the real estimator backend in K4; base package JAX/NumPy.
**Карта поведения из статического исследования:** Focused cache/cap regression tests exist. Two B54 selectors are explicitly described by the test file as expected RED on the cited base. B56 has a synthetic worker-cap witness and a separate bounded native-fit selector.

**Дополнительные пробы / границы:**
- B54: after the expected-red baseline is captured, show the repaired cache returns a separately owned hit and recomputes current diagnostics without refitting; preserve the input-change positive control.
- B56: connect two outer fit requests to the actual shared resource/budget owner and demonstrate cap=1 limits native tasks without dropping folds/repeats/seeds or creating a nested-pool deadlock. The existing middleware tests alone do not prove this bridge.
- Ограничение: No actual outer-request-to-shared-budget assertion is identified. The test file has @pytest.mark.slow on the native selector; pytest.ini at this SHA registers slow, but exact-node selection avoids broad marker-based execution. No tests were run here.

<a id="frc-01"></a>

## FRC-01 — S10: реальные времена и запрет выдуманного calibration pass

**Записи:** B32, LA-051. **Реестр:** B32=partial, LA-051=partial.
**Маршрут:** первый сбор Q07; historical C11, C16; дополнительно D02, D04. **Checkpoint:** CP1. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FRC-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CYC-01. Protected controls: LK29, LK30.

**Дискриминатор из owner-пакета:** Nominal 0.8/0.95 без новых observations не меняет empirical coverage; report None, failed diagnostic, неизвестная history/ссылка не дают calibration pass. Шесть временных ролей не заполняются 2026-06-02 или now. Полезный conditional output и S10 purpose denials сохраняются.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_frc_01.py` → Q07 / C11
- `policy-engine/tests/unit/runtime/quality/test_design_axes_outcome_prediction.py` → Q07 / C16

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_frc_01.py tests/unit/runtime/quality/test_design_axes_outcome_prediction.py
```

**Profile и доступность:** test; runtime; base package.
**Карта поведения из статического исследования:** Focused no-fake-calibration, time-role, missing-reference, and S10-authority tests exist. The test module calls itself test-first and explicitly says the first two fake-pass witnesses are expected RED until the producer adapter changes.

**Дополнительные пробы / границы:**
- B32: falsify each missing source-time/ref premise and prove no fallback to the historical 2026-06-02 constant or current time produces an empirical calibration pass; current time-role tests prove preservation when all values are supplied, not absence/default behavior for every role.
- LA-051: exercise the actual producer-to-S10 consumer route after FRC-02 wiring, while keeping this no-fake-pass boundary and purpose denials green.
- Ограничение: These fixtures validate the S10 boundary with synthetic report inputs, not a real calibration producer. FRC-01 is only the first LA-051 stage; full closure must remain pending until FRC-02's bridge evidence is accepted.

<a id="frc-02"></a>

## FRC-02 — S10: один действительный calibration producer и связанный forecast

**Записи:** LA-051. **Реестр:** LA-051=partial.
**Маршрут:** первый сбор Q05, Q09, Q14, Q19; historical C04, C06, C11, C12; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FRC-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: FRC-01, PCL-01, EMP-01. Protected controls: LK01, LK29, LK30.

**Дискриминатор из owner-пакета:** Одинаковая форма estimator-report при разных настоящих calibration observations даёт разную пригодность. Нет evidence — ограниченный полезный результат, а не pass. Tiny real producer→S10 readback проверяет refs, task, scope и запреты. Если совместимый producer не найден, сдать честную FRC-01 границу и оставить bridge явно незавершённым, не подставлять predictive CI вместо effect CI.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_frc_02.py` → Q19 / C12
- `policy-engine/tests/unit/remediation/test_frc_02_owner.py` → Q14 / C04
- `policy-engine/tests/unit/remediation/test_frc_02_bridge.py` → Q05 / C11
- `policy-engine/tests/unit/remediation/test_frc_02_s10.py` → Q09 / C06

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_frc_02.py tests/unit/remediation/test_frc_02_owner.py tests/unit/remediation/test_frc_02_bridge.py tests/unit/remediation/test_frc_02_s10.py
```

**Profile и доступность:** test; runtime; base NumPy/Pydantic.
**Карта поведения из статического исследования:** A real, deterministic predictive ETS producer → persisted CAS evidence → S10 readback/consumer chain is represented by focused tests. The chain deliberately grants predictive-only authority and retains causal/treatment/S10 denials.

**Дополнительные пробы / границы:**
- LA-051: tie the accepted experimental estimand and caller to the intended S10 forecast task and record an actual end-to-end invocation/readback receipt; the present chain is tiny predictive ETS and its raw causal-effect control remains non-positive.
- LA-051: preserve and report the consumer-side purpose denials in the real S10 result. Do not treat nominal CI fields, report shape, or an unbound artifact ref as sufficient evidence.
- Ограничение: The tests are a predictive forecasting calibration bridge, not proof that a causal effect CI is empirical calibration evidence. `test_frc_02.py` alone is reference transport; the other three files are required for this bundle's producer/bridge/consumer acceptance.

<a id="fry-01"></a>

## FRY-01 — Foundry compile/catalog: randomization, families и прямой IR layout

**Записи:** LA-001, LA-002, LA-037. **Реестр:** LA-001=partial, LA-002=partial, LA-037=partial.
**Маршрут:** первый сбор Q04, Q16, Q18, Q19; historical C07, C10, C11, C20; дополнительно D04. **Checkpoint:** CP1. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FRY-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK03, LK06.

**Дискриминатор из owner-пакета:** Seed=0/nonzero, permutation/recompile/old plan bytes; четыре family IDs/assumptions и unknown ID; пять layout objects identity, native build_slot_layout/family и compiler outputs. Временный facade допускается один прямой, не цепочка; не расширять public exports.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/foundry/compile/test_randomization.py` → Q18 / C20
- `policy-engine/tests/unit/foundry/mechanisms/test_treasury.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_families.py` → Q19 / C10
- `policy-engine/tests/unit/foundry/mechanisms/test_mechanism_design.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/compile/test_trinity_compiler.py` → Q04 / C07
- `policy-engine/tests/unit/foundry/contracts/test_layout.py` → Q16 / C11

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_fry_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/foundry/compile/test_randomization.py tests/unit/foundry/mechanisms/test_treasury.py tests/unit/foundry/methods/catalog/mechanism/test_families.py tests/unit/foundry/mechanisms/test_mechanism_design.py tests/unit/foundry/compile/test_trinity_compiler.py tests/unit/foundry/contracts/test_layout.py
```

**Profile и доступность:** test; base Python/JAX packages.
**Карта поведения из статического исследования:** Existing canonical-owner, serialization-parity, family behavior, importer, and compiler tests give targeted relocation coverage. The bundle's proposed consolidated regression file is absent.

**Дополнительные пробы / границы:**
- LA-001: ensure compiler-emitted plan bytes remain stable across the actual `compile_trinity` path and legacy symbolic/string loaders still resolve after the owner move; current canonical-vs-legacy builder parity is strong but is not the full compiler route.
- LA-002: verify IC consumer result remains unchanged for representative family after cutover, not only that the imported function object is bound to the catalog owner.
- LA-037: assert identity/equivalence for all five layout objects requested by the bundle at native `build_slot_layout`/family and compiled output boundaries; current direct-binding tests name only the manifest/layout helpers.
- Ограничение: There is no `test_fry_01.py` at the assigned base. Existing tests are split by owner and some assertions are import identity/serialization, so the additional end-to-end compile and five-object identity probes remain needed.

<a id="fry-03"></a>

## FRY-03 — Fiscal/labor: эквивалентный перенос живых PatchMap kernels

**Записи:** LA-003. **Реестр:** LA-003=partial.
**Маршрут:** первый сбор Q04; historical C01; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FRY-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: FRY-01. Protected controls: LK06, LK08.

**Дискриминатор из owner-пакета:** Native registry creation, spec→kernel, same patches/key, masked/inactive, fiscal balance/employer/counts. Сравнить старые plans и строковые loads; тесты должны импортировать новый production kernel, не оставленную копию. JAX/gradient один tiny N job.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_fry_03.py` → Q04 / C01
- `policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_runtime.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/mechanisms/test_fiscal.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/mechanisms/test_labor.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_fry_03.py tests/unit/foundry/methods/catalog/mechanism/test_runtime.py tests/unit/foundry/mechanisms/test_fiscal.py tests/unit/foundry/mechanisms/test_labor.py
```

**Profile и доступность:** test; base JAX/NumPy.
**Карта поведения из статического исследования:** Focused relocation parity tests exercise real canonical fiscal/labor kernels and the registry/spec loader; one tiny JAX JIT/gradient path is included.

**Дополнительные пробы / границы:**
- LA-003: if old persisted plans or string class-path loads are in the supported compatibility set, replay one actual saved/string plan after cutover and verify it resolves the canonical implementation; descriptor/spec creation alone does not prove every external string loader.
- Ограничение: No GPU or Apple-metal dependency is appropriate on Linux. Historical FQN/string replay needs a separate probe only if those loaders are supported.

<a id="fun-01"></a>

## FUN-01 — Версионный ticket и одинаковое full/split продолжение

**Записи:** B156, B158, B159. **Реестр:** B156=partial, B158=partial, B159=partial.
**Маршрут:** первый сбор Q20; historical C03; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FUN-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CTL-03. Protected controls: нет.

**Дискриминатор из owner-пакета:** Один candidate с разными contexts/roles не получает старый terminal. Full/split потребляют одну конфигурацию и transition decision. Без нового основания defer не запускает работу; с разрешённым изменением продолжается только нужный остаток.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/search/funnel/test_orchestrator.py` → Q20 / C03
- `policy-engine/tests/unit/scientist/search/funnel/test_types.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_fun_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/search/funnel/test_orchestrator.py tests/unit/scientist/search/funnel/test_types.py
```

**Profile и доступность:** test; base package.
**Карта поведения из статического исследования:** Existing L-level funnel unit tests cover effective-context cache isolation, full/split cache reuse, and budget/defer/freeze continuations. Proposed bundle-specific regression file is absent.

**Дополнительные пробы / границы:**
- B156: keep candidate and dataset/model fixed while changing calibration/evaluation role and sentinel status; prove no old terminal ticket is reused and an exact same-effective request still does reuse.
- B158: compare full and split execution at L2→L3 with one declared config and transition decision, including the final allowed continuation and its decision.
- B159: test freeze/defer with and without an explicit external resume event/new authorized basis; absent that event, a new ticket must not silently run work.
- Ограничение: No `test_fun_01.py` exists. Existing tests are useful but do not fully cover calibration-role identity or a real resume basis/event; keep those properties explicitly open.

<a id="fun-02"></a>

## FUN-02 — Изоляция reduced-config и правдивый результат воронки

**Записи:** B157, B160, B162, B165. **Реестр:** B157=partial, B160=partial, B162=partial, B165=partial.
**Маршрут:** первый сбор Q18, Q20; historical C03; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FUN-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: FUN-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** L3 fraction/bootstrap не меняют L4 full config. Пустая/capped воронка не даёт APPROVE/0. Broken/null/zero width различаются. Stage APPROVE с final defer сохраняет результат стадии, но не разрешает promotion; наличие поля verdict не выбирает исход случайно.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_fun_02.py` → Q18 / C03
- `policy-engine/tests/unit/scientist/search/funnel/test_level3_medium.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/search/funnel/test_level4_full.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/search/funnel/test_orchestrator.py` → Q20 / C03

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_fun_02.py tests/unit/scientist/search/funnel/test_level3_medium.py tests/unit/scientist/search/funnel/test_level4_full.py tests/unit/scientist/search/funnel/test_orchestrator.py
```

**Profile и доступность:** test; runtime; base package.
**Карта поведения из статического исследования:** The proposed remediation test exists and provides focused behavioral witnesses for config isolation, empty/capped results, CI width, and final status aggregation; importer/stage tests are relevant consumer checks.

**Дополнительные пробы / границы:**
- B157: verify the real downstream L4 consumer reads the complete config after L3, not only that the fixture/caller object is unchanged; preserve the targeted importer check.
- B160/B162/B165: include one actual orchestrator result/readback that demonstrates the derived aggregate action and status projection consumed by the downstream caller. Existing tests cover local stage output and some orchestration, not every external projection.
- Ограничение: Local regression coverage is strong. Before claiming lifecycle/promotion behavior, retain the actual orchestrator consumer result and authority/status boundary evidence; do not generalize stage tests to publication.

<a id="fun-03"></a>

## FUN-03 — Текущее знание, calibration routing и pre-commit ограничение

**Записи:** B161, B163, B164. **Реестр:** B161=partial, B163=partial, B164=partial.
**Маршрут:** первый сбор Q07, Q18, Q20; historical C03, C06, C15; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_08.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FUN-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: FUN-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Unknown=1 затем связанная оценка 0.1 обновляет current, сохраняя историю и независимый risk=0.8. Пустой tracker не сообщает одновременно normal/no_promotion. Запрет не вызывает callback; готовый payload читается без нового действия; потеря разрешения перед commit обнаруживается.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_fun_03.py` → Q18 / C06
- `policy-engine/tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py` → Q07 / C15
- `policy-engine/tests/unit/scientist/search/funnel/test_orchestrator.py` → Q20 / C03
- `policy-engine/tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_fun_03.py tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py tests/unit/scientist/search/funnel/test_orchestrator.py tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py
```

**Profile и доступность:** test; runtime; base package.
**Карта поведения из статического исследования:** Focused tracker-status and L6 callback tests exist, including a real policy-node → workflow/funnel → L6 → owner-recheck/effect-recorder route. The effect recorder is test-local, not a real publication or registry write.

**Дополнительные пробы / границы:**
- B161: preserve the full identity dimensions (same subject/value/input basis/rule/time) in any newly added positive update path; test an in-scope and near-match mutation so the old history cannot be erased by a merely similar context.
- B164: prove the removal/falsifier at the owner boundary: remove the inner owner recheck while retaining L6 preflight and require the protected-mode actual-node test to fail. Do not claim production write/publish coverage from the test-local recorder.
- B164: preserve the ordinary positive callback control and explicit permission-loss-before-commit case in the same actual-node route.
- Ограничение: The test-local effect recorder verifies ordering and owner recheck; no external publication, registry write, or production authority issuance occurs. `test_calibration_uncertainty_adapter.py` is adjacent source coverage, not the complete B161 tracker transition witness.

<a id="grf-01"></a>

## GRF-01 — Правильные static ADMG m-separation и perfect-do

**Записи:** B216, B217, LA-007, LA-019. **Реестр:** B216=partial, B217=partial, LA-007=partial, LA-019=partial.
**Маршрут:** первый сбор Q06, Q17; historical C05, C16; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/GRF-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK05, LK13.

**Дискриминатор из owner-пакета:** Цепь, вилка X←U→Y, collider и conditioned descendant; симметрия и переименование. Для X↔Y операция do(X) согласуется с явным latent-DAG. Локально несколько малых графов; полный конечный differential-набор 200 ADMG/2400 запросов один раз в K5, без экстраполяции на все PAG. После удаления трёх sibling .py native find_spec/public imports должны разрешать сохранившиеся packages. Сборка distribution объединяется в CP6; до неё retirement имеет отдельный непроверенный packaging-остаток.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_s_ops.py` → Q06 / C16
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_do_calculus_postpass.py` → Q17 / C05

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_grf_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/foundry/methods/catalog/causal/test_admg_s_ops.py tests/unit/foundry/methods/catalog/causal/test_do_calculus_postpass.py
```

**Profile и доступность:** Requires the repository test extra for pytest. The target tests do not invoke JAX, DoWhy, or a numerical backend.; No new external artifact is needed for the targeted tests; the 2,400-query comparison is described by the B216 audit card but is not present as a pytest nodeid in these test files..
**Карта поведения из статического исследования:** Direct behavioral unit cases plus direct Rule 1, sigma Rule 1, and Rule 3 consumer calls. M-separation tests cover chain, fork, directed collider, bidirected collider, conditioned descendant, symmetry, and renaming. Perfect-do tests cover cutting action-incident bidirected influence, retaining outgoing/unrelated edges, graph immutability, and latent-DAG surgery.

**Дополнительные пробы / границы:**
- B216: retain the recorded 200-ADMG/2,400-query independent latent-DAG/NetworkX differential as a reproducible test or bounded audit artifact; the current suite contains hand-built counterexamples, not that full oracle sweep.
- B216/B217: run at least one mixed-graph counterexample through the real ID/IDC or transport consumer after the primitive checks; current consumer tests call rule functions directly, and the real ID-engine smoke uses a simple DAG.
- B217: add the card's multiple-action surgery case and ensure outgoing effects survive for each selected action.
- LA-007/LA-019: no current selector verifies removal of the exact sibling .py files with package resolution, filename loader, generated-source inventory, and installed wheel/sdist import behavior. Keep the package directories and defer the installed-distribution pass to CP6.
- Ограничение: LA-007 and LA-019 retirement behavior is not directly tested; current behavioral tests do not establish find_spec/file-loader/package outcomes after the exact files are removed.
- Ограничение: The manual differential result is not a repeatable repository test, and the suite does not demonstrate the full ID-engine route for the fork/collider counterexample.
- Ограничение: PAG/CPDAG and temporal semantics are explicitly outside this static ADMG acceptance unless a separate supported contract is exercised.

<a id="grf-02"></a>

## GRF-02 — Неизменяемый граф, mixed-edge export и версии кэша

**Записи:** B219, B220. **Реестр:** B219=held, B220=partial.
**Маршрут:** первый сбор Q11, Q13; historical C03, C20; дополнительно по готовности новых проб. **Checkpoint:** CP5. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/GRF-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: GRF-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** X→Y и X↔Y не перезаписывают друг друга при перестановке edges. После прогрева export/adjacency новое пустое ребро-представление совпадает с dump и cold-query. Nested mutation отвергается или остаётся только в builder до публикации. Weakref-cleanup сохраняется.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/ir/test_causal_graph_contract.py` → Q11 / C03
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_performance_primitives.py` → Q13 / C20

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_grf_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/ir/test_causal_graph_contract.py tests/unit/foundry/methods/catalog/causal/test_performance_primitives.py
```

**Profile и доступность:** Requires the repository test extra. The three to_networkx tests also require NetworkX at runtime; it is a lazy import and is not a direct pyproject dependency, so provisioned test environments must confirm its presence.; The targeted mutation/cache tests need no database, native graph service, JAX compilation, or build artifact..
**Карта поведения из статического исследования:** Direct behavioral tests of same-endpoint directed/bidirected and lagged edge identity independent of insertion order, duplicate payload keying, and single-edge payload preservation. Cache controls prove weakref eviction, reject nested mutation across graph/edge containers, and prove model_copy(update=...) does not reuse warmed Kuzu rows or adjacency.

**Дополнительные пробы / границы:**
- B219: exercise the actual ID/transport consumer on a graph containing parallel relation kinds if that consumer reads the NetworkX projection; the current tests stop at the export boundary.
- B220: retain the warmed-copy and mutation probes, and include a consumer read after attempted nested metadata mutation if a downstream path can observe metadata independently of topology.
- Check test-environment availability of NetworkX before running the export tests: CausalGraphModel.to_networkx lazily imports it, while pyproject.toml does not declare NetworkX directly. Do not launch a broad extras install for this read-only review.
- Ограничение: No current project test drives a consumer through the parallel-edge export to show that it interprets the multigraph relations correctly.
- Ограничение: NetworkX is an undeclared direct runtime dependency of the export surface; success depends on the installed environment or a transitive extra.

<a id="grf-03"></a>

## GRF-03 — Известные направления и явная временная/частичная семантика

**Записи:** B214, B218. **Реестр:** B214=partial, B218=partial.
**Маршрут:** первый сбор Q09, Q11; historical C03, C06, C13; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/GRF-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: GRF-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** PAG X←Y не превращается в X→Y. CPDAG triangle не получает labelDAG поверх цикла. Lag=1/lag=2 различимы после round-trip; autoregression разрешается в подходящем temporal contract. Малое конечное развёртывание четырёх времён сохраняет ацикличность. Static DAG остаётся рабочим.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_grf_03.py` → Q09 / C13
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_fit.py` → Q09 / C06
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_pag_completion.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/ir/test_causal_graph_contract.py` → Q11 / C03

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_grf_03.py tests/unit/foundry/methods/catalog/causal/test_gcm_fit.py tests/unit/foundry/methods/catalog/causal/test_pag_completion.py tests/unit/ir/test_causal_graph_contract.py
```

**Profile и доступность:** Requires the repository test extra and the project's normal Python 3.14 environment. These selectors do not invoke a native temporal backend or a GPU.; No separate fixture corpus or external artifact is required; tests/unit/remediation/test_grf_03.py is already tracked on the pinned SHA..
**Карта поведения из статического исследования:** Dedicated direct behavioral regression file exists at the pinned SHA. It checks known reversed endpoint normalization and mark preservation, refusal of unresolved CPDAG triangle projection, distinct lag round-trip/DOT output, positive-lag self-edge acceptance versus zero-lag self-loop rejection, and static-DAG identity. Adjacent tests cover unresolved PAG refusal, lagged-edge separation at discovery projection, and contemporaneous-cycle validation.

**Дополнительные пробы / границы:**
- B214: pass a known reversed endpoint through the actual HybridSCMFit/GCM DAG-only consumer and assert the fitted graph uses the canonical direction; the dedicated test calls the projection helper directly.
- B214: keep arbitrary unresolved CPDAG/PAG extension blocked; a triangle rejection is a concrete witness, not a proof of valid extension for all equivalence classes.
- B218: exercise a supported temporal consumer on a small finite unrolled graph (including autoregression and lag1/lag2), because current dedicated tests prove serialized and DOT distinction but do not prove an estimator consumes those time coordinates.
- Recheck all relevant readers before claiming static/temporal consumers share the same graph semantics.
- Ограничение: Current direct tests stop at the projection/helper, IR payload, and DOT surfaces; positive direction and temporal semantics through the actual DAG-only estimator/consumer remain unestablished.
- Ограничение: Full PAG/CPDAG extension semantics and temporal model completeness are bounded limitations, not covered capabilities.

<a id="hyg-02"></a>

## HYG-02 — Evidence/governance/factlog: точные адресные retirement

**Записи:** LA-008, LA-009, LA-018. **Реестр:** LA-008=partial, LA-009=partial, LA-018=partial.
**Маршрут:** первый сбор Q04; historical C16; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/HYG-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK17, LK18.

**Дискриминатор из owner-пакета:** Public Scientist/evidence imports; Core type identity, Lex facts read result/access/provenance; config/string/relative/monkeypatch consumers и negative retired roots. Не восстанавливаются evidence_sources/provenance/claims старые корни. Selected native import tests сейчас, distribution inventory CP6; неизвестные external obligations явно перечислены.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/governance/test_shared_shims.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/lex/mirror_contracts/test_factlog.py` → Q04 / C16
- `policy-engine/tests/unit/scientist/evidence/test_phase44_taxonomy.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/methods/test_import_shims.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/facade/test_phase52_api_extensions.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_hyg_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/governance/test_shared_shims.py tests/unit/lex/mirror_contracts/test_factlog.py tests/unit/scientist/evidence/test_phase44_taxonomy.py tests/unit/scientist/methods/test_import_shims.py tests/unit/scientist/facade/test_phase52_api_extensions.py
```

**Profile и доступность:** Requires the repository test extra. No JAX, GPU, live Lex data, or broad research extra is required by the listed selectors.; The proposed tests/unit/remediation/test_hyg_02.py file is absent at the pinned SHA; use the existing native files and add no duplicate test file solely because the bundle proposed one..
**Карта поведения из статического исследования:** Identity and import-boundary characterization. Governance tests prove the three Scientist pass aliases resolve to Core class objects. Factlog tests prove the Lex facade exports the Fabric callable and a fresh NormPack subprocess uses Fabric without loading the legacy module. Evidence tests check the shim manifest is empty/current and retired roots are absent; the methods shim test rejects a batch of legacy roots.

**Дополнительные пробы / границы:**
- LA-008: before removing _shim.py, do a complete tracked src/tools/config/generated-docs/test string/import census for install_module_shim, shim_getattr, and shim_dir; no direct test currently proves the exact helper file can be removed without a dynamic consumer.
- LA-009: add or retain config-driven TOML/YAML/plugin loading probes and then a negative retired-path test after the migration; current test_shared_shims.py proves class identity while the aliases still exist.
- LA-018: preserve an actual Lex-through-facade read/result test for world-facts access/provenance if the facade remains public; the existing identity assertion does not itself call the reader or inspect returned data.
- Do not remove the live Core passes, Scientist pipeline, Fabric world reader, or protected evidence/OPA surfaces. The package card says unknown external configuration obligations remain unresolved.
- Ограничение: No HYG-02 dedicated regression file exists. Current tests characterize supported aliases; they do not establish full consumer retirement or external compatibility status.
- Ограничение: No test directly verifies _shim.py filename-level removal, dynamic string consumers, or after-removal packaging/import resolution.
- Ограничение: Factlog test coverage asserts object identity, not returned fact/result/provenance parity on the alias call.

<a id="hyg-04"></a>

## HYG-04 — Bootstrap/benchmark wrappers и frontend redirect: конечная миграция

**Записи:** LA-011, LA-012, LA-013. **Реестр:** LA-011=partial, LA-012=partial, LA-013=partial.
**Маршрут:** первый сбор Q05; historical C08; дополнительно D04. **Checkpoint:** CP6. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/HYG-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK16, LK23.

**Дискриминатор из owner-пакета:** Recording command/exit/arguments, early JAX subprocess order без полноценной компиляции, пользовательские env overrides, benchmark object identity и __main__, docs/lifecycle links и package inventory. Реальные apps/runtime-reference-shell, runtime-dashboard и самостоятельные benchmark subtrees сохраняются. Тяжёлая сборка — единый CP6 window, не на каждом alias.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_hyg_04.py` → Q05 / C08

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_hyg_04.py
```

**Profile и доступность:** Requires the repository test extra, Bash for install.sh behavior, and the normal uv/Python 3.14 environment for the real workspace-profile subprocess. The tests do not compile JAX or run benchmark workloads.; No external artifact is generated by this read-only research. The existing file is tracked at the pinned SHA even though the assignment still describes the path as proposed..
**Карта поведения из статического исследования:** A dedicated behavioral regression file exists at the pinned SHA. It uses a fake uv executable to assert install.sh argv and exit forwarding; guarded imports/fresh subprocesses to prove JAX defaults load before JAX; checks Darwin CPU default and explicit overrides; checks benchmark object identity/CLI forwarding/canonical equivalence; enumerates wrapper callers; and validates redirect lifecycle plus preservation of live frontend workspaces.

**Дополнительные пробы / границы:**
- LA-011: test an installed distribution/real supported CLI entry after cutover in the one CP6 package window; current fake-command tests do not execute a system install or JAX compilation.
- LA-012: after the canonical source cutover, verify every bounded in-repo caller/job uses the canonical command, not only that the wrappers forward and match it; external consumers remain unknown.
- LA-013: current checks exercise docs/lifecycle and protect the two live workspaces, but the real final removal/release state must be read back from the branch and rechecked against the lifecycle policy.
- Do not run the actual system bootstrap, frontend builds, benchmark workloads, or a multi-build sweep for this check.
- Ограничение: The current compatibility tests do not prove an installed wheel/sdist or resolve all external consumer obligations.
- Ограничение: The real OS bootstrap, actual JAX backend, heavy benchmark execution, and frontend production builds are intentionally out of scope; those boundaries must remain explicit.

<a id="ing-01"></a>

## ING-01 — Инкрементальный запрос, committed cursor и replay

**Записи:** B79, B80, B88. **Реестр:** B79=partial, B80=partial, B88=closed.
**Маршрут:** первый сбор Q10, Q13, Q20; historical C02, C06, C12; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/ING-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** A зафиксирован до 9, B failed: продвинут только A. Typed/dict manifests эквивалентны. Missing cursor явно означает полный режим. Missing/corrupt replay fixture не вызывает ordinary/live delegate; успешный replay сохраняет provenance.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/fabric/data_plane/test_r13_ingestion_store_custody.py` → Q20 / C06
- `policy-engine/tests/unit/fabric/data_plane/test_modes.py` → Q13 / C12
- `policy-engine/tests/unit/fabric/data_plane/test_cursor_store.py` → Q10 / C02

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ing_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/fabric/data_plane/test_r13_ingestion_store_custody.py tests/unit/fabric/data_plane/test_modes.py tests/unit/fabric/data_plane/test_cursor_store.py
```

**Profile и доступность:** Requires the repository test extra. Replay tests use local fixtures/simulators and assert no ordinary/native live request; they need no live network or cloud dataset.; No proposed tests/unit/remediation/test_ing_01.py exists at the pinned SHA..
**Карта поведения из статического исследования:** Partial bridge and persistence coverage. The mode custody test calls batch_incremental and proves supplied dependencies/store wiring, but its cursor spy returns None and it does not inspect the delegated FetchRequest or successful cursor advancement. Replay tests directly prove missing/corrupt replay does not fall back to live/ordinary ingestion and recorded bytes remain in replay mode. CursorStore tests cover local save/load/find behavior.

**Дополнительные пробы / границы:**
- B79: capture the connector request at the real supported ingestion boundary and assert a valid stored cursor becomes incremental_since; cover typed and dict manifests plus connector-capability/version rejection.
- B80: with two datasets, one source-confirmed and one failed, assert only the confirmed dataset cursor advances to the source boundary; prove it never advances from generic datasets_fetched or local now.
- B79/B80 activation A03: test that missing/unusable cursor clearly selects full mode and that legacy cursors are validated before incremental reads are enabled.
- B88: retain both the current negative no-live-delegate fixture-failure probe and successful replay provenance check; do not infer all replay paths from a mocked wrapper alone.
- Ограничение: No existing nodeid proves B79 request handoff.
- Ограничение: No existing nodeid proves B80 per-source confirmed advancement or failed-source non-advancement.
- Ограничение: The cursor mode wiring test uses the absent-cursor branch, so it cannot demonstrate the incremental request path.

<a id="ing-02"></a>

## ING-02 — Непрерывное окно, позиция и полная lineage

**Записи:** B81, B82, B85. **Реестр:** B81=partial, B82=partial, B85=partial.
**Маршрут:** первый сбор Q07, Q10; historical C02, C19; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/ING-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: ING-01, NET-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Поток [1,2]+[3] даёт одно окно после остановки до chunk commit и после commit с pending buffer. Ошибка после poll/dedupe не теряет строки. Окно A+B хранит обе ссылки; trigger следующего bucket отделён от contributor. COUNT/SESSION/sliding проверяются на десятках строк.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/fabric/data_plane/test_streaming_runtime.py` → Q07 / C19
- `policy-engine/tests/unit/fabric/data_plane/test_cursor_store.py` → Q10 / C02

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ing_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/fabric/data_plane/test_streaming_runtime.py tests/unit/fabric/data_plane/test_cursor_store.py
```

**Profile и доступность:** Requires the repository test extra and normal pyarrow/base runtime dependencies. Tests use local synthetic inputs and filesystem CAS, without external streams or cloud services.; No proposed tests/unit/remediation/test_ing_02.py exists at the pinned SHA..
**Карта поведения из статического исследования:** Behavioral stream recovery, pending window/operator-state serialization and restart, commit-pair rollback, fail-closed missing state, and contributor-lineage tests. B85 is directly covered for multi-chunk contributors, next-bucket trigger versus data contributor, and final flush.

**Дополнительные пробы / границы:**
- B81: current failure injection names cover before chunk persistence and after raw chunk but before checkpoint; add named interruption points after dedupe and after publication if those transitions can strand a cursor/window pair.
- B82: exercise order/pending-state recovery across COUNT, SESSION, and sliding strategies over a representative multi-chunk sequence; current targeted tests prove a pending window/restart path but not the full declared strategy matrix or global exactly-once.
- B85: preserve the existing revoke-A invalidation signal and distinguish data contributors from the chunk that only triggers a window close in every output/flush form.
- The card requires writer-to-reader behavior, so retain the filesystem-CAS restart tests; constructor/state-shape tests alone are insufficient.
- Ограничение: Explicit post-dedupe and post-publication interruption points are not named by the selected existing fault tests.
- Ограничение: The existing tests do not assert a universal exactly-once guarantee; the bundle explicitly forbids that claim.
- Ограничение: Full COUNT/SESSION/sliding strategy coverage over larger sequences remains a probe to map before claiming the complete bundle.

<a id="ing-03"></a>

## ING-03 — Ограниченный stream-state без смены выборки

**Записи:** B83, B84, B86. **Реестр:** B83=partial, B84=partial, B86=partial.
**Маршрут:** первый сбор Q07, Q13; historical C12, C19; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_09.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/ING-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: ING-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** При cap=2 последовательность a, b, c, a одинаково обрабатывается до и после restart. Optional note не меняет accepted set при batch=1/3. Длинная session и крупный chunk не меняют границы окна ради RAM. Малый threshold и счётчики сегментов/сериализации заменяют искусственный OOM.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/fabric/data_plane/test_streaming_runtime.py` → Q07 / C19
- `policy-engine/tests/unit/fabric/data_plane/test_modes.py` → Q13 / C12

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_ing_03.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/fabric/data_plane/test_streaming_runtime.py tests/unit/fabric/data_plane/test_modes.py
```

**Profile и доступность:** Requires the repository test extra and base pyarrow/runtime dependency. No GPU, external connector, cloud stream, or research extra is needed for these nodes.; No proposed tests/unit/remediation/test_ing_03.py exists at the pinned SHA..
**Карта поведения из статического исследования:** Direct behavior probes for bounded count-horizon replay consistency, row/byte backpressure, oversized-block behavior, batch-size-invariant accepted membership under both unknown-schema and bound-schema flows, missing-required/null distinction, non-finite metric quarantine, and schema revision binding. The spill test is a negative witness for explicit rejection when bounded spill is unavailable; it is not proof of production disk spill.

**Дополнительные пробы / границы:**
- B83: the existing restart-invariance node explicitly tests a count horizon. Do not upgrade this to a 24-hour TTL claim; add TTL/disabled/collision tests only if the accepted contract requires them.
- B84: keep the oversized-chunk negative witness; separately demonstrate real spill/consumer memory release if SPILL_TO_DISK is claimed, plus unchanged logical window contents across long sessions. The current test permits explicit unsupported/fail behavior.
- B84: add a small operation/serialization counter assertion if incremental buffered_bytes accounting is part of the accepted fix; current backpressure tests do not independently measure asymptotic reserialization work.
- B86: keep required field, optional absence, explicit null, non-finite value, and batch-size variants distinct; a green shape-only test is not schema-semantic coverage.
- Ограничение: No existing test establishes the original 24-hour dedupe guarantee; current direct restart test is deliberately count-horizon only.
- Ограничение: No test demonstrates actual production spill-to-disk or incremental byte-accounting complexity; current boundedness control accepts explicit refusal.
- Ограничение: The assignment proposes tests/unit/remediation/test_ing_03.py but that file is absent at the pinned SHA.

<a id="jit-01"></a>

## JIT-01 — Правильный warm kernel, single-flight и дешёвая подготовка

**Записи:** B49, B50, B53. **Реестр:** B49=partial, B50=partial, B53=partial.
**Маршрут:** первый сбор Q12; historical C05; дополнительно D04. **Checkpoint:** CP1. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/JIT-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Коэффициенты 2→3 на x=10 дают cold=warm=30, старый handle остаётся 20, kernel не пересобран ради dynamic. Управляемый follower до публикации не создаёт вторую сборку; error/cancel/invalidation завершают ожидания. Счётчик содержательных шагов не удваивается; один маленький настоящий JAX/JIT-тест по слоту N.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_jit_01.py` → Q12 / C05
- `policy-engine/tests/unit/foundry/methods/test_compiler.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/foundry/mirror_contracts/test_specialization.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_jit_01.py tests/unit/foundry/methods/test_compiler.py tests/unit/foundry/mirror_contracts/test_specialization.py
```

**Profile и доступность:** pytest/test extra; jax and jaxlib are base dependencies; CPU is the documented default; apple-metal is optional and not needed.
**Карта поведения из статического исследования:** behavioral_unit; deterministic_concurrency_interleavings; one_native_jax_cpu_case; static_source_contract

**Дополнительные пробы / границы:**
- Keep the event-controlled publication/error/cancel/invalidation cases; they falsify the ordering property deterministically.
- Run the small native JAX test on the supported CPU environment; this pass did not run compilation or inspect XLA compiler telemetry.
- No GPU/Metal or production workload probe is required by this bundle; the data-dependent-shape refusal is already represented by a negative test.
- Ограничение: The mapped tests are present but were not executed in this read-only pass; no current pass result is claimed.
- Ограничение: No production XLA compilation counter/profiler, accelerator backend, or real workload diagnostic was observed; the native test is a narrow CPU signal.

<a id="lex-01"></a>

## LEX-01 — Lex: norm/compliance comparison отдельно от impact-topic эвристики

**Записи:** LA-017. **Реестр:** LA-017=partial.
**Маршрут:** первый сбор Q15, Q17; historical C14, C17; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/LEX-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Unchanged/added/removed/modified norms, issue keys и pass configuration, реальные report refs/bytes, persistence и downstream display. OBLIGATION→compliance_cost tag остаётся предположением темы, не измеренными затратами. Для relocation старое полезное поведение совпадает; изменение label/schema версии явно отделено.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_lex_01.py` → Q15 / C17
- `policy-engine/tests/unit/lex/simulator/test_diff.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/lex/simulator/test_engine.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/integration/lex_ir_foundry/test_normpack_factlog_method_bridge.py` → Q17 / C14

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_lex_01.py tests/unit/lex/simulator/test_diff.py tests/unit/lex/simulator/test_engine.py tests/integration/lex_ir_foundry/test_normpack_factlog_method_bridge.py
```

**Profile и доступность:** pytest/test extra; no research extra or provider credentials identified.
**Карта поведения из статического исследования:** behavioral_unit; local_artifact_persistence; authority_gate_negative; narrow_integration_bridge; structural_architecture

**Дополнительные пробы / границы:**
- Retain all four change classes (unchanged/added/removed/modified) and issue/config behavior in the diff tests.
- Run the local report persistence test and the Lex-to-Foundry bridge together; inspect persisted report/diff refs and bytes.
- Keep topic-to-effect estimates explicitly candidate-only; no quantitative causal impact test is present for the compliance_cost heuristic.
- Ограничение: No final public API/dashboard display test for the saved report was identified in this bundle map.
- Ограничение: OBLIGATION→compliance_cost remains a topic heuristic, not a measured cost/effect; no numeric impact claim is established.
- Ограничение: Generic architecture guardrails are structural only; semantic test files provide the behavior evidence.

<a id="llm-01"></a>

## LLM-01 — Корректная обёртка, необязательная телеметрия и цена reuse

**Записи:** B64, B65, B66. **Реестр:** B64=partial, B65=partial, B66=partial.
**Маршрут:** первый сбор Q04, Q13; historical C02, C16; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/LLM-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Prompt= приходит один раз к поддерживающему provider, user/system/messages неизменны. Падение optional metrics не запускает provider снова и не теряет ответ. Один miss+два hits дают один billable-provider event и отдельный reuse; raw=None не стирает смысл cache-hit.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_llm_01.py` → Q13 / C02
- `policy-engine/tests/unit/scientist/orchestration/llm/test_prompt_cache.py` → Q04 / C16
- `policy-engine/tests/unit/scientist/orchestration/llm/test_cost_metrics.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_llm_01.py tests/unit/scientist/orchestration/llm/test_prompt_cache.py tests/unit/scientist/orchestration/llm/test_cost_metrics.py
```

**Profile и доступность:** pytest/test extra; openai SDK is in base dependencies but the mapped tests use local spies/fakes; no API key or cloud LLM account required.
**Карта поведения из статического исследования:** behavioral_unit; async_fake_provider; optional_sink_failure; billing_reuse_accounting

**Дополнительные пробы / границы:**
- Preserve a provider spy proving one accepted prompt representation reaches the provider once, and conflicting forms fail before invocation.
- Preserve the injected metrics failure and mandatory-accounting failure as distinct cases; verify response exposure and no provider retry.
- Keep provider raw cache metadata from being treated as authoritative evidence of a cache hit or new billable call.
- Ограничение: No live provider response, invoice/usage reconciliation, or remote telemetry export was exercised or requested.
- Ограничение: No end-to-end persisted audit record for external billing was observed; current mapped signal is a local fake-provider/accounting assertion.
- Ограничение: Tests are present but were not executed in this read-only pass.

<a id="llm-02"></a>

## LLM-02 — Разрешённый immutable reuse и single-flight

**Записи:** B67, B68. **Реестр:** B67=partial, B68=partial.
**Маршрут:** первый сбор Q04; historical C16; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/LLM-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: LLM-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Frozen snapshot со ссылкой reuse-ится; живой URL без снимка — нет. Четыре одинаковых разрешённых miss дают один provider-call; другой seed/tenant — отдельный. Отмена одного follower не лишает результата остальных; error не оставляет вечный flight.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/orchestration/llm/test_prompt_cache.py` → Q04 / C16

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_llm_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/orchestration/llm/test_prompt_cache.py
```

**Profile и доступность:** pytest/test extra; openai SDK not needed for the prompt-cache unit cases; no cloud cache extra identified.
**Карта поведения из статического исследования:** behavioral_unit; immutable_snapshot_and_scope; deterministic_single_flight; async_cancel_and_error

**Дополнительные пробы / границы:**
- Exercise frozen URL snapshot reuse and reject changed/missing snapshots, revoked permission, changed model, and live URL without an immutable snapshot.
- Retain four equal allowed misses→one provider spy call; differing seed or tenant stays separate; follower cancellation/error release checks remain.
- Use local mocks only; do not turn this into a live LLM/provider or cloud cache exercise.
- Ограничение: E02 proposed tests/unit/remediation/test_llm_02.py is absent at the pin; coverage is in tests/unit/scientist/orchestration/llm/test_prompt_cache.py.
- Ограничение: No production rate/load, multi-process cache, remote cache, or live provider validation identified.
- Ограничение: Tests are present but were not executed in this read-only pass.

<a id="mig-01"></a>

## MIG-01 — Один migration CLI: делегирование и явная Trinity validation

**Записи:** LA-010, LA-049. **Реестр:** LA-010=closed, LA-049=closed.
**Маршрут:** первый сбор Q17; historical C16; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/MIG-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK26, LK27.

**Дискриминатор из owner-пакета:** Native CLI JSON/YAML: полный Trinity, неполный current-version mapping, malformed nested payload, legacy markers/major bump, готовая model, default/explicit target. Проверить вызов настоящего validator, exit/error identity, source input и atomic output. Прежний root CLI и canonical entry имеют один исполнитель; tuple/auto_migrate consumers сохраняются до lifecycle. Неполный target не считается validated только по version.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_mig_01.py` → Q17 / C16
- `policy-engine/tests/contract/test_ir_migrations.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/contract/test_trinity_migration.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_mig_01.py tests/contract/test_ir_migrations.py tests/contract/test_trinity_migration.py
```

**Profile и доступность:** pytest/test extra; YAML parser is available in current .venv; no heavyweight research extra identified.
**Карта поведения из статического исследования:** behavioral_cli_json_yaml; real_trinity_validator_call; negative_and_error_contract; IR_contract; structural_architecture

**Дополнительные пробы / границы:**
- Exercise the canonical CLI with valid JSON/YAML, current-version incomplete payload, malformed nested payload, legacy/major-version errors, and explicit/default target.
- Verify the root entrypoint delegates to one executor, current-version path calls real Trinity validation, and input/output atomicity and error identity remain covered.
- Keep profile semantics (unchanged/validated/converted) distinct; the architecture guardrail cannot prove this classification.
- Ограничение: No real external/production migration corpus, release promotion, or shell-level deployment invocation was identified in these tests.
- Ограничение: The tests are targeted unit/contract fixtures; they do not establish every consumer lifecycle mentioned by LA-010.
- Ограничение: Architecture guardrails are an independent structural acceptance signal, not semantic validation coverage.

<a id="mig-02"></a>

## MIG-02 — RunManifest: сохраняющее identity преобразование paths

**Записи:** LA-048. **Реестр:** LA-048=partial.
**Маршрут:** первый сбор Q04; historical C01; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/MIG-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: MIG-01. Protected controls: LK15, LK27.

**Дискриминатор из owner-пакета:** Временные реальные files: sub/data.json рядом с чужим data.json; два external пути с одним basename; разные roots; отсутствующий источник; symlink/escape; повтор, relative_path, --to. До/после читается тот же разрешённый объект или точная диагностика, не удобный чужой файл. Containment и atomic output сохранены; отказ не перезаписывает исходный manifest.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_mig_02.py` → Q04 / C01
- `policy-engine/tests/unit/runtime/test_runtime_manifest_paths.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_mig_02.py tests/unit/runtime/test_runtime_manifest_paths.py
```

**Profile и доступность:** pytest/test extra; no cloud storage or heavyweight extra required.
**Карта поведения из статического исследования:** behavioral_local_filesystem; path_identity_and_containment; negative_symlink_escape; adjacent_runtime_paths

**Дополнительные пробы / границы:**
- Use the real temp-directory collision, multiple-root, missing-source, symlink escape, repeated-migration, relative-path, and --to refusal cases.
- Treat the adjacent runtime path suite as consumer context only; it is not the Pydantic RunManifest migration path.
- Do not infer copy behavior from a successful path rewrite; preserve explicit no-implicit-copy checks.
- Ограничение: Full Pydantic RunManifest plus manifest journal were not established as exercised by the path migration tests; LA-048 explicitly bounds its source evidence to narrow functions/two-field ArtifactRef.
- Ограничение: Shell entrypoint and release-promotion path are outside observed tests.
- Ограничение: Path behavior is host-specific; Windows symlink permission behavior remains unverified.

<a id="mig-04"></a>

## MIG-04 — DatasetManifest: converter у schema owner, явная registration

**Записи:** LA-050. **Реестр:** LA-050=partial.
**Маршрут:** первый сбор Q09, Q17; historical C13, C16; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/MIG-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: MIG-01. Protected controls: LK28.

**Дискриминатор из owner-пакета:** Legacy-only/current fields, equal/conflicting aliases, unknown/absent fields, historical fixture, JSON/YAML, no-op/default target, caller isolation, exception types и native Fabric DTO. Версия 1.0 не подставляет raw_hash или created_at. Generic Common import не загружает весь Fabric; CLI binding указывает реального converter.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_mig_04.py` → Q09 / C13
- `policy-engine/tests/unit/remediation/test_mig_01.py` → Q17 / C16
- `policy-engine/tests/unit/core/mirror_contracts/test_manifest.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_mig_04.py tests/unit/remediation/test_mig_01.py tests/unit/core/mirror_contracts/test_manifest.py
```

**Profile и доступность:** pytest/test extra; YAML parser is available in current .venv; no research extra identified.
**Карта поведения из статического исследования:** behavioral_conversion_profile; real_fabric_dto_validation; negative_alias_conflict; lazy_import_behavior; operational_binding; static_mirror_contract; structural_architecture

**Дополнительные пробы / границы:**
- Keep legacy-only/current fields, missing fields, equal/conflicting aliases, native Fabric DTO validation, JSON/YAML registration, default/no-op/error and no eager Fabric import checks.
- Use architecture guardrails for layer-boundary drift and the mirror test for source shape only; conversion and alias results require behavioral tests.
- Any historical artifact fixture should bind a real known profile; the current tests appear synthetic and do not certify a general legacy corpus.
- Ограничение: No broad inventory of persisted historical DatasetManifest artifacts or proof that all historical fields/versions are represented by fixtures.
- Ограничение: A successful Pydantic parse is shape validation, not provenance/admission; the tests do not establish those authorities.
- Ограничение: Structural architecture acceptance cannot prove the converter preserved historical semantics.

<a id="mig-05"></a>

## MIG-05 — Common/IR: общая линейная механика, разные migration profiles

**Записи:** LA-047. **Реестр:** LA-047=partial.
**Маршрут:** первый сбор Q06; historical C04; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_10.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/MIG-05.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK25.

**Дискриминатор из owner-пакета:** Два шага, missing edge, cycle, duplicate registration, bad result type, conflicting version, nested mutation+failure, source version type, no-op identity и реальные registered callbacks. Профили сохраняют объявленные различия; Data Forge shortest-path/branching/instance state не заменяются линейным engine. Public exception identity проверена.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_mig_05.py` → Q06 / C04
- `policy-engine/tests/unit/common/test_migrations_purity.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/contract/test_ir_migrations.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_mig_05.py tests/unit/common/test_migrations_purity.py tests/contract/test_ir_migrations.py
```

**Profile и доступность:** pytest/test extra; no research extra identified.
**Карта поведения из статического исследования:** behavioral_common_ir_profile_matrix; mutation_and_failure_isolation; version_and_error_contracts; one_real_registered_common_callback; structural_architecture

**Дополнительные пробы / границы:**
- Retain separate Common/IR assertions for nested mutation before success/failure, no-op identity, version stamping/conflict, source version type, missing edge/cycle, duplicate registration, bad result type and public exception identity.
- Keep the real Common manifest callback test; it does not substitute for enumerating all registered callbacks in Common and IR.
- Do not fold Data Forge shortest-path/branching/instance-state migration into this linear engine acceptance.
- Ограничение: The LA card explicitly says full interchangeability is false; profile semantics are preserved as distinct.
- Ограничение: Only one real registered Common manifest callback is exercised by the remediation test; no complete live callback corpus or representative registered IR callback inventory was identified.
- Ограничение: Data Forge shortest-path/branching/stateful migrations remain out of scope and are not proven by this suite.

<a id="net-01"></a>

## NET-01 — Владение соединением от acquire до cleanup

**Записи:** B87, B89, B90. **Реестр:** B87=partial, B89=partial, B90=partial.
**Маршрут:** первый сбор Q07, Q11; historical C18, C19; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/NET-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Отмена после permit во время lock/connect/close не уменьшает ёмкость. Закрытый pool не делает double-release. Ошибка subscribe и повторный close завершают cleanup. Медленный connect не блокирует release другого handle. Достаточно пула из 1–2 соединений и управляемых событий.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/fabric/data_plane/test_streaming_runtime.py` → Q07 / C19
- `policy-engine/tests/unit/fabric/connectors/test_registry.py` → Q11 / C18

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_net_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/fabric/data_plane/test_streaming_runtime.py tests/unit/fabric/connectors/test_registry.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Current behavioral tests cover B87 cleanup and most B89 permit/owner transitions. B90 has code-level lock separation but no direct slow-connect concurrency/deadline regression witness.

**Дополнительные пробы / границы:**
- B87: Keep one acquired fake handle and inject subscribe, close, checkpoint, and rewind failures; assert release/close is completed exactly once and the primary exception survives cleanup failure. Add cancellation at startup if cancellation semantics are claimed for these preparation awaits. Existing selectors: tests/unit/fabric/data_plane/test_streaming_runtime.py::test_net01_subscribe_failure_releases_acquired_handle, tests/unit/fabric/data_plane/test_streaming_runtime.py::test_net01_close_failure_can_finish_cleanup_on_retry, tests/unit/fabric/data_plane/test_streaming_runtime.py::test_net01_create_failure_retries_session_cleanup_before_reraising, tests/unit/fabric/data_plane/test_streaming_runtime.py::test_net01_checkpoint_lookup_failure_closes_owned_session, tests/unit/fabric/data_plane/test_streaming_runtime.py::test_net01_rewind_failure_closes_owned_session, tests/unit/fabric/data_plane/test_streaming_runtime.py::test_net01_stream_cleanup_does_not_mask_primary_failure
- B89: With max_size=1, cancel after permit acquisition during connect and disconnect; ensure no replacement appears until physical cleanup, then retry succeeds. Repeated release and acquire-after-close must not inflate permits. Existing selectors: tests/unit/fabric/connectors/test_registry.py::TestConnectionPool::test_release_is_idempotent_per_handle, tests/unit/fabric/connectors/test_registry.py::TestConnectionPool::test_net01_cancelled_connect_releases_reserved_permit, tests/unit/fabric/connectors/test_registry.py::TestConnectionPool::test_net01_cancelled_disconnect_keeps_same_owner_until_cleanup, tests/unit/fabric/connectors/test_registry.py::TestConnectionPool::test_net01_closed_pool_acquire_rejects_while_cleanup_pending, tests/unit/fabric/connectors/test_registry.py::TestConnectionPool::test_net01_close_all_waits_for_pending_release_owner
- B90: Add deterministic event-gated connectors with max_size=2: block the first connect/health check, prove a second connect can start and release of an unrelated handle completes. Separately pin documented acquire queue timeout versus connection/health timeout; do not claim a single end-to-end deadline unless tested. Existing selectors: tests/unit/fabric/connectors/test_registry.py::TestConnectionPool::test_net01_cancelled_connect_releases_reserved_permit
- Ограничение: The assignment-proposed tests/unit/remediation/test_net_01.py does not exist at the pin; direct tests live in the two native test modules listed above.
- Ограничение: No direct deterministic witness was found for B90 independent slow-connect progress or end-to-end timeout composition.

<a id="net-02"></a>

## NET-02 — Редкий rate, поколения circuit и невыбрасываемая защита

**Записи:** B91, B92, B93. **Реестр:** B91=partial, B92=partial, B93=partial.
**Маршрут:** первый сбор Q08; historical C17; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/NET-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Rate=0.2/cap=1 разрешает один запрос и следующий через 5 по управляемым часам. Weighted request сверх capacity отвергается. Старый CLOSED-success не закрывает новый HALF_OPEN. TTL/pressure не сбрасывает Retry-After и не создаёт второй независимый регулятор.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/fabric/connectors/test_resilience.py` → Q08 / C17

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_net_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/fabric/connectors/test_resilience.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Direct fake-clock and state-transition tests cover B91 and B92; B93 has pressure/TTL witnesses for cooldown and OPEN state, with an active HALF_OPEN lease case still absent.

**Дополнительные пробы / границы:**
- B91: Use a fake monotonic clock for 0.1/0.2/1/2 rps, unit and over-capacity requests, cold start, Retry-After, and cancellation; assert unit admission plus configured long-term pacing. Existing selectors: tests/unit/fabric/connectors/test_resilience.py::test_rate_limiter_sub_unit_rate_accepts_unit_request_and_preserves_pacing, tests/unit/fabric/connectors/test_resilience.py::test_rate_limiter_single_capacity_keeps_declared_long_term_rate, tests/unit/fabric/connectors/test_resilience.py::test_rate_limiter_rejects_weight_above_capacity_without_waiting, tests/unit/fabric/connectors/test_resilience.py::test_rate_limiter_cancellation_does_not_consume_unacquired_request
- B92: With fake time/events, complete an old CLOSED request after OPEN->HALF_OPEN; preserve its result/error and leave the new generation to its own probe. Retain wrong-owner/repeated-finalization diagnostics. Existing selectors: tests/unit/fabric/connectors/test_resilience.py::test_circuit_breaker_late_closed_success_does_not_claim_new_half_open_generation, tests/unit/fabric/connectors/test_resilience.py::test_circuit_breaker_late_closed_failure_preserves_original_error, tests/unit/fabric/connectors/test_resilience.py::test_circuit_breaker_stale_half_open_token_does_not_steal_new_generation
- B93: Under pressure and TTL, hold an active HALF_OPEN lease and a nonzero cooldown; reacquiring the same key must not mint an independent fresh regulator. Confirm finite capacity reports a typed refusal when every entry is protected. Existing selectors: tests/unit/fabric/connectors/test_resilience.py::test_bounded_registry_pressure_preserves_rate_limit_cooldown, tests/unit/fabric/connectors/test_resilience.py::test_bounded_registry_ttl_preserves_rate_limit_cooldown, tests/unit/fabric/connectors/test_resilience.py::test_bounded_registry_pressure_preserves_open_circuit_state
- Ограничение: The assignment-proposed tests/unit/remediation/test_net_02.py does not exist at the pin; use the existing test_resilience.py nodes.
- Ограничение: B93 lacks a direct active HALF_OPEN lease/pressure or protected-capacity-refusal regression test.

<a id="obs-01"></a>

## OBS-01 — Календарные observation helpers: перенос и корректные периоды

**Записи:** B146, LA-031. **Реестр:** B146=partial, LA-031=held.
**Маршрут:** первый сбор Q04; historical C03; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OBS-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: UDF-01. Protected controls: LK12.

**Дискриминатор из owner-пакета:** Relocation: valid month/quarter/year дают прежние bytes/поля. Bugfix: 2024-02 заканчивается 29-м; invalid и missing не становятся датами. Сохраняется уникальный-period precompute; native sources caller читает новый helper. B147 — отдельный OBS-02.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_obs_01.py` → Q04 / C03
- `policy-engine/tests/unit/data_forge/domains/ukraine/test_builders.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_obs_01.py tests/unit/data_forge/domains/ukraine/test_builders.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** B146 has semantic calendar/invalid-input and consumer tests. LA-031 is partially advanced: period ownership and caller/facade boundaries are tested; the broader common.py split is explicitly assigned to later UDF-02 closure.

**Дополнительные пробы / границы:**
- B146: Assert leap and ordinary February, quarter/year bounds, missing/malformed/invalid month typed absence, and downstream consumer quarantine; never coerce an invalid period to a concrete date. Existing selectors: tests/unit/remediation/test_obs_01.py::test_canonical_period_owner_uses_inclusive_calendar_bounds, tests/unit/remediation/test_obs_01.py::test_period_owner_rejects_unknown_periods_without_2025_fallback, tests/unit/remediation/test_obs_01.py::test_period_series_preserves_unique_mapping_and_typed_absence_for_bad_rows, tests/unit/remediation/test_obs_01.py::test_source_observation_consumer_uses_canonical_period_bounds, tests/unit/remediation/test_obs_01.py::test_household_demography_consumer_preserves_valid_period_and_rejects_bad_dates, tests/unit/remediation/test_obs_01.py::test_graph_consumer_quarantines_missing_or_invalid_period_edges
- LA-031: Treat this as staged only: verify period helper owner/import aliases and actual consumers here; broader I/O, bindings, and common facade extraction belongs to the named UDF-02 closure owner. Existing selectors: tests/unit/remediation/test_obs_01.py::test_period_helpers_have_one_canonical_owner_and_compatibility_aliases, tests/unit/remediation/test_obs_01.py::test_builder_facade_exports_only_the_declared_stage_surface, tests/unit/remediation/test_obs_01.py::test_legacy_runner_private_facade_aliases_remain_explicit_only
- Ограничение: LA-031 is not full cleanup completion; the bundle explicitly leaves remaining split work under UDF-02.
- Ограничение: No real population-wide invalid-period prevalence or production data refresh is established by unit fixtures.

<a id="obs-02"></a>

## OBS-02 — Observation reader: непрерывность после partial yield

**Записи:** B147. **Реестр:** B147=partial.
**Маршрут:** первый сбор Q03; historical C10; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OBS-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: UDF-02. Protected controls: LK12.

**Дискриминатор из owner-пакета:** Сбой до выдачи, после первого batch и между двумя metric frames не повторяет префикс и не теряет наблюдения. На двух blocks проверить итоговые shard IDs/counts, snapshot и отсутствие full-read memory обхода. Малый настоящий Parquet-reader плюс controlled failure.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_obs_02.py` → Q03 / C10

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_obs_02.py
```

**Profile и доступность:** test; base project dependencies: pandas, pyarrow, duckdb.
**Карта поведения из статического исследования:** Local semantic/integration tests include injected reader failures, real temporary Parquet batches, snapshot binding, and the D2 shard consumer.

**Дополнительные пробы / границы:**
- B147: Exercise failure before first yield, after a confirmed batch, between metric frames, missing resume cursor, and changed snapshot; verify emitted observation IDs, shard counts, and no duplicate prefix. Existing selectors: tests/unit/remediation/test_obs_02.py::test_partial_batch_failure_resumes_without_republishing_confirmed_prefix, tests/unit/remediation/test_obs_02.py::test_failure_between_metric_frames_resumes_at_confirmed_metric_cursor, tests/unit/remediation/test_obs_02.py::test_partial_resume_aborts_when_unchanged_snapshot_lacks_pending_metric_cursor, tests/unit/remediation/test_obs_02.py::test_small_real_parquet_reader_preserves_metric_counts_and_snapshot_values, tests/unit/remediation/test_obs_02.py::test_partial_resume_aborts_when_normalized_snapshot_changes, tests/unit/remediation/test_obs_02.py::test_build_d2_materializes_unique_observation_shards_and_counts
- Ограничение: Several failure cases use a controlled ParquetFile shim; retain the existing small real-Parquet reader/D2 consumer checks as the runtime artifact witness.
- Ограничение: No large-file memory bound, production dataset, or remote storage behavior is established.

<a id="opt-01"></a>

## OPT-01 — Метрика, полная координата и строгий Pareto

**Записи:** B108, B109, B110, B111. **Реестр:** B108=partial, B109=partial, B110=partial, B111=partial.
**Маршрут:** первый сбор Q06, Q20; historical C13; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Альтернативный budget_deficit используется при отсутствующем gov_balance, настоящий 0 сохраняется. При максимизации точка (2,1) доминирует (1,1); равные значения не подменяют IDs. Train/holdout не сливаются. NaN/inf и неверный reference point не портят фронт. Малый slow oracle проверяет быстрый алгоритм.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/methods/search/test_objective.py` → Q06 / C13
- `policy-engine/tests/unit/scientist/methods/autotune/test_pareto.py` → Q20 / C13

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_opt_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/methods/search/test_objective.py tests/unit/scientist/methods/autotune/test_pareto.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Native semantic tests cover metric fallback/presence, strict 2D/3D dominance, full coordinate identity, missing/nonfinite metrics, and an independent slow Pareto oracle.

**Дополнительные пробы / границы:**
- B108: Test missing/null primary plus valid deficit, explicit zero, aliases/sign, conflicting values, and non-finite input; missing must not turn into favorable zero. Existing selectors: tests/unit/scientist/methods/search/test_objective.py::test_budget_deficit_normalizes_missing_null_alias_and_sign, tests/unit/scientist/methods/search/test_objective.py::test_budget_deficit_marks_missing_metric_unusable, tests/unit/scientist/methods/search/test_objective.py::test_budget_deficit_keeps_non_finite_metric_unusable, tests/unit/scientist/methods/search/test_objective.py::test_budget_deficit_rejects_conflicting_balance_aliases
- B109: Compare optimized 1-4D results against a direct slow dominance oracle for equality at one coordinate, same-point identity, permutations, and both objective directions. Existing selectors: tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_two_dimensional_fast_front_removes_equal_secondary_value_from_later_group, tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_three_dimensional_fast_front_removes_equal_secondary_value_from_later_group, tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_fast_front_matches_independent_slow_oracle, tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_three_objective_front_matches_slow_reference
- B110: Serialize and round-trip duplicate display names across split/unit/direction; changing display labels must not change coordinate semantics. Existing selectors: tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_coordinate_identity_keeps_split_unit_and_direction, tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_coordinate_schema_round_trips_and_labels_reference_point, tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_single_axis_identity_distinguishes_absent_and_present_unit
- B111: Permute missing/NaN/inf inputs; preserve their typed exclusion reason and ensure the finite subset/hypervolume is finite or explicitly unavailable. Existing selectors: tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_non_finite_and_missing_metrics_are_excluded_from_numeric_front, tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_mixed_objective_coverage_is_typed_and_keeps_finite_front, tests/unit/scientist/methods/autotune/test_pareto.py::TestParetoFront::test_invalid_reference_point_does_not_emit_non_finite_hypervolume
- Ограничение: All evidence is local algorithm/DTO behavior; no real benchmark population or downstream promotion workload is executed.

<a id="opt-02"></a>

## OPT-02 — Настоящий SearchSpace и координаты фактического исполнения

**Записи:** B112, B113, B127. **Реестр:** B112=partial, B113=partial, B127=partial.
**Маршрут:** первый сбор Q16; historical C06, C13; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: OPT-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Backend получает поддержанные sample_sobol/denormalize. Разные параметры не превращаются в 0.5; отсутствие оценки не становится успешную оценку 0. Две координаты одного discrete action связаны с одним исполнением, но отдельные допустимые реплики сохраняются.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/methods/autotune/test_bayesian_generator.py` → Q16 / C13
- `policy-engine/tests/unit/scientist/search/strategies/test_bayesian.py` → Q16 / C06

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_opt_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/methods/autotune/test_bayesian_generator.py tests/unit/scientist/search/strategies/test_bayesian.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Adapter tests cover canonical mixed SearchSpace wiring and history identity; canonical Bayesian strategy tests cover effective integer/category duplicate detection and replica seeds.

**Дополнительные пробы / границы:**
- B112: Drive the first candidate through the canonical SearchSpace sample/denormalize path with continuous, integer and categorical bounds; distinguish an honest optional-backend fallback from a falsely advertised Bayesian execution. Existing selectors: tests/unit/scientist/methods/autotune/test_bayesian_generator.py::test_first_sobol_candidate_uses_native_search_space_protocol, tests/unit/scientist/search/strategies/test_bayesian.py::test_bayesian_cold_start_uses_sobol
- B113: Use two distinct parameter sets and full candidate/evaluation/origin IDs; assert normalized coordinates differ, missing score is unusable, and split/replica metadata stays bound. Link adapter output to actual GP training if claiming the whole path. Existing selectors: tests/unit/scientist/methods/autotune/test_bayesian_generator.py::test_search_iteration_history_preserves_origin_params_split_and_full_ids, tests/unit/scientist/methods/autotune/test_bayesian_generator.py::test_history_identity_conflicts_fail_closed, tests/unit/scientist/methods/autotune/test_bayesian_generator.py::test_history_without_score_is_not_a_successful_zero_observation, tests/unit/scientist/methods/autotune/test_bayesian_generator.py::TestBenchmarkToEvaluation::test_preserves_full_identity_split_origin_and_candidate_params
- B127: Two relaxed integer/category vectors mapping to one effective action must deduplicate; distinct action and independent seed stay distinct. Add a continuous-parameter control because current direct duplicate tests focus on integer/category. Existing selectors: tests/unit/scientist/search/strategies/test_bayesian.py::test_duplicate_detection_uses_canonical_integer_and_category_execution, tests/unit/scientist/search/strategies/test_bayesian.py::test_duplicate_detection_keeps_same_replicate_different_seed_distinct
- Ограничение: The strategy tests live under tests/unit/scientist/search/strategies but import the canonical methods.search.strategies owner; retain the canonical import.
- Ограничение: No single current test demonstrates adapter history flowing all the way into GP training, and continuous effective-action deduplication has no explicit probe.

<a id="opt-03"></a>

## OPT-03 — Рабочий warm-start и сохранённое GP-состояние

**Записи:** B114, B115. **Реестр:** B114=partial, B115=partial.
**Маршрут:** первый сбор Q16; historical C06; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: OPT-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Исторические оценки действительно достигают GP training/conditioning и начального порога. Новый observation не создаёт модель с defaults. Несовместимые bounds/transforms исключаются адресно. Tiny GP на 8–12 точках выполняется в K3; локальный boundary test использует spy.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/search/strategies/test_bayesian.py` → Q16 / C06

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_opt_03.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/search/strategies/test_bayesian.py
```

**Profile и доступность:** test; search_bo (required; otherwise pytest skipif omits both B114/B115 witnesses).
**Карта поведения из статического исследования:** Direct real-BoTorch tests exist for warm history reaching GP training and conditioning an appended observation without refit; both are skipped when the search_bo stack is unavailable.

**Дополнительные пробы / границы:**
- B114: With search_bo installed, pass compatible warm evaluations plus current evaluation through suggest; spy on _prepare_training_data/_fit_gp and assert effective training includes each unique permitted record, excludes foreign basis/context and preserves independent replicas. Existing selectors: tests/unit/scientist/search/strategies/test_bayesian.py::test_bayesian_warm_start_reaches_gp_training_before_initial_threshold
- B115: Use the existing bounded 8->9 observation case; assert one optimizer fit, learned parameters/transforms persist, new training X is consumed, and a non-append or conditioning failure takes the explicit bounded-refit path. Existing selectors: tests/unit/scientist/search/strategies/test_bayesian.py::test_bayesian_no_refit_preserves_learned_gp_state_with_new_observation
- Ограничение: No test was run under this read-only assignment. If search_bo is absent, do not count the skip as verification; defer the native result rather than installing outside I1.
- Ограничение: Prediction-quality equivalence and performance cost are not established by the state-preservation tests.

<a id="opt-04"></a>

## OPT-04 — Привязанный champion и compare-and-publish

**Записи:** B116, B117. **Реестр:** B116=partial, B117=partial.
**Маршрут:** первый сбор Q12; historical C05; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_11.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: OPT-01, OPT-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Чужая evaluation или другой suite не promote. Старый score=2 не переписывает уже опубликованный score=3. Сравнение против нового predecessor выполняется явно. Две управляемые локальные попытки проверяют гонку; новый comparison profile требует собственного перехода.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/methods/autotune/test_registry_and_runner.py` → Q12 / C05

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_opt_04.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/methods/autotune/test_registry_and_runner.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Binding failures and deterministic compare-and-publish race are covered with local FileSystemCAS/temp files and two controlled writer threads.

**Дополнительные пробы / границы:**
- B116: Pair candidate/evaluation IDs, loop, suite/version and compare split; mismatches leave pointer unchanged, while a matching basis can promote. Existing selectors: tests/unit/scientist/methods/autotune/test_registry_and_runner.py::test_champion_registry_rejects_evaluation_for_different_candidate, tests/unit/scientist/methods/autotune/test_registry_and_runner.py::test_champion_registry_rejects_evaluation_for_different_loop, tests/unit/scientist/methods/autotune/test_registry_and_runner.py::test_champion_registry_rejects_incompatible_suite, tests/unit/scientist/methods/autotune/test_registry_and_runner.py::test_champion_registry_rejects_wrong_comparison_split, tests/unit/scientist/methods/autotune/test_registry_and_runner.py::test_search_loop_runner_rejects_evaluator_from_foreign_suite
- B117: Use the existing event-gated score-2/score-3 two-writer schedule; final pointer must remain at 3, and stale writer must compare against current predecessor. If multi-process writers are a supported mode, add a subprocess-level witness. Existing selectors: tests/unit/scientist/methods/autotune/test_registry_and_runner.py::test_champion_registry_serializes_compare_and_publish_against_new_predecessor, tests/unit/scientist/methods/autotune/test_registry_and_runner.py::test_champion_registry_keeps_newer_champion_when_stale_score_arrives
- Ограничение: No external/multi-process deployment workload was exercised; the current race test uses threads in one process.

<a id="pcl-01"></a>

## PCL-01 — Предиктивная калибровка: знаменатель, receipt и canonical tests

**Записи:** LA-052, LA-053. **Реестр:** LA-052=partial, LA-053=partial.
**Маршрут:** первый сбор Q10, Q13; historical C04, C12; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/PCL-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK01, LK30, LK32.

**Дискриминатор из owner-пакета:** 100 finite y_true + intervals={} или []/levels=[] не получают положительного tier; missing/surplus/misaligned пары видны. 95/100 при 0.95 и 0/100 различимы; small-sample downgrade сохранён. Native report/TruthfulnessReceipt не заменяются fixture. Binary/multiclass не обязаны иметь interval_coverage. Identity трёх public objects и поддержанного старого alias проверяется.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/calibration/test_continuous.py` → Q13 / C04
- `policy-engine/tests/unit/scientist/methods/backtesting/test_calibration_curve.py` → Q10 / C12
- `policy-engine/tests/unit/ir/analytics/test_calibration_diagnostics_report.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_pcl_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/calibration/test_continuous.py tests/unit/scientist/methods/backtesting/test_calibration_curve.py tests/unit/ir/analytics/test_calibration_diagnostics_report.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Owner-level numerical and report-to-TruthfulnessReceipt behavior. Existing tests cover 100 finite observations with empty mapping/sequence, not_evaluated receipt downgrade, healthy 95/100 coverage, zero-coverage downgrade, small-sample downgrade, mismatched/misaligned inputs, and identity of CalibrationPoint/CalibrationResult/compute_calibration_curve across implementation, public API, and Scientist alias. Static inspection only; not executed.

**Дополнительные пробы / границы:**
- Compare 0/100 with 95/100 on the same 100-observation denominator; current positive case uses 95/100, while the zero-coverage receipt case uses three observations.
- Pin both missing and surplus mapping/sequence members at the report-to-receipt boundary, including the reported evaluated-comparison count.
- Explicitly preserve a multiclass report without interval_coverage; the IR model test covers a healthy binary receipt but not multiclass evaluation.
- Finish moving the substantive generic curve tests into the calibration owner suite; the existing curve tests still live under Scientist backtesting.
- Ограничение: The proposed tests/unit/remediation/test_pcl_01.py does not exist; extend the owner tests rather than adding a duplicate suite.
- Ограничение: PCL-01 consolidation/coverage is partial: the requested same-denominator 0/100 contrast and explicit multiclass case are not pinned.

<a id="plg-01"></a>

## PLG-01 — DomainPlugin: общая discovery-механика без смены ABI

**Записи:** LA-022. **Реестр:** LA-022=partial.
**Маршрут:** первый сбор Q03; historical C10; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/PLG-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK08.

**Дискриминатор из owner-пакета:** Builtin/dev/entrypoint plugins, dependency/load/unload, duplicate IDs, import error и deterministic ordering. Выбранный economics plugin создаётся через прежний ABI; FoundryMethodPlugin не подменяется DomainPlugin. Малые временные plugin files вместо установки всех packages.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_plg_01.py` → Q03 / C10
- `policy-engine/tests/unit/foundry/plugins/test_plugin_system.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_plg_01.py tests/unit/foundry/plugins/test_plugin_system.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral fixture tests for DomainPlugin ABI/lifecycle, builtin EconomicsPlugin, declared polisyos.plugins entry-point group, dev directories, deterministic directory ordering, import failures, duplicate IDs, dependency/unload behavior, and Core's source-file loader seam. No tests run.

**Дополнительные пробы / границы:**
- Exercise a genuinely installed distribution/entry point through importlib.metadata; current entry-point test uses a monkeypatched EntryPoint and a temporary source file.
- Pin one aggregate deterministic source/error ordering across builtins, entry points, prefix-discovered distributions, and directories.
- The current implementation still has separate builtin, entry-point/distribution, and directory discovery flows; only the directory flow delegates to Core's load_module_from_file. Verify the requested single collector/error path before calling consolidation complete.
- Verify the planned lifecycle for distribution-prefix scanning after explicit declarations; package-prefix scanning remains active in _discover_installed_plugins.
- Ограничение: The proposed path already exists, but its focused tests do not prove behavior for installed packages or a unified collector across all source types.
- Ограничение: Relevant pattern pass: P06 (compatibility/ABI), P27 (reuse canonical owner); preserve DomainPlugin semantics and the polisyos.plugins group.

<a id="plg-02"></a>

## PLG-02 — PolisySimulator: честный rollout result вместо псевдообучения

**Записи:** LA-023. **Реестр:** LA-023=partial.
**Маршрут:** первый сбор Q04; historical C15; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/PLG-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Fixture rollout с rewards [2,2,2] и нулём optimizer updates остаётся полезным evaluation, не trained policy. Train запрос без совместимого execution adapter даёт точную capability причину. Старые simulation/domain routines работают; CLI текст и return semantics согласованы.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_plg_02.py` → Q04 / C15

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_plg_02.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral tests keep simulator.run as a SimulationResult and return a typed bridge_pending result for an unsupported training profile; the CLI omits Training complete and Final loss for that result. No tests run.

**Дополнительные пробы / границы:**
- Assert the specified [2,2,2] reward rollout as useful evaluation data without presenting it as optimizer loss; the current test checks rollout type, step count, and trajectory presence, not those rewards.
- No historical TrainingResult deserializer/reader was found in the plugin path or its focused tests. If historical payloads are supported, test that an old reward trace cannot become trained-state evidence.
- TrainingResult is a plain dataclass with status defaulting to trained; determine supported historical construction/read paths before relying on that default as migration semantics.
- Ограничение: Historical-result compatibility remains verification_missing until a supported read path and provenance behavior are identified and tested.
- Ограничение: Relevant pattern pass: P04/P05/P14 — status and training authority must follow actual optimizer/update evidence, not reward traces.

<a id="plg-03"></a>

## PLG-03 — Один DomainPlugin → существующий trainer: реальный learning bridge

**Записи:** LA-023. **Реестр:** LA-023=partial.
**Маршрут:** первый сбор Q05; historical C08; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/PLG-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: PLG-02. Protected controls: LK08.

**Дискриминатор из owner-пакета:** Один tiny native rollout и один-два optimizer updates: nonzero gradient меняет параметры и следующие actions; zero gradient вправе не менять. Train/eval, RNG/reset/continuation и learned artifact readback. Unsupported CompositeState сохраняет честное ограничение, не silent default. Без совместимого adapter LA-023 остаётся частично завершённой.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_plg_03.py` → Q05 / C08
- `policy-engine/tests/unit/foundry/agent_sim/test_training.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_plg_03.py tests/unit/foundry/agent_sim/test_training.py
```

**Profile и доступность:** test; agent-sim.
**Карта поведения из статического исследования:** Bounded Economics DomainPlugin-to-existing-trainer bridge tests. They run a small native training configuration, require trained status, parameter movement, finite loss, artifact persistence/readback, tenant-store enforcement, and bridge_pending for unsupported composite state. The adapter also checks parameter and action deltas. No tests run.

**Дополнительные пробы / границы:**
- Add an explicit assertion that the same observation produces a changed post-training action; current primary witness asserts parameter delta and finite action, while trained status depends on the adapter's action-delta guard.
- Add a zero-gradient/no-update control and verify the result stays honest rather than claiming training completion.
- Exercise train/eval separation and reset/RNG/continuation on the actual Economics adapter, rather than relying only on the canonical trainer's separate tests.
- Ограничение: semantic_test_missing for the explicit post-update action and zero-gradient controls; current parameter delta is useful but is not the clearest standalone witness for those two cases.
- Ограничение: Relevant pattern pass: P01/P02/P04/P14 — one existing trainer, typed bridge status, persisted artifact, and measured policy effect.

<a id="rep-01"></a>

## REP-01 — Runtime replay: прямой Scientist owner без лишнего compatibility hop

**Записи:** LA-033. **Реестр:** LA-033=partial.
**Маршрут:** первый сбор Q06; historical C15; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/REP-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK15.

**Дискриминатор из owner-пакета:** Actual enum/signature/identity; lazy import не грузит runtime до запроса; --check-only и малый persisted replay/resume. Unknown symbol отказывает. Исторические run manifests и runtime/quality/replay.py остаются. Wheel/package validation объединяется с CP6.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_rep_01.py` → Q06 / C15
- `policy-engine/tests/unit/scientist/replay/test_deterministic_compatibility.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/runtime/test_replay_input_bindings_completeness.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/runtime/test_replay_runtime.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_rep_01.py tests/unit/scientist/replay/test_deterministic_compatibility.py tests/unit/runtime/test_replay_input_bindings_completeness.py tests/unit/runtime/test_replay_runtime.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Direct-owner/lazy-import tests cover the ten-symbol Runtime root, twenty-symbol compatibility window, unknown-symbol failure, delayed Core CLI import, benchmark import, dynamic inventory, check-only incomplete packet, persisted checkpoint resume, and historical manifest/quality replay availability. No tests run.

**Дополнительные пробы / границы:**
- Add a check-only case with a complete persisted packet that proves the successful admissibility path without invoking replay execution; the current CLI witness is deliberately incomplete/unreadable.
- Run wheel/package validation at the separately assigned CP6 checkpoint; the focused unit command does not prove built-distribution imports.
- Keep the 20-symbol compatibility window until actual external-consumer retirement evidence is complete; do not treat this direct-import migration as alias retirement.
- Ограничение: Compatibility module remains intentionally present and identity-tested; final removal is a separate lifecycle decision.
- Ограничение: Verification_missing for wheel/package validation until CP6; no packaging/build command was run.

<a id="req-01"></a>

## REQ-01 — DataRequirement: явный контекст и ограниченная private-очистка

**Записи:** LA-045, LA-046. **Реестр:** LA-045=partial, LA-046=partial.
**Маршрут:** первый сбор Q07, Q08; historical C05, C18; дополнительно D04. **Checkpoint:** CP1. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/REQ-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK24, LK31.

**Дискриминатор из owner-пакета:** Сравнить AST всех оставшихся функций cleanup-коммита. Generic запрос другой jurisdiction/даты не наследует UA/2022; parent-support и отрицание rent не создают обязательного требования по подстроке ID. Optional/mandatory resolver, explicit constructs и opt-in family fallback сохраняют свои правила. Полный N7 caller проверяет ACQ-01.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/data_requirement/test_compiler.py` → Q08 / C18
- `policy-engine/tests/unit/remediation/test_acq_01.py` → Q07 / C05

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_req_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/data_requirement/test_compiler.py tests/unit/remediation/test_acq_01.py
```

**Profile и доступность:** test; runtime.
**Карта поведения из статического исследования:** Canonical compiler tests cover opaque scenario IDs, negation, generic scope, explicit-construct precedence, no proposal crossing the resolver boundary, text/request and domain/domain_hint adapter input, feature-flagged legacy fallback, report persistence, and strict resolver requirements. Adjacent ACQ-01 selectors cover the N7 handoff, explicit specs, scope/resolver transfer, and refusal to acquire with empty specs. Resolver/compiler ports in those handoff witnesses are test doubles. No tests run.

**Дополнительные пробы / границы:**
- Before claiming LA-045 closure, complete the source-wide caller scan for all seven named private helpers, _DATA_FAMILY_ORDER, and the AM03 _digest; this research pass only observed that the named definitions are absent from the current compiler file.
- Exercise one real resolver/index consumer with a non-UA jurisdiction and non-2022 date through the N7 caller; existing compiler/N7 tests use recording or fake resolver ports.
- Keep the compiler semantic tests and ACQ-01 handoff test distinct: the latter is the consumer-side witness and is not replaced by test_compiler.py.
- Ограничение: The proposed test_req_01.py does not exist; current compiler owner tests already cover most LA-046 semantics, so add only uncovered cases to that owner.
- Ограничение: verification_missing for full external caller census and real resolver/index boundary; do not infer zero callers from module-local absence.
- Ограничение: Relevant pattern pass: P10/P16/P37/P38 — distinguish candidate lexical proposals from the typed resolver predicate and name the real consumer boundary.

<a id="res-01"></a>

## RES-01 — Повторный resume, достаточный state и дешёвый индекс

**Записи:** B63, B70, B71. **Реестр:** B63=partial, B70=partial, B71=partial.
**Маршрут:** первый сбор Q04, Q13, Q18; historical C04, C06, C08; дополнительно D02. **Checkpoint:** CP2. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/RES-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: STA-02, RES-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** A→B→C переживает две остановки: A/B не запускаются заново. Полный valid-state без ненужного cache seed продолжает C; две копии A не покрывают B. 100 повторных точных refs не дают 100 повторных чтений; failed load не помечается проверенным. Changed functional input остаётся несовместимым.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_res_01.py` → Q04 / C04
- `policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint.py` → Q18 / C06
- `policy-engine/tests/integration/scientist/test_checkpoint_resume.py` → Q13 / C08

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_res_01.py tests/unit/scientist/orchestration/engine/test_checkpoint.py tests/integration/scientist/test_checkpoint_resume.py
```

**Profile и доступность:** test; runtime.
**Карта поведения из статического исследования:** Focused unit witnesses cover repeated exact-ref deduplication and failed-load retry, same-key/different-content handling, A→B→C double resume preserving origin fingerprint, complete-state resume without cache seeds, missing required state refusal, allow_replay behavior, changed functional input refusal, and duplicate refs not counting as independent coverage. One existing integration selector exercises durable local CAS resume when trace is truncated. No tests run.

**Дополнительные пробы / границы:**
- Measure the B63 whole path across trace refs plus checkpoint refs and the first real get, including bytes/read count and time-to-first-useful-work; the focused counter test covers seed_from_entry_refs, not remote CAS performance or the combined trace/checkpoint path.
- Obtain operated Temporal/Ray and external-state sufficiency evidence for B63/B70/B71; local FileSystemCAS and runner fixtures cannot close the external_institution blocker recorded in E02R2 PARTIAL_TRIAGE.
- Keep origin fingerprint and functional-input mismatch tests alongside cache-seed optimization; do not let allow_replay stand in for a restored missing state.
- Ограничение: External service/runtime evidence remains not_established; do not upgrade B63/B70/B71 from local tests.
- Ограничение: Performance-effect evidence is semantic_test_missing for trace-plus-checkpoint duplicate reads and representative remote CAS latency.

<a id="res-02"></a>

## RES-02 — Единый завершённый frontier и атомарный tier checkpoint

**Записи:** B72, B73. **Реестр:** B72=partial, B73=partial.
**Маршрут:** первый сбор Q02, Q13; historical C08, C20; дополнительно D02. **Checkpoint:** CP2. **Исследователь:** e02_12.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/RES-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: STA-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Независимый сосед не меняет skip в completed. A/B increment: остановка после первой публикации не применяет B дважды. A=ok/B=fail при fail_fast и continue даёт согласованные returned state, durable head и компенсацию. CAS-результат завершённого вычисления не уничтожается из-за rollback state.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_res_02.py` → Q02 / C20
- `policy-engine/tests/integration/scientist/test_checkpoint_resume.py` → Q13 / C08

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_res_02.py tests/integration/scientist/test_checkpoint_resume.py
```

**Profile и доступность:** test; runtime.
**Карта поведения из статического исследования:** Unit witnesses exercise native skip/ok outcomes in single and parallel executor branches, full-tier completion/cache refs, fail_fast rollback versus continue, and checkpoint-hook requirements. Integration witnesses use real local CAS, spawned fresh reader processes, publication cut points, and failure-policy resume to compare durable state with completed frontier. No tests run.

**Дополнительные пробы / границы:**
- Add or identify a fresh-process durable checkpoint/resume case where a native skip is followed by a dependent node; current B72 witnesses assert checkpoint completed sets through a recording hook but do not restart from a persisted skip checkpoint.
- No live remote runner or remote persistence service is exercised by the B73 local FileSystemCAS process-boundary tests; keep that limitation explicit.
- Ограничение: B73 has a strong local durable witness, but the persisted B72 skip→dependent-resume boundary is not separately shown.
- Ограничение: Relevant pattern pass: P04/P07/P08 — status and checkpoint frontier must match the committed state at the same durable boundary.

<a id="res-03"></a>

## RES-03 — Сохранение частичного результата через последующий отказ

**Записи:** B13. **Реестр:** B13=partial.
**Маршрут:** первый сбор Q01; historical C19; дополнительно D02. **Checkpoint:** CP2. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/RES-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CYC-02, CMP-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** После настоящего численного producer следующий узел падает: предыдущий результат читается повторно со scope и error. A success/B fail сохраняет A. Нарушение общего основания отзывает зависимые выводы, а независимая техническая ошибка не стирает всё.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_res_03.py` → Q01 / C19

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_res_03.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral unit coverage of the actual AsyncChainExecutor, MethodComposer, and registry using synthetic registered methods; the partial result is an in-memory exception payload.

**Дополнительные пробы / границы:**
- Drive the served chain through the normal run lifecycle, persist an earlier successful numeric/artifact result, fail a later stage, and read that result through the ordinary user-facing result reader with scope, failing stage, and basis/retraction semantics.
- Remove the retained result reference while leaving status markers and prove the served read fails closed.
- Show a changed common basis invalidates dependent conclusions while a sibling technical failure retains independent outputs.
- Ограничение: The artifact_ref is a literal fixture string; the test does not persist or resolve CAS bytes and does not call run_lifecycle, generation_cycle, engine_simple, or a served result reader.
- Ограничение: Current witness is component-level; B13's served preservation path and negative missing-reference probe remain unestablished (surface_missing / semantic_test_missing for that claim).

<a id="res-04"></a>

## RES-04 — Точный Foundry checkpoint и неизменяемые sidecars

**Записи:** B74, B75, B76. **Реестр:** B74=partial, B75=partial, B76=partial.
**Маршрут:** первый сбор Q12, Q16; historical C17, C18; дополнительно D02. **Checkpoint:** CP2. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/RES-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CMP-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Цепочка multiply/add: changed factor/input не принимает прежний результат 7 вместо холодный результат 10/9. Выходы 6/7 после resume остаются 6/7, исходный seed сохраняется. a_b и a→b сохраняют разные массивы; ошибка нового save после sidecar не портит старый snapshot. Tiny NumPy-файлы, без больших массивов.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_res_04.py` → Q12 / C18
- `policy-engine/tests/unit/foundry/methods/backends/test_checkpointing.py` → Q16 / C17

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_res_04.py tests/unit/foundry/methods/backends/test_checkpointing.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral component tests against CheckpointingChainExecutor/ChainCheckpoint with a synthetic dispatcher, real JSON/NumPy sidecar IO, and one compiled-chain contract path.

**Дополнительные пробы / границы:**
- Mutate each effective request identity dimension independently: method/version, binding, seed, input snapshot, scientific parameter, and model/context version; prove invalidation/recompute, plus that an operational timeout alone can reuse a valid checkpoint.
- Assert a legacy checkpoint with missing node history returns a typed explicit history limitation; prove the resumed state through its served consumer.
- Tamper sidecar shape and dtype independently from content hash/path and assert rejection.
- Ограничение: Bindings, method/runtime versions, and operational-timeout reuse are not isolated as changed/unchanged controls.
- Ограничение: Legacy missing identity is rejected with CheckpointDigestMismatchError, but there is no explicit missing-history result consumed by a served reader.
- Ограничение: No distinct malformed shape/dtype probe was found; existing foreign-sidecar test changes bytes and checks content mismatch. The dispatcher/registry remain doubles rather than a complete real Foundry execution.

<a id="run-01"></a>

## RUN-01 — Deadline, contextvars и безопасные sync/async-мосты

**Записи:** B14, B40, B69, B95, LA-057. **Реестр:** B14=partial, B40=partial, B69=partial, B95=partial, LA-057=partial.
**Маршрут:** первый сбор Q07, Q08; historical C15, C17; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/RUN-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK36.

**Дискриминатор из owner-пакета:** Одинаковые direct/async/thread входы имеют согласованный timeout/context; A затем B не протекают через worker. Малый saturated pool с управляемыми событиями не блокирует собственную inner task. Noncooperative timeout явно оставляет диагностируемую незавершённость, не разрешает поздний актуальный commit. Проверить get_type_hints с корректными namespaces, четыре function-local T, ContextVar, cancellation/finally, direct/star/reflection imports; отдельный малый процесс до/внутри loop.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/common/test_async_tools.py` → Q07 / C17
- `policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py` → Q08 / C15
- `policy-engine/tests/performance/test_overhead.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_run_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/common/test_async_tools.py tests/unit/scientist/orchestration/engine/test_retry.py tests/performance/test_overhead.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral unit coverage for caller timeout, late-write revocation, event-loop responsiveness, and context propagation in the common bridge; retry fallback has a structural executor submission check.

**Дополнительные пробы / границы:**
- Force the retry non-fork thread fallback, set a ContextVar in the caller, and assert the timed node reads that exact value; include a positive control and verify no context leaks to the executor thread afterward.
- Saturate a deliberately small shared pool with nested run_coro_sync -> run_blocking_async calls and compare against a direct async control (B69).
- Resolve one top-level monotonic deadline and assert remaining budget reaches nested calls and the trace; assert one timed-out blocking call does not launch duplicate work (B40).
- For LA-057, remove the module-global TypeVar and TypeVar import, then run a scope-aware AST census of the full module plus positive local-PEP695 generic controls.
- Ограничение: The source still contains `from typing import TYPE_CHECKING, TypeVar` and module `T = TypeVar("T")` in common/async_tools.py. The complete tracked test census had a TypeVar text hit only in unrelated performance/test_overhead.py; there is no async_tools scope-census node.
- Ограничение: Current timeout tests do not establish generic helper cancellation; the thread can finish later. B14 is bounded as post-timeout write revocation, not worker termination.
- Ограничение: No B69 starvation witness or B40 remaining-deadline propagation/trace witness exists in the mapped test nodes.

<a id="run-02"></a>

## RUN-02 — Доставка результата через процессную границу

**Записи:** B24. **Реестр:** B24=partial.
**Маршрут:** первый сбор Q08; historical C15; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/RUN-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: RUN-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** В отдельном тестовом процессе маленький результат и 1MiB доставляются без ложного timeout. Compute timeout прекращает только принадлежащее тесту вычисление; сбой отправки не публикует success. Проверить сериализацию и отсутствие висящих собственных потомков после завершения.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py` → Q08 / C15

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_run_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/orchestration/engine/test_retry.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral tests of the actual sync and async fork-worker result transport, including a 1 MiB payload, delivery failure, serialization failure, and deadline-vs-delivery distinction.

**Дополнительные пробы / границы:**
- Keep the 1 MiB transfer witness and add a documented payload above the measured boundary if production outputs can exceed it; preserve a small-result control.
- Verify end-to-end through a real result consumer or persisted artifact reference if that is the chosen large-result transport; the current path tests queue delivery rather than CAS handoff.
- Ограничение: The test demonstrates exactly 1 MiB, not an unbounded large-result guarantee or a full real MethodResult/served consumer chain.
- Ограничение: These tests prove queue drain behavior, not an alternate artifact-store result-reference design.

<a id="run-03"></a>

## RUN-03 — Одна retry-политика и чистый baseline каждой попытки

**Записи:** B39, B96. **Реестр:** B39=partial, B96=partial.
**Маршрут:** первый сбор Q09, Q13; historical C05, C07; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/RUN-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: STA-01, RUN-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Постоянный дефект return/raise имеет одинаковое число попыток; временная ошибка допускает ограниченный retry. x+=1→ошибка→успех даёт x=1, не 2. Старые расходы и история сохраняются; чистый producing-copy узел работает как раньше.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_run_03.py` → Q09 / C07
- `policy-engine/tests/unit/scientist/orchestration/engine/test_retry_integration.py` → Q13 / C05

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_run_03.py tests/unit/scientist/orchestration/engine/test_retry_integration.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral tests of both actual retry wrappers plus retry integration through the workflow engine; sync/async attempt states are synthetic in-memory nodes.

**Дополнительные пробы / границы:**
- Vary permanent return/raise defects across all typed error categories and prove identical attempt count; include real ValidationError/TypeError controls if they remain retryable candidates.
- Exercise retries whose node writes persisted artifacts or invokes an external effect; prove no duplicate side effect and keep uncertainty about an unknown external outcome explicit.
- Ограничение: The negative witness covers mutable in-memory state, not durable CAS/audit artifacts or non-idempotent external actions.
- Ограничение: Coverage samples error categories; it does not establish every possible exception classification.

<a id="scl-01"></a>

## SCL-01 — Scholar: пустой ответ, общий raw transport и точные причины отказа

**Записи:** B17, LA-024. **Реестр:** B17=partial, LA-024=partial.
**Маршрут:** первый сбор Q03, Q16, Q19; historical C02, C12, C13; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SCL-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK09.

**Дискриминатор из owner-пакета:** Первый provider возвращает [], второй разрешённый — результат: второй вызван. Exception-failover продолжает работать. При запрете доступа/лимите следующий вызов не выполняется. Все провайдеры в тесте локальные, без платной сети. Fake-response tests: initial/redirect blocked, loop, timeout, oversize, MIME и raw hash; no live HTTP. Полный raw документ не заменяется search snippets; refresh и cache-hit constraints сохранены.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scholar/search/test_providers.py` → Q19 / C13
- `policy-engine/tests/unit/scholar/search/test_fetcher_security_cache.py` → Q16 / C02
- `policy-engine/tests/unit/remediation/test_scl_03.py` → Q03 / C12
- `policy-engine/tests/unit/scholar/search/test_service_jobs_tools.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_scl_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scholar/search/test_providers.py tests/unit/scholar/search/test_fetcher_security_cache.py tests/unit/remediation/test_scl_03.py tests/unit/scholar/search/test_service_jobs_tools.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral unit tests of ProviderFailoverPolicy and both raw transport adapters with fake HTTP responses/resolver; one deep-search non-empty consumer control.

**Дополнительные пробы / границы:**
- Run an empty first provider through the real deep-search caller, assert the secondary result reaches the citation/consumer output, and keep a useful-first-response short-circuit control.
- Exercise allowed URL, redirect target, and redirect loop through both seed-fetch and search-fetch callers; test license and raw digest preservation through both caller outputs.
- Keep DNS/SSRF admission explicitly separate until resolver rebinding/redirect admission is independently established.
- Ограничение: Provider exhaustion reasons for empty/unsuitable/inaccessible/budget-limited sources and useful-first short-circuit are not all exercised by the mapped nodes.
- Ограничение: No redirect-loop node was found. DNS answers are mocked to a public/private address, so actual DNS rebinding/SSRF closure is not established; this matches the triage boundary.
- Ограничение: License and raw hash are not asserted end-to-end through both seed and search callers; current coverage is split across transport and seed metadata tests.

<a id="scl-03"></a>

## SCL-03 — Search→enrich: точный raw snapshot, не повторный URL-fetch

**Записи:** LA-025. **Реестр:** LA-025=partial.
**Маршрут:** первый сбор Q03; historical C12; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SCL-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: SCL-01. Protected controls: LK09, LK20.

**Дискриминатор из owner-пакета:** Search v1, URL уже v2: enrich использует v1 без сети либо явно получает v2 с новыми refs. Cache hit/miss, утраченный blob, denied access, MIME/size/document limits и no-snippet reconstruction. Связь между fragments и исходными raw bytes проверена.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_scl_03.py` → Q03 / C12

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_scl_03.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral component tests using the actual UrlFetchCache/FileSystemCAS and web-bootstrap handoff, with explicit missing/denied/mismatched-snapshot negatives.

**Дополнительные пробы / границы:**
- Keep the no-network cache-hit assertion at the bootstrap boundary and add a miss/expired-cache control that distinguishes explicit refresh from silent refetch.
- Assert the typed gap/refresh reason and lineage through the ordinary downstream consumer for missing, denied, and digest-mismatched bytes.
- Ограничение: The fixture tests exercise real local CAS/cache objects but no remote CAS permissions or network behavior.
- Ограничение: No cache-expiration/cache-miss branch is mapped here. The existing consumer handoff is present, but producer-handshake and broader artifact lifecycle remain separate residuals as PARTIAL_TRIAGE states.

<a id="scm-01"></a>

## SCM-01 — Наблюдаемые корни и выполняемый nonlinear payload

**Записи:** B221, B222. **Реестр:** B221=partial, B222=partial.
**Маршрут:** первый сбор Q16; historical C02; дополнительно по готовности новых проб. **Checkpoint:** CP5. **Исследователь:** e02_13.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SCM-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: GRF-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Y=3T+2Z, Z=99/101, do(T=1) даёт условное среднее около 203, не 3. y=x² при x=2 выполняет 4, не 1.36 с почти нулевым noise. LINEAR y=1+3x остаётся 7. Неинтервенируемые зависимые корни сохраняют joint relation; недостающий корень не становится тайным N(0,1).

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_scm_01.py` → Q16 / C02

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_scm_01.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Behavioral unit tests of actual HybridSCMFit, StructuralCausalModelSpec, GCMQuery and TwinNetworkQuery using deterministic NumPy fixtures; polynomial query payload is directly constructed.

**Дополнительные пробы / границы:**
- Exercise fitted polynomial production through query/twin execution and artifact round trip rather than only manually constructing the stored polynomial payload.
- Extend observed-root fixture with a nontrivial joint distribution/correlated roots and verify query retains the joint carrier; keep the absent-root declared-hypothesis negative control.
- Ограничение: The observed-root example is a small synthetic fixture, not a representative empirical claim.
- Ограничение: The polynomial test validates query execution of a manually authored stored payload; it does not prove the full fit->persist->query producer chain or arbitrary polynomial interactions.

<a id="scm-02"></a>

## SCM-02 — Factual abduction и две явные стороны attribution

**Записи:** B215, B223. **Реестр:** B215=partial, B223=partial.
**Маршрут:** первый сбор Q13, Q17; historical C18, C19; дополнительно D04. **Checkpoint:** CP5. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SCM-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: SCM-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** X=Ux, Y=X+Uy, evidenceY=2, doX=0 даёт mean=1/variance=0.5 в поддержанном Gaussian-контроле, а полное X=1, Y=2 —Y(0)=1. Для Y=1+3X targetX=2/baselineX=0 контраст 6, не 0; одинаковые явные стороны дают 0. Shared-U и независимые межмировые выборки не смешиваются.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_scm_02.py` → Q13 / C19
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_query.py` → Q17 / C18
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_twin_network_query.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_scm_02.py tests/unit/foundry/methods/catalog/causal/test_gcm_query.py tests/unit/foundry/methods/catalog/causal/test_twin_network_query.py
```

**Profile и доступность:** test extra for pytest/runtime-http test dependencies.; Base project dependencies provide JAX/JAXlib and Pydantic; NumPy is imported directly and currently arrives through the JAX dependency graph.; No research umbrella required for the described tests; do not include optional DoWhy comparison..
**Карта поведения из статического исследования:** 24 collected behavioral cases across GCM/Twin abduction, explicit target/comparator contrasts, legacy normalization, typed persistence, CAS manifest binding, producer/consumer rejection. Collection only; no runtime result asserted by this report.

**Дополнительные пробы / границы:**
- Falsify the declaration that an imputed parent was observed while leaving its value intact; ensure posterior conditioning and authority/status remain limited.
- Use identical target and comparator, then independently sampled worlds with identical marginals; assert the contrast is zero only in the first case and shared-U dependence is preserved for twin outcomes.
- End-to-end producer tests currently monkeypatch ensure_causal_methods_registered/run_job in the node tests; add or capture one real RunCausalQueriesNode -> GCMQuery -> CAS -> load/consumer path so a canned JobResult cannot stand in for execution.
- Ограничение: `test_causal_query_producer_reconciles_envelope_with_result` and `test_causal_query_producer_persists_typed_contrast_and_v1_1_manifest` stub the job/registration bridge; they cover downstream reconciliation/persistence logic, not a real producer execution.
- Ограничение: No test result or persisted runtime artifact was produced in this research pass.

<a id="scm-03"></a>

## SCM-03 — Активный query-plan и сохранённый stochastic law

**Записи:** B224, B225. **Реестр:** B224=partial, B225=partial.
**Маршрут:** первый сбор Q12, Q17; historical C06, C18; дополнительно по готовности новых проб. **Checkpoint:** CP5. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SCM-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: SCM-02, GRF-01, GRF-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** DoX=2 даёт Y=7 даже если старый natural X не нужен/невычислим; shift=5+2 всё ещё требует естественное 5.20 посторонних корней не вычисляются без запроса full-trace. Typo-law не превращается в atomic=7. Truncnorm[8,9] имеет внутренние значения, не 100 граничных восьмёрок. Логические seeds сохраняются при сужении плана.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_scm_03.py` → Q12 / C06
- `policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_query.py` → Q17 / C18

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_scm_03.py tests/unit/foundry/methods/catalog/causal/test_gcm_query.py
```

**Profile и доступность:** test extra plus core project dependencies.; The truncnorm case requires SciPy; project `analytics` extra supplies SciPy but also brings unrelated analytics packages. `research` is broader than this targeted test requires..
**Карта поведения из статического исследования:** 9 collected behavioral cases at the public GCMQuery seam: skip replaced do-mechanism, prune unrelated roots but retain factual ancestors, retain logical draws, preserve shift dependency, reject malformed/invalid law, sample truncated tails inside bounds, seeded uniform reproducibility.

**Дополнительные пробы / границы:**
- Capture the executed dependency set for a do query with a deliberately failing replaced mechanism and a separately failing unrelated root; include a shift intervention control that still requires the natural root.
- Resolve a stochastic law once, then mutate or invalidate its source during planning/replay; show no atomic fallback and no law-type substitution.
- Repeat truncnorm on a narrow far-tail interval under fixed seeds; assert interior support and reproducibility, while an unavailable SciPy dependency fails as a typed limitation/error rather than changing the law.
- Ограничение: No persisted runtime artifact is expected from this pure query boundary; keep evidence to the actual result, executed-node trace, seed, and typed failure/status.
- Ограничение: The only observed extra beyond core/test is SciPy for truncated-normal sampling; cloud availability was not verified.

<a id="sel-01"></a>

## SEL-01 — Singleton, eligibility и неизменные требования выбора

**Записи:** B34, B35, B36. **Реестр:** B34=partial, B35=partial, B36=partial.
**Маршрут:** первый сбор Q05; historical C16; дополнительно по готовности новых проб. **Checkpoint:** CP1. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SEL-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK06.

**Дискриминатор из owner-пакета:** Genuine singleton выбирается, фиктивный вне каталога — нет. Добавление non-value методов не прячет value-метод. Panel-запрос не становится пустым требованием при tabular-only каталоге; разрешённый adapter имеет реальный producer.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/foundry/methods/test_selection_advisor.py` → Q05 / C16

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_sel_01.py (absent at pinned SHA)`, `policy-engine/tests/unit/remediation/test_sel_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/foundry/methods/test_selection_advisor.py
```

**Profile и доступность:** test extra plus core dependencies (Pydantic/NumPy via core numerical stack). No research extra required for the three selected cases..
**Карта поведения из статического исследования:** 3 collected existing behavioral tests cover genuine singleton vs fictional method, required-value eligibility before top-k, and hard panel modality/blocker preservation. The proposed E02 remediation file is missing; current coverage lives in canonical selection-advisor tests.

**Дополнительные пробы / границы:**
- Use the real catalog snapshot builder and registry discovery to prove a true one-entry denominator is admissible; keep a present-but-unregistered/fictional FQN negative control.
- Add non-value entries ahead of a valid value owner and check the full eligible denominator and stable selection, not only selected FQN/top-k output.
- Resolve and execute the selected panel adapter through its real producer; assert its typed output. Selection currently proves a runnable owner is chosen, but not that the chosen producer runs.
- Keep panel requested with a tabular-only catalog and verify it remains a typed blocker through the actual downstream consumer.
- Ограничение: Do not create a duplicate selection implementation/test owner; either extend `test_selection_advisor.py` or intentionally add a mirrored remediation module that imports the canonical owner.
- Ограничение: New proposed file absent means the assigned test path itself is not currently realized; existing behavior is partial coverage, not `semantic_test_missing` for all three findings.

<a id="sim-01"></a>

## SIM-01 — Полный выбор движка и верная история fallback

**Записи:** B06, B07. **Реестр:** B06=partial, B07=partial.
**Маршрут:** первый сбор Q12, Q17; historical C13, C14; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SIM-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Первый движок не поддерживает coupling, второй действительно вычисляет: принимается второй. Оба неподходящие — отказ. Подставленный selected без результата не легализует чужие траектории. Перед K1 — небольшой native selector→adapter test.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_sim_01.py` → Q12 / C14
- `policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py` → Q17 / C13

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_sim_01.py tests/unit/runtime/quality/test_joint_simulation_horizon.py
```

**Profile и доступность:** test extra and core project dependencies; no research-only estimator extra identified for these selected nodes..
**Карта поведения из статического исследования:** 5 collected behavioral controller cases cover unsupported-first fallback, all-rejected typed refusal, selected-plan execution binding, preservation of rejected reasons, and foreign-plan trajectory rejection. Two nearby native method-registry selector cases also collect.

**Дополнительные пробы / границы:**
- Capture real selector decisions plus selected engine/method FQN, objective and content-bound physical_run_ref from the actual selected runner; a selected marker with no matching execution must remain rejected.
- Falsify one selected-plan discriminator at a time (same engine/different objective, same objective/different method, stale/foreign trajectory) and run generation-cycle consumer projection to prove it cannot import another plan's result.
- The card asks for native selector-to-adapter evidence before K1; use the two registry tests plus the actual fallback path and preserve every rejected engine reason in the result receipt.
- Ограничение: No executed physical run or content-bound result was produced during this research pass.
- Ограничение: The monkeypatched runner negatives are good semantic witnesses but do not replace one real selected-plan execution receipt.

<a id="sim-02"></a>

## SIM-02 — Выходы, конфликты атомов и покрытие траекторий

**Записи:** B18, B20, B22. **Реестр:** B18=partial, B20=partial, B22=partial.
**Маршрут:** первый сбор Q17; historical C11, C13; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SIM-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Пустой пакет, частичный outcome, zero, NaN/inf различимы. A: x=1 и B: x=2 не дают случайный last-wins; перестановка совместимых атомов инвариантна. Пустая/короткая/полная trajectory и явный допустимый hold-last сохраняют разные статусы.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_sim_02.py` → Q17 / C11
- `policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py` → Q17 / C13

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_sim_02.py tests/unit/runtime/quality/test_joint_simulation_horizon.py
```

**Profile и доступность:** test extra and core JAX/NumPy/Pydantic stack; no optional research estimator extra identified..
**Карта поведения из статического исследования:** 10 collected behavioral cases: missing/NaN/inf/partial selected outcomes fail closed, explicit zero control, conflicting assignments rejected in both orders, identical assignment permutation control, and short method-registry trajectory with explicit partial-or-refusal contract.

**Дополнительные пробы / границы:**
- Run the actual NCM executor for each output shape, then verify no trajectory is emitted for missing/non-finite data and an explicit zero remains numeric zero.
- Mutate order and target-slot values through the full request path; include equal duplicates as a positive control and ensure no last-wins behavior leaks into receipts.
- Exercise coverage behavior per coupled_des_abm queue, system-dynamics stock-flow, and program-graph/program-override horizon branches; the test module explicitly lists these as residual uncovered paths.
- Ограничение: No current red/green state established: no test bodies were run.
- Ограничение: Coverage remains NCM-specific for missing output and atom conflict; sibling engine branches need their own property-level diagnostics before acceptance.

<a id="sim-03"></a>

## SIM-03 — Контрасты, реплики, SMM и экономия одинаковых расчётов

**Записи:** B19, B21, B23, B25, B26. **Реестр:** B19=partial, B21=partial, B23=partial, B25=closed, B26=partial.
**Маршрут:** первый сбор Q03, Q17; historical C08, C13; дополнительно D02. **Checkpoint:** CP1. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SIM-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: SIM-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Y(A)=Y(B)=Y(AB)=100 при comparator=100 даёт нулевые эффекты. Один stochastic draw не даёт установленный SE=0. Удаление трудного момента не улучшает SMM. Для одного/двух атомов нет лишнего идентичного вызова; другой seed — отдельная работа. y=x1*x2*x3 не называется глобально additive по нулевым парным эффектам.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_sim_03.py` → Q03 / C08
- `policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py` → Q17 / C13

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_sim_03.py tests/unit/runtime/quality/test_joint_simulation_horizon.py
```

**Profile и доступность:** test extra plus core dependencies; NumPy required.; No optional SciPy/DoWhy path identified in the assigned SIM-03 test file..
**Карта поведения из статического исследования:** 22 collected behavioral cases cover comparator, unique replication seeds/SE status, SMM mandatory moments, physical-run identity/cache separation, requested-order/higher-order interactions, and explicit selected outcome/horizon basis. Test module declares N/C-exclusive due shared native joint-simulation fixture.

**Дополнительные пробы / границы:**
- Capture real paired runs with declared seeds, per-arm outcomes, required metric set/counts, SE state, and source/evidence mode; prove a single draw and duplicate seed never produce an independence claim.
- For actual NCM runs, capture each physical_run_ref's seed, plan, effective evidence, engine horizon, and interaction order; rerun same spec across roles for reuse and changed seed/plan/evidence for separation.
- Keep triple-only/higher-order and cancellation controls; a pairwise zero is not proof of global additivity.
- Ограничение: Most evidence is synthetic callback/controller evidence; no run receipt was produced in this pass.
- Ограничение: File imports `os` to support seed/plan removal probes; ensure cloud subprocess/environment isolation is per worker and don't share a mutation-probe environment across parallel workers.

<a id="srv-01"></a>

## SRV-01 — SearchService: чистые contracts и один ask/tell state transition

**Записи:** LA-014. **Реестр:** LA-014=partial.
**Маршрут:** первый сбор Q17; historical C05; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SRV-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: CTL-03. Protected controls: нет.

**Дискриминатор из owner-пакета:** Contract-only import при controller trap; настоящие ask/tell и run_search, unknown/duplicate IDs, typed evaluation, frontier и resume. Tell не может обойти B123 или вернуть старый history-counter. Identity поддержанных DTO/aliases и lazy facade проверяется.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_srv_01.py` → Q17 / C05

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_srv_01.py
```

**Profile и доступность:** test extra plus core Pydantic/JAX dependencies; no research extras identified..
**Карта поведения из статического исследования:** 8 collected behavioral/import tests cover contracts-only import traps, lazy compatibility alias, ask/tell state transition and resume, Stage A/B counters, unknown/duplicate IDs, malformed typed feedback, and `run_search` compatibility entrypoint.

**Дополнительные пробы / границы:**
- Preserve the subprocess import trap under a clean module cache and prove contracts import does not load controller/funnel; run on Linux path semantics as cloud is not yet verified.
- Drive ask -> typed tell -> read owner history/frontier, then malformed, duplicate, and unknown feedback through the same public consumer; assert no stale history counter or scalar-best fallback.
- Enumerate supported adapter aliases/callers before any legacy export removal; an import-level compatibility test alone does not establish caller/lifecycle closure.
- Ограничение: `SearchService` is a protocol; concrete `_NativeSearchServiceDriver` is private and exposed under `LegacySearchServiceAdapter`. Preserve the exact public compatibility contract before changing/removing the legacy-named export.
- Ограничение: No live persisted search artifact is expected by the ask/tell tests; the lifecycle state is in-memory and should be distinguished from SRV-03 CAS behavior.

<a id="srv-03"></a>

## SRV-03 — Autotune: native SearchService driver и ограниченный cutover

**Записи:** LA-015. **Реестр:** LA-015=partial.
**Маршрут:** первый сбор Q06, Q12; historical C03, C05; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_14.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/SRV-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: SRV-01, CTL-02, STP-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Два кандидатных сценария: обычное завершение и warm→sentinel→empty/error→resume. Совпадают effective requests, расходы, history/frontier, partial outcomes; B118–127 исправленные controls не теряются при cutover. Отдельно typed result, RNG и negative admission. Не требовать равенства с доказанно неверным старым поведением.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_srv_03.py` → Q06 / C03
- `policy-engine/tests/unit/scientist/methods/autotune/test_registry_and_runner.py` → Q12 / C05

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_srv_03.py tests/unit/scientist/methods/autotune/test_registry_and_runner.py
```

**Profile и доступность:** test extra and core dependencies; no research extras identified for the assigned cases..
**Карта поведения из статического исследования:** 6 collected cases (5 functions plus falsy-ID parameterization) include warm/sentinel/empty/error/resume trace, native-service identity validation, and a real autotune SearchLoopRunner -> temporary FileSystemCAS -> ChampionRegistry promote/readback path. The latter monkeypatches SearchController.run to reject legacy-loop use.

**Дополнительные пробы / границы:**
- Compare frozen pre-cutover and native traces for effective requests, cost, history/frontier, stage counts, sentinel, transient empty, evaluator error, partial outcome, and resume; don't demand parity with known-bad legacy behavior.
- Exercise the real SearchLoopRunner caller and CAS promotion/readback, then enumerate all supported autotune callers and retained-history readers before declaring strangle closure.
- Check that corrected B118-B127 controls remain wired into the native lifecycle; no B118-B127 test references were found in the assigned test file or the searched canonical search/autotune unit-test directories, so use the original finding IDs/source controls rather than an assumed set.
- Ограничение: Direct test does not establish full trace parity across all supported consumers or prove all historical payload readers remain compatible.
- Ограничение: No final caller/lifecycle census or strangle receipt was run in this research pass; compatibility status must remain pending until it is.

<a id="sta-01"></a>

## STA-01 — Изоляция ветвей и точные эффекты replay

**Записи:** B57, B58, B59. **Реестр:** B57=partial, B58=partial, B59=closed.
**Маршрут:** первый сбор Q01, Q08, Q14; historical C02, C05, C06; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/STA-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Warm/cold сохраняют unrelated=new; явно записанное y=4 заменяет текущее 9 даже при старом 4. Delete≠null≠no-write. Мутация вложенного списка не протекает в base/соседа; failed branch не меняет базу. Запрещённое удаление evidence-index по-прежнему отвергается.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/orchestration/engine/test_state_branching.py` → Q01 / C02
- `policy-engine/tests/unit/scientist/orchestration/engine/test_state_merge.py` → Q01 / C06
- `policy-engine/tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py` → Q08 / C02
- `policy-engine/tests/unit/scientist/orchestration/engine/test_idempotency.py` → Q14 / C05

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_sta_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/orchestration/engine/test_state_branching.py tests/unit/scientist/orchestration/engine/test_state_merge.py tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py tests/unit/scientist/orchestration/engine/test_idempotency.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Direct semantic coverage plus executor/cache E2E for unrelated-state preservation and failed-node rollback; proposed test_sta_01.py is absent.

**Дополнительные пробы / границы:**
- Carry an explicit same-value setter through a persisted NodeResultCache hit while the current target differs; same-value replay is pinned at merge layer, while executor cache coverage pins unrelated state and ref writes.
- Exercise delete/null/no-write through a persisted cache hit and assert a sibling branch remains unchanged; current delete semantics and deep leaf isolation are direct branch/merge tests.
- Keep protected-index deletion refusal as a negative control when broadening replay.
- Ограничение: No current test routes same-value ordinary-field writes or delete/null/no-write through a persisted warm cache hit; these are tested at mutation/merge layer.
- Ограничение: Nested-leaf test proves isolation from base, but does not directly assert a separately-created sibling branch is unchanged.
- Ограничение: Assignment-proposed tests/unit/remediation/test_sta_01.py does not exist at the pin.

<a id="sta-02"></a>

## STA-02 — Точная версия входа и пригодность готового bundle

**Записи:** B60, B61, B62. **Реестр:** B60=partial, B61=held, B62=partial.
**Маршрут:** первый сбор Q01, Q05, Q14, Q19; historical C05, C08, C09, C19; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/STA-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: STA-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Старый bundle на новом target_context/required_parameters не даёт пустой ok. Смена bytes по тому же SKG path меняет actual snapshot/key, замороженный снимок остаётся reusable. Missing threshold, null, zero, false и empty-list различаются там, где это различает метод.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/nodes/builtins/causal/test_resolve_parameters.py` → Q19 / C08
- `policy-engine/tests/unit/scientist/methods/causal/test_resolve_parameters_node.py` → Q05 / C19
- `policy-engine/tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py` → Q01 / C09
- `policy-engine/tests/unit/scientist/orchestration/engine/test_idempotency.py` → Q14 / C05

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_sta_02.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/nodes/builtins/causal/test_resolve_parameters.py tests/unit/scientist/methods/causal/test_resolve_parameters_node.py tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py tests/unit/scientist/orchestration/engine/test_idempotency.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Direct semantic coverage for all three findings; source-snapshot, bundle-reuse, and key-presence pieces live in separate suites.

**Дополнительные пробы / границы:**
- Change required_parameters while retaining an old bundle and prove the node cannot return empty ok unless the new request is covered.
- Run one ResolveParametersNode/executor scenario where SKG bytes change at the same path between preflight and consumption; assert consumed read and cache binding identify the same prepared snapshot.
- Retain null/zero/false/empty-list presence tests as selector-specific semantics rather than universal key requirements.
- Ограничение: B60 direct tests change context/domain and graph binding; explicit required_parameters expansion against an old bundle is not visible in inspected tests.
- Ограничение: B61 proves prepared-reader digest changes and key changes separately, but not one end-to-end node execution proving its query consumed exactly the snapshot used to build the cache key.
- Ограничение: A read of a large mutable source currently computes a file SHA-256; owner-ref optimization boundary and production-size throughput are not measured.
- Ограничение: Assignment-proposed tests/unit/remediation/test_sta_02.py does not exist at the pin.

<a id="stp-01"></a>

## STP-01 — Актуальный convergence-сигнал и плато около нуля

**Записи:** B41, B122. **Реестр:** B41=partial, B122=partial.
**Маршрут:** первый сбор Q05, Q16; historical C08, C18; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/STP-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Одинаковые старые embeddings+ошибка текущего не подтверждают convergence. Настоящие две актуальные одинаковые записи дают ограниченный результат. Лучшее 0 и последующие положительные losses не означают improvement=inf; улучшение отрицательных/малых значений считается в правильном направлении.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/orchestration/engine/test_convergence_semantic.py` → Q16 / C18
- `policy-engine/tests/unit/scientist/orchestration/engine/test_convergence.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/scientist/search/test_search_loop.py` → Q05 / C08

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_stp_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/orchestration/engine/test_convergence_semantic.py tests/unit/scientist/orchestration/engine/test_convergence.py tests/unit/scientist/search/test_search_loop.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Existing direct semantic coverage of stale-signal refusal, provenance change, and zero-baseline signed improvement.

**Дополнительные пробы / границы:**
- If closure requires the consumer effect, add a small controller/engine test showing an unavailable current embedding leaves convergence false and the loop continues; direct detector test already proves it does not converge.
- Do not substitute max-iteration or budget stop outcomes for semantic convergence.
- Ограничение: No algorithm-level probe missing for the two finding statements was identified in inspected tests.
- Ограничение: The algorithm tests do not establish a persisted/public convergence evidence surface; if that capability is claimed, it remains surface_missing/artifact_missing.

<a id="str-01"></a>

## STR-01 — Направление stress-поиска и независимые от top-k счётчики

**Записи:** B106, B107. **Реестр:** B106=partial, B107=partial.
**Маршрут:** первый сбор Q06, Q20; historical C13, C14; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/STR-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Для 10 нарушенных сценариев top_k1/10 не меняет score. Десять проявлений одной проблемы не становятся одним нарушением. Lower-tail значения 10/−5 при пороге 0 выбирают−5; cost-профиль проверяет обратное направление. Empty не выглядит установленной устойчивостью.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/search/test_adversarial.py` → Q20 / C14
- `policy-engine/tests/unit/scientist/methods/search/test_objective.py` → Q06 / C13

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_str_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/search/test_adversarial.py tests/unit/scientist/methods/search/test_objective.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Direct behavior tests cover top-k invariance and direction; duplicate-issue and empty-set adequacy probes remain.

**Дополнительные пробы / границы:**
- Emit repeated manifestations of one issue across multiple evaluated scenarios and verify attempted/valid/observed counts and robustness_score are unchanged by presentation dedupe/top-k.
- Exercise an empty or entirely missing evaluation set and require explicit not-established/unverified adequacy rather than a healthy robustness interpretation.
- Assert persisted StressTestReport counters preserve attempted, invalid, observed, unique, and presented counts when CAS persistence is enabled.
- Ограничение: Current top-k test uses ten distinct parameter/objective observations, not repeated representations of one semantic issue; it proves score independence from top-k but not duplicate-issue case.
- Ограничение: No direct empty-set adequacy test was found in inspected adversarial suite.
- Ограничение: Listed tests call run_stress_test without CAS and do not prove report persistence/consumer use.

<a id="trn-01"></a>

## TRN-01 — Численный transfer без фиктивного benchmark

**Записи:** B128, B130, B131, B132. **Реестр:** B128=partial, B130=partial, B131=partial, B132=partial.
**Маршрут:** первый сбор Q19; historical C07; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/TRN-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: OPT-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Найденные строки не исчезают из-за constructor mismatch. При minimize=1 отбирается раньше 9 по объявленной квоте. Несовместимая оценка остаётся proposal/ограничением, не GP training. Нет zero SHA, фиктивного holdout или params в metrics. Native DTO проверки обязательны.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/methods/autotune/test_warm_start.py` → Q19 / C07
- `policy-engine/tests/unit/scientist/search/test_warm_start.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_trn_01.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/methods/autotune/test_warm_start.py tests/unit/scientist/search/test_warm_start.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Direct typed transfer tests cover constructor retention, objective direction, binding mismatches, and limited benchmark conversion; source_test_ref in search/test_warm_start.py is only adjacent controller warm-start coverage.

**Дополнительные пробы / границы:**
- Add an objective_directions mismatch case to the fingerprint matrix if direction is a numeric compatibility key.
- If numerical warm-start is claimed end-to-end, prove a compatible persisted source produces a candidate consumed by the receiving optimizer, while incompatible source stays proposal/limited and cannot enter training.
- Ограничение: Compatibility matrix does not visibly vary objective_directions.
- Ограничение: The cited tests/unit/scientist/search/test_warm_start.py::TestWarmStart exercises initial raw dictionaries in SearchController, not B128/B130/B131/B132 artifacts; do not count it as transfer-bridge coverage.
- Ограничение: Bridge tests establish bounded output shape and limits, not a real optimizer training-consumption lifecycle.
- Ограничение: Assignment-proposed tests/unit/remediation/test_trn_01.py does not exist at the pinned checkout.

<a id="trn-02"></a>

## TRN-02 — Точные snapshot-refs и атомарное поколение vector memory

**Записи:** B129, B133, B134. **Реестр:** B129=partial, B133=partial, B134=partial.
**Маршрут:** первый сбор Q20; historical C08; дополнительно по готовности новых проб. **Checkpoint:** CP3. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/TRN-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Рост ANN-каталога не прячет известную ref. Новый snapshot того же run_id не возвращает старую историю. Sorting потребителя не мутирует следующий hit. Ошибка native add/load не смешивает имена/векторы. Малый native индекс из десятков векторов проверяется в K3.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_trn_02.py` → Q20 / C08

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_trn_02.py
```

**Profile и доступность:** test; vector-search.
**Карта поведения из статического исследования:** Direct B129/B133 snapshot tests; B134 load-failure and round-trip tests plus a non-discriminating capacity failure case.

**Дополнительные пробы / границы:**
- Inject a native add_items failure after the native index call has begun, ideally after partial mutation, and prove the old index plus metadata generation remains queryable.
- Keep controlled load failure and small native round-trip as negative/positive generation controls.
- Ensure CI reports the importorskip count; without vector-search, three HNSW tests silently skip.
- Ограничение: Native add failure test currently tests capacity preflight, not a native add exception, so it does not distinguish intact native generation from partial native mutation.
- Ограничение: Native tests are guarded by pytest.importorskip('hnswlib'); vector-search is the specific optional extra. On a fresh Linux/Python 3.14 worker, compatible wheel or compiler may be needed; install behavior was not checked.
- Ограничение: The assignment-proposed file exists, but its module header describes an earlier characterization phase; read test bodies/current runtime rather than treating header as current failure evidence.

<a id="trn-03"></a>

## TRN-03 — Контекст переноса, фильтры lessons и время подтверждения

**Записи:** B135, B136, B137. **Реестр:** B135=partial, B136=partial, B137=partial.
**Маршрут:** первый сбор Q01, Q12; historical C03; дополнительно D04. **Checkpoint:** CP3. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/TRN-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Переданный typed context не заменяется policy/isolated defaults. Source_run/trust/threshold одинаковы в обеих ветвях. Два чтения старого урока не повышают confidence без новой проверки; настоящее подтверждение имеет свои ссылки/время.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/scientist/search/test_lesson_transfer.py` → Q12 / C03
- `policy-engine/tests/unit/scientist/search/test_lessons.py` → Q01 / C03
- `policy-engine/tests/unit/scientist/orchestration/memory/test_failure_lessons.py` → отдельная дельта, вне исторической матрицы

**Отсутствующие предложенные пути:** `policy-engine/tests/unit/remediation/test_trn_03.py`.

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/scientist/search/test_lesson_transfer.py tests/unit/scientist/search/test_lessons.py tests/unit/scientist/orchestration/memory/test_failure_lessons.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Direct typed context/filter tests and negative repeated-read confidence test; no typed positive reverification artifact/time path.

**Дополнительные пробы / границы:**
- Prove equivalent source_run/trust/threshold filters before and after transfer materialization for each relevant field.
- Define and test a genuine evidence-revalidation event with new refs/time that changes adequacy; keep last_accessed_at as retention telemetry only.
- Assert repeated reads update only access/retention metadata and never a verification timestamp or evidence confidence.
- Ограничение: LessonCard/IndexSnapshot expose created_at and last_accessed_at but no distinct verified_at/verification-ref contract was found; no positive revalidation producer appears in these owners.
- Ограничение: Repeated-read test checks confidence/strict filtering, not that last_accessed_at changes without changing an evidence-verification clock.
- Ограничение: Assignment-proposed tests/unit/remediation/test_trn_03.py does not exist at the pinned checkout.

<a id="udf-01"></a>

## UDF-01 — Ukraine builders: D4 handoff и малые явные contracts

**Записи:** LA-030, LA-031. **Реестр:** LA-030=partial, LA-031=held.
**Маршрут:** первый сбор Q08; historical C01; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_15.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UDF-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK10, LK12.

**Дискриминатор из owner-пакета:** D4 bytes, schema_version, output filename, required stages и четыре may_not_use_for совпадают. Contract-only import не поднимает все builders. Новый incidental common symbol не появляется в handoff namespace. Полезный producer_handoff_ready не становится governance permission.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_udf_01.py` → Q08 / C01
- `policy-engine/tests/unit/data_forge/domains/ukraine/test_builders.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_udf_01.py tests/unit/data_forge/domains/ukraine/test_builders.py
```

**Profile и доступность:** test.
**Карта поведения из статического исследования:** Strong LA-030 producer-to-verified-consumer coverage; partial LA-031 import-boundary coverage.

**Дополнительные пробы / границы:**
- Use a clean subprocess import of polisyos.data_forge.domains.ukraine.builders.contracts and assert unrelated builders/common heavy modules are absent from sys.modules; current builders package facade eagerly imports common, demography, release, sources, IO, and observation modules.
- Keep exact D4 payload/bytes, narrow compatibility alias, stage registry binding, verified read, and consumer may_not_use_for checks.
- Ограничение: Current test imports builders package before contracts and checks namespace contents, but does not prove contract-only import avoids importing other builders.
- Ограничение: UDF-01 flow proves producer/read/consumer payload authority limits; it is not a full Ukraine D4 pipeline or governance decision run.
- Ограничение: Assignment-proposed tests/unit/remediation/test_udf_01.py exists at pin.

<a id="udf-02"></a>

## UDF-02 — Ukraine common: доменный I/O, binding diagnostics и явные exports

**Записи:** LA-031. **Реестр:** LA-031=held.
**Маршрут:** первый сбор Q11; historical C16; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UDF-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: UDF-01, OBS-01. Protected controls: LK10, LK11, LK12.

**Дискриминатор из owner-пакета:** JSON/NPZ/Parquet output profile не меняется от relocation, ошибки atomic write и прежние диагностические warnings сохранены. Synthetic validation payload остаётся явно тестовым, не observation. Canonical builders работают без common wildcard bootstrap; sequential memory scheduler сохраняется. Deferred native Parquet означает непроверенный профиль, не успешный тест.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_udf_02.py` → Q11 / C16
- `policy-engine/tests/unit/data_forge/domains/ukraine/test_builders.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_udf_02.py tests/unit/data_forge/domains/ukraine/test_builders.py
```

**Profile и доступность:** pytest extra (uv run --extra test); Project base dependencies: NumPy, pandas, PyArrow; no research/runtime extra indicated for these selectors..
**Карта поведения из статического исследования:** Behavioral unit: canonical helper ownership and aliases, JSON byte profile, NPZ profile, Parquet frame profile.; Negative behavior: atomic-write error propagation; synthetic validation payload remains non-observational.; Existing consumer characterization: deterministic sequential memory scheduler.

**Дополнительные пробы / границы:**
- If the native Parquet reader or streaming backend differs from pandas/PyArrow frame writing, keep that profile explicitly deferred until exercised on its intended server runtime.
- LA-031 accountable closure is not complete in this bundle alone; UDF-01 and OBS-01 are assignment dependencies, with UDF-02 as the final I/O/bindings/explicit-import stage.
- Ограничение: No runtime evidence in this research pass; test presence and assertions were inspected statically.
- Ограничение: Bundle prose calls test_udf_02.py proposed, but it already exists in the pinned checkout; use the tree as current selector source.

<a id="udf-04"></a>

## UDF-04 — Ukraine ops: явный workspace root и перенос server gate

**Записи:** LA-029. **Реестр:** LA-029=partial.
**Маршрут:** первый сбор Q10; historical C15, C18; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UDF-04.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Command/cwd/env/exit/skipped сравниваются recording subprocess, explicit root и installed layout. На Mac не выполнять apt-get, CPX62 provisioning или server-only C7. Native маленький CLI test проверяет маршрут без запуска сервера; тяжёлый deployment остаётся unrun.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_udf_04.py` → Q10 / C15
- `policy-engine/tests/unit/data_forge/domains/ukraine/test_cli.py` → отдельная дельта, вне исторической матрицы
- `policy-engine/tests/unit/data_forge/domains/ukraine/test_orchestrator.py` → Q10 / C18

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_udf_04.py tests/unit/data_forge/domains/ukraine/test_cli.py tests/unit/data_forge/domains/ukraine/test_orchestrator.py
```

**Profile и доступность:** pytest extra (uv run --extra test); Project base dependencies and click; no research/runtime extra indicated..
**Карта поведения из статического исследования:** Behavioral unit: explicit product/workspace root passed through CLI and orchestration.; Recording-subprocess contract: command, cwd, environment, exit, and skip outcome.; Negative behavior: installed/no-checkout or missing workspace returns typed unavailable before subprocess.; Composition: ops runner connects domain orchestration to gate and rendering callbacks.

**Дополнительные пробы / границы:**
- Do not run apt-get, CPX62 provisioning, server bootstrap, or server-only C7 on a general cloud runner; retain those as deferred platform/runtime checks.
- If deployment acceptance is required, run the server-only check in its intended Linux server environment and retain a separate receipt; recording-subprocess unit tests do not prove deployment success.
- Ограничение: No runtime evidence in this research pass.
- Ограничение: Installed-wheel behavior is covered through a no-checkout fixture; this does not replace a separately required real installed-wheel launch check.

<a id="udf-05"></a>

## UDF-05 — Демография: единый snapshot вместо per-file legacy fallback

**Записи:** LA-032. **Реестр:** LA-032=held.
**Маршрут:** первый сбор Q03; historical C08; дополнительно D04. **Checkpoint:** CP2. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UDF-05.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: LK12, LK20.

**Дискриминатор из owner-пакета:** Чистые old/new, mixed targets-new/priors-old, optional donor, повреждённый/утраченный blob, несовпадение shapes и явный прежний snapshot. Удаление одного нового filename не выбирает молча другой эксперимент. Read_api controls и pure static aging сохранены.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_udf_05.py` → Q03 / C08
- `policy-engine/tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_udf_05.py tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py
```

**Profile и доступность:** pytest extra (uv run --extra test); Project base dependencies include NumPy, pandas, and PyArrow; no research extra indicated..
**Карта поведения из статического исследования:** Behavioral unit: whole-snapshot selection for new and legacy layouts.; Negative controls: mixed, incomplete, corrupt, shape-mismatched, or removed required members fail closed without fallback.; Consumer regression: static aging and read API snapshot controls.

**Дополнительные пробы / границы:**
- Retain the deletion and corruption cases as semantic controls; constructors or file-presence checks alone would not establish fail-closed layout behavior.
- No live-source refresh or production demographic rebuild is needed for this local fixture test.
- Ограничение: No runtime evidence in this research pass.
- Ограничение: The broader verified-release read-api suite is not needed for these demographic-layout selectors unless the implementation changes its verification boundary.

<a id="uqp-01"></a>

## UQP-01 — Настоящая функция отклика и полный effective call

**Записи:** B186, B189, B190, B191. **Реестр:** B186=partial, B189=partial, B190=partial, B191=partial.
**Маршрут:** первый сбор Q03, Q05, Q11, Q14, Q16; historical C04, C06, C08, C14, C16; дополнительно по готовности новых проб. **Checkpoint:** CP4. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UQP-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** y=x*scale при scale=2 сохраняет 20 в nominal/delta/MC, не 10. Для реальной affine-карты dispatcher выбирает delta без сотни fallback calls. y=x−2 при baseline=0 имеет ненулевую дисперсию, если Var(x)>0. Missing output не даёт [0,0]; настоящая константа 0 остаётся допустимой. Малые массивы и JAX grad по одному слоту.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_uqp_01.py` → Q03 / C04
- `policy-engine/tests/unit/foundry/uncertainty/test_delta.py` → Q14 / C08
- `policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo.py` → Q11 / C14
- `policy-engine/tests/unit/foundry/uncertainty/test_dispatcher_routing.py` → Q05 / C16
- `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py` → Q16 / C06

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_uqp_01.py tests/unit/foundry/uncertainty/test_delta.py tests/unit/foundry/uncertainty/test_monte_carlo.py tests/unit/foundry/uncertainty/test_dispatcher_routing.py tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py
```

**Profile и доступность:** pytest extra (uv run --extra test); JAX/JAXlib and NumPy are project base dependencies; no research extra needed for these small deterministic fixtures..
**Карта поведения из статического исследования:** Behavioral unit: fixed nominal inputs retained in delta and Monte Carlo sampling.; Routing/performance witness: complete affine JAX response selects delta without large Monte Carlo fallback.; Negative behavior: missing output remains unknown while a real zero remains valid.; Consumer/E2E: persisted propagation report records unresolved mapping and gate_eligible=false.

**Дополнительные пробы / границы:**
- Add one shared parameterized y=x*scale fixture asserting nominal, delta, and MC all preserve the same effective scale/value; current checks split this parity case across files.
- Keep the baseline-zero JAX response probe; it exists at node-function level, while a unified parameterized case would make lower-level route consistency easier to review.
- Ограничение: No runtime evidence in this research pass.
- Ограничение: Do not turn this numerical component check into a broader public capability claim; no external surface is part of this local repair.

<a id="uqp-02"></a>

## UQP-02 — Оси covariance, совместный закон и эмпирический carrier

**Записи:** B187, B188, B192. **Реестр:** B187=partial, B188=partial, B192=partial.
**Маршрут:** первый сбор Q02, Q06; historical C10, C18; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UQP-02.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: UQP-01. Protected controls: нет.

**Дискриминатор из owner-пакета:** Перестановка covariance columns при разных дисперсиях 1/9 сохраняет diag(1,9), не искусственную матрицу 2.5. Для a=b и y=a−b analytical/delta/совместный MC дают 0; для независимых inputs сохраняется 2. Эмпирический carrier [-1,0,0,1] сохраняет атомы и joint row IDs. Десятки/сотни простых draws, не большой Monte Carlo.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_uqp_02.py` → Q02 / C18
- `policy-engine/tests/unit/foundry/uncertainty/test_covariance.py` → Q06 / C10
- `policy-engine/tests/unit/ir/test_uncertainty.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_uqp_02.py tests/unit/foundry/uncertainty/test_covariance.py tests/unit/ir/test_uncertainty.py
```

**Profile и доступность:** pytest extra (uv run --extra test); JAX/JAXlib and NumPy are project base dependencies; no Bayesian sampler or research extra is required by these carrier fixtures..
**Карта поведения из статического исследования:** Behavioral unit: covariance row/column identity, declared order, and marginal compatibility.; Joint-law consumer: analytical, delta, random MC, and QMC behavior for shared rows, weighted atoms, typed parametric fits, and unknown dependence.; Negative controls: incompatible axes/weights/lengths and missing joint identity fail closed.; Candidate authority: empirical carrier output remains gate-ineligible.

**Дополнительные пробы / границы:**
- Add a paired same-marginals/different-joint empirical-law case, such as correlation +1 versus -1, and assert propagation preserves the distinction through the returned carrier; current tests exercise shared positive alignment and independent analytical variance but not this paired contrast.
- If MC independence claims are required, add the variance-2 independent control through random MC as well as the existing analytical control.
- Ограничение: No runtime evidence in this research pass.
- Ограничение: The B192 counterexample's distinct joint correlations with identical marginal summaries is not directly paired in current tests; retain this as a missing semantic probe.

<a id="uqp-03"></a>

## UQP-03 — Точность функционала, остановка MC и непокрытая область

**Записи:** B193, B194. **Реестр:** B193=partial, B194=held.
**Маршрут:** первый сбор Q02, Q11, Q16; historical C09, C14, C16; дополнительно по готовности новых проб. **Checkpoint:** CP4. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UQP-03.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: UQP-02. Protected controls: нет.

**Дискриминатор из owner-пакета:** Постоянный выход с batch=50/60 достигает одной объявленной проверки, а не лишних 240 прогонов. Физический диапазон 99/101 не обязан сужаться от большего n. Отказ на x<0 не выдаёт среднее успешной половины за безусловное среднее 0. Временный сбой повторяет тот же draw; известная часть результата сохраняется.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_uqp_03.py` → Q02 / C09
- `policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo.py` → Q11 / C14
- `policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` → Q16 / C16

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_uqp_03.py tests/unit/foundry/uncertainty/test_monte_carlo.py tests/unit/foundry/uncertainty/test_monte_carlo_b194.py
```

**Profile и доступность:** pytest extra (uv run --extra test); JAX/JAXlib and NumPy are project base dependencies; no research extra indicated..
**Карта поведения из статического исследования:** Behavioral unit: non-divisible batch/check boundary and stopping at the requested boundary.; Semantic interval probe: fixed wide 99/101 outputs do not become narrower merely by increasing draw count.; Negative candidate control: partial successful draws remain candidate-only rather than an unconditional statistical result.; Authority check: adaptively stopped output is not labelled a confidence interval.

**Дополнительные пробы / границы:**
- Add a transient-failure/retry fixture proving the identical sampled input and draw index are retried and already-known successful outputs are retained; no matching retry node was found in the assigned or B194 test inventory.
- Keep the B194 partial-failure selector as the negative control for x<0; it proves candidate-only treatment but not transient retry semantics.
- Ограничение: No runtime evidence in this research pass.
- Ограничение: Transient retry/same-draw preservation is semantic_test_missing on the reviewed tree.

<a id="uqs-01"></a>

## UQS-01 — Summary, интервалы и независимые информационные единицы

**Записи:** B199, B200, B201, B202. **Реестр:** B199=partial, B200=partial, B201=held, B202=held.
**Маршрут:** первый сбор Q02, Q07; historical C13, C15; дополнительно D04. **Checkpoint:** CP4. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UQS-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: UQP-02, CAL-06. Protected controls: нет.

**Дискриминатор из owner-пакета:** Один CI=0.8 и две ссылки на него сохраняют 0.8 и тип; credible не становится confidence. Четыре копии STD=1 не дают STD=0.5, четыре реально независимые оценки могут. Выборка 99 нулей и 100 сохраняет mean=1 и equal-tail[0,0] без подмены функционала. Разные атомы/корреляции при одинаковых marginal summaries доступны через carrier.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_uqs_01.py` → Q02 / C13
- `policy-engine/tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py` → Q07 / C15
- `policy-engine/tests/unit/ir/test_uncertainty.py` → отдельная дельта, вне исторической матрицы

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_uqs_01.py tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py tests/unit/ir/test_uncertainty.py
```

**Profile и доступность:** pytest extra (uv run --extra test); NumPy and IR base dependencies suffice; research/bayesian extras are unnecessary because draws are supplied directly..
**Карта поведения из статического исследования:** Behavioral unit: duplicate-origin accounting, independence/provenance requirements, and mixed interval semantics.; IR consumer support: existing carrier validation, join, and push-forward behavior.; Adapter smoke: supplied posterior draws produce a Bayesian summary and credible-interval label.

**Дополнительные пробы / границы:**
- Add the asymmetric 99-zero/one-100 input to prove posterior mean=1 and equal-tail interval=[0,0] can be represented without relabeling or widening; the current adapter smoke uses five ordinary draws.
- The Bayesian calibration producer accepts full draws but current parameter_envelopes omit distribution_payload and an exact artifact reference. Attach the existing PosteriorSamplesCarrier or CAS reference, preserve sample/draw identity and weights, and test downstream retrieval without rerunning sampling.
- Add duplicate credible-interval inputs at a non-default level and assert the result remains credible with the original level; the existing duplicate-level witness uses a confidence interval, while the mixed-semantics test checks only fail-closed bounds.
- Ограничение: No runtime evidence in this research pass.
- Ограничение: B201 and B202 producer semantics remain semantic_test_missing on the reviewed tree; the existing source adapter test is a happy-path diagnostics smoke.

<a id="wire-01"></a>

## WIRE-01 — Версионированный transport допустимых типов state

**Записи:** B94. **Реестр:** B94=partial.
**Маршрут:** первый сбор Q01, Q09; historical C02, C04; дополнительно по готовности новых проб. **Checkpoint:** CP2. **Исследователь:** e02_16.
**Источник требования:** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/WIRE-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; finding IDs выше. Dependencies: нет. Protected controls: нет.

**Дискриминатор из owner-пакета:** Decimal в budget и params после round-trip имеет прежний тип/значение. Nested non-finite/unsupported даёт точный отказ, не строку/ноль. Настоящие ArtifactRef и OutputAwareNodeOutcome проходят native codec. Запуск Ray/Temporal для codec-теста не нужен.

**Существующие пути на research SHA:**
- `policy-engine/tests/unit/remediation/test_wire_01.py` → Q01 / C02
- `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization.py` → Q09 / C04

```bash
.venv/bin/python -m pytest -c pytest.ini tests/unit/remediation/test_wire_01.py tests/unit/scientist/orchestration/engine/runner/test_serialization.py
```

**Profile и доступность:** pytest extra (uv run --extra test); orjson is a project base dependency; stdlib backend is explicitly monkeypatched by the test fixture..
**Карта поведения из статического исследования:** Behavioral unit: typed Decimal and bytes round-trip for plain, safe, and outcome state wires.; Cross-backend negative probes: stdlib and native JSON backend reject nested non-finite and unsupported values.; Integrity/version compatibility: digest binds exact bytes and legacy v0/v1 readers remain usable.; Consumer contract: real ArtifactRef and OutputAwareNodeOutcome survive native codec round-trip.

**Дополнительные пробы / границы:**
- Negative tests assert either TypeError or ValueError; if callers rely on a stable typed refusal reason, assert the exact exception class/code or stable diagnostic for each backend.
- Do not add Ray/Temporal or distributed orchestration to the codec test; the bundle explicitly says neither service is needed.
- Ограничение: No runtime evidence in this research pass.
- Ограничение: No Ray/Temporal service check is required for this codec contract.
