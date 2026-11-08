# PolicyOS: техническая спецификация связывания переменных и входов моделей

> Для агента-реализатора: выполнять проверяемыми пакетами через существующих владельцев. При необходимости использовать `superpowers:executing-plans` или `superpowers:subagent-driven-development`, но правила `AGENTS.md`, текущий E02-план и реальные конфликты владения имеют приоритет над универсальным процессом навыка. Этот документ не запускает реализацию и не разрешает менять статус E02.

**Дата:** 8 ноября 2026 года  
**База спецификации:** `df809a7a835cf7ee6c97effc30e89ede285a1de0`  
**База предыдущего исследования:** `b51c99f8e777a5bf3e8e020fd45ff48ecb385e27`  
**База исторического инцидента:** `414c95e4f374b88aeb8241d7d319b5866d564341`  
**Статус:** спецификация для реализации, не доказательство реализованной capability

**Цель:** новый показатель должен проходить от реальной потребности модели до фактически потреблённого входа через версионированные описания и проверяемое соответствие, без ветки общего runtime для каждого показателя

**Архитектура:** расширить существующие Catalog, IR/model owners, DataRequirementCompiler, CGF, N7 и Foundry. Связать выбранное основание с реальным потреблением и существующим effective-basis reuse. Не создавать параллельный реестр семантики, отдельную систему authority или универсальный словарь всех переменных

**Стек:** существующий Python 3.14 / Pydantic / CAS / Catalog / DuckDB / pytest / Ruff, текущие contract, index и admission owners. Выбор нового хранилища, vector database или отдельного сервиса в эту спецификацию не входит

**Исходная спецификация:** исследование «PolicyOS: идентичность переменных, связывание данных и входы моделей», файл `policyos-variable-binding-report-2026-11-08.ru.md`. В репозитории исходная постановка: [policyos-variable-identity-research-brief.md][S01]

## 1. Что именно должен получить реализатор

Нужен не улучшенный поиск по названиям, а проверяемый путь:

**выбранная модель → действительное недостающее требование → подходящее измерение → допустимое преобразование → конкретный вход модели → фактическое потребление → честный результат для следующего потребителя**

Первый результат должен быть небольшим, но сквозным. Один правильный показатель проходит по реальным владельцам. Близкий неправильный показатель отклоняется на нужной границе. Ещё один заранее неизвестный показатель проходит тем же путём после добавления метаданных, без изменения общего runtime. Только после этого расширять многовходовые преобразования и проверять масштаб.

У работы три независимых критерия приёмки:

1. **Безопасность смысла:** несовместимый показатель не становится исполняемым входом за счёт имени, единицы или высокого score
2. **Полезная полнота:** совместимый показатель действительно доходит до потребителя, а не навсегда остаётся в безопасном отказе
3. **Реальность исполнения:** результат получен через реальный producer, сохранённый artifact и actual Foundry input, а не через вручную собранный DTO или мок потребителя

Прохождение одного критерия не компенсирует провал другого. «Всегда отказывать» безопасно, но не реализует free growth. «Получить верное число» недостаточно, если его смысл или основание заменены.

### 1.1. Граница исходного инцидента

- `global.tax_rate`: параметр налоговой ставки, `ratio`
- `government.balance`: денежный stock, USD
- `GC.BAL.CASH.GD.ZS`: cash surplus/deficit за период в процентах ВВП

Это не три имени одной величины. Исторический отказ сохранить как отрицательный контроль. Для продолжения fiscal-модели сначала требуется реальная, отдельно произведённая потребность этой модели, а не переименование outcome-gap в другой input.

Преобразование `balance_percent / 100 × GDP` при выполнении его условий может давать денежный **поток**. Оно не создаёт stock. Переход к stock требует заданной модели изменения запаса, начального состояния, периода и всех требуемых этой моделью потоков/корректировок. Полную fiscal accounting model не реализовывать ради зелёного LANE-01.

### 1.2. Что уже проверено, а что ещё нет

Проверены исходная постановка, архитектурные решения и указанные ниже участки исходного кода. Свежий `main` на момент проверки: `df809a7a…`; сравнение с `b51c99f8…` показывает три новых commit. Проверенные variable-binding, compiler, source и Foundry owners не изменились. Новые изменения затрагивают E02 state, served-history helper, смежные тесты и аннотации Fabric tracer.

В рамках подготовки документа **не выполнялись runtime-прототип, новый защищённый запуск, unit/integration tests или benchmark**. Все численные значения ниже являются входами будущих fixtures либо условиями будущей приёмки, а не полученные результаты. Статусы E02 из исторической постановки нельзя выдавать за текущую проверку.

## 2. Организация работы и ограничения

### 2.1. Вход в текущую работу

- [ ] Прочитать `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, корневой `E02-WORK-PLAN.md` и актуальные записи назначенного пакета
- [ ] Зафиксировать фактические branch, HEAD, рабочее дерево и используемый environment. Сопоставить с базой этой спецификации, прочитать относящийся к ней diff
- [ ] Согласовать с текущим координатором одного writer на каждый пересекающийся механизм и его mirrored tests. Не запускать второй owner для уже занятого пути
- [ ] Зафиксировать в существующей записи задачи: producer, artifact, bridge, consumer, проверку и публичную проекцию. Не заводить второй действующий E02-план
- [ ] До дорогой проверки заморозить только её реальный набор входов. Чужой документационный commit сам по себе не обнуляет результаты по неизменным inputs

Эта русскоязычная спецификация является передаваемым пользователю документом. Если её положения включаются в репозиторий, включать их на английском в существующие design/reference/plan owners. Не создавать датированный параллельный workflow и не переносить весь документ в `AGENTS.md`.

### 2.2. Запрещённые способы «починки»

1. Alias между tax rate, fiscal flow и government stock
2. Подмена отсутствующего model-input producer вручную изготовленным requirement в единственном e2e fixture
3. Новые ветки `if variable_id == ...` в общем пути для каждой отрасли или серии
4. Замена scientific correspondence полями `exact=true`, `confidence=1`, signature, ID или hash, созданными тем же mapping producer без независимого основания
5. Удаление защитных условий старого World Bank/country-year профиля ради расширения
6. Применение `latest` вместо выбранных immutable refs во время исполнения
7. Автоматическое повышение candidate-only результата при readback, export или повторном использовании
8. Объявление complete readset для произвольной непрозрачной программы
9. Закрытие criterion после любого exception, мокнутого N5 или заполненного certificate-looking JSON
10. Изменение LANE-01/G acceptance или всего E02 только потому, что локальный новый тест стал зелёным

### 2.3. Что не входит в первую реализацию

Универсальная мировая онтология, доказательство всех научных соответствий, произвольный исполняемый код в метаданных, полный causal transport для новых доменов, произвольная реконструкция stock, новая платформа авторизации и замена всех существующих adapters. Они не нужны, чтобы проверить предложенный механизм.

### Review focus

- Пустой набор explicit rules незаметно запускает name-based inference: P04, V09
- Dependency впервые читается на позднем шаге горизонта: P03/P04, V08
- Законно различные operands отвергаются универсальным равенством scope: P06, V15
- Одинаковый scalar скрывает новый release или revocation: P05, V11/V12
- Отсутствующий metadata axis становится wildcard либо причиной вечного отказа: P02/P07, V05/V19

## 3. Контракт механизма

Названия новых типов и функций в этом разделе **предлагаются спецификацией**, а не выдаются за существующий API. Перед добавлением сверить ближайший существующий owner. Если эквивалентный тип уже есть в более новом HEAD, расширить его и записать однозначное соответствие имён. Требования к данным и проверкам при этом сохраняются.

### 3.1. Разделить шесть идентичностей

| Объект | Обязательное содержание для нового пути | Канонический владелец |
|---|---|---|
| Semantic definition | Namespaced stable ID, immutable revision/ref, автор определения, смысл величины, основание определения | Catalog/L2 и существующий custodian определений |
| Representation/measurement profile | Только необходимые для данного вида величины grain, numerator/denominator, stock/flow/parameter, unit/scale, aggregation, time support, method/base, cardinality/shape, missingness и правила координат | Catalog/measurement owner |
| Model input requirement | Выбранная model/interface revision, input port/slot, producer basis, purpose, причина необходимости, требуемый профиль и действительный недостающий input | Выбранный model/interface owner, затем compiler |
| Observation | Exact source, dataset/release/profile, координаты, значение, uncertainty, provenance, права и временные роли | Catalog/source admission |
| Transformation/relation | Направление, тип, версии сторон/оператора, область применимости, зависимости, доказательства и ограничения | Действующие CGF/verification/operator owners |
| Executable binding | Точное соединение requirement, observation/derivation, model port и допущенного использования | Compiler + текущий binding/admission owner |

Label, alias и provider code служат поиску и не заменяют эти объекты. Страна/год обычно являются координатами observation, а не поводом создавать новую semantic identity. Изменение denominator или методики может менять определение и должно быть представлено явно.

Для нового пути `ownerA:balance` и `ownerB:balance` различаются. Слияние возможно только через направленное, ограниченное relation с собственным основанием. Одинаковые строки definition или hash не переносят полномочия между owners.

### 3.2. Обязательство модели: не путать роль и необходимость данных

Предлагаемый логический контракт `ModelInputObligation` должен сохранять:

- exact ref выбранной модели, исполняемого interface и producer event/basis
- port/slot/state-path binding в этой версии модели
- требуемый semantic/representation profile и координатный scope
- назначение: например simulation input, initial state, calibration или outcome validation
- основание необходимости: actual required dependency, precondition выбранного метода либо отдельный claim obligation
- существующее значение/правило его получения или reason, почему его не хватает
- связь с исходным candidate/problem/request и решение о допустимой authority band

Тип роли не запускает acquisition автоматически. При `do(tax_rate=0.2)` значение `0.2` уже поставлено интервенцией. Предсказываемый outcome не всегда требует observation. Уже связанный initial state не должен снова запрашиваться у источника. Метод оценки, напротив, может требовать observation, даже если симулятор способен вычислить результат без него.

Producer обязан различать эти случаи. Compiler не имеет права превратить недостаток outcome observation в другую потребность модели. `ModelSpec` сейчас владеет механикой и assumptions, но **не содержит полного typed per-port input manifest**. `CandidateSimulationSyntheticModelDeclarationV1` тоже не является таким manifest и не даёт эмпирической causal authority [S04].

### 3.3. Предварительный план, исполнимый manifest и факт потребления

Сохранять направленную цепочку, без циклических ссылок:

1. **План получения входов:** requirement refs, кандидаты источников, проверки и неразрешённые зависимости. Может быть сохранён до приобретения observations, но не исполняется как готовый binding
2. **Resolved binding manifest:** exact observations/выходы derivation, версии definitions, model port, profile, operator DAG и проверяемые relation/admission refs. Создаётся после разрешения необходимых inputs
3. **FoundryInputBindings:** правила из выбранного manifest, snapshot и bound state. Ссылка на manifest входит в новую версию существующего контракта
4. **FoundryExecutionInputBasis:** уже ссылается на exact `input_bindings_ref`; через него достигает manifest. Не дублировать прямую ссылку без отдельной необходимости
5. **Результат reconciliation/readback:** подтверждает соответствие выбранного manifest фактически применённым bindings и входам конкретного шага. Ссылается на уже существующие артефакты

Предварительный immutable manifest не должен ссылаться на ещё не созданный execution receipt. Замыкание такой ссылки через mutable поля или последующую перезапись CAS недопустимо. При необходимости pre-acquisition plan и resolved manifest являются двумя immutable стадиями существующего artifact flow, а не новой глобальной status lattice.

Для каждого binding необходимы как минимум:

| Группа | Содержимое |
|---|---|
| Origin | requirement/producer/candidate/model/port refs |
| Meaning | semantic definition revision, representation profile revision, выбранный purpose |
| Data | observation/release/descriptor refs, exact selectors и координаты |
| Computation | operator revisions, входы/выходы DAG, параметры, unit evidence, cardinality/shape/missingness/precision policy и применённые rules |
| Justification | relation/verification refs, профиль обязательных предикатов, evidence classification, ограничения |
| Selection | выбранный index/reference snapshot, информация о неполноте поиска, alternatives и основание конкретного выбора |
| Lifecycle | schema/rule versions и ссылки на зависимости currentness/staling, без подмены времён единым `as_of` |

Exact source occurrence не исключать из истории, даже когда его численные значения совпадают с предыдущим release. В canonical numerical-basis projection не включать display alias только потому, что он присутствует в полном объекте.

### 3.4. Проверки профиля `measurement_to_model.v1`

`measurement_to_model.v1`: предлагаемое имя **нового ограниченного профиля**, не новый owner. В первой версии он поддерживает доказанное scoped correspondence и уже реализованную fixed multiplicative unit conversion. Derivation, proxy и causal transport не превращаются в exact.

Профиль задаёт обязательные предикаты для конкретного input/purpose. Для каждого предиката различаются подтверждение, противоречие и неизвестность. Это результаты проверки, не новая лестница authority.

- Неизвестное обязательное поле не считается wildcard
- Необязательное неизвестное поле сохраняется как limitation, но не блокирует всё без причины
- `null`, отсутствующее значение, пустая строка и ошибочно типизированное значение не превращаются в `all`/`any`
- Нельзя выбирать более слабый профиль из request только ради успешного binding
- Units, диапазон значений, уникальный ID и подпись не устанавливают semantic correspondence
- Сам mapping author не может создать обе стороны «независимого» доказательства и затем объявить их совпадение проверенным
- Пересечение scope проверяется по правилам конкретного relation/operator, а не одинаковостью всех полей у всех inputs
- CG1 остаётся shadow. Новый measurement-profile не получает production bind только из-за наличия старого mechanistic certificate

Принять конечный, проверяемый класс автоматических положительных случаев: например provider-defined series с закреплённой документацией и отдельно определённой потребностью model port, для которых approved profile даёт детерминированное соответствие. Fixture может проверять механику этого класса, но synthetic definition не доказывает соответствие реального внешнего показателя.

### 3.5. Предлагаемые интерфейсы

Это IDL-подобные сигнатуры, не готовый Python и не требование объединить всё в один модуль. `ArtifactRef`, result/ref и существующие diagnostic/status типы переиспользовать из репозитория. `ModelInputObligationSet` объединяет exact producer/interface basis, obligations и ссылки на уже удовлетворённые зависимости; `InputBindingPlanRef` и `ResolvedInputBindingManifestRef` обозначают стадии из §3.3, а не новые источники authority.

```python
produce_model_input_obligations(
    *, selected_model_ref, selected_interface_ref, prepared_request_ref,
    supplied_input_basis_ref, purpose_ref
) -> ModelInputObligationSet

compile_input_binding_plan(
    *, obligation_set_ref, catalog_snapshot_ref, resolver, profile_ref
) -> InputBindingPlanRef

resolve_input_binding_manifest(
    *, plan_ref, acquired_input_refs, relation_result_refs, admission_context_ref
) -> ResolvedInputBindingManifestRef

compile_manifest_binding_rules(
    *, manifest_ref, registry_bundle_ref, data_snapshot_ref
) -> tuple[FoundryInputBindingRule, ...]

reconcile_consumed_binding(
    *, manifest_ref, execution_input_basis_ref, observed_binding_result_ref
) -> BindingReconciliationResult
```

Каждый возвращённый ref открывается существующим artifact owner. Успех constructor/JSON schema не заменяет повторное разрешение зависимостей. Нельзя передать строку в поле `evidence_ref` и считать доказательство существующим. Producer сохраняет artifact, orchestration передаёт именно его ref, потребитель загружает и проверяет тот же объект.

## 4. Пакеты реализации

Пути ниже относительно `policy-engine/`, кроме явно названного корневого плана. Новые файлы помечены. Для каждого пакета: сначала воспроизводимый положительный контроль и различающий отрицательный тест, затем минимальное изменение, затем повторная проверка именно изменённого пути. Не переписывать полезные существующие тесты только для имитации test-first истории.

Зависимости: **P00 → P01; P00 → P02/P03; P02+P03 → P04 → P05 → Gate A; затем P06 → P07 → P08 → Gate B**. P02 и P03 допускают параллельную работу только после согласования общих DTO и без пересекающихся writers.

### P00. Зафиксировать baseline, владельцев и предел доказательства

**Изменения:** существующая запись задачи/пакета, без product code. Read set: `AGENTS.md`, `CONTRIBUTING.md`, `E02-WORK-PLAN.md`, [S01]–[S05].

- [ ] Найти действующий owner LANE-01, связанный пакет и все незавершённые изменения в намеченных файлах
- [ ] Зафиксировать конкретный supported model/interface для тонкого среза. Объяснить, как проверяются его inputs, defaults/config и шаги исполнения
- [ ] Выбрать две реальные разные границы: модель требует вход и модель уже получила `do`/initial value. Не фабриковать requirement ради маршрута
- [ ] Зафиксировать positive control, fiscal negative и хотя бы один held-out compatible extension
- [ ] Запустить только относящиеся baseline tests на выбранном checkout. Сохранить команды, полные deciding outputs и content-qualified inputs
- [ ] Разделить будущий mechanical proof и empirical correspondence. Для каждого семантического утверждения указать, что будет пересчитано, независимо сопоставлено либо останется `not_established`

**Выход:** можно назвать actual producer, persisted artifact, consumer, positive case и близкий negative. Если нельзя, не начинать общий resolver. Сначала устранить отсутствие producer/поддержанного execution interface.

### P01. Сохранить причинную диагностику исходного отказа

**Modify:** `runtime/quality/generation_cycle.py`, `runtime/quality/acquisition_planner.py`, `runtime/quality/acquisition_route_loop.py` в соответствующих reason projections  
**Tests:** `tests/unit/runtime/quality/test_candidate_n5_l1_routing.py` и mirrored tests действующего costed-route consumer

- [ ] Добавить контроль: реальный L1 producer требует `global.tax_rate`; compiled requirement сохраняет этот target
- [ ] Проверить, что zero resolutions и отсутствие routable descriptor не превращаются во внешний диагноз «два конкурирующих подходящих источника»
- [ ] Сохранить compatibility существующих outer error codes, но передавать структурированные stage/count/reason из реального owner
- [ ] Добавить различение: producer missing, no compatible source, search incomplete, semantic contradiction/unknown, missing transform input, incomplete cost basis и действительно неоднозначный маршрут
- [ ] Убедиться, что diagnostic не меняет authority, не вызывает fetch для несовместимого кандидата и не закрывает gap

**Приёмка:** исходный отказ понятен и воспроизводим. Тест проверяет точный stage и semantic target, а не просто `raises`.

### P02. Добавить минимальные versioned семантические ссылки и профиль

**Modify:** `data_forge/domains/catalog/knowledge/overlay.py`, ближайшие существующие L2 definition/alias contracts, `runtime/quality/grounding_relation.py` и соответствующий CG2 owner только в общей границе profile dispatch  
**Предлагаемые новые модули:** `core/contracts/variable_binding.py` для отсутствующих строгих public DTO, `runtime/quality/measurement_binding.py` для ограниченного measurement-to-model verification. Если эквивалент уже появился, расширять его, не создавать двойник  
**Tests:** новые mirrored `tests/unit/core/contracts/test_variable_binding.py`, `tests/unit/runtime/quality/test_measurement_binding.py`; существующие overlay/alignment/CGF tests

- [ ] Написать paired fixtures `known_correspondence`, `same_unit_wrong_denominator`, `same_label_wrong_kind`, `unknown_required_axis`, `optional_unknown`
- [ ] Ввести immutable refs определения, representation и relation там, где нынешней строки `canonical_variable` недостаточно. Сохранить старые schemas и их semantics
- [ ] Реализовать обязательные проверки §3.4. Positive проходит не из-за `alignment_method="exact"`, а из-за выбранного проверяемого класса correspondence
- [ ] Переиспользовать fixed unit executor из `overlay.py`; `20% → 0.2` проходит только с реально выполненным закреплённым transform
- [ ] Удалить/заменить property-bearing evidence в negative, оставив ID, hash marker, названия и внешний JSON shape. Новый профиль должен отказать на нужной границе
- [ ] Не передавать в новый профиль fallback «нет unit значит совместимо», population из prefix или именованные fiscal/tax правила
- [ ] Проверить смысловые conflicts во всех допустимых candidates, а не выбрать первый по insertion order

**Приёмка:** одна автоматическая положительная correspondence имеет некруговое основание; close negatives отклоняются; proxy/unknown остаются в допустимой candidate band с явными ограничениями. Изменения ещё не объявляют сквозную capability.

### P03. Произвести требования из выбранной модели и провести через compiler

**Modify:** `ir/model_layer/model_spec.py` либо конкретный существующий model-interface contract, `runtime/quality/candidate_simulation.py` только для выбранного supported adapter, `data_requirement/_impl/models.py`, `data_requirement/compiler.py`, `runtime/quality/generation_cycle.py`, `runtime/quality/acquisition_planner.py`  
**Предлагаемый helper:** `runtime/quality/model_input_requirements.py` под существующим model/interface owner  
**Tests:** новые mirrored producer tests, `tests/unit/data_requirement/test_compiler.py`, `test_candidate_n5_l1_routing.py`

- [ ] Тест `required_input_is_produced_by_selected_model`: actual selected interface требует вход, supplied basis его не содержит, producer сохраняет отдельное obligation
- [ ] Проверить preflight до первого исполнения, которому необходим этот input. Без input и без default система должна суметь сформировать acquisition. Нельзя сначала незаметно подставить default и выполнить N5, а затем объявить post-N5 outcome-gap новым producer
- [ ] Тесты `supplied_do_value_creates_no_observation_gap`, `predicted_outcome_creates_no_unrequired_observation_gap`, `calibration_requirement_remains_separate`
- [ ] Сопоставить declared inputs с реальным supported execution contract: state reads, external input bindings, parameters, defaults, seed/config и conditional dependencies в пределах объявленной поддержки
- [ ] Провести producer artifact через compiler и N7, сохранив модель, port, purpose, scope и origin. Fixture не подменяет этот этап непосредственной записью gap
- [ ] Проверить coexistence outcome-validation gap и model-input gap: оба сохраняются, ни один не переименовывается в другой
- [ ] Добавить negative `catalog_available_but_required_scope_incompatible`: общий L1 count не отменяет проверку периода, population, denominator и representation
- [ ] Для поддержанных независимых model inputs не требовать искусственно включать их в `problem.levers`/`outcome`. Доступное сейчас ограничение переносится в legacy profile, новый путь проверяет exact declared dependency closure

**Приёмка:** actual model-input producer достиг compiler; полученный requirement достаточен для правильного descriptor join и не выдаёт routing authority за scientific closure. Необъяснимый дополнительный dependency означает незавершённый supported interface, а не повод вставить default.

### P04. Связать manifest с настоящим Foundry intake

**Modify:** `core/contracts/foundry.py`, `foundry/data_plane/bindings.py`, `foundry/execute/api.py`, `runtime/quality/data_state_substrate.py`, actual N5 bridge в `runtime/quality/generation_cycle.py`  
**Tests:** existing mirrored Foundry binding/execute tests, `tests/unit/runtime/quality/test_candidate_acquisition_world.py`, `test_candidate_acquisition_prefetch_world.py`; новый integration case в текущем подходящем owner suite

- [ ] Сохранить resolved manifest в CAS и поместить ref в новую schema variant существующего `FoundryInputBindings`
- [ ] Writer должен сохранить согласованный с этим полем **role-qualified manifest edge** в существующем artifact graph. Текущий execution source inventory видит selected sources и их прямые `manifest.inputs`, а не рекурсивно любые ссылки в JSON. Новый semantic owner явно и ограниченно проверяет необходимую dependency closure; field без edge либо edge на другой ref не проходит
- [ ] Реализовать явную матрицу схем: legacy без SQL, legacy с SQL, semantic без SQL, semantic с SQL. Номера версий выбрать по действующему registry, не предполагать, что `1.2` свободна
- [ ] Обновить вместе DTO validators, writer, loader, artifact registry/schema fixtures и affected consumers. Старые artifacts остаются читаемыми без изменения content identity
- [ ] Компилировать explicit binding rules только из выбранного manifest. Проверять target, source path, transform sequence и required/default semantics
- [ ] Запретить name-based auto inference в новом manifest-required profile. Особенно проверить **`rules=[]`**: текущий `_prepare_rules` использует truthiness, поэтому пустой список тоже вызывает `_auto_rules_from_payload`
- [ ] До материализации значения проверять missingness, cardinality/shape, precision и permitted coercions выбранного port. В текущем binder explicit null может стать нулём, vector→scalar взять первый элемент, scalar→array распространить значение. Новый semantic profile не наследует эти преобразования молча: missing/null не равны наблюдённому нулю, несколько observations не равны одному scalar, broadcast или lossy conversion требуют явного допущенного transform
- [ ] Проверять единственность выбранного writer для effective destination после разрешения slot/state_path. Два разных binding IDs не должны последовательно перезаписать один target в порядке сортировки ID. Если несколько inputs законно объединяются, нужен явный admitted merge/composition с проверенным исполнением; наличие `SlotSpec.merge_rule` само по себе ещё не доказывает, что binder применил его
- [ ] Открывать manifest и его точные dependencies при подготовке и actual intake. Если выбранный ref отсутствует, похожие bytes в другом profile не подставлять
- [ ] Сопоставить expected rules/values со реально применёнными rules, bound state и `FoundryExecutionInputBasis`. Последний сохраняет purpose `execution_input_identity_only`
- [ ] Провести negative замены manifest после compilation, удаления relation, смены source profile и ошибочного target port. Ни один не должен получить новое post-binding исполнение с подменённым input
- [ ] Для горизонта проверить **каждый реально исполненный step instance**, включая dependency, впервые прочитанный на шаге 3. Один receipt первого шага не сертифицирует весь горизонт
- [ ] Fresh consumer в новом context/process открывает сохранённый результат и показывает variable/role/unit/source/profile/limitations без обращения к памяти producer

**Критические существующие швы:** `prepare_input_bindings`/`build_input_bindings`/`load_input_bindings` в `foundry/data_plane/bindings.py`; `_build_execution_input_basis`, `_admit_execution_source` и `execution_input_basis_sources` в `foundry/execute/api.py` [S09]–[S11]. Не создавать рядом второй observer, который actual executor не использует.

**Приёмка:** можно проследить exact ref от requirement до фактически потреблённого значения. При удалении доказательной зависимости ломается именно это использование. Старый lawful execution до возникновения нового gap не считается нарушением; проверяется конкретный post-binding consumer.

### P05. Обеспечить корректные reuse, staling и A → B → B → B → C

**Modify:** `runtime/quality/candidate_source_basis.py`, `runtime/quality/acquisition_evaluation.py`, соответствующие existing dependency/currentness owners; при необходимости `data_state_substrate.py`  
**Tests:** `test_candidate_source_basis.py`, `test_candidate_source_basis_chained.py`, `test_candidate_model_revision_basis.py`, действующий continuation suite

- [ ] Включить в существующий effective basis реально потреблённые semantic/model/operator/config dependencies. Не создавать ещё один независимо решающий cache
- [ ] Развести numerical identity, evidence occurrence, binding identity и current-use authority. New release с тем же числом не теряет source history
- [ ] Выполнить настоящее A → B → B → B → C на рабочем matched fixture. При повторных B сохраняются exact numerical artifact refs там, где existing contract требует reuse, но появляются новые acquisition/current decision occurrences
- [ ] При изменении зависимого значения в C actual N5 выполняется вновь. Проверять trace и новые exact refs, а не только отличающееся число результата
- [ ] Alias-only change не вызывает глобального numerical rerun. Смысловое изменение definition инвалидирует зависимый binding и требует новой проверки даже при том же scalar
- [ ] Повторное использование чистого численного результата после смыслового изменения допустимо только после отдельного подтверждения равенства полного numerical basis. Старый semantic/current claim не переносится автоматически. Консервативный отказ от reuse предпочтительнее неявного смешения
- [ ] Current revocation учитывается на соответствующей текущей границе, historical replay сохраняет исходный выбор. Различать историческое воспроизведение и новое доверие к результату
- [ ] Ввести/расширить reverse dependency lookup у существующего owner. Unrelated alias/source update не stales весь корпус. Глобальное правило может иметь глобальный эффект только по действительной зависимости
- [ ] Учитывать не только выбранные positive refs, но и область, в которой доказано отсутствие конкурирующего смысла. Добавление relevant countercandidate может опровергнуть прежнюю uniqueness без изменения выбранного artifact. Для таких bindings сохранять query/reference envelope и подписку на относящиеся к нему изменения; unrelated aliases не создают глобальную invalidation

**Приёмка:** numerical work и история evidence изменяются по разным основаниям. Положительная mechanical последовательность на другом корректном fixture не объявляется доказательством fiscal correspondence и не закрывает автоматически первоначальный CYC-03 criterion.

### Gate A. Проверка жизнеспособности архитектуры

До AND/DAG и масштабирования получить все четыре результата:

1. Реальный model-input producer → compiler → source admission → manifest → actual Foundry → fresh consumer
2. Близкий fiscal/denominator/stock-flow negative отказывается по целевой причине
3. Held-out показатель с существующим representation/operator profile проходит без изменения common runtime
4. Repeated B сохраняет numerical refs и обновляет history; changed C реально вычисляется

Отсутствие любого результата оставляет Gate A открытым. Нельзя компенсировать это большим числом DTO-тестов, обещанием будущего index или добавлением ещё одного wrapper. Архитектурные причины остановки перечислены в §7.

### P06. Обобщить AND-input bundles и ограниченный derivation DAG

**Modify:** `runtime/quality/acquisition_planner.py`, `candidate_acquisition_source.py`, `data_state_substrate.py`, contracts/bridge из P02–P04, действующий operator/transform owner  
**Tests:** `test_n7_mixed_candidate_obligations.py`, новые mirrored derivation tests и сквозной multi-input case

- [ ] Разделить AND dependencies преобразования и OR alternatives одного input. Не использовать число sources как число смысловых интерпретаций
- [ ] Версионировать нынешний helper «L1 плюс не более одного grounding gap». Сохранить старую cardinality для старого профиля, не урезать новый bundle до первого элемента
- [ ] Передавать в N7 весь неполный bundle, стоимости и ограничения. VOI оценивает decision-relevant bundle; отдельный дешёвый input не закрывает цель
- [ ] Для первого derivation поддержать только объявленный оператор ratio × denominator с явным output semantics. Входы и оператор content-bound, вычисление исполняется, а не просто декларируется
- [ ] Положительный контроль: `−3%` соответствующего GDP `200 000 000 000 USD` → `−6 000 000 000 USD` annual fiscal flow. Противопоставить GDP другого года/base/release, revenue denominator, отсутствующий input и stock target
- [ ] Проверять соответствие **роли** каждого input. Government numerator и economy-wide GDP законно имеют разный институциональный scope; требовать механически одинаковую population у всех operands было бы ошибкой
- [ ] Сохранять operator-specific совместимость geography/time/currency/base и той denominator definition, к которой относится ratio. Корректность отдельных edges не доказывает корректность композиции
- [ ] Обрабатывать cycles, missing inputs, disjoint scopes, inverse lossy mappings, NaN/inf и превышение установленного DAG budget. Метаданные не исполняются как Python/SQL/инструкции
- [ ] Не выдумывать uncertainty=0. Выполнять поддержанное правило propagation либо сохранять uncertainty limitation и ограничивать затронутый use
- [ ] Не расширять глобальный slot allowlist. Derivation dependencies разрешаются из выбранного model/interface и exact DAG closure

**Приёмка:** partial acquisition сохраняется, но target requirement остаётся открытым до полного допустимого DAG. Денежный flow доходит до flow port; тот же output не проходит в stock port без отдельной модели.

### P07. Проверить free growth и заменить повторные scans индексированным поиском

**Modify:** существующие `runtime/quality/capability_index.py`, `runtime/quality/capability_resolver.py`, Catalog alias/definition indexes  
**Tests:** `test_capability_index.py`, `test_capability_resolver.py`, controlled metadata extension suite, benchmark рядом с существующим benchmark owner

- [ ] Сохранить `CapabilityResolverPort` и authoritative validator. Index только сокращает candidates, но не выдаёт bind
- [ ] Добавить lookup по exact namespaced definition/revision, structure/scope и many-to-many aliases. Fuzzy retrieval может дополнять поиск, но не обязательно для первого proof
- [ ] Lazy-load exact evidence выбранных candidates вместо загрузки полного корпуса для каждого query
- [ ] Сравнить indexed и exhaustive reference resolver на конечном контролируемом корпусе. Совпадают admissible set/disposition при одинаковой полноте и snapshot
- [ ] Добавить два held-out домена, отличных от fiscal fixture: например health annual count и transport monthly flow. После freeze common runtime добавляются только definitions, metadata, accepted evidence и уже поддержанные registrations
- [ ] Проверить unrelated labels с правильным semantic evidence и одинаковые labels с несовместимым смыслом. Новый язык/alias не меняет exact selection
- [ ] Проверить permutations insertion order, разные namespaces, два источника одной величины, stale index и конфликтующую публикацию revisions
- [ ] В ограниченном search сохранять frontier/index snapshot/cutoff и limitation. Top-k singleton не является robust singleton. Для exact-ID положительного класса completeness ограничена его явно определённым namespace/reference envelope
- [ ] Запустить масштабный набор §6. Не объявлять system-wide free growth только по числу JSON-объектов

**Приёмка:** новые ресурсы реально расширяют доступную capability, а indexed backend не меняет semantic gate. Для routine supported queries исчезает полный повторный scan корпуса; miss и incomplete search не скрываются как scientific absence.

### P08. Закрыть миграцию и проверить соседних потребителей

**Modify:** existing versioned loaders/writers, affected API/export projections, документация текущих owners и запись E02-пакета  
**Tests:** старые exact-profile fixtures, SQL/schema matrix, consumer-removal и cross-consumer integration tests

- [ ] Old byte-exact artifacts загружаются по старому профилю; отсутствующие новые fields не получают придуманную semantic authority
- [ ] Новые current bindings используют новый profile и не падают обратно в legacy name inference при неизвестном поле/ошибке
- [ ] Действующие ограничения `worldbank.wdi`, `worldbank_wdi`, country/year и exact target остаются в своём старом профиле. Обобщение не равно их удалению
- [ ] Проверить mixed legacy/new и SQL/no-SQL combinations, serialization round-trip и стабильность historical refs
- [ ] Fresh API и применимые export/UI consumers показывают одинаковый target, role, unit, selected source, purpose и limitation. Candidate-only число не становится grounded result при другом формате
- [ ] Удалить дублирующий новый путь, если он появился во время прототипа. Старый predecessor либо явно изолирован как historical compatibility, либо удалён по разрешённой миграции с сохранением replay
- [ ] Независимый reviewer проверяет один coherent change и material deltas. Отдельная G acceptance не подменяется этим review

**Приёмка:** сохранена историческая воспроизводимость, current use не повышает authority и нет обхода через соседний consumer.

## 5. Исполняемая приёмка

### 5.1. Правило каждого теста

В существующем test/evidence record сохранять:

`ID → требование → положительный контроль → одно изменение → ожидаемая граница → наблюдаемые refs/эффекты → verdict`

1. Positive control достигает **того же** целевого consumer
2. Negative меняет проверяемое основание, оставляя остальные prerequisites рабочими
3. Проверяется точный reason и недопустимый эффект, а не любой exception
4. После negative positive повторно проходит, чтобы исключить общий отказ сервиса
5. Expected result не вычисляется тем же production resolver/transform, который проверяется
6. Если тест сломался раньше binder, verdict: `inconclusive` для данного свойства, не PASS

Expected semantic cases закрепляет reviewer до реализации. Арифметику вычислять независимо. Для реальной серии указать первичное определение, для synthetic case явно обозначить искусственно заданную семантику. Отложенный held-out набор не должен быть доступен автору resolver до freeze реализации.

### 5.2. Обязательный различающий набор

Таблица задаёт поведение, а не новые production statuses. Причины отображаются в существующие reason/limitation contracts. Все строки обязательны для заявленной поддержанной границы. Unsupported случай нельзя задним числом объявить unsupported только потому, что он провалился.

| ID / пакет | Положительный контроль и мутация | Проверяемый результат |
|---|---|---|
| V01 / P01–P04 | Реальный tax-rate input `20%` → `0.2`; подставить balance/GDP при той же dimensionless форме | Только tax-rate observation достигает нужного port; fiscal negative останавливается по смыслу |
| V02 / P02/P06 | Разрешённый monetary flow; тот же output подать в USD stock | Unit equality не разрешает flow→stock |
| V03 / P02 | Одна доля; поменять GDP denominator на revenue | Смысл меняется, высокий lexical score не спасает |
| V04 / P02/P04 | Выполненный percent→ratio converter; удалить ref или не выполнить conversion | Нельзя объявить 20 равным 0.2 по одной metadata записи |
| V05 / P02 | Required denominator известен; убрать/исказить его. Отдельно убрать необязательную методику | Первый use заблокирован; второй разрешён в своём узком scope с limitation |
| V06 / P03 | Реальный отсутствующий input; уже supplied `do` или initial state | Producer создаёт нужный gap и не создаёт искусственных |
| V07 / P03 | Simulation не требует observed outcome; выбранный calibration method требует history | Раздельные obligations и причины необходимости |
| V08 / P03/P04 | Полный declared input set; скрытый config/default/branch dependency, впервые используемый на шаге 3 | Расхождение выявлено в supported adapter; никакой ложной horizon completeness |
| V09 / P04 | Явные manifest rules; `rules=[]` плюс совпадающие payload path names | Новый профиль не запускает implicit binding и не получает required=False default |
| V10 / P04 | Exact selected refs; другой profile с теми же bytes, удалённый relation, сменённый latest | Точный intake отказывается или требует новый binding, не перечитывает latest |
| V11 / P05 | B повторён трижды; C меняет реально потреблённый input | Exact numerical refs retained для B; actual N5 и новый input basis для C |
| V12 / P05 | Новый release с прежним scalar; затем current revocation | Evidence occurrence сохраняется; numerical reuse отдельно; current authority не наследуется |
| V13 / P05 | Alias-only update; затем зависимая definition revision | Нет глобального rerun от alias; semantic dependency переоценивается |
| V14 / P06 | Ratio+GDP+operator; убрать GDP. Затем два GDP suppliers | AND не закрыт частично; OR alternatives не считаются двумя смыслами |
| V15 / P06 | Government fiscal numerator/economy-wide GDP; затем другой GDP base/period | Корректные разные роли разрешены; несовместимый denominator отвергнут |
| V16 / P06 | Два совместимых relation edges; disjoint scope или reverse lossy map | Нет композиции без общей области и нет восстановления потерянных данных |
| V17 / P06 | Acyclic DAG с общим input; cycle либо executable string в metadata | Общий input не покупается дважды; cycle bounded; код не исполняется |
| V18 / P07 | Exact qualified ID; такой же local ID у другого owner и перестановка insertion order | Exact binding не меняется, first-wins не определяет смысл |
| V19 / P07 | Верный held-out с непохожим label; неверный с похожим label/unit | Первый проходит без core patch, второй отказывается |
| V20 / P07 | Два meanings недоопределённого requirement; второй за top-k | Search cutoff не доказывает уникальность |
| V21 / P07 | Два sources одной exact quantity; глобально похожий несовместимый construct | Sources остаются alternatives; чужой construct не блокирует уже определённый локальный use |
| V22 / P07 | Полный актуальный index; stale index либо catalog count от wrong scope | Incomplete/freshness limitation, не доказанное отсутствие/совместимость |
| V23 / P04/P08 | Новый semantic/no-SQL и semantic/SQL; old 1.0/1.1 artifacts | Все законные сочетания читаются правильно, old refs не переписаны |
| V24 / P08 | Admitted result; candidate-only с тем же числом, fresh API/export | Ни одна поверхность не повышает authority по числу или наличию certificate |
| V25 / P05/P08 | Closed historical record; новое current use после staling | История неизменна, current gate свежий; доступ к данным остаётся в пределах текущих прав |
| V26 / P06/P08 | Persisted partial acquisition; crash/retry до transform/admission или projection | Partial не становится ready; повтор соблюдает существующий idempotency/accounting contract |
| V27 / P02/P06 | Weighted mean с weights; среднее средних без weights, total вместо per-person, fiscal year вместо calendar year | Нужна другая derivation/estimand, не alias |
| V28 / P02/P05 | Независимые источники; два перепубликованных наблюдения общей survey | Occurrences различны, evidence dependence не превращается в независимое подтверждение |
| V29 / P02/P04 | Read-only measurement certificate; reuse для do/calibration/causal claim | Новый purpose требует собственного допуска |
| V30 / P02 | Некруговое evidence; тот же mapper сам выпускает «canonical» ID и подписывает соответствие | Самоутверждение не закрывает correspondence |
| V31 / P04 | Наблюдённый ноль; missing/null, два значения для scalar, scalar для vector без transform | Legitimate zero проходит; отсутствующее/неоднозначное значение не превращается в ноль/первый элемент, broadcast только явно |
| V32 / P05/P07 | Scoped uniqueness; новый admissible countercandidate без изменения selected refs | Затронутый binding переоценивается, unrelated bindings сохраняются |
| V33 / P04 | Один writer на target; второй binding с другим ID в тот же slot/state_path, затем переименование IDs | Нет silent overwrite по порядку ID. Только явная исполняемая merge/composition может объединять inputs |

V01–V33 покрывают исходные T01–T32 по их свойствам и добавляют новые seams: preflight, пустые binding rules, silent coercions/overwrites, schema/SQL matrix, поздние horizon inputs, новое противоречие после admission и crash/retry. Исходные тесты не удалять ради новой нумерации.

### 5.3. Точечные mutation controls

В изолированном verification slice, не в чужом рабочем дереве, временно отключить по одному load-bearing свойству. После каждого mutant восстановить исходное состояние обычным контролируемым способом, не затрагивая чужие изменения.

| Mutation | Какой тест обязан стать красным |
|---|---|
| Проверка denominator/quantity всегда true | V01–V03 |
| Intake доверяет внешнему `approved` и не открывает relation | V10/V30 |
| Empty explicit rules снова включают auto inference | V09 |
| Missing/null и shape coercions вновь выполняются до проверки manifest policy | V31 |
| Разные binding IDs получают право молча перезаписать один destination | V33 |
| Profile/model/transform dependency исключена из проверки selected basis | V08/V10/V13 |
| Реально потребляемый C input исключён из effective basis | V11 |
| Current revocation check пропущена | V12/V25 |
| Resolver выбирает первый alias | V18–V20 |
| Invalidation видит только selected refs и пропускает новый countercandidate | V32 |
| Candidate projection удаляет limitation | V24 |

Mutation, сломавшая импорт или ранний unrelated prerequisite, не считается доказательством чувствительности целевого теста. Требуется не общий процент mutation coverage, а эти конкретные различающие исходы.

### 5.4. Проверки существующего кода и команды

Команды выполняются из `policy-engine/` в рабочем окружении проекта. Ни одна команда в этом документе ещё не запускалась как проверка реализации.

Уже существующие compiler selectors, которые необходимо сохранить:

```bash
uv run pytest -q \
  tests/unit/data_requirement/test_compiler.py::test_declared_world_slot_joins_exact_canonical_construct_need \
  tests/unit/data_requirement/test_compiler.py::test_cpi_index_world_slot_rejects_the_growth_series_descriptor \
  tests/unit/data_requirement/test_compiler.py::test_world_slot_join_requires_actual_declared_source_binding \
  tests/unit/data_requirement/test_compiler.py::test_world_slot_join_preserves_multiple_matching_claim_specs_as_ambiguous \
  tests/unit/data_requirement/test_compiler.py::test_world_slot_join_preserves_source_alternatives_inside_one_spec
```

Существующие смежные suites выбирать по пакетам, не автоматически все после каждого изменения:

```bash
uv run pytest -q \
  tests/unit/runtime/quality/test_candidate_n5_l1_routing.py \
  tests/unit/runtime/quality/test_candidate_acquisition_prefetch_world.py \
  tests/unit/runtime/quality/test_candidate_acquisition_world.py \
  tests/unit/runtime/quality/test_n7_mixed_candidate_obligations.py \
  tests/unit/runtime/quality/test_candidate_source_basis.py \
  tests/unit/runtime/quality/test_candidate_source_basis_chained.py \
  tests/unit/runtime/quality/test_candidate_model_revision_basis.py \
  tests/unit/runtime/quality/test_capability_resolver.py \
  tests/unit/runtime/quality/test_capability_index.py
```

Для новых P02/P03 helpers создать mirrored files и дать тестам осмысленные names из шагов пакета; затем указывать их реальные node IDs в записи проверок. Integration case размещается в существующем подходящем suite после осмотра checkout. Не выдавать предложенное имя файла за уже существующую команду.

Также выполнять Ruff на изменённых файлах через `.venv/bin/python -m ruff`, необходимые generated/schema/import checks и:

```bash
uv run polisyos-tools architecture guardrails check
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

Вторая команда обязательна при затронутом runtime API contract. Broad backend/CI-parity и native/installed checks определять blast radius и требуемыми gates. Изменение contract, loaders и нескольких actual consumers в конце потребует соответствующей широкой проверки, но не повторять дорогую волну после каждой правки документации. Использовать обычные hooks. Отказ formatter/backend не переименовывать в продуктовый PASS.

## 6. Проверка масштаба и операционной пригодности

### 6.1. Данные и нагрузка

Ступени: **1k → 10k → 100k → не менее 300k различных definition/revision records**, с namespace collisions, aliases, source alternatives, relation edges и near-neighbor clusters. Отдельно сообщать число уникальных semantic definitions и revisions, чтобы 300k aliases одной величины не выглядели как 300k показателей.

Одинаковый закреплённый truth subset сохраняется на всех ступенях; растут distractors. Нужны strata: exact ID, правильное evidence при непохожем label, source alternatives, semantic near-miss, ambiguity, required unknown, held-out extension, local revision/revocation. Прогнать cold/warm запросы и контролируемую одновременную нагрузку с index updates. Seed, hardware, worker count и resource budgets закрепить до запуска.

Для метрик semantic quality считать denominator явно:

- false executable binds / число проверенных недопустимых подстановок
- false abstentions / число known-compatible cases внутри заявленного supported envelope
- retrieval recall / число known-compatible candidates в объявленном complete test corpus
- authority promotions / число candidate-only или revoked current-use cases

Считать их по каждому stratum/domain, а не только среднее. `Inconclusive` и skipped не удалять из required denominator.

### 6.2. Жёсткие условия finite-suite acceptance

- **0** ложных исполняемых подстановок в обязательном наборе
- **100%** обязательных положительных controls доходят до intended consumer
- **0** неразрешённых authority promotions
- **Не менее двух** held-out доменов проходят metadata-only extension после freeze общего runtime, без нового per-variable условия
- **100% реально исполненных шагов** declared horizon reconciled, если horizon входит в релиз
- При локальном alias update **0 unrelated numerical reruns** в контролируемом dependency fixture
- Для declared exact-key query examined semantic candidates ограничены его реальным index bucket/declared reference envelope, а не размером всего корпуса. Полный corpus scan не является обычным lookup

Это критерии конечного набора, а не обещание нулевой ошибки в мире или автоматическое достижение δ-ground guarantee. Для статистических risk claims нужны собственные assumptions, sampling/denominator и текущий risk-ledger owner.

### 6.3. Что измерить, а не придумать

Сохранить raw measurements и p50/p95/p99 по retrieval, verification, source/transform и intake. Дополнительно: examined rows, expensive checks, CAS/proof reads, DB queries, memory, index build/update time, update visibility lag, actual N5 invocations и invalidation fanout против реальной dependency closure.

До оптимизации зафиксировать latency/RAM/update budgets из текущего deployment/CI envelope. Если их ещё нет, агент сначала выполняет baseline measurement и предлагает обоснованный budget в текущей записи задачи. **Без заранее установленного budget нельзя объявлять performance gate пройденным.** Это не повод тормозить функциональную реализацию и не разрешение подогнать SLO под итог.

При росте unrelated corpus в десять раз сравнивать не только время, но и число прочитанных candidates/proofs. Рост этих величин пропорционально всему корпусу на localized exact queries указывает на непригодный execution path. Разовая перестройка index допустима; скрытый rebuild на каждом request недопустим. Чисто технический отсутствующий SQL index ещё не опровергает semantic architecture.

Измерить отдельно цену расширения: сколько metadata fields, ручных действий и qualified reviews нужно для нового variable/source внутри уже принятого класса. Human review нового scientific relation допустим. Ручное переодобрение каждой строки или alias при неизменном принятом профиле означает, что масштабирование не доказано.

### Gate B. Граница готовности расширенного механизма

Gate B закрывается после P06–P08, обязательных V-тестов, mutation controls, независимого held-out rerun и benchmark с заранее принятыми budgets. Отдельно вынести verdicts: соответствие спецификации, жизнеспособность архитектуры в проверенной границе, готовность к текущему production rollout. Один общий зелёный статус их не заменяет.

## 7. Когда нужно менять архитектуру, а не дописывать исправление

Ключевой вопрос: **может ли общий контракт выразить нужное различие и обеспечить его проверку в настоящем consumer?** Если может, но конкретный validator/bridge ошибся, это дефект реализации. Если для каждого контрпримера требуется особое исключение, проблема находится в механизме.

| Наблюдение | Локальная ошибка, если | Архитектурный stop, если |
|---|---|---|
| Denominator/stock-flow перепутаны | Axis и evidence уже есть, конкретная проверка пропущена | Система знает только name/unit и не может выразить различие без доменного `if` |
| Новый совместимый показатель не доходит до модели | Потеряна одна index/bridge запись | Каждый новый показатель требует core allowlist либо правки общего алгоритма |
| Отсутствующий input не может инициировать acquisition | Preflight producer существует, но не подключён | Получить missing-input requirement можно только после N5, который без него невозможен |
| Hidden input меняет результат при прежнем basis | Supported adapter умеет видеть его, но helper пропустил | Runtime свободно читает ambient state, а архитектура обещает полную closure |
| Подписанный mapping принят без correspondence | Independent evidence требуется, но consumer его не открывает | Самоподпись автора или shape/hash объявлены достаточным доказательством смысла |
| Система безопасно отказывает почти всему | Конкретный index/profile слишком строг | Для обычного локального use требуется полный глобальный ontology agreement или все возможные metadata axes |
| Один alias stales весь corpus | Ошибочен dependency query | Единственный общий epoch является единственным предусмотренным способом currentness |
| Current revocation не действует | Проверка предусмотрена, но забыта в consumer | Immutable receipt по design даёт вечное разрешение вне времени и purpose |
| Два источника одной величины вызывают ambiguity | Ошибка группировки sources | Единственность смысла смешана с единственностью supplier |
| Корректные разные operands запрещены | Один operator-validator сравнивает лишнюю ось | Единственный механизм композиции требует одинаковости всех полей, без ролей и preconditions |
| Неверная композиция или inverse проходит | Известное precondition не проверено | Relations представлены как безусловная симметричная/transitive equivalence |
| Exact lookup растёт как весь corpus | Не построен пригодный технический index | Каждый binding по замыслу требует all-pairs сравнения или полного corpus scan |
| Старый результат меняет смысл при replay | Ошибка version router | История хранит только mutable latest IDs и не может адресовать прежние meanings |
| Semantic manifest не влияет на выполнение | Забыт один enforcement hook | Политика допуска отделена от реального Foundry execution так, что обход не наблюдается |
| Новый countercandidate не меняет прежнюю uniqueness | Забыто обновление query-scope dependency | Design учитывает только выбранные refs и не может выразить зависимость от отсутствия конкурентов |

### 7.1. Протокол остановки

При false executable bind, незаметной authority promotion или нарушении selected dependencies остановить расширение **затронутого профиля** и удержать соответствующую authority gate закрытой. Не останавливать несвязанную допустимую candidate работу и независимые маршруты LANE-01.

1. Сохранить minimal counterexample, baseline/new inputs, actual trace и точную границу нарушения
2. Классифицировать: bug, unsupported envelope, неверное основание/evidence либо architectural deficiency
3. Если контракт способен выразить нужное различие, исправить существующий owner и повторить pair, mutation и affected siblings
4. Если не способен, предложить изменение соответствующего design decision/contract. Не скрывать его новым alias, default или exception в fixture
5. На втором escape того же класса расширить механизм либо явно зафиксировать отсутствующую capability и residual falsifier, как требует P40
6. После изменения design повторить прежние positive и negative controls. Нельзя считать решение улучшенным, если новый запрет просто уничтожил все positive

Невоспроизведённое предположение называется риском, а не доказанной ошибкой архитектуры. Спорную scientific correspondence нельзя исправить техническим голосованием нескольких LLM; она остаётся отдельным evidence gap.

### 7.2. Три раунда red-team реализации

- **Раунд 1, смысл и producer:** names/units/denominator, подмена role→requirement, circular IDs/evidence, false abstention. После исправлений повторить Gate A positives
- **Раунд 2, исполнение и жизненный цикл:** empty rules, late horizon dependency, proof removal, compile/intake race, wrong selected source, reuse/currentness и consumer promotion
- **Раунд 3, рост и эксплуатация:** blind held-out domains, index lag/cutoff/collisions, AND/OR, concurrent revisions, local invalidation, crash/retry и 100k–300k corpus

В каждом раунде должны быть запускаемые атаки, результат, правка при найденном дефекте и повтор старых controls. Три аналитических обсуждения не считаются тремя проверками реализации. Один fresh independent review coherent change сохраняется по правилам проекта; не нужен новый reviewer после каждого микрошага.

## 8. Пакет свидетельств и завершение

Использовать существующий компактный change/verification record. Не вводить новую receipt-схему только для отчётности. Большие raw outputs сохранить по действующим правилам проекта с реальным доступом к bytes, а не одним hash.

Минимально необходимо:

1. Baseline, implementation commit/diff и фактический environment. Для live work: actual selected profile/input refs
2. Команды, exit codes, длительности, seeds, required tests с PASS/FAIL/PARTIAL/INCONCLUSIVE и объяснённым unsupported
3. Для каждого vertical case: producer requirement → definition/representation → relation evidence → plan/manifest → input bindings → **все соответствующие step input bases** → execution/result → fresh readback
4. Для A/B/C: таблица exact numerical refs, invocation/event records, source/evidence occurrences и current decision refs
5. Mutation outputs, показывающие, что тесты действительно замечают удаление нужной защиты
6. Hold-out runtime diff, metadata diff, все ручные действия и граница нового operator против metadata-only extension
7. Benchmark generator/data/query seeds, raw measurements, hardware, заранее принятые budgets и результат по каждому stratum
8. Найденные атаки, что именно изменилось в механизме и какие прежние тесты повторены
9. Неустранённые scientific/authority gaps, unsupported adapters и текущие ограничения поиска/наблюдения dependencies
10. Отдельное решение о локальном пакете, о возможности rollout и о том, что **остаётся открытым в E02/CYC-03**

Не писать «универсальная семантика решена». Допустимый итог уже и проверяем: заявленные классы variables и model interfaces расширяются через общий механизм, близкие несовместимые подстановки в проверенных границах не проходят, фактическое вычисление соответствует выбранному binding, а provenance, ограничения и current authority не теряются.

## 9. Короткое задание для запуска реализации

> Реализуй техническую спецификацию связывания переменных PolicyOS по пакетам P00–P08. Начни с текущего `E02-WORK-PLAN.md`, branch/HEAD и владельцев путей. Не исправляй исходный fiscal failure alias между tax rate, balance/GDP и stock. Сначала докажи Gate A: реальный missing-input producer до нужного N5, существующий compiler/source path, immutable resolved manifest, explicit Foundry rules, actual consumption и fresh readback. Проверь close negative и held-out compatible extension без core patch. Сохрани candidate/authority границу и старые schemas. Особое внимание: `rules=[]` не должно включать name inference, model dependencies не ограничиваются outcome/levers, Foundry 1.0/1.1 требует полной SQL/semantic migration matrix, horizon требует bases всех actual steps. После Gate A реализуй AND/OR, bounded derivations, localized invalidation и indexed retrieval. Выполняй V01–V33, точечные mutation controls и три исполняемых red-team раунда. При системном контрпримере останови затронутый profile и предложи изменение design, не новый hardcode. В конце представь exact artifacts/tests/benchmarks, ограничения и отдельные verdicts. Не объявляй E02 или fiscal correspondence закрытыми по чужому matched fixture. Не меняй чужие paths, index/commits или current plan вне назначенного ownership.

## 10. Проверенные ссылки и архитектурные основания

Все repository links ниже закреплены на `df809a7a835cf7ee6c97effc30e89ede285a1de0`. Перед реализацией пересмотреть релевантный diff, а не трактовать эти line anchors как вечный контракт.

- [S01. Исходная постановка, §Observed failure и LANE-01 boundary][S01]
- [S02. Правила репозитория: Working Model, Checks и Toolchain][S02]
- [S03. CGF: §1–4 и conditional guarantees §5][S03]
- [S04. ModelSpec и candidate-only declaration][S04]; [candidate declaration][S04b]
- [S05. Actual L1 producer][S05]; [compiler descriptor join][S05b]
- [S06. Candidate source: bounded World Bank profile][S06]; [model slot scope guard][S06b]
- [S07. Catalog measured binding][S07]; [existing unit conversion][S07b]
- [S08. N7 mixed-obligation cardinality][S08]
- [S09. FoundryInputBindings schema/SQL relation][S09]; [FoundryExecutionInputBasis, identity-only][S09b]
- [S10. Binding producer/loader][S10]; [implicit rule fallback][S10b]; [проверка rules и последовательная запись state][S10c]; [null и shape coercions][S10d]
- [S11. Actual execution input-basis construction][S11]; [execution source admission][S11b]; [source inventory и его прямые inputs][S11c]
- [S12. Existing effective basis][S12]
- [S13. Current resolver scan][S13]; [existing CapabilityIndex owner][S13b]
- [S14. S0-K06 candidate и authority bands][S14]
- [S15. CORR: constructibility не равна внешней correspondence][S15]
- [S16. Organizing Rules: capability reality и extension conformance][S16]

Внешние стандарты из исходного исследования обосновывают разделение concepts/representations, directed mappings и provenance. Они не являются зависимостью, которую нужно целиком импортировать в PolicyOS: [DDI-CDI ConceptualVariable](https://docs.ddialliance.org/DDI-CDI/1.0/model/FieldLevelDocumentation/DDICDILibrary/Classes/Conceptual/ConceptualVariable.html), [FHIR R5 ConceptMap §4.10](https://www.hl7.org/fhir/R5/conceptmap.html), [UCUM §12, annotations](https://ucum.org/ucum). Fiscal distinction: [World Bank metadata GC.BAL.CASH.GD.ZS](https://databank.worldbank.org/metadataglossary/africa-development-indicators/series/GC.BAL.CASH.GD.ZS), [ONS GFSM §4.2](https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance/methodologies/internationalmonetaryfundsgovernmentfinancestatisticsframeworkinthepublicsectorfinances).

[S01]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/docs/research/policyos-variable-identity-research-brief.md
[S02]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/AGENTS.md
[S03]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/docs/system-design-decisions/policy-design-causal-grounding-firewall.md#L28-L142
[S04]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/ir/model_layer/model_spec.py#L181-L275
[S04b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/candidate_simulation.py#L253-L330
[S05]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L17559-L17629
[S05b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/data_requirement/compiler.py#L782-L941
[S06]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/candidate_acquisition_source.py#L294-L426
[S06b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/data_state_substrate.py#L3151-L3200
[S07]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py#L257-L322
[S07b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/overlay.py#L437-L615
[S08]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/acquisition_planner.py#L5264-L5321
[S09]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/core/contracts/foundry.py#L1517-L1566
[S09b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/core/contracts/foundry.py#L2460-L2530
[S10]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/foundry/data_plane/bindings.py#L1943-L2245
[S10b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/foundry/data_plane/bindings.py#L2698-L2820
[S10c]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/foundry/data_plane/bindings.py#L2829-L2966
[S10d]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/foundry/data_plane/bindings.py#L3107-L3147
[S11]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/foundry/execute/api.py#L1174-L1266
[S11b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/foundry/execute/api.py#L579-L640
[S11c]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/foundry/execute/api.py#L392-L472
[S12]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/candidate_source_basis.py#L695-L975
[S13]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/capability_resolver.py#L470-L662
[S13b]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/src/polisyos/runtime/quality/capability_index.py#L472
[S14]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md#L155-L176
[S15]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/docs/research/policy-operations/corr-consolidation/corr-consolidation-report.md#L186-L251
[S16]: https://github.com/DenisKopylov/polisyos/blob/df809a7a835cf7ee6c97effc30e89ede285a1de0/policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md#6-the-capability-reality-bar

