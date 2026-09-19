# Защищённые legacy-разграничения LK01–LK36

Ниже неизменённые source K01–K36. Активные checkpoints — CP1–CP6; не путать их с source K.

<a id="lk01"></a>
## LK01 · задачи PCL-01, FRC-02, BKT-02, CAL-01, DDM-01, DDM-02

<!-- SOURCE_BEGIN LK:LK01 -->
## K01. polisyos.calibration и foundry/calibration

README явно разводит predictive calibration diagnostics/recalibration и parameter calibration симулятора. DDM calibration имеет третью роль: мониторинг drift. Совпадение имени не означает общую заменяемую реализацию.

**Решение:** Сохранить роли; объединять только доказанно одинаковые primitive helpers без переноса ответственности. [E32]

<!-- SOURCE_END LK:LK01 -->

<a id="lk02"></a>
## LK02 · задачи CYC-01

<!-- SOURCE_BEGIN LK:LK02 -->
## K02. foundry/data_plane и fabric/data_plane

Foundry input binding связывает внешние артефакты с runtime state и method contracts; Fabric отвечает за свой data-plane. Два файла в Foundry не делают intake устаревшим.

**Решение:** Сохранить input-binding границу; рассматривать дробление большого bindings.py как modularity-task, не как удаление legacy. [E33, E36]

<!-- SOURCE_END LK:LK02 -->

<a id="lk03"></a>
## LK03 · задачи FRY-01, DFK-01

<!-- SOURCE_BEGIN LK:LK03 -->
## K03. schemas/abi_models.py

В прочитанной части это ABIModelEntry registry со ссылками на настоящие DTO и schema files, а не дублирующие определения этих DTO.

**Решение:** Не переносить весь реестр в один продуктовый домен по числу файлов. Возможность generative consolidation требует отдельной проверки downstream generation. [E35]

<!-- SOURCE_END LK:LK03 -->

<a id="lk04"></a>
## LK04 · задачи ECO-01, FED-01

<!-- SOURCE_BEGIN LK:LK04 -->
## K04. fabric/numerics/finite.py

Малый модуль выполняет реальные boundary-checks: finite, non-negative и probability. Небольшая чистая функция может быть правильным законченным компонентом.

**Решение:** Оставить, пока не найден семантически эквивалентный shared helper с теми же error/clamp/typing semantics. Из одного имени generic utility вывод о дублировании не следует. [E34]

<!-- SOURCE_END LK:LK04 -->

<a id="lk05"></a>
## LK05 · задачи GRF-01, API-01, CAU-01

<!-- SOURCE_BEGIN LK:LK05 -->
## K05. foundry/methods/catalog/causal/id_engine/

Пакет содержит настоящие core/transport/counterfactual/api; пустой соседний id_engine.py — другой объект.

**Решение:** Удаление LA-007 никогда не распространяется на package. Его доказательную и численную корректность этот legacy-аудит не аттестует. [E11, E12]

<!-- SOURCE_END LK:LK05 -->

<a id="lk06"></a>
## LK06 · задачи SEL-01, FRY-01, FRY-03, ECO-01

<!-- SOURCE_BEGIN LK:LK06 -->
## K06. foundry/_registry.py и catalog/mechanism/runtime.py

Registry уже является view над MethodRegistry, а runtime.py связывает method ABI с state-transition implementation. Наличие adapter и kernel оправдано разными ролями.

**Решение:** Не заменять view вторым реестром. Дороговизну повторного построения descriptor-view, если она проявится, исследовать отдельно от retirement. [E01, E06]

<!-- PAGEBREAK -->
<!-- SOURCE_END LK:LK06 -->

<a id="lk07"></a>
## LK07 · задачи CAN-01

<!-- SOURCE_BEGIN LK:LK07 -->
## K07. Runtime JSON и строгий канон — разные контракты

common.serialization.JsonDataVisitor служит JSON-safe преобразованию runtime values и имеет собственные cycle/depth/unsupported policies. Строгий канон участвует в устойчивой идентичности и typed round-trip. LA-021 объединяет две копии строгой механики, а не все сериализаторы по сходству имени. [E45, E46, E64]

<!-- SOURCE_END LK:LK07 -->

<a id="lk08"></a>
## LK08 · задачи FRY-03, ECO-01, PLG-01, PLG-03

<!-- SOURCE_BEGIN LK:LK08 -->
## K08. DomainPlugin не равен FoundryMethodPlugin

State factory, rewards, objectives, lifecycle и observations доменного plugin не покрываются одним методом pure_step. Общая discovery-инфраструктура полезна, но смена entry-point group без bridge меняет ABI. Поддержанные runtime registries могут оставаться отдельными lookup-структурами. [E49, E50, E51, E52, E66]

<!-- SOURCE_END LK:LK08 -->

<a id="lk09"></a>
## LK09 · задачи SCL-01, SCL-03

<!-- SOURCE_BEGIN LK:LK09 -->
## K09. Поиск, seed acquisition и enrichment не являются тремя копиями поиска

Discover принимает URL/files/bytes, search находит и ранжирует источники и фрагменты, orchestrator выполняет документный и claim-процесс. Объединению подлежат транспорт и граница повторного использования snapshot, не все три поддерева. [E56, E57, E58, E59, E60]

Ни техническое совершенство соседнего кода, ни слово canonical не являются доказательством взаимозаменяемости. Новый адрес функций должен уменьшать число конкурирующих исполнителей; простое перемещение старого алгоритма без смены зависимостей и контрактов не завершает смысловую миграцию.

<!-- PAGEBREAK -->

<!-- SOURCE_END LK:LK09 -->

<a id="lk10"></a>
## LK10 · задачи UDF-01, UDF-02, DFK-01

<!-- SOURCE_BEGIN LK:LK10 -->
## K10. Малый materialize.py выполняет настоящую функцию

Его AssetDefinition связывает спецификацию с callable; декоратор сохраняет связь; plan_asset_specs упорядочивает зависимости и отвергает отсутствующую зависимость и цикл. Три контрольных случая P20–P22 прошли на выбранной исходной функции с минимальными fixture-спецификациями. Это не полный materialization executor, но и не бессодержательный placeholder. **Сохранить реальные контракты и planner; не приписывать ему неисполненные возможности распределённой системы.** [E72]

<!-- SOURCE_END LK:LK10 -->

<a id="lk11"></a>
## LK11 · задачи UDF-02

<!-- SOURCE_BEGIN LK:LK11 -->
## K11. Academic shadow — не обязательно остаток, который пора выбросить

В прочитанном loader проверяются schema generation, текущая materialized schema identity и согласованность готовности потребителя. Там же есть inventory и дифференциальный отчёт. В skg.py — реальная read-only DuckDB-инспекция. Название shadow и упоминание legacy-входов не отменяют текущую read-функцию после завершения cutover. **Не удалять на основании названия; отделять поддержку сохранённых данных от необязательного исторического сравнения только по найденным потребителям.** Нативный DuckDB здесь не запускался. [E90, E91]

<!-- SOURCE_END LK:LK11 -->

<a id="lk12"></a>
## LK12 · задачи UDF-01, OBS-01, UDF-02, OBS-02, UDF-05

<!-- SOURCE_BEGIN LK:LK12 -->
## K12. read_api содержит проверки, а не только forwarding

В Ukraine read_api кроме ленивых экспортов есть проверка и сохранение точных bytes, размеров и hashes и явные ограничения назначения receipts. Это не лишняя оболочка, которую можно обойти прямым открытием файлов. В то же время D5 receipt не является готовым сертификатом любого демографического каталога. LA-032 использует этот подход как существующий материал для адаптера, а не автоматически расширяет его область. Чистый build_static_aging_state также остаётся полезной отдельной операцией. [E87, E88]

<!-- SOURCE_END LK:LK12 -->

<a id="lk13"></a>
## LK13 · задачи GRF-01, API-01, BER-01

<!-- SOURCE_BEGIN LK:LK13 -->
## K13. BERL — не целиком legacy; раскрытый fallback может быть полезен

README закрепляет роль действующей Scientist support infrastructure. Полностью прочитанные kernels выполняют реальное вычисление, а controls показывают зависимость результата от входного background и действующие отказы. Synthetic eligibility rows прямо названы fixtures для smoke/release tests; прочитанный release-report formatter лишь выводит переданные ограничения validation. Это не даёт основания удалить BERL, его benchmarks или весь adapter layer. LA-034 и LA-036 относятся к точным format/identity поверхностям, а не к бесполезности explainability-функции. Сам факт существования narrow fallback допустим; он должен оставаться различимым с запрошенным специализированным методом. [E111–E115, E123, E134–E135]

<!-- SOURCE_END LK:LK13 -->

<a id="lk14"></a>
## LK14 · задачи DDM-01, DDM-02

<!-- SOURCE_BEGIN LK:LK14 -->
## K14. DDM monitoring и N11 confidence accounting не являются заменами

DDM monitor действительно составляет shift/degradation/quality/readiness/incident outputs. В просмотренном GY-N11 reuse-census прямо записано сохранить DDM в O2 monitoring family, не копировать его alpha-wealth как durable N9/N11 authority и не считать новый ledger реализацией generic FDR algorithm. Поэтому наличие более развитого accounting-плана **не основание удалить DDM multiple_testing или заменить его импортом Runtime ledger**. [E124–E128]

Это не аттестация FDR-гарантий `OnlineFDRController`: его математическая допустимость в конкретном мониторинговом режиме требует отдельной проверки. Прочитанный план выражает роль и запреты, но не доказывает, что все плановые свойства N11 реализованы и работают сейчас. В r04 ни DDM pipeline, ни N11 runtime не исполнялись. Рассмотренные YAML и Python readiness-представления также не признаны взаимозаменяемыми лишь по соседству и сходству порогов.

<!-- SOURCE_END LK:LK14 -->

<a id="lk15"></a>
## LK15 · задачи REP-01, MIG-02

<!-- SOURCE_BEGIN LK:LK15 -->
## K15. Старый RunManifest сохраняет самостоятельный on-disk контракт

`runtime/manifest.py` явно обслуживает сохранённые run directories, локальную диагностику и bootstrap replay; в `runtime/api.py` есть действующие write/audit/journal-recovery операции. Наличие более новых Core runtime DTO не доказывает эквивалентности persisted schema. В r04 полный mapping между ними не строился. Сохранить reader/writer и старые fixtures до согласованного format converter; не удалять всё Runtime из-за compatibility-ролей `replay.py`. [E129–E130]

<!-- SOURCE_END LK:LK15 -->

<a id="lk16"></a>
## LK16 · задачи HYG-04, CLI-01

<!-- SOURCE_BEGIN LK:LK16 -->
## K16. Runtime Reference Shell — отдельный diagnostic consumer, не прежний frontend redirect

В отличие от пустого `frontend/` из LA-013, проверенное дерево `apps/runtime-reference-shell` содержит приложение, стили, package/config, tests и architecture check. README описывает узкую static diagnostics UI без полного dashboard toolchain; прочитанный helper реально вызывает `client.listGovernedProjections()` и возвращает available/unavailable. Это положительная самостоятельная роль, не вывод о production-готовности shell. [E131–E132]

Код всего `app.js`, dashboard и generated client в этом проходе не сравнивался; equivalence их функций не доказана. Рекомендуемое действие — сохранить разницу «минимальный diagnostic consumer / product dashboard», а не удалять второе приложение по количеству UI-корней. Команды из README здесь не запускались.

<!-- SOURCE_END LK:LK16 -->

<a id="lk17"></a>
## LK17 · задачи CYC-01, HYG-02

<!-- SOURCE_BEGIN LK:LK17 -->
## K17. Явно публичный OPA facade не обязан исчезать вместе со всеми aliases

`runtime/http/opa_input.py` — четыре явных reexports sealed runtime authorization objects у того же владельца. Собственной OPA-evaluation логики там нет, но narrow public import может быть нужной границей для consumers. Не установлены ни retirement-решение, ни эквивалентный обязательный публичный заменитель. Поэтому файл не добавлен в delete/retire manifest. Существование compatibility-фасада — сигнал выяснить его договор, не автоматическое доказательство legacy. Полные authorization/middleware implementations и их consumers здесь не аудированы. [E133]

<!-- SOURCE_END LK:LK17 -->

<a id="lk18"></a>
## LK18 · задачи HYG-02

<!-- SOURCE_BEGIN LK:LK18 -->
## K18. Корневой evidence — не доказанный дубль Scientist evidence

README описывает `polisyos.evidence` как внутреннего владельца cross-producer evidence-graph records. Полный initializer явно экспортирует claim-registry normalization, conflict records и effective-independence graph operations. Это положительное основание существования отдельной роли, не ещё один случай восстановленного retired Scientist namespace из LA-008. Документ требует downstream binding и не разрешает превращать conflict materialization в положительную поддержку. **Не удалять этот корень по совпадению слова evidence.** [E153–E154]

Ограничение контроля: реализации portfolio и все runtime bridges здесь не прочитаны. README и exports не являются доказательством end-to-end корректности или полномочий этих записей. Новые функции/owners в этом аудите не назначаются.

<!-- SOURCE_END LK:LK18 -->

<a id="lk19"></a>
## LK19 · задачи DFK-02, DFI-01, DFI-02

<!-- SOURCE_BEGIN LK:LK19 -->
## K19. Catalog ingestion уже переиспользует Fabric — не всякая дополнительная стадия является вторым acquisition

В начале `core_sources/api.py` используются Fabric `AsyncFetchLease`, `FetchRequest`, connection/source-execution profiles и специализированные connectors. Это поддерживает разделение между исполнителем приобретения и batch orchestration/преобразованием/записью данных. **LA-038 не предполагает удаления Fabric connectors или переноса всей batch orchestration в Fabric.** [E137]

У source-specific `harvester.py` в r05 прочитано только начало с imports и приоритетами; его сетевые функции не сравнивались целиком с Fabric. Полная equivalence или наличие вторых HTTP-реализаций по каждой source family **не установлены**. Эта часть следующей очереди остаётся открытой, а не подменяется новой общей карточкой «все harvesters — legacy».

<!-- SOURCE_END LK:LK19 -->

<a id="lk20"></a>
## LK20 · задачи CAS-01, CAN-01, UDF-05, DFK-02, EMB-01, EMB-02, EMB-03, DFI-03, SCL-03

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

<a id="lk21"></a>
## LK21 · задачи CLI-01

<!-- SOURCE_BEGIN LK:LK21 -->
## K21. Полная generated-output freshness-проверка уже существует

В нынешнем `tools/devx/architecture/guardrails.py` есть `_measure_required_generated_artifacts`: выделение required families, isolated source/environment, запись генераторов в scratch, перечисление фактически выпущенных files, проверка единственного зарегистрированного owner, bytes, лишних/недостающих outputs и worktree escape; неисполненные измерения отделяются через `GeneratedArtifactCheckUnrunError`. Поэтому ограниченный raw checker из LA-043 **не доказывает репозиторного отсутствия canonical freshness gate**. Общий механизм — кандидат для переиспользования при retirement старого checker-path. [E162]

Журнал 2 сентября описывает запуск полного набора и positive corruption test; это исторический результат автора журнала, не наш повторный запуск. В r06 общий механизм прочитан по указанным диапазонам, включая полное тело измерения, но не исполнен. Не повышать source inspection до подтверждения свежести текущих пяти файлов. [E164]

<!-- SOURCE_END LK:LK21 -->

<a id="lk22"></a>
## LK22 · задачи CLI-01

<!-- SOURCE_BEGIN LK:LK22 -->
## K22. Канонизатор и recursive normalizer не равны лишней копии клиента

Канонизатор действительно устраняет независимые DTO bodies в публичной поверхности и привязывает aliases к schema types; его коллизионные/структурные отказы проверены локально. Обе shell-команды явно используют recursive-type normalizer. Даже при снятии raw committed pair нужно сохранить эти обязанности либо доказать их эквивалентное выполнение в текущем generator. Одно совпадение имён файлов и строковых методов такой эквивалентности не устанавливает. Нормализатор содержательно не аудирован и здесь не запускался. [E158–E159, E161]

<!-- SOURCE_END LK:LK22 -->

<a id="lk23"></a>
## LK23 · задачи HYG-04, CLI-01

<!-- SOURCE_BEGIN LK:LK23 -->
## K23. Небольшой terminal styleguide и RuntimeMiddlewarePlugin — не мёртвые CLI/плагины

Полное дерево `packages/cli` показывает библиотеку styleguide; package export — `./styleguide`, а не executable `bin`. Прочитанные tokens и format-status формируют ASCII status/progress strings. Отсутствие исполняемой CLI-команды не противоречит этой узкой заявленной роли. Независимая проверка истинности `verified` не обещается самим formatter; статус передаёт вызывающий код. Не переносить туда Runtime admission и не удалять библиотеку только из-за названия. Реальные consumers, Unicode display-width и полнота её temporal presentation требуют отдельного исследования. [E171–E173]

`runtime/extensions/api.py` определяет runtime-checkable Protocol с metadata/create. Это маленькая публичная типовая граница, не незавершённая concrete middleware implementation. Consumer census и extension lifecycle не выполнены, поэтому файл не добавлен в D-очередь. [E174–E175]

<!-- SOURCE_END LK:LK23 -->

<a id="lk24"></a>
## LK24 · задачи REQ-01, ACQ-01

<!-- SOURCE_BEGIN LK:LK24 -->
## K24. Неиспользуемый extractor не делает неиспользуемыми исторические readers и resolver guards

LA-045 исключает из очистки active construct extractor, opt-in heuristic и legacy-scenario fallback. Их вызовы видны в полном compiler. LA-046 различает возникновение candidate construct и действительный результат capability resolution: в probes использован только recording resolver. Сохранить требование injection для mandatory mode и family projection denials; устранение lexical defaults не должно возвращать authority selection по старым family strings. [E166–E169]

<!-- SOURCE_END LK:LK24 -->

<a id="lk25"></a>
## LK25 · задачи MIG-05, DFK-01

<!-- SOURCE_BEGIN LK:LK25 -->
## K25. Data Forge graph migration не равен двум линейным runners

Полная реализация допускает несколько переходов из одной версии, сортирует исходящие рёбра и строит кратчайший путь. В контрольном графе с двумя равными по длине путями порядок регистрации не изменил выбранные `low → vialow`; повтор exact-edge отвергнут, формат двухкомпонентной версии не прошёл schema validation. Это самостоятельные полезные свойства. Его shallow copy и отсутствие auto-stamping прямо соответствуют описанной функции, хотя их нельзя подменять Common guarantee. **Не удалять registry и не объявлять его готовой заменой Common/IR.** [E180, E195–E196; r07-P10–P12]

<!-- SOURCE_END LK:LK25 -->

<a id="lk26"></a>
## LK26 · задачи MIG-01

<!-- SOURCE_BEGIN LK:LK26 -->
## K26. Текущий Trinity loader действительно вызывает validator

`load_trinity_bundle` вызывает model validation после parsing/Mapping-check; `split_to_bundle` при mapping тоже его вызывает. Незадействованная self-edge из LA-049 не означает, что весь IR принимает произвольный current-version payload. В настоящем source path есть отдельный validator owner и тесты valid/invalid loading; в локальном исполнении его вызов проверен с модельной фикстурой. **Не убирать loading guard и не объявлять доказанный обход runtime admission.** [E190–E193; r07-P13–P17]

<!-- SOURCE_END LK:LK26 -->

<a id="lk27"></a>
## LK27 · задачи MIG-01, MIG-02

<!-- SOURCE_BEGIN LK:LK27 -->
## K27. Path containment и operational binding — полезные, но другие проверки

Настоящий `resolve_artifact_path` отверг `../outside`, absolute path без разрешения и отсутствие path fields. Настоящий `validate_helper_binding` на временном TOML отказал, когда удалена требуемая contract-directory; CLI не записал output. Эти свойства сохраняются. Они не доказывают, что basename-rewrite выбрал прежний артефакт, и не заменяют release review. **Не ослаблять containment, чтобы сделать старую миграцию удобнее.** [E185, E188; r07-P24–P26]

<!-- SOURCE_END LK:LK27 -->

<a id="lk28"></a>
## LK28 · задачи MIG-04

<!-- SOURCE_BEGIN LK:LK28 -->
## K28. Маленький manifest converter не является пустым placeholder

В отличие от LA-026 с неисполняемым codegen descriptor, здесь функция реально меняет ключи и включена в опубликованный migration CLI. Слово `Placeholder` — не доказательство отсутствия ценности. Полный контрольный payload после преобразования принят действующим DatasetManifest. **Переносить конкретную обязанность и регистрацию, а не удалять Common migration API или все manifest readers.** [E181–E186; r07-P27–P29]

<!-- SOURCE_END LK:LK28 -->

<a id="lk29"></a>
## LK29 · задачи FRC-01, FRC-02, BKT-02

<!-- SOURCE_BEGIN LK:LK29 -->
## K29. S10-запись, численная диагностика и production admission — разные уровни

S10 models/builders имеют ненулевой знаменатель для pass, арифметическую согласованность, temporal ordering и purpose denials. Generation-cycle value port содержит отдельные EvalSafety/WMR/candidate bindings; путь promotion — отдельные runtime/epoch gates. Они были прочитаны адресно, но не исполнялись в r08. LA-051 не даёт основания удалить эти проверки или утверждать доказанный обход production admission. Устранение суррогатных показателей полезно даже при наличии последующей защиты. [E200–E201]

<!-- SOURCE_END LK:LK29 -->

<a id="lk30"></a>
## LK30 · задачи FRC-01, PCL-01, FRC-02, BKT-02

<!-- SOURCE_BEGIN LK:LK30 -->
## K30. Shared calibration — работающий вычислительный владелец, но не готовая полная замена N8 calibration

`evaluate_continuous` действительно использует наблюдения, интервалы и при наличии samples — PIT/ENCE. На проверенном непустом corpus он различает 95% и нулевое покрытие; строгие ошибки lengths/bounds/missing evidence работают. Это положительный материал для миграции, не ещё один placeholder. Но правильный experimental estimand и привязка к выбранному causal method не возникают автоматически из generic функции. Foundry parameter calibration и DDM drift calibration остаются отдельными ролями. [E202–E203, E208; r08-P09–P18]

<!-- SOURCE_END LK:LK30 -->

<a id="lk31"></a>
## LK31 · задачи REQ-01, ACQ-01

<!-- SOURCE_BEGIN LK:LK31 -->
## K31. N7 уже имеет реальные пути явного требования; fallback не означает, что весь acquisition устарел

Проверенные typed-gap и explicit-spec branches обходят старый scenario adapter. Mandatory resolver guard в настоящем compiler продолжает поднимать ошибку при отсутствии injection. Empty specs не превращаются в выполненный acquisition. Поэтому LA-046 не предлагает удалить closed-loop planner, verified receipt re-entry или весь DataRequirementCompiler. Улучшается конкретный legacy handoff, а не возвращается выбор authority по строковым family labels. [E200, E210; r08-P27–P33]

<!-- SOURCE_END LK:LK31 -->

<a id="lk32"></a>
## LK32 · задачи PCL-01

<!-- SOURCE_BEGIN LK:LK32 -->
## K32. TruthfulnessReceipt исполняет reconciliation, а не повторную калибровку

Полный `_truthfulness.py` проверяет согласованность runtime/declared/effective tier и сохраняет scope. В r08 его настоящая модель приняла `runtime_only / predictive_calibration`. Это не делает модель лишней: входной calibration report передал положительный tier, и receipt не обязан угадывать отсутствующий внешний эксперимент. Исправление LA-052 должно находиться у производителя пригодности и report projection, сохраняя generic reconciliation и не расширяя diagnostic receipt до полномочий на решение. [E207, E211]

<!-- PAGEBREAK -->
<!-- SOURCE_END LK:LK32 -->

<a id="lk33"></a>
## LK33 · задачи DDM-01, DDM-02

<!-- SOURCE_BEGIN LK:LK33 -->
## K33. Существующая validity-проверка нужна; исторический FP pass не равен текущей применимости

`check_calibration_validity` действительно отличает истечение от совпавшего invalidation trigger, сохраняет конкретные причины и допускает непосторонний текущий случай. Два отчёта с одинаковым holdout pass могут иметь разные сроки. LA-054 использует этот действующий owner вместо нового отдельного срока. Проверенный state/gate pipeline не запускает никаких реальных deployment actions; поля incident — инструкции/данные для дальнейшего потребителя. Нельзя описывать локальный `promotion_allowed=True` как состоявшееся развёртывание модели. [E218, E220–E221; r09-P03–P06]

<!-- SOURCE_END LK:LK33 -->

<a id="lk34"></a>
## LK34 · задачи DDM-01, DDM-02

<!-- SOURCE_BEGIN LK:LK34 -->
## K34. R2 signoff, diagnostic-only и drift-only ограничения — намеренные полезные различия

Документированный R2 override не распространяется на failed certificate, R1 или R0. Default actions из YAML и code совпали для всех пяти состояний в конечной проверенной таблице. Diagnostic-only shift исключается из readiness; сильный drift без degradation даёт R2, не R0. Это не пять одинаковых дефектных statuses и не причина заменить весь DDM одним bool. Boolean signoff сам по себе не доказывает identity/authority подписавшего лица: эта внешняя обязанность в r09 не исследована. [E216–E219, E226–E227; r09-P13–P17]

<!-- SOURCE_END LK:LK34 -->

<a id="lk35"></a>
## LK35 · задачи DDM-01, DDM-02

<!-- SOURCE_BEGIN LK:LK35 -->
## K35. Ручная DDM JSON-schema — не пустой generated-дубль

В контроле корректный ShiftDetectedEvent принят и runtime-моделью, и ручной schema. После удаления всех `p_value/e_value/ert` модель и ручная schema отвергли payload, а schema, полученная обычным `ShiftDetectedEvent.model_json_schema()`, приняла его. С другой стороны, reversed window отвергнут runtime-validator, но принят ручной schema: её shape/format правила не выражают сравнение дат. Поэтому ни один из двух путей не объявлен универсально полной заменой другого. Миграция к генерируемой схеме должна сохранять явно кодируемые guards и отличать структурную проверку от cross-field/application validation. [E214, E225; r09-P18–P19]

Этот результат не регистрируется вторым LA-034: здесь нет рекомендации удалить конкретную schema, и hand-written `anyOf` имеет продемонстрированную ценность. Формат дат действительно проверялся `jsonschema.FormatChecker`; отсутствие channel не является побочным эффектом выключенного date-time validation.

<!-- SOURCE_END LK:LK35 -->

<a id="lk36"></a>
## LK36 · задачи RUN-01

<!-- SOURCE_BEGIN LK:LK36 -->
## K36. Async bridge работает; маленькая типовая очистка не отменяет его исполнительный контракт

Нативные coroutine, executor и ContextVar проверки дали совпадающие результаты до/после in-memory cleanup. Это защищает ограниченную LA-057, но не аттестует все комбинации event-loop affinity, fork, nested executor saturation или подавления cancellation. Cooperative cancellation не превращается в доказанный hard real-time deadline. Удаляется только ненужный типовой residue; остальные функции не названы legacy из-за сложности или размера. [E229–E230; r09-P23–P29]

<!-- SOURCE_END LK:LK36 -->

