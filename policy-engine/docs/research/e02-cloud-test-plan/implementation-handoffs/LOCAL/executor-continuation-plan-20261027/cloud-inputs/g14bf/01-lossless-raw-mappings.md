# CAN-01: сохранять raw mappings через versioned grammar

## 1. Решение и его граница

Выбран вариант A. Extend `common/canonical.py`, существующие Core/IR facades, `CanonSpec` и `CanonInfo`; новая grammar version — `polisyos.canon.json@0.3.0`. Имя owner profile, его flags и reader policy продолжают участвовать в admission. `0.2.0` сохраняет свои bytes, decoding и ограничения. Public facades сохраняют собственные exception identities.

Контракт: encode/decode сохраняет различие **ordinary mapping vs native typed value vs explicitly typed internal descriptor**. Это сохранение значения в объявленной области профиля, а не исходных JSON bytes, insertion order, spelling чисел, Python subclass identity или произвольного object graph. При необходимости исходных bytes их сохраняет существующий raw-byte artifact owner.

В source `7a4c713` raw `{"_type":"decimal","value":"1"}` и `Decimal("1")` попадают в одинаковое typed представление. `_canonicalize_mapping` проверяет имя tag, а decoder интерпретирует его как native value. Foundry раньше стирает различие в `_convert_value_for_canonical`. Поэтому решение обязано закрыть оба choke points.

## 2. Grammar `.3`

Для **каждого обычного mapping, содержащего точный ключ `_type`**, writer создаёт structural node:

```json
{"_type":"mapping","entries":[["_type","decimal"],["value","1"]]}
```

Правила обязательны:

1. Escape определяется наличием ключа, не значением и не списком известных tags. `_type=null`, `_type=[]`, неизвестное имя, malformed native-looking map и map с extra fields остаются данными. `__type__` — обычный ключ, без новых правил.
2. Entries содержат все исходные string keys и recursively encoded values. Никакие значения обычного map, включая `None`, не выбрасываются. Для canonical режима ключи отсортированы тем же string ordering, что существующий canonical owner; без Unicode normalization. `sort_keys` как сериализационный flag не разрешает permutation списка `entries`: у structural node порядок фиксирован независимо.
3. Decoder проверяет точную форму wrapper: только `_type` и `entries`, пары длины два, string keys, отсутствие дубликатов, canonical order. Результирующий map обязан содержать `_type`; wrapper для map без него — неканоническая альтернативная запись и отказывает.
4. Реконструированный root **не проходит повторный tag dispatch**. Values декодируются рекурсивно. Raw map, сам похожий на `mapping/entries`, также экранируется ровно на своём уровне; его обычное содержимое не становится управляющим grammar node.
5. Внутренний writer создаёт grammar nodes отдельным typed emission path, не вызывает обычный map encoder на собственном wrapper. Это исключает бесконечный self-escape.
6. Native typed envelopes вне escape читаются только по выбранным owner/version rules. Unknown/unallowed/malformed unescaped envelopes отказывают; это не запрещает идентичные по shape **данные** внутри escaped map.
7. Dataclass/Pydantic projections проходят общую mapping policy после своих существующих rules (`by_alias`, объявленный `exclude_none`). Нельзя оставить отдельный dataclass обход. Private carriers распознаются **до** generic dataclass/Pydantic/mapping projection; произвольный пользовательский dict/dataclass не создаёт carrier своим shape.
8. `.3` byte parser отказывает на duplicate JSON member names до потери информации стандартным `json.loads`. Resource/depth limits проверяются и в byte parser, и при value traversal; typed refusal не превращается в частично прочитанное значение.

Core и IR используют одинаковую structural escape law, но **разные native type policies**. IR не получает Core-only `array_digest`, `bytes_hex`, `float_hex`. Raw map с любым из этих имён в IR `.3` сохраняется как data. Будущие native tags добавляются через owner/version law; existing escaped data от этого не меняет смысл.

## 3. Foundry и типизированные представления

Не переводить Foundry float механически в generic native float encoding: `_canonical_float_repr` объединяет signed zero, тогда как текущий Foundry `float.hex()` различает `+0.0` и `-0.0`. Это изменение cache semantics вне задачи.

Выбрана следующая bounded схема:

| Значение на Foundry входе | Новый pre-encoder output | Обязательство decoder/re-encoder |
|---|---|---|
| `Decimal`, date/datetime и другие уже native поддерживаемые значения | Сохранить native value до codec; не строить tag-shaped dict. | Сохранить существующую owner normalization law; не обещать Python object identity. |
| bytes-like | Core-owned immutable `bytes_hex` representation carrier с нормализованным hex. | Возвращать carrier на `.3` read, re-emit тот же tag; явное извлечение bytes отдельно. |
| Python/NumPy floating scalar по существующей Foundry projection law | Core-owned immutable `float_hex` representation carrier. | Canonical finite hex, signed zero сохранён; не превращать при conformance read в generic float. |
| Array после существующего `_array_digest` | Core-owned opaque `array_digest` carrier: dtype/shape/digest по существующей Foundry law. | Сохранить carrier identity и exact wire representation. Это descriptor, не восстановленный array и не доказательство его истинности. |
| Обычный raw mapping любого shape | Обычный recursively projected mapping. | Только structural escape; никогда carrier inference. |

Названия Python classes — выбор исполнителя внутри существующего Core owner. Нужны узкие typed constructors/accessors, не публичный `tag:str + arbitrary payload` bypass и не универсальный plugin registry. Common механика не импортирует Foundry/NumPy. Core владеет grammar/representation validation; Foundry — построением descriptor из реально поданного значения. Существующая NumPy scalar/array numerical projection не расширяется этим решением.

Такие carriers — **различимые representation values**, а не две canonical записи одного Python primitive. `.3` native `bytes`/`float` имеют свою обычную запись; hex carrier имеет свой тип и сохраняет его на read/re-encode. Если нужен primitive, потребитель делает явную owner operation после conformance verification. `.2` продолжает декодировать hex в primitives и array digest в opaque dict как раньше.

Flags не обходятся carrier-ом: `.3` `forbid_nan_inf` действует также на float carrier; запрет floating values не обходится его wrapper. Foundry явно выбирает подходящий spec для своих floating projections. Не переносить незаметно прежнюю лазейку с NaN/Inf; nonfinite numerical support, если действительно требуется, требует отдельной owner law, а не fallback. Для bytes/array descriptor действует shape/type validation; digest shape не выдаётся за content verification массива.

## 4. Version dispatch и public readers

В pinned source `CanonSpec.version` не выбирает ветку codec; profile declaration сопоставляется лишь с default version; direct decoders принимают только `max_depth`. Поэтому `.3` требует **реального version dispatch**, не одной смены metadata.

- Extend существующие decode APIs keyword-only selected spec/version context. Старый unqualified вызов остаётся `.2`. Encoder с explicit `.3` и decoder с explicit `.3` образуют пару. Нельзя автоматически угадывать `.3` по wrapper.
- `common/canonical_profile.py`, Core profile adapter, IR IO должны выбрать одну поддерживаемую owner/version implementation **до** decode/re-encode. Не заменить проверку default-version на “accept any version”. Существующий неизвестный профиль остаётся raw/unqualified candidate или refusal по purpose, без executable/authority interpretation.
- Declared profile проверяется полностью, payload — по exact decode/re-encode; selected manifest profile hash проверяется существующим ArtifactStore. Профиль codec не равен producer attestation.
- Contextual reader identity также version-bound: current `core-tag-policy@1` не должен незаметно означать новые carrier returns. Сохранить старый ID для старой law; новая `.3` Core interpretation получает следующую reader-policy version, IR — собственную version-qualified interpretation. Это расширение существующих owner policies, не их объединение.
- Direct readers persisted state/checkpoint/outcomes переходят на selected manifest read либо получают exact profile из своего typed contract. В частности, нельзя оставить `scientist/orchestration/engine/context.py` на голом default decoder после включения `.3` state writers.
- `.3` raw-map migration не меняет DTO schema version, если DTO shape и value contract действительно прежние. Изменившиеся typed descriptor returns и публичные read APIs документируются как `.3`-qualified contracts. Schema changes у иных owners версионируются отдельно.

Логическая глубина: wrapper/entry pair — wire representation, не новые пользовательские levels. `.3` writer и reader используют одинаковую logical value-depth law `CanonSpec.max_depth`. `.2` accounting неизменно. **Wire limits имеют другого owner и не переопределяются этим правилом:** существующий Core `CoreJsonReadLimits(max_bytes, max_depth, max_elements, max_manifest_bytes)` получает explicit положительные пределы из selected resource policy; его `max_depth/max_elements` продолжают считать реальную JSON wire структуру, включая escape overhead. Нельзя переименовать старый lexical depth в logical или использовать `MAX_LIBRARY_BYTES`/HTTP inspector cap как общий payload budget.

До включения writer каждый cohort связывает свою selected resource-policy/version с конкретным budget vector для write/read/cache admission. Core переиспользует bounded scanner/reader и его refusal measurements. IR/Foundry передают ограничения от своих admission/resource owners в dependency-neutral механический слой; common не импортирует Core. Если resource policy не задаёт нужного bound, добавить его в **существующий owner policy/config**, без нового budget service и без выбранного здесь универсального числа MiB. Неполная budget binding блокирует только включение этого writer cohort.

Writer учитывает фактический encoded wire overhead до публикации/cache effects; byte/node refusal не должен случаться лишь после безлимитного materialization. Boundary checks используют actual выбранные числа: на лимите/сверх лимита, escaped и non-escaped значения. Вполне допустимо, что logical-in-limit map превышает отдельный wire budget: выдать typed capacity refusal с limit/observed/profile, не потерять поля и не откатиться на `.2`. Увеличение admission budgets — отдельный ресурсный выбор, не незаметная смена grammar. Не обещать zero-copy; не создавать лишние полные копии сверх существующего materialized API. Дальнейший streaming serializer — отдельная измеряемая оптимизация, не precondition этого исправления.

## 5. Cache и history

`compute_static_params_hash` обязан перестать ловить semantic/profile/resource refusals через `except Exception → json.dumps`. При доступном canonical owner нет оснований для JSON fallback; отсутствие нужного owner — явная dependency failure. Проверить sibling fingerprint/hash paths в фактическом importer footprint.

Новая Foundry key domain включает version существующей static-parameter identity law и полный выбранный canonical spec. Domain separation **обязательна**, даже если native Decimal bytes не изменились: в старой generation мог лежать результат от colliding raw map. Использовать существующие generation/in-flight fences, чтобы старое вычисление не публиковалось в новую generation. Не строить второй cache manager. Старые ключи не читаются новым lookup; retained old entries допускаются только старой law.

NodeResultCache имеет отдельную `IDEMPOTENCY_CONTRACT_VERSION`, CanonSpec и journal proof. Их новый writer должен version-bind новую law; чтение/проверка старого journal сохраняет старую law. Payload profile сменился — это не означает, что независимый idempotency key уже versioned. Retry не должен повторно выдавать side effects под видом harmless cache miss: owner сохраняет durable attempt/result binding и его версию, reuse только после проверки совместимого ключа и потреблённых inputs.

Старые CAS bytes и IDs не переписывать. Из `.2` bytes невозможно восстановить, был ли origin raw map или native value. Readable history не превращается в доказанный raw roundtrip. Source-qualified восстановление — новый artifact/view, lineage к исходному свидетельству и фактическое время миграции. Нет verified origin — bounded limitation, без догадки. New raw-map writes должны использовать `.3`; до готовности выбранного reader cohort такой путь может честно отказывать до cache/persistence. Это временная rollout safety, не постоянный вариант B.

## 6. Минимальный footprint и completion

Codec/common profile; Core/IR facades + adapters; Core manifest/store wiring; Foundry converter/hash/specialization/cache generation; ExperimentState state writers/readers; sync/async executors; checkpoints/resume; NodeResultCache idempotency/journal; installed consumers; public profile/read docs. Exact paths и tests выводятся из source freeze/importers, а не из ограниченного списка примеров. Нельзя считать 22 pins полным repository census.

Capability сейчас имеет `consumer_missing`/`verification_missing` для новой grammar и `semantic_test_missing` для composed paths. Completion — [CAN acceptance matrix](04-delivery-and-acceptance.md), включая настоящий cache hit/miss, persistence/fresh read, rollback-reader compatibility и removal с сохранёнными маркерами. Identity, authority и formal closure не следуют из codec PASS.
