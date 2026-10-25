# AD-E02-FABRIC-REFLECTION-01: совместимость разрешённых аннотаций

Версия решения 2, 25 октября 2026. Owner реализации — Fabric (`team-polisyos` в public-surface manifest); DevX владеет генерацией lint-config, `team-architecture` — public-surface policy. G выбирает контракт, затем отдельно принимает код. `code_acceptance=false`, `closure_ids=[]`.

## 1. Архитектурный выбор

Сохранить доступность настоящих runtime-типов для перечисленной ниже поверхности. Для E02 рекомендуемый механизм — **существующие module-level imports и точечные, объяснённые `TC001`/`TC003` исключения**. Убрать эти два кода из общего production Fabric ignore в том же delivery. Никаких новых dependency-resolver, decorator, proxy types или runtime-патчей `__annotations__` ради линтера.

Почему: удаление runtime binding уменьшает возможности типизированных adapters, tooling и расширений, а текущий пакет не показывает выигрыша по памяти/времени импорта. Python допускает static-only annotations, но не превращает их в эквивалент работающего `get_type_hints`. Это осознанный локальный compatibility contract PolicyOS, а не якобы универсальное правило Python или доказательство существования конкретного downstream consumer. [Python typing](https://docs.python.org/3.14/library/typing.html#typing.get_type_hints), [TC001](https://docs.astral.sh/ruff/rules/typing-only-first-party-import/).

## 2. Проверяемое свойство

После обычного импорта поддерживаемого entrypoint `typing.get_type_hints(target)` и `typing.get_type_hints(target, include_extras=True)` разрешают **полные объявленные аннотации выбранного объекта** в его штатных namespaces. Caller не обязан заранее импортировать deep implementation modules, передавать ремонтирующие `globalns`/`localns`, вызывать бизнес-функцию или прогревать registry.

Сохраняются реальные nominal types, canonical type aliases и generic arguments, union/nullability и метаданные, если они объявлены. Уже существующий `Any` не запрещается; замена требуемого типа на `Any`, `object`, пустую mapping, unresolved `ForwardRef` или строковый fallback не удовлетворяет контракту. Ключи результата сверяются с объявленными параметрами/return либо class annotations; проверка одного непустого dict недостаточна. Валидные `TypeAliasType`/parameterized alias не обязаны быть экземплярами `type` или принудительно раскрываться до underlying union. Не требуется рекурсивно разрешать поля каждого класса, встреченного внутри типа: это другое, неограниченное обязательство.

Совместимость сверяется с **reviewed baseline + явно одобренной delta**, а не только с текущим объектом. Сохранить имена и kinds параметров, смысл defaults, return, async/member kind и существующие call forms; удаление параметра вместе с аннотацией не должно уменьшить одновременно implementation и его oracle. Не фиксировать адреса default-объектов, строковый `repr` или случайный порядок union branches. Новое поле/параметр допускается по обычным правилам совместимости, а не запрещается замороженным сегодняшним множеством.

Canonical alias — не освобождение от его смыслового контракта. Сравнение с alias, импортированным из того же изменённого owner, не ловит изменение его RHS. Для unchanged alias достаточно source-qualified preservation плюс проверка разрешения; при изменении owner/dependency проверяется конкретная accepted relation отдельным owner test и affected consumers. Для `SourceConnectorValue` это сохранение обеих предусмотренных connector forms и generic argument, а не обязательный универсальный рекурсивный evaluator. Валидные `Literal` со строковыми значениями, type parameters и metadata `Annotated` не являются неразрешёнными forward references. Не запрещать новые законные формы Python typing широким правилом «внутри hints не бывает строк».

Для классов тестируется class object, для методов — реально полученный member, для classmethod — class-bound member. `get_type_hints(Class)` не подменяет проверку `Class.method` или `Class.__init__`. Private protocol, встреченный в публичной сигнатуре, сохраняет собственную identity, но от этого не становится новым поддерживаемым import path. Identity проверяется с canonical owner **внутри данного candidate/process**; это не запрет обоснованной будущей миграции типа и не сравнение указателей между версиями/процессами.

Базовая среда — объявленный проектом Python `>=3.14,<3.15` и существующий dependency/backend profile, в котором соответствующий facade поддерживается. Записывать точные версии и профиль actual candidate. Решение не требует импорта полного Fabric со всеми optional backends в любой минимальной среде; уже существующее optional-dependency поведение нельзя ухудшать или выдавать за новую общую гарантию. Reflection не подтверждает доступность backend, пригодность данных или полномочия метода.

## 3. Scope: bindings, объекты и import routes

Сокращённые IDs в таблице — последние три цифры `FABRIC-TC001-*`, кроме 012–014 (`FABRIC-TC003-*`). Canonical ledger остаётся [в исходном inputs.json](https://github.com/DenisKopylov/polisyos/blob/8533003b91961cf9ba1305ec296dab7f3ed40e4b/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/g-questions/native-exceptions-20261025/inputs.json). Ни source line, ни сегодняшний размер множества не являются вечным API-ключом.

| IDs / runtime bindings | Получение объекта / полный затронутый scope | Решение |
| --- | --- | --- |
| 001 `ConnectionHandle`, 002 `SourceConnectorValue` | `polisyos.fabric.connectors.InvalidationTrigger.check_for_updates` | Сохранить разрешение `handle` и `connector`, включая generic arguments; проверять полную сигнатуру |
| 003 `ConnectorSchemaContract`, 004 `EvolutionReport` | `polisyos.fabric.connectors.SchemaChangeInvalidationTrigger.on_contract_registered` | Сохранить точные contract/report types и optional report |
| 005 `ConnectorCacheStore` | Через `polisyos.fabric.connectors`: **оба** `InvalidationOrchestrator.__init__` и `SchemaChangeInvalidationTrigger.__init__` | Второй конструктор — обязательный companion, пропущенный representative ledger |
| 006 `ConnectorMetadataSpec` | `SourceContract.from_connector_schema_contract`, `SourceContractSLA.from_metadata`; существующие comment/tests | Уже выбранное обязательство; не переоткрывать и не удалять при сужении ignore |
| 007 `ConnectionConfig` | `polisyos.fabric.data_plane.modes`: `run_batch_incremental`, `run_record_mode`, `run_replay_mode`, `run_streaming_windowed` | Сохранить runtime binding и текущие функции; отдельная bounded compatibility ниже |
| 008 `RuntimeLineageRef` | Private `_lineage_from_runtime` | Не новая public reflection guarantee; решение об import placement принимает исполнитель, сохраняя реальную конверсию |
| 009 `RuntimeQuantityValue` | Helpers в `fabric.evidence.decision_data`, включая annotations параметров и return | Не новая public reflection guarantee; проверить полный actual use до переноса, не удалять рабочие conversions/imports по lint-сообщению |
| 010 `RuntimeTemporalRef`, 011 `RuntimeTemporalScope` | `polisyos.fabric.TemporalRef.from_runtime_scope` | Сохранить настоящие Core types внутри union вместе с остальными branches; aliases не путать с Fabric `TemporalRef` |
| 012 `Iterable`, 013 `Mapping`, 014 `Sequence` | Через `polisyos.fabric`: `query_world_table`, **`query_claims`, `query_events` и class `WorldQueryRequest`** | Сохранить разрешение всех соответствующих параметров и полей class. `query_world_table` также экспортируется через `polisyos.fabric.data_plane`: bindings фасадов должны вести к одному implementation object |

Итог для исходных 14 import diagnostics: **10 новых facade-backed + 1 bounded mode binding + 1 ранее связанный public + 2 internal**. Для новых facade-backed bindings source-use closure включает **8 callable signatures + 1 class-field surface**. Четыре mode functions и два существующих metadata methods считаются отдельно; не суммировать это с числом diagnostics как число capabilities.

### Data Plane: не скрывать конфликт документации

`data_plane/README.md` на source называет четыре mode functions «Public Entrypoints», но manifest поддерживает `polisyos.fabric.data_plane`, а его `__all__`/lazy map эти функции не экспортируют. Отсюда нельзя вывести ни новое stable обещание для всех descendants, ни разрешение молча сломать документированный путь.

**Решение сейчас:** сохранить четыре существующих deep call paths и `ConnectionConfig` runtime binding; выполнить bounded reflection checks по самим mode-функциям и существующие consumer checks. В README различить supported facade routes и документированные implementation-mode routes, явно указав текущую compatibility boundary и отсутствие нового facade export. Не удалять описания функций, не создавать aliases/exports только ради теста. Новый публичный фасад или retirement этих маршрутов — отдельное изменение surface по действующей compatibility procedure, не prerequisite этой работы. Так исправляется фактическая классификация без потери поведения и без искусственного ожидания ещё одного G-вопроса.

## 4. Расширяемость и отвергнутые варианты

**B — перевести выбранные bindings в static-only — отклонён для этого delivery.** Это допустимая модель Python, но несовместимая с выбранным здесь обязательством. Последующее снятие public-stable reflection contract требует обычной migration/deprecation процедуры: текущий manifest задаёт две minor releases, release fragment `python-public-api` и inventory review. Не выводить из этого новую дату или автоматическое разрешение после истечения времени.

**C — custom resolver / fake namespaces / строковый metadata reader — не нужен.** `annotationlib` умеет выдавать строки и неразрешённые ссылки; это полезно для другого tooling contract, но не замена разрешённым типам. Такой consumer может существовать отдельно, честно обозначая неполноту; он не исправляет ложный positive в проверке A. [annotationlib](https://docs.python.org/3.14/library/annotationlib.html).

**D — blanket runtime imports / package-wide ignore — отклонён.** Не заставлять все Fabric/private annotations разрешаться и не освобождать все будущие imports от TC001/TC003. Static-only imports остаются нормальным инструментом там, где runtime reflection не является потребляемым контрактом.

Перечень — исходный scope ремонта, не allowlist будущих API. Добавление нового ресурса/метода в существующей модели не требует нового центрального registry. Для нового reflection-facing API owner добавляет обычную surface-документацию и семантический тест, связывает типы и использует тот же локальный механизм. Если в будущем import cycle или измеренная стоимость потребуют изменения, допускается reuse/extend существующего type owner с сохранением observable contract; не вводить фиктивный протокол или копию nominal type ради устранения цикла. Dependency refactor обязан включить импортеров, fresh-import и compatibility checks, а не ещё один обязательный архитектурный раунд по любому alias.

## 5. Status, authority и границы

Это engineering API contract, редакция решения 2; версия product API этим документом не меняется. Нет новой artifact schema, product enum, law, authority, custody или временного статуса. Annotation type — описание интерфейса, а не evidence достаточности политического вывода. Resolver не исполняет expressions из недоверенного документа, артефакта или LLM-ответа; здесь исследуются trusted repository objects. Python предупреждает о выполнении кода при introspection. [Typing security](https://docs.python.org/3.14/library/typing.html#typing.get_type_hints).

Нет настоящих внешних law/production inputs для выбора A. Требуются engineering inputs: actual source/tree, admitted dependency profile и полные deciding outputs. До supported-facade и semantic checks состояние проверки — `verification_missing` / `semantic_test_missing`; существующий source не объявляется отсутствующей capability. HTTP/browser surfaces для самого Python reflection property — `surface_out_of_scope`; Python facade и reference documentation входят в scope.
