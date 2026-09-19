# FRY-03 — Fiscal/labor: эквивалентный перенос живых PatchMap kernels

**E02 · окно CP4 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-003 (R).

**Предшественники:** [FRY-01](../bundles/FRY-01.md). **Совместная очередь:** LANE-04.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Перенести baseline fiscal/labor execution к согласованному execution owner, обновив точные runtime class paths и exports. До исправления import-direction текущий путь может остаться с явным baseline именем. Numeric модель не заменяется plugin law.

**Различающие тесты и сохраняемое поведение.** Native registry creation, spec→kernel, same patches/key, masked/inactive, fiscal balance/employer/counts. Сравнить старые plans и строковые loads; тесты должны импортировать новый production kernel, не оставленную копию. JAX/gradient один tiny N job.

**Не считать исправлением.** Не удалять живые kernels; не подменять PatchMap EconomicState и не менять шум/налог в relocation-коммите.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-003:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **FRY-03**; необходимые пакеты: FRY-03.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/execute/mechanisms/__init__.py
policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py
policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py
policy-engine/src/polisyos/foundry/mechanisms/__init__.py
policy-engine/src/polisyos/foundry/mechanisms/fiscal.py
policy-engine/src/polisyos/foundry/mechanisms/labor.py
policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/_registry.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_fry_03.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** ECO-01. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-01, MOVE-04. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-003

Источник LA_r09, строки 136–166; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-003 -->
## LA-003. Fiscal/labor: живые kernels ранних базовых моделей

**Перемещение по смысловой роли**

**Статус.** Живой код; кандидат на уточнение профиля и перенос, не прямое удаление.

**Точная область:**

`src/polisyos/foundry/mechanisms/fiscal.py`

`src/polisyos/foundry/mechanisms/labor.py`

`src/polisyos/foundry/mechanisms/__init__.py`

**Что установлено и почему это legacy-кандидат.** IncomeTax/TaxSubsidy эмитируют PatchMap; LaborMarketMechanism заново выбирает занятость по threshold и фирму из равномерного распределения. Это узкие модели, а не универсальный рынок труда. Но каталог уже вызывает эти классы через runtime_mechanism_class_path: это backend зарегистрированных методов, а не забытый независимый методовый каталог.

**Что сохранить.** Patch-first ABI, active/target masks, фискальный баланс, employer IDs, firm labor counts, PRNG key progression и дешёвые контрольные модели. Существующий runtime-каталог уже ограничивает evidence/authority-scope этих методов.

**Куда перенести / с чем объединить.** Предлагаемый src/polisyos/foundry/execute/mechanisms/{fiscal,labor}.py под существующим execute/ как низкоуровневый доменный backend. Методовые adapters остаются в methods/catalog/mechanism/runtime.py. До согласования import-direction допустимо оставить текущий путь, но явно назвать профиль baseline.

**Порядок миграции.** Разделить relocation и изменение модели. Сначала эквивалентный перенос со старым method ID, затем при желании новая версия модели с иной динамикой. Обновить строковые class paths, registry descriptors и exports; не переносить численный код внутрь обёртки ради одного файла.

**Приёмочная проверка.** Регистрация, создание по spec, одинаковые patches/key при фиксированных входах, masked/inactive cases, compiler/replay и существующие fiscal/labor/gradient tests. Новый содержательный закон требует отдельной версии, а не тех же fingerprints.

**Приоритет.** Средняя цена. Выше приоритета косметического выравнивания дерева — точный статус baseline-модели.

**Граница вывода.** Простая модель не является legacy только из-за простоты. Доказательств готовой эквивалентной замены и всех production-вызовов нет; смысловая граница уже частично защищена metadata.

**Основания:** E01, E04, E05, E06.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-003 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK06 -->
## K06. foundry/_registry.py и catalog/mechanism/runtime.py

Registry уже является view над MethodRegistry, а runtime.py связывает method ABI с state-transition implementation. Наличие adapter и kernel оправдано разными ролями.

**Решение:** Не заменять view вторым реестром. Дороговизну повторного построения descriptor-view, если она проявится, исследовать отдельно от retirement. [E01, E06]

<!-- PAGEBREAK -->
<!-- SOURCE_END LK:LK06 -->

<!-- SOURCE_BEGIN LK:LK08 -->
## K08. DomainPlugin не равен FoundryMethodPlugin

State factory, rewards, objectives, lifecycle и observations доменного plugin не покрываются одним методом pure_step. Общая discovery-инфраструктура полезна, но смена entry-point group без bridge меняет ABI. Поддержанные runtime registries могут оставаться отдельными lookup-структурами. [E49, E50, E51, E52, E66]

<!-- SOURCE_END LK:LK08 -->

