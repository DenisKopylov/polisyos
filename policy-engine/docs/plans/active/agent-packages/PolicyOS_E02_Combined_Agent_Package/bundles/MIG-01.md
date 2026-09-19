# MIG-01 — Один migration CLI: делегирование и явная Trinity validation

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-010 (M), LA-049 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-06.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Корневой migrate.py направить к действительному ops runner без второй parser/I/O реализации; не возвращать POLICY_IR_CURRENT_VERSION в Common ради старого импорта. Отдельным коммитом связать current-version policy_ir с существующим validation owner: различить unchanged, validated и converted. Удалить недостижимую self-edge, не заставляя generic engine исполнять self-loops. Старые split/auto_migrate/tuple адреса мигрировать с их реальными error/return contracts.

**Различающие тесты и сохраняемое поведение.** Native CLI JSON/YAML: полный Trinity, неполный current-version mapping, malformed nested payload, legacy markers/major bump, готовая model, default/explicit target. Проверить вызов настоящего validator, exit/error identity, source input и atomic output. Прежний root CLI и canonical entry имеют один исполнитель; tuple/auto_migrate consumers сохраняются до lifecycle. Неполный target не считается validated только по version.

**Не считать исправлением.** Не удалять IR loading/migrations, не изобретать migration report для no-op, не повышать старые bytes до прошедших новый validator. Не принимать canonical название за аттестацию каждой ветви runner.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-010:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **MIG-01**; необходимые пакеты: MIG-01.

**LA-049:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **MIG-01**; необходимые пакеты: MIG-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/migrate.py
policy-engine/src/polisyos/ir/loading/loaders.py
policy-engine/src/polisyos/ir/migrations/__init__.py
policy-engine/src/polisyos/ir/migrations/policy_ir.py
policy-engine/src/polisyos/ir/migrations/trinity_migration.py
policy-engine/tools/ops_runners/migrations/migrate.py
```

**Читать как соседние контракты:**

```text
policy-engine/ops/migrations/migration-contracts.toml
policy-engine/src/polisyos/common/migrations/__init__.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_mig_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** MIG-02, MIG-04. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-15. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A18.** Изменение import-пути не меняет historical bytes/format/ошибки автоматически. Relocation, исправление поведения и прекращение поддержки получают раздельные результаты.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-010

Источник LA_r09, строки 339–367; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-010 -->
## LA-010. Корневой migrate.py: реальная вторая реализация команды

**Слияние / разделение ответственности**

**Статус.** Содержательный legacy-дубль подтверждён сравнением обоих файлов.

**Точная область:**

`migrate.py`

`tools/ops_runners/migrations/migrate.py`

**Что установлено и почему это legacy-кандидат.** Несмотря на wrapper_only в shims.toml, root migrate.py содержит собственные parser/load/dump, прямую запись файла и общий common-migrator для policy_ir. Канонический runner проверяет object-вход, вызывает validate_helper_binding, использует IR-owned migrate_policy_ir, атомарную запись и поддерживает run_manifest. Это не два равноценных адреса одной функции.

**Что сохранить.** Поддержанные JSON/YAML-входы, выбор target version, совместимость CLI и реальные миграционные функции. Сохранить полезное старое поведение лишь там, где оно не противоречит актуальному формату.

**Куда перенести / с чем объединить.** Существующий tools/ops_runners/migrations/migrate.py — единственный исполнитель команды; policy_ir остаётся за polisyos.ir.migrations, остальные поддержанные common artifacts — у своего владельца.

**Порядок миграции.** Сначала root entrypoint делегирует canonical main без копии parser/I/O; затем удалить его после миграции команд пользователей. Обновить неверное wrapper_only-описание. Не считать старые и новые policy_ir миграции эквивалентными без fixture comparison.

**Приёмочная проверка.** JSON/YAML, явно заданная и default версия, неправильный top-level input, exit codes, newline/encoding, ошибка записи, поддержанные historical fixtures. Прямое удаление root CLI — отдельная смена интерфейса.

**Приоритет.** Высокая отдача при умеренной цене: убирается реальное расхождение путей.

**Граница вывода.** Не выполнялись настоящие миграции persisted artifacts. Наличие дополнительных проверок canonical runner не аттестует каждое его преобразование.

**Основания:** E18, E19, E22.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-010 -->

## Обязательное позднее уточнение LA-010

<!-- SOURCE_BEGIN AM:AM01 -->
## LA-010 — уточнение r02

Уточнение: root migrate.py импортирует POLICY_IR_CURRENT_VERSION из common.migrations. Полный текущий __init__.py этого пакета не определяет и не экспортирует имя, не содержит lazy __getattr__. Это уже несовместимый import-контракт, а не только более слабый runner. Локальная проверка initializer с fixture child modules дала ImportError; весь CLI не запускался. Не возвращать старую константу в Common ради маскировки: переключить root entrypoint на действительного владельца миграций. [E62, E18, E19]

<!-- SOURCE_END AM:AM01 -->

## Исходное решение LA-049

Источник LA_r09, строки 3358–3396; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-049 -->
## LA-049. Trinity: validation продолжает жить под migration-контрактами, но self-edge не выполняется

**M — согласование validation, conversion и compatibility-API у существующего владельца**

**Точная область:**

`src/polisyos/ir/migrations/policy_ir.py#migrate_policy_ir_identity`

`src/polisyos/ir/migrations/__init__.py#migrate_policy_ir`

`src/polisyos/ir/migrations/trinity_migration.py`

`src/polisyos/ir/loading/loaders.py#load_trinity_bundle/load_policy`

**Статус.** Все четыре файла и IR base прочитаны целиком и сохранены точно. Execution traces проверяют настоящее управление вызовами, но **TrinityBundle заменён минимальной Pydantic-фикстурой**. Полный нативный model/IR corpus не исполнялся. Существующий contract test прочитан, а не выдан за запущенный. [E179, E189–E193]

**Что установлено.** В `policy_ir.py` зарегистрировано ребро `1.0 → 1.0`; его функция вызывает `TrinityBundle.model_validate` и сериализует модель. Но base runner немедленно возвращает input, когда current version совпадает с target. Публичный `migrate_policy_ir` проверяет наличие/форму версии, legacy markers и major change, затем обращается к этому base. Поэтому зарегистрированная identity-validation **не исполняется в обычном current-version migration path**.

В локальной композиции фактическая `main` канонического CLI приняла `{"schema_version":"1.0"}`, записала тот же mapping и вернула `0`, не вызвав модель ни разу. Прямой identity-helper и текущий loader вызвали fixture validator и отвергли неполную структуру. Это доказывает отсутствие вызова нужного звена в данном маршруте; не доказывает, что такой файл принят native runtime или стал допустимым PolicyOS-результатом. [r07-P13, P17]

Остальная старая поверхность тоже уже не выполняет конверсию. `split_to_bundle` либо возвращает готовую модель, либо делает `model_validate`: он ничего не разбивает на части и не переводит прежний non-Trinity формат. `is_trinity_migrated` сообщает о текущей валидируемости, а не об истории выполненной миграции. В loader `auto_migrate=True/False` меняет только текст ошибки при validation failure; во всех успешных путях migration report равен `None`. Важно: docstring **честно раскрывает** сохранение параметра ради старой сигнатуры, поэтому это не новая скрытая capability, а законченный повод для lifecycle-решения. [E190–E192; r07-P14–P15]

**Почему это legacy.** После перехода к Trinity-only входам сохранились self-migration registration, исторические имена «split/migrated», флаг без conversion-поведения и tuple slot несуществующего отчёта. Полезная validation-функция при этом существует у действующего loading/model owner. Убрать следует конкурирующие способы объяснить результат и недостижимое размещение проверки, а не запретить поддержку старых inputs без анализа.

**Что сохранить.** Реальный `TrinityBundle` validator, JSON/YAML/bytes parsing, `PolicyLoadError` и связанные exception contracts, identity уже созданной модели там, где она обещана, запреты старой `2.*`/`semantic` поверхности и явное согласие на major change. Сохранить внешних callers tuple-return и `auto_migrate` на фактическое окно совместимости. Разные accepted input types и exceptions двух helper API запрещают считать их механическими aliases.

**С чем объединить.** Текущие `ir.loading.loaders` и Trinity model — существующий дом для parse/validation. `ir.migrations` должен отвечать за действительную version conversion, если поддерживаемые переходы есть, не за возможность произвольно вызвать validator как ребро графа. Для migration-CLI необходимо явно согласовать постусловие: «версия уже требуемая, преобразование не выполнялось» либо «результат проверен как текущий Trinity». Сегодня self-edge не обеспечивает второе. Если второе требуется контрактом команды, validator должен вызываться явно на выходной границе, включая no-op path. Это проектируемое уточнение, не утверждение о введённом в репозитории новом правиле.

**Порядок миграции.** Сначала tests на реальную CLI→IR→validator цепочку и различие no-op/validated/converted. Подключить существующего validation owner в согласованном месте; затем убрать недостижимую self-edge регистрацию. Не заставлять весь generic runner выполнять self-loops: это смешает проверку схемы с поиском перехода и затронет другие artifact profiles. Legacy helper можно сохранить как узкий adapter с прежними error/return semantics, затем перевести callers на явно named validation/load API.

Флаг `auto_migrate` и `(bundle, None)` выводятся отдельным compatibility-шагом. Если реальная migration report нужна будущему поддержанному переходу, её следует определять у actual converter; не оставлять поле как доказательство несуществующего исполнения. Старый формат не становится поддержанным от удаления слова `legacy` из ошибки. Исторические outputs не помечаются задним числом как проверенные новой моделью.

**Приёмка.** Native валидный Trinity, неполный current-version mapping, неправильный вложенный объект, готовая модель, JSON/YAML/UTF-8, старые markers, major bump, прямой helper и настоящий operator CLI. Проверить validation call, exception identity, model dump mode/defaults и no-op identity. Сравнивать не только номер версии и return code. Существующий `test_trinity_migration.py` — один из полезных спутников; он не должен исчезнуть вместе с именем wrapper.

**Граница вывода.** Нативный Trinity model, его вложенные defaults/validators, schema registry initialization и production admission не запускались. Изолированный импорт registry использует пустую fixture, что не меняет доказанную раннюю ветку равной версии, но не позволяет аттестовать все compatibility rules. Для старых helper имен есть подтверждённый test consumer; полный внешней lifecycle census не выполнен. Это M, не разрешение удалить целиком `ir/migrations/`.

**Приоритет:** высокая смысловая ясность; начать с одного явного результата команды и проверки её настоящего postcondition. **Основания:** E179, E184, E189–E193; r07-P13–P17.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-049 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK26 -->
## K26. Текущий Trinity loader действительно вызывает validator

`load_trinity_bundle` вызывает model validation после parsing/Mapping-check; `split_to_bundle` при mapping тоже его вызывает. Незадействованная self-edge из LA-049 не означает, что весь IR принимает произвольный current-version payload. В настоящем source path есть отдельный validator owner и тесты valid/invalid loading; в локальном исполнении его вызов проверен с модельной фикстурой. **Не убирать loading guard и не объявлять доказанный обход runtime admission.** [E190–E193; r07-P13–P17]

<!-- SOURCE_END LK:LK26 -->

<!-- SOURCE_BEGIN LK:LK27 -->
## K27. Path containment и operational binding — полезные, но другие проверки

Настоящий `resolve_artifact_path` отверг `../outside`, absolute path без разрешения и отсутствие path fields. Настоящий `validate_helper_binding` на временном TOML отказал, когда удалена требуемая contract-directory; CLI не записал output. Эти свойства сохраняются. Они не доказывают, что basename-rewrite выбрал прежний артефакт, и не заменяют release review. **Не ослаблять containment, чтобы сделать старую миграцию удобнее.** [E185, E188; r07-P24–P26]

<!-- SOURCE_END LK:LK27 -->

