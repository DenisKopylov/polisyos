# API-01 — Причинные фасады: explicit surface вместо отражающих globals

**E02 · окно CP5 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-020 (C).

**Предшественники:** Нет. **Совместная очередь:** LANE-05.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Снять фактический supported export manifest двух пакетов; заменить dir/globals-copy явными bindings. Public/test-facing/случайные имена различить; identity классов и helpers сохранить на объявленное окно. Внутренние тесты переводить к реальным leaf owners, не скрывать коллизии порядком import.

**Различающие тесты и сохраняемое поведение.** Public/star/underscore exports, docs/monkeypatch/FQN, unknown name, incidental new internal import не расширяет API. Реальные causal_engine/interference пакетные imports сохраняются независимо от удалённых sibling файлов.

**Не считать исправлением.** Не удалять все underscore symbols без census, сами packages или их algorithms; не считать один __all__ полноценным retirement всех clients.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-020:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **API-01**; необходимые пакеты: API-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/__init__.py
policy-engine/src/polisyos/foundry/methods/catalog/causal/interference/__init__.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_api_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Ресурс:** L — максимум два таких jobs по всем worktree. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-020

Источник LA_r09, строки 960–989; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-020 -->
## LA-020. Фасады причинных пакетов сохраняют устройство старого монолита

Вывод compatibility после миграции

**Статус.** Compatibility-роль подтверждена; требуется явная миграция поверхности, не удаление пакетов.

**Точная область:**

`src/polisyos/foundry/methods/catalog/causal/causal_engine/__init__.py`

`src/polisyos/foundry/methods/catalog/causal/interference/__init__.py`

**Что установлено и почему это legacy.** После физического разделения модулей фасады копируют globals из dir() внутренних implementation-модулей. CausalEngine экспортирует и имена с одним подчёркиванием; interference объединяет три пространства по порядку, а затем строит __all__ из полученных имён. Это сохранение старого целого namespace вместо определённого интерфейса. Добавление внутреннего импорта может расширить видимый API, не меняя ни одну публичную функцию.

**Что сохранить.** Документированные публичные типы и функции, а также реально поддерживаемые test-facing symbols на согласованное окно. Обратная совместимость здесь может быть намеренной; сам существующий alias не является дефектом.

**Куда перенести / с чем объединить.** Оставить пакеты и их api.py; заменить отражающее копирование явным перечнем экспортов у текущих владельцев. Внутренние тесты постепенно переводить к модулю, которому принадлежит helper. Не нужен новый центральный mega-facade или перенос всех helpers в api.py.

**Порядок миграции.** Снять фактический export manifest и потребителей, различить публичные обязательства, исторические тестовые пути и случайно попавшие imports. Сначала зафиксировать совместимую поверхность, затем выводить лишние имена по решению владельца API. Сохранить identity объектов: wrapper, меняющий класс или исключение, может нарушить ABI.

**Приёмка.** Проверить imports, star-import surface, docs generation, monkeypatch targets и сериализованные FQN. Отдельный тест: внутренний служебный импорт не должен сам менять public exports. На полных initializer-файлах с синтетическими подмодулями подтверждены копирование incidental/private имён и правило «последний одноимённый символ побеждает».

**Приоритет.** Небольшая кодовая правка, средняя миграционная цена из-за возможных внешних потребителей.

**Граница вывода.** Конкретная вредная коллизия в настоящих подмодулях не установлена. Проверен механизм отражения, а не полный список ненужных public symbols. Нельзя удалить все underscore-экспорты без обследования их клиентов.

**Основания.** E43, E44. P04–P05; настоящие initializer, fixture implementation modules.

<!-- PAGEBREAK -->

<!-- SOURCE_END LA:LA-020 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK05 -->
## K05. foundry/methods/catalog/causal/id_engine/

Пакет содержит настоящие core/transport/counterfactual/api; пустой соседний id_engine.py — другой объект.

**Решение:** Удаление LA-007 никогда не распространяется на package. Его доказательную и численную корректность этот legacy-аудит не аттестует. [E11, E12]

<!-- SOURCE_END LK:LK05 -->

<!-- SOURCE_BEGIN LK:LK13 -->
## K13. BERL — не целиком legacy; раскрытый fallback может быть полезен

README закрепляет роль действующей Scientist support infrastructure. Полностью прочитанные kernels выполняют реальное вычисление, а controls показывают зависимость результата от входного background и действующие отказы. Synthetic eligibility rows прямо названы fixtures для smoke/release tests; прочитанный release-report formatter лишь выводит переданные ограничения validation. Это не даёт основания удалить BERL, его benchmarks или весь adapter layer. LA-034 и LA-036 относятся к точным format/identity поверхностям, а не к бесполезности explainability-функции. Сам факт существования narrow fallback допустим; он должен оставаться различимым с запрошенным специализированным методом. [E111–E115, E123, E134–E135]

<!-- SOURCE_END LK:LK13 -->

