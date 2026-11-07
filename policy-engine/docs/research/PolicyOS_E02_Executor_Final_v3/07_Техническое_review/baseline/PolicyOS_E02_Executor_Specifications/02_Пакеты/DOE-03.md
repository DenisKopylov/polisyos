# DOE-03 — Не повышать median-imputed trajectory до обычного CI

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

**REQ-DOE-03-03.** PCA component count должен соблюдать centered rank до backend choice; unmet variance threshold и малый sample scope не называются scientific sufficiency.

**REQ-DOE-03-04.** Native Morris point и uncertainty должны использовать одну declared normalized effect convention и source trajectory basis; unsupported transformed coordinate UQ не угадывается.

**REQ-DOE-03-05.** Fresh consumer должен сохранить original/retained trajectory binding, units, failure/imputation/selection limitations и допустимый partial-output scope.

## 5. Конкретное техническое решение — рекомендуемый способ

- В _prepare_analysis_inputs при actual imputed rows добавить explicit imputation_applied, row IDs/method=observed_median и qualification not_established в existing preparation metadata. MultiOutputAnalyzer уже передаёт context каждому component — сохранить его.
- В _attach_morris_uncertainty рядом с selection_bias guard проверять imputation posture: без qualified model _append_uncertainty_warning(...imputation_model_not_established), сохранить point/complete observations. Не запрещать exploratory imputation целиком и не invent correction variance. Проверить соседние uncertainty attachments, чтобы общий prepared context не терялся; расширение beyond Morris только при actual affected route.
- Existing source trajectory/storage и normalized EE owners остаются одними. Whole-block drop не устраняет selection bias. PCA units/ranking — ограниченное предметное решение фактического consumer, не автоматическая стандартизация всех outputs.

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

**Setup:** Float64 fixed matrix из tests/unit/remediation/test_doe_03.py:178–219: X=[[0,0,0,0,1],[1,2,3,4,0],[2,4,6,8,1]], max_components5, min_variance_explained1. Centered nonzero singular-value squares60 и2/3 (разделённый spectrum); retain оба. Отдельный cap fixture из :222–245: 6×5 matrix [I5; zero row], max_components1, threshold0.95. Constant/zero-centered public inputs — отдельные negative controls.

**Действие:** Run actual sklearn и NumPy fallback (единственный fallback seam — controlled sklearn import failure по existing test); те же данные, centering и retained rank. Для full-rank2 case сравнить полный retained feature projector VᵀV, не ориентацию знаков/eigenvectors; cap case проверять отдельно.

**Oracle:** Для X оба backends дают2 centered components, variance ratios[90/91,1/91] с atol=1e-8, rtol=1e-8. Полный projector сравнить с независимым analytic block diag(vvᵀ/30,1), v=[1,2,3,4], atol=1e-8, rtol=1e-8; это full retained subspace, не обрезанный tied eigenspace. Для cap fixture ровно1 component, explained ratio6/25=0.24 (<0.95), status unmet_limited с тем же metadata; leading eigenspace здесь tied, поэтому НЕ требовать одинаковый rank1 projector/vector между backends. Constant/zero public input отказывает до ложного successful PCA.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-03-04 → REQ-DOE-03-04

**Уровень:** SALib1.5.2 point/bootstrap. **Ожидается:** positive + negative + boundary.

**Setup:** y=2x on[0,10], transformed units x′=100x with y=.02x′; output×1000.

**Действие:** Real sampler/analyzer and retained EE bootstrap with fixed seed.

**Oracle:** Normalized EE/point20 (rtol=1e-6 atol=1e-8), unit change invariant; output×1000 scales point/CI×1000. Unsupported nonuniform/grouped/scaled profile returns UQ unavailable, не universal multiplier.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DOE-03-05 → REQ-DOE-03-05

**Уровень:** E02-I10-C persisted trajectory. **Ожидается:** positive + negative + boundary.

**Setup:** Existing retained matrix/artifact owner, actual fresh reader; source row/axis/unit mismatch controls.

**Действие:** Save→load→recompute supported point/UQ; consume explicit partial outputs.

**Oracle:** Exact source and limitations survive, source mismatch rejects affected claim; restored JSON parity не empirical coverage proof.

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
