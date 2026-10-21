# Где хранить и что переиспользовать

Часть [проекта получения и развёртывания](../12-acquisition-storage-and-deployment.md). Это решения проекта, не применённая миграция. Статические code pointers ниже относятся к C = `635413bcd1bd1d7e7b829d9123765e28e6bf23d6`; пути относительно `policy-engine/src/polisyos/`. Движущийся E02 source перед реализацией требует delta review.

## 1. Что означает «хранить рядом»

Предварительно подготовленный corpus и runtime captures должны быть **в одной системе идентичностей, lineage и разрешённого поиска**, но не обязательно в одном каталоге, bucket, регионе или security domain. Источник версии V, полученный background worker и позже востребованный run R, не копируется только из-за смены инициатора. Runtime capture V2 дополняет историю и может использоваться следующими задачами; он не переписывает V и результаты старого run.

Логические роли: original occurrence, normalized derivative, semantic assertion/assessment, admitted use, search/index projection, run binding. Это роли уже существующих артефактов/owners, не шесть новых универсальных DTO. Byte hash не заменяет manifest kind/media/profile, source occurrence, tenant custody и смысл. Одинаковые bytes могут иметь разные lawful uses и разные provenance occurrences.

## 2. Физические области и владельцы

| Область | Содержимое и существующий owner | Placement и жизненный цикл |
|---|---|---|
| Connector attempt/quarantine | Части fetch, временный decode, remote lease; Fabric capture/data-plane + Runtime intent | Private scoped scratch, hard size/time bound, durable checkpoint refs. Incomplete не попадает в admitted catalog. Temp тоже copy с правами и cleanup receipt. |
| Immutable source/derivatives | Core `ArtifactRef`/manifest, `FileSystemCAS` или проверенный backend | Exact payload/member + profile/lineage. Authorized raw, normalized tables/text, method/calibration releases. Retention решается до write, а не «CAS хранит всё». |
| Mutable coordination | `control_plane_store.py`, source frontiers, catalog heads, native claim ledger | Транзакционный owner store; indexes и outbox в своих boundaries. Bytes сначала устойчивы и проверены, затем head/receipt фиксируются; нет фиктивной общей SQL+CAS transaction. |
| Domain read models | DataForge prepared assets, Lex/Scholar/Foundry/Scientist owned stores | Native representation и explicit release binding. Таблица, граф, vector index или model checkpoint выбираются по access pattern; каждый производный объект связан с исходной generation. |
| Query accelerators | Semantic catalog, lexical/vector indexes, materialized views, bounded local cache | Rebuildable где возможно; не source of truth и не единственное место provenance. Keys включают semantics/visibility/generation. Private metadata тоже защищается. |
| Task/run | Selected immutable refs, source cut, method/config, evidence/use decisions, results | Run ссылается на общие разрешённые objects; tenant/private bindings и trace отдельно. Исторический replay не подменяется current catalog head. |
| Audit/operational logs | Minimized event IDs, error classes, effect/cursor receipts, dependency edges | Owner journal доказательных событий отдельно от sampling telemetry. Query strings, prompts, raw rows и signed URLs по умолчанию не обычные logs. |
| Credentials | Existing auth/connector secret resolution; deployment secret store | Вне source cards, CAS, prompts и export. В записи только opaque credential binding, не secret value. |
| Backup/export/cold tier | Разрешённые recoverable copies с inventory и внешним rollback witness | Отдельный failure domain; backup не новая authority. Restore проходит reconciliation прав/withdrawals перед serving. |

**Фактические FS/config seams @C:** `core/artifacts/store.py::FileSystemCAS` документирует `<root>/artifacts/sha256/ab/cd/<hex>.blob`, `.manifest.json`, optional `.sig`. `core/artifacts/backends/config.py` читает `POLISYOS_CAS_ROOT`; default — `.polisyos/cas` относительно cwd. `fabric/storage/tenant_cas.py::tenant_scoped_cas_root` формирует `<root>/tenants/<tenant>`, а `TenantSidecarScope` задаёт scoped cache/cursor locality. Production deployment должен задавать absolute managed roots; эти runtime данные не хранятся под Git `docs/` или рядом с исходниками как неявное durable хранилище.

Factory знает `filesystem`, `s3`, `gcs`, `cached_s3`, `cached_gcs`, bucket/prefix/region/local-cache settings. **В @C explicit tenant/cell ownership разрешён factory только для filesystem**; остальным он отказывает. Нельзя убрать scope, чтобы «включить облако». `S3ArtifactStore` использует conditional create (`IfNoneMatch`) и readback существующего object, но `_get_object_bytes` читает body целиком. Наличие S3 backend не подтверждает memory bound для больших members, distributed ownership parity или end-to-end readiness.

Local state layout уже регулируется `policy-engine/architecture/runtime_state_layout.toml` (G base этого пакета): registered slots, migration/readers и retention/cleanup boundaries. Новое размещение должно расширять этот owner contract, а не создавать неучтённый `.polisyos/library`. Mutable heads/projections отделяются от append-only claim/event history; SQL storage не разрешает переписывать прошлое.

Пример размещения, не новые env vars/API: выделенный persistent volume для FS CAS; отдельный volume/DSN control store; bounded encrypted scratch; rebuildable index volume; secret mount; разрешённый backup target. Фактический путь каждого owner фиксируется в deployment inventory, включая sidecars, provider files и frontend/download caches. Если adapter пишет скрытую копию вне inventory, supported retention scope не установлен.

## 3. Runtime→библиотека: три независимых решения

1. **Сохранить capture.** До получения проверить разрешённые storage/processing locations и resource budget. Commit только complete selected capture; partial pages сохраняются как incomplete attempt с ограниченной retention, не complete dataset. Если raw хранить нельзя, выбрать разрешённый transient/remote маршрут, не бессрочный encrypted cache «на всякий случай».
2. **Сделать обнаруживаемым.** Зарегистрировать source occurrence, descriptor, completeness bounds, provenance и allowed audience в existing catalog/owner. Discovery publication атомарно связана с durable refs и index generation. Private result может быть reusable только внутри своего scope. Shared/public promotion — отдельная visibility/rights decision, не rename каталога.
3. **Использовать в новой задаче.** Resolver повторно проверяет exact ref/content/profile, действующие права, applicability/currentness выбранного claim, метод/популяцию/единицы и dependence. Старый admission, search rank, успех предыдущего run или авторитет создавшего агента не переносятся автоматически.

Эти решения могут быть автоматическими для заранее выбранного source class и проверяемого правила. Ручная проверка каждого легально открытого statistical release не обязательна. Ручной input нужен, когда отсутствует реальный внешний акт/неоднозначная authority; researcher может проверить доступные каналы, но не создать его своим выводом. Ошибка consumer/profile не маскируется как отсутствие external authority.

### Composite outputs: полная связь с родителями

Join, synthesis, embedding, model или aggregate из нескольких источников связывает **полный набор material computational parents** через immutable refs/manifest roots, включая существенные selector/model/rule generations и set/negative dependencies. Это не копия всего transitive corpus. Native owner проверяет actual producer input closure; неизвестное влияние, например непроверенная provenance чужой pretrained модели, сохраняется как соответствующая limitation, а не выдуманная полная lineage.

Перед расширением discovery audience, remote submission, новым use или disclosure rights/domain owners проверяют exact transform/output/purpose/recipient против применимых оснований **всех существенных родителей** либо проверенного правила, прямо разрешающего выбранный derivative/aggregate. Разрешение каждого input в отдельности не разрешает их join; один открытый parent не очищает restricted parent. Универсальное пересечение licence strings тоже неверно: permitted aggregate может иметь собственный законный режим при запрете raw export. Producer label `public`/`anonymized` и tenant совпадение не достаточны; output-level rule и его discriminator должны проверяться.

При unknown output rule результат не становится discoverable за пределами уже разрешённого scope и не получает protected use. Реальный validated derivative grant разрешает только bound recipient/purpose. Parent revoke/correction/retirement проходит native dependency reaction с учётом применимости: это не автоматическое удаление всех производных на любую смену terms. Existing index/root verification и fences могут амортизировать проверку, но не пропускать parent или stale rule. Future falsifier: restricted microdata + public table → join/aggregate → попытка shared index/API/export, затем parent change и restore; разрешён только independently verified permitted output, не произвольный derived payload.

### Совокупное раскрытие

Output rights и confidentiality composition — разные predicates. Два разрешённых aggregates по пересекающимся populations могут раскрыть индивидуальный факт через разность. Source/custodian owner задаёт protected unit, overlap/lineage между releases/aliases, recipient/cooperation scope, поддержанный query/output mechanism и composition rule. Все result paths и retries используют один accounting boundary для этого scope; clock reset, новый run/dataset label/cell/key не создаёт новый privacy budget. Установленное shared grant допускает cross-cell reuse через тот же boundary; чужая cell не запрещена только своим именем.

Не изобретать универсальный epsilon или ledger всех человеческих disclosure. Для DP-гарантии единица защиты и композиция обязательны; это подтверждает [NIST SP800-226 §§2.4,4.1](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-226.pdf). Для иных disclosure правил нужен их собственный discriminator. Неподтверждённый overlap не трактуется как disjointness; выбранный консервативный bound или refusal защищённого result предпочтительнее ложного privacy claim. Перед disclosure reserve/commit учёт атомарен относительно конкурирующих запросов; timeout с неизвестной выдачей не возвращает allowance автоматически. Повтор уже разрешённого идентичного protected output не становится новым raw query; новые noisy samples или audience expansion проверяются по applicable rule. Не переносить эту гарантию на неконтролируемые внешние disclosures.

Future AP07: overlapping releases и aliases в разных runs проходят один composition owner, явный разрешённый share работает, превышение выбранного bound — нет. Remove shared binding, сохранив permissions/labels: отрицательный сценарий должен различиться. Общая цепочка пока проектируется; факт наличия бюджета в prose не runtime capability.

## 4. Матрица сохранения

| Runtime объект | Что сохранять при разрешении | Что не переносится в следующий use |
|---|---|---|
| Официальный документ/release | Exact representation, source version/section, retrieval cut, applicable licence, native relations; permitted original + parsed derivative | Current applicability, legal interpretation, approval конкретного решения |
| Mutable API/query slice | Exact request semantics без secrets, source snapshot/receipt, selected rows/aggregate, coverage и execution identity | Полнота всего dataset; неизменность remote source; другой tenant/query с тем же URL |
| Закрытые microdata | В разрешённой cell, либо только custodian result/receipt при запрете export; минимально необходимый slice | Автоматическое попадание в общую search library или обучение; digest может быть sensitive |
| Query-only licensed source | Разрешённый query/result/metadata receipt, допустимый cache TTL или отсутствие cache | Raw mirror, perpetual replay или downstream redistribution. Если exact replay невозможен — limitation, а не фальшивый immutable input |
| Web/LLM research | Разрешённые original captures, cited spans, search selections и candidate extraction; LLM payload только в permitted trace | Truth/authority из summary; независимость двух пересказов; включение prompt в public audit |
| Model/metric/calibration | Versioned method/config/parameters и native inputs; reproducible recipe где возможен | Applicability к новой population, threshold authority, независимость test data |
| Remote/evaluator receipt | Проверяемая связь с input snapshot/executable/config и реальным issuer, допустимый output | Верность underlying raw, если она не проверена; независимость evaluator без соответствующего основания |
| Empty/failed search | Minimized attempt: request scope, provider/version/cut, error/coverage, retry boundary | «Оснований нет». Negative cache ограничен конкретным запросом и свежестью, outage не durable absence |
| Denied/revoked capture | Минимально допустимые no-retry/deletion/withdrawal bindings для recovery | Сам запрещённый payload «для аудита», прежний green status или resurrect после restore |
| Synthetic/sample/approximation | Generator/seed/method и declared purpose, exact sampled selection если допустимо | Подмена measured/authentic data, full-population inference или exact answer |

Сохранение для повторного retrieval **не означает разрешение на model training**. Training, embeddings, evaluation, query acceleration и publication — различные uses и derivative dependencies. Отозванный источник не доказывает ни автоматическое забывание из модели, ни необходимость удалить всякую модель: проверить actual permission, contribution/dependency и поддержанную реакцию, сохраняя unknown influence явно.

## 5. Dedup, updates, retention и экономия

- Physical dedup допустим внутри согласованной trust/rights boundary, при отдельных access/retention references. Межтенантное content-existence/timing leakage и конфликт erasure/WORM требуют отдельного решения; глобальный hash cache не default.
- Catalogue head «latest» — discovery alias. Selected run получает immutable version/root и source-native coverage. Изменение только licence/applicability может требовать re-admission без изменения payload bytes.
- Для одного dataset хранить canonical authorized partitions и reuse refs, а не full copy/run. Materialize дорогое преобразование, если законно и ожидаемый повторный cost оправдывает storage/refresh/verification. Это optimization после eligibility.
- Минимально сохранить то, от чего зависит подписанный claim, в разрешённом объёме и сроке. Если custody obligation несовместима с доступным retention, ограничить/отказать соответствующей publishable claim либо выбрать другой permitted verification route. Нельзя обещать perpetual replay только на URL.
- Непопулярный материал: снять optional index/cache, затем разрешённая tier migration/retirement. Proof-relevant bytes/receipts не удаляются по одному LRU. «Immutable» значит отсутствие перезаписи истории, а не обязательное вечное хранение каждого payload.
- Retention содержит срок/trigger/owner/legal hold/возможность re-fetch; renewal не бесконечный по факту доступа. Storage pressure вызывает bounded pause/defer, permitted eviction и explicit limitation, не silent evidence loss.
- Холодный tier экономит storage, но retrieval latency/fees/temporary disk/verification входят в план. Пока bytes не доступны и не проверены, наличие manifest не означает готовность consumer.

## 6. Multi-store и масштабирование

Metadata/control DB хранит heads, jobs, leases, relations и indexes подходящего размера; object/FS layer — immutable payloads; analytical table engine — большие scan/join, vector/lexical views — retrieval. Не переносить все payloads в PostgreSQL и не превращать bucket listing в transactional catalog. Новая graph DB не обязательна только потому, что отношения графовые; сначала native read paths и measured access pattern.

Для многопользовательских partitioned tables Iceberg может стать **adapter к существующему dataset owner**, если появятся реальные multi-writer/snapshot/maintenance требования. Его snapshot/manifest model полезен для согласованных table versions; он не заменяет source provenance, rights, Claim ledger или историческую доступность после snapshot expiry. Это опция исследования, не выбранная зависимость. [Iceberg specification](https://iceberg.apache.org/spec/).

S3 conditional writes и GCS generation preconditions дают object-level concurrency primitives, а не транзакцию между bucket, SQL, источником и PolicyOS claim. В adapter нужно сохранить existing immutable conflict verification и owner publication protocol. ETag/generation — provider token, не универсальный semantic digest. [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html), [GCS preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions).

Перенос FS→remote выполняется через staging, copy verification, capability parity и контролируемый cutover с сохранением refs/ownership/generations; старый store остаётся read-only до доказанного завершения допустимых readers/restore paths. Изменение locator не меняет identity. Нельзя dual-write mutable head без выбранного owner. Restore/GC/disclosure races и active reader copies регулируются [canonical protocols](../lifecycle/05-implementation-protocols.md), а memory/spill/cold recovery — [resource design](../lifecycle/09-resource-execution-design.md).

Pattern pass: P04/P05/P07/P08/P14/P27/P31/P32/P37/P38. Acceptance: runtime capture реально обнаруживается вторым разрешённым run, новый use проходит свою проверку, запрещённый scope не видит payload/metadata, correction или revoke меняет fresh consumer. Отдельные negative controls на same bytes/different rights, wrong profile, expired source, missing member, cache bypass и restored revoked version. Всё UNRUN.
