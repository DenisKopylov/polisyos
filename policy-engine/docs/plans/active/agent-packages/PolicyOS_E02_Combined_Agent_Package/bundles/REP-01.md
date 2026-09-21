# REP-01 — Runtime replay: прямой Scientist owner без лишнего compatibility hop

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-033 (C).

**Предшественники:** Нет. **Совместная очередь:** LANE-06.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Перенаправить десять root lazy bindings и Core delayed string CLI прямо на Scientist deterministic owner, обновив dynamic inventory и benchmark imports. Сохранить двадцать supported module exports на реальное окно; retirement промежуточного replay.py отдельно от root API.

**Различающие тесты и сохраняемое поведение.** Actual enum/signature/identity; lazy import не грузит runtime до запроса; --check-only и малый persisted replay/resume. Unknown symbol отказывает. Исторические run manifests и runtime/quality/replay.py остаются. Wheel/package validation объединяется с CP6.

**Не считать исправлением.** Не заменять отложенный Core import eager loading и не расширять 10 root имён до20. Не объявлять B checkpoint исправленным переадресацией.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-033:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **REP-01**; необходимые пакеты: REP-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/architecture/imports/dynamic.toml
policy-engine/benchmarks/advanced/common.py
policy-engine/src/polisyos/core/components/_cli_replay.py
policy-engine/src/polisyos/runtime/__init__.py
policy-engine/src/polisyos/runtime/replay.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/runtime/manifest.py
policy-engine/src/polisyos/scientist/replay/deterministic.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_rep_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-13, MOVE-18. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A18.** Изменение import-пути не меняет historical bytes/format/ошибки автоматически. Relocation, исправление поведения и прекращение поддержки получают раздельные результаты.

**Ресурс:** N/C — I1 broker drains L and admits one exclusive native/numerical/build or checkpoint job using the full seven-unit budget; no other resource-bearing job runs concurrently. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без permit. Immutable argv/cwd/worktree/SHA/selectors/timeout/output root and named resources are fixed at admission; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-033

Источник LA_r09, строки 1994–2028; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-033 -->
## LA-033. Runtime replay: реализация перенесена, но старый путь остаётся транзитным

**C — завершение compatibility-миграции**

**Точная область:**

`src/polisyos/runtime/replay.py`

`src/polisyos/runtime/__init__.py`

Зависимые поверхности: `core/components/_cli_replay.py`, запись в `architecture/imports/dynamic.toml`, `benchmarks/advanced/common.py` и compatibility-тесты.

**Статус.** Alias-роль доказана полным файлом; есть реальные source-, строковые и тестовые потребители. Удаление без переключения зависимостей преждевременно.

**Что установлено.** `runtime/replay.py` явно присваивает 20 объектов из `scientist.replay.deterministic` и перечисляет те же 20 имён в `__all__`. Отдельного replay-алгоритма здесь нет. Однако package-root Runtime лениво разрешает десять публичных символов именно через старый модуль. Core-команда `_cmd_replay` тоже вызывает `importlib.import_module("polisyos.runtime.replay")`, хотя исполнение replay далее уже получает из Scientist backend. Для этого строкового пути существует отдельная запись dynamic-import inventory. Benchmark также импортирует старый адрес. [E95–E101]

Действующий `test_deterministic_compatibility.py` требует равенства экспортов, identity, signatures и значений перечислений. Это полезный контракт перехода, а не доказательство, что shell больше никому не нужен. Найденный список потребителей не выдаётся за полный census.

**Что сохранить.** Каноническую реализацию Scientist, все поддержанные enum values и dataclass contracts, различие complete/recoverable/incomplete и bit-exact/CI-bounded/skip; точную идентичность объектов. Сохранить ленивость root API: замена ленивого разрешения широким eager import меняет стоимость и side effects импорта.

**Куда перенести / с чем объединить.** Действующий владелец — `src/polisyos/scientist/replay/deterministic.py`; вычисления переносить уже не требуется. В качестве первого шага десять root exports могут разрешаться прямо у него, сохраняя прежний root API. Это не разрешение расширить десять имён root до всех двадцати. Новые внутренние callers используют владельца непосредственно. В Core CLI сохраняется обоснованная отложенная загрузка; её перевод в static import автоматически не предлагается.

**Порядок миграции.** Сначала переключить точные source/string consumers и соответствующую dynamic-import декларацию. Затем обновить документацию и разделить tests канонического поведения и tests временной совместимости. После подтверждённого окна поддержки удалить `runtime/replay.py`; прекращение публичного root API — отдельное решение, не обязательная часть удаления промежуточного модуля. Не удалять `runtime/quality/replay.py`: похожая строка `runtime.replay_manifest` там относится к другому контракту.

**Фактическая проверка.** r04-P02 подтвердил identity всех 20 экспортов на точном исходнике с fixture canonical objects. P03–P04 проверили ленивое обращение root и отказ неизвестного символа. P05 показал, что блокирование старого import-path ломает ещё не переключённый root, а локальное переназначение binding сохраняет identity. Это проверки механизма с фиктивным canonical owner, не настоящий replay CAS-пакета и не запуск repository compatibility-test.

**Приёмка в проекте.** Реальные import/signature/enum tests; `--check-only`, bundle import/export и replay/resume CLI; root import-budget; docs и dynamic paths; поддержанные старые артефакты без смены bytes и роли данных. Отдельно проверить monkeypatch/FQN consumers, а не ограничиться `from ... import`.

**Приоритет.** Низкая/средняя стоимость, ясная последовательность. Сначала убрать внутренний транзит через compatibility, затем решать срок публичного адреса.

**Граница вывода.** Canonical deterministic прочитан в диапазоне 1–150; его полный алгоритм в r04 не аттестован и не исполнен. Ни нулевой production-трафик старого адреса, ни разрешение немедленно убрать stable root surface не установлены.

**Основания:** E95–E101. Локальные проверки: r04-P01–P05.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-033 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK15 -->
## K15. Старый RunManifest сохраняет самостоятельный on-disk контракт

`runtime/manifest.py` явно обслуживает сохранённые run directories, локальную диагностику и bootstrap replay; в `runtime/api.py` есть действующие write/audit/journal-recovery операции. Наличие более новых Core runtime DTO не доказывает эквивалентности persisted schema. В r04 полный mapping между ними не строился. Сохранить reader/writer и старые fixtures до согласованного format converter; не удалять всё Runtime из-за compatibility-ролей `replay.py`. [E129–E130]

<!-- SOURCE_END LK:LK15 -->

