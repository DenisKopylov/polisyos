# HYG-04 — Bootstrap/benchmark wrappers и frontend redirect: конечная миграция

**E02 · окно CP6 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-011 (C), LA-012 (C), LA-013 (D).

**Предшественники:** Нет. **Совместная очередь:** LANE-12.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Перевести точные consumers install.sh/jax_bootstrap.py, трёх benchmark wrappers и redirect-only frontend README на canonical owners. JAX env defaults применяются до импорта, overrides не теряются. Проверить реальные lifecycle notices; просроченная дата сама по себе не разрешает rm. Каждую небольшой поверхность принимать отдельно, не удаляя соседние рабочие инструменты.

**Различающие тесты и сохраняемое поведение.** Recording command/exit/arguments, early JAX subprocess order без полноценной компиляции, пользовательские env overrides, benchmark object identity и __main__, docs/lifecycle links и package inventory. Реальные apps/runtime-reference-shell, runtime-dashboard и самостоятельные benchmark subtrees сохраняются. Тяжёлая сборка — единый CP6 window, не на каждом alias.

**Не считать исправлением.** Не удалять весь tools/research/benchmarks или apps/packages, не превращать старый bootstrap в поздний вызов after JAX. Не исполнять реальный system bootstrap ради теста и не стирать sunset запись без решения.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-011:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **HYG-04**; необходимые пакеты: HYG-04.

**LA-012:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **HYG-04**; необходимые пакеты: HYG-04.

**LA-013:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **HYG-04**; необходимые пакеты: HYG-04.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/architecture/shims.toml
policy-engine/frontend/README.md
policy-engine/install.sh
policy-engine/jax_bootstrap.py
policy-engine/tools/research/benchmarks/harness.py
policy-engine/tools/research/benchmarks/metrics.py
policy-engine/tools/research/benchmarks/suite_registry.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/common/jax_env.py
policy-engine/tools/devx/workspace/bootstrap.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_hyg_04.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Условия общего использования:**

**A16.** Удаление committed raw client после scratch handoff и всех retaining consumers. Generated checks пользуются одним input/output family; build/caller/lifecycle обязательства не исчезают по истёкшей дате.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-011

Источник LA_r09, строки 368–396; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-011 -->
## LA-011. Install и JAX bootstrap: разные виды переходных entrypoints

**Вывод compatibility после миграции**

**Статус.** Delegation подтверждена; удаление зависит от миграции пользователей.

**Точная область:**

`install.sh`

`jax_bootstrap.py`

**Что установлено и почему это legacy-кандидат.** install.sh уже exec-делегат canonical workspace bootstrap. jax_bootstrap.py добавляет src import path и применяет common.jax_env defaults до импорта JAX. Собственной научной модели нет, но ранний bootstrap имеет значимую точку исполнения. В shims.toml для обоих стоит sunset 2026-08-01, ранее даты аудита 2026-09-18.

**Что сохранить.** Рабочую команду bootstrap и раннюю установку JAX environment. Удаление wrapper не должно менять порядок и момент применения defaults.

**Куда перенести / с чем объединить.** Существующие tools/devx/workspace/bootstrap.py и src/polisyos/common/jax_env.py. Пользовательские команды переводить на canonical CLI; ранний JAX setup — на управляемый bootstrap владельца.

**Порядок миграции.** Проверить README, CI, devcontainers, notebooks, tool entrypoints и внешние setup scripts. Просроченная декларация требует фактического закрытия либо явного решения о продлении; нельзя просто стереть запись sunset.

**Приёмочная проверка.** Доступность минимального bootstrap и профилей, сохранение пользовательских override, subprocess-проверка import-order до JAX. Ранний side effect нельзя переносить в функцию, вызываемую после импорта JAX.

**Приоритет.** Средняя цена при большом внешнем числе клиентов; ниже LA-010 по устранению дублируемой логики.

**Граница вывода.** CI здесь не запускался; истёкшая дата в файле не доказывает, что действующий CI сейчас падает.

**Основания:** E20, E21, E22.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-011 -->

## Исходное решение LA-012

Источник LA_r09, строки 397–427; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-012 -->
## LA-012. Benchmark wrappers: снять второй адрес, не удалить рабочие benchmarks

**Вывод compatibility после миграции**

**Статус.** Три точных alias подтверждены.

**Точная область:**

`tools/research/benchmarks/metrics.py`

`tools/research/benchmarks/harness.py`

`tools/research/benchmarks/suite_registry.py`

**Что установлено и почему это legacy-кандидат.** Эти файлы вызывают expose_module для benchmarks.metrics/harness/suite_registry. Последний также переносит __main__-entrypoint. Они не содержат метрик и benchmark algorithms. Однако соседние jax/, lex/, run_parallel и data preparation не являются этими wrappers.

**Что сохранить.** Канонические benchmarks реализации, suite IDs, generated artifacts и способ запуска. Никакого алгоритма из трёх wrappers переселять не требуется.

**Куда перенести / с чем объединить.** Существующие policy-engine/benchmarks/{metrics,harness,suite_registry}.py. Для команд — их реальный canonical entrypoint, не новый дублирующий runner.

**Порядок миграции.** Заменить source imports, CLI paths и job definitions; проверить конфигурации tools/registry. При переходном периоде wrappers допустимы, но не должны оставаться второй рекомендуемой поверхностью навсегда.

**Приёмочная проверка.** Сравнить импортируемые objects и CLI exit/arguments, воспроизведение suite и документированные пути. Инвентаризировать package целиком перед любым directory removal.

**Приоритет.** Низкая цена по трём файлам, ограниченная выгода для runtime.

**Граница вывода.** Нельзя удалить весь tools/research/benchmarks: в дереве есть существенные самостоятельные инструменты. Полный caller census этих aliases не выполнен.

**Основания:** E23, E24, E25.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-012 -->

## Исходное решение LA-013

Источник LA_r09, строки 428–454; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-013 -->
## LA-013. frontend/: истёкший указатель вместо второго приложения

**Прямая очистка: перенос логики не нужен**

**Статус.** Полный каталог проверен: только redirect README.

**Точная область:**

`frontend/README.md`

**Что установлено и почему это legacy-кандидат.** В проверенном дереве frontend/ один README с redirect_stub=true. Он указывает на apps, packages/runtime-api-client и frontend workspace contract; sunset_date — 2026-08-05. Это уже не старый UI, который нужно портировать, а остаточный адрес после миграции.

**Что сохранить.** Только актуальную навигацию и, при необходимости, внешний redirect старого URL. Никаких компонентов UI в этом каталоге нет.

**Куда перенести / с чем объединить.** Существующие apps/, packages/ и docs/reference/frontend/workspace-contract.md. Исторический Git-снимок остаётся доступным; новая копия frontend не нужна.

**Порядок миграции.** Заменить оставшиеся ссылки, выполнить указанный check_docs_lifecycle, затем удалить README и пустую директорию. Для публично используемых старых ссылок можно временно оставить один redirect с актуальным обоснованием, а не имитировать второе приложение.

**Приёмочная проверка.** Ссылки документации, workspace build paths, packaging include/exclude. Не удалять apps или packages по сходству названий.

**Приоритет.** Низкая цена, прямое упрощение структуры.

**Граница вывода.** Полный фронтенд-код не аудирован: проверена именно эта пустая legacy-директория. Отсутствие кода тут не означает отсутствие старых компонентов внутри apps.

**Основания:** E26.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-013 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK16 -->
## K16. Runtime Reference Shell — отдельный diagnostic consumer, не прежний frontend redirect

В отличие от пустого `frontend/` из LA-013, проверенное дерево `apps/runtime-reference-shell` содержит приложение, стили, package/config, tests и architecture check. README описывает узкую static diagnostics UI без полного dashboard toolchain; прочитанный helper реально вызывает `client.listGovernedProjections()` и возвращает available/unavailable. Это положительная самостоятельная роль, не вывод о production-готовности shell. [E131–E132]

Код всего `app.js`, dashboard и generated client в этом проходе не сравнивался; equivalence их функций не доказана. Рекомендуемое действие — сохранить разницу «минимальный diagnostic consumer / product dashboard», а не удалять второе приложение по количеству UI-корней. Команды из README здесь не запускались.

<!-- SOURCE_END LK:LK16 -->

<!-- SOURCE_BEGIN LK:LK23 -->
## K23. Небольшой terminal styleguide и RuntimeMiddlewarePlugin — не мёртвые CLI/плагины

Полное дерево `packages/cli` показывает библиотеку styleguide; package export — `./styleguide`, а не executable `bin`. Прочитанные tokens и format-status формируют ASCII status/progress strings. Отсутствие исполняемой CLI-команды не противоречит этой узкой заявленной роли. Независимая проверка истинности `verified` не обещается самим formatter; статус передаёт вызывающий код. Не переносить туда Runtime admission и не удалять библиотеку только из-за названия. Реальные consumers, Unicode display-width и полнота её temporal presentation требуют отдельного исследования. [E171–E173]

`runtime/extensions/api.py` определяет runtime-checkable Protocol с metadata/create. Это маленькая публичная типовая граница, не незавершённая concrete middleware implementation. Consumer census и extension lifecycle не выполнены, поэтому файл не добавлен в D-очередь. [E174–E175]

<!-- SOURCE_END LK:LK23 -->

