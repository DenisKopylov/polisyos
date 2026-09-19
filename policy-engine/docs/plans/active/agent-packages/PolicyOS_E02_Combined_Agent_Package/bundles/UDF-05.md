# UDF-05 — Демография: единый snapshot вместо per-file legacy fallback

**E02 · окно CP2 · локальная проверка N · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-032 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-07.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Выбирать полный declared layout/inventory до чтения targets/priors/donor. Сохранить old/new readers и типизированные arrays; адаптер к existing content-bound primitives не выдаёт D5 receipt за универсальный demographic certificate. Несовместимые смешанные каталоги не определяют эксперимент случайным существованием файла.

**Различающие тесты и сохраняемое поведение.** Чистые old/new, mixed targets-new/priors-old, optional donor, повреждённый/утраченный blob, несовпадение shapes и явный прежний snapshot. Удаление одного нового filename не выбирает молча другой эксперимент. Read_api controls и pure static aging сохранены.

**Не считать исправлением.** Не пересобирать источники без нужды, не считать одинаковую shape общим происхождением и не обойти verified read_api прямым open.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-032:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **UDF-05**; необходимые пакеты: UDF-05.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/ukraine/demography/__init__.py
policy-engine/src/polisyos/data_forge/read_api/ukraine.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/data_forge/domains/ukraine/static_aging.py
policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_udf_05.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-09. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** N — один tiny native/numerical job, без других тестовых jobs. Общий агентный fan-out остаётся12–16; ожидание test slot не останавливает написание/review. Для загрузки зависимостей и широких builds обращаться к I1, не запускать их самостоятельно.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-032

Источник LA_r09, строки 1668–1715; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-032 -->
## LA-032. Демографический reader: совместимость по отдельным filename вместо целого снимка

**Объединение / разделение ответственности**

**Точная область:**

`src/polisyos/data_forge/domains/ukraine/demography/__init__.py#load_demography_artifacts`

`src/polisyos/data_forge/read_api/ukraine.py#legacy demographic exports`



**Статус.** Неявный смешанный layout воспроизведён; реальное production-смешение версий не измерено.



**Что установлено и почему это legacy-кандидат.** Targets, priors и optional donor независимо выбирают первый существующий файл из нового hierarchical и старого flat layouts. Затем dicts объединяются и проверяются по форме. Нет единого выбора версии bundle. В полном исходном reader новые targets=[20] из demography/targets.json совместились со старыми priors=[[0.5]] из demography_transition_priors.json; metadata осталась old. Удаление нового targets-файла вернуло старые targets=[10] без изменения API-запроса. Это остаточный режим исторической совместимости, который определяет эксперимент через случайный состав директории.



**Что сохранить.** Типизированные массивы, shape checks, поддержанные старые layouts, optional donor, удобный public read_api и чистый build_static_aging_state. Пригодные исторические данные не должны становиться нечитаемыми. Намеренная композиция разных источников возможна, но требует явного описания состава, а не предположения, что все одноразмерные файлы совместимы.



**Куда перенести / с чем объединить.** Один явный выбор layout и inventory/version-bound bundle у Ukraine reader; existing verified-stage/release read_api содержит полезный механизм content binding и проверки размера/hash. Для demographic-формата нужен отдельный поддержанный adapter/manifest, а не ложное переименование старой папки в готовый D5 receipt. У старых адресов остаётся точный historical reader до завершения миграции.



**Порядок миграции.** Сначала определять полный layout или явно переданный manifest. Для смешанной неоднозначной директории выдавать адресный запрос на выбор, не незаметный fallback. Сохранить объявленные пути, digest и версию каждого входа; преобразование старого bundle выполнять как новую версию, не переписывая source bytes. Не требовать повторной сборки данных, когда совместимый сохранённый снимок доступен. Переиспользование receipt не создаёт governance или method-validity authority.



**Фактическая проверка и приёмка.** P13/P15 проверяют чистые новые/старые layouts; P14 — законное отсутствие donor. P16 воспроизводит смешение; P17 — смену выбранных targets после удаления новой копии. P18/P19 подтверждают действующие отказы при отсутствии targets и несовпадении размерностей. В интеграции нужны идентичность inventory, конфликт версий, недоступный blob, чтение прежнего bundle и сохранность численных полей.



**Приоритет.** Высокая семантическая отдача, средняя цена. Первое ограниченное исправление — явный bundle/layout resolver, без новой универсальной data-platform.



**Граница вывода.** Исполнен полный локально сверенный reader с настоящими Pydantic/NumPy и временными JSON. CAS, native verified receipt, настоящий demographic builder и внешние policy checks не запускались. Одинаковая размерность не доказывает общий снимок, но сама по себе разность источников тоже не запрещена.



**Основания:** E86, E87, E88, E89. Локальные проверки: P13, P14, P15, P16, P17, P18, P19.


<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-032 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK12 -->
## K12. read_api содержит проверки, а не только forwarding

В Ukraine read_api кроме ленивых экспортов есть проверка и сохранение точных bytes, размеров и hashes и явные ограничения назначения receipts. Это не лишняя оболочка, которую можно обойти прямым открытием файлов. В то же время D5 receipt не является готовым сертификатом любого демографического каталога. LA-032 использует этот подход как существующий материал для адаптера, а не автоматически расширяет его область. Чистый build_static_aging_state также остаётся полезной отдельной операцией. [E87, E88]

<!-- SOURCE_END LK:LK12 -->

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

