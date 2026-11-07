# FIT-01 — Квалификация fit reuse и реального ограничения работы без потери folds

**Исполнительская спецификация; содержательный review формата пройден. LANE-05 · CP4.** Все проверки ниже — **NOT_RUN**; документ не является исполнением ремонта. Основание: `20d9009be21097bfbdc38a546a15cc60213b8ace`. Именной исполнитель и reviewer назначаются проектом, не выдумываются этим комплектом.

## 1. Цель, основания и область

Сдать уже существующий content-bound fit-core/current-view путь через настоящий worker pool и persisted consumer; измерить композицию ресурса. Не переписывать работающий cache и не восстанавливать старый nested pool ради буквального исходного решения.

**Тип работы:** Preserve/qualify-only по текущему аудиту: подтверждённых R нет. Продуктовый код меняется только при воспроизведённом нарушении ниже либо отдельно принятой оптимизации после измерений.

**Исходные ID:** B54, B56. [Полный аудит](../05_Основания/Аудит/02_Пакеты/FIT-01.md), [остатки C60](../05_Основания/Аудит/01_Реестры/C60_остатки.json), [исходная карточка](../05_Основания/Аудит/05_Источники/FIT-01_исходные_строки.txt), [pinned source index](../05_Основания/Аудит/05_Источники/C60_источники.json), [машинная трассировка](../04_Трассировка/FIT-01.json). Полные probes/logs — в отдельно переданном неизменном ZIP фазы 1.

Действуют [общие правила исполнения и приёмки](../00_Общее/Правила_исполнения_и_приёмки.md). При отличающемся HEAD сначала сверить owners и фактическую семантику, а не восстанавливать прежний дефект ради старого reproduction.

## 2. Сохранить полезное и учесть исходные требования

- `preserve:0168`: Immutable fit-core/current reader separation. Проверки: `TEST-FIT-01-01`.
- `preserve:0169`: Full content-bound data/fit identity even with explicit caller label. Проверки: `TEST-FIT-01-02`.
- `preserve:0170`: Readonly bytes and reader-owned metadata. Проверки: `TEST-FIT-01-03`.
- `preserve:0171`: Controlled precomputed resolution. Проверки: `TEST-FIT-01-04`.
- `preserve:0172`: All folds/repeats/seeds and explicit serial-inner policy. Проверки: `TEST-FIT-01-05`, `TEST-FIT-01-06`.

**Исходная матрица:** B54 — уже исправленная core/view identity, REQ-01–04 плюс реальный current consumer REQ-08; B56 — уже существующая serial-inner policy, REQ-05/06 плюс измеряемое решение REQ-07. Не считать настройку максимального числа workers самоцелью. Связанных LK/S в исходной карточке нет; отсутствие нового R не отменяет native qualification.

## 3. Полный остаток и disposition

| Остаток | Действие | Требования и владелец |
|---|---|---|
| `C60-G01` | qualify: Все основные механизмы уже есть; требуется actual supported pool/report/CAS qualification, а не второй scheduler. | REQ-FIT-01-01, REQ-FIT-01-02, REQ-FIT-01-03, REQ-FIT-01-04, REQ-FIT-01-05, REQ-FIT-01-06, REQ-FIT-01-08 |
| `C60-G02` | qualify: Измерение ресурса и отдельная научная квалификация; inner fan-out только по обоснованному решению. | REQ-FIT-01-05, REQ-FIT-01-07, REQ-FIT-01-08 |

Все строки source-registry remaining связаны в companion JSON: `remaining:0119`, `remaining:0120`. Это отдельная проверка полноты, не дополнительные независимые дефекты.

## 4. Нормативные требования

### REQ-FIT-01-01
При неизменных X/T/Y и fitting contract изменение только diagnostic policy (в частности min_effective_sample_size 48→100 и coverage_guard ess_aware→off) должно повторно использовать fit identity и predictions без нового fit, но вернуть отдельный reader с текущим contract и актуальной diagnostics. Старый выданный reader не изменяется.
Основание: B54; C60-G01. Проверка: `TEST-FIT-01-01`.

### REQ-FIT-01-02
Изменение X, T, Y, fitting seed/split/model/fitting-параметра должно изменить fit identity и вызвать требуемый refit даже при одинаковом __shared_nuisance_key. Для каждого поля фактического ATENuisanceContract должен быть явный fit либо current-view эффект; новый field не может молча выпадать из этой классификации.
Основание: B54; C60-G01. Проверка: `TEST-FIT-01-02`.

### REQ-FIT-01-03
Попытка потребителя изменить массив, его shape/metadata либо вложенные scaler/manifests не должна изменять последующий cache hit. Общие числовые данные остаются read-only на immutable backing; отдельная разрешённая рабочая копия не может заменить cached core.
Основание: B54; C60-G01. Проверка: `TEST-FIT-01-01`, `TEST-FIT-01-03`.

### REQ-FIT-01-04
Offered precomputed bundle допускается только при совпадении вычисленной текущей fit identity и наличии соответствующего controlled core. Predictions/metadata самого предложенного объекта не принимаются как основание; mismatch/неизвестная identity дают точный отказ без загрязнения cache.
Основание: B54; C60-G01. Проверка: `TEST-FIT-01-04`.

### REQ-FIT-01-05
Независимо от requested parallel_folds/max_parallel_folds текущая serial-inner политика должна выполнять весь набор repeats×folds и детерминированные seeds в согласованном порядке. Effective workers=1 и serial_folds_within_admitted_job должны отражать фактическое исполнение, а не requested flags. Сокращать repeats ради ресурсного cap запрещено.
Основание: B56; C60-G01, C60-G02. Проверка: `TEST-FIT-01-05`, `TEST-FIT-01-06`.

### REQ-FIT-01-06
При actual LocalWorkerPool budget=1 и 2 допущенная внешняя работа не превышает capacity, ожидающие studies сохраняются, завершение/ошибка освобождает slot. Результат успешной study должен пройти node dispatch, parent receipt/trace, запись CAS и свежего reader; failure одной study не теряет ожидающий корректный sibling.
Основание: B56, B54; C60-G01. Проверка: `TEST-FIT-01-06`.

### REQ-FIT-01-07
Для решения о ресурсе предъявить воспроизводимую таблицу одинакового workload: serial baseline и actual outer budgets 1/2, число scientific tasks, wall time, peak RSS, queue wait и peak active work с оговорённой единицей измерения. По измерениям сохранить serial-inner либо отдельно обосновать bounded transferable admission; отсутствие ускорения не устранять урезанием scientific plan или выдачей неподтверждённого SLA.
Основание: B56; C60-G02. Проверка: `TEST-FIT-01-07`.

### REQ-FIT-01-08
Текущий diagnostic contract должен достигать actual TMLEEstimator result/report projection после cache hit, а допустимый conditional estimate сохраняться. Candidate/gate_eligible=False и consumer_asserted basis не повышаются cache identity или успешным fit. Неподдержанный inference профиль не получает выдуманный interval. Scientific coverage на известном DGP и empirical применимость указываются отдельно.
Основание: B54, B56; C60-G01, C60-G02. Проверка: `TEST-FIT-01-08`, `TEST-FIT-01-09`.

## 5. Предлагаемое техническое решение

1. **Сначала квалифицировать, не переделывать.** В `tmle_core.py` уже есть `_ATENuisanceFitCore.from_bundle/materialize`, immutable bytes `_readonly_array`, полный `_fit_identity`, controlled precomputed lookup и serial fold loop. Существующий механизм отвечает исходной цели B54/B56 лучше буквального восстановления прежнего nested ThreadPoolExecutor.
2. Запустить существующие native tests на закреплённом Python3.14/backend с реальными imports. Instrumentation только оборачивает настоящий `_fit_crossfit_fold`, не подменяет models готовыми predictions. Сверять полный current contract field denominator; если появляется новое fitting поле, добавить его в fitting fingerprint и field-classification тест вместе. Диагностическое поле не включать в expensive key только ради устранения stale view: current policy связывается при `materialize`.
3. **Producer→consumer:** actual `TMLEEstimator.pure_step` → `fit_tmle_ate`/nuisance core → current `result_payload` и causal report → real StudyNode/LocalWorkerPool → parent output+trace → CAS → fresh reader. Имеющийся native test сохраняет descriptive result; расширение для REQ-08 должно также проверить actual causal report/envelope, а не считать descriptive JSON полной projection acceptance.
4. Scientific task list определяется repeats/folds/seeds, ресурс — допуском выполнения. Оставить один уровень параллельности как текущий baseline. Monetary reservation в budget_middleware не является fold permit: не связывать `max_parallel_folds` с денежным остатком и не импортировать Scientist scheduler внутрь Foundry в обход слоёв.
5. При доказанной потребности inner parallelism варианты: (а) оставить outer parallelism и serial folds; (б) расширить существующий ресурсный контракт transferable/subordinate capacity с одним owner, не удерживая исчерпанный parent permit во время ожидания child. Второй вариант требует отдельного design review зависимых owners и failure/deadlock теста. До измерений предпочтителен (а); это конечное решение, не обязательная новая архитектура.
6. Никакой новой схемы CAS/cache или переписывания исторических outputs для этой квалификации не требуется. Если native запуск обнаружит реальный mismatch, устранить его у canonical owner с новым различающим regression и повторить только affected tests/shared variants.

### Проверенные текущие места

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py:244–351](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L244-L351)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py:746–819](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L746-L819)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py:878–1048](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L878-L1048)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py:378–524](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py#L378-L524)
- [policy-engine/src/polisyos/scientist/orchestration/engine/runner/local_pool.py:117–206](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/local_pool.py#L117-L206)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py:377–747](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py#L377-L747)

## 6. Проверки и точные критерии

Каждый TEST-ID ниже — требуемая проверка, не утверждение, что в репозитории уже существует одноимённый test. Указанные существующие файлы/символы — места расширения и повторного использования. Старый ограниченный audit MATCH не заменяет новый native результат.

### TEST-FIT-01-01 · native numerical cache/current-view
**Требования:** REQ-FIT-01-01, REQ-FIT-01-03. **Состояние:** NOT_RUN.
**Setup:** Расширить existing test_native_cold_warm_rebind_and_reader_isolation с настоящими моделями и фиксированными входами; минимум 3 folds×2 repeats. Холодный contract threshold48/ess_aware, затем threshold100/off на том же X/T/Y.
**Действие:** Инструментировать _fit_crossfit_fold обёрткой, вызывающей original; прочитать cold/current reader, result_payload, затем повторный hit.
**Oracle:** Fit identity, predictions и число fold calls не меняются на diagnostic-only hit; diagnostics показывают 100/off. Старый reader показывает 48/ess_aware и не мутирован. При удалении current materialize/замене cached shared object тест должен падать.
**Ожидаемый класс:** Положительный cache hit и различающий stale-contract removal.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-FIT-01-02 · native field-complete contract matrix
**Требования:** REQ-FIT-01-02. **Состояние:** NOT_RUN.
**Setup:** Использовать существующие _FIT_CHANGES/_VIEW_CHANGES и test_all_contract_axes_by_actual_native_fit_calls; перед запуском сверить полный set dataclass fields, на основании аудита 32=17+15, не hardcode старое число после изменения схемы.
**Действие:** По одному изменить X/T/Y, seed/folds/model/split при одинаковом caller label и все contract axes.
**Oracle:** Fit-поля действительно добавляют ожидаемые fold calls и меняют identity; current-view поля не переобучают, но доходят до current contract. Полный набор полей покрыт без пропусков/пересечений; математический смысл classification объяснён для новых полей.
**Ожидаемый класс:** Положительный reuse и отрицательные same-label invalidations.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-FIT-01-03 · native ownership mutation
**Требования:** REQ-FIT-01-03. **Состояние:** NOT_RUN.
**Setup:** Получить cold/current/third reader одного fit. Четыре массива propensity,mu1,mu0,trim_mask плюс вложенные selection/split manifests и scaler.
**Действие:** Попытаться сделать массив writeable, изменить shape доступного view, изменить вложенные metadata одного reader; снова получить hit.
**Oracle:** Writeability backing не повышается; последующий hit сохраняет исходные values/shape/metadata. Разрешённая reader-local metadata мутация не протекает. Проверка только frozen dataclass или одного top-level dict недостаточна.
**Ожидаемый класс:** Отрицательный mutation и положительное повторное чтение.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-FIT-01-04 · native precomputed resolution
**Требования:** REQ-FIT-01-04. **Состояние:** NOT_RUN.
**Setup:** Controlled fit известной identity; offered bundle с тем же label, но подменённым mu1=900; отдельные changed-data, missing/unknown identity варианты.
**Действие:** Вызвать fit_crossfit_nuisance_bundle с __shared_nuisance_bundle.
**Oracle:** Для genuine issued identity возвращаются predictions controlled core, не offered 900. Mismatch/unknown identity адресно отвергаются, cache и следующий обычный hit не изменены.
**Ожидаемый класс:** Положительный controlled reuse + отрицательная подмена.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-FIT-01-05 · native numerical execution policy
**Требования:** REQ-FIT-01-05. **Состояние:** NOT_RUN.
**Setup:** Один неизменный tiny actual fit,3folds×2repeats, фиксированный seed manifest; serial baseline и requested parallel/maxcap0/1/2.
**Действие:** Посчитать actual (repeat seed,fold id,test indices) и выполнить все модели.
**Oracle:** Ровно шесть соответствующих задач на fit, одинаковый набор splits/seeds и predictions/EIF/ATE/CI в одном backend profile; effective workers=1, current requested flags видимы. При иной численной BLAS среде заранее определить и обосновать tolerance, не подгонять её после результата.
**Ожидаемый класс:** Положительные все requested profiles; task truncation mutation должна провалить контроль.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-FIT-01-06 · native worker/CAS lifecycle E02-I05-C: FIT branch
**Требования:** REQ-FIT-01-05, REQ-FIT-01-06. **Состояние:** NOT_RUN.
**Setup:** Существующие test_native_studies_wait_in_actual_worker_pool_without_nested_fold_fanout и test_failed_native_study_releases_shared_pool_slot_for_waiting_study. Четыре studies, каждая3folds×2repeats, actual LocalWorkerPool budgets1/2 и real CAS.
**Действие:** Barrier на первом real fold создаёт overlap; получить capacity до release, затем результаты/parent traces и fresh reader. Отдельно инъецировать одну controlled failure, сохранив настоящий waiting sibling.
**Oracle:** До release active_tasks=budget, queue_depth=4-budget; peak active folds≤budget, все24folds в успешном варианте. Каждая successful study имеет полный held-out partition, parent output ref и один lifecycle event каждого ожидаемого типа. Failed study освобождает slot; sibling завершается и читается из CAS.
**Ожидаемый класс:** Положительный полезный результат, очередь и отрицательный failure release.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Тестовый StudyNode, данные, barrier и failure injection допустимы; fold wrapper зовёт native. Запрещена замена LocalWorkerPool, parent contract, модели, serializer/CAS и reader. Данный TMLE branch не объявляется исполнением selected SCM/DoWhy.

### TEST-FIT-01-07 · bounded benchmark/decision, not universal SLO
**Требования:** REQ-FIT-01-07. **Состояние:** NOT_RUN.
**Setup:** Один заранее сохранённый representative finite workload и тот же tiny контроль; фиксировать backend, CPU/RAM, BLAS/OMP, seeds, cache cold/warm режим отдельно. Не смешивать кэшированный hit с cold training.
**Действие:** Измерить serial baseline и outer budgets1/2 с одинаковым общим набором studies, warm-up отдельно; сохранить исходные samples, а не один лучший запуск.
**Oracle:** Во всех вариантах сохраняются task count/splits/results; таблица содержит wall/RSS/wait/active work и границы измерения. Вывод выбирает существующий безопасный профиль либо обосновывает отдельную оптимизацию. Нет выдуманного порога ускорения и вывода о OS threads из одного fold counter.
**Ожидаемый класс:** Исследование с конечным выходом DEC-FIT-01-RESOURCE; само по себе не требует менять код.
**Место:** `tmle_core.py::_fit_crossfit_nuisance_bundle_uncached; runner/local_pool.py::LocalWorkerPool`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-FIT-01-08 · native actual method/report/consumer
**Требования:** REQ-FIT-01-08. **Состояние:** NOT_RUN.
**Setup:** TMLEEstimator.pure_step на тех же source-bound X/T/Y до/после diagnostic-only hit; actual CausalEffectReport/envelope и persisted payload. Добавить как вариант существующего native pool suite, не второй CAS harness.
**Действие:** Сохранить result и report, прочитать свежим reader; сверить текущую threshold/policy и честные ограничения; отдельно unsupported inference_profile=clustered/unknown.
**Oracle:** Численный candidate сохраняется где допустим; current diagnostics не stale; unsupported profile не выдаёт interval. Никакой gate authority не появляется от shared key/currentness/fit SUCCESS.
**Ожидаемый класс:** Положительный current payload и отрицательное повышение/unsupported interval.
**Место:** `src/polisyos/foundry/methods/catalog/causal/treatment_effects.py::TMLEEstimator.pure_step; tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-FIT-01-09 · bounded scientific qualification
**Требования:** REQ-FIT-01-08. **Состояние:** NOT_RUN.
**Setup:** Существующий test_regular_iid_native_binary_dgp_coverage_pilot:120 предзаданных seeds1000..1119,n1000,analytic ATE0.3, поддержанный binary iid профиль; без выбора seeds после результата.
**Действие:** В отдельном scientific qualification окне запустить существующий pilot и unsupported profiles; сохранить covered/120, exact binomial interval/pvalue и mean error.
**Oracle:** Существующие критерии pilot: binomtest p>0.01 и |mean_error|<0.02; это конечная проверка указанного DGP, не population coverage реального кейса. Неуспех не скрывается новым seed/tolerance. Реальные assumptions/positivity/independence требуют отдельного основания; его отсутствие обозначается, не фабрикуется.
**Ожидаемый класс:** Положительная known-law квалификация и отрицательная граница; не blocker для честно отдельно сданного cache repair.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### Команды: адаптируемый шаблон, не журнал выполненного запуска

В уже подготовленной поддержанной среде Python3.14 с закреплёнными test/analytics/backend зависимостями, из `policy-engine/`. Этот документ не разрешает автоматически устанавливать зависимости. Сначала проверить интерпретатор и imports; missing dependency фиксируется BLOCKED, не product FAIL.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_fit_01.py
python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py -k "not regular_iid_native_binary_dgp_coverage_pilot"
# Отдельное scientific qualification окно, не повторять после каждой правки документа:
python -m pytest -q -s tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py::test_regular_iid_native_binary_dgp_coverage_pilot
```

Ruff/затронутые import/architecture проверки выбрать по реальному patch согласно CONTRIBUTING; полный backend suite после каждого пакета не требуется. Численный job занимает согласованный native slot, без конкурентного тяжёлого тестирования.

## 7. Общая интеграция, зависимости и ownership

Переиспользовать **E02-I05-C** в [каноническом контракте LANE-05](../03_Интеграция/LANE-05.md). Общая инфраструктура и свидетельство не копируются в отдельный packet harness. Local TEST связываются с exact variant этого сценария; чужие variants не считаются выполненными автоматически.

FIT-01 — отдельная TMLE/cache/resource ветка E02-I05-C. Она не доказывает selected DoWhy/SCM query/twin, а те ветки не заменяют её worker/current-diagnostic проверку. CP4 для FIT-01 сохраняется; не вводить новый глобальный CP5 барьер.

- **LANE-06:** Переиспользовать actual worker lifecycle/receipt/CAS; найденные дефекты admission направлять владельцам, не дублировать scheduler.
- **SCM-01/SCM-02/SCM-03:** Совместное окно E02-I05-C, но TMLE nuisance cache не объявлять SCM fit/twin backend. Независимые branches сохраняют собственные oracles.

Правку общего файла принимает один назначенный writer. Читающие/тестовые companion пакеты согласуют контракт и повторно используют тот же frozen input/backend result. Порядок: локальный distinguishing control → адресный repair либо подтверждение existing behavior → focused tests → затронутый общий variant после стабилизации owners.

## 8. Совместимость и возврат

Сохранить существующие params и честное разделение requested/effective parallel flags. Менять публичный contract/schema только при установленной необходимости; текущий repair не требует миграции persisted evidence. При новом fitting algorithm/version нельзя принимать старый core под прежней вычисленной identity. Исторические artifacts остаются неизменными, текущая diagnostic policy материализуется в новом результате. Rollback оптимизации возвращает квалифицированную serial-inner policy, не сокращает scientific repeats и не возвращает общие mutable readers.

## 9. Free-grow и design alignment

- [universal-policy-design-target-architecture-and-gap.md — D0 Operational Definition Of Universality, lines559–617](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общность механизма и честная область; не абсолютное отсутствие нового кода. Один content-bound fit-core/current-view механизм служит разным данным и diagnostic contracts, не новая cache ветка на исследование.
- [policy-design-execution-topology.md — lines143–159: deterministic applicability versus semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md): Механически проверяемая применимость не доказывает оптимальность метода или эмпирические предпосылки. Корректность reuse и resource admission не доказывает scientific inference; current diagnostics сохраняют ограниченную роль.

Документация задаёт цель и существенные различения, не требует нового универсального framework. В этом локальном пакете не нужен искусственный второй предметный домен: параметризованные содержательно различающиеся inputs проверяют общность действующего механизма. LLM может предложить постановку/профиль, но не подменяет partition, measured execution или независимое основание научного claim.

## 10. Конечные решения и сдача

### DEC-FIT-01-RESOURCE
**Вопрос:** Даёт ли новая внутренняя параллельность полезный выигрыш на заявленном workload?
**Владелец решения:** Владельцы tmle_core и существующего LocalWorkerPool; технический reviewer.
**Ограниченное действие/выход:** Сдать TEST-07 таблицу cold/warm отдельно, сравнить одинаковый scientific plan и memory/wait cost. Выбрать сохранение serial-inner либо отдельное расширение admission с показанным отсутствием cyclic wait.
**Без нового решения:** Serial folds inside admitted job; это допустимый результат, не незавершённый обязательный fan-out.

### DEC-FIT-01-SCIENTIFIC
**Вопрос:** Для какого реального inference profile заявляется применимость?
**Владелец решения:** Владелец scientific use case.
**Ограниченное действие/выход:** Назвать independence/positivity/outcome basis и реальный consumer; synthetic binary pilot не переносить на неизвестный профиль. При отсутствии оснований сохранить conditional candidate и ограничение.
**Без нового решения:** Квалификация механизма не создаёт эмпирической или институциональной authority.

Предъявить: patch/base/head и rationale, exact REQ→TEST→shared variant, исходные inputs и их идентичности, команды/exit/log, значения независимых oracles, positive/negative/removal controls, сохранённые инварианты, compatibility/remaining decisions. Не скрывать FAIL/UNRUN. Можно отдельно принять адресный механизм и оставить явно названную scientific/историческую квалификацию открытой; нельзя назвать это полной эмпирической или институциональной готовностью.
