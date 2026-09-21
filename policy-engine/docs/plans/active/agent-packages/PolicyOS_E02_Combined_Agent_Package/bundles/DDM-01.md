# DDM-01 — DDM: один event/budget owner и lazy parent facade

**E02 · окно CP3 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-056 (R).

**Предшественники:** Нет. **Совместная очередь:** LANE-11.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Сначала исправить parent imports, затем перенести нейтральные event/budget declarations в предложенные contracts/events.py и contracts/metric_budget.py. Все consumers используют один class object; old exports — только forwarding. Сохранить поля, validators, event_type/pass aliases и старый supported profile в relocation commit. ReadinessPolicy/monitor/incident остаются у своих владельцев.

**Различающие тесты и сохраняемое поведение.** Contract-only import с monitor trap не загружает orchestration; root API, все enum/classes, native model validation и JSON forms сохраняются. Проверить __module__/FQN/pickle/schema introspection, когда реально используются. Ручной Shift schema anyOf по p/e/ert сохраняется: generic generated schema не полная замена; reversed window остаётся runtime-check.

**Не считать исправлением.** Не копировать классы в оба места, не переносить DDM в Core и не считать перемещение файла достаточным при eager root. Не удалять ручную schema ради единообразия.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-056:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **DDM-01**; необходимые пакеты: DDM-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/ddm/__init__.py
policy-engine/src/polisyos/ddm/calibration/audit.py
policy-engine/src/polisyos/ddm/contracts/events.py
policy-engine/src/polisyos/ddm/contracts/metric_budget.py
policy-engine/src/polisyos/ddm/detectors/track_2_2_shift_adapter.py
policy-engine/src/polisyos/ddm/integration/__init__.py
policy-engine/src/polisyos/ddm/integration/events.py
policy-engine/src/polisyos/ddm/integration/incident.py
policy-engine/src/polisyos/ddm/integration/model_registry.py
policy-engine/src/polisyos/ddm/integration/monitor.py
policy-engine/src/polisyos/ddm/readiness/readiness_mapper.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/ddm/integration/shift_event.schema.json
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_ddm_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** DDM-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-10. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A15.** Relocation не исправляет applicability/gate. Нельзя потерять LK35 channel guard, R2 signoff exception, non-overridable failures и actual observation-window precondition.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-056

Источник LA_r09, строки 4141–4171; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-056 -->
## LA-056. DDM contracts: нейтральные типы всё ещё входят через integration orchestration

**R — перенос декларативной границы к контрактному владельцу с исправлением parent imports**

**Точная область:** `ddm/integration/events.py` — модели общих событий и перечисления; `ddm/readiness/readiness_mapper.py#MetricBudgetPolicy`; parent facades `ddm/__init__.py` и `ddm/integration/__init__.py`.

**Существующее ближайшее место:** `src/polisyos/ddm/contracts/`. Полное возвращённое дерево этой папки содержит четыре YAML contract/template файла, но не обнаруженный готовый Python event-owner. Предлагаемые `contracts/events.py` и, при оправданном размере, `contracts/metric_budget.py` — **новые возможные файлы**, не существующие implementations. [E222–E224]

**Что установлено.** Сам полный `events.py` зависит только от стандартной библиотеки и Pydantic. Но calibration/audit, detector adapter, readiness mapper и incident/registry обращаются к нему через `ddm.integration`. Этот package initializer импортирует не только типы, но и monitor, registry helpers, incident builders. Root `ddm` также eagerly импортирует monitor. Бюджетная DTO живёт в executable mapper, хотя используется как входной договор window и registry. Разные обязанности расположены и импортируются как единый старый integration surface. [E214–E223]

**Локальная проверка импортной границы.** В временное дерево помещены точные DDM root/integration initializer и event/incident/registry sources. `monitor.py` заменён явно падающим trap. Запрос одной event-модели потребовал загрузки monitor и достиг trap. Перенос копии event-модуля в `contracts/events.py` **без изменения root facade** дал тот же результат: root всё ещё проходит integration. Это не обнаруженный ImportError штатного DDM — trap намеренный; он показывает фактический dependency path. [r09-P20–P21]

В отдельном минимальном контроле с нейтральными parent shells и одним старым reexport-path импорт нового event-owner не потребовал monitor; identity `MetricDirection` через новый и прежний адрес совпала. Все event classes в этом контроле исполнялись из настоящего файла, но проверка identity ограничена указанным enum. Это иллюстрация направления перехода, **не готовый patch полного facade API**. [r09-P22]

**Почему это содержательный перенос.** Контрактный импорт не обязан настраивать или даже загружать исполнение мониторинга, чтобы объявить форму события. Здесь есть реальная нейтральная группа моделей и несколько consumers разных стадий. Выигрыш — независимость contracts и ясное направление зависимости, а не изменение математического detector. Само существование `integration/events.py` не универсальная ошибка архитектуры; кандидат обусловлен именно обнаруженными eager parents и шириной использования типов.

**Что сохранить.** Идентичность поддержанных классов/исключений, enum values, event_type literals, aliases `pass/pass_`, runtime validators, on-disk/wire forms и export list на объявленное окно. Сохранить настоящий monitor/incident/registry у integration-owner. `ReadinessPolicy` как правило поведения не обязана автоматически переехать вместе с `MetricBudgetPolicy`; сначала отделить действительно декларативный входной договор.

**Порядок миграции.** Снять public/type/config consumers и стоимость настоящего root import. Сделать `ddm` и при необходимости старую integration facade явными/lazy так, чтобы новый contract import не входил обратно в orchestration. Затем перенести event/budget declarations без изменения полей и validators, переключить adapter/calibration/readiness/monitor и оставить минимальные нужные exports прежнего пути. Common уже демонстрирует текущий lazy-submodule подход, который можно рассмотреть как организационный образец; его реализация не является готовой DDM facade. [E230]

Не дублировать классы в двух файлах: нужен один объект и forwarding на период совместимости. При физическом переносе `__module__` может измениться — отдельно проверить сохранённые FQN, pickling, schema introspection и plugins, где они действительно используются. Удаление старого alias после конечной миграции consumers — companion этой R-карточки, не ещё одна C-находка ради счёта.

**Сопутствующие схемы не объявлены мусором.** Ручная `shift_event.schema.json` содержит `anyOf` для наличия хотя бы одного численного evidence channel. Обычная Pydantic JSON-schema генерация из текущей модели не воспроизводит этот after-validator. Поэтому перенос Python DTO не даёт права удалить schema-файл или заменить его чистым generated output без semantic comparison. Подробный отрицательный контроль — K35. [E225]

**Приёмка.** Contract-only import при trap/отсутствии runtime execution dependency; обычный public root import; все прежние public models и values; event model validation; JSON output schema; настоящие DDM tests; typing/import-cycle checks; обнаруженные сериализованные FQN. Миграция LA-054/055 может добавить поля/правила позже, но первый relocation-коммит должен сохранять старый supported profile.

**Граница вывода.** Не измерены импортное время, память, wheel/sdist и весь граф packages. Не утверждается, что DDM сейчас падает при обычном импорте. Не предлагается переносить DDM events в глобальный Core или удалять integration. Переход устраняет конкретную dependency-связь, не «все import cycles» проекта.

**Приоритет:** умеренная цена, лучше выполнять маленьким contract-extraction шагом. **Основания:** E214–E224, E230; r09-P20–P22.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-056 -->

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

