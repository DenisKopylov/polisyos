# CAU-01 — Standard DiD: полное разбиение по единицам и честная неопределённость

**Исполнительская спецификация; содержательный review формата пройден. LANE-05 · CP5.** Все проверки ниже — **NOT_RUN**; документ не является исполнением ремонта. Основание: `20d9009be21097bfbdc38a546a15cc60213b8ace`. Именной исполнитель и reviewer назначаются проектом, не выдумываются этим комплектом.

## 1. Цель, основания и область

Исправить потерю score у недопустимой cluster identity, не потеряв уже действующие DiD/CR0/CI и выделенные wrappers. Квалифицировать реальный маршрут результата и не превращать численный SUCCESS в causal authority.

**Тип работы:** Адресный ремонт C52-R01; сохранение уже выполненных B204/B206 и большей части B205/LA-016; native/научная квалификация; общий migration closeout у CAU-05.

**Исходные ID:** B204, B205, B206, LA-016. [Полный аудит](../05_Основания/Аудит/02_Пакеты/CAU-01.md), [остатки C52](../05_Основания/Аудит/01_Реестры/C52_остатки.json), [исходная карточка](../05_Основания/Аудит/05_Источники/CAU-01_исходные_строки.txt), [pinned source index](../05_Основания/Аудит/05_Источники/C52_источники.json), [машинная трассировка](../04_Трассировка/CAU-01.json). Полные probes/logs — в отдельно переданном неизменном ZIP фазы 1.

Действуют [общие правила исполнения и приёмки](../00_Общее/Правила_исполнения_и_приёмки.md). При отличающемся HEAD сначала сверить owners и фактическую семантику, а не восстанавливать прежний дефект ради старого reproduction.

## 2. Сохранить полезное и учесть исходные требования

- `preserve:0519`: Общий panel допускает t0=0, standard boundary отказывает. Проверки: `TEST-CAU-01-03`.
- `preserve:0520`: Known ATT и actual uncorrected unit-cluster CR0. Проверки: `TEST-CAU-01-02`, `TEST-CAU-01-03`.
- `preserve:0521`: Unit permutation/technical repetition invariance для корректных labels. Проверки: `TEST-CAU-01-02`.
- `preserve:0522`: Normal critical value по confidence_level в DiD и RDD. Проверки: `TEST-CAU-01-04`.
- `preserve:0523`: Independent metadata constants/copies и old-slot adapter. Проверки: `TEST-CAU-01-05`.
- `preserve:0524`: Non-authoritative pretrend diagnostics и non-gating report projection. Проверки: `TEST-CAU-01-03`, `TEST-CAU-01-06`, `TEST-CAU-01-08`.

**Исходная матрица:** B204 — уже существующий standard-only precondition и честные diagnostics, сохранить/квалифицировать REQ-03/04; B205 — действующие HC1/CR0 сохраняются, ремонт partition REQ-01/02 и квалификация REQ-05; B206 — существующий quantile обоих callers; REQ-06 дополнен source-backed phase2 boundary qualification/repair для extreme levels, это не новый ретроспективный audit R; LA-016 — metadata separation уже есть, REQ-07 и общий closeout CAU-05. **LK05:** защищённый настоящий `causal/id_engine/` package не входит в удаление/ремонт; исчезновение пустого sibling не разрешает удалить package. Новые S-направления этим локальным пакетом не назначаются.

## 3. Полный остаток и disposition

| Остаток | Действие | Требования и владелец |
|---|---|---|
| `C52-R01` | fix: Исправляется потеря кластерного score, а не вся covariance заново. | REQ-CAU-01-01, REQ-CAU-01-02, REQ-CAU-01-05 |
| `C52-G01` | qualify: Настоящие поддержанные imports/numeric references/registry/CAS и consumers. | REQ-CAU-01-03, REQ-CAU-01-04, REQ-CAU-01-05, REQ-CAU-01-06, REQ-CAU-01-07, REQ-CAU-01-08 |
| `C52-G02` | qualify: Разделены численная корректность, применимость asymptotics и causal authority; никакой новой гарантии из малого fixture. | REQ-CAU-01-04, REQ-CAU-01-05, REQ-CAU-01-09 |
| `C52-G03` | shared: Metadata сохранена; staggered проверяет CAU-02, final planning/FQN lifecycle — CAU-05. | REQ-CAU-01-07; shared owner **CAU-05** |

Все строки source-registry remaining связаны в companion JSON: `remaining:0323`, `remaining:0324`, `remaining:0325`, `remaining:0326`. Это отдельная проверка полноты, не дополнительные независимые дефекты.

## 4. Нормативные требования

### REQ-CAU-01-01
При unit-cluster covariance идентификатор отсутствующего или нерефлексивного значения (NaN, None/эквивалент missing, NaT) должен отклоняться на границе кластеризации до расчёта covariance. Публичный StandardDifferenceInDifferences возвращает INPUT_INVALID, точную причину и не выдаёт point/SE/CI; общий PanelObservationalData и допустимый HC1 не ужесточаются этим правилом. Нормальные конечные числовые и строковые labels остаются допустимыми.
Основание: B205; C52-R01. Проверка: `TEST-CAU-01-01`.

### REQ-CAU-01-02
Для каждого принятого unit-cluster запроса все n_units×n_periods observations должны иметь ровно одну группу, постоянную внутри единицы; фактически использованное число групп равно n_units и reported n_clusters. Score каждой группы участвует ровно один раз, включая нулевой score. Не допускаются пропуск rows, dedupe единиц или переименование HC1 в CR0.
Основание: B205; C52-R01. Проверка: `TEST-CAU-01-01`, `TEST-CAU-01-02`.

### REQ-CAU-01-03
Standard DiD при t0=0 либо отсутствии treated/control должен возвращать существующий адресный INPUT_INVALID без эффекта; корректная панель с pre/post и обоими режимами должна сохранять оценимый ATT. Общая модель панели продолжает представлять t0=0 для иных методов.
Основание: B204; C52-G01. Проверка: `TEST-CAU-01-03`.

### REQ-CAU-01-04
Предтрендовая диагностика должна сохранять разные not_testable, no_detected_pretrend и evidence_of_violation; недостаточные pre-periods и неотвержение не дают identifying authority. Report/envelope после сохранения сохраняют parallel_trends_identified=False и non-gating роль, даже при численном SUCCESS.
Основание: B204, B205, B206; C52-G02, C52-G01. Проверка: `TEST-CAU-01-03`, `TEST-CAU-01-07`, `TEST-CAU-01-08`.

### REQ-CAU-01-05
Выбранный HC1 или unit-cluster CR0 должен реально определять covariance и effective method_params. Для CR0 техническое повторение периодов и перестановка единиц не меняют SE/ATT в пределах заранее заданной численной погрешности; неизвестные covariance/cluster specifications дают точный отказ. CR0 остаётся объявленно uncorrected, с large_independent_units и finite_cluster_guarantee=False.
Основание: B205; C52-R01, C52-G01, C52-G02. Проверка: `TEST-CAU-01-02`, `TEST-CAU-01-07`.

### REQ-CAU-01-06
В standard DiD и conventional RDD при неизменных point и положительном SE границы двухстороннего normal CI должны равняться point ± q×SE для уровня 0<level<1 при конечном положительном q. Верхний квантиль вычислять устойчиво через нижний tail, например q=−NormalDist.inv_cdf((1−level)/2), а не округляемую к1 сумму (1+level)/2. Если выбранная арифметика не представляет положительный q/конечные endpoints, выдавать адресный numerical-range отказ, не нулевой CI. Уровни 0.80/0.95/0.99 изменяют ширину в правильном порядке; nonfinite/внеинтервальные уровни отклоняются до дорогой оценки. Это не заменяет covariance или RBC.
Основание: B206; C52-G01. Проверка: `TEST-CAU-01-04`.

### REQ-CAU-01-07
Независимые module metadata и dedicated classes сохраняются. На одинаковом standard effective request old-slot adapter и dedicated route дают равные полные reports/warnings после ремонта; изменение metadata deprecated wrapper не меняет dedicated metadata. CAU-01 не снимает legacy FQN, не удаляет did.py и не объявляет закрытие LA-016 без результатов CAU-02/CAU-05.
Основание: LA-016; C52-G03. Проверка: `TEST-CAU-01-05`.

### REQ-CAU-01-08
Через зарегистрированный standard method, actual dispatcher/Scientist job и CAS корректный report должен дойти до свежего reader с сохранёнными числом, covariance/level и диагностическим основанием. Подмена diagnostic window/result или согласованная подмена report+markers должна быть отвергнута реальным consumer относительно исходных входов.
Основание: B204, B205, B206, LA-016; C52-G01. Проверка: `TEST-CAU-01-06`.

### REQ-CAU-01-09
Перед заявлением пригодности inference для конкретного реального дизайна исполнитель должен представить отдельное заключение о единице независимости, parallel trends/anticipation и области normal/cluster приближения. При недостаточном основании сохраняется доступный кандидатный численный результат с ограничением, но finite-cluster/population coverage и causal identification не заявляются. Если нужен иной finite-cluster профиль, он оформляется как отдельное решение текущего estimator owner, а не скрытая замена CR0.
Основание: B204, B205, B206; C52-G02. Проверка: `TEST-CAU-01-07`, `TEST-CAU-01-08`.

## 5. Предлагаемое техническое решение

1. **Canonical owner — `did.py::_unit_cluster_ids` и `_ols_cluster_cr0`.** До `np.unique` явно проверить допустимость scalar labels. Предлагаемый узкий контракт: finite числовые и обычные строковые labels; missing/non-reflexive labels — `ValueError` с причиной, перехватываемый существующим `_run_standard_did`. Не преобразовывать все значения в строки: это склеит, например, `1` и `"1"` и изменит identity. Не добавлять глобальный запрет в `PanelObservationalData`.
2. После проверки уникальности units преобразовать labels в плотные integer group codes; сохранить порядок rows и unit membership. В helper на фактических codes проверить диапазон, длину и отсутствие отрицательного/missing кода; использовать `np.add.at`/эквивалентное накопление `X*residual[:,None]` по группам, затем `scores.T @ scores`. Это избегает `label == NaN` и не создаёт N×N матрицу. Можно сохранить цикл по группам, если он работает на проверенных integer codes и соблюдает тот же oracle. Общее число групп получить из **того же** нормализованного разбиения, не из отдельного перечня старых labels. Не удалять нулевые score-группы.
3. Нормализацию выполнить один раз на canonical boundary; private helper получает проверенные codes либо проверяет свой direct-call контракт. Полнота задаётся конструкцией inverse-index и проверкой count/shape, а не дорогой N×G матрицей membership. На supported homogeneous string/int labels должна сохраниться семантика. Смешанные/custom-object labels, для которых нет надёжного равенства/порядка, адресно отвергнуть; не вводить новую универсальную систему identity.
4. **Не переписывать рабочие ремонты.** `_run_standard_did`, `_normal_critical_value`, `_DID_*` constants и metadata copies уже существуют. Изменять их только при выявленном нарушении REQ; B206 имеет одного владельца CAU-01, а не второй код у RDD. `_common.py`/IR не требуют нового framework для этой правки.
5. Полная цепочка: `PanelObservationalData` → dedicated registered method → covariance/report helpers → `_wrap_did_output` → actual method job/CAS → fresh `_verify_selected_did_diagnostics` и report/envelope. Локальный reject не заменяет положительную цепочку. Не выдавать исправленный SE за доказательство parallel trends.

### Проверенные текущие места

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:197–265](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L197-L265)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:322–523](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L322-L523)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py:1014–1288](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L1014-L1288)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py:45–144](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py#L45-L144)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py:453–645](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L453-L645)
- [policy-engine/src/polisyos/ir/analytics/causal.py:541–705](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal.py#L541-L705)

## 6. Проверки и точные критерии

Каждый TEST-ID ниже — требуемая проверка, не утверждение, что в репозитории уже существует одноимённый test. Указанные существующие файлы/символы — места расширения и повторного использования. Старый ограниченный audit MATCH не заменяет новый native результат.

### TEST-CAU-01-01 · native unit/public method
**Требования:** REQ-CAU-01-01, REQ-CAU-01-02. **Состояние:** NOT_RUN.
**Setup:** Взять _panel из tests/unit/remediation/test_cau_01.py: четыре единицы×четыре периода, treatment=[1,1,0,0], t0=2. Параметризовать unit_ids и explicit per-unit/per-observation cluster_var: [NaN,1,2,3], missing/NaT и нормальные строки/int; отдельные duplicate и внутриединичный конфликт.
**Действие:** Вызвать StandardDifferenceInDifferences.pure_step с cov_type=cluster; сохранить typed report и счётчик вызовов _ols_cluster_cr0.
**Oracle:** Недопустимая identity: INPUT_INVALID, point/SE/CI отсутствуют, covariance helper не вызван. Допустимая: SUCCESS, 4 непустые группы покрывают 16 rows без повторов. На старом NaN дефекте данный отказ не выполняется; наблюдался ложный SUCCESS с SE≈0.5077524002897.
**Ожидаемый класс:** Отрицательный/граничный; положительный тот же panel с допустимыми labels.
**Место:** `tests/unit/remediation/test_cau_01.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-CAU-01-02 · native numerical + independent reference
**Требования:** REQ-CAU-01-02, REQ-CAU-01-05. **Состояние:** NOT_RUN.
**Setup:** Та же панель с допустимыми labels; NormalDist не используется для covariance. Независимый oracle строит unit pre/post changes, не вызывает _ols_cluster_cr0 и не копирует его masks. Дополнительно statsmodels OLS/cov_cluster(use_correction=False).
**Действие:** Сравнить HC1 и CR0, переставить units, повторить каждый период 2 и 10 раз с соответственно изменённым t0; проверить явные per-unit/per-observation labels.
**Oracle:** ATT=3.125; CR0-SE≈0.5659615711336; HC1-SE≈0.9042722672588 для исходной панели. Сравнение float64: atol=1e-10, rtol=1e-10 для этого конечного fixture. CR0-SE инвариантен повторению. Подстановка HC1 вместо CR0 должна провалить oracle.
**Ожидаемый класс:** Положительный, метаморфный и различающий removal-контроль.
**Место:** `tests/unit/remediation/test_cau_01.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-CAU-01-03 · native unit/registered method
**Требования:** REQ-CAU-01-03, REQ-CAU-01-04. **Состояние:** NOT_RUN.
**Setup:** Существующий known-ATT=3 panel из test_did.py и нулевой-pre вариант; fixtures диагностик с 1–2 pre-periods, нулевым и ненулевым детерминированным differential trend.
**Действие:** Вызвать существующий DTO и standard method; отдельно построить diagnostic report каждого профиля.
**Oracle:** DTO с t0=0 создаётся, standard report точечно отказывает без point; valid known ATT=3 достигает SUCCESS. Для 1–2 pre periods not_testable и passed=False; остальные diagnostic statuses различаются; identification_authority=False во всех случаях.
**Ожидаемый класс:** Положительный и отрицательный; не доказательство parallel trends реального мира.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_did.py; tests/unit/foundry/methods/catalog/causal/test_did_diagnostics_ownership.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-CAU-01-04 · native numerical two callers
**Требования:** REQ-CAU-01-06. **Состояние:** NOT_RUN.
**Setup:** Существующие _panel и _rdd из test_cau_01.py; positive SE; levels 0.80/0.95/0.99, math.nextafter(1.0,0.0), tiny positive math.nextafter(0.0,1.0) и [0,1,-0.1,1.1,NaN,±infinity].
**Действие:** Запустить standard DiD и conventional sharp RDD с одинаковыми остальными параметрами на каждом уровне.
**Oracle:** Point/SE неизменны; каждый endpoint соответствует независимому NormalDist oracle (atol/rtol=1e-10 на малых fixtures); width80<width95<width99. Nextafter(1,0) даёт конечный положительный q/CI по independent lower-tail oracle; tiny positive level при округлении tail к.5 и q к0 получает numerical-range отказ, не zero-width SUCCESS. Invalid level не даёт SUCCESS. Нельзя заменить conventional RDD на RBC для этого требования.
**Ожидаемый класс:** Положительный и граничный; 95% сохраняет действующую normal процедуру.
**Место:** `tests/unit/remediation/test_cau_01.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-CAU-01-05 · native API/compatibility
**Требования:** REQ-CAU-01-07. **Состояние:** NOT_RUN.
**Setup:** Один standard effective request в старых и новых slot names; независимые копии metadata.
**Действие:** Вызвать old adapter и StandardDifferenceInDifferences, затем изменить только старую metadata в изолированном test context и повторить dedicated call.
**Oracle:** Полные reports/warnings эквивалентны; dedicated assumptions/equations/citations не изменились. Старый generic route не регистрируется заново ради этого локального теста.
**Ожидаемый класс:** Положительная совместимость; отрицательная metadata coupling. Staggered и historical FQN replay — соседние владельцы.
**Место:** `tests/unit/remediation/test_cau_01.py; tests/unit/foundry/methods/catalog/causal/test_did_diagnostics_ownership.py`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-CAU-01-06 · native integration E02-I05-B
**Требования:** REQ-CAU-01-08. **Состояние:** NOT_RUN.
**Setup:** Расширить actual consumer suite test_did_diagnostic_consumer.py standard-вариантом с корректными cluster labels; real source artifact, MethodRegistry/JobSpec, _run_primary_causal_job, FileSystemCAS и новый процесс reader.
**Действие:** Получить и сохранить report через job; прочитать новым процессом; повторить window/result/coherent-forgery substitutions относительно исходного source.
**Oracle:** Корректные ATT/SE/CI/effective profile и complete diagnostics совпадают с TEST-02/04; actual verifier принимает неизменённый результат и отказывает каждой подмене. Target/marker equality одна не достаточна. Невалидный NaN запрос не получает успешный report по тому же dispatch route.
**Ожидаемый класс:** Положительный producer→consumer и различающие negative controls.
**Место:** `tests/unit/scientist/nodes/builtins/simulate/test_did_diagnostic_consumer.py`.
**Doubles:** Тестовый panel и контролируемые входы допустимы. Запрещено подменять registry, job, CAS, report validator или final consumer готовым ответом.

### TEST-CAU-01-07 · bounded scientific/profile review
**Требования:** REQ-CAU-01-04, REQ-CAU-01-05, REQ-CAU-01-09. **Состояние:** NOT_RUN.
**Setup:** Зафиксированный реально предлагаемый unit/row dependence profile; если реальных данных нет — явно известный synthetic panel и отдельный перечень непроверенных empirical assumptions.
**Действие:** Проследить effective covariance и report limitations; проверить, не используется ли техническое повторение rows как рост independent sample. Сравнить политику unsupported/small-cluster профилей с declared scope.
**Oracle:** Заключение перечисляет независимую единицу, предпосылки и границы; CR0/normal результат не назван finite-cluster guarantee. Неизвестность не стирается положительным p-value. Отсутствие реального дизайна явно оставляет empirical qualification NOT_ESTABLISHED, не блокируя локальный numerical repair.
**Ожидаемый класс:** Документированная область/ограничение; не новая выдуманная граница числа clusters.
**Место:** `did.py::_run_standard_did; ir/analytics/causal.py::CausalEffectReport`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### TEST-CAU-01-08 · native report projection
**Требования:** REQ-CAU-01-04, REQ-CAU-01-09. **Состояние:** NOT_RUN.
**Setup:** Численный SUCCESS с корректным исходным основанием и диагностический отказ/недостаточность.
**Действие:** Провести оба результата через actual CausalEffectReport.to_uncertainty_envelope и затронутый consumer.
**Oracle:** Число сохраняется там, где оно допустимо; gate_eligible не становится True только от SUCCESS, количества clusters или metadata. Никакой институциональный/эмпирический акт не фабрикуется.
**Ожидаемый класс:** Положительный условный результат + отрицательный authority control.
**Место:** `src/polisyos/ir/analytics/causal.py::CausalEffectReport.to_uncertainty_envelope`.
**Doubles:** Разрешена инструментирующая обёртка, сохраняющая настоящий расчёт. Запрещены success-shaped report, подмена estimator и fixture CAS для native приёмки.

### Команды: адаптируемый шаблон, не журнал выполненного запуска

В уже подготовленной поддержанной среде Python3.14 с закреплёнными test/analytics/backend зависимостями, из `policy-engine/`. Этот документ не разрешает автоматически устанавливать зависимости. Сначала проверить интерпретатор и imports; missing dependency фиксируется BLOCKED, не product FAIL.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_cau_01.py
python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_did.py tests/unit/foundry/methods/catalog/causal/test_did_diagnostics_ownership.py tests/unit/foundry/methods/catalog/causal/test_did_diagnostic_binding.py
python -m pytest -q tests/unit/scientist/nodes/builtins/simulate/test_did_diagnostic_consumer.py
```

Ruff/затронутые import/architecture проверки выбрать по реальному patch согласно CONTRIBUTING; полный backend suite после каждого пакета не требуется. Численный job занимает согласованный native slot, без конкурентного тяжёлого тестирования.

## 7. Общая интеграция, зависимости и ownership

Переиспользовать **E02-I05-B** в [каноническом контракте LANE-05](../03_Интеграция/LANE-05.md). Общая инфраструктура и свидетельство не копируются в отдельный packet harness. Local TEST связываются с exact variant этого сценария; чужие variants не считаются выполненными автоматически.

- **CAU-02:** Общий did.py и staggered phase LA-016; не независимая копия common inference.
- **CAU-03:** RDD consumer confidence-level общего B206; RBC/численная устойчивость остаются у CAU-03.
- **CAU-05:** Accountable LA-016 closure и historical FQN lifecycle; не блокирует локальный partition repair.
- **LANE-06:** Повторное использование действительных CAS/worker contracts без нового store.

Правку общего файла принимает один назначенный writer. Читающие/тестовые companion пакеты согласуют контракт и повторно используют тот же frozen input/backend result. Порядок: локальный distinguishing control → адресный repair либо подтверждение existing behavior → focused tests → затронутый общий variant после стабилизации owners.

## 8. Совместимость и возврат

Это намеренное изменение ранее ошибочно принимаемого missing-label входа; корректные string/int inputs и schema report остаются совместимы. Записать ошибку/ограничение в существующей release-поверхности, не менять старые сохранённые reports. Для исторического NaN-report можно квалифицировать его как старый результат с неверной covariance, но нельзя переписать его bytes под прежней identity. Rollback должен откатить код целостно; нельзя вернуть silent score loss как «совместимость». При регрессии ограничить только затронутый cluster профиль, сохранив явно допустимый HC1/кандидатный путь; миграция old FQN — CAU-05.

## 9. Free-grow и design alignment

- [universal-policy-design-target-architecture-and-gap.md — D0 Operational Definition Of Universality, lines559–617](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общность механизма и честная область; не абсолютное отсутствие нового кода. Общий unit-cluster admission работает для разных labels/panels без ветки по имени предметной области.
- [policy-design-execution-topology.md — lines143–159: deterministic applicability versus semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md): Механически проверяемая применимость не доказывает оптимальность метода или эмпирические предпосылки. Разбиение rows/CI проверяется численно; parallel trends и область covariance требуют отдельного основания.

Документация задаёт цель и существенные различения, не требует нового универсального framework. В этом локальном пакете не нужен искусственный второй предметный домен: параметризованные содержательно различающиеся inputs проверяют общность действующего механизма. LLM может предложить постановку/профиль, но не подменяет partition, measured execution или независимое основание научного claim.

## 10. Конечные решения и сдача

### DEC-CAU-01-LABEL
**Вопрос:** Есть ли заявленные callers с mixed/custom scalar labels за пределами normal string/int?
**Владелец решения:** Исполнитель CAU-01 и reviewer публичного input contract.
**Ограниченное действие/выход:** Проверить actual callers/tests и сериализуемый тип unit_ids/cluster_var; перечислить поддерживаемые классы. Если нужен новый scalar тип, предложить общее правило identity и различающий тест. Не принимать arbitrary object equality молча.
**Без нового решения:** Missing/non-reflexive labels отклоняются; нормальные string/int сохраняются; выбор не блокирует ремонт NaN.

### DEC-CAU-01-INFERENCE
**Вопрос:** Требуется ли finite-cluster процедура конкретному реальному дизайну?
**Владелец решения:** Владелец научного профиля/технический reviewer, без выдуманного имени.
**Ограниченное действие/выход:** Предъявить независимую единицу, предпосылки и требуемый estimand; выбрать существующую поддержанную процедуру либо явно ограничить normal CR0. Новый метод — отдельный обоснованный scope.
**Без нового решения:** Существующий large-unit normal CR0 остаётся кандидатом с limitation, без finite-cluster guarantee.

Предъявить: patch/base/head и rationale, exact REQ→TEST→shared variant, исходные inputs и их идентичности, команды/exit/log, значения независимых oracles, positive/negative/removal controls, сохранённые инварианты, compatibility/remaining decisions. Не скрывать FAIL/UNRUN. Можно отдельно принять адресный механизм и оставить явно названную scientific/историческую квалификацию открытой; нельзя назвать это полной эмпирической или институциональной готовностью.
