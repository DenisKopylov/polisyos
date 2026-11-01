# PCL-01 — измеренный знаменатель, настоящий receipt и миграция tests
## C30 · 31 октября 2026 года

**Исходные IDs:** LA-052, LA-053. **Порядок:** 30/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Аудит без изменения продукта.

## Решение

**Старый «нет пригодных интервалов — хорошо» устранён в прочитанной и исполненной короткой цепочке.** Empty получает неизвестные метрики и not_evaluated; частичный набор — incomplete с inventory пропусков; лишние levels/sets и несовпавшие observations не отбрасываются. Настоящие report и TruthfulnessReceipt после JSON readback сохраняют ограничения. Численное качество 95/100 не потеряно, но отделено от неизвестного происхождения измерений.

Численные тесты уже находятся у canonical calibration owner. Старый Scientist test теперь проверяет только identity трёх экспортов; alias остаётся явно поддерживаемым. Его наличие не объявляется багом, а retirement без решения compatibility lifecycle не назначается.

Остался **C30-R01:** actual dispatcher merge учитывает ограничивающий continuous report только в typed форме; та же JSON mapping рядом с положительным sidecar оставляет positive receipt. Это условный локальный разрыв consumer, не доказанный production путь.

**22 MATCH, 0 ERROR**, exit 0 в обоих запусках. Исполнены настоящие numerical owners, report/receipt, MethodResult и merge; package initialization изолирована, root neighbors частично фикстурны. Native pytest/runner/distribution не запускались.

## 1. Исходные IDs и реальная структура

| ID | Сохранённое и проверенное исправление | Остаток |
|---|---|---|
| LA-052 | Явные not_evaluated/incomplete/evaluated, метрики None при отсутствии измерений, строгие lengths, skipped-level inventory, реальные DTO и receipt после readback, small-sample и task-specific reconciliation | C30-R01 — mapping/typed consumer boundary; C30-G01 — native qualification; C30-G03 — источник измерений не равен хорошей математике |
| LA-053 | Canonical numerical tests перенесены; old test identity-only; alias/root/implementation дают те же объекты в изолированном графе | C30-G02 — поддерживаемое окно и внешний FQN/config/notebook census; C30-G01 — native import/distribution |

[Полная карточка](../05_Источники/PCL-01_исходные_строки.txt), строки 3670–3845, включает LK01/LK30/LK32. Actual paths изменились: `calibration/curve/_compute.py` и `calibration/diagnostics/continuous.py`; прежние имена из плана не принимаются за отсутствующую реализацию.

## 2. Численный owner и точный смысл знаменателя

Curve проверяет равенство количества levels/sets, непустые finite observations, finite levels/tolerance/bounds и длину каждого непустого набора. Пустой набор может остаться для plotting/частичной диагностики, но делает итог incomplete и не позволяет positive flag. При полном отсутствии points ECE/MCE=None, well_calibrated=False. [S01:12–86](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/curve/_compute.py#L12-L86)

Continuous owner различает observations count и число проверенных interval levels. Он сохраняет requested/evaluated/skipped inventory, добавляет error issue для missing/incomplete, не запускает bootstrap по неполному сравнению и оставляет нормальную математику измеренной части. [S03:24–187](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/diagnostics/continuous.py#L24-L187) [S03:211–256](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/diagnostics/continuous.py#L211-L256)

**P01/P02:** 100 finite y + empty mapping/sequence → n_obs=100, comparisons=0, ECE/MCE/RMSCE=None, error, настоящий receipt unverified. Это воспроизведено через реальный временный JSON-файл и `CalibrationDiagnosticsReport.model_validate_json`, не словарь, выдаваемый за DTO.

**P03–P08:** empty y, отсутствующие интервалы/samples, лишний level, лишний set, короткий set и несогласованные mapping keys — адресные отказы. **P09/P10:** частичный и полностью пропущенный корпус не повышаются до pass. Для одного корректного уровня среди пропусков ECE=0 сохраняет смысл **только измеренной части**, inventory помечен incomplete, bootstrap отсутствует, receipt unverified.

**P11/P12:** 95/100 при .95 → ECE=0; 0/100 → ECE=.95. Реальный bootstrap сохраняется после typed readback. **P13–P15:** small-sample downgrade, PIT/ENCE и default levels для predictive samples сохранены; явный пустой список levels не заменяется default. Эти контролируемые корпуса проверяют расчёт, не доказывают пригодность реального калибровочного эксперимента.

## 3. Report→receipt: источник измерения не возникает из DTO

`CalibrationDiagnosticsReport._interval_coverage_admission` выводит число сравнений из bins, проверяет совпадение inventory, counts, nominal/observed fractions и ECE/MCE/RMSCE. **P20:** metadata claiming 5 comparisons при одном bin не становится основанием допуска. [S04:241–325](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py#L241-L325)

Continuous `to_truthfulness_receipt` сохраняет хороший `candidate_numeric_tier=approximate_calibrated`, но actual runtime/effective tier остаётся unverified с `measurement_source_not_established`. **C30-G03:** это намеренное разделение численного результата и происхождения данных, не необходимость вернуть старый unconditional positive tier. Источнику и эксперименту требуется существующий measurement bridge, а не снижение ECE threshold или новый registry. [S04:151–240](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py#L151-L240)

**P16/P17:** положительный supplied sidecar не побеждает actual typed empty report, включая canonical readback. **P19:** binary report не получает чужое требование continuous interval inventory. **P21:** настоящий `TruthfulnessReceipt` отвергает несогласованный effective tier; reconciliation не заменялся фикстурой и не обязан самостоятельно измерять coverage. [S05:112–171](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/_truthfulness.py#L112-L171) [S05:183–240](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/_truthfulness.py#L183-L240)

## 4. C30-R01 — ограничивающий report исчезает для extractor после перехода к mapping

`_typed_continuous_receipts` рекурсивно ищет только настоящий CalibrationDiagnosticsReport. Если такого объекта нет, generic extractor разрешает положительный `truthfulness_receipt` из mapping. `_merge_dispatch_result` использует этот extractor для объединения output и artifacts. `MethodResult.output` имеет контракт Any, а merge не восстанавливает report DTO. [S05:183–233](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/_truthfulness.py#L183-L233) [S13:199–222](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/protocol.py#L199-L222) [S14:387–417](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/dispatch.py#L387-L417)

**P18, actual MethodResult и actual merge:**

1. Один и тот же empty continuous report в `output`, положительный sidecar в `artifacts`.
2. Typed report → sidecar заменяется на **unverified**.
3. Его `model_dump(mode="json")` → sidecar остаётся **approximate_calibrated**.

Это не дефект canonical `model_validate_json`: P16 показывает, что корректное восстановление DTO сохраняет защиту. Остаток — на поддерживаемой границе serialized output→consumer. Нужно восстановить/проверить известный owner contract до reconciliation либо отказать несвязанному positive sidecar. Нельзя доверять произвольному dict только по самоназванию `task=continuous`.

**Граница:** merge действительно исполнен, но реальный method runner и production сериализация не запускались; timing/reproducibility не используются этим helper и заданы None. Наличие реального caller/telemetry подтверждено чтением, однако публикация ложного tier или обход внешнего gate не установлены. Соседний value-evidence consumer дополнительно требует typed uncertainty/estimand binding и gate eligibility; его защиты не отменяются. [S14:177–215](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/dispatch.py#L177-L215) [S15:275–325](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/value_evidence.py#L275-L325)

## 5. LA-053: migration состоялась, retirement ещё не заявлен

Canonical curve tests (139 строк) содержат старые численные сценарии с исправленным empty expectation, 95/100, нулевое покрытие, lengths и incomplete controls. Continuous tests (341 строка) добавляют actual report/readback/receipt, skipped inventory, samples и sidecar controls. Старый Scientist test — только 34-строчный identity check, без второго численного комплекта. Все прочитаны; native pytest не запускался. [S07:1–139](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/calibration/curve/test__compute.py#L1-L139) [S08:1–341](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/calibration/diagnostics/test_continuous.py#L1-L341) [S09:1–34](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/backtesting/test_calibration_curve.py#L1-L34)

**P22** исполняет настоящий root initializer и 15-строчный alias; три объекта совпадают с actual curve implementation. Соседние root imports binary/multiclass/recalibration заменены явными заглушками; отсюда нельзя заключить штатную загрузку всего пакета, startup cost или совместимость установленной distribution. [S10:1–15](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/calibration_curve.py#L1-L15) [S11:1–79](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/__init__.py#L1-L79)

**C30-G02:** адресный Python src/tests поиск нашёл старые imports в compatibility test; это не полный внешний нулевой граф. Исторический residual ledger также оставляет FQN/config/notebook census и lifecycle открытыми, но сам ledger не служит текущим тестом. До подтверждённого завершения поддержки alias полезен; не требуется удалять backtesting целиком, назначать произвольную sunset date или создавать цепочку новых aliases. [S16:499–500](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/RESIDUAL_LEDGER.md#L499-L500)

README сохраняет разные роли predictive diagnostics, Foundry parameter calibration и DDM drift calibration; одинаковое слово calibration не делает их взаимозаменяемыми. [S12:1–76](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/calibration/README.md#L1-L76)

## 6. Проверки и продолжение

**C30-G01:** supported native tests, public imports/distribution и полный dispatcher путь остаются UNRUN; зависимости не устанавливались. Реальная короткая numerical→typed report→filesystem readback→typed receipt цепочка здесь выполнена с настоящими моделями, но изолированной package initialization.

Первый и итоговый audit runs: **22 MATCH, 0 ERROR**. Во втором добавлено явное pin/hash logging root/alias, без изменения семантики. Исторические receipts, прежние пакетные отчёты и checkout сохранены; MATCH не равен product PASS.

[Диагностика](../04_Проверки/C30_PCL01/bounded_diagnostics.json) · [команды](../04_Проверки/C30_PCL01/commands.json) · [границы](../04_Проверки/C30_PCL01/Чтение_и_границы.md) · [источники](../05_Источники/C30_источники.json) · [остатки](../01_Реестры/C30_остатки.json).

**30/127 пакетов рассмотрены ограниченно; 80 уникальных B/LA частично оценены; полного закрытия нет.** Следующий **FRC-02**, по исходной очереди.
