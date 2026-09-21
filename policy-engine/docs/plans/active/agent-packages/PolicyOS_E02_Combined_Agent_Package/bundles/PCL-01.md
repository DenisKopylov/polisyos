# PCL-01 — Предиктивная калибровка: знаменатель, receipt и canonical tests

**E02 · окно CP3 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-052 (M), LA-053 (C).

**Предшественники:** Нет. **Совместная очередь:** LANE-03.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

У существующего calibration owner согласовать levels/sets/observations, not-evaluated/incomplete/evaluated. Исправить report→receipt так, чтобы отсутствие сравнений не стало approximate_calibrated. Перевести содержательные Scientist tests на canonical API и объединить с test_continuous без двойного набора. Import-only шаг и намеренная смена empty=True expectations — отдельные коммиты.

**Различающие тесты и сохраняемое поведение.** 100 finite y_true + intervals={} или []/levels=[] не получают положительного tier; missing/surplus/misaligned пары видны. 95/100 при 0.95 и 0/100 различимы; small-sample downgrade сохранён. Native report/TruthfulnessReceipt не заменяются fixture. Binary/multiclass не обязаны иметь interval_coverage. Identity трёх public objects и поддержанного старого alias проверяется.

**Не считать исправлением.** Не удалять Scientist backtesting, не снижать ECE threshold, не ломать task-specific receipt reconciliation и не объявлять public alias снятым до lifecycle.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-052:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **PCL-01**; необходимые пакеты: PCL-01.

**LA-053:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **PCL-01**; необходимые пакеты: PCL-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/calibration/continuous.py
policy-engine/src/polisyos/calibration/curve.py
policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py
policy-engine/src/polisyos/scientist/methods/backtesting/calibration_curve.py
policy-engine/tests/unit/calibration/test_continuous.py
policy-engine/tests/unit/scientist/methods/backtesting/test_calibration_curve.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/calibration/__init__.py
policy-engine/src/polisyos/ir/analytics/_truthfulness.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_pcl_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-17. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A13.** No fake pass может быть принято раньше реального bridge. Наличие report с finite CI не calibration evidence; полного завершения LA-051 нет при bridge_pending.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-052

Источник LA_r09, строки 3747–3792; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-052 -->
## LA-052. Calibration curve: старое правило «нет пригодных интервалов — хорошо» пережило перенос в общий пакет

**M — единая политика пригодности входа и измеренного знаменателя, с миграцией отчётов и тестов**

**Точная область:**

`src/polisyos/calibration/curve.py#compute_calibration_curve`;
`src/polisyos/calibration/continuous.py#_prepare_interval_sets/evaluate_continuous`;
`src/polisyos/ir/analytics/calibration_diagnostics.py#CalibrationDiagnosticsReport.to_truthfulness_receipt`;
`tests/unit/scientist/methods/backtesting/test_calibration_curve.py#test_empty_intervals`.

**Статус.** Полные numerical modules, IR report и `TruthfulnessReceipt` сохранены с совпадающими Git blob SHA и действительно исполнены. Package initialization изолирована; `ValidationSeverity` — точный исходный excerpt. Результаты report/receipt не заменялись фикстурами. [E202–E207, E211–E212]

**Что установлено.** Curve-helper использует `zip(..., strict=False)`, поэтому лишний level или interval set не обязан участвовать. Пустые наборы и наборы с числом интервалов, отличным от числа observations, пропускаются. Если после этого points пуст, возвращаются `ece=0`, `max_ce=0`, `is_well_calibrated=True`. При этом старый тест прямо требует именно такое поведение для empty intervals. Это подтверждённый сохраняемый контракт, а не исключительно гипотетический новый caller.

Более содержательный `evaluate_continuous` уже требует непустой finite `y_true`, отвергает отсутствие обоих источников интервалов, проверяет длины и порядок границ. Но явные `intervals={}` и `intervals=[]` с `levels=[]` проходят: для них цикл проверок пуст. Нулевые показатели curve переходят в настоящий `CalibrationDiagnosticsReport` с `n_obs`, равным длине `y_true`, хотя калибровочных сравнений нет. [E202–E203]

**Полная короткая цепочка воспроизведена:**

```text
100 finite y_true + intervals={}
→ evaluate_continuous: interval_coverage=[]; ece=mce=rmsce=0; n_obs=100
→ CalibrationDiagnosticsReport: has_errors=False; summary содержит VALID
→ to_truthfulness_receipt()
→ runtime/effective tier = approximate_calibrated
   scope = predictive_calibration; status = runtime_only
   evidence_ref = None; degradation_reasons = []
```

Receipt-model реально проверил своё tier reconciliation. Его работа не добавила отсутствующие интервальные сравнения. В report остаётся предупреждение, что PIT пропущен из-за отсутствия predictive samples; оно не является отдельной диагностикой отсутствия всех interval-coverage points. Состояние `VALID` здесь означает отсутствие error-severity issues, не доказанную истинность прогноза. Тем не менее сам `approximate_calibrated` уже является содержательным выходным label, а не только названием теста. [E207, E211; r08-P14–P15]

**Другие различения.** Два interval sets при одном level, либо два levels при одном set, оставили один согласованный point и положительный flag. Если обе пары перечислены полностью и вторая имеет нулевое покрытие при level `0.9`, flag отрицателен. На корректных 100 observations с 95 покрытиями при nominal `0.95` вычисление даёт ECE 0; при отсутствии покрытий — ECE 0.95 и downgrade в unverified. При 10 observations даже пустой результат понижается существующим sample-size guard. Эти контроли отделяют полезную математику от ошибки определения области измерения. [r08-P04–P18]

**Почему это смысловое legacy.** Низкоуровневая старая политика permissive plotting/calculation сохранилась как публичный положительный verdict, была закреплена тестом под прежним Scientist-адресом и стала входом более развитых typed diagnostics/receipt. Здесь не нужно переписывать всю калибровку: нужно перестать превращать отсутствие пригодной измеренной выборки в нулевую ошибку, пригодную для нового label. Точная история происхождения такого правила не устанавливалась.

**Что сохранить.** Математику coverage/deviation, поддержку нескольких уровней и предиктивных samples, bootstrap/PIT/ENCE возможности, действительные Pydantic models, warnings и нормальные результаты существующих вызовов. Старый тип `CalibrationResult` публично экспортируется; его изменение имеет собственный compatibility-контракт. Не удалять numerical tests лишь потому, что они находятся в Scientist.

**С чем объединить.** У существующего calibration owner должна быть одна политика согласования levels, interval sets и observations. В обычном diagnostic-режиме недостающий/лишний член набора — адресная ошибка, а не бесшумное уменьшение проверяемого запроса. Если нужен permissive plotting-режим, он сохраняется явно с inventory пропусков и статусом неполноты, который не используется для positive calibration label. Верхний report и receipt получают сведения о фактически оценённом знаменателе/пригодности; длина массива наблюдений сама по себе не свидетельствует о числе interval comparisons.

**Порядок миграции.** Зафиксировать корректный численный corpus и случаи old permissive behavior. Сначала различить `not_evaluated`, incomplete и evaluated результат — в поддержанном нынешнем report через явную issue/неопределённую метрику либо согласованное расширение типа, не обязательно новый registry. Затем связать receipt projection с установленной пригодностью измерения; нельзя просто поставить глобальный lower threshold на ECE или заменить один `True` на `False`, оставив нули в соседнем пути. Обновить `test_empty_intervals` как намеренную смену контракта и добавить проверку всей короткой цепочки. После переключения клиентов убрать независимые старые acceptance-правила.

**Приёмка.** Empty mapping/sequence, пустой `y_true`, отсутствие интервалов, несовпавшие lengths, лишние levels/sets, полностью пропущенный corpus, частично пригодный corpus, корректное положительное и отрицательное покрытие, small-sample downgrade и report→receipt. Проверять как значения метрик, так и число фактически измеренных points, причины отказа/ограничения и полученный tier. Сохранённые старые receipts не переписывать; обнаруженные старые результаты без основания могут потребовать re-evaluation либо явно ограниченного historical-use, по правилам владельца.

**Приоритет:** высокий; локальная цепочка воспроизводится без моделей, сети или CI. **Граница:** не установлено, что такие receipts реально были опубликованы, приняты другим institution-level gate или использованы production. Scope `predictive_calibration` не расширяется до decision/publication authority.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-052 -->

## Исходное решение LA-053

Источник LA_r09, строки 3793–3815; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-053 -->
## LA-053. Scientist backtesting calibration_curve: перенесённая функция и невыведенный прежний адрес

**C — завершение compatibility; смысловой перенос численных тестов к действующему владельцу**

**Точная область:** `src/polisyos/scientist/methods/backtesting/calibration_curve.py` и импорт в `tests/unit/scientist/methods/backtesting/test_calibration_curve.py`.

**Существующий целевой API:** `polisyos.calibration` — публичные `CalibrationPoint`, `CalibrationResult`, `compute_calibration_curve`. Реализация находится в `polisyos/calibration/curve.py`. README общего пакета закрепляет generic calibration как отдельную роль, не Foundry parameter calibration или DDM drift-monitor calibration. [E203–E206, E208]

**Что установлено.** Старый Scientist-файл содержит только три импорта и `__all__`. Отдельной математики, состояния и преобразования результата в нём нет. Общий package initializer экспортирует те же объекты. Все три identity локально совпали через implementation, публичный API и compatibility-модуль. Однако старый test file действительно импортирует прежний путь; он является положительным consumer. Адресный search не даёт полного нулевого внешнего графа. [r08-P02; E209]

**Что сохранить.** Три публичных объекта, одинаковые значения и exception/return semantics на поддержанном окне, содержательные numerical tests. Нельзя удалять `scientist/methods/backtesting/` целиком или переносить туда S10 decision authority. Alias сейчас полезен как совместимая точка; его наличие не доказывает runtime defect.

**Куда перенести / с чем объединить.** Обычные imports переводятся на публичный `polisyos.calibration`. Численная characterization принадлежит существующему `tests/unit/calibration/`, где уже найден `test_continuous.py`; сопоставить его тесты до объединения, а не копировать всё вторым комплектом. Маленький test идентичности старого адреса можно оставить только на реальное compatibility-окно. После завершения окна проверяется отсутствие retired-поверхности, не успешный импорт пустого tombstone. Новый implementation-файл не требуется.

**Разделение двух изменений.** Локальная замена только import-path в памяти сохранила все четыре текущих test bodies, включая проблемное empty=True. Следовательно, retirement alias **не исправляет LA-052**. Исправление численного/статусного контракта и снятие старого адреса планируются отдельно, даже когда затрагивают общий test file. Одну и ту же работу над tests не учитывать дважды как независимую экономию. [r08-P03, P19]

**Порядок миграции.** Проверить прямой FQN, относительные exports, notebooks, generated public-surface records и внешний API-статус. Переключить обычных consumers и численные tests. Определить фактическое окно совместимости без произвольной sunset-date. Затем удалить только reexport-файл и ненужные related declarations; сохранять history в Git, а не создавать ещё один alias chain. Import общего root может иметь другой startup cost, поскольку он импортирует соседние diagnostics/recalibration; проверить это в штатном окружении, не обещать ускорение от удаления wrapper.

**Приёмка.** Тождественность classes/function и exceptions; прежний корректный corpus; native calibration/backtesting tests; публичные imports и distributions; запрет возврата retired alias после окончания поддержки. В этом проходе четыре существующих тестовых метода выполнены непосредственно в изолированном import-контексте и повторены с изменённым только import. Это не запуск всей repository pytest suite и не full Scientist initialization.

**Приоритет:** небольшой ограниченный C-пакет. Перенос tests — его обязательный смысловой companion, не новая самостоятельная R-карточка. **Прямое D не объявляется:** подтверждён consumer и не обследован внешний compatibility-договор.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-053 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK01 -->
## K01. polisyos.calibration и foundry/calibration

README явно разводит predictive calibration diagnostics/recalibration и parameter calibration симулятора. DDM calibration имеет третью роль: мониторинг drift. Совпадение имени не означает общую заменяемую реализацию.

**Решение:** Сохранить роли; объединять только доказанно одинаковые primitive helpers без переноса ответственности. [E32]

<!-- SOURCE_END LK:LK01 -->

<!-- SOURCE_BEGIN LK:LK30 -->
## K30. Shared calibration — работающий вычислительный владелец, но не готовая полная замена N8 calibration

`evaluate_continuous` действительно использует наблюдения, интервалы и при наличии samples — PIT/ENCE. На проверенном непустом corpus он различает 95% и нулевое покрытие; строгие ошибки lengths/bounds/missing evidence работают. Это положительный материал для миграции, не ещё один placeholder. Но правильный experimental estimand и привязка к выбранному causal method не возникают автоматически из generic функции. Foundry parameter calibration и DDM drift calibration остаются отдельными ролями. [E202–E203, E208; r08-P09–P18]

<!-- SOURCE_END LK:LK30 -->

<!-- SOURCE_BEGIN LK:LK32 -->
## K32. TruthfulnessReceipt исполняет reconciliation, а не повторную калибровку

Полный `_truthfulness.py` проверяет согласованность runtime/declared/effective tier и сохраняет scope. В r08 его настоящая модель приняла `runtime_only / predictive_calibration`. Это не делает модель лишней: входной calibration report передал положительный tier, и receipt не обязан угадывать отсутствующий внешний эксперимент. Исправление LA-052 должно находиться у производителя пригодности и report projection, сохраняя generic reconciliation и не расширяя diagnostic receipt до полномочий на решение. [E207, E211]

<!-- PAGEBREAK -->
<!-- SOURCE_END LK:LK32 -->

