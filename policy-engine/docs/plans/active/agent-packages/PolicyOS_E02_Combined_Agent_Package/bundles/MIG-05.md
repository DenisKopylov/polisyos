# MIG-05 — Common/IR: общая линейная механика, разные migration profiles

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-047 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-06.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Снять callback corpus и матрицу copy/stamp/returned-version/error/no-op identity. Выделить один linear executor внутри Common migrations, сохранив явные facade profiles; IR registry/compatibility negotiation остаются у IR. Переключать по одному потребителю, не унифицируя silently наблюдаемые отличия. Усиление caller isolation или version policy — отдельный behavioral commit.

**Различающие тесты и сохраняемое поведение.** Два шага, missing edge, cycle, duplicate registration, bad result type, conflicting version, nested mutation+failure, source version type, no-op identity и реальные registered callbacks. Профили сохраняют объявленные различия; Data Forge shortest-path/branching/instance state не заменяются линейным engine. Public exception identity проверена.

**Не считать исправлением.** Не импортировать все domain converters в Common, не удалять Data Forge migration registry и не считать один новый shared loop доказательством эквивалентности всех profiles.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-047:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **MIG-05**; необходимые пакеты: MIG-05.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/common/migrations/_engine.py
policy-engine/src/polisyos/common/migrations/base.py
policy-engine/src/polisyos/ir/migrations/base.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/common/migrations/manifest.py
policy-engine/src/polisyos/data_forge/kernel/schemas/migrations.py
policy-engine/src/polisyos/ir/migrations/policy_ir.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_mig_05.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-14, MOVE-15. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A18.** Изменение import-пути не меняет historical bytes/format/ошибки автоматически. Relocation, исправление поведения и прекращение поддержки получают раздельные результаты.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-047

Источник LA_r09, строки 3275–3316; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-047 -->
## LA-047. Common / IR migration engines: один линейный механизм с разошедшимися свойствами

**M — консолидация общей механики при сохранении явных профилей**

**Точная область:**

`src/polisyos/common/migrations/base.py`

`src/polisyos/ir/migrations/base.py` — прежде всего `register_migration`, `migrate_artifact`, `_apply_migration`; не весь registry совместимости схем.

**Статус.** Оба файла прочитаны полностью, сохранены с совпадающими Git blob SHA и исполнены локально. Сходство основной цепочки подтверждено; полной взаимозаменяемости нет. Это продолжение принципа LA-021 для другого механизма, а не повторный счёт двух кодеков. [E178–E179]

**Что установлено.** Оба исполнителя хранят для артефакта одно следующее ребро на `from_version`, проходят версии до target, защищаются от циклов и отсутствующего перехода, проверяют, что callback вернул словарь. Регистрация второго ребра с тем же исходным ключом заменяет первое. Однако критические свойства расходятся:

| Свойство точного API | Common | IR |
|---|---|---|
| Исходный payload | `deepcopy` до обработки и вокруг каждого шага | Callback получает текущий объект без глубокой изоляции |
| Вложенная мутация callback | Не изменяет исходный объект вызывающего кода в проверенном корпусе | Изменяет его; эффект сохраняется и при исключении callback |
| `schema_version`, возвращённая callback | Перезаписывается зарегистрированной target-версией | Несовпавшая явно возвращённая версия вызывает ошибку |
| Тип исходной версии | Требуется `str` | Значение приводится к строке для маршрутизации |
| Совпадение текущей и целевой версии | Возвращается глубокая копия | Возвращается сам исходный объект |
| Декларации direct-read compatibility | Не входят в этот generic runner | Отдельный schema registry и negotiation API |

На общем двухшаговом корпусе, где callback убирает старое поле версии, полезный результат совпал. Но тестовый callback с вложенным изменением `nested.x` оставил исходное значение `0` в Common и изменил его на `7` в IR — как при успешном завершении, так и перед намеренным исключением. Возвращённая версия `9.9` была заменена на `1.0` в Common и отвергнута IR. Это свойства механизмов на явных callbacks, **не утверждение, что действительные зарегистрированные продуктовые миграции уже повредили данные**. [r07-P02–P09]

**Почему это legacy-кандидат.** Общая линейная исполнительная логика поддерживается независимо и получает разные улучшения. Механическое объявление IR «новой заменой» потеряет гарантированную Common изоляцию; обратная замена потеряет IR version checks и его API совместимости. Поэтому исчезнуть должна одна из независимо поддерживаемых копий общей операции, а не предметные rules или публичные ошибки.

**Что сохранить.** Защиту исходных данных, конечность цепочки, различение отсутствующего перехода и неправильного результата, нужные типы исключений, зарегистрированные миграции и их order semantics. IR-owned `SchemaCompatibilityRule`, `negotiate_schema_version` и ограничения major change остаются у IR. Callback mutation может быть фактической частью старого API; изменение её видимости следует объявить, а не выдать за побайтово эквивалентный перенос.

**С чем объединить.** Наиболее узкий путь — использовать существующего нейтрального владельца `common/migrations`, выделив из двух реализаций один проверяемый linear executor. Предлагаемый `_engine.py` внутри этого пакета — возможный новый внутренний файл, **не уже найденная реализация**. Поддержанные facade-профили явно определяют copy policy, stamping/returned-version policy и перевод ошибок; IR сохраняет собственную registry/negotiation composition. На первом шаге достаточно отделить engine от registry, не вводя новый верхний migration framework.

**Data Forge не объявляется третьей удаляемой копией.** Его `SchemaMigrationRegistry` имеет граф с несколькими исходящими рёбрами, instance-local состояние, детерминированный поиск кратчайшего пути и версии из трёх компонентов. Его `apply` документирует shallow copy и не обещает автоматически менять envelope version. Это другой контракт, подробнее K25. Использовать общий низкоуровневый безопасный вызов возможно лишь после согласования этих различий. [E180, E196]

**Порядок миграции.** Снять registry/callback corpus фактических Common и IR потребителей; отдельно записать no-op identity, входную версию, возвращённый stamp, nested state и error contract. Выделить общую механику без изменения этих observable profiles, затем переключить одну facade и её tests. Усиление отдельного свойства оформлять как самостоятельную смену поведения. Не загружать все domain converters в Common и не переносить IR schema compatibility в Data Forge ради количества файлов.

**Приёмка.** Действительный dataset-manifest converter, IR callbacks, no-op, два последовательных шага, отсутствующий переход, цикл, conflicting version, nested mutation + failure, повторная регистрация, внешний импорт exception classes и воспроизведение старых inputs. Если замена меняет profile, сопоставить разрешённые и запрещённые случаи явно; не требовать совпадения там, где намеренно принят новый контракт.

**Граница вывода.** Полный registry всех устанавливаемых расширений и все migration call sites не перечислены. Исполнены полные engine-файлы с синтетическими callback-переходами; не проводилась миграция production snapshots. Direct-read compatibility policy IR не аттестована этими тестами. Готового drop-in successor не установлено.

**Приоритет:** средняя цена; высокая отдача для единообразия сопровождения, но не первая маленькая очистка. **Основания:** E178–E180; проверки r07-P02–P12.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-047 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK25 -->
## K25. Data Forge graph migration не равен двум линейным runners

Полная реализация допускает несколько переходов из одной версии, сортирует исходящие рёбра и строит кратчайший путь. В контрольном графе с двумя равными по длине путями порядок регистрации не изменил выбранные `low → vialow`; повтор exact-edge отвергнут, формат двухкомпонентной версии не прошёл schema validation. Это самостоятельные полезные свойства. Его shallow copy и отсутствие auto-stamping прямо соответствуют описанной функции, хотя их нельзя подменять Common guarantee. **Не удалять registry и не объявлять его готовой заменой Common/IR.** [E180, E195–E196; r07-P10–P12]

<!-- SOURCE_END LK:LK25 -->

