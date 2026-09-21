# REQ-01 — DataRequirement: явный контекст и ограниченная private-очистка

**E02 · окно CP1 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-045 (D), LA-046 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-01.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Сначала отдельно удалить только семь private функций и _DATA_FAMILY_ORDER из LA-045 после конечного scan (включая дополнение _digest). Затем отделить named pilot profile от generic construct resolution: opaque scenario_id не текст; geography не UA; periodicity не фиксированная дата. Явные constructs имеют приоритет, proposals не становятся authority. Поддержать text/request и domain/domain_hint по определённому adapter contract.

**Различающие тесты и сохраняемое поведение.** Сравнить AST всех оставшихся функций cleanup-коммита. Generic запрос другой jurisdiction/даты не наследует UA/2022; parent-support и отрицание rent не создают обязательного требования по подстроке ID. Optional/mandatory resolver, explicit constructs и opt-in family fallback сохраняют свои правила. Полный N7 caller проверяет ACQ-01.

**Не считать исправлением.** Не удалять compiler.py, hashlib/json, активный _required_data_families_from_heuristic и governed resolver. Не создавать NLP framework и не объявлять regex полноценной интерпретацией.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-045:** Полная уточнённая область: семь функций + одна constant; две подгруппы, включая _digest. Accountable closure: **REQ-01**; необходимые пакеты: REQ-01.

**LA-046:** Этап 1/2: generic/pilot input и compiler/resolver contract; actual N7 composition/закрытие — ACQ-01. Accountable closure: **ACQ-01**; необходимые пакеты: REQ-01, ACQ-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_requirement/compiler.py
```

**Читать как соседние контракты:**

```text
policy-engine/architecture/shims.toml
policy-engine/src/polisyos/data_requirement/__init__.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_req_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-045

Источник LA_r09, строки 2999–3033; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-045 -->
## LA-045. Старый extractor data families: замкнутая неиспользуемая ветка внутри действующего compiler

**D — прямая очистка точной группы private-определений без переноса логики**

**Точная область:** `src/polisyos/data_requirement/compiler.py` — только следующие определения:

```text
_data_families_from_obligation_graph
_data_family_token_from_frontier_item
_nested
_normalised_family
_slug_family
_ordered_data_families
_DATA_FAMILY_ORDER
```

**Статус.** Полный файл из **1 228 строк** сохранён с совпадающим Git blob SHA `2810157d9607fef55af291ddf35a9e8bec875390`. Полный AST этого одного файла показывает: корневой extractor не имеет Name-load ссылок, а все обращения к остальным шести именам приходят только из указанной группы. Attribute-ссылок с этими именами в файле не найдено. Это конечный **module-local census**, не census всего репозитория и не измерение production callers. [E166; r06-P16]

**Что установлено и почему это legacy.** Docstring старого extractor всё ещё описывает его как primary Track-A1 path от `blocking_frontier` к data-family names. Реальный `compile_for_claim_ledger` теперь получает families через `_capability_bindings_for_requirements` и governed construct mappings. Внутри этой действующей цепочки используется `_required_constructs_from_obligation_graph`, а не старый family extractor. Шесть private functions и `_DATA_FAMILY_ORDER` образуют остаток прежнего маршрута. Public `__all__` compiler и package lazy exports их не открывают. Адресный поиск корневого имени вернул определение, но не заменяет полный внешний caller scan. [E166–E167, E170]

На прямом локальном вызове extractor корректно отфильтровал не-data frontier и отсортировал две family labels. Поэтому основание удаления — **отсутствие роли в проверенном нынешнем потоке**, а не ошибочность алгоритма, малый размер или слово legacy. Нельзя называть все эти функции заглушками.

**Что сохранить.** Весь `DataRequirementCompiler`, active construct extractor, injected resolver, governed mappings, current reports и публичные wrappers. Особо сохранить `_required_data_families_from_heuristic`: она действительно вызывается при включённом feature flag и отсутствии family rules. Её похожее имя не делает её частью изолированного кластера. Не менять family IDs, порядок живых текущих outputs или сохранённые historical reports ради удаления неиспользуемого helper.

**Куда перенести.** Никуда, если конечная проверка внешних consumers подтверждает отсутствие необходимого использования. Удалять определения из существующего файла, не переносить их в очередной `legacy.py`. При найденном внешнем historical reader сначала определить его реальную потребность и поддержанный адрес; direct-D disposition для используемого имени тогда пересматривается.

**Порядок миграции.** Проверить qualified и относительные imports каждого из шести helpers, `getattr`/string loaders, тестовые monkeypatch targets и generated inventories. Затем удалить ровно перечисленную группу, вместе с устаревшим docstring и локальной таблицей порядка. Это не требует переноса действующего compiler или завершения LA-046. Отрицательную архитектурную проверку при необходимости формулировать по отсутствию старой ветки, а не сохранять её доступность ради теста.

**Фактическая проверка.** r06-P16 перечисляет все соответствующие AST loads по полному модулю с номерами строк. P17 удаляет группу **только в in-memory AST**, проверяет компилируемость, неизменность всех остальных узлов и четырёх compiler exports. P18 исполняет настоящий старый extractor на fixture frontier. P23 исполняет одну выбранную нынешнюю request-construction цепочку до и после удаления и получает тот же запрос/результат на recording resolver. Это не native DataRequirementCompiler integration-test, не полная семантическая эквивалентность всей программы и не уже выполненная правка репозитория.

**Приёмка в проекте.** Конечный caller scan за пределами модуля; unit tests DataRequirementCompiler; scenario compilation и runtime/fabric consumers; default flag и opt-in fallback; публичные imports; packaging/import checks. Успех локального AST-прохода не разрешает удалить сам файл или весь `data_requirement/`.

**Приоритет:** новая небольшая прямая очистка рядом с прежними LA-007/LA-019/LA-026. **Основания:** E166–E170; r06-P16–P18, P23.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-045 -->

## Обязательное позднее уточнение LA-045

<!-- SOURCE_BEGIN AM:AM03 -->
## LA-045 — дополнительное private-определение, без новой карточки

В полном SHA-сверенном `data_requirement/compiler.py` найден ещё один изолированный кандидат:

```text
_digest — строки 1213–1215
```

Это самостоятельный helper JSON→SHA-256[:16], **не часть прежнего связанного кластера** family-extractor. Обход всего AST одного файла не нашёл Name-load, Attribute-access или точной строковой константы `_digest`; в `__all__` имени нет. Удаление только этой функции в in-memory AST сохранило все остальные узлы с их атрибутами и компилируемость. Никакого полного исполнения compiler или внешнего caller census из этого не следует. [E197; r07-P30–P31]

Очередь LA-045 теперь имеет две подгруппы: прежние шесть private helpers + `_DATA_FAMILY_ORDER`, и отдельно `_digest`. Всего **семь функций и одна constant** в этой карточке. Не удалять `hashlib` и `json`: оставшийся AST содержит их реальные использования, включая работающую идентификацию requirements. Public functions с нулём локальных вызовов тоже не являются D только по этой метрике: их экспорт и внешняя роль сохранены.

**Действие:** при конечной проверке внешних imports/строковых targets можно удалить точное private-определение без нового общего hashing helper. Существующий код уже не нуждается в нём локально. Если обнаружен внешний consumer, его договор рассматривается отдельно; нынешний bounded-zero не означает общего отсутствия использования.

<!-- SOURCE_END AM:AM03 -->

## Исходное решение LA-046

Источник LA_r09, строки 3034–3068; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-046 -->
## LA-046. DataRequirementCompiler: именованный construct-путь всё ещё наследует неявный сценарный профиль

**M — отделение сценарных предпосылок от общего построения capability-запроса**

**Точная область:** `src/polisyos/data_requirement/compiler.py`:

`_required_constructs_from_semantics`, `_scope_from_facets`, `_jurisdiction_for_geography`, `_time_start_for_scope`, `_capability_bindings_for_requirements`; связанный adapter — `compile_for_scenario` / `_scenario_text`.

**Статус.** Активный fallback при пустом construct frontier и фиксированные значения запроса подтверждены полным исходником и локальными execution traces. Неверное разрешение authority в реальной системе **не установлено**.

**Что установлено.** Feature flag `POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED=false` ограничивает старую family-эвристику. Но в нынешнем `_capability_bindings_for_requirements` при отсутствии constructs из графа вызывается другая функция — `_required_constructs_from_semantics`. Она объединяет facet values, claim text, metadata values и `scenario_id` в строку и проверяет substrings. Флаг не заявлен как выключатель этого нового пути. Тем не менее физический переход от family labels к construct refs не устранил саму раннюю технику семантического выбора. [E166, E168]

В различающем примере нейтральный `case-alpha` не создаёт construct, а одно переименование в `parent-support` добавляет `housing_rent_burden`: в `parent` находится подстрока `rent`. Текст `No housing or rent intervention is requested.` тоже добавляет его. Это точное свойство substring matching; оно не означает, что любое распознавание темы или любой эвристический candidate discovery недопустим. Но непрозрачный ID и отрицание не должны незаметно определять обязательный предмет capability query.

Scope также наследует конкретику: для `national`, `state_or_region`, `municipal`, `displacement_affected` helper возвращает jurisdiction `UA`; для `annual`, `phased_rollout`, `event_triggered` начало окна — `2022-02-01`. Query получает их через `scope.jurisdiction or scope.geography` и `time_window`, с `authority_level="governed_pilot"`. Такие настройки могут быть намеренным профилем украинского пилота, но общего значения слов «национальный» и «годовой» для их восстановления недостаточно. **Предлагается сделать профиль явным, не удалить сам пилот.**

Дополнительная граница старого adapter: `_scenario_text` читает `request`, `title` и ряд контекстных ключей, но не `text`, и всегда добавляет `annual`. На локальном mapping `{scenario_id: case-alpha, text: ...}` остаётся `case-alpha annual`; с `request` содержание сохраняется. Найден Runtime search-fragment, где `problem_statement` передаётся как `text`, однако весь caller mapping и его downstream chain в r06 не прочитаны. Поэтому это **точная interface-characterization и приоритет следующего trace**, не уже доказанная потеря всех сведений в native Runtime. [E169]

**Что сохранить.** Явные construct refs из obligation frontier, governed mappings, resolver port, исходные claim/facet данные, pilot scenario fixtures и ограничения назначения family projections. Сохранить полезный lexical discovery как явно ограниченный candidate proposal там, где он нужен. Реальный capability resolver и guards остаются: без optional resolver проверенная функция возвращает пустой набор, а обязательный resolver при отсутствии вызывает ошибку. Явный construct frontier имеет приоритет над text heuristic. Это существенные отрицательные контроли, не формальности.

**С чем объединить / куда отнести.** Существующий graph → construct → injected resolver путь остаётся основным. Для конкретных golden scenarios нужен явно именованный versioned input profile в принадлежащем им adapter, содержащий jurisdiction, temporal interval и правила topic proposals. Общий compiler получает проверенный context, а не угадывает его из категории географии или текстового ID. Готовый универсальный replacement для полной interpretation-функции в r06 не установлен; новый LLM/NLP framework создавать ради этой миграции не предлагается.

Простейшее ограниченное исправление — перестать считать `scenario_id` содержательным текстом, явно передавать scope и различать `not_derived` от отсутствия потребности. Это не полное решение интерпретации negation или construct completeness. Замена проверки `rent in text` одним regex исправит только пример и не завершит миграцию. При сохранении эвристики записывается её actual profile и статус candidate; downstream resolver не должен быть единственным местом, где пытаются восстановить утраченный исходный смысл.

**Порядок миграции.** Зафиксировать inputs/queries штатного pilot corpus и явно названные defaults. Разделить generic compiler и scenario adapter, согласовать `text`/`request` handoff. Перевести один реальный runtime consumer на явные facets, interval и jurisdiction, не меняя исторические артефакты задним числом. Затем удалить неявные generic defaults либо оставить только внутри объявленного compatibility profile. Старый opt-in family fallback имеет собственные lifecycle conditions; его removal не закрывает активный construct fallback. LA-045 можно выполнить независимо.

**Фактическая проверка.** r06-P19–P27 исполняют выбранные точные функции из полного SHA-сверенного исходника. Реальны Python, mapping/string operations, branch logic и построение kwargs. Scope, query, governed mapping boundary и resolver — явно заданные fixtures; resolver только записывает вход и не выдаёт настоящего допуска. P23 фиксирует query с `UA`, `2022-02-01` и `housing_rent_burden`; P24/P25/P27 сохраняют отказы и precedence. P26 проверяет только input adapter.

**Приёмка.** Один явный исторический пилот; другая jurisdiction с теми же generic geography labels; явное годовое окно другой даты; идентичное содержание с разными opaque IDs; отрицание темы; пустой и явный construct frontier; отсутствующий optional/required resolver; mapping с `text` и `request`. Сравнивать полный query, причины получения construct и разрешённую роль результата, а не только число specs. Изменение интерпретации оформлять как версию правила, отдельно от relocation.

**Граница вывода.** Не измерены правильность native obligation graph, полнота construct catalog, реальный resolver/authority gate и production decisions. Нет основания объявлять все DataRequirementSpec недействительными или заменять их family strings. Явная фиксация специфического профиля допустима и дешевле необоснованной универсализации.

**Приоритет:** содержательная input-binding миграция; сначала явный scope и непрозрачность ID. **Основания:** E166, E168–E169; r06-P19–P27.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-046 -->

## Обязательное позднее уточнение LA-046

<!-- SOURCE_BEGIN AM:AM04 -->
## LA-046 — N7 handoff теперь прочитан до непосредственного downstream-вызова

В `GenerationCycleController._n7_data_requirement_specs` проверены полные ветки: специальный typed requirement gap; `runtime_hints.n7_data_requirement_specs`; явные specs; затем fallback через legacy scenario adapter. Последний формирует mapping из `scenario_id`, `text`, `domain` и `expected_evidence_contract.admissible_data_source_families`, после чего вызывает `DataRequirementCompiler()` **без resolver**. Это точный ранее неизвестный caller, не только предположение на основе сигнатуры приёмника. [E200]

Полный наследованный compiler той же базы действительно строит `_scenario_text` из других ключей (`request`, `title`, `domain_hint`, части context и т. д.), не из `text`/`domain`, и добавляет `annual`. Его regular claim-ledger path требует resolver для получения capability bindings; default legacy-family flag остаётся false. Если grammar не сформировала facets, другая ветка читает прежний список families и выпускает minimal specs с metadata о legacy fallback. [E210]

**Ограниченная композиция actual source bodies дала:**

| Заданный boundary-сценарий | Наблюдаемый результат |
|---|---|
| `case-alpha`, health statement/domain; grammar-фикстура возвращает facets | В grammar пришло `case-alpha annual` и `fiscal`; regular compiler дал 0 specs без resolver |
| Тот же ID, другой education statement/domain | Тот же grammar input; изменение исходного содержания не дошло по этим полям |
| Тот же запрос, grammar-фикстура возвращает `facets=None` | Legacy branch вернула заданную `health_panel` family |
| Непустые явные `data_requirement_specs` | Identity объекта сохранена; scenario compiler не вызван |
| Специальный совпадающий typed any-of gap | Сохранён gap; не синтезированы новые family requirements |
| Empty primary specs плюс непустой secondary alias | Из-за `or` использован secondary; empty runtime hint, напротив, сохранён |

**Downstream проверен адресно.** `_run_n7_acquisition_if_requested` получает specs, затем запрашивает world snapshot и owner gateway. При пустых specs он возвращает `None` до `run_acquisition_closed_loop`; это не успешное приобретение данных. При непустом legacy fallback он передаёт specs в тот же closed-loop entrypoint. В probe world/gateway/acquisition — recording fixtures: измерен вызов и отказ от вызова, а не настоящая загрузка или admission. [r08-P25–P32]

**Что теперь установлено точнее:** интерфейсная потеря `text`/`domain` и отсутствие injection принадлежат реальному source handoff; regular/legacy ветки имеют разные preconditions. **Что не установлено:** какая ветка штатной grammar выполняется на конкретном настоящем DesignProblem, насколько часто используется fallback, принимаются ли такие specs далее и можно ли на их основе получить authority. Native grammar, PDC graph, DTO validation и acquisition owners здесь заменены явно описанными фикстурами.

**Рекомендация:** не создавать третью ветку восстановленной семантики. Внешний composition owner должен передавать полное typed requirement или явный текст/область/времена и resolver туда, где они действительно требуются. Для legacy-only replay сохранить ограниченный профиль; `None` receipt не маскировать как отсутствие потребности. Принципиальный порядок уже в LA-046: контекст и основания становятся явными, затем выводится старый scenario-shaped bridge. Механическая замена `text` на `request` закрывает только одну потерю; сама по себе она не добавляет resolver и не определяет scope.

Это **тот же класс на следующей границе**, а не LA-054. Новая проверка также не закрывает весь вопрос construct completeness или эвристических scope defaults из r06.

<!-- SOURCE_END AM:AM04 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK24 -->
## K24. Неиспользуемый extractor не делает неиспользуемыми исторические readers и resolver guards

LA-045 исключает из очистки active construct extractor, opt-in heuristic и legacy-scenario fallback. Их вызовы видны в полном compiler. LA-046 различает возникновение candidate construct и действительный результат capability resolution: в probes использован только recording resolver. Сохранить требование injection для mandatory mode и family projection denials; устранение lexical defaults не должно возвращать authority selection по старым family strings. [E166–E169]

<!-- SOURCE_END LK:LK24 -->

<!-- SOURCE_BEGIN LK:LK31 -->
## K31. N7 уже имеет реальные пути явного требования; fallback не означает, что весь acquisition устарел

Проверенные typed-gap и explicit-spec branches обходят старый scenario adapter. Mandatory resolver guard в настоящем compiler продолжает поднимать ошибку при отсутствии injection. Empty specs не превращаются в выполненный acquisition. Поэтому LA-046 не предлагает удалить closed-loop planner, verified receipt re-entry или весь DataRequirementCompiler. Улучшается конкретный legacy handoff, а не возвращается выбор authority по строковым family labels. [E200, E210; r08-P27–P33]

<!-- SOURCE_END LK:LK31 -->

