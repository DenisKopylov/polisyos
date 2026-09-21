# ACQ-01 — N7: типизированное требование → acquisition → re-entry

**E02 · окно CP1 · локальная проверка L · начальный статус planned.**

**B:** B12. **LA:** LA-046 (M).

**Предшественники:** [REQ-01](../bundles/REQ-01.md), [CYC-03](../bundles/CYC-03.md). **Совместная очередь:** LANE-01.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Объединить B12 с уточнением LA-046 из r08: сохранить typed gap/explicit specs precedence, провести text/domain/scope и настоящий resolver из composition owner. Связать план, разрешённый job, приёмку источника и re-entry. Исправлять реальный _n7_data_requirement_specs и downstream, а не только переименовать text в request.

**Различающие тесты и сохраняемое поведение.** Два разных problem statements доходят до resolver как разные запросы; отсутствие resolver/empty specs не считается отсутствием потребности или выполненным acquisition. Explicit specs и typed any-of gap не перезаписываются. Один разрешённый local fixture-source через настоящие contracts даёт receipt и повтор зависимого расчёта; отказ прав/бюджета сохранён.

**Не считать исправлением.** Не синтезировать family-authority, не выдавать URL/план за новые данные, не запускать live acquisition или платную сеть ради приёмки.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-046:** Этап 2/2 и accountable closure: actual N7 caller/receiver/consumer, включая r08 correction; REQ-01 — обязательная часть. Accountable closure: **ACQ-01**; необходимые пакеты: REQ-01, ACQ-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py
policy-engine/src/polisyos/runtime/quality/generation_cycle.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/data_requirement/compiler.py
policy-engine/src/polisyos/runtime/quality/world_model_record.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_acq_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** CYC-01, CYC-02, CYC-03, CYC-04, CYC-05, EMP-01, FRC-01, FRC-02, RES-03, SIM-01. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B12

Источник B_r19, строки 337–348; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B12 -->
## B12. Между планом приобретения основания и его исполнением нужен связующий шаг

*Источник карточки: A:B12. Унаследовано из прочитанной сводки A; не новый интеграционный прогон.*

**Происхождение и подтверждение:** P1/P2; код. В `run` результат `_plan_n7_requirement_gap_if_requested` сохраняется; `_run_n7_acquisition_if_requested` находится в `else`. Наличие типизированного плана само по себе не означает исполнение; `acquisition_required` переводит обычное продолжение к эскалации. Отдельные acquisition-job и overlay re-entry уже есть. [A.R04: 2820–3070, 3330–3590; A.R07]

**Экономное расширение:** проверенный план → проверка уже имеющихся разрешений и бюджета → существующий job → принятие данных владельцем → существующий re-entry → повтор зависимого расчёта. Начать с одного действительно разрешённого семейства, а не полной автономии по всем источникам.

**Критерий:** новые данные реально получены, приняты и изменяют зависимый расчёт. План, неподтверждённый ответ или новый URL не считаются world growth. Пробел лицензии, метода, соответствия или полномочия не переклассифицируется в нехватку строк.

**Ограничение и приоритет:** утверждение «acquisition отсутствует» отвергнуто. Разрыв локализован в композиции планирования/исполнения. Средняя сложность; полезность зависит от выбранного типа реального пробела.

<!-- SOURCE_END B:B12 -->

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

