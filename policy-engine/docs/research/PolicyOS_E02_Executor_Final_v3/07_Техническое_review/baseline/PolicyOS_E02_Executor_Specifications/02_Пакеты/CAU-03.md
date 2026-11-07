# CAU-03 — Unit-stable conventional RDD WLS и сохранённая настоящая bounded RBC

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B210, B211.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Исправить silently wrong conventional effect при смене единиц running variable. Сохранить действительную point/variance RBC и линейную память, квалифицировать native source→report lifecycle и ограниченный scientific profile без требования включать RBC как workaround обычной регрессии.

**Тип работы:** Высокоприоритетный bounded numerical repair C54-R01; native/performance qualification; scientific applicability текущего ограниченного RBC отдельно.

[Аудит](../05_Основания/Аудит/02_Пакеты/CAU-03.md) · [остатки](../05_Основания/Аудит/01_Реестры/C54_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/CAU-03_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C54_источники.json) · [трассировка](../04_Трассировка/CAU-03.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B210 уже реализует corrected weights и их HC0 variance, не metadata flag/quadratic refit. B211 уже не выделяет N×N weight matrix. Остаток — raw powers/Gram pinv effective-rank mismatch в conventional route. A10: finite oracle/coverage только свой профиль; full inferential guarantee не следует из исправленного point.

- `preserve:0532`: Раздельные conventional и declared fixed sharp RBC profiles → REQ-CAU-03-02, REQ-CAU-03-03; TEST-CAU-03-02, TEST-CAU-03-04, TEST-CAU-03-05.
- `preserve:0533`: Combined corrected weights и HC0 variance включают bias covariance → REQ-CAU-03-03; TEST-CAU-03-04.
- `preserve:0534`: Explicit unsupported settings и missing bandwidth refusal → REQ-CAU-03-03; TEST-CAU-03-05.
- `preserve:0535`: Vector weights без product N×N diagonal → REQ-CAU-03-02; TEST-CAU-03-03.
- `preserve:0536`: Cutoff-preserving input materializer и content-bound profile → REQ-CAU-03-04; TEST-CAU-03-06.
- `preserve:0537`: Non-gating causal report projection → REQ-CAU-03-04; TEST-CAU-03-06.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C54-R01` | fix: Scaled coordinate и единая rank-revealing solve/covariance policy. | REQ-CAU-03-01, REQ-CAU-03-02 |
| `C54-G01` | qualify: Native registered materialization/report/CAS/fresh reader. | REQ-CAU-03-04 |
| `C54-G02` | qualify: Current real bounded RBC retained; broader science separately justified. | REQ-CAU-03-03, REQ-CAU-03-05 |
| `C54-G03` | qualify: Structural O(n·p) preservation and measured lifecycle if claimed. | REQ-CAU-03-02, REQ-CAU-03-06 |

Все source-registry remaining также связаны: `remaining:0330`, `remaining:0331`, `remaining:0332`, `remaining:0333`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-CAU-03-01
Conventional local polynomial использует dimensionless centered coordinate u=(x−cutoff)/h и согласованную rank/solve policy. Положительная смена единиц x,cutoff,h на общий finite scale не меняет support/weights/intercept effect/SE в численной tolerance; принятый full-rank design не теряет slope в другой pseudoinverse threshold.
Источник: B211; C54-R01. Проверки: TEST-CAU-03-01, TEST-CAU-03-02.

### REQ-CAU-03-02
Исправление solve сохраняет действительную conventional weighted-residual homoskedastic covariance formula, effective counts и kernel/order semantics. Использовать O(n·p) weighted design и одну согласованную небольшую факторизацию, без product N×N diagonal и без скрытой замены covariance на RBC/HC0. Rank-deficient/insufficient support остаются адресными отказами.
Источник: B211; C54-R01, C54-G03. Проверки: TEST-CAU-03-02, TEST-CAU-03-03.

### REQ-CAU-03-03
RBC сохраняет declared sharp/fixed h,b/q=p+1/HC0/no-cluster/no-masspoints профиль: corrected point и corrected variance включают bias-estimation uncertainty/covariance и union h/b windows. Unsupported settings не становятся uncorrected result с флагом True. Conventional remains independently supported.
Источник: B210; C54-G02. Проверки: TEST-CAU-03-04, TEST-CAU-03-05.

### REQ-CAU-03-04
Actual registered input materializer сохраняет typed cutoff и bound running/outcome vectors, не угадывает missing cutoff. Persisted whole report/envelope/fresh consumer сохраняют corrected/conventional profile, h/b/p/q, variance method, input digest и non-gating role; ни synthetic envelope ни direct pure_step не заменяют native lifecycle.
Источник: B210, B211; C54-G01. Проверки: TEST-CAU-03-06.

### REQ-CAU-03-05
Independent sensitivity oracle и finite fixed-design DGP квалифицируют только текущий sharp profile. Реальные continuity/manipulation/bandwidth assumptions остаются отдельными; расширение на fuzzy/clusters/masspoints/data-driven selectors требует названного methodological/reference профиля и новых independent tests, не флага поддержки.
Источник: B210; C54-G02. Проверки: TEST-CAU-03-04, TEST-CAU-03-05, TEST-CAU-03-07.

### REQ-CAU-03-06
Performance evidence различает размер математических структур и измеренный peak memory/runtime полного method lifecycle. Numerical correctness/rank не жертвуются ради скорости; shared native job не повторяет400-repetition campaign для каждого test.
Источник: B211; C54-G03. Проверки: TEST-CAU-03-03, TEST-CAU-03-07.

## 5. Конкретное техническое решение

**Предпочтительный conventional repair:** после выбора стороны/window построить R=[1,u,...,u^p], u=x_centered/h. A=sqrt(w)[:,None]*R, b=sqrt(w)*y. Одна rank-revealing SVD/QR определяет effective rank и решает least squares; для SVD accepted singular values s и V дают inverse normal matrix V·diag(1/s²)·Vᵀ без N×N. Coefficients и covariance используют те же rank/tolerance. Preserve sigma2=sum(w*residual²)/max(n−(p+1),1), intercept=beta0, SE=sqrt(sigma2*inverse00). Scaling не требует возвращать slope в старых единицах, если helper экспортирует только intercept/SE/count; если consumer использует coefficients, обратное преобразование явно по h^order.

Минимальный x/h+small-Gram вариант допустим только если rank/solve согласованы на accepted singular subspace и TEST01–02 проходит; просто поменять metadata rank или увеличить rcond недостаточно. Предпочтение QR/SVD избегает квадратного ухудшения conditioning normal equations. Product noN×N и no repeated factorization сохраняются содержательно, не обязательно буквальным требованием оставить pinv.

**RBC не переписывать.** Existing `_fit_rbc_polynomial` уже использует x/h,x/b, corrected weights a−L*d и combined-weight HC0 variance, сохраняет union windows. Keep bounded sharp fixed-profile и independent oracle/removal tests. Не называть quadratic refit RBC, но и не возвращать старое unsupported только потому, что clean-room implementation не внешняя rdrobust. Расширение профиля требует отдельно названной методологии/reference и finite acceptance.

Native materializer обязательно сохраняет cutoff, source vector identity и report profile. Whole-report/source checks координирует CAU-05. Численный unit fix сдаётся независимо от неизвестной external empirical validity; useful non-gating result сохраняется.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py:69–177](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L69-L177)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py:300–318](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L300-L318)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py:420–642](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L420-L642)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py:55–152](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py#L55-L152)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py:199–264](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py#L199-L264)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_dml_input_materialization.py:33–77](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_dml_input_materialization.py#L33-L77)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-CAU-03-01 · native unit-rescaling distinguishing regression
**NOT_RUN. REQ:** REQ-CAU-03-01.
**Setup:** 400unique x, y=1+.3*x_original+3*I(x>=0), cutoff0,h.7, p1 conventional. Повторить x/cutoff/h scales1,1e-8 и допустимый широкий finite scale; translated cutoff variant.
**Действие:** Actual registered conventional RDD и independent weighted lstsq на u=x_centered/h; JSON/CAS readback.
**Oracle:** Оба исходных cases jump≈3, не3.14100798995 при SUCCESS; support/counts/weights unchanged, SE согласован с own covariance oracle. Tolerance привязана к conditioning/float error, не расширена до старой ошибки. Positive unit conversion не требует bias_correction=True.
**Место:** `tests/unit/remediation/test_cau_03.py; rdd.py::_fit_local_polynomial`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-03-02 · native rank/solve/covariance reference matrix
**NOT_RUN. REQ:** REQ-CAU-03-01, REQ-CAU-03-02.
**Setup:** Triangular/epanechnikov/uniform, p1/p2, left/right, permutation, rescaling; rank-deficient repeated forcing support, insufficient rows, nonpositive bandwidth. Tiny diagonal oracle только test.
**Действие:** Compare actual fit with independent sqrt(w)-weighted QR/SVD/lstsq and preserved sigma2 covariance.
**Oracle:** Intercept/SE/counts сохраняются normal-scale и scale-equivalent designs; rank decision использует те же singular values/tolerance, что solve. Deficient support refused, no silent truncated slope. No switch conventional variance profile.
**Место:** `tests/unit/remediation/test_cau_03.py; tests/unit/foundry/methods/catalog/causal/test_rdd_rbc.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-03-03 · native allocation/factorization and bounded measurement
**NOT_RUN. REQ:** REQ-CAU-03-02, REQ-CAU-03-06.
**Setup:** 400admitted rows одной стороны, then declared larger finite n; product np.diag tripwire, actual factorization observer; separate end-to-end timer/RSS profile.
**Действие:** Run conventional helper/full method; record matrix shapes and numerical outputs.
**Oracle:** No n×n weight allocation; O(n×(p+1)) design plus small factors. One rank-revealing factorization reused for coefficients/covariance, not duplicated pinv. If retained small Gram variant selected, one pinv/rank-consistency demonstrated.6400vs1280000bytes historical structure comparison not measured speedup; new timing/RSS labelled measured only.
**Место:** `tests/unit/remediation/test_cau_03.py; rdd.py::_fit_local_polynomial`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-03-04 · native RBC independent sensitivity/removal oracle
**NOT_RUN. REQ:** REQ-CAU-03-03, REQ-CAU-03-05.
**Setup:** Existing curved and piecewise-linear signals, h=.45/b=.70 and reverse; independent weighted-lstsq unit-outcome perturbations.
**Действие:** Actual RBC point/SE vs independent functional derivative HC0 oracle; remove correction and corrected-covariance separately in controlled mutants.
**Oracle:** Both bandwidth orders agree within existing tolerances; curved correction nonzero, linear correction zero. Removal mutants fail despite preserved RBC metadata. Corrected SE not old uncorrected SE; union h/b support retained.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-03-05 · native profile refusal and bounded coverage
**NOT_RUN. REQ:** REQ-CAU-03-03, REQ-CAU-03-05.
**Setup:** Explicit sharp h,b,q=p+1 HC0; missing/bad h/b, fuzzy/clustering/masspoint/unsupported q/variance requests. Existing400-repetition fixed-design heteroskedastic DGP seed2026102803.
**Действие:** Run focused profile controls and once existing DGP.
**Oracle:** Unsupported settings typed refusal, no hidden conventional fallback. Existing coverage acceptance[.915,.985] with all accepted/failed counts retained; historical371/400 not required as immutable future exact count. No claim universal95% coverage or installed rdrobust equivalence.
**Место:** `test_rdd_rbc.py; test_rdd_rbc_independent_oracle.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-03-06 · native materialize→registry→CAS→fresh consumer E02-I05-B
**NOT_RUN. REQ:** REQ-CAU-03-04.
**Setup:** Actual source-bound vectors with typed fallback cutoff0.2, running∈[-1,1], jump2.5 case; missing cutoff negative; conventional and RBC profiles.
**Действие:** Native dispatcher/materializer→whole CausalEffectReport/envelope persistence→fresh selected reader.
**Oracle:** Cutoff not lost, expected jump≈2.5; missing cutoff refused before compute. Full h/b/p/q/profile/digest/estimate/SE and gate_eligible=False survive; forged output/profile refused by canonical readback. No fixture envelope substitutes actual route.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_rdd_dml_input_materialization.py; test_rdd_rbc.py; CAU-05 shared job owner`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-03-07 · bounded methodology/performance applicability
**NOT_RUN. REQ:** REQ-CAU-03-05, REQ-CAU-03-06.
**Setup:** Chosen real study forcing/outcome/cutoff definition, manipulation/continuity assumptions, selected bandwidth policy; declared n/kernel/order/backend benchmark.
**Действие:** Record study-method profile and independent methodological/reference comparison only for requested extension; measure lifecycle if performance claim required.
**Oracle:** Current conventional/RBC numerical result remains conditional on stated assumptions. New fuzzy/cluster/masspoint claims not admitted without matching reference/acceptance; missing scientific source not replaced by synthetic curvature. Actual runtime/RSS denominators recorded without universal speedup promise.
**Место:** `RDD method/study owner; DEC-PROFILE`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_cau_03.py tests/unit/foundry/methods/catalog/causal/test_rdd_rbc.py tests/unit/foundry/methods/catalog/causal/test_rdd_dml_input_materialization.py
python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py
# Native shared consumer accepted with CAU-05; commands NOT_RUN.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-B**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

CAU-03 владеет conventional/RBC numerical owner rdd.py и focused tests; IR/report helper изменения только согласованно с CAU-01/05. Один numerical slot для independent oracle/DGP; no repeated dependency installs или внешней библиотеки ради каждого packet.

- **CAU-01:** Shared typed causal report/metadata, not replacement of RDD inference.
- **CAU-05:** Native registry/source→whole-report selected-consumer acceptance shared.

## 8. Совместимость, миграция и возврат

Normal-scale valid conventional outputs эквивалентны в обоснованной tolerance; extreme unit case intentional correction. Covariance profile/name не меняется без отдельного решения. RBC metadata/version и historical outputs не переписывать; input digest отражает фактические units/params. Rollback при проблеме ограничивает неподдержанный numeric range с useful output, не выдаёт неверный SUCCESS и не принуждает к другой inference процедуре.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0, reusable numerical contracts](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Dimensionless general solver поддерживает новую единицу измерения без bespoke case; stronger inference требует своего profile, не label.
- [wave5-evidence-substitution-ratification.md — K01/K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Corrected point/variance и finite coverage не заменяют real-data causal assumptions/authority; non-gating output полезен.

## 10. Конечные решения и сдача

### DEC-CAU-03-PROFILE
**Вопрос:** Нужен ли профиль шире текущего sharp/fixed-bandwidth/q=p+1/HC0?
**Кто решает:** RDD numerical/methodological reviewer.
**Конечное действие/выход:** Назвать конкретный requested design; если шире — выбрать primary methodological/maintained reference с matching settings, сравнить formulas/point/SE и новый independent DGP. Не расширять silently. Если текущего профиля достаточно, preserve и квалифицировать его assumptions.
**До решения:** Current bounded profile, no fuzzy/cluster/masspoint/data-driven selector guarantee.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
