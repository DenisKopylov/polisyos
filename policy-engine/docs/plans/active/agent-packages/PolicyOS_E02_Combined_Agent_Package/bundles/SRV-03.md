# SRV-03 — Autotune: native SearchService driver и ограниченный cutover

**E02 · окно CP3 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-015 (M).

**Предшественники:** [SRV-01](../bundles/SRV-01.md), [CTL-02](../bundles/CTL-02.md), [STP-01](../bundles/STP-01.md). **Совместная очередь:** LANE-02.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Создать native ask/tell driver у текущего methods/search owner, переиспользуя извлечённый state transition, стратегии, stopping и funnel ports. Переключить один реальный autotune consumer. Снять старый full-loop только после trace parity и конечного caller/lifecycle scan; сохранённые histories получают совместимый reader, не новую трактовку.

**Различающие тесты и сохраняемое поведение.** Два кандидатных сценария: обычное завершение и warm→sentinel→empty/error→resume. Совпадают effective requests, расходы, history/frontier, partial outcomes; B118–127 исправленные controls не теряются при cutover. Отдельно typed result, RNG и negative admission. Не требовать равенства с доказанно неверным старым поведением.

**Не считать исправлением.** Не писать второй search framework с копией старого loop и не удалять все methods/search. Неперенесённый поддержанный consumer означает compatibility_pending, не разрешение rm.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-015:** Этап 2/2 и accountable closure: native driver, actual autotune caller, lifecycle. CTL-01 извлечение и CTL-03 корректность переходов обязательны. Accountable closure: **SRV-03**; необходимые пакеты: CTL-01, SRV-03.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/scientist/methods/autotune/runtime.py
policy-engine/src/polisyos/scientist/methods/search/adapters.py
policy-engine/src/polisyos/scientist/methods/search/controller.py
policy-engine/src/polisyos/scientist/methods/search/service.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/scientist/methods/search/frontier.py
policy-engine/src/polisyos/scientist/methods/search/stopping.py
policy-engine/src/polisyos/scientist/methods/search/strategies/base.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_srv_03.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** CTL-01, CTL-03, OPT-02, OPT-04, SRV-01. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-05, MOVE-06. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A11.** Native search cutover не копирует private mutation и сохраняет все принятые B fresh/empty/cost/typed controls. LA-015 закрывается после проверки реального consumer, не появления protocol.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-015

Источник LA_r09, строки 482–512; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-015 -->
## LA-015. SearchController: живое legacy-ядро, требующее поэтапного замещения

**Слияние / разделение ответственности**

**Статус.** Legacy-роль и production-source caller подтверждены.

**Точная область:**

`src/polisyos/scientist/methods/search/controller.py`

`src/polisyos/scientist/methods/search/frontier.py`

`src/polisyos/scientist/methods/autotune/runtime.py`

**Что установлено и почему это legacy-кандидат.** Контроллер поддерживает старый монолитный loop; autotune/runtime действительно создаёт SearchController. Protocol ask/tell не доказывает наличия второго полноценного loop, уже покрывающего stopping, warm-start, sentinels и историю. Сохранение старого драйвера лишь ради зрелого consumer — типичный случай живого legacy, а не unused code.

**Что сохранить.** Проверенные сценарии, историю, причины остановки, evaluator ports, sentinel roles, бюджетные ограничения и частичные результаты. Стратегии и funnel не нужно выносить или переписывать вместе с driver.

**Куда перенести / с чем объединить.** Текущий владелец methods/search/ и SearchService-contract. Предлагаемая extraction: state transition и run state под тем же владельцем, затем native ask/tell driver; autotune/runtime переводится на этот сервис. Это план миграции, не ссылка на якобы уже готовый advanced implementation.

**Порядок миграции.** Снять characterization traces по фактически используемым сценариям. Выделять операции без смены поведения, переключать одного consumer и только затем выводить full-loop API. Отдельный retirement для старых serialized histories и import names.

**Приёмочная проверка.** Новый запуск/продолжение, stopping, warm-history, пустое предложение, sentinel, отказ evaluator и совпадение final/history/frontier на известных сценариях. Проверить не только число итераций, но и предмет оценивания.

**Приоритет.** Высокая полезность, высокая цена; не первая cleanup-волна.

**Граница вывода.** В этом проходе перечитан contract и подтверждён caller; весь controller/runtime повторно не исполнен. Нет основания удалить весь methods/search, содержащий работающие современные компоненты.

**Основания:** E27, E28, E37.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-015 -->

