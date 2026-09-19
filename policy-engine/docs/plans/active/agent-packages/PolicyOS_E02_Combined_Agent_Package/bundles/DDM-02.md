# DDM-02 — DDM: актуальное основание и единый gate с R2 override

**E02 · окно CP3 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-054 (M), LA-055 (M).

**Предшественники:** [DDM-01](../bundles/DDM-01.md). **Совместная очередь:** LANE-11.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

После contract-extraction связать existing check_calibration_validity с тем же report/application, effective time и triggers. Согласовать model/detector/calibration/regime/budget/window identities, провести expiry и refs в registry. Следующим behavioral commit определить baseline eligibility, независимые veto и разрешённый R2 signoff; mapper/builder/gate используют одну явную policy projection. Historical pass читается как исторический факт, не бессрочное разрешение.

**Различающие тесты и сохраняемое поведение.** Before/after expiry; model-change trigger; чужая model/regime/calibration/metric budget; позднее событие в разрешённом окне; unavailable feed против observed empty-alert window. Матрица: R4/R3 с veto не разрешены; R2 только с допустимым signoff; R1/R0 и failed certificate не разрешены даже с signoff. Проверить причины/сроки/версию policy и действительные native models, не fixture verdict. Реальный deployment не вызывается.

**Не считать исправлением.** Не ремонтировать gate простым AND, теряющим R2-исключение. Не выдавать bool signoff за доказательство полномочия, FP certificate за predictive calibration, horizon30d за valid_until и текущие часы за время evidence.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-054:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **DDM-02**; необходимые пакеты: DDM-02.

**LA-055:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **DDM-02**; необходимые пакеты: DDM-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/ddm/calibration/audit.py
policy-engine/src/polisyos/ddm/contracts/events.py
policy-engine/src/polisyos/ddm/contracts/metric_budget.py
policy-engine/src/polisyos/ddm/integration/model_registry.py
policy-engine/src/polisyos/ddm/integration/model_registry_gate.md
policy-engine/src/polisyos/ddm/integration/monitor.py
policy-engine/src/polisyos/ddm/readiness/readiness_mapper.py
policy-engine/src/polisyos/ddm/readiness/readiness_policy.yaml
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/ddm/calibration/calibrate.py
policy-engine/src/polisyos/ddm/integration/incident.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_ddm_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** DDM-01. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-10. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A15.** Relocation не исправляет applicability/gate. Нельзя потерять LK35 channel guard, R2 signoff exception, non-overridable failures и actual observation-window precondition.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-054

Источник LA_r09, строки 4053–4107; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-054 -->
## LA-054. DDM: rich calibration/report context сужается до бессрочного pass и несвязанной registry-записи

**M — завершение перехода от автономных status projections к связанному контексту применения**

**Точная область:**

`src/polisyos/ddm/calibration/audit.py#build_calibration_audit/check_calibration_validity`

`src/polisyos/ddm/integration/events.py#CalibrationAudit/ReadinessStateEvent`

`src/polisyos/ddm/integration/monitor.py#DriftAndDegradationMonitor.evaluate_window`

`src/polisyos/ddm/integration/model_registry.py#build_model_registry_record`

Связанные предметные данные — `CalibrationReport`, `CalibrationExpiration`, `StationarityRegime` из `ddm/calibration/calibrate.py`, а также event IDs, detector/calibration/regime refs и `MetricBudgetPolicy`. [E214–E221]

**Статус.** Полные действующие audit, monitor, mapper, registry, event и incident bodies исполнены с настоящими Pydantic-моделями на явно синтетических входах. CalibrationReport и связанные модели взяты точным excerpt, не заменены упрощённым DTO. Сам `calibrate_detector` и реальные stationary streams не исполнялись. Полный product bootstrap, model registry service и deployment отсутствуют в области испытания.

**Что установлено.** `CalibrationReport` хранит `expiration.valid_until` и `invalidation_triggers`. Существующий `check_calibration_validity` учитывает оба. Но `build_calibration_audit` переносит только detector/regime/calibration labels, FP-параметры и исторический holdout `pass`; дата, триггеры и результат проверки в `CalibrationAudit` отсутствуют. Monitor получает именно эту сокращённую запись и не вызывает validity-check. Registry builder снова сужает представление: сохраняет calibration ID, regime и bool `empirical_fp_certificate`; `ReadinessStateEvent.expires_at` и timestamp туда также не попадают. [E214–E217, E220–E221]

**Различающие исполнения:**

| Контрольный вход | Наблюдаемый результат действующих функций |
|---|---|
| Один отчёт, проверка 26 апреля и 19 сентября 2026 года; `valid_until=1 мая` | Existing checker сначала `valid=True`, затем `expired=True`, `valid=False` |
| Два отчёта, отличающиеся только сроком 1 мая / 31 декабря | Runtime audits побайтно одинаковы после одинаковой JSON-сериализации; применимость на 19 сентября разная |
| Непросроченный отчёт и объявленный trigger `model_version_change` | Checker выдаёт `invalidated=True`; historical holdout pass не меняется |
| Просроченный отчёт → audit → monitor с benign degradation → registry → gate | R4, запись разрешает, gate разрешает; existing validity-check при той же дате отвергает |
| Два readiness events с разными timestamp и expires_at | Одинаковая registry-запись: временная граница утрачена |

Это не предъявленные повреждённые production-артефакты: численные значения holdout и события заданы в диагностике. Доказана **несвязанность реально существующих source paths**, а не факт выполненного развёртывания модели. `CalibrationAudit.pass` может оставаться корректным историческим фактом успешного испытания; ошибочно использовать его как достаточную текущую применимость без доступного контекста. [r09-P03–P06, P11]

**Вторая грань того же сокращённого контекста — принадлежность события.** Monitor принимает отдельные `model_id/model_version` и списки уже типизированных events, но проверенные функции не сопоставляют их идентичности. В тесте событие `model-B/v7`, `detector-B`, `calib-B`, `regime-B` вошло в window для `model-A/v1`; registry сослался на отдельно переданный `calib-A`, а R3-gate разрешил переход. Исходная identity не исчезла из `shift_risk_events`, однако она не была согласована с target/registry. Metadata root-cause даже перечислила оба calibration IDs — наличие списка refs не заменяет их binding. [E214–E219; r09-P07]

Аналогично бюджет `model-C/v9/latency` оказался в registry для `model-A/v1`, хотя degradation относилась к accuracy. `_metric_budget_payload` не переносит model identity бюджета, а `map_readiness` использует уже переданный `degradation_event.budget_used`, не пересчитывает его по этому budget. Проверка floor/ceiling внутри самой модели бюджета полезна, но не доказывает соответствие другому событию. Требуется согласовать происхождение и версию рассчитанного budget consumption, а не безусловно пересчитывать его в каждом слое. [r09-P08]

Обратный контроль показал, что смешение субъектов может дать и **ложный блок**: hard DQ failure для B породил R0 и rollback-флаг в payload для A. Самого rollback не было. Ещё один trace сохранил апрельский timestamp degradation, но выдал readiness от 19 сентября с новым семидневным TTL. Это не доказательство, что апрельский факт запрещено использовать: допустимый возраст и окна должны задаваться применимым профилем, а не восстанавливаться из времени вызова. [r09-P09–P10]

**Почему это миграция legacy, а не просьба добавить ещё один if.** Сокращённые интеграционные DTO предполагают, что вызывающий код уже обеспечил целостность субъекта, режима и актуальности. Богатый producer и отдельный invalidation-check уже существуют, но этот предварительный результат не связан с проверенным registry-путём. По мере добавления новых consumers старое предположение становится неявным договором. Исправлять следует boundary и composition, а не сохранять прежний bool и дублировать разные проверки рядом с каждым consumer.

**Что сохранить.** Исторические FP-измерения, declared horizon/alpha, исходные model/detector/regime IDs, stationarity metadata, временные поля и активные причины инвалидирования. Сохранить реальную `check_calibration_validity`, guard отсутствующего evidence channel в shift adapter, разделение drift/degradation/DQ, диагностические записи и incident payload. Нельзя считать generic predictive calibration или Foundry parameter fit заменой DDM false-positive certification.

**С чем объединить.** Переиспользовать текущий validity-owner в `ddm/calibration/audit.py`, связав его результат с **тем же report и тем же применением**, а не передавая произвольный `valid=True`. Composition owner получает report/ref, разрешённый stationarity context, effective time и наблюдённые triggers; согласует model version, detector/calibration/regime и budget с событиями. Конкретный существующий resolver всех этих refs не найден. Небольшой контекстный объект/adapter может потребоваться, но это предлагаемый контракт, не уже готовая новая подсистема.

**Порядок миграции.** Сначала сохранить полный input/decision trace действительного DDM consumer и определить точные обязательные bindings. Подключить existing validity-check до выпуска пригодной для gate проекции; несовпадение или отсутствие обязательного binding выдавать как ограниченный/непроверенный результат, а не как новый FP pass. Затем провести source report/version refs и temporal boundary через registry projection либо оставить их доступными через проверяемую ссылку. Для нескольких детекторов нельзя молча считать один audit общим сертификатом: нужен явный состав соответствующих оснований. Наконец убрать самостоятельный pass-only путь для новых gate-запросов. Historical audit остаётся читаемым, но его текущая применимость не восстанавливается без evidence.

Срок `horizon="30d"` описывает FP-профиль и не должен механически заменять календарный `valid_until` или readiness TTL. Старая запись без срока не становится текущей от назначения сегодняшней даты. Повторный replay фиксирует момент проверки отдельно от времени события; сохранённые source bytes и старые записи не переписываются задним числом.

**Приёмка.** До/после expiry; объявленный и посторонний trigger; новая версия модели при прежнем detector ID; другая модель при той же форме события; несогласованный calibration/regime; несовпавшая metric policy; поздно пришедшее событие в разрешённом окне; утраченная report-ref; несколько детекторов; historical-only mode. Сравнивать inputs, resolved identity, выбранную политику, причины и срок решения. Existing `test_full_acceptance` сохраняется, но его один положительный R1-сценарий не закрывает эти случаи.

**Граница вывода.** Не доказано, что production callers не проверяют всё выше по стеку; полный их census не выполнен. Проверено, что названная автономная цепочка не принимает и не исполняет такое основание. Решение о включении конкретной модели в production не наблюдалось. Это M для живого DDM, не удаление detector, calibration harness или registry.

**Приоритет:** высокий для применения registry-output; переиспользование найденного checker дешевле создания второго механизма истечения. **Основания:** E214–E221, E228, E231; r09-P02–P11.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-054 -->

## Исходное решение LA-055

Источник LA_r09, строки 4108–4140; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-055 -->
## LA-055. DDM promotion: состояние, базовое разрешение и окончательный gate конкурируют за один смысл

**M — консолидация решения при сохранении явной override-политики**

**Точная область:** `ddm/readiness/readiness_mapper.py#map_readiness`, `ddm/integration/model_registry.py#build_model_registry_record/evaluate_registry_gate`; companions — `ReadinessStateEvent`, `ModelRegistryReadinessRecord`, `RegistryGateDecision`, `readiness_policy.yaml`, `model_registry_gate.md`.

**Статус.** Расхождение поля и возвращённого решения воспроизведено на валидированных настоящих моделях. Нормальная матрица R0–R4 и R2 signoff проверена отдельно; это не объявление любого override ошибкой. [E214, E216–E217, E226–E227]

**Что установлено.** Mapper выдаёт `promotion_allowed` по membership в R4/R3. Builder переносит разрешение как `readiness_event.promotion_allowed and calibration_audit.pass_`. Но evaluator не читает `record.promotion_allowed`: после проверки certificate он заново разрешает R4/R3, а R2 — при `owner_signoff=True`. Одно имя `promotion_allowed` таким образом встречается на трёх стадиях с неочевидно разными обязательствами.

**Различающее исполнение.** Настоящая `ReadinessStateEvent` для R4 с явным `promotion_allowed=False` и причиной `fixture_external_restriction` была принята моделью. Builder сохранил `False`. `evaluate_registry_gate` на этой же записи вернул `True` с причиной `R4_promotion_allowed`. Это локальный counterexample согласованности **сохранённого запрета и следующей state-only интерпретации**. Он не доказывает подделку пользовательского решения или действие реального release service. [r09-P12]

**Не потерять существенный контрпример к простому исправлению.** Документ прямо разрешает ограниченное расширение R2 после owner signoff. Поэтому замена gate на `record.promotion_allowed and ...` без различения baseline eligibility и независимого veto ломает заявленный R2-контракт. Прогон пяти состояний подтвердил: без signoff допустимы R4/R3; с signoff добавляется только R2; R1/R0 и любой failed empirical certificate остаются запрещены. Дефект нельзя исправлять отменой всей override-политики. [E227; r09-P13–P14, P16]

**Уточнение входного смысла, не отдельная новая карточка.** При отсутствии всех supplied signals mapper возвращает R4/100 и пустой список active signals. Без audit/budget registry не создаётся; с ними gate может разрешить переход. Такой результат может быть законным для alert-only feed, **если** полнота/доставка наблюдения и актуальная baseline readiness гарантированы выше. Из отсутствия events само по себе не следует, что модель не наблюдалась; но текущий интерфейс не различает «окно наблюдено и отклонений нет» и «данные об окне не переданы». Для использования как deployment gate это предварительное условие должно стать явным. Требовать realized labels в каждом окне без учёта label delay здесь не предлагается. [r09-P15]

**Почему это legacy-кандидат.** Упрощённая state table продолжает служить самостоятельной инструкцией допуска, хотя upstream уже передаёт отдельный decision flag и downstream имеет собственную signoff-ветку. Это остаток параллельных правил одного действия, а не три независимых правильных measurements. Сохранение одинакового bool-имени маскирует переход от классификации к окончательному решению. Вывести следует конкурирующее толкование, не пять операционных состояний.

**Что сохранить.** Численное измерение budget и readiness score, state/reason, action lists, gate result с причинами, обязательный certificate failure и явно объявленное R2-исключение. State, score и readiness observations могут быть отдельными полезными проекциями. Не нужно сводить их в один scalar score, переносить institutional authorization в DDM или объявлять `owner_signoff: bool` доказательством полномочий человека.

**С чем объединить.** В существующем `ddm/readiness`/registry adapter определить одного владельца нормативной для этого API таблицы: базовая eligibility; неотменяемые в данном режиме ограничения; допустимые основания override; окончательный результат. Конкретная операция deployment остаётся за её реальным владельцем. Возможны два честных профиля: upstream flag — обязательный veto, либо явно названная baseline eligibility, которую gate может ограниченно изменить. Выбор требует текущего consumer-контракта, а не произвольной интерпретации одного поля.

`readiness_policy.yaml` сейчас содержит описание условий и actions, а не доказанный исполняемый DSL. В этом проходе проверено совпадение default actions/state promotion с кодом; расхождение YAML с штатным default не заявляется. Не надо немедленно парсить free-text `condition` как код. Возможен один typed policy с генерируемой human-readable проекцией или versioned adapter, но нового universal rule engine для этой задачи не требуется.

**Порядок миграции.** Сначала объявить значение каждого существующего flag и precedence. Закрепить матрицу baseline/override/veto с конкретной причиной и scope. Перевести registry builder и evaluator на согласованный результат; обновить название/схему поля, если его прежнее значение неоднозначно. Только затем снять избыточное самостоятельное state-based решение. Старые snapshots читаются с прежним профилем; на новый final permission они не повышаются автоматически. Observability/precondition описывается рядом с window input и не подменяет FP-certification из LA-054.

**Приёмка.** R4/R3 с явным запретом; R2 без/с допустимым signoff; R1/R0 даже с signoff; failed certificate; действительное empty-alert окно и unavailable feed; несовместимая версия policy; повторное построение result с тем же effective input. Сравнивать не только bool, но и причину, допустимый тип override и сохранённые ограничения. Внешний action не запускать только потому, что payload содержит флаг.

**Граница вывода.** В обычном mapper-produced R4 запись сама выдаёт `True`; counterexample использует разрешённое моделью явно ограниченное событие. Внешние consumers могут считать flag лишь advisory baseline. Это требует явного договора, а не позволяет молча утверждать доказанный runtime bypass. Готовый согласованный replacement для всех callers здесь не найден.

**Приоритет:** ограниченная behavioral-миграция рядом с LA-054. **Различие карточек:** LA-054 сохраняет субъект/срок/основание; LA-055 определяет единственный смысл и precedence решения. Исправление одного не доказывает исправление другого. **Основания:** E214, E216–E217, E226–E228; r09-P12–P17.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-055 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK01 -->
## K01. polisyos.calibration и foundry/calibration

README явно разводит predictive calibration diagnostics/recalibration и parameter calibration симулятора. DDM calibration имеет третью роль: мониторинг drift. Совпадение имени не означает общую заменяемую реализацию.

**Решение:** Сохранить роли; объединять только доказанно одинаковые primitive helpers без переноса ответственности. [E32]

<!-- SOURCE_END LK:LK01 -->

<!-- SOURCE_BEGIN LK:LK14 -->
## K14. DDM monitoring и N11 confidence accounting не являются заменами

DDM monitor действительно составляет shift/degradation/quality/readiness/incident outputs. В просмотренном GY-N11 reuse-census прямо записано сохранить DDM в O2 monitoring family, не копировать его alpha-wealth как durable N9/N11 authority и не считать новый ledger реализацией generic FDR algorithm. Поэтому наличие более развитого accounting-плана **не основание удалить DDM multiple_testing или заменить его импортом Runtime ledger**. [E124–E128]

Это не аттестация FDR-гарантий `OnlineFDRController`: его математическая допустимость в конкретном мониторинговом режиме требует отдельной проверки. Прочитанный план выражает роль и запреты, но не доказывает, что все плановые свойства N11 реализованы и работают сейчас. В r04 ни DDM pipeline, ни N11 runtime не исполнялись. Рассмотренные YAML и Python readiness-представления также не признаны взаимозаменяемыми лишь по соседству и сходству порогов.

<!-- SOURCE_END LK:LK14 -->

<!-- SOURCE_BEGIN LK:LK33 -->
## K33. Существующая validity-проверка нужна; исторический FP pass не равен текущей применимости

`check_calibration_validity` действительно отличает истечение от совпавшего invalidation trigger, сохраняет конкретные причины и допускает непосторонний текущий случай. Два отчёта с одинаковым holdout pass могут иметь разные сроки. LA-054 использует этот действующий owner вместо нового отдельного срока. Проверенный state/gate pipeline не запускает никаких реальных deployment actions; поля incident — инструкции/данные для дальнейшего потребителя. Нельзя описывать локальный `promotion_allowed=True` как состоявшееся развёртывание модели. [E218, E220–E221; r09-P03–P06]

<!-- SOURCE_END LK:LK33 -->

<!-- SOURCE_BEGIN LK:LK34 -->
## K34. R2 signoff, diagnostic-only и drift-only ограничения — намеренные полезные различия

Документированный R2 override не распространяется на failed certificate, R1 или R0. Default actions из YAML и code совпали для всех пяти состояний в конечной проверенной таблице. Diagnostic-only shift исключается из readiness; сильный drift без degradation даёт R2, не R0. Это не пять одинаковых дефектных statuses и не причина заменить весь DDM одним bool. Boolean signoff сам по себе не доказывает identity/authority подписавшего лица: эта внешняя обязанность в r09 не исследована. [E216–E219, E226–E227; r09-P13–P17]

<!-- SOURCE_END LK:LK34 -->

<!-- SOURCE_BEGIN LK:LK35 -->
## K35. Ручная DDM JSON-schema — не пустой generated-дубль

В контроле корректный ShiftDetectedEvent принят и runtime-моделью, и ручной schema. После удаления всех `p_value/e_value/ert` модель и ручная schema отвергли payload, а schema, полученная обычным `ShiftDetectedEvent.model_json_schema()`, приняла его. С другой стороны, reversed window отвергнут runtime-validator, но принят ручной schema: её shape/format правила не выражают сравнение дат. Поэтому ни один из двух путей не объявлен универсально полной заменой другого. Миграция к генерируемой схеме должна сохранять явно кодируемые guards и отличать структурную проверку от cross-field/application validation. [E214, E225; r09-P18–P19]

Этот результат не регистрируется вторым LA-034: здесь нет рекомендации удалить конкретную schema, и hand-written `anyOf` имеет продемонстрированную ценность. Формат дат действительно проверялся `jsonschema.FormatChecker`; отсутствие channel не является побочным эффектом выключенного date-time validation.

<!-- SOURCE_END LK:LK35 -->

