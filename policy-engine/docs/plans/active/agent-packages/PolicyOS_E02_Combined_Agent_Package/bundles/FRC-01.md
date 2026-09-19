# FRC-01 — S10: реальные времена и запрет выдуманного calibration pass

**E02 · окно CP1 · локальная проверка L · начальный статус planned.**

**B:** B32. **LA:** LA-051 (M).

**Предшественники:** [CYC-01](../bundles/CYC-01.md). **Совместная очередь:** LANE-03.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

В одном hotspot объединить B32 и LA-051: разделить estimator-shape diagnostics и calibration evidence. Убрать вывод pass_rate=1/coverage=nominal из finite CI, передавать доступный эффект с точным ограничением. Временные роли и refs происходят из своих источников; historical записи не переписываются.

**Различающие тесты и сохраняемое поведение.** Nominal 0.8/0.95 без новых observations не меняет empirical coverage; report None, failed diagnostic, неизвестная history/ссылка не дают calibration pass. Шесть временных ролей не заполняются 2026-06-02 или now. Полезный conditional output и S10 purpose denials сохраняются.

**Не считать исправлением.** Не превращать причинный CI в интервал индивидуального прогноза. Не удалять EvalSafety/WMR/candidate guards. Это честная граница, ещё не готовый measurement bridge.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-051:** Этап 1/2: устранение неподтверждённого pass и временных defaults; реальный совместимый bridge — FRC-02. Accountable closure: **FRC-02**; необходимые пакеты: FRC-01, FRC-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/runtime/quality/design_axes/outcome_prediction.py
policy-engine/src/polisyos/runtime/quality/generation_cycle.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/calibration/continuous.py
policy-engine/src/polisyos/ir/analytics/calibration_diagnostics.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_frc_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** ACQ-01, CYC-01, CYC-02, CYC-03, CYC-04, CYC-05, EMP-01, FRC-02, RES-03, SIM-01. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Условия общего использования:**

**A02.** Эмпирические helpers открываются после scope/uncertainty/graph-binding EMP-01; S10 временная и calibration-семантика — FRC-01/FRC-02. Условный simulation-only путь не ждёт неиспользуемых empirical/calibration функций.

**A13.** No fake pass может быть принято раньше реального bridge. Наличие report с finite CI не calibration evidence; полного завершения LA-051 нет при bridge_pending.

**Ресурс:** L — максимум два таких jobs по всем worktree. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B32

Источник B_r19, строки 607–620; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B32 -->
## B32. Прогноз и калибровка получают одну зашитую дату и оптимистичные значения по умолчанию

*Источник карточки: L:F30. Унаследовано из Library S01; не дублируется с A.*

**Основание:** Вспомогательный путь прочитан; его актуальный production-допуск не доказан. **Происхождение:** P4 — новая находка. **Приоритет:** A до подключения B08. **Охват изменения:** S–M.

**Наблюдение и барьер.** _build_s10_forecast_inputs использует datetime(2026,6,2,UTC) и назначает её нескольким различным временным ролям. Также есть fallback counterfactual_credibility="credible" и floor_passed, выводимый из calibration_status при отсутствии отдельного входа. [L.S24, L.S06]

**Минимальное расширение.** Получать временные роли и основания проверки из реального связанного результата/источника; неизвестное оставлять неизвестным. Для чистой условной симуляции не создавать запись эмпирической калибровки. Старые артефакты не переписывать: новая схема и явный переход.

**Проверка результата.** Расчёт 18 сентября не выдаёт 2 июня как фактическое время наблюдения; отсутствие доказательства credibility не превращается в credible; тесты различают prediction time, observation time, valid time и calibration window.

**Граница вывода.** Не заменять все даты на now: это другая подмена. Наличие helper не доказывает, что такой пакет уже попал в production; данный пункт — обязательная проверка перед оживлением положительной цепочки.

<!-- SOURCE_END B:B32 -->

## Исходное решение LA-051

Источник LA_r09, строки 3712–3746; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-051 -->
## LA-051. N8 → S10: адаптер формы причинной оценки продолжает выполнять роль производителя калибровки

**M — разделение estimator diagnostics и эмпирически обоснованной calibration admission**

**Точная область:** `src/polisyos/runtime/quality/generation_cycle.py`:

`RealValueOwnerGateway.produce_forecast_inputs`, `_build_real_s10_forecast_inputs`, `_s10_calibration_evidence_from_report`, `_build_s10_forecast_inputs`.

**Существующие владельцы для сопоставления:** `runtime/quality/design_axes/outcome_prediction.py` — S10 records, builders и ограничения назначения; `calibration/continuous.py` и `calibration/curve.py` — generic численная диагностика по наблюдениям и предиктивным интервалам. [E200–E204]

**Статус.** Положительный вызов из production-named gateway подтверждён полным прочтением соответствующего метода. Числовой helper исполнен как точный excerpt. Всю `generation_cycle.py`, настоящий Foundry estimator, S10 envelope и конечный N9 admission этот проход не исполняет. Вывод относится к производству входных показателей, не к доказанному выпуску ошибочной production-рекомендации.

**Что установлено.** `_s10_calibration_evidence_from_report` проверяет finite point/CI, finite либо отсутствующий standard error, булевы diagnostics и положительные количества treated/control/pre/post. Если эта проверка выполнена, он назначает `calibration_status="pass"`, `floor_passed=True`, числитель равным `sample_size`, а `pass_rate=1`. Поле `interval_coverage_metric` получает объявленный `confidence_level` отчёта либо `0.95`; поле `calibration_error_metric` — ограниченную сверху относительную ширину CI. Попарных прогнозов и наблюдённых исходов, списка калибровочных испытаний или их результатов helper не получает. [E200]

Это не одно и то же измерение. Объявленный уровень интервала и наблюдаемая доля покрытых исходов имеют разные входы; ширина интервала и ошибка калибровки тоже не тождественны. При этом finite-check и диагностика исходного estimator полезны: они не становятся лишними от того, что их недостаточно для другого вывода.

**Различающее испытание.** На явном mapping, содержащем только поля estimator, helper выдал `pass`, `pass_rate=1`, `interval_coverage_metric=0.95`. Изменение только `confidence_level` на `0.8` изменило названное coverage на `0.8`, не добавив наблюдения. Отдельный настоящий `evaluate_continuous` на 100 исходах вне интервалов дал empirical coverage `0.0` и ECE `0.95`. Последнее — **иллюстрация различия измеряемых величин**, не заявление, что CI причинного параметра следует автоматически проверять как предиктивный интервал индивидуального исхода. Правильный калибровочный корпус должен соответствовать своему estimand и дизайну оценки. [r08-P20–P22]

В `_build_s10_forecast_inputs` дополнительно обнаружена фиксированная дата `2026-06-02 UTC`, которую код использует сразу как prediction, observation, policy-effective, data-valid time и обе границы calibration window. Ссылки `observed_outcome_ref`, `credible_evaluation_evidence_ref` и ряд lineage refs конструируются строками из имеющихся IDs. В прочитанном builder они не разрешаются в эмпирические источники. Это статическое наблюдение текущего исходника; данный builder целиком не запускался и существование всех таких refs во внешнем хранилище не проверялось. Простая замена даты на `now()` не восстановит разные временные роли. [E200]

**Почему это legacy-кандидат.** В orchestration-adapter сохранилось самостоятельное суррогатное производство калибровки рядом с уже существующими владельцами расчёта и S10-records. Название `RealValueOwnerGateway` и вызов S10-builder не превращают локально сочинённые показатели в результат другого производителя. Нужна миграция обязанности, а не перемещение той же формулы в ещё один файл `calibration.py`.

**Что сохранить.** CausalEffectReport, численные оценки и интервалы, estimator diagnostics, knowledge gaps, errors, реальные ограниченные forecast tiers и S10 purpose denials. Нельзя автоматически заменить причинную модель generic predictive-calibration функцией. Нельзя снимать EvalSafety/WMR/candidate checks или считать временный доступ к отчёту сертификатом на production.

**С чем объединить.** Generic вычисление интервал-покрытия/ошибок — существующий `polisyos.calibration`, когда ему передан подходящий корпус. Дизайн калибровочного эксперимента и binding к предсказываемому эффекту должны оставаться у фактического исследовательского/методового владельца. S10 получает проверяемый результат и определяет допустимую ограниченную роль. N8 gateway переносит ссылки, значения, эффективный запрос и отдельные времена, а не создаёт evidence из наличия finite CI. Готового полного bridge от всех Foundry reports к независимой калибровке в этом проходе **не установлено**.

**Порядок миграции.** Сначала переименовать/разделить существующий результат как estimator-shape diagnostics; такие сведения можно сохранять, не называя их calibration pass. Когда действительного калибровочного основания нет, выдавать поддержанное состояние отсутствия/ограничения с причиной, не маскируя его идеальным pass rate. Затем подключить один реальный calibration producer для одного совместимого метода, связать данные, версию модели, правило, калибровочный знаменатель и времена. После переключения потребителей удалить суррогатное ветвление. Исторические записи сохраняются с прежним provenance и явным статусом; их нельзя задним числом назвать измеренной новой калибровкой.

**Приёмка.** Одинаковая форма estimator-report с разными результатами настоящего калибровочного корпуса; изменение nominal confidence без новых observations; отсутствие history; failing diagnostic; неполный/несогласованный calibration record; другой model/rule revision; независимые temporal roles; недоступный reference. Сравнивать происхождение numerator/denominator и фактическое измерение, а не только shape DTO и значение `pass`.

**Отрицательные контроли.** `report=None` даёт `blocked`; явно неуспешная diagnostic даёт `limit` и `floor_passed=False`. Эти защитные ветки воспроизведены. S10-record проверяет согласованность numerator/denominator, ненулевой знаменатель для pass и порядок окна, а S10-назначение явно ограничено. Они полезны, но arithmetic-consistency не устанавливает происхождение чисел. [E201; r08-P23–P24]

**Приоритет:** высокий по смысловой корректности; первый шаг ограничен прекращением неподтверждённого calibration pass. **Граница:** ни обход production admission, ни фактический ущерб пользовательским решениям не установлены.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-051 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK29 -->
## K29. S10-запись, численная диагностика и production admission — разные уровни

S10 models/builders имеют ненулевой знаменатель для pass, арифметическую согласованность, temporal ordering и purpose denials. Generation-cycle value port содержит отдельные EvalSafety/WMR/candidate bindings; путь promotion — отдельные runtime/epoch gates. Они были прочитаны адресно, но не исполнялись в r08. LA-051 не даёт основания удалить эти проверки или утверждать доказанный обход production admission. Устранение суррогатных показателей полезно даже при наличии последующей защиты. [E200–E201]

<!-- SOURCE_END LK:LK29 -->

<!-- SOURCE_BEGIN LK:LK30 -->
## K30. Shared calibration — работающий вычислительный владелец, но не готовая полная замена N8 calibration

`evaluate_continuous` действительно использует наблюдения, интервалы и при наличии samples — PIT/ENCE. На проверенном непустом corpus он различает 95% и нулевое покрытие; строгие ошибки lengths/bounds/missing evidence работают. Это положительный материал для миграции, не ещё один placeholder. Но правильный experimental estimand и привязка к выбранному causal method не возникают автоматически из generic функции. Foundry parameter calibration и DDM drift calibration остаются отдельными ролями. [E202–E203, E208; r08-P09–P18]

<!-- SOURCE_END LK:LK30 -->

