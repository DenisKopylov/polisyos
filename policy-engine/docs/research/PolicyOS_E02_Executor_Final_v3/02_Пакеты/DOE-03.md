# DOE-03 — Не повышать median-imputed trajectory до обычного CI

**Редакция: PROPOSED v2 — адресные изменения FN-DOE-PCA-RNG. Содержательное review изменений выполнено; принятие проектом и реализация остаются отдельными шагами. Все product tests NOT_RUN.**

**LANE-10 · B102, B103, B104, B105 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Сохранить полезный exploratory analysis и точные failed counts, не скрывая модель восстановления.

**Тип:** C118-R01 semantic fix; C118-G01/G02 native/source/scientific qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/DOE-03.md), [исходные карточки](../05_Основания/Аудит/05_Источники/DOE-03_исходные_строки.txt), [трассировка](../04_Трассировка/DOE-03.json).

## 2. Уже работает — сохранить

- Whole trajectory filtering, original denominator/failure reasons, pre-PCA shared policy.
- Limited selection posture и centered-rank cap; unmet threshold не success.
- Normalized EE и storage convention одинаковы для point/UQ.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B102 | fix | REQ-DOE-03-01, REQ-DOE-03-02, REQ-DOE-03-05 | Whole-block repair сохранить; imputation не measured baseline. |
| B103 | fix | REQ-DOE-03-01, REQ-DOE-03-02, REQ-DOE-03-05 | Counts repaired, unqualified CI остаётся. |
| B104 | qualify | REQ-DOE-03-03 | Rank repair проверяется на обоих backends. |
| B105 | qualify | REQ-DOE-03-04, REQ-DOE-03-05 | Normalized EE source/native parity открыта. |
| C118-R01 | fix | REQ-DOE-03-01 | Count не заменяет imputation uncertainty model. |
| C118-G01 | qualify | REQ-DOE-03-04, REQ-DOE-03-05 | Real SALib point + retained artifact consumer. |
| C118-G02 | lifecycle | REQ-DOE-03-02, REQ-DOE-03-03, REQ-DOE-03-05 | Geometry/positional IDs не source и не selection-bias solution. |

## 4. Нормативные требования результата

**REQ-DOE-03-01.** При failed outputs и explicit median imputation ordinary Morris CI не получает status ok без квалифицированной missingness/imputation model; exploratory point/result сохраняется с limitation.

**REQ-DOE-03-02.** Scalar/multi-output preparation должны одинаково применять failure policy до PCA, сохранять original counts/reasons/whole block IDs и selection limitations.

**REQ-DOE-03-03.** PCA component count должен соблюдать centered rank до backend choice; unmet variance threshold и малый sample scope не называются scientific sufficiency. PCA preprocessing принадлежит whole-request RNG contract DOE-02: explicit local stochastic stream и actual resolved solver/profile фиксируются в producer record. Small rank fixtures не заменяют qualification randomized solver на поддержанном большем shape.

**REQ-DOE-03-04.** Native Morris point и uncertainty должны использовать одну declared normalized effect convention и source trajectory basis; unsupported transformed coordinate UQ не угадывается.

**REQ-DOE-03-05.** Fresh consumer должен сохранить original/retained trajectory binding, units, failure/imputation/selection limitations и допустимый partial-output scope. Multi-output source binding включает actual PCA backend/version/solver/profile/local seed и component cap; fresh read не использует ambient RNG/default auto policy для восстановления объявленного replay.

## 5. Конкретное техническое решение — рекомендуемый способ

- В _prepare_analysis_inputs при actual imputed rows добавить explicit imputation_applied, row IDs/method=observed_median и qualification not_established в existing preparation metadata. MultiOutputAnalyzer уже передаёт context каждому component — сохранить его.
- В _attach_morris_uncertainty рядом с selection_bias guard проверять imputation posture: без qualified model _append_uncertainty_warning(...imputation_model_not_established), сохранить point/complete observations. Не запрещать exploratory imputation целиком и не invent correction variance. Проверить соседние uncertainty attachments, чтобы общий prepared context не терялся; расширение beyond Morris только при actual affected route.
- Existing source trajectory/storage и normalized EE owners остаются одними. Whole-block drop не устраняет selection bias. PCA units/ranking — ограниченное предметное решение фактического consumer, не автоматическая стандартизация всех outputs.

**PCA profile без нового framework.** Existing MultiOutputAnalyzer использует общий DOE-02 request/stage seed owner. Для bounded randomized qualification задаётся explicit profile sklearn1.8.0: svd_solver=randomized, n_oversamples=10, iterated_power=7, power_iteration_normalizer=QR, component cap5, min_variance_explained=1, local random_state из DOE-02. Small fixtures/fallback full SVD сохраняются и имеют собственный declared backend profile. Исполнитель не должен silently менять numerical tolerances, fixture seed search или solver параметры после просмотра failing oracle. Direct analytic DCT matrix проверяет solver/seed/subspace; отдельно source-bound Morris fixture проверяет integration и repeated-input semantics. Ни один не доказывает empirical sensitivity accuracy или CI coverage.

**Существующие code/test owners:**
- [`src/polisyos/scientist/methods/doe/analysis.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/analysis.py).
- [`src/polisyos/scientist/methods/doe/multi_output.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/multi_output.py).
- [`src/polisyos/scientist/methods/doe/uncertainty.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/uncertainty.py).
- [`tests/unit/remediation/test_doe_03.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_doe_03.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-DOE-03-01 → REQ-DOE-03-01, REQ-DOE-03-05

**Уровень:** actual preparation→uncertainty. **Ожидается:** positive + negative + boundary.

**Setup:** 48-row Morris fixture, один failed output, explicit IMPUTE_BASELINE; complete control.

**Действие:** Actual bootstrap attachment через scalar и multi-output; persist/read.

**Oracle:** Point provisional доступен, failed count1 сохранён; uncertainty unavailable/limited с imputation reason, не ordinary ok. Complete control может дать supported CI. Удаление guard воспроизводит R01.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-03-02 → REQ-DOE-03-02

**Уровень:** policy/block matrix. **Ожидается:** positive + negative + boundary.

**Setup:** 12 rows/4 two-param trajectories; failures[1] и[1,4,5], FAIL_FAST/min_success_rate/IMPUTE controls.

**Действие:** Scalar/multi actual preparation before PCA.

**Oracle:** Retained IDs [1,2,3] и[2,3], no survivor splice; original N12 и failures preserved. Same policy refusal before backend; geometry проверяет coordinate changes.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-03-03 → REQ-DOE-03-03

**Уровень:** real sklearn + NumPy. **Ожидается:** positive + negative + boundary.

**Setup:** Float64 fixed matrix из tests/unit/remediation/test_doe_03.py:178–219: X=[[0,0,0,0,1],[1,2,3,4,0],[2,4,6,8,1]], max_components5, min_variance_explained1. Centered nonzero singular-value squares60 и2/3 (разделённый spectrum); retain оба. Отдельный cap fixture из :222–245: 6×5 matrix [I5; zero row], max_components1, threshold0.95. Constant/zero-centered public inputs — отдельные negative controls. Добавить direct PCA fixture D (НЕ model/Morris data): float64 i=0..599,j=1..100, D[i,j−1]=2^(−j/4)*sqrt(2/600)*cos(pi*(i+.5)*j/600). Формула задаёт centered orthogonal columns с known singular values s_j=2^(−j/4). Для explicit randomized profile из §5 cap5/threshold1, analytic leading sample-space basis U5 задаётся той же cos формулой без s_j. Отдельный source-bound fixture M: двухпараметровый Uniform[0,1] Morris, num_levels=8 у обеих axes,200 trajectories/600rows; outputs j=10a+b, a,b=0..9: f_j(x1,x2)=2^(−j/8)*P_a(2x1−1)*P_b(2x2−1). Legendre polynomials определять независимой recurrence P0=1,P1=z,P_(k+1)=((2k+1)zP_k−kP_(k−1))/(k+1), не row index/replica RNG. Один и тот же sample parameter vector обязан давать тот же output. Конечный preflight ДО tested PCA: по seeds[13,17,19,23] в этом порядке actual SALib генерирует designs, deterministic model вычисляет outputs; independent NumPy float64 full SVD centered matrix проверяет shape600×100, finite values, rank>15 при cutoff1e-10*s1 и relative gap(s5−s6)/s1≥1e-3. Выбрать первые два прошедших seed как A/B; сохранить все preflight ranks/singular values/reasons, canonical inputs и matrix hashes. Если меньше двух — qualification NOT_RUN/fixture-preflight-blocked, не менять список/формулу/tolerance ради PASS. После freeze никакого выбора fixtures по PCA output. Default num_levels4 здесь не подходит для требования rank>15 у deterministic2D grid.

**Действие:** Run actual sklearn и NumPy fallback (единственный fallback seam — controlled sklearn import failure по existing test); те же данные, centering и retained rank. Для full-rank2 case сравнить полный retained feature projector VᵀV, не ориентацию знаков/eigenvectors; cap case проверять отдельно. Для D execute actual explicit randomized solver/profile с local seed и snapshot external RNG; full-SVD reference separate. Для M после preflight freeze выполнить full source-bound PCA→Morris analysis AB/BA/replay по TEST-DOE-02-02, затем actual persistence→fresh reader TEST05. Сравнение duplicate sample inputs/output и block geometry производится до PCA. Нельзя подставить precomputed scores или заменить sklearn solver.

**Oracle:** Для X оба backends дают2 centered components, variance ratios[90/91,1/91] с atol=1e-8, rtol=1e-8. Полный projector сравнить с независимым analytic block diag(vvᵀ/30,1), v=[1,2,3,4], atol=1e-8, rtol=1e-8; это full retained subspace, не обрезанный tied eigenspace. Для cap fixture ровно1 component, explained ratio6/25=0.24 (<0.95), status unmet_limited с тем же metadata; leading eigenspace здесь tied, поэтому НЕ требовать одинаковый rank1 projector/vector между backends. Constant/zero public input отказывает до ложного successful PCA. D: ровно5 retained components; reference explained ratios s_j²/sum_(q=1..100)s_q², actual ratios rtol=1e-5/atol=1e-8. Из actual score columns получить orthonormal Q5; leading-subspace distance sqrt(max(0,10−2*||Q5.T@U5||_F²))≤1e-3, то есть сравнивается projector без sign ambiguity и без600×600 allocation. Reconstruction residual ||D−Q5@(Q5.T@D)||_F≤1.01*sqrt(sum_(j=6..100)s_j²)+1e-12; это analytic truncated-SVD lower bound с declared approximation tolerance. M: exact source/row identities и identical repeated-parameter outputs; whole-pipeline same-request arrays/indices rtol=1e-10/atol=1e-12 и external RNG unchanged по DOE02. Preflight SVD — fixture qualification/reference, не tested PCA output и не empirical model evidence. Исходные small3×5/6×5, fallback и tied-subspace caveats выше сохраняются полностью. Если rank/gap/native solver недоступны, честный конкретный NOT_RUN, не уменьшение проверяемого scope до старой tiny matrix.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-03-04 → REQ-DOE-03-04

**Уровень:** SALib1.5.2 point/bootstrap. **Ожидается:** positive + negative + boundary.

**Setup:** y=2x on[0,10], transformed units x′=100x with y=.02x′; output×1000.

**Действие:** Real sampler/analyzer and retained EE bootstrap with fixed seed.

**Oracle:** Normalized EE/point20 (rtol=1e-6 atol=1e-8), unit change invariant; output×1000 scales point/CI×1000. Unsupported nonuniform/grouped/scaled profile returns UQ unavailable, не universal multiplier.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-03-05 → REQ-DOE-03-05

**Уровень:** E02-I10-C persisted trajectory. **Ожидается:** positive + negative + boundary.

**Setup:** Existing retained matrix/artifact owner, actual fresh reader; source row/axis/unit mismatch controls. Дополнить source-bound Morris M из TEST03 с actual solver/local-seed/profile metadata; negative altered solver/seed при прежнем raw matrix.

**Действие:** Save→load→recompute supported point/UQ; consume explicit partial outputs.

**Oracle:** Exact source and limitations survive, source mismatch rejects affected claim; restored JSON parity не empirical coverage proof. Fresh recomputation использует именно recorded qualified profile и actual original/retained rows; missing/tampered PCA provenance ограничивает affected reproducibility claim. Partial useful source results сохраняются по прежней policy, но current defaults не считаются восстановленными historical facts.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-C** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: DOE-02. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

DOE-02 source design binding; один writer analysis.py. Shared native SALib/retained fixture.

## 8. Совместимость и восстановление

Existing imputation explicitly allowed for exploratory point; new limitation intentional semantic correction. Historical ok не retroactively certified; fresh consumer current qualification отдельно. Qualified restoration model возможна только отдельным typed profile с validation.

## 9. Free-grow и design decisions

- [North Star §5](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#5-data-acquisition-and-the-real-product) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): ограниченный поиск даёт полезный результат и следующий запрос данных, не ложную полноту. [Синтез §4](../05_Основания/Исследование/design_direction.md): развивать существующий общий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-DOE-03-01: actual PCA consumer задаёт units/metric/ranking assumptions и partial-output scope; выход короткая declared contract table, не всеобщая normalization policy. Missingness correction требует предметного основания и не блокирует narrow limitation fix.

## 11. Что предъявить и что не является готовностью

R01 regression должен различать ordinary CI promotion; native SALib и fresh artifact separately. Shape/rank admissibility не sample sufficiency/coverage.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0165` → REQ-DOE-03-01; Count не заменяет imputation uncertainty model.
- `remaining:0166` → REQ-DOE-03-04, REQ-DOE-03-05; Real SALib point + retained artifact consumer.
- `remaining:0167` → REQ-DOE-03-02, REQ-DOE-03-03, REQ-DOE-03-05; Geometry/positional IDs не source и не selection-bias solution.
- `preserve:0273` → REQ-DOE-03-02; Whole trajectory filtering — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0274` → REQ-DOE-03-02; Original denominator and failure reasons — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0275` → REQ-DOE-03-02; Pre-PCA shared policy — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0276` → REQ-DOE-03-01, REQ-DOE-03-02; Limited selection posture — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0277` → REQ-DOE-03-03; Centered-rank cap — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0278` → REQ-DOE-03-03; Unmet variance threshold metadata — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0279` → REQ-DOE-03-04, REQ-DOE-03-05; Normalized EE/storage consistency — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
