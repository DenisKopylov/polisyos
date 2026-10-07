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
