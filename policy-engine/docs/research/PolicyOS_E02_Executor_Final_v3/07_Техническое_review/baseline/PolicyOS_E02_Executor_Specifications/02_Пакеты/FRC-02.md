# FRC-02 — Строгие counts, native ETS→S10 и полезная связь observed metric с вопросом

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP4 · LA-051.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Завершить LA-051 на уже существующем ForecastOwner/neutral bridge, а не заказать новый calibration service. Исправить усечение metadata counts, квалифицировать реальную короткую цепочку и подключить один проверяемый outcome relation, сохраняя полезную predictive-only работу при неизвестной внешней достоверности.

**Тип работы:** Локальный ремонт C31-R01; native квалификация существующей реализации; ограниченное расширение способности C31-G02; научная квалификация отдельно от software acceptance.

[Аудит](../05_Основания/Аудит/02_Пакеты/FRC-02.md) · [остатки](../05_Основания/Аудит/01_Реестры/C31_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/FRC-02_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C31_источники.json) · [трассировка](../04_Трассировка/FRC-02.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

LA-051 этап2/2 и accountable closure: реальный ETS producer, измеренный estimand predictive_interval_coverage, train/holdout, report/model/rule/version и шесть временных ролей уже существуют. FRC-01 снимает ложное summary promotion, PCL-01 сохраняет report→receipt ограничения. Здесь не заменять causal CI предиктивным интервалом. LK01/LK29/LK30: parameter calibration, predictive diagnostics, S10 records и production authority остаются разными ролями. Полная empirical authority не является автоматическим результатом tiny native теста.

- `preserve:0779`: Actual ForecastOwner and held-out comparisons → REQ-FRC-02-02, REQ-FRC-02-03, REQ-FRC-02-07; TEST-FRC-02-02, TEST-FRC-02-03, TEST-FRC-02-08.
- `preserve:0780`: Canonical report/evidence reprojection and exact selected profiles → REQ-FRC-02-03, REQ-FRC-02-04; TEST-FRC-02-03, TEST-FRC-02-04, TEST-FRC-02-05, TEST-FRC-02-06.
- `preserve:0781`: Predictive-only denials and conservative credibility → REQ-FRC-02-05, REQ-FRC-02-08; TEST-FRC-02-03, TEST-FRC-02-05, TEST-FRC-02-06, TEST-FRC-02-08.
- `preserve:0782`: Historical bytes/read semantics → REQ-FRC-02-06; TEST-FRC-02-07.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C31-R01` | fix: До преобразования проверить точную неотрицательную целочисленность. | REQ-FRC-02-01 |
| `C31-G01` | qualify: Existing native producer/service/readback квалифицируется, не пишется заново. | REQ-FRC-02-02, REQ-FRC-02-03, REQ-FRC-02-06, REQ-FRC-02-08 |
| `C31-G02` | capability: Проверяемая outcome↔observed relation отсутствует; одной команды pytest недостаточно. | REQ-FRC-02-04, REQ-FRC-02-05, REQ-FRC-02-06, REQ-FRC-02-08 |
| `C31-G03` | qualify: Scoped scientific experiment и denominator semantics, не causal CI из predictive coverage. | REQ-FRC-02-02, REQ-FRC-02-07, REQ-FRC-02-08 |

Все source-registry remaining также связаны: `remaining:0477`, `remaining:0478`, `remaining:0479`, `remaining:0480`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-FRC-02-01
Каждый metadata numerator/denominator принимается только как неотрицательное конечное целое без потери значения. До int-нормализации исключить bool, дробные2.9 и-0.1, nonfinite, произвольные объекты с __int__. Ошибка даёт persisted_metadata_counter_invalid, не usable pass. Actual observed counts всё равно независимо вычисляются из bounds. Для текстовых целых явно зафиксировать ограниченную legacy grammar, не разрешать decimal/exponent truncation.
Источник: LA-051; C31-R01. Проверки: TEST-FRC-02-01, TEST-FRC-02-02.

### REQ-FRC-02-02
Один train slice и одинаковые параметры дают одинаковые point forecast/intervals при разных holdout; actual observed hits и usability различаются. Изменение только nominal confidence в report без новых observations не меняет измеренный numerator/denominator; отсутствие интервалов даёт сохраняемый ограниченный результат с нулевым denominator, не pass.
Источник: LA-051; C31-G01, C31-G03. Проверки: TEST-FRC-02-02, TEST-FRC-02-03.

### REQ-FRC-02-03
Actual ForecastOwner, registry/dispatcher, native CAS, canonical report/evidence loader и run-bound service→S10→fresh association reader выполняют одну содержательную цепочку. Exact profiles/source edges/model/rule/time binding проверяются при создании и чтении. Forged flags, foreign selected profile, изменённый источник, модель, правило либо временная роль не могут сохранять прежний admitted outcome.
Источник: LA-051; C31-G01. Проверки: TEST-FRC-02-03, TEST-FRC-02-04.

### REQ-FRC-02-04
Добавить к существующему selected source/profile пути проверяемую relation N4 target variable/metric→observed snapshot metric для одного полезного случая. Relation связывает выбранные candidate/problem/world revision, snapshot/profile/member, единицы, transformation, population и time scope; неизвестные поля явно неизвестны. Совпадение строк metric_id недостаточно. Consumer разрешает только ту ограниченную predictive роль, которая обоснована этой relation; отсутствие/несогласованность relation блокирует лишь outcome-calibrated tier, не уничтожая годный series calibration record.
Источник: LA-051; C31-G02. Проверки: TEST-FRC-02-05, TEST-FRC-02-06.

### REQ-FRC-02-05
LLM может предложить relation и объяснение единиц/агрегации, но её usable status устанавливает существующий source/model owner по доступным данным и declared assumptions. Не присваивать issuer_status, source_population_scope_status, source_time_status=established из наличия internal role artifact. Новая совместимая метрика подключается через тот же relation mechanism без специальной ветки на название страны/политики.
Источник: LA-051; C31-G02, C31-G03. Проверки: TEST-FRC-02-05, TEST-FRC-02-06.

### REQ-FRC-02-06
Исторические evidence1.0/1.1 сохраняют bytes и прежнюю семантику; новое evidence использует текущие exact profiles. Исторический nominal не восстанавливается догадкой, legacy repersist как newly measured evidence запрещён. При необходимости расширения relation/profile выполнить явное versioned чтение, не задним числом объявлять старую not_established relation подтверждённой.
Источник: LA-051; C31-G01, C31-G02. Проверки: TEST-FRC-02-04, TEST-FRC-02-07.

### REQ-FRC-02-07
Конечный эксперимент квалифицирует конкретный horizon/sample/source regime и estimand predictive_interval_coverage: train/holdout разделены, numerator/denominator и пропуски открыты, temporal dependence и uncertainty измерения отражены. Generic bridge denominator по наблюдённым interval rows не называется полным requested corpus; ForecastOwner сохраняет требование полного horizon set. Finite-sample screening tolerance не становится universal calibration или causal-effect authority.
Источник: LA-051; C31-G03. Проверки: TEST-FRC-02-02, TEST-FRC-02-08.

### REQ-FRC-02-08
Сохранить EvalSafety/WMR/candidate checks, conservative counterfactual credibility, predictive-only denials, method/rule revisions и раздельные времена. Успех software bridge и поддержанная outcome relation не выпускают production recommendation и не подтверждают causal effect CI. Доказательство новой положительной способности содержит фактическое значение/единицы/ограничения у fresh S10 consumer, не только факт отказа.
Источник: LA-051; C31-G01, C31-G02, C31-G03. Проверки: TEST-FRC-02-03, TEST-FRC-02-04, TEST-FRC-02-05, TEST-FRC-02-06, TEST-FRC-02-08.

## 5. Конкретное техническое решение

**Локальный ремонт.** `_coerce_int` сейчас вызывает `int` прежде проверки. Применить явный разбор разрешённых JSON-чисел/строк: bool запрещён; int>=0; finite float с `is_integer()` и>=0; для строки — документированная decimal integer grammar без дробной/экспоненциальной нотации, если legacy требует её. Не принимать произвольный object coercion. После нормализации сравнивать с independently recomputed hits; сохранять нынешние issue codes, не изменять numerator из metadata. Большие целые не прогонять через float. Точная legacy grammar решается на сохранённых fixtures, а не на предположении о клиентах.

**Bridge уже существует.** ForecastOwner читает selected source/profile, считает ETS и rolling-origin uncertainty на training, сравнивает holdout, сохраняет report. Neutral bridge повторяет observed counts и проверяет context role edges; service создаёт run-bound refs, persists evidence/association, `_recompute_s10` заново открывает candidate/report/evidence. Принять этот путь native, а не переписать provider или убрать standalone bridge_pending. Исправления FRC-01/PCL-01 включаются как варианты одного E02-I03-B.

**Положительная недостающая способность.** `_n4_outcome_target_binding_record` пока только записывает две identity со статусом not_established; `_s10_n4_outcome_binding_limitation_ref` блокирует любой typed N4 candidate. Расширить существующий selected profile/source контракт проверяемой relation и передать её canonical projection в S10. Сначала finite census existing source/profile schemas: если они уже выражают relation, использовать их; иначе минимальное versioned поле/DTO в текущем owner, а не новый service/registry. Relation содержит candidate/problem/world revision, observed snapshot/profile/member, target definition, units/transformation и scope. Разрешённую transformation выбирает existing measurement/model owner; неизвестное semantic соответствие остаётся явно условным, не исправляется string equality. LLM предлагает гипотезу/сопоставление, system проверяет структуры/единицы/selected-source применимость, а научные assumptions не объявляет доказанными.

Service и fresh `_recompute_s10` должны разрешать **тот же** persisted relation через canonical source/profile loader и recompute scope; старый helper меняется с unconditional N4 refusal на refusal без подтверждённой применимой relation. Не доверять `metadata.status=established`. Unknown source population/time/issuer и credibility не становятся известными лишь потому, что внутренний artifact существует. Сначала поддержать один полезный relation, затем второй совместимый case тем же механизмом; неизвестная новая семантика требует честного declared gap, не бесконечного универсального изобретателя моделей.

### Текущие owners и источники

- [policy-engine/src/polisyos/calibration/forecast_bridge.py:440–580](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/forecast_bridge.py#L440-L580)
- [policy-engine/src/polisyos/calibration/forecast_bridge.py:748–786](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/forecast_bridge.py#L748-L786)
- [policy-engine/src/polisyos/calibration/forecast_bridge.py:1446–1463](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/forecast_bridge.py#L1446-L1463)
- [policy-engine/src/polisyos/calibration/forecast_bridge.py:1852–1859](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/forecast_bridge.py#L1852-L1859)
- [policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py:647–800](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py#L647-L800)
- [policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py:1239–1254](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py#L1239-L1254)
- [policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py:595–630](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py#L595-L630)
- [policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py:961–980](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py#L961-L980)
- [policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py:1948–2036](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py#L1948-L2036)
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:17203–17217](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17203-L17217)
- [policy-engine/tests/unit/remediation/test_frc_02_s10.py:1191–1251](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_frc_02_s10.py#L1191-L1251)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-FRC-02-01 · native count regression
**NOT_RUN. REQ:** REQ-FRC-02-01.
**Setup:** Настоящий BacktestReport с observed2/2; во всех четырёх metadata keys поочерёдно2.9,-0.1,True,NaN,inf,объект __int__, целые0/2,2.0 и согласованная textual legacy grammar.
**Действие:** Вызвать actual bridge producer; valid persist/load; malformed нельзя объявлять usable. Вне JSON проверить прямую DTO boundary, затем JSON-supported subset через native CAS.
**Oracle:** 2.9 не становится2 и-0.1 не становится0; persisted_metadata_counter_invalid присутствует, floor_passed=False. Valid2 и точно integral2.0 согласованы с observed2; bool не проходит. Text2 разрешается только если выбранная явная grammar; 2.9/2e0 не усекать. Mismatch3 vs observed2 остаётся mismatch, observed counts не заменены metadata.
**Место:** `tests/unit/remediation/test_frc_02.py; calibration/forecast_bridge.py::_coerce_int/_recompute_and_reconcile`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-02-02 · native independent observation oracle
**NOT_RUN. REQ:** REQ-FRC-02-01, REQ-FRC-02-02, REQ-FRC-02-07.
**Setup:** Два отчёта одинаковой формы с2/2 и1/2 hits; nominal.80/.95; отсутствующие интервалы; generic2requested/1interval; actual owner incomplete horizon output.
**Действие:** Recompute по y_true и inclusive low<=y<=high независимым простым loop; actual produce/persist/load сравнить с oracle.
**Oracle:** Observed rate1/.5 не следует nominal. Без intervals denominator0 и limitation. Generic subset1/1 явно не whole2/2; actual owner incomplete horizon отвергнут. Malformed metadata не делает subset полным; actual measured numbers сохранены.
**Место:** `tests/unit/remediation/test_frc_02.py; test_frc_02_owner.py; forecast_owner.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-02-03 · native owner→CAS→service→fresh S10 E02-I03-B
**NOT_RUN. REQ:** REQ-FRC-02-02, REQ-FRC-02-03, REQ-FRC-02-08.
**Setup:** Existing empirical_bridge fixture training10..19 и holdout20,21,22 vs1000,1001,1002; actual ETS NumPy/uncertainty/dispatcher. Existing run/profile integration fixture создаёт действительные selected source/model/policy/rule и scoped intent.
**Действие:** Сначала standalone owner→report→bridge, затем actual service role artifacts→evidence→association. Новый process/reader открывает association и повторяет S10.
**Oracle:** Одинаковые forecast/intervals, разные observed counts; standalone bridge_pending не превращается в false missing-producer diagnosis. Service result имеет воспроизводимые refs/counts и predictive-only scope; без outcome relation series record полезен, N4 tier blocked. Нельзя manufactured context считать внешним source authentication.
**Место:** `tests/unit/remediation/test_frc_02_empirical_bridge.py; tests/integration/core_runtime/test_predictive_calibration_profile_owner_binding.py`.
**Doubles:** Synthetic data и test tenant допустимы. Actual ETS, uncertainty, dispatcher, CAS, service, canonical loader и S10 не подменяются; HTTP transport может вызываться in-process, но fresh read отдельно.

### TEST-FRC-02-04 · native mutation/removal matrix
**NOT_RUN. REQ:** REQ-FRC-02-03, REQ-FRC-02-06, REQ-FRC-02-08.
**Setup:** Сохранённая valid association; по одному изменению bytes/hash, selected profile member, child source edge, model ref, method/rule version, threshold, одной temporal role, positive flag.
**Действие:** Открыть через canonical evidence/association loader и вызвать S10; рядом unchanged control.
**Oracle:** Каждое несовместимое изменение адресно refused/limited; новый hash для неверного payload не помогает. Unchanged control воспроизводит measured record. Времена остаются разными семантическими ролями; не чинить chronology подстановкой now().
**Место:** `tests/unit/remediation/test_frc_02_s10.py; tests/unit/runtime/http/test_predictive_calibration_profile_boundary.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-02-05 · native positive selected relation capability
**NOT_RUN. REQ:** REQ-FRC-02-04, REQ-FRC-02-05, REQ-FRC-02-08.
**Setup:** Один выбранный policy question и реальный конечный observed snapshot с документированными units/population/time; relation proposal с корректной identity либо явной применимой transformation. Второй совместимый вопрос/метрика отличается содержательно, не толькоID.
**Действие:** Existing owners validate/select relation, persist exact profile edges, actual ForecastOwner→service→fresh S10. Показать numeric forecast/calibration и scoped outcome relation у consumer.
**Oracle:** Оба случая идут через один mechanism без if по case-name. Target variable/metric, units/transformation и scope воспроизводятся; поддержанная conditional predictive роль доступна. Unknown issuer остаётся unknown; отсутствие основания для causal effect/production продолжает ограничивать только такие claims.
**Место:** `runtime/http/services/predictive_calibration.py::_n4_outcome_target_binding_record/_recompute_s10; generation_cycle.py::_s10_n4_outcome_binding_limitation_ref`.
**Doubles:** Контролируемый LLM proposal допустим; source/profile resolver и relation validation не заменяются готовым established flag. Если фактического empirical corpus нет, software fixture квалифицирует механизм, practical validation остаётся отдельным NOT_RUN.

### TEST-FRC-02-06 · native relation negative and useful fallback
**NOT_RUN. REQ:** REQ-FRC-02-04, REQ-FRC-02-05, REQ-FRC-02-08.
**Setup:** Тот же series evidence с отсутствующей relation, foreign snapshot/profile, несовместимыми единицами/агрегацией, population/time вне declared scope, self-declared established и одинаковым metric name для другого определения.
**Действие:** Reopen и повторить S10 по actual selected candidate.
**Oracle:** Ни одна подмена не создаёт outcome-calibrated tier. Сохранённые legitimate series counts/forecast доступны с причиной и точным scope; не возвращается общий пустой error вместо полезного результата. Отказ подтверждает только affected claim, не blanket invalidation других lawful evidence.
**Место:** `tests/unit/remediation/test_frc_02_s10.py; tests/integration/core_runtime/test_predictive_calibration_profile_owner_binding.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-02-07 · native historical compatibility
**NOT_RUN. REQ:** REQ-FRC-02-06.
**Setup:** Genuine retained schema1.0/1.1 fixture, текущая1.2, versioned relation при изменении profile.
**Действие:** Load старых bytes, compare SHA до/после; attempt repersist как new; current positive load.
**Oracle:** SHA неизменён, исторический nominal отсутствует где отсутствовал, old semantics reproduced; legacy repersist refused; new exact-profile path проходит. Старый not_established не повышается от новой версии reader.
**Место:** `tests/unit/remediation/test_frc_02.py; calibration/forecast_bridge.py::_reproduce_evidence`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-FRC-02-08 · scientific scoped experiment, separate acceptance
**NOT_RUN. REQ:** REQ-FRC-02-07, REQ-FRC-02-08.
**Setup:** Заранее выбранный доступный finite observed corpus и horizon grid, training/calibration/holdout protocol, baseline ETS/naive comparator, dependence-aware evaluation plan. Synthetic known-process control отдельно от реального корпуса.
**Действие:** Получить actual held-out predictions/hits по horizon, denominators/пропуски, interval widths и uncertainty observed rate; сохранить весь protocol до inspection результатов.
**Oracle:** Отчёт указывает точный sample/source/time/horizon scope, численное сравнение baseline и ограничения; admissible claim соответствует реально измеренному estimand. Не вводить универсальный порог acceptance из tiny fixture или tolerance max(.05,1/sqrt(n)). Отсутствие научной поддержки сохраняет conditional numerical result и блокирует лишь неподдержанный claim.
**Место:** `forecast_owner.py::run; foundry/methods/catalog/forecasting/uncertainty.py`.
**Doubles:** Источник/дизайн не заменяются synthetic examples для empirical authority. Доступный конечный corpus может отсутствовать: записать конкретный BLOCKED и не снимать software bridge acceptance.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_frc_02.py tests/unit/remediation/test_frc_02_owner.py tests/unit/remediation/test_frc_02_empirical_bridge.py tests/unit/remediation/test_frc_02_s10.py
python -m pytest -q tests/integration/core_runtime/test_predictive_calibration_profile_owner_binding.py
# Новые count/relation варианты добавить в существующие suites; selectors определить по actual patch.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-B**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

Forecast bridge владеет numeric reconciliation. Service/source-profile owner владеет relation persistence и selected binding; S10 только потребляет проверенную projection и определяет ограниченную роль. Schema/profile изменение согласовать с CYC/ACQ, не параллельно редактировать generation_cycle.py. Порядок: count regression→native baseline→relation decision/DTO→positive/fallback/fresh read→scoped practical experiment. Scientific gap не блокирует сдачу честного локального repair.

- **FRC-01:** Summary preservation и honest optional refs; единый gateway writer, один shared chain.
- **PCL-01:** Continuous report/receipt representation и denominator; не второй calibration owner.
- **EMP-01:** Selected source population/time и useful candidate scope; relation не выводится из country-only data.
- **CYC-01 / ACQ-01:** Использовать существующие N4 selected source/context/profile и acquisition, не новый planning registry.

## 8. Совместимость, миграция и возврат

Сохранять старые evidence bytes/versions и not_established, new profile version явно отличать при изменении semantics. Native current producer integer counters не меняются. Fractional metadata теперь ограничивается — intentional behavior fix. Rollback нового relation path возвращает только outcome tier в limited/blocked, series evidence остаётся доступным; не возвращать truncation и не переписывать historical artifacts. Доступность внешнего issuer не предполагается.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0 и практический target architecture](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Typed selected relation расширяет повторно используемую способность, а не перечень частных политик; поддерживает полезный conditional output.
- [wave5-evidence-substitution-ratification.md — K01, K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Internal role graph и good calibration math не заменяют empirical scope/authority. Consumer принимает собственное назначение, не статус producer как право действия.

## 10. Конечные решения и сдача

### DEC-FRC-02-COUNTS
**Вопрос:** Какие textual integers действительно входят в поддержанный historical contract?
**Кто решает:** Calibration bridge/release owner.
**Конечное действие/выход:** Проверить retained report fixtures/schema/callers; выбрать и протестировать конечную grammar. По умолчанию только неотрицательная decimal integer запись, не float parsing. Зафиксировать intentional отказ неподдержанным coercions.
**До решения:** Дробные/negative/nonfinite/bool не принимаются независимо от legacy решения.

### DEC-FRC-02-RELATION
**Вопрос:** Какой existing source/profile owner несёт проверяемое N4 outcome↔observed relation?
**Кто решает:** Selected source/profile owner и S10 reviewer.
**Конечное действие/выход:** Проследить actual N4 source/profile/member schemas; выбрать existing relation projection либо минимальное versioned расширение. Сдать schema/path map, один содержательный positive и второй совместимый case, mismatch/fresh-read controls. Не оставлять как общее исследование без результата.
**До решения:** Series record доступен; outcome-calibrated tier ограничен без применимой relation. Нельзя снять N4 guard только по равенству metric names.

### DEC-FRC-02-EXPERIMENT
**Вопрос:** Какое конкретное научное утверждение требуется сверх конечного measured screening?
**Кто решает:** Domain/method reviewer.
**Конечное действие/выход:** Назвать estimand, source/sample/horizon и protocol; выбрать имеющийся доступный corpus и baseline. Если external corpus недоступен, предъявить scoped software result и точный qualification gap без фиктивного authority.
**До решения:** Predictive-only conditional result, никаких causal/production claims.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
