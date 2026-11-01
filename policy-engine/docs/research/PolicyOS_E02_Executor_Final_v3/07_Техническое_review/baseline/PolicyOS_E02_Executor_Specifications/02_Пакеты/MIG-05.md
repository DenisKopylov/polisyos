# MIG-05 — Common/IR: общая линейная механика, разные migration profiles

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-047. Тип: узкий fingerprint fix + compatibility qualification.

Регистрация callback либо действительно сохраняет тот же смысл, либо явно отказывает. Общий traversal уже существует; не заказывать его повторную консолидацию.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/MIG-05.md), [все остатки](../05_Основания/Аудит/01_Реестры/C82_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/MIG-05_исходные_строки.txt), исходный объединённый план §MIG-05 (исторические строки 9544–9664).

## 2. Уже работает — сохранить

- Common run_linear_migration и явные LinearMigrationProfile; Common deepcopy/stamp/str/no-op deep copy, IR live nested mutation/returned-version check/coercion/no-op identity.
- IR strict identical repeat / conflicting repeat / registration cycle refusal; исходный permissive overwrite IR намеренно устарел.
- IR schema compatibility/negotiation и public exception identities отдельны от traversal.
- LK25: DataForge branching BFS shortest path, deterministic tie, instance registry, three-component version, shallow copy и no auto-stamp. S развитие не включать.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C82-R01 | fix: Только genuinely empty closure cell получает marker; stable encoding error не подавлять. | REQ-MIG-05-01 |
| C82-G01 | qualify: Исторические callbacks/extensions и observable profiles требуют реального release corpus, не синтетической уверенности. | REQ-MIG-05-02, REQ-MIG-05-04 |
| C82-G02 | qualify: Supported/installed owner chain, direct-read versus migration и DTO admission проверяются отдельно; DataForge сохранён. | REQ-MIG-05-03, REQ-MIG-05-04 |

### Исходные обязанности, не только новые R

- LA-047 → fix C82-R01 и preserve/qualify REQ-MIG-05-01…-04: один traversal уже есть; снять actual supported callback/import corpus, сохранить profiles и separately verify compatibility/admission.
- LK25 → preserve REQ-MIG-05-03: не удалять DataForge graph registry и не объявлять его взаимозаменяемым с linear engine.

## 4. Нормативный контракт

### REQ-MIG-05-01
В _migration_function_fingerprint ValueError от чтения действительно пустого cell может кодироваться empty_cell; MigrationCompatibilityError от _stable_migration_value должен распространяться без изменения registry. Два unsupported captured objects не могут приниматься как одинаковая регистрация. Supported identical repeat допустим; supported conflicting repeat явно отказан.

Источник: LA-047; аудит: C82-R01; проверки: TEST-MIG-05-01.

### REQ-MIG-05-02
Shared linear runner должен сохранять объявленные Common/IR copy, stamp, returned-version, exception, source-version и no-op identity profiles на двухшаговом переходе, missing-later-edge и callback mutate-then-fail. Strict IR conflict/cycle behavior не откатывается к историческому overwrite.

Источник: LA-047; аудит: C82-G01; проверки: TEST-MIG-05-02.

### REQ-MIG-05-03
DataForge graph route сохраняет shortest path и deterministic tie независимо от order регистрации, instance isolation и свой version/copy/stamp contract. IR compatibility возвращает migration_required отдельно от direct-read; successful callback не заменяет actual DTO admission.

Источник: LA-047; аудит: C82-G02; проверки: TEST-MIG-05-03.

### REQ-MIG-05-04
Supported release composition должна предъявить конечный inventory фактически поддерживаемых callback registrations/import paths и доступных historical inputs с результатами public/installed consumer. Неизвестные внешние plugins/historical corpus обозначаются как незаквалифицированные, не как отсутствующие и не как обязательная бесконечная универсальность.

Источник: LA-047; аудит: C82-G01, C82-G02; проверки: TEST-MIG-05-04.

## 5. Техническое решение и producer → consumer

В ir/migrations/base.py разделить чтение cell и stable encoding: try только value = cell.cell_contents; except ValueError добавить empty_cell; else вызвать _stable_migration_value(value) вне этого except. Существующий MigrationCompatibilityError наследует ValueError: широкий блок ошибочно поглощает его. Fingerprint вычисляется до _REGISTRY_LOCK mutation, поэтому отказ должен оставить snapshot registry неизменным. Не использовать repr/address/hash(object), не silently unwrap неизвестные Config objects. Поддерживаемые closures проходят прежний stable encoder; расширение типов отдельным общим контрактом только при реальном callback.

Registered callback → typed MigrationEdge+fingerprint → Common shared traversal с IR profile → migrated payload → IR compatibility/actual DTO reader. Common facade и DataForge потребляют собственные profiles; общий loop не переносит их semantic ownership. Снять finite list actual imports/registrations из supported distribution, сравнить до/после. Если реальные captures неподдержанны, вынести их стабильную конфигурацию в поддерживаемые immutable/typed значения либо предложить отдельный explicit stable identity contract; не маскировать их empty cell.

### Проверенные owners на срезе
- policy-engine/src/polisyos/ir/migrations/base.py: _stable_migration_value, _migration_function_fingerprint, register_migration, migrate_artifact
- policy-engine/src/polisyos/common/migrations/_engine.py: LinearMigrationProfile, run_linear_migration
- policy-engine/src/polisyos/common/migrations/base.py: Common facade/profile
- policy-engine/src/polisyos/data_forge/kernel/schemas/migrations.py: SchemaMigrationRegistry
- policy-engine/src/polisyos/ir/migrations/policy_ir.py: policy facade

Новый framework и Common overwrite для IR отклонены: механика уже общая, дефект в границе исключения. Унификация IR isolation — отдельная смена публичного поведения, не часть этого fix.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-MIG-05-01
- Уровень: unit + targeted native integration.
- Setup: Closures одного code с разными Config objects; actual empty cell; scalar/dict captures; clean registry snapshot.
- Действие: Сравнить fingerprint и выполнить first/second registrations; затем run actual migration для valid supported callback.
- Точный oracle: Unsupported capture даёт MigrationCompatibilityError до любой регистрации; snapshot неизменен. Empty cell кодируется стабильно. Identical supported repeat принят; differing scalar/dict refused; actual result соответствует зарегистрированному callback, не второму ошибочно принятому.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-05-02
- Уровень: unit + targeted native integration.
- Setup: Одна матрица Common и IR profiles; callbacks two-step, conflicting stamp, bad result, nested mutate-then-raise; public exceptions imported штатно.
- Действие: Выполнить оба фасада через actual shared runner; проверить no-op identity и original nested values.
- Точный oracle: Common original unchanged/deep no-op copy/stamp target/TypeError; IR сохраняет live nested effect/no-op is input и typed version error. Missing edge и cycle не замаскированы успехом. Spy может считать shared call, но output вычисляет настоящий owner.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-05-03
- Уровень: unit + targeted native integration.
- Setup: DataForge два равных пути с reverse registration, два instance; IR schema rule NONE и отдельно доступный migration route.
- Действие: Plan/apply и negotiate; valid/invalid actual DTO read.
- Точный oracle: DataForge low→vialow при обоих orders; exact duplicate и bad version refused; shallow nested identity/no auto-stamp сохранены. IR migration_required=true не выдан за direct-read; invalid DTO refused независимо от conversion success.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-05-04
- Уровень: native/installed integration P-CORE/P-PACKAGING.
- Setup: Supported package/entrypoints, перечисленные реальные callbacks и доступные historical fixtures с hashes; изолированный process.
- Действие: Импортировать supported compositions по объявленным order, invoke actual manifest converter/Trinity helper и current/historical readers; интегрировать с MIG-01/02/04.
- Точный oracle: Все заявленные supported callbacks зарегистрированы либо имеют точный compatibility refusal; profile outputs соответствуют golden semantics. Ненайденные historical inputs не сфабрикованы; список ограничений явный.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_mig_05.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: synthetic callbacks для различения copy/error/identity; wrapping spy только на shared call count. Запрещено: замена stable encoder/fingerprint/registry/DTO, fake historical corpus, mock success вместо installed import.

## 7. Общая интеграция и порядок

MIG-05 — владелец общего linear traversal/profile contract; MIG-01/02/04 используют его без копий. CAN-01 owns canonical bytes, но fingerprint repair не равен смене canonical artifact hash. Сначала narrow regression, затем migration corpus E02-I06-E; CP2 не требует новой реализации уже работающего loop.

Точные общие сценарии: E02-I06-E из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: MIG-01 / MIG-02 / MIG-04: реальные converter/reader witnesses; CAN-01: исторический profile contract; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Поддержанные stable fingerprints не меняются при сужении except; unsupported captures из ошибочно accepted области теперь explicitly refused. Исторические bytes не переписывать. Если persisted snapshot уже содержит such fingerprint, не делать вид, что новый отказ доказывает порчу данных: enumerate affected supported records и отделить read-history от new registration. Rollback не должен вновь объявлять unsupported captures identical.

## 9. Free-grow и design direction

- design_direction.md §2.2, §5 Rule12, §7: новые совместимые converters подключаются через общую механику; новая семантика может потребовать общий профиль, не case branch.
- §4.1, §4.7 / Identity и CTM: version conversion/identity не равны semantic validity/currentness.
- LK25 защищает полезное различие graph vs linear; буквальная минимизация числа файлов не цель.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; хранение не добавляет authority.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-MIG-05-01: inventory supported external callbacks/historical inputs определяет release owner перед acceptance. Выход: конечный список import paths, payload hashes и unsupported scope. Отсутствующий внешний corpus блокирует только соответствующий compatibility claim, не узкий fingerprint fix.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

