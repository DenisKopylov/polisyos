# DFK-02 — один source registry и единая seed-selection policy

## 1. Решение

**Ограниченно оценён, не закрыт.** YAML стал фактическим источником полной записи; module/batch projections используют один selector, который различает None/default и explicit empty и отказывает при disabled/missing/cyclic mandatory seed. Все **35 штатных записей, 32 enabled / 3 disabled / 7 seed edges**, порядок, поля фильтрации и asset contracts подтверждены свежим исполнением. Старые Python literals ещё создаются перед canonical overwrite: это оставшийся migration scaffolding, **не доказательство второй действующей policy**.

Свежий результат: **5 MATCH; 26 unchanged existing bodies / 37 cases PASS**. Найден один low residual — predicate отдельной catalog-only entry требует connector раньше, чем общая profile selection. Native published pipeline/Fabric resolve не выполнены.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Полная карточка](../05_Источники/DFK-02_исходные_строки.txt) · [Источники](../05_Источники/C92_источники.json).

## 2. Матрица исходных IDs

| ID | Подтверждённое | Остаток |
|---|---|---|
| LA-028 / M | Canonical strict YAML, полный module/batch view, shared selection, seed errors, explicit empty,35-entry equality,36 profile-wave combinations | C92-R01 predicate parity; G01 native producer/consumer; G02 compatibility scaffolding |
| LK19 | Catalog orchestration/metadata не заменяют Fabric acquisition/connectors | Сетевые реализации не сравнивались целиком и не удалялись |
| LK20 | Content/hash equality не выдаётся за reuse/currentness/closeout admission | Full producer receipts/fresh reader qualification ещё нужна |

## 3. Actual owner и передача смысла

Canonical registry нормализует YAML sequences в tuple, сохраняет scalar types и затем применяет strict Pydantic model. Duplicate mapping keys, duplicate source identities, alias conflicts, truthy text вместо bool и неизвестные поля не теряются молча. Historical omitted version1 и положительная future version сохраняют existing behavior; это не обещание поддержки произвольного нового schema (`S01`, `S13`).

`to_module_spec` теперь переносит **все** registry fields: agency/include/exclude, format/keywords, curated requirement, history/window/budgets, connector/profile и flags. Batch owner только переименовывает source_id→name и None seed→empty string. Выбор профиля и seed closure едины; seed берётся из полного registered index и проверяется enabled/present/acyclic, результат сохраняет registry order. Mandatory dependency может пересекать wave/profile фильтр — это явное closure, не тихое включение disabled (`S01–S03`, `S11`).

`CORE_CATALOG_SOURCE_MODULES` — lazy default YAML view. Named family exports в конце модулей заменяются canonical values; временные historical declarations ещё присутствуют, но их неполные фильтры не остаются final policy. Default static cache не объявляется live registry freshness owner. В Fabric `_catalog_registry` заново получает полный registry, сравнивает effective model и инвалидирует cached selections при изменении, а actual connector join и disabled check остаются отдельными (`S05–S12`).

Read API lazy exports направляют loader к catalog owner. Native facade graph здесь не исполняется успешно; четыре service policy methods проверены отдельно с явной state/loader seam. Это глубже статического grep, но не полный selected published-catalog consumer.

## 4. Свежие различающие проверки

1. **P01:**23 existing DFK pure bodies плюс3 phase3 bodies =26 bodies/37cases PASS. Включены None vs(), disabled/missing/cyclic seed, duplicate identities, canonical registered row вместо подложенной selected copy, unknown profile даже при empty input, rich filters, custom YAML cross-wave seed, strict malformed/duplicate YAML, defaults и cross-field constraints. Existing tests не переписаны.
2. **P02:** весь checked-in35-row corpus: каждый `entry.model_dump()` равен `module.model_dump()` по всем полям; сохранены ordered IDs, assets и stage contracts. Проверены6 profiles ×6 waves (None/A/b/C/D/unknown) =36 пар. Полный corpus и matrix записаны в run04. В isolated contract-only source_modules import YAML не читался; parent shells исключают native-import claim.
3. **P03:** observational wrapper actual source factory насчитал35 transient literal constructions при reload family modules. После canonical replacement все named exports совпадают с registry. Следовательно scaffolding остаётся, но нельзя называть его текущей второй authoritative policy или заявлять измеренный performance regression.
4. **P04 / R01:** canonical custom YAML с допустимым omitted connector даёт catalog-only entry. Для prod_full и catalog_refresh `registry.enabled_sources` включает её, batch predicate=True, но `entry.included_in_run_profile` raises `connector_identity_missing`, поскольку вызывает `to_module_spec`. Control прямой execution projection по-прежнему отказывает — этот guard нужно сохранить.
5. **P05:** четыре actual Fabric methods с fixture lock/cache и actual loader отражают смену same-ID `publish_blocking=True→False` и в warm, и в fresh state; wrong connector и missing seed отказывают. Никаких plans, published receipt, index mutation или real fetch этим опытом не доказано. Existing full pipeline tests с same-stat policy change/producer reissue/fresh reader прочитаны, но UNRUN.

## 5. Остатки и сохранение

**C92-R01 — low, высокая уверенность; узкая API inconsistency.** [Entry predicate](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/domains/catalog/registry.py#L85-L98) маршрутизирует простой profile question через executable module projection. Передать его непосредственно existing shared predicate, как batch owner, и проверить parity на catalog-only omitted-connector/disabled/unknown-profile cases. **Не** ослаблять to_module_spec или actual connector intake. Для всех35 штатных строк этот дефект не воспроизведён; production failure не заявлен.

**C92-G01 — native цепочка.** В supported Python3.14 выполнить existing public consumers и два опубликованных full-pipeline tests: current receipt, same-ID policy change при прежнем stat, warm/fresh readers, producer reissue и disabled seed без мутации индекса. Это может быть общим LANE-08 integration witness. Локальный YAML/selected-method success не подменяет его.

**C92-G02 — завершение migration.** Убрать ненужное создание ручных literal specs из compatibility family surfaces, оставив canonical source-ID projection или generated view и прежние public names/order. Это локальная уборка существующего owner, а не новая catalog platform. Current effective values уже едины; не объявлять сломанными полезные projection/equality controls из-за ещё не удалённых деклараций. После изменения повторить golden corpus/native import; реальная execution policy остаётся богатой, не lossy ModuleSpec.

**Сохранить:** strict admission без coercive bool, полноту полей, typed dependency reasons, registered-row dependency ownership, порядок, assets/stages, empty/default distinction, cross-wave mandatory seed и его enabled guard, fresh registry comparison/connector join. Не удалять реальные Fabric connectors или переносить всю batch orchestration в Fabric. Hash/manifest equality не устанавливает source authority, currentness или право на reuse.

## 6. Воспроизводимость

[Commands/exit/logs](../04_Проверки/C92_DFK02/commands.json) · [Diagnostics](../04_Проверки/C92_DFK02/bounded_diagnostics.json) · [Ordered corpus](../04_Проверки/C92_DFK02/run04/ordered_catalog_projection.json) · [Profile/wave matrix](../04_Проверки/C92_DFK02/run04/profile_wave_matrix.json) · [Native status](../04_Проверки/C92_DFK02/native_verification.json) · [Оснастка](../04_Проверки/C92_DFK02/Чтение_и_границы.md) · [Остатки](../01_Реестры/C92_остатки.json).

Run04 exit0. Run01/02 import/parse compatibility limits и run03 service extraction error сохранены; это не product failures. В run03 те же37 cases уже PASS, но повторный run04 не удваивает счётчик. Actual YAML/Pydantic/registry/selection/source modules/batch/assets исполнены; supporting alias/Enum/error class взяты unchanged, parent shells и read-API loader seam перечислены. Actual PEP695 selector работает на Python3.12; blanket syntax limitation не применяется к нему.

Native registry/service imports BLOCKED на транзитивном Core store except syntax, pytest/DuckDB отсутствуют. Полный RetrievalService, real database/published receipts/network intake не запускались. Endpoint strings не использовались для сетевых вызовов. Репозиторий и зависимости не менялись.

**92/127 рассмотрены ограниченно. Следующий — DFI-01, затем точная очередь LANE-08. Фаза 2 не начата.**
