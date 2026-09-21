# CAU-05 — DiD: dedicated planning, old-slot replay и retirement umbrella

**E02 · окно CP5 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-016 (M).

**Предшественники:** [CAU-01](../bundles/CAU-01.md), [CAU-02](../bundles/CAU-02.md). **Совместная очередь:** LANE-05.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

После общих численных исправлений переключить first-party planning на dedicated Standard/Staggered methods, старые slots/staggered flag преобразовать в однозначный request. Frozen plans читаются своим versioned adapter. Удаление deprecated class/registration только после metadata-detachment и finite FQN/caller scan.

**Различающие тесты и сохраняемое поведение.** Old/dedicated equivalent inputs совпадают после CAU-01/02, shared assumptions/equations доступны без deprecated metadata owner. Unsupported slot/mode не превращается в другой estimator. Registry больше не предлагает retired generic для новых plans; supported historical replay сохранён.

**Не считать исправлением.** Не удалять did.py или numerical helpers. Dedicated class не считается доказательством исправленного CI или статистического покрытия.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-016:** Этап 2/2 и accountable closure; metadata detachment и общие bugfix уже у CAU-01, не повторять. Accountable closure: **CAU-05**; необходимые пакеты: CAU-01, CAU-05.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_cau_05.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** CAU-01, CAU-02. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Условия общего использования:**

**A12.** Metadata-detachment и dedicated cutover не заменяют numerical/inferential fixes; supported old plans и corrected common helpers проверяются вместе.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-016

Источник LA_r09, строки 513–539; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-016 -->
## LA-016. DiD umbrella-wrapper удерживает метаданные новых методов

**Слияние / разделение ответственности**

**Статус.** Deprecated агрегатор подтверждён; новые классы всё ещё зависят от него.

**Точная область:**

`src/polisyos/foundry/methods/catalog/causal/did.py#DifferenceInDifferences`

**Что установлено и почему это legacy-кандидат.** DifferenceInDifferences выбирает standard/staggered по флагу и переводит старые slot names outcome_panel/treatment_indicator. Уже есть StandardDifferenceInDifferences и StaggeredDifferenceInDifferences, но они читают metadata старого класса; общие _run_* helpers тоже берут assumptions из него. Удаление «только deprecated класса» сломает живые пути.

**Что сохранить.** Оба numerical helpers, общий контракт панели, assumptions/citations/equations и alias-mapping старых slots для объявленного перехода. Dedicated methods — более точная интерфейсная декомпозиция, не доказательство исправленной статистики.

**Куда перенести / с чем объединить.** Существующие dedicated classes в том же did.py. Общие определения поднять в независимые module constants либо маленький adjacent shared module только при оправданном размере. Legacy class оставить временным адаптером, затем снять регистрацию.

**Порядок миграции.** Сначала отвязать metadata от deprecated class; мигрировать old FQN, флаг staggered и имена slots в явный dedicated request. Сохранить старое чтение frozen plans по утверждённой версии. Не менять численный estimator в той же relocation-правке.

**Приёмочная проверка.** Одинаковые эффективные запросы обеих оболочек дают одинаковый результат и warnings; registry не предлагает старую generic route для нового планирования; старые replay inputs обрабатываются согласованно.

**Приоритет.** Высокая отдача при средней цене; хороший ограниченный consolidation-пакет.

**Граница вывода.** Это не основание удалять did.py целиком. Переход к dedicated class не исправляет сам собой ранее замеченные inferential-дефекты.

**Основания:** E29.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-016 -->

