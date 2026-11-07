# LANE-03: общий интеграционный контракт

**Цель:** Прогноз и эмпирическое основание полезны в объявленной области; holdout, coverage и calibration не подменяют causal authority.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: EMP-01, FRC-01, PCL-01, FRC-02, BKT-01, BKT-02, BKT-03, BKT-04

- CP1 ограниченные empirical results доступны до полного CP4 bridge.
- FRC-02 исходно зависит от FRC-01/PCL-01/EMP-01, не от завершения всего LANE-03.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-ANALYTICS:** P-CORE + applicable analytics/causal-core extras and exact selected numeric backend; no fixture substitution for native numeric claim (основание: policy-engine/pyproject.toml [project.optional-dependencies])

- Синтетический известный временной ряд допустим как проверка вычисления, не фактическая эмпирическая валидность политики.
- Transport и внешний clock контролируются; numeric producer, persisted report/role refs и consumer реальные.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I03-A — Empirical scope → summary без повышения силы

Покрываемая область: EMP-01, FRC-01

**Положительный oracle:** Country/unit/truncation ограничения проходят в summary; конечный условный прогноз и descriptive uncertainty остаются доступными без fabricated calibration.

**Различающий негативный oracle:** Смена единиц не меняет физическую ширину; finite overflow не создаёт false bound. Счётчик observation/CI не восстанавливает pass/floor вопреки input limitation.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I03-B — ETS holdout → report → receipt → fresh S10

Покрываемая область: PCL-01, FRC-02

**Положительный oracle:** Реальный ForecastOwner и numeric calibration сохраняют source/training/holdout/time roles; fresh reader выдаёт ограниченный S10 candidate с влиянием именно held-out ошибок.

**Различающий негативный oracle:** Nominal confidence не фабрикует observed hits/counts; report-only несогласованная подмена nominal/rule отвергается binding, а действительно выбранный новый nominal/rule может изменить gap и suitability по существующей формуле; empty/incomplete/дробные counts, wrong-kind/foreign/tampered evidence либо future temporal role не дают positive receipt. Predictive report не становится causal certification.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I03-C — Pre-cutoff view → backtest → persisted decision packet

Покрываемая область: BKT-01, BKT-02, BKT-03, BKT-04

**Положительный oracle:** Runner потребляет реальные prefix refs; partial rows сохраняют честный denominator; micro-метрика инвариантна техническому split. Constant residual сохраняет descriptive bias. Finite representable residual row не теряется только от overflow residual²/SSE: устойчивые MAE/RMSE остаются finite, SSE имеет отдельный unavailable reason; actual serialized rows независимо сверяет fresh IR.

**Различающий негативный oracle:** Future leakage, missing forecast, cancelled computation, unavailable SciPy или typo selector не дают false significance/trust; max_folds проверяется до дорогой работы, native failure не трактуется как отсутствие bias. Сам непредставимый residual остаётся invalid; unavailable SSE не подставляется 0/inf, requested denominator не уменьшается и trust не повышается.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/remediation/test_frc_02_empirical_bridge.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_frc_02_empirical_bridge.py) — SHA256 `09d018eed152f96937aa96184092c40ad03587a6b8dee8818b4e5d82db3c06bf`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_frc_02_s10.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_frc_02_s10.py) — SHA256 `1532c8b7e947ca341bcd9d6492fbe0d9b2dc955930c990d18e1b3142a51ba1f7`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/methods/backtesting/test_backtesting.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/backtesting/test_backtesting.py) — SHA256 `5052ded2db80238d69360ce390b1fdc0499a66473c2e61e1ae4691554e1e53cb`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_bkt_03.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_bkt_03.py) — SHA256 `2d6e387b2464c3b8bb3a5a5bf13919d960a384102a3331d84f8c562d84d7d537`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/nodes/test_decision_packet_node_v3.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/nodes/test_decision_packet_node_v3.py) — SHA256 `11e9237b98349c4570391bb65d390ee12da8dcd5ba8231f1ec5668f21009c326`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
