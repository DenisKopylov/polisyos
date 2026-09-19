# FRY-01 — Foundry compile/catalog: randomization, families и прямой IR layout

**E02 · окно CP1 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-001 (R), LA-002 (R), LA-037 (C).

**Предшественники:** Нет. **Совместная очередь:** LANE-04.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Три небольших адресных переноса, отдельные коммиты: treasury builder→compile/randomization; family declarations→catalog/mechanism/families; Trinity layout imports→IR kernel.slots без двух hops. Переключить compiler и IC-service один раз. Shared certificates остаются IR-owned; строковые runtime paths и public aliases учитываются явно.

**Различающие тесты и сохраняемое поведение.** Seed=0/nonzero, permutation/recompile/old plan bytes; четыре family IDs/assumptions и unknown ID; пять layout objects identity, native build_slot_layout/family и compiler outputs. Временный facade допускается один прямой, не цепочка; не расширять public exports.

**Не считать исправлением.** Не менять PRNG, slot IDs, model laws или CAS digests при переезде. Не создавать второй registry и не переносить certificates в Foundry.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-001:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **FRY-01**; необходимые пакеты: FRY-01.

**LA-002:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **FRY-01**; необходимые пакеты: FRY-01.

**LA-037:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **FRY-01**; необходимые пакеты: FRY-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/compile/randomization.py
policy-engine/src/polisyos/foundry/compile/trinity_compiler.py
policy-engine/src/polisyos/foundry/mechanisms/design.py
policy-engine/src/polisyos/foundry/mechanisms/treasury.py
policy-engine/src/polisyos/foundry/methods/catalog/mechanism/families.py
policy-engine/src/polisyos/foundry/methods/compiler/layout.py
policy-engine/src/polisyos/foundry/methods/layout.py
policy-engine/src/polisyos/scientist/validation/verification/ic/service.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/ir/analytics/mechanism_design.py
policy-engine/src/polisyos/ir/kernel/slots.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_fry_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-01, MOVE-02, MOVE-03. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-001

Источник LA_r09, строки 82–108; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-001 -->
## LA-001. Treasury: инфраструктура случайности под предметным названием

**Перемещение по смысловой роли**

**Статус.** Семантическое несоответствие подтверждено; удалять функцию нельзя.

**Точная область:**

`src/polisyos/foundry/mechanisms/treasury.py`

**Что установлено и почему это legacy-кандидат.** Файл строит root_seed, node_salts и stream_salts; казначейских потоков и государственных балансов здесь нет. Это не устаревшая вычислительная формула, а живой план воспроизводимости в неподходящей предметной папке. Trinity compiler импортирует build_treasury_plan и сохраняет результат.

**Что сохранить.** Весь алгоритм, включая историческую семантику root_seed=0, стабильные node IDs, формат сериализации и содержимое сохранённых планов.

**Куда перенести / с чем объединить.** Предлагаемый новый файл src/polisyos/foundry/compile/randomization.py в существующей compile/. Не переносить в экономический plugin. Отдельный DTO в contracts/ нужен лишь при действительно нескольких независимых потребителях; пока допустимо оставить модель рядом с builder.

**Порядок миграции.** Сначала перенести без изменения формулы, переключить compiler и tests; временный alias старого import-path — только при подтверждённой необходимости. Python-имя можно менять отдельно от schema/kind: переименование файла не требует переписывать исторические CAS-артефакты.

**Приёмочная проверка.** Сравнить результаты для seed=0 и ненулевого seed, перестановки program nodes, повторной компиляции и чтения старого плана. Проверить код, конфигурации и сохранённые symbol paths; не менять digest ради косметики.

**Приоритет.** Высокая ясность назначения; низкая/средняя цена переноса.

**Граница вывода.** Перенос сам по себе не ускоряет численные вычисления. Полная карта downstream-readers не построена.

**Основания:** E02, E39, E36.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-001 -->

## Исходное решение LA-002

Источник LA_r09, строки 109–135; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-002 -->
## LA-002. Design: каталог семейств рядом с исполняемыми механизмами

**Перемещение по смысловой роли**

**Статус.** Разнородность ролей подтверждена.

**Точная область:**

`src/polisyos/foundry/mechanisms/design.py`

**Что установлено и почему это legacy-кандидат.** В одном namespace с state-transition kernels находятся четыре декларации семейств, параметры, assumptions и solver hints. Сами certify_* уже импортируются из IR. Следовательно, здесь не отдельный полноценный solver, а предметный каталог плюс промежуточный путь доступа к сертификатам.

**Что сохранить.** Идентификаторы четырёх семейств, их параметризацию, предпосылки, catalog view и существующие certificate implementations. get_mechanism_family_spec используется IC-service.

**Куда перенести / с чем объединить.** Предлагаемый src/polisyos/foundry/methods/catalog/mechanism/families.py; родительский каталог существует. Для сертификатов сохранить нынешнего владельца polisyos.ir.analytics.mechanism_design: их копирование в Foundry не является частью этого переноса.

**Порядок миграции.** Свести семейства и методовые descriptors в связанное представление, но не склеивать их идентичности: спецификация семейства не обязательно исполняемый метод. Переключить IC-service, tests и публичные reexports; оставить узкий alias при необходимости.

**Приёмочная проверка.** Сверить catalog IDs, все assumptions и параметры, поведение неизвестного ID; проверить загрузку зарегистрированных runtime-методов и вызовы сертификатов. Факт присутствия в каталоге не должен превращаться в доказательство IC.

**Приоритет.** Высокая семантическая отдача при небольшом объёме.

**Граница вывода.** Наличие четырёх деклараций не доказывает, что они исчерпывают будущие семейства. Не следует считать этот файл дубликатом всех методов каталога.

**Основания:** E03, E40, E06.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-002 -->

## Исходное решение LA-037

Источник LA_r09, строки 2146–2178; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-037 -->
## LA-037. Slot layout: две последовательные compatibility-обёртки после переноса в IR

**C — завершение адресной миграции; перенос алгоритма не требуется**

**Точная область:**

`src/polisyos/foundry/methods/layout.py`

`src/polisyos/foundry/methods/compiler/layout.py`

**Статус.** Оба hop прочитаны полностью; конечный IR-владелец и действующий compiler caller подтверждены. Две обёртки не являются двумя layout-алгоритмами.

**Что установлено.** Внешний `methods/layout.py` вызывает общий `_reexport_module` с target `foundry.methods.compiler.layout`. Сам target импортирует лишь пять объектов из `polisyos.ir.kernel.slots`: три типа и два builder. Таким образом, «канонический» адрес первой миграции уже стал compatibility второго переноса. Trinity compiler всё ещё импортирует `build_slot_layout` через самый внешний путь; документация рекомендует промежуточный, а найденный тест специально сохраняет старую Foundry-поверхность. [E116–E122]

Прочитанный конечный владелец действительно содержит `SlotLayout`, `SlotFamily`, `SlotFamilyManifest`, `build_slot_layout` и `build_slot_family_manifest`. Здесь не предлагается переносить layout в IR заново или заводить четвёртый registry.

**Что сохранить.** Identity типов/функций и семантику builders: пропуск slots без `state_path`, grouping/family inventory, порядок и fallback для global family. Полный численный/execution контракт нельзя заменить одной типовой fixture. Сохранить compiler tests и различие между проверкой текущего поведения и временным условием доступности старого import-path.

**Куда перенести / с чем объединить.** Существующий `src/polisyos/ir/kernel/slots.py` — конечный адрес. Для first-party imports использовать его напрямую там, где import direction уже позволяет IR. Если внешний Foundry facade действительно нужен как стабильный контракт, сохранить **один** осознанный facade с прямыми явными bindings, а не обязательную цепочку двух. Сам `_internal/reexport.py` этим решением не удаляется: есть другие consumers, включая loss facade.

**Порядок миграции.** Переключить Trinity и установленных клиентов, references/API-doc directives и config/FQN consumers. При временной поддержке внешнего адреса сначала направить его прямо к IR; только затем выводить промежуточный wrapper. Закрытие последнего поддерживаемого public facade требует собственного lifecycle-решения. Отрицательные проверки от возврата старого самостоятельного layout-кода оставить у архитектурных/contract tests.

**Фактическая проверка.** r04-P23–P25 исполняют оба точных wrapper и точный reexport-helper с fixture IR objects. Все пять объектов сохраняют identity; внешняя поверхность содержит ровно эти пять имён. Блокирование промежуточного адреса ломает ещё не перенаправленный внешний facade. Настоящий `ir.kernel.slots` в этих probes не исполняется.

**Приёмка.** Native slot-layout/family tests, compiler output и registry defaults, public imports/identity, docs build и package distribution. Проверить именно старые и промежуточные адреса; поиск только `compiler.layout` не найдёт callers внешнего `methods.layout` и наоборот. Переименование Python-пути не меняет сохранённые slot IDs и data manifests.

**Приоритет.** Небольшая по коду, конечная по зависимостям миграция. Ни ожидаемое ускорение Foundry, ни существенное уменьшение объёма данных не заявляются.

**Граница вывода.** IR source прочитан в диапазоне 1–230, включая оба builder, но не весь registry. Положительные caller/test/docs fragments доказывают наличие зависимостей, не их полный перечень. Удалять обе обёртки до миграции известных consumers нельзя.

**Основания:** E116–E122. Локальные проверки: r04-P23–P25.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-037 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK03 -->
## K03. schemas/abi_models.py

В прочитанной части это ABIModelEntry registry со ссылками на настоящие DTO и schema files, а не дублирующие определения этих DTO.

**Решение:** Не переносить весь реестр в один продуктовый домен по числу файлов. Возможность generative consolidation требует отдельной проверки downstream generation. [E35]

<!-- SOURCE_END LK:LK03 -->

<!-- SOURCE_BEGIN LK:LK06 -->
## K06. foundry/_registry.py и catalog/mechanism/runtime.py

Registry уже является view над MethodRegistry, а runtime.py связывает method ABI с state-transition implementation. Наличие adapter и kernel оправдано разными ролями.

**Решение:** Не заменять view вторым реестром. Дороговизну повторного построения descriptor-view, если она проявится, исследовать отдельно от retirement. [E01, E06]

<!-- PAGEBREAK -->
<!-- SOURCE_END LK:LK06 -->

