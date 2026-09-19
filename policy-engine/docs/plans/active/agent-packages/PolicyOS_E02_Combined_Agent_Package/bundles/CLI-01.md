# CLI-01 — Runtime client: package-owned генерация и снятие raw committed surface

**E02 · окно CP6 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-043 (C), LA-044 (R).

**Предшественники:** Нет. **Совместная очередь:** LANE-12.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Перенести разрешение schema-tool к package/workspace build owner на закреплённой существующей версии; согласовать lock и isolated provisioning. Обычные tests направить к public canonical client; checker/генератор используют один OpenAPI input, включая --openapi. Raw TS/JS сначала перевести в scratch для существующего canonicalizer, затем снять committed outputs и обновить generated inventory/freshness. Dashboard downstream formatting сохраняется своим явным профилем.

**Различающие тесты и сохраняемое поведение.** Один bounded frozen install при реальной необходимости и одна full-family регенерация в N/CP6. Public operation/type surface, binary response/exposure headers, query/path/body/errors, discriminated aliases; corruption/missing/extra каждого supported output, custom OpenAPI и UNRUN. Isolated output root, canonicalizer idempotency/collision guard; consumer без dashboard runtime. Не считать byte equality исполнением всех endpoints.

**Не считать исправлением.** Не удалять raw до scratch handoff, canonicalizer/recursive normalizer или existing full-set freshness guard. Не обновлять toolchain версии и весь lockfile автоматически; не запускать несколько Node builds/installs параллельно.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-043:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **CLI-01**; необходимые пакеты: CLI-01.

**LA-044:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **CLI-01**; необходимые пакеты: CLI-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/apps/runtime-dashboard/scripts/generate-api-client.sh
policy-engine/architecture/generated_artifacts.toml
policy-engine/packages/runtime-api-client/package.json
policy-engine/packages/runtime-api-client/runtimeApiClient.js
policy-engine/packages/runtime-api-client/runtimeApiClient.test.mjs
policy-engine/packages/runtime-api-client/runtimeApiClient.ts
policy-engine/packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs
policy-engine/packages/runtime-api-client/scripts/generate-runtime-api-client.sh
policy-engine/tools/devx/architecture/guardrails.py
policy-engine/tools/ops_runners/runtime/check_runtime_api_contract.py
```

**Читать как соседние контракты:**

```text
policy-engine/packages/runtime-api-client/README.md
```

**Предлагаемый отдельный regression-файл:** `policy-engine/packages/runtime-api-client/remediation.test.mjs`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Уточнение путей:** Workspace lockfile и actual generated output names определяет I1 по checkout один раз; после этого добавляет конкретные paths в write lease до изменения. В плане не выдумывается имя отсутствующего lock.

**Условия общего использования:**

**A16.** Удаление committed raw client после scratch handoff и всех retaining consumers. Generated checks пользуются одним input/output family; build/caller/lifecycle обязательства не исчезают по истёкшей дате.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-043

Источник LA_r09, строки 2933–2967; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-043 -->
## LA-043. Runtime API client: публичный twin сменился, а старый generated-адрес остался обязательным

**C — завершение compatibility-миграции сохраняемых промежуточных артефактов**

**Точная область:**

`packages/runtime-api-client/runtimeApiClient.ts`

`packages/runtime-api-client/runtimeApiClient.js`

Обязательные companions: `scripts/canonicalize-runtime-client.mjs`, `scripts/generate-runtime-api-client.sh`, `runtimeApiClient.test.mjs`, `package.json`, `tools/ops_runners/runtime/check_runtime_api_contract.py` и соответствующие generated-artifact declarations.

**Статус.** Переход публичной поверхности подтверждён README и package exports; retaining consumers подтверждены исходниками checker и теста. Это не два независимо написанных HTTP-клиента и не безусловный D-кандидат. [E156–E160, E176]

**Что установлено.** Package `main`, `types` и root `exports` направлены в `canonicalRuntimeApiClient.*`. Канонизатор заменяет тела совпавших schema DTO на ссылки в `types.ts`, сохраняет несхемные helpers и client class, а JavaScript получает форматированием raw JS. Общая shell-команда выпускает пять файлов: schema types, raw TS/JS и canonical TS/JS. README прямо называет raw pair compatibility-артефактом для прежнего checker. Однако фактические tests тоже импортируют raw JS: общий `createClient` использует именно его, а отдельные проверки работают с canonical либо обеими версиями. Поэтому одного изменения checker недостаточно для retirement. [E156–E160, E176]

Отдельная `_check_runtime_client_drift` по-прежнему регенерирует и сравнивает только raw TS/JS. В локальном контроле она обнаружила изменённый raw TS и отсутствующий raw JS, но не изменила результат после одновременной порчи `types.ts` и обоих canonical-файлов. Это **граница одной команды**, не отсутствие общей freshness-защиты: действующий `guardrails._measure_required_generated_artifacts` уже измеряет фактически выпущенный набор, его регистрацию и совпадение bytes. См. K21. [E160, E162]

В том же checker обнаружена ещё одна граница старой композиции: `--openapi` передаётся в OpenAPI comparison, но raw-client helper заново выбирает стандартный `schemas/runtime_api_v1.openapi.json`. В диагностике main с `custom.json` comparison получил custom-путь, тогда как реальный subprocess с fixture-generator прочёл default. Native OpenAPI app не запускался; это проверка маршрутизации аргумента, а не установленный production drift.

**Что сохранить.** Публичные типы и discriminated schema aliases, runtime methods, query/path/header/body encoding, binary response handling, ошибки и constructor options. Сохранить содержательные tests: среди прочего текущий тест проверяет точные exposure headers и bytes ответа; их нельзя удалить вместе с raw import. Канонизатор — полезный этап, а не бессодержательный файл. Сохранить различение `UNRUN`, drift и успешного измерения.

**С чем объединить.** Существующая package-owned генерация и общий generator-observed freshness-механизм. Первый ограниченный шаг — направить обычные behavioral tests к публичному canonical entrypoint; временный raw/canonical differential test оставить только там, где он защищает реальный переход. Затем raw pair может стать временным внутренним результатом генератора, а не отдельными committed outputs. Это **предлагаемая миграция**, сейчас raw-файлы ещё сохраняются и потребляются. Нельзя просто перестать их писать: канонизатор читает raw TS/JS, поэтому сначала требуется scratch/staging-путь либо эквивалентный in-memory handoff.

**Порядок миграции.** Зафиксировать публичный operation/type surface и всех прямых raw consumers; перевести tests и standalone verifier на действительный поддерживаемый набор; согласовать единый schema input, включая override либо его явное ограничение; перенести промежуточные outputs в управляемый scratch; обновить generated registry, output probes, lint/architecture lists и документацию. Лишь затем удалить committed raw-файлы. Существующий полный freshness-probe переиспользовать, а не писать третий независимый checker. Не повышать byte agreement до доказательства endpoint execution.

**Фактическая проверка.** r06-P02–P07 исполняют точные тела checker и настоящий subprocess во временном дереве; generator и OpenAPI rendering — fixtures. P08–P09 исполняют настоящий JavaScript canonicalizer на Node: schema alias заменён, helper и client tail сохранены, повторный вызов идемпотентен, alias collision и отсутствие client отвергнуты. Неиспользуемый импорт Prettier заменён trap; форматирование и настоящий многотысячный generated-client corpus не выполнялись.

**Приёмка в проекте.** Полная регенерация от закреплённого OpenAPI; порча каждого поддерживаемого output, лишний и отсутствующий output; публичный import; package type tests; existing HTTP request/response tests; старые direct imports в разрешённое окно; `--openapi` и skip-mode; output-root isolation. Реальный raw-generator остаётся владельцем исполняемой механики до согласованной замены, независимо от удаления промежуточного filename.

**Граница вывода.** Не установлены все внешние filesystem imports и не аттестована корректность всех API operations. Общий guardrails-проход и repository Node tests в r06 не запускались. Нельзя формулировать вывод как «весь canonical client не проверяется»: подтверждён более широкий действующий механизм. [E162–E164]

**Приоритет:** небольшой первый шаг с test imports; умеренная миграция generated-family. **Основания:** E156–E164, E176; r06-P02–P15.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-043 -->

## Исходное решение LA-044

Источник LA_r09, строки 2968–2998; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-044 -->
## LA-044. Генератор клиента уже принадлежит package, но schema-tool по-прежнему разрешается через dashboard

**R — перенос build-зависимости к фактическому владельцу генерации**

**Точная область:**

`packages/runtime-api-client/scripts/generate-runtime-api-client.sh`

`packages/runtime-api-client/package.json`

Связанные поверхности: `apps/runtime-dashboard/scripts/generate-api-client.sh`, workspace dependency/lock records и isolated-probe provisioning.

**Статус.** Направление tool-resolution подтверждено точным shell и native command trace. Это кандидат на упрощение владения сборкой, **не установленная неисправность текущего workspace** и не runtime import-cycle.

**Что установлено.** Первым содержательным шагом package-generator запускает `corepack pnpm --dir <project>/apps/runtime-dashboard exec openapi-typescript`. В полном `runtime-api-client/package.json` такого devDependency нет. Таким образом, источник клиентских DTO находится в общей схеме, публичный клиент — в package, а место разрешения generator dependency остаётся у одного из приложений-потребителей. Dashboard имеет собственную downstream-команду, использующую тот же schema-tool и package-owned recursive normalizer, затем Prettier. Различие последнего formatting-step запрещает объявить оба сегодняшних outputs побайтово одинаковыми без измерения. [E157, E159, E161]

**Что сохранить.** Frozen workspace toolchain и lockfile semantics, версии schema generator и formatter, recursive normalizer, порядок этапов и output-root isolation. Сохранить возможность build-time использования tools без загрузки React/Vite в runtime consumer. Package README обещает лёгкую клиентскую поверхность; это не обещание полностью независимой установки всех development-tools.

**Куда перенести.** Разрешение schema generator логично закрепить за `@polisyos/runtime-api-client` либо явным существующим workspace build-owner, доступным всем generators. Конкретный рекомендуемый вариант — package devDependency и package-relative exec; версия берётся из действительного workspace lock, а не назначается по памяти и не обновляется автоматически. Dashboard generation становится downstream-проекцией/совместимым адаптером общего этапа. Новый UI-пакет или централизованный mega-builder не требуется.

**Порядок миграции.** Сначала зафиксировать используемые resolved версии и output corpus. Перенести declaration/resolution без обновления алгоритмов, проверить frozen install и обе команды. Перепроверить isolated freshness environment: нынешний guardrails специально подготавливает private environment и связывает необходимые node_modules. Снять dashboard-generation dependency можно только после адаптации этого provisioning. Удаление старого raw pair из LA-043 не является обязательным предварительным условием: направление build dependency можно исправить отдельно.

**Фактическая проверка.** r06-P10 исполняет точный shell через настоящий Bash; `corepack`, `node` и `<repo>/.venv/bin/python` заменены command recorders. Зафиксированы четыре вызова, dashboard cwd-аргумент, source-schema path и отдельные output destinations. P11–P13 проверяют output-root и отказ неизвестного/неполного аргумента до любых tool calls. P14 фиксирует три вызова downstream shell, включая общий normalizer и дополнительное форматирование. P15 проверяет полное package declaration. **Настоящие pnpm install, TypeScript generation и formatter здесь не запускались.**

**Приёмка.** Frozen install после изменения lock declarations; обе генерации на том же OpenAPI; byte/type equivalence выбранного профиля; минимальный consumer без dashboard runtime; общий freshness-probe в изолированном source tree. Не удалять app dependency, пока она нужна его собственной downstream-команде; не считать перенос declaration причиной менять весь lockfile.

**Граница вывода.** `PROJECT_ROOT/.venv/bin/python` не объявлен ошибкой сам по себе: прочитанный общий probe создаёт соответствующий private-environment link. Ни отказ package install, ни ненужность dashboard как приложения не установлены. [E162]

**Приоритет:** ограниченное улучшение сопровождения, ниже содержательных input-binding миграций. **Основания:** E157, E159, E161–E162; r06-P10–P15.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-044 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK16 -->
## K16. Runtime Reference Shell — отдельный diagnostic consumer, не прежний frontend redirect

В отличие от пустого `frontend/` из LA-013, проверенное дерево `apps/runtime-reference-shell` содержит приложение, стили, package/config, tests и architecture check. README описывает узкую static diagnostics UI без полного dashboard toolchain; прочитанный helper реально вызывает `client.listGovernedProjections()` и возвращает available/unavailable. Это положительная самостоятельная роль, не вывод о production-готовности shell. [E131–E132]

Код всего `app.js`, dashboard и generated client в этом проходе не сравнивался; equivalence их функций не доказана. Рекомендуемое действие — сохранить разницу «минимальный diagnostic consumer / product dashboard», а не удалять второе приложение по количеству UI-корней. Команды из README здесь не запускались.

<!-- SOURCE_END LK:LK16 -->

<!-- SOURCE_BEGIN LK:LK21 -->
## K21. Полная generated-output freshness-проверка уже существует

В нынешнем `tools/devx/architecture/guardrails.py` есть `_measure_required_generated_artifacts`: выделение required families, isolated source/environment, запись генераторов в scratch, перечисление фактически выпущенных files, проверка единственного зарегистрированного owner, bytes, лишних/недостающих outputs и worktree escape; неисполненные измерения отделяются через `GeneratedArtifactCheckUnrunError`. Поэтому ограниченный raw checker из LA-043 **не доказывает репозиторного отсутствия canonical freshness gate**. Общий механизм — кандидат для переиспользования при retirement старого checker-path. [E162]

Журнал 2 сентября описывает запуск полного набора и positive corruption test; это исторический результат автора журнала, не наш повторный запуск. В r06 общий механизм прочитан по указанным диапазонам, включая полное тело измерения, но не исполнен. Не повышать source inspection до подтверждения свежести текущих пяти файлов. [E164]

<!-- SOURCE_END LK:LK21 -->

<!-- SOURCE_BEGIN LK:LK22 -->
## K22. Канонизатор и recursive normalizer не равны лишней копии клиента

Канонизатор действительно устраняет независимые DTO bodies в публичной поверхности и привязывает aliases к schema types; его коллизионные/структурные отказы проверены локально. Обе shell-команды явно используют recursive-type normalizer. Даже при снятии raw committed pair нужно сохранить эти обязанности либо доказать их эквивалентное выполнение в текущем generator. Одно совпадение имён файлов и строковых методов такой эквивалентности не устанавливает. Нормализатор содержательно не аудирован и здесь не запускался. [E158–E159, E161]

<!-- SOURCE_END LK:LK22 -->

<!-- SOURCE_BEGIN LK:LK23 -->
## K23. Небольшой terminal styleguide и RuntimeMiddlewarePlugin — не мёртвые CLI/плагины

Полное дерево `packages/cli` показывает библиотеку styleguide; package export — `./styleguide`, а не executable `bin`. Прочитанные tokens и format-status формируют ASCII status/progress strings. Отсутствие исполняемой CLI-команды не противоречит этой узкой заявленной роли. Независимая проверка истинности `verified` не обещается самим formatter; статус передаёт вызывающий код. Не переносить туда Runtime admission и не удалять библиотеку только из-за названия. Реальные consumers, Unicode display-width и полнота её temporal presentation требуют отдельного исследования. [E171–E173]

`runtime/extensions/api.py` определяет runtime-checkable Protocol с metadata/create. Это маленькая публичная типовая граница, не незавершённая concrete middleware implementation. Consumer census и extension lifecycle не выполнены, поэтому файл не добавлен в D-очередь. [E174–E175]

<!-- SOURCE_END LK:LK23 -->

