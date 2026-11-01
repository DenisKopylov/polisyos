# SCM-02 — Масштабно корректная posterior sampling и условный совместный закон корней

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B215, B223.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Исправить два конкретных нарушения conditional law, сохранить точную Gaussian/full-factual abduction и явный двухсторонний contrast. Квалифицировать действительный refit отдельно от fixed-model distribution.

**Тип работы:** Два bounded numerical/conditional-law repair C58-R01/R02; native custody и отдельная refit/scientific qualification.

[Аудит](../05_Основания/Аудит/02_Пакеты/SCM-02.md) · [остатки](../05_Основания/Аудит/01_Реестры/C58_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/SCM-02_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C58_источники.json) · [трассировка](../04_Трассировка/SCM-02.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B215 original imputed-as-observed исправлен для independent linear Gaussian; R01/R02 остаются. B223 target/comparator и sentinel уже исправлены. A07 требует surgery/factual/shared-noise preservation. C58-G02 refit явно относится сюда как отдельная qualification, а не автоматически SCM-03.

- `preserve:0548`: Independent linear-Gaussian posterior and full factual control → REQ-SCM-02-01, REQ-SCM-02-02; TEST-SCM-02-01, TEST-SCM-02-03.
- `preserve:0549`: Explicit unsupported abduction limitations → REQ-SCM-02-03, REQ-SCM-02-08; TEST-SCM-02-05.
- `preserve:0550`: Typed distinct target/comparator and legacy normalization → REQ-SCM-02-05; TEST-SCM-02-06, TEST-SCM-02-07.
- `preserve:0551`: Shared-U ITE versus independent arm means distinction → REQ-SCM-02-02, REQ-SCM-02-05; TEST-SCM-02-02, TEST-SCM-02-06.
- `preserve:0552`: Conservative non-gating envelopes and raw provenance refusal → REQ-SCM-02-06, REQ-SCM-02-07, REQ-SCM-02-08; TEST-SCM-02-07, TEST-SCM-02-08, TEST-SCM-02-09.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C58-R01` | fix: Scale-aware factor/draw owner без абсолютного physical covariance cutoff. | REQ-SCM-02-01, REQ-SCM-02-02 |
| `C58-R02` | fix: Поддержанный finite joint conditional sampling с positive oracle, не только новый warning. | REQ-SCM-02-03, REQ-SCM-02-04 |
| `C58-G01` | qualify: Actual persisted query/ensemble custody, не local JSON-only. | REQ-SCM-02-05, REQ-SCM-02-06 |
| `C58-G02` | qualify: Source-bound refit отдельно закреплён здесь; fixed-model law и scientific assumptions не смешиваются. | REQ-SCM-02-02, REQ-SCM-02-07, REQ-SCM-02-08 |

Все source-registry remaining также связаны: `remaining:0340`, `remaining:0341`, `remaining:0342`, `remaining:0343`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-SCM-02-01
Shared Gaussian draw owner сохраняет любую представимую ненулевую PSD posterior covariance при допустимой смене единиц. Абсолютный allclose-atol1e-12 не может объявлять random posterior deterministic. Rank/PSD handling выполняется в нормированных координатах с контролируемой roundoff policy; exact deterministic structure и incompatible factual evidence остаются различимыми.
Источник: B215; C58-R01. Проверки: TEST-SCM-02-01, TEST-SCM-02-02, TEST-SCM-02-03.

### REQ-SCM-02-02
Для supported independent linear-Gaussian SCM partial factual input condition-ит совместный закон U, а не фиксирует residual по imputed parent. Один posterior draw используется в сравниваемых worlds; ненулевая marginal variance не обязана означать ненулевую ITE variance. Полный factual input сохраняет точную residual-инверсию.
Источник: B215; C58-R01, C58-G02. Проверки: TEST-SCM-02-01, TEST-SCM-02-02, TEST-SCM-02-03.

### REQ-SCM-02-03
В declared finite aligned empirical joint-root profile factual root evidence condition-ит общий row index: выбираются только rows, совместимые со всеми observed roots данного group, с сохранением их исходных multiplicities. Нельзя выбирать unconditional row и затем перезаписывать один root. Empty compatible support — incompatible evidence; unsupported partial nonlinear evidence — явная limitation/refusal, не exact fallback.
Источник: B215; C58-R02. Проверки: TEST-SCM-02-04, TEST-SCM-02-05.

### REQ-SCM-02-04
Conditional-row plan и evidence dependencies общие для GCM/twin и согласованы с SCM-01 relevance closure. Root observation не становится do-intervention и non-ancestor evidence не удаляется, если общий закон связывает его с outcome. Unconditional common-row sampling и genuinely exact full-parent residual сохраняются.
Источник: B215; C58-R02. Проверки: TEST-SCM-02-04, TEST-SCM-02-05, TEST-SCM-02-06.

### REQ-SCM-02-05
Canonical typed target/comparator, observational regime и no-override sentinel сохраняются в request/result/persisted metadata. Explicit do0, natural comparator и identical arms различаются; shared-U ITE не заменяется разностью независимых arm samples. Ensemble требует совпадающие canonical arms до aggregation.
Источник: B223; C58-G01. Проверки: TEST-SCM-02-06, TEST-SCM-02-07.

### REQ-SCM-02-06
Native selected method→CAS→fresh reader→Scientist/ensemble проверяет actual source, whole output/aliases/request, manifest versions и derived envelope. Raw DTO normalization не создаёт source provenance; partial unsupported law остаётся non-gating.
Источник: B215, B223; C58-G01. Проверки: TEST-SCM-02-07.

### REQ-SCM-02-07
Fixed-model outcome/ITE distribution не является estimator sampling CI. Для заявленного iid refit interval реальный worker переобучает все mechanisms на каждом полном aligned row resample; interval связывает source/data/rows/graph/target/indices/fit response и читается fresh validator. Conditional individual counterfactual, undeclared iid unit или native/manual SCM не получают этот interval. Each replica target/contrast and final percentile endpoints должны совпадать с независимым finite-design oracle, а не только source-row coefficient validator или width-shrink ratio. Quantile convention и полный replica denominator фиксируются; same interval helper producer/validator не считается независимым numerical oracle.
Источник: B215, B223; C58-G02. Проверки: TEST-SCM-02-08, TEST-SCM-02-09.

### REQ-SCM-02-08
Synthetic Gaussian/finite empirical/refit controls квалифицируют только названные laws/estimands. Causal graph correctness, scientific identification и real-data sampling assumptions имеют отдельное основание; candidate calculation остаётся полезным без автоматической authority.
Источник: B215, B223; C58-G02. Проверки: TEST-SCM-02-05, TEST-SCM-02-08, TEST-SCM-02-09.

## 5. Конкретное техническое решение

**Gaussian.** Удалить shortcut `allclose(cov,0,atol=1e-12)`. Подготовить scale-normalized PSD factor один раз при abduction, переиспользовать draws. Предпочтительно оперировать стандартизованными structural noises и observation map: rank-revealing SVD/QR задаёт observed/null subspaces, а posterior factor переносится обратно в физические units. Если сохраняется covariance API, нормировать её согласованными noise scales, symmetrize, проверять negative eigenvalues относительно norm/epsilon и факторизовать положительную часть. Не отбрасывать положительные eigenvalues только потому, что они малы в физических units. Deterministic branch подтверждается нулевым structural factor, а не absolute magnitude. Не добавлять jitter как замену научно нулевой дисперсии. Сохранить explicit incompatible-evidence check, проверить его rescaling вместе с factor.

**Empirical roots.** Для существующего aligned carrier group вычислить compatible row indices по всем factual root observations. В bounded finite discrete profile сравнение exact declared values, без nearest-match bandwidth. Выбирать общий index из этого списка с исходной multiplicity и использовать во всех связанных roots/обеих worlds. Empty intersection — incompatible evidence; descendant/nonlinear evidence требует собственного posterior и не притворяется root filter. Admission diagnostic exact только когда весь relevant evidence действительно покрыт этим rule/fully observed residual. Условия и selected carrier identity участвуют в request/result lineage. Unknown joint dependencies не заменять independence.

**Refit.** Existing `_refit_bootstrap_interval`→`_fit_gcm_specs`→worker.gcm_fit уже resamples полные rows и возвращает каждую fitted model. Требуется actual qualification, не новая bootstrap архитектура. Выполнить source-bound positive и target/indices mutation controls; зафиксировать distinction n predictive draws vs n iid units vs n refits. General counterfactual posterior и real-study sampling validity не закрываются ростом Monte Carlo count.

**v2 / CS-005:** сохранить real aligned full-row refits, source-row OLS validation и existing n400/800 shrink diagnostic. Дополнить независимый target/quantile audit на маленьком linear SCM: gcm_query validator повторно использует _refit_interval_from_models, поэтому сам не обнаруживает общую target aggregation ошибку. Новый test не обещает coverage и не заменяет iid row bootstrap другим law.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:788–1015](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L788-L1015)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:1069–1163](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1069-L1163)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:1371–1489](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1371-L1489)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py:458–507](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L458-L507)
- [policy-engine/workers/dowhy-014/worker.py:220–245](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/workers/dowhy-014/worker.py#L220-L245)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py:491–527](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py#L491-L527)
- [policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py:657–680](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py#L657-L680)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-SCM-02-01 · native posterior analytic/metamorphic
**NOT_RUN. REQ:** REQ-SCM-02-01, REQ-SCM-02-02.
**Setup:** X=Ux,Y=X+Uy, independent U~N(0,s²), evidenceY=2s; s=1 и1e-7; query doX0.
**Действие:** Сравнить actual posterior с closed form mean(s,s),cov=s²[[.5,-.5],[-.5,.5]], затем4096 draws fixedseed.
**Oracle:** Analytic covariance согласована с relative tolerance; нормированный draw mean≈1 (abs.05),variance≈.5 (abs.06),distinct draws>1 при обоих scales. Старый allclose branch проваливает small-scale control. Непредставимый underflow не требует фиктивного noise, получает numerical-range boundary.
**Место:** `tests/unit/remediation/test_scm_02.py; gcm_query.py::_draw_linear_gaussian_noises`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-02-02 · native twin marginal/shared-U
**NOT_RUN. REQ:** REQ-SCM-02-01, REQ-SCM-02-02.
**Setup:** Тот же partial Gaussian s1e-7, twin armsX0/Xs с общим posterior draw.
**Действие:** Получить обе potential-outcome arrays и ITE; нормировать к s.
**Oracle:** Marginal variance≈.5 у обеих worlds; ITE=s с roundoff-level variance при этой additive model. Нельзя использовать deterministic ITE как oracle отсутствия stochastic marginals.
**Место:** `twin_network_query.py; shared posterior draw owner`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-02-03 · native singular/full-factual boundary
**NOT_RUN. REQ:** REQ-SCM-02-01, REQ-SCM-02-02.
**Setup:** X=s,Y=2s full factual; deterministic zero model с incompatibleY=2s; valid rank-deficient conditioning; finite rescaling.
**Действие:** Подготовить posterior factor один раз и выполнить draws/query.
**Oracle:** Full factual givesY(0)=s без добавленного искусственного jitter; incompatible evidence refused. PSD roundoff negative допускается лишь по explicit normalized relative rule, materially indefinite covariance refused. Removing absolute threshold не должно создать произвольный шум в exact branch.
**Место:** `gcm_query.py::_linear_gaussian_posterior/_prepare_linear_gaussian_abduction`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-02-04 · native finite joint-law distinguishing regression
**NOT_RUN. REQ:** REQ-SCM-02-03, REQ-SCM-02-04.
**Setup:** Joint rows(W,Z)={(0,0),(10,1)},Y=T+W, factualZ1,doT0; second carrier duplicate rows to test empirical weights; unconditional control.
**Действие:** Actual DTO→query и supported twin conditional path через общий row selector.
**Oracle:** ConditionalY10/std0, невозможная pair(0,1) никогда не создаётся; unconditional только original pairs. Для нескольких compatible rows selection frequencies сохраняют исходную multiplicity по предзаданному multinomial tolerance, не uniform по unique values. Старый pin-root путь проваливает exact support oracle.
**Место:** `tests/unit/remediation/test_scm_02.py; _joint_root_sample_index/conditional companion`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-02-05 · native evidence/error/limitation
**NOT_RUN. REQ:** REQ-SCM-02-03, REQ-SCM-02-04, REQ-SCM-02-08.
**Setup:** EvidenceZ2 отсутствует в finite support; condition на двух roots с пустым intersection; nonlinear partial evidence вне bounded profile; full observed polynomial residual positive.
**Действие:** Вызвать common abduction plan и обе consumers.
**Oracle:** Empty support адресно incompatible, не nearest-row match и не unconditional fallback. Unsupported nonlinear posterior имеет truthful limited/non-gating diagnostic, не exact_residual_fallback. Fully observed supported residual остаётся полезным. No automatic empirical identification claim.
**Место:** `_fallback_residual_is_exact; _prepare_linear_gaussian_abduction; SCM-01 predictor`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-02-06 · native explicit contrast laws
**NOT_RUN. REQ:** REQ-SCM-02-04, REQ-SCM-02-05.
**Setup:** Y=1+3X, targetX2/comparatordo0; natural root mean4; identical arms; two declared stochastic uniform arms.
**Действие:** Natural comparator и stochastic arms выполняются существующим GCM attribution route; public TwinNetworkQueryData проверяется отдельно только с двумя текущими float ATOMIC arms. Request→JSON result сохраняет обе arms и sharedU без расширения twin API.
**Oracle:** Explicit contrast6; identical arms0; natural comparator≈-6 в Monte Carlo tolerance, не0. Typed stochastic laws сохранены. Observed auxiliary root из TEST04 не вырезается structural-only closure.
**Место:** `tests/unit/remediation/test_scm_02.py; causal_queries.py::CausalContrastSpec`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-02-07 · native E02-I05-C custody/ensemble
**NOT_RUN. REQ:** REQ-SCM-02-05, REQ-SCM-02-06.
**Setup:** Actual bound query jobs, real CAS/fresh process; valid common contrast ensemble и один foreign comparator member; current and declared legacy result profiles.
**Действие:** Reopen typed result and reconcile whole canonical output/aliases/request; mutate arms/source/profile/diagnostics with valid new serialization.
**Oracle:** Valid result reaches consumer; mismatched member arms rejected before aggregation; foreign content/profile/request refused; raw legacy DTO не получает manifest provenance. Mock run_job tests отдельно labeled, genuine method job обязателен.
**Место:** `scientist/nodes/builtins/causal/run_causal_queries.py; run_causal_ensemble.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-02-08 · real selected refit qualification
**NOT_RUN. REQ:** REQ-SCM-02-07, REQ-SCM-02-08.
**Setup:** Existing test_true_refit_sampling_interval_shrinks_predictive_distribution_does_not: n400/800,80refits,seed45,4000predictive draws; declared iid_observation_row and real locked worker.
**Действие:** Source-bound fit→full-row resamples→actual gcm.fit каждого replica→interval→fresh validate_persisted_estimator_interval. Instrument actual fit count/indices без подмены fits.
**Oracle:** Все requested replicas реально refitted, aligned rows сохранены. Existing width ratio .45<ratio<.95 и predictive span ratio .8<ratio<1.2; полные результаты/denominators сохранены. Это finite synthetic qualification, не гарантированная real-data coverage.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py:491–527; workers/dowhy-014/worker.py`.
**Doubles:** Synthetic data разрешены; selected worker, resampling, fitter и validator не заменять записанными arrays. Full-worker reexecution один согласованный qualification job.

### TEST-SCM-02-09 · native refit negative/target binding
**NOT_RUN. REQ:** REQ-SCM-02-07, REQ-SCM-02-08.
**Setup:** Conditional individual query, missing iid declaration, manual/native_hybrid SCM, replicas19/501; genuine supported interval с altered target/indices/source/mechanisms.
**Действие:** Запросить interval и перечитать tampered persisted interval при новом корректном payload hash.
**Oracle:** Unsupported estimand/unit/profile/count отказаны до дорогого refit; замены содержательных bindings отвергнуты. Valid interventional/attribution profile remains useful; posterior/ITE range не переименован estimator CI ради завершения job.
**Место:** `gcm_query.py::_refit_bootstrap_interval/validate_persisted_estimator_interval`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_scm_02.py tests/unit/foundry/methods/catalog/causal/test_gcm_query.py
# Подготовленная selected-worker среда: python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py; refit cases отдельным ресурсным слотом.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-C**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

SCM-02 — единственный writer conditional-row/PSD и owner actual source-bound refit qualification. SCM-03 владеет common closure/prepared-plan API/canonical stream coordinates, SCM-01 — twin consumer и native selected fit→query acceptance. Shared gcm_query.py/twin файл редактируется одним writer совместно с SCM-01/03. Worker fit owner общий с SCM-01; no duplicate bootstrap pipeline или store.

- **SCM-01:** Оригинальный predecessor; shared carrier/predictor и twin relevance closure сохраняют joint evidence dependencies.
- **SCM-03:** SCM-03 — единственный writer common closure/prepared-plan API и canonical stream coordinates; inference/refit qualification остаётся SCM-02.
- **GRF-03:** Static declared DAG/source disposition для selected fit; temporal/partial support отдельно.

## 8. Совместимость, миграция и возврат

Small-scale posterior и conditional empirical result намеренно меняются с ошибочных deterministic/unconditional на declared conditional law. Сохранять historical bytes и явный computational profile/seed provenance; если replay draws изменились, не обещать bitwise historical reproduction. Current typed arms/legacy normalization сохраняются. Unsupported profile ограничивается адресно, а не блокирует все partial SCM.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общие dimensionless posterior и joint-row mechanisms работают для новых compatible models без branches по именам узлов; positive conditional case обязателен.
- [wave5-evidence-substitution-ratification.md — K01/K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Ни source hash, ни fixed-model distribution не заменяют scientific estimator evidence; полезный conditional result сохраняется отдельно.

## 10. Конечные решения и сдача

### DEC-SCM-02-PSD
**Вопрос:** Какое нормированное factor representation сохраняет current public covariance contract и exact factual controls?
**Кто решает:** SCM-02 — conditional-row/PSD writer с независимым numerical reviewer.
**Конечное действие/выход:** Сравнить standardized-noise SVD factor с существующим covariance path на analytic2node, singular/full-factual и rescaled fixtures. Выбрать одно внутреннее representation с задокументированным epsilon/rank criterion, не внешний новый API.
**До решения:** Никакого absolute covariance cutoff или artificial jitter; positive represented law сохраняется.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.


## v2: дополнительная различающая проверка (PROPOSED, не выполнена)

Основание: финальное technical/capability review `CS-005`. Исходные source/residual/preservation mappings сохраняются; это дополнительное условие приёмки, не утверждение исправленного продукта.

### TEST-SCM-02-10 · selected worker per-replica independent linear target and percentile oracle

**Требования:** REQ-SCM-02-07, REQ-SCM-02-08. **Статус:** NOT_RUN.

**Setup:** Linear A→Y source rows A=(-3,-2,-1,0,1,2,3,4), Y=1+2A+r, r=(1,-1,0,1,-1,0,1,-1); declared iid_observation_row,80refits,seed45, selected actual worker. Persist exact bootstrap row indices; no filtering failed replicas. Queries E[Y|do(A=2)] and attribution do2 vs do−1.

**Действие:** Для каждого actual resampled row corpus independent scalar sums дают beta1=sum((a−abar)(y−ybar))/sum((a−abar)²), beta0=ybar−beta1*abar. Reference intervention mean=beta0+2beta1; attribution=3beta1. Test не вызывает product target/interval helper. Sort replica estimates; q linear interpolation uses j=(R−1)q, lower=floor(j),fraction=j−lower, q=.025/.975. Compare every point and endpoints to persisted actual result/fresh validator.

**Oracle:** Все80 source-bound replica targets agree with independent sums within declared OLS tolerance; endpoints agree with explicit linear quantile convention. Reverse arms negates attribution and reverses interval. Constant target offset/scale, shuffled source-index pairing and wrong quantile convention mutants fail. Source rank failures recorded, not resampled until success; no blanket width monotonicity/coverage claim.

**Ожидается:** Positive actual refit numerical qualification + negative target/quantile mutants; NOT_RUN.

**Owner:** gcm_query.py::_refit_target_estimate/_refit_interval_from_models/validate_persisted_estimator_interval; tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py

**Doubles/запреты:** Independent test-only scalar sum oracle and observer allowed; actual selected worker full-row refits/CAS/fresh readback mandatory. No mock fit/no product target helper as oracle.

**Evidence:** Complete replica index/target corpus and accepted/failed denominator; actual worker inventory, independent formulas/quantile convention. Width shrink and predictive range tests retained separately.

**Дополнение REQ→TEST:** REQ-SCM-02-07 → TEST-SCM-02-10; REQ-SCM-02-08 → TEST-SCM-02-10. Existing TEST и historical evidence не удаляются.
