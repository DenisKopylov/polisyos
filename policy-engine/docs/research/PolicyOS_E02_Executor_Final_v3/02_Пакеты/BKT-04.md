# BKT-04 — Квалификация выбранных CV folds и честного bootstrap selector

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP3 · B174, B175.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Сохранить оба уже исправленных локальных механизма и квалифицировать их actual public/native consumer. До интерпретации generic CVResult определить shape/missing/weight policy и resampling unit. Не придумывать новый defect или обязательный вызов helper на каждом runtime пути.

**Тип работы:** Preserve/qualify-only исходных repairs; ограниченный caller-contract capability для CV metrics при реальном потребителе; научная квалификация resampling отдельно.

[Аудит](../05_Основания/Аудит/02_Пакеты/BKT-04.md) · [остатки](../05_Основания/Аудит/01_Реестры/C35_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/BKT-04_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C35_источники.json) · [трассировка](../04_Трассировка/BKT-04.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B174: positive discrete progress и selection-before-materialization уже присутствуют; grid и callback isolation сохраняются. B175: unknown selector отвергается до RNG, finite1D и finite result, builtin/callable identity уже различены. Нет подтверждённой новой R-находки. C35-G02/G03 не превращают generic helper в faulty production admission; определить intended caller и его смысловой контракт.

- `preserve:0442`: Old valid grid → REQ-BKT-04-01; TEST-BKT-04-01.
- `preserve:0443`: Early parameter validation → REQ-BKT-04-01; TEST-BKT-04-02.
- `preserve:0444`: Selected6 lists/1504 elements → REQ-BKT-04-01; TEST-BKT-04-01.
- `preserve:0445`: Callback isolation → REQ-BKT-04-02; TEST-BKT-04-02.
- `preserve:0446`: Early selector resolution → REQ-BKT-04-04; TEST-BKT-04-04.
- `preserve:0447`: Finite1D inputs/results → REQ-BKT-04-05; TEST-BKT-04-04.
- `preserve:0448`: Builtin/callable identity distinction → REQ-BKT-04-04; TEST-BKT-04-05.
- `preserve:0449`: Local RNG and direct RMSE bootstrap → REQ-BKT-04-05, REQ-BKT-04-06; TEST-BKT-04-06.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C35-G01` | qualify: Native public tests и finite actual activation census; не forced runtime dependency. | REQ-BKT-04-01, REQ-BKT-04-04, REQ-BKT-04-05, REQ-BKT-04-07 |
| `C35-G02` | capability: Явный selected evaluator shape/metric denominator contract, generic limitations не production defect. | REQ-BKT-04-02, REQ-BKT-04-03 |
| `C35-G03` | qualify: Sampling-unit/scientific scope и honest arbitrary-callable identity. | REQ-BKT-04-04, REQ-BKT-04-05, REQ-BKT-04-06 |

Все source-registry remaining также связаны: `remaining:0294`, `remaining:0295`, `remaining:0296`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-BKT-04-01
Сохранить current valid forward-chaining grid и выбранные позиции: max_folds ограничивает создание index lists, а не только final slice. Discrete positive step/train/cap проверяются до range/materialization; bool/fraction недопустимы, NumPy integers поддержаны. Full-grid запрос честно несёт свою неизбежную стоимость.
Источник: B174; C35-G01. Проверки: TEST-BKT-04-01, TEST-BKT-04-02.

### REQ-BKT-04-02
Callback получает изолированные train/test arrays только выбранных folds, без мутации original/соседнего fold. Shape policy задаётся явно у selected evaluator/caller: deliberate multivariate first-axis observations допустимы, silent flatten и расхождение1D docstring/контракта устраняются документацией/validation в правильной boundary.
Источник: B174; C35-G02. Проверки: TEST-BKT-04-02, TEST-BKT-04-03.

### REQ-BKT-04-03
При использовании CVResult как measurement selected caller сохраняет requested folds, per-metric evaluated/missing/invalid counts и weighting policy. NaN либо отсутствующий metric не превращаются в measured zero/full success. Полезные finite fold metrics остаются доступны; aggregate вычисляется только по declared denominator и не скрывает missing folds. Generic raw helper result не получает authority от dataclass serialization.
Источник: B174; C35-G02. Проверки: TEST-BKT-04-03, TEST-BKT-04-07.

### REQ-BKT-04-04
Unknown explicit statistic отвергается до callback/RNG/sampling; default применяется только при отсутствии параметра. Named mean/median/std сохраняют реальный resolved selector отдельно от display metric. Callable declaration остаётся consumer_asserted, anonymous callable not_established, function name/closure label не считается verified semantic identity.
Источник: B175; C35-G01, C35-G03. Проверки: TEST-BKT-04-04, TEST-BKT-04-05.

### REQ-BKT-04-05
Оба bootstrap entrypoints сохраняют finite1D observation unit, early empty/count/confidence guards, finite scalar callback/result/CI и caller exception semantics. Bad point statistic не расходует draws; bad sampled statistic прекращает computation без нормального CI. Local seeded RNG воспроизводим; RMSE вычисляется внутри каждого resample, не как sqrt интервала другой статистики.
Источник: B175; C35-G01, C35-G03. Проверки: TEST-BKT-04-04, TEST-BKT-04-06.

### REQ-BKT-04-06
Selected resampling protocol обосновывает exchangeable observation unit/effective n и назначение confidence interval. Для time/cluster dependence использовать подходящий existing method с block/cluster unit либо сохранить explicit unsupported scientific claim, а не flatten/pretend iid. Singleton std0 остаётся convention, не доказанная population variance/coverage.
Источник: B175; C35-G03. Проверки: TEST-BKT-04-06, TEST-BKT-04-07.

### REQ-BKT-04-07
Native public tests и конкретный intended caller/consumer квалифицируются без обязательного искусственного runtime hook. Если finite census не находит active runtime caller, сдать supported public helper contract и честную неустановленную activation; end-to-end speedup/empirical authority не заявлять. Если caller есть, result→persisted representation→fresh consumer сохраняет counts/statistic identity/limits.
Источник: B174, B175; C35-G01. Проверки: TEST-BKT-04-01, TEST-BKT-04-07.

## 5. Конкретное техническое решение

**Не менять работающие алгоритмы ради diff.** `forward_chaining_splits` уже вычисляет count/selected positions до list(range), проверяет operator.index и bool, сохраняет прежний linspace grid. `bootstrap_metric` уже разрешает statistic и point до RNG и сохраняет identity basis. First action — current native tests, затем только воспроизведённое несоответствие или выбранный caller-contract gap.

**CV consumer policy:** generic callback возвращает dict, а aggregate берёт только folds с данным ключом и допускаетNaN. Это не автоматически authoritative defect. У actual intended consumer определить observation axis и metric inventory; предпочтительно adapter к существующему backtest completeness/report контракту с requested/evaluated/missing/invalid по каждому metric и явно выбранными weights. Не flatten2D, если rows — multivariate observations. Либо generic public contract действительно1D и проверяет ndim, либо docstring/typed expectation честно поддерживает first-axis arrays. Решение основывается на finite caller census, не на предположении. Missing metric сохраняется как missing, raw folds полезны; не подставлять0 и не silently renormalize admission.

**Bootstrap:** сохранить independent scalar statistic от display label. Для arbitrary callable нельзя обеспечить универсальный mathematical verifier; consumer_asserted/not_established — правильный честный контракт, не повод запретить useful callbacks. Effective method identity в downstream содержит selector/declaration/basis, n_bootstrap/seed/backend context, без нового provenance registry.

**Sampling protocol и activation:** этот helper ресэмплирует elements iid. Если selected study требует clusters/time blocks, подключить существующий подходящий owner для того случая с declared sampling unit, а не ломать iid helper и не автоматически группировать по форме arrays. Если active caller пока отсутствует, не заказывать глобальную регистрацию: public API qualified, runtime activation отдельно not established. Shared E02-I03-C получает лёгкий variant только для фактически выбранного consumer; helper performance measure не выдаётся за ускорение всей системы.

### Текущие owners и источники

- [policy-engine/src/polisyos/scientist/methods/backtesting/cv.py:1–160](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/cv.py#L1-L160)
- [policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py:25–246](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py#L25-L246)
- [policy-engine/src/polisyos/scientist/methods/backtesting/__init__.py:1–106](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/__init__.py#L1-L106)
- [policy-engine/tests/unit/scientist/methods/backtesting/test_cv.py:1–153](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/backtesting/test_cv.py#L1-L153)
- [policy-engine/tests/unit/scientist/methods/backtesting/test_bootstrap.py:1–263](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/backtesting/test_bootstrap.py#L1-L263)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-BKT-04-01 · native materialization and reference-grid regression
**NOT_RUN. REQ:** REQ-BKT-04-01, REQ-BKT-04-07.
**Setup:** n1000,min_train2,step1,max_folds3; controlled observer materialization; finite exhaustive small parameter grid с independent old full-grid/linspace reference.
**Действие:** Actual forward_chaining_splits; observer считает реальные list allocations/elements, не оценивает по final object.
**Oracle:** Ровно6 index lists,1504 elements, train sizes[2,500,999], test[2]/[500]/[999]. Valid small grids совпадают со reference; no hidden grid change. Это preparation evidence, не системный speedup multiplier.
**Место:** `tests/unit/scientist/methods/backtesting/test_cv.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-04-02 · native invalid-progress and isolation
**NOT_RUN. REQ:** REQ-BKT-04-01, REQ-BKT-04-02.
**Setup:** step0/-1/1.5/True, invalid train/cap, numpy integer positive, train=n; callback пытается изменить arrays.
**Действие:** Проверить validation до first range; actual run_forward_chaining_cv на3folds.
**Oracle:** Invalid parameters быстро ValueError без loop/materialization. np.integer valid; train=n zero folds. Callback mutations не меняют original/другой fold, only selected callback invocations. Не запускать unbounded hang как тест.
**Место:** `tests/unit/scientist/methods/backtesting/test_cv.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-04-03 · selected caller CV metric contract
**NOT_RUN. REQ:** REQ-BKT-04-02, REQ-BKT-04-03.
**Setup:** Two folds: metric finite в первом, missing во втором; NaN metric; несколько metrics с разными missing patterns;1D и deliberate2D observations.
**Действие:** Caller/evaluator adapter применяет declared shape/metric policy, сохраняет fold inventory и читает result.
**Oracle:** Finite values доступны с correct per-metric denominator1/2 и reason; invalidNaN не silent zero/normal mean. Whole-fold n2 не выдаётся за metric n2. Explicit multivariate first-axis policy preserves columns; unsupported shape refused before expensive evaluation, no flatten. Weighting equal-fold либо test-cell явно названо.
**Место:** `cv.py::run_forward_chaining_cv плюс actual selected caller из DEC-CALLER`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-04-04 · native selector-before-RNG and finite guards
**NOT_RUN. REQ:** REQ-BKT-04-04, REQ-BKT-04-05.
**Setup:** [0,0,9], labelmedian/statisticmedain,n_bootstrap1000;2D,NaN/inf,empty,badcount/badconfidence; invalid callback point/sample outputs.
**Действие:** Count actual RNG constructions/callback calls; invoke both public entrypoints.
**Oracle:** medain unknown_statistic с0RNG; invalid input0callback/0RNG. Invalid point0draw, bad first draw толькоpoint+1sample и noCI. Callable-raised TypeError сохраняет причину, не fallbackmean.
**Место:** `tests/unit/scientist/methods/backtesting/test_bootstrap.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-04-05 · native identity/readback matrix
**NOT_RUN. REQ:** REQ-BKT-04-04.
**Setup:** Same display label, named mean/median/std; two same-name closures q.5/q1 с разными IDs; anonymous maximum; blankID/nonstringID/builtin override.
**Действие:** BootstrapCI dataclass→ordinary JSON→explicit reader; selected consumer проверяет identity basis.
**Oracle:** [0,0,9]: mean3,median0,stdsqrt27; resolved names сохранены. Closures outputs0/9 consumer_asserted, anonymous9/not_established; invalid declaration rejected before callback. Ни JSON ни function name не повышают basis до recomputed.
**Место:** `tests/unit/scientist/methods/backtesting/test_bootstrap.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-04-06 · native RNG and direct resampled statistic
**NOT_RUN. REQ:** REQ-BKT-04-05, REQ-BKT-04-06.
**Setup:** Fixed errors/seed и конечный n_bootstrap; independent reference rng.choice+per-draw sqrt(mean(square))→percentile; singleton std.
**Действие:** Both entrypoints twice same seed; compare exact generated summary по закреплённому backend/version.
**Oracle:** Same-seed samebounds; actual RMSE bootstrap совпадает с independent per-resample oracle, MAE mean(abs) сохранён. Singleton std0 маркируется convention в intended interpretation; seed не называется independent population evidence.
**Место:** `tests/unit/scientist/methods/backtesting/test_bootstrap.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-04-07 · finite activation and scoped consumer E02-I03-C
**NOT_RUN. REQ:** REQ-BKT-04-03, REQ-BKT-04-06, REQ-BKT-04-07.
**Setup:** Полный actual src/public facade/callsite/config census данного helper, не всего проекта; selected intended caller либо public-library use. Один justified iid observation sample и один time/cluster-dependent counterexample.
**Действие:** Запустить current public imports/tests; для actual caller — result transport/readback и проверку bounded policy. Сохранить caller path, sampling unit, confidence/statistic identity/denominators.
**Oracle:** Active caller подтверждён actual route, либо честно not established без forced runtime registration. iid helper полезен; dependent claim использует подходящий existing resampler или остаётся ограниченным без псевдоcoverage. Нет публикации generic NaN mean как admitted measurement; partial finite values доступны. Native source/profile claims требуют actual owner, ordinary dataclass JSON только transport.
**Место:** `backtesting/__init__.py; test_cv.py; test_bootstrap.py; selected caller из DEC-CALLER`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/scientist/methods/backtesting/test_cv.py tests/unit/scientist/methods/backtesting/test_bootstrap.py
# Selected caller variant добавить только после DEC-CALLER; отдельный native runtime outcome не предполагается.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-C**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

BKT-04 владеет cv.py/bootstrap.py public contracts и focused tests. Actual caller owner отвечает за metric/sampling policy и интерпретацию, BKT-02 — report completeness semantics. Не требуется очередной scheduler/registry или 127fold integration suite. Работа может завершиться без product diff для исходных repairs, но qualification/caller decision документируются конкретно.

- **BKT-01:** Historical feature leakage отдельно от CV boundaries; selected folds не доказывают as-of admissibility.
- **BKT-02:** Переиспользовать per-metric completeness/weight semantics у actual consumer, не смешивать CV mean с microRMSE.
- **BKT-03:** Independence/effective-n scientific assumptions сохраняются при bootstrap interpretation.

## 8. Совместимость, миграция и возврат

Сохранить public builtins, anonymous/custom callable support, local RNG, valid grid и evaluator isolation. Новый selected consumer validation не меняет generic valid multivariate use без census. Existing raw CVResult не переаттестовывается; any typed measurement adapter явно отличается от ordinary dataclass. Rollback adapter оставляет raw descriptive result и limitation, не возвращает unknown-statistic fallback или NaN positive qualification.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0, extensible computation contracts](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Generic callable/evaluator остаются расширяемыми; реальные limits/observation semantics задаются contract, не жёстким перечнем задач.
- [wave5-evidence-substitution-ratification.md — K01 и K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Имя callable, seed и JSON не заменяют проверку научного смысла/coverage; полезный conditional result сохраняется.

## 10. Конечные решения и сдача

### DEC-BKT-04-CALLER
**Вопрос:** Кто фактически потребляет generic CV/bootstrap как measurement?
**Кто решает:** Scientist backtesting/public API owner.
**Конечное действие/выход:** Finite census exact imports/calls/public facade/config и объявленного intended usage; выбрать actual caller с shape/metric policy либо supported public-only status. Сдать конкретный route и TEST07; не объявлять отсутствующими dynamic callers без evidence.
**До решения:** Public helper supported, runtime activation not established; никакой forced global hook.

### DEC-BKT-04-SAMPLING
**Вопрос:** Обосновано ли iid resampling для выбранной observation unit?
**Кто решает:** Selected study/method owner.
**Конечное действие/выход:** Назвать unit, dependence/effective-n и confidence target; iid оставить при обосновании, иначе выбрать existing block/cluster method с distinguishing dependent control. Недоступная domain evidence остаётся qualification gap.
**До решения:** Численный bootstrap conditional, без empirical coverage/causal/population authority.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
