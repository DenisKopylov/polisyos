# MIG-02 — RunManifest: сохраняющее identity преобразование paths

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-048 (M).

**Предшественники:** [MIG-01](../bundles/MIG-01.md). **Совместная очередь:** LANE-06.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Вынести path conversion из ops CLI к предложенному Runtime manifest_migrations.py. Явно связать source root, destination root/layout и режим rebase/relocation/historical-only. Убрать fallback к basename, сохранять значимые подкаталоги и согласовать существующий run_root. --to исполняется по определённому version profile либо явно отвергается для path-only режима. Никакого автоматического копирования внешних файлов.

**Различающие тесты и сохраняемое поведение.** Временные реальные files: sub/data.json рядом с чужим data.json; два external пути с одним basename; разные roots; отсутствующий источник; symlink/escape; повтор, relative_path, --to. До/после читается тот же разрешённый объект или точная диагностика, не удобный чужой файл. Containment и atomic output сохранены; отказ не перезаписывает исходный manifest.

**Не считать исправлением.** Не ослаблять Runtime containment и не менять только строку пути без проверки адресуемого объекта. Не мигрировать пользовательские runs при тестировании.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-048:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **MIG-02**; необходимые пакеты: MIG-02.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/ops/migrations/migration-contracts.toml
policy-engine/src/polisyos/runtime/manifest_migrations.py
policy-engine/tools/ops_runners/migrations/migrate.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/runtime/api.py
policy-engine/src/polisyos/runtime/manifest.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_mig_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** MIG-01, MIG-04. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-13. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A18.** Изменение import-пути не меняет historical bytes/format/ошибки автоматически. Relocation, исправление поведения и прекращение поддержки получают раздельные результаты.

**Ресурс:** L — максимум два таких jobs по всем worktree. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-048

Источник LA_r09, строки 3317–3357; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-048 -->
## LA-048. RunManifest: старое эвристическое переписывание путей внутри канонического migration CLI

**M — миграция от угадывания filename к явному сохранению адресуемого артефакта**

**Точная область:**

`tools/ops_runners/migrations/migrate.py#main`, ветка `run_manifest`.

Потребитель результата: `src/polisyos/runtime/api.py#resolve_artifact_path`; persisted schema: `src/polisyos/runtime/manifest.py`; operational binding: `ops/migrations/migration-contracts.toml`.

**Статус.** Полный CLI прочитан и исполнен как функция с настоящими JSON, файловой записью и проверкой TOML binding на временном конфигурационном дереве. Полные две функции Runtime path resolution исполнены как исходный excerpt. Native Runtime initialization, реальные run directories и release gate не запускались. [E184–E188, E194]

**Что установлено.** Base вычисляется из расположения входного manifest: `input.parent.parent`. Если у записи ещё нет `relative_path`, абсолютный путь пытаются сделать относительным этому base; при неудаче оставляют только `Path(path_val).name`. Точно та же ветка обрабатывает уже относительный `path`, у которого могут быть значимые подкаталоги. Затем оба поля адреса заменяются полученной строкой. Файлы артефактов этот код не переносит и не проверяет. Существующий `run_root` сохраняется через `setdefault`, даже когда relative path только что рассчитан относительно другого корня. Параметр `--to` в этой ветке не читается. [E184]

**Различающие случаи.** В локальном корпусе:

- Абсолютный путь **внутри** выбранного run root преобразовался корректно, и читатель открыл прежние bytes.
- Поддерживаемый самим reader относительный `sub/data.json` стал `data.json`. При наличии другого файла с таким basename читатель после миграции открыл его содержимое `unrelated`, а не прежнее `original`.
- Два различных внешних пути с одинаковым basename превратились в один внутренний адрес. Исходные внешние файлы остались нетронуты; новый manifest на них уже не указывал.
- Сохранённый ранее `run_root` и новая relative string дали адрес другого корня; в fixture по нему не было файла.
- Запуск с `--to 9.9` и без него дал одинаковый manifest с `schema_version=1.0`.

Это проверенные временные примеры, **не обнаруженные пользовательские повреждённые runs и не утверждение о разрешённом доступе к внешним путям**. Точный Runtime reader по умолчанию отвергает absolute paths и не допускает выход за корень; его защиту не предлагается ослабить. Проблема в том, что containment нового пути не подтверждает сохранение исходной identity. [r07-P18–P26]

**Почему это legacy.** После консолидации операционной команды сохранилась старая модель «перевести путь в относительный, в крайнем случае взять имя». Она меняет ссылку вместо определённой миграции данных. В operational contract `run_manifest_relative_path_rewrite` указан как implementation label, но исполняемая логика остаётся inline в CLI. Проверка helper binding устанавливает существование class/contract path, а не семантическую эквивалентность ссылок. [E185–E186]

**Что сохранить.** Stable on-disk RunManifest, reader/writer, strict shape failures для artifacts list, целые исходные manifests, корректные относительные paths, запрет выхода за допустимый root и атомарную публикацию текста. Существующие historical readers не удаляются. Не копировать произвольные внешние файлы автоматически и не искать замену по совпавшему basename.

**Куда перенести / с чем объединить.** Смысловая конверсия адресов относится к Runtime persisted-format owner. Возможный новый `src/polisyos/runtime/manifest_migrations.py` должен содержать небольшой чистый converter с явными source root, destination root/layout и disposition для неподдержанной ссылки. Это **предлагаемый файл**, не готовый найденный converter. Ops сохраняет разбор CLI, авторизованное чтение/копирование при явно выбранном режиме, dry-run/report и атомарный output. Для проверки target paths переиспользуется существующая Runtime containment-семантика; она не заменяет проверку того, какой объект требуется сохранить.

**Порядок миграции.** Сначала прекратить fallback, который придумывает basename при невозможности установить корректное отображение; неоднозначную запись оставить неизменной с диагностикой либо отклонить согласно согласованному CLI-контракту. Разделить операции: rebase только адреса уже доступного объекта; relocation с явным переносом и проверкой bytes; чтение historical-only. Зафиксировать относительность к конкретному source root, прежде чем назначать destination root. Не менять root всего manifest частично и не смешивать старую и новую интерпретацию отдельных записей без явной карты.

`--to` либо получает реальный смысл для versioned RunManifest migration, либо явно отвергается для отдельной path-normalization команды. Удаление/переименование общего параметра во всех artifact modes не требуется. Окончательное решение зависит от обещаний операционного CLI. Старую inline-ветку удалить после подключения converter и миграции команд/fixtures, не после одного переименования label.

**Приёмка.** Внутренний абсолютный путь, сохранённый относительный подкаталог, явный `relative_path`, различные roots, одинаковые basenames, неизвестный/отсутствующий объект, перенос directory, symlink/escape, повторный запуск и намеренный target-version. Сравнивать ожидаемый источник и реальные output bytes/refs. Для недоступного source не выдавать identity как подтверждённую; для version-only команды не утверждать, что артефакты физически перемещены.

**Граница вывода.** Политика выбора доверенного root и реальные runtime consumers за пределами двух функций не исследованы. В тестах `ArtifactRef` представлен объектом с двумя полями; весь Pydantic RunManifest и manifest journal не исполнялись. Shell entrypoint и release promotion не запускались. LA-010 остаётся рекомендацией единого runner; эта карточка уточняет качество одной его живой ветки, а не возвращает старый root CLI.

**Приоритет:** сначала устранить потерю адресной информации; последующее выделение converter — ограниченная миграция. **Основания:** E184–E188, E194; r07-P18–P26.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-048 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK15 -->
## K15. Старый RunManifest сохраняет самостоятельный on-disk контракт

`runtime/manifest.py` явно обслуживает сохранённые run directories, локальную диагностику и bootstrap replay; в `runtime/api.py` есть действующие write/audit/journal-recovery операции. Наличие более новых Core runtime DTO не доказывает эквивалентности persisted schema. В r04 полный mapping между ними не строился. Сохранить reader/writer и старые fixtures до согласованного format converter; не удалять всё Runtime из-за compatibility-ролей `replay.py`. [E129–E130]

<!-- SOURCE_END LK:LK15 -->

<!-- SOURCE_BEGIN LK:LK27 -->
## K27. Path containment и operational binding — полезные, но другие проверки

Настоящий `resolve_artifact_path` отверг `../outside`, absolute path без разрешения и отсутствие path fields. Настоящий `validate_helper_binding` на временном TOML отказал, когда удалена требуемая contract-directory; CLI не записал output. Эти свойства сохраняются. Они не доказывают, что basename-rewrite выбрал прежний артефакт, и не заменяют release review. **Не ослаблять containment, чтобы сделать старую миграцию удобнее.** [E185, E188; r07-P24–P26]

<!-- SOURCE_END LK:LK27 -->

